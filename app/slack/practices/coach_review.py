"""Coach review workflow, logging, and weekly summary operations."""

from datetime import datetime
from typing import Optional
from flask import current_app
from slack_sdk.errors import SlackApiError

from app.models import db
from app.slack.client import get_slack_client, get_channel_id_by_name
from app.slack.blocks import build_collab_practice_blocks
from app.practices.models import Practice

from app.slack.practices._config import (
    LOGGING_CHANNEL_ID,
    PRACTICES_CORE_CHANNEL_ID,
    COLLAB_CHANNEL_ID,
    KJ_SLACK_ID,
    ADMIN_SLACK_IDS,
    FALLBACK_COACH_IDS,
)


def post_48h_workout_reminder(
    practices_needing_workout: list,
    channel_override: Optional[str] = None
) -> dict:
    """Post 48h workout reminder to #collab-coaches-practices.

    Tags @kj as a safety check before practices go live.

    Args:
        practices_needing_workout: List of Practice objects missing workouts
        channel_override: Optional channel name to override default (e.g., 'general')

    Returns:
        dict with keys:
        - success: bool
        - message_ts: str (if success)
        - error: str (if failure)
    """
    from app.practices.service import convert_practice_to_info

    if not practices_needing_workout:
        return {'success': True, 'message_ts': None, 'skipped': True}

    client = get_slack_client()

    # Determine channel - use override if provided
    if channel_override:
        channel_id = get_channel_id_by_name(channel_override.lstrip('#'))
    else:
        channel_id = COLLAB_CHANNEL_ID

    # Build message blocks
    blocks = []

    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": ":memo: Workout Check - 48 Hours Out",
            "emoji": True
        }
    })

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"<@{KJ_SLACK_ID}> The following practice(s) need workout descriptions before posting:"
        }
    })

    blocks.append({"type": "divider"})

    for practice in practices_needing_workout:
        practice_info = convert_practice_to_info(practice)
        time_str = practice_info.date.strftime('%A, %b %-d at %-I:%M %p')
        location = practice_info.location.name if practice_info.location else "TBD"

        # Get coach names
        coaches = [lead for lead in practice.leads if lead.role == 'coach']
        coach_text = ", ".join([f"<@{c.user.slack_user.slack_uid}>" for c in coaches
                               if c.user and c.user.slack_user]) or "No coach assigned"

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{time_str}*\n:round_pushpin: {location}\n:bust_in_silhouette: {coach_text}"
            }
        })

    try:
        response = client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text="48h Workout Check",
            unfurl_links=False,
            unfurl_media=False
        )

        message_ts = response.get('ts')
        current_app.logger.info(f"Posted 48h workout reminder (ts: {message_ts})")

        return {
            'success': True,
            'message_ts': message_ts,
            'channel_id': channel_id
        }

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error posting 48h workout reminder: {error_msg}")
        return {'success': False, 'error': error_msg}


def post_daily_practice_recap(
    evaluations: list[dict],
    channel_override: Optional[str] = None
) -> dict:
    """Post daily practice conditions recap to #practices-core.

    Called by morning_check routine at 7am when there are practices today.
    Shows weather, trail conditions, lead status, and any cancellation proposals.

    Args:
        evaluations: List of dicts with keys:
            - practice: PracticeInfo
            - evaluation: PracticeEvaluation (or None)
            - summary: str
            - is_go: bool
            - proposal_id: int (if cancellation proposed)
        channel_override: Optional channel name to override default (e.g., 'general')

    Returns:
        dict with keys:
        - success: bool
        - message_ts: str (if success)
        - error: str (if failure)
    """
    from app.slack.blocks import build_daily_practice_recap_blocks

    client = get_slack_client()

    # Determine channel - use override if provided
    if channel_override:
        channel_id = get_channel_id_by_name(channel_override.lstrip('#'))
    else:
        channel_id = PRACTICES_CORE_CHANNEL_ID

    # Check if any proposals were created
    has_proposals = any(e.get('proposal_id') for e in evaluations)

    # Build blocks
    blocks = build_daily_practice_recap_blocks(evaluations, has_proposals)

    try:
        response = client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text="Daily Practice Conditions Recap",
            unfurl_links=False,
            unfurl_media=False
        )

        message_ts = response.get('ts')
        current_app.logger.info(f"Posted daily practice recap (ts: {message_ts})")

        return {
            'success': True,
            'message_ts': message_ts,
            'channel_id': channel_id
        }

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error posting daily practice recap: {error_msg}")
        return {'success': False, 'error': error_msg}


