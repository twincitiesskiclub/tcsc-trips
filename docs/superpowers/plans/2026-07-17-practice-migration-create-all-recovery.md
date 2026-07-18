# Practice Migration `create_all` Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Alembic the sole schema authority, transactionally replace only the audited empty ORM-created summary-table orphan, and safely complete the interrupted practice-announcement deployment.

**Architecture:** Application startup becomes schema-neutral, while the Render release command enters an explicit migration-only lifecycle before Python imports Slack. Migration `d8b2c6f4a901` locks and validates the exact orphan fingerprint before replacing it inside Alembic's PostgreSQL transaction; focused catalog tests and a real `scripts/release.sh` subprocess prove both success and rollback from the audited production starting state.

**Tech Stack:** Python 3.11, Flask 3.1, Flask-Migrate/Alembic, Flask-SQLAlchemy/SQLAlchemy 2, PostgreSQL, Bash, pytest, Slack Bolt, Render, Git/GitHub CLI.

## Global Constraints

- Alembic is the only application schema authority. Remove runtime `db.create_all()` rather than hiding it behind an environment flag.
- Only literal `TCSC_MIGRATION_ONLY=1` suppresses background startup; normal Render web workers retain their existing scheduler and Slack behavior.
- `scripts/release.sh` must blank `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, and `SLACK_SIGNING_SECRET` before Python imports `app.slack.bolt_app`.
- Recover only a permanent, row-security-disabled, exact seven-column ORM-shaped `practice_summary_posts` table with its expected serial sequence, constraints, indexes, no timestamp defaults, no user triggers, row-security policies, or explicit publication memberships, and zero rows.
- Acquire `ACCESS EXCLUSIVE` before fingerprint and emptiness validation and hold it through orphan replacement.
- Any populated, canonical-looking, or structurally different pre-existing relation fails before `DROP TABLE`; errors identify invariants but never include Slack timestamps or practice data.
- The `c4f1a8e2d9b7` changes, orphan replacement, legacy conflict checks, backfill, and revision update remain in one PostgreSQL transaction. A failure from the audited starting shape must restore the orphan, roll back all four `c4` columns, and leave revision `e36bbec59bde`.
- Never stamp a revision, manually mutate production DDL, or retry an unchanged failed commit.
- Keep the local Slack companion stopped and never post to `#announcements-practices`; Preview remains user-invoked only in `C07G9RTMRT3`.
- Keep the practice-writer quiet window active until the deployed Preview succeeds.
- Run PostgreSQL tests serially against the suite-pinned local database, with all Slack credentials explicitly blank.
- Preserve the untracked `env` symlink and unrelated user changes.

### Approved production-only review amendment (2026-07-18)

- The user explicitly prioritized restoring the existing production database
  and removed clean local-database bootstrap from this rollout's acceptance
  criteria. The repository's historical root migration assumes pre-existing
  base tables; repairing that legacy chain remains separate work.
- Keep `create_app()` schema-neutral despite that known local-bootstrap gap.
- Before dropping the audited empty orphan, also reject behavior-bearing
  attached metadata: user triggers, row-security policies, and explicit
  PostgreSQL publication membership. Cover each with a fixed invariant error,
  a direct no-`drop_table` assertion, and unchanged catalog state.
- Offline Alembic SQL generation and test-only process-group timeout cleanup
  are review Minors outside the Render online migration path and are deferred.

---

## File Map

- Modify `app/__init__.py`: remove runtime schema creation and skip the scheduler only during migration-only startup.
- Modify `scripts/release.sh`: establish the migration-only process boundary and blank Slack credentials for `flask db upgrade`.
- Create `tests/test_app_startup.py`: verify normal and migration-only app-factory behavior.
- Create `tests/scripts/test_release.py`: verify the shell environment boundary and isolated import-time consumer state.
- Modify `migrations/versions/d8b2c6f4a901_add_practice_summary_posts.py`: lock, fingerprint, and replace only the exact empty orphan before the existing create/conflict/backfill flow.
- Create `tests/practices/migration_test_support.py`: local-only catalog snapshot and exact-orphan helpers shared by migration tests.
- Modify `tests/practices/test_practice_summary_post_migration.py`: cover normal creation, exact adoption, locking, and fail-closed variants without constructing the Flask app.
- Create `tests/practices/test_practice_migration_release.py`: run the real release script from an isolated committed `e36` schema and prove success plus transactional rollback.
- Create no production repair script; the repaired Alembic migration performs the one approved recovery.

### Task 1: Make Startup Schema-Neutral and Release Migration-Only

**Files:**

- Modify: `app/__init__.py:74-82`
- Modify: `scripts/release.sh:8-9`
- Create: `tests/test_app_startup.py`
- Create: `tests/scripts/test_release.py`

**Interfaces:**

- Consumes `TCSC_MIGRATION_ONLY` from the process environment.
- Produces `create_app()` behavior that never calls `db.create_all()` and calls `init_scheduler(app)` unless the flag is exactly `"1"`.
- Produces a release command that invokes exactly `flask db upgrade` with the migration flag set and all three Slack credentials present but empty.

- [ ] **Step 1: Write the failing app-factory tests**

Create `tests/test_app_startup.py`:

