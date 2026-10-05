"""Draft block generation: slot expansion and idempotency."""

from datetime import date, datetime

import pytest

from app import create_app
from app.models import AppConfig, db
from app.practices.drafting import (
    expected_slots,
    generate_draft_block,
)
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


def test_default_practice_days_include_saturday(no_practice_days_row):
    """With no practice_days row (the state of dev AND prod today), drafting
    must cover the same Tue/Thu/Sat schedule the coach post renders — a
    Tue/Thu-only drafting default meant Saturday practices were never drafted
    while the coach post showed a permanent empty Saturday placeholder,
    inviting a duplicate on top of a draft."""
    slots = expected_slots(date(2026, 8, 3), date(2026, 8, 9))  # Mon..Sun
    assert slots == [
        datetime(2026, 8, 4, 18, 0),
        datetime(2026, 8, 6, 18, 0),
        datetime(2026, 8, 8, 9, 0),
    ], "the built-in default must draft Saturday 09:00, matching the coach post"


def test_default_practice_days_is_one_shared_constant():
    """Every site that defaults `practice_days` must share the ONE source.

    The bug this pins: drafting had its own Tue/Thu copy while the coach
    post, refresh, and the admin settings endpoint each carried a Tue/Thu/Sat
    copy — identical-looking literals that had already drifted.
    """
    from app.practices import drafting
    from app.routes import admin_practices
    from app.slack.practices import coach_review, refresh

    for module in (admin_practices, coach_review, refresh):
        assert module.default_practice_days is drafting.default_practice_days, (
            f"{module.__name__} must import the shared default helper, not carry a copy"
        )

    # bolt_app is the fourth site and was missed by the identity check above,
    # because it imports lazily inside the handler (this file's deliberate
    # style, to avoid import cycles) so there is no module attribute to
    # compare. Asserted on the source instead -- with a positive control, so
    # renaming the helper can't turn this into a vacuous pass.
    import inspect
    from app.slack import bolt_app
    source = inspect.getsource(bolt_app)
    assert "AppConfig.get('practice_days', default_practice_days())" in source, (
        "bolt_app must default practice_days from the shared helper: with no "
        "config row, [] matches no entry and the coach post's Saturday 09:00 "
        "placeholder opens a create modal prefilled 18:00"
    )
    assert "AppConfig.get('practice_days', [])" not in source, (
        "the bare [] default must not come back"
    )


def test_default_practice_days_copies_are_independent():
    """AppConfig.get(key, default) hands the default object itself to the
    caller, so a shared mutable default means one consumer writing
    entry['active'] = False would corrupt the drafting schedule process-wide
    until restart. Each call must return a fresh, independently mutable copy."""
    from app.practices.drafting import default_practice_days

    first = default_practice_days()
    first[0]["active"] = False
    first.append({"day": "monday", "time": "00:00", "active": True})

    second = default_practice_days()
    assert second[0]["active"] is True, "mutating one copy must not leak into the next"
    assert all(entry["day"] != "monday" for entry in second)


def _delete_practices_in_slots(slots):
    """Clean up every Practice row in the given slots, regardless of who
    created it or what any function under test happened to return.

    Scoped-query cleanup instead of tracking returned lists: a returned list
    can't include rows the code under test wrongly created (e.g. a broken
    collision check creating unexpected duplicates), so it can't be trusted
    to enumerate everything that needs deleting. Cleanup must hold even when
    an assertion above it fails and the test never reaches a "success" path
    — hence the rollback first, so a poisoned session can't abort it.

    ORM deletes, never a bulk .delete(): practice deletes must go through
    db.session.delete() so the ORM-level cascades (poll mappings, responses,
    junction rows) fire — a bulk delete skips them and dies on the first FK
    reference, which inside a finally would leak every remaining row into
    the shared dev database with no second cleanup path.
    """
    db.session.rollback()
    for practice in Practice.query.filter(Practice.date.in_(slots)).all():
        db.session.delete(practice)
    db.session.commit()


def test_generate_creates_drafts(practice_days_generate):
    slots = expected_slots(date(2099, 12, 7), date(2099, 12, 20))
    try:
        created = generate_draft_block(date(2099, 12, 7), date(2099, 12, 20))
        assert len(created) == 6
        assert all(p.is_draft is True for p in created)
        assert all(p.leads_needed == 2 for p in created)
    finally:
        _delete_practices_in_slots(slots)


def test_generate_is_idempotent(practice_days_generate):
    slots = expected_slots(date(2099, 12, 7), date(2099, 12, 20))
    try:
        first = generate_draft_block(date(2099, 12, 7), date(2099, 12, 20))
        second = generate_draft_block(date(2099, 12, 7), date(2099, 12, 20))

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


