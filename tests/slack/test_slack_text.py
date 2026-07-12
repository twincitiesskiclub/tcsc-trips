import logging

import app.slack.blocks as slack_blocks
from app.slack.blocks.text import (
    CONTEXT_TEXT_MAX,
    FALLBACK_TEXT_MAX,
    HEADER_TEXT_MAX,
    SECTION_FIELD_TEXT_MAX,
    SECTION_TEXT_MAX,
    guard_fallback_text,
    guard_slack_blocks,
    truncate_slack_text,
)


def test_guard_truncates_each_supported_block_field(caplog):
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "H" * 151}},
        {"type": "section", "text": {"type": "mrkdwn", "text": "S" * 3001}},
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": "F" * 3001},
            ],
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": "C" * 2001},
                {
                    "type": "image",
                    "image_url": "https://example.test/icon.png",
                    "alt_text": "icon",
                },
            ],
        },
    ]

    with caplog.at_level(logging.WARNING):
        guarded = guard_slack_blocks(blocks, surface="practice", practice_id=42)

    assert len(guarded[0]["text"]["text"]) == HEADER_TEXT_MAX == 150
    assert len(guarded[1]["text"]["text"]) == SECTION_TEXT_MAX == 3000
    assert len(guarded[2]["fields"][0]["text"]) == SECTION_FIELD_TEXT_MAX == 2000
    assert len(guarded[3]["elements"][0]["text"]) == CONTEXT_TEXT_MAX == 2000
    assert guarded[3]["elements"][1]["alt_text"] == "icon"
    assert "practice" in caplog.text and "42" in caplog.text


def test_guards_do_not_mutate_the_input_and_preserve_short_text():
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "Short"}}]

    guarded = guard_slack_blocks(blocks, surface="test")

    assert guarded == blocks
    assert guarded is not blocks
    assert guarded[0] is not blocks[0]
    assert guarded[0]["text"] is not blocks[0]["text"]
    assert blocks[0]["text"]["text"] == "Short"


def test_fallback_text_is_nonempty_and_bounded():
    assert guard_fallback_text("", surface="practice") == "Practice details unavailable"
    result = guard_fallback_text("A" * 5000, surface="practice")
    assert len(result) == FALLBACK_TEXT_MAX == 4000
    assert result.endswith("…")


def test_named_source_is_logged_without_member_content(caplog):
    secret_member_text = "private workout detail " * 200
    with caplog.at_level(logging.WARNING):
        truncate_slack_text(
            secret_member_text,
            100,
            field="workout_description",
            surface="practice",
            practice_id=42,
        )
    assert "workout_description" in caplog.text
    assert "42" in caplog.text
    assert secret_member_text[:20] not in caplog.text


def test_guards_are_reexported_from_the_blocks_package():
    assert slack_blocks.HEADER_TEXT_MAX == 150
    assert slack_blocks.SECTION_TEXT_MAX == 3000
    assert slack_blocks.SECTION_FIELD_TEXT_MAX == 2000
    assert slack_blocks.CONTEXT_TEXT_MAX == 2000
    assert slack_blocks.FALLBACK_TEXT_MAX == 4000
    assert slack_blocks.truncate_slack_text is truncate_slack_text
    assert slack_blocks.guard_slack_blocks is guard_slack_blocks
    assert slack_blocks.guard_fallback_text is guard_fallback_text