```python
from unittest.mock import Mock

import app as app_module


def _prepare_factory(monkeypatch):
    monkeypatch.setattr(app_module, "load_stripe_config", lambda: None)
    monkeypatch.setenv("FLASK_SECRET_KEY", "startup-test-secret")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://tcsc:tcsc@localhost:5432/tcsc_trips",
    )


def test_create_app_never_calls_create_all(monkeypatch):
    _prepare_factory(monkeypatch)
    monkeypatch.delenv("TCSC_MIGRATION_ONLY", raising=False)
    create_all = Mock(side_effect=AssertionError("schema mutation"))
    scheduler = Mock(return_value=False)
    monkeypatch.setattr(app_module.db, "create_all", create_all)
    monkeypatch.setattr(app_module, "init_scheduler", scheduler)

    application = app_module.create_app()

    create_all.assert_not_called()
    scheduler.assert_called_once_with(application)


def test_create_app_skips_scheduler_in_migration_only_mode(monkeypatch):
    _prepare_factory(monkeypatch)
    monkeypatch.setenv("TCSC_MIGRATION_ONLY", "1")
    create_all = Mock(side_effect=AssertionError("schema mutation"))
    scheduler = Mock(return_value=False)
    monkeypatch.setattr(app_module.db, "create_all", create_all)
    monkeypatch.setattr(app_module, "init_scheduler", scheduler)

    application = app_module.create_app()

    assert "migrate" in application.extensions
    create_all.assert_not_called()
    scheduler.assert_not_called()
```

- [ ] **Step 2: Run the app-factory tests and verify RED**

```bash
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= \
  env/bin/pytest tests/test_app_startup.py -q
```

Expected: the first test fails because current `create_app()` calls
`db.create_all()`; the second also cannot satisfy the migration-only contract.

- [ ] **Step 3: Write the failing release-boundary tests**

Create `tests/scripts/test_release.py`:

```python
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT / "scripts" / "release.sh"


def test_release_runs_upgrade_with_migration_only_and_blank_slack_environment(
    tmp_path,
):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_flask = fake_bin / "flask"
    fake_flask.write_text(
        """#!/bin/sh
{
  printf 'argv=%s\\n' "$*"
  printf 'migration_only=%s\\n' "${TCSC_MIGRATION_ONLY-unset}"
  printf 'bot=%s\\n' "${SLACK_BOT_TOKEN-unset}"
  printf 'app=%s\\n' "${SLACK_APP_TOKEN-unset}"
  printf 'signing=%s\\n' "${SLACK_SIGNING_SECRET-unset}"
} >> "$TCSC_RELEASE_CAPTURE"
""",
        encoding="utf-8",
    )
    fake_flask.chmod(0o755)
    capture = tmp_path / "release-environment.txt"
    environment = os.environ.copy()
    environment.update({
        "PATH": f"{fake_bin}{os.pathsep}{environment['PATH']}",
        "TCSC_RELEASE_CAPTURE": str(capture),
        "TCSC_MIGRATION_ONLY": "0",
        "SLACK_BOT_TOKEN": "must-be-cleared",
        "SLACK_APP_TOKEN": "must-be-cleared",
        "SLACK_SIGNING_SECRET": "must-be-cleared",
    })

    result = subprocess.run(
        ["bash", str(RELEASE)],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert capture.read_text(encoding="utf-8").splitlines() == [
        "argv=db upgrade",
        "migration_only=1",
        "bot=",
        "app=",
        "signing=",
    ]


def test_migration_only_process_starts_no_background_consumers():
    probe = r"""
import json
from unittest.mock import Mock

import app as app_module
import app.scheduler as scheduler_module
import app.slack.bolt_app as bolt_module

app_module.load_stripe_config = lambda: None
create_all = Mock(side_effect=AssertionError("schema mutation"))
init_scheduler = Mock(side_effect=AssertionError("background startup"))
app_module.db.create_all = create_all
app_module.init_scheduler = init_scheduler
application = app_module.create_app()
print(json.dumps({
    "create_all_calls": create_all.call_count,
    "scheduler_calls": init_scheduler.call_count,
    "migrate_registered": "migrate" in application.extensions,
    "bolt_enabled": bolt_module.is_bolt_enabled(),
    "socket_available": bolt_module.is_socket_mode_available(),
    "socket_running": bolt_module.is_socket_mode_running(),
    "scheduler_running": scheduler_module.scheduler.running,
}))
"""
    environment = os.environ.copy()
    environment.update({
        "DATABASE_URL": (
            "postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"
        ),
        "FLASK_SECRET_KEY": "release-process-test-secret",
        "TCSC_MIGRATION_ONLY": "1",
        "SLACK_BOT_TOKEN": "",
        "SLACK_APP_TOKEN": "",
        "SLACK_SIGNING_SECRET": "",
    })

    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    state = json.loads(result.stdout.strip().splitlines()[-1])
    assert state == {
        "create_all_calls": 0,
        "scheduler_calls": 0,
        "migrate_registered": True,
        "bolt_enabled": False,
        "socket_available": False,
        "socket_running": False,
        "scheduler_running": False,
    }
```

- [ ] **Step 4: Run the release-boundary tests and verify RED**

```bash
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= \
  env/bin/pytest tests/scripts/test_release.py -q
```

Expected: the fake command sees the sentinel values and no migration flag;
the isolated process fails on the current runtime `create_all()` call.

- [ ] **Step 5: Remove runtime schema creation and gate only background startup**

In `app/__init__.py`, replace the existing `create_all()` and scheduler block
with:

```python
    # Schema changes belong exclusively to Alembic. Migration commands still
    # need the Flask-Migrate extension, but must not start background workers.
    if os.getenv("TCSC_MIGRATION_ONLY") != "1":
        init_scheduler(app)

    return app
```

Keep `Migrate(app, db)` registered earlier in the factory. Do not retain any
`db.create_all()` call or add an alternate schema-initialization path.

