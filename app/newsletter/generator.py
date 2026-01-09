"""
Claude API integration for newsletter generation.

Uses Claude Opus 4.5 to generate the Weekly Dispatch newsletter
from collected Slack messages, news items, and member submissions.
"""

import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

import yaml

from app.newsletter.interfaces import (
    GenerationResult,
    NewsletterContext,
    SlackMessage,
    NewsItem,
    MemberSubmission,
    TrailConditionSummary,
    MessageVisibility,
)
from app.newsletter.models import (
    Newsletter,
    NewsletterVersion,
    NewsletterPrompt,
    db,
)

logger = logging.getLogger(__name__)

# Import anthropic SDK with graceful fallback
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logger.warning("Anthropic SDK not available - newsletter generation will use fallback")


# Default model configuration
DEFAULT_MODEL = "claude-opus-4-5-20251101"
DEFAULT_MAX_TOKENS = 4000
DEFAULT_TEMPERATURE = 1.0  # Required for extended thinking


def _load_generation_config() -> dict[str, Any]:
    """Load generation config from newsletter.yaml.

    Returns:
        dict with generation settings (model, max_tokens, temperature, extended_thinking)
    """
    config_path = Path(__file__).parent.parent.parent / 'config' / 'newsletter.yaml'

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
        return config.get('newsletter', {}).get('generation', {})
    except (FileNotFoundError, yaml.YAMLError) as e:
        logger.warning(f"Could not load generation config: {e}")
        return {}


def get_anthropic_client():
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


def get_newsletter_prompt(name: str = 'main') -> str:
    """Load newsletter generation prompt from database or file fallback.

    Priority:
    1. Active NewsletterPrompt from database with matching name
    2. File from config/prompts/newsletter_{name}.md
    3. Embedded default prompt

    Args:
        name: Prompt name (e.g., 'main', 'final', 'quiet')

    Returns:
        Prompt text string
    """
    # 1. Try database first
    db_prompt = NewsletterPrompt.get_active(name)
    if db_prompt:
        logger.info(f"Using database prompt '{name}' (v{db_prompt.version})")
        return db_prompt.content

    # 2. Try file fallback
    prompt_path = Path(__file__).parent.parent.parent / 'config' / 'prompts' / f'newsletter_{name}.md'
    if prompt_path.exists():
        logger.info(f"Using file prompt from {prompt_path}")
        return prompt_path.read_text()

    # 3. Embedded default (main prompt only)
    logger.warning(f"No prompt found for '{name}', using embedded default")
    return _get_default_prompt()


def _get_default_prompt() -> str:
    """Return embedded default prompt for fallback."""
    return """You are writing the weekly newsletter for the Twin Cities Ski Club (TCSC).

Return ONLY a valid JSON object with this structure:
{
  "week_dates": "Month Day-Day, Year",
  "opening_hook": "2-3 engaging sentences...",
  "week_in_review": ["Item 1", "Item 2"],
  "trail_conditions": [{"location": "Name", "status": "Open", "quality": "Good", "notes": ""}],
  "local_news": [{"title": "Title", "link": "URL", "summary": "Brief"}],
  "member_submissions": [],
  "looking_ahead": ["Upcoming item"],
  "closing": "Sign-off :wave:"
}

Use Slack mrkdwn: *bold*, _italic_, <url|text> links, :emoji:.
NO markdown headers, tables, or horizontal rules.
"""


def _parse_newsletter_json(content: str) -> Optional[dict]:
    """Parse newsletter JSON from Claude's response.

    Handles various formats Claude might return:
    - Pure JSON
    - JSON in markdown code blocks
    - JSON with surrounding text

    Args:
        content: Raw response from Claude

    Returns:
        Parsed dict or None if parsing fails
    """
    if not content:
        return None

    # Try to extract JSON from markdown code block
    json_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', content)
    if json_match:
        json_str = json_match.group(1).strip()
    else:
        # Try to find JSON object directly
        # Look for content starting with { and ending with }
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

        # Validate required fields exist
        required_fields = ['week_dates', 'opening_hook', 'closing']
        missing = [f for f in required_fields if f not in parsed]
        if missing:
            logger.warning(f"JSON missing required fields: {missing}")
            # Still return the parsed content, just log the warning

        return parsed

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse newsletter JSON: {e}")
        logger.debug(f"Content that failed to parse: {json_str[:500]}...")
        return None


