from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.models import db
from app.practices import PracticeSummaryPost


@pytest.fixture
def app():
    application = create_app()
    application.config.update(TESTING=True, SECRET_KEY="test-secret-key")
    return application


@pytest.fixture(autouse=True)
def clear_summary_posts(app):
    with app.app_context():
        db.session.rollback()
        PracticeSummaryPost.query.delete()
        db.session.commit()
    try:
        yield
    finally:
        with app.app_context():
            db.session.rollback()
            PracticeSummaryPost.query.delete()
            db.session.commit()


def test_summary_identity_is_unique_per_week_and_surface(app):
    with app.app_context():
        coach = PracticeSummaryPost(
            week_start=date(2026, 7, 13),
            surface="coach_summary",
            channel_id="C-COACH",
            message_ts="100.1",
        )
        public = PracticeSummaryPost(
            week_start=date(2026, 7, 13),
            surface="weekly_summary",
            channel_id="C-PUBLIC",
            message_ts="100.2",
        )
        db.session.add_all([coach, public])
        db.session.commit()

        db.session.add(PracticeSummaryPost(
            week_start=date(2026, 7, 13),
            surface="weekly_summary",
            channel_id="C-OTHER",
            message_ts="100.3",
        ))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_summary_surface_is_restricted(app):
    with app.app_context():
        db.session.add(PracticeSummaryPost(
            week_start=date(2026, 7, 20),
            surface="other_summary",
            channel_id="C-OTHER",
            message_ts="200.1",
        ))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
