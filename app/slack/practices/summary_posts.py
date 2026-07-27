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
READINESS_DIGEST = "readiness_digest"
# The two Monday-anchored weekly surfaces served by find/stage_summary_post.
# READINESS_DIGEST is deliberately excluded: it is block-anchored (see the
# dedicated helpers below), so passing it through the week-normalising helpers
# would silently move its anchor.
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


def find_readiness_digest_post(block_start: date) -> PracticeSummaryPost | None:
    """The digest post for the draft block starting on block_start.

    A readiness digest belongs to a 4-week draft *block*, not a single week,
    so despite the column name, week_start stores the block's start date
    verbatim — no Monday normalisation.
    """
    return PracticeSummaryPost.query.filter_by(
        week_start=block_start, surface=READINESS_DIGEST
    ).one_or_none()


def stage_readiness_digest_post(
    *,
    block_start: date,
    channel_id: str,
    message_ts: str,
) -> PracticeSummaryPost:
    """Upsert the digest's Slack identity for a block. Never commits."""
    record = find_readiness_digest_post(block_start)
    if record is None:
        record = PracticeSummaryPost(
            week_start=block_start, surface=READINESS_DIGEST
        )
        db.session.add(record)
    record.channel_id = channel_id
    record.message_ts = message_ts
    return record


def summary_post_channel(record: PracticeSummaryPost) -> str | None:
    if record.channel_id:
        return record.channel_id
    if record.surface == COACH_SUMMARY:
        return COLLAB_CHANNEL_ID
    if record.surface == WEEKLY_SUMMARY:
        return _get_announcement_channel()
    raise ValueError(f"Unknown practice summary surface: {record.surface}")
