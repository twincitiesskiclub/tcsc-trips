"""Canonical weekly practice-summary Slack identities."""

from datetime import date, datetime, timedelta

from app.models import db
from app.practices.models import PracticeSummaryPost
from app.slack.practices._config import (
    COLLAB_CHANNEL_ID,
    _get_announcement_channel,
)


COACH_SUMMARY = "coach_summary"
WEEKLY_SUMMARY = "weekly_summary"
SUMMARY_SURFACES = (COACH_SUMMARY, WEEKLY_SUMMARY)
_LEGACY_TS_FIELDS = {
    COACH_SUMMARY: "slack_coach_summary_ts",
    WEEKLY_SUMMARY: "slack_weekly_summary_ts",
}


def week_start_date(value: date | datetime) -> date:
    day = value.date() if isinstance(value, datetime) else value
    return day - timedelta(days=day.weekday())


def find_summary_post(
    value: date | datetime,
    surface: str,
) -> PracticeSummaryPost | None:
    if surface not in SUMMARY_SURFACES:
        raise ValueError(f"Unknown practice summary surface: {surface}")
    return PracticeSummaryPost.query.filter_by(
        week_start=week_start_date(value), surface=surface
    ).one_or_none()


def stage_summary_post(
    *,
    value: date | datetime,
    surface: str,
    channel_id: str,
    message_ts: str,
    practices=(),
) -> PracticeSummaryPost:
    record = find_summary_post(value, surface)
    if record is None:
        record = PracticeSummaryPost(
            week_start=week_start_date(value), surface=surface
        )
        db.session.add(record)
    record.channel_id = channel_id
    record.message_ts = message_ts
    field = _LEGACY_TS_FIELDS[surface]
    for practice in practices:
        setattr(practice, field, message_ts)
    return record


def summary_post_channel(record: PracticeSummaryPost) -> str | None:
    if record.channel_id:
        return record.channel_id
    if record.surface == COACH_SUMMARY:
        return COLLAB_CHANNEL_ID
    if record.surface == WEEKLY_SUMMARY:
        return _get_announcement_channel()
    raise ValueError(f"Unknown practice summary surface: {record.surface}")
