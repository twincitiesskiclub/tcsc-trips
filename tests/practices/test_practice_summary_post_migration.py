from contextlib import contextmanager
from datetime import date
import os
from unittest.mock import Mock
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError

from migrations.versions import (
    d8b2c6f4a901_add_practice_summary_posts as revision,
)
from tests._db_guard import is_local_db
from tests.practices.migration_test_support import (
    create_exact_summary_orphan,
    summary_catalog_snapshot,
)


@pytest.fixture(scope="module")
def engine():
    database_url = os.environ["DATABASE_URL"]
    assert is_local_db(database_url), "migration tests require local PostgreSQL"
    local_engine = create_engine(database_url)
    yield local_engine
    local_engine.dispose()


@contextmanager
def migration_schema(engine, prefix="practice_summary"):
    schema = f"{prefix}_{uuid4().hex}"
    connection = engine.connect()
    transaction = connection.begin()
    try:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')
        yield connection, schema
    finally:
        transaction.rollback()
        connection.close()


@contextmanager
def committed_orphan_migration_schema(engine, prefix="summary_lock"):
    schema = f"{prefix}_{uuid4().hex}"
    with engine.begin() as setup_connection:
        setup_connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        setup_connection.exec_driver_sql(
            f'SET LOCAL search_path TO "{schema}"'
        )
        create_exact_summary_orphan(setup_connection)

    connection = engine.connect()
    transaction = connection.begin()
    try:
        connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')
        yield connection, schema
    finally:
        transaction.rollback()
        connection.close()
        with engine.begin() as cleanup_connection:
            cleanup_connection.exec_driver_sql(
                f'DROP SCHEMA "{schema}" CASCADE'
            )


def configure_revision(connection, monkeypatch):
    context = MigrationContext.configure(connection)
    monkeypatch.setattr(revision, "op", Operations(context))


def create_legacy_practices_table(connection):
    connection.exec_driver_sql("""
        CREATE TABLE practices (
            id INTEGER PRIMARY KEY,
            date TIMESTAMP NOT NULL,
            slack_coach_summary_ts VARCHAR(50),
            slack_weekly_summary_ts VARCHAR(50)
        )
    """)


def _access_exclusive_locks(connection, relation_oid):
    return connection.execute(text("""
        SELECT mode, granted
        FROM pg_locks
        WHERE pid = pg_backend_pid()
          AND relation = :oid
          AND mode = 'AccessExclusiveLock'
    """), {"oid": relation_oid}).all()


def test_upgrade_backfills_one_identity_per_linked_week_and_surface_and_downgrades(
    engine,
    monkeypatch,
):
    with migration_schema(engine) as (connection, schema):
        create_legacy_practices_table(connection)
        connection.exec_driver_sql("""
            INSERT INTO practices (
                id,
                date,
                slack_coach_summary_ts,
                slack_weekly_summary_ts
            ) VALUES
                (1, '2026-07-13 18:00', 'shared-ts', 'public-1'),
                (2, '2026-07-15 18:00', 'shared-ts', 'public-1'),
                (3, '2026-07-20 18:00', 'coach-2', NULL),
                (4, '2026-07-22 18:00', NULL, 'shared-ts')
        """)

        configure_revision(connection, monkeypatch)
        revision.upgrade()

        rows = connection.exec_driver_sql("""
            SELECT week_start, surface, channel_id, message_ts
            FROM practice_summary_posts
            ORDER BY week_start, surface
        """).all()
        assert rows == [
            (date(2026, 7, 13), "coach_summary", None, "shared-ts"),
            (date(2026, 7, 13), "weekly_summary", None, "public-1"),
            (date(2026, 7, 20), "coach_summary", None, "coach-2"),
            (date(2026, 7, 20), "weekly_summary", None, "shared-ts"),
        ]

        revision.downgrade()
        assert not inspect(connection).has_table(
            "practice_summary_posts",
            schema=schema,
        )


def test_upgrade_rejects_conflicting_legacy_summary_timestamps(
    engine,
    monkeypatch,
):
    with migration_schema(engine, "practice_summary_conflict") as (
        connection, _schema,
    ):
        create_legacy_practices_table(connection)
        connection.exec_driver_sql("""
            INSERT INTO practices (
                id,
                date,
                slack_weekly_summary_ts
            ) VALUES
                (1, '2026-07-13 18:00', 'public-1'),
                (2, '2026-07-15 18:00', 'public-2')
        """)

        configure_revision(connection, monkeypatch)
        with pytest.raises(
            DBAPIError,
            match="conflicting legacy practice summary timestamps",
        ):
            revision.upgrade()


