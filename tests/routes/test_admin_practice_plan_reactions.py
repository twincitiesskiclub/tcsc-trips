"""Route coverage for Activity and Workout Type Plan-reaction defaults."""

import re
from datetime import datetime
from pathlib import Path

import pytest

from app import create_app
from app.models import db
from app.practices.models import (
    Practice,
    PracticeActivity,
    PracticeLocation,
    PracticeType,
)


TEST_RECORD_PREFIX = "Plan Reaction Test"
MODIFIER_RECORD_PREFIX = "Plan Reaction Modifier"
REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_TEMPLATE = REPO_ROOT / "app/templates/admin/practices/config.html"
DETAIL_TEMPLATE = REPO_ROOT / "app/templates/admin/practices/detail.html"
DETAIL_SCRIPT = REPO_ROOT / "app/templates/admin/practices/_detail_script.js"
PLAN_REACTION_EDITOR = REPO_ROOT / "app/static/plan_reactions.js"
PRACTICE_EDITOR = REPO_ROOT / "app/static/practice_editor.js"
MALFORMED_SELECTOR_VALUES = (
    pytest.param(False, id="false"),
    pytest.param(0, id="zero"),
    pytest.param("", id="empty-string"),
    pytest.param({}, id="empty-mapping"),
    pytest.param({"id": 1}, id="truthy-mapping"),
)


def _confirmed_absent_id(model):
    highest_id = (
        db.session.query(model.id)
        .order_by(model.id.desc())
        .limit(1)
        .scalar()
        or 0
    )
    unknown_id = highest_id + 1
    assert db.session.get(model, unknown_id) is None
    return unknown_id


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
    locations = PracticeLocation.query.filter(
        PracticeLocation.name.startswith(TEST_RECORD_PREFIX)
    ).all()
    location_ids = [location.id for location in locations]
    if location_ids:
        for practice in Practice.query.filter(
            Practice.location_id.in_(location_ids)
        ).all():
            db.session.delete(practice)
        db.session.flush()
        for location in locations:
            db.session.delete(location)
    for model in (PracticeActivity, PracticeType):
        model.query.filter(
            model.name.startswith(TEST_RECORD_PREFIX)
            | model.name.startswith(MODIFIER_RECORD_PREFIX)
        ).delete(synchronize_session=False)
    db.session.commit()

    yield

    db.session.rollback()
    locations = PracticeLocation.query.filter(
        PracticeLocation.name.startswith(TEST_RECORD_PREFIX)
    ).all()
    location_ids = [location.id for location in locations]
    if location_ids:
        for practice in Practice.query.filter(
            Practice.location_id.in_(location_ids)
        ).all():
            db.session.delete(practice)
        db.session.flush()
        for location in locations:
            db.session.delete(location)
    for model in (PracticeActivity, PracticeType):
        model.query.filter(
            model.name.startswith(TEST_RECORD_PREFIX)
            | model.name.startswith(MODIFIER_RECORD_PREFIX)
        ).delete(synchronize_session=False)
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


@pytest.fixture
def second_activity(db_session):
    activity = PracticeActivity(
        name="Plan Reaction Test Second Activity",
        default_plan_reactions=[
            {"emoji": "snowflake", "label": "Use the shorter route"}
        ],
    )
    db.session.add(activity)
    db.session.commit()
    return activity


@pytest.fixture
def conflicting_type(db_session):
    practice_type = PracticeType(
        name="Plan Reaction Test Conflicting Type",
        default_plan_reactions=[
            {"emoji": "hatching_chick", "label": "Choose technique drills"}
        ],
    )
    db.session.add(practice_type)
    db.session.commit()
    return practice_type


@pytest.fixture
def location(db_session):
    practice_location = PracticeLocation(name="Plan Reaction Test Location")
    db.session.add(practice_location)
    db.session.commit()
    return practice_location


@pytest.fixture
def practice_with_plan_reactions(db_session, location):
    practice = Practice(
        date=datetime.fromisoformat("2026-07-14T18:15"),
        day_of_week="Tuesday",
        location_id=location.id,
        plan_reactions=[
            {"emoji": "evergreen_tree", "label": "Saved endurance option"}
        ],
    )
    db.session.add(practice)
    db.session.commit()
    return practice


