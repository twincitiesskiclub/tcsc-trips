"""The conversion SQL, run against real PostgreSQL time zone rules."""
import importlib.util
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "migrations/versions/c7e1a9d3f5b2_event_times_to_utc.py"
)


def _migration():
    spec = importlib.util.spec_from_file_location("event_times_to_utc", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(db_session, expression, value):
    sql = f"SELECT {expression}"
    return db_session.session.execute(text(sql), {"v": value}).scalar()


def test_cdt_value_converts_with_five_hours(db_session):
    m = _migration()
    expr = m.central_to_utc_sql("CAST(:v AS timestamp)")
    assert _run(db_session, expr, datetime(2026, 10, 24, 9, 0)) == datetime(2026, 10, 24, 14, 0)


def test_cst_value_converts_with_six_hours(db_session):
    m = _migration()
    expr = m.central_to_utc_sql("CAST(:v AS timestamp)")
    assert _run(db_session, expr, datetime(2026, 1, 19, 12, 0)) == datetime(2026, 1, 19, 18, 0)


def test_downgrade_expression_restores_the_original(db_session):
    m = _migration()
    expr = m.utc_to_central_sql(m.central_to_utc_sql("CAST(:v AS timestamp)"))
    for value in (datetime(2026, 10, 22, 23, 59), datetime(2025, 12, 10, 0, 0)):
        assert _run(db_session, expr, value) == value


def test_migration_follows_the_previous_head():
    assert _migration().down_revision == "9b2e6d4f1a37"
