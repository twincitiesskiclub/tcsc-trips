"""Two-week practice blocks.

Every other Monday, a week before a block starts, the block job creates the
block's sessions and its poll row (DRAFT) and posts the block post in
#collab-coaches-practices. Someone on the practices team presses Open poll,
which posts the leads poll. The block post then shows coverage and an Assign
button per session.

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
from app.utils import today_central

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
        and poll.block_post_ts
        and poll.wednesday_reminder_sent_at is None
        and today >= start - timedelta(days=REMINDER_DAYS_AHEAD)
    ):
        reminded = post_wednesday_reply(poll)

    return {"start": start, "poll_id": poll.id, "posted": posted, "reminded": reminded}


def run_block_job(today: date | None = None) -> list[dict]:
    today = today or today_central()
    return [ensure_block(start, today) for start in blocks_due(today, block_anchor())]


def open_block_poll(poll_id: int, opened_by_slack_uid: str | None) -> dict:
    """Post the leads poll for a block. Exactly one caller wins.

    The row lock is held through the Slack post and released by open_poll's
    commit (or our rollback). A second click while the first is in flight
    fails NOWAIT; a click after it sees status open. A crash mid-open rolls
    the transaction back, so nothing gets stuck.
    """
    try:
        poll = (
            LeadAvailabilityPoll.query
            .filter_by(id=poll_id)
            .populate_existing()
            .with_for_update(nowait=True)
            .one()
        )
    except OperationalError:
        db.session.rollback()
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

def post_block_post(poll) -> bool:
    raise NotImplementedError


def refresh_block_post(poll, *, exclude_practice_id=None) -> bool:
    raise NotImplementedError


def post_wednesday_reply(poll) -> bool:
    raise NotImplementedError


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
            "coaches": [short_name(u) for u in coaches],
            "leads_needed": practice.leads_needed or 2,
            "available": available.get(practice.id, 0),
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
