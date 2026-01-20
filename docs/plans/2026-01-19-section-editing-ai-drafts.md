# Section-by-Section Editing and AI Draft Generation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement per-section editing in Slack modals and update AI draft generation to produce section-specific content for the Monthly Dispatch.

**Architecture:** Each newsletter section gets its own "Edit" button in the living post that opens a modal with current content. AI drafts are generated per-section (not as one big newsletter), respecting the 2900-char Slack modal limit. Sections are stored in NewsletterSection model with status tracking.

**Tech Stack:** Flask/SQLAlchemy, Slack Bolt (Block Kit, modals), Claude Opus 4.5

---

## Task 1: Create Section Editor Module

**Files:**
- Create: `app/newsletter/section_editor.py`
- Test: `tests/newsletter/test_section_editor.py`

**Step 1: Write the failing test**

Create `tests/newsletter/test_section_editor.py`:

```python
"""Tests for section editor module."""

import pytest
from app.newsletter.section_editor import (
    build_section_edit_modal,
    get_section_for_editing,
    save_section_edit,
)
from app.newsletter.interfaces import SectionType, SectionStatus


def test_build_section_edit_modal():
    """Test building a section edit modal."""
    modal = build_section_edit_modal(
        section_type=SectionType.FROM_THE_BOARD.value,
        current_content="Test content here",
        newsletter_id=1,
        section_id=5
    )

    assert modal['type'] == 'modal'
    assert modal['callback_id'] == 'section_edit_submit'
    assert 'From the Board' in modal['title']['text']
    # Verify content is pre-filled
    content_block = None
    for block in modal['blocks']:
        if block.get('block_id') == 'content_block':
            content_block = block
            break
    assert content_block is not None
    assert content_block['element']['initial_value'] == 'Test content here'


def test_build_section_edit_modal_truncates_long_content():
    """Test that content over 2900 chars is truncated with warning."""
    long_content = "x" * 3500
    modal = build_section_edit_modal(
        section_type=SectionType.MONTH_IN_REVIEW.value,
        current_content=long_content,
        newsletter_id=1,
        section_id=5
    )

    # Find content block
    content_block = None
    for block in modal['blocks']:
        if block.get('block_id') == 'content_block':
            content_block = block
            break

    # Content should be truncated to 2900 chars
    initial_value = content_block['element']['initial_value']
    assert len(initial_value) <= 2900
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/newsletter/test_section_editor.py -v --tb=short`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.newsletter.section_editor'"

**Step 3: Write minimal implementation**

Create `app/newsletter/section_editor.py`:

```python
"""
Section-by-section editing for Monthly Dispatch newsletter.

Provides modal builders and handlers for editing individual newsletter
sections via Slack. Each AI-drafted section can be edited independently.
"""

import logging
from datetime import datetime
from typing import Optional

from app.models import db
from app.newsletter.models import Newsletter, NewsletterSection
from app.newsletter.interfaces import SectionType, SectionStatus

logger = logging.getLogger(__name__)

# Maximum content length for Slack modal text inputs
MAX_SECTION_CONTENT = 2900

# Section display names
SECTION_NAMES = {
    SectionType.OPENER.value: "Opener",
    SectionType.QOTM.value: "Question of the Month",
    SectionType.COACHES_CORNER.value: "Coaches Corner",
    SectionType.MEMBER_HEADS_UP.value: "Member Heads Up",
    SectionType.UPCOMING_EVENTS.value: "Upcoming Events",
    SectionType.MEMBER_HIGHLIGHT.value: "Member Highlight",
    SectionType.MONTH_IN_REVIEW.value: "Month in Review",
    SectionType.FROM_THE_BOARD.value: "From the Board",
    SectionType.CLOSER.value: "Closer",
    SectionType.PHOTO_GALLERY.value: "Photo Gallery",
}


def get_section_display_name(section_type: str) -> str:
    """Get human-readable name for section type."""
    return SECTION_NAMES.get(section_type, section_type.replace('_', ' ').title())


def build_section_edit_modal(
    section_type: str,
    current_content: str,
    newsletter_id: int,
    section_id: int,
    ai_draft: Optional[str] = None
) -> dict:
    """Build modal for editing a newsletter section.

    Args:
        section_type: The SectionType value (e.g., 'from_the_board')
        current_content: Current content to pre-fill
        newsletter_id: Newsletter ID for callback
        section_id: Section ID for callback
        ai_draft: Original AI draft (shown for reference if different)

    Returns:
        Slack modal view payload
    """
    section_name = get_section_display_name(section_type)

    # Truncate content if too long for modal
    display_content = current_content or ""
    if len(display_content) > MAX_SECTION_CONTENT:
        display_content = display_content[:MAX_SECTION_CONTENT]
        logger.warning(
            f"Section {section_type} content truncated from {len(current_content)} "
            f"to {MAX_SECTION_CONTENT} chars for modal"
        )

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":pencil2: *Editing: {section_name}*\n\nEdit the content below. Use Slack mrkdwn formatting: *bold*, _italic_, <url|link text>, :emoji:"
            }
        },
        {
            "type": "divider"
        },
        {
            "type": "input",
            "block_id": "content_block",
            "label": {
                "type": "plain_text",
                "text": "Content"
            },
            "element": {
                "type": "plain_text_input",
                "action_id": "section_content",
                "multiline": True,
                "initial_value": display_content,
                "max_length": MAX_SECTION_CONTENT,
                "placeholder": {
                    "type": "plain_text",
                    "text": f"Enter {section_name.lower()} content..."
                }
            }
        }
    ]

    # Show AI draft reference if different from current content
    if ai_draft and ai_draft != current_content:
        ai_preview = ai_draft[:500] + "..." if len(ai_draft) > 500 else ai_draft
        blocks.append({
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": f":robot_face: *Original AI Draft:*\n_{ai_preview}_"
            }]
        })

    return {
        "type": "modal",
        "callback_id": "section_edit_submit",
        "private_metadata": f"{newsletter_id}:{section_id}:{section_type}",
        "title": {
            "type": "plain_text",
            "text": f"Edit: {section_name}"[:24]  # Slack title limit
        },
        "submit": {
            "type": "plain_text",
            "text": "Save"
        },
        "close": {
            "type": "plain_text",
            "text": "Cancel"
        },
        "blocks": blocks
    }


def get_section_for_editing(newsletter_id: int, section_type: str) -> Optional[NewsletterSection]:
    """Get or create a section for editing.

    Args:
        newsletter_id: Newsletter ID
        section_type: Section type string

    Returns:
        NewsletterSection instance or None if newsletter not found
    """
    newsletter = Newsletter.query.get(newsletter_id)
    if not newsletter:
        logger.error(f"Newsletter {newsletter_id} not found")
        return None

    # Check for existing section
    section = NewsletterSection.query.filter_by(
        newsletter_id=newsletter_id,
        section_type=section_type
    ).first()

    if not section:
        # Create new section
        section = NewsletterSection(
            newsletter_id=newsletter_id,
            section_type=section_type,
            status=SectionStatus.AWAITING_CONTENT.value
        )
        db.session.add(section)
        db.session.flush()
        logger.info(f"Created new section {section_type} for newsletter {newsletter_id}")

    return section


def save_section_edit(
    section_id: int,
    new_content: str,
    editor_slack_uid: str
) -> dict:
    """Save edited section content.

    Args:
        section_id: NewsletterSection ID
        new_content: Updated content
        editor_slack_uid: Slack user ID of editor

    Returns:
        dict with success status and section info
    """
    section = NewsletterSection.query.get(section_id)
    if not section:
        return {'success': False, 'error': 'Section not found'}

    # Update section
    section.content = new_content
    section.edited_by = editor_slack_uid
    section.edited_at = datetime.utcnow()

    # Update status
    if section.status in [SectionStatus.AWAITING_CONTENT.value, SectionStatus.HAS_AI_DRAFT.value]:
        section.status = SectionStatus.HUMAN_EDITED.value

    db.session.commit()

    logger.info(
        f"Section {section.section_type} (id={section_id}) edited by {editor_slack_uid}"
    )

    return {
        'success': True,
        'section_id': section_id,
        'section_type': section.section_type,
        'status': section.status,
        'edited_by': editor_slack_uid
    }


def get_all_sections_for_newsletter(newsletter_id: int) -> list[NewsletterSection]:
    """Get all sections for a newsletter, ordered by section_order.

    Args:
        newsletter_id: Newsletter ID

    Returns:
        List of NewsletterSection instances
    """
    return NewsletterSection.query.filter_by(
        newsletter_id=newsletter_id
    ).order_by(NewsletterSection.section_order).all()


def initialize_sections_for_newsletter(newsletter_id: int) -> list[NewsletterSection]:
    """Create all sections for a newsletter based on config.

    Creates NewsletterSection records for each section type defined in
    the newsletter config, with appropriate initial status.

    Args:
        newsletter_id: Newsletter ID

    Returns:
        List of created NewsletterSection instances
    """
    import yaml
    from pathlib import Path

    config_path = Path(__file__).parent.parent.parent / 'config' / 'newsletter.yaml'

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Could not load newsletter config: {e}")
        return []

    sections_config = config.get('sections', [])
    created = []

    for i, section_cfg in enumerate(sections_config):
        section_id = section_cfg.get('id')
        if not section_id:
            continue

        # Check if section already exists
        existing = NewsletterSection.query.filter_by(
            newsletter_id=newsletter_id,
            section_type=section_id
        ).first()

        if existing:
            continue

        # Determine initial status based on whether AI-generated
        is_ai = section_cfg.get('ai_generated', False)
        initial_status = (
            SectionStatus.HAS_AI_DRAFT.value if is_ai
            else SectionStatus.AWAITING_CONTENT.value
        )

        section = NewsletterSection(
            newsletter_id=newsletter_id,
            section_type=section_id,
            section_order=i,
            status=initial_status
        )
        db.session.add(section)
        created.append(section)

    if created:
        db.session.commit()
        logger.info(f"Created {len(created)} sections for newsletter {newsletter_id}")

    return created
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/newsletter/test_section_editor.py -v --tb=short`
Expected: PASS

