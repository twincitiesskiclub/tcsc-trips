"""Centralized Slack post refresh for practices.

When a practice is modified in the database, call refresh_practice_posts()
to update ALL related Slack posts (announcement, collab review, coach
summary, weekly summary, edit logs).
"""

import logging
from datetime import date, datetime, time, timedelta

from sqlalchemy import update
from sqlalchemy.orm.attributes import set_committed_value

from app.practices.models import Practice, PracticeSummaryPost
from app.slack.practices.summary_posts import (
    COACH_SUMMARY,
    WEEKLY_SUMMARY,
    find_summary_post,
    summary_post_channel,
    week_start_date,
)

logger = logging.getLogger(__name__)

# Change types that any surface may react to.
ALL_CHANGE_TYPES = ("edit", "cancel", "delete", "rsvp", "workout", "create")


class PracticeSurface:
    """A Slack surface that displays practice info and can be refreshed.

    Adding a new surface (e.g. a future lead-scheduling DM) is one registry
    entry — no changes to refresh_practice_posts() or any call site.
    """

    def __init__(self, name, ts_field, applies_to, refresh_fn):
        self.name = name
        self.ts_field = ts_field
        self.applies_to = set(applies_to)
        self._refresh_fn = refresh_fn

    def is_present(self, practice):
        return self.ts_field is None or bool(
            getattr(practice, self.ts_field, None)
        )

    def refresh(self, practice, change_type, **context):
        if change_type not in self.applies_to:
            return {"skipped": "not_applicable"}
        if not self.is_present(practice):
            # The post exists in Slack but this practice isn't linked to it
            # (e.g. created out-of-band after the post). Distinguished from a
            # not-applicable change type so it can be logged as a real gap.
            return {"skipped": "absent"}
        return self._refresh_fn(practice, change_type, **context)


def _week_bounds(value):
    """Return Monday-anchored datetime bounds for a date or datetime."""
    start = datetime.combine(week_start_date(value), time.min)
    return start, start + timedelta(days=7)


def refresh_practice_posts(
    practice,
    change_type='edit',
    actor_slack_id=None,
    notify=True,
    announcement_notice=None,
    previous_plan_reactions=None,
    previous_date=None,
):
    """Update all Slack posts for a practice after DB changes.

    Args:
        practice: Practice model instance (already committed to DB)
        change_type: 'edit' | 'cancel' | 'delete' | 'rsvp' | 'workout' | 'create'
        actor_slack_id: Slack UID of person who made the change (for edit logs)
        notify: Whether to post thread notifications (edit logs)
        previous_date: Date before an edit, used to refresh a distinct source
            week when the practice crosses a Monday boundary

    Returns:
        dict with results per post type, e.g.:
        {
            'announcement': {'success': True},
            'collab': {'success': True},
            'coach_summary': {'success': False, 'error': '...'},
            'weekly_summary': {'skipped': True},
        }
    """
    context = {
        "announcement_notice": announcement_notice,
        "previous_plan_reactions": previous_plan_reactions,
    }
    results = {}
    had_announcement = bool(practice.slack_message_ts)
    for index, surface in enumerate(PRACTICE_SURFACES):
        result = surface.refresh(practice, change_type, **context)
        results[surface.name] = result
        if (
            change_type == "delete"
            and surface.name == "announcement"
            and had_announcement
            and result.get("success") is not True
        ):
            for blocked in PRACTICE_SURFACES[index + 1:]:
                results[blocked.name] = {
                    "skipped": "blocked_by_announcement"
                }
            break

    if (
        change_type == "edit"
        and previous_date is not None
        and week_start_date(previous_date) != week_start_date(practice.date)
    ):
        previous_results = refresh_registered_practice_summaries(
            previous_date
        )
        results["previous_coach_summary"] = previous_results[
            "coach_summary"
        ]
        results["previous_weekly_summary"] = previous_results[
            "weekly_summary"
        ]

    safety_note_posted = False
    announcement_result = results.get("announcement", {})
    if (
        announcement_notice
        and announcement_result.get("success") is True
        and practice.slack_message_ts
        and practice.slack_channel_id
    ):
        from app.slack.practices.rsvp import post_thread_reply
        try:
            note_result = post_thread_reply(
                practice,
                announcement_notice,
                user_mention=actor_slack_id,
            )
            if (
                not isinstance(note_result, dict)
                or not isinstance(note_result.get("success"), bool)
            ):
                raise ValueError(
                    "Invalid result from announcement change note post"
                )
        except Exception as exc:
            logger.warning(
                "Practice #%s: announcement change note failed: %s",
                practice.id,
                exc,
            )
            note_result = {"success": False, "error": str(exc)}
        results["announcement_change_note"] = note_result
        safety_note_posted = note_result.get("success") is True

    # Edit logging (thread replies) remains a post-pass keyed on notify + type
    if notify and actor_slack_id and change_type in ('edit', 'workout'):
        results['edit_logs'] = _post_edit_logs(
            practice,
            actor_slack_id,
            skip_announcement=safety_note_posted,
        )

    _log_refresh_results(practice, change_type, results)

    return results


