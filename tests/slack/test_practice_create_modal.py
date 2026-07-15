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
from app.models import User, db
from app.practices.plan_reaction_editor import (
    add_catalog_plan_reaction,
    build_plan_reaction_editor_state,
    reconcile_plan_reaction_editor_state,
)
from app.practices.plan_reaction_queries import SelectedPlanReactionSources
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


def _omit_selector(modal, block_id):
    modal["blocks"] = [
        block for block in modal["blocks"] if block.get("block_id") != block_id
    ]
    modal["state"]["values"].pop(block_id, None)


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


def test_create_source_query_outage_rolls_back_and_acks_retryable_error(
    db_session,
    create_view,
    monkeypatch,
):
    rollback = MagicMock(side_effect=db.session.rollback)
    monkeypatch.setattr(db.session, "rollback", rollback)
    monkeypatch.setattr(
        bolt_module,
        "load_selected_plan_reaction_sources",
        lambda _session, **_ids: (_ for _ in ()).throw(
            RuntimeError("database unavailable")
        ),
    )
    ack = MagicMock()
    logger = MagicMock()
    before = Practice.query.count()

    bolt_module._handle_practice_create_submission(
        ack,
        CREATE_BODY,
        create_view,
        MagicMock(),
        logger,
    )

    rollback.assert_called_once_with()
    logger.exception.assert_called_once()
    assert ack.call_args.kwargs["response_action"] == "errors"
    assert "location_block" in ack.call_args.kwargs["errors"]
    assert Practice.query.count() == before


@pytest.mark.parametrize("failure_kind", ["location_lookup", "user_lookup"])
def test_create_authoritative_form_lookup_outage_is_retryable_before_mutation(
    db_session,
    create_view,
    monkeypatch,
    failure_kind,
):
    values = create_view["state"]["values"]
    if failure_kind == "location_lookup":
        original_get = db.session.get

        def fail_location_lookup(model, identifier, **kwargs):
            if model is PracticeLocation:
                raise RuntimeError("location database unavailable")
            return original_get(model, identifier, **kwargs)

        monkeypatch.setattr(db.session, "get", fail_location_lookup)
    else:
        values["coaches_block"] = {
            "coach_ids": {"selected_options": [{"value": "999999"}]}
        }
        original_query = db.session.query

        def fail_user_lookup(*entities, **kwargs):
            if entities == (User,):
                raise RuntimeError("user database unavailable")
            return original_query(*entities, **kwargs)

        monkeypatch.setattr(db.session, "query", fail_user_lookup)

    original_rollback = db.session.rollback
    rollback = MagicMock(side_effect=original_rollback)
    add = MagicMock()
    flush = MagicMock()
    commit = MagicMock()
    thread = MagicMock()
    monkeypatch.setattr(db.session, "rollback", rollback)
    monkeypatch.setattr(db.session, "add", add)
    monkeypatch.setattr(db.session, "flush", flush)
    monkeypatch.setattr(db.session, "commit", commit)
    monkeypatch.setattr(bolt_module.threading, "Thread", thread)
    ack = MagicMock()
    logger = MagicMock()
    before = Practice.query.count()

    result = bolt_module._handle_practice_create_submission(
        ack,
        CREATE_BODY,
        create_view,
        MagicMock(),
        logger,
    )

    assert result is None
    rollback.assert_called_once_with()
    logger.exception.assert_called_once()
    ack.assert_called_once()
    assert ack.call_args.kwargs["response_action"] == "errors"
    error_block = next(iter(ack.call_args.kwargs["errors"]))
    assert _blocks_by_id(create_view)[error_block]["type"] == "input"
    assert Practice.query.count() == before
    add.assert_not_called()
    flush.assert_not_called()
    commit.assert_not_called()
    thread.assert_not_called()


@pytest.mark.parametrize(
    ("failure_kind", "expected_block"),
    [("deleted_activity", "activities_block"), ("malformed_type", "types_block")],
)
def test_create_stale_or_malformed_selected_source_maps_selector_error(
    db_session,
    create_sources,
    create_view,
    failure_kind,
    expected_block,
):
    _location, activity, practice_type = create_sources
    if failure_kind == "deleted_activity":
        db.session.delete(activity)
    else:
        practice_type.default_plan_reactions = "not-a-list"
    db.session.commit()
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
    assert expected_block in ack.call_args.kwargs["errors"]
    assert Practice.query.count() == before


