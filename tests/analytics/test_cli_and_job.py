"""CLI and scheduler wiring, with step functions and commits mocked."""
from datetime import date
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

from app.models import db


@pytest.fixture(autouse=True)
def transaction(app):
    with app.app_context(), patch.object(db.session, "commit") as commit, \
         patch.object(db.session, "rollback") as rollback:
        yield SimpleNamespace(commit=commit, rollback=rollback)


def test_cli_group_registered(app):
    result = app.test_cli_runner().invoke(args=["analytics", "--help"])
    assert result.exit_code == 0
    for cmd in ("import-slack", "sync", "rebuild", "fetch-weather", "flags", "nightly",
                "set-coach-emoji", "corrections"):
        assert cmd in result.output


@pytest.mark.parametrize("token", ["bot", "user"])
def test_import_selects_token_and_commits_once(app, transaction, token):
    from app.analytics import cli
    stats = {"messages": 2, "replies": 1, "seen": {"123.000001"}}
    with patch.object(cli, "get_slack_client") as bot, \
         patch.object(cli, "get_slack_user_client") as user, \
         patch.object(cli, "import_channel", return_value=stats) as ingest:
        args = ["analytics", "import-slack", "--channel", "CFAKEIMPORT"]
        if token == "user":
            args += ["--token", "user"]
        result = app.test_cli_runner().invoke(args=args)
    assert result.exit_code == 0, result.output
    selected, unused = (bot, user) if token == "bot" else (user, bot)
    selected.assert_called_once_with()
    unused.assert_not_called()
    ingest.assert_called_once_with(selected.return_value, "CFAKEIMPORT")
    transaction.commit.assert_called_once_with()
    assert json.loads(result.output) == {"messages": 2, "replies": 1}
    assert "seen" in stats  # Output filtering must not mutate the result.


@pytest.mark.parametrize("days", [21, 7])
def test_sync_bot_and_days(app, transaction, days):
    from app.analytics import cli
    with patch.object(cli, "get_slack_client") as bot, \
         patch.object(cli, "sync_recent", return_value={}) as sync:
        args = ["analytics", "sync"] + ([] if days == 21 else ["--days", str(days)])
        result = app.test_cli_runner().invoke(args=args)
    assert result.exit_code == 0, result.output
    sync.assert_called_once_with(bot.return_value, days=days)
    transaction.commit.assert_called_once_with()


@pytest.mark.parametrize("command, function", [("rebuild", "rebuild"), ("fetch-weather", "fetch_missing_weather")])
def test_standalone_steps(app, transaction, command, function):
    from app.analytics import cli
    with patch.object(cli, function, return_value={"sessions": 3}) as step:
        result = app.test_cli_runner().invoke(args=["analytics", command])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {"sessions": 3}
    step.assert_called_once_with()
    transaction.commit.assert_not_called()  # These functions own their commits.


def test_set_coach_emoji(app, transaction):
    from app.analytics import cli
    with patch.object(cli.AppConfig, "set") as setter:
        result = app.test_cli_runner().invoke(args=["analytics", "set-coach-emoji", "coachface, snowcoach ,"])
    assert result.exit_code == 0, result.output
    setter.assert_called_once_with("analytics_coach_emoji", ["coachface", "snowcoach"], category="analytics")
    transaction.commit.assert_called_once_with()


@pytest.mark.parametrize("command", ["import", "export", "list"])
def test_corrections_commands(app, transaction, tmp_path, command):
    from app.analytics import cli
    path = tmp_path / "corrections.json"
    path.write_text("{}")
    with patch.object(cli, "import_corrections", return_value=2) as importer, \
         patch.object(cli, "export_corrections", return_value=2) as exporter, \
         patch.object(cli, "load_corrections", return_value={"CFAKE:123.000001": {"skip": True}}) as loader:
        result = app.test_cli_runner().invoke(args=["analytics", "corrections", command] +
                                             ([] if command == "list" else [str(path)]))
    assert result.exit_code == 0, result.output
    if command == "list":
        loader.assert_called_once_with()
        assert json.loads(result.output) == loader.return_value
    else:
        step = importer if command == "import" else exporter
        step.assert_called_once_with(str(path))
        assert "2" in result.output
    assert transaction.commit.call_count == (command == "import")


def test_flags_reads_db_sessions_and_builds_misses_without_writes(app, transaction, tmp_path):
    from app.analytics import cli
    from app.analytics.drafts import ArchivedMessage, LineageResult
    post = ArchivedMessage("CFAKEFLAGS", "4087911600.000100", {"text": "Invented practice"},
                           replies=({"text": "Invented reply"},), archive_id=17)
    miss = ArchivedMessage("CFAKEFLAGS", "4087911601.000100", {
        "text": "Invented reminder", "reactions": [{"name": "six", "count": 7}]})
    key = f"{post.channel_id}:{post.ts}"
    miss_key = f"{miss.channel_id}:{miss.ts}"
    flagged = SimpleNamespace(session_key="practice:999", group_key=key, source_message_id=17,
                              date=date(2099, 7, 16), title="Invented title", flags=["unknown_venue"],
                              format="single", rsvp_count=2)
    inputs = ([post, miss], [], [], [])
    output = tmp_path / "flags.json"
    with patch.object(cli, "load_inputs", return_value=inputs), \
         patch.object(cli, "load_corrections", return_value={}) as corrections, \
         patch.object(cli.AppConfig, "get", return_value=["snowcoach"]) as config, \
         patch.object(cli, "build_lineage", return_value=LineageResult([], [], [miss_key])) as build, \
         patch.object(cli, "flagged_sessions", return_value=[flagged]), \
         patch.object(cli, "rebuild") as rebuild:
        result = app.test_cli_runner().invoke(args=["analytics", "flags", "--json", str(output)])
    assert result.exit_code == 0, result.output
    config.assert_called_once_with("analytics_coach_emoji", [])
    assert build.call_args.args[:4] == inputs
    assert build.call_args.args[4].coach_emoji == frozenset({"snowcoach"})
    assert build.call_args.args[5] == corrections.return_value
    rebuild.assert_not_called()
    transaction.commit.assert_not_called()
    assert "2099-07-16  practice:999  unknown_venue  Invented title" in result.output
    assert miss_key in result.output
    data = json.loads(output.read_text())
    assert data["flagged_sessions"] == [{
        "session_key": "practice:999", "post_key": key, "date": "2099-07-16",
        "title": "Invented title", "flags": ["unknown_venue"], "format": "single",
        "rsvp_count": 2, "text": "Invented practice", "replies": ["Invented reply"],
    }]
    assert data["possible_misses"] == [{"post_key": miss_key, "date": "2099-07-16",
                                          "text": "Invented reminder", "reactions": {"six": 7}}]


