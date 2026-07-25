"""Reaction capture and reconciliation for lead availability polls.

Runs against the real local dev database (see tests/practices/conftest.py's
docstring, which this package's db_session fixture in tests/slack/conftest.py
also follows): dates are pinned to year 2099, the Slack channel id and user
email/name carry a "TEST" marker so a leaked row is unmistakable, and every
row created here is deleted in a try/finally (rollback first) so cleanup
survives an assertion failure.

Note: the brief's reference _setup() constructs SlackUser with a "user_id"
kwarg, but SlackUser has no such column -- the real FK lives on User
(User.slack_user_id -> SlackUser.id), matching the linked_user fixture in
tests/slack/test_reaction_rsvp.py. Fixed here so the "linked user" tests
actually exercise a linked user rather than silently testing an unlinked one.
"""

from datetime import date, datetime
from uuid import uuid4
from unittest.mock import MagicMock, patch

from app.models import SlackUser, User, db
from app.practices.availability_models import (
    LeadAvailabilityParticipant,
    LeadAvailabilityPoll,
    LeadAvailabilityPollPractice,
    LeadAvailabilityResponse,
    ParticipantStatus,
    PollStatus,
)
from app.practices.models import Practice
from app.slack.practices.availability_reactions import (
    handle_availability_reaction,
    reconcile_poll,
)

TEST_CHANNEL_ID = "TEST-CHANNEL-AVAIL"
_STARTS_ON = date(2099, 8, 1)
_ENDS_ON = date(2099, 8, 31)
_PRACTICE_DATE = datetime(2099, 8, 4, 18, 15)


def _setup(db_session, message_ts):
    practice = Practice(date=_PRACTICE_DATE, day_of_week="Tuesday", is_draft=True)
    db_session.add(practice)
    db_session.flush()

    poll = LeadAvailabilityPoll(
        starts_on=_STARTS_ON, ends_on=_ENDS_ON,
        channel_id=TEST_CHANNEL_ID, message_ts=message_ts, status=PollStatus.OPEN,
    )
    db_session.add(poll)
    db_session.flush()
    db_session.add(LeadAvailabilityPollPractice(
        poll_id=poll.id, practice_id=practice.id, emoji="letter_a", position=0))

    suffix = uuid4().hex
    slack_user = SlackUser(slack_uid=f"TEST-U-{suffix}")
    db_session.add(slack_user)
    db_session.flush()
    user = User(first_name="TEST Ada", last_name="Lead",
                email=f"test-ada-{suffix}@example.test",
                slack_user_id=slack_user.id)
    db_session.add(user)
    db_session.commit()
    return poll, practice, user, slack_user


def _cleanup(poll_id=None, practice_id=None, user_id=None, slack_user_id=None):
    """Delete only the rows this test created.

    Rolls back first so a poisoned session (e.g. a prior statement that
    raised and left the transaction aborted) doesn't turn this cleanup
    itself into an error that leaves debris behind for the next test.
    Deleting the poll first cascades to its poll-practice mapping,
    participants, and responses; the user must go before its slack_user
    (User.slack_user_id is the FK); the practice can go any time after the
    poll (which held the only FK to it).
    """
    db.session.rollback()
    if poll_id is not None:
        poll = db.session.get(LeadAvailabilityPoll, poll_id)
        if poll is not None:
            db.session.delete(poll)
    db.session.flush()
    if user_id is not None:
        user = db.session.get(User, user_id)
        if user is not None:
            db.session.delete(user)
    db.session.flush()
    if slack_user_id is not None:
        slack_user = db.session.get(SlackUser, slack_user_id)
        if slack_user is not None:
            db.session.delete(slack_user)
    if practice_id is not None:
        practice = db.session.get(Practice, practice_id)
        if practice is not None:
            db.session.delete(practice)
    db.session.commit()


def test_letter_reaction_records_availability(db_session):
    poll, practice, user, slack_user = _setup(db_session, "111.1")
    try:
        result = handle_availability_reaction(
            channel=TEST_CHANNEL_ID, message_ts="111.1", reaction="letter_a",
            slack_user_id=slack_user.slack_uid, removed=False)

        assert result["success"] is True
        row = LeadAvailabilityResponse.query.filter_by(poll_id=poll.id).one()
        assert row.practice_id == practice.id and row.user_id == user.id
        assert row.answered_for_date == practice.date, "snapshot for staleness detection"
    finally:
        _cleanup(poll.id, practice.id, user.id, slack_user.id)


