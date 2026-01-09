"""
MCP (Model Context Protocol) server for newsletter generation.

Provides tools that Claude can call during newsletter generation to:
- Collect Slack messages from channels
- Get member submissions
- Scrape external ski news
- Get trail conditions
- Access prior newsletter for continuity
- Save newsletter versions
- Update the living Slack post

This enables an agentic approach where Claude orchestrates data gathering
as needed during generation, rather than pre-collecting all data.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Optional

from app.models import db
from app.newsletter.interfaces import (
    NewsletterContext,
    NewsletterStatus,
    GenerationResult,
    SlackMessage,
    NewsItem,
    MemberSubmission,
    TrailConditionSummary,
    MessageVisibility,
    SubmissionStatus,
)
from app.newsletter.models import (
    Newsletter,
    NewsletterVersion,
    NewsletterSubmission,
    NewsletterDigest,
    NewsletterNewsItem,
    NewsletterPrompt,
)

logger = logging.getLogger(__name__)

# Import anthropic SDK
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logger.warning("Anthropic SDK not available - MCP tools will not work")


# =============================================================================
# Tool Definitions (JSON Schema format for Claude)
# =============================================================================

NEWSLETTER_TOOLS = [
    {
        "name": "collect_slack_messages",
        "description": (
            "Collect messages from Slack channels since a given timestamp. "
            "Returns messages from all public channels (where bot is member) "
            "and configured private channels. Respects privacy rules: "
            "public channels include permalinks and names, private channels "
            "are summarized without identifying information."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "since_days_ago": {
                    "type": "integer",
                    "description": "Number of days back to collect messages (default: 7)",
                    "default": 7
                },
                "max_messages": {
                    "type": "integer",
                    "description": "Maximum messages to return per channel (default: 50)",
                    "default": 50
                }
            },
            "required": []
        }
    },
    {
        "name": "get_member_submissions",
        "description": (
            "Get pending member submissions for the newsletter. "
            "These are content items submitted via /dispatch command or App Home. "
            "Returns submission type, content, and attribution preferences."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "newsletter_id": {
                    "type": "integer",
                    "description": "Optional newsletter ID to filter by"
                }
            },
            "required": []
        }
    },
    {
        "name": "scrape_ski_news",
        "description": (
            "Scrape local ski news from external sources: SkinnySkI, "
            "Loppet Foundation, and Three Rivers Parks. Returns recent "
            "articles with titles, summaries, and URLs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "since_days_ago": {
                    "type": "integer",
                    "description": "Number of days back to scrape news (default: 7)",
                    "default": 7
                },
                "max_articles_per_source": {
                    "type": "integer",
                    "description": "Maximum articles per source (default: 5)",
                    "default": 5
                }
            },
            "required": []
        }
    },
    {
        "name": "get_trail_conditions",
        "description": (
            "Get current trail conditions for monitored ski locations. "
            "Returns conditions for Theodore Wirth, Elm Creek, Hyland Lake, "
            "and Lebanon Hills including open status, quality, and grooming info."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_prior_newsletter",
        "description": (
            "Get the most recently published newsletter content for continuity. "
            "Use this to maintain running jokes, story arcs, and themes across weeks."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "max_length": {
                    "type": "integer",
                    "description": "Maximum characters to return (default: 2000)",
                    "default": 2000
                }
            },
            "required": []
        }
    },
    {
        "name": "save_newsletter_version",
        "description": (
            "Save the generated newsletter content as a new version. "
            "This persists the content to the database and increments the version number."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "newsletter_id": {
                    "type": "integer",
                    "description": "ID of the newsletter to save version for"
                },
                "content": {
                    "type": "string",
                    "description": "The generated newsletter content in Slack markdown"
                },
                "trigger": {
                    "type": "string",
                    "description": "What triggered this version: scheduled, manual, or feedback",
                    "enum": ["scheduled", "manual", "feedback"],
                    "default": "scheduled"
                }
            },
            "required": ["newsletter_id", "content"]
        }
    },
    {
        "name": "update_living_post",
        "description": (
            "Update the living newsletter post in Slack with new content. "
            "Creates the post if it doesn't exist, or updates it if it does. "
            "Also adds a version to the thread history."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "newsletter_id": {
                    "type": "integer",
                    "description": "ID of the newsletter to update post for"
                },
                "content": {
                    "type": "string",
                    "description": "The newsletter content to post"
                }
            },
            "required": ["newsletter_id", "content"]
        }
    }
]


# =============================================================================
# Tool Implementations
# =============================================================================

def tool_collect_slack_messages(
    since_days_ago: int = 7,
    max_messages: int = 50
) -> dict[str, Any]:
    """Collect Slack messages from configured channels.

    Args:
        since_days_ago: Days back to collect messages
        max_messages: Max messages per channel

    Returns:
        Dict with messages grouped by visibility and channel
    """
    logger.info(f"MCP Tool: collect_slack_messages(since_days={since_days_ago})")

    try:
        from app.newsletter.collector import collect_all_messages

        since = datetime.utcnow() - timedelta(days=since_days_ago)
        messages = collect_all_messages(since=since)

        # Group messages
        public_messages = []
        private_messages = []

        for msg in messages[:max_messages * 10]:  # Rough limit
            msg_data = {
                "channel": msg.channel_name,
                "user": msg.user_name,
                "text": msg.text[:500],  # Truncate long messages
                "reactions": msg.reaction_count,
                "replies": msg.reply_count,
                "posted_at": msg.posted_at.isoformat() if msg.posted_at else None,
            }

            if msg.visibility == MessageVisibility.PUBLIC:
                msg_data["permalink"] = msg.permalink
                public_messages.append(msg_data)
            else:
                private_messages.append(msg_data)

        return {
            "success": True,
            "public_messages": public_messages[:max_messages],
            "private_messages": private_messages[:max_messages // 2],
            "total_collected": len(messages),
            "privacy_note": (
                "Public messages can be quoted with attribution. "
                "Private messages should be summarized without names or links."
            )
        }

    except Exception as e:
        logger.error(f"collect_slack_messages failed: {e}")
        return {"success": False, "error": str(e)}


def tool_get_member_submissions(
    newsletter_id: Optional[int] = None
) -> dict[str, Any]:
    """Get pending member submissions.

    Args:
        newsletter_id: Optional newsletter ID to filter by

    Returns:
        Dict with list of pending submissions
    """
    logger.info(f"MCP Tool: get_member_submissions(newsletter_id={newsletter_id})")

    try:
        from app.newsletter.service import get_pending_submissions

        submissions = get_pending_submissions(newsletter_id)

        submission_list = []
        for sub in submissions:
            submission_list.append({
                "id": sub.id,
                "type": sub.submission_type.value,
                "content": sub.content,
                "display_name": sub.display_name if sub.permission_to_name else None,
                "can_attribute": sub.permission_to_name,
                "submitted_at": sub.submitted_at.isoformat() if sub.submitted_at else None,
            })

        return {
            "success": True,
            "submissions": submission_list,
            "count": len(submission_list),
            "attribution_note": (
                "Only include submitter names where can_attribute is true. "
                "Otherwise, refer to them as 'a member' or similar."
            )
        }

    except Exception as e:
        logger.error(f"get_member_submissions failed: {e}")
        return {"success": False, "error": str(e)}


def tool_scrape_ski_news(
    since_days_ago: int = 7,
    max_articles_per_source: int = 5
) -> dict[str, Any]:
    """Scrape ski news from external sources.

    Args:
        since_days_ago: Days back to scrape
        max_articles_per_source: Max articles per source

    Returns:
        Dict with news items by source
    """
    logger.info(f"MCP Tool: scrape_ski_news(since_days={since_days_ago})")

    try:
        from app.newsletter.news_scraper import scrape_all_news

        since = datetime.utcnow() - timedelta(days=since_days_ago)
        news_items = scrape_all_news(since=since)

        # Group by source
        by_source = {}
        for item in news_items:
            source = item.source.value
            if source not in by_source:
                by_source[source] = []

            if len(by_source[source]) < max_articles_per_source:
                by_source[source].append({
                    "title": item.title,
                    "summary": item.summary[:300] if item.summary else None,
                    "url": item.url,
                    "published_at": item.published_at.isoformat() if item.published_at else None,
                })

        return {
            "success": True,
            "news_by_source": by_source,
            "total_articles": len(news_items),
        }

    except Exception as e:
        logger.error(f"scrape_ski_news failed: {e}")
        return {"success": False, "error": str(e)}


def tool_get_trail_conditions() -> dict[str, Any]:
    """Get current trail conditions.

    Returns:
        Dict with conditions for each monitored location
    """
    logger.info("MCP Tool: get_trail_conditions()")

    try:
        from app.newsletter.service import get_trail_conditions

        conditions = get_trail_conditions()

        condition_list = []
        for trail in conditions:
            condition_list.append({
                "location": trail.location,
                "trails_open": trail.trails_open,
                "ski_quality": trail.ski_quality,
                "groomed": trail.groomed,
                "groomed_for": trail.groomed_for,
                "report_date": trail.report_date.isoformat() if trail.report_date else None,
                "notes": trail.notes[:200] if trail.notes else None,
            })

        return {
            "success": True,
            "conditions": condition_list,
            "count": len(condition_list),
        }

    except Exception as e:
        logger.error(f"get_trail_conditions failed: {e}")
        return {"success": False, "error": str(e)}


def tool_get_prior_newsletter(max_length: int = 2000) -> dict[str, Any]:
    """Get most recent published newsletter.

    Args:
        max_length: Max characters to return

    Returns:
        Dict with prior newsletter content
    """
    logger.info(f"MCP Tool: get_prior_newsletter(max_length={max_length})")

    try:
        from app.newsletter.service import get_prior_newsletter

        content = get_prior_newsletter()

        if content:
            truncated = len(content) > max_length
            return {
                "success": True,
                "has_prior": True,
                "content": content[:max_length],
                "truncated": truncated,
                "continuity_note": (
                    "Use this to maintain running themes, inside jokes, "
                    "and narrative continuity across newsletters."
                )
            }
        else:
            return {
                "success": True,
                "has_prior": False,
                "content": None,
            }

    except Exception as e:
        logger.error(f"get_prior_newsletter failed: {e}")
        return {"success": False, "error": str(e)}


def tool_save_newsletter_version(
    newsletter_id: int,
    content: str,
    trigger: str = "scheduled"
) -> dict[str, Any]:
    """Save newsletter content as a new version.

    Args:
        newsletter_id: Newsletter ID to save for
        content: Generated content
        trigger: What triggered this version

    Returns:
        Dict with version info
    """
    logger.info(f"MCP Tool: save_newsletter_version(newsletter_id={newsletter_id})")

    try:
        newsletter = Newsletter.query.get(newsletter_id)
        if not newsletter:
            return {"success": False, "error": f"Newsletter {newsletter_id} not found"}

        # Increment version
        newsletter.current_version = (newsletter.current_version or 0) + 1
        newsletter.current_content = content
        newsletter.updated_at = datetime.utcnow()

        # Create version record
        version = NewsletterVersion(
            newsletter_id=newsletter.id,
            version_number=newsletter.current_version,
            content=content,
            trigger_type=trigger,
            model_used="claude-opus-4-5-20251101",
            tokens_used=0,  # Set by caller if known
        )
        db.session.add(version)
        db.session.commit()

        logger.info(f"Saved newsletter version {newsletter.current_version}")

        return {
            "success": True,
            "version_number": newsletter.current_version,
            "newsletter_id": newsletter.id,
        }

    except Exception as e:
        logger.error(f"save_newsletter_version failed: {e}")
        db.session.rollback()
        return {"success": False, "error": str(e)}


def tool_update_living_post(
    newsletter_id: int,
    content: str
) -> dict[str, Any]:
    """Update the living Slack post.

    Args:
        newsletter_id: Newsletter ID
        content: Content to post

    Returns:
        Dict with post info
    """
    logger.info(f"MCP Tool: update_living_post(newsletter_id={newsletter_id})")

    try:
        from app.newsletter.slack_actions import (
            create_living_post,
            update_living_post,
            add_version_to_thread,
            is_dry_run,
        )

        newsletter = Newsletter.query.get(newsletter_id)
        if not newsletter:
            return {"success": False, "error": f"Newsletter {newsletter_id} not found"}

        if is_dry_run():
            logger.info("DRY RUN: Would update living post")
            return {
                "success": True,
                "dry_run": True,
                "message": "Dry run mode - no actual post made",
            }

        # Create or update the post
        if not newsletter.slack_main_message_ts:
            # Create new living post
            post_ref = create_living_post(newsletter, content)
            action = "created"
        else:
            # Update existing post
            post_ref = update_living_post(newsletter, content)
            action = "updated"

        # Add version to thread
        version = newsletter.versions.order_by(
            NewsletterVersion.version_number.desc()
        ).first()
        if version:
            add_version_to_thread(newsletter, version)

        return {
            "success": True,
            "action": action,
            "channel_id": post_ref.channel_id if post_ref else None,
            "message_ts": post_ref.message_ts if post_ref else None,
        }

    except Exception as e:
        logger.error(f"update_living_post failed: {e}")
        return {"success": False, "error": str(e)}


# =============================================================================
# Tool Dispatcher
# =============================================================================

TOOL_HANDLERS = {
    "collect_slack_messages": tool_collect_slack_messages,
    "get_member_submissions": tool_get_member_submissions,
    "scrape_ski_news": tool_scrape_ski_news,
    "get_trail_conditions": tool_get_trail_conditions,
    "get_prior_newsletter": tool_get_prior_newsletter,
    "save_newsletter_version": tool_save_newsletter_version,
    "update_living_post": tool_update_living_post,
}


def execute_tool(tool_name: str, tool_input: dict[str, Any]) -> str:
    """Execute a tool and return JSON result.

    Args:
        tool_name: Name of the tool to execute
        tool_input: Input parameters for the tool

    Returns:
        JSON string with tool result
    """
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    try:
        result = handler(**tool_input)
        return json.dumps(result, default=str)
    except Exception as e:
        logger.error(f"Tool {tool_name} execution failed: {e}")
        return json.dumps({"error": str(e)})


# =============================================================================
# Agentic Newsletter Generation
# =============================================================================

DEFAULT_MODEL = "claude-opus-4-5-20251101"
DEFAULT_MAX_TOKENS = 4000


def get_anthropic_client():
    """Get Anthropic client from environment."""
    if not ANTHROPIC_AVAILABLE:
        raise RuntimeError("Anthropic SDK not installed")

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    return anthropic.Anthropic(api_key=api_key)


def run_newsletter_agent(
    newsletter: Newsletter,
    is_final: bool = False,
    max_turns: int = 10
) -> GenerationResult:
    """Run the newsletter generation agent with MCP tools.

    This runs an agentic loop where Claude can call tools as needed
    to gather data and generate the newsletter.

    Args:
        newsletter: Newsletter to generate for
        is_final: Whether this is the Sunday final version
        max_turns: Maximum tool-use turns before stopping

    Returns:
        GenerationResult with generated content
    """
    if not ANTHROPIC_AVAILABLE:
        logger.error("Anthropic SDK not available")
        return GenerationResult(
            success=False,
            error="Anthropic SDK not installed"
        )

    logger.info("=" * 60)
    logger.info("MCP AGENT: Starting newsletter generation")
    logger.info(f"  Newsletter ID: {newsletter.id}")
    logger.info(f"  Final version: {is_final}")
    logger.info("=" * 60)

    # Load the appropriate prompt
    from app.newsletter.generator import get_newsletter_prompt
    prompt_name = 'final' if is_final else 'main'
    system_prompt = get_newsletter_prompt(prompt_name)

    # Build initial user message
    week_start = newsletter.week_start.strftime('%B %d')
    week_end = newsletter.week_end.strftime('%B %d, %Y')

    user_message = f"""Generate this week's TCSC Weekly Dispatch newsletter for the week of {week_start} - {week_end}.

