"""Lead availability poll construction and lifecycle."""

from datetime import date, datetime, timedelta

from flask import current_app
from slack_sdk.errors import SlackApiError
from sqlalchemy.orm import joinedload

from app.constants import UserStatus
from app.models import AppConfig, SlackUser, Tag, User, db
from app.practices.availability_emoji import (
    DONE_EMOJI,
    letter_emoji,
    validate_emoji_available,
)
from app.practices.availability_models import (
    LeadAvailabilityParticipant,
    LeadAvailabilityPoll,
    LeadAvailabilityPollPractice,
    ParticipantStatus,
    PollStatus,
)
from app.practices.drafting import is_ready, missing_fields
from app.practices.interfaces import PracticeStatus
from app.practices.models import Practice
from app.slack.blocks.availability import build_poll_blocks, poll_fallback_text
from app.slack.client import get_slack_client
from app.slack.practices.availability_reactions import reconcile_poll
from app.utils import now_central_naive

# Every tag that makes a member eligible to be asked for availability.
ELIGIBLE_TAGS = ["PRACTICES_LEAD", "PRACTICES_DIRECTOR", "HEAD_COACH", "ASSISTANT_COACH"]


class PollNotReadyError(RuntimeError):
    """Raised when practices in range still lack location, type or time."""


def eligible_leads() -> list[User]:
    """Everyone who may be asked, computed live from tags.

    Computed rather than stored so a lead who joins mid-block is included
    automatically — a stale roster is a failure that recurred every single
    season with the old spreadsheet.

    Excludes DROPPED members: a former member who kept a tag should not still
    be DMed. ALUMNI is deliberately NOT filtered here -- coaches are routinely
    ALUMNI-status while actively coaching (see the coach override in Slack
    tier logic), so excluding ALUMNI would drop real, active coaches from the
    pool. Whether ALUMNI leads (not just coaches) should also be nudged is an
    open question for the practices director, not settled by this fix.
    """
    tag_ids = [t.id for t in Tag.query.filter(Tag.name.in_(ELIGIBLE_TAGS)).all()]
    if not tag_ids:
        return []
    return (
        User.query.options(joinedload(User.tags))
        .filter(User.tags.any(Tag.id.in_(tag_ids)))
        .filter(User.status != UserStatus.DROPPED)
        .order_by(User.first_name)
        .all()
    )


def shadow_roster_leads() -> list[User]:
    """Resolve the shadow-mode participant pool.

    Fails closed on purpose: an unset or empty `lead_availability.shadow_roster`
    returns an empty list rather than falling back to eligible_leads(). Shadow
    mode exists specifically so a misconfiguration cannot DM the live 10-17
    person tag pool -- silently falling back to that pool on a missing config
    key would recreate the exact disaster this fix closes.
    """
    slack_uids = AppConfig.get("lead_availability.shadow_roster") or []
    if not slack_uids:
        current_app.logger.warning(
            "lead_availability.shadow_roster is unset or empty -- shadow poll "
            "participant pool is empty (failing closed, not falling back to "
            "the live tag pool)"
        )
        return []

    users = []
    for slack_uid in slack_uids:
        slack_user = SlackUser.query.filter_by(slack_uid=slack_uid).first()
        if slack_user and slack_user.user:
            users.append(slack_user.user)
    return users


def _week_label(when: datetime) -> str:
    monday = when.date() - timedelta(days=when.weekday())
    return f"Week of {monday.strftime('%b %-d')}"


def _target_channel(is_shadow: bool) -> str:
    from app.slack.practices._config import COORD_CHANNEL_ID

    if is_shadow:
        # #collab-asset-mgmt-practices — see docs/superpowers/specs/
        # 2026-07-25-lead-availability-design.md "Phase 1 — Shadow mode".
        return AppConfig.get("lead_availability.shadow_channel_id", "C0B3Y71PG92")
    return COORD_CHANNEL_ID