def _log_refresh_results(practice, change_type, results):
    """Surface skipped/failed refreshes instead of letting them pass silently.

    A surface that errors (`success: False`) or has no registered/linked post
    (`skipped: "absent"`) is surfaced for diagnosis. Legitimate applicability
    skips stay quiet.
    """
    errored = [
        name for name, r in results.items()
        if isinstance(r, dict) and r.get('success') is False
    ]
    absent = [
        name for name, r in results.items()
        if isinstance(r, dict) and r.get('skipped') == 'absent'
    ]

    if errored:
        logger.warning(
            "Practice #%s (%s): refresh FAILED for %s — posts may be stale. Details: %s",
            practice.id, change_type, ", ".join(errored),
            {n: results[n] for n in errored},
        )
    if absent:
        logger.warning(
            "Practice #%s (%s): refresh skipped for %s — no linked or "
            "registered post was found.",
            practice.id, change_type, ", ".join(absent),
        )
    if not errored and not absent:
        logger.info(
            "Practice #%s (%s): refresh ok (%s)",
            practice.id, change_type,
            {n: (r.get('skipped') or 'updated') if isinstance(r, dict) else r
             for n, r in results.items()},
        )


def _refresh_announcement(
    practice,
    change_type,
    *,
    announcement_notice=None,
    previous_plan_reactions=None,
    **_context,
):
    """Update the main practice announcement post."""
    if not practice.slack_message_ts:
        return {"success": True, "skipped": "absent"}
    if not practice.slack_channel_id:
        return {"success": False, "error": "Slack message has no channel"}

    try:
        if change_type == 'cancel':
            from app.slack.practices.announcements import (
                is_combined_lift_practice,
                update_combined_lift_post,
            )
            from app.slack.practices.cancellations import (
                post_combined_cancellation_thread_notice,
                update_practice_as_cancelled,
            )
            if is_combined_lift_practice(practice):
                result = update_combined_lift_post(practice)
                if result.get("success"):
                    notice = post_combined_cancellation_thread_notice(practice)
                    if not notice.get("success"):
                        logger.warning(
                            "Combined cancellation root updated but thread note "
                            "failed for #%s: %s",
                            practice.id,
                            notice,
                        )
                return result
            return update_practice_as_cancelled(practice, 'Admin')

        if change_type == 'delete':
            from app.slack.practices.announcements import (
                remove_practice_from_announcement,
            )
            return remove_practice_from_announcement(practice)

        if change_type == 'rsvp':
            from app.slack.practices.rsvp import update_practice_rsvp_counts
            return update_practice_rsvp_counts(practice)

        # For edit, workout, create — rebuild the full announcement.
        # update_practice_slack_post -> update_practice_post also upserts the
        # threaded "Practice Details" reply transitively, so no separate
        # surface registration is needed for the details thread.
        from app.slack.practices.announcements import update_practice_slack_post
        return update_practice_slack_post(
            practice,
            announcement_notice=announcement_notice,
            previous_plan_reactions=previous_plan_reactions,
        )

    except Exception as e:
        logger.warning(f"Failed to refresh announcement for practice #{practice.id}: {e}")
        return {'success': False, 'error': str(e)}


def _refresh_collab(practice, change_type, **_context):
    """Update the collab review post in #collab-coaches-practices."""
    if not practice.slack_collab_message_ts:
        return {'skipped': True}

    try:
        from app.slack.practices.coach_review import update_collab_post
        return update_collab_post(practice)
    except Exception as e:
        logger.warning(f"Failed to refresh collab post for practice #{practice.id}: {e}")
        return {'success': False, 'error': str(e)}


