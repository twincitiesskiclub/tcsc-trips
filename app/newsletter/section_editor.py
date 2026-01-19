"""Section editor module for per-section newsletter editing via Slack modals.

Provides functions for building edit modals, fetching section data,
and saving edits. Each section can be edited independently with content
preserved and tracked.
"""

from datetime import datetime
from typing import Optional

from app.models import db
from app.newsletter.models import Newsletter, NewsletterSection
from app.newsletter.interfaces import SectionType, SectionStatus


# Maximum content length for Slack modal text input
MAX_SECTION_CONTENT = 2900

# Human-readable names for each section type
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

# Order for sections in newsletter
SECTION_ORDER = {
    SectionType.OPENER.value: 1,
    SectionType.QOTM.value: 2,
    SectionType.COACHES_CORNER.value: 3,
    SectionType.MEMBER_HEADS_UP.value: 4,
    SectionType.UPCOMING_EVENTS.value: 5,
    SectionType.MEMBER_HIGHLIGHT.value: 6,
    SectionType.MONTH_IN_REVIEW.value: 7,
    SectionType.FROM_THE_BOARD.value: 8,
    SectionType.PHOTO_GALLERY.value: 9,
    SectionType.CLOSER.value: 10,
}


def get_section_display_name(section_type: str) -> str:
    """Get human-readable display name for a section type.

    Args:
        section_type: The section type value (e.g., 'from_the_board')

    Returns:
        Human-readable name (e.g., 'From the Board')
    """
    return SECTION_NAMES.get(section_type, section_type.replace('_', ' ').title())


def build_section_edit_modal(
    section_type: str,
    current_content: str,
    newsletter_id: int,
    section_id: int,
    ai_draft: Optional[str] = None
) -> dict:
    """Build a Slack modal for editing a newsletter section.

    Args:
        section_type: The type of section being edited
        current_content: Current content to pre-fill in the editor
        newsletter_id: ID of the newsletter this section belongs to
        section_id: ID of the section being edited
        ai_draft: Optional AI-generated draft for reference

    Returns:
        Slack modal view payload
    """
    display_name = get_section_display_name(section_type)

    # Truncate content if too long for Slack modal
    truncated = False
    if current_content and len(current_content) > MAX_SECTION_CONTENT:
        current_content = current_content[:MAX_SECTION_CONTENT]
        truncated = True

    # Store metadata for submission handling
    private_metadata = f"{newsletter_id}:{section_id}:{section_type}"

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"Edit the *{display_name}* section content below."
            }
        }
    ]

    # Add truncation warning if content was trimmed
    if truncated:
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f":warning: Content was truncated to {MAX_SECTION_CONTENT} characters. The full content is preserved in the database."
                }
            ]
        })

    # Add AI draft reference if present and different from current
    if ai_draft and ai_draft != current_content:
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": ":robot_face: _An AI draft is available. Your edits will be saved as the new content._"
                }
            ]
        })

    blocks.append({"type": "divider"})

    # Content input block
    content_element = {
        "type": "plain_text_input",
        "action_id": "section_content",
        "multiline": True,
        "max_length": 3000,
        "placeholder": {
            "type": "plain_text",
            "text": f"Enter the {display_name} content..."
        }
    }

    if current_content:
        content_element["initial_value"] = current_content

    blocks.append({
        "type": "input",
        "block_id": "content_block",
        "label": {
            "type": "plain_text",
            "text": "Content"
        },
        "element": content_element
    })

    return {
        "type": "modal",
        "callback_id": "section_edit_submit",
        "private_metadata": private_metadata,
        "title": {
            "type": "plain_text",
            "text": f"Edit: {display_name}"[:24]  # Slack title limit
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


def get_section_for_editing(
    newsletter_id: int,
    section_type: str
) -> Optional[NewsletterSection]:
    """Get a section for editing, creating it if it doesn't exist.

    Args:
        newsletter_id: ID of the newsletter
        section_type: Type of section to retrieve

    Returns:
        NewsletterSection instance or None if newsletter doesn't exist
    """
    newsletter = Newsletter.query.get(newsletter_id)
    if not newsletter:
        return None

    section = NewsletterSection.query.filter_by(
        newsletter_id=newsletter_id,
        section_type=section_type
    ).first()

    if not section:
        section = NewsletterSection(
            newsletter_id=newsletter_id,
            section_type=section_type,
            section_order=SECTION_ORDER.get(section_type, 99),
            status=SectionStatus.AWAITING_CONTENT.value
        )
        db.session.add(section)
        db.session.flush()

    return section


def save_section_edit(
    section_id: int,
    new_content: str,
    editor_slack_uid: str
) -> dict:
    """Save edited content to a section.

    Args:
        section_id: ID of the section to update
        new_content: New content to save
        editor_slack_uid: Slack user ID of the editor

    Returns:
        Dict with success status and section info
    """
    section = NewsletterSection.query.get(section_id)
    if not section:
        return {
            'success': False,
            'error': 'Section not found'
        }

    # Preserve AI draft if this is first human edit
    if section.status == SectionStatus.HAS_AI_DRAFT.value and not section.ai_draft:
        section.ai_draft = section.content

    # Update content and status
    section.content = new_content
    section.status = SectionStatus.HUMAN_EDITED.value
    section.edited_by = editor_slack_uid
    section.edited_at = datetime.utcnow()

    db.session.commit()

    return {
        'success': True,
        'section_id': section.id,
        'section_type': section.section_type,
        'status': section.status
    }


def get_all_sections_for_newsletter(newsletter_id: int) -> list[NewsletterSection]:
    """Get all sections for a newsletter, ordered by section_order.

    Args:
        newsletter_id: ID of the newsletter

    Returns:
        List of NewsletterSection instances ordered by section_order
    """
    return NewsletterSection.query.filter_by(
        newsletter_id=newsletter_id
    ).order_by(NewsletterSection.section_order).all()


def initialize_sections_for_newsletter(newsletter_id: int) -> list[NewsletterSection]:
    """Initialize all standard sections for a newsletter.

    Creates NewsletterSection records for each SectionType if they
    don't already exist.

    Args:
        newsletter_id: ID of the newsletter

    Returns:
        List of all sections (new and existing) for the newsletter
    """
    newsletter = Newsletter.query.get(newsletter_id)
    if not newsletter:
        return []

    existing_types = {
        s.section_type for s in
        NewsletterSection.query.filter_by(newsletter_id=newsletter_id).all()
    }

    # Create missing sections
    for section_type in SectionType:
        if section_type.value not in existing_types:
            section = NewsletterSection(
                newsletter_id=newsletter_id,
                section_type=section_type.value,
                section_order=SECTION_ORDER.get(section_type.value, 99),
                status=SectionStatus.AWAITING_CONTENT.value
            )
            db.session.add(section)

    db.session.flush()

    return get_all_sections_for_newsletter(newsletter_id)
