"""
Monthly AI Draft Generator for Newsletter Sections.

Generates AI drafts for individual newsletter sections using Claude API.
Each section is generated independently with section-specific context.
"""

import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml

from app.newsletter.interfaces import SectionType, SectionStatus, MessageVisibility
from app.newsletter.models import Newsletter, NewsletterSection, db

logger = logging.getLogger(__name__)

# Maximum characters per section (Slack modal limit)
MAX_SECTION_CHARS = 2900

# Sections that use AI generation
AI_DRAFTED_SECTIONS = [
    SectionType.FROM_THE_BOARD.value,
    SectionType.MEMBER_HEADS_UP.value,
    SectionType.UPCOMING_EVENTS.value,
    SectionType.MONTH_IN_REVIEW.value,
]

# Import anthropic SDK with graceful fallback
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logger.warning("Anthropic SDK not available - AI draft generation will use fallback")


def _load_monthly_prompt() -> str:
    """Load the monthly section generation prompt from file.

    Returns:
        Prompt text string
    """
    prompt_path = Path(__file__).parent.parent.parent / 'config' / 'prompts' / 'newsletter_monthly.md'

    if prompt_path.exists():
        logger.debug(f"Loading monthly prompt from {prompt_path}")
        return prompt_path.read_text()

    logger.warning(f"Monthly prompt not found at {prompt_path}, using embedded default")
    return _get_default_monthly_prompt()


def _get_default_monthly_prompt() -> str:
    """Return embedded default prompt for fallback."""
    return """You are generating a single section of the TCSC Monthly Dispatch newsletter.

Return ONLY a valid JSON object:
{
  "section_type": "the_section_type",
  "content": "The formatted section content...",
  "char_count": 1234
}

Use Slack mrkdwn: *bold*, _italic_, <url|text> links, :emoji:.
NO markdown headers (#), tables, or horizontal rules.
Maximum 2900 characters.
"""


def _load_generation_config() -> dict[str, Any]:
    """Load generation config from newsletter.yaml.

    Returns:
        dict with generation settings (model, max_tokens, temperature, extended_thinking)
    """
    config_path = Path(__file__).parent.parent.parent / 'config' / 'newsletter.yaml'

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
        return config.get('generation', {})
    except (FileNotFoundError, yaml.YAMLError) as e:
        logger.warning(f"Could not load generation config: {e}")
        return {}


def _get_anthropic_client():
    """Get Anthropic client using ANTHROPIC_API_KEY from environment.

    Returns:
        anthropic.Anthropic: Configured Anthropic client

    Raises:
        RuntimeError: If SDK not installed or API key not set
    """
    if not ANTHROPIC_AVAILABLE:
        raise RuntimeError("Anthropic SDK not installed - pip install anthropic")

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable not set")

    return anthropic.Anthropic(api_key=api_key)


