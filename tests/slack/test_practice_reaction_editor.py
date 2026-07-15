"""Contracts for the structured Slack Plan-reaction editor adapter."""

from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import pytest

from app.practices.plan_reaction_editor import (
    PlanReactionEditorRow,
    PlanReactionEditorState,
    add_catalog_plan_reaction,
    build_plan_reaction_editor_state,
    remove_plan_reaction,
)
from app.practices.plan_reactions import (
    EVERGREEN_PLAN_REACTION,
    PlanReactionCatalogOption,
    PlanReactionValidationError,
)
from app.slack.practice_reaction_editor import (
    ADD_ACTION_ID,
    CATALOG_ACTION_ID,
    DESCRIPTION_ACTION_ID,
    REMOVE_ACTION_ID,
    RESTORE_ACTION_ID,
    UNDO_ACTION_ID,
    apply_current_view_values,
    build_practice_reaction_blocks,
    build_retryable_practice_reaction_error_view,
    decode_practice_reaction_metadata,
    encode_practice_reaction_metadata,
    merge_practice_reaction_inputs,
    parse_practice_reaction_submission,
)


CATALOG = (
    PlanReactionCatalogOption(
        "evergreen-option",
        "evergreen_tree",
        "Endurance instead of intervals",
        ("type:1",),
    ),
    PlanReactionCatalogOption(
        "shoe-option",
        "athletic_shoe",
        "runner",
        ("activity:1",),
    ),
)

PREVIEW_CONFIG = {
    "practice_date": "2026-07-14",
    "default_time": "18:15",
    "locations": [{"id": 1, "name": "Theodore Wirth - Trailhead"}],
    "practice_types": [
        {
            "id": 1,
            "name": "Intervals",
            "default_plan_reactions": [EVERGREEN_PLAN_REACTION],
        }
    ],
    "activities": [
        {
            "id": 1,
            "name": "Run",
            "default_plan_reactions": [
                {"emoji": "athletic_shoe", "label": "runner"}
            ],
        }
    ],
    "slot_defaults": {
        "location_id": 1,
        "activity_ids": [1],
        "type_ids": [1],
    },
    "eligible_coaches": [],
    "eligible_leads": [],
}


def _blocks_by_id(blocks):
    return {
        block["block_id"]: block
        for block in blocks
        if "block_id" in block
    }


def _action_ids(blocks):
    action_ids = []
    for block in blocks:
        action_ids.extend(
            element["action_id"]
            for element in block.get("elements", [])
            if "action_id" in element
        )
        accessory = block.get("accessory", {})
        if "action_id" in accessory:
            action_ids.append(accessory["action_id"])
    return action_ids


@pytest.fixture
def editor_state():
    intervals = SimpleNamespace(
        id=1,
        name="Intervals",
        default_plan_reactions=[EVERGREEN_PLAN_REACTION],
    )
    return build_plan_reaction_editor_state(
        practice_types=[intervals],
        activities=[],
        saved_snapshot=None,
    ).state


@pytest.fixture
def empty_state():
    return PlanReactionEditorState()


@pytest.fixture
def create_blocks():
    return [
        {
            "type": "input",
            "block_id": "workout_block",
            "label": {"type": "plain_text", "text": "Workout"},
            "element": {
                "type": "plain_text_input",
                "action_id": "workout_description",
                "initial_value": "Default workout",
            },
        },
        {
            "type": "input",
            "block_id": "time_block",
            "label": {"type": "plain_text", "text": "Time"},
            "element": {
                "type": "timepicker",
                "action_id": "practice_time",
                "initial_time": "18:15",
            },
        },
        {
            "type": "input",
            "block_id": "activities_block",
            "label": {"type": "plain_text", "text": "Activities"},
            "element": {
                "type": "multi_static_select",
                "action_id": "activity_ids",
                "options": [
                    {
                        "text": {"type": "plain_text", "text": "Run"},
                        "value": "1",
                    },
                    {
                        "text": {"type": "plain_text", "text": "Rollerski"},
                        "value": "2",
                    },
                ],
                "initial_options": [
                    {
                        "text": {"type": "plain_text", "text": "Run"},
                        "value": "1",
                    }
                ],
            },
        },
        {
            "type": "input",
            "block_id": "flags_block",
            "label": {"type": "plain_text", "text": "Flags"},
            "element": {
                "type": "checkboxes",
                "action_id": "practice_flags",
                "options": [
                    {
                        "text": {"type": "plain_text", "text": "Dark"},
                        "value": "dark",
                    }
                ],
                "initial_options": [
                    {
                        "text": {"type": "plain_text", "text": "Dark"},
                        "value": "dark",
                    }
                ],
            },
        },
    ]