@pytest.mark.parametrize("failure_kind", ["catalog_query", "malformed_settings"])
def test_create_catalog_failure_rolls_back_and_acks_retryable_error(
    db_session,
    create_view,
    monkeypatch,
    failure_kind,
):
    rollback = MagicMock(side_effect=db.session.rollback)
    monkeypatch.setattr(db.session, "rollback", rollback)
    if failure_kind == "catalog_query":
        failure_loader = lambda _session: (_ for _ in ()).throw(
            RuntimeError("catalog unavailable")
        )
    else:
        failure_loader = lambda _session: SelectedPlanReactionSources(
            practice_types=(SimpleNamespace(
                id=999,
                name="Malformed Settings Type",
                default_plan_reactions="not-a-list",
            ),),
            activities=(),
        )
    monkeypatch.setattr(
        bolt_module,
        "load_all_plan_reaction_sources",
        failure_loader,
    )
    ack = MagicMock()
    logger = MagicMock()
    before = Practice.query.count()

    bolt_module._handle_practice_create_submission(
        ack,
        CREATE_BODY,
        create_view,
        MagicMock(),
        logger,
    )

    rollback.assert_called_once_with()
    logger.exception.assert_called_once()
    assert ack.call_args.kwargs["response_action"] == "errors"
    assert "location_block" in ack.call_args.kwargs["errors"]
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


@pytest.mark.parametrize("clear_blocking_error", [False, True])
def test_create_submission_rejects_blocked_or_tampered_selector_transition(
    db_session,
    create_sources,
    clear_blocking_error,
    monkeypatch,
):
    location, activity, selected_type = create_sources
    catalog_type = PracticeType(
        name=f"{CREATE_TEST_PREFIX} Four-row catalog",
        default_plan_reactions=[
            {"emoji": f"catalog_{index}", "label": f"Catalog {index}"}
            for index in range(4)
        ],
    )
    db.session.add(catalog_type)
    db.session.commit()
    catalog = build_plan_reaction_catalog(
        [catalog_type, selected_type],
        [activity],
    )
    state = build_plan_reaction_editor_state(
        practice_types=[],
        activities=[activity],
        saved_snapshot=None,
    ).state
    for option in catalog[:4]:
        state = add_catalog_plan_reaction(state, option)
    blocked = reconcile_plan_reaction_editor_state(
        state,
        practice_types=[selected_type],
        activities=[activity],
    ).state
    assert blocked.blocking_error and "more than 4" in blocked.blocking_error
    if clear_blocking_error:
        blocked.blocking_error = None

    modal = build_practice_create_modal(
        datetime(2026, 7, 21, 18, 15),
        "18:15",
        locations=[(location.id, location.name)],
        channel_id="C-CREATE-TEST",
        message_ts=CREATE_TEST_PREFIX,
        all_activities=[(activity.id, activity.name)],
        all_types=[
            (catalog_type.id, catalog_type.name),
            (selected_type.id, selected_type.name),
        ],
        slot_defaults={
            "location_id": location.id,
            "activity_ids": [activity.id],
            "type_ids": [selected_type.id],
        },
        reaction_editor=blocked,
        reaction_catalog=catalog,
    )
    modal["state"] = {"values": _view_values(modal)}
    ack = MagicMock()
    thread = MagicMock()
    monkeypatch.setattr(bolt_module.threading, "Thread", thread)
    before = Practice.query.count()
    add = MagicMock()
    flush = MagicMock()
    commit = MagicMock()
    monkeypatch.setattr(db.session, "add", add)
    monkeypatch.setattr(db.session, "flush", flush)
    monkeypatch.setattr(db.session, "commit", commit)

    bolt_module._handle_practice_create_submission(
        ack,
        CREATE_BODY,
        modal,
        MagicMock(),
        MagicMock(),
    )

    assert ack.call_args.kwargs["response_action"] == "errors"
    assert "types_block" in ack.call_args.kwargs["errors"]
    assert Practice.query.count() == before
    add.assert_not_called()
    flush.assert_not_called()
    commit.assert_not_called()
    thread.assert_not_called()


def test_initial_blocking_error_uses_authoritative_selector_attribution(
    db_session,
    create_sources,
):
    location, activity, selected_type = create_sources
    overflow_type = PracticeType(
        name=f"{CREATE_TEST_PREFIX} Initial overflow",
        default_plan_reactions=[
            {"emoji": f"overflow_{index}", "label": f"Overflow {index}"}
            for index in range(4)
        ],
    )
    db.session.add(overflow_type)
    db.session.commit()
    blocked = build_plan_reaction_editor_state(
        practice_types=[overflow_type, selected_type],
        activities=[activity],
        saved_snapshot=None,
    ).state
    assert blocked.blocking_error and "more than 4" in blocked.blocking_error
    assert set(blocked.last_valid_type_ids) == {
        overflow_type.id,
        selected_type.id,
    }
    modal = build_practice_create_modal(
        datetime(2026, 7, 21, 18, 15),
        "18:15",
        locations=[(location.id, location.name)],
        channel_id="C-CREATE-TEST",
        message_ts=CREATE_TEST_PREFIX,
        all_activities=[(activity.id, activity.name)],
        all_types=[
            (overflow_type.id, overflow_type.name),
            (selected_type.id, selected_type.name),
        ],
        slot_defaults={
            "location_id": location.id,
            "activity_ids": [activity.id],
            "type_ids": [overflow_type.id, selected_type.id],
        },
        reaction_editor=blocked,
        reaction_catalog=build_plan_reaction_catalog(
            [overflow_type, selected_type],
            [activity],
        ),
    )
    modal["state"] = {"values": _view_values(modal)}
    ack = MagicMock()
    before = Practice.query.count()

    bolt_module._handle_practice_create_submission(
        ack,
        CREATE_BODY,
        modal,
        MagicMock(),
        MagicMock(),
    )

    assert ack.call_args.kwargs["response_action"] == "errors"
    assert list(ack.call_args.kwargs["errors"]) == ["types_block"]
    assert Practice.query.count() == before


