"""
Photo Gallery system for the Monthly Dispatch newsletter.

Handles collecting photos from #photos Slack channel, admin curation,
and publishing the gallery as a thread reply to the newsletter.
"""

import logging
import os
from datetime import datetime
from typing import Optional

import yaml
from slack_sdk.errors import SlackApiError

from app.models import db
from app.newsletter.models import Newsletter, PhotoSubmission
from app.slack.client import get_slack_client, get_channel_id_by_name

logger = logging.getLogger(__name__)

# Module-level config cache
_config_cache = None


def _load_config() -> dict:
    """Load newsletter configuration from YAML (cached after first load)."""
    global _config_cache
    if _config_cache is None:
        config_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'config', 'newsletter.yaml'
        )
        try:
            with open(config_path, 'r') as f:
                _config_cache = yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning(f"Newsletter config not found at {config_path}")
            _config_cache = {}
    return _config_cache


def _get_channel_id(channel_name: str) -> Optional[str]:
    """Resolve channel name to channel ID.

    Args:
        channel_name: Channel name (with or without # prefix)

    Returns:
        Channel ID or None if not found
    """
    # Remove # prefix if present
    channel_name = channel_name.lstrip('#')
    return get_channel_id_by_name(channel_name)


def _is_dry_run() -> bool:
    """Check if newsletter system is in dry-run mode."""
    try:
        config = _load_config()
        return config.get('newsletter', {}).get('dry_run', True)
    except Exception:
        return True  # Default to dry-run if config fails


def collect_month_photos(
    newsletter_id: int,
    channel: str = 'photos',
    month_start: Optional[datetime] = None,
    month_end: Optional[datetime] = None
) -> dict:
    """Collect photos from a Slack channel for the newsletter's month.

    Fetches images posted to the channel within the date range and
    creates PhotoSubmission records for each new photo found.

    Args:
        newsletter_id: ID of the newsletter to collect photos for
        channel: Channel name to collect from (default: 'photos')
        month_start: Start of date range (uses newsletter's period_start if None)
        month_end: End of date range (uses newsletter's period_end if None)

    Returns:
        dict with keys:
        - success: bool
        - photos_collected: int (number of new photos collected)
        - photos_skipped: int (already collected)
        - error: str (if failed)
    """
    try:
        # Get newsletter for date range defaults
        newsletter = Newsletter.query.get(newsletter_id)
        if not newsletter:
            return {'success': False, 'error': f'Newsletter {newsletter_id} not found'}

        # Use newsletter's period dates if not specified
        if month_start is None:
            month_start = newsletter.period_start or newsletter.week_start
        if month_end is None:
            month_end = newsletter.period_end or newsletter.week_end

        # Get channel ID
        channel_id = _get_channel_id(channel)
        if not channel_id:
            logger.error(f"Could not find photos channel: #{channel}")
            return {'success': False, 'error': f'Channel not found: #{channel}'}

        dry_run = _is_dry_run()

        if dry_run:
            logger.info(
                f"[DRY RUN] Would collect photos from #{channel} "
                f"for newsletter #{newsletter_id} "
                f"({month_start.strftime('%Y-%m-%d')} to {month_end.strftime('%Y-%m-%d')})"
            )
            return {
                'success': True,
                'photos_collected': 0,
                'photos_skipped': 0
            }

        client = get_slack_client()

        # Convert datetime to Slack timestamp format
        oldest_ts = str(month_start.timestamp())
        latest_ts = str(month_end.timestamp())

        # Fetch files from the channel within the date range
        photos_collected = 0
        photos_skipped = 0
        cursor = None

        while True:
            response = client.files_list(
                channel=channel_id,
                ts_from=oldest_ts,
                ts_to=latest_ts,
                types='images',
                cursor=cursor,
                count=100
            )

            for file_info in response.get('files', []):
                file_id = file_info.get('id')

                # Skip if already collected
                existing = PhotoSubmission.query.filter_by(
                    newsletter_id=newsletter_id,
                    slack_file_id=file_id
                ).first()

                if existing:
                    photos_skipped += 1
                    continue

                # Get reaction count from the file
                reaction_count = 0
                for reaction in file_info.get('reactions', []):
                    reaction_count += reaction.get('count', 0)

                # Create PhotoSubmission record
                photo = PhotoSubmission(
                    newsletter_id=newsletter_id,
                    slack_file_id=file_id,
                    slack_permalink=file_info.get('permalink'),
                    caption=file_info.get('title') or file_info.get('name'),
                    reaction_count=reaction_count,
                    submitted_by_user_id=file_info.get('user'),
                    posted_at=datetime.fromtimestamp(file_info.get('created', 0)),
                    selected=False
                )
                db.session.add(photo)
                photos_collected += 1

            # Check for more pages
            cursor = response.get('response_metadata', {}).get('next_cursor')
            if not cursor:
                break

        db.session.commit()

        logger.info(
            f"Collected {photos_collected} photos from #{channel} "
            f"for newsletter #{newsletter_id} (skipped {photos_skipped} existing)"
        )

        return {
            'success': True,
            'photos_collected': photos_collected,
            'photos_skipped': photos_skipped
        }

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        logger.error(f"Slack API error collecting photos: {error_msg}")
        return {'success': False, 'error': error_msg}

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error collecting photos for newsletter #{newsletter_id}: {e}")
        return {'success': False, 'error': str(e)}


