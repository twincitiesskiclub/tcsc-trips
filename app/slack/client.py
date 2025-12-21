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