def test_create_without_plan_key_resolves_selected_defaults(
    admin_client,
    db_session,
    activity_with_plan_reactions,
    second_activity,
    location,
):
    response = admin_client.post(
        "/admin/practices/create",
        json={
            "date": "2026-07-14T18:15",
            "location_id": location.id,
            "activity_ids": [
                activity_with_plan_reactions.id,
                second_activity.id,
            ],
            "type_ids": [],
        },
    )

    assert response.status_code == 200
    practice = db_session.session.get(
        Practice, response.get_json()["practice_id"]
    )
    assert practice.plan_reactions == (
        activity_with_plan_reactions.default_plan_reactions
        + second_activity.default_plan_reactions
    )


def test_create_explicit_empty_suppresses_defaults(
    admin_client, db_session, activity_with_plan_reactions, location
):
    response = admin_client.post(
        "/admin/practices/create",
        json={
            "date": "2026-07-14T18:15",
            "location_id": location.id,
            "activity_ids": [activity_with_plan_reactions.id],
            "type_ids": [],
            "plan_reactions": [],
        },
    )

    assert response.status_code == 200
    practice = db_session.session.get(
        Practice, response.get_json()["practice_id"]
    )
    assert practice.plan_reactions == []


def test_create_without_selector_keys_uses_empty_sources(
    admin_client, db_session, location
):
    response = admin_client.post(
        "/admin/practices/create",
        json={
            "date": "2026-07-14T18:15",
            "location_id": location.id,
        },
    )

    assert response.status_code == 200
    practice = db.session.get(Practice, response.get_json()["practice_id"])
    assert practice.plan_reactions == []
    assert practice.activities == []
    assert practice.practice_types == []


def test_create_duplicate_activity_ids_count_once_not_as_multisport(
    admin_client, db_session, activity_with_plan_reactions, location
):
    response = admin_client.post(
        "/admin/practices/create",
        json={
            "date": "2026-07-14T18:15",
            "location_id": location.id,
            "activity_ids": [activity_with_plan_reactions.id] * 3,
            "type_ids": [],
        },
    )

    assert response.status_code == 200
    practice = db.session.get(Practice, response.get_json()["practice_id"])
    assert practice.plan_reactions == []
    assert [item.id for item in practice.activities] == [
        activity_with_plan_reactions.id
    ]


@pytest.mark.parametrize(
    ("field", "model", "error_label"),
    [
        ("activity_ids", PracticeActivity, "Activity"),
        ("type_ids", PracticeType, "Workout Type"),
    ],
)
def test_create_rejects_unknown_selector_ids(
    admin_client,
    db_session,
    activity_with_plan_reactions,
    conflicting_type,
    location,
    field,
    model,
    error_label,
):
    unknown_id = _confirmed_absent_id(model)
    known_id = (
        activity_with_plan_reactions.id
        if field == "activity_ids"
        else conflicting_type.id
    )
    payload = {"activity_ids": [], "type_ids": []}
    payload[field] = [known_id, unknown_id]
    response = admin_client.post(
        "/admin/practices/create",
        json={
            "date": "2026-07-14T18:15",
            "location_id": location.id,
            **payload,
        },
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": f"Unknown {error_label} ID: {unknown_id}",
        "field": field,
    }


def test_edit_rejects_unknown_selector_id_without_mutating_snapshot(
    admin_client,
    db_session,
    practice_with_plan_reactions,
    activity_with_plan_reactions,
):
    unknown_id = _confirmed_absent_id(PracticeActivity)
    before = list(practice_with_plan_reactions.plan_reactions)
    response = admin_client.post(
        f"/admin/practices/{practice_with_plan_reactions.id}/edit",
        json={
            "activity_ids": [
                activity_with_plan_reactions.id,
                unknown_id,
            ]
        },
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": f"Unknown Activity ID: {unknown_id}",
        "field": "activity_ids",
    }
    db.session.refresh(practice_with_plan_reactions)
    assert practice_with_plan_reactions.plan_reactions == before


