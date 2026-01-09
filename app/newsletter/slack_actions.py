"""
Slack actions for the Weekly Dispatch newsletter system.

Manages the "living post" in Slack that shows the latest newsletter version,
with version history in thread replies. Handles publishing workflow including
review buttons and final publication.
"""

import os
import yaml
import logging
from datetime import datetime
from typing import Optional

from slack_sdk.errors import SlackApiError

from app.models import db
from app.newsletter.interfaces import (
    SlackPostReference,
    PublishResult,
    VersionTrigger,
    NewsletterStatus,
)
from app.newsletter.models import Newsletter, NewsletterVersion
from app.slack.client import get_slack_client, get_channel_id_by_name

logger = logging.getLogger(__name__)

# Module-level config cache
_config_cache = None


# =============================================================================
# Configuration
# =============================================================================

def _load_config() -> dict:
    """Load newsletter configuration from YAML (cached after first load)."""
    global _config_cache
    if _config_cache is None:
        config_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'config', 'newsletter.yaml'
        )
        with open(config_path, 'r') as f:
            _config_cache = yaml.safe_load(f)
    return _config_cache


def reload_config() -> dict:
    """Force reload of config from disk (useful for testing or config changes)."""
    global _config_cache
    _config_cache = None
    return _load_config()


def get_living_post_channel() -> Optional[str]:
    """Get channel ID for living post from config.

    Returns:
        Channel ID string or None if channel not found
    """
    try:
        config = _load_config()
        channel_name = config.get('newsletter', {}).get('channels', {}).get(
            'living_post_channel', 'tcsc-logging'
        )
        # Remove # prefix if present
        channel_name = channel_name.lstrip('#')
        channel_id = get_channel_id_by_name(channel_name)
        if not channel_id:
            logger.error(f"Could not find living post channel: #{channel_name}")
        return channel_id
    except Exception as e:
        logger.error(f"Error loading living post channel from config: {e}")
        return None


def get_publish_channel() -> Optional[str]:
    """Get channel ID for final newsletter publication from config.

    Returns:
        Channel ID string or None if channel not found
    """
    try:
        config = _load_config()
        channel_name = config.get('newsletter', {}).get('channels', {}).get(
            'publish_channel', 'announcements-tcsc'
        )
        # Remove # prefix if present
        channel_name = channel_name.lstrip('#')
        channel_id = get_channel_id_by_name(channel_name)
        if not channel_id:
            logger.error(f"Could not find publish channel: #{channel_name}")
        return channel_id
    except Exception as e:
        logger.error(f"Error loading publish channel from config: {e}")
        return None


def is_dry_run() -> bool:
    """Check if newsletter system is in dry-run mode."""
    try:
        config = _load_config()
        return config.get('newsletter', {}).get('dry_run', True)
    except Exception:
        return True  # Default to dry-run if config fails


# =============================================================================
# Block Kit Builders
# =============================================================================

