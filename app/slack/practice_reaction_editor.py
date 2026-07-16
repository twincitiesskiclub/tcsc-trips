"""Block Kit adapter for structured practice-plan reaction editing."""

from __future__ import annotations

import copy
import json
import math
import re
from collections.abc import Mapping
from datetime import date

from app.practices.plan_reaction_editor import (
    PlanReactionEditorState,
    active_plan_reaction_snapshot,
    deserialize_plan_reaction_editor_state,
    reserved_plan_reaction_slots,
    serialize_plan_reaction_editor_state,
)
from app.practices.plan_reactions import (
    MAX_PLAN_REACTION_LABEL,
    MAX_PLAN_REACTIONS,
    PlanReactionValidationError,
    normalize_plan_reactions,
)


PRACTICE_REACTION_METADATA_VERSION = 1
SLACK_PRIVATE_METADATA_MAX_CHARS = 3000
SLACK_STATIC_SELECT_MAX_OPTIONS = 100
SLACK_REACTION_CATALOG_MAX_OPTIONS = SLACK_STATIC_SELECT_MAX_OPTIONS
SLACK_OPTION_TEXT_MAX_CHARS = 75
SLACK_OPTION_VALUE_MAX_CHARS = 150
SLACK_TEXT_OBJECT_MAX_CHARS = 3000
SLACK_BLOCK_ID_MAX_CHARS = 255
PREVIEW_WORKOUT_MAX_CHARS = 2500
_METADATA_MAX_DEPTH = 32

DESCRIPTION_ACTION_ID = "practice_reaction_description"
REMOVE_ACTION_ID = "practice_reaction_remove"
UNDO_ACTION_ID = "practice_reaction_undo"
ADD_ACTION_ID = "practice_reaction_add"
EDIT_ACTION_ID = "practice_reaction_edit"
CATALOG_ACTION_ID = "practice_reaction_catalog_select"
RESTORE_ACTION_ID = "practice_reaction_restore"

_METADATA_MODES = frozenset({"create", "edit", "preview"})
_WRITABLE_VIEW_KEYS = (
    "type",
    "callback_id",
    "private_metadata",
    "title",
    "submit",
    "close",
    "notify_on_close",
    "blocks",
)
_LINE_BREAK_RE = re.compile(r"[\n\r\v\f\x1c-\x1e\x85\u2028\u2029]")
_TIME_RE = re.compile(r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
_PREVIEW_CONFIG_KEYS = {
    "practice_date",
    "default_time",
    "locations",
    "practice_types",
    "activities",
    "slot_defaults",
    "eligible_coaches",
    "eligible_leads",
}
_PREVIEW_DATABASE_TARGET_KEYS = {
    "database_id",
    "database_url",
    "db_id",
    "model_id",
    "practice_id",
    "record_id",
    "table_id",
    "target_id",
}
_PREVIEW_SLOT_DEFAULT_KEYS = {
    "location_id",
    "workout",
    "activity_ids",
    "type_ids",
    "coach_ids",
    "lead_ids",
    "is_dark_practice",
}
_ROW_BLOCK_ID_PREFIXES = (
    "practice_reaction_key_",
    "practice_reaction_row_",
    "practice_reaction_controls_",
    "practice_reaction_removed_",
)


def _mrkdwn_escape(value: object) -> str:
    return (
        str(value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _ellipsize(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[: limit - 1]}…"


def _button(
    *,
    action_id: str,
    text: str,
    accessibility_label: str,
    value: str | None = None,
) -> dict:
    result = {
        "type": "button",
        "action_id": action_id,
        "text": {"type": "plain_text", "text": text},
        "accessibility_label": _ellipsize(
            accessibility_label,
            SLACK_OPTION_TEXT_MAX_CHARS,
        ),
    }
    if value is not None:
        result["value"] = value
    return result


def _distinct_catalog(catalog) -> tuple:
    result = []
    seen = set()
    for option in catalog or ():
        key = (option.emoji, option.label)
        if key in seen:
            continue
        seen.add(key)
        result.append(option)
    return tuple(result)


def _practice_reaction_status_blocks(
    state: PlanReactionEditorState,
) -> list[dict]:
    blocks = []
    if state.unconfigured_activity_names:
        names = ", ".join(state.unconfigured_activity_names)
        message = _mrkdwn_escape(
            "No reaction pairs are configured for selected "
            f"Activities: {names}."
        )
        blocks.append(
            {
                "type": "context",
                "block_id": "practice_reaction_unconfigured",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": _ellipsize(
                            message,
                            SLACK_TEXT_OBJECT_MAX_CHARS,
                        ),
                    }
                ],
            }
        )
    if state.blocking_error:
        blocks.append(
            {
                "type": "section",
                "block_id": "practice_reaction_error",
                "text": {
                    "type": "mrkdwn",
                    "text": _ellipsize(
                        _mrkdwn_escape(state.blocking_error),
                        SLACK_TEXT_OBJECT_MAX_CHARS,
                    ),
                },
            }
        )
    return blocks