@pytest.fixture()
def practice_days_with_duplicate_entry(db_session):
    """Two config entries with the same day AND time — reachable from the
    admin UI, since update_practice_days does not dedupe.

    Uses the generation suite's reserved 20:05 time rather than 18:15: this
    fixture drives a test that WRITES rows and cleans up by exact datetime.
    """
    yield from _save_restore_practice_days([
        {"day": "tuesday", "time": "20:05", "active": True},
        {"day": "tuesday", "time": "20:05", "active": True},
    ])


@pytest.fixture()
def practice_days_generate(db_session):
    """Config for the tests that actually WRITE practices.

    Deliberately Tue 20:05 + Thu 20:05/21:10 — times no other suite uses —
    because _delete_practices_in_slots sweeps every row at these datetimes
    "regardless of who created it". Paired with the reserved 2099-12 window
    in those tests, that sweep cannot reach a real practice. These tests
    previously ran over 2026-08-03..08-16 at 18:15: real near-term dates, at
    the exact time every other availability suite treats as the club's
    practice slot, so a failing assertion deleted a genuine practice along
    with its RSVPs, leads and junction rows.

    Same shape as the unrestricted `practice_days` fixture (1 Tuesday slot,
    2 Thursday slots, an inactive Sunday) so the counts the tests assert are
    unchanged.
    """
    yield from _save_restore_practice_days([
        {"day": "tuesday", "time": "20:05", "active": True},
        {"day": "thursday", "time": "20:05", "active": True},
        {"day": "thursday", "time": "21:10", "active": True},
        {"day": "sunday", "time": "09:00", "active": False},
    ])


def test_generate_creates_one_draft_for_duplicated_config_entries(
    practice_days_with_duplicate_entry,
):
    """expected_slots yields the duplicated datetime twice; generation must
    still create exactly one row for it — this is the one function whose
    idempotency is load-bearing."""
    slots = expected_slots(date(2099, 12, 7), date(2099, 12, 13))
    assert len(slots) == 2, "sanity: the duplicated config entry reaches the slot list"
    try:
        created = generate_draft_block(date(2099, 12, 7), date(2099, 12, 13))
        assert len(created) == 1
        assert Practice.query.filter(Practice.date.in_(slots)).count() == 1, (
            "a duplicated day+time config entry must not double-draft the slot"
        )
    finally:
        _delete_practices_in_slots(slots)


def test_generate_skips_slots_that_already_have_a_real_practice(practice_days_generate):
    slots = expected_slots(date(2099, 12, 7), date(2099, 12, 13))
    existing = Practice(
        date=datetime(2099, 12, 8, 20, 5),
        day_of_week="Tuesday",
        is_draft=False,
        logistics_notes="TEST drafting collision practice",
    )
    db.session.add(existing)
    db.session.commit()

    try:
        created = generate_draft_block(date(2099, 12, 7), date(2099, 12, 13))
        assert len(created) == 2, "must not duplicate an already-published practice"
        assert Practice.query.filter_by(date=datetime(2099, 12, 8, 20, 5)).count() == 1
    finally:
        _delete_practices_in_slots(slots)


# -----------------------------------------------------------------------
# A bad `time` in the practice_days config used to erase a whole weekday.
#
# expected_slots skipped an unparseable time with one log line, so that day
# vanished from drafting for the entire two-month horizon while the readiness
# digest still reported every surviving draft as ready — nothing anywhere said
# a third of the schedule was missing. The admin UI's <input type="time">
# submits "" whenever the field is cleared, so this was one keystroke away.
# An out-of-range hour was worse: it parsed as ints and then raised when the
# datetime was built, outside any guard, killing the bootstrap job.
# -----------------------------------------------------------------------

@pytest.fixture()
def practice_days_blank_time(db_session):
    yield from _save_restore_practice_days([
        {"day": "tuesday", "time": "", "active": True},
        {"day": "thursday", "time": "18:15", "active": True},
    ])


@pytest.fixture()
def practice_days_out_of_range_time(db_session):
    yield from _save_restore_practice_days([
        {"day": "tuesday", "time": "25:00", "active": True},
        {"day": "thursday", "time": "18:15", "active": True},
    ])


def test_blank_time_falls_back_to_the_default_instead_of_dropping_the_day(
    practice_days_blank_time,
):
    slots = expected_slots(date(2026, 8, 3), date(2026, 8, 9))  # Mon..Sun
    assert slots == [
        datetime(2026, 8, 4, 18, 0),   # Tuesday, defaulted — NOT missing
        datetime(2026, 8, 6, 18, 15),
    ], "a cleared time field must default, not silently erase Tuesday"


def test_out_of_range_time_skips_one_entry_without_killing_the_run(
    practice_days_out_of_range_time,
):
    # The surviving day must still be drafted: the failure is contained to the
    # bad entry rather than raising out of expected_slots.
    slots = expected_slots(date(2026, 8, 3), date(2026, 8, 9))
    assert slots == [datetime(2026, 8, 6, 18, 15)], (
        "an unusable hour must skip its own entry and leave the rest intact"
    )
