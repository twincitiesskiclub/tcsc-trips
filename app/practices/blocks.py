"""Two-week practice blocks.

Every other Monday, a week before a block starts, the block job creates the
block's sessions and its poll row (DRAFT) and posts the block post in
#practices-core. Someone on the practices team presses Open poll,
which posts the leads poll. The block post then shows coverage and an Assign
button per session. When the team is done assigning, Post schedule to leads
posts the leads' copy in #coord-practices-leads-assists, and every block
post refresh updates it from then on.

The job acts on state, not on the day it runs, so a missed Monday is caught
the next morning. It never creates a block that starts before the anchor:
the block running at cutover (Oct 12 to 25) is made by the cutover script.
"""

from datetime import date, datetime, timedelta

from flask import current_app
from sqlalchemy.exc import OperationalError

from app.models import AppConfig, db
from app.practices.availability import (
    FIRST_NUDGE_AFTER_DAYS,
    MAX_NUDGES,
    MIN_DAYS_BETWEEN_NUDGES,
    PollNotReadyError,
    block_practices,
    create_block_poll,
    eligible_leads,
    map_sessions,
    open_poll,
)
from app.practices.availability_emoji import EmojiSupplyError
from app.practices.availability_models import (
    LeadAvailabilityParticipant,
    LeadAvailabilityPoll,
    LeadAvailabilityResponse,
    ParticipantStatus,
    PollStatus,
)
from app.practices.drafting import generate_draft_block
from app.practices.interfaces import PracticeStatus
from app.slack.client import get_slack_client
from app.slack.practices._config import COORD_CHANNEL_ID, PRACTICES_CORE_CHANNEL_ID
from app.utils import now_central_naive, today_central

BLOCK_DAYS = 14
DEFAULT_ANCHOR = date(2026, 10, 26)
POST_DAYS_AHEAD = 7       # block post goes up the Monday before
REMINDER_DAYS_AHEAD = 5   # Wednesday of the post week


def block_anchor() -> date:
    raw = AppConfig.get("lead_availability.block_anchor")
    if not raw:
        return DEFAULT_ANCHOR
    try:
        return date.fromisoformat(str(raw))
    except ValueError:
        current_app.logger.warning(
            "lead_availability.block_anchor %r is not an ISO date; using %s",
            raw, DEFAULT_ANCHOR)
        return DEFAULT_ANCHOR


def block_start_for(day: date, anchor: date) -> date:
    """Monday that starts the block containing `day`. Pure date math, so DST
    and year boundaries cannot shift it."""
    return day - timedelta(days=(day - anchor).days % BLOCK_DAYS)


def blocks_due(today: date, anchor: date) -> list[date]:
    """Block starts the job should handle today: the current block, and the
    next one from its post day on. Never a block before the anchor."""
    current = block_start_for(today, anchor)
    upcoming = current + timedelta(days=BLOCK_DAYS)
    due = [current]
    if today >= upcoming - timedelta(days=POST_DAYS_AHEAD):
        due.append(upcoming)
    return [start for start in due if start >= anchor]


def poll_for_date(day: date):
    """The block poll whose range covers `day`, if one exists."""
    return (
        LeadAvailabilityPoll.query
        .filter(LeadAvailabilityPoll.starts_on <= day,
                LeadAvailabilityPoll.ends_on >= day)
        .order_by(LeadAvailabilityPoll.created_at.desc())
        .first()
    )


def ensure_block(start: date, today: date) -> dict:
    """Bring one block up to date: sessions, poll row, block post, reminder."""
    end = start + timedelta(days=BLOCK_DAYS - 1)
    poll = LeadAvailabilityPoll.query.filter_by(starts_on=start, ends_on=end).first()
    if poll is None:
        generate_draft_block(start, end)
        if not block_practices(start, end):
            current_app.logger.error(
                "Block %s..%s has no practices and practice_days yields no "
                "slots for it; no block post", start, end)
            return {"start": start, "skipped": "no_sessions"}
        poll = create_block_poll(start, end)

    posted = False
    if poll.block_post_ts is None:
        posted = post_block_post(poll)

    reminded = False
    if (
        poll.status == PollStatus.DRAFT
        and poll.wednesday_reminder_sent_at is None
        and today >= start - timedelta(days=REMINDER_DAYS_AHEAD)
    ):
        reminded = post_wednesday_reply(poll)

    return {"start": start, "poll_id": poll.id, "posted": posted, "reminded": reminded}


