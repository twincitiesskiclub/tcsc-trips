"""run_lead_availability_nudge_job: ordering, poll filtering, and isolation.

Note on the ``app`` fixture: this file lives directly under ``tests/`` (not
``tests/practices/`` or ``tests/slack/``), which has no shared conftest
providing one, so it's defined locally here following the same pattern as
``tests/test_scheduler_draft_jobs.py``.

Nothing here touches the real database. ``run_lead_availability_nudge_job``
looks up open polls via ``LeadAvailabilityPoll.query``, then calls
``reconcile_poll`` / ``sync_participants`` / ``send_nudges`` -- all four are
mocked, using lightweight ``SimpleNamespace`` stand-ins for polls (only
``.id`` is ever read by the job or by these mocks).

Every mocked function is patched at its *source* module
(``app.practices.availability_models.LeadAvailabilityPoll.query``,
``app.slack.practices.availability_reactions.reconcile_poll``,
``app.practices.availability.sync_participants`` / ``send_nudges``), not at
``app.scheduler``, because the job imports each of these locally inside its
``with app.app_context():`` block rather than at module scope -- patching
``app.scheduler.X`` would have no effect since no such module-level name
exists to patch.

``LeadAvailabilityPoll.query`` is a Flask-SQLAlchemy descriptor that reads the
current app context the moment it's accessed (even just to capture the
"original" value for ``unittest.mock.patch`` to restore afterward), so every
``patch(...LeadAvailabilityPoll.query...)`` block below is entered inside
``app.app_context()``.
"""

from types import SimpleNamespace

from sqlalchemy import text

from app.models import db
from unittest.mock import patch

import pytest

from app import create_app


@pytest.fixture
def app():
    application = create_app()
    application.config.update(TESTING=True, SECRET_KEY="test-secret-key")
    return application


def test_reconcile_runs_before_sync_and_send(app):
    """Order matters: reconcile must run before sync/send so a missed
    reaction event doesn't get nudged against stale state. Swapping the
    call order in the job (e.g. sync-then-reconcile) must fail this test.
    """
    from app.scheduler import run_lead_availability_nudge_job

    poll = SimpleNamespace(id=1)
    calls = []

    def _reconcile(p):
        calls.append("reconcile")
        return {"added": 0, "removed": 0}

    def _sync(p):
        calls.append("sync")
        return 0

    def _send(p):
        calls.append("send")
        return {"sent": 0, "skipped": 0}

    with app.app_context(), \
         patch("app.practices.availability_models.LeadAvailabilityPoll.query") as q, \
         patch("app.slack.practices.availability_reactions.reconcile_poll", side_effect=_reconcile), \
         patch("app.practices.availability.sync_participants", side_effect=_sync), \
         patch("app.practices.availability.send_nudges", side_effect=_send):
        q.filter_by.return_value.all.return_value = [poll]
        run_lead_availability_nudge_job(app)

    assert calls == ["reconcile", "sync", "send"], (
        "reconcile must run before sync/send -- DMing on unreconciled state "
        "is the exact failure reconcile-first exists to prevent"
    )


def test_only_open_polls_are_processed(app):
    from app.scheduler import run_lead_availability_nudge_job
    from app.practices.availability_models import PollStatus

    with app.app_context(), \
         patch("app.practices.availability_models.LeadAvailabilityPoll.query") as q, \
         patch("app.slack.practices.availability_reactions.reconcile_poll",
               return_value={"added": 0, "removed": 0}), \
         patch("app.practices.availability.sync_participants", return_value=0), \
         patch("app.practices.availability.send_nudges", return_value={"sent": 0, "skipped": 0}):
        q.filter_by.return_value.all.return_value = []
        run_lead_availability_nudge_job(app)

    q.filter_by.assert_called_once_with(status=PollStatus.OPEN)


