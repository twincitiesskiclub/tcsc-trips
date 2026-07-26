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

The test practice is given a real PracticeLocation (rather than leaving
location_id null) so answered_for_location_id snapshot assertions actually
distinguish "snapshotted the real value" from "happens to be None either way".
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
from app.practices.interfaces import PracticeStatus
from app.practices.models import Practice, PracticeLocation
from app.slack.practices.availability_reactions import (
    handle_availability_reaction,
    reconcile_poll,
)

TEST_CHANNEL_ID = "TEST-CHANNEL-AVAIL"
_STARTS_ON = date(2099, 8, 1)
_ENDS_ON = date(2099, 8, 31)
_PRACTICE_DATE = datetime(2099, 8, 4, 18, 15)


def _setup(db_session, message_ts):
    location = PracticeLocation(name="TEST Location")
    db_session.add(location)
    db_session.flush()

    practice = Practice(date=_PRACTICE_DATE, day_of_week="Tuesday", is_draft=True,
                         location_id=location.id)
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
    return poll, practice, user, slack_user, location



def _row_ids(poll, practice, user, slack_user, location):
    """Plain ints for every row a test created, captured before its `try`.

    Python evaluates a call's arguments before invoking it, so
    `_cleanup(poll.id, practice.id, ...)` written at the `finally` site
    resolves five ORM attributes BEFORE _cleanup's own db.session.rollback()
    runs. On a session already poisoned by a failing assertion (a regression
    that makes handle_availability_reaction violate uq_poll_practice_user,
    say) that attribute access hits SQLAlchemy's expired-attribute refresh and
    raises PendingRollbackError -- so cleanup never executes, six rows leak
    into the shared dev database, and the PendingRollbackError masks the
    original failure in the report.

    Same rule and the same reasoning as tests/practices/test_availability_nudge.py.
    """
    return (poll.id, practice.id, user.id, slack_user.id, location.id)


