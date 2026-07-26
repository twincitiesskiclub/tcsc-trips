"""Posting the monthly draft readiness digest."""

from datetime import date

from flask import current_app
from slack_sdk.errors import SlackApiError

from app.models import db
from app.practices.drafting import readiness_summary
from app.slack.blocks.practice_drafts import build_readiness_digest_blocks
from app.slack.client import get_slack_client
from app.slack.practices._config import COLLAB_CHANNEL_ID
from app.slack.practices.summary_posts import (
    find_readiness_digest_post,
    stage_readiness_digest_post,
)


def post_readiness_digest(
    practices: list,
    start_label: str,
    end_label: str,
    *,
    block_start: date | None = None,
) -> dict:
    """Post the digest to the coaches/directors channel.

    When ``block_start`` is given, the digest's Slack identity is kept per
    draft block: if a digest is already on record for the block, this posts a
    reply in its thread (the daily nudge — threaded so it doesn't spam the
    channel); otherwise it posts top-level and records channel + ts so the
    next day's nudge can thread onto it. That fallback also covers blocks
    whose original digest failed to post (or predates this bookkeeping) —
    the chase must never silently stop.

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
        channel = COLLAB_CHANNEL_ID
        thread_ts = None
        if block_start is not None:
            record = find_readiness_digest_post(block_start)
            if record is not None:
                channel = record.channel_id or COLLAB_CHANNEL_ID
                thread_ts = record.message_ts

        kwargs = {"channel": channel, "blocks": blocks, "text": fallback}
        if thread_ts is not None:
            kwargs["thread_ts"] = thread_ts

        response = get_slack_client().chat_postMessage(**kwargs)
        ts = response["ts"]
    except SlackApiError as exc:
        error = exc.response.get("error", str(exc))
        current_app.logger.error("Readiness digest failed to post: %s", error)
        return {"success": False, "error": error}
    except Exception as exc:
        current_app.logger.error("Readiness digest failed to post: %s", exc)
        return {"success": False, "error": str(exc)}
    if block_start is not None and thread_ts is None:
        # Remember the top-level digest so tomorrow's nudge threads onto it.
        try:
            stage_readiness_digest_post(
                block_start=block_start, channel_id=channel, message_ts=ts
            )
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.warning(
                "Readiness digest posted but its identity could not be "
                "recorded; the next nudge will post top-level again",
                exc_info=True,
            )
    return {"success": True, "ts": ts}
