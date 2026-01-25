"""Practice posting and update operations."""

from typing import Optional
from flask import current_app
from slack_sdk.errors import SlackApiError

from app.models import db
from app.slack.client import get_slack_client, get_channel_id_by_name
from app.slack.blocks import (
    build_practice_announcement_blocks,
    build_combined_lift_blocks,
)
from app.practices.models import Practice
from app.practices.interfaces import WeatherConditions, TrailCondition

from app.slack.practices._config import _get_announcement_channel


def post_practice_announcement(
    practice: Practice,
    weather: Optional[WeatherConditions] = None,
    trail_conditions: Optional[TrailCondition] = None,
    channel_override: Optional[str] = None
) -> dict:
    """Post practice announcement to #practices channel.

    Also immediately posts the going list thread reply so there's always
    a linkable thread for RSVPs.

    Args:
        practice: Practice SQLAlchemy model
        weather: Weather conditions (optional)
        trail_conditions: Trail conditions (optional)
        channel_override: Optional channel name to override default (e.g., 'general')

    Returns:
        dict with keys:
        - success: bool
        - message_ts: str (only if success=True)
        - error: str (only if success=False)
    """
    client = get_slack_client()

    # Determine channel - use override if provided
    if channel_override:
        channel_id = get_channel_id_by_name(channel_override.lstrip('#'))
    else:
        channel_id = _get_announcement_channel()

    if not channel_id:
        return {'success': False, 'error': 'Could not find announcement channel'}

    # Convert SQLAlchemy model to PracticeInfo dataclass
    from app.practices.service import convert_practice_to_info
    practice_info = convert_practice_to_info(practice)

    # Build blocks
    blocks = build_practice_announcement_blocks(practice_info, weather, trail_conditions)

    try:
        response = client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text=f"Practice on {practice.date.strftime('%A, %B %d')}",  # Fallback text
            unfurl_links=False,
            unfurl_media=False
        )

        message_ts = response.get('ts')
        current_app.logger.info(f"Posted practice announcement for practice #{practice.id} (ts: {message_ts})")

        # Save slack info to practice
        practice.slack_message_ts = message_ts
        practice.slack_channel_id = channel_id
        db.session.commit()

        # Add pre-seeded checkmark emoji for RSVP
        try:
            client.reactions_add(
                channel=channel_id,
                timestamp=message_ts,
                name="white_check_mark"
            )
        except Exception as e:
            current_app.logger.warning(f"Could not add checkmark reaction: {e}")

        # Create logging thread in #tcsc-logging
        try:
            from app.slack.practices.coach_review import create_practice_log_thread
            create_practice_log_thread(practice)
        except Exception as e:
            current_app.logger.warning(f"Could not create practice log thread: {e}")

        return {
            'success': True,
            'message_ts': message_ts,
            'channel_id': channel_id
        }

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error posting practice announcement: {error_msg}")
        return {'success': False, 'error': error_msg}


def post_combined_lift_announcement(
    practices: list[Practice],
    channel_override: Optional[str] = None
) -> dict:
    """Post combined lift announcement for multiple lift practices.

    Used when 2-3 lift practices (e.g., Wed + Fri at Balance Fitness) should
    be announced together in a single message with per-day RSVP emojis.

    Args:
        practices: List of Practice SQLAlchemy models (2-3 practices)
        channel_override: Optional channel name to override default

    Returns:
        dict with keys:
        - success: bool
        - message_ts: str (only if success=True)
        - channel_id: str (only if success=True)
        - error: str (only if success=False)
    """
    if not practices:
        return {'success': False, 'error': 'No practices provided'}

    client = get_slack_client()

    # Determine channel
    if channel_override:
        channel_id = get_channel_id_by_name(channel_override.lstrip('#'))
    else:
        channel_id = _get_announcement_channel()

    if not channel_id:
        return {'success': False, 'error': 'Could not find announcement channel'}

    # Convert SQLAlchemy models to PracticeInfo dataclasses
    from app.practices.service import convert_practice_to_info
    practice_infos = [convert_practice_to_info(p) for p in practices]

    # Build combined blocks
    blocks = build_combined_lift_blocks(practice_infos)

    # Sort practices by date for consistent emoji assignment
    sorted_practices = sorted(practices, key=lambda p: p.date)

    # Build fallback text with all days
    days = [p.date.strftime('%A') for p in sorted_practices]
    days_str = " & ".join(days)

    try:
        response = client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text=f"TCSC Lift - {days_str}",
            unfurl_links=False,
            unfurl_media=False
        )

        message_ts = response.get('ts')
        practice_ids = [p.id for p in sorted_practices]
        current_app.logger.info(f"Posted combined lift announcement for practices {practice_ids} (ts: {message_ts})")

        # Save slack info to all practices
        for practice in sorted_practices:
            practice.slack_message_ts = message_ts
            practice.slack_channel_id = channel_id
        db.session.commit()

        # Add RSVP emojis for each day (different emoji per day)
        rsvp_emojis = ["white_check_mark", "ballot_box_with_check", "heavy_check_mark"]
        for i, practice in enumerate(sorted_practices):
            emoji = rsvp_emojis[i] if i < len(rsvp_emojis) else "white_check_mark"
            try:
                client.reactions_add(
                    channel=channel_id,
                    timestamp=message_ts,
                    name=emoji
                )
            except Exception as e:
                current_app.logger.warning(f"Could not add {emoji} reaction: {e}")

        return {
            'success': True,
            'message_ts': message_ts,
            'channel_id': channel_id
        }

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error posting combined lift announcement: {error_msg}")
        return {'success': False, 'error': error_msg}


