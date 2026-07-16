from datetime import date
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import DBAPIError

from app import create_app
from app.models import db
from migrations.versions import d8b2c6f4a901_add_practice_summary_posts as revision


@pytest.fixture
def app():
    application = create_app()
    application.config.update(TESTING=True, SECRET_KEY="test-secret-key")
    return application


@pytest.fixture
def db_session(app):
    with app.app_context():
        yield db


def _create_legacy_practices_table(connection):
    connection.exec_driver_sql("""
        CREATE TABLE practices (
            id INTEGER PRIMARY KEY,
            date TIMESTAMP NOT NULL,
            slack_coach_summary_ts VARCHAR(50),
            slack_weekly_summary_ts VARCHAR(50)
        )
    """)


def test_upgrade_backfills_one_identity_per_linked_week_and_surface_and_downgrades(
    db_session,
    monkeypatch,
):
    schema = f"practice_summary_{uuid4().hex}"
    connection = db_session.engine.connect()
    transaction = connection.begin()
    try:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')
        _create_legacy_practices_table(connection)
        connection.exec_driver_sql("""
            INSERT INTO practices (
                id,
                date,
                slack_coach_summary_ts,
                slack_weekly_summary_ts
            ) VALUES
                (1, '2026-07-13 18:00', 'coach-1', 'public-1'),
                (2, '2026-07-15 18:00', 'coach-1', 'public-1'),
                (3, '2026-07-20 18:00', 'coach-2', NULL),
                (4, '2026-07-22 18:00', NULL, 'public-2')
        """)

        context = MigrationContext.configure(connection)
        monkeypatch.setattr(revision, "op", Operations(context))
        revision.upgrade()

        rows = connection.exec_driver_sql("""
            SELECT week_start, surface, channel_id, message_ts
            FROM practice_summary_posts
            ORDER BY week_start, surface
        """).all()
        assert rows == [
            (date(2026, 7, 13), "coach_summary", None, "coach-1"),
            (date(2026, 7, 13), "weekly_summary", None, "public-1"),
            (date(2026, 7, 20), "coach_summary", None, "coach-2"),
            (date(2026, 7, 20), "weekly_summary", None, "public-2"),
        ]

        revision.downgrade()
        assert not inspect(connection).has_table(
            "practice_summary_posts",
            schema=schema,
        )
    finally:
        transaction.rollback()
        connection.close()


def test_upgrade_rejects_conflicting_legacy_summary_timestamps(
    db_session,
    monkeypatch,
):
    schema = f"practice_summary_conflict_{uuid4().hex}"
    connection = db_session.engine.connect()
    transaction = connection.begin()
    try:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')
        _create_legacy_practices_table(connection)
        connection.exec_driver_sql("""
            INSERT INTO practices (
                id,
                date,
                slack_weekly_summary_ts
            ) VALUES
                (1, '2026-07-13 18:00', 'public-1'),
                (2, '2026-07-15 18:00', 'public-2')
        """)

        context = MigrationContext.configure(connection)
        monkeypatch.setattr(revision, "op", Operations(context))
        with pytest.raises(
            DBAPIError,
            match="conflicting legacy practice summary timestamps",
        ):
            revision.upgrade()
    finally:
        transaction.rollback()
        connection.close()