def test_create_submission_counts_duplicate_selector_ids_once(
    db_session,
    create_sources,
    create_view,
    monkeypatch,
):
    _location, activity, _practice_type = create_sources
    create_view["state"]["values"]["activities_block"]["activity_ids"][
        "selected_options"
    ] = [{"value": str(activity.id)}, {"value": str(activity.id)}]
    monkeypatch.setattr(bolt_module.threading, "Thread", MagicMock())
    ack = MagicMock()

    bolt_module._handle_practice_create_submission(
        ack,
        CREATE_BODY,
        create_view,
        MagicMock(),
        MagicMock(),
    )

    ack.assert_called_once_with()
    created = Practice.query.filter_by(
        slack_coach_summary_ts=CREATE_TEST_PREFIX
    ).one()
    assert [item.id for item in created.activities] == [activity.id]


@pytest.mark.parametrize(
    ("activity_empty", "type_empty"),
    [(True, False), (False, True), (True, True)],
)
def test_create_submission_accepts_legitimately_omitted_empty_selectors(
    db_session,
    create_sources,
    create_view,
    monkeypatch,
    activity_empty,
    type_empty,
):
    _location, activity, practice_type = create_sources
    selected_activities = () if activity_empty else (activity,)
    selected_types = () if type_empty else (practice_type,)
    state = build_plan_reaction_editor_state(
        practice_types=selected_types,
        activities=selected_activities,
        saved_snapshot=None,
    ).state
    mode, context, _old_state, _preview = decode_practice_reaction_metadata(
        create_view["private_metadata"]
    )
    create_view["private_metadata"] = encode_practice_reaction_metadata(
        mode=mode,
        context=context,
        state=state,
    )
    if activity_empty:
        _omit_selector(create_view, "activities_block")
    if type_empty:
        _omit_selector(create_view, "types_block")
    activity_id = activity.id
    type_id = practice_type.id

    def load_sources(session):
        return SelectedPlanReactionSources(
            practice_types=(
                ()
                if type_empty
                else (session.get(PracticeType, type_id),)
            ),
            activities=(
                ()
                if activity_empty
                else (session.get(PracticeActivity, activity_id),)
            ),
        )

    monkeypatch.setattr(
        bolt_module,
        "load_all_plan_reaction_sources",
        load_sources,
    )
    monkeypatch.setattr(
        bolt_module,
        "load_selected_plan_reaction_sources",
        lambda session, **_ids: load_sources(session),
    )
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
    created = Practice.query.filter_by(
        slack_coach_summary_ts=CREATE_TEST_PREFIX
    ).one()
    assert {item.id for item in created.activities} == {
        item.id for item in selected_activities
    }
    assert {item.id for item in created.practice_types} == {
        item.id for item in selected_types
    }


def test_create_missing_selector_with_configured_sources_uses_existing_error_block(
    db_session,
    create_sources,
    create_view,
    monkeypatch,
):
    _location, activity, practice_type = create_sources
    mode, context, state, _preview = decode_practice_reaction_metadata(
        create_view["private_metadata"]
    )
    state.last_valid_activity_ids = ()
    create_view["private_metadata"] = encode_practice_reaction_metadata(
        mode=mode,
        context=context,
        state=state,
    )
    _omit_selector(create_view, "activities_block")
    sources = SelectedPlanReactionSources(
        practice_types=(practice_type,),
        activities=(activity,),
    )
    monkeypatch.setattr(
        bolt_module,
        "load_all_plan_reaction_sources",
        lambda _session: sources,
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

    assert ack.call_args.kwargs == {
        "response_action": "errors",
        "errors": {
            "location_block": "Invalid Activity selection. Please try again."
        },
    }
    assert Practice.query.count() == before


def test_create_selector_error_never_targets_block_absent_from_view(
    db_session,
    create_view,
):
    create_view["blocks"] = [
        block
        for block in create_view["blocks"]
        if block.get("block_id") != "activities_block"
    ]
    create_view["state"]["values"]["activities_block"]["activity_ids"][
        "selected_options"
    ] = [{"value": "not-an-id"}]
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
            "location_block": "Invalid Activity selection. Please try again."
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
