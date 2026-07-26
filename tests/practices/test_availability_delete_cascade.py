"""Deleting a practice must remove its availability-poll rows.

Two tables FK to ``practices.id`` (``lead_availability_poll_practices``,
``lead_availability_responses``); before the practice-side cascade existed,
deleting a polled practice raised ForeignKeyViolation. The cascade is
ORM-level, so these tests delete through the ORM (session and the admin
route) — never in bulk.

Runs against the real local dev database (see conftest.py): dates use year
2099, strings carry a "TEST " prefix, ids are captured as plain ints before
the try, and cleanup runs in a finally with a rollback first.
"""

from datetime import date, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.models import User, db
from app.practices.availability_models import (
    LeadAvailabilityPoll,
    LeadAvailabilityPollPractice,
    LeadAvailabilityResponse,
    PollStatus,
)
from app.practices.models import Practice


def _scenario():
    """An OPEN poll covering two practices, each with one response."""
    doomed = Practice(
        date=datetime(2099, 9, 8, 18, 15), day_of_week="Tuesday",
        is_draft=True,
    )
    kept = Practice(
        date=datetime(2099, 9, 10, 18, 15), day_of_week="Thursday",
        is_draft=True,
    )
    user = User(
        first_name="TEST",
        last_name="Cascade",
        email=f"test-cascade-{uuid4().hex}@example.test",
    )
    db.session.add_all([doomed, kept, user])
    db.session.flush()

    poll = LeadAvailabilityPoll(
        starts_on=date(2099, 9, 1),
        ends_on=date(2099, 9, 30),
        status=PollStatus.OPEN,
        channel_id="TEST_C_CASCADE",
        message_ts="1786.1",
    )
    db.session.add(poll)
    db.session.flush()
    for position, (practice, emoji) in enumerate(
        [(doomed, "letter_a"), (kept, "letter_b")]
    ):
        db.session.add(LeadAvailabilityPollPractice(
            poll_id=poll.id,
            practice_id=practice.id,
            emoji=emoji,
            position=position,
        ))
        db.session.add(LeadAvailabilityResponse(
            poll_id=poll.id,
            practice_id=practice.id,
            user_id=user.id,
            source="reaction",
        ))
    db.session.commit()
    return doomed.id, kept.id, user.id, poll.id


def _cleanup(poll_id, practice_ids, user_id):
    """Poll first (its rows cascade), then practices, then the user."""
    db.session.rollback()
    poll = db.session.get(LeadAvailabilityPoll, poll_id)
    if poll is not None:
        db.session.delete(poll)
    db.session.flush()
    for practice_id in practice_ids:
        practice = db.session.get(Practice, practice_id)
        if practice is not None:
            db.session.delete(practice)
    db.session.flush()
    user = db.session.get(User, user_id)
    if user is not None:
        db.session.delete(user)
    db.session.commit()


def _assert_practice_rows_cascaded(doomed_id, kept_id, poll_id):
    """The doomed practice's rows are gone; the poll and the other
    session's rows survive."""
    assert db.session.get(Practice, doomed_id) is None
    assert LeadAvailabilityPollPractice.query.filter_by(
        practice_id=doomed_id
    ).count() == 0
    assert LeadAvailabilityResponse.query.filter_by(
        practice_id=doomed_id
    ).count() == 0

    assert db.session.get(LeadAvailabilityPoll, poll_id) is not None
    assert LeadAvailabilityPollPractice.query.filter_by(
        poll_id=poll_id, practice_id=kept_id
    ).count() == 1
    assert LeadAvailabilityResponse.query.filter_by(
        poll_id=poll_id, practice_id=kept_id
    ).count() == 1


def test_deleting_a_polled_practice_cascades_only_its_own_rows(db_session):
    doomed_id, kept_id, user_id, poll_id = _scenario()
    try:
        db_session.delete(db_session.get(Practice, doomed_id))
        db_session.commit()

        _assert_practice_rows_cascaded(doomed_id, kept_id, poll_id)
    finally:
        _cleanup(poll_id, [doomed_id, kept_id], user_id)


def test_delete_route_succeeds_for_a_polled_practice(app):
    """End to end through the admin route — it is the route users hit, and
    it refreshes Slack (mocked here) before deleting the row."""
    with app.app_context():
        doomed_id, kept_id, user_id, poll_id = _scenario()

    client = app.test_client()
    with client.session_transaction() as session:
        session["user"] = {
            "email": "tester@twincitiesskiclub.org",
            "name": "Tester",
        }

    slack = MagicMock()
    try:
        with patch("app.slack.client.get_slack_client", return_value=slack):
            response = client.post(f"/admin/practices/{doomed_id}/delete")

        assert response.status_code == 200
        assert response.get_json() == {
            "success": True,
            "message": "Practice deleted successfully",
        }
        with app.app_context():
            _assert_practice_rows_cascaded(doomed_id, kept_id, poll_id)
    finally:
        with app.app_context():
            _cleanup(poll_id, [doomed_id, kept_id], user_id)