def run_block_job(today: date | None = None) -> list[dict]:
    today = today or today_central()
    results = []
    for start in blocks_due(today, block_anchor()):
        try:
            results.append(ensure_block(start, today))
        except Exception as exc:  # noqa: BLE001 - one block must not stop the next
            db.session.rollback()
            current_app.logger.exception("Block job failed for block %s", start)
            results.append({"start": start, "error": str(exc)})
    return results


def _lock_poll(poll_id: int):
    """Lock the poll row until the next commit or rollback, or None if it's taken.

    A second click while the first is in flight fails NOWAIT. A crash rolls
    the transaction back, so nothing gets stuck. populate_existing() matters:
    without it a caller that already loaded the poll reads stale columns
    under the lock and acts twice (reproduced in review).
    """
    try:
        return (
            LeadAvailabilityPoll.query
            .filter_by(id=poll_id)
            .populate_existing()
            .with_for_update(nowait=True)
            .one()
        )
    except OperationalError:
        db.session.rollback()
        return None


def open_block_poll(poll_id: int, opened_by_slack_uid: str | None) -> dict:
    """Post the leads poll for a block. Exactly one caller wins.

    The row lock is held through the Slack post and released by open_poll's
    commit (or our rollback); a click after that sees status open.
    """
    poll = _lock_poll(poll_id)
    if poll is None:
        return {"success": False, "error": "Someone is opening this poll right now."}

    if poll.status != PollStatus.DRAFT:
        who = f"<@{poll.opened_by_slack_uid}>" if poll.opened_by_slack_uid else "Someone"
        db.session.rollback()
        return {"success": False, "already_open": True,
                "error": f"{who} already opened this poll."}

    try:
        map_sessions(poll)
    except (PollNotReadyError, EmojiSupplyError) as exc:
        db.session.rollback()
        return {"success": False, "error": str(exc)}

    poll.opened_by_slack_uid = opened_by_slack_uid
    result = open_poll(poll)
    if not result.get("success"):
        db.session.rollback()
        return result

    refresh_block_post(poll)
    return result


# --- Slack side: implemented in Task B5. Module-level so tests can patch. ---

def _render(poll, *, exclude_practice_id=None) -> tuple[list[dict], str]:
    from app.slack.blocks.block_post import block_range_label, build_block_post
    from app.slack.practices.availability_nudge import poll_permalink

    permalink = poll_permalink(poll) if poll.message_ts else None
    rows = block_post_rows(poll, exclude_practice_id=exclude_practice_id)
    rendered = build_block_post(poll, rows, permalink=permalink,
                                footer=footer_text(poll, today_central()))
    return rendered, f"Lead poll {block_range_label(poll.starts_on, poll.ends_on)}"


def _render_schedule(poll, *, exclude_practice_id=None) -> tuple[list[dict], str]:
    from app.slack.blocks.block_post import build_lead_schedule, lead_schedule_text

    rows = block_post_rows(poll, exclude_practice_id=exclude_practice_id)
    now = now_central_naive()
    return build_lead_schedule(poll, rows, now=now), lead_schedule_text(poll, rows, now=now)


def post_lead_schedule(poll_id: int) -> dict:
    """Post the block's lead schedule to the leads channel. Exactly one caller wins.

    After this, refresh_block_post keeps the schedule current.
    """
    poll = _lock_poll(poll_id)
    if poll is None:
        return {"success": False, "error": "Someone is posting this schedule right now."}
    if poll.schedule_ts:
        db.session.rollback()
        return {"success": False, "error": "The schedule is already posted."}
    try:
        rendered, text = _render_schedule(poll)
        ts = get_slack_client().chat_postMessage(
            channel=COORD_CHANNEL_ID, blocks=rendered, text=text,
            unfurl_links=False, unfurl_media=False)["ts"]
    except Exception as exc:  # noqa: BLE001 - never raise; the button stays for a retry
        db.session.rollback()
        current_app.logger.warning("Lead schedule for poll %s failed: %s", poll_id, exc)
        return {"success": False, "error": "Could not post the schedule. Try again."}
    poll.schedule_ts = ts
    db.session.commit()
    refresh_block_post(poll)
    return {"success": True, "ts": ts}


NOT_IN_POOL = "Leading is open to the lead pool. Want in? Ask in this thread."


def _signup_refusal(practice, user_id: int) -> str | None:
    """Why this user can't take this session right now, or None if they can."""
    if practice is None:
        return "That practice is gone."
    if practice.status == PracticeStatus.CANCELLED.value:
        return "That practice was cancelled."
    if practice.date <= now_central_naive():
        return "That practice already started."
    if any(l.user_id == user_id for l in practice.leads):
        return "You're already on it."
    if sum(1 for l in practice.leads if l.role == "lead") >= (practice.leads_needed or 2):
        return "Just filled, thanks!"
    return None