def build_section_context(
    newsletter: Newsletter,
    section_type: str,
    slack_messages: Optional[list] = None,
    leadership_messages: Optional[list] = None,
    events: Optional[list] = None,
    member_highlight_answers: Optional[dict] = None
) -> str:
    """Build context string for a specific section type.

    Args:
        newsletter: Newsletter being generated
        section_type: Type of section to build context for
        slack_messages: List of SlackMessage or dict objects from public channels
        leadership_messages: List of SlackMessage or dict objects from leadership channels
        events: List of event dicts with title, date, description
        member_highlight_answers: Dict with member's Q&A responses for highlight section

    Returns:
        Formatted context string for the AI prompt
    """
    sections = []

    # Header with newsletter info
    month_display = newsletter.month_year or "Unknown"
    sections.append(f"=== NEWSLETTER INFO ===")
    sections.append(f"Month: {month_display}")
    if newsletter.period_start and newsletter.period_end:
        sections.append(f"Period: {newsletter.period_start.strftime('%B %d')} - {newsletter.period_end.strftime('%B %d, %Y')}")
    sections.append(f"Section Type: {section_type}")
    sections.append("")

    # Section-specific context
    if section_type == SectionType.FROM_THE_BOARD.value:
        sections.append("=== LEADERSHIP UPDATES ===")
        if leadership_messages:
            sections.append(f"Messages from leadership channels ({len(leadership_messages)} total):")
            sections.append("NOTE: These are from PRIVATE channels - summarize themes only, no names or direct quotes.")
            sections.append("")
            for msg in leadership_messages[:10]:
                # Support both dict and object access
                text = msg.get('text', '') if isinstance(msg, dict) else getattr(msg, 'text', '')
                channel = msg.get('channel_name', 'leadership') if isinstance(msg, dict) else getattr(msg, 'channel_name', 'leadership')
                visibility = msg.get('visibility', 'private') if isinstance(msg, dict) else getattr(msg, 'visibility', MessageVisibility.PRIVATE)
                visibility_str = visibility if isinstance(visibility, str) else visibility.value
                sections.append(f"[{visibility_str.upper()}] #{channel}: {text[:300]}...")
                sections.append("")
        else:
            sections.append("No leadership messages available for this period.")
        sections.append("")

    elif section_type == SectionType.MEMBER_HEADS_UP.value:
        sections.append("=== ANNOUNCEMENTS AND NOTICES ===")
        if slack_messages:
            sections.append(f"Recent announcements ({len(slack_messages)} messages):")
            sections.append("")
            for msg in slack_messages[:15]:
                text = msg.get('text', '') if isinstance(msg, dict) else getattr(msg, 'text', '')
                channel = msg.get('channel_name', 'general') if isinstance(msg, dict) else getattr(msg, 'channel_name', 'general')
                user = msg.get('user_name', 'Unknown') if isinstance(msg, dict) else getattr(msg, 'user_name', 'Unknown')
                permalink = msg.get('permalink', '') if isinstance(msg, dict) else getattr(msg, 'permalink', '')
                visibility = msg.get('visibility', 'public') if isinstance(msg, dict) else getattr(msg, 'visibility', MessageVisibility.PUBLIC)
                visibility_str = visibility if isinstance(visibility, str) else visibility.value

                sections.append(f"[{visibility_str.upper()}] #{channel} | {user}:")
                sections.append(f"  {text[:250]}")
                if permalink and visibility_str == 'public':
                    sections.append(f"  Link: {permalink}")
                sections.append("")
        else:
            sections.append("No announcement messages available.")
        sections.append("")

    elif section_type == SectionType.UPCOMING_EVENTS.value:
        sections.append("=== UPCOMING EVENTS ===")
        if events:
            sections.append(f"Events for the coming month ({len(events)} total):")
            sections.append("")
            for event in events:
                title = event.get('title', 'Untitled Event')
                date = event.get('date', 'TBD')
                description = event.get('description', '')
                location = event.get('location', '')
                sections.append(f"- {title}")
                sections.append(f"  Date: {date}")
                if location:
                    sections.append(f"  Location: {location}")
                if description:
                    sections.append(f"  Details: {description[:150]}")
                sections.append("")
        else:
            sections.append("No events data available.")
        sections.append("")

    elif section_type == SectionType.MONTH_IN_REVIEW.value:
        sections.append("=== MONTH IN REVIEW ===")
        sections.append("Highlights and memorable moments from the past month:")
        sections.append("")

        if slack_messages:
            # Separate public and private messages
            public_msgs = []
            private_msgs = []

            for msg in slack_messages:
                visibility = msg.get('visibility', 'public') if isinstance(msg, dict) else getattr(msg, 'visibility', MessageVisibility.PUBLIC)
                visibility_str = visibility if isinstance(visibility, str) else visibility.value

                if visibility_str == 'public':
                    public_msgs.append(msg)
                else:
                    private_msgs.append(msg)

            if public_msgs:
                sections.append(f"PUBLIC CHANNEL HIGHLIGHTS ({len(public_msgs)} messages):")
                sections.append("(Can quote, link, and name members)")
                sections.append("")
                for msg in public_msgs[:12]:
                    text = msg.get('text', '') if isinstance(msg, dict) else getattr(msg, 'text', '')
                    channel = msg.get('channel_name', 'general') if isinstance(msg, dict) else getattr(msg, 'channel_name', 'general')
                    user = msg.get('user_name', 'Unknown') if isinstance(msg, dict) else getattr(msg, 'user_name', 'Unknown')
                    permalink = msg.get('permalink', '') if isinstance(msg, dict) else getattr(msg, 'permalink', '')
                    reactions = msg.get('reaction_count', 0) if isinstance(msg, dict) else getattr(msg, 'reaction_count', 0)
                    replies = msg.get('reply_count', 0) if isinstance(msg, dict) else getattr(msg, 'reply_count', 0)

                    sections.append(f"[PUBLIC] #{channel} | {user}:")
                    sections.append(f"  {text[:250]}")
                    if permalink:
                        sections.append(f"  Link: {permalink}")
                    sections.append(f"  Engagement: {reactions} reactions, {replies} replies")
                    sections.append("")

            if private_msgs:
                sections.append(f"PRIVATE CHANNEL THEMES ({len(private_msgs)} messages):")
                sections.append("(Summarize themes only - NO names, NO quotes)")
                sections.append("")
                for msg in private_msgs[:5]:
                    text = msg.get('text', '') if isinstance(msg, dict) else getattr(msg, 'text', '')
                    channel = msg.get('channel_name', 'private') if isinstance(msg, dict) else getattr(msg, 'channel_name', 'private')
                    sections.append(f"[PRIVATE] #{channel}: {text[:150]}...")
                    sections.append("")
        else:
            sections.append("No messages available for review.")
        sections.append("")

    elif section_type == SectionType.MEMBER_HIGHLIGHT.value:
        sections.append("=== MEMBER HIGHLIGHT ===")
        if member_highlight_answers:
            sections.append("Member Q&A responses to compose into polished prose:")
            sections.append("")
            for question, answer in member_highlight_answers.items():
                sections.append(f"Q: {question}")
                sections.append(f"A: {answer}")
                sections.append("")
        else:
            sections.append("No member highlight answers available.")
        sections.append("")

    return "\n".join(sections)