def _build_collapsed_practice_reaction_blocks(
    state: PlanReactionEditorState,
) -> list[dict]:
    active = [row for row in state.rows if not row.removed]
    lines = ["*Plan reactions*"]
    if active:
        lines.extend(
            f":{row.emoji}: {_mrkdwn_escape(row.label)}"
            for row in active
        )
        button_text = "Edit reactions"
    else:
        lines.append("No Plan reactions")
        button_text = "Add reactions"
    blocks = [
        {
            "type": "section",
            "block_id": "practice_reaction_summary",
            "text": {
                "type": "mrkdwn",
                "text": _ellipsize(
                    "\n".join(lines),
                    SLACK_TEXT_OBJECT_MAX_CHARS,
                ),
            },
            "accessory": _button(
                action_id=EDIT_ACTION_ID,
                text=button_text,
                accessibility_label=button_text,
            ),
        }
    ]
    blocks.extend(_practice_reaction_status_blocks(state))
    return blocks


def build_practice_reaction_blocks(
    state: PlanReactionEditorState,
    catalog,
    *,
    allow_restore: bool,
) -> list[dict]:
    """Render validated reaction working state as bounded Block Kit blocks."""

    _validate_slack_row_block_ids(state)
    if not state.editor_expanded:
        return _build_collapsed_practice_reaction_blocks(state)

    blocks = []
    for row in state.rows:
        shortcode = f":{row.emoji}:"
        if row.removed:
            text = f"*{shortcode}*"
            if row.label:
                text = f"{text}\n{_mrkdwn_escape(row.label)}"
            text = f"{text}\n_Removed_"
            text = _ellipsize(text, SLACK_TEXT_OBJECT_MAX_CHARS)
            blocks.append(
                {
                    "type": "section",
                    "block_id": f"practice_reaction_removed_{row.row_id}",
                    "text": {"type": "mrkdwn", "text": text},
                    "accessory": _button(
                        action_id=UNDO_ACTION_ID,
                        text="Undo",
                        value=row.row_id,
                        accessibility_label=(
                            f"Undo removal of reaction {shortcode}"
                        ),
                    ),
                }
            )
            continue

        blocks.extend(
            [
                {
                    "type": "section",
                    "block_id": f"practice_reaction_key_{row.row_id}",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{shortcode}*",
                    },
                },
                {
                    "type": "input",
                    "block_id": f"practice_reaction_row_{row.row_id}",
                    "optional": True,
                    "label": {
                        "type": "plain_text",
                        "text": f"Description for {shortcode}",
                    },
                    "element": {
                        "type": "plain_text_input",
                        "action_id": DESCRIPTION_ACTION_ID,
                        "max_length": MAX_PLAN_REACTION_LABEL,
                        **(
                            {"initial_value": row.label}
                            if row.label
                            else {}
                        ),
                    },
                },
                {
                    "type": "actions",
                    "block_id": f"practice_reaction_controls_{row.row_id}",
                    "elements": [
                        _button(
                            action_id=REMOVE_ACTION_ID,
                            text="Remove",
                            value=row.row_id,
                            accessibility_label=(
                                f"Remove reaction {shortcode}"
                            ),
                        )
                    ],
                },
            ]
        )

    if not state.rows:
        blocks.append(
            {
                "type": "section",
                "block_id": "practice_reaction_empty",
                "text": {
                    "type": "mrkdwn",
                    "text": "No Plan reactions are set for this practice.",
                },
            }
        )

    blocks.extend(_practice_reaction_status_blocks(state))

    add_allowed = (
        (
            state.effective_inherited_count == 0
            or bool(state.unconfigured_activity_names)
        )
        and not state.blocking_error
        and reserved_plan_reaction_slots(state) < MAX_PLAN_REACTIONS
    )
    catalog = _distinct_catalog(catalog)
    footer_buttons = []
    if add_allowed:
        if not catalog:
            blocks.append(
                {
                    "type": "section",
                    "block_id": "practice_reaction_catalog_guidance",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            "Configure reaction pairs in Practices Settings "
                            "first."
                        ),
                    },
                }
            )
        elif len(catalog) > SLACK_REACTION_CATALOG_MAX_OPTIONS:
            blocks.append(
                {
                    "type": "section",
                    "block_id": "practice_reaction_catalog_error",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            "Reaction Settings contain more than 100 catalog "
                            "pairs. Reduce the configured pairs before adding "
                            "a reaction."
                        ),
                    },
                }
            )
        elif state.add_open:
            used_emojis = {row.emoji for row in state.rows}
            available = [
                option
                for option in catalog
                if option.emoji not in used_emojis
            ]
            if available:
                blocks.append(
                    {
                        "type": "actions",
                        "block_id": "practice_reaction_catalog_block",
                        "elements": [
                            {
                                "type": "static_select",
                                "action_id": CATALOG_ACTION_ID,
                                "placeholder": {
                                    "type": "plain_text",
                                    "text": "Choose a configured reaction",
                                },
                                "options": [
                                    {
                                        "text": {
                                            "type": "plain_text",
                                            "text": _ellipsize(
                                                f":{option.emoji}: "
                                                f"{option.label}",
                                                SLACK_OPTION_TEXT_MAX_CHARS,
                                            ),
                                        },
                                        "value": option.option_id,
                                    }
                                    for option in available
                                ],
                            }
                        ],
                    }
                )
            else:
                blocks.append(
                    {
                        "type": "section",
                        "block_id": "practice_reaction_catalog_exhausted",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                "No additional configured reaction pairs are "
                                "available."
                            ),
                        },
                    }
                )
        else:
            footer_buttons.append(
                _button(
                    action_id=ADD_ACTION_ID,
                    text="Add reaction",
                    accessibility_label="Add Plan reaction",
                )
            )

    if allow_restore:
        footer_buttons.append(
            _button(
                action_id=RESTORE_ACTION_ID,
                text="Restore defaults",
                accessibility_label="Restore default Plan reactions",
            )
        )
    if footer_buttons:
        blocks.append(
            {
                "type": "actions",
                "block_id": "practice_reaction_actions",
                "elements": footer_buttons,
            }
        )
    return blocks


