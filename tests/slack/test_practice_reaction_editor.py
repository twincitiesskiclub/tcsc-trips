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
    EDIT_ACTION_ID,
    REMOVE_ACTION_ID,
    RESTORE_ACTION_ID,
    UNDO_ACTION_ID,
    _validate_preview_config,
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

_TEST_METADATA_MAX_DEPTH = 32
_PREVIEW_OPTION_COLLECTIONS = (
    "locations",
    "practice_types",
    "activities",
    "eligible_coaches",
    "eligible_leads",
)


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


def _nested_list(depth):
    value = "leaf"
    for _ in range(depth):
        value = [value]
    return value


def _preview_option(collection, item_id, *, name="x", slack_uid="U"):
    if collection == "locations":
        return {"id": item_id, "name": name}
    if collection in {"practice_types", "activities"}:
        return {
            "id": item_id,
            "name": name,
            "default_plan_reactions": [],
        }
    return {
        "user_id": item_id,
        "name": name,
        "slack_uid": slack_uid,
    }


def _isolated_preview_config(collection, items):
    config = copy.deepcopy(PREVIEW_CONFIG)
    for key in _PREVIEW_OPTION_COLLECTIONS:
        config[key] = []
    config["slot_defaults"] = {}
    config[collection] = items
    return config


@pytest.fixture
def editor_state():
    intervals = SimpleNamespace(
        id=1,
        name="Intervals",
        default_plan_reactions=[EVERGREEN_PLAN_REACTION],
    )
    state = build_plan_reaction_editor_state(
        practice_types=[intervals],
        activities=[],
        saved_snapshot=None,
    ).state
    state.editor_expanded = True
    return state


@pytest.fixture
def empty_state():
    return PlanReactionEditorState(editor_expanded=True)


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


def test_collapsed_summary_lists_only_active_rows_in_order(editor_state):
    editor_state.editor_expanded = False
    second = PlanReactionEditorRow(
        row_id="r1",
        emoji="athletic_shoe",
        label="runner",
        catalog_order=0,
    )
    removed = PlanReactionEditorRow(
        row_id="r2",
        emoji="hatching_chick",
        label="new rollerskier",
        removed=True,
        catalog_order=1,
    )
    editor_state.rows.extend([second, removed])
    editor_state.next_row_number = 3

    blocks = build_practice_reaction_blocks(
        editor_state,
        CATALOG,
        allow_restore=True,
    )
    summary = _blocks_by_id(blocks)["practice_reaction_summary"]

    assert summary["text"]["text"] == (
        "*Plan reactions*\n"
        ":evergreen_tree: Endurance instead of intervals\n"
        ":athletic_shoe: runner"
    )
    assert summary["accessory"]["action_id"] == EDIT_ACTION_ID
    assert summary["accessory"]["text"]["text"] == "Edit reactions"
    assert not any(
        block.get("block_id", "").startswith("practice_reaction_row_")
        for block in blocks
    )


def test_collapsed_empty_summary_uses_add_reactions(empty_state):
    empty_state.editor_expanded = False
    summary = _blocks_by_id(build_practice_reaction_blocks(
        empty_state,
        CATALOG,
        allow_restore=False,
    ))["practice_reaction_summary"]

    assert summary["text"]["text"] == "*Plan reactions*\nNo Plan reactions"
    assert summary["accessory"]["text"]["text"] == "Add reactions"


def test_collapsed_summary_escapes_labels_and_keeps_status_blocks(editor_state):
    editor_state.editor_expanded = False
    editor_state.rows[0].label = "Use <short> & steady"
    editor_state.unconfigured_activity_names = ("Skate <Rollerski>",)
    editor_state.blocking_error = "Resolve <conflict> & retry"

    blocks = _blocks_by_id(build_practice_reaction_blocks(
        editor_state,
        CATALOG,
        allow_restore=True,
    ))

    assert "Use &lt;short&gt; &amp; steady" in (
        blocks["practice_reaction_summary"]["text"]["text"]
    )
    assert "Skate &lt;Rollerski&gt;" in (
        blocks["practice_reaction_unconfigured"]["elements"][0]["text"]
    )
    assert blocks["practice_reaction_error"]["text"]["text"] == (
        "Resolve &lt;conflict&gt; &amp; retry"
    )


