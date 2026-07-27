"""Attendance persistence for Slack reaction events."""

import logging
from datetime import datetime
from types import SimpleNamespace

from app.models import User, db
from app.practices.interfaces import PracticeStatus, RSVPStatus
from app.practices.models import Practice, PracticeRSVP


logger = logging.getLogger(__name__)


def _select_attendance_practice(siblings, reaction):
    """Return the one practice whose attendance emoji matches the reaction."""
    if len(siblings) == 1 and not siblings[0].slack_session_emoji:
        return siblings[0] if reaction == "white_check_mark" else None

    persisted = {
        practice.slack_session_emoji: practice
        for practice in siblings
        if practice.slack_session_emoji
    }
    return persisted.get(reaction)


def handle_attendance_reaction(
    *, channel, message_ts, reaction, slack_user_id, removed=False
):
    """Route one reaction event and persist only an exact going RSVP."""
    if not all((channel, message_ts, reaction, slack_user_id)):
        return {"success": True, "ignored": "invalid_event"}

    # Availability polls live in the same channels as announcements, so check
    # them first. Returns None when this message is not a poll.
    #
    # This call is wrapped defensively: availability handling is new and
    # this function is the entry point for practice RSVP via reactions,
    # which every member relies on daily. An unguarded exception here would
    # propagate out of handle_attendance_reaction and take down attendance
    # RSVP for every announcement -- previously independent of, and much
    # older and more relied-upon than, availability polling.
    from app.slack.practices.availability_reactions import handle_availability_reaction

    availability = None
    try:
        availability = handle_availability_reaction(
            channel=channel, message_ts=message_ts, reaction=reaction,
            slack_user_id=slack_user_id, removed=removed,
        )
    except Exception:
        # Rollback before falling through. handle_availability_reaction does
        # db.session.add() before its commits, so the likeliest exception here
        # is a flush/constraint error (Slack retries an unacked event within
        # 3s, and two deliveries racing violate the response unique index) --
        # which leaves the session poisoned. Without this, the fall-through
        # below immediately raises PendingRollbackError out of
        # handle_attendance_reaction, so the guard re-raises on the very error
        # class it was written for and the log line claiming a fallback
        # happened is a lie.
        db.session.rollback()
        logger.error(
            "Availability reaction handling failed for channel=%s ts=%s "
            "reaction=%s; falling through to attendance handling",
            channel, message_ts, reaction, exc_info=True,
        )
    if availability is not None:
        return availability

    from app.slack.practices.announcements import get_announcement_siblings

    siblings = get_announcement_siblings(SimpleNamespace(
        slack_channel_id=channel,
        slack_message_ts=message_ts,
    ))
    if not siblings:
        return {"success": True, "ignored": "message_not_linked"}

    if len(siblings) > 1:
        saved = [
            item.slack_session_emoji
            for item in siblings
            if item.slack_session_emoji
        ]
        if len(saved) != len(set(saved)):
            return {"success": True, "ignored": "invalid_combined_mapping"}
        if any(not item.slack_session_emoji for item in siblings):
            from app.slack.client import assign_combined_session_emojis

            assignment = assign_combined_session_emojis(siblings)
            if not assignment["success"]:
                return {
                    "success": True,
                    "ignored": "invalid_combined_mapping",
                }

    practice = _select_attendance_practice(siblings, reaction)
    if practice is None:
        return {"success": True, "ignored": "not_attendance"}
    if practice.status == PracticeStatus.CANCELLED.value:
        return {"success": True, "ignored": "cancelled"}

    user = (
        User.query.join(User.slack_user)
        .filter_by(slack_uid=slack_user_id)
        .first()
    )
    if user is None:
        return {"success": True, "ignored": "unlinked_user"}

    rsvp = PracticeRSVP.query.filter_by(
        practice_id=practice.id,
        user_id=user.id,
    ).first()
    if removed:
        if rsvp is None or rsvp.status != RSVPStatus.GOING.value:
            return {
                "success": True,
                "ignored": "no_matching_going_rsvp",
            }
        db.session.delete(rsvp)
        action = "removed"
    else:
        if rsvp is None:
            rsvp = PracticeRSVP(
                practice_id=practice.id,
                user_id=user.id,
                slack_user_id=slack_user_id,
            )
            db.session.add(rsvp)
        rsvp.status = RSVPStatus.GOING.value
        rsvp.slack_user_id = slack_user_id
        rsvp.responded_at = datetime.utcnow()
        action = "upserted"

    db.session.commit()

    try:
        from app.slack.practices.rsvp import update_practice_rsvp_counts

        update_practice_rsvp_counts(practice)
    except Exception:
        logger.warning(
            "Attendance saved but legacy count refresh failed for practice #%s",
            practice.id,
            exc_info=True,
        )

    return {
        "success": True,
        "action": action,
        "practice_id": practice.id,
    }
