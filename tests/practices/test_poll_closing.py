"""Poll closing.

Dates use year 2099 and the channel/message fields carry a "TEST" marker per
tests/practices/conftest.py -- this suite runs against the real local dev
database, and 2026 (the year the brief's own example used) is now the real
near future, so it can't be used here without risking a collision with real
practice data. See test_availability_service.py for the same adaptation.
"""

from datetime import date, datetime
from unittest.mock import patch

from app.models import db
from app.practices.availability import close_poll
from app.practices.availability_models import LeadAvailabilityPoll, PollStatus


def _poll(db_session, ends_on):
    poll = LeadAvailabilityPoll(
        starts_on=date(2099, 8, 1), ends_on=ends_on, channel_id="TEST_C1",
        message_ts="1.1", status=PollStatus.OPEN, opened_at=datetime(2099, 8, 1),
    )
    db_session.add(poll)
    db_session.commit()
    return poll


def _cleanup_poll(poll_id):
    """Roll back first so a poisoned session from a failed assertion doesn't
    turn this cleanup itself into a PendingRollbackError that leaves debris
    behind for the next test to trip over.
    """
    db.session.rollback()
    obj = db.session.get(LeadAvailabilityPoll, poll_id)
    if obj is not None:
        db.session.delete(obj)
    db.session.commit()


def test_closing_reconciles_first(db_session):
    poll = _poll(db_session, date(2099, 8, 31))
    poll_id = poll.id

    try:
        with patch("app.practices.availability.reconcile_poll") as reconcile:
            reconcile.return_value = {"added": 0, "removed": 1}
            result = close_poll(poll)

        reconcile.assert_called_once_with(poll)
        assert result["success"] is True
        assert poll.status == PollStatus.CLOSED
        assert poll.closed_at is not None
    finally:
        _cleanup_poll(poll_id)


def test_closing_twice_is_harmless(db_session):
    poll = _poll(db_session, date(2099, 8, 31))
    poll_id = poll.id

    try:
        with patch("app.practices.availability.reconcile_poll", return_value={}):
            close_poll(poll)
            result = close_poll(poll)

        assert result["success"] is True
        assert result.get("already_closed") is True
    finally:
        _cleanup_poll(poll_id)


def test_expired_polls_close_automatically(db_session, app):
    from app.scheduler import run_close_expired_polls_job

    past = _poll(db_session, date(2099, 8, 1))
    future = _poll(db_session, date(2099, 10, 1))
    past_id = past.id
    future_id = future.id

    try:
        with patch("app.practices.availability.reconcile_poll", return_value={}), \
             patch("app.scheduler.today_central", return_value=date(2099, 8, 15)):
            run_close_expired_polls_job(app)

        # The job runs its own `with app.app_context():`, which is a second,
        # distinct SQLAlchemy session from this test's `db_session` fixture
        # (Flask-SQLAlchemy scopes a session per app-context push, even
        # nested within the same Flask app). Its commits are durable, but
        # this test's `past`/`future` objects belong to a different session
        # and won't reflect that commit until re-fetched.
        db_session.expire_all()
        assert db_session.get(LeadAvailabilityPoll, past_id).status == PollStatus.CLOSED
        assert db_session.get(LeadAvailabilityPoll, future_id).status == PollStatus.OPEN
    finally:
        _cleanup_poll(past_id)
        _cleanup_poll(future_id)