def _build_newsletter_blocks(
    content: str,
    version_number: int,
    status: str,
    include_review_buttons: bool = False,
    newsletter_id: Optional[int] = None
) -> list[dict]:
    """Build Block Kit blocks for newsletter message.

    Args:
        content: Newsletter markdown content
        version_number: Current version number
        status: Newsletter status string
        include_review_buttons: Whether to add Approve/Request Changes buttons
        newsletter_id: Newsletter ID for button values

    Returns:
        List of Block Kit block dicts
    """
    blocks = []

    # Header with version info
    status_emoji = {
        NewsletterStatus.BUILDING.value: ':hammer_and_wrench:',
        NewsletterStatus.READY_FOR_REVIEW.value: ':eyes:',
        NewsletterStatus.APPROVED.value: ':white_check_mark:',
        NewsletterStatus.PUBLISHED.value: ':mega:',
    }.get(status, ':newspaper:')

    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": f"{status_emoji} Weekly Dispatch v{version_number}",
            "emoji": True
        }
    })

    # Status context
    status_text = {
        NewsletterStatus.BUILDING.value: 'Building - updates daily at 8am',
        NewsletterStatus.READY_FOR_REVIEW.value: 'Ready for Review',
        NewsletterStatus.APPROVED.value: 'Approved - awaiting publication',
        NewsletterStatus.PUBLISHED.value: 'Published',
    }.get(status, status)

    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": f"*Status:* {status_text} | *Last updated:* <!date^{int(datetime.utcnow().timestamp())}^{{date_short_pretty}} at {{time}}|just now>"
        }]
    })

    blocks.append({"type": "divider"})

    # Main content - split into sections if long
    # Slack has a 3000 char limit per text block
    MAX_SECTION_LENGTH = 2900

    if len(content) <= MAX_SECTION_LENGTH:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": content
            }
        })
    else:
        # Split content at paragraph boundaries
        paragraphs = content.split('\n\n')
        current_section = ""

        for para in paragraphs:
            if len(current_section) + len(para) + 2 <= MAX_SECTION_LENGTH:
                if current_section:
                    current_section += '\n\n'
                current_section += para
            else:
                if current_section:
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": current_section
                        }
                    })
                current_section = para

        # Add remaining content
        if current_section:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": current_section
                }
            })

    # Review buttons (for finalized newsletters awaiting approval)
    if include_review_buttons and newsletter_id:
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Approve & Publish",
                        "emoji": True
                    },
                    "style": "primary",
                    "action_id": "newsletter_approve",
                    "value": str(newsletter_id)
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Request Changes",
                        "emoji": True
                    },
                    "action_id": "newsletter_request_changes",
                    "value": str(newsletter_id)
                }
            ]
        })

    return blocks


def _build_version_thread_blocks(version: NewsletterVersion) -> list[dict]:
    """Build Block Kit blocks for version history thread reply.

    Args:
        version: NewsletterVersion model

    Returns:
        List of Block Kit block dicts
    """
    # Trigger type emoji
    trigger_emoji = {
        VersionTrigger.SCHEDULED.value: ':clock8:',
        VersionTrigger.MANUAL.value: ':hand:',
        VersionTrigger.SUBMISSION.value: ':envelope:',
        VersionTrigger.FEEDBACK.value: ':speech_balloon:',
    }.get(version.trigger_type, ':page_facing_up:')

    # Trigger description
    trigger_desc = {
        VersionTrigger.SCHEDULED.value: 'Scheduled daily update',
        VersionTrigger.MANUAL.value: 'Manual regeneration',
        VersionTrigger.SUBMISSION.value: 'New submission added',
        VersionTrigger.FEEDBACK.value: 'Feedback incorporated',
    }.get(version.trigger_type, version.trigger_type)

    # Content preview (truncated)
    content_preview = version.content[:500]
    if len(version.content) > 500:
        content_preview += '...'

    blocks = [
        {
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": f"{trigger_emoji} *Version {version.version_number}* - {trigger_desc} - <!date^{int(version.created_at.timestamp())}^{{date_short_pretty}} at {{time}}|{version.created_at.strftime('%Y-%m-%d %H:%M')}>"
            }]
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"```{content_preview}```"
            }
        }
    ]

    # Add generation metadata if available
    if version.model_used or version.tokens_used:
        meta_parts = []
        if version.model_used:
            meta_parts.append(f"Model: {version.model_used}")
        if version.tokens_used:
            meta_parts.append(f"Tokens: {version.tokens_used:,}")
        if version.generation_time_ms:
            meta_parts.append(f"Time: {version.generation_time_ms}ms")

        blocks.append({
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": " | ".join(meta_parts)
            }]
        })

    return blocks


# =============================================================================
# Living Post Management
# =============================================================================