def create_practice_log_thread(practice: Practice) -> dict:
    """Create a logging thread for a practice in #tcsc-logging.

    Posts the initial message that will serve as the parent for RSVP logs.

    Args:
        practice: Practice SQLAlchemy model

    Returns:
        dict with keys:
        - success: bool
        - message_ts: str (only if success=True)
        - error: str (only if success=False)
    """
    client = get_slack_client()

    # Format practice info for log header
    date_str = practice.date.strftime('%A, %B %d')
    time_str = practice.date.strftime('%-I:%M %p').replace(' AM', 'am').replace(' PM', 'pm')
    location = practice.location.name if practice.location else "TBD"
    practice_types = ', '.join([t.name for t in practice.practice_types]) if practice.practice_types else "Practice"

    log_text = f":thread: *Practice Log: {date_str}*\n{practice_types} @ {location} ({time_str})"

    try:
        response = client.chat_postMessage(
            channel=LOGGING_CHANNEL_ID,
            text=log_text,
            unfurl_links=False,
            unfurl_media=False
        )

        message_ts = response.get('ts')
        practice.slack_log_message_ts = message_ts
        db.session.commit()

        current_app.logger.info(f"Created practice log thread for practice #{practice.id}")
        return {'success': True, 'message_ts': message_ts}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error creating practice log thread: {error_msg}")
        return {'success': False, 'error': error_msg}


def post_collab_review(practice: Practice) -> dict:
    """Post practice review request to #collab-coaches-practices.

    This is posted before the practice announcement so coaches can review
    and approve the practice details.

    Args:
        practice: Practice SQLAlchemy model

    Returns:
        dict with keys:
        - success: bool
        - message_ts: str (only if success=True)
        - channel_id: str (only if success=True)
        - error: str (only if success=False)
    """
    client = get_slack_client()

    # Convert SQLAlchemy model to PracticeInfo dataclass
    from app.practices.service import convert_practice_to_info
    practice_info = convert_practice_to_info(practice)

    # Build blocks (not approved yet)
    blocks = build_collab_practice_blocks(
        practice_info,
        approved=practice.coach_approved,
        approved_by=practice.approved_by_slack_uid,
        approved_at=practice.approved_at
    )

    try:
        response = client.chat_postMessage(
            channel=COLLAB_CHANNEL_ID,
            blocks=blocks,
            text=f"Practice review: {practice.date.strftime('%A, %B %d')}",  # Fallback text
            unfurl_links=False,
            unfurl_media=False
        )

        message_ts = response.get('ts')
        current_app.logger.info(f"Posted collab review for practice #{practice.id} (ts: {message_ts})")

        # Save collab message info to practice
        practice.slack_collab_message_ts = message_ts
        db.session.commit()

        # Also create logging thread if not already created
        if not practice.slack_log_message_ts:
            try:
                create_practice_log_thread(practice)
            except Exception as e:
                current_app.logger.warning(f"Could not create practice log thread: {e}")

        return {
            'success': True,
            'message_ts': message_ts,
            'channel_id': COLLAB_CHANNEL_ID
        }

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error posting collab review: {error_msg}")
        return {'success': False, 'error': error_msg}


