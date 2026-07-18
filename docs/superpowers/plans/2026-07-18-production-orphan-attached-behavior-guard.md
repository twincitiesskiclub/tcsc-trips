# Production Orphan Attached-Behavior Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the production migration recovery by refusing to replace an otherwise matching empty summary table when user triggers or row-security policies are attached.

**Architecture:** Extend the already locked `d8` catalog fingerprint with one behavior tuple: non-internal trigger count and policy count for the captured relation OID. Both counts must be zero before `DROP TABLE`; independent PostgreSQL tests prove the fixed refusal occurs before the drop. Fresh local-database bootstrap, offline SQL generation, and test process-group cleanup remain outside this production rollout by explicit user direction.

**Tech Stack:** Python 3.11+, Flask-Migrate/Alembic, SQLAlchemy 2, PostgreSQL 18, pytest, Bash, Git/GitHub, Render.

## Global Constraints

- Keep `create_app()` schema-neutral; do not restore runtime `db.create_all()`.
- Do not repair or work around clean local-database bootstrap in this rollout.
- Acquire `ACCESS EXCLUSIVE` before every orphan fingerprint query and hold it through replacement.
- Reject user triggers and policies with a fixed invariant-only error before `op.drop_table` is called.
- Do not include trigger names, policy names, Slack timestamps, or practice data in errors.
- Preserve all existing exact column/default/sequence/constraint/index/dependency/row checks.
- Run PostgreSQL tests serially against the suite-pinned localhost database with `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, and `SLACK_SIGNING_SECRET` blank.
- Do not access or write Slack while implementing or testing.
- Preserve the untracked `env` symlink and unrelated user changes.
- Defer offline Alembic SQL support and test-only process-group timeout cleanup.

---

### Task 1: Reject Attached Triggers and Policies Before Drop

**Files:**

- Modify: `migrations/versions/d8b2c6f4a901_add_practice_summary_posts.py`
- Modify: `tests/practices/migration_test_support.py`
- Modify: `tests/practices/test_practice_summary_post_migration.py`

**Interfaces:**

- Extends `_summary_table_fingerprint(bind, relation_oid)` with `"attached_behavior": tuple[int, int]` in `(user_trigger_count, policy_count)` order.
- Extends `summary_catalog_snapshot(connection)` with the same independent `"attached_behavior"` tuple.
- `_assert_exact_empty_create_all_orphan(...)` raises exactly `RuntimeError("practice_summary_posts orphan recovery refused: attached behavior mismatch")` when either count is nonzero.

- [ ] **Step 1: Add the independent behavior snapshot**

In `summary_catalog_snapshot(...)`, after the external-dependency query and before the row-count query, add:

```python
    attached_behavior = connection.execute(text("""
        SELECT
          (SELECT count(*)
           FROM pg_trigger AS trigger
           WHERE trigger.tgrelid = :oid
             AND NOT trigger.tgisinternal) AS user_trigger_count,
          (SELECT count(*)
           FROM pg_policy AS policy
           WHERE policy.polrelid = :oid) AS policy_count
    """), {"oid": oid}).one()
```

Add this field to the returned dictionary:

```python
        "attached_behavior": tuple(attached_behavior),
```

- [ ] **Step 2: Add trigger and policy refusal regressions**

Add these tests to `tests/practices/test_practice_summary_post_migration.py`:

```python
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
```

Add `"attached behavior mismatch"` to the refusal helper's allowed invariant tuple.

- [ ] **Step 3: Run the two tests and verify RED**

Run:

```bash
DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips \
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= \
  env/bin/pytest tests/practices/test_practice_summary_post_migration.py \
  -q -k 'user_trigger or policy_without_mutation'
```

Expected: both tests fail because the current fingerprint accepts the attached behavior and reaches `op.drop_table` instead of raising the fixed refusal.

- [ ] **Step 4: Add the locked production fingerprint query**

In `_summary_table_fingerprint(...)`, after `has_external_dependencies` and before the schema-qualified row query, add:

```python
    attached_behavior = bind.execute(sa.text("""
        SELECT
          (SELECT count(*)
           FROM pg_trigger AS trigger
           WHERE trigger.tgrelid = :oid
             AND NOT trigger.tgisinternal) AS user_trigger_count,
          (SELECT count(*)
           FROM pg_policy AS policy
           WHERE policy.polrelid = :oid) AS policy_count
    """), {"oid": relation_oid}).one()
