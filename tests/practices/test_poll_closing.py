"""Poll closing.

Dates use year 2099 and the channel/message fields carry a "TEST" marker per
tests/practices/conftest.py -- this suite runs against the real local dev
database, and 2026 (the year the brief's own example used) is now the real
near future, so it can't be used here without risking a collision with real
practice data. See test_availability_service.py for the same adaptation.
"""

from datetime import date, datetime
from unittest.mock import patch

import pytest

from app.models import db
from app.practices.availability import close_poll
from app.practices.availability_models import LeadAvailabilityPoll, PollStatus

# The faked clock the batch-job tests run the scheduler under. Deliberately a
# module constant: `protect_foreign_polls` below has to know the same date the
# tests patch in, because that date is what decides which rows the job's
# unscoped query will sweep.
_JOB_TODAY = date(2099, 8, 15)


@pytest.fixture
def protect_foreign_polls(db_session):
    """Snapshot and restore every OPEN poll this file didn't create.

    `run_close_expired_polls_job` queries `status == OPEN AND ends_on < today`
    with no other scope, and these tests patch `today_central` to 2099 — so
    the job closes EVERY open poll in the database, not just the test's own.
    Against the real local dev database (see tests/practices/conftest.py) that
    means a live shadow-mode poll gets silently CLOSED: the nudge job stops
    chasing it, the lead picker treats partial availability as final, and the
    only recovery is a manual UPDATE.

    Restoring rather than refusing keeps the test running in every DB state.
    `reconcile_poll` is patched out in all three job tests, so close_poll's
    only writes are `status` and `closed_at` — both restored exactly here.
    """
    before = [
        (poll.id, poll.status, poll.closed_at)
        for poll in LeadAvailabilityPoll.query.filter(
            LeadAvailabilityPoll.status == PollStatus.OPEN,
            LeadAvailabilityPoll.ends_on < _JOB_TODAY,
        ).all()
    ]
    try:
        yield
    finally:
        db.session.rollback()
        restored = []
        for poll_id, status, closed_at in before:
            poll = db.session.get(LeadAvailabilityPoll, poll_id)
            if poll is not None and poll.status != status:
                poll.status = status
                poll.closed_at = closed_at
                restored.append(poll_id)
        if restored:
            db.session.commit()
            # Loud on purpose: it means a poll outside this suite was live in
            # the dev database and the job reached it.
            print(f"\nprotect_foreign_polls: restored OPEN status on poll(s) {restored}")


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

    # Record the poll's status at the moment reconcile_poll is actually
    # called, not just whether it was called -- a reviewer moved the
    # reconcile call to after the status flip once and every assertion in
    # this test still passed, since none of them checked ordering.
    observed_status = []

    def _record_status_and_reconcile(p):
        observed_status.append(p.status)
        return {"added": 0, "removed": 1}

    try:
        with patch(
            "app.practices.availability.reconcile_poll",
            side_effect=_record_status_and_reconcile,
        ) as reconcile:
            result = close_poll(poll)

        reconcile.assert_called_once_with(poll)
        assert observed_status == [PollStatus.OPEN]
        assert result["success"] is True
        assert poll.status == PollStatus.CLOSED
        assert poll.closed_at is not None
    finally:
        _cleanup_poll(poll_id)


def test_closing_surfaces_reconcile_failure(db_session):
    """A failed final reconcile must not be silently swallowed.

    The poll still closes -- an OPEN poll stuck forever keeps the daily
    nudge job DMing people about a block that already ended, which is
    worse than availability data that may be slightly stale -- but the
    failure must be loud and visible to an operator, since CLOSED polls
    are never reconciled again.
    """
    poll = _poll(db_session, date(2099, 8, 31))
    poll_id = poll.id

    try:
        with patch(
            "app.practices.availability.reconcile_poll",
            return_value={"added": 0, "removed": 0, "error": "channel_not_found"},
        ):
            result = close_poll(poll)

        assert poll.status == PollStatus.CLOSED
        assert result["success"] is True
        assert result.get("reconcile_failed") is True
        assert "channel_not_found" in result.get("error", "")
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


def test_expired_polls_close_automatically(db_session, app, protect_foreign_polls):
    from app.scheduler import run_close_expired_polls_job

    past = _poll(db_session, date(2099, 8, 1))
    future = _poll(db_session, date(2099, 10, 1))
    past_id = past.id
    future_id = future.id

    try:
        with patch("app.practices.availability.reconcile_poll", return_value={}), \
             patch("app.scheduler.today_central", return_value=_JOB_TODAY):
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


def test_poll_ending_today_does_not_close(db_session, app, protect_foreign_polls):
    """The rule is `ends_on < today`, not `<=` -- a block that ends today is
    still in progress and must stay OPEN through the day it ends.
    """
    from app.scheduler import run_close_expired_polls_job

    today_poll = _poll(db_session, date(2099, 8, 15))
    today_id = today_poll.id

    try:
        with patch("app.practices.availability.reconcile_poll", return_value={}), \
             patch("app.scheduler.today_central", return_value=_JOB_TODAY):
            run_close_expired_polls_job(app)

        db_session.expire_all()
        assert db_session.get(LeadAvailabilityPoll, today_id).status == PollStatus.OPEN
    finally:
        _cleanup_poll(today_id)


def test_one_poll_failing_does_not_block_others(db_session, app, protect_foreign_polls):
    """One poll's close() raising must not abort the whole batch, leaving
    later expired polls open for that run -- each poll is handled in its
    own try/except, matching run_lead_availability_nudge_job.
    """
    from app.scheduler import run_close_expired_polls_job

    broken = _poll(db_session, date(2099, 8, 1))
    healthy = _poll(db_session, date(2099, 8, 2))
    broken_id = broken.id
    healthy_id = healthy.id

    from app.practices.availability import close_poll as real_close_poll

    def _flaky_close_poll(poll):
        if poll.id == broken_id:
            raise RuntimeError("boom")
        return real_close_poll(poll)

    try:
        # run_close_expired_polls_job does `from app.practices.availability
        # import close_poll` inside its own function body (re-executed every
        # call), so the patch target is the source module's attribute, not
        # anything already bound in app.scheduler's namespace.
        with patch("app.practices.availability.close_poll", side_effect=_flaky_close_poll), \
             patch("app.practices.availability.reconcile_poll", return_value={}), \
             patch("app.scheduler.today_central", return_value=_JOB_TODAY):
            run_close_expired_polls_job(app)

        db_session.expire_all()
        assert db_session.get(LeadAvailabilityPoll, broken_id).status == PollStatus.OPEN
        assert db_session.get(LeadAvailabilityPoll, healthy_id).status == PollStatus.CLOSED
    finally:
        _cleanup_poll(broken_id)
        _cleanup_poll(healthy_id)