def update_collab_post(practice: Practice) -> dict:
    """Update the collab review post with current practice data.

    Args:
        practice: Practice SQLAlchemy model with slack_collab_message_ts set

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    if not practice.slack_collab_message_ts:
        return {'success': False, 'error': 'No collab message to update'}

    client = get_slack_client()

    # Convert SQLAlchemy model to PracticeInfo dataclass
    from app.practices.service import convert_practice_to_info
    practice_info = convert_practice_to_info(practice)

    # Build updated blocks
    blocks = build_collab_practice_blocks(
        practice_info,
        approved=practice.coach_approved,
        approved_by=practice.approved_by_slack_uid,
        approved_at=practice.approved_at
    )

    try:
        client.chat_update(
            channel=COLLAB_CHANNEL_ID,
            ts=practice.slack_collab_message_ts,
            blocks=blocks,
            text=f"Practice review: {practice.date.strftime('%A, %B %d')}"
        )

        current_app.logger.info(f"Updated collab post for practice #{practice.id}")
        return {'success': True}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error updating collab post: {error_msg}")
        return {'success': False, 'error': error_msg}


def log_collab_edit(practice: Practice, slack_user_id: str) -> dict:
    """Log an edit action to the collab post thread.

    Args:
        practice: Practice SQLAlchemy model with slack_collab_message_ts set
        slack_user_id: Slack user ID who made the edit

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    if not practice.slack_collab_message_ts:
        return {'success': False, 'error': 'No collab message to add thread to'}

    client = get_slack_client()
    log_text = f":pencil2: <@{slack_user_id}> updated this practice"

    try:
        client.chat_postMessage(
            channel=COLLAB_CHANNEL_ID,
            thread_ts=practice.slack_collab_message_ts,
            text=log_text,
            unfurl_links=False,
            unfurl_media=False
        )

        current_app.logger.info(f"Logged collab edit for practice #{practice.id}")
        return {'success': True}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error logging collab edit: {error_msg}")
        return {'success': False, 'error': error_msg}


def log_practice_edit(practice: Practice, slack_user_id: str) -> dict:
    """Log an edit action to the practice announcement thread.

    Args:
        practice: Practice SQLAlchemy model with slack_message_ts set
        slack_user_id: Slack user ID who made the edit

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    if not practice.slack_message_ts or not practice.slack_channel_id:
        return {'success': False, 'error': 'No practice message to add thread to'}

    client = get_slack_client()
    log_text = f":pencil2: <@{slack_user_id}> updated the workout"

    try:
        client.chat_postMessage(
            channel=practice.slack_channel_id,
            thread_ts=practice.slack_message_ts,
            text=log_text,
            unfurl_links=False,
            unfurl_media=False
        )

        current_app.logger.info(f"Logged practice edit for practice #{practice.id}")
        return {'success': True}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error logging practice edit: {error_msg}")
        return {'success': False, 'error': error_msg}


def post_coach_weekly_summary(
    week_start: datetime,
    channel_override: Optional[str] = None
) -> dict:
    """Post weekly coach review summary to #collab-coaches-practices.

    Creates a summary post showing all practices for the week with Edit buttons.
    For days without practices, shows placeholders with "Add Practice" buttons.
    Tags users with HEAD_COACH role for review.

    Args:
        week_start: Monday of the week to summarize
        channel_override: Optional channel name to override default (e.g., 'general')

    Returns:
        dict with keys:
        - success: bool
        - message_ts: str (if success)
        - error: str (only if success=False)
    """
    from datetime import timedelta
    from app.models import AppConfig, db, Tag, User
    from app.practices.service import convert_practice_to_info
    from app.slack.blocks import build_coach_weekly_summary_blocks

    # Get expected practice days from config
    expected_days = AppConfig.get('practice_days', [
        {"day": "tuesday", "time": "18:00", "active": True},
        {"day": "thursday", "time": "18:00", "active": True},
        {"day": "saturday", "time": "09:00", "active": True}
    ])

    # Query practices for the week
    week_end = week_start + timedelta(days=7)
    practices = Practice.query.filter(
        Practice.date >= week_start,
        Practice.date < week_end
    ).order_by(Practice.date).all()

    # Convert to PracticeInfo
    practice_infos = [convert_practice_to_info(p) for p in practices]

    # Build blocks
    blocks = build_coach_weekly_summary_blocks(practice_infos, expected_days, week_start)

    # Determine channel - use override if provided
    if channel_override:
        channel_id = get_channel_id_by_name(channel_override.lstrip('#'))
    else:
        channel_id = COLLAB_CHANNEL_ID

    # Get users with HEAD_COACH tag to mention
    review_tags = Tag.query.filter(Tag.name == 'HEAD_COACH').all()
    mentions = []
    for tag in review_tags:
        for user in tag.users:
            if user.slack_user and user.slack_user.slack_uid:
                mentions.append(f"<@{user.slack_user.slack_uid}>")

    # Add mentions as a context block at the end if we have any
    if mentions:
        unique_mentions = list(dict.fromkeys(mentions))  # Remove duplicates, preserve order
        blocks.append({
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": f":eyes: {' '.join(unique_mentions)} — please review this week's practices"
            }]
        })

    # Post to channel
    client = get_slack_client()
    try:
        response = client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text=f"Coach Review: Week of {week_start.strftime('%B %-d')}",
            unfurl_links=False,
            unfurl_media=False
        )

        message_ts = response.get('ts')
        current_app.logger.info(f"Posted coach weekly summary (ts: {message_ts})")

        # Save message_ts to each practice's slack_coach_summary_ts
        for practice in practices:
            practice.slack_coach_summary_ts = message_ts
        db.session.commit()

        return {'success': True, 'message_ts': message_ts, 'channel_id': channel_id}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error posting coach weekly summary: {error_msg}")
        return {'success': False, 'error': error_msg}


def log_coach_summary_edit(practice: Practice, slack_user_id: str) -> dict:
    """Log an edit action to the coach weekly summary thread.

    Args:
        practice: Practice SQLAlchemy model with slack_coach_summary_ts set
        slack_user_id: Slack user ID who made the edit

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    if not practice.slack_coach_summary_ts:
        return {'success': False, 'error': 'No summary message to add thread to'}

    client = get_slack_client()
    date_str = practice.date.strftime('%A, %b %-d')
    log_text = f":pencil2: <@{slack_user_id}> updated *{date_str}* practice"

    try:
        client.chat_postMessage(
            channel=COLLAB_CHANNEL_ID,
            thread_ts=practice.slack_coach_summary_ts,
            text=log_text,
            unfurl_links=False,
            unfurl_media=False
        )

        current_app.logger.info(f"Logged coach summary edit for practice #{practice.id}")
        return {'success': True}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error logging coach summary edit: {error_msg}")
        return {'success': False, 'error': error_msg}