def _metadata_error(message: str = "Invalid practice reaction metadata"):
    return PlanReactionValidationError(message)


def _validate_slack_row_block_ids(state: PlanReactionEditorState) -> None:
    row_ids = [row.row_id for row in state.rows]
    try:
        row_ids.append(f"r{state.next_row_number}")
    except (TypeError, ValueError, RecursionError):
        raise _metadata_error() from None
    for row_id in row_ids:
        if not isinstance(row_id, str):
            raise _metadata_error()
        if any(
            len(prefix) + len(row_id) > SLACK_BLOCK_ID_MAX_CHARS
            for prefix in _ROW_BLOCK_ID_PREFIXES
        ):
            raise _metadata_error()


def _validate_json_tree(value) -> None:
    pending = [(value, 0)]
    while pending:
        item, depth = pending.pop()
        if depth > _METADATA_MAX_DEPTH:
            raise _metadata_error()
        if item is None or isinstance(item, (str, int, bool)):
            continue
        if isinstance(item, float):
            if not math.isfinite(item):
                raise _metadata_error()
            continue
        if isinstance(item, list):
            pending.extend((child, depth + 1) for child in item)
            continue
        if isinstance(item, Mapping):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise _metadata_error()
                pending.append((child, depth + 1))
            continue
        raise _metadata_error()


def _contains_preview_database_target(value) -> bool:
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, Mapping):
            for key, child in item.items():
                normalized = key.strip().lower().replace("-", "_")
                if normalized in _PREVIEW_DATABASE_TARGET_KEYS:
                    return True
                pending.append(child)
        elif isinstance(item, list):
            pending.extend(item)
    return False


