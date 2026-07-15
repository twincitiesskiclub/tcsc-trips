"""Ephemeral working state for structured practice-plan reaction editors."""

from __future__ import annotations

import copy
import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from app.practices.plan_reactions import (
    MAX_PLAN_REACTION_LABEL,
    MAX_PLAN_REACTIONS,
    PlanReactionCatalogOption,
    PlanReactionResolution,
    PlanReactionValidationError,
    normalize_plan_reactions,
    resolve_plan_reaction_defaults,
)

PLAN_REACTION_EDITOR_VERSION = 1

_EDITOR_METADATA_ERROR = "Invalid reaction editor metadata"
_EDITOR_KEYS = {
    "version",
    "rows",
    "suppressed",
    "last_valid_type_ids",
    "last_valid_activity_ids",
    "next_row_number",
    "blocking_error",
    "unconfigured_activity_names",
    "effective_inherited_count",
    "add_open",
}
_ROW_KEYS = {
    "row_id",
    "emoji",
    "label",
    "removed",
    "inherited_source_keys",
    "inherited_order",
    "protected_order",
    "catalog_order",
}
_SUPPRESSED_KEYS = {"emoji", "source_keys", "inherited_order"}
_ROW_ID_RE = re.compile(r"^r(0|[1-9][0-9]*)$")
_SOURCE_KEY_RE = re.compile(r"^(type|activity):([1-9][0-9]*)$")
_LINE_BREAK_RE = re.compile(r"[\n\r\v\f\x1c-\x1e\x85\u2028\u2029]")


@dataclass
class PlanReactionEditorRow:
    row_id: str
    emoji: str
    label: str
    removed: bool = False
    inherited_source_keys: tuple[str, ...] = ()
    inherited_order: int | None = None
    protected_order: int | None = None
    catalog_order: int | None = None


@dataclass(frozen=True)
class SuppressedPlanReaction:
    emoji: str
    source_keys: tuple[str, ...]
    inherited_order: int


@dataclass
class PlanReactionEditorState:
    version: int = PLAN_REACTION_EDITOR_VERSION
    rows: list[PlanReactionEditorRow] = field(default_factory=list)
    suppressed: list[SuppressedPlanReaction] = field(default_factory=list)
    last_valid_type_ids: tuple[int, ...] = ()
    last_valid_activity_ids: tuple[int, ...] = ()
    next_row_number: int = 0
    blocking_error: str | None = None
    unconfigured_activity_names: tuple[str, ...] = ()
    effective_inherited_count: int = 0
    add_open: bool = False


@dataclass(frozen=True)
class PlanReactionEditorResult:
    state: PlanReactionEditorState
    resolution: PlanReactionResolution | None
    blocking_error: str | None = None


def _clone(state: PlanReactionEditorState) -> PlanReactionEditorState:
    return copy.deepcopy(state)


def _source_ids(items) -> tuple[int, ...]:
    return tuple(dict.fromkeys(item.id for item in items or ()))


def _new_row(
    state: PlanReactionEditorState,
    *,
    emoji: str,
    label: str,
    inherited=(),
    inherited_order: int | None = None,
    protected_order: int | None = None,
    catalog_order: int | None = None,
) -> PlanReactionEditorRow:
    row = PlanReactionEditorRow(
        row_id=f"r{state.next_row_number}",
        emoji=emoji,
        label=label,
        inherited_source_keys=tuple(inherited),
        inherited_order=inherited_order,
        protected_order=protected_order,
        catalog_order=catalog_order,
    )
    state.next_row_number += 1
    return row


def _row_sort_key(row: PlanReactionEditorRow) -> tuple[int, int]:
    if row.inherited_order is not None:
        return (0, row.inherited_order)
    if row.protected_order is not None:
        return (1, row.protected_order)
    return (2, row.catalog_order if row.catalog_order is not None else 10_000)