You have access to tools to gather the content you need:
- Use collect_slack_messages to get recent Slack activity
- Use get_member_submissions to get content submitted by members
- Use scrape_ski_news to get local ski news
- Use get_trail_conditions to get current trail conditions
- Use get_prior_newsletter to maintain continuity with last week

After gathering the content you need, generate the newsletter using Slack-compatible markdown.

When you're satisfied with the newsletter content, use save_newsletter_version to persist it,
then use update_living_post to post/update it in Slack.

{"This is the FINAL version for Sunday publication. Make it polished and publication-ready." if is_final else ""}

Begin by collecting the content you need."""

    try:
        client = get_anthropic_client()

        messages = [{"role": "user", "content": user_message}]
        final_content = None
        total_tokens = 0

        for turn in range(max_turns):
            logger.info(f"  Turn {turn + 1}/{max_turns}")

            response = client.messages.create(
                model=DEFAULT_MODEL,
                max_tokens=DEFAULT_MAX_TOKENS,
                system=system_prompt,
                tools=NEWSLETTER_TOOLS,
                messages=messages,
            )

            total_tokens += response.usage.input_tokens + response.usage.output_tokens

            # Check stop reason
            if response.stop_reason == "end_turn":
                # Claude finished without calling tools
                for block in response.content:
                    if hasattr(block, 'text'):
                        final_content = block.text
                        break
                logger.info("  Agent completed (end_turn)")
                break

            elif response.stop_reason == "tool_use":
                # Process tool calls
                assistant_message = {"role": "assistant", "content": response.content}
                messages.append(assistant_message)

                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        logger.info(f"    Tool call: {block.name}")
                        result = execute_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })

                        # Check if this was a save that includes content
                        if block.name == "save_newsletter_version":
                            final_content = block.input.get("content")

                messages.append({"role": "user", "content": tool_results})

            else:
                logger.warning(f"  Unexpected stop_reason: {response.stop_reason}")
                break

        if not final_content:
            logger.error("  Agent did not produce newsletter content")
            return GenerationResult(
                success=False,
                error="Agent did not produce content"
            )

        logger.info(f"  Total tokens: {total_tokens}")
        logger.info(f"  Content length: {len(final_content)} chars")
        logger.info("=" * 60)

        return GenerationResult(
            success=True,
            content=final_content,
            version_number=newsletter.current_version or 1,
            model_used=DEFAULT_MODEL,
            tokens_used=total_tokens,
        )

    except Exception as e:
        logger.error(f"MCP Agent failed: {e}", exc_info=True)
        return GenerationResult(
            success=False,
            error=str(e)
        )


# =============================================================================
# Hybrid Generation (MCP with fallback to direct)
# =============================================================================

def generate_newsletter_with_mcp(
    newsletter: Newsletter,
    context: Optional[NewsletterContext] = None,
    is_final: bool = False,
    use_agent: bool = True
) -> GenerationResult:
    """Generate newsletter using MCP agent or direct approach.

    Args:
        newsletter: Newsletter to generate for
        context: Pre-collected context (used if agent fails)
        is_final: Whether this is the final version
        use_agent: Whether to try the agentic approach first

    Returns:
        GenerationResult with generated content
    """
    if use_agent and ANTHROPIC_AVAILABLE:
        try:
            result = run_newsletter_agent(newsletter, is_final=is_final)
            if result.success:
                return result
            logger.warning(f"MCP agent failed: {result.error}, falling back to direct")
        except Exception as e:
            logger.warning(f"MCP agent exception: {e}, falling back to direct")

    # Fallback to direct generation
    from app.newsletter.generator import generate_newsletter
    from app.newsletter.service import collect_newsletter_content

    if context is None:
        context = collect_newsletter_content(newsletter)

    return generate_newsletter(context, is_final=is_final)
