"""
Slack message collection for the Weekly Dispatch newsletter.

Collects messages from configured public and private Slack channels,
respecting privacy rules and engagement metrics for newsletter content.
"""

import logging
import os
from datetime import datetime
from typing import Optional

import yaml
from slack_sdk.errors import SlackApiError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.newsletter.interfaces import SlackMessage, MessageVisibility
from app.slack.client import get_slack_client

logger = logging.getLogger(__name__)

# Cache for channel info to avoid repeated lookups
_channel_cache: dict[str, dict] = {}
_user_cache: dict[str, str] = {}


def _load_config() -> dict:
    """Load newsletter configuration from YAML file.

    Returns:
        dict: Newsletter configuration or empty dict if file not found.
    """
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        'config',
        'newsletter.yaml'
    )

    try:
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.warning(f"Newsletter config not found at {config_path}")
        return {}
    except yaml.YAMLError as e:
        logger.error(f"Error parsing newsletter config: {e}")
        return {}


def _get_channel_info(channel_id: str) -> dict:
    """Get channel info with caching.

    Args:
        channel_id: Slack channel ID.

    Returns:
        dict with 'name' and 'is_private' keys, or empty dict on error.
    """
    if channel_id in _channel_cache:
        return _channel_cache[channel_id]

    client = get_slack_client()

    try:
        result = client.conversations_info(channel=channel_id)
        channel = result.get('channel', {})
        info = {
            'name': channel.get('name', ''),
            'is_private': channel.get('is_private', False),
        }
        _channel_cache[channel_id] = info
        return info
    except SlackApiError as e:
        logger.error(f"Error fetching channel info for {channel_id}: {e}")
        return {'name': '', 'is_private': False}


def _get_user_name(user_id: str) -> str:
    """Get user display name with caching.

    Args:
        user_id: Slack user ID.

    Returns:
        User display name or user_id if lookup fails.
    """
    if user_id in _user_cache:
        return _user_cache[user_id]

    client = get_slack_client()

    try:
        result = client.users_info(user=user_id)
        user = result.get('user', {})
        profile = user.get('profile', {})
        # Prefer display_name, fall back to real_name, then user_id
        name = (
            profile.get('display_name')
            or profile.get('real_name')
            or user_id
        )
        _user_cache[user_id] = name
        return name
    except SlackApiError as e:
        logger.warning(f"Error fetching user info for {user_id}: {e}")
        _user_cache[user_id] = user_id
        return user_id


