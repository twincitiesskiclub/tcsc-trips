"""Letter emoji supply and pre-flight validation."""

from unittest.mock import MagicMock, patch

import pytest
from slack_sdk.errors import SlackApiError

from app.practices.availability_emoji import (
    EmojiSupplyError,
    done_emoji,
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
        assert done_emoji() not in letter_emoji(26)


def test_done_emoji_reads_the_config_key(app):
    """config/practices.yaml defines lead_availability.done_emoji, and this
    module's whole argument is that the emoji set lives in config because a
    rename once broke a live poll — so editing the key must actually change
    the emoji, not silently do nothing against a hardcoded constant."""
    with patch(
        "app.slack.practices._config._load_practice_config",
        return_value={"lead_availability": {"done_emoji": "TEST_custom_done"}},
    ):
        assert done_emoji() == "TEST_custom_done"


def test_done_emoji_falls_back_to_white_check_mark(app):
    with patch(
        "app.slack.practices._config._load_practice_config",
        return_value={},
    ):
        assert done_emoji() == "white_check_mark"


def test_configured_done_emoji_reaches_the_poll_message(app):
    """The consumer-side proof: the poll's instruction line must render the
    CONFIGURED done emoji, not a hardcoded one."""
    from app.slack.blocks.availability import build_poll_blocks

    with patch(
        "app.slack.practices._config._load_practice_config",
        return_value={"lead_availability": {"done_emoji": "TEST_custom_done"}},
    ):
        blocks = build_poll_blocks([], "Aug 1", "Aug 31")

    instruction = blocks[1]["elements"][0]["text"]
    assert ":TEST_custom_done:" in instruction
    assert ":white_check_mark:" not in instruction


def test_configured_custom_done_emoji_is_validated_like_any_custom_emoji(app):
    """white_check_mark is skipped from validation because it's native and
    emoji.list never returns it — but a CUSTOM done emoji from config must be
    validated, or a typo'd config value ships an unanswerable poll."""
    client = MagicMock()
    client.emoji_list.return_value = {"emoji": {"letter_a": "u"}}

    with patch("app.practices.availability_emoji.get_slack_client", return_value=client):
        with app.app_context():
            ok, missing = validate_emoji_available(["letter_a", "TEST_custom_done"])

    assert ok is False
    assert missing == ["TEST_custom_done"]


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


def test_missing_token_refuses_rather_than_raises(app):
    """get_slack_client() raises ValueError when SLACK_BOT_TOKEN isn't configured.

    That call happens inside the try block, but ValueError is not a
    SlackApiError -- without a catch-all backstop it propagates and crashes
    the poll-open path instead of refusing.
    """
    with patch(
        "app.practices.availability_emoji.get_slack_client",
        side_effect=ValueError("SLACK_BOT_TOKEN not configured"),
    ):
        with app.app_context():
            ok, missing = validate_emoji_available(["letter_a", "letter_b"])

    assert ok is False
    assert missing == ["letter_a", "letter_b"]


def test_transport_failure_refuses_rather_than_raises(app):
    """slack_sdk re-raises raw transport errors (e.g. TimeoutError) unwrapped.

    Only SlackApiError originally had a catch here, so a network timeout
    would propagate instead of yielding the promised refusal.
    """
    client = MagicMock()
    client.emoji_list.side_effect = TimeoutError("connection timed out")

    with patch("app.practices.availability_emoji.get_slack_client", return_value=client):
        with app.app_context():
            ok, missing = validate_emoji_available(["letter_a", "letter_b"])

    assert ok is False
    assert missing == ["letter_a", "letter_b"]
