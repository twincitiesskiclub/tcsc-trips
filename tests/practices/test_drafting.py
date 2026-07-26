"""Draft block generation — idempotency and month-tail continuity are the point.

The window is an explicit [start_date, end_date] range (see
end_of_next_month): the old weeks-count window was normalised back to the
Monday of start_date's week, which silently shortened the forward window and
left the tail of most months undrafted. The twelve-consecutive-runs test at
the bottom is the guard against that bug recurring.
"""

from datetime import date, datetime, timedelta

import pytest

from app import create_app
from app.models import AppConfig, db
from app.practices.drafting import (
    drafted_practices_in_window,
    end_of_next_month,
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


def _save_restore_practice_days(value):
    """Save and restore the real `practice_days` AppConfig row.

    This is the real local dev database. An unconditional delete on teardown
    would silently wipe a value a human (or another script) had seeded.
    Capture whatever was there before the test (if anything) and put it back
    exactly afterward, deleting only if there was no row to begin with --
    never assume delete is the correct restore.
    """
    db.session.rollback()
    existing = AppConfig.query.filter_by(key="practice_days").first()
    had_row = existing is not None
    original = (
        (existing.value, existing.description, existing.category)
        if had_row else None
    )

    if value is None:
        AppConfig.query.filter_by(key="practice_days").delete()
    else:
        AppConfig.set(
            key="practice_days", value=value,
            description="test", category="practices",
        )
    db.session.commit()
    yield
    db.session.rollback()
    if had_row:
        stored_value, description, category = original
        AppConfig.set(key="practice_days", value=stored_value,
                      description=description, category=category)
    else:
        AppConfig.query.filter_by(key="practice_days").delete()
    db.session.commit()


@pytest.fixture()
def practice_days(db_session):
    yield from _save_restore_practice_days([
        {"day": "tuesday", "time": "18:15", "active": True},
        {"day": "thursday", "time": "18:15", "active": True},
        {"day": "thursday", "time": "19:20", "active": True},
        {"day": "sunday", "time": "09:00", "active": False},
    ])


@pytest.fixture()
def practice_days_continuity(db_session):
    """Tue/Thu/Sat at 06:45 — a time no other suite uses, so the continuity
    test's cleanup-by-exact-datetime can never touch another test's rows."""
    yield from _save_restore_practice_days([
        {"day": "tuesday", "time": "06:45", "active": True},
        {"day": "thursday", "time": "06:45", "active": True},
        {"day": "saturday", "time": "06:45", "active": True},
    ])


@pytest.fixture()
def no_practice_days_row(db_session):
    """Force the no-config-row state (what dev and prod look like today)."""
    yield from _save_restore_practice_days(None)


def test_expected_slots_covers_active_days_only(practice_days):
    slots = expected_slots(date(2026, 8, 3), date(2026, 8, 9))  # Mon..Sun
    assert slots == [
        datetime(2026, 8, 4, 18, 15),
        datetime(2026, 8, 6, 18, 15),
        datetime(2026, 8, 6, 19, 20),
    ], "inactive days must be skipped and times honoured"


def test_expected_slots_excludes_dates_before_start_date(practice_days):
    # Wed Aug 5, 2026: the Tuesday slot (Aug 4) is earlier in the same week
    # and must not appear — the contract is "no slot earlier than start_date."
    slots = expected_slots(date(2026, 8, 5), date(2026, 8, 9))
    assert slots == [
        datetime(2026, 8, 6, 18, 15),
        datetime(2026, 8, 6, 19, 20),
    ], "slots before start_date must be excluded"


def test_expected_slots_end_date_is_inclusive(practice_days):
    # Thu Aug 6 IS the end date; its slots must still be produced. The old
    # weeks-window bug was exactly this shape: a window that quietly stopped
    # short of the dates a human would say it covered.
    slots = expected_slots(date(2026, 8, 3), date(2026, 8, 6))
    assert slots == [
        datetime(2026, 8, 4, 18, 15),
        datetime(2026, 8, 6, 18, 15),
        datetime(2026, 8, 6, 19, 20),
    ], "a slot falling on end_date itself must be included"


def test_expected_slots_excludes_dates_after_end_date(practice_days):
    slots = expected_slots(date(2026, 8, 3), date(2026, 8, 5))
    assert slots == [
        datetime(2026, 8, 4, 18, 15),
    ], "slots after end_date must be excluded"


def test_end_of_next_month_spans_year_boundaries():
    assert end_of_next_month(date(2026, 8, 1)) == date(2026, 9, 30)
    assert end_of_next_month(date(2026, 8, 31)) == date(2026, 9, 30)
    assert end_of_next_month(date(2026, 10, 1)) == date(2026, 11, 30)
    assert end_of_next_month(date(2026, 11, 1)) == date(2026, 12, 31)
    assert end_of_next_month(date(2026, 12, 1)) == date(2027, 1, 31)
    # Next month is February — leap and non-leap.
    assert end_of_next_month(date(2027, 1, 15)) == date(2027, 2, 28)
    assert end_of_next_month(date(2028, 1, 15)) == date(2028, 2, 29)


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
    slots = expected_slots(date(2026, 8, 3), date(2026, 8, 16))
    try:
        created = generate_draft_block(date(2026, 8, 3), date(2026, 8, 16))
        assert len(created) == 6
        assert all(p.is_draft is True for p in created)
        assert all(p.leads_needed == 2 for p in created)
    finally:
        _delete_practices_in_slots(slots)


def test_generate_is_idempotent(practice_days):
    slots = expected_slots(date(2026, 8, 3), date(2026, 8, 16))
    try:
        first = generate_draft_block(date(2026, 8, 3), date(2026, 8, 16))
        second = generate_draft_block(date(2026, 8, 3), date(2026, 8, 16))

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
    slots = expected_slots(date(2026, 8, 3), date(2026, 8, 9))
    existing = Practice(
        date=datetime(2026, 8, 4, 18, 15),
        day_of_week="Tuesday",
        is_draft=False,
    )
    db.session.add(existing)
    db.session.commit()

    try:
        created = generate_draft_block(date(2026, 8, 3), date(2026, 8, 9))
        assert len(created) == 2, "must not duplicate an already-published practice"
        assert Practice.query.filter_by(date=datetime(2026, 8, 4, 18, 15)).count() == 1
    finally:
        _delete_practices_in_slots(slots)


# -----------------------------------------------------------------------
# Twelve consecutive monthly bootstrap runs — the continuity property.
#
# The bug this guards against: the old window was `weeks=4` normalised back
# to the Monday of start_date's week, so a run on the 1st covered only
# 28 - weekday(1st) days forward, and the tail of most months was NEVER
# drafted by any run (the next run started at the next 1st and never looked
# back). Measured before the fix: 15 of 91 Tue/Thu/Sat slots over 8 months
# simply never existed as rows.
#
# The fix drafts through the end of NEXT month on every run, so consecutive
# runs overlap by a whole month and idempotency absorbs the overlap. The
# property asserted here — no configured slot in the spanned period is
# skipped, ever — is the entire reason the feature can promise availability
# is collected for every practice.
# -----------------------------------------------------------------------


def test_twelve_consecutive_monthly_runs_skip_no_configured_slot(practice_days_continuity):
    starts = [date(2099, month, 1) for month in range(1, 13)]
    final_end = end_of_next_month(starts[-1])  # 2100-01-31

    # Independently enumerate every configured slot in the spanned period —
    # deliberately NOT via expected_slots(), so a bug there can't hide.
    expected = []
    day = starts[0]
    while day <= final_end:
        if day.weekday() in (1, 3, 5):  # Tue/Thu/Sat per the fixture
            expected.append(datetime(day.year, day.month, day.day, 6, 45))
        day += timedelta(days=1)
    assert len(expected) > 150, "sanity: a year of Tue/Thu/Sat is ~170 slots"

    try:
        for start in starts:
            generate_draft_block(start, end_of_next_month(start))

        drafted = {
            row.date
            for row in Practice.query.with_entities(Practice.date)
            .filter(Practice.date.in_(expected))
            .all()
        }
        missing = sorted(set(expected) - drafted)
        assert missing == [], (
            f"{len(missing)} configured slot(s) were never drafted by any of "
            f"twelve consecutive monthly runs — first few: {missing[:6]}"
        )
        # And the month-long overlap must not create duplicates.
        assert Practice.query.filter(Practice.date.in_(expected)).count() == len(expected), (
            "overlapping monthly runs must never double-draft a slot"
        )
    finally:
        _delete_practices_in_slots(expected)


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
        result = drafted_practices_in_window(start, date(2099, 3, 16))
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
        result = drafted_practices_in_window(start, date(2099, 3, 16))
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
        result = drafted_practices_in_window(start, date(2099, 3, 16))
        assert [p.id for p in result] == [inside.id], "a draft before start_date must be excluded"
    finally:
        _delete_practices_in_slots([before_slot, inside_slot])


def test_drafted_practices_in_window_includes_end_date_and_excludes_beyond(db_session):
    start = date(2099, 3, 2)
    end = date(2099, 3, 16)
    on_end_slot = datetime(2099, 3, 16, 18, 0)  # ON the end date — inclusive
    after_slot = datetime(2099, 3, 17, 12, 0)
    on_end = Practice(
        date=on_end_slot, day_of_week="Monday", is_draft=True, logistics_notes=_TEST_NOTE
    )
    after = Practice(
        date=after_slot, day_of_week="Tuesday", is_draft=True, logistics_notes=_TEST_NOTE
    )
    db.session.add_all([on_end, after])
    db.session.commit()

    try:
        result = drafted_practices_in_window(start, end)
        assert [p.id for p in result] == [on_end.id], (
            "a draft on end_date must be included; one past it must be excluded"
        )
    finally:
        _delete_practices_in_slots([on_end_slot, after_slot])


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
        result = drafted_practices_in_window(start, date(2099, 3, 16))
        assert [p.id for p in result] == [earliest.id, middle.id, latest.id], (
            "results must be ordered by date, not creation order"
        )
    finally:
        _delete_practices_in_slots([middle_slot, latest_slot, earliest_slot])