- [ ] **Step 6: Establish the release process boundary before Python import**

Replace the migration command in `scripts/release.sh` with:

```bash
env \
  TCSC_MIGRATION_ONLY=1 \
  SLACK_BOT_TOKEN= \
  SLACK_APP_TOKEN= \
  SLACK_SIGNING_SECRET= \
  flask db upgrade
```

Do not move credential blanking into Python: `bolt_app` snapshots those values
at import time.

- [ ] **Step 7: Run the startup/release tests and verify GREEN**

```bash
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= \
  env/bin/pytest tests/test_app_startup.py tests/scripts/test_release.py -q
```

Expected: four tests pass; no PostgreSQL schema or Slack state is mutated.

- [ ] **Step 8: Commit the startup boundary**

```bash
git add app/__init__.py scripts/release.sh \
  tests/test_app_startup.py tests/scripts/test_release.py
git commit -m "fix(deploy): isolate migration startup"
```

### Task 2: Adopt Only the Exact Empty ORM Orphan

**Files:**

- Modify: `migrations/versions/d8b2c6f4a901_add_practice_summary_posts.py`
- Create: `tests/practices/migration_test_support.py`
- Modify: `tests/practices/test_practice_summary_post_migration.py`

**Interfaces:**

- Produces `_visible_summary_table_oid(bind) -> int | None`.
- Produces `_lock_existing_summary_table(bind, relation_oid: int) -> int`, which holds `AccessExclusiveLock` until the surrounding transaction ends.
- Produces `_summary_table_fingerprint(bind, relation_oid: int) -> dict` and `_assert_exact_empty_create_all_orphan(bind, relation_oid: int) -> None`.
- Produces `_drop_exact_empty_create_all_orphan_if_present(bind) -> bool`; `upgrade()` calls it immediately before the existing canonical create/conflict/backfill flow.
- Test support produces `create_exact_summary_orphan(connection)` and `summary_catalog_snapshot(connection)` without calling `create_app()` or `db.create_all()`.

- [ ] **Step 1: Add independent exact-orphan and catalog-snapshot test helpers**

Create `tests/practices/migration_test_support.py`:

```python
from sqlalchemy import text

from app.practices.models import PracticeSummaryPost


def create_exact_summary_orphan(connection):
    """Create only the ORM table in the active test schema."""
    PracticeSummaryPost.__table__.create(connection)


def summary_catalog_snapshot(connection):
    relation = connection.execute(text("""
        SELECT c.oid, c.relkind, c.relpersistence,
               c.relrowsecurity, c.relforcerowsecurity
        FROM pg_class AS c
        JOIN pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = current_schema()
          AND c.relname = 'practice_summary_posts'
    """)).mappings().one_or_none()
    if relation is None:
        return None
    oid = relation["oid"]
    columns = connection.execute(text("""
        SELECT a.attnum, a.attname,
               format_type(a.atttypid, a.atttypmod) AS sql_type,
               a.attnotnull, a.attidentity, a.attgenerated,
               pg_get_expr(d.adbin, d.adrelid) AS default_expr
        FROM pg_attribute AS a
        LEFT JOIN pg_attrdef AS d
          ON d.adrelid = a.attrelid AND d.adnum = a.attnum
        WHERE a.attrelid = :oid
          AND a.attnum > 0
          AND NOT a.attisdropped
        ORDER BY a.attnum
    """), {"oid": oid}).all()
    constraints = connection.execute(text("""
        SELECT con.conname, con.contype,
               coalesce(
                 array_agg(a.attname ORDER BY key.ord)
                   FILTER (WHERE a.attname IS NOT NULL),
                 ARRAY[]::name[]
               ) AS columns,
               pg_get_constraintdef(con.oid, true) AS definition
        FROM pg_constraint AS con
        LEFT JOIN LATERAL
          unnest(con.conkey) WITH ORDINALITY AS key(attnum, ord) ON true
        LEFT JOIN pg_attribute AS a
          ON a.attrelid = con.conrelid AND a.attnum = key.attnum
        WHERE con.conrelid = :oid
          AND con.contype IN ('c', 'p', 'u', 'f', 'x')
        GROUP BY con.oid, con.conname, con.contype
        ORDER BY con.conname
    """), {"oid": oid}).all()
    indexes = connection.execute(text("""
        SELECT idx.relname, ind.indisprimary, ind.indisunique,
               ind.indisvalid, ind.indisready,
               am.amname, ind.indnkeyatts, ind.indnatts,
               array_agg(a.attname ORDER BY key.ord) AS columns,
               pg_get_expr(ind.indpred, ind.indrelid) AS predicate,
               pg_get_expr(ind.indexprs, ind.indrelid) AS expressions
        FROM pg_index AS ind
        JOIN pg_class AS idx ON idx.oid = ind.indexrelid
        JOIN pg_am AS am ON am.oid = idx.relam
        JOIN LATERAL
          unnest(ind.indkey::smallint[]) WITH ORDINALITY
          AS key(attnum, ord) ON true
        LEFT JOIN pg_attribute AS a
          ON a.attrelid = ind.indrelid AND a.attnum = key.attnum
        WHERE ind.indrelid = :oid
        GROUP BY idx.relname, ind.indisprimary, ind.indisunique,
                 ind.indisvalid, ind.indisready,
                 am.amname, ind.indnkeyatts, ind.indnatts,
                 ind.indpred, ind.indexprs, ind.indrelid
        ORDER BY idx.relname
    """), {"oid": oid}).all()
    sequence = connection.execute(text("""
        SELECT seq_ns.nspname, seq.relname,
               ownership.deptype, default_dep.deptype
        FROM pg_class AS table_rel
        JOIN pg_attribute AS id_column
          ON id_column.attrelid = table_rel.oid
         AND id_column.attname = 'id'
        JOIN pg_attrdef AS id_default
          ON id_default.adrelid = table_rel.oid
         AND id_default.adnum = id_column.attnum
        JOIN pg_depend AS ownership
          ON ownership.refobjid = table_rel.oid
         AND ownership.refobjsubid = id_column.attnum
         AND ownership.deptype = 'a'
        JOIN pg_class AS seq
          ON seq.oid = ownership.objid AND seq.relkind = 'S'
        JOIN pg_namespace AS seq_ns ON seq_ns.oid = seq.relnamespace
        JOIN pg_depend AS default_dep
          ON default_dep.classid = 'pg_attrdef'::regclass
         AND default_dep.objid = id_default.oid
         AND default_dep.refobjid = seq.oid
        WHERE table_rel.oid = :oid
        ORDER BY seq_ns.nspname, seq.relname
    """), {"oid": oid}).all()
    row_count = connection.exec_driver_sql(
        "SELECT count(*) FROM practice_summary_posts"
    ).scalar_one()
    return {
        "relation": tuple(relation[key] for key in (
            "relkind", "relpersistence", "relrowsecurity",
            "relforcerowsecurity",
        )),
        "columns": [tuple(row) for row in columns],
        "constraints": [
            (row[0], row[1], tuple(row[2]), " ".join(row[3].split()))
            for row in constraints
        ],
        "indexes": [
            (*tuple(row[:8]), tuple(row[8]), row[9], row[10])
            for row in indexes
        ],
        "sequence": [tuple(row) for row in sequence],
        "row_count": row_count,
    }
```

