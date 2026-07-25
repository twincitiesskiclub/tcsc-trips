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

from datetime import datetime
from unittest.mock import patch

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