def update_practice_announcement(
    practice: Practice,
    weather: Optional[WeatherConditions] = None,
    trail_conditions: Optional[TrailCondition] = None
) -> dict:
    """Update an existing practice announcement message.

    Args:
        practice: Practice SQLAlchemy model with slack_message_ts set
        weather: Updated weather conditions (optional)
        trail_conditions: Updated trail conditions (optional)

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    if not practice.slack_message_ts or not practice.slack_channel_id:
        return {'success': False, 'error': 'No Slack message to update'}

    client = get_slack_client()

    # Convert to dataclass
    from app.practices.service import convert_practice_to_info
    practice_info = convert_practice_to_info(practice)

    # Build updated blocks
    blocks = build_practice_announcement_blocks(practice_info, weather, trail_conditions)

    try:
        client.chat_update(
            channel=practice.slack_channel_id,
            ts=practice.slack_message_ts,
            blocks=blocks,
            text=f"Practice on {practice.date.strftime('%A, %B %d')}"
        )

        current_app.logger.info(f"Updated practice announcement for practice #{practice.id}")
        return {'success': True}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error updating practice announcement: {error_msg}")
        return {'success': False, 'error': error_msg}


def update_practice_post(practice: Practice) -> dict:
    """Update the main practice announcement post with current data.

    Args:
        practice: Practice SQLAlchemy model with slack_message_ts set

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    if not practice.slack_message_ts or not practice.slack_channel_id:
        return {'success': False, 'error': 'No practice message to update'}

    client = get_slack_client()

    # Convert SQLAlchemy model to PracticeInfo dataclass
    from app.practices.service import convert_practice_to_info
    practice_info = convert_practice_to_info(practice)

    # Build updated blocks (without weather/trail data)
    blocks = build_practice_announcement_blocks(practice_info)

    try:
        client.chat_update(
            channel=practice.slack_channel_id,
            ts=practice.slack_message_ts,
            blocks=blocks,
            text=f"Practice on {practice.date.strftime('%A, %B %d')}"
        )

        current_app.logger.info(f"Updated practice post for practice #{practice.id}")
        return {'success': True}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error updating practice post: {error_msg}")
        return {'success': False, 'error': error_msg}


def is_combined_lift_practice(practice: Practice) -> bool:
    """Check if practice is part of a combined lift post.

    A practice is part of a combined lift if:
    1. It has slack_message_ts set
    2. Another practice shares the same slack_message_ts

    Args:
        practice: Practice SQLAlchemy model

    Returns:
        True if practice is part of a combined post with other practices.
    """
    if not practice.slack_message_ts:
        return False

    # Count how many practices share this message_ts
    count = Practice.query.filter(
        Practice.slack_message_ts == practice.slack_message_ts
    ).count()

    return count > 1


def update_combined_lift_post(practice: Practice) -> dict:
    """Update combined lift announcement when any practice in it changes.

    Finds all practices sharing the same slack_message_ts and rebuilds
    the combined block structure.

    Args:
        practice: Practice SQLAlchemy model (one of the combined practices)

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    if not practice.slack_message_ts or not practice.slack_channel_id:
        return {'success': False, 'error': 'No Slack message to update'}

    client = get_slack_client()

    # Find all practices sharing this message_ts
    practices = Practice.query.filter(
        Practice.slack_message_ts == practice.slack_message_ts
    ).order_by(Practice.date).all()

    if not practices:
        return {'success': False, 'error': 'No practices found for this message'}

    # Convert to PracticeInfo dataclasses
    from app.practices.service import convert_practice_to_info
    practice_infos = [convert_practice_to_info(p) for p in practices]

    # Build combined blocks
    blocks = build_combined_lift_blocks(practice_infos)

    # Build fallback text with all days
    days = [p.date.strftime('%A') for p in practices]
    days_str = " & ".join(days)

    try:
        client.chat_update(
            channel=practice.slack_channel_id,
            ts=practice.slack_message_ts,
            blocks=blocks,
            text=f"TCSC Lift - {days_str}"
        )

        practice_ids = [p.id for p in practices]
        current_app.logger.info(f"Updated combined lift post for practices {practice_ids}")
        return {'success': True}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error updating combined lift post: {error_msg}")
        return {'success': False, 'error': error_msg}


def update_practice_slack_post(practice: Practice) -> dict:
    """Smart update that handles both individual and combined posts.

    Detects whether the practice is part of a combined lift post and
    uses the appropriate update function.

    Args:
        practice: Practice SQLAlchemy model

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    if not practice.slack_message_ts:
        return {'success': False, 'error': 'No Slack post to update'}

    if is_combined_lift_practice(practice):
        return update_combined_lift_post(practice)
    else:
        return update_practice_post(practice)
