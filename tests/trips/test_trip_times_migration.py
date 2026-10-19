"""Trip signup times typed in the plain admin form move from Central to UTC."""
import importlib.util
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

from app.models import Trip, db

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "migrations/versions/f4b8d2a6c1e9_trip_signup_times_to_utc.py"
)


def _migration():
    spec = importlib.util.spec_from_file_location("trip_signup_times_to_utc", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_follows_the_previous_head():
    assert _migration().down_revision == "e3a7c1f9b4d2"


def _trip(slug, signup_start, signup_end):
    trip = Trip(slug=slug, name="tz probe", destination="x", max_participants_standard=1,
                max_participants_extra=0, start_date=datetime(2099, 1, 1), end_date=datetime(2099, 1, 2),
                signup_start=signup_start, signup_end=signup_end, price_low=1, price_high=1,
                status="draft", custom_questions=[])
    db.session.add(trip)
    return trip


def test_upgrade_converts_form_era_rows_only_and_downgrade_restores(db_session):
    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext

    m = _migration()
    _trip("tz-probe-form", datetime(2026, 10, 19, 0, 0), datetime(2026, 12, 1, 9, 0))
    _trip("tz-probe-grid", datetime(2025, 12, 10, 13, 0), datetime(2025, 12, 20, 23, 0))
    db.session.flush()
    conn = db_session.session.connection()
    select = text("SELECT slug, signup_start, signup_end FROM trips"
                  " WHERE slug LIKE 'tz-probe-%' ORDER BY slug")
    operations = Operations(MigrationContext.configure(conn))
    try:
        with Operations.context(operations.migration_context):
            m.upgrade()
            assert [tuple(r) for r in conn.execute(select)] == [
                ("tz-probe-form", datetime(2026, 10, 19, 5, 0), datetime(2026, 12, 1, 15, 0)),
                ("tz-probe-grid", datetime(2025, 12, 10, 13, 0), datetime(2025, 12, 20, 23, 0)),
            ]
            m.downgrade()
            assert [tuple(r) for r in conn.execute(select)] == [
                ("tz-probe-form", datetime(2026, 10, 19, 0, 0), datetime(2026, 12, 1, 9, 0)),
                ("tz-probe-grid", datetime(2025, 12, 10, 13, 0), datetime(2025, 12, 20, 23, 0)),
            ]
    finally:
        # The UPDATE touches real trips rows in the test DB; never let it commit.
        db_session.session.rollback()
