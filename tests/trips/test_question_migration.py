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
followup_migration = importlib.import_module(
    "migrations.versions.6c2f8a4d9e10_editable_trip_builtin_followups")


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


def test_add_followups_preserves_edits_order_and_missing_builtins():
    carpool, region, dietary, tent = default_builtin_questions()
    custom = {"key": "note", "label": "Note", "type": "text", "required": False}
    legacy = [custom, carpool | {"followups": {
        "seats": {"label": "Passenger seats?"}, "bikes": {"enabled": False},
    }}, region, {key: value for key, value in dietary.items() if key != "followups"}, tent]
    original = deepcopy(legacy)

    migrated = followup_migration.add_followups(legacy)

    assert legacy == original
    assert [q.get("builtin", q.get("key")) for q in migrated] == [
        "note", "carpool", "region_code", "dietary", "tent"]
    assert migrated[1]["followups"]["seats"] == {
        "label": "Passenger seats?", "help_text": "", "enabled": True}
    assert migrated[1]["followups"]["bikes"] == carpool["followups"]["bikes"] | {"enabled": False}
    assert migrated[1]["followups"]["hitch"] == carpool["followups"]["hitch"]
    assert migrated[3] == dietary
    assert followup_migration.add_followups(migrated) == migrated
    assert followup_migration.add_followups([custom, tent]) == [custom, tent]
    assert followup_migration.add_followups([]) == []
    assert followup_migration.add_followups(None) is None


def test_followup_migration_upgrade_and_downgrade_on_postgres(db_session):
    schema = "trip_followup_migration_" + uuid4().hex
    defaults = default_builtin_questions()
    legacy = [{key: value for key, value in q.items() if key != "followups"} for q in defaults]
    edited = deepcopy(defaults)
    edited[0]["followups"]["bikes"]["enabled"] = False
    edited[2]["followups"]["other"].update(label="Other needs?", help_text="Tell the cook.")
    table = sa.table("trips", sa.column("id", sa.Integer()),
                     sa.column("custom_questions", sa.JSON()))
    with db.engine.connect() as connection, connection.begin() as transaction:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')
        connection.exec_driver_sql("CREATE TABLE trips (id INTEGER PRIMARY KEY, custom_questions JSON)")
        connection.execute(table.insert(), [
            {"id": 1, "custom_questions": legacy},
            {"id": 2, "custom_questions": edited},
            {"id": 3, "custom_questions": None},
            {"id": 4, "custom_questions": []},
        ])

        def stored():
            return list(connection.execute(sa.select(table.c.custom_questions).order_by(table.c.id)).scalars())

        with Operations.context(MigrationContext.configure(connection)):
            followup_migration.upgrade()
            assert stored() == [defaults, edited, None, []]
            followup_migration.upgrade()
            assert stored() == [defaults, edited, None, []]
            followup_migration.downgrade()
            assert stored() == [legacy, legacy, None, []]
            followup_migration.downgrade()
            assert stored() == [legacy, legacy, None, []]
            followup_migration.upgrade()
            assert stored() == [defaults, defaults, None, []]
        transaction.rollback()
