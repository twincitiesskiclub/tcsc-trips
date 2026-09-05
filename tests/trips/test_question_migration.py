from copy import deepcopy
import importlib
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa

from app.models import db
from app.trips.questions import default_builtin_questions, get_template

migration = importlib.import_module(
    "migrations.versions.9f3a1c7e5b20_editable_builtin_trip_questions")


def test_prepend_preserves_north_shore_and_existing_builtins():
    legacy = deepcopy(get_template("north_shore")["custom_questions"][4:])
    migrated = migration.prepend_builtins(legacy)
    assert migrated == default_builtin_questions() + legacy
    assert migration.prepend_builtins(migrated) == migrated
    edited = default_builtin_questions()[0] | {"enabled": False, "label": "Edited carpool"}
    partial = [legacy[0], edited, *legacy[1:]]
    assert migration.prepend_builtins(partial) == default_builtin_questions()[1:] + partial
    assert migration.prepend_builtins(None) == default_builtin_questions()


def test_migration_upgrade_idempotent_and_downgrade_on_postgres(db_session):
    # Exercise the actual Alembic functions without touching any dev trip.
    schema = "trip_question_migration_" + uuid4().hex
    legacy = deepcopy(get_template("north_shore")["custom_questions"][4:])
    edited = default_builtin_questions()[0] | {"enabled": False}
    partial = [legacy[0], edited, *legacy[1:]]
    table = sa.table("trips", sa.column("id", sa.Integer()),
                     sa.column("custom_questions", sa.JSON()))
    with db.engine.connect() as connection, connection.begin() as transaction:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')
        connection.exec_driver_sql("CREATE TABLE trips (id INTEGER PRIMARY KEY, custom_questions JSON)")
        connection.execute(table.insert(), [
            {"id": 1, "custom_questions": legacy},
            {"id": 2, "custom_questions": partial},
            {"id": 3, "custom_questions": None},
        ])

        def stored():
            return list(connection.execute(sa.select(table.c.custom_questions).order_by(table.c.id)).scalars())

        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            expected = [default_builtin_questions() + legacy,
                        default_builtin_questions()[1:] + partial,
                        default_builtin_questions()]
            assert stored() == expected
            migration.upgrade()
            assert stored() == expected
            migration.downgrade()
            assert stored() == [legacy, legacy, []]
            migration.downgrade()
            assert stored() == [legacy, legacy, []]
            migration.upgrade()
            assert stored()[0] == expected[0]
        transaction.rollback()  # includes the isolated schema
