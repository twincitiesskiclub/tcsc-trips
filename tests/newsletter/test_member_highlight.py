"""Tests for the Member Highlight system."""

import pytest
from datetime import datetime, timedelta
import uuid

from app import create_app
from app.models import db, User, SlackUser
from app.newsletter.models import Newsletter, MemberHighlight
from app.newsletter.interfaces import HighlightStatus
from app.newsletter.member_highlight import (
    HIGHLIGHT_QUESTIONS,
    nominate_member,
    handle_highlight_submission,
    mark_highlight_declined,
    get_previous_highlight_dates,
    get_highlight_for_newsletter,
    build_highlight_submission_modal,
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
    """Create a database session for testing.

    Creates all tables, yields the session, then rolls back
    any changes to keep tests isolated.
    """
    with app.app_context():
        # Create all tables
        db.create_all()

        yield db

        # Cleanup: rollback any uncommitted changes
        db.session.rollback()


@pytest.fixture
def newsletter(db_session):
    """Create a test newsletter."""
    newsletter = Newsletter(
        month_year='2026-03',
        week_start=datetime(2026, 3, 1),
        week_end=datetime(2026, 3, 31, 23, 59, 59),
        period_start=datetime(2026, 3, 1),
        period_end=datetime(2026, 3, 31, 23, 59, 59),
        publish_target_date=datetime(2026, 3, 15, 12, 0, 0),
        qotm_question="What's your favorite ski trail?",
        status='building'
    )
    db.session.add(newsletter)
    db.session.commit()
    yield newsletter
    # Cleanup
    MemberHighlight.query.filter_by(newsletter_id=newsletter.id).delete()
    db.session.delete(newsletter)
    db.session.commit()


@pytest.fixture
def member(db_session):
    """Create a test member user."""
    unique_id = uuid.uuid4().hex[:8]

    member = User(
        first_name='Test',
        last_name='Member',
        email=f'test.member.{unique_id}@test.com',
        status='ACTIVE'
    )
    db.session.add(member)
    db.session.commit()

    yield member

    # Cleanup - remove any highlights and the user
    MemberHighlight.query.filter_by(member_user_id=member.id).delete()
    db.session.delete(member)
    db.session.commit()


@pytest.fixture
def member_with_slack(db_session):
    """Create a test member user with linked Slack account."""
    unique_id = uuid.uuid4().hex[:8]

    # Create SlackUser first
    slack_user = SlackUser(
        slack_uid=f'U{unique_id}',
        email=f'test.slackmember.{unique_id}@test.com',
        display_name='Test Slack Member'
    )
    db.session.add(slack_user)
    db.session.flush()

    # Create User linked to SlackUser
    member = User(
        first_name='Test',
        last_name='SlackMember',
        email=f'test.slackmember.{unique_id}@test.com',
        status='ACTIVE',
        slack_user_id=slack_user.id
    )
    db.session.add(member)
    db.session.commit()

    yield member

    # Cleanup
    MemberHighlight.query.filter_by(member_user_id=member.id).delete()
    db.session.delete(member)
    db.session.delete(slack_user)
    db.session.commit()


class TestHighlightQuestions:
    """Tests for HIGHLIGHT_QUESTIONS constant."""

    def test_highlight_questions_exist(self):
        """Test that HIGHLIGHT_QUESTIONS is defined with expected structure."""
        assert HIGHLIGHT_QUESTIONS is not None
        assert isinstance(HIGHLIGHT_QUESTIONS, list)
        assert len(HIGHLIGHT_QUESTIONS) > 0

    def test_highlight_questions_have_required_fields(self):
        """Test that each question has id, question, and placeholder."""
        for q in HIGHLIGHT_QUESTIONS:
            assert 'id' in q, f"Question missing 'id': {q}"
            assert 'question' in q, f"Question missing 'question': {q}"
            assert 'placeholder' in q, f"Question missing 'placeholder': {q}"

    def test_highlight_questions_ids_are_unique(self):
        """Test that all question IDs are unique."""
        ids = [q['id'] for q in HIGHLIGHT_QUESTIONS]
        assert len(ids) == len(set(ids)), "Question IDs are not unique"

    def test_highlight_questions_expected_count(self):
        """Test that there are 6 template questions as specified."""
        assert len(HIGHLIGHT_QUESTIONS) == 6


class TestNominateMember:
    """Tests for nominate_member function."""

    def test_nominate_member_creates_record(self, app, newsletter, member):
        """Test that nominating a member creates a MemberHighlight record."""
        with app.app_context():
            # Refresh from database
            member_id = member.id
            member = User.query.get(member_id)

            result = nominate_member(
                newsletter_id=newsletter.id,
                member_user_id=member.id,
                nominated_by='admin@test.com'
            )

            assert result['success'] is True
            assert 'highlight_id' in result
            assert result['member_name'] == member.full_name

            # Verify the highlight was created in the database
            highlight = MemberHighlight.query.get(result['highlight_id'])
            assert highlight is not None
            assert highlight.newsletter_id == newsletter.id
            assert highlight.member_user_id == member.id
            assert highlight.nominated_by == 'admin@test.com'
            assert highlight.status == HighlightStatus.NOMINATED.value
            assert highlight.raw_answers is None
            assert highlight.ai_composed_content is None
            assert highlight.content is None

    def test_nominate_member_updates_existing(self, app, newsletter, member):
        """Test that nominating a different member updates the existing record."""
        with app.app_context():
            member_id = member.id
            member = User.query.get(member_id)

            # Create another member
            unique_id = uuid.uuid4().hex[:8]
            member2 = User(
                first_name='Another',
                last_name='Member',
                email=f'another.member.{unique_id}@test.com',
                status='ACTIVE'
            )
            db.session.add(member2)
            db.session.commit()

            try:
                # First nomination
                result1 = nominate_member(
                    newsletter_id=newsletter.id,
                    member_user_id=member.id,
                    nominated_by='admin1@test.com'
                )
                first_highlight_id = result1['highlight_id']

                # Second nomination (different member)
                result2 = nominate_member(
                    newsletter_id=newsletter.id,
                    member_user_id=member2.id,
                    nominated_by='admin2@test.com'
                )

                assert result2['success'] is True
                # Should return the same highlight_id (updated, not new)
                assert result2['highlight_id'] == first_highlight_id
                assert result2['member_name'] == member2.full_name

                # Verify only one highlight record exists
                highlights = MemberHighlight.query.filter_by(
                    newsletter_id=newsletter.id
                ).all()
                assert len(highlights) == 1

                # Verify the highlight was updated
                highlight = highlights[0]
                assert highlight.member_user_id == member2.id
                assert highlight.nominated_by == 'admin2@test.com'
            finally:
                # Cleanup member2
                MemberHighlight.query.filter_by(member_user_id=member2.id).delete()
                db.session.delete(member2)
                db.session.commit()

    def test_nominate_member_invalid_newsletter(self, app, member):
        """Test that nominate_member fails for non-existent newsletter."""
        with app.app_context():
            result = nominate_member(
                newsletter_id=99999,
                member_user_id=member.id,
                nominated_by='admin@test.com'
            )

            assert result['success'] is False
            assert 'error' in result
            assert 'not found' in result['error']

    def test_nominate_member_invalid_user(self, app, newsletter):
        """Test that nominate_member fails for non-existent user."""
        with app.app_context():
            result = nominate_member(
                newsletter_id=newsletter.id,
                member_user_id=99999,
                nominated_by='admin@test.com'
            )

            assert result['success'] is False
            assert 'error' in result
            assert 'not found' in result['error']


class TestHandleHighlightSubmission:
    """Tests for handle_highlight_submission function."""

    def test_handle_highlight_submission_stores_answers(self, app, newsletter, member):
        """Test that highlight submission stores answers correctly."""
        with app.app_context():
            member = User.query.get(member.id)

            # First nominate the member
            nominate_result = nominate_member(
                newsletter_id=newsletter.id,
                member_user_id=member.id,
                nominated_by='admin@test.com'
            )

            # Submit answers
            raw_answers = {
                'years_skiing': '5 years skiing, 2 with TCSC',
                'favorite_memory': 'That time I skied through the blizzard',
                'looking_forward': 'Improving my skate technique',
                'classic_or_skate': 'Classic all the way - more elegant!',
                'wipeout_story': 'Faceplanted at the finish line',
                'anything_else': 'Thanks for having me!'
            }
            result = handle_highlight_submission(
                newsletter_id=newsletter.id,
                raw_answers=raw_answers
            )

            assert result['success'] is True
            assert result['highlight_id'] == nominate_result['highlight_id']

            # Verify the submission was saved
            highlight = MemberHighlight.query.get(result['highlight_id'])
            assert highlight.raw_answers == raw_answers
            assert highlight.status == HighlightStatus.SUBMITTED.value
            assert highlight.submitted_at is not None

    def test_handle_highlight_submission_requires_at_least_one_answer(self, app, newsletter, member):
        """Test that highlight submission requires at least one non-empty answer."""
        with app.app_context():
            member = User.query.get(member.id)

            nominate_member(
                newsletter_id=newsletter.id,
                member_user_id=member.id,
                nominated_by='admin@test.com'
            )

            # Empty answers
            result = handle_highlight_submission(
                newsletter_id=newsletter.id,
                raw_answers={}
            )

            assert result['success'] is False
            assert 'error' in result
            assert 'at least one' in result['error'].lower()

    def test_handle_highlight_submission_accepts_partial_answers(self, app, newsletter, member):
        """Test that highlight submission accepts partial answers."""
        with app.app_context():
            member = User.query.get(member.id)

            nominate_member(
                newsletter_id=newsletter.id,
                member_user_id=member.id,
                nominated_by='admin@test.com'
            )

            # Only one answer provided
            raw_answers = {
                'years_skiing': '3 years'
            }
            result = handle_highlight_submission(
                newsletter_id=newsletter.id,
                raw_answers=raw_answers
            )

            assert result['success'] is True

            # Verify the submission was saved
            highlight = MemberHighlight.query.get(result['highlight_id'])
            assert highlight.raw_answers == raw_answers
            assert highlight.status == HighlightStatus.SUBMITTED.value

    def test_handle_highlight_submission_no_nomination(self, app, newsletter):
        """Test that highlight submission fails if no member is nominated."""
        with app.app_context():
            result = handle_highlight_submission(
                newsletter_id=newsletter.id,
                raw_answers={'years_skiing': '5 years'}
            )

            assert result['success'] is False
            assert 'error' in result
            assert 'No member nominated' in result['error']


class TestMarkHighlightDeclined:
    """Tests for mark_highlight_declined function."""

    def test_mark_highlight_declined(self, app, newsletter, member):
        """Test that marking a highlight as declined works."""
        with app.app_context():
            member = User.query.get(member.id)

            nominate_member(
                newsletter_id=newsletter.id,
                member_user_id=member.id,
                nominated_by='admin@test.com'
            )

            result = mark_highlight_declined(newsletter_id=newsletter.id)

            assert result['success'] is True
            assert result['member_name'] == member.full_name

            # Verify the highlight was marked as declined
            highlight = get_highlight_for_newsletter(newsletter.id)
            assert highlight.status == HighlightStatus.DECLINED.value

    def test_mark_highlight_declined_no_nomination(self, app, newsletter):
        """Test that marking declined fails if no nomination exists."""
        with app.app_context():
            result = mark_highlight_declined(newsletter_id=newsletter.id)

            assert result['success'] is False
            assert 'error' in result
            assert 'No member nominated' in result['error']


class TestGetPreviousHighlightDates:
    """Tests for get_previous_highlight_dates function."""

    def test_get_previous_highlight_dates_empty(self, app, member):
        """Test that get_previous_highlight_dates returns empty list for new member."""
        with app.app_context():
            member = User.query.get(member.id)
            dates = get_previous_highlight_dates(member.id)
            assert dates == []

    def test_get_previous_highlight_dates_with_history(self, app, member):
        """Test that get_previous_highlight_dates returns dates for member with history."""
        with app.app_context():
            member = User.query.get(member.id)

            # Create historical newsletters and highlights
            newsletters = []
            for i in range(3):
                nl = Newsletter(
                    month_year=f'2025-{10+i:02d}',
                    week_start=datetime(2025, 10+i, 1),
                    week_end=datetime(2025, 10+i, 28, 23, 59, 59),
                    period_start=datetime(2025, 10+i, 1),
                    period_end=datetime(2025, 10+i, 28, 23, 59, 59),
                    publish_target_date=datetime(2025, 10+i, 15, 12, 0, 0),
                    status='published'
                )
                db.session.add(nl)
                newsletters.append(nl)
            db.session.commit()

            # Create highlights - some submitted, one declined
            submitted_dates = []
            for i, nl in enumerate(newsletters):
                status = HighlightStatus.SUBMITTED.value if i < 2 else HighlightStatus.DECLINED.value
                submitted_at = datetime(2025, 10+i, 10) if i < 2 else None

                highlight = MemberHighlight(
                    newsletter_id=nl.id,
                    member_user_id=member.id,
                    nominated_by='admin@test.com',
                    status=status,
                    nominated_at=datetime(2025, 10+i, 1),
                    submitted_at=submitted_at
                )
                db.session.add(highlight)
                if submitted_at:
                    submitted_dates.append(submitted_at)
            db.session.commit()

            try:
                dates = get_previous_highlight_dates(member.id)

                # Should only return dates for SUBMITTED highlights
                assert len(dates) == 2
                # Should be ordered by most recent first
                assert dates[0] > dates[1]
            finally:
                # Cleanup
                for nl in newsletters:
                    MemberHighlight.query.filter_by(newsletter_id=nl.id).delete()
                    db.session.delete(nl)
                db.session.commit()


class TestGetHighlightForNewsletter:
    """Tests for get_highlight_for_newsletter function."""

    def test_get_highlight_returns_highlight(self, app, newsletter, member):
        """Test that get_highlight_for_newsletter returns the nomination."""
        with app.app_context():
            member = User.query.get(member.id)

            nominate_member(
                newsletter_id=newsletter.id,
                member_user_id=member.id,
                nominated_by='admin@test.com'
            )

            highlight = get_highlight_for_newsletter(newsletter.id)

            assert highlight is not None
            assert highlight.member_user_id == member.id

    def test_get_highlight_returns_none_when_no_nomination(self, app, newsletter):
        """Test that get_highlight_for_newsletter returns None when no nomination."""
        with app.app_context():
            highlight = get_highlight_for_newsletter(newsletter.id)
            assert highlight is None


class TestBuildHighlightSubmissionModal:
    """Tests for build_highlight_submission_modal function."""

    def test_build_modal_structure(self, app, newsletter):
        """Test that the modal has the correct structure."""
        with app.app_context():
            modal = build_highlight_submission_modal(newsletter.id)

            assert modal['type'] == 'modal'
            assert modal['callback_id'] == 'highlight_submission'
            assert modal['private_metadata'] == str(newsletter.id)
            assert 'title' in modal
            assert 'submit' in modal
            assert 'close' in modal
            assert 'blocks' in modal

    def test_build_modal_has_all_questions(self, app, newsletter):
        """Test that the modal includes input blocks for all questions."""
        with app.app_context():
            modal = build_highlight_submission_modal(newsletter.id)

            # Count input blocks
            input_blocks = [
                b for b in modal['blocks']
                if b.get('type') == 'input'
            ]

            # Should have one input block per question
            assert len(input_blocks) == len(HIGHLIGHT_QUESTIONS)

            # Verify each question has a corresponding input
            for question in HIGHLIGHT_QUESTIONS:
                block_id = f"highlight_{question['id']}_block"
                matching_blocks = [
                    b for b in input_blocks
                    if b.get('block_id') == block_id
                ]
                assert len(matching_blocks) == 1, f"Missing input for question: {question['id']}"