def test_upgrade_rejects_one_summary_timestamp_mapped_to_multiple_weeks(
    engine,
    monkeypatch,
):
    with migration_schema(engine, "practice_summary_cross_week_conflict") as (
        connection, _schema,
    ):
        create_legacy_practices_table(connection)
        connection.exec_driver_sql("""
            INSERT INTO practices (
                id,
                date,
                slack_weekly_summary_ts
            ) VALUES
                (1, '2026-07-13 18:00', 'public-source-week'),
                (2, '2026-07-20 18:00', 'public-source-week')
        """)

        configure_revision(connection, monkeypatch)
        with pytest.raises(
            DBAPIError,
            match="conflicting legacy practice summary timestamps",
        ):
            revision.upgrade()


def test_upgrade_without_existing_summary_table_uses_normal_path(
    engine, monkeypatch,
):
    with migration_schema(engine, "summary_normal") as (connection, schema):
        create_legacy_practices_table(connection)
        configure_revision(connection, monkeypatch)

        revision.upgrade()

        assert inspect(connection).has_table(
            "practice_summary_posts", schema=schema
        )
        defaults = {
            row[0]: row[1]
            for row in connection.execute(text("""
                SELECT column_name, column_default
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'practice_summary_posts'
                  AND column_name IN ('created_at', 'updated_at')
            """))
        }
        assert defaults == {"created_at": "now()", "updated_at": "now()"}


def test_existing_orphan_lock_is_access_exclusive(engine):
    with committed_orphan_migration_schema(engine) as (connection, _schema):
        oid = revision._visible_summary_table_oid(connection)
        assert _access_exclusive_locks(connection, oid) == []

        locked_oid = revision._lock_existing_summary_table(connection, oid)

        assert locked_oid == oid
        assert _access_exclusive_locks(connection, oid) == [
            ("AccessExclusiveLock", True),
        ]


def test_upgrade_adopts_exact_empty_orm_orphan_and_backfills(
    engine, monkeypatch,
):
    with migration_schema(engine, "summary_adopt") as (connection, schema):
        create_legacy_practices_table(connection)
        connection.exec_driver_sql("""
            INSERT INTO practices (
                id, date, slack_coach_summary_ts, slack_weekly_summary_ts
            ) VALUES
                (1, '2026-07-13 18:00', 'coach-1', 'public-1'),
                (2, '2026-07-15 18:00', 'coach-1', 'public-1')
        """)
        create_exact_summary_orphan(connection)
        before = summary_catalog_snapshot(connection)
        old_oid = revision._visible_summary_table_oid(connection)
        assert before["row_count"] == 0
        assert before["external_dependency_count"] == 0
        assert dict(
            (row[1], row[6]) for row in before["columns"]
        )["created_at"] is None
        configure_revision(connection, monkeypatch)

        expected_savepoint = connection.begin_nested()
        try:
            connection.exec_driver_sql(
                f'DROP TABLE "{schema}".practice_summary_posts'
            )
            revision.upgrade()
            expected = summary_catalog_snapshot(connection)
        finally:
            expected_savepoint.rollback()

        assert summary_catalog_snapshot(connection) == before
        drop_table = Mock(wraps=revision.op.drop_table)
        monkeypatch.setattr(revision.op, "drop_table", drop_table)
        revision.upgrade()

        after = summary_catalog_snapshot(connection)
        assert revision._visible_summary_table_oid(connection) != old_oid
        assert after == expected
        drop_table.assert_called_once_with(
            revision.SUMMARY_TABLE,
            schema=schema,
        )
        rows = connection.exec_driver_sql("""
            SELECT week_start, surface, channel_id, message_ts
            FROM practice_summary_posts
            ORDER BY surface
        """).all()
        assert rows == [
            (date(2026, 7, 13), "coach_summary", None, "coach-1"),
            (date(2026, 7, 13), "weekly_summary", None, "public-1"),
        ]


