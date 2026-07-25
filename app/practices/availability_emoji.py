"""Letter emoji supply and pre-flight validation for availability polls.

The letter emoji (:letter_a: .. :letter_z:) are custom workspace emoji, not
native Slack ones -- :regional_indicator_a: and :alphabet-white-a: don't
exist in Slack at all, and native keycap numbers stop being ordered after
:nine:. The club uploaded A-Z as custom emoji, first named
`regional_indicator_*`, then renamed to `letter_*`. That rename silently
broke a live poll that had been posted minutes earlier.

Hence the two rules this module enforces:
- The emoji set lives in config (`config/practices.yaml`), never hardcoded.
- A poll must refuse to open if any of its emoji are missing or unverifiable
  -- posting a poll nobody can answer is worse than posting nothing.
"""

import os
from typing import Optional

import yaml
from flask import current_app
from slack_sdk.errors import SlackApiError

from app.slack.client import get_slack_client

FALLBACK_LETTERS = [f"letter_{c}" for c in "abcdefghijklmnopqrstuvwxyz"]
DONE_EMOJI = "white_check_mark"

# emoji.list only returns CUSTOM workspace emoji -- native emoji like
# white_check_mark are never in that response and must not be reported
# missing just because they're absent from it.
NATIVE_EMOJI = {DONE_EMOJI}

# Module-level config cache (loaded once per process), matching the pattern
# in app/slack/practices/_config.py.
_config_cache: Optional[dict] = None


def _load_config() -> dict:
    """Load the lead_availability section of practices.yaml (cached after first load)."""
    global _config_cache
    if _config_cache is None:
        path = os.path.join(
            os.path.dirname(__file__), "..", "..", "config", "practices.yaml"
        )
        with open(path, "r", encoding="utf-8") as handle:
            _config_cache = yaml.safe_load(handle) or {}
    return _config_cache


def reload_config() -> dict:
    """Force reload of config from disk (useful for testing or config changes)."""
    global _config_cache
    _config_cache = None
    return _load_config()


class EmojiSupplyError(RuntimeError):
    """Raised when a poll needs more distinct emoji than are configured."""


def letter_emoji(count: int) -> list[str]:
    """Return the first `count` configured letter emoji names, in order.

    Raises EmojiSupplyError rather than silently truncating or reusing an
    emoji across two sessions -- a poll needs one distinct emoji per
    session, and running short is a configuration problem to fix, not
    something to paper over.
    """
    letters = (
        _load_config().get("lead_availability", {}).get("letter_emoji") or FALLBACK_LETTERS
    )
    if count > len(letters):
        raise EmojiSupplyError(
            f"poll needs {count} distinct emoji but only {len(letters)} are configured; "
            "add more to config/practices.yaml lead_availability.letter_emoji "
            "or split the block into shorter polls"
        )
    return list(letters[:count])


def validate_emoji_available(names: list[str]) -> tuple[bool, list[str]]:
    """Check every custom emoji in `names` actually exists before a poll opens.

    Native emoji (currently just DONE_EMOJI) are skipped, since emoji.list
    never returns them and they'd otherwise always be reported as missing.

    If emoji.list itself can't be reached, that is an unverifiable state,
    not a pass -- we refuse (ok=False) and report every requested custom
    emoji as unverified, rather than assuming they're all fine.
    """
    custom = [name for name in names if name not in NATIVE_EMOJI]
    if not custom:
        return True, []

    try:
        available = set(get_slack_client().emoji_list().get("emoji", {}).keys())
    except SlackApiError as exc:
        current_app.logger.error(
            "emoji.list failed (%s); refusing to open a poll unverified",
            exc.response.get("error", exc),
        )
        return False, custom
    except Exception as exc:
        current_app.logger.error(
            "emoji.list failed (%s); refusing to open a poll unverified", exc
        )
        return False, custom

    missing = [name for name in custom if name not in available]
    return (not missing), missing