def _persist_summary_channel(record, channel_id):
    """Best-effort legacy channel repair without committing the app session."""
    if record.id is None:
        return

    from app.models import db

    try:
        with db.engine.begin() as connection:
            result = connection.execute(
                update(PracticeSummaryPost)
                .where(
                    PracticeSummaryPost.id == record.id,
                    PracticeSummaryPost.channel_id.is_(None),
                )
                .values(channel_id=channel_id)
            )
        if result.rowcount:
            set_committed_value(record, "channel_id", channel_id)
    except Exception as exc:
        logger.warning(
            "Could not persist legacy summary channel for record #%s: %s",
            record.id,
            exc,
        )


def _refresh_coach_summary_for_week(value, *, exclude_practice_id=None):
    """Rebuild the registered Coach summary for one calendar week."""
    try:
        from app.models import AppConfig
        from app.practices.service import convert_practice_to_info
        from app.slack.blocks import build_coach_weekly_summary_blocks
        from app.slack.client import get_slack_client
        from app.slack.practices._config import (
            COACH_SUMMARY_FALLBACK_CHANNEL_ID,
            COLLAB_CHANNEL_ID,
        )

        record = find_summary_post(value, COACH_SUMMARY)
        if record is None:
            return {"skipped": "absent"}

        week_start, week_end = _week_bounds(value)
        week_query = Practice.query.filter(
            Practice.date >= week_start,
            Practice.date < week_end,
        )
        if exclude_practice_id is not None:
            week_query = week_query.filter(
                Practice.id != exclude_practice_id
            )
        practices_for_week = week_query.order_by(Practice.date).all()

        expected_days = AppConfig.get('practice_days', [
            {"day": "tuesday", "time": "18:00", "active": True},
            {"day": "thursday", "time": "18:00", "active": True},
            {"day": "saturday", "time": "09:00", "active": True}
        ])
        practice_infos = [
            convert_practice_to_info(practice)
            for practice in practices_for_week
        ]
        blocks = build_coach_weekly_summary_blocks(
            practice_infos,
            expected_days,
            week_start,
        )

        resolved_channel = summary_post_channel(record)
        if record.channel_id:
            channels_to_try = [resolved_channel] if resolved_channel else []
        else:
            channels_to_try = []
            for channel in (
                resolved_channel,
                COLLAB_CHANNEL_ID,
                COACH_SUMMARY_FALLBACK_CHANNEL_ID,
            ):
                if channel and channel not in channels_to_try:
                    channels_to_try.append(channel)

        client = get_slack_client()
        for channel in channels_to_try:
            try:
                client.chat_update(
                    channel=channel,
                    ts=record.message_ts,
                    blocks=blocks,
                    text=(
                        "Coach Review: Week of "
                        f"{week_start.strftime('%B %-d')}"
                    ),
                )
            except Exception:
                continue
            if record.channel_id is None:
                _persist_summary_channel(record, channel)
            return {'success': True}

        return {'success': False, 'error': 'Could not update in any channel'}
    except Exception as exc:
        logger.warning(
            "Failed to refresh registered Coach summary for %s: %s",
            value,
            exc,
        )
        return {'success': False, 'error': str(exc)}


def _refresh_weekly_summary_for_week(value, *, exclude_practice_id=None):
    """Rebuild the registered public summary for one calendar week."""
    try:
        from app.integrations.weather import get_weather_for_location
        from app.practices.interfaces import PracticeStatus
        from app.practices.service import convert_practice_to_info
        from app.slack.blocks import (
            build_weekly_summary_blocks,
            build_weekly_summary_fallback_text,
        )
        from app.slack.client import get_slack_client

        record = find_summary_post(value, WEEKLY_SUMMARY)
        if record is None:
            return {"skipped": "absent"}

        week_start, week_end = _week_bounds(value)
        week_query = Practice.query.filter(
            Practice.date >= week_start,
            Practice.date < week_end,
            Practice.status.in_([
                PracticeStatus.SCHEDULED.value,
                PracticeStatus.CONFIRMED.value,
                PracticeStatus.CANCELLED.value,
            ])
        )
        if exclude_practice_id is not None:
            week_query = week_query.filter(
                Practice.id != exclude_practice_id
            )
        practices_for_week = week_query.order_by(
            Practice.date,
            Practice.id,
        ).all()

        weather_data = {}
        for item in practices_for_week:
            location = item.location
            if (
                item.status != PracticeStatus.CANCELLED.value
                and location
                and location.latitude is not None
                and location.longitude is not None
            ):
                try:
                    weather = get_weather_for_location(
                        lat=location.latitude,
                        lon=location.longitude,
                        target_datetime=item.date,
                    )
                    weather_data[item.id] = {
                        "temp_f": weather.temperature_f,
                        "conditions": weather.conditions_summary,
                    }
                except Exception as exc:
                    logger.warning(
                        "Weekly weather refresh failed for practice #%s: %s",
                        item.id,
                        exc,
                    )

        practice_infos = [
            convert_practice_to_info(practice)
            for practice in practices_for_week
        ]
        blocks = build_weekly_summary_blocks(
            practice_infos,
            week_start=week_start.date(),
            weather_data=weather_data,
        )
        fallback = build_weekly_summary_fallback_text(
            practice_infos,
            week_start=week_start.date(),
            weather_data=weather_data,
        )

        channel_id = summary_post_channel(record)
        if not channel_id:
            return {
                'success': False,
                'error': 'Announcement channel is not configured',
            }

        client = get_slack_client()
        client.chat_update(
            channel=channel_id,
            ts=record.message_ts,
            blocks=blocks,
            text=fallback,
        )
        if record.channel_id is None:
            _persist_summary_channel(record, channel_id)
        return {'success': True}
    except Exception as exc:
        logger.warning(
            "Failed to refresh registered weekly summary for %s: %s",
            value,
            exc,
        )
        return {'success': False, 'error': str(exc)}


