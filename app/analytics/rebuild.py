"""DB inputs and the sole writer of the derived session/attendance tables."""
from collections import defaultdict
import dataclasses
from datetime import datetime

from sqlalchemy import insert, tuple_
from sqlalchemy.orm import joinedload, selectinload

from app.analytics import LINEAGE_CHANNELS
from app.analytics.corrections import load_corrections
from app.analytics.coverage import empty_weeks
from app.analytics.drafts import AppPractice, ArchivedMessage, LocationRef, SeasonRef, TripSignup
from app.analytics.history_config import load_history_config
from app.analytics.lineage import build_lineage
from app.analytics.models import PracticeAttendance, PracticeSession, SlackArchiveMessage
from app.analytics.parse_trips import edition_year, normalize_name
from app.models import AppConfig, Season, SlackUser, Trip, User, db
from app.practices.models import Practice, PracticeLead, PracticeLocation, PracticeRSVP
from app.trips.models import TripRegistration, TripSeries
from app.utils import utc_naive_to_central_naive


def load_inputs() -> tuple[list[ArchivedMessage], list[AppPractice], list[LocationRef], list[SeasonRef]]:
    """Read DB snapshots for the pure lineage builder, without network access."""
    archive = SlackArchiveMessage.query.filter(
        SlackArchiveMessage.channel_id.in_(LINEAGE_CHANNELS)
    ).order_by(SlackArchiveMessage.channel_id, SlackArchiveMessage.ts).all()
    replies = defaultdict(list)
    for row in archive:
        if row.thread_ts is not None and row.thread_ts != row.ts and row.deleted_at is None:
            replies[(row.channel_id, row.thread_ts)].append(row.raw)
    # Keep every archived row available for rsvp_from. Lineage only parses
    # top-level posts (thread_ts absent or equal to ts) as template sessions.
    messages = [ArchivedMessage(
        channel_id=row.channel_id, ts=row.ts, raw=row.raw,
        replies=tuple(replies[(row.channel_id, row.ts)])
        if row.thread_ts is None or row.thread_ts == row.ts else (),
        deleted=row.deleted_at is not None, archive_id=row.id,
    ) for row in archive]

    leads = defaultdict(list)
    coaches = defaultdict(list)
    assignments = db.session.query(PracticeLead.practice_id, PracticeLead.role, SlackUser.slack_uid).join(
        User, PracticeLead.user_id == User.id
    ).join(SlackUser, User.slack_user_id == SlackUser.id).order_by(PracticeLead.id).all()
    for practice_id, role, uid in assignments:
        if role == "lead":
            leads[practice_id].append(uid)
        elif role == "coach":
            coaches[practice_id].append(uid)
    buttons = defaultdict(list)
    rsvps = db.session.query(PracticeRSVP.practice_id, SlackUser.slack_uid).join(
        User, PracticeRSVP.user_id == User.id
    ).join(SlackUser, User.slack_user_id == SlackUser.id).filter(
        PracticeRSVP.status == "going"
    ).order_by(PracticeRSVP.id).all()
    for practice_id, uid in rsvps:
        buttons[practice_id].append(uid)
    practices = Practice.query.options(
        joinedload(Practice.location), selectinload(Practice.activities), selectinload(Practice.practice_types)
    ).order_by(Practice.id).all()
    app_practices = [AppPractice(
        id=row.id, date=row.date, status=row.status, is_draft=row.is_draft,
        slack_channel_id=row.slack_channel_id, slack_message_ts=row.slack_message_ts,
        slack_session_emoji=row.slack_session_emoji,
        location_name=row.location.name if row.location else None,
        location_spot=row.location.spot if row.location else None,
        activities=tuple(activity.name for activity in sorted(row.activities, key=lambda item: item.id)),
        types=tuple(kind.name for kind in sorted(row.practice_types, key=lambda item: item.id)),
        lead_uids=tuple(leads[row.id]), coach_uids=tuple(coaches[row.id]),
        plan_emoji=tuple(reaction["emoji"] for reaction in row.plan_reactions or []),
        button_rsvp_uids=tuple(buttons[row.id]),
    ) for row in practices]
    locations = [LocationRef(row.id, row.name, row.spot, row.latitude, row.longitude)
                 for row in PracticeLocation.query.order_by(PracticeLocation.id).all()]
    seasons = [SeasonRef(row.name, row.start_date, row.end_date)
               for row in Season.query.filter(Season.season_type != "legacy").order_by(Season.id).all()]
    return messages, app_practices, locations, seasons


