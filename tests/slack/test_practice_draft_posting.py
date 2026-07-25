"""Readiness digest posting."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def _practice(day):
    # readiness_summary() (Task 4) reads location_id/practice_types/activities
    # off the practice, not `location` — using the real attribute names here
    # so post_readiness_digest's call into it doesn't AttributeError.
    return SimpleNamespace(
        id=day, date=datetime(2026, 8, day, 18, 15),
        location_id=None, practice_types=[], activities=[],
    )


def test_posts_to_the_coaches_channel(app):
    from app.slack.practices.drafts import post_readiness_digest

    client = MagicMock()
    client.chat_postMessage.return_value = {"ok": True, "ts": "1785000000.1"}

    with patch("app.slack.practices.drafts.get_slack_client", return_value=client):
        with app.app_context():
            result = post_readiness_digest([_practice(4)], "Jul 21", "Aug 13")

    assert result["success"] is True
    assert result["ts"] == "1785000000.1"
    kwargs = client.chat_postMessage.call_args.kwargs
    from app.slack.practices._config import COLLAB_CHANNEL_ID
    assert kwargs["channel"] == COLLAB_CHANNEL_ID
    assert kwargs["blocks"], "digest must carry blocks"
    assert kwargs["text"], "fallback text is required for notifications and screen readers"


def test_slack_failure_is_reported_not_raised(app):
    from slack_sdk.errors import SlackApiError

    from app.slack.practices.drafts import post_readiness_digest

    client = MagicMock()
    client.chat_postMessage.side_effect = SlackApiError(
        "boom", response={"error": "channel_not_found"}
    )

    with patch("app.slack.practices.drafts.get_slack_client", return_value=client):
        with app.app_context():
            result = post_readiness_digest([_practice(4)], "Jul 21", "Aug 13")

    assert result["success"] is False
    assert result["error"] == "channel_not_found"


def test_non_slack_failure_is_reported_not_raised(app):
    from app.slack.practices.drafts import post_readiness_digest

    client = MagicMock()
    client.chat_postMessage.side_effect = TimeoutError("connection timed out")

    with patch("app.slack.practices.drafts.get_slack_client", return_value=client):
        with app.app_context():
            result = post_readiness_digest([_practice(4)], "Jul 21", "Aug 13")

    assert result["success"] is False
    assert "connection timed out" in result["error"]


def test_empty_practice_list_posts_nothing(app):
    from app.slack.practices.drafts import post_readiness_digest

    client = MagicMock()
    with patch("app.slack.practices.drafts.get_slack_client", return_value=client):
        with app.app_context():
            result = post_readiness_digest([], "Jul 21", "Aug 13")

    assert result["success"] is False
    client.chat_postMessage.assert_not_called()