def test_active_row_has_fixed_key_single_line_description_and_remove(editor_state):
    blocks = _blocks_by_id(
        build_practice_reaction_blocks(
            editor_state,
            CATALOG,
            allow_restore=True,
        )
    )

    assert blocks["practice_reaction_key_r0"]["text"]["text"] == (
        "*:evergreen_tree:*"
    )
    field = blocks["practice_reaction_row_r0"]
    assert field["optional"] is True
    assert field["label"]["text"] == "Description for :evergreen_tree:"
    assert field["element"] == {
        "type": "plain_text_input",
        "action_id": DESCRIPTION_ACTION_ID,
        "max_length": 80,
        "initial_value": "Endurance instead of intervals",
    }
    assert blocks["practice_reaction_controls_r0"]["elements"][0] == {
        "type": "button",
        "action_id": REMOVE_ACTION_ID,
        "value": "r0",
        "text": {"type": "plain_text", "text": "Remove"},
        "accessibility_label": "Remove reaction :evergreen_tree:",
    }


def test_removed_row_is_static_escaped_labelled_and_undoable(editor_state):
    editor_state.rows[0].label = "Use <short> & steady"
    removed = remove_plan_reaction(editor_state, "r0")
    blocks = _blocks_by_id(
        build_practice_reaction_blocks(removed, CATALOG, allow_restore=True)
    )

    block = blocks["practice_reaction_removed_r0"]
    assert block["text"]["text"] == (
        "*:evergreen_tree:*\nUse &lt;short&gt; &amp; steady\n_Removed_"
    )
    assert block["accessory"]["action_id"] == UNDO_ACTION_ID
    assert block["accessory"]["value"] == "r0"
    assert "practice_reaction_row_r0" not in blocks


def test_add_filters_every_reserved_emoji_and_restore_is_full_edit_only(empty_state):
    empty_state.add_open = True
    blocks = build_practice_reaction_blocks(
        empty_state,
        CATALOG,
        allow_restore=False,
    )
    picker = _blocks_by_id(blocks)["practice_reaction_catalog_block"][
        "elements"
    ][0]
    assert picker["action_id"] == CATALOG_ACTION_ID
    assert [option["value"] for option in picker["options"]] == [
        "evergreen-option",
        "shoe-option",
    ]
    assert RESTORE_ACTION_ID not in _action_ids(blocks)

    used = copy.deepcopy(empty_state)
    used.rows = [
        PlanReactionEditorRow(
            row_id="r0",
            emoji="evergreen_tree",
            label="Removed still reserves this key",
            removed=True,
            catalog_order=0,
        )
    ]
    filtered = _blocks_by_id(
        build_practice_reaction_blocks(used, CATALOG, allow_restore=False)
    )["practice_reaction_catalog_block"]["elements"][0]
    assert [option["value"] for option in filtered["options"]] == [
        "shoe-option"
    ]


def test_closed_add_and_restore_render_as_bounded_buttons(empty_state):
    blocks = build_practice_reaction_blocks(
        empty_state,
        CATALOG,
        allow_restore=True,
    )

    assert ADD_ACTION_ID in _action_ids(blocks)
    assert RESTORE_ACTION_ID in _action_ids(blocks)
    for block in blocks:
        for element in block.get("elements", []):
            if element.get("type") == "button":
                assert len(element["accessibility_label"]) <= 75