This helper is test-only and intentionally uses catalog queries independent of
the migration helper implementation.

- [ ] **Step 2: Refactor the migration test harness away from Flask startup**

Replace the `create_app()`/`db` fixtures in
`tests/practices/test_practice_summary_post_migration.py` with:

```python
from contextlib import contextmanager
from datetime import date
import os
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
```

Update the three existing tests to consume `engine` and
`migration_schema(...)`, call `configure_revision(...)`, and retain their
existing rows and assertions. Do not initialize the Flask application.

- [ ] **Step 3: Write the failing normal, lock, and exact-adoption tests**

Add these tests to the same file:

```python
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
    with migration_schema(engine, "summary_lock") as (connection, _schema):
        create_legacy_practices_table(connection)
        create_exact_summary_orphan(connection)
        oid = revision._visible_summary_table_oid(connection)

        locked_oid = revision._lock_existing_summary_table(connection, oid)

        assert locked_oid == oid
        locks = connection.execute(text("""
            SELECT mode, granted
            FROM pg_locks
            WHERE pid = pg_backend_pid()
              AND relation = :oid
              AND mode = 'AccessExclusiveLock'
        """), {"oid": oid}).all()
        assert locks == [("AccessExclusiveLock", True)]


def test_upgrade_adopts_exact_empty_orm_orphan_and_backfills(
    engine, monkeypatch,
):
    with migration_schema(engine, "summary_adopt") as (connection, _schema):
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
        assert before["row_count"] == 0
        assert dict(
            (row[1], row[6]) for row in before["columns"]
        )["created_at"] is None
        configure_revision(connection, monkeypatch)

        revision.upgrade()

        after = summary_catalog_snapshot(connection)
        defaults = {row[1]: row[6] for row in after["columns"]}
        assert defaults["created_at"] == "now()"
        assert defaults["updated_at"] == "now()"
        rows = connection.exec_driver_sql("""
            SELECT week_start, surface, channel_id, message_ts
            FROM practice_summary_posts
            ORDER BY surface
        """).all()
        assert rows == [
            (date(2026, 7, 13), "coach_summary", None, "coach-1"),
            (date(2026, 7, 13), "weekly_summary", None, "public-1"),
        ]
```

- [ ] **Step 4: Write the failing fail-closed fingerprint tests**

Add:

```python
def _assert_upgrade_refused_without_mutation(connection, monkeypatch):
    before = summary_catalog_snapshot(connection)
    configure_revision(connection, monkeypatch)

    savepoint = connection.begin_nested()
    try:
        with pytest.raises(
            RuntimeError,
            match="practice_summary_posts orphan recovery refused",
        ):
            revision.upgrade()
    finally:
        savepoint.rollback()

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
```

- [ ] **Step 5: Run all migration tests and verify RED**

```bash
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= \
  env/bin/pytest tests/practices/test_practice_summary_post_migration.py -q
```

Expected: the new tests fail because the lock/fingerprint helpers do not exist
and current `upgrade()` collides with any pre-existing table. The three
existing normal/conflict tests continue to establish their prior behavior.

- [ ] **Step 6: Add exact fingerprint constants and catalog helpers to `d8`**

Add these constants and helpers above `upgrade()` in
`migrations/versions/d8b2c6f4a901_add_practice_summary_posts.py`:

```python
SUMMARY_TABLE = "practice_summary_posts"

_EXPECTED_COLUMN_SHAPE = (
    (1, "id", "integer", True, "", ""),
    (2, "week_start", "date", True, "", ""),
    (3, "surface", "character varying(32)", True, "", ""),
    (4, "channel_id", "character varying(50)", False, "", ""),
    (5, "message_ts", "character varying(50)", True, "", ""),
    (6, "created_at", "timestamp without time zone", True, "", ""),
    (7, "updated_at", "timestamp without time zone", True, "", ""),
)

_EXPECTED_CONSTRAINTS = (
    (
        "ck_practice_summary_post_surface",
        "c",
        ("surface",),
        "CHECK (surface::text = ANY (ARRAY['coach_summary'::character "
        "varying, 'weekly_summary'::character varying]::text[]))",
    ),
    (
        "practice_summary_posts_pkey",
        "p",
        ("id",),
        "PRIMARY KEY (id)",
    ),
    (
        "uq_practice_summary_post_week_surface",
        "u",
        ("week_start", "surface"),
        "UNIQUE (week_start, surface)",
    ),
)

_EXPECTED_INDEXES = (
    (
        "practice_summary_posts_pkey", True, True, True, True,
        "btree", 1, 1,
        ("id",), None, None,
    ),
    (
        "uq_practice_summary_post_week_surface", False, True, True, True,
        "btree", 2, 2,
        ("week_start", "surface"), None, None,
    ),
)


def _refuse_orphan_recovery(invariant):
    raise RuntimeError(
        "practice_summary_posts orphan recovery refused: " + invariant
    )


def _visible_summary_relation(bind):
    row = bind.execute(sa.text("""
        SELECT c.oid, n.nspname AS schema_name, c.relkind,
               c.relpersistence, c.relrowsecurity, c.relforcerowsecurity
        FROM pg_class AS c
        JOIN pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = current_schema()
          AND c.relname = :table_name
    """), {"table_name": SUMMARY_TABLE}).mappings().one_or_none()
    return dict(row) if row is not None else None


def _visible_summary_table_oid(bind):
    relation = _visible_summary_relation(bind)
    return None if relation is None else relation["oid"]


def _lock_existing_summary_table(bind, relation_oid):
    relation = _visible_summary_relation(bind)
    if relation is None or relation["oid"] != relation_oid:
        _refuse_orphan_recovery("relation changed before lock")
    quote = bind.dialect.identifier_preparer.quote
    qualified = (
        f"{quote(relation['schema_name'])}.{quote(SUMMARY_TABLE)}"
    )
    try:
        bind.exec_driver_sql(
            f"LOCK TABLE {qualified} IN ACCESS EXCLUSIVE MODE"
        )
    except sa.exc.DBAPIError as error:
        raise RuntimeError(
            "practice_summary_posts orphan recovery refused: "
            "relation could not be locked"
        ) from error
    locked = _visible_summary_relation(bind)
    if locked is None or locked["oid"] != relation_oid:
        _refuse_orphan_recovery("relation changed while acquiring lock")
    return relation_oid
```

These exact constants, including `indisvalid` and `indisready`, were compared
read-only with the production orphan on 2026-07-17. Do not broaden them to
accept alternate table shapes.

- [ ] **Step 7: Add the complete locked fingerprint reader**

Continue in the migration file:

```python
def _summary_table_fingerprint(bind, relation_oid):
    relation = _visible_summary_relation(bind)
    if relation is None or relation["oid"] != relation_oid:
        _refuse_orphan_recovery("locked relation is no longer visible")
    columns = bind.execute(sa.text("""
        SELECT a.attnum, a.attname,
               format_type(a.atttypid, a.atttypmod) AS sql_type,
               a.attnotnull, a.attidentity, a.attgenerated,
               pg_get_expr(d.adbin, d.adrelid) AS default_expr
        FROM pg_attribute AS a
        LEFT JOIN pg_attrdef AS d
          ON d.adrelid = a.attrelid AND d.adnum = a.attnum
        WHERE a.attrelid = :oid
          AND a.attnum > 0
          AND NOT a.attisdropped
        ORDER BY a.attnum
    """), {"oid": relation_oid}).all()
    constraints = bind.execute(sa.text("""
        SELECT con.conname, con.contype,
               coalesce(
                 array_agg(a.attname ORDER BY key.ord)
                   FILTER (WHERE a.attname IS NOT NULL),
                 ARRAY[]::name[]
               ) AS columns,
               pg_get_constraintdef(con.oid, true) AS definition
        FROM pg_constraint AS con
        LEFT JOIN LATERAL
          unnest(con.conkey) WITH ORDINALITY AS key(attnum, ord) ON true
        LEFT JOIN pg_attribute AS a
          ON a.attrelid = con.conrelid AND a.attnum = key.attnum
        WHERE con.conrelid = :oid
          AND con.contype IN ('c', 'p', 'u', 'f', 'x')
        GROUP BY con.oid, con.conname, con.contype
        ORDER BY con.conname
    """), {"oid": relation_oid}).all()
    indexes = bind.execute(sa.text("""
        SELECT idx.relname, ind.indisprimary, ind.indisunique,
               ind.indisvalid, ind.indisready,
               am.amname, ind.indnkeyatts, ind.indnatts,
               array_agg(a.attname ORDER BY key.ord) AS columns,
               pg_get_expr(ind.indpred, ind.indrelid) AS predicate,
               pg_get_expr(ind.indexprs, ind.indrelid) AS expressions
        FROM pg_index AS ind
        JOIN pg_class AS idx ON idx.oid = ind.indexrelid
        JOIN pg_am AS am ON am.oid = idx.relam
        JOIN LATERAL
          unnest(ind.indkey::smallint[]) WITH ORDINALITY
          AS key(attnum, ord) ON true
        LEFT JOIN pg_attribute AS a
          ON a.attrelid = ind.indrelid AND a.attnum = key.attnum
        WHERE ind.indrelid = :oid
        GROUP BY idx.relname, ind.indisprimary, ind.indisunique,
                 ind.indisvalid, ind.indisready,
                 am.amname, ind.indnkeyatts, ind.indnatts,
                 ind.indpred, ind.indexprs, ind.indrelid
        ORDER BY idx.relname
    """), {"oid": relation_oid}).all()
    sequence = bind.execute(sa.text("""
        SELECT seq_ns.nspname, seq.relname,
               ownership.deptype, default_dep.deptype
        FROM pg_class AS table_rel
        JOIN pg_attribute AS id_column
          ON id_column.attrelid = table_rel.oid
         AND id_column.attname = 'id'
        JOIN pg_attrdef AS id_default
          ON id_default.adrelid = table_rel.oid
         AND id_default.adnum = id_column.attnum
        JOIN pg_depend AS ownership
          ON ownership.refobjid = table_rel.oid
         AND ownership.refobjsubid = id_column.attnum
         AND ownership.deptype = 'a'
        JOIN pg_class AS seq
          ON seq.oid = ownership.objid AND seq.relkind = 'S'
        JOIN pg_namespace AS seq_ns ON seq_ns.oid = seq.relnamespace
        JOIN pg_depend AS default_dep
          ON default_dep.classid = 'pg_attrdef'::regclass
         AND default_dep.objid = id_default.oid
         AND default_dep.refobjid = seq.oid
        WHERE table_rel.oid = :oid
        ORDER BY seq_ns.nspname, seq.relname
    """), {"oid": relation_oid}).all()
    has_rows = bind.exec_driver_sql(
        "SELECT EXISTS (SELECT 1 FROM practice_summary_posts LIMIT 1)"
    ).scalar_one()
    return {
        "relation": (
            relation["relkind"], relation["relpersistence"],
            relation["relrowsecurity"], relation["relforcerowsecurity"],
        ),
        "schema": relation["schema_name"],
        "columns": [tuple(row) for row in columns],
        "constraints": tuple(
            (row[0], row[1], tuple(row[2]), " ".join(row[3].split()))
            for row in constraints
        ),
        "indexes": tuple(
            (*tuple(row[:8]), tuple(row[8]), row[9], row[10])
            for row in indexes
        ),
        "sequence": [tuple(row) for row in sequence],
        "has_rows": has_rows,
    }
```