def build_plan_reaction_editor_state(
    *,
    practice_types,
    activities,
    saved_snapshot=None,
) -> PlanReactionEditorResult:
    """Reconstruct a Create or Edit working state from selected sources."""

    practice_types = tuple(practice_types or ())
    activities = tuple(activities or ())
    try:
        resolution = resolve_plan_reaction_defaults(practice_types, activities)
    except PlanReactionValidationError as exc:
        state = PlanReactionEditorState(
            last_valid_type_ids=_source_ids(practice_types),
            last_valid_activity_ids=_source_ids(activities),
            blocking_error=str(exc),
        )
        if saved_snapshot is not None:
            for saved_order, pair in enumerate(
                normalize_plan_reactions(
                    saved_snapshot,
                    source="Saved Plan reactions",
                )
            ):
                state.rows.append(
                    _new_row(
                        state,
                        emoji=pair["emoji"],
                        label=pair["label"],
                        protected_order=saved_order,
                    )
                )
        return PlanReactionEditorResult(state, None, str(exc))

    state = PlanReactionEditorState(
        last_valid_type_ids=_source_ids(practice_types),
        last_valid_activity_ids=_source_ids(activities),
        unconfigured_activity_names=resolution.unconfigured_activity_names,
        effective_inherited_count=len(resolution.rows),
    )
    current = {
        row.emoji: (index, row)
        for index, row in enumerate(resolution.rows)
    }
    if saved_snapshot is None:
        for index, row in enumerate(resolution.rows):
            state.rows.append(
                _new_row(
                    state,
                    emoji=row.emoji,
                    label=row.label,
                    inherited=row.source_keys,
                    inherited_order=index,
                )
            )
    else:
        saved = normalize_plan_reactions(
            saved_snapshot,
            source="Saved Plan reactions",
        )
        for saved_order, pair in enumerate(saved):
            match = current.get(pair["emoji"])
            state.rows.append(
                _new_row(
                    state,
                    emoji=pair["emoji"],
                    label=pair["label"],
                    inherited=match[1].source_keys if match else (),
                    inherited_order=match[0] if match else None,
                    protected_order=None if match else saved_order,
                )
            )
        saved_keys = {pair["emoji"] for pair in saved}
        state.suppressed = [
            SuppressedPlanReaction(row.emoji, row.source_keys, index)
            for index, row in enumerate(resolution.rows)
            if row.emoji not in saved_keys
        ]
    state.rows.sort(key=_row_sort_key)
    return PlanReactionEditorResult(state, resolution)


def reconcile_plan_reaction_editor_state(
    state: PlanReactionEditorState,
    *,
    practice_types,
    activities,
) -> PlanReactionEditorResult:
    """Reconcile an existing working state with a source selection change."""

    practice_types = tuple(practice_types or ())
    activities = tuple(activities or ())
    original = _clone(state)
    try:
        resolution = resolve_plan_reaction_defaults(practice_types, activities)
    except PlanReactionValidationError as exc:
        original.blocking_error = str(exc)
        original.add_open = False
        return PlanReactionEditorResult(original, None, str(exc))

    working = _clone(state)
    desired = {
        row.emoji: (index, row)
        for index, row in enumerate(resolution.rows)
    }
    kept_suppression = []
    for item in working.suppressed:
        match = desired.get(item.emoji)
        if match and any(
            key in match[1].source_keys for key in item.source_keys
        ):
            kept_suppression.append(
                SuppressedPlanReaction(
                    item.emoji,
                    item.source_keys,
                    match[0],
                )
            )
    kept_suppression.sort(key=lambda item: item.inherited_order)
    suppressed_keys = {item.emoji for item in kept_suppression}

    kept_rows = []
    for row in working.rows:
        match = desired.get(row.emoji)
        if match:
            row.inherited_order = match[0]
            row.inherited_source_keys = match[1].source_keys
        else:
            row.inherited_order = None
            row.inherited_source_keys = ()
        if (
            match
            or row.protected_order is not None
            or row.catalog_order is not None
        ):
            kept_rows.append(row)
    working.rows = kept_rows

    by_emoji = {row.emoji: row for row in working.rows}
    for index, resolved in enumerate(resolution.rows):
        if (
            resolved.emoji not in by_emoji
            and resolved.emoji not in suppressed_keys
        ):
            row = _new_row(
                working,
                emoji=resolved.emoji,
                label=resolved.label,
                inherited=resolved.source_keys,
                inherited_order=index,
            )
            working.rows.append(row)
            by_emoji[row.emoji] = row

    working.suppressed = kept_suppression
    if len({row.emoji for row in working.rows}) > MAX_PLAN_REACTIONS:
        original.blocking_error = (
            "Selected Activities and Workout Types reserve more than "
            f"{MAX_PLAN_REACTIONS} reactions"
        )
        original.add_open = False
        return PlanReactionEditorResult(
            original,
            None,
            original.blocking_error,
        )

    working.rows.sort(key=_row_sort_key)
    working.last_valid_type_ids = _source_ids(practice_types)
    working.last_valid_activity_ids = _source_ids(activities)
    working.unconfigured_activity_names = resolution.unconfigured_activity_names
    working.effective_inherited_count = len(resolution.rows)
    working.blocking_error = None
    return PlanReactionEditorResult(working, resolution)