@pytest.mark.parametrize("field", ["activity_ids", "type_ids"])
@pytest.mark.parametrize("selector_value", MALFORMED_SELECTOR_VALUES)
def test_create_rejects_malformed_selector_values(
    admin_client,
    location,
    field,
    selector_value,
):
    payload = {
        "date": "2026-07-14T18:15",
        "location_id": location.id,
        "activity_ids": [],
        "type_ids": [],
    }
    payload[field] = selector_value

    response = admin_client.post("/admin/practices/create", json=payload)

    label = {
        "activity_ids": "Activity IDs",
        "type_ids": "Workout Type IDs",
    }[field]
    assert response.status_code == 400
    assert response.get_json() == {
        "error": f"{label}: invalid ID",
        "field": field,
    }


@pytest.mark.parametrize("field", ["activity_ids", "type_ids"])
@pytest.mark.parametrize("selector_value", MALFORMED_SELECTOR_VALUES)
def test_edit_rejects_malformed_selector_values_without_mutation(
    admin_client,
    db_session,
    practice_with_plan_reactions,
    activity_with_plan_reactions,
    conflicting_type,
    field,
    selector_value,
):
    practice_with_plan_reactions.activities = [activity_with_plan_reactions]
    practice_with_plan_reactions.practice_types = [conflicting_type]
    practice_with_plan_reactions.workout_description = "Original workout"
    db.session.commit()
    practice_id = practice_with_plan_reactions.id
    before_snapshot = [
        dict(item) for item in practice_with_plan_reactions.plan_reactions
    ]
    before_activity_ids = [
        item.id for item in practice_with_plan_reactions.activities
    ]
    before_type_ids = [
        item.id for item in practice_with_plan_reactions.practice_types
    ]

    response = admin_client.post(
        f"/admin/practices/{practice_id}/edit",
        json={
            field: selector_value,
            "workout_description": "Must not be saved",
        },
    )

    label = {
        "activity_ids": "Activity IDs",
        "type_ids": "Workout Type IDs",
    }[field]
    assert response.status_code == 400
    assert response.get_json() == {
        "error": f"{label}: invalid ID",
        "field": field,
    }
    db.session.expire_all()
    practice = db.session.get(Practice, practice_id)
    assert [item.id for item in practice.activities] == before_activity_ids
    assert [item.id for item in practice.practice_types] == before_type_ids
    assert practice.plan_reactions == before_snapshot
    assert practice.workout_description == "Original workout"


def test_editing_tags_without_plan_key_preserves_snapshot(
    admin_client, db_session, practice_with_plan_reactions, second_activity
):
    original = list(practice_with_plan_reactions.plan_reactions)
    response = admin_client.post(
        f"/admin/practices/{practice_with_plan_reactions.id}/edit",
        json={"activity_ids": [second_activity.id]},
    )

    assert response.status_code == 200
    db_session.session.refresh(practice_with_plan_reactions)
    assert practice_with_plan_reactions.plan_reactions == original


def test_cross_week_date_edit_passes_previous_date_and_notice(
    admin_client,
    practice_with_plan_reactions,
    second_activity,
    monkeypatch,
):
    refresh_calls = []
    monkeypatch.setattr(
        "app.slack.practices.refresh_practice_posts",
        lambda *args, **kwargs: refresh_calls.append((args, kwargs)),
    )

    response = admin_client.post(
        f"/admin/practices/{practice_with_plan_reactions.id}/edit",
        json={
            "date": "2026-07-21T19:15",
            "plan_reactions": [
                {"emoji": "snowflake", "label": "New shorter route"}
            ],
        },
    )

    assert response.status_code == 200
    assert len(refresh_calls) == 1
    args, kwargs = refresh_calls[0]
    assert args == (practice_with_plan_reactions,)
    assert kwargs == {
        "change_type": "edit",
        "previous_date": datetime(2026, 7, 14, 18, 15),
        "announcement_notice": (
            "🕒 Date or time updated, check the heading above."
        ),
        "previous_plan_reactions": [
            {"emoji": "evergreen_tree", "label": "Saved endurance option"}
        ],
    }


