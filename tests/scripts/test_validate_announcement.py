"""Safety and completeness contracts for the live announcement harness."""

from __future__ import annotations

import inspect
import json
import re
from datetime import timedelta
from types import SimpleNamespace

import pytest
from slack_sdk.errors import SlackApiError

from app.practices.interfaces import AnnouncementConditions
from app.utils import utc_naive_to_central_naive
from scripts import validate_announcement as validate


REQUIRED_SCENARIOS = {
    "routine",
    "july_no_false_headlamp",
    "after_sunset",
    "weather_alert",
    "aqi_101",
    "missing_workout",
    "no_details",
    "interval_evergreen",
    "multiple_plan_reactions",
    "overridden_plan",
    "empty_plan",
    "long_boundaries",
    "weekly_cross_month_cancelled",
    "combined_strength",
    "combined_mixed_cancelled",
}


def _client(**methods):
    defaults = {
        "chat_postMessage": lambda **kwargs: {"ts": "100.1"},
        "reactions_add": lambda **kwargs: {"ok": True},
        "chat_getPermalink": lambda **kwargs: {
            "permalink": "https://slack.example/message"
        },
        "chat_delete": lambda **kwargs: {"ok": True},
    }
    defaults.update(methods)
    return SimpleNamespace(**defaults)


def _record(ts, thread_ts=None, channel=None):
    return {
        "channel": channel or validate.TEST_CHANNEL,
        "ts": ts,
        "thread_ts": thread_ts,
    }


def _state(records=None):
    return {"run_id": "test-run", "records": list(records or [])}


def _stub_scenario():
    return SimpleNamespace(reaction_names=())


def _stub_build(*, details=False):
    reply = ([{"type": "divider"}], "details fallback") if details else None
    return [{"type": "divider"}], "root fallback", reply


def test_channel_and_cli_offer_no_destination_override(monkeypatch):
    monkeypatch.setenv("SLACK_CHANNEL", "C_PRODUCTION")
    monkeypatch.setenv("TEST_CHANNEL", "C_PRODUCTION")

    assert validate.TEST_CHANNEL == "C07G9RTMRT3"
    assert "channel" not in inspect.signature(validate.post).parameters


def test_sanitize_removes_all_broadcast_mentions_recursively():
    value = {
        "text": "Root <!channel>",
        "blocks": [{
            "elements": (
                {"text": "Details <!here>"},
                ["Nested <!everyone>", "safe"],
            ),
        }],
    }

    sanitized = validate._sanitize_for_test(value)

    assert isinstance(sanitized["blocks"][0]["elements"], tuple)
    assert all(
        mention not in str(sanitized)
        for mention in validate.MENTIONS
    )


def test_registry_is_synthetic_complete_and_uses_final_builders():
    assert set(validate.SCENARIOS) >= REQUIRED_SCENARIOS
    assert "Practice.query" not in inspect.getsource(validate)

    for name, scenario in validate.SCENARIOS.items():
        assert scenario.kind in {"standalone", "weekly", "combined"}
        assert scenario.practices
        assert all(
            isinstance(practice, SimpleNamespace)
            for practice in scenario.practices
        )
        if scenario.kind == "standalone":
            assert isinstance(scenario.conditions, AnnouncementConditions)

        blocks, fallback, details = validate.build_scenario(name, scenario)
        assert blocks, name
        assert isinstance(fallback, str) and fallback.strip(), name
        if details:
            assert scenario.kind == "standalone", name
            assert details[0] and details[1].strip(), name

        if scenario.kind == "standalone":
            expected_reactions = (
                "white_check_mark",
                *(item["emoji"] for item in scenario.practices[0].plan_reactions),
            )
        elif scenario.kind == "combined":
            expected_reactions = tuple(
                practice.slack_session_emoji for practice in scenario.practices
            ) + tuple(
                item["emoji"] for item in scenario.practices[0].plan_reactions
            )
        else:
            expected_reactions = ()
        assert scenario.reaction_names == expected_reactions, name
        for reaction_name in expected_reactions:
            if reaction_name != "white_check_mark":
                assert f":{reaction_name}:" in str(blocks), (name, reaction_name)

    weekly = validate.SCENARIOS["weekly_cross_month_cancelled"]
    assert weekly.week_start.isoformat() == "2026-07-27"
    assert validate.build_scenario("no_details", validate.SCENARIOS["no_details"])[
        2
    ] is None


