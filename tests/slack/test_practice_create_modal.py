"""Tests for the Slack 'Add Practice' (create) modal builder.

Covers the coach/lead pickers added so coaches can assign people at creation
time from the weekly coach-summary 'Add Practice' button.
"""

import copy
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app import create_app
from app.models import db
from app.practices.plan_reaction_editor import build_plan_reaction_editor_state
from app.practices.models import (
    Practice,
    PracticeActivity,
    PracticeLocation,
    PracticeType,
)
from app.practices.plan_reactions import (
    EVERGREEN_PLAN_REACTION,
    build_plan_reaction_catalog,
)
import app.slack.bolt_app as bolt_module
from app.slack.bolt_app import _parse_practice_authoring_values
from app.slack.modals import build_practice_create_modal
from app.slack.practice_reaction_editor import (
    decode_practice_reaction_metadata,
    encode_practice_reaction_metadata,
)


CREATE_TEST_PREFIX = "Slack Create Structured Test"
CREATE_BODY = {"user": {"id": "U-CREATE-TEST"}}


def _blocks_by_id(modal):
    return {b.get("block_id"): b for b in modal["blocks"] if b.get("block_id")}


def _authoring_values(workout=""):
    return {
        "workout_block": {"workout_description": {"value": workout}},
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
        elif element["type"] == "timepicker":
            action_value = {"selected_time": element.get("initial_time")}
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


def _reaction_inputs():
    intervals = SimpleNamespace(
        id=1,
        name="Intervals",
        default_plan_reactions=[EVERGREEN_PLAN_REACTION],
    )
    editor = build_plan_reaction_editor_state(
        practice_types=[intervals],
        activities=[],
        saved_snapshot=None,
    ).state
    return {
        "reaction_editor": editor,
        "reaction_catalog": build_plan_reaction_catalog([intervals], []),
    }


def _cleanup_create_records():
    for practice in Practice.query.filter(
        Practice.slack_coach_summary_ts == CREATE_TEST_PREFIX
    ).all():
        practice.activities.clear()
        practice.practice_types.clear()
        db.session.delete(practice)
    db.session.flush()
    for model in (PracticeActivity, PracticeType, PracticeLocation):
        for record in model.query.filter(
            model.name.startswith(CREATE_TEST_PREFIX)
        ).all():
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
        _cleanup_create_records()
        yield db
        db.session.rollback()
        _cleanup_create_records()


@pytest.fixture
def create_sources(db_session):
    location = PracticeLocation(name=f"{CREATE_TEST_PREFIX} Location")
    activity = PracticeActivity(
        name=f"{CREATE_TEST_PREFIX} Run",
        default_plan_reactions=[
            {"emoji": "athletic_shoe", "label": "runner"}
        ],
    )
    practice_type = PracticeType(
        name=f"{CREATE_TEST_PREFIX} Intervals",
        default_plan_reactions=[
            {"emoji": "snowflake", "label": "shorter route"}
        ],
    )
    db.session.add_all([location, activity, practice_type])
    db.session.commit()
    return location, activity, practice_type


@pytest.fixture
def create_view(create_sources):
    location, activity, practice_type = create_sources
    editor = build_plan_reaction_editor_state(
        practice_types=[practice_type],
        activities=[activity],
        saved_snapshot=None,
    ).state
    catalog = build_plan_reaction_catalog([practice_type], [activity])
    modal = build_practice_create_modal(
        datetime(2026, 7, 21, 18, 15),
        "18:15",
        locations=[(location.id, location.name)],
        channel_id="C-CREATE-TEST",
        message_ts=CREATE_TEST_PREFIX,
        all_activities=[(activity.id, activity.name)],
        all_types=[(practice_type.id, practice_type.name)],
        slot_defaults={
            "location_id": location.id,
            "activity_ids": [activity.id],
            "type_ids": [practice_type.id],
        },
        reaction_editor=editor,
        reaction_catalog=catalog,
    )
    modal["state"] = {"values": _view_values(modal)}
    return modal


def test_create_modal_has_coach_and_lead_pickers():
    eligible_coaches = [(1, "Alice Coach", "U1"), (2, "Bob Coach", "U2")]
    eligible_leads = [(3, "Carol Lead", "U3")]
    modal = build_practice_create_modal(
        datetime(2026, 6, 9, 18, 0),
        "18:00",
        locations=[(10, "Theodore Wirth")],
        eligible_coaches=eligible_coaches,
        eligible_leads=eligible_leads,
        **_reaction_inputs(),
    )
    blocks = _blocks_by_id(modal)
    assert "coaches_block" in blocks, "create modal must expose a Coaches picker"
    assert "leads_block" in blocks, "create modal must expose a Leads picker"
    assert blocks["coaches_block"]["element"]["action_id"] == "coach_ids"
    assert blocks["leads_block"]["element"]["action_id"] == "lead_ids"


def test_create_modal_preselects_default_coaches():
    modal = build_practice_create_modal(
        datetime(2026, 6, 9, 18, 0),
        "18:00",
        locations=[(10, "Theodore Wirth")],
        eligible_coaches=[(1, "Alice Coach", "U1"), (2, "Bob Coach", "U2")],
        eligible_leads=[(3, "Carol Lead", "U3")],
        slot_defaults={"coach_ids": [2]},
        **_reaction_inputs(),
    )
    coaches = _blocks_by_id(modal)["coaches_block"]["element"]
    initial = {o["value"] for o in coaches.get("initial_options", [])}
    assert initial == {"2"}, "default coach_ids should be pre-selected"


def test_create_modal_omits_pickers_when_no_people():
    """No eligible people -> no coach/lead blocks (graceful, like the edit modal)."""
    modal = build_practice_create_modal(
        datetime(2026, 6, 9, 18, 0),
        "18:00",
        locations=[(10, "Theodore Wirth")],
        **_reaction_inputs(),
    )
    blocks = _blocks_by_id(modal)
    assert "coaches_block" not in blocks
    assert "leads_block" not in blocks


def test_create_uses_structured_reactions_and_dispatching_selectors():
    modal = build_practice_create_modal(
        datetime(2026, 7, 14, 18, 15),
        "18:15",
        locations=[(10, "Theodore Wirth")],
        all_activities=[(1, "Run"), (2, "Rollerski")],
        all_types=[(1, "Intervals")],
        slot_defaults={"activity_ids": [1, 2], "type_ids": [1]},
        **_reaction_inputs(),
    )
    blocks = _blocks_by_id(modal)

    assert "plan_reactions_block" not in blocks
    assert blocks["activities_block"]["dispatch_action"] is True
    assert blocks["types_block"]["dispatch_action"] is True
    assert blocks["practice_reaction_key_r0"]["text"]["text"] == (
        "*:evergreen_tree:*"
    )
    assert blocks["practice_reaction_row_r0"]["element"]["max_length"] == 80
    assert blocks["workout_block"]["element"]["max_length"] == 2500
    mode, context, state, preview = decode_practice_reaction_metadata(
        modal["private_metadata"]
    )
    assert mode == "create"
    assert context == {
        "date": "2026-07-14",
        "channel_id": None,
        "message_ts": None,
    }
    assert state.rows[0].emoji == "evergreen_tree"
    assert preview is None


def test_create_ellipsizes_location_activity_and_type_option_text():
    long_name = "x" * 76
    modal = build_practice_create_modal(
        datetime(2026, 7, 14, 18, 15),
        "18:15",
        locations=[(10, long_name)],
        all_activities=[(1, long_name)],
        all_types=[(1, long_name)],
        **_reaction_inputs(),
    )
    blocks = _blocks_by_id(modal)

    for block_id in ("location_block", "activities_block", "types_block"):
        option = blocks[block_id]["element"]["options"][0]
        assert len(option["text"]["text"]) == 75
        assert option["text"]["text"].endswith("…")


def test_authoring_parser_reads_only_workout():
    fields, errors = _parse_practice_authoring_values(
        _authoring_values(workout="5 x 4 minutes"),
    )
    assert errors == {}
    assert fields == {"workout_description": "5 x 4 minutes"}


def test_authoring_rejects_tampered_oversized_workout():
    fields, errors = _parse_practice_authoring_values(
        _authoring_values(workout="x" * 2501)
    )
    assert len(fields["workout_description"]) == 2501
    assert errors == {
        "workout_block": "Workout must be 2,500 characters or fewer"
    }


def test_authoring_rejects_malformed_scalar_workout_without_throwing():
    fields, errors = _parse_practice_authoring_values({
        "workout_block": {"workout_description": {"value": 7}}
    })

    assert fields == {"workout_description": ""}
    assert errors == {"workout_block": "Workout must be text"}


def test_create_submission_rejects_unknown_activity_before_persistence(
    db_session,
    create_view,
):
    create_view["state"]["values"]["activities_block"]["activity_ids"][
        "selected_options"
    ] = [{"value": "999999"}]
    ack = MagicMock()
    before = Practice.query.count()

    bolt_module._handle_practice_create_submission(
        ack,
        CREATE_BODY,
        create_view,
        MagicMock(),
        MagicMock(),
    )

    assert ack.call_args.kwargs["response_action"] == "errors"
    assert "activities_block" in ack.call_args.kwargs["errors"]
    assert Practice.query.count() == before


def test_create_submission_maps_malformed_activity_state_without_persistence(
    db_session,
    create_view,
):
    create_view["state"]["values"]["activities_block"]["activity_ids"][
        "selected_options"
    ] = "not-a-list"
    ack = MagicMock()
    before = Practice.query.count()

    bolt_module._handle_practice_create_submission(
        ack,
        CREATE_BODY,
        create_view,
        MagicMock(),
        MagicMock(),
    )

    assert ack.call_args.kwargs == {
        "response_action": "errors",
        "errors": {
            "activities_block": "Invalid Activity selection. Please try again."
        },
    }
    assert Practice.query.count() == before


@pytest.mark.parametrize(
    "tamper",
    [
        lambda values: values["flags_block"]["practice_flags"].update(
            {"selected_options": "not-a-list"}
        ),
        lambda values: values.update({
            "coaches_block": {
                "coach_ids": {"selected_options": "not-a-list"}
            }
        }),
        lambda values: values.update({"workout_block": 7}),
        lambda values: values.pop("flags_block"),
        lambda values: values.pop("location_block"),
    ],
)
def test_create_submission_rejects_malformed_optional_state_without_persistence(
    db_session,
    create_view,
    tamper,
):
    tamper(create_view["state"]["values"])
    ack = MagicMock()
    before = Practice.query.count()

    bolt_module._handle_practice_create_submission(
        ack,
        CREATE_BODY,
        create_view,
        MagicMock(),
        MagicMock(),
    )

    assert ack.call_args.kwargs["response_action"] == "errors"
    assert Practice.query.count() == before


def test_create_submission_rejects_metadata_tampered_emoji(
    db_session,
    create_view,
):
    mode, context, state, _preview = decode_practice_reaction_metadata(
        create_view["private_metadata"]
    )
    state.rows[0].emoji = "tampered"
    create_view["private_metadata"] = encode_practice_reaction_metadata(
        mode=mode,
        context=context,
        state=state,
    )
    ack = MagicMock()
    before = Practice.query.count()

    bolt_module._handle_practice_create_submission(
        ack,
        CREATE_BODY,
        create_view,
        MagicMock(),
        MagicMock(),
    )

    assert ack.call_args.kwargs["response_action"] == "errors"
    assert "not configured in Settings" in next(
        iter(ack.call_args.kwargs["errors"].values())
    )
    assert Practice.query.count() == before


@pytest.mark.parametrize(
    "tamper",
    [
        lambda view: view.update({"private_metadata": "{}"}),
        lambda view: view.update({"callback_id": "practice_edit_full"}),
    ],
)
def test_create_submission_rejects_malformed_context_without_persistence(
    db_session,
    create_view,
    tamper,
):
    tamper(create_view)
    ack = MagicMock()
    before = Practice.query.count()

    bolt_module._handle_practice_create_submission(
        ack,
        CREATE_BODY,
        create_view,
        MagicMock(),
        MagicMock(),
    )

    assert ack.call_args.kwargs["response_action"] == "errors"
    assert Practice.query.count() == before


def test_create_submission_maps_incomplete_structured_row_without_persistence(
    db_session,
    create_view,
):
    create_view["state"]["values"]["practice_reaction_row_r0"][
        "practice_reaction_description"
    ]["value"] = ""
    ack = MagicMock()
    before = Practice.query.count()

    bolt_module._handle_practice_create_submission(
        ack,
        CREATE_BODY,
        create_view,
        MagicMock(),
        MagicMock(),
    )

    assert ack.call_args.kwargs == {
        "response_action": "errors",
        "errors": {
            "practice_reaction_row_r0": (
                "Enter a description for :snowflake:."
            )
        },
    }
    assert Practice.query.count() == before


def test_create_reaction_action_reloads_settings_without_persisting(
    db_session,
    create_view,
):
    create_view["id"] = "V_CREATE"
    create_view["hash"] = "HASH_CREATE"
    create_view["state"]["values"]["workout_block"][
        "workout_description"
    ]["value"] = "Unsaved Create workout"
    body = {
        "type": "block_actions",
        "user": {"id": "U-CREATE-TEST"},
        "view": create_view,
    }
    before = Practice.query.count()
    client = MagicMock()

    bolt_module._handle_practice_reaction_action(
        lambda: None,
        body,
        {"action_id": "practice_reaction_remove", "value": "r0"},
        client,
        MagicMock(),
    )

    updated = client.views_update.call_args.kwargs["view"]
    assert updated["callback_id"] == "practice_create"
    assert _blocks_by_id(updated)["workout_block"]["element"][
        "initial_value"
    ] == "Unsaved Create workout"
    assert Practice.query.count() == before


def test_create_submission_persists_validated_structured_state(
    db_session,
    create_sources,
    create_view,
    monkeypatch,
):
    _location, activity, practice_type = create_sources
    values = create_view["state"]["values"]
    values["workout_block"]["workout_description"]["value"] = (
        "Validated workout"
    )
    values["practice_reaction_row_r0"][
        "practice_reaction_description"
    ]["value"] = "Edited shorter-route label"
    thread = MagicMock()
    monkeypatch.setattr(bolt_module.threading, "Thread", thread)
    ack = MagicMock()

    bolt_module._handle_practice_create_submission(
        ack,
        CREATE_BODY,
        create_view,
        MagicMock(),
        MagicMock(),
    )

    ack.assert_called_once_with()
    practice = Practice.query.filter_by(
        slack_coach_summary_ts=CREATE_TEST_PREFIX
    ).one()
    assert practice.workout_description == "Validated workout"
    assert practice.plan_reactions == [{
        "emoji": "snowflake",
        "label": "Edited shorter-route label",
    }]
    assert {item.id for item in practice.activities} == {activity.id}
    assert {item.id for item in practice.practice_types} == {practice_type.id}
    thread.return_value.start.assert_called_once_with()
