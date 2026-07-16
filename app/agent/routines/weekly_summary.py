"""Post the coming Monday-through-Sunday practice summary."""

import logging
from datetime import date, datetime, time, timedelta

from app.agent.decision_engine import load_skipper_config
from app.integrations.weather import get_weather_for_location
from app.models import db
from app.practices.interfaces import PracticeStatus
from app.practices.models import Practice
from app.practices.service import convert_practice_to_info
from app.slack.blocks import (
    build_weekly_summary_blocks,
    build_weekly_summary_fallback_text,
)
from app.slack.client import get_channel_id_by_name, get_slack_client
from app.slack.practices._config import _get_announcement_channel
from app.slack.practices.announcements import _delete_slack_message
from app.slack.practices.summary_posts import (
    WEEKLY_SUMMARY,
    stage_summary_post,
)
from app.utils import now_central_naive


logger = logging.getLogger(__name__)


def _upcoming_monday(now):
    days_ahead = (-now.weekday()) % 7
    return (now + timedelta(days=days_ahead)).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )


def _normalize_week_start(value):
    start = (
        value
        if isinstance(value, datetime)
        else datetime.combine(value, time.min)
    )
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    if start.weekday() != 0:
        raise ValueError("week_start must be a Monday")
    return start


def run_weekly_summary(
    channel_override: str | None = None,
    *,
    week_start: date | datetime | None = None,
) -> dict:
    """Build and optionally post the coming calendar-week summary."""
    start = _normalize_week_start(
        week_start or _upcoming_monday(now_central_naive())
    )
    end = start + timedelta(days=7)
    config = load_skipper_config()
    dry_run = config.get("agent", {}).get("dry_run", True)
    practices = Practice.query.filter(
        Practice.date >= start,
        Practice.date < end,
        Practice.status.in_(
            [
                PracticeStatus.SCHEDULED.value,
                PracticeStatus.CONFIRMED.value,
                PracticeStatus.CANCELLED.value,
            ]
        ),
    ).order_by(Practice.date, Practice.id).all()

    weather_data = {}
    for practice in practices:
        if practice.status == PracticeStatus.CANCELLED.value:
            continue
        location = practice.location
        if not (
            location
            and location.latitude is not None
            and location.longitude is not None
        ):
            continue
        try:
            weather = get_weather_for_location(
                lat=location.latitude,
                lon=location.longitude,
                target_datetime=practice.date,
            )
            weather_data[practice.id] = {
                "temp_f": weather.temperature_f,
                "conditions": weather.conditions_summary,
            }
        except Exception as exc:
            logger.warning(
                "Weekly weather fetch failed for practice #%s: %s",
                practice.id,
                exc,
            )

    infos = [convert_practice_to_info(practice) for practice in practices]
    blocks = build_weekly_summary_blocks(
        infos,
        week_start=start.date(),
        weather_data=weather_data,
    )
    fallback = build_weekly_summary_fallback_text(
        infos,
        week_start=start.date(),
        weather_data=weather_data,
    )
    result = {
        "dry_run": dry_run,
        "week_start": start.isoformat(),
        "week_end": end.isoformat(),
        "practice_count": len(practices),
        "fallback": fallback,
    }
    if dry_run:
        return result

    try:
        channel_id = (
            get_channel_id_by_name(channel_override.lstrip("#"))
            if channel_override
            else _get_announcement_channel()
        )
        if not channel_id:
            return {
                **result,
                "slack_posted": False,
                "slack_error": "Channel not found",
                "refresh_linked": False,
            }
        client = get_slack_client()
        response = client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text=fallback,
        )
        message_ts = response.get("ts")
        if not message_ts:
            return {
                **result,
                "slack_posted": False,
                "slack_error": "Slack returned no message timestamp",
                "refresh_linked": False,
            }
        if channel_override:
            return {
                **result,
                "slack_posted": True,
                "slack_message_ts": message_ts,
                "refresh_linked": False,
            }
        original_timestamps = {
            practice.id: practice.slack_weekly_summary_ts
            for practice in practices
        }

        def apply_links():
            stage_summary_post(
                value=start.date(),
                surface=WEEKLY_SUMMARY,
                channel_id=channel_id,
                message_ts=message_ts,
                practices=practices,
            )

        def restore_originals():
            for practice in practices:
                practice.slack_weekly_summary_ts = original_timestamps[
                    practice.id
                ]

        try:
            apply_links()
            db.session.commit()
        except Exception as exc:
            try:
                db.session.rollback()
            except Exception:
                logger.warning(
                    "Could not roll back weekly summary timestamp links",
                    exc_info=True,
                )
            restore_originals()
            cleanup = _delete_slack_message(
                client,
                channel=channel_id,
                ts=message_ts,
            )
            failure = {
                **result,
                "slack_posted": False,
                "slack_error": str(exc),
                "refresh_linked": False,
                "cleanup": cleanup,
            }
            if cleanup.get("success"):
                return failure

            try:
                apply_links()
                db.session.commit()
            except Exception as recovery_error:
                try:
                    db.session.rollback()
                except Exception:
                    logger.warning(
                        "Could not roll back weekly summary recovery link",
                        exc_info=True,
                    )
                restore_originals()
                logger.critical(
                    "Ambiguous Slack orphan after weekly summary links: "
                    "channel=%s ts=%s; initial_error=%s recovery_error=%s",
                    channel_id,
                    message_ts,
                    exc,
                    recovery_error,
                )
                failure["slack_error"] = (
                    f"{exc}; recovery commit failed: {recovery_error}"
                )
                failure["ambiguous_orphan"] = {
                    "channel_id": channel_id,
                    "message_ts": message_ts,
                }
                return failure

            return {
                **result,
                "slack_posted": True,
                "slack_message_ts": message_ts,
                "refresh_linked": True,
                "recovered": True,
                "cleanup": cleanup,
            }
        return {
            **result,
            "slack_posted": True,
            "slack_message_ts": message_ts,
            "refresh_linked": True,
        }
    except Exception as exc:
        logger.exception("Failed to post weekly summary")
        return {
            **result,
            "slack_posted": False,
            "slack_error": str(exc),
            "refresh_linked": False,
        }