def test_location_edit_passes_temporary_notice(
    admin_client, db_session, practice_with_plan_reactions, monkeypatch
):
    replacement = PracticeLocation(name="Plan Reaction Test New Location")
    db.session.add(replacement)
    db.session.commit()
    refresh_calls = []
    monkeypatch.setattr(
        "app.slack.practices.refresh_practice_posts",
        lambda *args, **kwargs: refresh_calls.append((args, kwargs)),
    )

    response = admin_client.post(
        f"/admin/practices/{practice_with_plan_reactions.id}/edit",
        json={"location_id": replacement.id},
    )

    assert response.status_code == 200
    assert refresh_calls[0][1]["announcement_notice"] == (
        "📍 Location updated, check Where below."
    )


def test_workout_only_edit_passes_no_temporary_notice(
    admin_client, practice_with_plan_reactions, monkeypatch
):
    refresh_calls = []
    monkeypatch.setattr(
        "app.slack.practices.refresh_practice_posts",
        lambda *args, **kwargs: refresh_calls.append((args, kwargs)),
    )

    response = admin_client.post(
        f"/admin/practices/{practice_with_plan_reactions.id}/edit",
        json={"workout_description": "6 x 3 minutes"},
    )

    assert response.status_code == 200
    assert refresh_calls[0][1]["announcement_notice"] is None


def test_posted_web_edit_returns_saved_but_unsynced_feedback(
    admin_client, db_session, practice_with_plan_reactions, monkeypatch
):
    practice_with_plan_reactions.slack_channel_id = "C-POSTED"
    practice_with_plan_reactions.slack_message_ts = "root.1"
    db.session.commit()
    monkeypatch.setattr(
        "app.slack.practices.refresh_practice_posts",
        lambda *_args, **_kwargs: {
            "announcement": {"success": False, "error": "Slack failed"},
        },
    )

    response = admin_client.post(
        f"/admin/practices/{practice_with_plan_reactions.id}/edit",
        json={"workout_description": "Saved workout"},
    )

    assert response.status_code == 502
    assert response.get_json() == {
        "success": False,
        "practice_updated": True,
        "error": (
            "Practice was updated, but its Slack announcement did not update. "
            "Retry the edit to refresh the announcement."
        ),
    }
    db.session.refresh(practice_with_plan_reactions)
    assert practice_with_plan_reactions.workout_description == "Saved workout"


def test_unposted_web_edit_remains_successful_when_refresh_has_no_announcement(
    admin_client, db_session, practice_with_plan_reactions, monkeypatch
):
    monkeypatch.setattr(
        "app.slack.practices.refresh_practice_posts",
        lambda *_args, **_kwargs: {
            "announcement": {"success": False, "error": "No root"},
        },
    )

    response = admin_client.post(
        f"/admin/practices/{practice_with_plan_reactions.id}/edit",
        json={"workout_description": "No-root workout"},
    )

    assert response.status_code == 200
    assert response.get_json()["success"] is True
    db.session.refresh(practice_with_plan_reactions)
    assert practice_with_plan_reactions.workout_description == "No-root workout"


def test_web_edit_ignores_later_refresh_failures_after_announcement_success(
    admin_client, db_session, practice_with_plan_reactions, monkeypatch
):
    practice_with_plan_reactions.slack_channel_id = "C-POSTED"
    practice_with_plan_reactions.slack_message_ts = "root.1"
    db.session.commit()
    monkeypatch.setattr(
        "app.slack.practices.refresh_practice_posts",
        lambda *_args, **_kwargs: {
            "announcement": {"success": True},
            "collab": {"success": False, "error": "Collab failed"},
            "weekly_summary": {"success": False, "error": "Summary failed"},
        },
    )

    response = admin_client.post(
        f"/admin/practices/{practice_with_plan_reactions.id}/edit",
        json={"workout_description": "Root-synced workout"},
    )

    assert response.status_code == 200
    assert response.get_json()["success"] is True


