"""
Newsletter Host system for the Monthly Dispatch newsletter.

Handles host assignment, request sending, submission processing,
and reminders for hosts who write opener and closer sections.
"""

import logging
import os
from datetime import datetime
from typing import Optional

import yaml
from slack_sdk.errors import SlackApiError

from app.models import db
from app.newsletter.models import Newsletter, NewsletterHost
from app.newsletter.interfaces import HostStatus
from app.slack.client import get_slack_client, open_conversation

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


def _is_dry_run() -> bool:
    """Check if newsletter system is in dry-run mode."""
    try:
        config = _load_config()
        return config.get('newsletter', {}).get('dry_run', True)
    except Exception:
        return True  # Default to dry-run if config fails


def assign_host(
    newsletter_id: int,
    slack_user_id: Optional[str] = None,
    external_name: Optional[str] = None,
    external_email: Optional[str] = None
) -> dict:
    """Assign a host to write the newsletter opener and closer.

    The host can be either a Slack member (identified by slack_user_id)
    or an external guest (identified by name and optionally email).
    Only one of slack_user_id or external_name should be provided.

    Args:
        newsletter_id: ID of the newsletter to assign host for
        slack_user_id: Slack user ID if host is a member (e.g., 'U12345ABC')
        external_name: Name if host is an external guest
        external_email: Email for external guest (optional, for contact purposes)

    Returns:
        dict with keys:
        - success: bool
        - host_id: int (if successful)
        - is_external: bool (True if external guest)
        - error: str (if failed)
    """
    # Validate inputs
    if not slack_user_id and not external_name:
        return {
            'success': False,
            'error': 'Must provide either slack_user_id or external_name'
        }

    if slack_user_id and external_name:
        return {
            'success': False,
            'error': 'Cannot provide both slack_user_id and external_name'
        }

    try:
        # Check if newsletter exists
        newsletter = Newsletter.query.get(newsletter_id)
        if not newsletter:
            return {'success': False, 'error': f'Newsletter {newsletter_id} not found'}

        # Check for existing host assignment
        existing = NewsletterHost.query.filter_by(newsletter_id=newsletter_id).first()
        if existing:
            # Update existing assignment
            existing.slack_user_id = slack_user_id
            existing.external_name = external_name
            existing.external_email = external_email
            existing.status = HostStatus.ASSIGNED.value
            existing.opener_content = None
            existing.closer_content = None
            existing.submitted_at = None
            existing.assigned_at = datetime.utcnow()
            db.session.commit()

            host_display = external_name if external_name else slack_user_id
            logger.info(
                f"Updated host assignment to {host_display} "
                f"for newsletter #{newsletter_id}"
            )

            return {
                'success': True,
                'host_id': existing.id,
                'is_external': bool(external_name)
            }

        # Create new host assignment
        host = NewsletterHost(
            newsletter_id=newsletter_id,
            slack_user_id=slack_user_id,
            external_name=external_name,
            external_email=external_email,
            status=HostStatus.ASSIGNED.value,
            assigned_at=datetime.utcnow()
        )
        db.session.add(host)
        db.session.commit()

        host_display = external_name if external_name else slack_user_id
        logger.info(
            f"Assigned {host_display} as host for newsletter #{newsletter_id}"
        )

        return {
            'success': True,
            'host_id': host.id,
            'is_external': bool(external_name)
        }

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error assigning host for newsletter #{newsletter_id}: {e}")
        return {'success': False, 'error': str(e)}