def _post_signup_reply(practice, slack_uid: str, partners) -> None:
    from app.slack.blocks.block_post import join_names

    poll = poll_for_date(practice.date.date())
    if poll is None or not poll.schedule_ts:
        return
    when = practice.date
    text = (f":raised_hands: <@{slack_uid}> is leading {when.strftime('%a %-m/%-d')} · "
            f"{when.strftime('%-I:%M%p').replace('PM', 'p').replace('AM', 'a')}")
    if partners:
        text += f" with {join_names(_mention(u) for u in partners)}"
    try:
        get_slack_client().chat_postMessage(
            channel=COORD_CHANNEL_ID, thread_ts=poll.schedule_ts, text=text)
    except Exception as exc:  # noqa: BLE001 - never raise; the sign-up stands
        current_app.logger.warning("Sign-up reply for practice %s failed: %s", practice.id, exc)


def sign_up_as_lead(practice_id: int, slack_uid: str) -> dict:
    """The Lead button: add the clicker as a lead if the session still needs one.

    The practice row is locked NOWAIT (with populate_existing, see _lock_poll)
    so two clicks on the last spot can't both win.
    """
    from app.models import SlackUser
    from app.practices.models import Practice, PracticeLead
    from app.slack.practices import refresh_practice_posts

    slack = SlackUser.query.filter_by(slack_uid=slack_uid).first()
    user = slack.user if slack else None
    if user is None or user.id not in {u.id for u in eligible_leads()}:
        return {"success": False, "error": NOT_IN_POOL}
    try:
        practice = (Practice.query.filter_by(id=practice_id).populate_existing()
                    .with_for_update(nowait=True).one_or_none())
    except OperationalError:
        db.session.rollback()
        return {"success": False, "error": "Someone just signed up. Try again in a second."}
    refusal = _signup_refusal(practice, user.id)
    if refusal:
        db.session.rollback()
        return {"success": False, "error": refusal}

    partners = [l.user for l in practice.leads if l.role == "lead" and l.user]
    practice.leads.append(PracticeLead(user_id=user.id, role="lead"))
    db.session.commit()
    try:
        refresh_practice_posts(practice, change_type="edit", notify=False)
    except Exception:  # noqa: BLE001 - the sign-up is saved; the next refresh repairs posts
        db.session.rollback()
        current_app.logger.exception("Refresh after sign-up failed for practice %s", practice_id)
    _post_signup_reply(practice, slack_uid, partners)
    return {"success": True}


def post_block_post(poll) -> bool:
    try:
        rendered, text = _render(poll)
        response = get_slack_client().chat_postMessage(
            channel=PRACTICES_CORE_CHANNEL_ID, blocks=rendered, text=text)
        ts = response["ts"]
    except Exception as exc:  # noqa: BLE001 - never raise; the job retries tomorrow
        current_app.logger.warning("Block post for poll %s failed: %s", poll.id, exc)
        return False
    poll.block_post_ts = ts
    db.session.commit()
    return True


def refresh_block_post(poll, *, exclude_practice_id=None) -> bool:
    """Re-render the block post and, once it's posted, the leads' schedule."""
    if not poll.block_post_ts:
        return False
    ok = True
    for channel, ts, render in ((PRACTICES_CORE_CHANNEL_ID, poll.block_post_ts, _render),
                                (COORD_CHANNEL_ID, poll.schedule_ts, _render_schedule)):
        if not ts:
            continue
        try:
            rendered, text = render(poll, exclude_practice_id=exclude_practice_id)
            get_slack_client().chat_update(channel=channel, ts=ts, blocks=rendered, text=text)
        except Exception as exc:  # noqa: BLE001 - never raise; next edit or morning repairs it
            current_app.logger.warning(
                "Refresh of %s in %s for poll %s failed: %s", ts, channel, poll.id, exc)
            ok = False
    return ok


