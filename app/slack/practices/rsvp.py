"""RSVP thread management operations."""

from datetime import datetime
from typing import Optional
from flask import current_app
from slack_sdk.errors import SlackApiError

from app.slack.client import get_slack_client
from app.practices.models import Practice

from app.slack.practices._config import LOGGING_CHANNEL_ID


def post_thread_reply(
    practice: Practice,
    message: str,
    user_mention: Optional[str] = None
) -> dict:
    """Post a threaded reply to a practice announcement.

    Args:
        practice: Practice SQLAlchemy model with slack_message_ts set
        message: Message text to post
        user_mention: Optional Slack user ID to mention

    Returns:
        dict with keys:
        - success: bool
        - message_ts: str (only if success=True)
        - error: str (only if success=False)
    """
    if not practice.slack_message_ts or not practice.slack_channel_id:
        return {'success': False, 'error': 'No Slack message to reply to'}

    client = get_slack_client()

    # Build message with optional mention
    text = message
    if user_mention:
        text = f"<@{user_mention}> {message}"

    try:
        response = client.chat_postMessage(
            channel=practice.slack_channel_id,
            thread_ts=practice.slack_message_ts,
            text=text
        )

        message_ts = response.get('ts')
        current_app.logger.info(f"Posted thread reply for practice #{practice.id}")

        return {
            'success': True,
            'message_ts': message_ts
        }

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error posting thread reply: {error_msg}")
        return {'success': False, 'error': error_msg}


def update_going_list_thread(practice: Practice) -> dict:
    """Update (or create) a thread reply showing who's going to practice.

    Posts a context-sized reply in the thread with mentions of all "going" RSVPs.

    Args:
        practice: Practice SQLAlchemy model with slack_message_ts set

    Returns:
        dict with keys:
        - success: bool
        - message_ts: str (only if success=True and new message created)
        - error: str (only if success=False)
    """
    if not practice.slack_message_ts or not practice.slack_channel_id:
        return {'success': False, 'error': 'No Slack message to update'}

    from app.practices.models import PracticeRSVP
    from app.models import User

    client = get_slack_client()

    # Get all "going" RSVPs with their Slack user IDs
    going_rsvps = PracticeRSVP.query.filter_by(
        practice_id=practice.id,
        status='going'
    ).all()

    # Build list of mentions
    mentions = []
    for rsvp in going_rsvps:
        if rsvp.slack_user_id:
            mentions.append(f"<@{rsvp.slack_user_id}>")
        elif rsvp.user:
            # Try to get Slack ID from linked user
            if rsvp.user.slack_user:
                mentions.append(f"<@{rsvp.user.slack_user.slack_uid}>")
            else:
                mentions.append(rsvp.user.first_name)

    # Build the going list text
    count = len(mentions)
    if count == 0:
        going_text = ":white_check_mark: *Going (0):* No one yet - be the first!"
    else:
        going_text = f":white_check_mark: *Going ({count}):* {', '.join(mentions)}"

    try:
        # Search thread for our existing going list message
        result = client.conversations_replies(
            channel=practice.slack_channel_id,
            ts=practice.slack_message_ts,
            limit=20
        )

        messages = result.get('messages', [])
        existing_ts = None

        # Find our going list message (starts with :white_check_mark: *Going)
        for msg in messages:
            text = msg.get('text', '')
            if text.startswith(':white_check_mark: *Going'):
                existing_ts = msg.get('ts')
                break

        if existing_ts:
            # Update existing message
            client.chat_update(
                channel=practice.slack_channel_id,
                ts=existing_ts,
                text=going_text
            )
            current_app.logger.info(f"Updated going list for practice #{practice.id}")
            return {'success': True}
        else:
            # Post new thread reply
            response = client.chat_postMessage(
                channel=practice.slack_channel_id,
                thread_ts=practice.slack_message_ts,
                text=going_text
            )
            message_ts = response.get('ts')
            current_app.logger.info(f"Posted going list for practice #{practice.id}")
            return {'success': True, 'message_ts': message_ts}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error updating going list: {error_msg}")
        return {'success': False, 'error': error_msg}


def update_practice_rsvp_counts(practice: Practice) -> dict:
    """Update practice announcement with current going count.

    Updates the last context block in the message with the current going count.

    Args:
        practice: Practice SQLAlchemy model with slack_message_ts set

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    if not practice.slack_message_ts or not practice.slack_channel_id:
        return {'success': False, 'error': 'No Slack message to update'}

    from app.practices.models import PracticeRSVP

    client = get_slack_client()

    # Get going count
    going_count = PracticeRSVP.query.filter_by(
        practice_id=practice.id,
        status='going'
    ).count()

    try:
        # Get the current message
        result = client.conversations_history(
            channel=practice.slack_channel_id,
            latest=practice.slack_message_ts,
            inclusive=True,
            limit=1
        )

        messages = result.get('messages', [])
        if not messages:
            return {'success': False, 'error': 'Original message not found'}

        current_blocks = messages[0].get('blocks', [])

        # Find and update the going count context block
        # It contains ":white_check_mark:" and mentions "going"
        # Search backwards from the end (it's near the end of the message)
        going_context_idx = None
        for i in range(len(current_blocks) - 1, -1, -1):
            block = current_blocks[i]
            if block.get('type') == 'context':
                elements = block.get('elements', [])
                for el in elements:
                    text = el.get('text', '')
                    if ':white_check_mark:' in text and 'going' in text:
                        going_context_idx = i
                        break
            if going_context_idx is not None:
                break

        if going_context_idx is not None:
            current_blocks[going_context_idx] = {
                "type": "context",
                "elements": [{
                    "type": "mrkdwn",
                    "text": f":white_check_mark: *{going_count} going* — _see thread for list_"
                }]
            }

        # Update message
        client.chat_update(
            channel=practice.slack_channel_id,
            ts=practice.slack_message_ts,
            blocks=current_blocks,
            text=f"Practice on {practice.date.strftime('%A, %B %d')}"
        )

        current_app.logger.info(f"Updated going count for practice #{practice.id}: {going_count}")
        return {'success': True}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error updating going count: {error_msg}")
        return {'success': False, 'error': error_msg}


def log_rsvp_action(practice: Practice, slack_user_id: str, action: str) -> dict:
    """Log an RSVP action to the practice's logging thread.

    Args:
        practice: Practice SQLAlchemy model with slack_log_message_ts set
        slack_user_id: Slack user ID who performed the action
        action: 'going' or 'removed'

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    if not practice.slack_log_message_ts:
        return {'success': False, 'error': 'No log thread for this practice'}

    client = get_slack_client()

    # Format the log message
    timestamp = datetime.now().strftime('%-I:%M %p')
    if action == 'going':
        log_text = f":white_check_mark: <@{slack_user_id}> RSVP'd going ({timestamp})"
    else:
        log_text = f":wave: <@{slack_user_id}> removed their RSVP ({timestamp})"

    try:
        client.chat_postMessage(
            channel=LOGGING_CHANNEL_ID,
            thread_ts=practice.slack_log_message_ts,
            text=log_text,
            unfurl_links=False,
            unfurl_media=False
        )

        current_app.logger.info(f"Logged RSVP action for practice #{practice.id}: {action}")
        return {'success': True}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error logging RSVP action: {error_msg}")
        return {'success': False, 'error': error_msg}
