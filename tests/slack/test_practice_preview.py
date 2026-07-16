"""Contracts for the discard-only Slack Practice Preview."""

import copy
from contextlib import nullcontext
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import app.slack.bolt_app as bolt_module
from app.practices.plan_reaction_editor import build_plan_reaction_editor_state
from app.practices.plan_reactions import build_plan_reaction_catalog
from app.slack.modals import build_practice_preview_modal
from app.slack.practice_reaction_editor import (
    decode_practice_reaction_metadata,
)


PREVIEW_DATE = datetime(2026, 7, 14, 18, 15)


def _blocks_by_id(modal):
    return {
        block["block_id"]: block
        for block in modal["blocks"]
        if "block_id" in block
    }


def _block_index(modal, block_id):
    return next(
        index
        for index, block in enumerate(modal["blocks"])
        if block.get("block_id") == block_id
    )


def _preview_command(**overrides):
    command = {
        "text": "practice-preview",
        "channel_id": "C07G9RTMRT3",
        "user_id": "U_PREVIEWER",
        "user_name": "previewer",
        "trigger_id": "TRIGGER_PREVIEW",
    }
    command.update(overrides)
    return command


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


def _action_body_from_view(modal, *, view_hash="HASH_PREVIEW"):
    view = copy.deepcopy(modal)
    view.update({
        "id": "V_PREVIEW",
        "hash": view_hash,
        "state": {"values": _view_values(modal)},
    })
    return {
        "type": "block_actions",
        "user": {"id": "U_PREVIEWER"},
        "view": view,
    }


@pytest.fixture
def preview_action_body():
    return _action_body_from_view(build_practice_preview_modal(PREVIEW_DATE))


def _expanded_preview_action_body(preview_action_body):
    client = MagicMock()
    bolt_module._handle_practice_reaction_action(
        lambda: None,
        preview_action_body,
        {"action_id": "practice_reaction_edit"},
        client,
        MagicMock(),
    )
    return _action_body_from_view(
        client.views_update.call_args.kwargs["view"],
        view_hash="HASH_EXPANDED",
    )


def test_preview_wraps_the_structured_production_create_modal():
    modal = build_practice_preview_modal(PREVIEW_DATE)

    assert modal["type"] == "modal"
    assert modal["title"] == {
        "type": "plain_text",
        "text": "Practice Preview",
    }
    assert modal["submit"] == {
        "type": "plain_text",
        "text": "Close Preview",
    }
    assert modal["callback_id"] == "practice_preview"
    assert len(modal["blocks"]) == 11
    assert len(modal["private_metadata"]) == 1939
    options = [
        option
        for block in modal["blocks"]
        for option in block.get("element", {}).get("options", [])
    ]
    assert all(len(option["text"]["text"]) <= 75 for option in options)
    assert all(len(option["value"]) <= 150 for option in options)


def test_preview_starts_with_collapsed_summary_as_final_region():
    modal = build_practice_preview_modal(PREVIEW_DATE)
    blocks = _blocks_by_id(modal)
    assert "practice_reaction_summary" in blocks
    assert "practice_reaction_row_r0" not in blocks
    assert _block_index(modal, "practice_reaction_summary") > _block_index(
        modal, "flags_block"
    )


def test_preview_derives_four_rows_from_interval_run_and_rollerski_sources(
    preview_action_body,
):
    modal = _expanded_preview_action_body(preview_action_body)["view"]
    blocks = _blocks_by_id(modal)

    assert blocks["time_block"]["element"]["initial_time"] == "18:15"
    assert blocks["location_block"]["element"]["initial_option"]["value"] == "1"
    assert [
        option["value"]
        for option in blocks["activities_block"]["element"]["initial_options"]
    ] == ["1", "2"]
    assert [
        option["value"]
        for option in blocks["types_block"]["element"]["initial_options"]
    ] == ["1"]
    assert [
        option["value"]
        for option in blocks["coaches_block"]["element"]["initial_options"]
    ] == ["1"]
    assert [
        option["value"]
        for option in blocks["leads_block"]["element"]["initial_options"]
    ] == ["2"]
    assert "plan_reactions_block" not in blocks
    assert [
        blocks[f"practice_reaction_key_r{index}"]["text"]["text"]
        for index in range(4)
    ] == [
        "*:evergreen_tree:*",
        "*:athletic_shoe:*",
        "*:hatching_chick:*",
        "*:older_adult::skin-tone-4:*",
    ]
    assert blocks["activities_block"]["dispatch_action"] is True
    assert blocks["types_block"]["dispatch_action"] is True

    mode, context, state, preview = decode_practice_reaction_metadata(
        modal["private_metadata"]
    )
    assert mode == "preview"
    assert context == {"preview": True}
    assert [row.emoji for row in state.rows] == [
        "evergreen_tree",
        "athletic_shoe",
        "hatching_chick",
        "older_adult::skin-tone-4",
    ]
    assert preview["activities"][2]["name"] == "Strength"
    assert preview["slot_defaults"]["activity_ids"] == [1, 2]