def _require_positive_int(value) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise _metadata_error("Invalid Preview reaction configuration")
    return value


def _require_preview_option_id(value) -> int:
    result = _require_positive_int(value)
    if len(str(result)) > SLACK_OPTION_VALUE_MAX_CHARS:
        raise _metadata_error("Invalid Preview reaction configuration")
    return result


def _validate_preview_option_name(value) -> None:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > SLACK_OPTION_TEXT_MAX_CHARS
    ):
        raise _metadata_error("Invalid Preview reaction configuration")


def _validate_preview_sources(value, *, kind: str) -> set[int]:
    if (
        not isinstance(value, list)
        or len(value) > SLACK_STATIC_SELECT_MAX_OPTIONS
    ):
        raise _metadata_error("Invalid Preview reaction configuration")
    ids = set()
    for source in value:
        if not isinstance(source, Mapping) or set(source) != {
            "id",
            "name",
            "default_plan_reactions",
        }:
            raise _metadata_error("Invalid Preview reaction configuration")
        source_id = _require_preview_option_id(source["id"])
        if source_id in ids:
            raise _metadata_error("Invalid Preview reaction configuration")
        ids.add(source_id)
        _validate_preview_option_name(source["name"])
        pairs = source["default_plan_reactions"]
        try:
            normalized = normalize_plan_reactions(
                pairs,
                source=f"Preview {kind} {source['name']}",
            )
        except PlanReactionValidationError:
            raise _metadata_error(
                "Invalid Preview reaction configuration"
            ) from None
        if normalized != pairs:
            raise _metadata_error("Invalid Preview reaction configuration")
    return ids


def _validate_preview_people(value) -> set[int]:
    if (
        not isinstance(value, list)
        or len(value) > SLACK_STATIC_SELECT_MAX_OPTIONS
    ):
        raise _metadata_error("Invalid Preview reaction configuration")
    ids = set()
    for person in value:
        if not isinstance(person, Mapping) or set(person) != {
            "user_id",
            "name",
            "slack_uid",
        }:
            raise _metadata_error("Invalid Preview reaction configuration")
        user_id = _require_preview_option_id(person["user_id"])
        if user_id in ids:
            raise _metadata_error("Invalid Preview reaction configuration")
        ids.add(user_id)
        _validate_preview_option_name(person["name"])
        if (
            not isinstance(person["slack_uid"], str)
            or not person["slack_uid"].strip()
            or len(person["slack_uid"]) > SLACK_OPTION_VALUE_MAX_CHARS
        ):
            raise _metadata_error("Invalid Preview reaction configuration")
    return ids


def _validate_id_selection(value, *, allowed: set[int]) -> None:
    if not isinstance(value, list):
        raise _metadata_error("Invalid Preview reaction configuration")
    selected = []
    for item in value:
        selected.append(_require_preview_option_id(item))
    if len(selected) != len(set(selected)) or not set(selected) <= allowed:
        raise _metadata_error("Invalid Preview reaction configuration")