def _assert_upgrade_refused_without_mutation(
    connection,
    monkeypatch,
    expected_invariant=None,
):
    before = summary_catalog_snapshot(connection)
    configure_revision(connection, monkeypatch)
    drop_table = Mock(wraps=revision.op.drop_table)
    monkeypatch.setattr(revision.op, "drop_table", drop_table)

    savepoint = connection.begin_nested()
    try:
        with pytest.raises(
            RuntimeError,
            match="practice_summary_posts orphan recovery refused",
        ) as refusal:
            revision.upgrade()
    finally:
        savepoint.rollback()

    allowed_messages = {
        "practice_summary_posts orphan recovery refused: " + invariant
        for invariant in (
            "relation changed before lock",
            "relation could not be locked",
            "relation changed while acquiring lock",
            "locked relation is no longer visible",
            "relation metadata mismatch",
            "column shape mismatch",
            "id serial default mismatch",
            "non-id column default mismatch",
            "owned serial sequence mismatch",
            "constraint mismatch",
            "index mismatch",
            "external dependency mismatch",
            "attached behavior mismatch",
            "publication membership mismatch",
            "table contains rows",
        )
    }
    if expected_invariant is None:
        assert str(refusal.value) in allowed_messages
    else:
        assert str(refusal.value) == (
            "practice_summary_posts orphan recovery refused: "
            + expected_invariant
        )
    drop_table.assert_not_called()
    assert summary_catalog_snapshot(connection) == before


def test_upgrade_refuses_nonempty_orm_orphan_without_mutation(
    engine, monkeypatch,
):
    with migration_schema(engine, "summary_nonempty") as (connection, _schema):
        create_legacy_practices_table(connection)
        create_exact_summary_orphan(connection)
        connection.exec_driver_sql("""
            INSERT INTO practice_summary_posts (
                id, week_start, surface, message_ts, created_at, updated_at
            ) VALUES (
                1, '2026-07-13', 'weekly_summary', 'existing', now(), now()
            )
        """)

        _assert_upgrade_refused_without_mutation(connection, monkeypatch)


def test_upgrade_refuses_noncanonical_nextval_default_without_mutation(
    engine, monkeypatch,
):
    with migration_schema(engine, "summary_default") as (connection, _schema):
        create_legacy_practices_table(connection)
        create_exact_summary_orphan(connection)
        connection.exec_driver_sql("""
            CREATE FUNCTION nextval(regclass, integer)
            RETURNS bigint
            LANGUAGE SQL VOLATILE
            AS 'SELECT pg_catalog.nextval($1) + $2'
        """)
        connection.exec_driver_sql("""
            ALTER TABLE practice_summary_posts ALTER COLUMN id
            SET DEFAULT nextval(
                'practice_summary_posts_id_seq'::regclass,
                0
            )
        """)

        _assert_upgrade_refused_without_mutation(connection, monkeypatch)


def test_upgrade_refuses_partition_child_without_mutation(
    engine, monkeypatch,
):
    with migration_schema(engine, "summary_partition") as (
        connection, _schema,
    ):
        create_legacy_practices_table(connection)
        create_exact_summary_orphan(connection)
        connection.exec_driver_sql("""
            CREATE TABLE summary_partition_parent (
                id INTEGER NOT NULL,
                week_start DATE NOT NULL,
                surface VARCHAR(32) NOT NULL,
                channel_id VARCHAR(50),
                message_ts VARCHAR(50) NOT NULL,
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
            ) PARTITION BY RANGE (week_start)
        """)
        connection.exec_driver_sql("""
            ALTER TABLE summary_partition_parent
            ATTACH PARTITION practice_summary_posts
            FOR VALUES FROM (MINVALUE) TO (MAXVALUE)
        """)

        _assert_upgrade_refused_without_mutation(connection, monkeypatch)


def test_upgrade_refuses_empty_orphan_with_inheritance_child_without_mutation(
    engine,
    monkeypatch,
):
    with migration_schema(engine, "summary_inheritance_child") as (
        connection,
        _schema,
    ):
        create_legacy_practices_table(connection)
        create_exact_summary_orphan(connection)
        connection.exec_driver_sql("""
            CREATE TABLE dependent_summary_child ()
            INHERITS (practice_summary_posts)
        """)
        assert summary_catalog_snapshot(connection)[
            "external_dependency_count"
        ] > 0

        _assert_upgrade_refused_without_mutation(
            connection,
            monkeypatch,
            expected_invariant="external dependency mismatch",
        )