def create_living_post(newsletter: Newsletter, content: str) -> SlackPostReference:
    """Create initial living post for a new newsletter week.

    Posts to configured living post channel (default #tcsc-logging).
    Saves message_ts to newsletter.slack_main_message_ts.

    Args:
        newsletter: Newsletter model to create post for
        content: Initial newsletter content

    Returns:
        SlackPostReference with channel_id and message_ts

    Raises:
        SlackApiError: If Slack API call fails
        ValueError: If channel cannot be found
    """
    channel_id = get_living_post_channel()
    if not channel_id:
        raise ValueError("Could not find living post channel")

    dry_run = is_dry_run()

    if dry_run:
        logger.info(
            f"[DRY RUN] Would create living post for newsletter #{newsletter.id} "
            f"in channel {channel_id}"
        )
        # Return a mock reference for dry run
        return SlackPostReference(
            channel_id=channel_id,
            message_ts="dry_run_ts"
        )

    client = get_slack_client()

    # Build blocks
    blocks = _build_newsletter_blocks(
        content=content,
        version_number=newsletter.current_version,
        status=newsletter.status
    )

    # Create week date range for fallback text
    week_str = f"{newsletter.week_start.strftime('%b %d')} - {newsletter.week_end.strftime('%b %d')}"
    fallback_text = f"Weekly Dispatch ({week_str}) - v{newsletter.current_version}"

    try:
        response = client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text=fallback_text,
            unfurl_links=False,
            unfurl_media=False
        )

        message_ts = response.get('ts')
        logger.info(
            f"Created living post for newsletter #{newsletter.id} "
            f"(channel: {channel_id}, ts: {message_ts})"
        )

        # Save Slack references to newsletter
        newsletter.slack_channel_id = channel_id
        newsletter.slack_main_message_ts = message_ts
        db.session.commit()

        return SlackPostReference(
            channel_id=channel_id,
            message_ts=message_ts
        )

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        logger.error(f"Error creating living post for newsletter #{newsletter.id}: {error_msg}")
        raise


def update_living_post(
    newsletter: Newsletter,
    content: str,
    version_number: int
) -> SlackPostReference:
    """Update existing living post with new content.

    Uses chat.update to modify the main post in place.

    Args:
        newsletter: Newsletter model with slack_main_message_ts set
        content: Updated newsletter content
        version_number: New version number

    Returns:
        SlackPostReference with channel_id and message_ts

    Raises:
        SlackApiError: If Slack API call fails
        ValueError: If no existing message to update
    """
    if not newsletter.slack_main_message_ts or not newsletter.slack_channel_id:
        raise ValueError("No Slack message to update - create living post first")

    dry_run = is_dry_run()

    if dry_run:
        logger.info(
            f"[DRY RUN] Would update living post for newsletter #{newsletter.id} "
            f"to version {version_number}"
        )
        return SlackPostReference(
            channel_id=newsletter.slack_channel_id,
            message_ts=newsletter.slack_main_message_ts
        )

    client = get_slack_client()

    # Determine if we need review buttons
    include_buttons = newsletter.status == NewsletterStatus.READY_FOR_REVIEW.value

    # Build blocks
    blocks = _build_newsletter_blocks(
        content=content,
        version_number=version_number,
        status=newsletter.status,
        include_review_buttons=include_buttons,
        newsletter_id=newsletter.id
    )

    # Create fallback text
    week_str = f"{newsletter.week_start.strftime('%b %d')} - {newsletter.week_end.strftime('%b %d')}"
    fallback_text = f"Weekly Dispatch ({week_str}) - v{version_number}"

    try:
        client.chat_update(
            channel=newsletter.slack_channel_id,
            ts=newsletter.slack_main_message_ts,
            blocks=blocks,
            text=fallback_text
        )

        logger.info(
            f"Updated living post for newsletter #{newsletter.id} to v{version_number}"
        )

        return SlackPostReference(
            channel_id=newsletter.slack_channel_id,
            message_ts=newsletter.slack_main_message_ts
        )

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        logger.error(f"Error updating living post for newsletter #{newsletter.id}: {error_msg}")
        raise


