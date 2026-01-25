"""Lead coordination and reminder operations."""

from datetime import datetime
from typing import Optional
from flask import current_app
from slack_sdk.errors import SlackApiError

from app.slack.client import get_slack_client, get_channel_id_by_name
from app.slack.blocks import (
    build_lead_confirmation_blocks,
    build_substitution_request_blocks,
)
from app.practices.models import Practice

from app.slack.practices._config import _get_escalation_channel, COORD_CHANNEL_ID


def send_lead_availability_request(practice: Practice, user_slack_id: str) -> dict:
    """Send DM to practice lead requesting confirmation.

    Args:
        practice: Practice SQLAlchemy model
        user_slack_id: Slack user ID of the lead

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    # Convert to dataclass
    from app.practices.service import convert_practice_to_info
    practice_info = convert_practice_to_info(practice)

    # Build blocks
    blocks = build_lead_confirmation_blocks(practice_info)

    client = get_slack_client()

    try:
        response = client.chat_postMessage(
            channel=user_slack_id,
            blocks=blocks,
            text=f"Lead confirmation needed for practice on {practice.date.strftime('%A, %B %d')}"
        )

        current_app.logger.info(f"Sent lead confirmation request to {user_slack_id} for practice #{practice.id}")
        return {'success': True}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error sending lead confirmation request: {error_msg}")
        return {'success': False, 'error': error_msg}


def send_workout_reminder(practice: Practice, coach_slack_id: str) -> dict:
    """Send DM to coach requesting workout submission.

    Args:
        practice: Practice SQLAlchemy model
        coach_slack_id: Slack user ID of the coach

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    client = get_slack_client()

    # Build message
    date_str = practice.date.strftime('%A, %B %d at %I:%M %p')
    location = practice.location.name if practice.location else "TBD"

    message = (
        f":clipboard: Hi! You're scheduled to coach practice on *{date_str}* at *{location}*.\n\n"
        f"Could you submit the workout plan? Members like to see it in advance to plan their participation.\n\n"
        f"Thanks!"
    )

    try:
        response = client.chat_postMessage(
            channel=coach_slack_id,
            text=message
        )

        current_app.logger.info(f"Sent workout reminder to {coach_slack_id} for practice #{practice.id}")
        return {'success': True}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error sending workout reminder to {coach_slack_id}: {error_msg}")
        return {'success': False, 'error': error_msg}


def send_lead_checkin_dm(practice: Practice) -> dict:
    """Send group DM to practices directors + lead for lead check-in.

    Used by 4pm/10pm lead verification checks when a lead hasn't confirmed
    by reacting to the practice post.

    Args:
        practice: Practice SQLAlchemy model

    Returns:
        dict with keys:
        - success: bool
        - channel_id: str (only if success=True)
        - error: str (only if success=False)
    """
    from app.models import Tag
    from app.slack.client import open_conversation, get_slack_client
    from app.utils import format_datetime_central

    # Get practices directors by tag
    director_slack_ids = []
    practices_director_tag = Tag.query.filter_by(name='PRACTICES_DIRECTOR').first()
    if practices_director_tag:
        for user in practices_director_tag.users:
            if user.slack_user and user.slack_user.slack_uid:
                director_slack_ids.append(user.slack_user.slack_uid)

    # Fallback admin IDs if no directors are tagged
    ADMIN_FALLBACK_IDS = ["U02JP5QNQFS", "U02K5TKMQH3", "U02J6R6CZS7"]  # augie, simon, rob

    if not director_slack_ids:
        current_app.logger.warning("No PRACTICES_DIRECTOR users found, using admin fallback")
        director_slack_ids = ADMIN_FALLBACK_IDS

    # Get lead Slack IDs
    lead_slack_ids = []
    lead_mentions = []
    for lead in practice.leads:
        if lead.role == 'lead' and lead.user and lead.user.slack_user:
            lead_slack_ids.append(lead.user.slack_user.slack_uid)
            lead_mentions.append(f"<@{lead.user.slack_user.slack_uid}>")

    if not lead_slack_ids:
        current_app.logger.warning(f"No Slack IDs for leads of practice #{practice.id}")
        return {'success': False, 'error': 'No lead Slack IDs found'}

    # Combine all participants (deduplicate)
    all_participants = list(set(director_slack_ids + lead_slack_ids))

    if len(all_participants) < 2:
        return {'success': False, 'error': 'Not enough participants for group DM'}

    # Open the group conversation
    conv_result = open_conversation(all_participants)
    if not conv_result.get('success'):
        return conv_result

    channel_id = conv_result.get('channel_id')

    # Build the message
    time_str = format_datetime_central(practice.date, '%-I:%M %p')
    location = practice.location.name if practice.location else "TBD"
    practice_types = ", ".join([t.name for t in practice.practice_types]) if practice.practice_types else "Practice"
    lead_mention_text = " ".join(lead_mentions)
    director_mention_text = ", ".join(f"<@{uid}>" for uid in director_slack_ids)

    # Determine if evening or morning practice for message
    is_tonight = practice.date.date() == datetime.utcnow().date()
    time_label = "Tonight" if is_tonight else "Tomorrow"

    message = (
        f":clipboard: *Practice Check-In*\n\n"
        f"*{time_label}* — {time_str}\n"
        f"{practice_types} at {location}\n\n"
        f"---\n\n"
        f"Hey {lead_mention_text}! Just verifying you're good to lead {time_label.lower()}.\n\n"
        f":white_check_mark: React to the practice post or reply here to confirm!\n\n"
        f"If you need a sub, post to <#C02J4DGCFL2|coord-practices-leads-assists>.\n"
        f"If you need to go over anything, {director_mention_text} are here."
    )

    client = get_slack_client()

    try:
        client.chat_postMessage(
            channel=channel_id,
            text=message,
            unfurl_links=False,
            unfurl_media=False
        )

        current_app.logger.info(f"Sent lead check-in DM for practice #{practice.id} to {len(all_participants)} participants")
        return {'success': True, 'channel_id': channel_id}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error sending lead check-in DM: {error_msg}")
        return {'success': False, 'error': error_msg}


