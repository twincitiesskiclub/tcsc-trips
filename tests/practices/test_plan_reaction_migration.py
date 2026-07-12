from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import inspect

from app import create_app
from app.models import db
from migrations.versions import c4f1a8e2d9b7_add_practice_plan_reactions as revision


@pytest.fixture
def app():
    application = create_app()
    application.config.update(TESTING=True, SECRET_KEY="test-secret-key")
    return application


@pytest.fixture
def db_session(app):
    with app.app_context():
        yield db


def _column_names(connection, table, schema):
    return {
        item["name"]
        for item in inspect(connection).get_columns(table, schema=schema)
    }


def test_upgrade_backfills_intervals_and_downgrade_removes_columns(
    db_session, monkeypatch
):
    schema = f"plan_reaction_{uuid4().hex}"
    connection = db_session.engine.connect()
    transaction = connection.begin()
    try:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')
        connection.exec_driver_sql(
            "CREATE TABLE practice_activities (id INTEGER PRIMARY KEY)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE practice_types ("
            "id INTEGER PRIMARY KEY, has_intervals BOOLEAN NOT NULL)"
        )
        connection.exec_driver_sql("CREATE TABLE practices (id INTEGER PRIMARY KEY)")
        connection.exec_driver_sql(
            "CREATE TABLE practice_types_junction ("
            "practice_id INTEGER NOT NULL, type_id INTEGER NOT NULL)"
        )
        connection.exec_driver_sql("INSERT INTO practice_activities VALUES (1)")
        connection.exec_driver_sql(
            "INSERT INTO practice_types VALUES (10, TRUE), (20, FALSE)"
        )
        connection.exec_driver_sql("INSERT INTO practices VALUES (100), (200)")
        connection.exec_driver_sql(
            "INSERT INTO practice_types_junction VALUES (100, 10), (200, 20)"
        )

        context = MigrationContext.configure(connection)
        monkeypatch.setattr(revision, "op", Operations(context))
        revision.upgrade()

        type_rows = dict(
            connection.exec_driver_sql(
                "SELECT id, default_plan_reactions FROM practice_types ORDER BY id"
            ).all()
        )
        practice_rows = dict(
            connection.exec_driver_sql(
                "SELECT id, plan_reactions FROM practices ORDER BY id"
            ).all()
        )
        evergreen = [
            {
                "emoji": "evergreen_tree",
                "label": "Endurance instead of intervals",
            }
        ]
        assert type_rows == {10: evergreen, 20: []}
        assert practice_rows == {100: evergreen, 200: []}
        assert "default_plan_reactions" in _column_names(
            connection, "practice_activities", schema
        )
        assert "slack_session_emoji" in _column_names(
            connection, "practices", schema
        )

        revision.downgrade()
        assert "default_plan_reactions" not in _column_names(
            connection, "practice_activities", schema
        )
        assert "default_plan_reactions" not in _column_names(
            connection, "practice_types", schema
        )
        assert "plan_reactions" not in _column_names(
            connection, "practices", schema
        )
        assert "slack_session_emoji" not in _column_names(
            connection, "practices", schema
        )
    finally:
        transaction.rollback()
        connection.close()