**Step 5: Commit**

```bash
git add app/newsletter/section_editor.py tests/newsletter/test_section_editor.py
git commit -m "feat(newsletter): add section editor module for per-section editing"
```

---

## Task 2: Add Section Edit Button Handler to Bolt App

**Files:**
- Modify: `app/slack/bolt_app.py`
- Test: Manual testing via Slack

**Step 1: Add block action handler for section edit buttons**

Add to `app/slack/bolt_app.py` after the existing action handlers:

```python
    # =========================================================================
    # Newsletter Section Editing
    # =========================================================================

    @bolt_app.action("section_edit")
    def handle_section_edit_button(ack, body, client, logger):
        """Handle click on section Edit button.

        Opens modal with current section content for editing.
        Button value format: "newsletter_id:section_id:section_type"
        """
        ack()

        try:
            value = body['actions'][0]['value']
            newsletter_id, section_id, section_type = value.split(':')
            newsletter_id = int(newsletter_id)
            section_id = int(section_id)
        except (KeyError, ValueError) as e:
            logger.error(f"Invalid section edit button value: {e}")
            return

        trigger_id = body.get('trigger_id')
        if not trigger_id:
            logger.error("No trigger_id for section edit")
            return

        with get_app_context():
            from app.newsletter.section_editor import (
                build_section_edit_modal,
                get_section_for_editing,
            )

            section = get_section_for_editing(newsletter_id, section_type)
            if not section:
                client.chat_postEphemeral(
                    channel=body['channel']['id'],
                    user=body['user']['id'],
                    text=":x: Could not find section to edit"
                )
                return

            modal = build_section_edit_modal(
                section_type=section.section_type,
                current_content=section.content or "",
                newsletter_id=newsletter_id,
                section_id=section.id,
                ai_draft=section.ai_draft
            )

            client.views_open(trigger_id=trigger_id, view=modal)

    @bolt_app.view("section_edit_submit")
    def handle_section_edit_submit(ack, body, client, view, logger):
        """Handle section edit modal submission.

        Saves the edited content and updates the living post.
        """
        ack()

        try:
            # Parse metadata
            metadata = view.get('private_metadata', '')
            newsletter_id, section_id, section_type = metadata.split(':')
            newsletter_id = int(newsletter_id)
            section_id = int(section_id)

            # Get submitted content
            values = view.get('state', {}).get('values', {})
            new_content = values.get('content_block', {}).get('section_content', {}).get('value', '')

            editor_uid = body['user']['id']

        except (KeyError, ValueError) as e:
            logger.error(f"Error parsing section edit submission: {e}")
            return

        with get_app_context():
            from app.newsletter.section_editor import save_section_edit
            from app.newsletter.models import Newsletter
            from app.newsletter.slack_actions import update_living_post

            # Save the edit
            result = save_section_edit(section_id, new_content, editor_uid)

            if not result.get('success'):
                logger.error(f"Failed to save section edit: {result.get('error')}")
                return

            # Notify user
            client.chat_postMessage(
                channel=editor_uid,
                text=f":white_check_mark: *{result['section_type'].replace('_', ' ').title()}* section updated!"
            )

            logger.info(f"Section {section_type} edited by {editor_uid}")
```

**Step 2: Verify handler is registered**

Run: `python -c "from app.slack.bolt_app import bolt_app; print('Handlers loaded')" 2>/dev/null || echo "OK - bolt_app may not load without tokens"`

**Step 3: Commit**

```bash
git add app/slack/bolt_app.py
git commit -m "feat(newsletter): add Bolt handlers for section editing"
```

---

## Task 3: Build Living Post with Section Edit Buttons

**Files:**
- Modify: `app/newsletter/slack_actions.py`
- Test: `tests/newsletter/test_slack_actions.py`

**Step 1: Add function to build section blocks with edit buttons**

Add to `app/newsletter/slack_actions.py`:

```python
def build_section_blocks_with_edit_buttons(
    newsletter: Newsletter,
    sections: list
) -> list[dict]:
    """Build Block Kit blocks for each section with edit buttons.

    Creates a compact representation of each section with:
    - Section header
    - Status indicator
    - Content preview (truncated)
    - Edit button (for AI-drafted sections)

    Args:
        newsletter: Newsletter model
        sections: List of NewsletterSection instances

    Returns:
        List of Block Kit blocks
    """
    from app.newsletter.section_editor import get_section_display_name
    from app.newsletter.interfaces import SectionStatus

    blocks = []

    # Header
    month_display = newsletter.month_year or "Current"
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": f":newspaper: Monthly Dispatch - {month_display}",
            "emoji": True
        }
    })

    # Status context
    status_emoji = {
        'building': ':hammer_and_wrench:',
        'ready_for_review': ':eyes:',
        'approved': ':white_check_mark:',
        'published': ':mega:',
    }.get(newsletter.status, ':newspaper:')

    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": f"{status_emoji} *Status:* {newsletter.status.replace('_', ' ').title()}"
        }]
    })

    blocks.append({"type": "divider"})

    # Section status emoji mapping
    status_emoji_map = {
        SectionStatus.AWAITING_CONTENT.value: ':hourglass:',
        SectionStatus.HAS_AI_DRAFT.value: ':robot_face:',
        SectionStatus.HUMAN_EDITED.value: ':pencil2:',
        SectionStatus.FINAL.value: ':white_check_mark:',
    }

    for section in sections:
        section_name = get_section_display_name(section.section_type)
        status_emoji = status_emoji_map.get(section.status, ':grey_question:')

        # Content preview
        content = section.content or section.ai_draft or "_No content yet_"
        preview = content[:150] + "..." if len(content) > 150 else content

        # Section header with status
        section_block = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{status_emoji} {section_name}*\n{preview}"
            }
        }

        # Add edit button for editable sections
        if section.status in [
            SectionStatus.HAS_AI_DRAFT.value,
            SectionStatus.HUMAN_EDITED.value,
            SectionStatus.AWAITING_CONTENT.value
        ]:
            section_block["accessory"] = {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Edit",
                    "emoji": True
                },
                "action_id": "section_edit",
                "value": f"{newsletter.id}:{section.id}:{section.section_type}"
            }

        blocks.append(section_block)

    blocks.append({"type": "divider"})

    return blocks
```

**Step 2: Update create_living_post to use section blocks**

Modify `create_living_post` in `app/newsletter/slack_actions.py` to optionally use section-based layout:

```python
def create_living_post_with_sections(
    newsletter: Newsletter
) -> SlackPostReference:
    """Create living post with section-by-section layout.

    Creates a compact overview with edit buttons for each section.
    Used for the monthly dispatch workflow.

    Args:
        newsletter: Newsletter model

    Returns:
        SlackPostReference with channel_id and message_ts
    """
    from app.newsletter.section_editor import (
        get_all_sections_for_newsletter,
        initialize_sections_for_newsletter,
    )

    channel_id = get_living_post_channel()
    if not channel_id:
        raise ValueError("Could not find living post channel")

    # Ensure sections exist
    sections = get_all_sections_for_newsletter(newsletter.id)
    if not sections:
        sections = initialize_sections_for_newsletter(newsletter.id)

    dry_run = is_dry_run()

    if dry_run:
        logger.info(
            f"[DRY RUN] Would create section-based living post for newsletter #{newsletter.id}"
        )
        return SlackPostReference(
            channel_id=channel_id,
            message_ts="dry_run_ts"
        )

    client = get_slack_client()

    # Build section blocks
    blocks = build_section_blocks_with_edit_buttons(newsletter, sections)

    # Add review buttons if ready
    if newsletter.status == NewsletterStatus.READY_FOR_REVIEW.value:
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Approve & Publish", "emoji": True},
                    "style": "primary",
                    "action_id": "newsletter_approve",
                    "value": str(newsletter.id)
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Request Changes", "emoji": True},
                    "action_id": "newsletter_request_changes",
                    "value": str(newsletter.id)
                }
            ]
        })

    fallback_text = f"Monthly Dispatch - {newsletter.month_year or 'Current'}"

    try:
        response = client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text=fallback_text,
            unfurl_links=False,
            unfurl_media=False
        )

        message_ts = response.get('ts')

        # Save references
        newsletter.slack_channel_id = channel_id
        newsletter.slack_main_message_ts = message_ts
        db.session.commit()

        logger.info(f"Created section-based living post for newsletter #{newsletter.id}")

        return SlackPostReference(
            channel_id=channel_id,
            message_ts=message_ts
        )

    except SlackApiError as e:
        logger.error(f"Error creating section-based living post: {e}")
        raise
```

**Step 3: Commit**

```bash
git add app/newsletter/slack_actions.py
git commit -m "feat(newsletter): add section-based living post with edit buttons"
```

---

## Task 4: Create Monthly AI Draft Generator

**Files:**
- Create: `app/newsletter/monthly_generator.py`
- Create: `config/prompts/newsletter_monthly.md`
- Test: `tests/newsletter/test_monthly_generator.py`

**Step 1: Create the monthly generation prompt**

Create `config/prompts/newsletter_monthly.md`:

