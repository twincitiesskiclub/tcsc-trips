"""Centralized Slack post refresh for practices.

When a practice is modified in the database, call refresh_practice_posts()
to update ALL related Slack posts (announcement, collab review, coach
summary, weekly summary, edit logs).
"""

import logging
from datetime import timedelta

from flask import current_app

from app.practices.models import Practice

logger = logging.getLogger(__name__)


def refresh_practice_posts(practice, change_type='edit', actor_slack_id=None, notify=True):
    """Update all Slack posts for a practice after DB changes.

    Args:
        practice: Practice model instance (already committed to DB)
        change_type: 'edit' | 'cancel' | 'delete' | 'rsvp' | 'workout' | 'create'
        actor_slack_id: Slack UID of person who made the change (for edit logs)
        notify: Whether to post thread notifications (edit logs)

    Returns:
        dict with results per post type, e.g.:
        {
            'announcement': {'success': True},
            'collab': {'success': True},
            'coach_summary': {'success': False, 'error': '...'},
            'weekly_summary': {'skipped': True},
        }
    """
    results = {}

    # 1. Announcement post
    results['announcement'] = _refresh_announcement(practice, change_type)

    # 2. Collab review post
    results['collab'] = _refresh_collab(practice, change_type)

    # 3. Coach weekly summary
    results['coach_summary'] = _refresh_coach_summary(practice, change_type)

    # 4. Weekly summary (#announcements-practices)
    results['weekly_summary'] = _refresh_weekly_summary(practice, change_type)

    # 5. Edit logging (thread replies)
    if notify and actor_slack_id and change_type in ('edit', 'workout'):
        results['edit_logs'] = _post_edit_logs(practice, actor_slack_id)

    return results


def _refresh_announcement(practice, change_type):
    """Update the main practice announcement post."""
    if not practice.slack_message_ts or not practice.slack_channel_id:
        return {'skipped': True}

    try:
        if change_type == 'cancel':
            from app.slack.practices.cancellations import update_practice_as_cancelled
            return update_practice_as_cancelled(practice, 'Admin')

        if change_type == 'delete':
            from app.slack.client import get_slack_client
            client = get_slack_client()
            client.chat_delete(
                channel=practice.slack_channel_id,
                ts=practice.slack_message_ts
            )
            return {'success': True}

        if change_type == 'rsvp':
            from app.slack.practices.rsvp import update_practice_rsvp_counts
            return update_practice_rsvp_counts(practice)

        # For edit, workout, create — rebuild the full announcement
        from app.slack.practices.announcements import update_practice_slack_post
        return update_practice_slack_post(practice)

    except Exception as e:
        logger.warning(f"Failed to refresh announcement for practice #{practice.id}: {e}")
        return {'success': False, 'error': str(e)}


def _refresh_collab(practice, change_type):
    """Update the collab review post in #collab-coaches-practices."""
    if not practice.slack_collab_message_ts:
        return {'skipped': True}

    try:
        from app.slack.practices.coach_review import update_collab_post
        return update_collab_post(practice)
    except Exception as e:
        logger.warning(f"Failed to refresh collab post for practice #{practice.id}: {e}")
        return {'success': False, 'error': str(e)}