def test_preview_metadata_fully_rebuilds_sources_and_catalog_without_database():
    modal = build_practice_preview_modal(PREVIEW_DATE)
    _mode, _context, encoded_state, preview = (
        decode_practice_reaction_metadata(modal["private_metadata"])
    )
    practice_types = [SimpleNamespace(**source) for source in preview["practice_types"]]
    activities = [SimpleNamespace(**source) for source in preview["activities"]]
    selected_type_ids = set(preview["slot_defaults"]["type_ids"])
    selected_activity_ids = set(preview["slot_defaults"]["activity_ids"])
    selected_types = [
        source for source in practice_types if source.id in selected_type_ids
    ]
    selected_activities = [
        source for source in activities if source.id in selected_activity_ids
    ]

    rebuilt = build_plan_reaction_editor_state(
        practice_types=selected_types,
        activities=selected_activities,
        saved_snapshot=None,
    ).state
    catalog = build_plan_reaction_catalog(practice_types, activities)

    assert [row.emoji for row in rebuilt.rows] == [
        row.emoji for row in encoded_state.rows
    ]
    assert [option.emoji for option in catalog] == [
        "evergreen_tree",
        "athletic_shoe",
        "hatching_chick",
        "older_adult::skin-tone-4",
    ]
    assert "practice_id" not in modal["private_metadata"]


def test_reaction_action_acks_first_and_updates_with_view_hash(
    preview_action_body,
):
    preview_action_body = _expanded_preview_action_body(preview_action_body)
    events = []
    client = MagicMock()
    client.views_update.side_effect = lambda **kwargs: events.append(
        ("update", kwargs)
    )

    bolt_module._handle_practice_reaction_action(
        ack=lambda: events.append(("ack", None)),
        body=preview_action_body,
        action={"action_id": "practice_reaction_remove", "value": "r0"},
        client=client,
        logger=MagicMock(),
    )

    assert events[0] == ("ack", None)
    update = events[1][1]
    assert update["view_id"] == "V_PREVIEW"
    assert update["hash"] == "HASH_EXPANDED"
    assert "practice_reaction_removed_r0" in _blocks_by_id(update["view"])


def test_preview_edit_reactions_expands_in_place_and_preserves_values(
    preview_action_body,
):
    values = preview_action_body["view"]["state"]["values"]
    values["workout_block"]["workout_description"]["value"] = (
        "Unsaved interval workout"
    )
    client = MagicMock()

    bolt_module._handle_practice_reaction_action(
        ack=lambda: None,
        body=preview_action_body,
        action={"action_id": "practice_reaction_edit"},
        client=client,
        logger=MagicMock(),
    )

    updated = client.views_update.call_args.kwargs["view"]
    blocks = _blocks_by_id(updated)
    assert blocks["workout_block"]["element"]["initial_value"] == (
        "Unsaved interval workout"
    )
    assert "practice_reaction_summary" not in blocks
    assert "practice_reaction_row_r0" in blocks
    assert decode_practice_reaction_metadata(
        updated["private_metadata"]
    )[2].editor_expanded is True


def test_preview_action_never_opens_application_context(
    preview_action_body,
    monkeypatch,
):
    monkeypatch.setattr(
        bolt_module,
        "get_app_context",
        lambda: (_ for _ in ()).throw(
            AssertionError("Preview touched app context")
        ),
    )

    bolt_module._handle_practice_reaction_action(
        ack=lambda: None,
        body=preview_action_body,
        action={"action_id": "activity_ids"},
        client=MagicMock(),
        logger=MagicMock(),
    )


def test_remove_accepts_temporarily_blank_description(preview_action_body):
    preview_action_body = _expanded_preview_action_body(preview_action_body)
    preview_action_body["view"]["state"]["values"][
        "practice_reaction_row_r0"
    ]["practice_reaction_description"]["value"] = ""
    client = MagicMock()

    bolt_module._handle_practice_reaction_action(
        ack=lambda: None,
        body=preview_action_body,
        action={"action_id": "practice_reaction_remove", "value": "r0"},
        client=client,
        logger=MagicMock(),
    )

    metadata = client.views_update.call_args.kwargs["view"]["private_metadata"]
    state = decode_practice_reaction_metadata(metadata)[2]
    assert state.rows[0].label == ""
    assert state.rows[0].removed is True


