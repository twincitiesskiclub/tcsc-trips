"""Nudge eligibility — the cadence rules are the whole point.

Adapted from the task brief for this repo's real-database test conventions
(see tests/practices/conftest.py): year-2099 dates, "TEST " prefixed rows,
and try/finally cleanup with rollback-first. The brief's literal fixtures
used bare integers (1, 2, 3) for LeadAvailabilityParticipant.user_id and a
"user_id" kwarg on SlackUser; neither is valid against the actual
FK-constrained schema (users.id is a foreign key on participants, and
SlackUser has no user_id column -- the FK lives on User.slack_user_id), so
every participant here is backed by a real User row, matching the fix
already made for this same brief mismatch in
tests/slack/test_availability_reactions.py.
"""

from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.models import SlackUser, User, db
from app.practices.availability import (
    participants_to_nudge,
    send_nudges,
    sync_participants,
)
from app.practices.availability_models import (
    LeadAvailabilityParticipant,
    LeadAvailabilityPoll,
    ParticipantStatus,
    PollStatus,
)

OPENED = datetime(2099, 7, 21, 9, 0)
_STARTS_ON = date(2099, 7, 21)
_ENDS_ON = date(2099, 8, 13)


def _poll(db_session):
    poll = LeadAvailabilityPoll(
        starts_on=_STARTS_ON, ends_on=_ENDS_ON,
        channel_id="TEST-CHANNEL-NUDGE", message_ts="1.1",
        status=PollStatus.OPEN, opened_at=OPENED,
    )
    db_session.add(poll)
    db_session.flush()
    return poll


def _user(db_session, name, with_slack=False):
    """A real User row -- LeadAvailabilityParticipant.user_id is FK-constrained
    to users.id, so a bare int (as in the brief's literal fixtures) would
    violate the constraint against this real Postgres dev database.
    """
    suffix = uuid4().hex
    slack_user_id = None
    if with_slack:
        slack_user = SlackUser(slack_uid=f"TEST-U-{suffix}")
        db_session.add(slack_user)
        db_session.flush()
        slack_user_id = slack_user.id
    user = User(first_name=f"TEST {name}", last_name="Nudge",
                email=f"test-nudge-{name.lower()}-{suffix}@example.test",
                slack_user_id=slack_user_id)
    db_session.add(user)
    db_session.flush()
    return user


def _participant(db_session, poll, user, **kw):
    p = LeadAvailabilityParticipant(poll_id=poll.id, user_id=user.id, **kw)
    db_session.add(p)
    db_session.flush()
    return p


def _cleanup(poll_id=None, user_ids=None):
    """Delete only the rows this test created.

    Rolls back first so a poisoned session (e.g. a prior statement that
    raised and left the transaction aborted) doesn't turn this cleanup
    itself into an error that leaves debris behind for the next test.
    Deleting the poll first cascades to its participants (poll_id FK); each
    user's slack_user (if any) must go after the user, since User.slack_user_id
    is the FK pointing at it.
    """
    db.session.rollback()
    if poll_id is not None:
        poll = db.session.get(LeadAvailabilityPoll, poll_id)
        if poll is not None:
            db.session.delete(poll)
    db.session.flush()
    for user_id in (user_ids or []):
        user = db.session.get(User, user_id)
        if user is None:
            continue
        slack_user_id = user.slack_user_id
        db.session.delete(user)
        db.session.flush()
        if slack_user_id is not None:
            slack_user = db.session.get(SlackUser, slack_user_id)
            if slack_user is not None:
                db.session.delete(slack_user)
    db.session.commit()


def test_nobody_is_nudged_before_day_three(db_session):
    poll = _poll(db_session)
    user = _user(db_session, "Ada")
    _participant(db_session, poll, user, status=ParticipantStatus.PENDING)
    db_session.commit()

    try:
        assert participants_to_nudge(poll, now=OPENED + timedelta(days=2)) == []
    finally:
        _cleanup(poll.id, [user.id])


def test_pending_participant_is_nudged_on_day_three(db_session):
    poll = _poll(db_session)
    user = _user(db_session, "Ada")
    p = _participant(db_session, poll, user, status=ParticipantStatus.PENDING)
    db_session.commit()

    try:
        due = participants_to_nudge(poll, now=OPENED + timedelta(days=3))
        assert [x.id for x in due] == [p.id]
    finally:
        _cleanup(poll.id, [user.id])


def test_responded_and_done_and_opted_out_are_never_nudged(db_session):
    poll = _poll(db_session)
    users = [_user(db_session, f"U{i}") for i in range(3)]
    for user, status in zip(users, (ParticipantStatus.RESPONDED, ParticipantStatus.DONE,
                                     ParticipantStatus.OPTED_OUT)):
        _participant(db_session, poll, user, status=status)
    db_session.commit()

    try:
        assert participants_to_nudge(poll, now=OPENED + timedelta(days=10)) == []
    finally:
        _cleanup(poll.id, [u.id for u in users])


def test_nudges_are_spaced_at_least_two_days(db_session):
    poll = _poll(db_session)
    user = _user(db_session, "Ada")
    _participant(db_session, poll, user, status=ParticipantStatus.PENDING,
                 nudge_count=1, last_nudged_at=OPENED + timedelta(days=3))
    db_session.commit()

    try:
        assert participants_to_nudge(poll, now=OPENED + timedelta(days=4)) == []
        assert len(participants_to_nudge(poll, now=OPENED + timedelta(days=5))) == 1
    finally:
        _cleanup(poll.id, [user.id])


def test_three_nudges_is_the_ceiling(db_session):
    poll = _poll(db_session)
    user = _user(db_session, "Ada")
    _participant(db_session, poll, user, status=ParticipantStatus.PENDING,
                 nudge_count=3, last_nudged_at=OPENED + timedelta(days=7))
    db_session.commit()

    try:
        assert participants_to_nudge(poll, now=OPENED + timedelta(days=30)) == [], \
            "3 sends is the ceiling; more trains people to mute the bot"
    finally:
        _cleanup(poll.id, [user.id])


def test_sync_participants_adds_new_leads_only(db_session):
    poll = _poll(db_session)
    existing_user = _user(db_session, "Existing")
    new_user = _user(db_session, "New")
    _participant(db_session, poll, existing_user, status=ParticipantStatus.RESPONDED)
    db_session.commit()

    try:
        with patch("app.practices.availability.eligible_leads",
                   return_value=[existing_user, new_user]):
            added = sync_participants(poll)

        assert added == 1
        assert LeadAvailabilityParticipant.query.filter_by(poll_id=poll.id).count() == 2
    finally:
        _cleanup(poll.id, [existing_user.id, new_user.id])


def test_send_nudges_records_the_send(db_session, app):
    poll = _poll(db_session)
    user = _user(db_session, "Ada", with_slack=True)
    _participant(db_session, poll, user, status=ParticipantStatus.PENDING)
    db_session.commit()

    client = MagicMock()
    client.chat_getPermalink.return_value = {"permalink": "https://slack/p/1"}

    try:
        with patch("app.slack.practices.availability_nudge.get_slack_client",
                   return_value=client):
            result = send_nudges(poll, now=OPENED + timedelta(days=3))

        assert result["sent"] == 1
        participant = LeadAvailabilityParticipant.query.filter_by(
            poll_id=poll.id, user_id=user.id).one()
        assert participant.nudge_count == 1
        assert participant.last_nudged_at is not None
    finally:
        _cleanup(poll.id, [user.id])
