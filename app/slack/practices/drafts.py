"""Posting the monthly draft readiness digest."""

from flask import current_app
from slack_sdk.errors import SlackApiError

from app.practices.drafting import readiness_summary
from app.slack.blocks.practice_drafts import build_readiness_digest_blocks
from app.slack.client import get_slack_client
from app.slack.practices._config import COLLAB_CHANNEL_ID


def post_readiness_digest(practices: list, start_label: str, end_label: str) -> dict:
    """Post the digest to the coaches/directors channel.

    Never raises — a Slack outage must not fail the drafting job that produced
    perfectly good practices.
    """
    if not practices:
        return {"success": False, "error": "no practices to report"}

    summary = readiness_summary(practices)
    blocks = build_readiness_digest_blocks(summary, start_label, end_label)
    fallback = (
        f"{summary['total']} practices drafted for {start_label} – {end_label}: "
        f"{summary['ready']} ready, {len(summary['incomplete'])} need details"
    )

    try:
        response = get_slack_client().chat_postMessage(
            channel=COLLAB_CHANNEL_ID,
            blocks=blocks,
            text=fallback,
        )
        return {"success": True, "ts": response["ts"]}
    except SlackApiError as exc:
        error = exc.response.get("error", str(exc))
        current_app.logger.error("Readiness digest failed to post: %s", error)
        return {"success": False, "error": error}