def test_add_is_hidden_when_defaults_fill_slots_without_unconfigured_sources(
    editor_state,
):
    blocks = build_practice_reaction_blocks(
        editor_state,
        CATALOG,
        allow_restore=False,
    )

    assert ADD_ACTION_ID not in _action_ids(blocks)
    assert CATALOG_ACTION_ID not in _action_ids(blocks)


def test_empty_catalog_has_guidance_and_never_emits_empty_static_select(empty_state):
    empty_state.add_open = True
    blocks = _blocks_by_id(
        build_practice_reaction_blocks(
            empty_state,
            (),
            allow_restore=False,
        )
    )

    assert "practice_reaction_catalog_block" not in blocks
    assert any(
        block.get("text", {}).get("text")
        == "Configure reaction pairs in Practices Settings first."
        for block in blocks.values()
    )


def test_catalog_over_100_is_explicit_configuration_error(empty_state):
    empty_state.add_open = True
    catalog = tuple(
        PlanReactionCatalogOption(
            str(index),
            f"choice_{index}",
            f"Choice {index}",
            (f"type:{index + 1}",),
        )
        for index in range(101)
    )
    blocks = _blocks_by_id(
        build_practice_reaction_blocks(
            empty_state,
            catalog,
            allow_restore=False,
        )
    )

    assert "more than 100" in blocks["practice_reaction_catalog_error"][
        "text"
    ]["text"]
    assert "practice_reaction_catalog_block" not in blocks


def test_no_rows_has_exact_empty_state_and_bounded_action_labels(empty_state):
    blocks = _blocks_by_id(
        build_practice_reaction_blocks(
            empty_state,
            CATALOG,
            allow_restore=False,
        )
    )
    assert blocks["practice_reaction_empty"]["text"]["text"] == (
        "No Plan reactions are set for this practice."
    )

    long_key_state = copy.deepcopy(empty_state)
    long_key_state.rows = [
        PlanReactionEditorRow(
            row_id="r0",
            emoji="x" * 80,
            label="choice",
            catalog_order=0,
        )
    ]
    rendered = _blocks_by_id(
        build_practice_reaction_blocks(
            long_key_state,
            CATALOG,
            allow_restore=False,
        )
    )
    button = rendered["practice_reaction_controls_r0"]["elements"][0]
    assert len(button["accessibility_label"]) == 75
    assert button["accessibility_label"].endswith("…")


def test_picker_ellipsizes_display_only_and_full_label_survives_selection(
    empty_state,
):
    label = "L" * 80
    option = PlanReactionCatalogOption(
        "opaque",
        "long",
        label,
        ("type:1",),
    )
    empty_state.add_open = True
    picker = _blocks_by_id(
        build_practice_reaction_blocks(
            empty_state,
            (option,),
            allow_restore=False,
        )
    )["practice_reaction_catalog_block"]["elements"][0]
    rendered = picker["options"][0]

    assert len(rendered["text"]["text"]) == 75
    assert rendered["text"]["text"].endswith("…")
    assert rendered["value"] == "opaque"
    assert add_catalog_plan_reaction(empty_state, option).rows[0].label == label


def test_unconfigured_context_and_blocking_error_escape_mrkdwn(empty_state):
    empty_state.unconfigured_activity_names = ("Strength <indoor>", "Bike & Run")
    empty_state.blocking_error = "Settings <failed> & need attention"
    blocks = build_practice_reaction_blocks(
        empty_state,
        CATALOG,
        allow_restore=False,
    )

    rendered_text = "\n".join(
        block.get("text", {}).get("text", "") for block in blocks
    )
    context_text = "\n".join(
        element.get("text", "")
        for block in blocks
        for element in block.get("elements", [])
    )
    assert "Settings &lt;failed&gt; &amp; need attention" in rendered_text
    assert "Strength &lt;indoor&gt;" in context_text
    assert "Bike &amp; Run" in context_text
    assert ADD_ACTION_ID not in _action_ids(blocks)


