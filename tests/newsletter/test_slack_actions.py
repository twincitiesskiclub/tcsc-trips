"""Tests for slack_actions module - living post with section editing."""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from app import create_app
from app.models import db
from app.newsletter.models import Newsletter, NewsletterSection
from app.newsletter.interfaces import (
    NewsletterStatus,
    SectionType,
    SectionStatus,
    SlackPostReference,
)
from app.newsletter.slack_actions import (
    build_section_blocks_with_edit_buttons,
    create_living_post_with_sections,
)


@pytest.fixture
def app():
    """Create a test Flask application."""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        'postgresql://tcsc:tcsc@localhost:5432/tcsc_trips'
    )
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture
def db_session(app):
    """Create a database session for testing."""
    with app.app_context():
        db.create_all()
        yield db
        db.session.rollback()


@pytest.fixture
def newsletter(db_session):
    """Create a test newsletter."""
    newsletter = Newsletter(
        month_year='2026-02',
        week_start=datetime(2026, 2, 1),
        week_end=datetime(2026, 2, 28, 23, 59, 59),
        period_start=datetime(2026, 2, 1),
        period_end=datetime(2026, 2, 28, 23, 59, 59),
        publish_target_date=datetime(2026, 2, 15, 12, 0, 0),
        qotm_question="What's your favorite winter activity?",
        status=NewsletterStatus.BUILDING.value
    )
    db.session.add(newsletter)
    db.session.commit()
    yield newsletter
    # Cleanup
    NewsletterSection.query.filter_by(newsletter_id=newsletter.id).delete()
    db.session.delete(newsletter)
    db.session.commit()


