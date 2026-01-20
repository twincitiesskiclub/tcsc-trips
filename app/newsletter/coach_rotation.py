"""
Coach Rotation system for the Monthly Dispatch newsletter.

Handles automated rotation through coaches for the "Coaches Corner" section.
Tracks coach assignments, submissions, and ensures fair rotation based on
historical contribution frequency.
"""

import logging
import os
from datetime import datetime
from typing import Optional

import yaml
from slack_sdk.errors import SlackApiError

from app.models import db, User, Tag
from app.newsletter.models import Newsletter, CoachRotation
from app.newsletter.interfaces import CoachStatus
from app.slack.client import get_slack_client, open_conversation

logger = logging.getLogger(__name__)

# Module-level config cache
_config_cache = None

# Coach tag names
COACH_TAGS = {'HEAD_COACH', 'ASSISTANT_COACH'}


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


def get_next_coach() -> Optional[User]:
    """Select the next coach in rotation based on contribution history.

    Selection logic:
    1. Query all users with HEAD_COACH or ASSISTANT_COACH tags
    2. For each coach, find their most recent CoachRotation with status='submitted'
    3. Sort: coaches with no contributions first, then by oldest submission date
    4. Return the first coach in the sorted list

    Returns:
        User object for the selected coach, or None if no coaches available
    """
    # Get all users with coach tags
    coaches = (
        User.query
        .join(User.tags)
        .filter(Tag.name.in_(COACH_TAGS))
        .all()
    )

    if not coaches:
        logger.warning("No coaches found with HEAD_COACH or ASSISTANT_COACH tags")
        return None

    # Build a list of (coach, last_submission_date) tuples
    coach_submissions = []
    for coach in coaches:
        # Find their most recent submitted rotation
        last_rotation = (
            CoachRotation.query
            .filter_by(
                coach_user_id=coach.id,
                status=CoachStatus.SUBMITTED.value
            )
            .order_by(CoachRotation.submitted_at.desc())
            .first()
        )

        if last_rotation and last_rotation.submitted_at:
            coach_submissions.append((coach, last_rotation.submitted_at))
        else:
            # Coach has never contributed - use None to sort first
            coach_submissions.append((coach, None))

    # Sort: None (never contributed) first, then by oldest submission date
    # Coaches who have never contributed should be selected first
    # Among those who have contributed, select the one who contributed longest ago
    def sort_key(item):
        coach, submitted_at = item
        if submitted_at is None:
            # Never contributed - return epoch to sort first
            return datetime.min
        return submitted_at

    coach_submissions.sort(key=sort_key)

    # Return the first coach (oldest contribution or never contributed)
    selected_coach = coach_submissions[0][0]
    logger.info(
        f"Selected coach for rotation: {selected_coach.full_name} "
        f"(id={selected_coach.id})"
    )
    return selected_coach


def assign_coach_for_month(
    newsletter_id: int,
    coach_user_id: Optional[int] = None
) -> dict:
    """Assign a coach to a newsletter for the Coaches Corner section.

    If no coach_user_id is provided, automatically selects the next coach
    in rotation using get_next_coach().

    Args:
        newsletter_id: ID of the newsletter to assign coach for
        coach_user_id: Optional User ID of the coach to assign.
                      If None, auto-selects using rotation logic.

    Returns:
        dict with keys:
        - success: bool
        - rotation_id: int (if successful)
        - coach_name: str (if successful)
        - error: str (if failed)
    """
    try:
        # Check if newsletter exists
        newsletter = Newsletter.query.get(newsletter_id)
        if not newsletter:
            return {'success': False, 'error': f'Newsletter {newsletter_id} not found'}

        # Auto-select coach if not provided
        if coach_user_id is None:
            coach = get_next_coach()
            if not coach:
                return {
                    'success': False,
                    'error': 'No coaches available for rotation'
                }
            coach_user_id = coach.id
        else:
            coach = User.query.get(coach_user_id)
            if not coach:
                return {
                    'success': False,
                    'error': f'User {coach_user_id} not found'
                }

        # Check for existing rotation assignment
        existing = CoachRotation.query.filter_by(newsletter_id=newsletter_id).first()
        if existing:
            # Update existing assignment
            existing.coach_user_id = coach_user_id
            existing.content = None
            existing.status = CoachStatus.ASSIGNED.value
            existing.submitted_at = None
            existing.assigned_at = datetime.utcnow()
            db.session.commit()

            logger.info(
                f"Updated coach assignment to {coach.full_name} "
                f"for newsletter #{newsletter_id}"
            )

            return {
                'success': True,
                'rotation_id': existing.id,
                'coach_name': coach.full_name
            }

        # Create new rotation assignment
        rotation = CoachRotation(
            newsletter_id=newsletter_id,
            coach_user_id=coach_user_id,
            status=CoachStatus.ASSIGNED.value,
            assigned_at=datetime.utcnow()
        )
        db.session.add(rotation)
        db.session.commit()

        logger.info(
            f"Assigned {coach.full_name} as coach for newsletter #{newsletter_id}"
        )

        return {
            'success': True,
            'rotation_id': rotation.id,
            'coach_name': coach.full_name
        }

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error assigning coach for newsletter #{newsletter_id}: {e}")
        return {'success': False, 'error': str(e)}