def test_metadata_round_trip_is_versioned_bounded_and_preview_has_no_target(
    editor_state,
):
    encoded = encode_practice_reaction_metadata(
        mode="preview",
        context={"preview": True},
        state=editor_state,
        preview_config=PREVIEW_CONFIG,
    )

    assert len(encoded) <= 3000
    mode, context, decoded, preview = decode_practice_reaction_metadata(encoded)
    assert mode == "preview"
    assert context == {"preview": True}
    assert decoded.rows[0].emoji == "evergreen_tree"
    assert preview == PREVIEW_CONFIG
    assert "practice_id" not in encoded


def test_metadata_rejects_unknown_version_and_oversize(editor_state):
    with pytest.raises(PlanReactionValidationError, match="metadata version"):
        decode_practice_reaction_metadata(
            '{"v":99,"m":"preview","c":{},"s":{}}'
        )
    with pytest.raises(PlanReactionValidationError, match="3,000"):
        encode_practice_reaction_metadata(
            mode="preview",
            context={"preview": True},
            state=editor_state,
            preview_config={"padding": "x" * 3000},
        )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.update({"extra": True}),
        lambda payload: payload.update({"m": "delete"}),
        lambda payload: payload.update({"m": []}),
        lambda payload: payload.update({"v": True}),
        lambda payload: payload.update({"c": {"preview": 1}}),
        lambda payload: payload.update({"c": {"preview": True, "practice_id": 8}}),
        lambda payload: payload["p"].update({"database_id": 8}),
        lambda payload: payload["p"]["slot_defaults"].update(
            {"workout": float("nan")}
        ),
        lambda payload: payload["s"].update({"next_row_number": -1}),
    ],
)
def test_metadata_decode_rejects_hostile_envelopes(editor_state, mutate):
    encoded = encode_practice_reaction_metadata(
        mode="preview",
        context={"preview": True},
        state=editor_state,
        preview_config=PREVIEW_CONFIG,
    )
    payload = json.loads(encoded)
    mutate(payload)

    with pytest.raises(PlanReactionValidationError):
        decode_practice_reaction_metadata(
            json.dumps(payload, separators=(",", ":"))
        )


def test_metadata_rejects_preview_database_target_during_encode(editor_state):
    preview_config = copy.deepcopy(PREVIEW_CONFIG)
    preview_config["activities"][0]["practice_id"] = 99

    with pytest.raises(PlanReactionValidationError, match="Preview"):
        encode_practice_reaction_metadata(
            mode="preview",
            context={"preview": True},
            state=editor_state,
            preview_config=preview_config,
        )


def test_merge_keeps_temporary_blank_and_removed_description_from_metadata(
    editor_state,
):
    values = {
        "practice_reaction_row_r0": {
            DESCRIPTION_ACTION_ID: {
                "type": "plain_text_input",
                "value": "",
            }
        }
    }
    merged = merge_practice_reaction_inputs(editor_state, values)
    assert merged.rows[0].label == ""

    removed = remove_plan_reaction(merged, "r0")
    hostile_removed_value = {
        "practice_reaction_row_r0": {
            DESCRIPTION_ACTION_ID: {"value": "UNTRUSTED REMOVED TEXT"}
        }
    }
    still_removed = merge_practice_reaction_inputs(
        removed,
        hostile_removed_value,
    )
    encoded = encode_practice_reaction_metadata(
        mode="create",
        context={"date": "2026-07-14", "channel_id": None, "message_ts": None},
        state=still_removed,
    )
    assert decode_practice_reaction_metadata(encoded)[2].rows[0].label == ""