@pytest.mark.parametrize("failure", ["sync", "commit", "rebuild", "weather", "client"])
def test_nightly_stops_at_first_failure(app, transaction, failure, caplog):
    from app.analytics import jobs
    with patch.object(jobs, "sync_recent", return_value={}) as sync, \
         patch.object(jobs, "rebuild", return_value={}) as rebuild, \
         patch.object(jobs, "fetch_missing_weather", return_value={}) as weather, \
         patch.object(jobs, "get_slack_client") as client:
        steps = {"sync": sync, "commit": transaction.commit, "rebuild": rebuild,
                 "weather": weather, "client": client}
        steps[failure].side_effect = RuntimeError("step down")
        out = jobs.run_nightly()
    expected_step = "sync" if failure in ("client", "commit") else failure
    assert out == {"step": expected_step, "ok": False, "error": "step down"}
    transaction.rollback.assert_called_once_with()
    if expected_step == "sync":
        rebuild.assert_not_called()
    if expected_step != "weather":
        weather.assert_not_called()
    assert "step down" in caplog.text


def test_nightly_runs_all_steps_in_order_with_bot(app, transaction):
    from app.analytics import jobs
    order = MagicMock()
    http_get = MagicMock()
    with patch.object(jobs, "sync_recent", return_value={}) as sync, \
         patch.object(jobs, "rebuild", return_value={"sessions": 1}) as rebuild, \
         patch.object(jobs, "fetch_missing_weather", return_value={"sessions": 0}) as weather, \
         patch.object(jobs, "get_slack_client") as bot, \
         patch("app.slack.client.get_slack_user_client") as user:
        for name, mock in (("sync", sync), ("commit", transaction.commit), ("rebuild", rebuild), ("weather", weather)):
            order.attach_mock(mock, name)
        out = jobs.run_nightly(http_get=http_get)
    assert out == {"step": "done", "ok": True, "sync": {}, "rebuild": {"sessions": 1}, "weather": {"sessions": 0}}
    assert order.mock_calls == [call.sync(bot.return_value), call.commit(), call.rebuild(), call.weather(http_get=http_get)]
    bot.assert_called_once_with()
    user.assert_not_called()
    transaction.rollback.assert_not_called()


def test_nightly_injected_client_and_default_weather(app):
    from app.analytics import jobs
    client = MagicMock()
    with patch.object(jobs, "sync_recent", return_value={}) as sync, \
         patch.object(jobs, "rebuild", return_value={}), \
         patch.object(jobs, "fetch_missing_weather", return_value={}) as weather, \
         patch.object(jobs, "get_slack_client") as bot:
        assert jobs.run_nightly(client=client)["ok"]
    bot.assert_not_called()
    sync.assert_called_once_with(client)
    weather.assert_called_once_with()


@pytest.mark.parametrize("ok", [True, False])
def test_nightly_cli_exit_status(app, ok):
    from app.analytics import cli
    out = {"step": "done" if ok else "sync", "ok": ok}
    with patch.object(cli, "run_nightly", return_value=out):
        result = app.test_cli_runner().invoke(args=["analytics", "nightly"])
    assert result.exit_code == (0 if ok else 1)
    assert json.loads(result.output) == out


def test_scheduler_registers_nightly_job(app):
    import app.scheduler as sched
    with patch.object(sched, "scheduler") as scheduler, \
         patch.object(sched, "is_main_worker", return_value=True), \
         patch.object(sched.atexit, "register"), \
         patch("app.slack.bolt_app.is_socket_mode_available", return_value=False):
        scheduler.running = False
        assert sched.init_scheduler(app)
    job = next(c.kwargs for c in scheduler.add_job.call_args_list if c.kwargs["id"] == "analytics_nightly")
    assert job["func"] is sched.run_analytics_nightly_job
    assert job["args"] == [app]
    assert job["misfire_grace_time"] == 3600
    assert job["replace_existing"] is True
    assert str(job["trigger"].timezone) == "America/Chicago"
    fields = {field.name: str(field) for field in job["trigger"].fields}
    assert (fields["hour"], fields["minute"]) == ("3", "30")


def test_scheduler_wrapper_pushes_context(app):
    from flask import current_app
    from app.scheduler import run_analytics_nightly_job
    def run():
        assert current_app._get_current_object() is app
        return {"step": "done", "ok": True}
    with patch("app.analytics.jobs.run_nightly", side_effect=run) as nightly:
        run_analytics_nightly_job(app)
    nightly.assert_called_once_with()