def _validate_preview_config(config) -> None:
    if not isinstance(config, Mapping) or set(config) != _PREVIEW_CONFIG_KEYS:
        raise _metadata_error("Invalid Preview reaction configuration")
    _validate_json_tree(config)
    if _contains_preview_database_target(config):
        raise _metadata_error("Preview metadata cannot contain a database target")
    try:
        date.fromisoformat(config["practice_date"])
    except (TypeError, ValueError):
        raise _metadata_error("Invalid Preview reaction configuration") from None
    if (
        not isinstance(config["default_time"], str)
        or not _TIME_RE.fullmatch(config["default_time"])
    ):
        raise _metadata_error("Invalid Preview reaction configuration")

    locations = config["locations"]
    if (
        not isinstance(locations, list)
        or len(locations) > SLACK_STATIC_SELECT_MAX_OPTIONS
    ):
        raise _metadata_error("Invalid Preview reaction configuration")
    location_ids = set()
    for location in locations:
        if not isinstance(location, Mapping) or set(location) != {"id", "name"}:
            raise _metadata_error("Invalid Preview reaction configuration")
        location_id = _require_preview_option_id(location["id"])
        if location_id in location_ids:
            raise _metadata_error("Invalid Preview reaction configuration")
        location_ids.add(location_id)
        _validate_preview_option_name(location["name"])

    type_ids = _validate_preview_sources(
        config["practice_types"],
        kind="Workout Type",
    )
    activity_ids = _validate_preview_sources(
        config["activities"],
        kind="Activity",
    )
    coach_ids = _validate_preview_people(config["eligible_coaches"])
    lead_ids = _validate_preview_people(config["eligible_leads"])

    defaults = config["slot_defaults"]
    if (
        not isinstance(defaults, Mapping)
        or not set(defaults) <= _PREVIEW_SLOT_DEFAULT_KEYS
    ):
        raise _metadata_error("Invalid Preview reaction configuration")
    if "location_id" in defaults:
        if (
            _require_preview_option_id(defaults["location_id"])
            not in location_ids
        ):
            raise _metadata_error("Invalid Preview reaction configuration")
    if "workout" in defaults and (
        not isinstance(defaults["workout"], str)
        or len(defaults["workout"]) > PREVIEW_WORKOUT_MAX_CHARS
    ):
        raise _metadata_error("Invalid Preview reaction configuration")
    for key, allowed in (
        ("activity_ids", activity_ids),
        ("type_ids", type_ids),
        ("coach_ids", coach_ids),
        ("lead_ids", lead_ids),
    ):
        if key in defaults:
            _validate_id_selection(defaults[key], allowed=allowed)
    if "is_dark_practice" in defaults and not isinstance(
        defaults["is_dark_practice"],
        bool,
    ):
        raise _metadata_error("Invalid Preview reaction configuration")


def _validate_context(mode: str, context) -> None:
    if not isinstance(context, Mapping):
        raise _metadata_error()
    _validate_json_tree(context)
    if mode == "preview":
        if set(context) != {"preview"} or context["preview"] is not True:
            raise _metadata_error(
                "Preview reaction metadata requires an isolated Preview context"
            )
        return
    if mode == "edit":
        if set(context) != {"practice_id"}:
            raise _metadata_error()
        _require_positive_int(context["practice_id"])
        return

    required = {"date", "channel_id", "message_ts"}
    if not required <= set(context) or not set(context) <= required | {"silent"}:
        raise _metadata_error()
    try:
        date.fromisoformat(context["date"])
    except (TypeError, ValueError):
        raise _metadata_error() from None
    for key in ("channel_id", "message_ts"):
        if context[key] is not None and not isinstance(context[key], str):
            raise _metadata_error()
    if "silent" in context and not isinstance(context["silent"], Mapping):
        raise _metadata_error()


def _validate_mode(mode) -> str:
    if not isinstance(mode, str) or mode not in _METADATA_MODES:
        raise _metadata_error("Invalid practice reaction metadata mode")
    return mode


def _validated_serialized_state(state: PlanReactionEditorState) -> dict:
    if not state.editor_expanded:
        raw_active = [
            {"emoji": row.emoji, "label": row.label}
            for row in state.rows
            if not row.removed
        ]
        if active_plan_reaction_snapshot(state) != raw_active:
            raise _metadata_error()
    payload = serialize_plan_reaction_editor_state(
        state,
        omit_active_labels=state.editor_expanded,
    )
    deserialize_plan_reaction_editor_state(payload)
    return payload


def encode_practice_reaction_metadata(
    *,
    mode: str,
    context: Mapping,
    state: PlanReactionEditorState,
    preview_config=None,
) -> str:
    """Encode compact, versioned, bounded Slack private metadata."""

    _validate_mode(mode)
    _validate_context(mode, context)
    if mode != "preview" and preview_config is not None:
        raise _metadata_error()
    if mode == "preview" and preview_config is None:
        raise _metadata_error("Preview reaction metadata requires Preview configuration")
    if preview_config is not None:
        _validate_json_tree(preview_config)

    _validate_slack_row_block_ids(state)
    serialized_state = _validated_serialized_state(state)
    try:
        envelope = {
            "v": PRACTICE_REACTION_METADATA_VERSION,
            "m": mode,
            "c": copy.deepcopy(dict(context)),
            "s": serialized_state,
        }
        if preview_config is not None:
            envelope["p"] = copy.deepcopy(preview_config)
        raw = json.dumps(envelope, separators=(",", ":"), ensure_ascii=False)
        raw.encode("utf-8")
    except (TypeError, ValueError, RecursionError):
        raise _metadata_error() from None
    if len(raw) > SLACK_PRIVATE_METADATA_MAX_CHARS:
        raise PlanReactionValidationError(
            "Practice reaction metadata exceeds Slack's 3,000-character limit"
        )
    if mode == "preview":
        _validate_preview_config(preview_config)
    return raw


