"""Tests for the Monthly AI Draft Generator module."""

import os
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

# Set DATABASE_URL before importing app
os.environ.setdefault('DATABASE_URL', 'postgresql://tcsc:tcsc@localhost:5432/tcsc_trips')

from app import create_app
from app.models import db
from app.newsletter.models import Newsletter, NewsletterSection
from app.newsletter.interfaces import SectionType, SectionStatus, MessageVisibility
from app.newsletter.monthly_generator import (
    AI_DRAFTED_SECTIONS,
    MAX_SECTION_CHARS,
    build_section_context,
    _load_monthly_prompt,
    _load_generation_config,
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
        qotm_question="What's your favorite ski trail?",
        status='building'
    )
    db.session.add(newsletter)
    db.session.commit()
    yield newsletter
    # Cleanup
    NewsletterSection.query.filter_by(newsletter_id=newsletter.id).delete()
    db.session.delete(newsletter)
    db.session.commit()


class TestAIDraftedSectionsList:
    """Tests for AI_DRAFTED_SECTIONS constant."""

    def test_ai_drafted_sections_list_contains_expected_sections(self):
        """Test that AI_DRAFTED_SECTIONS contains the correct section types."""
        assert SectionType.FROM_THE_BOARD.value in AI_DRAFTED_SECTIONS
        assert SectionType.MEMBER_HEADS_UP.value in AI_DRAFTED_SECTIONS
        assert SectionType.UPCOMING_EVENTS.value in AI_DRAFTED_SECTIONS
        assert SectionType.MONTH_IN_REVIEW.value in AI_DRAFTED_SECTIONS

    def test_ai_drafted_sections_excludes_human_sections(self):
        """Test that AI_DRAFTED_SECTIONS excludes human-written sections."""
        assert SectionType.OPENER.value not in AI_DRAFTED_SECTIONS
        assert SectionType.CLOSER.value not in AI_DRAFTED_SECTIONS
        assert SectionType.QOTM.value not in AI_DRAFTED_SECTIONS
        assert SectionType.COACHES_CORNER.value not in AI_DRAFTED_SECTIONS
        assert SectionType.PHOTO_GALLERY.value not in AI_DRAFTED_SECTIONS

    def test_ai_drafted_sections_count(self):
        """Test that AI_DRAFTED_SECTIONS has the expected count."""
        assert len(AI_DRAFTED_SECTIONS) == 4


class TestMaxSectionChars:
    """Tests for MAX_SECTION_CHARS constant."""

    def test_max_section_chars_value(self):
        """Test that MAX_SECTION_CHARS is set to Slack modal limit."""
        assert MAX_SECTION_CHARS == 2900


