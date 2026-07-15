import copy
import logging
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app import create_app
from app.models import db
from app.practices.interfaces import PracticeInfo, PracticeStatus
from app.practices.plan_reaction_editor import build_plan_reaction_editor_state
from app.practices.plan_reaction_queries import (
    load_all_plan_reaction_sources,
    load_selected_plan_reaction_sources,
)
from app.practices.models import (
    Practice,
    PracticeActivity,
    PracticeLocation,
    PracticeType,
)
from app.practices.plan_reactions import build_plan_reaction_catalog
from app.practices.service import convert_practice_to_info
import app.slack.bolt_app as bolt_module
from app.slack.modals import build_practice_edit_full_modal
from app.slack.practice_reaction_editor import (
    decode_practice_reaction_metadata,
    encode_practice_reaction_metadata,
)


TEST_PREFIX = "Slack Full Edit Test"
_CURRENT_PLAN_REACTIONS = object()


class AckRecorder:
    def __init__(self):
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)


def _blocks_by_id(modal):
    return {
        block["block_id"]: block
        for block in modal["blocks"]
        if "block_id" in block
    }


def _view_values(modal):
    values = {}
    for block in modal["blocks"]:
        block_id = block.get("block_id")
        element = block.get("element")
        if not block_id or not isinstance(element, dict):
            continue
        action_id = element.get("action_id")
        if not action_id:
            continue
        if element["type"] == "plain_text_input":
            action_value = {"value": element.get("initial_value", "")}
        elif element["type"] == "static_select":
            action_value = {"selected_option": element.get("initial_option")}
        else:
            action_value = {
                "selected_options": copy.deepcopy(
                    element.get("initial_options", [])
                )
            }
        values[block_id] = {action_id: action_value}
    return values


def _full_edit_action_body(practice):
    selected = load_selected_plan_reaction_sources(
        db.session,
        activity_ids=[item.id for item in practice.activities],
        type_ids=[item.id for item in practice.practice_types],
    )
    all_sources = load_all_plan_reaction_sources(db.session)
    editor = build_plan_reaction_editor_state(
        practice_types=selected.practice_types,
        activities=selected.activities,
        saved_snapshot=practice.plan_reactions or [],
    ).state
    modal = build_practice_edit_full_modal(
        convert_practice_to_info(practice),
        locations=[
            (item.id, item.name)
            for item in PracticeLocation.query.order_by(
                PracticeLocation.name
            ).all()
        ],
        all_activities=[
            (item.id, item.name)
            for item in all_sources.activities
        ],
        all_types=[
            (item.id, item.name)
            for item in all_sources.practice_types
        ],
        reaction_editor=editor,
        reaction_catalog=build_plan_reaction_catalog(
            all_sources.practice_types,
            all_sources.activities,
        ),
    )
    view = copy.deepcopy(modal)
    view.update({
        "id": "V_FULL_EDIT",
        "hash": "HASH_FULL_EDIT",
        "state": {"values": _view_values(modal)},
    })
    return {
        "type": "block_actions",
        "user": {"id": "U-FULL-EDIT-TEST"},
        "view": view,
    }