```

Add this field to the returned fingerprint:

```python
        "attached_behavior": tuple(attached_behavior),
```

In `_assert_exact_empty_create_all_orphan(...)`, after the external-dependency invariant and before the row invariant, add:

```python
    if fingerprint["attached_behavior"] != (0, 0):
        _refuse_orphan_recovery("attached behavior mismatch")
```

Do not query by object name or surface any catalog values in the error.

- [ ] **Step 5: Run focused GREEN and adjacent migration gates**

Run:

```bash
DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips \
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= \
  env/bin/pytest tests/practices/test_practice_summary_post_migration.py -q
```

Expected: `28 passed`.

Then run:

```bash
DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips \
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= \
  env/bin/pytest \
    tests/test_app_startup.py \
    tests/scripts/test_release.py \
    tests/practices/test_plan_reaction_migration.py \
    tests/practices/test_practice_summary_post_migration.py \
    tests/practices/test_practice_migration_release.py -q
```

Expected: `36 passed`.

- [ ] **Step 6: Commit the guard**

```bash
git add \
  migrations/versions/d8b2c6f4a901_add_practice_summary_posts.py \
  tests/practices/migration_test_support.py \
  tests/practices/test_practice_summary_post_migration.py
git commit -m "fix(practices): reject attached summary behavior"
```

The commit must not include `env` or any unrelated file.

### Task 2: Re-verify and Release the Production Hotfix

**Files:**

- Verify only: complete branch from merge base `81b92ea6e56bbdcf77ee62fa3e015d8b3285d6e2`
- Reuse: `scripts/release.sh`
- Reuse: `scripts/seed_practice_plan_reaction_defaults.py`

**Interfaces:**

- Produces a reviewed hotfix PR whose sole Alembic head is `d8b2c6f4a901`.
- Produces an online Render pre-deploy with no scheduler, Bolt, or Socket Mode startup.
- Leaves the production seed in dry-run mode until the user separately approves its exact digest.

- [ ] **Step 1: Run fresh whole-branch gates**

```bash
DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips \
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= \
  env/bin/pytest -q
npm run test:practice-reactions
git diff --check 81b92ea..HEAD
bash -n scripts/release.sh
DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips \
TCSC_MIGRATION_ONLY=1 FLASK_APP=app:create_app \
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= \
  env/bin/flask db heads
git status --short
```

Expected: all Python and all 51 Node tests pass; the only head is `d8b2c6f4a901`; the only untracked entry is `env`.

- [ ] **Step 2: Request independent whole-branch re-review**

Review `81b92ea..HEAD` against the approved recovery design and the production-only amendment. Critical and Important findings block release; local empty-database bootstrap, offline SQL generation, and test process-group cleanup are explicitly deferred and must not be reintroduced as rollout blockers.

- [ ] **Step 3: Audit the production precondition read-only**

In one read-only transaction, verify:

```sql
SELECT version_num FROM alembic_version;

SELECT
  (SELECT count(*)
   FROM pg_trigger
   WHERE tgrelid = 'public.practice_summary_posts'::regclass
     AND NOT tgisinternal) AS user_trigger_count,
  (SELECT count(*)
   FROM pg_policy
   WHERE polrelid = 'public.practice_summary_posts'::regclass) AS policy_count,
  (SELECT count(*) FROM public.practice_summary_posts) AS row_count;
```

Expected: revision `e36bbec59bde` and all three counts zero. Stop without deploying if any value differs.

- [ ] **Step 4: Merge and deploy**

Push the branch, open the hotfix PR, wait for required checks, merge without rewriting commits, and deploy the merged `main` commit to `tcsc-registration`. Confirm pre-deploy logs show `e36 -> c4 -> d8`, successful release completion, and no scheduler, Bolt, or Socket Mode startup.

- [ ] **Step 5: Verify production read-only after deployment**

Verify revision `d8b2c6f4a901`, all four `c4` columns, canonical `now()` defaults, expected constraints, 19 coach plus 11 weekly identities, zero duplicate `(week_start, surface)` rows, and zero cross-week timestamp reuse.

- [ ] **Step 6: Complete the user-operated Preview and seed gates**

Ask the user to invoke `/tcsc practice-preview` in `C07G9RTMRT3`. End the writer-quiet window only after that deployed Preview succeeds. Then run the production reaction-default seed in dry-run mode, present its complete target diff and exact digest, and stop for fresh explicit approval before any seed commit.