def get_practice_coach_ids(practice: Practice) -> list[str]:
    """Get Slack IDs of coaches assigned to this practice.

    Args:
        practice: Practice SQLAlchemy model

    Returns:
        List of Slack user IDs for assigned coaches
    """
    coach_ids = []
    if practice.leads:
        for lead in practice.leads:
            if lead.role == 'coach':
                if lead.user and lead.user.slack_user:
                    coach_ids.append(lead.user.slack_user.slack_uid)
    return coach_ids


def escalate_practice_review(practice: Practice) -> dict:
    """Post escalation thread reply tagging coaches and admins.

    Called when practice hasn't been approved by escalation deadline.

    Args:
        practice: Practice SQLAlchemy model with slack_collab_message_ts set

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    if not practice.slack_collab_message_ts:
        return {'success': False, 'error': 'No collab message to escalate'}

    client = get_slack_client()

    # Get coach IDs or use fallback
    coach_ids = get_practice_coach_ids(practice)
    if not coach_ids:
        coach_ids = FALLBACK_COACH_IDS

    # Build mentions
    mentions = [f"<@{uid}>" for uid in coach_ids]
    mentions.extend([f"<@{uid}>" for uid in ADMIN_SLACK_IDS])
    mention_text = " ".join(mentions)

    log_text = f":warning: {mention_text} This practice hasn't been reviewed yet. Please approve or edit."

    try:
        client.chat_postMessage(
            channel=COLLAB_CHANNEL_ID,
            thread_ts=practice.slack_collab_message_ts,
            text=log_text,
            unfurl_links=False,
            unfurl_media=False
        )

        # Mark as escalated
        practice.escalated = True
        db.session.commit()

        current_app.logger.info(f"Escalated practice review for practice #{practice.id}")
        return {'success': True}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error escalating practice review: {error_msg}")
        return {'success': False, 'error': error_msg}
