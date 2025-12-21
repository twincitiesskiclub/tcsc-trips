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


def get_slack_user_client() -> WebClient:
    """Get configured Slack WebClient using user token (for admin operations)."""
    token = os.environ.get('SLACK_USER_TOKEN')
    if not token:
        raise ValueError("SLACK_USER_TOKEN not configured")
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


def update_user_profile(slack_uid: str, fields: dict) -> dict:
    """
    Update custom profile fields for a Slack user.

    Args:
        slack_uid: Slack user ID (e.g., U12345ABC)
        fields: Dict of {field_id: value} for custom profile fields

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)

    Note: Requires users.profile:write scope on the USER token (not bot token).
    """
    client = get_slack_user_client()

    try:
        # Build profile payload with custom fields
        profile = {'fields': fields}
        client.users_profile_set(user=slack_uid, profile=profile)
        return {'success': True}
    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Slack API error updating profile for {slack_uid}: {error_msg}")
        return {'success': False, 'error': error_msg}


def get_channel_id_by_name(channel_name: str) -> str | None:
    """
    Look up a channel ID by its name.

    Args:
        channel_name: Channel name without the # prefix

    Returns:
        Channel ID string or None if not found
    """
    client = get_slack_client()
    cursor = None

    try:
        while True:
            response = client.conversations_list(
                cursor=cursor,
                limit=200,
                types='public_channel,private_channel'
            )

            for channel in response.get('channels', []):
                if channel.get('name') == channel_name:
                    return channel.get('id')

            cursor = response.get('response_metadata', {}).get('next_cursor')
            if not cursor:
                break

        return None
    except SlackApiError as e:
        current_app.logger.error(f"Slack API error looking up channel {channel_name}: {e}")
        return None


def get_user_latest_message_in_channel(channel_id: str, user_id: str) -> dict | None:
    """
    Find the most recent message from a user in a channel.

    DEPRECATED: Use get_latest_messages_by_user() for batch lookups.

    Args:
        channel_id: Slack channel ID
        user_id: Slack user ID to search for

    Returns:
        Dict with 'permalink' and 'text' if found, None otherwise
    """
    messages_map = get_latest_messages_by_user(channel_id, max_messages=500)
    return messages_map.get(user_id)


def get_latest_messages_by_user(channel_id: str, max_messages: int = 500) -> dict[str, dict]:
    """
    Fetch channel history once and build a map of each user's latest message.

    Constructs permalinks directly instead of making N API calls.
    Permalink format: https://{workspace}.slack.com/archives/{channel}/p{timestamp}

    Args:
        channel_id: Slack channel ID
        max_messages: Maximum messages to scan (default 500)

    Returns:
        Dict mapping user_id -> {'permalink': str, 'text': str}
        Only includes users who have posted in the scanned range.
    """
    client = get_slack_client()
    user_messages = {}

    # Get workspace domain for constructing permalinks (avoids N API calls)
    workspace_domain = os.environ.get('SLACK_WORKSPACE_DOMAIN', 'twincitiesskiclub')

    try:
        cursor = None
        messages_checked = 0

        while messages_checked < max_messages:
            response = client.conversations_history(
                channel=channel_id,
                cursor=cursor,
                limit=100
            )

            for message in response.get('messages', []):
                messages_checked += 1
                user_id = message.get('user')
                ts = message.get('ts')

                # Skip if no user (bot messages, etc.) or already have this user's latest
                if not user_id or user_id in user_messages:
                    continue

                # Construct permalink directly (no API call needed)
                # Format: remove dot from timestamp "1234567890.123456" -> "p1234567890123456"
                permalink = f"https://{workspace_domain}.slack.com/archives/{channel_id}/p{ts.replace('.', '')}"

                user_messages[user_id] = {
                    'permalink': permalink,
                    'text': message.get('text', '')[:100]
                }

            cursor = response.get('response_metadata', {}).get('next_cursor')
            if not cursor:
                break

        current_app.logger.info(f"Found {len(user_messages)} users with posts in #{channel_id}")
        return user_messages

    except SlackApiError as e:
        current_app.logger.error(f"Slack API error fetching channel history {channel_id}: {e}")
        return {}


# =============================================================================
# Channel Sync Operations (for Slack channel membership management)
# =============================================================================


def get_team_id() -> str:
    """Get the Slack workspace team ID.

    Required for admin API operations that need team_id parameter.

    Returns:
        The team ID string (e.g., 'T02J2AVLSCT')

    Raises:
        SlackApiError: If API call fails
    """
    client = get_slack_client()
    try:
        response = client.team_info()
        return response['team']['id']
    except SlackApiError as e:
        current_app.logger.error(f"Slack API error fetching team info: {e}")
        raise


def get_channel_maps() -> tuple[dict[str, str], dict[str, dict]]:
    """Get channel name-to-ID and ID-to-properties mappings.

    Returns a tuple of:
    - channel_name_to_id: Dict mapping channel name -> channel ID
    - channel_id_to_properties: Dict mapping channel ID -> channel properties
      (includes is_public, is_private, name, etc.)

    Fetches both public and private channels.
    Handles pagination automatically.
    """
    client = get_slack_client()
    channel_name_to_id = {}
    channel_id_to_properties = {}
    cursor = None

    try:
        while True:
            response = client.conversations_list(
                cursor=cursor,
                limit=200,
                types='public_channel,private_channel'
            )

            for channel in response.get('channels', []):
                name = channel.get('name')
                channel_id = channel.get('id')

                if name and channel_id:
                    channel_name_to_id[name] = channel_id

                    # Store properties including public/private status
                    channel_id_to_properties[channel_id] = {
                        'name': name,
                        'id': channel_id,
                        'is_private': channel.get('is_private', False),
                        'is_public': not channel.get('is_private', False),
                        'is_channel': channel.get('is_channel', True),
                        'is_archived': channel.get('is_archived', False),
                        'num_members': channel.get('num_members', 0),
                    }

            cursor = response.get('response_metadata', {}).get('next_cursor')
            if not cursor:
                break

        current_app.logger.info(
            f"Fetched {len(channel_name_to_id)} channels from Slack"
        )
        return channel_name_to_id, channel_id_to_properties

    except SlackApiError as e:
        current_app.logger.error(f"Slack API error fetching channels: {e}")
        raise


