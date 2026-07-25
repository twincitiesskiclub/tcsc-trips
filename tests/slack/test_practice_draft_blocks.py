"""Readiness digest blocks."""

import json
from datetime import datetime
from types import SimpleNamespace

from app.slack.blocks.practice_drafts import build_readiness_digest_blocks


def _practice(day, hour, minute):
    return SimpleNamespace(
        id=day, date=datetime(2026, 8, day, hour, minute),
        location=None, practice_types=[], activities=[],
    )


def test_digest_reports_ready_count_and_blocks_poll():
    summary = {
        "total": 12, "ready": 8,
        "incomplete": [(_practice(11, 18, 15), ["location", "type"])],
    }
    blocks = build_readiness_digest_blocks(summary, "Jul 21", "Aug 13")
    text = json.dumps(blocks)

    assert "8 of 12 ready" in text
    assert "Tue 8/11" in text
    assert "location" in text and "type" in text


def test_fully_ready_digest_says_poll_can_open():
    summary = {"total": 12, "ready": 12, "incomplete": []}
    blocks = build_readiness_digest_blocks(summary, "Jul 21", "Aug 13")
    text = json.dumps(blocks)

    assert "12 of 12 ready" in text
    assert "ready to send" in text.lower()


def test_each_incomplete_row_opens_the_existing_edit_modal():
    summary = {
        "total": 12, "ready": 10,
        "incomplete": [(_practice(11, 18, 15), ["location"]),
                       (_practice(13, 19, 20), ["type"])],
    }
    blocks = build_readiness_digest_blocks(summary, "Jul 21", "Aug 13")
    buttons = [b["accessory"] for b in blocks if b.get("accessory")]

    assert len(buttons) == 2
    assert all(b["action_id"] == "edit_practice_full" for b in buttons), \
        "reuse the existing handler rather than adding a new one"
    assert [b["value"] for b in buttons] == ["11", "13"], \
        "the handler reads the practice id from action['value']"


def test_digest_stays_within_slack_block_limit():
    # Feed 200 practices to ensure uncapped builder would exceed 50 blocks.
    # With MAX_LISTED=12 cap: 1 header + 1 summary + 12 rows + 1 "more" context + 1 bulb context = 16 blocks.
    incomplete = [(_practice(4 + i % 20, 18, 15), ["location"]) for i in range(200)]
    summary = {"total": 220, "ready": 20, "incomplete": incomplete}
    blocks = build_readiness_digest_blocks(summary, "Jul 21", "Aug 13")

    assert len(blocks) <= 50, "Slack rejects messages over 50 blocks"
    assert len(blocks) == 16, f"Cap should hold at 16 blocks, got {len(blocks)}"
