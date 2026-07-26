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

# The tags that keep an ALUMNI member in the pool. Mirrors the coach override in
# the Slack tier logic (see CLAUDE.md): coaches at this club are routinely
# ALUMNI-status while actively coaching, so the coach tag — not membership
# status — is what says "this person still runs practice".
COACH_TAGS = frozenset({"HEAD_COACH", "ASSISTANT_COACH"})


class PollNotReadyError(RuntimeError):
    """Raised when practices in range still lack location, type or time."""


class DuplicatePollError(PollNotReadyError):
    """Raised when a DRAFT/OPEN poll already covers an overlapping range.

    Subclasses PollNotReadyError so existing callers (the admin route's
    `except PollNotReadyError` -> 400 with the message verbatim) keep working
    without change.
    """


def eligible_leads() -> list[User]:
    """Everyone who may be asked, computed live from tags.

    Computed rather than stored so a lead who joins mid-block is included
    automatically — a stale roster is a failure that recurred every single
    season with the old spreadsheet.

    Excludes DROPPED members: a former member who kept a tag should not still
    be DMed.

    ALUMNI is a partial exclusion, decided by the practices director: an
    ALUMNI member stays in the pool only if they hold a coach tag. Coaches are
    routinely ALUMNI-status while actively coaching (see the coach override in
    Slack tier logic), so a blanket status filter would drop real, active
    coaches -- but a *lead*-tagged alumnus has stepped back from the club, and
    DMing them every block is how the bot gets muted by the people it depends
    on. Keeping someone in the pool after they lapse is now a matter of
    tagging them as a coach, not of the availability code guessing.
    """
    tag_ids = [t.id for t in Tag.query.filter(Tag.name.in_(ELIGIBLE_TAGS)).all()]
    if not tag_ids:
        return []
    candidates = (
        User.query.options(joinedload(User.tags))
        .filter(User.tags.any(Tag.id.in_(tag_ids)))
        .filter(User.status != UserStatus.DROPPED)
        .order_by(User.first_name)
        .all()
    )
    # Filtered in Python rather than SQL because tags are already eager-loaded
    # here, so this costs nothing and keeps the rule readable next to the
    # docstring that explains why it exists.
    return [user for user in candidates if _may_be_asked(user)]


def _may_be_asked(user) -> bool:
    """Whether this eligible-tagged user should still receive availability DMs."""
    if user.status != UserStatus.ALUMNI:
        return True
    return any(tag.name in COACH_TAGS for tag in user.tags)


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

    Also refuses to build a second poll whose date range overlaps an
    existing DRAFT or OPEN poll. Two overlapping live polls would both nudge
    the same leads about the same sessions, and reactions on the older one
    become invisible to whichever poll a lead happens to answer -- a
    confusing, silent way to under-count availability. CLOSED polls don't
    block a rebuild of the same range.
    """
    overlapping = (
        LeadAvailabilityPoll.query
        .filter(LeadAvailabilityPoll.status.in_([PollStatus.DRAFT, PollStatus.OPEN]))
        .filter(LeadAvailabilityPoll.starts_on <= ends_on,
                LeadAvailabilityPoll.ends_on >= starts_on)
        .first()
    )
    if overlapping is not None:
        raise DuplicatePollError(
            f"poll #{overlapping.id} ({overlapping.status}, "
            f"{overlapping.starts_on}..{overlapping.ends_on}) already covers "
            f"this range -- close or complete it before building another"
        )

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


def poll_rows(
    poll: LeadAvailabilityPoll, *, exclude_practice_id: int | None = None
) -> list[dict]:
    """Render rows for the block builder.

    Cancelled practices are skipped — a poll must not keep soliciting
    availability for a session that isn't happening (build_poll never maps
    them, but a practice can be cancelled after the poll opens).
    `exclude_practice_id` drops a practice that is mid-delete: the delete
    route refreshes Slack posts *before* removing the row, so the doomed
    practice is still queryable when its poll message gets rebuilt. A
    mapping whose practice row is already gone is skipped rather than
    crashed on. Surviving rows keep their original letter emoji — the
    emoji-to-practice mapping is persisted, so dropping a line never
    shifts the letters under leads' existing reactions.
    """
    rows = []
    for mapping in poll.practices:
        practice = mapping.practice
        if practice is None or practice.id == exclude_practice_id:
            continue
        if practice.status == PracticeStatus.CANCELLED.value:
            continue
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

    Also refuses to run at all unless the poll is still DRAFT. Calling this
    twice on the same poll would post a second Slack message and overwrite
    `poll.message_ts` with the new one -- orphaning every reaction on the
    first message, since reaction lookup matches only the current ts. A
    later `reconcile_poll` against that orphaned message sees zero reactions
    and deletes every stored response, demoting participants to PENDING: a
    double-open silently destroys the only durable record of who can lead.
    """
    if poll.status != PollStatus.DRAFT:
        message = (
            f"poll {poll.id} is already {poll.status} -- refusing to post "
            "again and overwrite its message_ts"
        )
        current_app.logger.warning(message)
        return {"success": False, "error": message}

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

    # Captured before the commit: if it fails, the rollback expires the poll
    # object, and the ts of the now-live message exists nowhere else once the
    # exception is swallowed -- these two values are what a human needs to
    # recover.
    poll_id = poll.id
    posted_ts = response["ts"]

    poll.message_ts = posted_ts
    poll.status = PollStatus.OPEN
    poll.opened_at = now_central_naive()
    try:
        db.session.commit()
    except Exception as exc:  # noqa: BLE001 - never raise; see module docstring
        # Roll back so the caller isn't handed a poisoned session. The poll
        # is back to DRAFT with no message_ts, but the Slack message IS live
        # and collecting reactions that match nothing -- do NOT delete it as
        # "cleanup" (that destroys the audit trail, and the delete can fail
        # too). A human recovers by setting message_ts/status from this log
        # line rather than re-opening, which would post a duplicate.
        db.session.rollback()
        message = (
            f"availability poll {poll_id}: message posted to Slack "
            f"(ts {posted_ts}) but the commit marking it OPEN failed: {exc}. "
            f"The message is live; record ts {posted_ts} on the poll manually "
            "instead of opening again."
        )
        current_app.logger.error(message)
        return {"success": False, "error": message}

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

    reconcile_poll() is fail-soft (Slack error -> logs and returns an
    "error" key rather than raising), so its result is captured here. The
    poll still closes either way -- a poll stuck OPEN keeps the daily nudge
    job DMing people about a block that already ended, which is worse than
    availability data that may be slightly stale, and the picker still works
    either way. But a failed final reconcile must be loud: it's logged at
    error level and surfaced back to the caller via `reconcile_failed`,
    since OPEN is the only status ever reconciled again -- once CLOSED,
    there is no other recovery path for this poll.
    """
    if poll.status == PollStatus.CLOSED:
        return {"success": True, "already_closed": True}

    reconcile_result = reconcile_poll(poll)
    poll.status = PollStatus.CLOSED
    poll.closed_at = now_central_naive()
    db.session.commit()

    result = {"success": True, "poll_id": poll.id}
    if reconcile_result.get("error"):
        current_app.logger.error(
            "Final reconcile failed while closing availability poll %s: %s",
            poll.id, reconcile_result["error"],
        )
        result["reconcile_failed"] = True
        result["error"] = reconcile_result["error"]

    current_app.logger.info("Closed availability poll %s", poll.id)
    return result