def _parse_section_json(content: str) -> Optional[dict]:
    """Parse section JSON from Claude's response.

    Args:
        content: Raw response from Claude

    Returns:
        Parsed dict with section_type, content, char_count or None
    """
    if not content:
        return None

    # Try to extract JSON from markdown code block
    json_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', content)
    if json_match:
        json_str = json_match.group(1).strip()
    else:
        # Try to find JSON object directly
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            json_str = json_match.group(0)
        else:
            json_str = content.strip()

    try:
        parsed = json.loads(json_str)
        if not isinstance(parsed, dict):
            logger.warning("Parsed JSON is not a dict")
            return None

        # Validate required fields
        required_fields = ['section_type', 'content']
        missing = [f for f in required_fields if f not in parsed]
        if missing:
            logger.warning(f"JSON missing required fields: {missing}")

        return parsed

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse section JSON: {e}")
        logger.debug(f"Content that failed to parse: {json_str[:500]}...")
        return None


def generate_section_draft(
    newsletter: Newsletter,
    section_type: str,
    context_data: dict
) -> dict:
    """Generate an AI draft for a single newsletter section.

    Args:
        newsletter: Newsletter to generate section for
        section_type: Type of section (from SectionType enum values)
        context_data: Dict with keys like 'slack_messages', 'leadership_messages',
                      'events', 'member_highlight_answers'

    Returns:
        Dict with keys: success, content, char_count, error (if any), model_used
    """
    logger.info(f"Generating AI draft for section: {section_type}")

    # Build context for this specific section
    context_str = build_section_context(
        newsletter=newsletter,
        section_type=section_type,
        slack_messages=context_data.get('slack_messages'),
        leadership_messages=context_data.get('leadership_messages'),
        events=context_data.get('events'),
        member_highlight_answers=context_data.get('member_highlight_answers')
    )

    if not ANTHROPIC_AVAILABLE:
        logger.warning("Anthropic SDK not available, returning fallback")
        return {
            'success': False,
            'content': None,
            'char_count': 0,
            'error': 'Anthropic SDK not installed',
            'model_used': 'none'
        }

    try:
        # Load prompt and config
        system_prompt = _load_monthly_prompt()
        gen_config = _load_generation_config()

        model = gen_config.get('model', 'claude-sonnet-4-20250514')
        max_tokens = min(gen_config.get('max_tokens', 4000), 8000)  # Limit for section generation
        temperature = gen_config.get('temperature', 0.7)

        # Build user message
        user_message = f"""Generate the "{section_type}" section for the TCSC Monthly Dispatch.

{context_str}

Generate the section now. Output ONLY valid JSON with section_type, content, and char_count."""

        logger.debug(f"Calling Claude API for section {section_type}")
        start_time = time.time()

        client = _get_anthropic_client()

        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "user", "content": f"{system_prompt}\n\n{user_message}"}
            ]
        )

        elapsed = time.time() - start_time
        logger.info(f"Claude API response received in {elapsed:.2f}s for section {section_type}")

        if not response.content:
            logger.error(f"Empty response from Claude API for section {section_type}")
            return {
                'success': False,
                'content': None,
                'char_count': 0,
                'error': 'Empty response from Claude API',
                'model_used': model
            }

        # Extract text content
        raw_content = None
        for block in response.content:
            if hasattr(block, 'text'):
                raw_content = block.text
                break

        if not raw_content:
            logger.error(f"No text content in Claude response for section {section_type}")
            return {
                'success': False,
                'content': None,
                'char_count': 0,
                'error': 'No text content in response',
                'model_used': model
            }

        # Parse JSON response
        parsed = _parse_section_json(raw_content)

        if parsed and 'content' in parsed:
            content = parsed['content']
            char_count = len(content)

            # Truncate if over limit
            if char_count > MAX_SECTION_CHARS:
                logger.warning(f"Section {section_type} content ({char_count} chars) exceeds limit, truncating")
                content = content[:MAX_SECTION_CHARS]
                char_count = MAX_SECTION_CHARS

            logger.info(f"Successfully generated section {section_type} ({char_count} chars)")
            return {
                'success': True,
                'content': content,
                'char_count': char_count,
                'error': None,
                'model_used': model
            }
        else:
            # If JSON parsing failed, try to use raw content
            logger.warning(f"JSON parsing failed for section {section_type}, using raw content")
            char_count = len(raw_content)
            if char_count > MAX_SECTION_CHARS:
                raw_content = raw_content[:MAX_SECTION_CHARS]
                char_count = MAX_SECTION_CHARS

            return {
                'success': True,
                'content': raw_content,
                'char_count': char_count,
                'error': 'JSON parsing failed, used raw content',
                'model_used': model
            }

    except Exception as e:
        logger.error(f"Error generating section {section_type}: {e}")
        return {
            'success': False,
            'content': None,
            'char_count': 0,
            'error': str(e),
            'model_used': 'none'
        }