def test_collapsed_metadata_retains_labels_while_expanded_omits_them():
    state = PlanReactionEditorState(
        rows=[PlanReactionEditorRow(
            row_id="r0",
            emoji="hatching_chick",
            label="Ny skiløper 🐣",
            catalog_order=0,
        )],
        next_row_number=1,
        editor_expanded=False,
    )
    context = {
        "date": "2026-07-14",
        "channel_id": None,
        "message_ts": None,
    }

    collapsed_raw = encode_practice_reaction_metadata(
        mode="create",
        context=context,
        state=state,
    )
    assert len(collapsed_raw) <= 3000
    assert decode_practice_reaction_metadata(collapsed_raw)[2].rows[0].label == (
        "Ny skiløper 🐣"
    )
    assert "\\u00f8" not in collapsed_raw

    state.editor_expanded = True
    expanded_raw = encode_practice_reaction_metadata(
        mode="create",
        context=context,
        state=state,
    )
    assert json.loads(expanded_raw)["s"]["rows"][0]["label"] is None


def test_collapsed_metadata_rejects_blank_active_label():
    state = PlanReactionEditorState(
        rows=[PlanReactionEditorRow(
            row_id="r0",
            emoji="athletic_shoe",
            label="",
            catalog_order=0,
        )],
        next_row_number=1,
        editor_expanded=False,
    )

    with pytest.raises(PlanReactionValidationError):
        encode_practice_reaction_metadata(
            mode="create",
            context={
                "date": "2026-07-14",
                "channel_id": None,
                "message_ts": None,
            },
            state=state,
        )


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


def test_dynamic_mrkdwn_is_bounded_after_nine_name_escape_expansion(
    empty_state,
):
    empty_state.unconfigured_activity_names = tuple(
        f"{index}{'&' * 74}" for index in range(9)
    )
    empty_state.blocking_error = "&" * 1000

    blocks = build_practice_reaction_blocks(
        empty_state,
        CATALOG,
        allow_restore=False,
    )
    text_objects = [
        value
        for block in blocks
        for value in (
            block.get("text"),
            *block.get("elements", []),
        )
        if isinstance(value, dict)
        and value.get("type") in {"mrkdwn", "plain_text"}
    ]

    assert all(len(value["text"]) <= 3000 for value in text_objects)
    assert _blocks_by_id(blocks)["practice_reaction_error"]["text"][
        "text"
    ].endswith("…")
    context = _blocks_by_id(blocks)["practice_reaction_unconfigured"]
    assert context["elements"][0]["text"].endswith("…")


def test_decoded_row_ids_respect_exact_slack_block_id_boundary(editor_state):
    longest_prefix = "practice_reaction_controls_"
    max_row_id_chars = 255 - len(longest_prefix)
    row_id = "r" + "1" * (max_row_id_chars - 1)
    encoded = encode_practice_reaction_metadata(
        mode="create",
        context={
            "date": "2026-07-14",
            "channel_id": None,
            "message_ts": None,
        },
        state=editor_state,
    )
    envelope = json.loads(encoded)
    envelope["s"]["rows"][0]["row_id"] = row_id
    envelope["s"]["next_row_number"] = int(row_id[1:]) + 1
    boundary = json.dumps(envelope, separators=(",", ":"))

    decoded = decode_practice_reaction_metadata(boundary)[2]
    blocks = build_practice_reaction_blocks(decoded, CATALOG, allow_restore=False)
    assert max(len(block["block_id"]) for block in blocks) == 255

    one_past_row_id = f"{row_id}1"
    envelope["s"]["rows"][0]["row_id"] = one_past_row_id
    envelope["s"]["next_row_number"] = int(one_past_row_id[1:]) + 1
    one_past = json.dumps(envelope, separators=(",", ":"))
    with pytest.raises(PlanReactionValidationError, match="metadata"):
        decode_practice_reaction_metadata(one_past)

    decoded.rows[0].row_id = one_past_row_id
    with pytest.raises(PlanReactionValidationError, match="metadata"):
        build_practice_reaction_blocks(
            decoded,
            CATALOG,
            allow_restore=False,
        )