- [ ] **Step 8: Validate every invariant and drop only after all pass**

Add:

```python
def _assert_exact_empty_create_all_orphan(bind, relation_oid):
    fingerprint = _summary_table_fingerprint(bind, relation_oid)
    if fingerprint["relation"] != ("r", "p", False, False):
        _refuse_orphan_recovery("relation metadata mismatch")
    columns = fingerprint["columns"]
    shape = tuple(row[:6] for row in columns)
    if shape != _EXPECTED_COLUMN_SHAPE:
        _refuse_orphan_recovery("column shape mismatch")
    id_default = columns[0][6]
    if not id_default or not id_default.startswith("nextval("):
        _refuse_orphan_recovery("id serial default mismatch")
    if any(row[6] is not None for row in columns[1:]):
        _refuse_orphan_recovery("non-id column default mismatch")
    expected_sequence = [(
        fingerprint["schema"],
        "practice_summary_posts_id_seq",
        "a",
        "n",
    )]
    if fingerprint["sequence"] != expected_sequence:
        _refuse_orphan_recovery("owned serial sequence mismatch")
    if fingerprint["constraints"] != _EXPECTED_CONSTRAINTS:
        _refuse_orphan_recovery("constraint mismatch")
    if fingerprint["indexes"] != _EXPECTED_INDEXES:
        _refuse_orphan_recovery("index mismatch")
    if fingerprint["has_rows"]:
        _refuse_orphan_recovery("table contains rows")


def _drop_exact_empty_create_all_orphan_if_present(bind):
    relation_oid = _visible_summary_table_oid(bind)
    if relation_oid is None:
        return False
    _lock_existing_summary_table(bind, relation_oid)
    _assert_exact_empty_create_all_orphan(bind, relation_oid)
    op.drop_table(SUMMARY_TABLE)
    return True
```

At the first line of `upgrade()`, before the existing canonical
`op.create_table(...)`, add:

```python
    _drop_exact_empty_create_all_orphan_if_present(op.get_bind())
```

Leave the canonical table definition, same-week/cross-week conflict block,
backfill SQL, and downgrade behavior unchanged.

- [ ] **Step 9: Run migration tests and verify GREEN**

```bash
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= \
  env/bin/pytest tests/practices/test_practice_summary_post_migration.py -q
```

Expected: normal create/downgrade, lock, exact adoption, nonempty refusal,
malformed refusal, canonical refusal, and both legacy conflict cases pass.

- [ ] **Step 10: Commit the locked orphan recovery**

```bash
git add migrations/versions/d8b2c6f4a901_add_practice_summary_posts.py \
  tests/practices/migration_test_support.py \
  tests/practices/test_practice_summary_post_migration.py
git commit -m "fix(practices): recover empty summary orphan"
```

### Task 3: Prove the Real Release Lifecycle and Transaction Rollback

**Files:**

- Create: `tests/practices/test_practice_migration_release.py`
- Reuse: `tests/practices/migration_test_support.py`

**Interfaces:**

