"""Practice draft flag and lead count defaults.

Year 2099 dates and a "TEST " marker per tests/practices/conftest.py: this
suite runs against the real local dev database. The rows previously landed on
2026-08-04/06 18:15 — real near-future dates at the exact time every
availability suite uses as the club's practice slot — and cleanup ran only on
the happy path, so a failing assertion left an `is_draft=False`,
`status='SCHEDULED'` practice a week out, indistinguishable from a real one.
It would then have shown up in published_practices(), the coach weekly summary
and the announcement job. Cleanup is now try/finally with rollback first.
"""

from datetime import datetime

import pytest

from app import create_app
from app.models import db
from app.practices.models import Practice

_DRAFT_SLOT = datetime(2099, 4, 14, 20, 45)
_PUBLISHED_SLOT = datetime(2099, 4, 16, 20, 45)


@pytest.fixture
def app():
    application = create_app()
    application.config.update(TESTING=True, SECRET_KEY="test-secret-key")
    return application


@pytest.fixture
def db_session(app):
    with app.app_context():
        yield db.session


def _cleanup(practice_id):
    """Rollback first, so a poisoned session (a prior statement that raised
    and left the transaction aborted) can't turn cleanup itself into the thing
    that leaves debris behind.
    """
    db.session.rollback()
    stored = db.session.get(Practice, practice_id)
    if stored is not None:
        db.session.delete(stored)
    db.session.commit()


def test_new_practice_defaults_to_published_with_two_leads(db_session):
    practice = Practice(
        date=_PUBLISHED_SLOT,
        day_of_week="Thursday",
        logistics_notes="TEST draft schema default",
    )
    db_session.add(practice)
    db_session.commit()
    practice_id = practice.id

    try:
        assert practice.is_draft is False, \
            "practices must be published unless explicitly drafted"
        assert practice.leads_needed == 2
    finally:
        _cleanup(practice_id)


def test_draft_flag_round_trips(db_session):
    practice = Practice(
        date=_DRAFT_SLOT,
        day_of_week="Tuesday",
        is_draft=True,
        leads_needed=3,
        logistics_notes="TEST draft schema round trip",
    )
    db_session.add(practice)
    db_session.commit()
    practice_id = practice.id

    try:
        db_session.expire(practice)
        assert practice.is_draft is True
        assert practice.leads_needed == 3
    finally:
        _cleanup(practice_id)