def load_app_trip_signups() -> list[TripSignup]:
    rows = db.session.query(TripRegistration.id, TripSeries.slug, Trip.start_date, SlackUser.slack_uid,
                            User.id).join(
        Trip, TripRegistration.trip_id == Trip.id).join(
        TripSeries, Trip.series_id == TripSeries.id).join(
        User, TripRegistration.user_id == User.id).outerjoin(
        SlackUser, User.slack_user_id == SlackUser.id).filter(
        TripRegistration.status != "cancelled").order_by(TripRegistration.id).all()
    return [TripSignup(slug, edition_year(start.date() if hasattr(start, "date") else start),
                       start.date() if hasattr(start, "date") else start,
                       uid, None, f"trip_registration:{rid}", user_id)
            for rid, slug, start, uid, user_id in rows]


def load_people() -> dict:
    """Slack uid to user, and full names that belong to exactly one member."""
    rows = db.session.query(User.id, User.first_name, User.last_name, SlackUser.slack_uid).outerjoin(
        SlackUser, User.slack_user_id == SlackUser.id).all()
    by_name = defaultdict(set)
    for user_id, first, last, uid in rows:
        by_name[normalize_name(f"{first} {last}")].add((user_id, uid))
    return {"uid_to_user": {uid: user_id for user_id, _, _, uid in rows if uid},
            "name_to_member": {name: next(iter(members)) for name, members in by_name.items()
                               if len(members) == 1}}


def resolve_people(rows, people) -> list[dict]:
    resolved = {}
    for row in rows:
        uid, user_id, unmatched = row.slack_uid, row.user_id, False
        if user_id is None:
            member = people["name_to_member"].get(normalize_name(row.person_name)) if row.person_name else None
            if member:
                user_id, member_uid = member
                uid = member_uid or uid
        if uid:
            person_key = f"slack:{uid}"
            user_id = user_id or people["uid_to_user"].get(uid)
        elif user_id:
            person_key = f"user:{user_id}"
        else:
            person_key, unmatched = f"name:{normalize_name(row.person_name)}", True
        key = (row.session_key, person_key, row.role, row.emoji, row.slot if row.emoji is None else None)
        resolved.setdefault(key, dict(
            session_key=row.session_key, slack_uid=uid, user_id=user_id, person_key=person_key,
            role=row.role, emoji=row.emoji, slot=row.slot, source=row.source, unmatched=unmatched))
    return list(resolved.values())


def _session_row(draft, rebuilt_at):
    """Map persisted draft fields explicitly; parsing-only fields stay pure."""
    return PracticeSession(
        session_key=draft.session_key, group_key=draft.group_key, era=draft.era,
        kind=draft.kind, category=draft.category, reported_count=draft.reported_count,
        source_message_id=draft.source_archive_id, practice_id=draft.practice_id,
        date=draft.date, start_time=draft.start_time, day_of_week=draft.day_of_week,
        season_label=draft.season_label, location_id=draft.location_id,
        location_name=draft.location_name, lat=draft.lat, lon=draft.lon, is_indoor=draft.is_indoor,
        activity=draft.activity, activities=draft.activities,
        workout_type=draft.workout_type, workout_types=draft.workout_types, title=draft.title,
        format=draft.format, slot=draft.slot, rsvp_emoji=draft.rsvp_emoji, status=draft.status,
        rsvp_count=draft.rsvp_count, flags=draft.flags, needs_review=draft.needs_review,
        rebuilt_at=rebuilt_at,
    )