def send_host_request(newsletter_id: int) -> dict:
    """Send a DM to the assigned host with a submission button.

    The DM includes information about the newsletter and a button
    that opens a modal for submitting opener and closer content.

    Note: Cannot send DMs to external guests - they must submit
    content through other means (email, web form, etc.)

    Args:
        newsletter_id: ID of the newsletter

    Returns:
        dict with keys:
        - success: bool
        - message_ts: str (if successful)
        - channel_id: str (if successful, the DM channel)
        - error: str (if failed)
    """
    try:
        # Get host assignment
        host = NewsletterHost.query.filter_by(newsletter_id=newsletter_id).first()
        if not host:
            return {
                'success': False,
                'error': f'No host assigned for newsletter #{newsletter_id}'
            }

        # Check if external guest
        if host.is_external:
            return {
                'success': False,
                'error': 'Cannot send DM to external guest. Contact them directly.'
            }

        if not host.slack_user_id:
            return {
                'success': False,
                'error': 'Host has no Slack user ID'
            }

        # Get newsletter for context
        newsletter = Newsletter.query.get(newsletter_id)
        month_display = newsletter.month_year if newsletter else 'the upcoming month'

        dry_run = _is_dry_run()

        if dry_run:
            logger.info(
                f"[DRY RUN] Would send host request to {host.slack_user_id} "
                f"for newsletter #{newsletter_id}"
            )
            return {
                'success': True,
                'message_ts': 'dry_run_ts',
                'channel_id': 'dry_run_channel'
            }

        # Open DM conversation
        conv_result = open_conversation([host.slack_user_id])
        if not conv_result.get('success'):
            return {
                'success': False,
                'error': f"Could not open DM: {conv_result.get('error')}"
            }

        channel_id = conv_result['channel_id']
        client = get_slack_client()

        # Build Block Kit message with submission button
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "You're the Monthly Dispatch Host!",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"You've been selected to host the *{month_display}* edition "
                        "of the Monthly Dispatch newsletter!\n\n"
                        "As host, you'll write:\n"
                        "- *Opener* (200-400 words): Welcome readers and set the tone\n"
                        "- *Closer* (100-200 words): Wrap up and sign off"
                    )
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": (
                            "Share your personality and voice! This is your chance "
                            "to connect with fellow club members."
                        )
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
                            "text": "Write My Sections",
                            "emoji": True
                        },
                        "style": "primary",
                        "action_id": "host_submit",
                        "value": str(newsletter_id)
                    }
                ]
            }
        ]

        response = client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text=f"You're the Monthly Dispatch host for {month_display}!",
            unfurl_links=False,
            unfurl_media=False
        )

        message_ts = response.get('ts')
        logger.info(
            f"Sent host request to {host.slack_user_id} for newsletter #{newsletter_id} "
            f"(channel: {channel_id}, ts: {message_ts})"
        )

        return {
            'success': True,
            'message_ts': message_ts,
            'channel_id': channel_id
        }

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        logger.error(f"Slack API error sending host request: {error_msg}")
        return {'success': False, 'error': error_msg}

    except Exception as e:
        logger.error(f"Error sending host request for newsletter #{newsletter_id}: {e}")
        return {'success': False, 'error': str(e)}


def handle_host_submission(
    newsletter_id: int,
    opener_content: str,
    closer_content: str
) -> dict:
    """Process a host submission with opener and closer content.

    Updates the NewsletterHost record with the submitted content
    and marks it as submitted.

    Args:
        newsletter_id: ID of the newsletter
        opener_content: The opener section content (200-400 words)
        closer_content: The closer section content (100-200 words)

    Returns:
        dict with keys:
        - success: bool
        - host_id: int (if successful)
        - error: str (if failed)
    """
    try:
        # Get host assignment
        host = NewsletterHost.query.filter_by(newsletter_id=newsletter_id).first()
        if not host:
            return {
                'success': False,
                'error': f'No host assigned for newsletter #{newsletter_id}'
            }

        # Validate content
        if not opener_content or not opener_content.strip():
            return {
                'success': False,
                'error': 'Opener content is required'
            }

        if not closer_content or not closer_content.strip():
            return {
                'success': False,
                'error': 'Closer content is required'
            }

        # Update host record
        host.opener_content = opener_content.strip()
        host.closer_content = closer_content.strip()
        host.status = HostStatus.SUBMITTED.value
        host.submitted_at = datetime.utcnow()
        db.session.commit()

        host_display = host.external_name if host.external_name else host.slack_user_id
        logger.info(
            f"Host {host_display} submitted content for newsletter #{newsletter_id}"
        )

        return {
            'success': True,
            'host_id': host.id
        }

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error processing host submission for newsletter #{newsletter_id}: {e}")
        return {'success': False, 'error': str(e)}