def test_removing_the_reaction_deletes_the_row(db_session):
    poll, practice, user, slack_user = _setup(db_session, "111.2")
    try:
        handle_availability_reaction(channel=TEST_CHANNEL_ID, message_ts="111.2",
                                     reaction="letter_a", slack_user_id=slack_user.slack_uid,
                                     removed=False)

        handle_availability_reaction(channel=TEST_CHANNEL_ID, message_ts="111.2",
                                     reaction="letter_a", slack_user_id=slack_user.slack_uid,
                                     removed=True)

        assert LeadAvailabilityResponse.query.filter_by(poll_id=poll.id).count() == 0
    finally:
        _cleanup(poll.id, practice.id, user.id, slack_user.id)


def test_done_emoji_marks_participant_done_without_a_response_row(db_session):
    poll, practice, user, slack_user = _setup(db_session, "111.3")
    try:
        handle_availability_reaction(channel=TEST_CHANNEL_ID, message_ts="111.3",
                                     reaction="white_check_mark", slack_user_id=slack_user.slack_uid,
                                     removed=False)

        participant = LeadAvailabilityParticipant.query.filter_by(
            poll_id=poll.id, user_id=user.id).one()
        assert participant.status == ParticipantStatus.DONE
        assert LeadAvailabilityResponse.query.filter_by(poll_id=poll.id).count() == 0, \
            "done is not availability for any session"
    finally:
        _cleanup(poll.id, practice.id, user.id, slack_user.id)


def test_unmapped_emoji_is_ignored(db_session):
    poll, practice, user, slack_user = _setup(db_session, "111.4")
    try:
        result = handle_availability_reaction(channel=TEST_CHANNEL_ID, message_ts="111.4",
                                              reaction="tada", slack_user_id=slack_user.slack_uid,
                                              removed=False)
        assert result["ignored"] == "unmapped_emoji"
        assert LeadAvailabilityResponse.query.filter_by(poll_id=poll.id).count() == 0
    finally:
        _cleanup(poll.id, practice.id, user.id, slack_user.id)


def test_non_poll_message_returns_none_so_attendance_still_runs(db_session):
    poll, practice, user, slack_user = _setup(db_session, "111.5")
    try:
        assert handle_availability_reaction(
            channel=TEST_CHANNEL_ID, message_ts="999.9", reaction="letter_a",
            slack_user_id=slack_user.slack_uid, removed=False) is None
    finally:
        _cleanup(poll.id, practice.id, user.id, slack_user.id)


def test_unlinked_slack_user_is_ignored_not_crashed(db_session):
    poll, practice, user, slack_user = _setup(db_session, "111.6")
    try:
        result = handle_availability_reaction(channel=TEST_CHANNEL_ID, message_ts="111.6",
                                              reaction="letter_a", slack_user_id="TEST-U-UNKNOWN",
                                              removed=False)
        assert result["ignored"] == "unlinked_user"
    finally:
        _cleanup(poll.id, practice.id, user.id, slack_user.id)


def test_reconcile_adds_missed_and_removes_stale(db_session):
    poll, practice, user, slack_user = _setup(db_session, "111.7")
    try:
        # A response that Slack no longer shows.
        db_session.add(LeadAvailabilityResponse(
            poll_id=poll.id, practice_id=practice.id, user_id=user.id, source="reaction"))
        db_session.commit()

        client = MagicMock()
        client.reactions_get.return_value = {
            "message": {"reactions": [{"name": "white_check_mark", "users": [slack_user.slack_uid]}]}
        }

        with patch("app.slack.practices.availability_reactions.get_slack_client",
                   return_value=client):
            result = reconcile_poll(poll)

        assert result["removed"] == 1, "a response Slack no longer shows must be dropped"
        assert LeadAvailabilityResponse.query.filter_by(poll_id=poll.id).count() == 0
        participant = LeadAvailabilityParticipant.query.filter_by(
            poll_id=poll.id, user_id=user.id).one()
        assert participant.status == ParticipantStatus.DONE
    finally:
        _cleanup(poll.id, practice.id, user.id, slack_user.id)


def test_reconcile_survives_a_non_slack_api_error(db_session):
    """get_slack_client() raises plain ValueError when SLACK_BOT_TOKEN is
    unset, and transport failures raise TimeoutError -- neither is a
    SlackApiError, so a bare `except SlackApiError` would let this crash the
    caller instead of returning a clean failure result.
    """
    poll, practice, user, slack_user = _setup(db_session, "111.8")
    try:
        with patch("app.slack.practices.availability_reactions.get_slack_client",
                   side_effect=TimeoutError("boom")):
            result = reconcile_poll(poll)

        assert result["added"] == 0 and result["removed"] == 0
        assert "error" in result
    finally:
        _cleanup(poll.id, practice.id, user.id, slack_user.id)
