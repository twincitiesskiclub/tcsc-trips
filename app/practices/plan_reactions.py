"""Validation and formatting for supplemental practice-plan reactions."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

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
    """Raised when a Plan-reaction definition cannot be rendered safely."""


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


def resolve_default_plan_reactions(practice_types: Iterable, activities: Iterable) -> list[dict[str, str]]:
    sources = [
        (f"Workout Type {item.name}", item)
        for item in sorted(practice_types or [], key=lambda item: item.name.lower())
    ] + [
        (f"Activity {item.name}", item)
        for item in sorted(activities or [], key=lambda item: item.name.lower())
    ]
    merged: list[dict[str, str]] = []
    by_emoji: dict[str, tuple[str, str]] = {}
    for source_name, item in sources:
        options = normalize_plan_reactions(
            getattr(item, "default_plan_reactions", None) or [], source=source_name
        )
        for option in options:
            previous = by_emoji.get(option["emoji"])
            if previous and previous[0] != option["label"]:
                raise PlanReactionValidationError(
                    f":{option['emoji']}: has conflicting labels in {previous[1]} and {source_name}"
                )
            if previous:
                continue
            by_emoji[option["emoji"]] = (option["label"], source_name)
            merged.append(option)
    if len(merged) > MAX_PLAN_REACTIONS:
        raise PlanReactionValidationError(
            f"Selected Activities and Workout Types produce more than {MAX_PLAN_REACTIONS} reactions"
        )
    return merged


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
