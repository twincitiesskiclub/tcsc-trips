"""Slack API client for workspace member management."""
import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from flask import current_app


def get_slack_client() -> WebClient:
    """Get configured Slack WebClient using bot token."""
    token = os.environ.get('SLACK_BOT_TOKEN')
    if not token:
        raise ValueError("SLACK_BOT_TOKEN not configured")
    return WebClient(token=token)


def fetch_workspace_members() -> list[dict]:
    """
    Fetch all workspace members via Slack users.list API.

    Returns:
        List of member dicts with keys:
        - slack_uid: Slack user ID (e.g., U12345ABC)
        - email: User's email (may be None for bots/restricted)
        - display_name: Slack display name
        - full_name: Real name
        - title: Job title
        - phone: Phone number
        - status: Status text
        - timezone: Timezone string
        - is_bot: Whether this is a bot account
        - deleted: Whether account is deactivated

    Handles pagination automatically.
    """
    client = get_slack_client()
    members = []
    cursor = None

    while True:
        try:
            response = client.users_list(cursor=cursor, limit=200)

            for member in response.get('members', []):
                # Skip Slackbot
                if member.get('id') == 'USLACKBOT':
                    continue

                profile = member.get('profile', {})

                members.append({
                    'slack_uid': member.get('id'),
                    'email': profile.get('email'),
                    'display_name': profile.get('display_name') or profile.get('real_name'),
                    'full_name': profile.get('real_name'),
                    'title': profile.get('title'),
                    'phone': profile.get('phone'),
                    'status': profile.get('status_text'),
                    'timezone': member.get('tz'),
                    'is_bot': member.get('is_bot', False),
                    'deleted': member.get('deleted', False),
                })

            # Check for more pages
            cursor = response.get('response_metadata', {}).get('next_cursor')
            if not cursor:
                break

        except SlackApiError as e:
            current_app.logger.error(f"Slack API error fetching members: {e}")
            raise

    return members


def get_user_by_email(email: str) -> dict | None:
    """
    Look up a Slack user by email address.

    Returns member dict or None if not found.
    """
    client = get_slack_client()

    try:
        response = client.users_lookupByEmail(email=email)
        user = response.get('user', {})
        profile = user.get('profile', {})

        return {
            'slack_uid': user.get('id'),
            'email': profile.get('email'),
            'display_name': profile.get('display_name') or profile.get('real_name'),
            'full_name': profile.get('real_name'),
            'title': profile.get('title'),
            'phone': profile.get('phone'),
            'status': profile.get('status_text'),
            'timezone': user.get('tz'),
            'is_bot': user.get('is_bot', False),
            'deleted': user.get('deleted', False),
        }
    except SlackApiError as e:
        if e.response.get('error') == 'users_not_found':
            return None
        current_app.logger.error(f"Slack API error looking up {email}: {e}")
        raise


def send_direct_message(slack_uid: str, text: str) -> dict:
    """
    Send a direct message to a single Slack user.

    Args:
        slack_uid: Slack user ID (e.g., U12345ABC)
        text: Message text to send

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    client = get_slack_client()

    try:
        client.chat_postMessage(channel=slack_uid, text=text)
        return {'success': True}
    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Slack API error sending DM to {slack_uid}: {error_msg}")
        return {'success': False, 'error': error_msg}


def open_conversation(user_ids: list[str]) -> dict:
    """
    Open or retrieve a conversation (DM or MPDM).

    For a single user, opens a 1:1 DM.
    For multiple users, opens a multi-party DM (MPDM).

    Args:
        user_ids: List of Slack user IDs to include in conversation

    Returns:
        dict with keys:
        - success: bool
        - channel_id: str (only if success=True)
        - error: str (only if success=False)
    """
    if not user_ids:
        return {'success': False, 'error': 'No user IDs provided'}

    client = get_slack_client()

    try:
        response = client.conversations_open(users=','.join(user_ids))
        channel_id = response.get('channel', {}).get('id')
        return {'success': True, 'channel_id': channel_id}
    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Slack API error opening conversation: {error_msg}")
        return {'success': False, 'error': error_msg}


def send_message_to_channel(channel_id: str, text: str) -> dict:
    """
    Send a message to a channel or conversation.

    Args:
        channel_id: Slack channel/conversation ID
        text: Message text to send

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    client = get_slack_client()

    try:
        client.chat_postMessage(channel=channel_id, text=text)
        return {'success': True}
    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Slack API error sending to {channel_id}: {error_msg}")
        return {'success': False, 'error': error_msg}
