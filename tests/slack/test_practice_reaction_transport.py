import json
import threading

from flask import Flask, current_app, has_app_context
from slack_bolt import App
from slack_bolt.authorization import AuthorizeResult
from slack_bolt.request import BoltRequest

from app import create_app
import app.slack.bolt_app as bolt_module


ACTION_IDS = (
    "activity_ids",
    "type_ids",
    "practice_reaction_remove",
    "practice_reaction_undo",
    "practice_reaction_add",
    "practice_reaction_catalog_select",
    "practice_reaction_restore",
)


def _current_app_from_background_context():
    observed = []
    errors = []

    def worker():
        try:
            assert not has_app_context()
            with bolt_module.get_app_context():
                observed.append(current_app._get_current_object())
        except BaseException as exc:  # Surface worker failures in the test thread.
            errors.append(exc)

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(timeout=1)

    assert not thread.is_alive()
    assert errors == []
    assert len(observed) == 1
    return observed[0]


def test_explicit_flask_binding_provides_context_to_background_worker(monkeypatch):
    monkeypatch.setattr(bolt_module, "_flask_app", None)
    flask_app = Flask("practice-reaction-worker")

    bolt_module.bind_flask_app(flask_app)

    assert _current_app_from_background_context() is flask_app


def test_http_app_factory_binds_context_for_background_worker(monkeypatch):
    monkeypatch.setattr(bolt_module, "_flask_app", None)

    flask_app = create_app()

    assert _current_app_from_background_context() is flask_app


def _installed_bolt_app():
    def authorize(**_kwargs):
        return AuthorizeResult(
            enterprise_id=None,
            team_id="T_TRANSPORT",
            bot_token="xoxb-transport-test",
            bot_id="B_TRANSPORT",
            bot_user_id="U_TRANSPORT_BOT",
        )

    return App(
        signing_secret="transport-secret",
        authorize=authorize,
        process_before_response=True,
        request_verification_enabled=False,
        ignoring_self_events_enabled=False,
    )


def _request(action_id):
    payload = {
        "type": "block_actions",
        "team": {"id": "T_TRANSPORT"},
        "user": {"id": "U_TRANSPORT"},
        "api_app_id": "A_TRANSPORT",
        "token": "transport-token",
        "container": {"type": "view", "view_id": "V_TRANSPORT"},
        "trigger_id": "TRIGGER_TRANSPORT",
        "response_url": "https://example.test/response",
        "view": {
            "id": "V_TRANSPORT",
            "hash": "HASH_TRANSPORT",
            "callback_id": "practice_create",
            "private_metadata": "metadata",
            "state": {"values": {}},
        },
        "actions": [{
            "action_id": action_id,
            "block_id": "transport_block",
            "action_ts": "1.000001",
            "type": "button",
            "value": "transport-value",
        }],
    }
    return BoltRequest(
        body=json.dumps(payload),
        headers={"content-type": "application/json"},
    )


def test_installed_bolt_returns_ack_before_delayed_reaction_worker_finishes():
    app = _installed_bolt_app()
    worker_started = threading.Event()
    release_worker = threading.Event()
    worker_finished = threading.Event()
    dispatch_finished = threading.Event()
    response = {}

    def delayed_worker(action):
        assert action["action_id"] == "practice_reaction_remove"
        worker_started.set()
        release_worker.wait(2)
        worker_finished.set()

    bolt_module._register_practice_reaction_action_listeners(
        app,
        worker=delayed_worker,
    )

    def dispatch():
        response["value"] = app.dispatch(
            _request("practice_reaction_remove")
        )
        dispatch_finished.set()

    dispatch_thread = threading.Thread(target=dispatch)
    dispatch_thread.start()
    try:
        assert worker_started.wait(1)
        assert dispatch_finished.wait(0.25), (
            "HTTP acknowledgment waited for the lazy reaction worker"
        )
        assert response["value"].status == 200
        assert not worker_finished.is_set()
    finally:
        release_worker.set()
        dispatch_thread.join(timeout=1)
    assert worker_finished.wait(1)


def test_all_seven_reaction_actions_share_ack_and_lazy_worker_registration():
    app = _installed_bolt_app()
    observed = []
    lock = threading.Lock()
    all_finished = threading.Event()

    def worker(action):
        with lock:
            observed.append(action["action_id"])
            if len(observed) == len(ACTION_IDS):
                all_finished.set()

    bolt_module._register_practice_reaction_action_listeners(app, worker=worker)

    responses = [app.dispatch(_request(action_id)) for action_id in ACTION_IDS]

    assert all(response.status == 200 for response in responses)
    assert all_finished.wait(1)
    assert set(observed) == set(ACTION_IDS)
    assert len(app._listeners) == len(ACTION_IDS)
