"""
Member Highlight system for the Monthly Dispatch newsletter.

Handles member nomination, template questions, and AI composition for
the Member Highlight section. Admin nominates a member, bot DMs them
with structured questions, member submits answers, AI composes into
polished prose, editor reviews and edits before publication.
"""

import logging
import os
from datetime import datetime
from typing import Optional

import yaml
from slack_sdk.errors import SlackApiError

from app.models import db, User
from app.newsletter.models import Newsletter, MemberHighlight
from app.newsletter.interfaces import HighlightStatus
from app.slack.client import get_slack_client, open_conversation

logger = logging.getLogger(__name__)

# Module-level config cache
_config_cache = None

# Template questions for member highlights
HIGHLIGHT_QUESTIONS = [
    {
        'id': 'years_skiing',
        'question': 'How long have you been skiing / with the club?',
        'placeholder': 'e.g., "5 years skiing, 2 with TCSC"'
    },
    {
        'id': 'favorite_memory',
        'question': "What's your favorite trail or skiing memory?",
        'placeholder': 'Share a moment that stands out!'
    },
    {
        'id': 'looking_forward',
        'question': 'What are you looking forward to this season?',
        'placeholder': 'A race? More practice? Better technique?'
    },
    {
        'id': 'classic_or_skate',
        'question': 'Classic or skate - and why are you right?',
        'placeholder': 'Defend your choice!'
    },
    {
        'id': 'wipeout_story',
        'question': 'Best wipeout story?',
        'placeholder': "We've all been there..."
    },
    {
        'id': 'anything_else',
        'question': 'Anything else you want to share with the club?',
        'placeholder': 'Optional - tips, shoutouts, random thoughts!'
    },
]


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


def nominate_member(
    newsletter_id: int,
    member_user_id: int,
    nominated_by: str
) -> dict:
    """Nominate a member for the Member Highlight section.

    Creates a MemberHighlight record linking the member to the newsletter.
    If a nomination already exists for this newsletter, it will be updated.

    Args:
        newsletter_id: ID of the newsletter
        member_user_id: User ID of the member being nominated
        nominated_by: Email of the admin who nominated the member

    Returns:
        dict with keys:
        - success: bool
        - highlight_id: int (if successful)
        - member_name: str (if successful)
        - error: str (if failed)
    """
    try:
        # Check if newsletter exists
        newsletter = Newsletter.query.get(newsletter_id)
        if not newsletter:
            return {'success': False, 'error': f'Newsletter {newsletter_id} not found'}

        # Check if member exists
        member = User.query.get(member_user_id)
        if not member:
            return {'success': False, 'error': f'User {member_user_id} not found'}

        # Check for existing nomination
        existing = MemberHighlight.query.filter_by(newsletter_id=newsletter_id).first()
        if existing:
            # Update existing nomination
            existing.member_user_id = member_user_id
            existing.nominated_by = nominated_by
            existing.raw_answers = None
            existing.ai_composed_content = None
            existing.content = None
            existing.status = HighlightStatus.NOMINATED.value
            existing.submitted_at = None
            existing.nominated_at = datetime.utcnow()
            db.session.commit()

            logger.info(
                f"Updated member highlight nomination to {member.full_name} "
                f"for newsletter #{newsletter_id} (by {nominated_by})"
            )

            return {
                'success': True,
                'highlight_id': existing.id,
                'member_name': member.full_name
            }

        # Create new nomination
        highlight = MemberHighlight(
            newsletter_id=newsletter_id,
            member_user_id=member_user_id,
            nominated_by=nominated_by,
            status=HighlightStatus.NOMINATED.value,
            nominated_at=datetime.utcnow()
        )
        db.session.add(highlight)
        db.session.commit()

        logger.info(
            f"Nominated {member.full_name} for member highlight "
            f"in newsletter #{newsletter_id} (by {nominated_by})"
        )

        return {
            'success': True,
            'highlight_id': highlight.id,
            'member_name': member.full_name
        }

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error nominating member for newsletter #{newsletter_id}: {e}")
        return {'success': False, 'error': str(e)}