def _structured_to_markdown(content: dict) -> str:
    """Convert structured content dict to markdown string for storage.

    This provides a readable fallback in case Block Kit rendering fails.

    Args:
        content: Structured newsletter content dict

    Returns:
        Markdown string representation
    """
    lines = []

    week = content.get('week_dates', 'This Week')
    lines.append(f":newspaper: *TCSC Weekly Dispatch* :ski:")
    lines.append(f"_{week}_")
    lines.append("")

    if content.get('opening_hook'):
        lines.append(content['opening_hook'])
        lines.append("")

    if content.get('week_in_review'):
        lines.append("*:speech_balloon: Week in Review*")
        for item in content['week_in_review']:
            lines.append(f"• {item}")
        lines.append("")

    if content.get('trail_conditions'):
        lines.append("*:ski: Trail Conditions*")
        for trail in content['trail_conditions']:
            loc = trail.get('location', '')
            status = trail.get('status', '')
            quality = trail.get('quality', '')
            lines.append(f"• *{loc}*: {status}, {quality}")
        lines.append("")

    if content.get('local_news'):
        lines.append("*:newspaper: Local Ski News*")
        for news in content['local_news']:
            title = news.get('title', '')
            link = news.get('link', '')
            if link:
                lines.append(f"• <{link}|{title}>")
            else:
                lines.append(f"• {title}")
        lines.append("")

    if content.get('member_submissions'):
        lines.append("*:raised_hands: Member Submissions*")
        for sub in content['member_submissions']:
            text = sub.get('content', '')
            attr = sub.get('attribution', 'Anonymous')
            lines.append(f"• {text} _— {attr}_")
        lines.append("")

    if content.get('looking_ahead'):
        lines.append("*:calendar: Looking Ahead*")
        for item in content['looking_ahead']:
            lines.append(f"• {item}")
        lines.append("")

    if content.get('closing'):
        lines.append(content['closing'])

    return "\n".join(lines)