def _refresh_coach_summary(practice, change_type):
    """Rebuild and update the coach weekly summary post."""
    if not practice.slack_coach_summary_ts:
        return {'skipped': True}

    try:
        from app.models import AppConfig, db
        from app.practices.service import convert_practice_to_info
        from app.slack.blocks import build_coach_weekly_summary_blocks
        from app.slack.practices._config import COLLAB_CHANNEL_ID
        from app.slack.client import get_slack_client

        # Calculate week boundaries from the practice date
        practice_date = practice.date
        days_since_monday = practice_date.weekday()
        week_start = (practice_date - timedelta(days=days_since_monday)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        week_end = week_start + timedelta(days=7)

        # Get all practices for the week
        practices_for_week = Practice.query.filter(
            Practice.date >= week_start,
            Practice.date < week_end
        ).order_by(Practice.date).all()

        # Get expected days from config
        expected_days = AppConfig.get('practice_days', [
            {"day": "tuesday", "time": "18:00", "active": True},
            {"day": "thursday", "time": "18:00", "active": True},
            {"day": "saturday", "time": "09:00", "active": True}
        ])

        # Rebuild blocks
        practice_infos = [convert_practice_to_info(p) for p in practices_for_week]
        blocks = build_coach_weekly_summary_blocks(practice_infos, expected_days, week_start)

        # Try to update — try collab channel first, then fallback
        client = get_slack_client()
        channels_to_try = [COLLAB_CHANNEL_ID, 'C053T1AR48Y']
        for channel in channels_to_try:
            try:
                client.chat_update(
                    channel=channel,
                    ts=practice.slack_coach_summary_ts,
                    blocks=blocks,
                    text=f"Coach Review: Week of {week_start.strftime('%B %-d')}"
                )
                return {'success': True}
            except Exception:
                continue

        return {'success': False, 'error': 'Could not update in any channel'}

    except Exception as e:
        logger.warning(f"Failed to refresh coach summary for practice #{practice.id}: {e}")
        return {'success': False, 'error': str(e)}


def _refresh_weekly_summary(practice, change_type):
    """Rebuild and update the weekly summary post in #announcements-practices."""
    if not practice.slack_weekly_summary_ts:
        return {'skipped': True}

    try:
        from app.practices.service import convert_practice_to_info
        from app.practices.interfaces import PracticeStatus
        from app.slack.blocks import build_weekly_summary_blocks
        from app.slack.client import get_slack_client
        from app.integrations.weather import get_weather_for_location

        # Calculate week boundaries from the practice date
        practice_date = practice.date
        days_since_monday = practice_date.weekday()
        week_start = (practice_date - timedelta(days=days_since_monday)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        week_end = week_start + timedelta(days=7)

        # Get all scheduled/confirmed practices for the week
        practices_for_week = Practice.query.filter(
            Practice.date >= week_start,
            Practice.date < week_end,
            Practice.status.in_([
                PracticeStatus.SCHEDULED.value,
                PracticeStatus.CONFIRMED.value
            ])
        ).order_by(Practice.date).all()

        # Build weather data
        weather_data = {}
        for p in practices_for_week:
            if p.location and p.location.latitude and p.location.longitude:
                try:
                    weather = get_weather_for_location(
                        lat=p.location.latitude,
                        lon=p.location.longitude,
                        target_datetime=p.date
                    )
                    weather_data[p.id] = {
                        'temp_f': int(weather.temperature_f),
                        'feels_like_f': int(weather.feels_like_f),
                        'conditions': weather.conditions_summary,
                        'precipitation_chance': int(weather.precipitation_chance)
                    }
                except Exception as e:
                    logger.warning(f"Weather fetch failed for practice {p.id}: {e}")

        # Rebuild blocks
        practice_infos = [convert_practice_to_info(p) for p in practices_for_week]
        blocks = build_weekly_summary_blocks(practice_infos, weather_data=weather_data)

        # Find the channel — use the practice's slack_channel_id if available,
        # otherwise fall back to the announcement channel
        channel_id = practice.slack_channel_id
        if not channel_id:
            from app.slack.practices._config import _get_announcement_channel
            channel_id = _get_announcement_channel()

        client = get_slack_client()
        client.chat_update(
            channel=channel_id,
            ts=practice.slack_weekly_summary_ts,
            blocks=blocks,
            text="Weekly Practice Summary"
        )

        return {'success': True}

    except Exception as e:
        logger.warning(f"Failed to refresh weekly summary for practice #{practice.id}: {e}")
        return {'success': False, 'error': str(e)}


def _post_edit_logs(practice, actor_slack_id):
    """Post edit notification thread replies."""
    results = {}

    # Log to announcement thread
    if practice.slack_message_ts:
        try:
            from app.slack.practices.coach_review import log_practice_edit
            results['announcement_log'] = log_practice_edit(practice, actor_slack_id)
        except Exception as e:
            results['announcement_log'] = {'success': False, 'error': str(e)}

    # Log to coach summary thread
    if practice.slack_coach_summary_ts:
        try:
            from app.slack.practices.coach_review import log_coach_summary_edit
            results['coach_summary_log'] = log_coach_summary_edit(practice, actor_slack_id)
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
