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
    parts = []
    for block in blocks:
        text = block.get("text")
        if isinstance(text, dict):
            parts.append(text.get("text", ""))
    return "\n".join(parts)


def test_blocks_render_every_section():
    from app.slack.season_recap import build_recap_blocks
    blocks, fallback = build_recap_blocks(_stats())
    text = _all_text(blocks)
    assert "3 registrations" in text          # yesterday
    assert "142" in text                       # season total
    assert "71%" in text                       # cap progress
    assert "day 5 of 21" in text               # window pace
    assert "Winter 2097" in text               # prior season
    assert "118" in text
    assert "Lead a group at practice" in text  # volunteer
    assert "Biggest day" in text               # highlight
    assert "142" in fallback


def test_blocks_omit_empty_sections():
    from app.slack.season_recap import build_recap_blocks
    blocks, _ = build_recap_blocks(_stats(
        prior_season=None,
        volunteer={"answered": 0, "of": 0, "interests": {}, "committees": {}},
        highlights=[],
        needs_review=0,
    ))
    text = _all_text(blocks)
    assert "Winter 2097" not in text
    assert "Get Involved" not in text
    assert "need review" not in text


def test_needs_review_warning_renders_with_link():
    from app.slack.season_recap import build_recap_blocks
    blocks, _ = build_recap_blocks(_stats(needs_review=4))
    text = _all_text(blocks)
    assert "4" in text
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
