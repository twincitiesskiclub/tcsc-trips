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

    drafted = [
        Practice(date=datetime(2026, 8, 4, 18, 15), day_of_week="Tuesday", is_draft=True)
    ]
    with patch("app.scheduler.generate_draft_block", return_value=drafted) as gen, \
         patch("app.scheduler.drafted_practices_in_window", return_value=drafted), \
         patch("app.scheduler.post_readiness_digest") as post:
        run_practice_block_bootstrap_job(app)

    gen.assert_called_once()
    post.assert_called_once()


def test_bootstrap_digest_covers_the_whole_window_not_just_new_rows(app):
    """After the first run, `created` only ever contains the FOLLOWING
    month's rows — the current month was drafted by the previous run and
    idempotency skips it. A digest computed over `created` would state a
    range including the current month while omitting its drafts from the
    count and the incomplete list, so a director reads "all ready" while
    current-month drafts still lack details. The digest must summarise the
    whole drafted window and label the range from what it actually covers."""
    from app.scheduler import run_practice_block_bootstrap_job

    created_oct_only = [
        Practice(date=datetime(2099, 10, 6, 18, 15), day_of_week="Tuesday", is_draft=True),
        Practice(date=datetime(2099, 10, 29, 18, 15), day_of_week="Thursday", is_draft=True),
    ]
    whole_window = [
        Practice(date=datetime(2099, 9, 3, 18, 15), day_of_week="Thursday", is_draft=True),
        *created_oct_only,
    ]

    with patch("app.utils.today_central", return_value=date(2099, 9, 1)), \
         patch("app.scheduler.generate_draft_block", return_value=created_oct_only), \
         patch("app.scheduler.drafted_practices_in_window",
               return_value=whole_window) as window, \
         patch("app.scheduler.post_readiness_digest") as post:
        run_practice_block_bootstrap_job(app)

    assert window.call_args.args == (date(2099, 9, 1), date(2099, 10, 31))
    args = post.call_args.args
    assert args[0] == whole_window, (
        "the digest must summarise every draft in the window, not only this "
        "run's new rows"
    )
    assert args[1] == "Sep 3", "start label must be the first draft actually covered"
    assert args[2] == "Oct 29", "end label must be the last draft actually covered"


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


def test_bootstrap_drafts_through_the_end_of_next_month(app):
    """The window must be an explicit horizon, not a Monday-normalised week
    count: the job fires on the 1st, and a weeks window anchored to the
    Monday before the 1st left the tail of most months entirely undrafted
    (no rows, no digest, no poll — invisible until the week it happened).
    Drafting through the end of NEXT month makes consecutive monthly runs
    overlap by a whole month; generate_draft_block's idempotency absorbs
    the overlap."""
    from app.scheduler import run_practice_block_bootstrap_job

    with patch("app.utils.today_central", return_value=date(2099, 8, 1)), \
         patch("app.scheduler.generate_draft_block", return_value=[]) as gen:
        run_practice_block_bootstrap_job(app)

    assert gen.call_args.args == (date(2099, 8, 1), date(2099, 9, 30))


def test_readiness_nudge_window_reaches_the_bootstrap_horizon(app):
    """The nudge must chase every draft the bootstrap created. A shorter
    window (the old fixed 4 weeks) would silently stop chasing the tail of
    the drafted block."""
    from app.scheduler import run_practice_readiness_nudge_job

    with patch("app.utils.today_central", return_value=date(2099, 8, 15)), \
         patch("app.scheduler.drafted_practices_in_window", return_value=[]) as window:
        run_practice_readiness_nudge_job(app)

    assert window.call_args.args == (date(2099, 8, 15), date(2099, 9, 30))


def test_both_jobs_compute_the_same_block_anchor(app):
    """The nudge threads onto the digest the bootstrap recorded; the two jobs
    must derive the anchor from one shared helper, not two copies of
    `start.replace(day=1)` coupled only by comments."""
    from app.scheduler import _block_anchor

    assert _block_anchor(date(2099, 7, 15)) == date(2099, 7, 1)
    assert _block_anchor(date(2099, 7, 1)) == date(2099, 7, 1)


def test_bootstrap_anchors_the_digest_to_the_first_of_the_month(app):
    """The digest identity is keyed to the block's start (the 1st, per the job
    cadence) even if a late run drafts mid-month — so the daily nudge, which
    computes the same anchor, can always find the post to thread onto."""
    from app.scheduler import run_practice_block_bootstrap_job

    drafted = [
        Practice(date=datetime(2099, 7, 21, 18, 15), day_of_week="Tuesday", is_draft=True)
    ]
    with patch("app.utils.today_central", return_value=date(2099, 7, 15)), \
         patch("app.scheduler.generate_draft_block", return_value=drafted), \
         patch("app.scheduler.drafted_practices_in_window", return_value=drafted), \
         patch("app.scheduler.post_readiness_digest") as post:
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
