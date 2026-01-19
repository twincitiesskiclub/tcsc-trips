"""Tests for the Newsletter Host system."""

import pytest
from datetime import datetime

from app import create_app
from app.models import db
from app.newsletter.models import Newsletter, NewsletterHost
from app.newsletter.interfaces import HostStatus
from app.newsletter.host import (
    assign_host,
    handle_host_submission,
    get_host_for_newsletter,
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
        month_year='2026-02',
        week_start=datetime(2026, 2, 1),
        week_end=datetime(2026, 2, 28, 23, 59, 59),
        period_start=datetime(2026, 2, 1),
        period_end=datetime(2026, 2, 28, 23, 59, 59),
        publish_target_date=datetime(2026, 2, 15, 12, 0, 0),
        qotm_question="What's your favorite winter activity?",
        status='building'
    )
    db.session.add(newsletter)
    db.session.commit()
    yield newsletter
    # Cleanup
    NewsletterHost.query.filter_by(newsletter_id=newsletter.id).delete()
    db.session.delete(newsletter)
    db.session.commit()


class TestAssignHost:
    """Tests for assign_host function."""

    def test_assign_host_creates_record(self, app, newsletter):
        """Test that assigning a Slack member as host creates a record."""
        with app.app_context():
            result = assign_host(
                newsletter_id=newsletter.id,
                slack_user_id='U12345ABC'
            )

            assert result['success'] is True
            assert 'host_id' in result
            assert result['is_external'] is False

            # Verify the host was created in the database
            host = NewsletterHost.query.get(result['host_id'])
            assert host is not None
            assert host.newsletter_id == newsletter.id
            assert host.slack_user_id == 'U12345ABC'
            assert host.external_name is None
            assert host.external_email is None
            assert host.status == HostStatus.ASSIGNED.value
            assert host.opener_content is None
            assert host.closer_content is None

    def test_assign_external_host(self, app, newsletter):
        """Test that assigning an external guest as host creates a record."""
        with app.app_context():
            result = assign_host(
                newsletter_id=newsletter.id,
                external_name='Jane Guest',
                external_email='jane@example.com'
            )

            assert result['success'] is True
            assert 'host_id' in result
            assert result['is_external'] is True

            # Verify the host was created in the database
            host = NewsletterHost.query.get(result['host_id'])
            assert host is not None
            assert host.newsletter_id == newsletter.id
            assert host.slack_user_id is None
            assert host.external_name == 'Jane Guest'
            assert host.external_email == 'jane@example.com'
            assert host.status == HostStatus.ASSIGNED.value
            assert host.is_external is True

    def test_assign_host_updates_existing(self, app, newsletter):
        """Test that assigning a new host updates the existing assignment."""
        with app.app_context():
            # First assignment
            result1 = assign_host(
                newsletter_id=newsletter.id,
                slack_user_id='U12345ABC'
            )
            first_host_id = result1['host_id']

            # Second assignment (different user)
            result2 = assign_host(
                newsletter_id=newsletter.id,
                slack_user_id='UXYZ98765'
            )

            assert result2['success'] is True
            # Should return the same host_id (updated, not new)
            assert result2['host_id'] == first_host_id

            # Verify only one host record exists
            hosts = NewsletterHost.query.filter_by(
                newsletter_id=newsletter.id
            ).all()
            assert len(hosts) == 1

            # Verify the host was updated
            host = hosts[0]
            assert host.slack_user_id == 'UXYZ98765'

    def test_assign_host_requires_identifier(self, app, newsletter):
        """Test that assign_host fails without slack_user_id or external_name."""
        with app.app_context():
            result = assign_host(newsletter_id=newsletter.id)

            assert result['success'] is False
            assert 'error' in result
            assert 'slack_user_id or external_name' in result['error']

    def test_assign_host_rejects_both_identifiers(self, app, newsletter):
        """Test that assign_host fails with both slack_user_id and external_name."""
        with app.app_context():
            result = assign_host(
                newsletter_id=newsletter.id,
                slack_user_id='U12345ABC',
                external_name='Jane Guest'
            )

            assert result['success'] is False
            assert 'error' in result
            assert 'Cannot provide both' in result['error']

    def test_assign_host_invalid_newsletter(self, app):
        """Test that assign_host fails for non-existent newsletter."""
        with app.app_context():
            result = assign_host(
                newsletter_id=99999,
                slack_user_id='U12345ABC'
            )

            assert result['success'] is False
            assert 'error' in result
            assert 'not found' in result['error']


class TestHandleHostSubmission:
    """Tests for handle_host_submission function."""

    def test_handle_host_submission_saves_content(self, app, newsletter):
        """Test that host submission saves opener and closer content."""
        with app.app_context():
            # First assign a host
            assign_result = assign_host(
                newsletter_id=newsletter.id,
                slack_user_id='U12345ABC'
            )

            # Submit content
            result = handle_host_submission(
                newsletter_id=newsletter.id,
                opener_content='Welcome to the February newsletter!',
                closer_content='See you on the trails!'
            )

            assert result['success'] is True
            assert result['host_id'] == assign_result['host_id']

            # Verify the submission was saved
            host = NewsletterHost.query.get(result['host_id'])
            assert host.opener_content == 'Welcome to the February newsletter!'
            assert host.closer_content == 'See you on the trails!'
            assert host.status == HostStatus.SUBMITTED.value
            assert host.submitted_at is not None

    def test_handle_host_submission_requires_opener(self, app, newsletter):
        """Test that host submission requires opener content."""
        with app.app_context():
            assign_host(
                newsletter_id=newsletter.id,
                slack_user_id='U12345ABC'
            )

            result = handle_host_submission(
                newsletter_id=newsletter.id,
                opener_content='',
                closer_content='See you on the trails!'
            )

            assert result['success'] is False
            assert 'error' in result
            assert 'Opener' in result['error']

    def test_handle_host_submission_requires_closer(self, app, newsletter):
        """Test that host submission requires closer content."""
        with app.app_context():
            assign_host(
                newsletter_id=newsletter.id,
                slack_user_id='U12345ABC'
            )

            result = handle_host_submission(
                newsletter_id=newsletter.id,
                opener_content='Welcome to the February newsletter!',
                closer_content=''
            )

            assert result['success'] is False
            assert 'error' in result
            assert 'Closer' in result['error']

    def test_handle_host_submission_no_host(self, app, newsletter):
        """Test that host submission fails if no host is assigned."""
        with app.app_context():
            result = handle_host_submission(
                newsletter_id=newsletter.id,
                opener_content='Welcome!',
                closer_content='Goodbye!'
            )

            assert result['success'] is False
            assert 'error' in result
            assert 'No host assigned' in result['error']


class TestGetHostForNewsletter:
    """Tests for get_host_for_newsletter function."""

    def test_get_host_returns_host(self, app, newsletter):
        """Test that get_host_for_newsletter returns the assigned host."""
        with app.app_context():
            assign_host(
                newsletter_id=newsletter.id,
                slack_user_id='U12345ABC'
            )

            host = get_host_for_newsletter(newsletter.id)

            assert host is not None
            assert host.slack_user_id == 'U12345ABC'

    def test_get_host_returns_none_when_no_host(self, app, newsletter):
        """Test that get_host_for_newsletter returns None when no host assigned."""
        with app.app_context():
            host = get_host_for_newsletter(newsletter.id)
            assert host is None
