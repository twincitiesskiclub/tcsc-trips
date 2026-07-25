"""Draft block generation — idempotency is the point."""

from datetime import date, datetime

import pytest

from app import create_app
from app.models import AppConfig, db
from app.practices.drafting import expected_slots, generate_draft_block
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


@pytest.fixture()
def practice_days(db_session):
    AppConfig.set(
        key="practice_days",
        value=[
            {"day": "tuesday", "time": "18:15", "active": True},
            {"day": "thursday", "time": "18:15", "active": True},
            {"day": "thursday", "time": "19:20", "active": True},
            {"day": "sunday", "time": "09:00", "active": False},
        ],
        description="test",
        category="practices",
    )
    db.session.commit()
    yield
    # This is the real local dev database — remove the config row we created
    # rather than leaving test data behind for the next run/developer.
    AppConfig.query.filter_by(key="practice_days").delete()
    db.session.commit()


def test_expected_slots_covers_active_days_only(practice_days):
    slots = expected_slots(date(2026, 8, 3), weeks=1)  # Mon Aug 3
    assert slots == [
        datetime(2026, 8, 4, 18, 15),
        datetime(2026, 8, 6, 18, 15),
        datetime(2026, 8, 6, 19, 20),
    ], "inactive days must be skipped and times honoured"


def test_expected_slots_excludes_dates_before_start_date(practice_days):
    # Wed Aug 5, 2026. The week containing it starts Mon Aug 3, so the
    # Tuesday slot (Aug 4) falls before start_date and must be dropped —
    # the contract is "no slot earlier than start_date."
    slots = expected_slots(date(2026, 8, 5), weeks=1)
    assert slots == [
        datetime(2026, 8, 6, 18, 15),
        datetime(2026, 8, 6, 19, 20),
    ], "slots before start_date must be excluded, even though week normalisation looks back to Monday"


def test_expected_slots_full_first_week_when_start_is_monday(practice_days):
    # Guard against over-trimming: when start_date already IS the Monday of
    # its week, no in-window slot should be excluded.
    slots = expected_slots(date(2026, 8, 3), weeks=1)  # Mon Aug 3
    assert slots == [
        datetime(2026, 8, 4, 18, 15),
        datetime(2026, 8, 6, 18, 15),
        datetime(2026, 8, 6, 19, 20),
    ], "a Monday start_date must still produce the full first week"


def _delete_practices_in_slots(slots):
    """Clean up every Practice row in the given slots, regardless of who
    created it or what any function under test happened to return.

    Scoped-query cleanup instead of tracking returned lists: a returned list
    can't include rows the code under test wrongly created (e.g. a broken
    collision check creating unexpected duplicates), so it can't be trusted
    to enumerate everything that needs deleting. Cleanup must hold even when
    an assertion above it fails and the test never reaches a "success" path.
    """
    Practice.query.filter(Practice.date.in_(slots)).delete(synchronize_session=False)
    db.session.commit()


def test_generate_creates_drafts(practice_days):
    slots = expected_slots(date(2026, 8, 3), weeks=2)
    try:
        created = generate_draft_block(date(2026, 8, 3), weeks=2)
        assert len(created) == 6
        assert all(p.is_draft is True for p in created)
        assert all(p.leads_needed == 2 for p in created)
    finally:
        _delete_practices_in_slots(slots)


def test_generate_is_idempotent(practice_days):
    slots = expected_slots(date(2026, 8, 3), weeks=2)
    try:
        first = generate_draft_block(date(2026, 8, 3), weeks=2)
        second = generate_draft_block(date(2026, 8, 3), weeks=2)

        assert len(first) == 6
        assert second == [], "re-running must create nothing"

        # Scoped to the slots this test created — an unscoped
        # Practice.query.count() would also see the developer's existing
        # practices in the local dev database and fail spuriously.
        assert Practice.query.filter(Practice.date.in_(slots)).count() == 6
    finally:
        # Covers rows from BOTH calls above (and any extra duplicates a
        # broken collision check might create) — not just what the first
        # call happened to return.
        _delete_practices_in_slots(slots)


def test_generate_skips_slots_that_already_have_a_real_practice(practice_days):
    slots = expected_slots(date(2026, 8, 3), weeks=1)
    existing = Practice(
        date=datetime(2026, 8, 4, 18, 15),
        day_of_week="Tuesday",
        is_draft=False,
    )
    db.session.add(existing)
    db.session.commit()

    try:
        created = generate_draft_block(date(2026, 8, 3), weeks=1)
        assert len(created) == 2, "must not duplicate an already-published practice"
        assert Practice.query.filter_by(date=datetime(2026, 8, 4, 18, 15)).count() == 1
    finally:
        _delete_practices_in_slots(slots)