def generate_all_ai_sections(
    newsletter: Newsletter,
    context_data: dict
) -> dict:
    """Generate AI drafts for all AI-assisted sections and save to database.

    Args:
        newsletter: Newsletter to generate sections for
        context_data: Dict with context data for all sections

    Returns:
        Dict with keys: success, sections (list of results), errors (list)
    """
    logger.info(f"Generating all AI sections for newsletter {newsletter.id}")

    results = {
        'success': True,
        'sections': [],
        'errors': []
    }

    for section_type in AI_DRAFTED_SECTIONS:
        logger.info(f"Processing section: {section_type}")

        # Generate the draft
        draft_result = generate_section_draft(
            newsletter=newsletter,
            section_type=section_type,
            context_data=context_data
        )

        section_result = {
            'section_type': section_type,
            'success': draft_result['success'],
            'char_count': draft_result.get('char_count', 0)
        }

        if draft_result['success'] and draft_result.get('content'):
            # Get or create the section record
            section = NewsletterSection.query.filter_by(
                newsletter_id=newsletter.id,
                section_type=section_type
            ).first()

            if not section:
                from app.newsletter.section_editor import SECTION_ORDER
                section = NewsletterSection(
                    newsletter_id=newsletter.id,
                    section_type=section_type,
                    section_order=SECTION_ORDER.get(section_type, 99),
                    status=SectionStatus.AWAITING_CONTENT.value
                )
                db.session.add(section)
                db.session.flush()

            # Save AI draft
            section.ai_draft = draft_result['content']
            section.content = draft_result['content']
            section.status = SectionStatus.HAS_AI_DRAFT.value
            section.updated_at = datetime.utcnow()

            db.session.commit()
            logger.info(f"Saved AI draft for section {section_type} (id={section.id})")

            section_result['section_id'] = section.id
        else:
            results['success'] = False
            error_msg = draft_result.get('error', 'Unknown error')
            results['errors'].append(f"{section_type}: {error_msg}")
            section_result['error'] = error_msg

        results['sections'].append(section_result)

    total_sections = len(AI_DRAFTED_SECTIONS)
    successful = sum(1 for s in results['sections'] if s['success'])
    logger.info(f"Generated {successful}/{total_sections} AI sections for newsletter {newsletter.id}")

    return results