def test_views_update_failure_is_logged(preview_action_body):
    preview_action_body = _expanded_preview_action_body(preview_action_body)
    logger = MagicMock()
    client = MagicMock()
    client.views_update.side_effect = RuntimeError("Slack unavailable")

    bolt_module._handle_practice_reaction_action(
        ack=lambda: None,
        body=preview_action_body,
        action={"action_id": "practice_reaction_remove", "value": "r0"},
        client=client,
        logger=logger,
    )

    logger.exception.assert_called_once()


def test_preview_selector_transition_preserves_unrelated_values(
    preview_action_body,
):
    preview_action_body = _expanded_preview_action_body(preview_action_body)
    values = preview_action_body["view"]["state"]["values"]
    values["workout_block"]["workout_description"]["value"] = "Do not lose me"
    values["activities_block"]["activity_ids"]["selected_options"] = [
        {"value": "1"}
    ]
    client = MagicMock()

    bolt_module._handle_practice_reaction_action(
        ack=lambda: None,
        body=preview_action_body,
        action={"action_id": "activity_ids"},
        client=client,
        logger=MagicMock(),
    )

    updated = client.views_update.call_args.kwargs["view"]
    blocks = _blocks_by_id(updated)
    assert blocks["workout_block"]["element"]["initial_value"] == (
        "Do not lose me"
    )
    assert [
        key for key in blocks if key.startswith("practice_reaction_row_")
    ] == ["practice_reaction_row_r0"]


def test_preview_selector_transition_one_two_three_one_matrix(
    preview_action_body,
):
    preview_action_body = _expanded_preview_action_body(preview_action_body)
    client = MagicMock()
    logger = MagicMock()
    body = preview_action_body
    expected_rows = (1, 4, 4, 1)

    for index, (selected, row_count) in enumerate(zip(
        (["1"], ["1", "2"], ["1", "2", "3"], ["1"]),
        expected_rows,
    )):
        values = body["view"]["state"]["values"]
        values["workout_block"]["workout_description"]["value"] = (
            "Matrix workout"
        )
        values["activities_block"]["activity_ids"]["selected_options"] = [
            {"value": value} for value in selected
        ]
        bolt_module._handle_practice_reaction_action(
            lambda: None,
            body,
            {"action_id": "activity_ids"},
            client,
            logger,
        )
        updated = client.views_update.call_args.kwargs["view"]
        blocks = _blocks_by_id(updated)
        assert len([
            key
            for key in blocks
            if key.startswith("practice_reaction_row_")
        ]) == row_count
        assert blocks["workout_block"]["element"]["initial_value"] == (
            "Matrix workout"
        )
        body = _action_body_from_view(
            updated,
            view_hash=f"HASH_MATRIX_{index}",
        )


def test_nonselector_action_deduplicates_selector_ids_in_first_seen_order(
    preview_action_body,
):
    preview_action_body = _expanded_preview_action_body(preview_action_body)
    values = preview_action_body["view"]["state"]["values"]
    values["activities_block"]["activity_ids"]["selected_options"] = [
        {"value": "2"},
        {"value": "1"},
        {"value": "2"},
    ]
    assert bolt_module._strict_practice_reaction_selector_ids(
        values,
        block_id="activities_block",
        action_id="activity_ids",
    ) == (2, 1)
    client = MagicMock()

    bolt_module._handle_practice_reaction_action(
        lambda: None,
        preview_action_body,
        {"action_id": "practice_reaction_remove", "value": "r0"},
        client,
        MagicMock(),
    )

    assert "practice_reaction_removed_r0" in _blocks_by_id(
        client.views_update.call_args.kwargs["view"]
    )


def test_remove_then_undo_restores_the_same_fixed_key(preview_action_body):
    preview_action_body = _expanded_preview_action_body(preview_action_body)
    client = MagicMock()
    logger = MagicMock()
    bolt_module._handle_practice_reaction_action(
        lambda: None,
        preview_action_body,
        {"action_id": "practice_reaction_remove", "value": "r0"},
        client,
        logger,
    )
    removed = client.views_update.call_args.kwargs["view"]

    bolt_module._handle_practice_reaction_action(
        lambda: None,
        _action_body_from_view(removed, view_hash="HASH_UNDO"),
        {"action_id": "practice_reaction_undo", "value": "r0"},
        client,
        logger,
    )

    restored = client.views_update.call_args.kwargs["view"]
    assert "practice_reaction_row_r0" in _blocks_by_id(restored)