def send_host_reminder(newsletter_id: int) -> dict:
    """Send a reminder DM to the host if they haven't submitted yet.

    Only sends reminder if the host is a Slack member (not external)
    and hasn't already submitted their content.

    Args:
        newsletter_id: ID of the newsletter

    Returns:
        dict with keys:
        - success: bool
        - message_ts: str (if successful)
        - channel_id: str (if successful)
        - skipped: bool (True if no reminder needed)
        - reason: str (if skipped)
        - error: str (if failed)
    """
    try:
        # Get host assignment
        host = NewsletterHost.query.filter_by(newsletter_id=newsletter_id).first()
        if not host:
            return {
                'success': False,
                'error': f'No host assigned for newsletter #{newsletter_id}'
            }

        # Check if already submitted
        if host.status == HostStatus.SUBMITTED.value:
            return {
                'success': True,
                'skipped': True,
                'reason': 'Host has already submitted content'
            }

        # Check if external guest
        if host.is_external:
            return {
                'success': True,
                'skipped': True,
                'reason': 'Cannot send reminder to external guest'
            }

        if not host.slack_user_id:
            return {
                'success': False,
                'error': 'Host has no Slack user ID'
            }

        # Get newsletter for context
        newsletter = Newsletter.query.get(newsletter_id)
        month_display = newsletter.month_year if newsletter else 'the upcoming month'

        dry_run = _is_dry_run()

        if dry_run:
            logger.info(
                f"[DRY RUN] Would send host reminder to {host.slack_user_id} "
                f"for newsletter #{newsletter_id}"
            )
            return {
                'success': True,
                'message_ts': 'dry_run_ts',
                'channel_id': 'dry_run_channel'
            }

        # Open DM conversation
        conv_result = open_conversation([host.slack_user_id])
        if not conv_result.get('success'):
            return {
                'success': False,
                'error': f"Could not open DM: {conv_result.get('error')}"
            }

        channel_id = conv_result['channel_id']
        client = get_slack_client()

        # Build reminder message
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*Friendly reminder!* We're still waiting for your opener "
                        f"and closer sections for the *{month_display}* Monthly Dispatch.\n\n"
                        "When you're ready, click the button below to submit your content."
                    )
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Write My Sections",
                            "emoji": True
                        },
                        "style": "primary",
                        "action_id": "host_submit",
                        "value": str(newsletter_id)
                    }
                ]
            }
        ]

        response = client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text=f"Reminder: Your Monthly Dispatch sections for {month_display} are due!",
            unfurl_links=False,
            unfurl_media=False
        )

        message_ts = response.get('ts')
        logger.info(
            f"Sent host reminder to {host.slack_user_id} for newsletter #{newsletter_id} "
            f"(channel: {channel_id}, ts: {message_ts})"
        )

        return {
            'success': True,
            'message_ts': message_ts,
            'channel_id': channel_id
        }

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        logger.error(f"Slack API error sending host reminder: {error_msg}")
        return {'success': False, 'error': error_msg}

    except Exception as e:
        logger.error(f"Error sending host reminder for newsletter #{newsletter_id}: {e}")
        return {'success': False, 'error': str(e)}


def get_host_for_newsletter(newsletter_id: int) -> Optional[NewsletterHost]:
    """Get the host assignment for a newsletter.

    Args:
        newsletter_id: ID of the newsletter

    Returns:
        NewsletterHost instance or None if no host assigned
    """
    return NewsletterHost.query.filter_by(newsletter_id=newsletter_id).first()


def build_host_submission_modal(newsletter_id: int) -> dict:
    """Build a Slack modal for host to submit opener and closer content.

    Args:
        newsletter_id: ID of the newsletter

    Returns:
        Slack modal view payload
    """
    return {
        "type": "modal",
        "callback_id": "host_submission",
        "private_metadata": str(newsletter_id),
        "title": {
            "type": "plain_text",
            "text": "Newsletter Host"
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
                    "text": (
                        "*Welcome, Newsletter Host!*\n\n"
                        "Please write your opener and closer sections below. "
                        "Your unique voice and personality make the newsletter special!"
                    )
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "input",
                "block_id": "opener_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "opener_input",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Welcome readers and set the tone for this month's newsletter... (200-400 words)"
                    }
                },
                "label": {
                    "type": "plain_text",
                    "text": "Opener (200-400 words)"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "The opener welcomes readers and introduces what's coming. Share your excitement about the season!"
                    }
                ]
            },
            {
                "type": "divider"
            },
            {
                "type": "input",
                "block_id": "closer_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "closer_input",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Wrap up and sign off with well wishes... (100-200 words)"
                    }
                },
                "label": {
                    "type": "plain_text",
                    "text": "Closer (100-200 words)"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "The closer wraps up the newsletter with final thoughts and a warm sign-off."
                    }
                ]
            }
        ]
    }