def post_wednesday_reply(poll) -> bool:
    from app.slack.blocks.block_post import block_range_label

    rows = [r for r in block_post_rows(poll) if not r["cancelled"]]
    first = f" The first practice is {rows[0]['when'].strftime('%a %-m/%-d')}." if rows else ""
    label = block_range_label(poll.starts_on, poll.ends_on)
    rendered = [{
        "type": "section",
        "text": {"type": "mrkdwn",
                 "text": f"Nobody has opened the lead poll for *{label}* yet.{first}"},
        "accessory": {"type": "button", "style": "primary", "action_id": "block_poll_open",
                      "value": str(poll.id), "text": {"type": "plain_text", "text": "Open poll"}},
    }]
    kwargs = {"channel": PRACTICES_CORE_CHANNEL_ID, "blocks": rendered,
              "text": f"Nobody has opened the lead poll for {label} yet."}
    if poll.block_post_ts:
        kwargs["thread_ts"] = poll.block_post_ts
    try:
        get_slack_client().chat_postMessage(**kwargs)
    except Exception as exc:  # noqa: BLE001 - never raise
        current_app.logger.warning("Wednesday reply for poll %s failed: %s", poll.id, exc)
        return False
    poll.wednesday_reminder_sent_at = now_central_naive()
    db.session.commit()
    return True


def _mention(user) -> str:
    from app.slack.blocks.block_post import short_name

    slack = user.slack_user
    return f"<@{slack.slack_uid}>" if slack and slack.slack_uid else short_name(user)


def block_post_rows(poll, *, exclude_practice_id=None) -> list[dict]:
    from app.slack.blocks.block_post import short_name, where_label

    letters = {m.practice_id: m.emoji for m in poll.practices}
    available = {}
    if poll.message_ts:
        for row in LeadAvailabilityResponse.query.filter_by(poll_id=poll.id).all():
            available[row.practice_id] = available.get(row.practice_id, 0) + 1

    rows = []
    for practice in block_practices(poll.starts_on, poll.ends_on):
        if practice.id == exclude_practice_id:
            continue
        leads = [l.user for l in practice.leads if l.role == "lead" and l.user]
        coaches = [l.user for l in practice.leads if l.role == "coach" and l.user]
        rows.append({
            "practice_id": practice.id,
            "emoji": letters.get(practice.id),
            "when": practice.date,
            "where": where_label(practice),
            "cancelled": practice.status == PracticeStatus.CANCELLED.value,
            "leads": [short_name(u) for u in leads],
            "lead_mentions": [_mention(u) for u in leads],
            "coaches": [short_name(u) for u in coaches],
            "leads_needed": practice.leads_needed or 2,
            "available": available.get(practice.id, 0),
            "activity": practice.activities[0].name if practice.activities else None,
            "location": ({"name": practice.location.name, "spot": practice.location.spot,
                          "url": practice.location.google_maps_url}
                         if practice.location else None),
            "kinds": ([t.name for t in practice.practice_types]
                      or [a.name for a in practice.activities]),
        })
    return rows


def reminder_days(opened_at: datetime, ends_on: date, today: date) -> list[date]:
    """Days the remaining nudges go out, per participants_to_nudge's rules."""
    first = opened_at.date() + timedelta(days=FIRST_NUDGE_AFTER_DAYS)
    days = [first + timedelta(days=MIN_DAYS_BETWEEN_NUDGES * i) for i in range(MAX_NUDGES)]
    return [d for d in days if today < d <= ends_on]


def footer_text(poll, today: date) -> str | None:
    if poll.status != PollStatus.OPEN or not poll.opened_at:
        return None
    pool = {u.id for u in eligible_leads()}
    answered = sum(
        1 for p in LeadAvailabilityParticipant.query.filter_by(poll_id=poll.id).all()
        if p.user_id in pool and p.status != ParticipantStatus.PENDING
    )
    text = f"{answered} of {len(pool)} leads have answered."
    days = reminder_days(poll.opened_at, poll.ends_on, today)
    if days:
        names = [d.strftime("%a") for d in days]
        joined = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
        text += f" Reminders go to the rest {joined}."
    return text