def test_july_scenario_ends_before_859_sunset_without_headlamp_warning():
    scenario = validate.SCENARIOS["july_no_false_headlamp"]
    practice = scenario.practices[0]
    conditions = scenario.conditions
    sunset = utc_naive_to_central_naive(conditions.daylight.sunset)
    practice_end = practice.date + timedelta(
        minutes=conditions.duration_minutes
    )

    assert (sunset.hour, sunset.minute) == (20, 59)
    assert practice.date < practice_end < sunset
    blocks, fallback, _ = validate.build_scenario(
        "july_no_false_headlamp", scenario
    )
    assert "Headlamp required" not in str(blocks)
    assert "Headlamp required" not in fallback


def test_after_sunset_scenario_starts_before_but_ends_after_sunset():
    scenario = validate.SCENARIOS["after_sunset"]
    practice = scenario.practices[0]
    conditions = scenario.conditions
    sunset = utc_naive_to_central_naive(conditions.daylight.sunset)
    practice_end = practice.date + timedelta(
        minutes=conditions.duration_minutes
    )

    assert practice.date < sunset < practice_end
    blocks, fallback, _ = validate.build_scenario("after_sunset", scenario)
    assert "Headlamp required" in str(blocks)
    assert "Headlamp required" in fallback


@pytest.mark.parametrize("boundary", ["post", "reaction", "permalink", "delete"])
def test_wrong_channel_is_rejected_before_every_slack_boundary(
    boundary, tmp_path
):
    calls = []
    client = _client(
        chat_postMessage=lambda **kwargs: calls.append(kwargs),
        reactions_add=lambda **kwargs: calls.append(kwargs),
        chat_getPermalink=lambda **kwargs: calls.append(kwargs),
        chat_delete=lambda **kwargs: calls.append(kwargs),
    )

    with pytest.raises(RuntimeError, match="Refusing live validation"):
        if boundary == "post":
            validate._post_recorded(
                client,
                _state(),
                state_path=tmp_path / "state.json",
                channel="C_PRODUCTION",
                text="unsafe",
            )
        elif boundary == "reaction":
            validate._add_reaction(
                client,
                channel="C_PRODUCTION",
                timestamp="100.1",
                name="white_check_mark",
            )
        elif boundary == "permalink":
            validate._get_permalink(
                client,
                channel="C_PRODUCTION",
                message_ts="100.1",
            )
        else:
            validate._delete_record(
                client,
                _record("100.1", channel="C_PRODUCTION"),
            )

    assert calls == []


def test_posts_are_sanitized_and_persisted_before_the_next_call(tmp_path):
    state_path = tmp_path / "state.json"
    state = _state()
    sent = []

    def chat_post_message(**kwargs):
        sent.append(kwargs)
        if len(sent) == 2:
            assert json.loads(state_path.read_text())["records"] == [
                _record("100.1")
            ]
        return {"ts": f"100.{len(sent)}"}

    client = _client(chat_postMessage=chat_post_message)
    for label in ("first", "second"):
        validate._post_recorded(
            client,
            state,
            state_path=state_path,
            channel=validate.TEST_CHANNEL,
            text=f"{label} <!channel> <!here> <!everyone>",
            blocks=[{"elements": [{"text": "nested <!channel>"}]}],
        )

    assert all(
        mention not in str(sent)
        for mention in validate.MENTIONS
    )
    assert json.loads(state_path.read_text())["records"] == [
        _record("100.1"),
        _record("100.2"),
    ]
    assert not list(tmp_path.glob(".*.tmp"))


def test_post_persists_empty_state_and_shows_run_id_on_every_message(
    tmp_path, monkeypatch
):
    state_path = tmp_path / "state.json"
    sent = []

    def chat_post_message(**kwargs):
        if not sent:
            assert json.loads(state_path.read_text())["records"] == []
        sent.append(kwargs)
        return {"ts": f"100.{len(sent)}"}

    monkeypatch.setattr(validate, "SCENARIOS", {"only": _stub_scenario()})
    monkeypatch.setattr(
        validate,
        "build_scenario",
        lambda name, scenario: _stub_build(details=True),
    )
    monkeypatch.setattr(
        validate,
        "get_slack_client",
        lambda: _client(chat_postMessage=chat_post_message),
    )

    validate.post(state_path=state_path)

    saved = json.loads(state_path.read_text())
    assert re.fullmatch(r"\d{8}T\d{6}Z-[0-9a-f]{8}", saved["run_id"])
    assert [item["text"] for item in sent] == [
        f"[{saved['run_id']}] root fallback",
        f"[{saved['run_id']}] details fallback",
    ]
    assert saved["records"] == [
        _record("100.1"),
        _record("100.2", thread_ts="100.1"),
    ]