def build_generation_context(context: NewsletterContext) -> str:
    """Build the context section for Claude from collected data.

    Formats all collected data into a structured text block
    that Claude can use to generate the newsletter.

    Args:
        context: NewsletterContext with all collected data

    Returns:
        Formatted context string
    """
    sections = []

    # Header with date range
    sections.append(f"=== NEWSLETTER WEEK ===")
    sections.append(f"Week: {context.week_start.strftime('%B %d')} - {context.week_end.strftime('%B %d, %Y')}")
    sections.append("")

    # Slack messages section
    if context.slack_messages:
        sections.append("=== SLACK ACTIVITY ===")
        sections.append(f"Total messages collected: {len(context.slack_messages)}")
        sections.append("")

        # Group by visibility
        public_msgs = [m for m in context.slack_messages if m.visibility == MessageVisibility.PUBLIC]
        private_msgs = [m for m in context.slack_messages if m.visibility == MessageVisibility.PRIVATE]

        if public_msgs:
            sections.append("PUBLIC CHANNEL HIGHLIGHTS (can quote, link, name):")
            for msg in public_msgs[:15]:  # Limit to top 15
                engagement = f"[{msg.reaction_count} reactions, {msg.reply_count} replies]"
                sections.append(f"- #{msg.channel_name} | {msg.user_name}: {msg.text[:200]}...")
                if msg.permalink:
                    sections.append(f"  Link: {msg.permalink}")
                sections.append(f"  {engagement}")
                sections.append("")

        if private_msgs:
            sections.append("PRIVATE CHANNEL THEMES (summarize only, no names/links):")
            for msg in private_msgs[:5]:  # Limit to 5
                sections.append(f"- #{msg.channel_name}: {msg.text[:150]}...")
            sections.append("")

    # Trail conditions section
    if context.trail_conditions:
        sections.append("=== TRAIL CONDITIONS ===")
        for trail in context.trail_conditions:
            grooming = ""
            if trail.groomed:
                grooming = f" | Groomed for {trail.groomed_for or 'skiing'}"
            date_str = ""
            if trail.report_date:
                date_str = f" (reported {trail.report_date.strftime('%m/%d')})"
            sections.append(
                f"- {trail.location}: {trail.trails_open} open, "
                f"{trail.ski_quality} quality{grooming}{date_str}"
            )
            if trail.notes:
                sections.append(f"  Notes: {trail.notes[:100]}...")
        sections.append("")

    # News items section
    if context.news_items:
        sections.append("=== LOCAL SKI NEWS ===")
        for item in context.news_items:
            date_str = ""
            if item.published_at:
                date_str = f" ({item.published_at.strftime('%m/%d')})"
            sections.append(f"- [{item.source.value}] {item.title}{date_str}")
            sections.append(f"  URL: {item.url}")
            if item.summary:
                sections.append(f"  Summary: {item.summary[:150]}...")
            sections.append("")

    # Member submissions section
    if context.submissions:
        sections.append("=== MEMBER SUBMISSIONS ===")
        for sub in context.submissions:
            attribution = "(use their name)" if sub.permission_to_name else "(keep anonymous)"
            sections.append(f"- Type: {sub.submission_type.value} {attribution}")
            if sub.permission_to_name:
                sections.append(f"  From: {sub.display_name}")
            sections.append(f"  Content: {sub.content}")
            sections.append("")

    # Prior newsletter for continuity
    if context.prior_newsletter_content:
        sections.append("=== PRIOR NEWSLETTER (for continuity) ===")
        # Truncate to avoid making context too long
        prior_preview = context.prior_newsletter_content[:1000]
        if len(context.prior_newsletter_content) > 1000:
            prior_preview += "...[truncated]"
        sections.append(prior_preview)
        sections.append("")

    # Admin feedback if any
    if context.admin_feedback:
        sections.append("=== ADMIN FEEDBACK ===")
        sections.append("Please incorporate this feedback in the regeneration:")
        sections.append(context.admin_feedback)
        sections.append("")

    return "\n".join(sections)