def add_version_to_thread(
    newsletter: Newsletter,
    version: NewsletterVersion
) -> SlackPostReference:
    """Add version history as thread reply.

    Posts reply with version number, timestamp, trigger type,
    and truncated content preview. Saves thread_ts to version.slack_thread_ts.

    Args:
        newsletter: Newsletter model with slack_main_message_ts set
        version: NewsletterVersion to add to thread

    Returns:
        SlackPostReference with channel_id, message_ts, and thread_ts

    Raises:
        SlackApiError: If Slack API call fails
        ValueError: If no parent message to reply to
    """
    if not newsletter.slack_main_message_ts or not newsletter.slack_channel_id:
        raise ValueError("No Slack message to reply to - create living post first")

    dry_run = is_dry_run()

    if dry_run:
        logger.info(
            f"[DRY RUN] Would add version {version.version_number} "
            f"to thread for newsletter #{newsletter.id}"
        )
        return SlackPostReference(
            channel_id=newsletter.slack_channel_id,
            message_ts="dry_run_thread_ts",
            thread_ts=newsletter.slack_main_message_ts
        )

    client = get_slack_client()

    # Build thread reply blocks
    blocks = _build_version_thread_blocks(version)

    # Trigger description for fallback
    trigger_desc = {
        VersionTrigger.SCHEDULED.value: 'scheduled',
        VersionTrigger.MANUAL.value: 'manual',
        VersionTrigger.SUBMISSION.value: 'submission',
        VersionTrigger.FEEDBACK.value: 'feedback',
    }.get(version.trigger_type, version.trigger_type)

    fallback_text = f"Version {version.version_number} ({trigger_desc})"

    try:
        response = client.chat_postMessage(
            channel=newsletter.slack_channel_id,
            thread_ts=newsletter.slack_main_message_ts,
            blocks=blocks,
            text=fallback_text,
            unfurl_links=False,
            unfurl_media=False
        )

        thread_ts = response.get('ts')
        logger.info(
            f"Added version {version.version_number} to thread "
            f"for newsletter #{newsletter.id} (ts: {thread_ts})"
        )

        # Save thread_ts to version
        version.slack_thread_ts = thread_ts
        db.session.commit()

        return SlackPostReference(
            channel_id=newsletter.slack_channel_id,
            message_ts=thread_ts,
            thread_ts=newsletter.slack_main_message_ts
        )

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        logger.error(
            f"Error adding version {version.version_number} to thread "
            f"for newsletter #{newsletter.id}: {error_msg}"
        )
        raise


def add_review_buttons(newsletter: Newsletter) -> bool:
    """Add Approve/Request Changes buttons to living post.

    Called on Sunday finalization to enable admin review workflow.
    Uses Block Kit buttons with action_ids: newsletter_approve, newsletter_request_changes.

    Args:
        newsletter: Newsletter model with slack_main_message_ts set

    Returns:
        True if buttons were added successfully

    Raises:
        SlackApiError: If Slack API call fails
    """
    if not newsletter.slack_main_message_ts or not newsletter.slack_channel_id:
        logger.error("No Slack message to add buttons to")
        return False

    if not newsletter.current_content:
        logger.error("No content to display with buttons")
        return False

    dry_run = is_dry_run()

    if dry_run:
        logger.info(
            f"[DRY RUN] Would add review buttons to newsletter #{newsletter.id}"
        )
        return True

    client = get_slack_client()

    # Build blocks with review buttons
    blocks = _build_newsletter_blocks(
        content=newsletter.current_content,
        version_number=newsletter.current_version,
        status=NewsletterStatus.READY_FOR_REVIEW.value,
        include_review_buttons=True,
        newsletter_id=newsletter.id
    )

    # Create fallback text
    week_str = f"{newsletter.week_start.strftime('%b %d')} - {newsletter.week_end.strftime('%b %d')}"
    fallback_text = f"Weekly Dispatch ({week_str}) - Ready for Review"

    try:
        client.chat_update(
            channel=newsletter.slack_channel_id,
            ts=newsletter.slack_main_message_ts,
            blocks=blocks,
            text=fallback_text
        )

        # Update newsletter status
        newsletter.status = NewsletterStatus.READY_FOR_REVIEW.value
        db.session.commit()

        logger.info(f"Added review buttons to newsletter #{newsletter.id}")
        return True

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        logger.error(f"Error adding review buttons to newsletter #{newsletter.id}: {error_msg}")
        return False


# =============================================================================
# Publishing
# =============================================================================