```markdown
# TCSC Monthly Dispatch Section Generation

You are generating draft content for specific sections of the Twin Cities Ski Club's Monthly Dispatch newsletter. Generate ONLY the requested section.

## Output Format

Return ONLY a valid JSON object with the section content:

```json
{
  "section_type": "from_the_board",
  "content": "The actual section content here...",
  "char_count": 450
}
```

## Section Guidelines

### from_the_board
- Summarize board/leadership discussions from the provided messages
- Focus on decisions, announcements, and upcoming plans
- Keep formal but friendly tone
- 200-400 words

### member_heads_up
- Compile event reminders and announcements
- Include practice schedule changes, registration deadlines
- Bullet-point style for scannability
- 150-300 words

### upcoming_events
- List races and events in the next 4-6 weeks
- Include date, location, registration links
- Format: "**Event Name** - Date, Location"
- 150-250 words

### month_in_review
- Highlight memorable moments from Slack activity
- Include funny quotes, achievements, community moments
- Can quote public channels (with names and links)
- Summarize private channel themes (no names)
- 300-500 words

### member_highlight
- Compose member's answers into engaging narrative prose
- Keep their voice but polish for readability
- Include fun details and personality
- 200-350 words

## Formatting Rules

- Use Slack mrkdwn: *bold*, _italic_, <url|text> links
- Use Slack emoji codes: :ski: :snowflake: :wave:
- NO markdown headers (#, ##)
- Keep under 2900 characters (Slack modal limit)
- Focus on quality over quantity

## Content Priority

1. Safety-related announcements
2. Time-sensitive events/deadlines
3. Community achievements
4. Fun/engaging moments
```

**Step 2: Create the monthly generator module**

Create `app/newsletter/monthly_generator.py`:

