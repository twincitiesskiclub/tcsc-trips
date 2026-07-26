"""Send the availability reminder DM.

Every Slack call here catches both `SlackApiError` and a generic `Exception`
backstop: `get_slack_client()` raises a bare `ValueError` when
`SLACK_BOT_TOKEN` is unset, and transport failures raise `TimeoutError` --
neither is a `SlackApiError`. A failed DM to one person must never abort the
run for everyone else, and must never consume that person's nudge budget
(the caller only advances `nudge_count`/`last_nudged_at` on a `True` return).
"""

from flask import current_app
from slack_sdk.errors import SlackApiError

from app.slack.blocks.availability import build_nudge_blocks
from app.slack.client import get_slack_client


def poll_permalink(poll) -> str | None:
    """Best-effort permalink for the "Go to post" button. None on any failure
    -- the nudge DM must still send without it (see build_nudge_blocks).
    """
    try:
        return get_slack_client().chat_getPermalink(
            channel=poll.channel_id, message_ts=poll.message_ts)["permalink"]
    except SlackApiError as exc:
        current_app.logger.warning(
            "No permalink for poll %s: %s", poll.id, exc.response.get("error", exc))
        return None
    except Exception as exc:  # noqa: BLE001 - ValueError (no token) / TimeoutError etc.
        current_app.logger.warning("No permalink for poll %s: %s", poll.id, exc)
        return None


def send_nudge_dm(poll, slack_uid: str, permalink: str | None) -> bool:
    """DM one participant. Returns False on any failure without raising, so
    the caller's loop keeps going for the remaining participants.
    """
    start_label = poll.starts_on.strftime("%b %-d")
    end_label = poll.ends_on.strftime("%b %-d")
    blocks = build_nudge_blocks(start_label, end_label, poll.channel_id, permalink,
                                done=poll.resolved_done_emoji)
    fallback = f"Reminder: provide lead availability for {start_label} – {end_label}"

    try:
        get_slack_client().chat_postMessage(
            channel=slack_uid, blocks=blocks, text=fallback)
        return True
    except SlackApiError as exc:
        current_app.logger.warning(
            "Nudge DM to %s failed: %s", slack_uid, exc.response.get("error", exc))
        return False
    except Exception as exc:  # noqa: BLE001 - ValueError (no token) / TimeoutError etc.
        current_app.logger.warning("Nudge DM to %s failed: %s", slack_uid, exc)
        return False