def _full_edit_submission_view(
    practice,
    *,
    workout="5 x 4 minutes",
    notes="Meet by the flagpole",
    plan_reactions=_CURRENT_PLAN_REACTIONS,
    location_id=None,
    activity_ids=None,
    type_ids=None,
    is_dark=False,
):
    selected_activity_ids = (
        [item.id for item in practice.activities]
        if activity_ids is None
        else list(activity_ids)
    )
    selected_type_ids = (
        [item.id for item in practice.practice_types]
        if type_ids is None
        else list(type_ids)
    )
    selected = load_selected_plan_reaction_sources(
        db.session,
        activity_ids=selected_activity_ids,
        type_ids=selected_type_ids,
    )
    all_sources = load_all_plan_reaction_sources(db.session)
    snapshot = (
        practice.plan_reactions or []
        if plan_reactions is _CURRENT_PLAN_REACTIONS
        else plan_reactions
    )
    editor = build_plan_reaction_editor_state(
        practice_types=selected.practice_types,
        activities=selected.activities,
        saved_snapshot=snapshot,
    ).state
    modal = build_practice_edit_full_modal(
        convert_practice_to_info(practice),
        locations=[
            (item.id, item.name)
            for item in PracticeLocation.query.order_by(
                PracticeLocation.name
            ).all()
        ],
        all_activities=[
            (item.id, item.name) for item in all_sources.activities
        ],
        all_types=[
            (item.id, item.name) for item in all_sources.practice_types
        ],
        reaction_editor=editor,
        reaction_catalog=build_plan_reaction_catalog(
            all_sources.practice_types,
            all_sources.activities,
        ),
    )
    values = _view_values(modal)
    values["workout_block"]["workout_description"]["value"] = workout
    values["notes_block"]["logistics_notes"]["value"] = notes
    values["activities_block"]["activity_ids"]["selected_options"] = [
        {"value": str(item)} for item in selected_activity_ids
    ]
    values["types_block"]["type_ids"]["selected_options"] = [
        {"value": str(item)} for item in selected_type_ids
    ]
    values["flags_block"]["practice_flags"]["selected_options"] = (
        [{"value": "is_dark_practice"}] if is_dark else []
    )
    if location_id is not None:
        values["location_block"]["location_id"]["selected_option"] = {
            "value": str(location_id)
        }
    modal["state"] = {"values": values}
    return modal


def _full_edit_values(
    *,
    workout="5 x 4 minutes",
    notes="Meet by the flagpole",
    plan_reactions=_CURRENT_PLAN_REACTIONS,
    location_id=None,
    activity_ids=None,
    type_ids=None,
    is_dark=False,
):
    return {
        "workout": workout,
        "notes": notes,
        "plan_reactions": plan_reactions,
        "location_id": location_id,
        "activity_ids": activity_ids,
        "type_ids": type_ids,
        "is_dark": is_dark,
    }


def _submit(practice, values, ack):
    return bolt_module._handle_practice_edit_full_submission(
        ack=ack,
        body={"user": {"id": "U-FULL-EDIT-TEST"}},
        view=_full_edit_submission_view(practice, **values),
        logger=logging.getLogger(__name__),
    )


def _cleanup_test_records():
    for practice in Practice.query.filter(
        Practice.airtable_id.like(f"{TEST_PREFIX}%")
    ).all():
        db.session.delete(practice)
    db.session.flush()
    for model in (PracticeActivity, PracticeType, PracticeLocation):
        for record in model.query.filter(model.name.startswith(TEST_PREFIX)).all():
            db.session.delete(record)
    db.session.commit()


@pytest.fixture
def app():
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret-key"
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = (
        "postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"
    )
    return flask_app


@pytest.fixture
def db_session(app):
    with app.app_context():
        db.create_all()
        _cleanup_test_records()
        yield db
        db.session.rollback()
        _cleanup_test_records()


@pytest.fixture
def source_records(db_session):
    current_location = PracticeLocation(name=f"{TEST_PREFIX} Current Location")
    replacement_location = PracticeLocation(
        name=f"{TEST_PREFIX} Replacement Location"
    )
    current_activity = PracticeActivity(
        name=f"{TEST_PREFIX} Current Activity",
        default_plan_reactions=[
            {"emoji": "evergreen_tree", "label": "Current activity default"}
        ],
    )
    replacement_activity = PracticeActivity(
        name=f"{TEST_PREFIX} Replacement Activity",
        default_plan_reactions=[
            {"emoji": "snowflake", "label": "Replacement activity default"}
        ],
    )
    current_type = PracticeType(
        name=f"{TEST_PREFIX} Current Type",
        default_plan_reactions=[
            {"emoji": "cyclist", "label": "Current type default"}
        ],
    )
    replacement_type = PracticeType(
        name=f"{TEST_PREFIX} Replacement Type",
        default_plan_reactions=[
            {"emoji": "mountain", "label": "Replacement type default"}
        ],
    )
    records = {
        "current_location": current_location,
        "replacement_location": replacement_location,
        "current_activity": current_activity,
        "replacement_activity": replacement_activity,
        "current_type": current_type,
        "replacement_type": replacement_type,
    }
    db.session.add_all(records.values())
    db.session.commit()
    return records


