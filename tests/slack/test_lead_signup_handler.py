"""The Lead button handler: sign up, or tell the clicker privately why not."""

from contextlib import nullcontext
from unittest.mock import MagicMock

from app.slack import bolt_app

BODY = {"user": {"id": "U0CLICK"}, "channel": {"id": "C0COORD"}}


def test_action_pattern_matches_only_lead_buttons():
    assert bolt_app.LEAD_SIGNUP_ACTION.match("lead_signup_123")
    assert not bolt_app.LEAD_SIGNUP_ACTION.match("lead_signup_")
    assert not bolt_app.LEAD_SIGNUP_ACTION.match("block_schedule_post")


def test_success_is_silent(monkeypatch, app):
    calls = []
    monkeypatch.setattr("app.slack.bolt_app.get_app_context", nullcontext)
    monkeypatch.setattr("app.practices.blocks.sign_up_as_lead",
                        lambda pid, uid: calls.append((pid, uid)) or {"success": True})
    client = MagicMock()
    bolt_app._lead_signup(BODY, {"value": "42"}, client)
    assert calls == [(42, "U0CLICK")]
    client.chat_postEphemeral.assert_not_called()


def test_refusal_goes_to_the_clicker_privately(monkeypatch, app):
    monkeypatch.setattr("app.slack.bolt_app.get_app_context", nullcontext)
    monkeypatch.setattr("app.practices.blocks.sign_up_as_lead",
                        lambda pid, uid: {"success": False, "error": "Just filled, thanks!"})
    client = MagicMock()
    bolt_app._lead_signup(BODY, {"value": "42"}, client)
    client.chat_postEphemeral.assert_called_once_with(
        channel="C0COORD", user="U0CLICK", text="Just filled, thanks!")


def test_crash_becomes_a_try_again(monkeypatch, db_session):  # rollback needs an app context
    monkeypatch.setattr("app.slack.bolt_app.get_app_context", nullcontext)

    def boom(pid, uid):
        raise RuntimeError("db down")

    monkeypatch.setattr("app.practices.blocks.sign_up_as_lead", boom)
    client = MagicMock()
    bolt_app._lead_signup(BODY, {"value": "42"}, client)
    assert client.chat_postEphemeral.call_args.kwargs["text"] == (
        "Could not sign you up. Try again.")
