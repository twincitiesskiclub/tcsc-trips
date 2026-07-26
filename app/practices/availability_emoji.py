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

from flask import current_app
from slack_sdk.errors import SlackApiError

from app.slack.client import get_slack_client

FALLBACK_LETTERS = [f"letter_{c}" for c in "abcdefghijklmnopqrstuvwxyz"]
DEFAULT_DONE_EMOJI = "white_check_mark"

# emoji.list only returns CUSTOM workspace emoji -- native emoji like
# white_check_mark are never in that response and must not be reported
# missing just because they're absent from it. A CUSTOM done emoji set via
# config is deliberately NOT in this set: it must be validated like any
# other custom emoji, or a typo'd config value ships an unanswerable poll.
NATIVE_EMOJI = {DEFAULT_DONE_EMOJI}

# Slack caps the reactions ONE user may add to a single message at 23, and
# open_poll seeds every letter plus the done emoji as the bot. Past the cap
# reactions.add fails with `too_many_reactions`, which the seeding loop only
# warns about -- so the poll shipped with no pill on its tail sessions and
# still reported success. Leads can technically still add those reactions from
# the picker (each person has their own budget), but a session with no visible
# pill on a message where every other line has one reads as "not an option".
#
# 22 letters + 1 done emoji = the 23 the bot may add. The drafting horizon
# reaches ~61 days, which on a Tue/Thu/Sat schedule is up to 27 sessions, so
# this is reachable by polling a whole drafted block -- the design assumed
# ~12-session blocks. Refusing names the fix, and splitting the block into two
# polls is the intended answer.
MAX_SEEDED_REACTIONS = 23
MAX_POLL_SESSIONS = MAX_SEEDED_REACTIONS - 1


def _practice_config() -> dict:
    """The shared practices.yaml config, via the one process-wide cache.

    Reuses _config.py's cache instead of keeping a second module-level copy
    of practices.yaml here: two caches meant that wiring reload_config on
    one side only would silently leave the other serving stale values.
    Imported lazily because app.slack.practices.__init__ imports modules
    (availability_reactions) that import this module back -- same pattern
    as _target_channel in app/practices/availability.py.
    """
    from app.slack.practices._config import _load_practice_config

    return _load_practice_config()


def done_emoji() -> str:
    """The "that's everything from me" emoji, from config.

    config/practices.yaml lead_availability.done_emoji, falling back to the
    native white_check_mark. Read from config for the same reason the letter
    emoji are: a rename once silently broke a live poll, and a config key
    nothing reads is worse than no key at all.
    """
    value = _practice_config().get("lead_availability", {}).get("done_emoji")
    return str(value) if value else DEFAULT_DONE_EMOJI


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
        _practice_config().get("lead_availability", {}).get("letter_emoji")
        or FALLBACK_LETTERS
    )
    if count > len(letters):
        raise EmojiSupplyError(
            f"poll needs {count} distinct emoji but only {len(letters)} are configured; "
            "add more to config/practices.yaml lead_availability.letter_emoji "
            "or split the block into shorter polls"
        )
    # Configuring 26 letters isn't enough on its own: the bot can only put 23
    # reactions on one message, so beyond MAX_POLL_SESSIONS the tail sessions
    # would post with no pill and open_poll would still report success. Refuse
    # here, where the number is known and the message can name the real fix.
    if count > MAX_POLL_SESSIONS:
        raise EmojiSupplyError(
            f"poll covers {count} sessions but Slack lets the bot seed only "
            f"{MAX_SEEDED_REACTIONS} reactions on one message "
            f"({MAX_POLL_SESSIONS} sessions plus the done emoji); the sessions "
            "past that would post with no reaction pill. Split the block into "
            "two shorter polls"
        )
    return list(letters[:count])


def validate_emoji_available(names: list[str]) -> tuple[bool, list[str]]:
    """Check every custom emoji in `names` actually exists before a poll opens.

    Native emoji (currently just white_check_mark, the default done emoji)
    are skipped, since emoji.list never returns them and they'd otherwise
    always be reported as missing.

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