def send_highlight_request(newsletter_id: int) -> dict:
    """Send a DM to the nominated member with highlight questions.

    The DM includes information about being featured in the newsletter
    and a button that opens a modal for submitting answers to the
    template questions.

    Note: Member must have a linked SlackUser to receive DMs.

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
        # Get member highlight nomination
        highlight = MemberHighlight.query.filter_by(newsletter_id=newsletter_id).first()
        if not highlight:
            return {
                'success': False,
                'error': f'No member nominated for newsletter #{newsletter_id}'
            }

        # Get member user
        member = User.query.get(highlight.member_user_id)
        if not member:
            return {
                'success': False,
                'error': f'Member user {highlight.member_user_id} not found'
            }

        # Check if member has Slack user linked
        if not member.slack_user or not member.slack_user.slack_uid:
            return {
                'success': False,
                'error': f'Member {member.full_name} has no linked Slack account'
            }

        slack_uid = member.slack_user.slack_uid

        # Get newsletter for context
        newsletter = Newsletter.query.get(newsletter_id)
        month_display = newsletter.month_year if newsletter else 'the upcoming month'

        dry_run = _is_dry_run()

        if dry_run:
            logger.info(
                f"[DRY RUN] Would send highlight request to {member.full_name} "
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
                    "text": "You're Our Featured Member!",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"Hi {member.first_name}! You've been nominated to be featured "
                        f"in the *Member Highlight* section of the *{month_display}* "
                        "Monthly Dispatch newsletter!\n\n"
                        "We'd love to share your skiing story with the club. "
                        "Click the button below to answer a few fun questions about "
                        "your skiing journey and experiences."
                    )
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "It only takes a few minutes, and your fellow club members will love hearing about you!"
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
                            "text": "Share My Story",
                            "emoji": True
                        },
                        "style": "primary",
                        "action_id": "highlight_submit",
                        "value": str(newsletter_id)
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Not This Time",
                            "emoji": True
                        },
                        "action_id": "highlight_decline",
                        "value": str(newsletter_id)
                    }
                ]
            }
        ]

        response = client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text=f"You've been nominated for the Member Highlight in the {month_display} newsletter!",
            unfurl_links=False,
            unfurl_media=False
        )

        message_ts = response.get('ts')
        logger.info(
            f"Sent highlight request to {member.full_name} for newsletter #{newsletter_id} "
            f"(channel: {channel_id}, ts: {message_ts})"
        )

        return {
            'success': True,
            'message_ts': message_ts,
            'channel_id': channel_id
        }

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        logger.error(f"Slack API error sending highlight request: {error_msg}")
        return {'success': False, 'error': error_msg}

    except Exception as e:
        logger.error(f"Error sending highlight request for newsletter #{newsletter_id}: {e}")
        return {'success': False, 'error': str(e)}


def handle_highlight_submission(newsletter_id: int, raw_answers: dict) -> dict:
    """Process a member's highlight submission with answers to template questions.

    Updates the MemberHighlight record with the submitted answers (as JSON)
    and marks it as submitted.

    Args:
        newsletter_id: ID of the newsletter
        raw_answers: Dict mapping question IDs to answer text
                    (e.g., {'years_skiing': '5 years', 'favorite_memory': '...'})

    Returns:
        dict with keys:
        - success: bool
        - highlight_id: int (if successful)
        - error: str (if failed)
    """
    try:
        # Get member highlight
        highlight = MemberHighlight.query.filter_by(newsletter_id=newsletter_id).first()
        if not highlight:
            return {
                'success': False,
                'error': f'No member nominated for newsletter #{newsletter_id}'
            }

        # Validate answers - at least one non-empty answer required
        has_content = False
        if raw_answers:
            for question in HIGHLIGHT_QUESTIONS:
                answer = raw_answers.get(question['id'], '').strip()
                if answer:
                    has_content = True
                    break

        if not has_content:
            return {
                'success': False,
                'error': 'At least one question must be answered'
            }

        # Update highlight record
        highlight.raw_answers = raw_answers
        highlight.status = HighlightStatus.SUBMITTED.value
        highlight.submitted_at = datetime.utcnow()
        db.session.commit()

        member = User.query.get(highlight.member_user_id)
        member_name = member.full_name if member else f"user {highlight.member_user_id}"
        logger.info(
            f"Member {member_name} submitted highlight answers for newsletter #{newsletter_id}"
        )

        return {
            'success': True,
            'highlight_id': highlight.id
        }

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error processing highlight submission for newsletter #{newsletter_id}: {e}")
        return {'success': False, 'error': str(e)}


def mark_highlight_declined(newsletter_id: int) -> dict:
    """Mark the member highlight as declined.

    Updates the MemberHighlight status to declined when the nominated
    member chooses not to participate.

    Args:
        newsletter_id: ID of the newsletter

    Returns:
        dict with keys:
        - success: bool
        - highlight_id: int (if successful)
        - member_name: str (if successful)
        - error: str (if failed)
    """
    try:
        # Get member highlight
        highlight = MemberHighlight.query.filter_by(newsletter_id=newsletter_id).first()
        if not highlight:
            return {
                'success': False,
                'error': f'No member nominated for newsletter #{newsletter_id}'
            }

        # Get member name for logging
        member = User.query.get(highlight.member_user_id)
        member_name = member.full_name if member else f"user {highlight.member_user_id}"

        # Mark as declined
        highlight.status = HighlightStatus.DECLINED.value
        db.session.commit()

        logger.info(
            f"Member {member_name} declined highlight for newsletter #{newsletter_id}"
        )

        return {
            'success': True,
            'highlight_id': highlight.id,
            'member_name': member_name
        }

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error marking highlight declined for newsletter #{newsletter_id}: {e}")
        return {'success': False, 'error': str(e)}


def compose_highlight_with_ai(newsletter_id: int) -> dict:
    """Use AI to compose polished prose from member's raw answers.

    Takes the raw Q&A format answers and composes them into a flowing
    narrative suitable for the newsletter's Member Highlight section.

    Args:
        newsletter_id: ID of the newsletter

    Returns:
        dict with keys:
        - success: bool
        - highlight_id: int (if successful)
        - composed_content: str (if successful)
        - error: str (if failed)
    """
    try:
        # Get member highlight
        highlight = MemberHighlight.query.filter_by(newsletter_id=newsletter_id).first()
        if not highlight:
            return {
                'success': False,
                'error': f'No member nominated for newsletter #{newsletter_id}'
            }

        if highlight.status != HighlightStatus.SUBMITTED.value:
            return {
                'success': False,
                'error': 'Member has not submitted their answers yet'
            }

        if not highlight.raw_answers:
            return {
                'success': False,
                'error': 'No raw answers to compose from'
            }

        # Get member info for context
        member = User.query.get(highlight.member_user_id)
        member_name = member.full_name if member else "Member"

        # Build Q&A context for the prompt
        qa_parts = []
        for question in HIGHLIGHT_QUESTIONS:
            answer = highlight.raw_answers.get(question['id'], '').strip()
            if answer:
                qa_parts.append(f"Q: {question['question']}\nA: {answer}")

        qa_context = "\n\n".join(qa_parts)

        # Build the prompt
        prompt = f"""You are writing a Member Highlight section for the Twin Cities Ski Club's Monthly Dispatch newsletter.