def build_poll(starts_on: date, ends_on: date, *, is_shadow: bool = False) -> LeadAvailabilityPoll:
    """Create a DRAFT poll with its emoji mapping, or refuse if drafts are incomplete.

    Leads decide availability from location, activity type and time,
    so every practice in range must have all three before a poll can be
    built — the error names which practice needs what, since the director
    is the one who has to go fix it.
    """
    practices = (
        Practice.query
        .filter(Practice.date >= datetime.combine(starts_on, datetime.min.time()),
                Practice.date <= datetime.combine(ends_on, datetime.max.time()),
                Practice.status != PracticeStatus.CANCELLED.value)
        .order_by(Practice.date)
        .all()
    )
    if not practices:
        raise PollNotReadyError(f"no practices between {starts_on} and {ends_on}")

    incomplete = [(p, missing_fields(p)) for p in practices if not is_ready(p)]
    if incomplete:
        detail = "; ".join(
            f"{p.date:%a %-m/%-d} needs {', '.join(fields)}" for p, fields in incomplete
        )
        raise PollNotReadyError(
            f"{len(incomplete)} practice(s) still need details: {detail}"
        )

    emoji = letter_emoji(len(practices))

    poll = LeadAvailabilityPoll(
        starts_on=starts_on,
        ends_on=ends_on,
        is_shadow=is_shadow,
        channel_id=_target_channel(is_shadow),
    )
    db.session.add(poll)
    db.session.flush()

    for position, (practice, name) in enumerate(zip(practices, emoji)):
        db.session.add(LeadAvailabilityPollPractice(
            poll_id=poll.id, practice_id=practice.id, emoji=name, position=position,
        ))

    db.session.commit()
    return poll


def poll_rows(poll: LeadAvailabilityPoll) -> list[dict]:
    """Render rows for the block builder."""
    rows = []
    for mapping in poll.practices:
        practice = mapping.practice
        rows.append({
            "emoji": mapping.emoji,
            "date": practice.date,
            "location": practice.location.name if practice.location else "TBD",
            "kind": ", ".join(t.name for t in practice.practice_types) or "Practice",
            "week_label": _week_label(practice.date),
        })
    return rows


def open_poll(poll: LeadAvailabilityPoll) -> dict:
    """Validate emoji, post the poll, seed reactions, mark it OPEN.

    Refuses to post at all if any letter emoji are missing — the letter
    emoji are custom workspace emoji that were renamed once already, silently
    breaking a live poll, and a poll nobody can answer is worse than no poll.
    """
    names = [m.emoji for m in poll.practices]
    ok, missing = validate_emoji_available(names + [DONE_EMOJI])
    if not ok:
        message = (
            "cannot open poll: missing workspace emoji "
            f"{', '.join(missing)} — re-add them or update "
            "config/practices.yaml lead_availability.letter_emoji"
        )
        current_app.logger.error(message)
        return {"success": False, "error": message}

    rows = poll_rows(poll)
    start_label = poll.starts_on.strftime("%B %-d")
    end_label = poll.ends_on.strftime("%b %-d")

    # get_slack_client() raises ValueError when SLACK_BOT_TOKEN is unset, and
    # transport failures raise TimeoutError -- neither is a SlackApiError, so
    # both must be caught alongside it or a Slack outage crashes the caller
    # instead of returning a clean failure.
    try:
        client = get_slack_client()
        response = client.chat_postMessage(
            channel=poll.channel_id,
            blocks=build_poll_blocks(rows, start_label, end_label),
            text=poll_fallback_text(rows, start_label, end_label),
        )
    except SlackApiError as exc:
        error = exc.response.get("error", str(exc))
        current_app.logger.error("Availability poll failed to post: %s", error)
        return {"success": False, "error": error}
    except Exception as exc:  # noqa: BLE001 - never raise; see module docstring
        current_app.logger.error("Availability poll failed to post: %s", exc)
        return {"success": False, "error": str(exc)}

    poll.message_ts = response["ts"]
    poll.status = PollStatus.OPEN
    poll.opened_at = now_central_naive()
    db.session.commit()

    # Seed every reaction so members tap an existing pill rather than hunting
    # through the emoji picker for :letter_g:. The poll is already posted at
    # this point, so a failure to seed one reaction is logged, not raised --
    # it must never fail the whole open.
    for name in names + [DONE_EMOJI]:
        try:
            client.reactions_add(channel=poll.channel_id, timestamp=poll.message_ts, name=name)
        except SlackApiError as exc:
            current_app.logger.warning(
                "Could not seed :%s: on availability poll %s — %s",
                name, poll.id, exc.response.get("error", exc),
            )
        except Exception as exc:  # noqa: BLE001 - never raise; see module docstring
            current_app.logger.warning(
                "Could not seed :%s: on availability poll %s — %s", name, poll.id, exc
            )

    return {"success": True, "poll_id": poll.id, "ts": poll.message_ts}