def test_prospective_row_id_respects_exact_slack_block_id_boundary(empty_state):
    max_row_id_chars = 255 - len("practice_reaction_controls_")
    empty_state.next_row_number = int("1" * (max_row_id_chars - 1))
    encoded = encode_practice_reaction_metadata(
        mode="create",
        context={
            "date": "2026-07-14",
            "channel_id": None,
            "message_ts": None,
        },
        state=empty_state,
    )
    decoded = decode_practice_reaction_metadata(encoded)[2]
    build_practice_reaction_blocks(decoded, CATALOG, allow_restore=False)

    one_past = copy.deepcopy(empty_state)
    one_past.next_row_number = int("1" * max_row_id_chars)
    with pytest.raises(PlanReactionValidationError, match="metadata"):
        encode_practice_reaction_metadata(
            mode="create",
            context={
                "date": "2026-07-14",
                "channel_id": None,
                "message_ts": None,
            },
            state=one_past,
        )

    envelope = json.loads(encoded)
    envelope["s"]["next_row_number"] = one_past.next_row_number
    hostile = json.dumps(envelope, separators=(",", ":"))
    with pytest.raises(PlanReactionValidationError, match="metadata"):
        decode_practice_reaction_metadata(hostile)
    with pytest.raises(PlanReactionValidationError, match="metadata"):
        build_practice_reaction_blocks(
            one_past,
            CATALOG,
            allow_restore=False,
        )


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


def test_metadata_encode_accepts_depth_boundary_and_rejects_one_past(
    editor_state,
):
    at_boundary = {
        "date": "2026-07-14",
        "channel_id": None,
        "message_ts": None,
        "silent": {
            "nested": _nested_list(_TEST_METADATA_MAX_DEPTH - 2),
        },
    }
    encoded = encode_practice_reaction_metadata(
        mode="create",
        context=at_boundary,
        state=editor_state,
    )
    assert decode_practice_reaction_metadata(encoded)[1] == at_boundary

    one_past = copy.deepcopy(at_boundary)
    one_past["silent"] = {
        "nested": _nested_list(_TEST_METADATA_MAX_DEPTH - 1),
    }
    with pytest.raises(PlanReactionValidationError, match="metadata"):
        encode_practice_reaction_metadata(
            mode="create",
            context=one_past,
            state=editor_state,
        )


def test_metadata_decode_normalizes_size_valid_parser_recursion(editor_state):
    encoded = encode_practice_reaction_metadata(
        mode="create",
        context={
            "date": "2026-07-14",
            "channel_id": None,
            "message_ts": None,
        },
        state=editor_state,
    )
    marker = '"message_ts":null}'
    assert marker in encoded
    nested_json = "[" * 1100 + '"leaf"' + "]" * 1100
    hostile = encoded.replace(
        marker,
        f'"message_ts":null,"silent":{nested_json}}}',
        1,
    )
    assert len(hostile) < 3000

    with pytest.raises(PlanReactionValidationError, match="metadata"):
        decode_practice_reaction_metadata(hostile)


def test_preview_metadata_depth_is_adapter_safe_for_encode_and_decode(
    editor_state,
):
    config = copy.deepcopy(PREVIEW_CONFIG)
    config["slot_defaults"]["nested"] = _nested_list(700)

    with pytest.raises(PlanReactionValidationError, match="metadata"):
        encode_practice_reaction_metadata(
            mode="preview",
            context={"preview": True},
            state=editor_state,
            preview_config=config,
        )

    valid = encode_practice_reaction_metadata(
        mode="preview",
        context={"preview": True},
        state=editor_state,
        preview_config=PREVIEW_CONFIG,
    )
    envelope = json.loads(valid)
    envelope["p"] = config
    hostile = json.dumps(envelope, separators=(",", ":"))
    assert len(hostile) < 3000
    with pytest.raises(PlanReactionValidationError, match="metadata"):
        decode_practice_reaction_metadata(hostile)


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