def test_every_root_and_details_post_has_visible_marker_on_copied_blocks(
    tmp_path, monkeypatch
):
    state_path = tmp_path / "state.json"
    sent = []
    builder_owned = {}
    build_scenario = validate.build_scenario

    def tracked_build(name, scenario):
        root, fallback, details = build_scenario(name, scenario)
        details_blocks = details[0] if details else None
        builder_owned[name] = (root, details_blocks)
        return root, fallback, details

    def chat_post_message(**kwargs):
        sent.append(kwargs)
        return {"ts": f"100.{len(sent)}"}

    monkeypatch.setattr(validate, "build_scenario", tracked_build)
    monkeypatch.setattr(
        validate,
        "get_slack_client",
        lambda: _client(chat_postMessage=chat_post_message),
    )

    validate.post(state_path=state_path)

    run_id = json.loads(state_path.read_text())["run_id"]
    message_index = 0
    for name in validate.SCENARIOS:
        root_message = sent[message_index]
        message_index += 1
        marker = f"🧪 Harness · {run_id} · {name}"
        assert root_message["blocks"][-1] == {
            "type": "context",
            "elements": [{"type": "plain_text", "text": marker}],
        }

        root_blocks, details_blocks = builder_owned[name]
        if details_blocks is not None:
            details_message = sent[message_index]
            message_index += 1
            assert details_message["blocks"][-1]["elements"][0]["text"] == (
                f"{marker} · Details"
            )

        assert "🧪 Harness" not in str(root_blocks)
        assert "🧪 Harness" not in str(details_blocks)

    assert message_index == len(sent)


def test_interrupted_post_keeps_the_last_successful_cleanup_record(
    tmp_path, monkeypatch
):
    state_path = tmp_path / "state.json"
    calls = []

    def chat_post_message(**kwargs):
        calls.append(kwargs)
        if len(calls) == 2:
            raise RuntimeError("details interrupted")
        return {"ts": "100.1"}

    monkeypatch.setattr(validate, "SCENARIOS", {"only": _stub_scenario()})
    monkeypatch.setattr(
        validate,
        "build_scenario",
        lambda name, scenario: _stub_build(details=True),
    )
    monkeypatch.setattr(
        validate,
        "get_slack_client",
        lambda: _client(chat_postMessage=chat_post_message),
    )

    with pytest.raises(RuntimeError, match="details interrupted"):
        validate.post(state_path=state_path)

    assert json.loads(state_path.read_text())["records"] == [_record("100.1")]


def test_post_refuses_existing_state_before_getting_client(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(_state([_record("100.1")])))
    monkeypatch.setattr(
        validate,
        "get_slack_client",
        lambda: (_ for _ in ()).throw(AssertionError("client requested")),
    )

    with pytest.raises(RuntimeError, match="run teardown first"):
        validate.post(state_path=state_path)

    assert json.loads(state_path.read_text())["records"] == [_record("100.1")]


def test_reaction_seeds_use_only_displayed_names_and_allow_existing_reactions():
    calls = []
    already = SlackApiError("already reacted", {"error": "already_reacted"})

    def reactions_add(**kwargs):
        calls.append(kwargs)
        if kwargs["name"] == "evergreen_tree":
            raise already
        return {"ok": True}

    results = validate.seed_scenario_reactions(
        _client(reactions_add=reactions_add),
        SimpleNamespace(reaction_names=("six", "evergreen_tree")),
        "100.1",
        state=_state(),
    )

    assert results == [
        {"success": True},
        {"success": True, "skipped": "already_reacted"},
    ]
    assert [item["name"] for item in calls] == ["six", "evergreen_tree"]
    assert all(item["channel"] == validate.TEST_CHANNEL for item in calls)


def test_reaction_failure_is_recorded_without_losing_cleanup_state(
    tmp_path, caplog
):
    state_path = tmp_path / "state.json"
    state = _state([_record("100.1")])
    validate._write_state(state, state_path)
    error = SlackApiError("bad reaction", {"error": "invalid_name"})

    result = validate.seed_scenario_reactions(
        _client(
            reactions_add=lambda **kwargs: (_ for _ in ()).throw(error)
        ),
        SimpleNamespace(reaction_names=("not_real",)),
        "100.1",
        state=state,
        state_path=state_path,
    )

    saved = json.loads(state_path.read_text())
    assert result == [{"success": False, "error": "invalid_name"}]
    assert saved["records"] == [_record("100.1")]
    assert saved["reaction_errors"] == [{
        "channel": validate.TEST_CHANNEL,
        "ts": "100.1",
        "name": "not_real",
        "error": "invalid_name",
    }]
    assert "invalid_name" in caplog.text