def test_restore_defaults_resolves_current_selected_sources(
    admin_client,
    db_session,
    practice_with_plan_reactions,
    activity_with_plan_reactions,
    second_activity,
):
    response = admin_client.post(
        f"/admin/practices/{practice_with_plan_reactions.id}/edit",
        json={
            "activity_ids": [
                activity_with_plan_reactions.id,
                second_activity.id,
            ],
            "type_ids": [],
            "restore_plan_reaction_defaults": True,
        },
    )

    assert response.status_code == 200
    db_session.session.refresh(practice_with_plan_reactions)
    assert practice_with_plan_reactions.plan_reactions == (
        activity_with_plan_reactions.default_plan_reactions
        + second_activity.default_plan_reactions
    )


def test_create_derived_defaults_reports_source_named_conflict(
    admin_client,
    activity_with_plan_reactions,
    second_activity,
    conflicting_type,
    location,
):
    response = admin_client.post(
        "/admin/practices/create",
        json={
            "date": "2026-07-14T18:15",
            "location_id": location.id,
            "activity_ids": [
                activity_with_plan_reactions.id,
                second_activity.id,
            ],
            "type_ids": [conflicting_type.id],
        },
    )

    assert response.status_code == 400
    result = response.get_json()
    assert result["field"] == "plan_reactions"
    assert "Activity Plan Reaction Test Clearable Activity" in result["error"]
    assert "Workout Type Plan Reaction Test Conflicting Type" in result["error"]


def test_explicit_snapshot_cannot_bypass_selected_source_conflict(
    admin_client,
    activity_with_plan_reactions,
    second_activity,
    conflicting_type,
    location,
):
    response = admin_client.post(
        "/admin/practices/create",
        json={
            "date": "2026-07-14T18:15",
            "location_id": location.id,
            "activity_ids": [
                activity_with_plan_reactions.id,
                second_activity.id,
            ],
            "type_ids": [conflicting_type.id],
            "plan_reactions": [],
        },
    )

    assert response.status_code == 400
    assert response.get_json()["field"] == "plan_reactions"
    assert "conflicting labels" in response.get_json()["error"]


def test_create_rejects_tampered_emoji_absent_from_settings(
    admin_client, location
):
    response = admin_client.post(
        "/admin/practices/create",
        json={
            "date": "2026-07-14T18:15",
            "location_id": location.id,
            "activity_ids": [],
            "type_ids": [],
            "plan_reactions": [
                {"emoji": "made_up", "label": "tampered"}
            ],
        },
    )

    assert response.status_code == 400
    assert response.get_json()["field"] == "plan_reactions"
    assert "not configured in Settings" in response.get_json()["error"]


def test_edit_allows_saved_key_after_settings_key_was_removed(
    admin_client, db_session, practice_with_plan_reactions
):
    practice_with_plan_reactions.plan_reactions = [
        {"emoji": "legacy_saved", "label": "legacy description"}
    ]
    db.session.commit()
    response = admin_client.post(
        f"/admin/practices/{practice_with_plan_reactions.id}/edit",
        json={
            "plan_reactions": [
                {
                    "emoji": "legacy_saved",
                    "label": "custom legacy description",
                }
            ]
        },
    )

    assert response.status_code == 200
    db.session.refresh(practice_with_plan_reactions)
    assert practice_with_plan_reactions.plan_reactions[0]["label"] == (
        "custom legacy description"
    )


def test_edit_allows_current_catalog_key_with_custom_description(
    admin_client,
    db_session,
    practice_with_plan_reactions,
    activity_with_plan_reactions,
):
    response = admin_client.post(
        f"/admin/practices/{practice_with_plan_reactions.id}/edit",
        json={
            "plan_reactions": [
                {
                    "emoji": "hatching_chick",
                    "label": "First time on rollerskis",
                }
            ]
        },
    )

    assert response.status_code == 200
    db.session.refresh(practice_with_plan_reactions)
    assert practice_with_plan_reactions.plan_reactions == [
        {
            "emoji": "hatching_chick",
            "label": "First time on rollerskis",
        }
    ]