def reserved_plan_reaction_slots(state: PlanReactionEditorState) -> int:
    """Return active plus removed emoji slots reserved by the editor."""

    return len({row.emoji for row in state.rows})


def remove_plan_reaction(
    state: PlanReactionEditorState,
    row_id: str,
) -> PlanReactionEditorState:
    working = _clone(state)
    row = next(
        (item for item in working.rows if item.row_id == row_id),
        None,
    )
    if row is None:
        raise PlanReactionValidationError("Unknown reaction row")
    row.removed = True
    return working


def undo_plan_reaction(
    state: PlanReactionEditorState,
    row_id: str,
) -> PlanReactionEditorState:
    working = _clone(state)
    row = next(
        (item for item in working.rows if item.row_id == row_id),
        None,
    )
    if row is None or not row.removed:
        raise PlanReactionValidationError("Unknown removed reaction row")
    row.removed = False
    return working


def add_catalog_plan_reaction(
    state: PlanReactionEditorState,
    option: PlanReactionCatalogOption,
) -> PlanReactionEditorState:
    working = _clone(state)
    suppressed = next(
        (
            item
            for item in working.suppressed
            if item.emoji == option.emoji
        ),
        None,
    )
    inherited_source_keys = ()
    inherited_order = None
    if suppressed is not None:
        inherited_source_keys = tuple(
            key
            for key in suppressed.source_keys
            if _source_key_is_applicable(
                key,
                type_ids=working.last_valid_type_ids,
                activity_ids=working.last_valid_activity_ids,
            )
        )
        if inherited_source_keys:
            inherited_order = suppressed.inherited_order
    working.suppressed = [
        item
        for item in working.suppressed
        if item.emoji != option.emoji
    ]
    existing = next(
        (row for row in working.rows if row.emoji == option.emoji),
        None,
    )
    if existing:
        if existing.catalog_order is None:
            existing.catalog_order = max(
                (
                    row.catalog_order
                    for row in working.rows
                    if row.catalog_order is not None
                ),
                default=-1,
            ) + 1
        return working

    if reserved_plan_reaction_slots(working) >= MAX_PLAN_REACTIONS:
        raise PlanReactionValidationError(
            "Plan reactions: use at most 4 reactions"
        )
    order = max(
        (
            row.catalog_order
            for row in working.rows
            if row.catalog_order is not None
        ),
        default=-1,
    ) + 1
    working.rows.append(
        _new_row(
            working,
            emoji=option.emoji,
            label=option.label,
            inherited=inherited_source_keys,
            inherited_order=inherited_order,
            catalog_order=order,
        )
    )
    working.rows.sort(key=_row_sort_key)
    working.add_open = False
    return working