class TestBuildSectionContext:
    """Tests for build_section_context function."""

    def test_build_section_context_from_the_board(self, app, newsletter):
        """Test that from_the_board context includes leadership messages."""
        with app.app_context():
            leadership_messages = [
                {
                    'text': 'Important board decision about membership fees.',
                    'channel_name': 'leadership-board',
                    'visibility': 'private',
                    'user_name': 'Board Member'
                },
                {
                    'text': 'New policy for volunteer coordination.',
                    'channel_name': 'leadership-ops',
                    'visibility': 'private',
                    'user_name': 'Ops Lead'
                }
            ]

            context = build_section_context(
                newsletter=newsletter,
                section_type=SectionType.FROM_THE_BOARD.value,
                leadership_messages=leadership_messages
            )

            # Verify newsletter info is included
            assert '2026-02' in context
            assert 'from_the_board' in context

            # Verify leadership messages are included
            assert 'LEADERSHIP UPDATES' in context
            assert 'Important board decision' in context
            assert 'PRIVATE' in context
            assert 'summarize themes only' in context.lower()

    def test_build_section_context_from_the_board_empty_messages(self, app, newsletter):
        """Test from_the_board context with no leadership messages."""
        with app.app_context():
            context = build_section_context(
                newsletter=newsletter,
                section_type=SectionType.FROM_THE_BOARD.value,
                leadership_messages=None
            )

            assert 'LEADERSHIP UPDATES' in context
            assert 'No leadership messages available' in context

    def test_build_section_context_month_in_review_public_private(self, app, newsletter):
        """Test that month_in_review context separates public and private messages."""
        with app.app_context():
            slack_messages = [
                {
                    'text': 'Great ski day at Theodore Wirth!',
                    'channel_name': 'general',
                    'visibility': 'public',
                    'user_name': 'Alice',
                    'permalink': 'https://slack.com/msg1',
                    'reaction_count': 15,
                    'reply_count': 3
                },
                {
                    'text': 'Confidential discussion about coaches.',
                    'channel_name': 'leadership-coaches',
                    'visibility': 'private',
                    'user_name': 'Coach Lead',
                    'reaction_count': 2,
                    'reply_count': 1
                }
            ]

            context = build_section_context(
                newsletter=newsletter,
                section_type=SectionType.MONTH_IN_REVIEW.value,
                slack_messages=slack_messages
            )

            # Verify public messages section
            assert 'PUBLIC CHANNEL HIGHLIGHTS' in context
            assert 'Can quote, link, and name members' in context
            assert '[PUBLIC]' in context
            assert 'Great ski day' in context
            assert 'Alice' in context
            assert 'https://slack.com/msg1' in context

            # Verify private messages section
            assert 'PRIVATE CHANNEL THEMES' in context
            assert 'NO names, NO quotes' in context
            assert '[PRIVATE]' in context

    def test_build_section_context_month_in_review_with_message_objects(self, app, newsletter):
        """Test month_in_review context works with SlackMessage-like objects."""
        with app.app_context():
            # Create mock objects that behave like SlackMessage
            class MockMessage:
                def __init__(self, text, channel_name, visibility, user_name, permalink=None, reaction_count=0, reply_count=0):
                    self.text = text
                    self.channel_name = channel_name
                    self.visibility = visibility
                    self.user_name = user_name
                    self.permalink = permalink
                    self.reaction_count = reaction_count
                    self.reply_count = reply_count

            messages = [
                MockMessage(
                    text='Object-based message test',
                    channel_name='test-channel',
                    visibility=MessageVisibility.PUBLIC,
                    user_name='Bob',
                    permalink='https://slack.com/msg2',
                    reaction_count=5,
                    reply_count=2
                )
            ]

            context = build_section_context(
                newsletter=newsletter,
                section_type=SectionType.MONTH_IN_REVIEW.value,
                slack_messages=messages
            )

            assert 'Object-based message test' in context
            assert 'Bob' in context
            assert 'https://slack.com/msg2' in context

    def test_build_section_context_upcoming_events(self, app, newsletter):
        """Test that upcoming_events context includes event details."""
        with app.app_context():
            events = [
                {
                    'title': 'Thursday Night Practice',
                    'date': 'Feb 6, 2026 6:00 PM',
                    'location': 'Theodore Wirth Park',
                    'description': 'Weekly practice session for all skill levels.'
                },
                {
                    'title': 'Annual Club Trip',
                    'date': 'Feb 15-17, 2026',
                    'location': 'Cable, WI',
                    'description': 'Weekend trip to the Birkie trails.'
                }
            ]

            context = build_section_context(
                newsletter=newsletter,
                section_type=SectionType.UPCOMING_EVENTS.value,
                events=events
            )

            assert 'UPCOMING EVENTS' in context
            assert 'Thursday Night Practice' in context
            assert 'Feb 6, 2026' in context
            assert 'Theodore Wirth' in context
            assert 'Annual Club Trip' in context
            assert 'Cable, WI' in context

    def test_build_section_context_member_heads_up(self, app, newsletter):
        """Test that member_heads_up context includes announcements."""
        with app.app_context():
            slack_messages = [
                {
                    'text': 'Registration deadline is tomorrow!',
                    'channel_name': 'announcements',
                    'visibility': 'public',
                    'user_name': 'Admin',
                    'permalink': 'https://slack.com/announce1'
                }
            ]

            context = build_section_context(
                newsletter=newsletter,
                section_type=SectionType.MEMBER_HEADS_UP.value,
                slack_messages=slack_messages
            )

            assert 'ANNOUNCEMENTS AND NOTICES' in context
            assert 'Registration deadline' in context
            assert 'Admin' in context

    def test_build_section_context_member_highlight(self, app, newsletter):
        """Test that member_highlight context includes Q&A responses."""
        with app.app_context():
            member_answers = {
                'How did you get into skiing?': 'My family took me skiing in Colorado when I was 5.',
                'What do you love about TCSC?': 'The welcoming community and Thursday practices!',
                'What advice would you give new members?': 'Just show up and have fun!'
            }

            context = build_section_context(
                newsletter=newsletter,
                section_type=SectionType.MEMBER_HIGHLIGHT.value,
                member_highlight_answers=member_answers
            )

            assert 'MEMBER HIGHLIGHT' in context
            assert 'q&a responses' in context.lower()
            assert 'How did you get into skiing?' in context
            assert 'My family took me skiing in Colorado' in context
            assert 'What do you love about TCSC?' in context
            assert 'welcoming community' in context


class TestLoadMonthlyPrompt:
    """Tests for _load_monthly_prompt function."""

    def test_load_monthly_prompt_returns_string(self, app):
        """Test that _load_monthly_prompt returns a non-empty string."""
        with app.app_context():
            prompt = _load_monthly_prompt()
            assert isinstance(prompt, str)
            assert len(prompt) > 0

    def test_load_monthly_prompt_contains_key_instructions(self, app):
        """Test that the prompt contains key formatting instructions."""
        with app.app_context():
            prompt = _load_monthly_prompt()
            # Should mention JSON output
            assert 'json' in prompt.lower()
            # Should mention Slack formatting
            assert 'slack' in prompt.lower() or 'mrkdwn' in prompt.lower()
            # Should mention character limit
            assert '2900' in prompt


class TestLoadGenerationConfig:
    """Tests for _load_generation_config function."""

    def test_load_generation_config_returns_dict(self, app):
        """Test that _load_generation_config returns a dict."""
        with app.app_context():
            config = _load_generation_config()
            assert isinstance(config, dict)

    def test_load_generation_config_has_model_setting(self, app):
        """Test that config includes model setting if file exists."""
        with app.app_context():
            config = _load_generation_config()
            # May have model key if newsletter.yaml has generation section
            # This just ensures no error is raised
            assert config is not None