def get_user_channels(user_id: str) -> set[str]:
    """Get all channel IDs a user is a member of.

    Args:
        user_id: Slack user ID

    Returns:
        Set of channel IDs the user belongs to

    Handles pagination automatically.
    """
    client = get_slack_client()
    channel_ids = set()
    cursor = None

    try:
        while True:
            response = client.users_conversations(
                user=user_id,
                cursor=cursor,
                limit=200,
                types='public_channel,private_channel'
            )

            for channel in response.get('channels', []):
                if channel.get('id'):
                    channel_ids.add(channel['id'])

            cursor = response.get('response_metadata', {}).get('next_cursor')
            if not cursor:
                break

        return channel_ids

    except SlackApiError as e:
        current_app.logger.error(f"Slack API error fetching channels for user {user_id}: {e}")
        raise


def add_user_to_channel(
    user_id: str,
    channel_id: str,
    email: str = '',
    dry_run: bool = False
) -> bool:
    """Add a user to a channel.

    Args:
        user_id: Slack user ID
        channel_id: Slack channel ID
        email: User email (for logging)
        dry_run: If True, only log what would be done

    Returns:
        True if user was added or already in channel, False on error
    """
    if dry_run:
        user_str = f"{email} ({user_id})" if email else user_id
        current_app.logger.info(f"[DRY RUN] Would add {user_str} to channel {channel_id}")
        return True

    client = get_slack_client()

    try:
        client.conversations_invite(channel=channel_id, users=user_id)
        user_str = f"{email} ({user_id})" if email else user_id
        current_app.logger.info(f"Added {user_str} to channel {channel_id}")
        return True

    except SlackApiError as e:
        error = e.response.get('error', '')
        user_str = f"{email} ({user_id})" if email else user_id

        if error == 'already_in_channel':
            current_app.logger.debug(f"{user_str} already in channel {channel_id}")
            return True
        elif error == 'is_archived':
            current_app.logger.warning(f"Cannot add {user_str} to archived channel {channel_id}")
            return False
        elif error == 'channel_not_found':
            current_app.logger.error(f"Channel {channel_id} not found when adding {user_str}")
            return False
        else:
            current_app.logger.error(f"Error adding {user_str} to channel {channel_id}: {error}")
            raise


def remove_user_from_channel(
    user_id: str,
    channel_id: str,
    email: str = '',
    dry_run: bool = False
) -> bool:
    """Remove a user from a channel.

    Args:
        user_id: Slack user ID
        channel_id: Slack channel ID
        email: User email (for logging)
        dry_run: If True, only log what would be done

    Returns:
        True if user was removed or not in channel, False on error
    """
    if dry_run:
        user_str = f"{email} ({user_id})" if email else user_id
        current_app.logger.info(f"[DRY RUN] Would remove {user_str} from channel {channel_id}")
        return True

    client = get_slack_client()

    try:
        client.conversations_kick(channel=channel_id, user=user_id)
        user_str = f"{email} ({user_id})" if email else user_id
        current_app.logger.info(f"Removed {user_str} from channel {channel_id}")
        return True

    except SlackApiError as e:
        error = e.response.get('error', '')
        user_str = f"{email} ({user_id})" if email else user_id

        if error == 'not_in_channel':
            current_app.logger.debug(f"{user_str} not in channel {channel_id}, no action needed")
            return True
        elif error == 'cant_kick_from_general':
            current_app.logger.warning(f"Cannot remove {user_str} from #general channel")
            return False
        elif error == 'channel_not_found':
            current_app.logger.error(f"Channel {channel_id} not found when removing {user_str}")
            return False
        elif error in ('restricted_action', 'user_is_restricted'):
            # Can't kick restricted users via this API - they're managed via admin APIs
            current_app.logger.debug(
                f"Cannot kick restricted user {user_str} from {channel_id} via conversations.kick"
            )
            return False
        else:
            current_app.logger.error(f"Error removing {user_str} from channel {channel_id}: {error}")
            raise


def fetch_all_slack_users() -> list[dict]:
    """Fetch all workspace members with full Slack user objects.

    Unlike fetch_workspace_members() which returns a simplified dict,
    this returns the raw Slack user objects with all fields including:
    - is_admin, is_owner, is_bot, is_restricted, is_ultra_restricted
    - deleted (deactivated status)
    - profile with email

    Used for channel sync where we need to process ALL Slack users,
    not just those matched to database records.

    Returns:
        List of raw Slack user dicts
    """
    client = get_slack_client()
    users = []
    cursor = None

    try:
        while True:
            response = client.users_list(cursor=cursor, limit=200)

            for user in response.get('members', []):
                # Skip Slackbot
                if user.get('id') == 'USLACKBOT':
                    continue

                users.append(user)

            cursor = response.get('response_metadata', {}).get('next_cursor')
            if not cursor:
                break

        current_app.logger.info(f"Fetched {len(users)} Slack users")
        return users

    except SlackApiError as e:
        current_app.logger.error(f"Slack API error fetching users: {e}")
        raise