@pytest.fixture
def practice_record(db_session, source_records):
    practice = Practice(
        date=datetime(2026, 7, 14, 18, 15),
        day_of_week="Tuesday",
        status="scheduled",
        location_id=source_records["current_location"].id,
        workout_description="Original workout",
        logistics_notes="Original notes",
        plan_reactions=[
            {"emoji": "athletic_shoe", "label": "Saved custom option"}
        ],
        airtable_id=f"{TEST_PREFIX} Practice",
    )
    practice.activities = [source_records["current_activity"]]
    practice.practice_types = [source_records["current_type"]]
    db.session.add(practice)
    db.session.commit()
    return practice


@pytest.fixture
def refresh_calls(monkeypatch):
    calls = []

    def record_refresh(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(
        "app.slack.practices.refresh_practice_posts", record_refresh
    )
    return calls


def _practice_info():
    return PracticeInfo(
        id=42,
        date=datetime(2026, 7, 14, 18, 15),
        day_of_week="Tuesday",
        status=PracticeStatus.SCHEDULED,
        workout_description="5 x 4 minutes",
        logistics_notes="Meet by the flagpole",
        plan_reactions=[
            {"emoji": "evergreen_tree", "label": "Endurance instead of intervals"}
        ],
    )


def _edit_reaction_inputs(practice):
    settings_source = SimpleNamespace(
        id=1,
        name="Configured options",
        default_plan_reactions=[
            {
                "emoji": row["emoji"],
                "label": row["label"],
            }
            for row in practice.plan_reactions or []
        ],
    )
    editor = build_plan_reaction_editor_state(
        practice_types=[],
        activities=[],
        saved_snapshot=practice.plan_reactions or [],
    ).state
    return {
        "reaction_editor": editor,
        "reaction_catalog": build_plan_reaction_catalog(
            [settings_source],
            [],
        ),
    }


def test_full_edit_modal_limits_all_authoring_fields():
    practice = _practice_info()
    blocks = _blocks_by_id(
        build_practice_edit_full_modal(
            practice,
            **_edit_reaction_inputs(practice),
        )
    )

    assert blocks["workout_block"]["element"]["max_length"] == 2500
    assert blocks["notes_block"]["element"]["max_length"] == 2500
    assert blocks["practice_reaction_row_r0"]["element"]["max_length"] == 80
    assert "plan_reactions_block" not in blocks


def test_full_edit_modal_prefills_saved_notes_and_plan_snapshot():
    practice = _practice_info()
    modal = build_practice_edit_full_modal(
        practice,
        **_edit_reaction_inputs(practice),
    )
    blocks = _blocks_by_id(modal)

    assert blocks["notes_block"]["element"]["initial_value"] == (
        "Meet by the flagpole"
    )
    assert blocks["practice_reaction_key_r0"]["text"]["text"] == (
        "*:evergreen_tree:*"
    )
    assert blocks["practice_reaction_row_r0"]["element"]["initial_value"] == (
        "Endurance instead of intervals"
    )
    action_ids = [
        element["action_id"]
        for block in blocks.values()
        for element in block.get("elements", [])
    ]
    assert "practice_reaction_restore" in action_ids
    mode, context, state, preview = decode_practice_reaction_metadata(
        modal["private_metadata"]
    )
    assert (mode, context, preview) == (
        "edit",
        {"practice_id": 42},
        None,
    )
    assert state.rows[0].emoji == "evergreen_tree"


def test_full_edit_modal_wraps_skin_tone_name_once():
    practice = _practice_info()
    practice.plan_reactions = [{
        "emoji": "older_adult::skin-tone-4",
        "label": "experienced rollerskier",
    }]
    blocks = _blocks_by_id(
        build_practice_edit_full_modal(
            practice,
            **_edit_reaction_inputs(practice),
        )
    )
    assert blocks["practice_reaction_key_r0"]["text"]["text"] == (
        "*:older_adult::skin-tone-4:*"
    )
    assert blocks["practice_reaction_row_r0"]["element"]["initial_value"] == (
        "experienced rollerskier"
    )


def test_full_edit_restore_preserves_every_nonreaction_value(
    db_session,
    practice_record,
):
    body = _full_edit_action_body(practice_record)
    values = body["view"]["state"]["values"]
    values["notes_block"]["logistics_notes"]["value"] = "Keep these notes"
    client = MagicMock()

    bolt_module._handle_practice_reaction_action(
        lambda: None,
        body,
        {"action_id": "practice_reaction_restore"},
        client,
        MagicMock(),
    )

    updated = _blocks_by_id(client.views_update.call_args.kwargs["view"])
    assert updated["notes_block"]["element"]["initial_value"] == (
        "Keep these notes"
    )
    state = decode_practice_reaction_metadata(
        client.views_update.call_args.kwargs["view"]["private_metadata"]
    )[2]
    assert all(row.emoji != "athletic_shoe" for row in state.rows)


def test_restore_conflict_keeps_reaction_state_unchanged(
    db_session,
    practice_record,
    source_records,
):
    source_records["current_type"].default_plan_reactions = [
        {"emoji": "collision", "label": "Current label"}
    ]
    source_records["replacement_type"].default_plan_reactions = [
        {"emoji": "collision", "label": "Conflicting label"}
    ]
    practice_record.practice_types = [
        source_records["current_type"],
        source_records["replacement_type"],
    ]
    db.session.commit()
    body = _full_edit_action_body(practice_record)
    before = decode_practice_reaction_metadata(
        body["view"]["private_metadata"]
    )[2]
    client = MagicMock()

    bolt_module._handle_practice_reaction_action(
        lambda: None,
        body,
        {"action_id": "practice_reaction_restore"},
        client,
        MagicMock(),
    )

    after = decode_practice_reaction_metadata(
        client.views_update.call_args.kwargs["view"]["private_metadata"]
    )[2]
    assert [
        (row.emoji, row.label, row.removed) for row in after.rows
    ] == [
        (row.emoji, row.label, row.removed) for row in before.rows
    ]
    assert after.blocking_error


def test_settings_lookup_failure_preserves_modal_and_surfaces_retry(
    db_session,
    practice_record,
    monkeypatch,
):
    body = _full_edit_action_body(practice_record)
    body["view"]["state"]["values"]["workout_block"][
        "workout_description"
    ]["value"] = "Unsaved workout"
    monkeypatch.setattr(
        bolt_module,
        "load_all_plan_reaction_sources",
        lambda _session: (_ for _ in ()).throw(
            RuntimeError("database unavailable")
        ),
        raising=False,
    )
    client = MagicMock()

    bolt_module._handle_practice_reaction_action(
        lambda: None,
        body,
        {"action_id": "practice_reaction_restore"},
        client,
        MagicMock(),
    )

    updated = _blocks_by_id(client.views_update.call_args.kwargs["view"])
    assert "Try again" in updated["practice_reaction_lookup_error"]["text"][
        "text"
    ]
    assert updated["workout_block"]["element"]["initial_value"] == (
        "Unsaved workout"
    )


def test_unknown_full_edit_selector_has_no_update_or_persistence(
    db_session,
    practice_record,
):
    body = _full_edit_action_body(practice_record)
    body["view"]["state"]["values"]["activities_block"]["activity_ids"][
        "selected_options"
    ] = [{"value": "999999"}]
    original = [dict(item) for item in practice_record.plan_reactions]
    client = MagicMock()

    bolt_module._handle_practice_reaction_action(
        lambda: None,
        body,
        {"action_id": "activity_ids"},
        client,
        MagicMock(),
    )

    client.views_update.assert_not_called()
    db.session.refresh(practice_record)
    assert practice_record.plan_reactions == original


def test_full_edit_accepts_saved_key_missing_from_settings(
    db_session,
    practice_record,
    refresh_calls,
):
    ack = AckRecorder()

    result = _submit(practice_record, _full_edit_values(), ack)

    assert ack.calls == [{}]
    assert result["practice_updated"] is True
    assert practice_record.plan_reactions == [
        {"emoji": "athletic_shoe", "label": "Saved custom option"}
    ]


def test_catalog_key_deleted_while_modal_open_preserves_text_but_blocks_save(
    db_session,
    practice_record,
    source_records,
    refresh_calls,
):
    submitted = [
        {"emoji": "snowflake", "label": "Choose the shorter route"}
    ]
    view = _full_edit_submission_view(
        practice_record,
        plan_reactions=submitted,
    )
    source_records["replacement_activity"].default_plan_reactions = []
    db.session.commit()
    ack = AckRecorder()

    bolt_module._handle_practice_edit_full_submission(
        ack=ack,
        body={"user": {"id": "U-FULL-EDIT-TEST"}},
        view=view,
        client=MagicMock(),
        logger=logging.getLogger(__name__),
    )

    assert ack.calls[0]["response_action"] == "errors"
    assert any(
        "not configured in Settings" in message
        for message in ack.calls[0]["errors"].values()
    )
    assert view["state"]["values"]["practice_reaction_row_r0"][
        "practice_reaction_description"
    ]["value"] == "Choose the shorter route"
    db.session.refresh(practice_record)
    assert practice_record.plan_reactions == [
        {"emoji": "athletic_shoe", "label": "Saved custom option"}
    ]
    assert refresh_calls == []


@pytest.mark.parametrize(
    ("submitted", "expected"),
    [
        (
            [{"emoji": "snowflake", "label": "Choose the shorter route"}],
            [{"emoji": "snowflake", "label": "Choose the shorter route"}],
        ),
        ([], []),
    ],
)
def test_full_edit_submission_persists_plan_edit_or_explicit_clear(
    db_session, practice_record, refresh_calls, submitted, expected
):
    ack = AckRecorder()

    _submit(
        practice_record,
        _full_edit_values(plan_reactions=submitted),
        ack,
    )

    db.session.refresh(practice_record)
    assert ack.calls == [{}]
    assert practice_record.plan_reactions == expected
    assert len(refresh_calls) == 1


@pytest.mark.parametrize(
    ("notes", "expected"),
    [("Updated trail conditions", "Updated trail conditions"), ("", None)],
)
def test_full_edit_submission_updates_or_clears_notes(
    db_session, practice_record, refresh_calls, notes, expected
):
    ack = AckRecorder()

    _submit(practice_record, _full_edit_values(notes=notes), ack)

    db.session.refresh(practice_record)
    assert ack.calls == [{}]
    assert practice_record.logistics_notes == expected
    assert len(refresh_calls) == 1


def test_full_edit_rejects_scalar_notes_without_mutation(
    db_session,
    practice_record,
    refresh_calls,
):
    view = _full_edit_submission_view(practice_record)
    view["state"]["values"]["notes_block"]["logistics_notes"]["value"] = 7
    ack = AckRecorder()

    bolt_module._handle_practice_edit_full_submission(
        ack=ack,
        body={"user": {"id": "U-FULL-EDIT-TEST"}},
        view=view,
        client=MagicMock(),
        logger=logging.getLogger(__name__),
    )

    assert ack.calls == [{
        "response_action": "errors",
        "errors": {"notes_block": "Notes / Logistics must be text"},
    }]
    db.session.refresh(practice_record)
    assert practice_record.logistics_notes == "Original notes"
    assert refresh_calls == []


@pytest.mark.parametrize(
    ("tamper", "expected_block"),
    [
        (
            lambda values: values["activities_block"]["activity_ids"].update(
                {"selected_options": 7}
            ),
            "activities_block",
        ),
        (
            lambda values: values["notify_block"]["notify_update"].update(
                {"selected_options": 7}
            ),
            "location_block",
        ),
        (
            lambda values: values.pop("notify_block"),
            "location_block",
        ),
        (
            lambda values: values.pop("location_block"),
            "location_block",
        ),
    ],
)
def test_full_edit_rejects_malformed_required_or_optional_state(
    db_session,
    practice_record,
    refresh_calls,
    tamper,
    expected_block,
):
    view = _full_edit_submission_view(practice_record)
    tamper(view["state"]["values"])
    ack = AckRecorder()

    bolt_module._handle_practice_edit_full_submission(
        ack=ack,
        body={"user": {"id": "U-FULL-EDIT-TEST"}},
        view=view,
        client=MagicMock(),
        logger=logging.getLogger(__name__),
    )

    assert ack.calls[0]["response_action"] == "errors"
    assert expected_block in ack.calls[0]["errors"]
    db.session.refresh(practice_record)
    assert practice_record.workout_description == "Original workout"
    assert refresh_calls == []


@pytest.mark.parametrize(
    ("overrides", "expected_errors"),
    [
        (
            {"workout": "x" * 2501},
            {"workout_block": "Workout must be 2,500 characters or fewer"},
        ),
        (
            {"notes": "x" * 2501},
            {"notes_block": "Notes / Logistics must be 2,500 characters or fewer"},
        ),
        (
            {
                "plan_reactions": [
                    {"emoji": "tampered", "label": "Tampered option"}
                ]
            },
            {
                "practice_reaction_row_r0": (
                    "Plan reactions: :tampered: is not configured in Settings"
                )
            },
        ),
    ],
)
def test_full_edit_invalid_authoring_returns_field_errors_without_side_effects(
    db_session,
    practice_record,
    source_records,
    refresh_calls,
    overrides,
    expected_errors,
):
    ack = AckRecorder()
    values = _full_edit_values(
        location_id=source_records["replacement_location"].id,
        activity_ids=[source_records["replacement_activity"].id],
        type_ids=[source_records["replacement_type"].id],
        is_dark=True,
        **overrides,
    )

    _submit(practice_record, values, ack)

    db.session.refresh(practice_record)
    assert ack.calls == [
        {"response_action": "errors", "errors": expected_errors}
    ]
    assert practice_record.location_id == source_records["current_location"].id
    assert practice_record.workout_description == "Original workout"
    assert practice_record.logistics_notes == "Original notes"
    assert practice_record.plan_reactions == [
        {"emoji": "athletic_shoe", "label": "Saved custom option"}
    ]
    assert practice_record.is_dark_practice is False
    assert {item.id for item in practice_record.activities} == {
        source_records["current_activity"].id
    }
    assert {item.id for item in practice_record.practice_types} == {
        source_records["current_type"].id
    }
    assert refresh_calls == []


def test_full_edit_source_changes_preserve_submitted_plan_snapshot(
    db_session, practice_record, source_records, refresh_calls
):
    ack = AckRecorder()
    original_snapshot = list(practice_record.plan_reactions)

    _submit(
        practice_record,
        _full_edit_values(
            activity_ids=[source_records["replacement_activity"].id],
            type_ids=[source_records["replacement_type"].id],
        ),
        ack,
    )

    db.session.refresh(practice_record)
    assert ack.calls == [{}]
    assert practice_record.plan_reactions == original_snapshot
    assert {item.id for item in practice_record.activities} == {
        source_records["replacement_activity"].id
    }
    assert {item.id for item in practice_record.practice_types} == {
        source_records["replacement_type"].id
    }
    assert len(refresh_calls) == 1


def test_full_edit_commit_failure_rolls_back_without_refresh(
    db_session,
    practice_record,
    refresh_calls,
    monkeypatch,
):
    original_rollback = db.session.rollback
    rollback = MagicMock(side_effect=original_rollback)
    monkeypatch.setattr(db.session, "rollback", rollback)
    monkeypatch.setattr(
        db.session,
        "commit",
        MagicMock(side_effect=RuntimeError("database unavailable")),
    )
    ack = AckRecorder()

    result = _submit(
        practice_record,
        _full_edit_values(workout="Must roll back"),
        ack,
    )

    assert ack.calls == [{}]
    rollback.assert_called_once_with()
    assert result == {
        "success": False,
        "practice_updated": False,
        "error": "Could not save practice changes. Please try again.",
    }
    assert practice_record.workout_description == "Original workout"
    assert refresh_calls == []


def test_posted_full_edit_returns_saved_but_unsynced_result_and_dms_user(
    db_session, practice_record, monkeypatch
):
    practice_record.slack_channel_id = "C-POSTED"
    practice_record.slack_message_ts = "root.1"
    db.session.commit()
    refresh_result = {
        "announcement": {"success": False, "error": "Slack failed"},
    }
    monkeypatch.setattr(
        "app.slack.practices.refresh_practice_posts",
        lambda *_args, **_kwargs: refresh_result,
    )
    ack = AckRecorder()
    client = MagicMock()

    result = bolt_module._handle_practice_edit_full_submission(
        ack=ack,
        body={"user": {"id": "U-FULL-EDIT-TEST"}},
        view=_full_edit_submission_view(
            practice_record,
            workout="Saved workout",
        ),
        client=client,
        logger=logging.getLogger(__name__),
    )

    db.session.refresh(practice_record)
    assert ack.calls == [{}]
    assert practice_record.workout_description == "Saved workout"
    assert result == {
        "success": False,
        "practice_updated": True,
        "error": (
            "Practice changes were saved, but the Slack announcement was not "
            "updated. Retry the edit or refresh the announcement."
        ),
        "refresh_results": refresh_result,
    }
    client.chat_postMessage.assert_called_once_with(
        channel="U-FULL-EDIT-TEST",
        text=(
            ":warning: Your practice changes were saved, but the Slack "
            "announcement was not updated. Retry the edit or refresh the "
            "announcement."
        ),
    )


def test_full_edit_dm_failure_does_not_undo_saved_database_edit(
    db_session, practice_record, monkeypatch, caplog
):
    practice_record.slack_channel_id = "C-POSTED"
    practice_record.slack_message_ts = "root.1"
    db.session.commit()
    monkeypatch.setattr(
        "app.slack.practices.refresh_practice_posts",
        lambda *_args, **_kwargs: {
            "announcement": {"success": False, "error": "Slack failed"},
        },
    )
    client = MagicMock()
    client.chat_postMessage.side_effect = RuntimeError("DM failed")

    with caplog.at_level(logging.WARNING):
        result = bolt_module._handle_practice_edit_full_submission(
            ack=AckRecorder(),
            body={"user": {"id": "U-FULL-EDIT-TEST"}},
            view=_full_edit_submission_view(
                practice_record,
                workout="Still saved",
            ),
            client=client,
            logger=logging.getLogger(__name__),
        )

    db.session.refresh(practice_record)
    assert result["practice_updated"] is True
    assert result["success"] is False
    assert practice_record.workout_description == "Still saved"
    assert "Could not DM saved-but-unsynced practice edit" in caplog.text


def test_unposted_full_edit_returns_structured_success_without_dm(
    db_session, practice_record, monkeypatch
):
    refresh_result = {
        "announcement": {"success": False, "error": "No root"},
    }
    monkeypatch.setattr(
        "app.slack.practices.refresh_practice_posts",
        lambda *_args, **_kwargs: refresh_result,
    )
    client = MagicMock()

    result = bolt_module._handle_practice_edit_full_submission(
        ack=AckRecorder(),
        body={"user": {"id": "U-FULL-EDIT-TEST"}},
        view=_full_edit_submission_view(practice_record),
        client=client,
        logger=logging.getLogger(__name__),
    )

    assert result == {
        "success": True,
        "practice_updated": True,
        "refresh_results": refresh_result,
    }
    client.chat_postMessage.assert_not_called()
