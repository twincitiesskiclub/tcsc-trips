"""
Block Kit template builder for newsletter.

Transforms structured content dict into Slack Block Kit blocks
with consistent formatting. This ensures the newsletter looks
the same every week regardless of content variations.
"""

import logging
from typing import Optional

from app.newsletter.interfaces import NewsletterStatus

logger = logging.getLogger(__name__)


def build_newsletter_blocks(
    content: dict,
    version_number: int,
    status: str,
    include_review_buttons: bool = False,
    newsletter_id: Optional[int] = None
) -> list[dict]:
    """Build newsletter Block Kit from structured content.

    Args:
        content: Dict with newsletter fields (week_dates, opening_hook, etc.)
        version_number: Current version number
        status: Newsletter status string
        include_review_buttons: Whether to add Approve/Request Changes buttons
        newsletter_id: Newsletter ID for button values

    Returns:
        List of Block Kit block dicts
    """
    blocks = []

    # Status emoji mapping
    status_emoji = {
        NewsletterStatus.BUILDING.value: ':hammer_and_wrench:',
        NewsletterStatus.READY_FOR_REVIEW.value: ':eyes:',
        NewsletterStatus.APPROVED.value: ':white_check_mark:',
        NewsletterStatus.PUBLISHED.value: ':mega:',
    }.get(status, ':newspaper:')

    # ===== HEADER =====
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": f"{status_emoji} TCSC Weekly Dispatch",
            "emoji": True
        }
    })

    # Week dates + version context
    week_dates = content.get('week_dates', 'This Week')
    status_text = _get_status_text(status)
    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": f"*{week_dates}* | v{version_number} | {status_text}"
        }]
    })

    blocks.append({"type": "divider"})

    # ===== OPENING HOOK =====
    if content.get('opening_hook'):
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": content['opening_hook']}
        })
        blocks.append({"type": "divider"})

    # ===== WEEK IN REVIEW =====
    week_items = content.get('week_in_review', [])
    if week_items:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*:speech_balloon: Week in Review*"}
        })
        # Combine items into bullet list, splitting if too long
        items_text = "\n".join(f"• {item}" for item in week_items)
        blocks.extend(_split_text_to_sections(items_text))
        blocks.append({"type": "divider"})

    # ===== TRAIL CONDITIONS =====
    trails = content.get('trail_conditions', [])
    if trails:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*:ski: Trail Conditions*"}
        })
        for trail in trails:
            loc = trail.get('location', 'Unknown')
            trail_status = trail.get('status', '')
            quality = trail.get('quality', '')
            notes = trail.get('notes', '')

            status_quality = f"{trail_status} | {quality}" if trail_status and quality else trail_status or quality

            blocks.append({
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*{loc}*\n{notes}" if notes else f"*{loc}*"},
                    {"type": "mrkdwn", "text": status_quality}
                ]
            })
        blocks.append({"type": "divider"})

    # ===== LOCAL NEWS =====
    news = content.get('local_news', [])
    if news:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*:newspaper: Local Ski News*"}
        })
        news_items = []
        for item in news:
            title = item.get('title', '')
            link = item.get('link', '')
            summary = item.get('summary', '')
            if link:
                news_items.append(f"• <{link}|{title}>" + (f" - {summary}" if summary else ""))
            else:
                news_items.append(f"• *{title}*" + (f" - {summary}" if summary else ""))
        news_text = "\n".join(news_items)
        blocks.extend(_split_text_to_sections(news_text))
        blocks.append({"type": "divider"})

    # ===== MEMBER SUBMISSIONS =====
    submissions = content.get('member_submissions', [])
    if submissions:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*:raised_hands: Member Submissions*"}
        })
        for sub in submissions:
            sub_type = sub.get('type', 'content')
            emoji = {
                'spotlight': ':star:',
                'event': ':calendar:',
                'announcement': ':mega:',
                'content': ':pencil:'
            }.get(sub_type, ':pencil:')
            text = sub.get('content', '')
            attr = sub.get('attribution', 'Anonymous')
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"{emoji} {text}\n_— {attr}_"}
            })
        blocks.append({"type": "divider"})

    # ===== LOOKING AHEAD =====
    ahead = content.get('looking_ahead', [])
    if ahead:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*:calendar: Looking Ahead*"}
        })
        items_text = "\n".join(f"• {item}" for item in ahead)
        blocks.extend(_split_text_to_sections(items_text))
        blocks.append({"type": "divider"})

    # ===== CLOSING =====
    if content.get('closing'):
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": content['closing']}
        })

    # ===== REVIEW BUTTONS =====
    if include_review_buttons and newsletter_id:
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Approve & Publish", "emoji": True},
                    "style": "primary",
                    "action_id": "newsletter_approve",
                    "value": str(newsletter_id)
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Request Changes", "emoji": True},
                    "action_id": "newsletter_request_changes",
                    "value": str(newsletter_id)
                }
            ]
        })

    logger.info(f"Built {len(blocks)} Block Kit blocks for newsletter")
    return blocks


def _get_status_text(status: str) -> str:
    """Get human-readable status text."""
    return {
        NewsletterStatus.BUILDING.value: 'Building',
        NewsletterStatus.READY_FOR_REVIEW.value: 'Ready for Review',
        NewsletterStatus.APPROVED.value: 'Approved',
        NewsletterStatus.PUBLISHED.value: 'Published',
    }.get(status, status)


def _split_text_to_sections(text: str, max_length: int = 2900) -> list[dict]:
    """Split long text into multiple section blocks.

    Slack has a 3000 char limit per text block. This splits at
    line boundaries to avoid breaking mid-sentence.

    Args:
        text: Text to split
        max_length: Maximum chars per section (default 2900 for safety margin)

    Returns:
        List of section block dicts
    """
    if len(text) <= max_length:
        return [{
            "type": "section",
            "text": {"type": "mrkdwn", "text": text}
        }]

    sections = []
    lines = text.split('\n')
    current_chunk = ""

    for line in lines:
        if len(current_chunk) + len(line) + 1 <= max_length:
            if current_chunk:
                current_chunk += '\n'
            current_chunk += line
        else:
            if current_chunk:
                sections.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": current_chunk}
                })
            current_chunk = line

    if current_chunk:
        sections.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": current_chunk}
        })

    return sections


def get_fallback_text(content: dict) -> str:
    """Generate plain text fallback for notifications.

    Used for clients/integrations that don't support Block Kit.

    Args:
        content: Newsletter content dict

    Returns:
        Plain text summary
    """
    week = content.get('week_dates', 'This Week')
    hook = content.get('opening_hook', '')[:200]
    return f"TCSC Weekly Dispatch - {week}\n\n{hook}..."


def build_version_thread_blocks(
    version_number: int,
    trigger: str,
    content_preview: str = ""
) -> list[dict]:
    """Build Block Kit blocks for version history thread reply.

    Args:
        version_number: Version number
        trigger: What triggered this version (scheduled, manual, submission)
        content_preview: Optional short preview of content

    Returns:
        List of Block Kit block dicts
    """
    trigger_emoji = {
        'scheduled': ':clock8:',
        'manual': ':hand:',
        'submission': ':inbox_tray:',
        'feedback': ':speech_balloon:',
    }.get(trigger, ':memo:')

    blocks = [{
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": f"{trigger_emoji} *Version {version_number}* | Trigger: {trigger}"
        }]
    }]

    if content_preview:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"_{content_preview[:300]}..._" if len(content_preview) > 300 else f"_{content_preview}_"}
        })

    return blocks