def generate_newsletter(
    context: NewsletterContext,
    is_final: bool = False
) -> GenerationResult:
    """Generate newsletter content using Claude Opus 4.5.

    Args:
        context: NewsletterContext with all collected data
        is_final: Whether this is the Sunday final version

    Returns:
        GenerationResult with success status and content
    """
    if not ANTHROPIC_AVAILABLE:
        logger.warning("Anthropic SDK not available, using fallback generator")
        structured = generate_fallback_newsletter(context)
        content = _structured_to_markdown(structured)
        return GenerationResult(
            success=True,
            content=content,
            structured_content=structured,
            version_number=0,
            model_used="fallback",
            tokens_used=0,
        )

    logger.info("=" * 50)
    logger.info("CLAUDE API: Generating newsletter content")
    logger.info(f"  Final version: {is_final}")
    logger.info(f"  Week: {context.week_start.strftime('%Y-%m-%d')} to {context.week_end.strftime('%Y-%m-%d')}")

    # Build the prompt
    prompt_name = 'final' if is_final else 'main'
    system_prompt = get_newsletter_prompt(prompt_name)

    # Build context section
    context_text = build_generation_context(context)
    logger.info(f"  Context length: {len(context_text)} chars")

    # Build the user message
    user_message = f"""Based on the following collected content, generate this week's TCSC Weekly Dispatch newsletter.

{context_text}

Generate the newsletter now. Remember to use Slack-compatible markdown and follow the formatting guidelines."""

    if is_final:
        user_message += """

This is the FINAL version for Sunday publication. Make it polished and publication-ready.
Double-check that all links are properly formatted and all names are attributed correctly."""

    try:
        # Load generation config
        gen_config = _load_generation_config()
        model = gen_config.get('model', DEFAULT_MODEL)
        max_tokens = gen_config.get('max_tokens', DEFAULT_MAX_TOKENS)
        temperature = gen_config.get('temperature', DEFAULT_TEMPERATURE)

        # Check for extended thinking config
        thinking_config = gen_config.get('extended_thinking', {})
        use_thinking = thinking_config.get('enabled', False)
        thinking_budget = thinking_config.get('budget_tokens', 10000)

        logger.info("  Calling Claude API...")
        if use_thinking:
            logger.info(f"  Extended thinking enabled (budget: {thinking_budget} tokens)")
        start_time = time.time()

        client = get_anthropic_client()

        # Build API call parameters
        api_params = {
            'model': model,
            'max_tokens': max_tokens,
            'messages': [
                {"role": "user", "content": f"{system_prompt}\n\n{user_message}"}
            ]
        }

        # Add extended thinking if enabled
        if use_thinking:
            api_params['temperature'] = 1  # Required for extended thinking
            api_params['thinking'] = {
                "type": "enabled",
                "budget_tokens": thinking_budget
            }
        else:
            api_params['temperature'] = temperature

        # Use streaming for extended thinking (required for long operations)
        if use_thinking:
            logger.info("  Using streaming mode for extended thinking...")
            logger.info("  Claude is thinking deeply...")

            thinking_started = False
            text_started = False
            dot_count = 0

            with client.messages.stream(**api_params) as stream:
                for event in stream:
                    # Log progress indicators
                    if hasattr(event, 'type'):
                        if event.type == 'content_block_start':
                            block = getattr(event, 'content_block', None)
                            if block and getattr(block, 'type', None) == 'thinking':
                                if not thinking_started:
                                    logger.info("  [Thinking phase started]")
                                    thinking_started = True
                            elif block and getattr(block, 'type', None) == 'text':
                                if not text_started:
                                    logger.info("  [Writing response]")
                                    text_started = True
                        elif event.type == 'content_block_delta':
                            # Show periodic progress
                            dot_count += 1
                            if dot_count % 50 == 0:
                                logger.info(f"  ... still processing ({dot_count} chunks)")

                # Get the final message
                response = stream.get_final_message()

            logger.info("  [Stream complete]")

            elapsed = time.time() - start_time

            if not response.content:
                logger.error("  ERROR: Empty response from Claude API")
                logger.info("=" * 50)
                return GenerationResult(
                    success=False,
                    error="Empty response from Claude API"
                )

            # Extract text content (skip thinking blocks)
            raw_content = None
            for block in response.content:
                if hasattr(block, 'text'):
                    raw_content = block.text
                    break

            tokens_used = response.usage.input_tokens + response.usage.output_tokens
        else:
            response = client.messages.create(**api_params)

            elapsed = time.time() - start_time

            if not response.content:
                logger.error("  ERROR: Empty response from Claude API")
                logger.info("=" * 50)
                return GenerationResult(
                    success=False,
                    error="Empty response from Claude API"
                )

            # Extract text content (skip thinking blocks)
            raw_content = None
            for block in response.content:
                if hasattr(block, 'text'):
                    raw_content = block.text
                    break

            tokens_used = response.usage.input_tokens + response.usage.output_tokens

        if not raw_content:
            logger.error("  ERROR: No text content in response")
            logger.info("=" * 50)
            return GenerationResult(
                success=False,
                error="No text content in Claude response"
            )

        logger.info(f"  Response received in {elapsed:.2f}s")
        logger.info(f"  Tokens used: {tokens_used}")
        logger.info(f"  Content length: {len(raw_content)} chars")

        # Try to parse as JSON
        structured_content = _parse_newsletter_json(raw_content)

        if structured_content:
            logger.info("  Successfully parsed JSON response")
            # Convert to markdown for storage/fallback
            content = _structured_to_markdown(structured_content)
        else:
            logger.warning("  Could not parse JSON, using raw content")
            content = raw_content
            structured_content = None

        logger.info("=" * 50)

        return GenerationResult(
            success=True,
            content=content,
            structured_content=structured_content,
            version_number=0,  # Set by caller
            model_used=DEFAULT_MODEL,
            tokens_used=tokens_used,
        )

    except Exception as e:
        logger.error(f"  ERROR: Claude API call failed - {e}")
        logger.info("  Falling back to template-based generation")
        logger.info("=" * 50)

        structured = generate_fallback_newsletter(context)
        content = _structured_to_markdown(structured)
        return GenerationResult(
            success=True,
            content=content,
            structured_content=structured,
            version_number=0,
            model_used="fallback",
            tokens_used=0,
            error=f"Claude API failed, used fallback: {str(e)}"
        )