```python
"""
AI draft generation for Monthly Dispatch sections.

Generates section-specific content using Claude, respecting the
2900-char Slack modal limit for each section.
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

from app.newsletter.interfaces import SectionType, SectionStatus
from app.newsletter.models import Newsletter, NewsletterSection, db

logger = logging.getLogger(__name__)

# Maximum content length for Slack modal
MAX_SECTION_CHARS = 2900

# Sections that get AI drafts
AI_DRAFTED_SECTIONS = [
    SectionType.FROM_THE_BOARD.value,
    SectionType.MEMBER_HEADS_UP.value,
    SectionType.UPCOMING_EVENTS.value,
    SectionType.MONTH_IN_REVIEW.value,
]


def _load_monthly_prompt() -> str:
    """Load the monthly generation prompt from file."""
    prompt_path = Path(__file__).parent.parent.parent / 'config' / 'prompts' / 'newsletter_monthly.md'

    if prompt_path.exists():
        return prompt_path.read_text()

    logger.warning("Monthly prompt not found, using default")
    return "Generate newsletter section content."


def _load_generation_config() -> dict:
    """Load generation config from newsletter.yaml."""
    config_path = Path(__file__).parent.parent.parent / 'config' / 'newsletter.yaml'

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
        return config.get('generation', {})
    except Exception as e:
        logger.warning(f"Could not load generation config: {e}")
        return {}


def build_section_context(
    newsletter: Newsletter,
    section_type: str,
    slack_messages: list = None,
    leadership_messages: list = None,
    events: list = None,
    member_highlight_answers: dict = None
) -> str:
    """Build context for generating a specific section.

    Args:
        newsletter: Newsletter model
        section_type: Which section to generate
        slack_messages: Public/private Slack messages for month
        leadership_messages: Messages from leadership-* channels
        events: Upcoming events data
        member_highlight_answers: Raw answers from highlighted member

    Returns:
        Formatted context string for Claude
    """
    lines = []

    lines.append(f"=== SECTION TO GENERATE ===")
    lines.append(f"Section: {section_type}")
    lines.append(f"Month: {newsletter.month_year}")
    lines.append(f"Max characters: {MAX_SECTION_CHARS}")
    lines.append("")

    if section_type == SectionType.FROM_THE_BOARD.value and leadership_messages:
        lines.append("=== LEADERSHIP CHANNEL MESSAGES ===")
        for msg in leadership_messages[:20]:
            lines.append(f"- {msg.get('channel', 'leadership')}: {msg.get('text', '')[:200]}")
        lines.append("")

    if section_type == SectionType.MEMBER_HEADS_UP.value and slack_messages:
        # Filter for announcements/events
        lines.append("=== ANNOUNCEMENTS AND EVENTS ===")
        for msg in slack_messages[:15]:
            if any(kw in msg.get('text', '').lower() for kw in ['reminder', 'event', 'registration', 'deadline', 'practice']):
                lines.append(f"- #{msg.get('channel', '')}: {msg.get('text', '')[:150]}")
        lines.append("")

    if section_type == SectionType.UPCOMING_EVENTS.value and events:
        lines.append("=== UPCOMING EVENTS ===")
        for event in events[:10]:
            lines.append(f"- {event.get('name', 'Event')}: {event.get('date', '')} at {event.get('location', '')}")
            if event.get('url'):
                lines.append(f"  Link: {event.get('url')}")
        lines.append("")

    if section_type == SectionType.MONTH_IN_REVIEW.value and slack_messages:
        lines.append("=== SLACK HIGHLIGHTS ===")
        # Sort by engagement
        sorted_msgs = sorted(
            slack_messages,
            key=lambda m: m.get('reactions', 0) + m.get('replies', 0) * 2,
            reverse=True
        )
        for msg in sorted_msgs[:15]:
            visibility = msg.get('visibility', 'public')
            if visibility == 'public':
                lines.append(f"- [PUBLIC] #{msg.get('channel', '')}: {msg.get('user', '')} said: {msg.get('text', '')[:150]}")
                if msg.get('permalink'):
                    lines.append(f"  Link: {msg.get('permalink')}")
            else:
                lines.append(f"- [PRIVATE] #{msg.get('channel', '')}: {msg.get('text', '')[:100]}...")
        lines.append("")

    if section_type == SectionType.MEMBER_HIGHLIGHT.value and member_highlight_answers:
        lines.append("=== MEMBER HIGHLIGHT ANSWERS ===")
        for question, answer in member_highlight_answers.items():
            lines.append(f"Q: {question}")
            lines.append(f"A: {answer}")
            lines.append("")

    return "\n".join(lines)


def generate_section_draft(
    newsletter: Newsletter,
    section_type: str,
    context_data: dict
) -> dict:
    """Generate AI draft for a single section.

    Args:
        newsletter: Newsletter model
        section_type: Which section to generate
        context_data: Dict with relevant data for this section

    Returns:
        dict with 'success', 'content', 'error' keys
    """
    try:
        import anthropic
    except ImportError:
        return {
            'success': False,
            'error': 'Anthropic SDK not installed'
        }

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return {
            'success': False,
            'error': 'ANTHROPIC_API_KEY not set'
        }

    # Build context
    context = build_section_context(
        newsletter=newsletter,
        section_type=section_type,
        slack_messages=context_data.get('slack_messages'),
        leadership_messages=context_data.get('leadership_messages'),
        events=context_data.get('events'),
        member_highlight_answers=context_data.get('highlight_answers')
    )

    # Load prompt and config
    system_prompt = _load_monthly_prompt()
    gen_config = _load_generation_config()

    model = gen_config.get('model', 'claude-opus-4-5-20251101')
    max_tokens = min(gen_config.get('max_tokens', 4000), 4000)  # Cap for section

    user_message = f"""Generate the '{section_type}' section for the Monthly Dispatch.

{context}

Remember:
- Maximum {MAX_SECTION_CHARS} characters
- Use Slack mrkdwn formatting
- Return ONLY valid JSON with 'section_type', 'content', and 'char_count' keys
"""

    logger.info(f"Generating AI draft for section: {section_type}")
    start_time = time.time()

    try:
        client = anthropic.Anthropic(api_key=api_key)

        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=0.7,
            messages=[
                {"role": "user", "content": f"{system_prompt}\n\n{user_message}"}
            ]
        )

        elapsed = time.time() - start_time

        # Extract text
        raw_content = ""
        for block in response.content:
            if hasattr(block, 'text'):
                raw_content = block.text
                break

        # Parse JSON
        json_match = re.search(r'\{[\s\S]*\}', raw_content)
        if json_match:
            try:
                parsed = json.loads(json_match.group(0))
                content = parsed.get('content', raw_content)
            except json.JSONDecodeError:
                content = raw_content
        else:
            content = raw_content

        # Ensure under limit
        if len(content) > MAX_SECTION_CHARS:
            content = content[:MAX_SECTION_CHARS - 3] + "..."
            logger.warning(f"Section {section_type} truncated to {MAX_SECTION_CHARS} chars")

        logger.info(f"Generated {section_type} in {elapsed:.2f}s ({len(content)} chars)")

        return {
            'success': True,
            'content': content,
            'section_type': section_type,
            'generation_time_ms': int(elapsed * 1000)
        }

    except Exception as e:
        logger.error(f"Error generating section {section_type}: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def generate_all_ai_sections(
    newsletter: Newsletter,
    context_data: dict
) -> dict:
    """Generate AI drafts for all AI-assisted sections.

    Args:
        newsletter: Newsletter model
        context_data: Dict with data for all sections

    Returns:
        dict with 'success', 'sections' (list of results), 'errors' keys
    """
    results = {
        'success': True,
        'sections': [],
        'errors': []
    }

    for section_type in AI_DRAFTED_SECTIONS:
        result = generate_section_draft(newsletter, section_type, context_data)

        if result.get('success'):
            # Save to database
            section = NewsletterSection.query.filter_by(
                newsletter_id=newsletter.id,
                section_type=section_type
            ).first()

            if not section:
                section = NewsletterSection(
                    newsletter_id=newsletter.id,
                    section_type=section_type,
                    section_order=AI_DRAFTED_SECTIONS.index(section_type)
                )
                db.session.add(section)

            section.ai_draft = result['content']
            section.content = result['content']  # Start with AI draft
            section.status = SectionStatus.HAS_AI_DRAFT.value

            results['sections'].append({
                'section_type': section_type,
                'success': True,
                'char_count': len(result['content'])
            })
        else:
            results['errors'].append({
                'section_type': section_type,
                'error': result.get('error')
            })

    db.session.commit()

    if results['errors']:
        results['success'] = False

    return results
```