class TestBuildSectionBlocksWithEditButtons:
    """Tests for build_section_blocks_with_edit_buttons function."""

    def test_returns_list_of_blocks(self, app, newsletter):
        """Test that function returns a list of Block Kit blocks."""
        with app.app_context():
            # Create some test sections
            section = NewsletterSection(
                newsletter_id=newsletter.id,
                section_type=SectionType.OPENER.value,
                section_order=1,
                status=SectionStatus.AWAITING_CONTENT.value,
                content="Test opener content here"
            )
            db.session.add(section)
            db.session.commit()

            sections = [section]
            blocks = build_section_blocks_with_edit_buttons(newsletter, sections)

            assert isinstance(blocks, list)
            assert len(blocks) > 0

    def test_includes_header_with_month_year(self, app, newsletter):
        """Test that blocks include header with month/year."""
        with app.app_context():
            sections = []
            blocks = build_section_blocks_with_edit_buttons(newsletter, sections)

            # Find header block
            header_block = None
            for block in blocks:
                if block.get('type') == 'header':
                    header_block = block
                    break

            assert header_block is not None
            # Check that month/year is in the header
            header_text = header_block['text']['text']
            assert 'February' in header_text or '2026-02' in header_text

    def test_includes_status_context(self, app, newsletter):
        """Test that blocks include status context."""
        with app.app_context():
            sections = []
            blocks = build_section_blocks_with_edit_buttons(newsletter, sections)

            # Find context block with status
            context_found = False
            for block in blocks:
                if block.get('type') == 'context':
                    elements = block.get('elements', [])
                    for elem in elements:
                        text = elem.get('text', '')
                        if 'building' in text.lower() or 'status' in text.lower():
                            context_found = True
                            break

            assert context_found

    def test_section_shows_status_emoji(self, app, newsletter):
        """Test that each section shows appropriate status emoji."""
        with app.app_context():
            section = NewsletterSection(
                newsletter_id=newsletter.id,
                section_type=SectionType.OPENER.value,
                section_order=1,
                status=SectionStatus.AWAITING_CONTENT.value,
                content=""
            )
            db.session.add(section)
            db.session.commit()

            sections = [section]
            blocks = build_section_blocks_with_edit_buttons(newsletter, sections)

            # Find section with hourglass emoji (AWAITING_CONTENT)
            blocks_text = str(blocks)
            assert ':hourglass:' in blocks_text

    def test_section_shows_ai_draft_emoji(self, app, newsletter):
        """Test that AI draft status shows robot emoji."""
        with app.app_context():
            section = NewsletterSection(
                newsletter_id=newsletter.id,
                section_type=SectionType.COACHES_CORNER.value,
                section_order=3,
                status=SectionStatus.HAS_AI_DRAFT.value,
                content="AI generated content"
            )
            db.session.add(section)
            db.session.commit()

            sections = [section]
            blocks = build_section_blocks_with_edit_buttons(newsletter, sections)

            blocks_text = str(blocks)
            assert ':robot_face:' in blocks_text

    def test_section_shows_human_edited_emoji(self, app, newsletter):
        """Test that human edited status shows pencil emoji."""
        with app.app_context():
            section = NewsletterSection(
                newsletter_id=newsletter.id,
                section_type=SectionType.FROM_THE_BOARD.value,
                section_order=8,
                status=SectionStatus.HUMAN_EDITED.value,
                content="Human edited content"
            )
            db.session.add(section)
            db.session.commit()

            sections = [section]
            blocks = build_section_blocks_with_edit_buttons(newsletter, sections)

            blocks_text = str(blocks)
            assert ':pencil2:' in blocks_text

    def test_section_shows_final_emoji(self, app, newsletter):
        """Test that final status shows checkmark emoji."""
        with app.app_context():
            section = NewsletterSection(
                newsletter_id=newsletter.id,
                section_type=SectionType.CLOSER.value,
                section_order=10,
                status=SectionStatus.FINAL.value,
                content="Final content"
            )
            db.session.add(section)
            db.session.commit()

            sections = [section]
            blocks = build_section_blocks_with_edit_buttons(newsletter, sections)

            blocks_text = str(blocks)
            assert ':white_check_mark:' in blocks_text

    def test_section_shows_edit_button(self, app, newsletter):
        """Test that each section has an Edit button."""
        with app.app_context():
            section = NewsletterSection(
                newsletter_id=newsletter.id,
                section_type=SectionType.OPENER.value,
                section_order=1,
                status=SectionStatus.AWAITING_CONTENT.value,
                content="Test content"
            )
            db.session.add(section)
            db.session.commit()

            sections = [section]
            blocks = build_section_blocks_with_edit_buttons(newsletter, sections)

            # Find button with action_id="section_edit"
            button_found = False
            for block in blocks:
                if block.get('type') == 'section' and 'accessory' in block:
                    accessory = block['accessory']
                    if accessory.get('action_id') == 'section_edit':
                        button_found = True
                        break

            assert button_found

    def test_edit_button_has_correct_value_format(self, app, newsletter):
        """Test that Edit button value has format newsletter_id:section_id:section_type."""
        with app.app_context():
            section = NewsletterSection(
                newsletter_id=newsletter.id,
                section_type=SectionType.OPENER.value,
                section_order=1,
                status=SectionStatus.AWAITING_CONTENT.value,
                content="Test content"
            )
            db.session.add(section)
            db.session.commit()

            sections = [section]
            blocks = build_section_blocks_with_edit_buttons(newsletter, sections)

            # Find button and check value format
            for block in blocks:
                if block.get('type') == 'section' and 'accessory' in block:
                    accessory = block['accessory']
                    if accessory.get('action_id') == 'section_edit':
                        value = accessory.get('value', '')
                        parts = value.split(':')
                        assert len(parts) == 3
                        assert parts[0] == str(newsletter.id)
                        assert parts[1] == str(section.id)
                        assert parts[2] == SectionType.OPENER.value
                        break

    def test_content_preview_truncated_at_150_chars(self, app, newsletter):
        """Test that content preview is truncated at 150 characters."""
        with app.app_context():
            long_content = "x" * 300
            section = NewsletterSection(
                newsletter_id=newsletter.id,
                section_type=SectionType.OPENER.value,
                section_order=1,
                status=SectionStatus.HUMAN_EDITED.value,
                content=long_content
            )
            db.session.add(section)
            db.session.commit()

            sections = [section]
            blocks = build_section_blocks_with_edit_buttons(newsletter, sections)

            # Find content preview - should be max 150 chars + "..."
            for block in blocks:
                if block.get('type') == 'section':
                    text = block.get('text', {}).get('text', '')
                    # The preview should NOT contain the full 300 chars
                    assert 'x' * 300 not in text


