"""Availability poll and nudge blocks — copy is approved and exact."""

import json
from datetime import datetime

from app.slack.blocks.availability import (
    build_nudge_blocks,
    build_poll_blocks,
    poll_fallback_text,
)


def _rows():
    return [
        {"emoji": "letter_a", "date": datetime(2026, 7, 21, 18, 15),
         "location": "Brackett Park", "kind": "Multi-sport", "week_label": "Week of Jul 21"},
        {"emoji": "letter_b", "date": datetime(2026, 7, 23, 18, 15),
         "location": "Balance", "kind": "Early Lift", "week_label": "Week of Jul 21"},
        {"emoji": "letter_c", "date": datetime(2026, 7, 28, 18, 15),
         "location": "Theo Wirth", "kind": "Trail Run", "week_label": "Week of Jul 28"},
    ]


def test_title_and_instruction_match_approved_copy():
    blocks = build_poll_blocks(_rows(), "July 21", "Aug 13")
    text = json.dumps(blocks)

    assert "Practice Leads July 21 - Aug 13" in text
    assert "React to each session you can lead." in text
    assert "when you're done, even if you picked nothing." in text


def test_no_deadline_footer():
    text = json.dumps(build_poll_blocks(_rows(), "July 21", "Aug 13")).lower()
    assert "closes" not in text
    assert "deadline" not in text


def test_rows_are_grouped_by_week_with_one_emoji_each():
    blocks = build_poll_blocks(_rows(), "July 21", "Aug 13")
    sections = [b for b in blocks if b["type"] == "section"]

    assert len(sections) == 2, "one section per week"
    assert "Week of Jul 21" in sections[0]["text"]["text"]
    assert ":letter_a:" in sections[0]["text"]["text"]
    assert ":letter_c:" in sections[1]["text"]["text"]


def test_each_line_carries_location_type_and_time():
    blocks = build_poll_blocks(_rows(), "July 21", "Aug 13")
    text = json.dumps(blocks)
    assert "Brackett Park" in text and "Multi-sport" in text and "6:15p" in text


def test_fallback_text_describes_the_poll_for_screen_readers():
    fallback = poll_fallback_text(_rows(), "July 21", "Aug 13")
    assert "Practice Leads" in fallback
    assert "3 sessions" in fallback


def test_poll_stays_within_block_limit():
    # 2 fixed blocks (header + instruction) + 60 distinct weeks would be 62
    # blocks with no cap -- comfortably over the 50-block ceiling, so this
    # actually exercises the cap rather than passing regardless of it.
    rows = [
        {"emoji": f"letter_{i}", "date": datetime(2026, 8, 4, 18, 15),
         "location": "Balance", "kind": "Lift", "week_label": f"Week {i}"}
        for i in range(60)
    ]
    blocks = build_poll_blocks(rows, "Aug 1", "Sep 1")
    assert len(blocks) <= 50
    assert "more weeks not shown" in json.dumps(blocks)


def test_nudge_uses_approved_copy_and_a_single_url_button():
    blocks = build_nudge_blocks("Jul 21", "Aug 13", "C02J4DGCFL2", "https://slack.com/p/1")
    text = json.dumps(blocks)

    assert "Reminder: Provide lead availability for" in text
    assert "<#C02J4DGCFL2>" in text
    assert "To suppress these" in text

    actions = [b for b in blocks if b["type"] == "actions"]
    assert len(actions) == 1
    buttons = actions[0]["elements"]
    assert len(buttons) == 1, "one button only"
    assert buttons[0]["text"]["text"] == "Go to post"
    assert buttons[0]["url"] == "https://slack.com/p/1"


def test_nudge_without_permalink_omits_the_button_rather_than_breaking():
    blocks = build_nudge_blocks("Jul 21", "Aug 13", "C02J4DGCFL2", None)
    assert not [b for b in blocks if b["type"] == "actions"], \
        "a url button with no url is rejected by Slack"