def refresh_registered_practice_summaries(
    value: date | datetime,
    *,
    exclude_practice_id: int | None = None,
) -> dict[str, dict]:
    """Refresh only the two registered weekly summary surfaces."""
    return {
        "coach_summary": _refresh_coach_summary_for_week(
            value,
            exclude_practice_id=exclude_practice_id,
        ),
        "weekly_summary": _refresh_weekly_summary_for_week(
            value,
            exclude_practice_id=exclude_practice_id,
        ),
    }


def _refresh_coach_summary(
    practice,
    change_type,
    *,
    summary_date=None,
    **_context,
):
    """Refresh the registered Coach summary containing this practice."""
    return _refresh_coach_summary_for_week(
        summary_date or practice.date,
        exclude_practice_id=(
            practice.id if change_type == 'delete' else None
        ),
    )


def _refresh_weekly_summary(
    practice,
    change_type,
    *,
    summary_date=None,
    **_context,
):
    """Refresh the registered public summary containing this practice."""
    return _refresh_weekly_summary_for_week(
        summary_date or practice.date,
        exclude_practice_id=(
            practice.id if change_type == 'delete' else None
        ),
    )


WEEKLY_CHANGE_TYPES = tuple(
    change_type for change_type in ALL_CHANGE_TYPES if change_type != "rsvp"
)


PRACTICE_SURFACES = [
    PracticeSurface("announcement", "slack_message_ts", ALL_CHANGE_TYPES, _refresh_announcement),
    PracticeSurface("collab", "slack_collab_message_ts", ALL_CHANGE_TYPES, _refresh_collab),
    PracticeSurface(
        "coach_summary",
        None,
        ALL_CHANGE_TYPES,
        _refresh_coach_summary,
    ),
    PracticeSurface(
        "weekly_summary",
        None,
        WEEKLY_CHANGE_TYPES,
        _refresh_weekly_summary,
    ),
]


def _post_edit_logs(practice, actor_slack_id, *, skip_announcement=False):
    """Post edit notification thread replies."""
    results = {}

    # Log to announcement thread
    if practice.slack_message_ts and not skip_announcement:
        try:
            from app.slack.practices.coach_review import log_practice_edit
            results['announcement_log'] = log_practice_edit(practice, actor_slack_id)
        except Exception as e:
            results['announcement_log'] = {'success': False, 'error': str(e)}

    # Log to the current week's registered Coach summary thread.
    try:
        coach_record = find_summary_post(practice.date, COACH_SUMMARY)
        if coach_record is not None:
            from app.slack.practices.coach_review import log_coach_summary_edit
            results['coach_summary_log'] = log_coach_summary_edit(
                practice,
                actor_slack_id,
                channel_id=summary_post_channel(coach_record),
                message_ts=coach_record.message_ts,
            )
    except Exception as e:
        results['coach_summary_log'] = {'success': False, 'error': str(e)}

    # Log to collab thread
    if practice.slack_collab_message_ts:
        try:
            from app.slack.practices.coach_review import log_collab_edit
            results['collab_log'] = log_collab_edit(practice, actor_slack_id)
        except Exception as e:
            results['collab_log'] = {'success': False, 'error': str(e)}

    return results
