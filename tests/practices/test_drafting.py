"""Draft block generation — idempotency is the point."""

from datetime import date, datetime

import pytest

from app import create_app
from app.models import AppConfig, db
from app.practices.drafting import (
    drafted_practices_in_window,
    expected_slots,
    generate_draft_block,
)
from app.practices.models import Practice

# Marks rows created directly (not via generate_draft_block) so a leaked row
# is unmistakably test debris rather than something a human entered — see
# tests/practices/conftest.py docstring, point 3.
_TEST_NOTE = "TEST drafted_practices_in_window coverage"


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
    """Save and restore the real `practice_days` AppConfig row.

    This is the real local dev database. The previous version of this
    fixture unconditionally deleted the `practice_days` row on teardown --
    if a human (or another script) had ever seeded a real value, running
    this module would silently wipe it. Capture whatever was there before
    the test (if anything) and put it back exactly afterward, deleting only
    if there was no row to begin with -- never assume delete is the correct
    restore.
    """
    db.session.rollback()
    existing = AppConfig.query.filter_by(key="practice_days").first()
    had_row = existing is not None
    original = (
        (existing.value, existing.description, existing.category)
        if had_row else None
    )

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
    db.session.rollback()
    if had_row:
        value, description, category = original
        AppConfig.set(key="practice_days", value=value,
                      description=description, category=category)
    else:
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


# -----------------------------------------------------------------------
# drafted_practices_in_window
#
# This function has no other direct coverage: every consumer (the
# scheduler's readiness nudge job, tests/test_scheduler_draft_jobs.py) mocks
# it away entirely. A reviewer proved that by deleting the
# `Practice.is_draft.is_(True)` filter and finding the whole suite (225
# tests in tests/practices/ plus test_scheduler_draft_jobs.py) still green.
# That filter is what keeps a real, already-published practice from being
# reported by the daily coach/director nudge as an incomplete draft — these
# tests exercise the function directly so that regression can't recur
# unnoticed.
#
# Dates use year 2099 (see conftest.py docstring) so they can never collide
# with real near-term dev-database practices.
# -----------------------------------------------------------------------


def test_drafted_practices_in_window_returns_drafts_inside_window(db_session):
    start = date(2099, 3, 2)
    inside_slot = datetime(2099, 3, 10, 18, 0)
    inside = Practice(
        date=inside_slot, day_of_week="Tuesday", is_draft=True, logistics_notes=_TEST_NOTE
    )
    db.session.add(inside)
    db.session.commit()

    try:
        result = drafted_practices_in_window(start, weeks=2)
        assert [p.id for p in result] == [inside.id], "a draft inside the window must be returned"
    finally:
        _delete_practices_in_slots([inside_slot])


def test_drafted_practices_in_window_excludes_published_practices(db_session):
    # This is the exact case the reviewer proved unprotected: a published
    # (non-draft) practice sitting inside the window must never come back
    # from this query, even though its date matches every other criterion.
    start = date(2099, 3, 2)
    draft_slot = datetime(2099, 3, 10, 18, 0)
    published_slot = datetime(2099, 3, 12, 18, 0)
    draft = Practice(
        date=draft_slot, day_of_week="Tuesday", is_draft=True, logistics_notes=_TEST_NOTE
    )
    published = Practice(
        date=published_slot, day_of_week="Thursday", is_draft=False, logistics_notes=_TEST_NOTE
    )
    db.session.add_all([draft, published])
    db.session.commit()

    try:
        result = drafted_practices_in_window(start, weeks=2)
        assert [p.id for p in result] == [draft.id], (
            "a published (non-draft) practice inside the window must be excluded"
        )
    finally:
        _delete_practices_in_slots([draft_slot, published_slot])


def test_drafted_practices_in_window_excludes_drafts_before_start_date(db_session):
    start = date(2099, 3, 2)
    before_slot = datetime(2099, 3, 1, 12, 0)  # the day before start_date
    inside_slot = datetime(2099, 3, 10, 18, 0)
    before = Practice(
        date=before_slot, day_of_week="Sunday", is_draft=True, logistics_notes=_TEST_NOTE
    )
    inside = Practice(
        date=inside_slot, day_of_week="Tuesday", is_draft=True, logistics_notes=_TEST_NOTE
    )
    db.session.add_all([before, inside])
    db.session.commit()

    try:
        result = drafted_practices_in_window(start, weeks=2)
        assert [p.id for p in result] == [inside.id], "a draft before start_date must be excluded"
    finally:
        _delete_practices_in_slots([before_slot, inside_slot])


def test_drafted_practices_in_window_excludes_drafts_after_window_end(db_session):
    start = date(2099, 3, 2)
    weeks = 2
    inside_slot = datetime(2099, 3, 10, 18, 0)
    # A full day past the 2-week horizon (start + 14 days = 2099-03-16), so
    # the exclusion doesn't depend on time-of-day boundary semantics.
    after_slot = datetime(2099, 3, 17, 12, 0)
    inside = Practice(
        date=inside_slot, day_of_week="Tuesday", is_draft=True, logistics_notes=_TEST_NOTE
    )
    after = Practice(
        date=after_slot, day_of_week="Wednesday", is_draft=True, logistics_notes=_TEST_NOTE
    )
    db.session.add_all([inside, after])
    db.session.commit()

    try:
        result = drafted_practices_in_window(start, weeks=weeks)
        assert [p.id for p in result] == [inside.id], (
            "a draft past the window's horizon must be excluded"
        )
    finally:
        _delete_practices_in_slots([inside_slot, after_slot])


def test_drafted_practices_in_window_orders_by_date(db_session):
    start = date(2099, 3, 2)
    # Created out of chronological order so a passing test can only mean the
    # function actually orders by date, not by creation/insertion order.
    middle_slot = datetime(2099, 3, 10, 18, 0)
    latest_slot = datetime(2099, 3, 12, 18, 0)
    earliest_slot = datetime(2099, 3, 3, 18, 0)
    middle = Practice(
        date=middle_slot, day_of_week="Tuesday", is_draft=True, logistics_notes=_TEST_NOTE
    )
    latest = Practice(
        date=latest_slot, day_of_week="Thursday", is_draft=True, logistics_notes=_TEST_NOTE
    )
    earliest = Practice(
        date=earliest_slot, day_of_week="Tuesday", is_draft=True, logistics_notes=_TEST_NOTE
    )
    db.session.add_all([middle, latest, earliest])
    db.session.commit()

    try:
        result = drafted_practices_in_window(start, weeks=2)
        assert [p.id for p in result] == [earliest.id, middle.id, latest.id], (
            "results must be ordered by date, not creation order"
        )
    finally:
        _delete_practices_in_slots([middle_slot, latest_slot, earliest_slot])
