"""Draft bootstrap and readiness nudge jobs.

Note on the ``app`` fixture: this file lives directly under ``tests/`` (not
``tests/practices/`` or ``tests/slack/``), which has no shared conftest
providing one, so it's defined locally here following the same pattern as
``tests/practices/conftest.py`` / ``tests/slack/conftest.py``.

None of these tests create real database rows — the suite's ``app`` fixture
points at the real local dev database (see ``tests/conftest.py`` /
``tests/practices/conftest.py``), and per those conventions we avoid writing
to it when mocking will do. The readiness-nudge test therefore mocks the
drafts lookup rather than inserting a ``Practice`` row.
"""

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app import create_app
from app.practices.models import Practice


@pytest.fixture
def app():
    application = create_app()
    application.config.update(TESTING=True, SECRET_KEY="test-secret-key")
    return application


def test_bootstrap_drafts_and_posts_digest(app):
    from app.scheduler import run_practice_block_bootstrap_job

    with patch("app.scheduler.generate_draft_block") as gen, \
         patch("app.scheduler.post_readiness_digest") as post:
        gen.return_value = [
            Practice(date=datetime(2026, 8, 4, 18, 15), day_of_week="Tuesday", is_draft=True)
        ]
        run_practice_block_bootstrap_job(app)

    gen.assert_called_once()
    post.assert_called_once()


def test_bootstrap_skips_digest_when_nothing_was_drafted(app):
    from app.scheduler import run_practice_block_bootstrap_job

    with patch("app.scheduler.generate_draft_block", return_value=[]), \
         patch("app.scheduler.post_readiness_digest") as post:
        run_practice_block_bootstrap_job(app)

    post.assert_not_called(), "a no-op run must not post"


def test_readiness_nudge_is_silent_when_all_drafts_are_ready(app):
    from app.scheduler import run_practice_readiness_nudge_job

    ready = Practice(
        date=datetime(2026, 8, 4, 18, 15), day_of_week="Tuesday",
        is_draft=True, location_id=None,
    )

    with patch("app.scheduler.drafted_practices_in_window", return_value=[ready]), \
         patch("app.scheduler.post_readiness_digest") as post, \
         patch("app.scheduler.is_ready", return_value=True):
        run_practice_readiness_nudge_job(app)

    post.assert_not_called(), "a daily all-clear post trains people to ignore the channel"


def test_readiness_nudge_posts_when_a_draft_is_incomplete(app):
    from app.scheduler import run_practice_readiness_nudge_job

    incomplete = Practice(
        date=datetime(2026, 8, 4, 18, 15), day_of_week="Tuesday",
        is_draft=True, location_id=None,
    )

    with patch("app.scheduler.drafted_practices_in_window", return_value=[incomplete]), \
         patch("app.scheduler.post_readiness_digest") as post, \
         patch("app.scheduler.is_ready", return_value=False):
        run_practice_readiness_nudge_job(app)

    post.assert_called_once()


def test_bootstrap_anchors_the_digest_to_the_first_of_the_month(app):
    """The digest identity is keyed to the block's start (the 1st, per the job
    cadence) even if a late run drafts mid-month — so the daily nudge, which
    computes the same anchor, can always find the post to thread onto."""
    from app.scheduler import run_practice_block_bootstrap_job

    with patch("app.utils.today_central", return_value=date(2099, 7, 15)), \
         patch("app.scheduler.generate_draft_block") as gen, \
         patch("app.scheduler.post_readiness_digest") as post:
        gen.return_value = [
            Practice(date=datetime(2099, 7, 21, 18, 15), day_of_week="Tuesday", is_draft=True)
        ]
        run_practice_block_bootstrap_job(app)

    assert post.call_args.kwargs["block_start"] == date(2099, 7, 1)


def test_readiness_nudge_anchors_to_the_first_of_the_month(app):
    from app.scheduler import run_practice_readiness_nudge_job

    incomplete = Practice(
        date=datetime(2099, 7, 21, 18, 15), day_of_week="Tuesday",
        is_draft=True, location_id=None,
    )

    with patch("app.utils.today_central", return_value=date(2099, 7, 15)), \
         patch("app.scheduler.drafted_practices_in_window", return_value=[incomplete]), \
         patch("app.scheduler.post_readiness_digest") as post, \
         patch("app.scheduler.is_ready", return_value=False):
        run_practice_readiness_nudge_job(app)

    assert post.call_args.kwargs["block_start"] == date(2099, 7, 1)


def test_readiness_nudge_slack_failure_is_logged_not_raised(app):
    """Exercises the real post_readiness_digest with a failing Slack client:
    the job must swallow the failure (and record nothing)."""
    from slack_sdk.errors import SlackApiError

    from app.models import db
    from app.practices.models import PracticeSummaryPost
    from app.scheduler import run_practice_readiness_nudge_job
    from app.slack.practices.summary_posts import READINESS_DIGEST

    incomplete = SimpleNamespace(
        id=1, date=datetime(2099, 7, 21, 18, 15),
        location_id=None, practice_types=[], activities=[],
    )
    client = MagicMock()
    client.chat_postMessage.side_effect = SlackApiError(
        "boom", response={"error": "channel_not_found"}
    )

    def _nudge_digest_rows():
        return PracticeSummaryPost.query.filter_by(
            week_start=date(2099, 7, 1), surface=READINESS_DIGEST
        ).all()

    try:
        with patch("app.utils.today_central", return_value=date(2099, 7, 15)), \
             patch("app.scheduler.drafted_practices_in_window", return_value=[incomplete]), \
             patch("app.scheduler.is_ready", return_value=False), \
             patch("app.slack.practices.drafts.get_slack_client", return_value=client):
            run_practice_readiness_nudge_job(app)  # must not raise

        client.chat_postMessage.assert_called_once()
        with app.app_context():
            assert not _nudge_digest_rows(), "a failed post must not be recorded"
    finally:
        with app.app_context():
            db.session.rollback()
            for row in _nudge_digest_rows():
                db.session.delete(row)
            db.session.commit()


def test_readiness_nudge_is_silent_when_there_are_no_drafts(app):
    from app.scheduler import run_practice_readiness_nudge_job

    with patch("app.scheduler.drafted_practices_in_window", return_value=[]), \
         patch("app.scheduler.post_readiness_digest") as post, \
         patch("app.scheduler.is_ready", return_value=True):
        run_practice_readiness_nudge_job(app)

    post.assert_not_called()


def test_both_jobs_are_registered():
    from app.scheduler import init_scheduler

    with patch("app.scheduler.scheduler") as sched, \
         patch("app.scheduler.is_main_worker", return_value=True):
        sched.running = False
        from flask import Flask
        init_scheduler(Flask(__name__))

    registered = {call.kwargs.get("id") for call in sched.add_job.call_args_list}
    assert "practice_block_bootstrap" in registered
    assert "practice_block_readiness_nudge" in registered
