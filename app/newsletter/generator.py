"""
Claude API integration for newsletter generation.

Uses Claude Opus 4.5 to generate the Weekly Dispatch newsletter
from collected Slack messages, news items, and member submissions.
"""

import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

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
DEFAULT_TEMPERATURE = 0.7


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

Create an engaging newsletter that:
- Opens with a warm greeting and seasonal context
- Summarizes key Slack activity from the week
- Includes trail conditions from monitored locations
- Shares relevant local ski news
- Incorporates any member submissions
- Ends with a call to action

Use Slack-compatible markdown. Keep total length under 800 words.
Be warm and inclusive, with light touches of humor.

Privacy rules:
- Public channels: Can quote and link
- Private channels: Summarize themes only, no names or links
- Member submissions: Respect attribution preferences
"""


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
        fallback_content = generate_fallback_newsletter(context)
        return GenerationResult(
            success=True,
            content=fallback_content,
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
        logger.info("  Calling Claude API...")
        start_time = time.time()

        client = get_anthropic_client()
        response = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=DEFAULT_MAX_TOKENS,
            temperature=DEFAULT_TEMPERATURE,
            messages=[
                {"role": "user", "content": f"{system_prompt}\n\n{user_message}"}
            ]
        )

        elapsed = time.time() - start_time

        if not response.content:
            logger.error("  ERROR: Empty response from Claude API")
            logger.info("=" * 50)
            return GenerationResult(
                success=False,
                error="Empty response from Claude API"
            )

        content = response.content[0].text
        tokens_used = response.usage.input_tokens + response.usage.output_tokens

        logger.info(f"  Response received in {elapsed:.2f}s")
        logger.info(f"  Tokens used: {tokens_used}")
        logger.info(f"  Content length: {len(content)} chars")
        logger.info("=" * 50)

        return GenerationResult(
            success=True,
            content=content,
            version_number=0,  # Set by caller
            model_used=DEFAULT_MODEL,
            tokens_used=tokens_used,
        )

    except Exception as e:
        logger.error(f"  ERROR: Claude API call failed - {e}")
        logger.info("  Falling back to template-based generation")
        logger.info("=" * 50)

        fallback_content = generate_fallback_newsletter(context)
        return GenerationResult(
            success=True,
            content=fallback_content,
            version_number=0,
            model_used="fallback",
            tokens_used=0,
            error=f"Claude API failed, used fallback: {str(e)}"
        )


def generate_fallback_newsletter(context: NewsletterContext) -> str:
    """Generate newsletter using template-based fallback.

    Used when Claude API is unavailable or fails.

    Args:
        context: NewsletterContext with all collected data

    Returns:
        Template-generated newsletter content
    """
    logger.info("Generating fallback newsletter")

    lines = []

    # Header
    week_str = f"{context.week_start.strftime('%B %d')} - {context.week_end.strftime('%B %d, %Y')}"
    lines.append(f":newspaper: *TCSC Weekly Dispatch* :ski:")
    lines.append(f"_Week of {week_str}_")
    lines.append("")

    # Opening
    lines.append("Hey TCSC! Here's your weekly roundup of what's happening in our skiing community.")
    lines.append("")

    # Week in Review
    if context.slack_messages:
        lines.append("*:speech_balloon: Week in Review*")
        public_msgs = [m for m in context.slack_messages if m.visibility == MessageVisibility.PUBLIC]
        for msg in public_msgs[:5]:
            lines.append(f"- {msg.user_name} in #{msg.channel_name}: {msg.text[:100]}...")
        lines.append("")

    # Trail Conditions
    if context.trail_conditions:
        lines.append("*:evergreen_tree: Trail Conditions*")
        for trail in context.trail_conditions:
            emoji = ":white_check_mark:" if trail.trails_open == 'all' else ":warning:"
            lines.append(f"{emoji} *{trail.location}*: {trail.trails_open} open, {trail.ski_quality} quality")
        lines.append("")

    # Local News
    if context.news_items:
        lines.append("*:newspaper: Local Ski News*")
        for item in context.news_items[:3]:
            lines.append(f"- <{item.url}|{item.title}>")
        lines.append("")

    # Member Submissions
    if context.submissions:
        lines.append("*:star: Member Submissions*")
        for sub in context.submissions:
            if sub.permission_to_name:
                lines.append(f"- From {sub.display_name}: {sub.content[:150]}...")
            else:
                lines.append(f"- Anonymous member shares: {sub.content[:150]}...")
        lines.append("")

    # Closing
    lines.append("---")
    lines.append("See you on the trails! :wave:")
    lines.append("")
    lines.append("_This newsletter was generated automatically. Reply with feedback or suggestions!_")

    return "\n".join(lines)


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