**Step 3: Write test file**

Create `tests/newsletter/test_monthly_generator.py`:

```python
"""Tests for monthly AI draft generator."""

import pytest
from unittest.mock import patch, MagicMock

from app.newsletter.monthly_generator import (
    build_section_context,
    MAX_SECTION_CHARS,
    AI_DRAFTED_SECTIONS,
)
from app.newsletter.interfaces import SectionType


def test_build_section_context_from_the_board():
    """Test context building for From the Board section."""
    mock_newsletter = MagicMock()
    mock_newsletter.month_year = "2026-01"

    leadership_msgs = [
        {'channel': 'leadership-general', 'text': 'Board meeting notes...'},
        {'channel': 'leadership-events', 'text': 'Planning spring trip...'},
    ]

    context = build_section_context(
        newsletter=mock_newsletter,
        section_type=SectionType.FROM_THE_BOARD.value,
        leadership_messages=leadership_msgs
    )

    assert 'from_the_board' in context
    assert '2026-01' in context
    assert 'Board meeting notes' in context


def test_build_section_context_month_in_review():
    """Test context building for Month in Review section."""
    mock_newsletter = MagicMock()
    mock_newsletter.month_year = "2026-01"

    slack_msgs = [
        {'channel': 'chat', 'user': 'Alice', 'text': 'Great ski day!', 'reactions': 5, 'visibility': 'public'},
        {'channel': 'coord-private', 'text': 'Planning discussion', 'reactions': 2, 'visibility': 'private'},
    ]

    context = build_section_context(
        newsletter=mock_newsletter,
        section_type=SectionType.MONTH_IN_REVIEW.value,
        slack_messages=slack_msgs
    )

    assert 'month_in_review' in context
    assert '[PUBLIC]' in context
    assert 'Alice' in context
    assert '[PRIVATE]' in context


def test_ai_drafted_sections_list():
    """Test that AI drafted sections are defined correctly."""
    assert SectionType.FROM_THE_BOARD.value in AI_DRAFTED_SECTIONS
    assert SectionType.MONTH_IN_REVIEW.value in AI_DRAFTED_SECTIONS
    assert SectionType.OPENER.value not in AI_DRAFTED_SECTIONS  # Human-written
    assert SectionType.CLOSER.value not in AI_DRAFTED_SECTIONS  # Human-written
```

**Step 4: Run tests**

Run: `pytest tests/newsletter/test_monthly_generator.py -v --tb=short`
Expected: PASS

**Step 5: Commit**

```bash
git add app/newsletter/monthly_generator.py config/prompts/newsletter_monthly.md tests/newsletter/test_monthly_generator.py
git commit -m "feat(newsletter): add monthly AI draft generator for sections"
```

---

## Task 5: Integrate Monthly Generator into Service

**Files:**
- Modify: `app/newsletter/service.py`
- Test: Manual testing

**Step 1: Add generate_ai_drafts function to service.py**

Add to `app/newsletter/service.py`:

```python
def generate_ai_drafts(newsletter_id: int) -> dict:
    """Generate AI drafts for all AI-assisted sections.

    Called on day 12 of the month to generate initial drafts
    for editor review.

    Args:
        newsletter_id: Newsletter ID

    Returns:
        dict with 'success', 'sections', 'errors' keys
    """
    from app.newsletter.monthly_generator import generate_all_ai_sections
    from app.newsletter.collector import collect_slack_messages

    newsletter = Newsletter.query.get(newsletter_id)
    if not newsletter:
        return {'success': False, 'error': 'Newsletter not found'}

    logger.info(f"Generating AI drafts for newsletter {newsletter_id}")

    # Collect context data
    context_data = {}

    try:
        # Get Slack messages from the month
        if newsletter.period_start and newsletter.period_end:
            messages = collect_slack_messages(
                start_date=newsletter.period_start,
                end_date=newsletter.period_end
            )
            context_data['slack_messages'] = [
                {
                    'channel': m.channel_name,
                    'user': m.user_name,
                    'text': m.text,
                    'reactions': m.reaction_count,
                    'replies': m.reply_count,
                    'visibility': m.visibility.value if hasattr(m.visibility, 'value') else m.visibility,
                    'permalink': m.permalink
                }
                for m in messages
            ]

        # Get leadership channel messages (leadership-* pattern)
        # This would need additional collector logic for leadership channels
        context_data['leadership_messages'] = []  # Placeholder

        # Get events from calendar/scrapers
        context_data['events'] = []  # Placeholder for events module

        # Get member highlight answers if applicable
        if newsletter.highlight and newsletter.highlight.raw_answers:
            context_data['highlight_answers'] = newsletter.highlight.raw_answers

    except Exception as e:
        logger.error(f"Error collecting context data: {e}")
        context_data['slack_messages'] = []

    # Generate drafts
    result = generate_all_ai_sections(newsletter, context_data)

    return result
```