def send_coach_request(newsletter_id: int) -> dict:
    """Send a DM to the assigned coach with a submission button.

    The DM includes information about the newsletter and a button
    that opens a modal for submitting Coaches Corner content.

    Note: Coach must have a linked SlackUser to receive DMs.

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
        # Get coach rotation assignment
        rotation = CoachRotation.query.filter_by(newsletter_id=newsletter_id).first()
        if not rotation:
            return {
                'success': False,
                'error': f'No coach assigned for newsletter #{newsletter_id}'
            }

        # Get coach user
        coach = User.query.get(rotation.coach_user_id)
        if not coach:
            return {
                'success': False,
                'error': f'Coach user {rotation.coach_user_id} not found'
            }

        # Check if coach has Slack user linked
        if not coach.slack_user or not coach.slack_user.slack_uid:
            return {
                'success': False,
                'error': f'Coach {coach.full_name} has no linked Slack account'
            }

        slack_uid = coach.slack_user.slack_uid

        # Get newsletter for context
        newsletter = Newsletter.query.get(newsletter_id)
        month_display = newsletter.month_year if newsletter else 'the upcoming month'

        dry_run = _is_dry_run()

        if dry_run:
            logger.info(
                f"[DRY RUN] Would send coach request to {coach.full_name} "
                f"({slack_uid}) for newsletter #{newsletter_id}"
            )
            return {
                'success': True,
                'message_ts': 'dry_run_ts',
                'channel_id': 'dry_run_channel'
            }

        # Open DM conversation
        conv_result = open_conversation([slack_uid])
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
                    "text": "You're Up for Coaches Corner!",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"Hi {coach.first_name}! You've been selected to write the "
                        f"*Coaches Corner* section for the *{month_display}* edition "
                        "of the Monthly Dispatch newsletter!\n\n"
                        "This is your chance to share:\n"
                        "- Training tips and technique advice\n"
                        "- Reflections on the season so far\n"
                        "- Encouragement for club members\n"
                        "- Anything else you'd like to share!"
                    )
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "Aim for 200-400 words. Your coaching wisdom is appreciated!"
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
                            "text": "Write Coaches Corner",
                            "emoji": True
                        },
                        "style": "primary",
                        "action_id": "coach_submit",
                        "value": str(newsletter_id)
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "I Can't This Month",
                            "emoji": True
                        },
                        "action_id": "coach_decline",
                        "value": str(newsletter_id)
                    }
                ]
            }
        ]

        response = client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text=f"You're up for Coaches Corner in the {month_display} newsletter!",
            unfurl_links=False,
            unfurl_media=False
        )

        message_ts = response.get('ts')
        logger.info(
            f"Sent coach request to {coach.full_name} for newsletter #{newsletter_id} "
            f"(channel: {channel_id}, ts: {message_ts})"
        )

        return {
            'success': True,
            'message_ts': message_ts,
            'channel_id': channel_id
        }

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        logger.error(f"Slack API error sending coach request: {error_msg}")
        return {'success': False, 'error': error_msg}

    except Exception as e:
        logger.error(f"Error sending coach request for newsletter #{newsletter_id}: {e}")
        return {'success': False, 'error': str(e)}


def handle_coach_submission(newsletter_id: int, content: str) -> dict:
    """Process a coach's submission for Coaches Corner.

    Updates the CoachRotation record with the submitted content
    and marks it as submitted.

    Args:
        newsletter_id: ID of the newsletter
        content: The Coaches Corner content (200-400 words)

    Returns:
        dict with keys:
        - success: bool
        - rotation_id: int (if successful)
        - error: str (if failed)
    """
    try:
        # Get coach rotation assignment
        rotation = CoachRotation.query.filter_by(newsletter_id=newsletter_id).first()
        if not rotation:
            return {
                'success': False,
                'error': f'No coach assigned for newsletter #{newsletter_id}'
            }

        # Validate content
        if not content or not content.strip():
            return {
                'success': False,
                'error': 'Content is required'
            }

        # Update rotation record
        rotation.content = content.strip()
        rotation.status = CoachStatus.SUBMITTED.value
        rotation.submitted_at = datetime.utcnow()
        db.session.commit()

        coach = User.query.get(rotation.coach_user_id)
        coach_name = coach.full_name if coach else f"user {rotation.coach_user_id}"
        logger.info(
            f"Coach {coach_name} submitted content for newsletter #{newsletter_id}"
        )

        return {
            'success': True,
            'rotation_id': rotation.id
        }

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error processing coach submission for newsletter #{newsletter_id}: {e}")
        return {'success': False, 'error': str(e)}


def handle_coach_decline(newsletter_id: int) -> dict:
    """Handle a coach declining to write Coaches Corner.

    Marks the current assignment as declined and automatically
    assigns the next coach in rotation.

    Args:
        newsletter_id: ID of the newsletter

    Returns:
        dict with keys:
        - success: bool
        - previous_coach: str (name of coach who declined)
        - new_coach: str (name of newly assigned coach, if any)
        - rotation_id: int (new rotation id, if reassigned)
        - error: str (if failed)
    """
    try:
        # Get current coach rotation assignment
        rotation = CoachRotation.query.filter_by(newsletter_id=newsletter_id).first()
        if not rotation:
            return {
                'success': False,
                'error': f'No coach assigned for newsletter #{newsletter_id}'
            }

        # Get the declining coach's name
        declining_coach = User.query.get(rotation.coach_user_id)
        declining_coach_name = declining_coach.full_name if declining_coach else 'Unknown'

        # Mark as declined
        rotation.status = CoachStatus.DECLINED.value
        db.session.commit()

        logger.info(
            f"Coach {declining_coach_name} declined for newsletter #{newsletter_id}"
        )

        # Get the next coach in rotation (excluding the one who just declined)
        next_coach = get_next_coach()

        # If the next coach is the same as the declining coach, we need to skip
        # (This could happen if there's only one coach or they're at the top of rotation)
        if next_coach and next_coach.id == rotation.coach_user_id:
            # Try to get another coach by looking at all coaches
            coaches = (
                User.query
                .join(User.tags)
                .filter(Tag.name.in_(COACH_TAGS))
                .filter(User.id != rotation.coach_user_id)
                .all()
            )
            if coaches:
                # Just pick the first one that's not the declining coach
                next_coach = coaches[0]
            else:
                next_coach = None

        if not next_coach:
            logger.warning(
                f"No other coaches available after {declining_coach_name} declined "
                f"for newsletter #{newsletter_id}"
            )
            return {
                'success': True,
                'previous_coach': declining_coach_name,
                'new_coach': None,
                'rotation_id': None
            }

        # Remove the old declined rotation first (since newsletter_id is unique)
        # Must delete and flush before adding new one to avoid unique constraint violation
        db.session.delete(rotation)
        db.session.flush()

        # Create new rotation assignment for the next coach
        new_rotation = CoachRotation(
            newsletter_id=newsletter_id,
            coach_user_id=next_coach.id,
            status=CoachStatus.ASSIGNED.value,
            assigned_at=datetime.utcnow()
        )
        db.session.add(new_rotation)
        db.session.commit()

        logger.info(
            f"Reassigned coach from {declining_coach_name} to {next_coach.full_name} "
            f"for newsletter #{newsletter_id}"
        )

        return {
            'success': True,
            'previous_coach': declining_coach_name,
            'new_coach': next_coach.full_name,
            'rotation_id': new_rotation.id
        }

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error handling coach decline for newsletter #{newsletter_id}: {e}")
        return {'success': False, 'error': str(e)}


def send_coach_reminder(newsletter_id: int) -> dict:
    """Send a reminder DM to the coach if they haven't submitted yet.

    Only sends reminder if the coach hasn't already submitted their content.

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
        # Get coach rotation assignment
        rotation = CoachRotation.query.filter_by(newsletter_id=newsletter_id).first()
        if not rotation:
            return {
                'success': False,
                'error': f'No coach assigned for newsletter #{newsletter_id}'
            }

        # Check if already submitted
        if rotation.status == CoachStatus.SUBMITTED.value:
            return {
                'success': True,
                'skipped': True,
                'reason': 'Coach has already submitted content'
            }

        # Check if declined
        if rotation.status == CoachStatus.DECLINED.value:
            return {
                'success': True,
                'skipped': True,
                'reason': 'Coach has declined this rotation'
            }

        # Get coach user
        coach = User.query.get(rotation.coach_user_id)
        if not coach:
            return {
                'success': False,
                'error': f'Coach user {rotation.coach_user_id} not found'
            }

        # Check if coach has Slack user linked
        if not coach.slack_user or not coach.slack_user.slack_uid:
            return {
                'success': False,
                'error': f'Coach {coach.full_name} has no linked Slack account'
            }

        slack_uid = coach.slack_user.slack_uid

        # Get newsletter for context
        newsletter = Newsletter.query.get(newsletter_id)
        month_display = newsletter.month_year if newsletter else 'the upcoming month'

        dry_run = _is_dry_run()

        if dry_run:
            logger.info(
                f"[DRY RUN] Would send coach reminder to {coach.full_name} "
                f"({slack_uid}) for newsletter #{newsletter_id}"
            )
            return {
                'success': True,
                'message_ts': 'dry_run_ts',
                'channel_id': 'dry_run_channel'
            }

        # Open DM conversation
        conv_result = open_conversation([slack_uid])
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
                        f"*Friendly reminder!* We're still waiting for your Coaches Corner "
                        f"section for the *{month_display}* Monthly Dispatch.\n\n"
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
                            "text": "Write Coaches Corner",
                            "emoji": True
                        },
                        "style": "primary",
                        "action_id": "coach_submit",
                        "value": str(newsletter_id)
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "I Can't This Month",
                            "emoji": True
                        },
                        "action_id": "coach_decline",
                        "value": str(newsletter_id)
                    }
                ]
            }
        ]

        response = client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text=f"Reminder: Your Coaches Corner for {month_display} is due!",
            unfurl_links=False,
            unfurl_media=False
        )

        message_ts = response.get('ts')
        logger.info(
            f"Sent coach reminder to {coach.full_name} for newsletter #{newsletter_id} "
            f"(channel: {channel_id}, ts: {message_ts})"
        )

        return {
            'success': True,
            'message_ts': message_ts,
            'channel_id': channel_id
        }

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        logger.error(f"Slack API error sending coach reminder: {error_msg}")
        return {'success': False, 'error': error_msg}

    except Exception as e:
        logger.error(f"Error sending coach reminder for newsletter #{newsletter_id}: {e}")
        return {'success': False, 'error': str(e)}