def _object_without_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise _metadata_error()
        result[key] = value
    return result


def _reject_json_constant(_value):
    raise _metadata_error()


def decode_practice_reaction_metadata(raw: str):
    """Decode and validate untrusted Slack private metadata."""

    if not isinstance(raw, str) or len(raw) > SLACK_PRIVATE_METADATA_MAX_CHARS:
        raise _metadata_error()
    try:
        envelope = json.loads(
            raw,
            object_pairs_hook=_object_without_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except (TypeError, ValueError, RecursionError, json.JSONDecodeError):
        raise _metadata_error() from None
    if not isinstance(envelope, Mapping):
        raise _metadata_error()
    version = envelope.get("v")
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version != PRACTICE_REACTION_METADATA_VERSION
    ):
        raise _metadata_error("Unsupported practice reaction metadata version")
    mode = _validate_mode(envelope.get("m"))
    expected_keys = {"v", "m", "c", "s", "p"} if mode == "preview" else {
        "v",
        "m",
        "c",
        "s",
    }
    if set(envelope) != expected_keys:
        raise _metadata_error()
    context = envelope["c"]
    _validate_context(mode, context)
    preview_config = envelope.get("p")
    if mode == "preview":
        _validate_preview_config(preview_config)
    state = deserialize_plan_reaction_editor_state(envelope["s"])
    _validate_slack_row_block_ids(state)
    if state.editor_expanded:
        if any(
            not row["removed"] and row["label"] is not None
            for row in envelope["s"]["rows"]
        ):
            raise _metadata_error()
    else:
        raw_active = [
            {"emoji": row.emoji, "label": row.label}
            for row in state.rows
            if not row.removed
        ]
        if active_plan_reaction_snapshot(state) != raw_active:
            raise _metadata_error()
    return mode, copy.deepcopy(dict(context)), state, copy.deepcopy(preview_config)


def merge_practice_reaction_inputs(
    state: PlanReactionEditorState,
    values,
) -> PlanReactionEditorState:
    """Merge exact active description inputs without trusting removed fields."""

    working = copy.deepcopy(state)
    if not isinstance(values, Mapping):
        return working
    for row in working.rows:
        if row.removed:
            continue
        block = values.get(f"practice_reaction_row_{row.row_id}")
        if not isinstance(block, Mapping):
            continue
        action = block.get(DESCRIPTION_ACTION_ID)
        if not isinstance(action, Mapping) or "value" not in action:
            continue
        value = action["value"]
        if value is None:
            row.label = ""
        elif isinstance(value, str):
            row.label = value
    return working


def parse_practice_reaction_submission(
    state: PlanReactionEditorState,
    values,
):
    """Return a validated active snapshot or exact Slack Input-block errors."""

    working = merge_practice_reaction_inputs(state, values)
    errors = {}
    for row in working.rows:
        if row.removed:
            continue
        block_id = f"practice_reaction_row_{row.row_id}"
        if not row.label.strip():
            errors[block_id] = f"Enter a description for :{row.emoji}:."
        elif _LINE_BREAK_RE.search(row.label):
            errors[block_id] = (
                f"Description for :{row.emoji}: must be a single line."
            )
        elif len(row.label) > MAX_PLAN_REACTION_LABEL:
            errors[block_id] = (
                f"Description for :{row.emoji}: must be "
                f"{MAX_PLAN_REACTION_LABEL} characters or fewer."
            )
    if errors:
        return None, errors
    try:
        return active_plan_reaction_snapshot(working), {}
    except PlanReactionValidationError as exc:
        active = next((row for row in working.rows if not row.removed), None)
        if active is None:
            return None, {"practice_reaction_error": str(exc)}
        return None, {
            f"practice_reaction_row_{active.row_id}": str(exc)
        }