def test_add_then_catalog_select_appends_configured_fixed_key(
    preview_action_body,
):
    preview_action_body = _expanded_preview_action_body(preview_action_body)
    values = preview_action_body["view"]["state"]["values"]
    values["activities_block"]["activity_ids"]["selected_options"] = [
        {"value": "1"}
    ]
    values["types_block"]["type_ids"]["selected_options"] = []
    client = MagicMock()
    logger = MagicMock()
    bolt_module._handle_practice_reaction_action(
        lambda: None,
        preview_action_body,
        {"action_id": "activity_ids"},
        client,
        logger,
    )
    reconciled = client.views_update.call_args.kwargs["view"]
    add_body = _action_body_from_view(reconciled, view_hash="HASH_ADD")

    bolt_module._handle_practice_reaction_action(
        lambda: None,
        add_body,
        {"action_id": "practice_reaction_add"},
        client,
        logger,
    )
    opened = client.views_update.call_args.kwargs["view"]
    picker = _blocks_by_id(opened)["practice_reaction_catalog_block"]
    option = picker["elements"][0]["options"][0]
    catalog_body = _action_body_from_view(opened, view_hash="HASH_CATALOG")

    bolt_module._handle_practice_reaction_action(
        lambda: None,
        catalog_body,
        {
            "action_id": "practice_reaction_catalog_select",
            "selected_option": {"value": option["value"]},
        },
        client,
        logger,
    )

    final = client.views_update.call_args.kwargs["view"]
    assert "practice_reaction_row_r4" in _blocks_by_id(final)
    assert option["value"] not in str(final["blocks"])


@pytest.mark.parametrize(
    "tamper",
    [
        lambda body: body["view"].update({"private_metadata": "{}"}),
        lambda body: body["view"].update({"callback_id": "practice_create"}),
        lambda body: body["view"]["state"]["values"].pop("types_block"),
        lambda body: body["view"]["state"]["values"]["activities_block"][
            "activity_ids"
        ].update({"selected_options": [{"value": "999"}]}),
        lambda body: body["view"]["state"]["values"]["activities_block"][
            "activity_ids"
        ].update({"selected_options": [{"value": "01"}]}),
    ],
)
def test_malformed_preview_action_has_no_update_or_persistence(
    preview_action_body,
    monkeypatch,
    tamper,
):
    tamper(preview_action_body)
    client = MagicMock()
    monkeypatch.setattr(
        bolt_module,
        "get_app_context",
        lambda: (_ for _ in ()).throw(
            AssertionError("malformed Preview touched app context")
        ),
    )

    bolt_module._handle_practice_reaction_action(
        ack=lambda: None,
        body=preview_action_body,
        action={"action_id": "activity_ids"},
        client=client,
        logger=MagicMock(),
    )

    client.views_update.assert_not_called()


@pytest.mark.parametrize(
    "action",
    [
        {"action_id": "unknown_reaction_action"},
        {"action_id": "practice_reaction_remove", "value": "r999"},
        {"action_id": "practice_reaction_undo", "value": "r0"},
        {
            "action_id": "practice_reaction_catalog_select",
            "selected_option": {"value": "forged-option"},
        },
        {"action_id": "practice_reaction_restore"},
    ],
)
def test_unknown_or_impossible_preview_action_is_a_noop(
    preview_action_body,
    action,
):
    preview_action_body = _expanded_preview_action_body(preview_action_body)
    client = MagicMock()

    bolt_module._handle_practice_reaction_action(
        lambda: None,
        preview_action_body,
        action,
        client,
        MagicMock(),
    )

    client.views_update.assert_not_called()


def test_preview_command_rejects_every_other_channel_before_opening_a_view():
    ack = MagicMock()
    client = MagicMock()

    bolt_module._handle_tcsc_command(
        ack=ack,
        command=_preview_command(channel_id="C_OTHER"),
        client=client,
        logger=MagicMock(),
    )

    ack.assert_called_once_with()
    client.views_open.assert_not_called()
    client.chat_postEphemeral.assert_called_once_with(
        channel="C_OTHER",
        user="U_PREVIEWER",
        text=":warning: Practice Preview is available only in the test channel.",
    )


