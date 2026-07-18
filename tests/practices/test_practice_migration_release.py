from datetime import date
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from tests._db_guard import is_local_db
from tests.practices.migration_test_support import (
    create_exact_summary_orphan,
    summary_catalog_snapshot,
)


ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT / "scripts" / "release.sh"
RELEASE_TIMEOUT_SECONDS = 30
E36 = "e36bbec59bde"
D8 = "d8b2c6f4a901"
EXPECTED_C4_COLUMNS = {
    ("practice_activities", "default_plan_reactions"),
    ("practice_types", "default_plan_reactions"),
    ("practices", "plan_reactions"),
    ("practices", "slack_session_emoji"),
}


@pytest.fixture(scope="module")
def engine():
    database_url = os.environ["DATABASE_URL"]
    assert is_local_db(database_url), "release tests require local PostgreSQL"
    local_engine = create_engine(database_url)
    yield local_engine
    local_engine.dispose()


@pytest.fixture
def release_schema(engine):
    schema = f"practice_release_{uuid4().hex}"
    with engine.begin() as connection:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    try:
        yield schema
    finally:
        with engine.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')


def _use_schema(connection, schema: str) -> None:
    connection.exec_driver_sql(f'SET search_path TO "{schema}"')


def _create_e36_baseline(connection, *, conflicting: bool) -> None:
    connection.exec_driver_sql("""
        CREATE TABLE alembic_version (
            version_num VARCHAR(32) NOT NULL,
            CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
        )
    """)
    connection.exec_driver_sql(
        "INSERT INTO alembic_version VALUES ('e36bbec59bde')"
    )
    connection.exec_driver_sql(
        "CREATE TABLE practice_activities (id INTEGER PRIMARY KEY)"
    )
    connection.exec_driver_sql("""
        CREATE TABLE practice_types (
            id INTEGER PRIMARY KEY,
            has_intervals BOOLEAN NOT NULL
        )
    """)
    connection.exec_driver_sql("""
        CREATE TABLE practices (
            id INTEGER PRIMARY KEY,
            date TIMESTAMP NOT NULL,
            slack_coach_summary_ts VARCHAR(50),
            slack_weekly_summary_ts VARCHAR(50)
        )
    """)
    connection.exec_driver_sql("""
        CREATE TABLE practice_types_junction (
            practice_id INTEGER NOT NULL,
            type_id INTEGER NOT NULL
        )
    """)
    connection.exec_driver_sql(
        "INSERT INTO practice_activities VALUES (1)"
    )
    connection.exec_driver_sql(
        "INSERT INTO practice_types VALUES (10, TRUE), (20, FALSE)"
    )
    second_public = "public-2" if conflicting else "public-1"
    connection.execute(text("""
        INSERT INTO practices (
            id, date, slack_coach_summary_ts, slack_weekly_summary_ts
        ) VALUES
            (1, '2026-07-13 18:00', 'coach-1', 'public-1'),
            (2, '2026-07-15 18:00', 'coach-1', :second_public)
    """), {"second_public": second_public})
    connection.exec_driver_sql(
        "INSERT INTO practice_types_junction VALUES (1, 10), (2, 20)"
    )
    create_exact_summary_orphan(connection)


def _schema_database_url(schema: str) -> str:
    url = make_url(os.environ["DATABASE_URL"])
    scoped = url.update_query_dict({
        "options": f"-csearch_path={schema}",
    })
    return scoped.render_as_string(hide_password=False)