def test_teardown_deletes_replies_before_roots_and_removes_state(
    tmp_path, monkeypatch
):
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(_state([
        _record("100.1"),
        _record("100.2", thread_ts="100.1"),
    ])))
    deleted = []
    monkeypatch.setattr(
        validate,
        "get_slack_client",
        lambda: _client(
            chat_delete=lambda **kwargs: deleted.append(kwargs["ts"])
        ),
    )

    assert validate.teardown(state_path=state_path) == {"success": True}
    assert deleted == ["100.2", "100.1"]
    assert not state_path.exists()


def test_teardown_failure_retains_failed_and_unprocessed_records_for_retry(
    tmp_path, monkeypatch
):
    state_path = tmp_path / "state.json"
    root = _record("100.1")
    first_reply = _record("100.2", thread_ts="100.1")
    last_reply = _record("100.3", thread_ts="100.1")
    state_path.write_text(json.dumps(_state([root, first_reply, last_reply])))
    first_attempt = []
    error = SlackApiError("delete failed", {"error": "ratelimited"})

    def fail_once(**kwargs):
        first_attempt.append(kwargs["ts"])
        if kwargs["ts"] == "100.2":
            raise error

    monkeypatch.setattr(
        validate,
        "get_slack_client",
        lambda: _client(chat_delete=fail_once),
    )

    assert validate.teardown(state_path=state_path) == {
        "success": False,
        "record": first_reply,
        "error": "ratelimited",
    }
    assert first_attempt == ["100.3", "100.2"]
    assert json.loads(state_path.read_text())["records"] == [root, first_reply]

    retry = []
    monkeypatch.setattr(
        validate,
        "get_slack_client",
        lambda: _client(
            chat_delete=lambda **kwargs: retry.append(kwargs["ts"])
        ),
    )
    assert validate.teardown(state_path=state_path) == {"success": True}
    assert retry == ["100.2", "100.1"]
    assert not state_path.exists()


@pytest.mark.parametrize("state_exists", [False, True])
def test_teardown_is_idempotent_for_missing_state_or_message(
    state_exists, tmp_path, monkeypatch
):
    state_path = tmp_path / "state.json"
    if state_exists:
        state_path.write_text(json.dumps(_state([_record("100.1")])))
        missing = SlackApiError("missing", {"error": "message_not_found"})
        client = _client(
            chat_delete=lambda **kwargs: (_ for _ in ()).throw(missing)
        )
    else:
        client = None

    monkeypatch.setattr(
        validate,
        "get_slack_client",
        lambda: client
        if client is not None
        else (_ for _ in ()).throw(AssertionError("client requested")),
    )

    result = validate.teardown(state_path=state_path)

    assert result["success"] is True
    assert not state_path.exists()


@pytest.mark.parametrize("args", [[], ["unknown"], ["post", "extra"]])
def test_invalid_cli_returns_two_without_dispatch(args, monkeypatch):
    monkeypatch.setattr(
        validate,
        "post",
        lambda: (_ for _ in ()).throw(AssertionError("post called")),
    )
    monkeypatch.setattr(
        validate,
        "teardown",
        lambda: (_ for _ in ()).throw(AssertionError("teardown called")),
    )

    assert validate.main(args) == 2


@pytest.mark.parametrize("command", ["post", "teardown"])
def test_valid_cli_dispatches_exactly_one_command_without_flask_app(
    command, monkeypatch
):
    called = []
    source = inspect.getsource(validate)
    assert "create_app" not in source
    assert not hasattr(validate, "create_app")
    monkeypatch.setattr(
        validate,
        "post",
        lambda: called.append("post") or {"success": True},
    )
    monkeypatch.setattr(
        validate,
        "teardown",
        lambda: called.append("teardown") or {"success": True},
    )

    assert validate.main([command]) == 0
    assert called == [command]


def test_failed_teardown_returns_one_and_reports_error(monkeypatch, capsys):
    monkeypatch.setattr(
        validate,
        "post",
        lambda: (_ for _ in ()).throw(AssertionError("post called")),
    )
    monkeypatch.setattr(
        validate,
        "teardown",
        lambda: {"success": False, "error": "ratelimited"},
    )

    assert validate.main(["teardown"]) == 1
    assert capsys.readouterr().err.strip() == "teardown failed: ratelimited"
