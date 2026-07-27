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
    # With the MAX_LISTED=40 cap: 1 header + 1 summary + 40 rows +
    # 1 "more" context + 1 bulb context = 44 blocks, inside Slack's 50.
    incomplete = [(_practice(4 + i % 20, 18, 15), ["location"]) for i in range(200)]
    summary = {"total": 220, "ready": 20, "incomplete": incomplete}
    blocks = build_readiness_digest_blocks(summary, "Jul 21", "Aug 13")

    assert len(blocks) <= 50, "Slack rejects messages over 50 blocks"
    assert len(blocks) == 44, f"Cap should hold at 44 blocks, got {len(blocks)}"


def test_digest_lists_a_full_two_month_block_without_truncating():
    """The drafting window is now two months (see end_of_next_month): a
    freshly-bootstrapped Tue/Thu/Sat block is ~29 all-incomplete drafts, and
    MAX_LISTED=12 (sized for the old 4-week block) would hide most of what
    needs filling in behind "+N more not shown" on every first digest."""
    incomplete = [(_practice(1 + i % 28, 18, 15), ["location"]) for i in range(29)]
    summary = {"total": 29, "ready": 0, "incomplete": incomplete}
    blocks = build_readiness_digest_blocks(summary, "Aug 1", "Sep 30")

    rows = [b for b in blocks if b.get("accessory")]
    assert len(rows) == 29, "every incomplete draft in a two-month block must be listed"
    assert not any(
        "more not shown" in element.get("text", "")
        for b in blocks if b.get("type") == "context"
        for element in b.get("elements", [])
    ), "a normal-size block must never be truncated"