def test_upgrade_refuses_empty_orphan_with_dependent_view_without_mutation(
    engine,
    monkeypatch,
):
    with migration_schema(engine, "summary_dependent_view") as (
        connection,
        _schema,
    ):
        create_legacy_practices_table(connection)
        create_exact_summary_orphan(connection)
        connection.exec_driver_sql("""
            CREATE VIEW dependent_summary_view AS
            SELECT id, week_start
            FROM practice_summary_posts
        """)
        assert summary_catalog_snapshot(connection)[
            "external_dependency_count"
        ] > 0

        _assert_upgrade_refused_without_mutation(
            connection,
            monkeypatch,
            expected_invariant="external dependency mismatch",
        )


def test_upgrade_refuses_empty_orphan_with_inbound_foreign_key_without_mutation(
    engine,
    monkeypatch,
):
    with migration_schema(engine, "summary_inbound_fk") as (
        connection,
        _schema,
    ):
        create_legacy_practices_table(connection)
        create_exact_summary_orphan(connection)
        connection.exec_driver_sql("""
            CREATE TABLE dependent_summary_fk (
                summary_id INTEGER REFERENCES practice_summary_posts(id)
            )
        """)
        assert summary_catalog_snapshot(connection)[
            "external_dependency_count"
        ] > 0

        _assert_upgrade_refused_without_mutation(
            connection,
            monkeypatch,
            expected_invariant="external dependency mismatch",
        )


def test_upgrade_refuses_empty_orphan_with_user_trigger_without_mutation(
    engine,
    monkeypatch,
):
    with migration_schema(engine, "summary_user_trigger") as (
        connection,
        _schema,
    ):
        create_legacy_practices_table(connection)
        create_exact_summary_orphan(connection)
        connection.exec_driver_sql("""
            CREATE FUNCTION keep_summary_row()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$ BEGIN RETURN NEW; END $$
        """)
        connection.exec_driver_sql("""
            CREATE TRIGGER unexpected_summary_trigger
            BEFORE INSERT ON practice_summary_posts
            FOR EACH ROW EXECUTE FUNCTION keep_summary_row()
        """)
        assert summary_catalog_snapshot(connection)[
            "attached_behavior"
        ] == (1, 0)

        _assert_upgrade_refused_without_mutation(
            connection,
            monkeypatch,
            expected_invariant="attached behavior mismatch",
        )


def test_upgrade_refuses_empty_orphan_with_policy_without_mutation(
    engine,
    monkeypatch,
):
    with migration_schema(engine, "summary_policy") as (
        connection,
        _schema,
    ):
        create_legacy_practices_table(connection)
        create_exact_summary_orphan(connection)
        connection.exec_driver_sql("""
            CREATE POLICY unexpected_summary_policy
            ON practice_summary_posts
            USING (true)
        """)
        assert summary_catalog_snapshot(connection)[
            "attached_behavior"
        ] == (0, 1)

        _assert_upgrade_refused_without_mutation(
            connection,
            monkeypatch,
            expected_invariant="attached behavior mismatch",
        )


def test_upgrade_refuses_empty_orphan_with_publication_membership_without_mutation(
    engine,
    monkeypatch,
):
    with migration_schema(engine, "summary_publication") as (
        connection,
        schema,
    ):
        create_legacy_practices_table(connection)
        create_exact_summary_orphan(connection)
        quote = connection.dialect.identifier_preparer.quote
        qualified = (
            f"{quote(schema)}.{quote(revision.SUMMARY_TABLE)}"
        )
        connection.exec_driver_sql(f"""
            CREATE PUBLICATION unexpected_summary_publication
            FOR TABLE {qualified}
        """)
        assert summary_catalog_snapshot(connection)[
            "publication_membership_count"
        ] == 1

        _assert_upgrade_refused_without_mutation(
            connection,
            monkeypatch,
            expected_invariant="publication membership mismatch",
        )


