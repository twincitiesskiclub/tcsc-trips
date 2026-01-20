"""Tests for the Photo Gallery system."""

import pytest
from datetime import datetime

from app import create_app
from app.models import db
from app.newsletter.models import Newsletter, PhotoSubmission
from app.newsletter.photos import (
    get_photo_submissions,
    select_photos,
    get_selected_photos,
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
    PhotoSubmission.query.filter_by(newsletter_id=newsletter.id).delete()
    db.session.delete(newsletter)
    db.session.commit()


@pytest.fixture
def photos(db_session, newsletter):
    """Create test photos for the newsletter."""
    photo1 = PhotoSubmission(
        newsletter_id=newsletter.id,
        slack_file_id='F001',
        slack_permalink='https://slack.com/files/F001',
        caption='Great day on the trails!',
        reaction_count=10,
        submitted_by_user_id='U001',
        posted_at=datetime(2026, 1, 10),
        selected=False
    )
    photo2 = PhotoSubmission(
        newsletter_id=newsletter.id,
        slack_file_id='F002',
        slack_permalink='https://slack.com/files/F002',
        caption='Snow day!',
        reaction_count=5,
        submitted_by_user_id='U002',
        posted_at=datetime(2026, 1, 12),
        selected=False
    )
    photo3 = PhotoSubmission(
        newsletter_id=newsletter.id,
        slack_file_id='F003',
        slack_permalink='https://slack.com/files/F003',
        caption='Club photo',
        reaction_count=15,
        submitted_by_user_id='U003',
        posted_at=datetime(2026, 1, 15),
        selected=False
    )
    db.session.add_all([photo1, photo2, photo3])
    db.session.commit()
    yield [photo1, photo2, photo3]


class TestGetPhotoSubmissions:
    """Tests for get_photo_submissions function."""

    def test_get_photo_submissions_returns_all(self, app, newsletter, photos):
        """Test that all photos for a newsletter are returned."""
        with app.app_context():
            submissions = get_photo_submissions(newsletter.id)

            assert len(submissions) == 3
            file_ids = [s.slack_file_id for s in submissions]
            assert 'F001' in file_ids
            assert 'F002' in file_ids
            assert 'F003' in file_ids

    def test_get_photo_submissions_sorted_by_popularity(self, app, newsletter, photos):
        """Test that photos are sorted by reaction count (highest first)."""
        with app.app_context():
            submissions = get_photo_submissions(newsletter.id)

            # Should be sorted by reaction_count descending
            # photo3 (15) > photo1 (10) > photo2 (5)
            assert len(submissions) == 3
            assert submissions[0].slack_file_id == 'F003'  # 15 reactions
            assert submissions[1].slack_file_id == 'F001'  # 10 reactions
            assert submissions[2].slack_file_id == 'F002'  # 5 reactions

    def test_get_photo_submissions_empty(self, app, newsletter):
        """Test that empty list is returned when no photos exist."""
        with app.app_context():
            submissions = get_photo_submissions(newsletter.id)
            assert submissions == []


class TestSelectPhotos:
    """Tests for select_photos function."""

    def test_select_photos_marks_selected(self, app, newsletter, photos):
        """Test that specified photos are marked as selected."""
        with app.app_context():
            # Select only first two photos
            result = select_photos(
                newsletter_id=newsletter.id,
                photo_ids=[photos[0].id, photos[1].id]
            )

            assert result['success'] is True
            assert result['selected_count'] == 2

            # Refresh from database and verify selection status
            db.session.expire_all()
            p1 = PhotoSubmission.query.get(photos[0].id)
            p2 = PhotoSubmission.query.get(photos[1].id)
            p3 = PhotoSubmission.query.get(photos[2].id)

            assert p1.selected is True
            assert p2.selected is True
            assert p3.selected is False

    def test_select_photos_deselects_previous(self, app, newsletter, photos):
        """Test that selecting new photos deselects previously selected ones."""
        with app.app_context():
            # First selection - select photo 1
            select_photos(
                newsletter_id=newsletter.id,
                photo_ids=[photos[0].id]
            )

            # Verify photo 1 is selected
            db.session.expire_all()
            p1 = PhotoSubmission.query.get(photos[0].id)
            assert p1.selected is True

            # New selection - only photo 2
            select_photos(
                newsletter_id=newsletter.id,
                photo_ids=[photos[1].id]
            )

            # Refresh from database
            db.session.expire_all()
            p1 = PhotoSubmission.query.get(photos[0].id)
            p2 = PhotoSubmission.query.get(photos[1].id)
            p3 = PhotoSubmission.query.get(photos[2].id)

            # Photo 1 should now be unselected, photo 2 selected
            assert p1.selected is False
            assert p2.selected is True
            assert p3.selected is False

    def test_select_photos_empty_list_deselects_all(self, app, newsletter, photos):
        """Test that passing empty list deselects all photos."""
        with app.app_context():
            # First select some photos
            select_photos(
                newsletter_id=newsletter.id,
                photo_ids=[photos[0].id, photos[1].id]
            )

            # Then deselect all by passing empty list
            result = select_photos(
                newsletter_id=newsletter.id,
                photo_ids=[]
            )

            assert result['success'] is True
            assert result['selected_count'] == 0

            # Verify all are deselected
            db.session.expire_all()
            for photo in photos:
                p = PhotoSubmission.query.get(photo.id)
                assert p.selected is False


class TestGetSelectedPhotos:
    """Tests for get_selected_photos function."""

    def test_get_selected_photos_returns_only_selected(self, app, newsletter, photos):
        """Test that only selected photos are returned."""
        with app.app_context():
            # Select photos 1 and 3
            select_photos(
                newsletter_id=newsletter.id,
                photo_ids=[photos[0].id, photos[2].id]
            )

            selected = get_selected_photos(newsletter.id)

            assert len(selected) == 2
            selected_ids = [p.id for p in selected]
            assert photos[0].id in selected_ids
            assert photos[2].id in selected_ids
            assert photos[1].id not in selected_ids

    def test_get_selected_photos_empty_when_none_selected(self, app, newsletter, photos):
        """Test that empty list is returned when no photos are selected."""
        with app.app_context():
            selected = get_selected_photos(newsletter.id)
            assert selected == []

    def test_get_selected_photos_sorted_by_popularity(self, app, newsletter, photos):
        """Test that selected photos are sorted by reaction count."""
        with app.app_context():
            # Select all photos
            select_photos(
                newsletter_id=newsletter.id,
                photo_ids=[p.id for p in photos]
            )

            selected = get_selected_photos(newsletter.id)

            # Should be sorted by reaction_count descending
            assert len(selected) == 3
            assert selected[0].slack_file_id == 'F003'  # 15 reactions
            assert selected[1].slack_file_id == 'F001'  # 10 reactions
            assert selected[2].slack_file_id == 'F002'  # 5 reactions