def load_rebuild_config(cfg=None):
    """Load rules plus DB coach emoji for both rebuild and read-only reports."""
    cfg = load_history_config() if cfg is None else cfg
    return dataclasses.replace(
        cfg, coach_emoji=frozenset(AppConfig.get("analytics_coach_emoji", []) or []))


def rebuild(*, cfg=None, commit=True) -> dict:
    """Replace both derived tables atomically; optionally leave commit to caller."""
    # Configuration errors must not roll back the caller's existing work either.
    cfg = load_history_config() if cfg is None else cfg
    try:
        corrections = load_corrections()
        cfg = load_rebuild_config(cfg)
        result = build_lineage(*load_inputs(), cfg, corrections, trip_signups=load_app_trip_signups())
        people = resolve_people(result.attendance, load_people())
        unmatched = {row["session_key"] for row in people if row["unmatched"]}
        signups = defaultdict(set)
        for row in people:
            if row["role"] == "signup":
                signups[row["session_key"]].add(row["person_key"])
        for draft in result.sessions:
            if draft.kind == "trip":
                draft.rsvp_count = len(signups[draft.session_key])
            if draft.session_key in unmatched:
                draft.flags = [*draft.flags, "unmatched_person"]
        rebuilt_at = datetime.utcnow()
        session_rows = [_session_row(draft, rebuilt_at) for draft in result.sessions]

        PracticeAttendance.query.delete(synchronize_session="fetch")
        PracticeSession.query.delete(synchronize_session="fetch")
        db.session.add_all(session_rows)
        db.session.flush()
        session_ids = {row.session_key: row.id for row in session_rows}
        attendance = [dict(session_id=session_ids[row["session_key"]],
                           **{k: row[k] for k in ("slack_uid", "user_id", "person_key", "role",
                                                  "emoji", "slot", "source")})
                      for row in people]
        if attendance:
            db.session.execute(insert(PracticeAttendance), attendance)
        from app.analytics.weather import apply_weather
        apply_weather(session_rows)
        weeks = empty_weeks(result.sessions, corrections)
        AppConfig.set("analytics_coverage", coverage_snapshot(result.possible_misses, weeks),
                      category="analytics")
        stats = {"sessions": len(session_rows), "attendance": len(attendance),
                 "needs_review": sum(row.needs_review for row in session_rows),
                 "possible_misses": result.possible_misses,
                 "candidates": len(result.possible_misses), "empty_weeks": len(weeks)}
        if commit:
            db.session.commit()
        else:
            db.session.flush()
        return stats
    except Exception:
        db.session.rollback()
        raise


def coverage_snapshot(candidate_keys, weeks) -> dict:
    pairs = [tuple(key.split(":", 1)) for key in candidate_keys]
    rows = {f"{row.channel_id}:{row.ts}": row for row in SlackArchiveMessage.query.filter(
        tuple_(SlackArchiveMessage.channel_id, SlackArchiveMessage.ts).in_(pairs)).all()} \
        if candidate_keys else {}
    candidates = []
    for key in candidate_keys:
        row = rows.get(key)
        text = next((line for line in (row.text if row else "").splitlines() if line.strip()), "")
        reactions = sorted((row.raw.get("reactions", []) if row else []),
                           key=lambda r: -r.get("count", 0))[:3]
        candidates.append({"post_key": key, "channel": key.split(":")[0],
                           "date": utc_naive_to_central_naive(row.posted_at).date().isoformat() if row else "",
                           "text": text[:140],
                           "reactions": {r["name"]: r.get("count", 0) for r in reactions}})
    return {"computed_at": datetime.utcnow().isoformat(timespec="seconds"),
            "candidates": candidates, "empty_weeks": [week.isoformat() for week in weeks]}


def flagged_sessions() -> list[PracticeSession]:
    return PracticeSession.query.filter_by(needs_review=True).order_by(
        PracticeSession.date, PracticeSession.session_key).all()