def test_current_values_replace_defaults_using_only_canonical_option_values(
    create_blocks,
):
    values = {
        "workout_block": {
            "workout_description": {"value": "Edited workout"}
        },
        "time_block": {"practice_time": {"selected_time": "19:30"}},
        "activities_block": {
            "activity_ids": {
                "selected_options": [
                    {"value": "2", "text": {"text": "UNTRUSTED"}},
                    {"value": "999", "text": {"text": "INJECTED"}},
                ]
            }
        },
        "flags_block": {"practice_flags": {"selected_options": []}},
    }
    apply_current_view_values(create_blocks, values)
    blocks = _blocks_by_id(create_blocks)

    assert blocks["workout_block"]["element"]["initial_value"] == (
        "Edited workout"
    )
    assert blocks["time_block"]["element"]["initial_time"] == "19:30"
    assert blocks["activities_block"]["element"]["initial_options"] == [
        blocks["activities_block"]["element"]["options"][1]
    ]
    assert "UNTRUSTED" not in json.dumps(create_blocks)
    assert "INJECTED" not in json.dumps(create_blocks)
    assert "initial_options" not in blocks["flags_block"]["element"]


def test_current_blank_text_and_time_remove_initial_values(create_blocks):
    apply_current_view_values(
        create_blocks,
        {
            "workout_block": {"workout_description": {"value": ""}},
            "time_block": {"practice_time": {"selected_time": None}},
        },
    )
    blocks = _blocks_by_id(create_blocks)

    assert "initial_value" not in blocks["workout_block"]["element"]
    assert "initial_time" not in blocks["time_block"]["element"]


def test_submission_errors_attach_to_exact_description_blocks(editor_state):
    second = copy.deepcopy(editor_state.rows[0])
    second.row_id = "r1"
    second.emoji = "athletic_shoe"
    second.label = "runner"
    second.inherited_order = None
    second.inherited_source_keys = ()
    second.catalog_order = 0
    editor_state.rows.append(second)
    editor_state.next_row_number = 2
    values = {
        "practice_reaction_row_r0": {
            DESCRIPTION_ACTION_ID: {"value": ""}
        },
        "practice_reaction_row_r1": {
            DESCRIPTION_ACTION_ID: {"value": "x" * 81}
        },
    }

    rows, errors = parse_practice_reaction_submission(editor_state, values)

    assert rows is None
    assert errors == {
        "practice_reaction_row_r0": (
            "Enter a description for :evergreen_tree:."
        ),
        "practice_reaction_row_r1": (
            "Description for :athletic_shoe: must be 80 characters or fewer."
        ),
    }


def test_submission_normalizes_active_rows_and_ignores_removed_rows(editor_state):
    editor_state.rows[0].label = "metadata label"
    values = {
        "practice_reaction_row_r0": {
            DESCRIPTION_ACTION_ID: {"value": "  Updated endurance choice  "}
        }
    }
    rows, errors = parse_practice_reaction_submission(editor_state, values)
    assert errors == {}
    assert rows == [
        {
            "emoji": "evergreen_tree",
            "label": "Updated endurance choice",
        }
    ]

    removed = remove_plan_reaction(editor_state, "r0")
    assert parse_practice_reaction_submission(removed, values) == ([], {})


def test_retryable_lookup_error_view_keeps_values_and_only_writable_keys(
    create_blocks,
):
    current_view = {
        "type": "modal",
        "callback_id": "practice_create",
        "private_metadata": "metadata",
        "title": {"type": "plain_text", "text": "Create"},
        "submit": {"type": "plain_text", "text": "Save"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "notify_on_close": True,
        "blocks": create_blocks,
        "id": "V123",
        "hash": "HASH",
        "state": {"values": {}},
        "team_id": "T123",
        "created": 123,
    }
    values = {
        "workout_block": {
            "workout_description": {"value": "Unsaved workout"}
        }
    }
    rebuilt = build_retryable_practice_reaction_error_view(
        current_view,
        values,
        "Could not load <reaction> Settings & Try again.",
    )
    blocks = _blocks_by_id(rebuilt["blocks"])

    assert blocks["workout_block"]["element"]["initial_value"] == (
        "Unsaved workout"
    )
    assert blocks["practice_reaction_lookup_error"]["text"]["text"] == (
        "Could not load &lt;reaction&gt; Settings &amp; Try again."
    )
    assert set(rebuilt) == {
        "type",
        "callback_id",
        "private_metadata",
        "title",
        "submit",
        "close",
        "notify_on_close",
        "blocks",
    }
    assert rebuilt["blocks"] is not current_view["blocks"]