def publish_to_announcement_channel(newsletter: Newsletter) -> PublishResult:
    """Publish final newsletter to announcements channel.

    Called after admin approval. Posts the newsletter content to the
    configured publish channel and updates newsletter metadata.

    Args:
        newsletter: Newsletter model with current_content set

    Returns:
        PublishResult with success status and post reference
    """
    if not newsletter.current_content:
        return PublishResult(
            success=False,
            error="No content to publish"
        )

    channel_id = get_publish_channel()
    if not channel_id:
        return PublishResult(
            success=False,
            error="Could not find publish channel"
        )

    dry_run = is_dry_run()

    if dry_run:
        logger.info(
            f"[DRY RUN] Would publish newsletter #{newsletter.id} "
            f"to channel {channel_id}"
        )
        return PublishResult(
            success=True,
            main_post=SlackPostReference(
                channel_id=channel_id,
                message_ts="dry_run_publish_ts"
            )
        )

    client = get_slack_client()

    # Build blocks for published newsletter (no buttons)
    blocks = _build_newsletter_blocks(
        content=newsletter.current_content,
        version_number=newsletter.current_version,
        status=NewsletterStatus.PUBLISHED.value,
        include_review_buttons=False
    )

    # Create fallback text
    week_str = f"{newsletter.week_start.strftime('%b %d')} - {newsletter.week_end.strftime('%b %d')}"
    fallback_text = f"Weekly Dispatch ({week_str})"

    try:
        response = client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text=fallback_text,
            unfurl_links=False,
            unfurl_media=False
        )

        message_ts = response.get('ts')
        logger.info(
            f"Published newsletter #{newsletter.id} "
            f"(channel: {channel_id}, ts: {message_ts})"
        )

        # Update newsletter metadata
        newsletter.publish_channel_id = channel_id
        newsletter.publish_message_ts = message_ts
        newsletter.published_at = datetime.utcnow()
        newsletter.status = NewsletterStatus.PUBLISHED.value
        db.session.commit()

        # Also update the living post to show published status
        try:
            update_living_post(
                newsletter,
                newsletter.current_content,
                newsletter.current_version
            )
        except Exception as e:
            logger.warning(f"Could not update living post after publish: {e}")

        return PublishResult(
            success=True,
            main_post=SlackPostReference(
                channel_id=channel_id,
                message_ts=message_ts
            )
        )

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        logger.error(f"Error publishing newsletter #{newsletter.id}: {error_msg}")
        return PublishResult(
            success=False,
            error=error_msg
        )


# =============================================================================
# Feedback and Regeneration
# =============================================================================

def post_feedback_request(newsletter: Newsletter, feedback: str) -> bool:
    """Post feedback to thread for regeneration.

    Called when admin clicks "Request Changes" button.
    Posts the feedback as a thread reply for audit trail.

    Args:
        newsletter: Newsletter model with slack_main_message_ts set
        feedback: Admin feedback text

    Returns:
        True if feedback was posted successfully
    """
    if not newsletter.slack_main_message_ts or not newsletter.slack_channel_id:
        logger.error("No Slack message to post feedback to")
        return False

    dry_run = is_dry_run()

    if dry_run:
        logger.info(
            f"[DRY RUN] Would post feedback to newsletter #{newsletter.id}: {feedback[:100]}..."
        )
        return True

    client = get_slack_client()

    # Build feedback message
    blocks = [
        {
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": f":speech_balloon: *Admin Feedback* - <!date^{int(datetime.utcnow().timestamp())}^{{date_short_pretty}} at {{time}}|just now>"
            }]
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"_{feedback}_"
            }
        },
        {
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": ":arrows_counterclockwise: Newsletter will regenerate with this feedback"
            }]
        }
    ]

    try:
        client.chat_postMessage(
            channel=newsletter.slack_channel_id,
            thread_ts=newsletter.slack_main_message_ts,
            blocks=blocks,
            text=f"Admin feedback: {feedback}",
            unfurl_links=False,
            unfurl_media=False
        )

        # Store feedback for regeneration
        newsletter.admin_feedback = feedback
        db.session.commit()

        logger.info(f"Posted feedback to newsletter #{newsletter.id}")
        return True

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        logger.error(f"Error posting feedback for newsletter #{newsletter.id}: {error_msg}")
        return False


