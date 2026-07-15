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


def test_date_edit_passes_temporary_notice_and_previous_plan_snapshot(
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
            "date": "2026-07-14T19:15",
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


def test_practice_editor_exposes_inline_plan_reaction_controls(admin_client, db_session):
    response = admin_client.get("/admin/practices/new")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'id="plan-reaction-rows"' in body
    assert 'id="add-plan-reaction"' in body
    assert 'id="restore-plan-reactions"' in body
    assert 'id="plan-reaction-status" role="status" aria-live="polite"' in body
    assert body.index("plan_reactions.js") < body.index("practice_editor.js")


def test_practice_editor_textareas_share_server_length_limit():
    template = DETAIL_TEMPLATE.read_text()

    assert re.search(r'id="workout_description"[^>]*maxlength="2500"', template)
    assert re.search(r'id="logistics_notes"[^>]*maxlength="2500"', template)


def test_tag_pills_notify_derived_reaction_state_after_toggle():
    editor = PRACTICE_EDITOR.read_text()

    assert "function peRenderTagPills(containerId, data, selectedIds, onChange = null)" in editor
    assert "if (onChange) onChange();" in editor


def test_practice_editor_payload_distinguishes_derived_custom_and_restore_modes():
    script = DETAIL_SCRIPT.read_text()

    assert "let planReactionMode = practiceId ? 'snapshot' : 'derived';" in script
    assert "if (planReactionMode === 'custom')" in script
    assert "payload.plan_reactions = reactions;" in script
    assert "else if (planReactionMode === 'restore')" in script
    assert "payload.restore_plan_reaction_defaults = true;" in script


def test_practice_plan_reaction_controls_have_mobile_touch_targets():
    template = DETAIL_TEMPLATE.read_text()

    mobile_styles = template.split("@media(max-width:767px){", 1)[1]
    assert ".plan-reaction-emoji" in mobile_styles
    assert ".plan-reaction-label" in mobile_styles
    assert ".plan-reaction-action" in mobile_styles
    assert "#add-plan-reaction" in mobile_styles
    assert "#restore-plan-reactions" in mobile_styles
    assert mobile_styles.count("min-height:44px") >= 3


def test_removing_last_practice_reaction_returns_focus_to_add():
    script = DETAIL_SCRIPT.read_text()
    callbacks = script.split("function planReactionCallbacks()", 1)[1].split(
        "function updatePlanReactionAddState()", 1
    )[0]

    assert "onEmptyFocus()" in callbacks
    assert "document.getElementById('add-plan-reaction').focus();" in callbacks


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