def test_deleted_catalog_key_blocks_new_open_edit_row_but_preserves_saved_key(
    admin_client,
    db_session,
    practice_with_plan_reactions,
    activity_with_plan_reactions,
):
    activity_with_plan_reactions.default_plan_reactions = []
    db.session.commit()
    response = admin_client.post(
        f"/admin/practices/{practice_with_plan_reactions.id}/edit",
        json={
            "plan_reactions": [
                {
                    "emoji": "hatching_chick",
                    "label": "unsaved open-modal text",
                }
            ]
        },
    )

    assert response.status_code == 400
    assert "not configured in Settings" in response.get_json()["error"]


@pytest.mark.parametrize("field", ["workout_description", "logistics_notes"])
def test_create_rejects_oversized_practice_text(admin_client, location, field):
    response = admin_client.post(
        "/admin/practices/create",
        json={
            "date": "2026-07-14T18:15",
            "location_id": location.id,
            field: "x" * 2501,
        },
    )

    assert response.status_code == 400
    assert response.get_json()["field"] == field


@pytest.mark.parametrize("field", ["workout_description", "logistics_notes"])
def test_edit_rejects_oversized_practice_text(
    admin_client, practice_with_plan_reactions, field
):
    response = admin_client.post(
        f"/admin/practices/{practice_with_plan_reactions.id}/edit",
        json={field: "x" * 2501},
    )

    assert response.status_code == 400
    assert response.get_json()["field"] == field


def test_practice_editor_exposes_structured_plan_reaction_controls(
    admin_client, db_session
):
    response = admin_client.get("/admin/practices/new")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'id="plan-reaction-editor"' in body
    assert 'id="plan-reaction-rows"' in body
    assert 'id="plan-reaction-empty"' in body
    assert 'id="add-plan-reaction"' in body
    assert 'id="restore-plan-reactions"' in body
    assert 'for="plan-reaction-catalog"' in body
    assert re.search(
        r'<label[^>]*for="plan-reaction-catalog"[^>]*class="sr-only"', body
    )
    assert 'id="plan-reaction-catalog"' in body
    assert 'id="plan-reaction-unconfigured"' in body
    assert 'id="plan-reaction-status" role="status" aria-live="polite"' in body
    assert (
        body.index("practice_editor.js")
        < body.index("practice_plan_reactions.js")
        < body.index("practice_plan_reaction_editor.js")
    )
    assert re.search(r'src="[^"]*/plan_reactions\.js"', body) is None


def test_practice_editor_textareas_share_server_length_limit():
    template = DETAIL_TEMPLATE.read_text()

    assert re.search(r'id="workout_description"[^>]*maxlength="2500"', template)
    assert re.search(r'id="logistics_notes"[^>]*maxlength="2500"', template)


def test_tag_pills_notify_derived_reaction_state_after_toggle():
    editor = PRACTICE_EDITOR.read_text()

    assert "function peRenderTagPills(containerId, data, selectedIds, onChange = null)" in editor
    assert "if (onChange) onChange();" in editor


def test_practice_editor_uses_one_structured_controller_and_explicit_snapshot():
    script = DETAIL_SCRIPT.read_text()

    assert "let planReactionController = null;" in script
    assert "PracticePlanReactionEditor.mount({" in script
    assert "planReactionController.setSelection(" in script
    assert "payload.plan_reactions = planReactionController.snapshot();" in script
    assert "showToast(error.message || 'Check Plan reactions.', 'error');" in script
    assert "planReactionMode" not in script
    assert re.search(r"\bPlanReactionEditor\b", script) is None
    assert ".plan-reaction-emoji" not in script
    assert "restore_plan_reaction_defaults" not in script


def test_practice_selectors_are_labelled_and_described_by_reaction_status():
    template = DETAIL_TEMPLATE.read_text()

    assert 'id="activities-label"' in template
    assert re.search(
        r'id="activities-pills"[^>]*role="group"'
        r'[^>]*aria-labelledby="activities-label"'
        r'[^>]*aria-describedby="plan-reaction-status"',
        template,
    )
    assert 'id="types-label"' in template
    assert re.search(
        r'id="types-pills"[^>]*role="group"'
        r'[^>]*aria-labelledby="types-label"'
        r'[^>]*aria-describedby="plan-reaction-status"',
        template,
    )


