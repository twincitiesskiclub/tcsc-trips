"""The recap job is a thin gate-then-post wrapper; these tests mock the
stats and Slack layers and only assert the wiring: quiet when gated, one
post (for yesterday) when due, and no crash when everything blows up.

Season choice deliberately goes through app.seasons.selection.select_season,
NOT Season.is_current: activation happens at season start, while the recap
must run during the registration window weeks earlier."""
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

import pytest

from app import create_app


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    return app


TODAY = date(2098, 1, 11)


def test_quiet_when_gate_says_no(app):
    from app.scheduler import run_season_recap_job
    with patch("app.seasons.selection.select_season",
               return_value=MagicMock()), \
         patch("app.seasons.recap.should_post", return_value=False), \
         patch("app.slack.season_recap.post_season_recap") as post:
        run_season_recap_job(app)
    post.assert_not_called()


def test_quiet_without_selectable_season(app):
    from app.scheduler import run_season_recap_job
    with patch("app.seasons.selection.select_season", return_value=None), \
         patch("app.slack.season_recap.post_season_recap") as post:
        run_season_recap_job(app)
    post.assert_not_called()


def test_posts_yesterdays_recap_when_due(app):
    from app.scheduler import run_season_recap_job
    season = MagicMock()
    stats = {"yesterday": {"total": 3}, "season_totals": {"total": 142}}
    with patch("app.seasons.selection.select_season",
               return_value=season) as select, \
         patch("app.seasons.recap.should_post", return_value=True), \
         patch("app.scheduler.today_central", return_value=TODAY), \
         patch("app.seasons.recap.build_recap",
               return_value=stats) as build, \
         patch("app.slack.season_recap.post_season_recap",
               return_value={"success": True}) as post:
        run_season_recap_job(app, channel_override="test-chan")
    select.assert_called_once()
    build.assert_called_once_with(season, TODAY - timedelta(days=1))
    post.assert_called_once_with(stats, channel_override="test-chan")


def test_job_survives_exceptions(app):
    from app.scheduler import run_season_recap_job
    with patch("app.seasons.selection.select_season",
               side_effect=RuntimeError("db down")):
        run_season_recap_job(app)  # must not raise