def restore_plan_reaction_defaults(
    state: PlanReactionEditorState,
    *,
    practice_types,
    activities,
) -> PlanReactionEditorResult:
    """Atomically discard practice-specific edits and rebuild defaults."""

    try:
        restored = build_plan_reaction_editor_state(
            practice_types=practice_types,
            activities=activities,
            saved_snapshot=None,
        )
    except PlanReactionValidationError as exc:
        working = _clone(state)
        working.blocking_error = str(exc)
        working.add_open = False
        return PlanReactionEditorResult(working, None, str(exc))
    if restored.blocking_error:
        working = _clone(state)
        working.blocking_error = restored.blocking_error
        working.add_open = False
        return PlanReactionEditorResult(
            working,
            None,
            restored.blocking_error,
        )
    next_row_number = state.next_row_number
    for row in restored.state.rows:
        row.row_id = f"r{next_row_number}"
        next_row_number += 1
    restored.state.next_row_number = next_row_number
    return restored


def active_plan_reaction_snapshot(
    state: PlanReactionEditorState,
) -> list[dict[str, str]]:
    """Validate and return the active rows for submission."""

    return normalize_plan_reactions(
        [
            {"emoji": row.emoji, "label": row.label}
            for row in state.rows
            if not row.removed
        ]
    )


def serialize_plan_reaction_editor_state(
    state: PlanReactionEditorState,
    *,
    omit_active_labels: bool = False,
) -> dict[str, object]:
    """Encode editor state using JSON-compatible primitives."""

    return {
        "version": state.version,
        "rows": [
            {
                "row_id": row.row_id,
                "emoji": row.emoji,
                "label": (
                    None
                    if omit_active_labels and not row.removed
                    else row.label
                ),
                "removed": row.removed,
                "inherited_source_keys": list(row.inherited_source_keys),
                "inherited_order": row.inherited_order,
                "protected_order": row.protected_order,
                "catalog_order": row.catalog_order,
            }
            for row in state.rows
        ],
        "suppressed": [
            {
                "emoji": item.emoji,
                "source_keys": list(item.source_keys),
                "inherited_order": item.inherited_order,
            }
            for item in state.suppressed
        ],
        "last_valid_type_ids": list(state.last_valid_type_ids),
        "last_valid_activity_ids": list(state.last_valid_activity_ids),
        "next_row_number": state.next_row_number,
        "blocking_error": state.blocking_error,
        "unconfigured_activity_names": list(
            state.unconfigured_activity_names
        ),
        "effective_inherited_count": state.effective_inherited_count,
        "add_open": state.add_open,
    }


def _metadata_error() -> PlanReactionValidationError:
    return PlanReactionValidationError(_EDITOR_METADATA_ERROR)


def _require_json_list(value) -> list:
    if not isinstance(value, list):
        raise _metadata_error()
    return value


def _require_nonnegative_int(value) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise _metadata_error()
    return value


def _decode_source_ids(value) -> tuple[int, ...]:
    values = _require_json_list(value)
    if any(
        isinstance(item, bool)
        or not isinstance(item, int)
        or item <= 0
        for item in values
    ):
        raise _metadata_error()
    if len(set(values)) != len(values):
        raise _metadata_error()
    return tuple(values)


def _decode_order(value) -> int | None:
    if value is None:
        return None
    order = _require_nonnegative_int(value)
    if order >= MAX_PLAN_REACTIONS:
        raise _metadata_error()
    return order


def _decode_source_keys(value) -> tuple[str, ...]:
    values = _require_json_list(value)
    if any(
        not isinstance(item, str) or not _SOURCE_KEY_RE.fullmatch(item)
        for item in values
    ):
        raise _metadata_error()
    if len(set(values)) != len(values):
        raise _metadata_error()
    return tuple(values)