def get_coach_rotation_for_newsletter(newsletter_id: int) -> Optional[CoachRotation]:
    """Get the coach rotation assignment for a newsletter.

    Args:
        newsletter_id: ID of the newsletter

    Returns:
        CoachRotation instance or None if no coach assigned
    """
    return CoachRotation.query.filter_by(newsletter_id=newsletter_id).first()


def build_coach_submission_modal(newsletter_id: int) -> dict:
    """Build a Slack modal for coach to submit Coaches Corner content.

    Args:
        newsletter_id: ID of the newsletter

    Returns:
        Slack modal view payload
    """
    return {
        "type": "modal",
        "callback_id": "coach_submission",
        "private_metadata": str(newsletter_id),
        "title": {
            "type": "plain_text",
            "text": "Coaches Corner"
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
                        "*Welcome to Coaches Corner!*\n\n"
                        "Share your coaching wisdom, training tips, or encouragement "
                        "with fellow club members. This is your space to inspire!"
                    )
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "input",
                "block_id": "coach_content_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "coach_content_input",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Share training tips, technique advice, season reflections, or words of encouragement... (200-400 words)"
                    }
                },
                "label": {
                    "type": "plain_text",
                    "text": "Your Coaches Corner (200-400 words)"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "Your contribution will be featured in the Monthly Dispatch newsletter!"
                    }
                ]
            }
        ]
    }
