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
