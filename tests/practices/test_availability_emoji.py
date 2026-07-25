"""Letter emoji supply and pre-flight validation."""

from unittest.mock import MagicMock, patch

import pytest
from slack_sdk.errors import SlackApiError

from app.practices.availability_emoji import (
    DONE_EMOJI,
    EmojiSupplyError,
    letter_emoji,
    validate_emoji_available,
)


def test_letter_emoji_returns_configured_names_in_order(app):
    with app.app_context():
        assert letter_emoji(3) == ["letter_a", "letter_b", "letter_c"]


def test_letter_emoji_refuses_to_run_short(app):
    with app.app_context():
        with pytest.raises(EmojiSupplyError) as exc:
            letter_emoji(99)
    assert "99" in str(exc.value)


def test_done_emoji_is_never_a_session(app):
    with app.app_context():
        assert DONE_EMOJI not in letter_emoji(26)


def test_validation_reports_missing_emoji(app):
    client = MagicMock()
    client.emoji_list.return_value = {"emoji": {"letter_a": "https://x/a.png"}}

    with patch("app.practices.availability_emoji.get_slack_client", return_value=client):
        with app.app_context():
            ok, missing = validate_emoji_available(["letter_a", "letter_b"])

    assert ok is False
    assert missing == ["letter_b"]


def test_validation_passes_when_all_present(app):
    client = MagicMock()
    client.emoji_list.return_value = {
        "emoji": {"letter_a": "u", "letter_b": "u", "white_check_mark": "u"}
    }

    with patch("app.practices.availability_emoji.get_slack_client", return_value=client):
        with app.app_context():
            ok, missing = validate_emoji_available(["letter_a", "letter_b"])

    assert ok is True
    assert missing == []


def test_native_emoji_are_not_reported_missing(app):
    """emoji.list only returns CUSTOM emoji; native ones must not fail validation."""
    client = MagicMock()
    client.emoji_list.return_value = {"emoji": {"letter_a": "u"}}

    with patch("app.practices.availability_emoji.get_slack_client", return_value=client):
        with app.app_context():
            ok, missing = validate_emoji_available(["letter_a", "white_check_mark"])

    assert ok is True, "white_check_mark is native and is not in emoji.list"


def test_unreachable_emoji_list_refuses_rather_than_passes(app):
    """An API failure is an unverifiable state, not a green light.

    If emoji.list can't be reached, we must not assume the emoji exist -- a
    poll opened on that basis could be the exact silent failure that broke
    a live poll before. Refuse (ok=False) and report every requested custom
    emoji as unverified/missing, rather than defaulting to "everything is
    fine".
    """
    client = MagicMock()
    client.emoji_list.side_effect = SlackApiError(
        message="internal_error", response=MagicMock(data={"error": "internal_error"})
    )

    with patch("app.practices.availability_emoji.get_slack_client", return_value=client):
        with app.app_context():
            ok, missing = validate_emoji_available(["letter_a", "letter_b"])

    assert ok is False
    assert missing == ["letter_a", "letter_b"]