def test_practice_plan_reaction_controls_have_mobile_touch_targets():
    template = DETAIL_TEMPLATE.read_text()

    mobile_styles = template.split("@media(max-width:767px){", 1)[1]
    assert ".practice-reaction-label" in mobile_styles
    assert ".practice-reaction-action" in mobile_styles
    assert "#add-plan-reaction" in mobile_styles
    assert "#restore-plan-reactions" in mobile_styles
    assert "#plan-reaction-catalog" in mobile_styles
    assert "#plan-reaction-catalog{min-height:44px;width:100%}" in mobile_styles


def test_practice_reaction_css_targets_the_controller_row_class():
    template = DETAIL_TEMPLATE.read_text()
    editor = (REPO_ROOT / "app/static/practice_plan_reaction_editor.js").read_text()

    assert "rowNode.className = 'practice-reaction-row';" in editor
    assert "practice-reaction-label" in editor
    assert "practice-reaction-action" in editor
    assert "#workout-editor .practice-reaction-row{" in template
    assert "#workout-editor .practice-reaction-row.is-removed{" in template
    assert "#workout-editor .practice-reaction-action{" in template
    assert "#workout-editor .practice-reaction-action:focus-visible{" in template
    mobile_styles = template.split("@media(max-width:767px){", 1)[1]
    assert "#workout-editor .practice-reaction-row{grid-template-columns:1fr}" in (
        mobile_styles
    )
    assert "#workout-editor .plan-reaction-row{" not in template
    assert "#workout-editor .plan-reaction-row.is-removed{" not in template
    assert "#workout-editor .plan-reaction-action{" not in template


def test_removed_reactions_use_full_contrast_surface_and_safe_wrapping():
    template = DETAIL_TEMPLATE.read_text()

    removed_match = re.search(
        r"#workout-editor \.practice-reaction-row\.is-removed\{([^}]*)\}",
        template,
    )
    assert removed_match
    removed = removed_match.group(1)
    assert "opacity" not in removed
    assert "background:#f8fafb" in removed
    assert "border:1px solid #cbd5e1" in removed
    assert "color:#1c2c44" in removed
    static_match = re.search(
        r"#workout-editor \.practice-reaction-label-static\{([^}]*)\}",
        template,
    )
    assert static_match
    static_label = static_match.group(1)
    assert "min-width:0" in static_label
    assert "overflow-wrap:anywhere" in static_label

    def channel(value):
        normalized = value / 255
        return (
            normalized / 12.92
            if normalized <= 0.04045
            else ((normalized + 0.055) / 1.055) ** 2.4
        )

    def luminance(color):
        values = [int(color[index:index + 2], 16) for index in (1, 3, 5)]
        red, green, blue = [channel(value) for value in values]
        return 0.2126 * red + 0.7152 * green + 0.0722 * blue

    light = luminance("#f8fafb")
    dark = luminance("#1c2c44")
    ratio = (max(light, dark) + 0.05) / (min(light, dark) + 0.05)
    assert ratio >= 4.5


def test_practice_reference_loading_mounts_safe_fallbacks_independently():
    script = DETAIL_SCRIPT.read_text()
    editor = (REPO_ROOT / "app/static/practice_plan_reaction_editor.js").read_text()

    assert "Promise.allSettled(" in editor
    assert "if (!response.ok)" in editor
    assert "PracticePlanReactionEditor.loadReferenceData(fetch)" in script
    assert "references.reactionSettingsReady" in script
    assert "Could not load reaction Settings. Try again." in script
    assert "referenceError:" in script
    assert "await Promise.all([" not in script


