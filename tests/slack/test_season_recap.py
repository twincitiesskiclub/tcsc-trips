"""Renderer + poster for the daily registration recap. The renderer is pure
(stats dict in, blocks out), so no DB needed; the poster mocks the Slack
client and must never raise."""
from datetime import date
from unittest.mock import patch, MagicMock

import pytest

from app import create_app


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    return app


def _stats(**overrides):
    base = {
        "season_id": 42,
        "season_name": "Winter 2098",
        "for_date": date(2098, 1, 10),
        "yesterday": {"new": 2, "returning": 1, "total": 3},
        "previous_day_total": 1,
        "season_totals": {"new": 90, "returning": 52, "total": 142,
                          "registration_limit": 200, "pct_of_limit": 71},
        "windows": {
            "returning": {"start": date(2098, 1, 6), "end": date(2098, 1, 26),
                          "is_open": True, "day_number": 5,
                          "days_remaining": 16, "length_days": 21},
            "new": None,
        },
        "prior_season": {"name": "Winter 2097",
                         "count_at_same_point": 118, "final_count": 240},
        "volunteer": {"answered": 2, "of": 3,
                      "interests": {"Lead a group at practice": 2},
                      "committees": {}},
        "needs_review": 0,
        "highlights": ["Biggest day of the season so far: 3 registrations."],
    }
    base.update(overrides)
    return base


def _all_text(blocks):
    """Every piece of text in the message: section text, section fields,
    context elements, header text."""
    parts = []
    for block in blocks:
        text = block.get("text")
        if isinstance(text, dict):
            parts.append(text.get("text", ""))
        for field in block.get("fields", []):
            parts.append(field.get("text", ""))
        for element in block.get("elements", []):
            if isinstance(element, dict):
                parts.append(element.get("text", ""))
    return "\n".join(parts)


def _assert_valid_block_kit(blocks):
    """The Slack limits the renderer must never exceed."""
    assert len(blocks) <= 50
    for block in blocks:
        assert block["type"] in ("header", "section", "context", "divider")
        if block["type"] == "header":
            assert block["text"]["type"] == "plain_text"
            assert len(block["text"]["text"]) <= 150
        if block["type"] == "section":
            assert "text" in block or block.get("fields")
            if "text" in block:
                assert len(block["text"]["text"]) <= 3000
            fields = block.get("fields", [])
            assert len(fields) <= 10
            for field in fields:
                assert len(field["text"]) <= 2000
        if block["type"] == "context":
            assert 1 <= len(block["elements"]) <= 10
        # House style: no em dashes anywhere.
        assert "—" not in str(block)


def test_blocks_render_every_section():
    from app.slack.season_recap import build_recap_blocks
    blocks, fallback = build_recap_blocks(_stats())
    _assert_valid_block_kit(blocks)

    # The header leads with yesterday's count, nothing else.
    assert blocks[0]["type"] == "header"
    assert blocks[0]["text"]["text"] == "3 registrations yesterday"

    text = _all_text(blocks)
    assert "Winter 2098" in text                # season name in the meta line
    assert "2 new, 1 returning" in text         # yesterday breakdown
    assert "Up from 1 the day before" in text   # trend
    assert "142 of 200 (71%)" in text           # season total with cap
    assert "90 / 52" in text                    # season new/returning split
    assert "Day 5 of 21" in text                # window pace
    assert "closes Jan 26" in text
    assert "Winter 2097" in text                # prior season
    assert "118" in text
    assert "Lead a group at practice (2)" in text  # volunteer
    assert ":sparkles:" in text                 # highlight
    assert "Biggest day" in text
    assert "142" in fallback
    assert "\n" not in fallback                 # fallback stays one line


def test_blocks_omit_empty_sections():
    from app.slack.season_recap import build_recap_blocks
    blocks, _ = build_recap_blocks(_stats(
        prior_season=None,
        volunteer={"answered": 0, "of": 0, "interests": {}, "committees": {}},
        highlights=[],
        needs_review=0,
    ))
    _assert_valid_block_kit(blocks)
    text = _all_text(blocks)
    assert "Winter 2097" not in text
    assert "Get Involved" not in text
    assert "need review" not in text
    assert ":warning:" not in text
    assert ":sparkles:" not in text


def test_quiet_day_renders_clean():
    from app.slack.season_recap import build_recap_blocks
    blocks, fallback = build_recap_blocks(_stats(
        yesterday={"new": 0, "returning": 0, "total": 0},
        previous_day_total=0,
        highlights=[],
    ))
    _assert_valid_block_kit(blocks)
    assert blocks[0]["text"]["text"] == "0 registrations yesterday"
    text = _all_text(blocks)
    assert "0 new, 0 returning" not in text     # zero-day breakdown is noise
    assert "Same as the day before (0)" in text
    assert "0 yesterday" in fallback


def test_needs_review_warning_renders_with_link():
    from app.slack.season_recap import build_recap_blocks
    blocks, _ = build_recap_blocks(_stats(needs_review=4))
    _assert_valid_block_kit(blocks)
    text = _all_text(blocks)
    assert "4 registrations need review" in text
    assert ":warning:" in text
    assert "registration-review?season_id=42" in text


def test_post_success(app):
    from app.slack.season_recap import post_season_recap
    client = MagicMock()
    with app.app_context(), \
         patch("app.slack.season_recap.get_channel_id_by_name",
               return_value="C123"), \
         patch("app.slack.season_recap.get_slack_client",
               return_value=client):
        result = post_season_recap(_stats())
    assert result["success"] is True
    kwargs = client.chat_postMessage.call_args.kwargs
    assert kwargs["channel"] == "C123"
    assert kwargs["blocks"]
    assert kwargs["text"]


def test_post_never_raises(app):
    from app.slack.season_recap import post_season_recap
    with app.app_context(), \
         patch("app.slack.season_recap.get_channel_id_by_name",
               side_effect=RuntimeError("slack down")):
        result = post_season_recap(_stats())
    assert result["success"] is False
    assert "slack down" in result["error"]


def test_post_unknown_channel(app):
    from app.slack.season_recap import post_season_recap
    with app.app_context(), \
         patch("app.slack.season_recap.get_channel_id_by_name",
               return_value=None):
        result = post_season_recap(_stats(), channel_override="nope")
    assert result["success"] is False
    assert "nope" in result["error"]
