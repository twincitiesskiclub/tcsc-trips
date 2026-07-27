"""Capture availability from poll reactions, and reconcile against Slack.

A letter reaction records availability for exactly that practice; removing
it deletes the row -- there is no boolean, presence *is* availability. The
done emoji (:white_check_mark:) marks the participant done and creates no
response row of its own.

Reconciliation exists because reaction events get missed during deploys,
restarts, and outages. A missed *removal* is the dangerous one: someone
withdraws their availability, the event is lost, and the director schedules
them for a practice they can't lead. `reconcile_poll` re-reads Slack's
actual reactions (requires the `reactions:read` scope) and makes stored
state match -- both adding what's missing and removing what Slack no
longer shows.
"""

from flask import current_app
from slack_sdk.errors import SlackApiError

from app.models import User, db
from app.practices.availability_models import (
    LeadAvailabilityParticipant,
    LeadAvailabilityPoll,
    LeadAvailabilityPollPractice,
    LeadAvailabilityResponse,
    ParticipantStatus,
    PollStatus,
)
from app.practices.interfaces import PracticeStatus
from app.slack.client import get_slack_client


def _poll_for_message(channel, message_ts):
    return LeadAvailabilityPoll.query.filter_by(
        channel_id=channel, message_ts=message_ts, status=PollStatus.OPEN
    ).first()


def _user_for_slack_uid(slack_user_id):
    return User.query.join(User.slack_user).filter_by(slack_uid=slack_user_id).first()


def _participant(poll_id, user_id):
    participant = LeadAvailabilityParticipant.query.filter_by(
        poll_id=poll_id, user_id=user_id).first()
    if participant is None:
        # Created lazily so a lead who joins mid-poll is handled automatically.
        # status is set explicitly rather than relying on the column default,
        # which only applies at INSERT time -- a freshly constructed instance
        # would otherwise compare as `None`, not ParticipantStatus.PENDING,
        # until something else happens to flush it first.
        participant = LeadAvailabilityParticipant(
            poll_id=poll_id, user_id=user_id, status=ParticipantStatus.PENDING)
        db.session.add(participant)
    return participant


def handle_availability_reaction(*, channel, message_ts, reaction, slack_user_id,
                                  removed=False):
    """Record or withdraw availability from one reaction event.

    Returns None when the message is not an open availability poll, so the
    caller (handle_attendance_reaction) falls through to the existing
    attendance handling untouched.
    """
    poll = _poll_for_message(channel, message_ts)
    if poll is None:
        return None

    user = _user_for_slack_uid(slack_user_id)
    if user is None:
        current_app.logger.info(
            "Availability reaction from unlinked Slack user %s", slack_user_id)
        return {"success": True, "ignored": "unlinked_user"}

    # The poll's SNAPSHOTTED done emoji, never the live config value: a
    # config rename mid-poll must not stop counting reactions leads already
    # gave (see LeadAvailabilityPoll.done_emoji).
    if reaction == poll.resolved_done_emoji:
        participant = _participant(poll.id, user.id)
        participant.status = (
            ParticipantStatus.PENDING if removed else ParticipantStatus.DONE
        )
        db.session.commit()
        return {"success": True, "done": not removed}

    mapping = LeadAvailabilityPollPractice.query.filter_by(
        poll_id=poll.id, emoji=reaction).first()
    if mapping is None:
        return {"success": True, "ignored": "unmapped_emoji"}

    # Only construct a participant row once we know the reaction means
    # something -- an unmapped emoji (a stray :tada: from a linked member)
    # should not create state, matching the unlinked_user path above which
    # also returns before creating anything.
    participant = _participant(poll.id, user.id)

    existing = LeadAvailabilityResponse.query.filter_by(
        poll_id=poll.id, practice_id=mapping.practice_id, user_id=user.id).first()

    if removed:
        if existing:
            db.session.delete(existing)
    elif existing is None:
        practice = mapping.practice
        # A cancelled session's line is dropped from the poll message by
        # poll_rows(), but its seeded reaction pill stays on the message --
        # there is nothing to remove it, and removing it would be its own
        # risk. So a lead can still tap a letter whose line is gone and, until
        # now, that wrote a real availability response for a practice that
        # isn't happening. Harmless to assignment (which is per-practice) but
        # it inflates every count the director reads. Withdrawing a reaction
        # is still honoured above, so an existing response can always be
        # cleaned up.
        if practice is not None and practice.status == PracticeStatus.CANCELLED.value:
            current_app.logger.info(
                "Ignoring availability reaction :%s: from %s on poll %s: "
                "practice %s is cancelled",
                reaction, slack_user_id, poll.id, mapping.practice_id,
            )
            db.session.commit()  # the participant row above is still real
            return {"success": True, "ignored": "cancelled_practice"}
        db.session.add(LeadAvailabilityResponse(
            poll_id=poll.id,
            practice_id=mapping.practice_id,
            user_id=user.id,
            source="reaction",
            answered_for_date=practice.date if practice else None,
            answered_for_location_id=practice.location_id if practice else None,
        ))

    if participant.status == ParticipantStatus.PENDING:
        participant.status = ParticipantStatus.RESPONDED

    db.session.commit()
    return {"success": True, "practice_id": mapping.practice_id, "removed": removed}