@pytest.mark.parametrize("collection", _PREVIEW_OPTION_COLLECTIONS)
def test_preview_option_collections_accept_100_and_reject_101(collection):
    items = [
        _preview_option(collection, index + 1)
        for index in range(100)
    ]
    config = _isolated_preview_config(collection, items)

    _validate_preview_config(config)
    config[collection].append(_preview_option(collection, 101))
    with pytest.raises(PlanReactionValidationError, match="Preview"):
        _validate_preview_config(config)


@pytest.mark.parametrize("collection", _PREVIEW_OPTION_COLLECTIONS)
def test_preview_option_names_accept_75_and_reject_76(collection):
    config = _isolated_preview_config(
        collection,
        [_preview_option(collection, 1, name="x" * 75)],
    )

    _validate_preview_config(config)
    config[collection][0]["name"] = "x" * 76
    with pytest.raises(PlanReactionValidationError, match="Preview"):
        _validate_preview_config(config)


@pytest.mark.parametrize("collection", _PREVIEW_OPTION_COLLECTIONS)
def test_preview_option_values_accept_150_and_reject_151(collection):
    boundary_id = int("1" * 150)
    config = _isolated_preview_config(
        collection,
        [_preview_option(collection, boundary_id)],
    )

    _validate_preview_config(config)
    one_past_id = int("1" * 151)
    id_key = "user_id" if collection.startswith("eligible_") else "id"
    config[collection][0][id_key] = one_past_id
    with pytest.raises(PlanReactionValidationError, match="Preview"):
        _validate_preview_config(config)


@pytest.mark.parametrize("collection", ("eligible_coaches", "eligible_leads"))
def test_preview_slack_uids_accept_150_and_reject_151(collection):
    config = _isolated_preview_config(
        collection,
        [_preview_option(collection, 1, slack_uid="U" * 150)],
    )

    _validate_preview_config(config)
    config[collection][0]["slack_uid"] = "U" * 151
    with pytest.raises(PlanReactionValidationError, match="Preview"):
        _validate_preview_config(config)


def _complete_preview_defaults_config():
    config = copy.deepcopy(PREVIEW_CONFIG)
    config["eligible_coaches"] = [
        {"user_id": 2, "name": "Coach", "slack_uid": "U2"}
    ]
    config["eligible_leads"] = [
        {"user_id": 3, "name": "Lead", "slack_uid": "U3"}
    ]
    config["slot_defaults"] = {
        "location_id": 1,
        "workout": "x",
        "activity_ids": [1],
        "type_ids": [1],
        "coach_ids": [2],
        "lead_ids": [3],
        "is_dark_practice": True,
    }
    return config


def test_preview_slot_defaults_accept_complete_schema_and_workout_boundary():
    config = _complete_preview_defaults_config()
    config["slot_defaults"]["workout"] = "x" * 2500

    _validate_preview_config(config)
    config["slot_defaults"]["workout"] = "x" * 2501
    with pytest.raises(PlanReactionValidationError, match="Preview"):
        _validate_preview_config(config)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("unknown", "value"),
        ("location_id", 1.0),
        ("workout", {"nested": "value"}),
        ("workout", 1.0),
        ("activity_ids", 1.0),
        ("type_ids", [1.0]),
        ("coach_ids", "2"),
        ("lead_ids", [True]),
        ("is_dark_practice", 1),
    ],
)
def test_preview_slot_defaults_reject_unknown_keys_and_wrong_types(key, value):
    config = _complete_preview_defaults_config()
    config["slot_defaults"][key] = value

    with pytest.raises(PlanReactionValidationError, match="Preview"):
        _validate_preview_config(config)


@pytest.mark.parametrize("workout", ({"nested": "value"}, 1.0))
def test_preview_metadata_encode_rejects_wrong_type_workout(
    editor_state,
    workout,
):
    config = copy.deepcopy(PREVIEW_CONFIG)
    config["slot_defaults"]["workout"] = workout

    with pytest.raises(PlanReactionValidationError, match="Preview"):
        encode_practice_reaction_metadata(
            mode="preview",
            context={"preview": True},
            state=editor_state,
            preview_config=config,
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
