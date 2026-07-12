"""Route coverage for Activity and Workout Type Plan-reaction defaults."""

import re
from pathlib import Path

import pytest

from app import create_app
from app.models import db
from app.practices.models import PracticeActivity, PracticeType


TEST_RECORD_PREFIX = "Plan Reaction Test"
REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_TEMPLATE = REPO_ROOT / "app/templates/admin/practices/config.html"
PLAN_REACTION_EDITOR = REPO_ROOT / "app/static/plan_reactions.js"


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key"
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"
    )
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db_session(app):
    with app.app_context():
        db.create_all()
        yield db
        db.session.rollback()


@pytest.fixture
def admin_client(client):
    """A test client with an authenticated admin session."""
    with client.session_transaction() as sess:
        sess["user"] = {
            "email": "tester@twincitiesskiclub.org",
            "name": "Tester",
        }
    return client


@pytest.fixture(autouse=True)
def cleanup_plan_reaction_test_records(db_session):
    """Remove records committed by the Settings routes before and after tests."""
    for model in (PracticeActivity, PracticeType):
        model.query.filter(model.name.startswith(TEST_RECORD_PREFIX)).delete(
            synchronize_session=False
        )
    db.session.commit()

    yield

    db.session.rollback()
    for model in (PracticeActivity, PracticeType):
        model.query.filter(model.name.startswith(TEST_RECORD_PREFIX)).delete(
            synchronize_session=False
        )
    db.session.commit()


@pytest.fixture
def activity_with_plan_reactions(db_session):
    activity = PracticeActivity(
        name="Plan Reaction Test Clearable Activity",
        default_plan_reactions=[
            {"emoji": "hatching_chick", "label": "New to rollerskiing"}
        ],
    )
    db.session.add(activity)
    db.session.commit()
    yield activity


def test_create_activity_persists_default_plan_reactions(admin_client, db_session):
    response = admin_client.post(
        "/admin/practices/activities/create",
        json={
            "name": "Plan Reaction Test Rollerski",
            "gear_required": [],
            "default_plan_reactions": [
                {"emoji": ":hatching_chick:", "label": "New to rollerskiing"}
            ],
        },
    )
    assert response.status_code == 200
    assert response.get_json()["activity"]["default_plan_reactions"] == [
        {"emoji": "hatching_chick", "label": "New to rollerskiing"}
    ]


def test_create_interval_type_uses_explicit_reactions(admin_client, db_session):
    response = admin_client.post(
        "/admin/practices/types/create",
        json={
            "name": "Plan Reaction Test Intervals",
            "fitness_goals": [],
            "has_intervals": True,
            "default_plan_reactions": [
                {
                    "emoji": "evergreen_tree",
                    "label": "Endurance instead of intervals",
                }
            ],
        },
    )
    assert response.status_code == 200
    assert (
        response.get_json()["type"]["default_plan_reactions"][0]["emoji"]
        == "evergreen_tree"
    )


def test_settings_reject_reserved_emoji(admin_client, db_session):
    response = admin_client.post(
        "/admin/practices/types/create",
        json={
            "name": "Plan Reaction Test Invalid",
            "default_plan_reactions": [
                {"emoji": "white_check_mark", "label": "Wrong"}
            ],
        },
    )
    assert response.status_code == 400
    assert response.get_json()["field"] == "default_plan_reactions"


def test_edit_can_clear_defaults(
    admin_client, db_session, activity_with_plan_reactions
):
    response = admin_client.post(
        f"/admin/practices/activities/{activity_with_plan_reactions.id}/edit",
        json={"default_plan_reactions": []},
    )
    assert response.status_code == 200
    assert response.get_json()["activity"]["default_plan_reactions"] == []


def test_interval_type_without_explicit_reactions_stays_empty(admin_client):
    response = admin_client.post(
        "/admin/practices/types/create",
        json={
            "name": "Plan Reaction Test No Hidden Default",
            "fitness_goals": [],
            "has_intervals": True,
        },
    )
    assert response.status_code == 200
    assert response.get_json()["type"]["default_plan_reactions"] == []


def test_plan_reaction_inputs_have_44px_mobile_touch_targets():
    template = CONFIG_TEMPLATE.read_text()

    assert re.search(
        r"@media\(max-width:\s*767px\)\s*\{.*?"
        r"\.plan-reaction-emoji,\s*\.plan-reaction-label\s*\{"
        r"(?=[^}]*min-height:\s*44px)[^}]*\}",
        template,
        re.DOTALL,
    )


def test_successful_plan_reaction_save_preserves_row_dom():
    template = CONFIG_TEMPLATE.read_text()
    save_function = template.split("function savePlanReactions()", 1)[1].split(
        "const callbacks =", 1
    )[0]
    success_handler = save_function.split(".then(result => {", 1)[1].split(
        "}).catch", 1
    )[0]

    assert "PlanReactionEditor.set(" not in success_handler


def test_successful_plan_reaction_save_keeps_live_confirmation_visible():
    template = CONFIG_TEMPLATE.read_text()
    save_function = template.split("function savePlanReactions()", 1)[1].split(
        "const callbacks =", 1
    )[0]
    success_handler = save_function.split(".then(result => {", 1)[1].split(
        "}).catch", 1
    )[0]

    assert success_handler.index("updateAddState();") < success_handler.index(
        "setStatus('Saved.', false);"
    )


def test_remove_reaction_hands_focus_to_a_stable_control():
    editor = PLAN_REACTION_EDITOR.read_text()
    remove_handler = editor.split("remove.onclick = () => {", 1)[1].split(
        "for (const button", 1
    )[0]
    template = CONFIG_TEMPLATE.read_text()

    assert "wrap.nextElementSibling" in remove_handler
    assert "wrap.previousElementSibling" in remove_handler
    assert "focusTarget.focus()" in remove_handler
    assert "onEmptyFocus()" in remove_handler
    assert "onEmptyFocus: () => addButton.focus()" in template