def generate_fallback_newsletter(context: NewsletterContext) -> dict:
    """Generate newsletter using template-based fallback.

    Used when Claude API is unavailable or fails.

    Args:
        context: NewsletterContext with all collected data

    Returns:
        Structured newsletter content dict
    """
    logger.info("Generating fallback newsletter")

    week_str = f"{context.week_start.strftime('%B %d')} - {context.week_end.strftime('%B %d, %Y')}"

    # Build structured content
    structured = {
        "week_dates": week_str,
        "opening_hook": "Hey TCSC! :ski: Here's your weekly roundup of what's happening in our skiing community.",
        "week_in_review": [],
        "trail_conditions": [],
        "local_news": [],
        "member_submissions": [],
        "looking_ahead": [],
        "closing": "See you on the trails! :wave:\n\n_This newsletter was generated automatically._"
    }

    # Week in Review
    if context.slack_messages:
        public_msgs = [m for m in context.slack_messages if m.visibility == MessageVisibility.PUBLIC]
        for msg in public_msgs[:5]:
            link_text = f"<{msg.permalink}|{msg.user_name}>" if msg.permalink else msg.user_name
            structured["week_in_review"].append(
                f"{link_text} in #{msg.channel_name}: {msg.text[:100]}..."
            )

    # Trail Conditions
    if context.trail_conditions:
        for trail in context.trail_conditions:
            structured["trail_conditions"].append({
                "location": trail.location,
                "status": trail.trails_open.capitalize() if trail.trails_open else "Unknown",
                "quality": trail.ski_quality.capitalize() if trail.ski_quality else "Unknown",
                "notes": trail.notes[:100] if trail.notes else ""
            })

    # Local News
    if context.news_items:
        for item in context.news_items[:3]:
            structured["local_news"].append({
                "title": item.title,
                "link": item.url,
                "summary": item.summary[:100] if item.summary else ""
            })

    # Member Submissions
    if context.submissions:
        for sub in context.submissions:
            structured["member_submissions"].append({
                "type": sub.submission_type.value,
                "content": sub.content[:150],
                "attribution": sub.display_name if sub.permission_to_name else "Anonymous"
            })

    return structured


def save_newsletter_version(
    newsletter: Newsletter,
    result: GenerationResult,
    trigger: str = 'scheduled'
) -> NewsletterVersion:
    """Save a generated newsletter as a new version.

    Args:
        newsletter: Newsletter to save version for
        result: GenerationResult from generation
        trigger: What triggered this version (scheduled, manual, feedback)

    Returns:
        Created NewsletterVersion object
    """
    # Increment version number
    newsletter.current_version = (newsletter.current_version or 0) + 1
    newsletter.current_content = result.content
    newsletter.updated_at = datetime.utcnow()

    # Create version record
    version = NewsletterVersion(
        newsletter_id=newsletter.id,
        version_number=newsletter.current_version,
        content=result.content,
        trigger_type=trigger,
        model_used=result.model_used,
        tokens_used=result.tokens_used,
    )
    db.session.add(version)
    db.session.commit()

    logger.info(f"Saved newsletter version {newsletter.current_version} for newsletter {newsletter.id}")

    return version


def regenerate_with_feedback(
    newsletter: Newsletter,
    context: NewsletterContext,
    feedback: str
) -> GenerationResult:
    """Regenerate newsletter incorporating admin feedback.

    Args:
        newsletter: Newsletter to regenerate
        context: Original NewsletterContext
        feedback: Admin feedback to incorporate

    Returns:
        GenerationResult with updated content
    """
    # Add feedback to context
    context.admin_feedback = feedback

    # Generate with feedback
    result = generate_newsletter(context, is_final=False)

    if result.success:
        # Clear feedback after successful regeneration
        newsletter.admin_feedback = None
        save_newsletter_version(newsletter, result, trigger='feedback')

    return result