class TestCreateLivingPostWithSections:
    """Tests for create_living_post_with_sections function."""

    @patch('app.newsletter.slack_actions.get_slack_client')
    @patch('app.newsletter.slack_actions.get_living_post_channel')
    @patch('app.newsletter.slack_actions.is_dry_run')
    def test_returns_slack_post_reference(
        self, mock_is_dry_run, mock_get_channel, mock_get_client, app, newsletter
    ):
        """Test that function returns a SlackPostReference."""
        mock_is_dry_run.return_value = False
        mock_get_channel.return_value = 'C12345'
        mock_client = MagicMock()
        mock_client.chat_postMessage.return_value = {'ts': '1234567890.123456'}
        mock_get_client.return_value = mock_client

        with app.app_context():
            result = create_living_post_with_sections(newsletter)

            assert isinstance(result, SlackPostReference)
            assert result.channel_id == 'C12345'
            assert result.message_ts == '1234567890.123456'

    @patch('app.newsletter.slack_actions.get_slack_client')
    @patch('app.newsletter.slack_actions.get_living_post_channel')
    @patch('app.newsletter.slack_actions.is_dry_run')
    def test_initializes_sections_if_none_exist(
        self, mock_is_dry_run, mock_get_channel, mock_get_client, app, newsletter
    ):
        """Test that sections are initialized if none exist."""
        mock_is_dry_run.return_value = False
        mock_get_channel.return_value = 'C12345'
        mock_client = MagicMock()
        mock_client.chat_postMessage.return_value = {'ts': '1234567890.123456'}
        mock_get_client.return_value = mock_client

        with app.app_context():
            # Verify no sections exist initially
            initial_sections = NewsletterSection.query.filter_by(
                newsletter_id=newsletter.id
            ).all()
            assert len(initial_sections) == 0

            create_living_post_with_sections(newsletter)

            # Verify sections were created
            sections = NewsletterSection.query.filter_by(
                newsletter_id=newsletter.id
            ).all()
            assert len(sections) > 0

    @patch('app.newsletter.slack_actions.get_slack_client')
    @patch('app.newsletter.slack_actions.get_living_post_channel')
    @patch('app.newsletter.slack_actions.is_dry_run')
    def test_saves_slack_references_to_newsletter(
        self, mock_is_dry_run, mock_get_channel, mock_get_client, app, newsletter
    ):
        """Test that Slack channel_id and message_ts are saved to newsletter."""
        mock_is_dry_run.return_value = False
        mock_get_channel.return_value = 'C12345'
        mock_client = MagicMock()
        mock_client.chat_postMessage.return_value = {'ts': '1234567890.123456'}
        mock_get_client.return_value = mock_client

        newsletter_id = newsletter.id

        with app.app_context():
            # Re-fetch newsletter in this context
            from app.newsletter.models import Newsletter as NL
            nl = NL.query.get(newsletter_id)
            create_living_post_with_sections(nl)

            # Refresh and check
            db.session.expire(nl)
            updated_nl = NL.query.get(newsletter_id)
            assert updated_nl.slack_channel_id == 'C12345'
            assert updated_nl.slack_main_message_ts == '1234567890.123456'

    @patch('app.newsletter.slack_actions.get_living_post_channel')
    @patch('app.newsletter.slack_actions.is_dry_run')
    def test_dry_run_returns_mock_reference(
        self, mock_is_dry_run, mock_get_channel, app, newsletter
    ):
        """Test that dry run mode returns a mock reference without posting."""
        mock_is_dry_run.return_value = True
        mock_get_channel.return_value = 'C12345'

        with app.app_context():
            result = create_living_post_with_sections(newsletter)

            assert isinstance(result, SlackPostReference)
            assert result.channel_id == 'C12345'
            assert result.message_ts == 'dry_run_ts'

    @patch('app.newsletter.slack_actions.get_living_post_channel')
    def test_raises_value_error_if_no_channel(
        self, mock_get_channel, app, newsletter
    ):
        """Test that ValueError is raised if channel cannot be found."""
        mock_get_channel.return_value = None

        with app.app_context():
            with pytest.raises(ValueError, match="Could not find living post channel"):
                create_living_post_with_sections(newsletter)

    @patch('app.newsletter.slack_actions.get_slack_client')
    @patch('app.newsletter.slack_actions.get_living_post_channel')
    @patch('app.newsletter.slack_actions.is_dry_run')
    def test_ready_for_review_includes_approve_buttons(
        self, mock_is_dry_run, mock_get_channel, mock_get_client, app, newsletter
    ):
        """Test that READY_FOR_REVIEW status includes approve/request changes buttons."""
        mock_is_dry_run.return_value = False
        mock_get_channel.return_value = 'C12345'
        mock_client = MagicMock()
        mock_client.chat_postMessage.return_value = {'ts': '1234567890.123456'}
        mock_get_client.return_value = mock_client

        with app.app_context():
            newsletter.status = NewsletterStatus.READY_FOR_REVIEW.value
            db.session.commit()

            create_living_post_with_sections(newsletter)

            # Check that the posted blocks include approve buttons
            call_args = mock_client.chat_postMessage.call_args
            blocks = call_args.kwargs.get('blocks', [])

            # Look for actions block with approve button
            approve_button_found = False
            for block in blocks:
                if block.get('type') == 'actions':
                    for element in block.get('elements', []):
                        if element.get('action_id') == 'newsletter_approve':
                            approve_button_found = True
                            break

            assert approve_button_found