def test_upgrade_checks_rows_on_locked_schema_despite_temp_shadow(
    engine, monkeypatch,
):
    with migration_schema(engine, "summary_shadow") as (connection, _schema):
        create_legacy_practices_table(connection)
        create_exact_summary_orphan(connection)
        connection.exec_driver_sql("""
            INSERT INTO practice_summary_posts (
                id, week_start, surface, message_ts, created_at, updated_at
            ) VALUES (
                1, '2026-07-13', 'weekly_summary',
                'sensitive-shadow-ts', now(), now()
            )
        """)
        connection.exec_driver_sql("""
            CREATE TEMP TABLE practice_summary_posts (id INTEGER)
            ON COMMIT DROP
        """)

        _assert_upgrade_refused_without_mutation(connection, monkeypatch)


@pytest.mark.parametrize(
    "malformation",
    [
        pytest.param(
            "ALTER TABLE practice_summary_posts DROP CONSTRAINT "
            "ck_practice_summary_post_surface",
            id="missing-check",
        ),
        pytest.param(
            "CREATE INDEX unexpected_summary_message_index "
            "ON practice_summary_posts (message_ts)",
            id="unexpected-index",
        ),
        pytest.param(
            "ALTER TABLE practice_summary_posts SET UNLOGGED",
            id="non-permanent-relation",
        ),
        pytest.param(
            "ALTER TABLE practice_summary_posts ENABLE ROW LEVEL SECURITY",
            id="row-security",
        ),
        pytest.param(
            "ALTER TABLE practice_summary_posts "
            "ALTER COLUMN channel_id TYPE VARCHAR(51)",
            id="column-shape",
        ),
        pytest.param(
            "ALTER TABLE practice_summary_posts ALTER COLUMN id DROP DEFAULT",
            id="serial-default",
        ),
        pytest.param(
            "ALTER TABLE practice_summary_posts DROP CONSTRAINT "
            "practice_summary_posts_pkey",
            id="missing-primary-key",
        ),
        pytest.param(
            "ALTER TABLE practice_summary_posts DROP CONSTRAINT "
            "uq_practice_summary_post_week_surface",
            id="missing-unique",
        ),
        pytest.param(
            "ALTER TABLE practice_summary_posts ADD CONSTRAINT "
            "unexpected_summary_fk FOREIGN KEY (id) "
            "REFERENCES practice_summary_posts(id)",
            id="unexpected-foreign-key",
        ),
        pytest.param(
            "ALTER SEQUENCE practice_summary_posts_id_seq "
            "RENAME TO unexpected_summary_id_seq",
            id="sequence-identity",
        ),
        pytest.param(
            "ALTER SEQUENCE practice_summary_posts_id_seq OWNED BY NONE",
            id="sequence-ownership",
        ),
    ],
)
def test_upgrade_refuses_malformed_orm_orphan_without_mutation(
    engine, monkeypatch, malformation,
):
    with migration_schema(engine, "summary_malformed") as (
        connection, _schema,
    ):
        create_legacy_practices_table(connection)
        create_exact_summary_orphan(connection)
        connection.exec_driver_sql(malformation)

        _assert_upgrade_refused_without_mutation(connection, monkeypatch)


def test_upgrade_refuses_non_table_relation_without_mutation(
    engine, monkeypatch,
):
    with migration_schema(engine, "summary_view") as (connection, _schema):
        create_legacy_practices_table(connection)
        connection.exec_driver_sql("""
            CREATE VIEW practice_summary_posts AS
            SELECT
                1::integer AS id,
                DATE '2026-07-13' AS week_start,
                'coach_summary'::varchar(32) AS surface,
                NULL::varchar(50) AS channel_id,
                'view-message'::varchar(50) AS message_ts,
                now()::timestamp AS created_at,
                now()::timestamp AS updated_at
            WHERE FALSE
        """)

        _assert_upgrade_refused_without_mutation(connection, monkeypatch)


def test_upgrade_refuses_canonical_preexisting_table_without_mutation(
    engine, monkeypatch,
):
    with migration_schema(engine, "summary_canonical") as (
        connection, _schema,
    ):
        create_legacy_practices_table(connection)
        create_exact_summary_orphan(connection)
        connection.exec_driver_sql("""
            ALTER TABLE practice_summary_posts
              ALTER COLUMN created_at SET DEFAULT now(),
              ALTER COLUMN updated_at SET DEFAULT now()
        """)

        _assert_upgrade_refused_without_mutation(connection, monkeypatch)