def assign_modal_data(practice_id: int) -> dict | None:
    """What the Assign modal shows for one session, or None if it is gone."""
    from app.models import User
    from app.practices.models import Practice
    from app.slack.blocks.block_post import short_name, where_label

    practice = db.session.get(Practice, practice_id)
    if practice is None:
        return None
    poll = poll_for_date(practice.date.date())

    available_users = []
    if poll is not None and poll.message_ts:
        ids = [r.user_id for r in LeadAvailabilityResponse.query.filter_by(
            poll_id=poll.id, practice_id=practice.id).all()]
        if ids:
            available_users = (User.query.filter(User.id.in_(ids))
                               .order_by(User.first_name, User.last_name).all())

    if poll is None or (poll.status == PollStatus.CLOSED and not poll.message_ts):
        available_text = None
    elif poll.status == PollStatus.DRAFT:
        available_text = "Available: poll not opened yet"
    elif available_users:
        available_text = "Available: " + ", ".join(short_name(u) for u in available_users)
    else:
        available_text = "Available: nobody yet"

    current = [l.user for l in practice.leads if l.role == "lead" and l.user]
    available_ids = {u.id for u in available_users}
    pool = [u for u in eligible_leads() if u.id not in available_ids]
    pool_ids = {u.id for u in pool}
    outside = [u for u in current if u.id not in available_ids and u.id not in pool_ids]
    others = sorted(pool + outside, key=lambda u: (u.first_name or "", u.last_name or ""))

    when = practice.date
    return {
        "practice_id": practice.id,
        "title": f"Assign leads · {when.strftime('%a %-m/%-d')}",
        "detail": f"{when.strftime('%-I:%M%p').replace('PM', 'p').replace('AM', 'a')} · "
                  f"{where_label(practice)} · needs {practice.leads_needed or 2}",
        "available_text": available_text,
        "available": [(u.id, short_name(u)) for u in available_users],
        "others": [(u.id, short_name(u)) for u in others],
        "initial_ids": [u.id for u in current],
        "location_id": practice.location_id,
        "type_ids": [t.id for t in practice.practice_types],
        "activity_ids": [a.id for a in practice.activities],
    }


def validate_assignment(type_ids, activity_ids) -> tuple[str, str] | None:
    """(block_id, message) when the chosen types/activities cannot be combined."""
    from app.practices.plan_reaction_queries import load_selected_plan_reaction_sources
    from app.practices.plan_reactions import (
        PlanReactionValidationError,
        resolve_plan_reaction_defaults,
    )

    try:
        selected = load_selected_plan_reaction_sources(
            db.session, activity_ids=activity_ids, type_ids=type_ids)
        resolve_plan_reaction_defaults(selected.practice_types, selected.activities)
    except PlanReactionValidationError as exc:
        return ("activities" if exc.field == "activities" else "types"), str(exc)
    return None


def save_assignment(practice_id: int, *, lead_ids, location_id, type_ids,
                    activity_ids, initial_lead_ids=None) -> None:
    """Save one Assign submission: leads (coaches untouched), location, type, activity.

    With initial_lead_ids (who the modal opened with), only the director's own
    changes apply, so a lead who signed up while the modal was open stays.
    None replaces every lead with lead_ids.

    A changed type or activity set resets plan reactions to the new defaults.
    A None location means "not chosen" and keeps the current one.
    """
    from app.practices.models import Practice, PracticeLead
    from app.practices.plan_reaction_queries import load_selected_plan_reaction_sources
    from app.practices.plan_reactions import resolve_plan_reaction_defaults
    from app.practices.publishing import publish_if_ready
    from app.slack.practices import refresh_practice_posts
    from app.slack.practices.announcements import build_announcement_change_notice

    practice = db.session.get(Practice, practice_id)
    if practice is None:
        return
    previous_date = practice.date
    previous_location_id = practice.location_id
    previous_plan_reactions = [dict(item) for item in (practice.plan_reactions or [])]

    current = [l for l in practice.leads if l.role == "lead"]
    if initial_lead_ids is None:
        remove, add = {l.user_id for l in current}, list(dict.fromkeys(lead_ids))
    else:
        initial = set(initial_lead_ids)
        remove = initial - set(lead_ids)
        add = [u for u in dict.fromkeys(lead_ids) if u not in initial]
    for lead in current:
        if lead.user_id in remove:
            practice.leads.remove(lead)
    have = {l.user_id for l in practice.leads if l.role == "lead"}
    for user_id in add:
        if user_id not in have:
            practice.leads.append(PracticeLead(user_id=user_id, role="lead"))
    if location_id is not None:
        practice.location_id = location_id

    selected = load_selected_plan_reaction_sources(
        db.session, activity_ids=activity_ids, type_ids=type_ids)
    changed = (
        {t.id for t in practice.practice_types} != {t.id for t in selected.practice_types}
        or {a.id for a in practice.activities} != {a.id for a in selected.activities})
    if changed:
        practice.practice_types = list(selected.practice_types)
        practice.activities = list(selected.activities)
        practice.plan_reactions = resolve_plan_reaction_defaults(
            selected.practice_types, selected.activities).snapshot
    db.session.commit()

    try:
        publish_if_ready(practice)
    except Exception:
        db.session.rollback()
        current_app.logger.exception("publish_if_ready failed for practice %s", practice_id)

    refresh_practice_posts(
        practice, change_type="edit", notify=False, previous_date=previous_date,
        previous_plan_reactions=previous_plan_reactions,
        announcement_notice=build_announcement_change_notice(
            previous_date=previous_date, previous_location_id=previous_location_id,
            practice=practice))