@retry(
    retry=retry_if_exception_type(SlackApiError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True,
)
def get_message_permalink(channel_id: str, message_ts: str) -> Optional[str]:
    """Get permalink URL for a specific message.

    Args:
        channel_id: Slack channel ID.
        message_ts: Message timestamp.

    Returns:
        Permalink URL or None if unavailable.
    """
    client = get_slack_client()

    try:
        result = client.chat_getPermalink(
            channel=channel_id,
            message_ts=message_ts
        )
        return result.get('permalink')
    except SlackApiError as e:
        error_code = e.response.get('error', '')
        if error_code in ('message_not_found', 'channel_not_found'):
            logger.warning(
                f"Cannot get permalink for {channel_id}/{message_ts}: {error_code}"
            )
            return None
        raise


def _parse_message_timestamp(ts: str) -> Optional[datetime]:
    """Convert Slack message timestamp to datetime.

    Args:
        ts: Slack timestamp string (e.g., '1234567890.123456').

    Returns:
        datetime object or None if parsing fails.
    """
    try:
        # Slack timestamps are Unix timestamps with microseconds after the dot
        unix_ts = float(ts)
        return datetime.fromtimestamp(unix_ts)
    except (ValueError, TypeError):
        return None


def _count_reactions(message: dict) -> int:
    """Count total reactions on a message.

    Args:
        message: Slack message dict.

    Returns:
        Total reaction count.
    """
    reactions = message.get('reactions', [])
    return sum(r.get('count', 0) for r in reactions)


def _count_replies(message: dict) -> int:
    """Count replies in a message thread.

    Args:
        message: Slack message dict.

    Returns:
        Reply count (excluding parent message).
    """
    return message.get('reply_count', 0)


@retry(
    retry=retry_if_exception_type(SlackApiError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True,
)
def collect_channel_messages(
    channel_id: str,
    since: datetime,
    is_private: bool = False
) -> list[SlackMessage]:
    """Collect messages from a single Slack channel.

    Args:
        channel_id: Slack channel ID to collect from.
        since: Only collect messages after this timestamp.
        is_private: Whether this is a private channel (affects privacy rules).

    Returns:
        List of SlackMessage objects.

    Privacy rules:
        - Public channels: Include permalinks, can quote and name users.
        - Private channels: NO permalinks, summarize only, no names unless permitted.
    """
    client = get_slack_client()
    messages: list[SlackMessage] = []

    # Get channel info for name
    channel_info = _get_channel_info(channel_id)
    channel_name = channel_info.get('name', channel_id)

    # Override is_private if channel info indicates it
    if channel_info.get('is_private'):
        is_private = True

    visibility = MessageVisibility.PRIVATE if is_private else MessageVisibility.PUBLIC

    logger.info(
        f"Collecting messages from #{channel_name} "
        f"(private={is_private}) since {since.isoformat()}"
    )

    oldest_ts = str(since.timestamp())
    cursor = None
    total_fetched = 0

    try:
        while True:
            # Build API call parameters
            params = {
                'channel': channel_id,
                'oldest': oldest_ts,
                'limit': 100,
            }
            if cursor:
                params['cursor'] = cursor

            result = client.conversations_history(**params)

            for msg in result.get('messages', []):
                total_fetched += 1

                # Skip bot messages, system messages, and message subtypes
                if msg.get('subtype') or msg.get('bot_id'):
                    continue

                # Skip messages without user (shouldn't happen but be safe)
                user_id = msg.get('user')
                if not user_id:
                    continue

                message_ts = msg.get('ts', '')
                text = msg.get('text', '')

                # Skip empty messages
                if not text.strip():
                    continue

                # Get user name
                user_name = _get_user_name(user_id)

                # Get permalink only for public channels
                permalink = None
                if not is_private:
                    permalink = get_message_permalink(channel_id, message_ts)

                # Create SlackMessage
                slack_message = SlackMessage(
                    channel_id=channel_id,
                    channel_name=channel_name,
                    message_ts=message_ts,
                    user_id=user_id,
                    user_name=user_name,
                    text=text,
                    permalink=permalink,
                    reaction_count=_count_reactions(msg),
                    reply_count=_count_replies(msg),
                    visibility=visibility,
                    posted_at=_parse_message_timestamp(message_ts),
                )
                messages.append(slack_message)

            # Check for more pages
            cursor = result.get('response_metadata', {}).get('next_cursor')
            if not cursor:
                break

        logger.info(
            f"Collected {len(messages)} messages from #{channel_name} "
            f"(scanned {total_fetched} total)"
        )

    except SlackApiError as e:
        error_code = e.response.get('error', '')
        if error_code == 'channel_not_found':
            logger.error(f"Channel {channel_id} not found")
            return []
        elif error_code == 'not_in_channel':
            logger.error(
                f"Bot not a member of #{channel_name}. "
                f"Invite the bot to collect messages."
            )
            return []
        else:
            raise

    return messages


def _get_all_public_channels() -> list[dict]:
    """Get list of all public channels the bot can access.

    Returns:
        List of dicts with 'id' and 'name' keys.
    """
    client = get_slack_client()
    channels = []
    cursor = None

    try:
        while True:
            result = client.conversations_list(
                cursor=cursor,
                limit=200,
                types='public_channel',
                exclude_archived=True,
            )

            for channel in result.get('channels', []):
                # Only include channels the bot is a member of
                if channel.get('is_member'):
                    channels.append({
                        'id': channel.get('id'),
                        'name': channel.get('name'),
                    })

            cursor = result.get('response_metadata', {}).get('next_cursor')
            if not cursor:
                break

    except SlackApiError as e:
        logger.error(f"Error listing public channels: {e}")

    return channels


def _resolve_channel_id(channel_name: str) -> Optional[str]:
    """Resolve channel name to channel ID.

    Args:
        channel_name: Channel name without # prefix.

    Returns:
        Channel ID or None if not found.
    """
    client = get_slack_client()
    cursor = None

    try:
        while True:
            result = client.conversations_list(
                cursor=cursor,
                limit=200,
                types='public_channel,private_channel',
            )

            for channel in result.get('channels', []):
                if channel.get('name') == channel_name:
                    return channel.get('id')

            cursor = result.get('response_metadata', {}).get('next_cursor')
            if not cursor:
                break

    except SlackApiError as e:
        logger.error(f"Error resolving channel name {channel_name}: {e}")

    return None


def collect_all_messages(since: datetime) -> list[SlackMessage]:
    """Collect messages from all configured channels.

    Reads channel configuration from config/newsletter.yaml:
    - Collects from all public channels (where bot is member)
    - Excludes channels in channels.public_exclude
    - Includes private channels in channels.private_include (bot must be member)

    Args:
        since: Only collect messages after this timestamp.

    Returns:
        List of SlackMessage objects from all channels, sorted by posted_at desc.
    """
    config = _load_config()
    newsletter_config = config.get('newsletter', {})
    channel_config = newsletter_config.get('channels', {})

    # Get exclusion list for public channels
    public_exclude = set(channel_config.get('public_exclude', []))

    # Get inclusion list for private channels
    private_include = channel_config.get('private_include', [])

    all_messages: list[SlackMessage] = []

    # Collect from public channels
    logger.info("Fetching list of public channels...")
    public_channels = _get_all_public_channels()
    logger.info(f"Found {len(public_channels)} public channels with bot membership")

    for channel in public_channels:
        channel_name = channel.get('name', '')
        channel_id = channel.get('id')

        # Skip excluded channels
        if channel_name in public_exclude:
            logger.debug(f"Skipping excluded channel #{channel_name}")
            continue

        try:
            messages = collect_channel_messages(
                channel_id=channel_id,
                since=since,
                is_private=False,
            )
            all_messages.extend(messages)
        except SlackApiError as e:
            logger.error(f"Failed to collect from #{channel_name}: {e}")
            continue

    # Collect from configured private channels
    logger.info(f"Collecting from {len(private_include)} private channels...")
    for channel_name in private_include:
        channel_id = _resolve_channel_id(channel_name)
        if not channel_id:
            logger.warning(
                f"Private channel #{channel_name} not found or bot not a member"
            )
            continue

        try:
            messages = collect_channel_messages(
                channel_id=channel_id,
                since=since,
                is_private=True,
            )
            all_messages.extend(messages)
        except SlackApiError as e:
            logger.error(f"Failed to collect from private #{channel_name}: {e}")
            continue

    # Sort by posted_at descending (most recent first)
    all_messages.sort(
        key=lambda m: m.posted_at or datetime.min,
        reverse=True,
    )

    logger.info(
        f"Collected {len(all_messages)} total messages from "
        f"{len(public_channels) - len(public_exclude) + len(private_include)} channels"
    )

    return all_messages


def clear_caches() -> None:
    """Clear internal caches for channel and user info.

    Call this if you need fresh data after cache has become stale.
    """
    global _channel_cache, _user_cache
    _channel_cache.clear()
    _user_cache.clear()
    logger.debug("Cleared collector caches")
