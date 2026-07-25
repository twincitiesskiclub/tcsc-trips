"""Practice draft flag and lead count defaults."""

from datetime import datetime

import pytest

from app import create_app
from app.models import db
from app.practices.models import Practice


@pytest.fixture
def app():
    application = create_app()
    application.config.update(TESTING=True, SECRET_KEY="test-secret-key")
    return application


@pytest.fixture
def db_session(app):
    with app.app_context():
        yield db.session


def test_new_practice_defaults_to_published_with_two_leads(db_session):
    practice = Practice(
        date=datetime(2026, 8, 4, 18, 15),
        day_of_week="Tuesday",
    )
    db_session.add(practice)
    db_session.commit()

    assert practice.is_draft is False, "practices must be published unless explicitly drafted"
    assert practice.leads_needed == 2

    db_session.delete(practice)
    db_session.commit()


def test_draft_flag_round_trips(db_session):
    practice = Practice(
        date=datetime(2026, 8, 6, 18, 15),
        day_of_week="Thursday",
        is_draft=True,
        leads_needed=3,
    )
    db_session.add(practice)
    db_session.commit()
    db_session.expire(practice)

    assert practice.is_draft is True
    assert practice.leads_needed == 3

    db_session.delete(practice)
    db_session.commit()