def test_one_poll_raising_does_not_abort_others(app):
    from app.scheduler import run_lead_availability_nudge_job

    poll_bad = SimpleNamespace(id=1)
    poll_good = SimpleNamespace(id=2)
    sync_calls = []
    send_calls = []

    def _reconcile(p):
        if p.id == poll_bad.id:
            raise RuntimeError("boom")
        return {"added": 0, "removed": 0}

    def _sync(p):
        sync_calls.append(p.id)
        return 0

    def _send(p):
        send_calls.append(p.id)
        return {"sent": 0, "skipped": 0}

    with app.app_context(), \
         patch("app.practices.availability_models.LeadAvailabilityPoll.query") as q, \
         patch("app.slack.practices.availability_reactions.reconcile_poll", side_effect=_reconcile), \
         patch("app.practices.availability.sync_participants", side_effect=_sync), \
         patch("app.practices.availability.send_nudges", side_effect=_send):
        q.filter_by.return_value.all.return_value = [poll_bad, poll_good]
        run_lead_availability_nudge_job(app)

    assert sync_calls == [poll_good.id], "the failing poll must not block the other poll"
    assert send_calls == [poll_good.id]


def test_reconcile_error_skips_nudges_for_that_poll(app):
    """Fix 4: reconcile_poll is fail-soft (returns an "error" key rather than
    raising on a Slack error). The job must check that key and skip sync/send
    for this poll -- nudging on unreconciled state is exactly what
    reconcile-first exists to prevent. Nothing is lost: the poll survives to
    tomorrow's run.
    """
    from app.scheduler import run_lead_availability_nudge_job

    poll = SimpleNamespace(id=1)

    with app.app_context(), \
         patch("app.practices.availability_models.LeadAvailabilityPoll.query") as q, \
         patch("app.slack.practices.availability_reactions.reconcile_poll",
               return_value={"added": 0, "removed": 0, "error": "channel_not_found"}), \
         patch("app.practices.availability.sync_participants") as sync_mock, \
         patch("app.practices.availability.send_nudges") as send_mock:
        q.filter_by.return_value.all.return_value = [poll]
        run_lead_availability_nudge_job(app)

    sync_mock.assert_not_called()
    send_mock.assert_not_called()


def test_a_poisoned_session_does_not_abort_the_other_polls(app):
    """Isolation has to survive a SESSION-POISONING error, not just a tidy one.

    test_one_poll_raising_does_not_abort_others raises a plain RuntimeError,
    which never touches the transaction -- so it passed even while the except
    block had no rollback. Every poll in a run shares one session, so a real
    failure (an IntegrityError on the participant unique index when a reaction
    event races the reconcile commit) left the session in a failed-flush state:
    the next poll's first query raised PendingRollbackError, was caught, and
    was logged as a second, unrelated failure. This drives the real thing by
    aborting the transaction at the database.
    """
    from app.scheduler import run_lead_availability_nudge_job

    poll_bad = SimpleNamespace(id=1)
    poll_good = SimpleNamespace(id=2)
    sync_calls = []

    def _reconcile(p):
        if p.id == poll_bad.id:
            # Poison the transaction the way a failed flush does, so the next
            # poll's queries raise unless the job rolled back.
            db.session.execute(text("SELECT 1/0"))
        return {"added": 0, "removed": 0}

    def _sync(p):
        # A real query, so a poisoned session actually shows up here rather
        # than being masked by a mock that never touches the DB.
        db.session.execute(text("SELECT 1"))
        sync_calls.append(p.id)
        return 0

    with app.app_context():
        try:
            with patch("app.practices.availability_models.LeadAvailabilityPoll.query") as q, \
                 patch("app.slack.practices.availability_reactions.reconcile_poll",
                       side_effect=_reconcile), \
                 patch("app.practices.availability.sync_participants", side_effect=_sync), \
                 patch("app.practices.availability.send_nudges",
                       return_value={"sent": 0, "skipped": 0}):
                q.filter_by.return_value.all.return_value = [poll_bad, poll_good]
                run_lead_availability_nudge_job(app)
        finally:
            # This test deliberately aborts a transaction; leave the shared
            # dev-database session clean for whatever runs next.
            db.session.rollback()

    assert sync_calls == [poll_good.id], (
        "the good poll must still be processed -- a DB-level failure on the "
        "first poll must not poison the session for the rest of the run"
    )
