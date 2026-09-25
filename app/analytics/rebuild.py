"""DB inputs and the sole writer of the derived session/attendance tables."""
from collections import defaultdict
import dataclasses
from datetime import datetime

from sqlalchemy import insert
from sqlalchemy.orm import joinedload, selectinload

from app.analytics import SESSION_CHANNELS
from app.analytics.corrections import load_corrections
from app.analytics.drafts import AppPractice, ArchivedMessage, LocationRef, SeasonRef
from app.analytics.history_config import load_history_config
from app.analytics.lineage import build_lineage
from app.analytics.models import PracticeAttendance, PracticeSession, SlackArchiveMessage
from app.models import AppConfig, Season, SlackUser, User, db
from app.practices.models import Practice, PracticeLead, PracticeLocation, PracticeRSVP


def load_inputs() -> tuple[list[ArchivedMessage], list[AppPractice], list[LocationRef], list[SeasonRef]]:
    """Read DB snapshots for the pure lineage builder, without network access."""
    archive = SlackArchiveMessage.query.filter(
        SlackArchiveMessage.channel_id.in_(SESSION_CHANNELS)
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


def _session_row(draft, rebuilt_at):
    """Map persisted draft fields explicitly; parsing-only fields stay pure."""
    return PracticeSession(
        session_key=draft.session_key, group_key=draft.group_key, era=draft.era,
        kind=draft.kind, source_message_id=draft.source_archive_id, practice_id=draft.practice_id,
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
        result = build_lineage(*load_inputs(), cfg, corrections)
        user_ids = dict(db.session.query(SlackUser.slack_uid, User.id).join(
            User, User.slack_user_id == SlackUser.id).all())
        rebuilt_at = datetime.utcnow()
        session_rows = [_session_row(draft, rebuilt_at) for draft in result.sessions]

        PracticeAttendance.query.delete(synchronize_session="fetch")
        PracticeSession.query.delete(synchronize_session="fetch")
        db.session.add_all(session_rows)
        db.session.flush()
        session_ids = {row.session_key: row.id for row in session_rows}
        attendance = [dict(
            session_id=session_ids[draft.session_key], slack_uid=draft.slack_uid,
            person_key=f"slack:{draft.slack_uid}",
            user_id=user_ids.get(draft.slack_uid), role=draft.role,
            emoji=draft.emoji, slot=draft.slot, source=draft.source,
        ) for draft in result.attendance]
        if attendance:
            db.session.execute(insert(PracticeAttendance), attendance)
        from app.analytics.weather import apply_weather
        apply_weather(session_rows)
        stats = {"sessions": len(session_rows), "attendance": len(attendance),
                 "needs_review": sum(row.needs_review for row in session_rows),
                 "possible_misses": result.possible_misses}
        if commit:
            db.session.commit()
        else:
            db.session.flush()
        return stats
    except Exception:
        db.session.rollback()
        raise


def flagged_sessions() -> list[PracticeSession]:
    return PracticeSession.query.filter_by(needs_review=True).order_by(
        PracticeSession.date, PracticeSession.session_key).all()