def test_preview_command_reports_a_missing_trigger_without_building_or_opening():
    ack = MagicMock()
    client = MagicMock()
    logger = MagicMock()

    with patch("app.slack.modals.build_practice_preview_modal") as build_preview:
        bolt_module._handle_tcsc_command(
            ack=ack,
            command=_preview_command(trigger_id=""),
            client=client,
            logger=logger,
        )

    ack.assert_called_once_with()
    build_preview.assert_not_called()
    client.views_open.assert_not_called()
    logger.error.assert_called_once()
    client.chat_postEphemeral.assert_called_once_with(
        channel="C07G9RTMRT3",
        user="U_PREVIEWER",
        text=":warning: Could not open Practice Preview. Please try again.",
    )


def test_preview_command_acks_before_opening_the_synthetic_view():
    events = []
    client = MagicMock()
    modal = {"type": "modal", "callback_id": "practice_preview"}

    def record_ack():
        events.append("ack")

    def record_open(**kwargs):
        events.append("views_open")
        assert kwargs == {"trigger_id": "TRIGGER_PREVIEW", "view": modal}

    client.views_open.side_effect = record_open
    with patch(
        "app.utils.now_central_naive", return_value=PREVIEW_DATE
    ), patch(
        "app.slack.modals.build_practice_preview_modal", return_value=modal
    ) as build_preview:
        bolt_module._handle_tcsc_command(
            ack=record_ack,
            command=_preview_command(),
            client=client,
            logger=MagicMock(),
        )

    assert events == ["ack", "views_open"]
    build_preview.assert_called_once_with(PREVIEW_DATE)
    client.chat_postEphemeral.assert_not_called()


def test_preview_command_reports_views_open_failure_ephemerally():
    ack = MagicMock()
    client = MagicMock()
    client.views_open.side_effect = RuntimeError("Slack unavailable")
    logger = MagicMock()

    with patch(
        "app.slack.modals.build_practice_preview_modal",
        return_value={"type": "modal", "callback_id": "practice_preview"},
    ):
        bolt_module._handle_tcsc_command(
            ack=ack,
            command=_preview_command(),
            client=client,
            logger=logger,
        )

    ack.assert_called_once_with()
    logger.exception.assert_called_once()
    client.chat_postEphemeral.assert_called_once_with(
        channel="C07G9RTMRT3",
        user="U_PREVIEWER",
        text=":warning: Could not open Practice Preview. Please try again.",
    )


def test_ordinary_tcsc_command_keeps_the_existing_processor_path(monkeypatch):
    ack = MagicMock()
    client = MagicMock()
    response = {"text": "Existing help", "blocks": [{"type": "divider"}]}
    monkeypatch.setattr(bolt_module, "get_app_context", lambda: nullcontext())

    with patch(
        "app.slack.commands.handle_tcsc_command", return_value=response
    ) as process_command:
        bolt_module._handle_tcsc_command(
            ack=ack,
            command=_preview_command(text="help", channel_id="C_MEMBER"),
            client=client,
            logger=MagicMock(),
        )

    ack.assert_called_once_with()
    process_command.assert_called_once_with("help", "U_PREVIEWER", "previewer")
    client.views_open.assert_not_called()
    client.chat_postEphemeral.assert_called_once_with(
        channel="C_MEMBER",
        user="U_PREVIEWER",
        text="Existing help",
        blocks=[{"type": "divider"}],
    )


def test_preview_command_requires_an_exact_subcommand(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(bolt_module, "get_app_context", lambda: nullcontext())

    with patch(
        "app.slack.commands.handle_tcsc_command",
        return_value={"text": "Unknown command", "blocks": None},
    ) as process_command:
        bolt_module._handle_tcsc_command(
            ack=MagicMock(),
            command=_preview_command(text="practice-preview extra"),
            client=client,
            logger=MagicMock(),
        )

    process_command.assert_called_once_with(
        "practice-preview extra", "U_PREVIEWER", "previewer"
    )
    client.views_open.assert_not_called()


def test_preview_submission_only_acknowledges_and_closes():
    ack = MagicMock()

    with patch.object(
        bolt_module,
        "_parse_practice_authoring_values",
        side_effect=AssertionError("preview must not parse create fields"),
    ), patch.object(
        bolt_module,
        "get_app_context",
        side_effect=AssertionError("preview must not open an app context"),
    ):
        bolt_module._handle_practice_preview_submission(ack)

    ack.assert_called_once_with()
