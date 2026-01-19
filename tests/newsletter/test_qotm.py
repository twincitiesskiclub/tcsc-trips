"""Tests for the QOTM (Question of the Month) system."""

import pytest
from datetime import datetime

from app import create_app
from app.models import db
from app.newsletter.models import Newsletter, QOTMResponse
from app.newsletter.qotm import (
    handle_qotm_submission,
    get_qotm_responses,
    select_qotm_responses,
    get_selected_qotm_for_newsletter,
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
    now = datetime.utcnow()
    newsletter = Newsletter(
        month_year='2026-01',
        week_start=datetime(2026, 1, 1),
        week_end=datetime(2026, 1, 31, 23, 59, 59),
        period_start=datetime(2026, 1, 1),
        period_end=datetime(2026, 1, 31, 23, 59, 59),
        publish_target_date=datetime(2026, 1, 15, 12, 0, 0),
        qotm_question="What's your favorite ski trail?",
        status='building'
    )
    db.session.add(newsletter)
    db.session.commit()
    yield newsletter
    # Cleanup
    QOTMResponse.query.filter_by(newsletter_id=newsletter.id).delete()
    db.session.delete(newsletter)
    db.session.commit()


class TestHandleQOTMSubmission:
    """Tests for handle_qotm_submission function."""

    def test_handle_qotm_submission_creates_response(self, app, newsletter):
        """Test that a new QOTM response is created for a first-time submitter."""
        with app.app_context():
            result = handle_qotm_submission(
                newsletter_id=newsletter.id,
                user_id='U12345ABC',
                user_name='Test User',
                response='I love the North Loop trail!'
            )

            assert result['success'] is True
            assert 'response_id' in result
            assert result['is_update'] is False

            # Verify the response was created in the database
            qotm = QOTMResponse.query.get(result['response_id'])
            assert qotm is not None
            assert qotm.newsletter_id == newsletter.id
            assert qotm.slack_user_id == 'U12345ABC'
            assert qotm.user_name == 'Test User'
            assert qotm.response == 'I love the North Loop trail!'
            assert qotm.selected is False

    def test_handle_qotm_submission_upserts(self, app, newsletter):
        """Test that submitting again updates the existing response."""
        with app.app_context():
            # First submission
            result1 = handle_qotm_submission(
                newsletter_id=newsletter.id,
                user_id='U12345ABC',
                user_name='Test User',
                response='Original response'
            )

            assert result1['success'] is True
            assert result1['is_update'] is False
            first_response_id = result1['response_id']

            # Second submission from same user
            result2 = handle_qotm_submission(
                newsletter_id=newsletter.id,
                user_id='U12345ABC',
                user_name='Test User Updated',
                response='Updated response'
            )

            assert result2['success'] is True
            assert result2['is_update'] is True
            # Should return the same response ID
            assert result2['response_id'] == first_response_id

            # Verify the response was updated, not duplicated
            responses = QOTMResponse.query.filter_by(
                newsletter_id=newsletter.id,
                slack_user_id='U12345ABC'
            ).all()
            assert len(responses) == 1

            qotm = responses[0]
            assert qotm.response == 'Updated response'
            assert qotm.user_name == 'Test User Updated'


class TestGetQOTMResponses:
    """Tests for get_qotm_responses function."""

    def test_get_qotm_responses_returns_all(self, app, newsletter):
        """Test that all responses for a newsletter are returned."""
        with app.app_context():
            # Create multiple responses
            handle_qotm_submission(
                newsletter_id=newsletter.id,
                user_id='U001',
                user_name='User One',
                response='Response one'
            )
            handle_qotm_submission(
                newsletter_id=newsletter.id,
                user_id='U002',
                user_name='User Two',
                response='Response two'
            )
            handle_qotm_submission(
                newsletter_id=newsletter.id,
                user_id='U003',
                user_name='User Three',
                response='Response three'
            )

            responses = get_qotm_responses(newsletter.id)

            assert len(responses) == 3
            # Verify all responses are present
            user_ids = [r.slack_user_id for r in responses]
            assert 'U001' in user_ids
            assert 'U002' in user_ids
            assert 'U003' in user_ids

    def test_get_qotm_responses_empty(self, app, newsletter):
        """Test that empty list is returned when no responses exist."""
        with app.app_context():
            responses = get_qotm_responses(newsletter.id)
            assert responses == []


class TestSelectQOTMResponses:
    """Tests for select_qotm_responses function."""

    def test_select_qotm_responses_marks_selected(self, app, newsletter):
        """Test that specified responses are marked as selected."""
        with app.app_context():
            # Create responses
            r1 = handle_qotm_submission(
                newsletter_id=newsletter.id,
                user_id='U001',
                user_name='User One',
                response='Response one'
            )
            r2 = handle_qotm_submission(
                newsletter_id=newsletter.id,
                user_id='U002',
                user_name='User Two',
                response='Response two'
            )
            r3 = handle_qotm_submission(
                newsletter_id=newsletter.id,
                user_id='U003',
                user_name='User Three',
                response='Response three'
            )

            # Select only first two
            result = select_qotm_responses(
                response_ids=[r1['response_id'], r2['response_id']],
                newsletter_id=newsletter.id
            )

            assert result['success'] is True
            assert result['selected_count'] == 2

            # Verify selection status
            qotm1 = QOTMResponse.query.get(r1['response_id'])
            qotm2 = QOTMResponse.query.get(r2['response_id'])
            qotm3 = QOTMResponse.query.get(r3['response_id'])

            assert qotm1.selected is True
            assert qotm2.selected is True
            assert qotm3.selected is False

    def test_select_qotm_responses_replaces_selection(self, app, newsletter):
        """Test that selecting new responses replaces previous selection."""
        with app.app_context():
            # Create responses
            r1 = handle_qotm_submission(
                newsletter_id=newsletter.id,
                user_id='U001',
                user_name='User One',
                response='Response one'
            )
            r2 = handle_qotm_submission(
                newsletter_id=newsletter.id,
                user_id='U002',
                user_name='User Two',
                response='Response two'
            )

            # First selection
            select_qotm_responses(
                response_ids=[r1['response_id']],
                newsletter_id=newsletter.id
            )

            # Verify first is selected
            qotm1 = QOTMResponse.query.get(r1['response_id'])
            assert qotm1.selected is True

            # New selection (only r2)
            select_qotm_responses(
                response_ids=[r2['response_id']],
                newsletter_id=newsletter.id
            )

            # Refresh from database
            db.session.refresh(qotm1)
            qotm2 = QOTMResponse.query.get(r2['response_id'])

            # r1 should now be unselected, r2 selected
            assert qotm1.selected is False
            assert qotm2.selected is True


class TestGetSelectedQOTMForNewsletter:
    """Tests for get_selected_qotm_for_newsletter function."""

    def test_get_selected_qotm_returns_only_selected(self, app, newsletter):
        """Test that only selected responses are returned."""
        with app.app_context():
            # Create responses
            r1 = handle_qotm_submission(
                newsletter_id=newsletter.id,
                user_id='U001',
                user_name='User One',
                response='Response one'
            )
            r2 = handle_qotm_submission(
                newsletter_id=newsletter.id,
                user_id='U002',
                user_name='User Two',
                response='Response two'
            )
            r3 = handle_qotm_submission(
                newsletter_id=newsletter.id,
                user_id='U003',
                user_name='User Three',
                response='Response three'
            )

            # Select only r1 and r3
            select_qotm_responses(
                response_ids=[r1['response_id'], r3['response_id']],
                newsletter_id=newsletter.id
            )

            selected = get_selected_qotm_for_newsletter(newsletter.id)

            assert len(selected) == 2
            selected_ids = [r.id for r in selected]
            assert r1['response_id'] in selected_ids
            assert r3['response_id'] in selected_ids
            assert r2['response_id'] not in selected_ids

    def test_get_selected_qotm_empty_when_none_selected(self, app, newsletter):
        """Test that empty list is returned when no responses are selected."""
        with app.app_context():
            # Create response but don't select it
            handle_qotm_submission(
                newsletter_id=newsletter.id,
                user_id='U001',
                user_name='User One',
                response='Response one'
            )

            selected = get_selected_qotm_for_newsletter(newsletter.id)
            assert selected == []