- Consumes the migration-only `scripts/release.sh` contract from Task 1 and the locked orphan recovery from Task 2.
- Produces `_create_e36_baseline(connection, *, conflicting: bool) -> None`, `_schema_database_url(schema: str) -> str`, and `_run_release(schema: str) -> subprocess.CompletedProcess[str]` inside the test module.
- Proves the exact audited start state—revision `e36bbec59bde`, four absent `c4` columns, and an empty ORM orphan—reaches `d8b2c6f4a901` or rolls back completely after a post-replacement conflict.

- [ ] **Step 1: Create a committed isolated-schema release harness**

Create `tests/practices/test_practice_migration_release.py` with these imports,
fixtures, and helpers:

```python
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


def _use_schema(connection, schema):
    connection.exec_driver_sql(f'SET search_path TO "{schema}"')


def _create_e36_baseline(connection, *, conflicting):
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


def _schema_database_url(schema):
    url = make_url(os.environ["DATABASE_URL"])
    scoped = url.update_query_dict({
        "options": f"-csearch_path={schema}",
    })
    return scoped.render_as_string(hide_password=False)


def _run_release(schema):
    environment = os.environ.copy()
    environment.update({
        "PATH": (
            f"{Path(sys.executable).parent}{os.pathsep}"
            f"{environment['PATH']}"
        ),
        "DATABASE_URL": _schema_database_url(schema),
        "FLASK_ENV": "testing",
        "FLASK_SECRET_KEY": "release-lifecycle-secret",
        "STRIPE_SECRET_KEY": "sk_test_release_lifecycle",
        "TCSC_MIGRATION_ONLY": "0",
        "SLACK_BOT_TOKEN": "must-be-cleared",
        "SLACK_APP_TOKEN": "must-be-cleared",
        "SLACK_SIGNING_SECRET": "must-be-cleared",
        "RENDER": "",
    })
    return subprocess.run(
        ["bash", str(RELEASE)],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def _revision(connection):
    return connection.exec_driver_sql(
        "SELECT version_num FROM alembic_version"
    ).scalar_one()


def _c4_columns(connection):
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
```

The schema setup must commit before `_run_release()` because the subprocess
uses a separate PostgreSQL connection. The fixture drops only its UUID-owned
schema.

- [ ] **Step 2: Add the successful real-release regression**

```python
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
```

- [ ] **Step 3: Add the forced post-replacement rollback regression**

```python
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
        assert summary_catalog_snapshot(connection) == baseline
        defaults = {
            row[1]: row[6]
            for row in summary_catalog_snapshot(connection)["columns"]
        }
        assert defaults["created_at"] is None
        assert defaults["updated_at"] is None
```

- [ ] **Step 4: Run the lifecycle file in isolation**

```bash
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= \
  env/bin/pytest tests/practices/test_practice_migration_release.py -q
```

Expected: both subprocess tests pass. The success path reaches `d8`; the
forced conflict fails inside `d8` but restores the exact baseline catalog,
four absent `c4` columns, and revision `e36`.

- [ ] **Step 5: Run the complete hotfix regression set**

```bash
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= \
  env/bin/pytest \
    tests/test_app_startup.py \
    tests/scripts/test_release.py \
    tests/practices/test_plan_reaction_migration.py \
    tests/practices/test_practice_summary_post_migration.py \
    tests/practices/test_practice_migration_release.py -q
```

Expected: startup, release boundary, both adjacent migrations, exact orphan
recovery, and real transaction lifecycle all pass serially.

- [ ] **Step 6: Commit the release-lifecycle proof**

```bash
git add tests/practices/test_practice_migration_release.py
git commit -m "test(deploy): prove practice migration rollback"
```

### Task 4: Verify, Review, Redeploy, and Resume the Approved Rollout

**Files:**

- No planned source changes; failures return to the owning task with a new regression test.
- Read: `docs/superpowers/specs/2026-07-17-practice-migration-create-all-recovery-design.md`
- Read: `docs/superpowers/plans/2026-07-16-practice-announcement-rollout.md`

**Interfaces:**

- Consumes the three reviewed hotfix commits and a sole Alembic head at `d8b2c6f4a901`.
- Produces a merged hotfix, successful Render pre-deploy, canonical production schema with 30 backfilled summary identities, and a deployed Preview confirmation.
- Produces a fresh read-only production seed digest, then stops for explicit approval; it does not seed in this task.

- [ ] **Step 1: Confirm no local Slack consumer is running**

```bash
pgrep -af "gunicorn|flask run|socket_mode|practice-preview" || true
```

Expected: no local TCSC companion or web process using production Slack
credentials. Inspect matches before acting; never stop unrelated user work.

- [ ] **Step 2: Run the focused hotfix and practice migration suites**

```bash
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= \
  env/bin/pytest \
    tests/test_app_startup.py \
    tests/scripts/test_release.py \
    tests/practices/test_plan_reaction_migration.py \
    tests/practices/test_practice_summary_post_migration.py \
    tests/practices/test_practice_migration_release.py \
    tests/practices/test_practice_summary_posts.py \
    tests/slack/test_practice_summary_registry.py -q
```

Expected: all focused tests pass serially with no external Slack calls.

- [ ] **Step 3: Run the full Python, Node, CSS, and migration-head gates**

```bash
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= \
  env/bin/pytest -q
npm run test:practice-reactions
npm run tailwind:build
git diff --exit-code -- app/static/css/tailwind-output.css
TCSC_MIGRATION_ONLY=1 \
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= \
DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips \
  env/bin/flask db heads
git diff --check
git status --short
```

Expected: all Python and Node tests pass, generated CSS is deterministic, the
sole Alembic head is `d8b2c6f4a901`, diff checks are clean, and status contains
only the pre-existing `?? env`.