def post_approval_notice(newsletter: Newsletter, approver_slack_uid: str) -> bool:
    """Post approval notice to thread.

    Called when admin clicks "Approve & Publish" button.

    Args:
        newsletter: Newsletter model with slack_main_message_ts set
        approver_slack_uid: Slack user ID of the approver

    Returns:
        True if notice was posted successfully
    """
    if not newsletter.slack_main_message_ts or not newsletter.slack_channel_id:
        logger.error("No Slack message to post approval notice to")
        return False

    dry_run = is_dry_run()

    if dry_run:
        logger.info(
            f"[DRY RUN] Would post approval notice for newsletter #{newsletter.id}"
        )
        return True

    client = get_slack_client()

    notice_text = (
        f":white_check_mark: *Approved by* <@{approver_slack_uid}> "
        f"<!date^{int(datetime.utcnow().timestamp())}^{{date_short_pretty}} at {{time}}|just now>"
    )

    try:
        client.chat_postMessage(
            channel=newsletter.slack_channel_id,
            thread_ts=newsletter.slack_main_message_ts,
            text=notice_text,
            unfurl_links=False,
            unfurl_media=False
        )

        # Update newsletter status and approver
        newsletter.status = NewsletterStatus.APPROVED.value
        newsletter.published_by_slack_uid = approver_slack_uid
        db.session.commit()

        logger.info(f"Posted approval notice for newsletter #{newsletter.id}")
        return True

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        logger.error(f"Error posting approval notice for newsletter #{newsletter.id}: {error_msg}")
        return False


# =============================================================================
# Utility Functions
# =============================================================================

def get_newsletter_permalink(newsletter: Newsletter) -> Optional[str]:
    """Get permalink to the living post for a newsletter.

    Args:
        newsletter: Newsletter model with Slack references set

    Returns:
        Permalink URL string or None
    """
    if not newsletter.slack_main_message_ts or not newsletter.slack_channel_id:
        return None

    dry_run = is_dry_run()

    if dry_run:
        return "https://slack.com/dry-run-permalink"

    client = get_slack_client()

    try:
        response = client.chat_getPermalink(
            channel=newsletter.slack_channel_id,
            message_ts=newsletter.slack_main_message_ts
        )
        return response.get('permalink')
    except SlackApiError as e:
        logger.warning(f"Could not get permalink for newsletter #{newsletter.id}: {e}")
        return None


def remove_review_buttons(newsletter: Newsletter) -> bool:
    """Remove review buttons from living post after action.

    Called after approval or when reverting to building status.

    Args:
        newsletter: Newsletter model with slack_main_message_ts set

    Returns:
        True if buttons were removed successfully
    """
    if not newsletter.slack_main_message_ts or not newsletter.slack_channel_id:
        return False

    if not newsletter.current_content:
        return False

    dry_run = is_dry_run()

    if dry_run:
        logger.info(
            f"[DRY RUN] Would remove review buttons from newsletter #{newsletter.id}"
        )
        return True

    client = get_slack_client()

    # Build blocks without review buttons
    blocks = _build_newsletter_blocks(
        content=newsletter.current_content,
        version_number=newsletter.current_version,
        status=newsletter.status,
        include_review_buttons=False
    )

    week_str = f"{newsletter.week_start.strftime('%b %d')} - {newsletter.week_end.strftime('%b %d')}"
    fallback_text = f"Weekly Dispatch ({week_str}) - v{newsletter.current_version}"

    try:
        client.chat_update(
            channel=newsletter.slack_channel_id,
            ts=newsletter.slack_main_message_ts,
            blocks=blocks,
            text=fallback_text
        )

        logger.info(f"Removed review buttons from newsletter #{newsletter.id}")
        return True

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        logger.error(f"Error removing review buttons from newsletter #{newsletter.id}: {error_msg}")
        return False
