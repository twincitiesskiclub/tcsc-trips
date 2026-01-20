"""
Question of the Month (QOTM) system for the Monthly Dispatch newsletter.

Handles posting questions to Slack, collecting member responses via modals,
and selecting responses for inclusion in the newsletter.
"""

import logging
import os
from datetime import datetime
from typing import Optional

import yaml
from slack_sdk.errors import SlackApiError

from app.models import db
from app.newsletter.models import Newsletter, QOTMResponse
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


def post_qotm_to_channel(
    newsletter_id: int,
    question: str,
    channel: str = 'chat'
) -> dict:
    """Post Question of the Month to a Slack channel with a response button.

    Posts a message with the question and a button that opens a modal
    for members to submit their responses.

    Args:
        newsletter_id: ID of the newsletter this QOTM is for
        question: The question text to post
        channel: Channel name to post to (default: 'chat')

    Returns:
        dict with keys:
        - success: bool
        - message_ts: str (if successful)
        - channel_id: str (if successful)
        - error: str (if failed)
    """
    channel_id = _get_channel_id(channel)
    if not channel_id:
        logger.error(f"Could not find QOTM channel: #{channel}")
        return {'success': False, 'error': f'Channel not found: #{channel}'}

    dry_run = _is_dry_run()

    if dry_run:
        logger.info(
            f"[DRY RUN] Would post QOTM for newsletter #{newsletter_id} "
            f"to channel #{channel}: {question[:50]}..."
        )
        return {
            'success': True,
            'message_ts': 'dry_run_ts',
            'channel_id': channel_id
        }

    client = get_slack_client()

    # Build Block Kit message with question and response button
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Question of the Month",
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{question}*"
            }
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "Your response may be featured in the Monthly Dispatch newsletter!"
                }
            ]
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Share Your Answer",
                        "emoji": True
                    },
                    "style": "primary",
                    "action_id": "qotm_respond",
                    "value": str(newsletter_id)
                }
            ]
        }
    ]

    try:
        response = client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text=f"Question of the Month: {question}",
            unfurl_links=False,
            unfurl_media=False
        )

        message_ts = response.get('ts')
        logger.info(
            f"Posted QOTM for newsletter #{newsletter_id} "
            f"(channel: {channel_id}, ts: {message_ts})"
        )

        return {
            'success': True,
            'message_ts': message_ts,
            'channel_id': channel_id
        }

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        logger.error(f"Error posting QOTM for newsletter #{newsletter_id}: {error_msg}")
        return {'success': False, 'error': error_msg}


def handle_qotm_submission(
    newsletter_id: int,
    user_id: str,
    user_name: str,
    response: str
) -> dict:
    """Save or update a member's QOTM response.

    Implements upsert logic: if the user has already submitted a response
    for this newsletter, update it instead of creating a duplicate.

    Args:
        newsletter_id: ID of the newsletter
        user_id: Slack user ID of the submitter
        user_name: Display name of the submitter
        response: The response text

    Returns:
        dict with keys:
        - success: bool
        - response_id: int (if successful)
        - is_update: bool (True if updated existing response)
        - error: str (if failed)
    """
    try:
        # Check for existing response from this user for this newsletter
        existing = QOTMResponse.query.filter_by(
            newsletter_id=newsletter_id,
            slack_user_id=user_id
        ).first()

        if existing:
            # Update existing response
            existing.response = response
            existing.user_name = user_name
            existing.submitted_at = datetime.utcnow()
            db.session.commit()

            logger.info(
                f"Updated QOTM response #{existing.id} from {user_name} "
                f"for newsletter #{newsletter_id}"
            )

            return {
                'success': True,
                'response_id': existing.id,
                'is_update': True
            }
        else:
            # Create new response
            qotm_response = QOTMResponse(
                newsletter_id=newsletter_id,
                slack_user_id=user_id,
                user_name=user_name,
                response=response,
                selected=False,
                submitted_at=datetime.utcnow()
            )
            db.session.add(qotm_response)
            db.session.commit()

            logger.info(
                f"Created QOTM response #{qotm_response.id} from {user_name} "
                f"for newsletter #{newsletter_id}"
            )

            return {
                'success': True,
                'response_id': qotm_response.id,
                'is_update': False
            }

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving QOTM response: {e}")
        return {'success': False, 'error': str(e)}


def get_qotm_responses(newsletter_id: int) -> list[QOTMResponse]:
    """Get all QOTM responses for a newsletter.

    Returns responses ordered by submission time (most recent first).

    Args:
        newsletter_id: ID of the newsletter

    Returns:
        List of QOTMResponse objects
    """
    return QOTMResponse.query.filter_by(
        newsletter_id=newsletter_id
    ).order_by(QOTMResponse.submitted_at.desc()).all()


def select_qotm_responses(response_ids: list[int], newsletter_id: int) -> dict:
    """Mark specific responses as selected for the newsletter.

    First unselects all responses for the newsletter, then selects
    only the specified ones. This ensures clean state management.

    Args:
        response_ids: List of response IDs to select
        newsletter_id: ID of the newsletter (for validation)

    Returns:
        dict with keys:
        - success: bool
        - selected_count: int (number of responses selected)
        - error: str (if failed)
    """
    try:
        # First, unselect all responses for this newsletter
        QOTMResponse.query.filter_by(
            newsletter_id=newsletter_id
        ).update({'selected': False})

        # Then select the specified responses (only if they belong to this newsletter)
        if response_ids:
            updated = QOTMResponse.query.filter(
                QOTMResponse.id.in_(response_ids),
                QOTMResponse.newsletter_id == newsletter_id
            ).update({'selected': True}, synchronize_session='fetch')
        else:
            updated = 0

        db.session.commit()

        logger.info(
            f"Selected {updated} QOTM response(s) for newsletter #{newsletter_id}"
        )

        return {
            'success': True,
            'selected_count': updated
        }

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error selecting QOTM responses: {e}")
        return {'success': False, 'error': str(e)}


def get_selected_qotm_for_newsletter(newsletter_id: int) -> list[QOTMResponse]:
    """Get selected QOTM responses for a newsletter.

    Returns only the responses that have been marked as selected by admin.
    Ordered by submission time (earliest first for narrative flow).

    Args:
        newsletter_id: ID of the newsletter

    Returns:
        List of selected QOTMResponse objects
    """
    return QOTMResponse.query.filter_by(
        newsletter_id=newsletter_id,
        selected=True
    ).order_by(QOTMResponse.submitted_at.asc()).all()


def build_qotm_response_modal(newsletter_id: int, question: str) -> dict:
    """Build a Slack modal for submitting QOTM responses.

    Args:
        newsletter_id: ID of the newsletter
        question: The question to display in the modal

    Returns:
        Slack modal view payload
    """
    return {
        "type": "modal",
        "callback_id": "qotm_submission",
        "private_metadata": str(newsletter_id),
        "title": {
            "type": "plain_text",
            "text": "Question of the Month"
        },
        "submit": {
            "type": "plain_text",
            "text": "Submit"
        },
        "close": {
            "type": "plain_text",
            "text": "Cancel"
        },
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{question}*"
                }
            },
            {
                "type": "input",
                "block_id": "qotm_response_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "qotm_response_input",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Share your thoughts..."
                    }
                },
                "label": {
                    "type": "plain_text",
                    "text": "Your Response"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "Your response may be featured in the Monthly Dispatch newsletter."
                    }
                ]
            }
        ]
    }