def _element_options(element) -> dict[str, dict]:
    options = element.get("options")
    if not isinstance(options, list):
        return {}
    return {
        option.get("value"): option
        for option in options
        if isinstance(option, Mapping) and isinstance(option.get("value"), str)
    }


def _apply_element_value(element: dict, action_value: Mapping) -> None:
    element_type = element.get("type")
    if element_type == "plain_text_input":
        value = action_value.get("value")
        if isinstance(value, str) and value:
            element["initial_value"] = value
        else:
            element.pop("initial_value", None)
        return
    if element_type == "timepicker":
        value = action_value.get("selected_time")
        if isinstance(value, str) and _TIME_RE.fullmatch(value):
            element["initial_time"] = value
        else:
            element.pop("initial_time", None)
        return

    canonical = _element_options(element)
    if element_type in {"static_select", "radio_buttons"}:
        selected = action_value.get("selected_option")
        value = selected.get("value") if isinstance(selected, Mapping) else None
        if value in canonical:
            element["initial_option"] = canonical[value]
        else:
            element.pop("initial_option", None)
        return
    if element_type in {"multi_static_select", "checkboxes"}:
        selected = action_value.get("selected_options")
        if not isinstance(selected, list):
            selected = []
        initial = []
        seen = set()
        for submitted in selected:
            value = (
                submitted.get("value")
                if isinstance(submitted, Mapping)
                else None
            )
            if value in canonical and value not in seen:
                initial.append(canonical[value])
                seen.add(value)
        if initial:
            element["initial_options"] = initial
        else:
            element.pop("initial_options", None)


def apply_current_view_values(blocks: list[dict], values) -> list[dict]:
    """Apply current Slack state by block/action ID using canonical options."""

    if not isinstance(values, Mapping):
        return blocks
    for block in blocks:
        block_id = block.get("block_id")
        submitted_block = values.get(block_id)
        if not isinstance(submitted_block, Mapping):
            continue
        elements = []
        if isinstance(block.get("element"), Mapping):
            elements.append(block["element"])
        elements.extend(
            element
            for element in block.get("elements", [])
            if isinstance(element, Mapping)
        )
        if isinstance(block.get("accessory"), Mapping):
            elements.append(block["accessory"])
        for element in elements:
            action_id = element.get("action_id")
            action_value = submitted_block.get(action_id)
            if not isinstance(action_value, Mapping):
                continue
            _apply_element_value(element, action_value)
    return blocks


def build_retryable_practice_reaction_error_view(
    current_view: Mapping,
    current_values,
    message: str,
) -> dict:
    """Rebuild a writable modal view after a transient Settings failure."""

    rebuilt = {
        key: copy.deepcopy(current_view[key])
        for key in _WRITABLE_VIEW_KEYS
        if key in current_view
    }
    blocks = [
        block
        for block in rebuilt.get("blocks", [])
        if block.get("block_id") != "practice_reaction_lookup_error"
    ]
    blocks.insert(
        0,
        {
            "type": "section",
            "block_id": "practice_reaction_lookup_error",
            "text": {
                "type": "mrkdwn",
                "text": _ellipsize(
                    _mrkdwn_escape(message),
                    SLACK_TEXT_OBJECT_MAX_CHARS,
                ),
            },
        },
    )
    rebuilt["blocks"] = blocks
    apply_current_view_values(blocks, current_values)
    return rebuilt


__all__ = [
    "ADD_ACTION_ID",
    "CATALOG_ACTION_ID",
    "DESCRIPTION_ACTION_ID",
    "EDIT_ACTION_ID",
    "PRACTICE_REACTION_METADATA_VERSION",
    "REMOVE_ACTION_ID",
    "RESTORE_ACTION_ID",
    "SLACK_OPTION_TEXT_MAX_CHARS",
    "SLACK_PRIVATE_METADATA_MAX_CHARS",
    "SLACK_REACTION_CATALOG_MAX_OPTIONS",
    "UNDO_ACTION_ID",
    "apply_current_view_values",
    "build_practice_reaction_blocks",
    "build_retryable_practice_reaction_error_view",
    "decode_practice_reaction_metadata",
    "encode_practice_reaction_metadata",
    "merge_practice_reaction_inputs",
    "parse_practice_reaction_submission",
]