def _decode_emoji(value) -> str:
    if not isinstance(value, str):
        raise _metadata_error()
    normalized = normalize_plan_reactions(
        [{"emoji": value, "label": "editor metadata"}],
        source="Reaction editor metadata",
    )[0]["emoji"]
    if normalized != value:
        raise _metadata_error()
    return value


def _decode_label(value, *, removed: bool) -> str:
    if value is None:
        if removed:
            raise _metadata_error()
        return ""
    if not isinstance(value, str):
        raise _metadata_error()
    if len(value) > MAX_PLAN_REACTION_LABEL or _LINE_BREAK_RE.search(value):
        raise _metadata_error()
    return value


def _source_key_is_applicable(
    source_key: str,
    *,
    type_ids: tuple[int, ...],
    activity_ids: tuple[int, ...],
) -> bool:
    match = _SOURCE_KEY_RE.fullmatch(source_key)
    if not match:
        return False
    source_id = int(match.group(2))
    if match.group(1) == "type":
        return source_id in type_ids
    return len(activity_ids) >= 2 and source_id in activity_ids


def _deserialize_plan_reaction_editor_state(
    payload,
) -> PlanReactionEditorState:
    if not isinstance(payload, Mapping) or set(payload) != _EDITOR_KEYS:
        raise _metadata_error()
    if (
        isinstance(payload["version"], bool)
        or not isinstance(payload["version"], int)
        or payload["version"] != PLAN_REACTION_EDITOR_VERSION
    ):
        raise _metadata_error()

    type_ids = _decode_source_ids(payload["last_valid_type_ids"])
    activity_ids = _decode_source_ids(
        payload["last_valid_activity_ids"]
    )
    next_row_number = _require_nonnegative_int(payload["next_row_number"])
    effective_inherited_count = _require_nonnegative_int(
        payload["effective_inherited_count"]
    )
    if effective_inherited_count > MAX_PLAN_REACTIONS:
        raise _metadata_error()
    blocking_error = payload["blocking_error"]
    if blocking_error is not None and not isinstance(blocking_error, str):
        raise _metadata_error()
    if not isinstance(payload["add_open"], bool):
        raise _metadata_error()

    names = _require_json_list(payload["unconfigured_activity_names"])
    if any(not isinstance(name, str) or not name for name in names):
        raise _metadata_error()

    row_payloads = _require_json_list(payload["rows"])
    if len(row_payloads) > MAX_PLAN_REACTIONS:
        raise _metadata_error()
    rows = []
    row_ids = set()
    emojis = set()
    row_numbers = set()
    orders = {
        "inherited": set(),
        "protected": set(),
        "catalog": set(),
    }
    for row_payload in row_payloads:
        if not isinstance(row_payload, Mapping) or set(row_payload) != _ROW_KEYS:
            raise _metadata_error()
        row_id = row_payload["row_id"]
        if not isinstance(row_id, str):
            raise _metadata_error()
        row_id_match = _ROW_ID_RE.fullmatch(row_id)
        if not row_id_match or row_id in row_ids:
            raise _metadata_error()
        row_number = int(row_id_match.group(1))
        if row_number in row_numbers or row_number >= next_row_number:
            raise _metadata_error()

        emoji = _decode_emoji(row_payload["emoji"])
        if emoji in emojis:
            raise _metadata_error()
        removed = row_payload["removed"]
        if not isinstance(removed, bool):
            raise _metadata_error()
        label = _decode_label(row_payload["label"], removed=removed)
        inherited_source_keys = _decode_source_keys(
            row_payload["inherited_source_keys"]
        )
        inherited_order = _decode_order(row_payload["inherited_order"])
        protected_order = _decode_order(row_payload["protected_order"])
        catalog_order = _decode_order(row_payload["catalog_order"])
        if (
            inherited_order is not None
            and inherited_order >= effective_inherited_count
        ):
            raise _metadata_error()
        if bool(inherited_source_keys) != (inherited_order is not None):
            raise _metadata_error()
        if (
            inherited_order is None
            and protected_order is None
            and catalog_order is None
        ):
            raise _metadata_error()
        if any(
            not _source_key_is_applicable(
                source_key,
                type_ids=type_ids,
                activity_ids=activity_ids,
            )
            for source_key in inherited_source_keys
        ):
            raise _metadata_error()
        for origin, order in (
            ("inherited", inherited_order),
            ("protected", protected_order),
            ("catalog", catalog_order),
        ):
            if order is not None:
                if order in orders[origin]:
                    raise _metadata_error()
                orders[origin].add(order)

        rows.append(
            PlanReactionEditorRow(
                row_id=row_id,
                emoji=emoji,
                label=label,
                removed=removed,
                inherited_source_keys=inherited_source_keys,
                inherited_order=inherited_order,
                protected_order=protected_order,
                catalog_order=catalog_order,
            )
        )
        row_ids.add(row_id)
        row_numbers.add(row_number)
        emojis.add(emoji)

    suppressed_payloads = _require_json_list(payload["suppressed"])
    suppressed = []
    suppressed_emojis = set()
    suppressed_orders = set()
    for suppressed_payload in suppressed_payloads:
        if (
            not isinstance(suppressed_payload, Mapping)
            or set(suppressed_payload) != _SUPPRESSED_KEYS
        ):
            raise _metadata_error()
        emoji = _decode_emoji(suppressed_payload["emoji"])
        source_keys = _decode_source_keys(suppressed_payload["source_keys"])
        inherited_order = _decode_order(
            suppressed_payload["inherited_order"]
        )
        if (
            not source_keys
            or inherited_order is None
            or inherited_order >= effective_inherited_count
            or inherited_order in suppressed_orders
            or inherited_order in orders["inherited"]
            or emoji in emojis
            or emoji in suppressed_emojis
            or not any(
                _source_key_is_applicable(
                    source_key,
                    type_ids=type_ids,
                    activity_ids=activity_ids,
                )
                for source_key in source_keys
            )
        ):
            raise _metadata_error()
        suppressed.append(
            SuppressedPlanReaction(emoji, source_keys, inherited_order)
        )
        suppressed_emojis.add(emoji)
        suppressed_orders.add(inherited_order)

    if rows != sorted(rows, key=_row_sort_key):
        raise _metadata_error()
    if suppressed != sorted(
        suppressed,
        key=lambda item: item.inherited_order,
    ):
        raise _metadata_error()
    if orders["inherited"] | suppressed_orders != set(
        range(effective_inherited_count)
    ):
        raise _metadata_error()

    return PlanReactionEditorState(
        version=payload["version"],
        rows=rows,
        suppressed=suppressed,
        last_valid_type_ids=type_ids,
        last_valid_activity_ids=activity_ids,
        next_row_number=next_row_number,
        blocking_error=blocking_error,
        unconfigured_activity_names=tuple(names),
        effective_inherited_count=effective_inherited_count,
        add_open=payload["add_open"],
    )


def deserialize_plan_reaction_editor_state(payload) -> PlanReactionEditorState:
    """Decode and validate untrusted adapter metadata."""

    try:
        return _deserialize_plan_reaction_editor_state(payload)
    except (KeyError, TypeError, ValueError, PlanReactionValidationError):
        raise _metadata_error() from None


__all__ = [
    "PLAN_REACTION_EDITOR_VERSION",
    "PlanReactionEditorResult",
    "PlanReactionEditorRow",
    "PlanReactionEditorState",
    "SuppressedPlanReaction",
    "active_plan_reaction_snapshot",
    "add_catalog_plan_reaction",
    "build_plan_reaction_editor_state",
    "deserialize_plan_reaction_editor_state",
    "reconcile_plan_reaction_editor_state",
    "remove_plan_reaction",
    "reserved_plan_reaction_slots",
    "restore_plan_reaction_defaults",
    "serialize_plan_reaction_editor_state",
    "undo_plan_reaction",
]
