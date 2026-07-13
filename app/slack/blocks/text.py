"""Slack Block Kit and notification-fallback text limits."""

from __future__ import annotations

import copy
import logging


logger = logging.getLogger(__name__)

BLOCKS_MAX = 50
HEADER_TEXT_MAX = 150
SECTION_TEXT_MAX = 3000
SECTION_FIELD_TEXT_MAX = 2000
CONTEXT_TEXT_MAX = 2000
FALLBACK_TEXT_MAX = 4000


def _guard_text_object(value, max_chars, field, surface, practice_id):
    if not isinstance(value, dict) or "text" not in value:
        return
    value["text"] = truncate_slack_text(
        value["text"],
        max_chars,
        field=field,
        surface=surface,
        practice_id=practice_id,
    )


def truncate_slack_text(text, max_chars, *, field, surface, practice_id=None):
    value = str(text or "")
    if len(value) <= max_chars:
        return value
    logger.warning(
        "Truncated Slack %s on %s for practice #%s from %s to %s characters",
        field,
        surface,
        practice_id,
        len(value),
        max_chars,
    )
    return value[: max_chars - 1].rstrip() + "…"


def guard_slack_blocks(blocks, *, surface, practice_id=None):
    guarded = copy.deepcopy(blocks)
    for block in guarded:
        if block.get("type") == "header":
            _guard_text_object(
                block.get("text"), HEADER_TEXT_MAX, "header", surface, practice_id
            )
        elif block.get("type") == "section":
            _guard_text_object(
                block.get("text"), SECTION_TEXT_MAX, "section", surface, practice_id
            )
            for field in block.get("fields", []):
                _guard_text_object(
                    field,
                    SECTION_FIELD_TEXT_MAX,
                    "section field",
                    surface,
                    practice_id,
                )
        elif block.get("type") == "context":
            for element in block.get("elements", []):
                if element.get("type") in {"mrkdwn", "plain_text"}:
                    _guard_text_object(
                        element,
                        CONTEXT_TEXT_MAX,
                        "context",
                        surface,
                        practice_id,
                    )
    return guarded


def guard_fallback_text(text, *, surface, practice_id=None):
    value = str(text or "").strip() or "Practice details unavailable"
    return truncate_slack_text(
        value,
        FALLBACK_TEXT_MAX,
        field="fallback",
        surface=surface,
        practice_id=practice_id,
    )
