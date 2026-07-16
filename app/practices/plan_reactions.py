"""Validation and formatting for supplemental practice-plan reactions."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

MAX_PLAN_REACTIONS = 4
MAX_PLAN_REACTION_LABEL = 80
MAX_PLAN_REACTION_NAME = 80

_BASE_EMOJI_PATTERN = r"[a-z0-9_+\-]+"
_SKIN_TONE_PATTERN = r"skin-tone-[2-6]"
_NORMALIZED_EMOJI_PATTERN = (
    rf"{_BASE_EMOJI_PATTERN}(?:::{_SKIN_TONE_PATTERN})?"
)
EMOJI_RE = re.compile(
    rf"^(?P<base>{_BASE_EMOJI_PATTERN})"
    rf"(?:::(?P<modifier>{_SKIN_TONE_PATTERN}))?$"
)
_LINE_BREAK_RE = re.compile(r"[\n\r\v\f\x1c-\x1e\x85\u2028\u2029]")
LINE_RE = re.compile(
    rf"^\s*(?P<emoji>"
    rf":(?:{_NORMALIZED_EMOJI_PATTERN}):|"
    rf"(?:{_NORMALIZED_EMOJI_PATTERN})"
    rf")\s+(?P<label>.+?)\s*$"
)

EVERGREEN_PLAN_REACTION = {
    "emoji": "evergreen_tree",
    "label": "Endurance instead of intervals",
}

RESERVED_ATTENDANCE_EMOJIS = frozenset({
    "white_check_mark", "ballot_box_with_check", "heavy_check_mark",
    "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "keycap_ten",
})


class PlanReactionValidationError(ValueError):
    """Validation error with optional adapter-safe field metadata."""

    def __init__(
        self,
        message: str,
        *,
        field: str | None = None,
        row_id: str | None = None,
        emoji: str | None = None,
    ):
        super().__init__(message)
        self.field = field
        self.row_id = row_id
        self.emoji = emoji


@dataclass(frozen=True)
class ResolvedPlanReaction:
    emoji: str
    label: str
    source_keys: tuple[str, ...]


@dataclass(frozen=True)
class PlanReactionResolution:
    rows: tuple[ResolvedPlanReaction, ...]
    unconfigured_activity_names: tuple[str, ...] = ()

    @property
    def snapshot(self) -> list[dict[str, str]]:
        return [
            {"emoji": row.emoji, "label": row.label}
            for row in self.rows
        ]


@dataclass(frozen=True)
class PlanReactionCatalogOption:
    option_id: str
    emoji: str
    label: str
    source_keys: tuple[str, ...]


@dataclass
class _MutableResolvedReaction:
    emoji: str
    label: str
    source_keys: list[str]
    source_names: list[str]


def _normalize_emoji(value: object, source: str) -> str:
    emoji = str(value or "").strip().lower()
    if emoji.startswith(":") and emoji.endswith(":") and len(emoji) > 2:
        emoji = emoji[1:-1]
    if len(emoji) > MAX_PLAN_REACTION_NAME:
        raise PlanReactionValidationError(
            f"{source}: emoji name must be {MAX_PLAN_REACTION_NAME} characters or fewer"
        )
    match = EMOJI_RE.fullmatch(emoji)
    if not match:
        raise PlanReactionValidationError(
            f"{source}: enter a Slack emoji shortcode"
        )
    if match.group("base") in RESERVED_ATTENDANCE_EMOJIS:
        raise PlanReactionValidationError(f"{source}: :{emoji}: is reserved for attendance")
    return emoji


def normalize_plan_reactions(value: object, *, source: str = "Plan reactions") -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise PlanReactionValidationError(f"{source}: expected a list")
    if len(value) > MAX_PLAN_REACTIONS:
        raise PlanReactionValidationError(f"{source}: use at most {MAX_PLAN_REACTIONS} reactions")

    normalized = []
    seen = set()
    for index, item in enumerate(value, start=1):
        item_source = f"{source} row {index}"
        if not isinstance(item, Mapping):
            raise PlanReactionValidationError(f"{item_source}: expected emoji and label")
        emoji = _normalize_emoji(item.get("emoji"), item_source)
        raw_label = str(item.get("label") or "")
        if _LINE_BREAK_RE.search(raw_label):
            raise PlanReactionValidationError(f"{item_source}: label must be a single line")
        label = raw_label.strip()
        if not label:
            raise PlanReactionValidationError(f"{item_source}: label is required")
        _display_label(label, item_source)
        if len(label) > MAX_PLAN_REACTION_LABEL:
            raise PlanReactionValidationError(
                f"{item_source}: label must be {MAX_PLAN_REACTION_LABEL} characters or fewer"
            )
        if emoji in seen:
            raise PlanReactionValidationError(f"{source}: :{emoji}: appears more than once")
        seen.add(emoji)
        normalized.append({"emoji": emoji, "label": label})
    return normalized


def _distinct_sources(items: Iterable, kind: str) -> list[tuple[str, object]]:
    by_key = {}
    for item in items or ():
        source_id = getattr(item, "id", None)
        name = str(getattr(item, "name", "") or "").strip()
        if isinstance(source_id, bool) or not isinstance(source_id, int) or not name:
            raise PlanReactionValidationError(
                f"Invalid {kind} reaction source",
                field="activities" if kind == "activity" else "types",
            )
        by_key.setdefault(f"{kind}:{source_id}", item)
    return sorted(by_key.items(), key=lambda pair: pair[1].name.casefold())


def _normalize_source_plan_reactions(item, source_key: str, source_name: str):
    """Normalize a Settings source while retaining its selector provenance."""
    try:
        return normalize_plan_reactions(
            getattr(item, "default_plan_reactions", None) or [],
            source=source_name,
        )
    except PlanReactionValidationError as exc:
        if exc.field is not None:
            raise
        raise PlanReactionValidationError(
            str(exc),
            field=(
                "activities"
                if source_key.startswith("activity:")
                else "types"
            ),
            row_id=exc.row_id,
            emoji=exc.emoji,
        ) from exc


def resolve_plan_reaction_defaults(
    practice_types: Iterable,
    activities: Iterable,
) -> PlanReactionResolution:
    type_sources = _distinct_sources(practice_types, "type")
    activity_sources = _distinct_sources(activities, "activity")
    applicable = type_sources + (
        activity_sources if len(activity_sources) >= 2 else []
    )
    rows = []
    by_emoji = {}
    for source_key, item in applicable:
        source_name = (
            f"Workout Type {item.name}"
            if source_key.startswith("type:")
            else f"Activity {item.name}"
        )
        for option in _normalize_source_plan_reactions(
            item,
            source_key,
            source_name,
        ):
            prior = by_emoji.get(option["emoji"])
            if prior and prior.label != option["label"]:
                prior_name = prior.source_names[0]
                raise PlanReactionValidationError(
                    f":{option['emoji']}: has conflicting labels in "
                    f"{prior_name} and {source_name}",
                    field=(
                        "activities"
                        if source_key.startswith("activity:")
                        else "types"
                    ),
                    emoji=option["emoji"],
                )
            if prior:
                prior.source_keys.append(source_key)
                prior.source_names.append(source_name)
                continue
            mutable = _MutableResolvedReaction(
                emoji=option["emoji"],
                label=option["label"],
                source_keys=[source_key],
                source_names=[source_name],
            )
            by_emoji[option["emoji"]] = mutable
            rows.append(mutable)
    if len(rows) > MAX_PLAN_REACTIONS:
        raise PlanReactionValidationError(
            "Selected Activities and Workout Types produce more than "
            f"{MAX_PLAN_REACTIONS} reactions",
            field="activities" if len(activity_sources) >= 2 else "types",
        )
    return PlanReactionResolution(
        rows=tuple(
            ResolvedPlanReaction(
                row.emoji,
                row.label,
                tuple(row.source_keys),
            )
            for row in rows
        ),
        unconfigured_activity_names=(
            tuple(
                item.name
                for _, item in activity_sources
                if not item.default_plan_reactions
            )
            if len(activity_sources) >= 2
            else ()
        ),
    )


def resolve_default_plan_reactions(
    practice_types: Iterable,
    activities: Iterable,
) -> list[dict[str, str]]:
    return resolve_plan_reaction_defaults(practice_types, activities).snapshot


def build_plan_reaction_catalog(
    practice_types: Iterable,
    activities: Iterable,
) -> tuple[PlanReactionCatalogOption, ...]:
    merged = {}
    ordered = []
    for source_key, item in (
        _distinct_sources(practice_types, "type")
        + _distinct_sources(activities, "activity")
    ):
        source_name = (
            f"Workout Type {item.name}"
            if source_key.startswith("type:")
            else f"Activity {item.name}"
        )
        for pair in _normalize_source_plan_reactions(
            item,
            source_key,
            source_name,
        ):
            key = (pair["emoji"], pair["label"])
            if key in merged:
                merged[key].append(source_key)
                continue
            merged[key] = [source_key]
            ordered.append(key)
    return tuple(
        PlanReactionCatalogOption(
            option_id=hashlib.sha256(
                json.dumps(
                    key,
                    separators=(",", ":"),
                    ensure_ascii=True,
                ).encode()
            ).hexdigest()[:16],
            emoji=key[0],
            label=key[1],
            source_keys=tuple(merged[key]),
        )
        for key in ordered
    )


def validate_authorized_plan_reactions(
    value,
    *,
    catalog,
    protected_snapshot=(),
    source="Plan reactions",
) -> list[dict[str, str]]:
    normalized = normalize_plan_reactions(value, source=source)
    allowed = {item.emoji for item in catalog}
    allowed.update(
        item["emoji"]
        for item in normalize_plan_reactions(
            list(protected_snapshot or []),
            source="Saved Plan reactions",
        )
    )
    for row in normalized:
        if row["emoji"] not in allowed:
            raise PlanReactionValidationError(
                f"{source}: :{row['emoji']}: is not configured in Settings",
                emoji=row["emoji"],
            )
    return normalized


def parse_plan_reaction_lines(text: str) -> list[dict[str, str]]:
    rows = []
    for line_number, line in enumerate((text or "").splitlines(), start=1):
        if not line.strip():
            continue
        match = LINE_RE.fullmatch(line)
        if not match:
            raise PlanReactionValidationError(
                f"Line {line_number}: use :emoji: Member-facing label"
            )
        rows.append({
            "emoji": match.group("emoji"),
            "label": match.group("label"),
        })
    return normalize_plan_reactions(rows, source="Plan reactions")


def format_plan_reaction_lines(reactions: Iterable[Mapping[str, str]]) -> str:
    normalized = normalize_plan_reactions(list(reactions or []))
    return "\n".join(f":{item['emoji']}: {item['label']}" for item in normalized)


def format_plan_reaction_legend(reactions: Iterable[Mapping[str, str]]) -> str:
    normalized = normalize_plan_reactions(list(reactions or []))
    def escape_label(label: str) -> str:
        return label.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return " · ".join(
        f":{item['emoji']}: {escape_label(item['label'])}" for item in normalized
    )


def _display_label(label: str, source: str) -> str:
    display = re.sub(r"[.?!]+$", "", str(label).rstrip()).rstrip()
    if not display:
        raise PlanReactionValidationError(f"{source}: label is required")
    return display


def _escape_slack_label(label: str) -> str:
    return label.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _natural_join(items: list[str], *, conjunction: str) -> str:
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} {conjunction} {items[1]}"
    return f"{', '.join(items[:-1])}, {conjunction} {items[-1]}"


def format_reaction_name_for_fallback(name: str) -> str:
    normalized = str(name or "").strip().lower()
    if normalized.startswith(":") and normalized.endswith(":") and len(normalized) > 2:
        normalized = normalized[1:-1]
    if len(normalized) > MAX_PLAN_REACTION_NAME or not EMOJI_RE.fullmatch(normalized):
        raise PlanReactionValidationError(
            "Reaction name: enter a Slack emoji shortcode"
        )
    base, separator, modifier = normalized.partition("::")
    rendered = base.replace("_", " ")
    if separator:
        rendered += ", " + modifier.replace("-", " ")
    return rendered


def format_supplemental_reaction_sentence(
    reactions: Iterable[Mapping[str, str]],
) -> str:
    normalized = normalize_plan_reactions(list(reactions or []))
    if not normalized:
        return ""
    clauses = [
        f"a :{item['emoji']}: for "
        f"{_escape_slack_label(_display_label(item['label'], 'Plan reactions'))}"
        for item in normalized
    ]
    return (
        "In addition to your attendance emoji, hit "
        + _natural_join(clauses, conjunction="and")
        + "."
    )


def format_supplemental_reaction_fallback(
    reactions: Iterable[Mapping[str, str]],
) -> str:
    normalized = normalize_plan_reactions(list(reactions or []))
    if not normalized:
        return ""
    clauses = [
        f"{format_reaction_name_for_fallback(item['emoji'])} for "
        f"{_display_label(item['label'], 'Plan reactions')}"
        for item in normalized
    ]
    heading = "Additional reaction" if len(clauses) == 1 else "Additional reactions"
    return f"{heading}: {'; '.join(clauses)}."


def plan_reaction_names(reactions: Iterable[Mapping[str, str]]) -> list[str]:
    return [item["emoji"] for item in normalize_plan_reactions(list(reactions or []))]