def test_invalid_reaction_settings_retry_with_the_protected_saved_row_fallback():
    script = DETAIL_SCRIPT.read_text()
    initializer = script.split(
        "function initializePlanReactionEditor", 1
    )[1].split("document.addEventListener", 1)[0]

    assert "try {" in initializer
    assert "catch (error)" in initializer
    assert "if (referenceError) throw error;" in initializer
    assert "initializePlanReactionEditor(reactionSettingsLoadError);" in initializer
    assert initializer.index("PracticePlanReactionEditor.mount") < initializer.index(
        "catch (error)"
    ) < initializer.index(
        "initializePlanReactionEditor(reactionSettingsLoadError);"
    )


def test_any_reference_failure_blocks_submit_before_empty_assignments_can_save():
    script = DETAIL_SCRIPT.read_text()

    assert "let formReferenceLoadError = null;" in script
    assert (
        "formReferenceLoadError = "
        "'Could not load form options. Refresh and try again.';" in script
    )
    submit = script.split(
        "document.getElementById('practice-form').addEventListener('submit'", 1
    )[1]
    assert "if (formReferenceLoadError) {" in submit
    assert "showToast(formReferenceLoadError, 'error');" in submit
    assert submit.index("if (formReferenceLoadError) {") < submit.index(
        "const payload = {"
    )


def test_all_reaction_server_fields_are_mirrored_to_the_live_status():
    script = DETAIL_SCRIPT.read_text()

    assert "PracticePlanReactionEditor.isReactionField(result.field)" in script
    assert "planReactionController.showError(result.error);" in script


def test_practice_reaction_script_never_renders_untrusted_html():
    script = DETAIL_SCRIPT.read_text()
    editor = (REPO_ROOT / "app/static/practice_plan_reaction_editor.js").read_text()

    assert "innerHTML" not in editor
    assert ".plan-reaction-emoji" not in script


def test_reaction_source_json_exposes_python_casefold_sort_keys(
    admin_client, db_session
):
    activity = PracticeActivity(name="Plan Reaction Test Straße Activity")
    practice_type = PracticeType(name="Plan Reaction Test Kelvin Type")
    db.session.add_all([activity, practice_type])
    db.session.commit()

    activities = admin_client.get("/admin/practices/activities/data").get_json()[
        "activities"
    ]
    types = admin_client.get("/admin/practices/types/data").get_json()["types"]
    activity_json = next(item for item in activities if item["id"] == activity.id)
    type_json = next(item for item in types if item["id"] == practice_type.id)

    assert activity_json["plan_reaction_sort_key"] == activity.name.casefold()
    assert type_json["plan_reaction_sort_key"] == practice_type.name.casefold()


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


def test_settings_normalizes_wrapped_skin_tone_name(admin_client, db_session):
    response = admin_client.post(
        "/admin/practices/activities/create",
        json={
            "name": "Plan Reaction Modifier Rollerski",
            "gear_required": [],
            "default_plan_reactions": [{
                "emoji": ":older_adult::skin-tone-4:",
                "label": "experienced rollerskier",
            }],
        },
    )
    assert response.status_code == 200
    assert response.get_json()["activity"]["default_plan_reactions"] == [{
        "emoji": "older_adult::skin-tone-4",
        "label": "experienced rollerskier",
    }]


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


def test_settings_rejects_reserved_base_with_modifier(admin_client, db_session):
    response = admin_client.post(
        "/admin/practices/types/create",
        json={
            "name": "Plan Reaction Modifier Invalid",
            "default_plan_reactions": [{
                "emoji": "white_check_mark::skin-tone-4",
                "label": "Wrong",
            }],
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


def test_reaction_move_boundaries_do_not_signal_customization():
    editor = PLAN_REACTION_EDITOR.read_text()
    up_handler = editor.split("up.onclick = () => {", 1)[1].split(
        "const down =", 1
    )[0]
    down_handler = editor.split("down.onclick = () => {", 1)[1].split(
        "const remove =", 1
    )[0]

    assert "if (!wrap.previousElementSibling) return;" in up_handler
    assert "if (!wrap.nextElementSibling) return;" in down_handler
    assert up_handler.count("changed(true);") == 1
    assert down_handler.count("changed(true);") == 1
    assert up_handler.index("insertBefore(") < up_handler.index("changed(true);")
    assert down_handler.index("insertBefore(") < down_handler.index("changed(true);")