**Step 2: Verify import works**

Run: `python -c "from app.newsletter.service import generate_ai_drafts; print('OK')"`
Expected: OK (or import error if running without app context)

**Step 3: Commit**

```bash
git add app/newsletter/service.py
git commit -m "feat(newsletter): integrate monthly AI draft generator into service"
```

---

## Task 6: Update Newsletter Module Exports

**Files:**
- Modify: `app/newsletter/__init__.py`

**Step 1: Add new exports**

Add to `app/newsletter/__init__.py`:

```python
# Section editor
from app.newsletter.section_editor import (
    build_section_edit_modal,
    get_section_for_editing,
    save_section_edit,
    get_all_sections_for_newsletter,
    initialize_sections_for_newsletter,
    get_section_display_name,
)

# Monthly generator
from app.newsletter.monthly_generator import (
    generate_section_draft,
    generate_all_ai_sections,
    build_section_context,
    AI_DRAFTED_SECTIONS,
)
```

And update `__all__`:

```python
__all__ = [
    # ... existing exports ...

    # Section editor
    'build_section_edit_modal',
    'get_section_for_editing',
    'save_section_edit',
    'get_all_sections_for_newsletter',
    'initialize_sections_for_newsletter',
    'get_section_display_name',

    # Monthly generator
    'generate_section_draft',
    'generate_all_ai_sections',
    'build_section_context',
    'AI_DRAFTED_SECTIONS',
]
```

**Step 2: Verify exports**

Run: `python -c "from app.newsletter import build_section_edit_modal, generate_section_draft; print('Exports OK')"`

**Step 3: Commit**

```bash
git add app/newsletter/__init__.py
git commit -m "feat(newsletter): export section editor and monthly generator"
```

---

## Task 7: Update Orchestrator to Use AI Drafts

**Files:**
- Modify: `app/newsletter/service.py` (run_monthly_orchestrator)

**Step 1: Update day 12 logic in run_monthly_orchestrator**

Find the day 12 section in `run_monthly_orchestrator` and update:

```python
    elif day_of_month == 12:
        # Generate AI drafts for AI-assisted sections
        result['actions'].append({
            'action': 'start_day_12_ai_drafts',
            'success': True,
            'detail': 'Starting AI draft generation'
        })

        try:
            ai_result = generate_ai_drafts(newsletter.id)
            result['actions'].append({
                'action': 'generate_ai_drafts',
                'success': ai_result.get('success', False),
                'detail': f"Generated {len(ai_result.get('sections', []))} sections"
            })
            if ai_result.get('errors'):
                result['errors'].extend([
                    f"AI draft error: {e.get('section_type')}: {e.get('error')}"
                    for e in ai_result['errors']
                ])
        except Exception as e:
            logger.error(f"AI draft generation failed: {e}", exc_info=True)
            result['errors'].append(f"AI draft generation error: {e}")
            result['actions'].append({
                'action': 'generate_ai_drafts',
                'success': False,
                'detail': str(e)
            })

        # Create/update living post with sections
        try:
            from app.newsletter.slack_actions import create_living_post_with_sections
            post_ref = create_living_post_with_sections(newsletter)
            result['actions'].append({
                'action': 'create_living_post_with_sections',
                'success': True,
                'detail': f"message_ts={post_ref.message_ts if post_ref else 'None'}"
            })
        except Exception as e:
            logger.error(f"Living post creation failed: {e}", exc_info=True)
            result['errors'].append(f"Living post error: {e}")
```

**Step 2: Verify the function runs**

Run: `python -c "from app.newsletter.service import run_monthly_orchestrator; print('OK')"`

**Step 3: Commit**

```bash
git add app/newsletter/service.py
git commit -m "feat(newsletter): update orchestrator to generate AI drafts on day 12"
```

---

## Verification Plan

1. **Unit Tests**
   - Section editor modal building
   - Section context building for each type
   - Content truncation to 2900 chars

2. **Integration Tests**
   - Create newsletter with sections
   - Generate AI drafts for sections
   - Save section edits

3. **Manual Testing**
   - Post living post with section edit buttons
   - Click edit button, verify modal opens
   - Edit content, save, verify update
   - Test AI draft generation (requires ANTHROPIC_API_KEY)

---

## Summary

This plan implements:
1. **Section Editor Module** (`section_editor.py`) - Modal builders and save logic
2. **Bolt Handlers** - Action handlers for edit buttons and modal submissions
3. **Living Post with Sections** - Block Kit layout with edit buttons per section
4. **Monthly AI Generator** (`monthly_generator.py`) - Per-section AI draft generation
5. **Service Integration** - Connect generator to orchestrator

The key architectural decisions:
- Each section stored in `NewsletterSection` model with status tracking
- Edit buttons use action_id `section_edit` with value `newsletter_id:section_id:section_type`
- AI drafts generated per-section (not monolithic) respecting 2900-char limit
- Living post shows compact overview with status indicators and edit buttons