def get_photo_submissions(newsletter_id: int) -> list[PhotoSubmission]:
    """Get all collected photos for a newsletter, sorted by popularity.

    Returns photos ordered by reaction count (highest first), then by
    posted date for photos with equal reactions.

    Args:
        newsletter_id: ID of the newsletter

    Returns:
        List of PhotoSubmission objects sorted by popularity
    """
    return PhotoSubmission.query.filter_by(
        newsletter_id=newsletter_id
    ).order_by(
        PhotoSubmission.reaction_count.desc(),
        PhotoSubmission.posted_at.desc()
    ).all()


def select_photos(newsletter_id: int, photo_ids: list[int]) -> dict:
    """Mark specific photos as selected for the newsletter.

    First deselects all photos for the newsletter, then selects
    only the specified ones. This ensures clean state management.

    Args:
        newsletter_id: ID of the newsletter
        photo_ids: List of PhotoSubmission IDs to select

    Returns:
        dict with keys:
        - success: bool
        - selected_count: int (number of photos selected)
        - error: str (if failed)
    """
    try:
        # First, unselect all photos for this newsletter
        PhotoSubmission.query.filter_by(
            newsletter_id=newsletter_id
        ).update({'selected': False})

        # Then select the specified photos (only if they belong to this newsletter)
        if photo_ids:
            updated = PhotoSubmission.query.filter(
                PhotoSubmission.id.in_(photo_ids),
                PhotoSubmission.newsletter_id == newsletter_id
            ).update({'selected': True}, synchronize_session='fetch')
        else:
            updated = 0

        db.session.commit()

        logger.info(
            f"Selected {updated} photo(s) for newsletter #{newsletter_id}"
        )

        return {
            'success': True,
            'selected_count': updated
        }

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error selecting photos for newsletter #{newsletter_id}: {e}")
        return {'success': False, 'error': str(e)}


def get_selected_photos(newsletter_id: int) -> list[PhotoSubmission]:
    """Get selected photos for a newsletter.

    Returns only the photos that have been marked as selected by admin.
    Ordered by reaction count (most popular first).

    Args:
        newsletter_id: ID of the newsletter

    Returns:
        List of selected PhotoSubmission objects
    """
    return PhotoSubmission.query.filter_by(
        newsletter_id=newsletter_id,
        selected=True
    ).order_by(
        PhotoSubmission.reaction_count.desc(),
        PhotoSubmission.posted_at.desc()
    ).all()


def post_photo_gallery_thread(
    newsletter_id: int,
    parent_message_ts: str,
    channel_id: str
) -> dict:
    """Post the photo gallery as a thread reply to the published newsletter.

    Builds a Block Kit message with selected photos and posts it as a
    thread reply to the main newsletter message.

    Args:
        newsletter_id: ID of the newsletter
        parent_message_ts: Timestamp of the parent message to reply to
        channel_id: Channel ID where the parent message was posted

    Returns:
        dict with keys:
        - success: bool
        - message_ts: str (if successful)
        - photo_count: int (number of photos posted)
        - error: str (if failed)
    """
    try:
        # Get selected photos
        photos = get_selected_photos(newsletter_id)

        if not photos:
            logger.info(f"No photos selected for newsletter #{newsletter_id}")
            return {
                'success': True,
                'message_ts': None,
                'photo_count': 0
            }

        dry_run = _is_dry_run()

        if dry_run:
            logger.info(
                f"[DRY RUN] Would post photo gallery with {len(photos)} photos "
                f"as thread reply for newsletter #{newsletter_id}"
            )
            return {
                'success': True,
                'message_ts': 'dry_run_ts',
                'photo_count': len(photos)
            }

        client = get_slack_client()

        # Build Block Kit message with photos
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "Photo Gallery",
                    "emoji": True
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"*{len(photos)} photos* from our members this month"
                    }
                ]
            },
            {
                "type": "divider"
            }
        ]

        # Add each photo with its caption
        for photo in photos:
            # Add image block if we have a permalink
            if photo.slack_permalink:
                blocks.append({
                    "type": "image",
                    "image_url": photo.slack_permalink,
                    "alt_text": photo.caption or "Club photo"
                })

            # Add caption and attribution if available
            caption_parts = []
            if photo.caption:
                caption_parts.append(photo.caption)
            if photo.submitted_by_user_id:
                caption_parts.append(f"Posted by <@{photo.submitted_by_user_id}>")
            if photo.reaction_count > 0:
                caption_parts.append(f"{photo.reaction_count} reactions")

            if caption_parts:
                blocks.append({
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": " | ".join(caption_parts)
                        }
                    ]
                })

        # Slack has a limit of 50 blocks per message
        if len(blocks) > 50:
            blocks = blocks[:50]
            logger.warning(
                f"Photo gallery truncated to 50 blocks for newsletter #{newsletter_id}"
            )

        response = client.chat_postMessage(
            channel=channel_id,
            thread_ts=parent_message_ts,
            blocks=blocks,
            text=f"Photo Gallery - {len(photos)} photos from our members",
            unfurl_links=False,
            unfurl_media=False
        )

        message_ts = response.get('ts')
        logger.info(
            f"Posted photo gallery with {len(photos)} photos for newsletter #{newsletter_id} "
            f"(channel: {channel_id}, thread_ts: {parent_message_ts}, ts: {message_ts})"
        )

        return {
            'success': True,
            'message_ts': message_ts,
            'photo_count': len(photos)
        }

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        logger.error(f"Slack API error posting photo gallery: {error_msg}")
        return {'success': False, 'error': error_msg}

    except Exception as e:
        logger.error(f"Error posting photo gallery for newsletter #{newsletter_id}: {e}")
        return {'success': False, 'error': str(e)}