- [ ] **Step 4: Request independent spec and safety reviews**

Review `81b92ea..HEAD` for:

- exact compliance with the approved recovery spec;
- import-time release isolation and absence of background consumers;
- lock-before-validation ordering and fail-closed catalog checks;
- no path that drops a populated, canonical, or malformed table;
- transaction rollback coverage from the exact audited start state;
- local-database and Slack side-effect safety; and
- no unrelated refactoring.

Any Critical or Important finding returns to the owning task's RED/GREEN cycle.
Do not push with an unresolved blocker.

- [ ] **Step 5: Push the hotfix and open the PR**

```bash
git push -u origin fix/practice-migration-create-all
gh pr create \
  --base main \
  --head fix/practice-migration-create-all \
  --title "Recover practice summary migration safely" \
  --body-file \
    docs/superpowers/specs/2026-07-17-practice-migration-create-all-recovery-design.md
```

Expected: the PR contains only the committed design, hotfix, tests, and this
plan; the untracked `env` symlink is absent.

- [ ] **Step 6: Require green GitHub checks and merge once**

```bash
gh pr checks
```

Expected: all required checks pass. Poll pending checks with the product wait
mechanism in intervals no longer than 60 seconds; never bypass a failure. Then:

```bash
gh pr merge --merge
```

Expected: the PR merges to `main` and Render starts one deployment from the new
merge commit. Do not manually retry the old `81b92ea` deployment.

- [ ] **Step 7: Observe the Render pre-deploy before checking production**

Require the new deployment log to show:

```text
=== Release tasks starting ===
Running database migrations...
Running upgrade e36bbec59bde -> c4f1a8e2d9b7
Running upgrade c4f1a8e2d9b7 -> d8b2c6f4a901
=== Release tasks completed ===
```

The pre-deploy log must not contain `APScheduler started successfully`,
`Slack Bolt enabled`, or `Socket Mode`. If pre-deploy fails, stop and inspect
production read-only; do not stamp, manually drop, or blindly redeploy.

- [ ] **Step 8: Verify the production schema and backfill read-only**

Run from the repository environment without printing the connection URL:

```bash
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= \
env/bin/python - <<'PY'
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv('.env')
engine = create_engine(os.environ['PROD_DATABASE_URL'])
with engine.connect() as connection:
    transaction = connection.begin()
    connection.exec_driver_sql('SET TRANSACTION READ ONLY')
    revision = connection.execute(
        text('SELECT version_num FROM alembic_version')
    ).scalar_one()
    assert revision == 'd8b2c6f4a901'
    c4_columns = {
        tuple(row)
        for row in connection.execute(text('''
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND (table_name, column_name) IN (
                ('practice_activities', 'default_plan_reactions'),
                ('practice_types', 'default_plan_reactions'),
                ('practices', 'plan_reactions'),
                ('practices', 'slack_session_emoji')
              )
        '''))
    }
    assert c4_columns == {
        ('practice_activities', 'default_plan_reactions'),
        ('practice_types', 'default_plan_reactions'),
        ('practices', 'plan_reactions'),
        ('practices', 'slack_session_emoji'),
    }
    defaults = dict(connection.execute(text('''
        SELECT column_name, column_default
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'practice_summary_posts'
          AND column_name IN ('created_at', 'updated_at')
    ''')).all())
    assert defaults == {'created_at': 'now()', 'updated_at': 'now()'}
    constraint_names = set(connection.execute(text('''
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'practice_summary_posts'::regclass
          AND contype IN ('c', 'p', 'u')
    ''')).scalars())
    assert constraint_names == {
        'ck_practice_summary_post_surface',
        'practice_summary_posts_pkey',
        'uq_practice_summary_post_week_surface',
    }
    counts = connection.execute(text('''
        SELECT surface, count(*)
        FROM practice_summary_posts
        GROUP BY surface
        ORDER BY surface
    ''')).all()
    assert counts == [('coach_summary', 19), ('weekly_summary', 11)]
    conflicts = connection.execute(text('''
        SELECT week_start, surface
        FROM practice_summary_posts
        GROUP BY week_start, surface
        HAVING count(*) > 1
    ''')).all()
    assert conflicts == []
    cross_week_reuse = connection.execute(text('''
        SELECT surface, message_ts
        FROM practice_summary_posts
        GROUP BY surface, message_ts
        HAVING count(DISTINCT week_start) > 1
    ''')).all()
    assert cross_week_reuse == []
    transaction.rollback()
engine.dispose()
print('production_migration_verified revision=d8b2c6f4a901 rows=30')
PY
```

Expected: one sanitized verification line. Keep the writer-quiet window active.

- [ ] **Step 9: Test Preview through Render as the sole Socket consumer**

Confirm the local companion remains stopped, then ask the user to invoke:

```text
/tcsc practice-preview
```

in `C07G9RTMRT3`. The user confirms the modal opens with the approved compact
reaction editor and Preview formatting, then discards it without creating or
editing a practice or message. Never post to `#announcements-practices`.

Only after that confirmation, tell the user practice Create/Edit may resume
and close the writer-quiet window.

- [ ] **Step 10: Generate the production seed dry run and stop for approval**

```bash
env/bin/python scripts/seed_practice_plan_reaction_defaults.py \
  --environment production --dry-run
```

Expected: canonical target/current/desired JSON and one approval digest, with
zero writes. Present the complete diff and exact digest to the user, state that
production values have not changed, and stop. Do not run `--commit` without a
fresh explicit approval of that exact digest.
