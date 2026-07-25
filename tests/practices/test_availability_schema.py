"""Lead availability schema.

Runs against the real local dev database (see tests/practices/conftest.py
docstring) — dates are pinned to year 2099 and the Slack channel id carries a
"TEST" prefix so leaked rows are unmistakable, and every row created here is
deleted in a try/finally so cleanup survives assertion failures.
"""

from datetime import date, datetime
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import User, db
from app.practices.availability_models import (
    LeadAvailabilityPoll,
    LeadAvailabilityPollPractice,
    LeadAvailabilityResponse,
    ParticipantStatus,
    PollStatus,
)
from app.practices.models import Practice

TEST_CHANNEL_ID = "TEST-CHANNEL"

_POLL_STARTS_ON = date(2099, 7, 21)
_POLL_ENDS_ON = date(2099, 8, 13)
_SLOT_A = datetime(2099, 8, 4, 18, 15)
_SLOT_B = datetime(2099, 8, 6, 18, 15)


def _poll():
    poll = LeadAvailabilityPoll(
        starts_on=_POLL_STARTS_ON,
        ends_on=_POLL_ENDS_ON,
        channel_id=TEST_CHANNEL_ID,
    )
    db.session.add(poll)
    db.session.flush()
    return poll


def _practice(dt):
    p = Practice(date=dt, day_of_week="Tuesday", is_draft=True)
    db.session.add(p)
    db.session.flush()
    return p


def _user():
    # user_id is a real FK to users.id — there's no guarantee a user with a
    # small hardcoded id exists in this shared dev database, so a throwaway
    # row is created here (unique email via uuid4) rather than assumed.
    u = User(
        first_name="TEST",
        last_name="Availability",
        email=f"test-availability-{uuid4().hex}@example.test",
    )
    db.session.add(u)
    db.session.flush()
    return u


def _cleanup(poll_ids=(), practice_ids=(), user_ids=()):
    """Delete only the rows this test created, scoped by id captured earlier.

    Deleting the poll first cascades to its poll-practices/participants/
    responses (see LeadAvailabilityPoll relationships), which clears any FK
    reference to the practices/users before those are deleted. A prior
    rollback() is required first in case the test under test left the
    session's transaction aborted (e.g. after an IntegrityError from
    pytest.raises).
    """
    db.session.rollback()
    for poll_id in poll_ids:
        poll = db.session.get(LeadAvailabilityPoll, poll_id)
        if poll is not None:
            db.session.delete(poll)
    db.session.flush()
    for practice_id in practice_ids:
        practice = db.session.get(Practice, practice_id)
        if practice is not None:
            db.session.delete(practice)
    db.session.flush()
    for user_id in user_ids:
        user = db.session.get(User, user_id)
        if user is not None:
            db.session.delete(user)
    db.session.commit()


def test_poll_defaults_to_draft_and_not_shadow(db_session):
    poll = _poll()
    poll_id = poll.id
    db_session.commit()
    try:
        assert poll.status == PollStatus.DRAFT
        assert poll.is_shadow is False
    finally:
        _cleanup(poll_ids=[poll_id])


def test_emoji_is_unique_within_a_poll(db_session):
    poll, a, b = _poll(), _practice(_SLOT_A), _practice(_SLOT_B)
    poll_id, a_id, b_id = poll.id, a.id, b.id
    db_session.add(LeadAvailabilityPollPractice(
        poll_id=poll.id, practice_id=a.id, emoji="letter_a", position=0))
    db_session.add(LeadAvailabilityPollPractice(
        poll_id=poll.id, practice_id=b.id, emoji="letter_a", position=1))
    try:
        with pytest.raises(IntegrityError):
            db_session.commit()
    finally:
        _cleanup(poll_ids=[poll_id], practice_ids=[a_id, b_id])


def test_one_response_per_person_per_practice(db_session):
    poll, practice, user = _poll(), _practice(_SLOT_A), _user()
    poll_id, practice_id, user_id = poll.id, practice.id, user.id
    db_session.commit()
    try:
        for _ in range(2):
            db_session.add(LeadAvailabilityResponse(
                poll_id=poll_id, practice_id=practice_id, user_id=user_id,
                source="reaction"))
        with pytest.raises(IntegrityError):
            db_session.commit()
    finally:
        _cleanup(poll_ids=[poll_id], practice_ids=[practice_id], user_ids=[user_id])


def test_response_snapshots_practice_details(db_session):
    poll, practice, user = _poll(), _practice(_SLOT_A), _user()
    poll_id, practice_id, user_id = poll.id, practice.id, user.id
    response = LeadAvailabilityResponse(
        poll_id=poll_id, practice_id=practice_id, user_id=user_id, source="reaction",
        answered_for_date=practice.date, answered_for_location_id=practice.location_id,
    )
    db_session.add(response)
    db_session.commit()
    try:
        assert response.answered_for_date == _SLOT_A
    finally:
        _cleanup(poll_ids=[poll_id], practice_ids=[practice_id], user_ids=[user_id])


def test_participant_statuses_exist():
    assert ParticipantStatus.PENDING == "pending"
    assert ParticipantStatus.RESPONDED == "responded"
    assert ParticipantStatus.DONE == "done"
    assert ParticipantStatus.OPTED_OUT == "opted_out"