def post_substitution_request(
    practice: Practice,
    requester_slack_id: str,
    reason: str
) -> dict:
    """Post substitution request to escalation channel (#practices-team).

    Args:
        practice: Practice SQLAlchemy model
        requester_slack_id: Slack ID of the person requesting a sub
        reason: Reason for needing a substitute

    Returns:
        dict with keys:
        - success: bool
        - message_ts: str (only if success=True)
        - error: str (only if success=False)
    """
    client = get_slack_client()
    channel_id = _get_escalation_channel()

    if not channel_id:
        return {'success': False, 'error': 'Could not find escalation channel'}

    # Convert to dataclass
    from app.practices.service import convert_practice_to_info
    practice_info = convert_practice_to_info(practice)

    # Build blocks
    blocks = build_substitution_request_blocks(practice_info, requester_slack_id, reason)

    try:
        response = client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text=f"Substitute needed for practice on {practice.date.strftime('%A, %B %d')}"
        )

        message_ts = response.get('ts')
        current_app.logger.info(f"Posted substitution request for practice #{practice.id} (ts: {message_ts})")

        return {
            'success': True,
            'message_ts': message_ts,
            'channel_id': channel_id
        }

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error posting substitution request: {error_msg}")
        return {'success': False, 'error': error_msg}


def post_24h_lead_confirmation(
    practices_needing_confirmation: list,
    channel_override: Optional[str] = None
) -> dict:
    """Post 24h lead confirmation request to #coord-practices-leads-assists.

    Tags the assigned leads for each practice needing confirmation.

    Args:
        practices_needing_confirmation: List of tuples (Practice, lead_slack_ids)
        channel_override: Optional channel name to override default (e.g., 'general')

    Returns:
        dict with keys:
        - success: bool
        - message_ts: str (if success)
        - error: str (if failure)
    """
    from app.practices.service import convert_practice_to_info

    if not practices_needing_confirmation:
        return {'success': True, 'message_ts': None, 'skipped': True}

    client = get_slack_client()

    # Determine channel - use override if provided
    if channel_override:
        channel_id = get_channel_id_by_name(channel_override.lstrip('#'))
    else:
        channel_id = COORD_CHANNEL_ID

    # Build message blocks
    blocks = []

    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": ":clock1: Lead Confirmation - Tomorrow's Practices",
            "emoji": True
        }
    })

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "Please confirm your availability for tomorrow's practice(s):"
        }
    })

    blocks.append({"type": "divider"})

    for practice, lead_slack_ids in practices_needing_confirmation:
        practice_info = convert_practice_to_info(practice)
        time_str = practice_info.date.strftime('%-I:%M %p')
        location = practice_info.location.name if practice_info.location else "TBD"

        # Build lead mentions
        lead_mentions = " ".join([f"<@{uid}>" for uid in lead_slack_ids]) or "No lead assigned"

        # Practice type info
        type_names = ", ".join([t.name for t in practice_info.practice_types]) if practice_info.practice_types else "Practice"

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{lead_mentions}\n*{time_str}* - {type_names} at *{location}*"
            }
        })

        # Add confirm/need-sub buttons
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":white_check_mark: I'll be there", "emoji": True},
                    "style": "primary",
                    "action_id": "lead_confirm",
                    "value": str(practice.id)
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":sos: Need a sub", "emoji": True},
                    "style": "danger",
                    "action_id": "lead_need_sub",
                    "value": str(practice.id)
                }
            ]
        })

        blocks.append({"type": "divider"})

    try:
        response = client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text="24h Lead Confirmation",
            unfurl_links=False,
            unfurl_media=False
        )

        message_ts = response.get('ts')
        current_app.logger.info(f"Posted 24h lead confirmation (ts: {message_ts})")

        return {
            'success': True,
            'message_ts': message_ts,
            'channel_id': channel_id
        }

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error posting 24h lead confirmation: {error_msg}")
        return {'success': False, 'error': error_msg}