The member being featured is: {member_name}

Here are their answers to our template questions:

{qa_context}

Please compose these answers into a warm, engaging 2-3 paragraph profile that:
1. Flows naturally as prose (not Q&A format)
2. Highlights what makes this member special
3. Captures their personality and enthusiasm
4. Uses a friendly, welcoming tone that matches a club newsletter
5. Is approximately 200-300 words

Write the member profile:"""

        # Try to use Anthropic client if available
        try:
            from app.agent.brain import get_anthropic_client, ANTHROPIC_AVAILABLE

            if not ANTHROPIC_AVAILABLE:
                logger.warning("Anthropic SDK not available, using fallback composition")
                composed = _fallback_compose_highlight(member_name, highlight.raw_answers)
            else:
                logger.info(f"Composing highlight with AI for member {member_name}")

                import time
                start_time = time.time()
                client = get_anthropic_client()
                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1000,
                    messages=[{"role": "user", "content": prompt}]
                )
                elapsed = time.time() - start_time

                if not response.content:
                    logger.error("Empty response from Claude API")
                    composed = _fallback_compose_highlight(member_name, highlight.raw_answers)
                else:
                    composed = response.content[0].text.strip()
                    logger.info(
                        f"AI composed highlight for {member_name} in {elapsed:.2f}s "
                        f"({len(composed)} chars)"
                    )

        except (ImportError, RuntimeError) as e:
            logger.warning(f"Could not use Anthropic client: {e}")
            composed = _fallback_compose_highlight(member_name, highlight.raw_answers)

        # Save the composed content
        highlight.ai_composed_content = composed
        db.session.commit()

        return {
            'success': True,
            'highlight_id': highlight.id,
            'composed_content': composed
        }

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error composing highlight for newsletter #{newsletter_id}: {e}")
        return {'success': False, 'error': str(e)}


def _fallback_compose_highlight(member_name: str, raw_answers: dict) -> str:
    """Fallback composition without AI.

    Creates a simple formatted version of the Q&A answers.

    Args:
        member_name: Name of the featured member
        raw_answers: Dict of question IDs to answers

    Returns:
        Formatted highlight text
    """
    parts = [f"Meet {member_name}!"]

    # Map question IDs to readable intros
    intro_map = {
        'years_skiing': 'Skiing experience:',
        'favorite_memory': 'Favorite memory:',
        'looking_forward': 'Looking forward to:',
        'classic_or_skate': 'On the classic vs skate debate:',
        'wipeout_story': 'Best wipeout story:',
        'anything_else': 'Also:'
    }

    for question in HIGHLIGHT_QUESTIONS:
        answer = raw_answers.get(question['id'], '').strip()
        if answer:
            intro = intro_map.get(question['id'], question['question'])
            parts.append(f"{intro} {answer}")

    return "\n\n".join(parts)


def get_previous_highlight_dates(member_user_id: int) -> list[datetime]:
    """Get dates when a member was previously featured in the highlight.

    Useful for ensuring members aren't featured too frequently and for
    showing highlight history in the admin UI.

    Args:
        member_user_id: User ID of the member

    Returns:
        List of datetime objects when the member was featured,
        ordered by most recent first
    """
    highlights = (
        MemberHighlight.query
        .filter_by(member_user_id=member_user_id)
        .filter(MemberHighlight.status == HighlightStatus.SUBMITTED.value)
        .order_by(MemberHighlight.submitted_at.desc())
        .all()
    )

    return [h.submitted_at for h in highlights if h.submitted_at]


def get_highlight_for_newsletter(newsletter_id: int) -> Optional[MemberHighlight]:
    """Get the member highlight for a newsletter.

    Args:
        newsletter_id: ID of the newsletter

    Returns:
        MemberHighlight instance or None if no nomination exists
    """
    return MemberHighlight.query.filter_by(newsletter_id=newsletter_id).first()


def build_highlight_submission_modal(newsletter_id: int) -> dict:
    """Build a Slack modal for member to submit highlight answers.

    Args:
        newsletter_id: ID of the newsletter

    Returns:
        Slack modal view payload
    """
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "*Welcome to the Member Highlight!*\n\n"
                    "Answer as many questions as you'd like below. "
                    "Your answers will be woven into a profile for the newsletter. "
                    "Have fun with it!"
                )
            }
        },
        {
            "type": "divider"
        }
    ]

    # Add input blocks for each question
    for question in HIGHLIGHT_QUESTIONS:
        # Use optional=True for all questions except the first
        is_optional = question['id'] != 'years_skiing'

        blocks.append({
            "type": "input",
            "block_id": f"highlight_{question['id']}_block",
            "optional": is_optional,
            "element": {
                "type": "plain_text_input",
                "action_id": f"highlight_{question['id']}_input",
                "multiline": True,
                "placeholder": {
                    "type": "plain_text",
                    "text": question['placeholder']
                }
            },
            "label": {
                "type": "plain_text",
                "text": question['question']
            }
        })

    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": "Your highlight will be featured in the Monthly Dispatch newsletter!"
            }
        ]
    })

    return {
        "type": "modal",
        "callback_id": "highlight_submission",
        "private_metadata": str(newsletter_id),
        "title": {
            "type": "plain_text",
            "text": "Member Highlight"
        },
        "submit": {
            "type": "plain_text",
            "text": "Submit"
        },
        "close": {
            "type": "plain_text",
            "text": "Cancel"
        },
        "blocks": blocks
    }