def reconcile_poll(poll) -> dict:
    """Make stored responses match Slack's actual reactions on the poll message.

    Requires the `reactions:read` Slack scope.
    """
    try:
        response = get_slack_client().reactions_get(
            channel=poll.channel_id, timestamp=poll.message_ts, full=True)
    except SlackApiError as exc:
        error = exc.response.get("error", str(exc))
        current_app.logger.error("Reconcile failed for poll %s: %s", poll.id, error)
        return {"added": 0, "removed": 0, "error": error}
    except Exception as exc:  # noqa: BLE001 - ValueError (no token) / TimeoutError etc.
        current_app.logger.error("Reconcile failed for poll %s: %s", poll.id, exc)
        return {"added": 0, "removed": 0, "error": str(exc)}

    reactions = (response.get("message") or {}).get("reactions") or []
    by_emoji = {r["name"]: set(r.get("users") or []) for r in reactions}

    slack_uid_to_user = {}
    for uid in {uid for users in by_emoji.values() for uid in users}:
        user = _user_for_slack_uid(uid)
        if user:
            slack_uid_to_user[uid] = user

    added = removed = 0

    for mapping in poll.practices:
        practice = mapping.practice
        cancelled = (
            practice is not None
            and practice.status == PracticeStatus.CANCELLED.value
        )
        # Same rule as handle_availability_reaction: no NEW availability for a
        # cancelled session, whose pill outlives its line on the message.
        # `should_have` is emptied rather than skipping the mapping outright,
        # so the removal loop below still runs and rows recorded before the
        # cancellation are cleaned up instead of being frozen in place.
        should_have = set() if cancelled else {
            slack_uid_to_user[uid].id
            for uid in by_emoji.get(mapping.emoji, set())
            if uid in slack_uid_to_user
        }
        existing_rows = LeadAvailabilityResponse.query.filter_by(
            poll_id=poll.id, practice_id=mapping.practice_id).all()
        has = {row.user_id: row for row in existing_rows}

        for user_id in should_have - set(has):
            db.session.add(LeadAvailabilityResponse(
                poll_id=poll.id, practice_id=mapping.practice_id, user_id=user_id,
                source="reaction",
                answered_for_date=practice.date if practice else None,
                answered_for_location_id=practice.location_id if practice else None,
            ))
            added += 1
        for user_id in set(has) - should_have:
            db.session.delete(has[user_id])
            removed += 1

    # Reconciliation is authoritative for participant status, not just
    # response rows: a stale DONE (the lead removed ✅ meaning to add more
    # sessions, but the removal event was lost) is exactly the failure class
    # this function exists to correct. Recompute every participant's status
    # from what Slack shows right now plus what response rows survived
    # above, rather than only ever promoting.
    db.session.flush()

    done_user_ids = {
        slack_uid_to_user[uid].id
        # Snapshot, not live config: reading the renamed config value here
        # would demote every already-DONE participant and re-enroll them for
        # nudges (see LeadAvailabilityPoll.done_emoji).
        for uid in by_emoji.get(poll.resolved_done_emoji, set())
        if uid in slack_uid_to_user
    }
    responded_user_ids = {
        row.user_id
        for row in LeadAvailabilityResponse.query.filter_by(poll_id=poll.id).all()
    }
    known_participant_ids = {
        p.user_id
        for p in LeadAvailabilityParticipant.query.filter_by(poll_id=poll.id).all()
    }

    for user_id in known_participant_ids | done_user_ids | responded_user_ids:
        participant = _participant(poll.id, user_id)
        if participant.status == ParticipantStatus.OPTED_OUT:
            continue  # a deliberate user choice, not derived state
        if user_id in done_user_ids:
            participant.status = ParticipantStatus.DONE
        elif user_id in responded_user_ids:
            participant.status = ParticipantStatus.RESPONDED
        else:
            participant.status = ParticipantStatus.PENDING

    db.session.commit()
    current_app.logger.info(
        "Reconciled poll %s: +%d -%d responses", poll.id, added, removed)
    return {"added": added, "removed": removed}