FIRST_NUDGE_AFTER_DAYS = 3
MIN_DAYS_BETWEEN_NUDGES = 2
MAX_NUDGES = 3


def sync_participants(poll) -> int:
    """Ensure every currently-eligible lead has a participant row.

    A lead who joins mid-block (new tag assignment) is picked up the next
    time this runs, since eligible_leads() is computed live rather than
    snapshotted when the poll opened.

    Shadow polls (poll.is_shadow) use the shadow roster instead of the live
    tag pool, so nudge DMs during the shadow month reach only the small test
    roster -- never the real 10-17 person lead/coach pool. See
    shadow_roster_leads() for the fail-closed behavior on a missing roster.
    """
    existing = {
        row.user_id for row in
        LeadAvailabilityParticipant.query.filter_by(poll_id=poll.id).all()
    }
    added = 0
    pool = shadow_roster_leads() if poll.is_shadow else eligible_leads()
    for user in pool:
        if user.id not in existing:
            db.session.add(LeadAvailabilityParticipant(poll_id=poll.id, user_id=user.id))
            added += 1
    if added:
        db.session.commit()
    return added


def participants_to_nudge(poll, *, now: datetime) -> list[LeadAvailabilityParticipant]:
    """Who is due a reminder right now.

    Only PENDING participants -- anyone who reacted, hit done, or opted out
    is left alone. First nudge at day 3, then at least 2 days apart, 3 sends
    is the ceiling. An off-by-one here DMs everyone every morning, which is
    the fastest way to get the bot muted by the people it depends on.
    """
    if not poll.opened_at:
        return []
    if now - poll.opened_at < timedelta(days=FIRST_NUDGE_AFTER_DAYS):
        return []

    due = []
    for participant in LeadAvailabilityParticipant.query.filter_by(
            poll_id=poll.id, status=ParticipantStatus.PENDING).all():
        if participant.nudge_count >= MAX_NUDGES:
            continue
        if participant.last_nudged_at and \
                now - participant.last_nudged_at < timedelta(days=MIN_DAYS_BETWEEN_NUDGES):
            continue
        due.append(participant)
    return due


def send_nudges(poll, *, now: datetime | None = None) -> dict:
    """DM everyone currently due a reminder.

    `now` defaults to now_central_naive() -- poll.opened_at is written with
    that same clock, and mixing in datetime.utcnow() would shift the day-3
    boundary by 5-6 hours.
    """
    from app.slack.practices.availability_nudge import poll_permalink, send_nudge_dm

    now = now or now_central_naive()
    due = participants_to_nudge(poll, now=now)
    if not due:
        return {"sent": 0, "skipped": 0}

    permalink = poll_permalink(poll)
    sent = skipped = 0
    for participant in due:
        slack_user = getattr(participant.user, "slack_user", None)
        if not slack_user or not slack_user.slack_uid:
            skipped += 1
            continue
        if send_nudge_dm(poll, slack_user.slack_uid, permalink):
            participant.nudge_count += 1
            participant.last_nudged_at = now
            sent += 1
        else:
            # A failed DM must not consume this person's nudge budget --
            # they haven't actually been reminded, so nudge_count/
            # last_nudged_at are left untouched and the next run retries.
            skipped += 1

    db.session.commit()
    current_app.logger.info("Poll %s nudges: %d sent, %d skipped", poll.id, sent, skipped)
    return {"sent": sent, "skipped": skipped}


def close_poll(poll) -> dict:
    """Reconcile one final time, then close.

    The last reconcile matters: the picker must read Slack's actual final
    state, not whatever the last delivered event happened to say.
    """
    if poll.status == PollStatus.CLOSED:
        return {"success": True, "already_closed": True}

    reconcile_poll(poll)
    poll.status = PollStatus.CLOSED
    poll.closed_at = datetime.utcnow()
    db.session.commit()
    current_app.logger.info("Closed availability poll %s", poll.id)
    return {"success": True, "poll_id": poll.id}