def _run_release(schema: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.update({
        "PATH": (
            f"{Path(sys.executable).parent}{os.pathsep}"
            f"{environment['PATH']}"
        ),
        "DATABASE_URL": _schema_database_url(schema),
        "FLASK_APP": "app:create_app",
        "FLASK_ENV": "testing",
        "FLASK_SECRET_KEY": "release-lifecycle-secret",
        "STRIPE_SECRET_KEY": "sk_test_release_lifecycle",
        "TCSC_MIGRATION_ONLY": "0",
        "SLACK_BOT_TOKEN": "must-be-cleared",
        "SLACK_APP_TOKEN": "must-be-cleared",
        "SLACK_SIGNING_SECRET": "must-be-cleared",
        "SLACK_USER_TOKEN": "",
        "SLACK_WEBHOOK_URL": "",
        "SLACK_ADMIN_TOKEN": "",
        "SLACK_YOUR_COOKIE": "",
        "SLACK_YOUR_X_ID": "",
        "RENDER": "",
    })
    return subprocess.run(
        ["bash", str(RELEASE)],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=RELEASE_TIMEOUT_SECONDS,
    )


def _revision(connection) -> str:
    return connection.exec_driver_sql(
        "SELECT version_num FROM alembic_version"
    ).scalar_one()


def _c4_columns(connection) -> set[tuple[str, str]]:
    rows = connection.execute(text("""
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND (table_name, column_name) IN (
            ('practice_activities', 'default_plan_reactions'),
            ('practice_types', 'default_plan_reactions'),
            ('practices', 'plan_reactions'),
            ('practices', 'slack_session_emoji')
          )
    """)).all()
    return {tuple(row) for row in rows}


def test_release_lifecycle_upgrades_e36_orphan_to_d8_without_consumers(
    engine, release_schema,
):
    with engine.begin() as connection:
        _use_schema(connection, release_schema)
        _create_e36_baseline(connection, conflicting=False)
        baseline = summary_catalog_snapshot(connection)
        assert _revision(connection) == E36
        assert _c4_columns(connection) == set()
        assert baseline["row_count"] == 0
        baseline_defaults = {row[1]: row[6] for row in baseline["columns"]}
        assert baseline_defaults["created_at"] is None
        assert baseline_defaults["updated_at"] is None

    result = _run_release(release_schema)

    assert result.returncode == 0, result.stdout + result.stderr
    output = result.stdout + result.stderr
    assert "Running upgrade e36bbec59bde -> c4f1a8e2d9b7" in output
    assert "Running upgrade c4f1a8e2d9b7 -> d8b2c6f4a901" in output
    assert "=== Release tasks completed ===" in output
    assert "APScheduler started successfully" not in output
    assert "Slack Bolt enabled" not in output
    assert "Socket Mode" not in output
    with engine.connect() as connection:
        _use_schema(connection, release_schema)
        assert _revision(connection) == D8
        assert _c4_columns(connection) == EXPECTED_C4_COLUMNS
        after = summary_catalog_snapshot(connection)
        defaults = {row[1]: row[6] for row in after["columns"]}
        assert defaults["created_at"] == "now()"
        assert defaults["updated_at"] == "now()"
        assert connection.exec_driver_sql("""
            SELECT week_start, surface, channel_id, message_ts
            FROM practice_summary_posts
            ORDER BY surface
        """).all() == [
            (date(2026, 7, 13), "coach_summary", None, "coach-1"),
            (date(2026, 7, 13), "weekly_summary", None, "public-1"),
        ]


def test_release_lifecycle_conflict_rolls_back_c4_and_restores_orphan(
    engine, release_schema,
):
    with engine.begin() as connection:
        _use_schema(connection, release_schema)
        _create_e36_baseline(connection, conflicting=True)
        baseline = summary_catalog_snapshot(connection)
        assert _revision(connection) == E36
        assert _c4_columns(connection) == set()

    result = _run_release(release_schema)

    assert result.returncode != 0
    assert "conflicting legacy practice summary timestamps" in (
        result.stdout + result.stderr
    )
    with engine.connect() as connection:
        _use_schema(connection, release_schema)
        assert _revision(connection) == E36
        assert _c4_columns(connection) == set()
        restored = summary_catalog_snapshot(connection)
        assert restored == baseline
        defaults = {
            row[1]: row[6]
            for row in restored["columns"]
        }
        assert defaults["created_at"] is None
        assert defaults["updated_at"] is None