def _cleanup(poll_id=None, practice_id=None, user_id=None, slack_user_id=None,
             location_id=None):
    """Delete only the rows this test created.

    Rolls back first so a poisoned session (e.g. a prior statement that
    raised and left the transaction aborted) doesn't turn this cleanup
    itself into an error that leaves debris behind for the next test.
    Deleting the poll first cascades to its poll-practice mapping,
    participants, and responses; the user must go before its slack_user
    (User.slack_user_id is the FK); the practice can go any time after the
    poll (which held the only FK to it); the location goes last since the
    practice holds the only FK to it.
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
    db.session.flush()
    if location_id is not None:
        location = db.session.get(PracticeLocation, location_id)
        if location is not None:
            db.session.delete(location)
    db.session.commit()


def test_letter_reaction_records_availability(db_session):
    poll, practice, user, slack_user, location = _setup(db_session, "111.1")
    ids = _row_ids(poll, practice, user, slack_user, location)
    try:
        result = handle_availability_reaction(
            channel=TEST_CHANNEL_ID, message_ts="111.1", reaction="letter_a",
            slack_user_id=slack_user.slack_uid, removed=False)

        assert result["success"] is True
        row = LeadAvailabilityResponse.query.filter_by(poll_id=poll.id).one()
        assert row.practice_id == practice.id and row.user_id == user.id
        assert row.answered_for_date == practice.date, "snapshot for staleness detection"
        assert practice.location_id is not None, "test practice must have a real location"
        assert row.answered_for_location_id == practice.location_id, \
            "location must be snapshotted, not left null"

        participant = LeadAvailabilityParticipant.query.filter_by(
            poll_id=poll.id, user_id=user.id).one()
        assert participant.status == ParticipantStatus.RESPONDED, \
            "a fresh letter reaction must flip a pending participant to responded"
    finally:
        _cleanup(*ids)


def test_removing_the_reaction_deletes_the_row(db_session):
    poll, practice, user, slack_user, location = _setup(db_session, "111.2")
    ids = _row_ids(poll, practice, user, slack_user, location)
    try:
        handle_availability_reaction(channel=TEST_CHANNEL_ID, message_ts="111.2",
                                     reaction="letter_a", slack_user_id=slack_user.slack_uid,
                                     removed=False)

        handle_availability_reaction(channel=TEST_CHANNEL_ID, message_ts="111.2",
                                     reaction="letter_a", slack_user_id=slack_user.slack_uid,
                                     removed=True)

        assert LeadAvailabilityResponse.query.filter_by(poll_id=poll.id).count() == 0
    finally:
        _cleanup(*ids)


def test_done_emoji_marks_participant_done_without_a_response_row(db_session):
    poll, practice, user, slack_user, location = _setup(db_session, "111.3")
    ids = _row_ids(poll, practice, user, slack_user, location)
    try:
        handle_availability_reaction(channel=TEST_CHANNEL_ID, message_ts="111.3",
                                     reaction="white_check_mark", slack_user_id=slack_user.slack_uid,
                                     removed=False)

        participant = LeadAvailabilityParticipant.query.filter_by(
            poll_id=poll.id, user_id=user.id).one()
        assert participant.status == ParticipantStatus.DONE
        assert LeadAvailabilityResponse.query.filter_by(poll_id=poll.id).count() == 0, \
            "done is not availability for any session"

        handle_availability_reaction(channel=TEST_CHANNEL_ID, message_ts="111.3",
                                     reaction="white_check_mark", slack_user_id=slack_user.slack_uid,
                                     removed=True)

        db.session.refresh(participant)
        assert participant.status == ParticipantStatus.PENDING, \
            "removing the done reaction must return the participant to pending"
    finally:
        _cleanup(*ids)


def test_unmapped_emoji_is_ignored(db_session):
    poll, practice, user, slack_user, location = _setup(db_session, "111.4")
    ids = _row_ids(poll, practice, user, slack_user, location)
    try:
        result = handle_availability_reaction(channel=TEST_CHANNEL_ID, message_ts="111.4",
                                              reaction="tada", slack_user_id=slack_user.slack_uid,
                                              removed=False)
        assert result["ignored"] == "unmapped_emoji"
        assert LeadAvailabilityResponse.query.filter_by(poll_id=poll.id).count() == 0
        assert LeadAvailabilityParticipant.query.filter_by(
            poll_id=poll.id, user_id=user.id).first() is None, \
            "an unmapped emoji must not create participant state"
    finally:
        _cleanup(*ids)


def test_non_poll_message_returns_none_so_attendance_still_runs(db_session):
    poll, practice, user, slack_user, location = _setup(db_session, "111.5")
    ids = _row_ids(poll, practice, user, slack_user, location)
    try:
        assert handle_availability_reaction(
            channel=TEST_CHANNEL_ID, message_ts="999.9", reaction="letter_a",
            slack_user_id=slack_user.slack_uid, removed=False) is None
    finally:
        _cleanup(*ids)


def test_unlinked_slack_user_is_ignored_not_crashed(db_session):
    poll, practice, user, slack_user, location = _setup(db_session, "111.6")
    ids = _row_ids(poll, practice, user, slack_user, location)
    try:
        result = handle_availability_reaction(channel=TEST_CHANNEL_ID, message_ts="111.6",
                                              reaction="letter_a", slack_user_id="TEST-U-UNKNOWN",
                                              removed=False)
        assert result["ignored"] == "unlinked_user"
    finally:
        _cleanup(*ids)


def test_reconcile_adds_missed_and_removes_stale(db_session):
    poll, practice, user, slack_user, location = _setup(db_session, "111.7")
    ids = _row_ids(poll, practice, user, slack_user, location)
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
        _cleanup(*ids)


def test_reconcile_adds_missed_response_with_snapshot(db_session):
    """The add half of reconciliation: Slack shows a letter reaction we never
    recorded (the add event was lost). This is the brief's headline
    requirement for reconcile_poll -- unlike the remove-only test above,
    should_have is non-empty here so the add branch actually executes.
    """
    poll, practice, user, slack_user, location = _setup(db_session, "111.13")
    ids = _row_ids(poll, practice, user, slack_user, location)
    try:
        client = MagicMock()
        client.reactions_get.return_value = {
            "message": {"reactions": [
                {"name": "letter_a", "users": [slack_user.slack_uid]},
            ]}
        }

        with patch("app.slack.practices.availability_reactions.get_slack_client",
                   return_value=client):
            result = reconcile_poll(poll)

        assert result["added"] == 1, "a reaction Slack shows but we never recorded must be added"
        row = LeadAvailabilityResponse.query.filter_by(poll_id=poll.id).one()
        assert row.practice_id == practice.id and row.user_id == user.id
        assert row.answered_for_date == practice.date
        assert practice.location_id is not None
        assert row.answered_for_location_id == practice.location_id, \
            "the add path must snapshot the real location, not null"
    finally:
        _cleanup(*ids)


def test_reconcile_recovers_missed_participant_to_responded(db_session):
    """Fix for: a lead's reaction ADD event is lost during a deploy, so no
    participant row was ever created for them. Reconciliation re-reads
    Slack, sees the letter reaction, and must not leave the recovered
    responder looking un-answered (stuck at pending/no-row) -- that is
    exactly the case reconciliation exists to correct.
    """
    poll, practice, user, slack_user, location = _setup(db_session, "111.9")
    ids = _row_ids(poll, practice, user, slack_user, location)
    try:
        assert LeadAvailabilityParticipant.query.filter_by(
            poll_id=poll.id, user_id=user.id).first() is None, \
            "precondition: no participant row exists yet"

        client = MagicMock()
        client.reactions_get.return_value = {
            "message": {"reactions": [
                {"name": "letter_a", "users": [slack_user.slack_uid]},
            ]}
        }

        with patch("app.slack.practices.availability_reactions.get_slack_client",
                   return_value=client):
            reconcile_poll(poll)

        participant = LeadAvailabilityParticipant.query.filter_by(
            poll_id=poll.id, user_id=user.id).one()
        assert participant.status == ParticipantStatus.RESPONDED
    finally:
        _cleanup(*ids)


def test_reconcile_demotes_stale_done_to_responded_when_response_survives(db_session):
    """Fix for: a lead removes ✅ intending to add more sessions, but the
    removal event is lost. Reconciliation must not leave them at DONE just
    because nobody promoted them -- it must actively demote based on what
    Slack shows now.
    """
    poll, practice, user, slack_user, location = _setup(db_session, "111.10")
    ids = _row_ids(poll, practice, user, slack_user, location)
    try:
        db_session.add(LeadAvailabilityParticipant(
            poll_id=poll.id, user_id=user.id, status=ParticipantStatus.DONE))
        db_session.add(LeadAvailabilityResponse(
            poll_id=poll.id, practice_id=practice.id, user_id=user.id, source="reaction"))
        db_session.commit()

        client = MagicMock()
        client.reactions_get.return_value = {
            "message": {"reactions": [
                {"name": "letter_a", "users": [slack_user.slack_uid]},
            ]}
        }  # no white_check_mark -- the checkmark was removed on Slack

        with patch("app.slack.practices.availability_reactions.get_slack_client",
                   return_value=client):
            reconcile_poll(poll)

        participant = LeadAvailabilityParticipant.query.filter_by(
            poll_id=poll.id, user_id=user.id).one()
        assert participant.status == ParticipantStatus.RESPONDED, \
            "a stale DONE with surviving responses must fall back to responded"
    finally:
        _cleanup(*ids)


def test_reconcile_demotes_stale_done_to_pending_when_no_responses_remain(db_session):
    poll, practice, user, slack_user, location = _setup(db_session, "111.11")
    ids = _row_ids(poll, practice, user, slack_user, location)
    try:
        db_session.add(LeadAvailabilityParticipant(
            poll_id=poll.id, user_id=user.id, status=ParticipantStatus.DONE))
        db_session.commit()

        client = MagicMock()
        client.reactions_get.return_value = {"message": {"reactions": []}}

        with patch("app.slack.practices.availability_reactions.get_slack_client",
                   return_value=client):
            reconcile_poll(poll)

        participant = LeadAvailabilityParticipant.query.filter_by(
            poll_id=poll.id, user_id=user.id).one()
        assert participant.status == ParticipantStatus.PENDING, \
            "a stale DONE with no surviving responses must fall back to pending"
    finally:
        _cleanup(*ids)


def test_reconcile_leaves_opted_out_participant_alone(db_session):
    poll, practice, user, slack_user, location = _setup(db_session, "111.12")
    ids = _row_ids(poll, practice, user, slack_user, location)
    try:
        db_session.add(LeadAvailabilityParticipant(
            poll_id=poll.id, user_id=user.id, status=ParticipantStatus.OPTED_OUT))
        db_session.commit()

        client = MagicMock()
        client.reactions_get.return_value = {"message": {"reactions": []}}

        with patch("app.slack.practices.availability_reactions.get_slack_client",
                   return_value=client):
            reconcile_poll(poll)

        participant = LeadAvailabilityParticipant.query.filter_by(
            poll_id=poll.id, user_id=user.id).one()
        assert participant.status == ParticipantStatus.OPTED_OUT, \
            "opted_out is a deliberate user choice, not derived state -- reconcile must not touch it"
    finally:
        _cleanup(*ids)


def test_reconcile_survives_a_non_slack_api_error(db_session):
    """get_slack_client() raises plain ValueError when SLACK_BOT_TOKEN is
    unset, and transport failures raise TimeoutError -- neither is a
    SlackApiError, so a bare `except SlackApiError` would let this crash the
    caller instead of returning a clean failure result.
    """
    poll, practice, user, slack_user, location = _setup(db_session, "111.8")
    ids = _row_ids(poll, practice, user, slack_user, location)
    try:
        with patch("app.slack.practices.availability_reactions.get_slack_client",
                   side_effect=TimeoutError("boom")):
            result = reconcile_poll(poll)

        assert result["added"] == 0 and result["removed"] == 0
        assert "error" in result
    finally:
        _cleanup(*ids)


# ---------------------------------------------------------------------------
# Done-emoji snapshot (mirrors the letter mapping): editing
# lead_availability.done_emoji while a poll is open must not change which
# reactions count as "done" for that poll.
# ---------------------------------------------------------------------------


def test_done_reaction_matches_the_polls_snapshot_not_current_config(db_session):
    poll, practice, user, slack_user, location = _setup(db_session, "111.20")
    ids = _row_ids(poll, practice, user, slack_user, location)
    try:
        poll.done_emoji = "TEST_snap_done"
        db_session.commit()

        with patch(
            "app.slack.practices._config._load_practice_config",
            return_value={"lead_availability": {"done_emoji": "TEST_renamed_done"}},
        ):
            handle_availability_reaction(
                channel=TEST_CHANNEL_ID, message_ts="111.20",
                reaction="TEST_snap_done", slack_user_id=slack_user.slack_uid,
                removed=False)

        participant = LeadAvailabilityParticipant.query.filter_by(
            poll_id=poll.id, user_id=user.id).one()
        assert participant.status == ParticipantStatus.DONE, (
            "the poll's snapshotted done emoji must keep working after a "
            "config rename"
        )
    finally:
        _cleanup(*ids)


def test_reconcile_counts_done_under_the_polls_snapshotted_emoji(db_session):
    """The dangerous half: reconcile computing done_user_ids from the NEW
    config value would demote every already-DONE participant, and the nudge
    job would then DM leads who had declared themselves finished -- exactly
    the bug class the persisted letter mapping exists to prevent."""
    poll, practice, user, slack_user, location = _setup(db_session, "111.21")
    ids = _row_ids(poll, practice, user, slack_user, location)
    try:
        poll.done_emoji = "TEST_snap_done"
        db_session.add(LeadAvailabilityParticipant(
            poll_id=poll.id, user_id=user.id, status=ParticipantStatus.DONE))
        db_session.commit()

        client = MagicMock()
        client.reactions_get.return_value = {
            "message": {"reactions": [
                {"name": "TEST_snap_done", "users": [slack_user.slack_uid]}]}
        }

        with patch("app.slack.practices.availability_reactions.get_slack_client",
                   return_value=client), \
             patch("app.slack.practices._config._load_practice_config",
                   return_value={"lead_availability": {"done_emoji": "TEST_renamed_done"}}):
            reconcile_poll(poll)

        participant = LeadAvailabilityParticipant.query.filter_by(
            poll_id=poll.id, user_id=user.id).one()
        assert participant.status == ParticipantStatus.DONE, (
            "a mid-poll config rename must not demote DONE participants"
        )
    finally:
        _cleanup(*ids)


def test_a_reaction_on_a_cancelled_practice_is_not_recorded(db_session):
    """A cancelled session's line is dropped from the poll message, but its
    seeded pill stays on it — nothing removes reactions from a live message.
    So a lead can still tap a letter whose line is gone, and that used to
    write a real availability response for a practice that isn't happening,
    inflating every count the director reads.
    """
    poll, practice, user, slack_user, location = _setup(db_session, "111.30")
    ids = _row_ids(poll, practice, user, slack_user, location)
    practice.status = PracticeStatus.CANCELLED.value
    db_session.commit()

    try:
        result = handle_availability_reaction(
            channel=TEST_CHANNEL_ID, message_ts="111.30", reaction="letter_a",
            slack_user_id=slack_user.slack_uid,
        )

        assert result == {"success": True, "ignored": "cancelled_practice"}
        assert LeadAvailabilityResponse.query.filter_by(
            poll_id=ids[0], practice_id=ids[1]).count() == 0, \
            "no availability may be recorded for a cancelled session"
    finally:
        _cleanup(*ids)


def test_withdrawing_a_reaction_on_a_cancelled_practice_still_cleans_up(db_session):
    """The guard is one-directional on purpose: a response recorded before the
    cancellation must still be removable, or a lead who un-reacts is stuck
    counted for a session that isn't happening.
    """
    poll, practice, user, slack_user, location = _setup(db_session, "111.31")
    ids = _row_ids(poll, practice, user, slack_user, location)

    try:
        handle_availability_reaction(
            channel=TEST_CHANNEL_ID, message_ts="111.31", reaction="letter_a",
            slack_user_id=slack_user.slack_uid,
        )
        assert LeadAvailabilityResponse.query.filter_by(
            poll_id=ids[0], practice_id=ids[1]).count() == 1, "sanity"

        practice.status = PracticeStatus.CANCELLED.value
        db_session.commit()

        handle_availability_reaction(
            channel=TEST_CHANNEL_ID, message_ts="111.31", reaction="letter_a",
            slack_user_id=slack_user.slack_uid, removed=True,
        )
        assert LeadAvailabilityResponse.query.filter_by(
            poll_id=ids[0], practice_id=ids[1]).count() == 0, \
            "withdrawal must still work after the practice is cancelled"
    finally:
        _cleanup(*ids)


def test_reconcile_does_not_re_add_a_cancelled_practices_responses(db_session):
    """The guard has to hold in reconcile too, or it is decorative.

    reconcile_poll re-derives responses from Slack's live reactions, and the
    cancelled session's pill is still on the message with the lead's reaction
    on it — so without this, the very next nudge run would put back every row
    handle_availability_reaction just declined to write.
    """
    poll, practice, user, slack_user, location = _setup(db_session, "111.32")
    ids = _row_ids(poll, practice, user, slack_user, location)

    try:
        # Recorded while the practice was live, then cancelled.
        handle_availability_reaction(
            channel=TEST_CHANNEL_ID, message_ts="111.32", reaction="letter_a",
            slack_user_id=slack_user.slack_uid,
        )
        practice.status = PracticeStatus.CANCELLED.value
        db_session.commit()

        client = MagicMock()
        client.reactions_get.return_value = {
            "message": {"reactions": [
                {"name": "letter_a", "users": [slack_user.slack_uid]},
            ]}
        }
        with patch("app.slack.practices.availability_reactions.get_slack_client",
                   return_value=client):
            result = reconcile_poll(poll)

        assert result.get("error") is None
        assert LeadAvailabilityResponse.query.filter_by(
            poll_id=ids[0], practice_id=ids[1]).count() == 0, (
            "reconcile must drop the stale row for a cancelled session, not "
            "re-add it from the surviving reaction pill"
        )
    finally:
        _cleanup(*ids)
