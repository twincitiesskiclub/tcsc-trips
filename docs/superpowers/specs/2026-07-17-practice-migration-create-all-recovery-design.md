# Practice Migration `create_all` Recovery Design

**Date:** 2026-07-17
**Status:** Approved

## Context

Render checked out merge commit `81b92ea6e56bbdcf77ee62fa3e015d8b3285d6e2`
and built it successfully. Its pre-deploy command, `flask db upgrade`, then
failed while applying `d8b2c6f4a901` because `practice_summary_posts` already
existed.

The failure is deterministic:

1. Flask constructs the application before running the `db upgrade` command.
2. `create_app()` imports the practice models and unconditionally calls
   `db.create_all()`.
3. SQLAlchemy creates the newly modeled `practice_summary_posts` table in its
   own committed transaction.
4. Alembic starts afterward and attempts to create the same table.

The failed Alembic transaction rolled back cleanly. Production remains at
`e36bbec59bde`; none of the four `c4f1a8e2d9b7` columns exists. The orphan
summary table is empty. Its columns and constraints match the ORM model, while
`created_at` and `updated_at` lack the `now()` server defaults required by
`d8`. This fingerprint confirms that `db.create_all()`, not Alembic, created
it.

## Goals

- Make Alembic the only application schema authority.
- Recover the one known empty ORM-created orphan transactionally.
- Fail closed for any pre-existing table that is populated or structurally
  different.
- Exercise the actual Flask/Alembic release lifecycle before redeployment.
- Complete the already-approved deployment without manual production DDL or
  revision stamping.

## Non-goals

- General-purpose migration repair for arbitrary database drift.
- Preserving data from an unexpected populated summary table.
- Adding retries, an outbox, maintenance mode, or a new deployment framework.
- Changing practice announcement, reaction, or authoring behavior.
- Repairing the historical migration root so a brand-new empty local database
  can reach head. The existing production database is already versioned at
  `e36bbec59bde`; empty-database bootstrap is separate legacy work and is not a
  gate for this production recovery.

## Design

### 1. Alembic becomes the schema authority

Remove the unconditional `db.create_all()` call from `create_app()`.
Application and Flask CLI startup must never create or alter schema objects.
This recovery targets existing versioned databases, including production.
Tests that own disposable schemas may continue to call `db.create_all()`
explicitly in their fixtures. The repository's pre-existing incomplete root
migration means clean local bootstrap requires separate follow-up work; this
hotfix does not reintroduce runtime schema creation to mask that legacy gap.

This is preferred over an environment flag in `scripts/release.sh`. A flag
would protect only one command while leaving web startup, Flask shell, and
other CLI commands able to mutate production schema before Alembic.

### 2. Pre-deploy starts no background consumers

`scripts/release.sh` runs the Flask migration command with
`TCSC_MIGRATION_ONLY=1` and explicitly blank Slack bot, app, and signing
credentials. `create_app()` still registers the Flask-Migrate extension, but
skips `init_scheduler()` when that flag is set. Because the credentials are
blank before Python imports the Slack module, the pre-deploy process cannot
initialize Bolt or Socket Mode either.

The flag affects process startup only; it never creates, alters, or bypasses
schema. Normal Render web workers retain the existing scheduler and Slack
behavior.

### 3. `d8` adopts only the exact empty orphan fingerprint

Before creating `practice_summary_posts`, migration `d8b2c6f4a901` checks
whether the relation already exists.

If it does not exist, the migration follows its normal create, validate, and
backfill path.

If it exists, the migration validates all of the following before mutation:

- it is a permanent ordinary table in the migration's target schema, with row
  security disabled;
- its column names, order, SQL types, and nullability match the ORM-created
  table;
- its `id` default and owned sequence match the ORM-created serial primary key,
  while the remaining non-timestamp columns have no defaults;
- its primary key, named `(week_start, surface)` unique constraint, named
  surface check constraint, indexes, and lack of foreign keys match;
- it has no user triggers, row-security policies, or explicit PostgreSQL
  publication memberships attached to it;
- `created_at` and `updated_at` have no server defaults, distinguishing the
  ORM-created shape from the canonical Alembic shape; and
- it contains zero rows.

The migration acquires an `ACCESS EXCLUSIVE` lock on the existing relation
before fingerprint or row validation and holds it through replacement. This
prevents a concurrent process from adding a row after the zero-row check. If
the relation cannot be locked as the expected table, recovery fails without
mutation.

Only that exact fingerprint is recoverable. The migration drops the empty
orphan and recreates the canonical table with Alembic's `now()` server
defaults. It then runs the existing same-week and cross-week legacy conflict
checks and performs the normal backfill.

Any populated table, canonical-looking table, malformed table, unexpected
constraint/index, or relation in another shape raises a clear migration error
before the table is dropped. The error reports the failed invariant without
including Slack timestamps or practice data.

### 4. Transaction boundary

The orphan validation, drop, canonical create, legacy conflict checks,
backfill, and Alembic version update all execute inside Alembic's PostgreSQL
transaction. If any step fails, PostgreSQL restores the original empty orphan
and leaves the database at `e36bbec59bde`.

Migration `c4` remains immediately before `d8` in that same upgrade. A
successful release therefore atomically produces the reaction columns, the
canonical summary table, its legacy backfill, and revision
`d8b2c6f4a901`.

## Testing

Tests must be written and observed failing before production changes.

Required coverage:

1. Application startup does not call `db.create_all()`.
2. Migration-only startup suppresses the scheduler, Bolt, and Socket Mode;
   the release command supplies the migration-only flag and blank credentials.
3. A normal pre-`d8` schema with no summary table upgrades successfully.
4. An exact empty ORM-shaped orphan is locked and adopted, yielding canonical
   timestamp defaults and the expected legacy backfill.
5. A non-empty orphan fails closed and remains unchanged.
6. A structurally different or canonical-looking pre-existing table fails
   closed and remains unchanged.
7. The actual Flask CLI release sequence starts at revision `e36bbec59bde`
   with no `c4` columns and the exact empty orphan, then reaches the sole
   Alembic head without pre-Alembic schema creation or background consumers.
8. From that same audited starting shape, a forced post-replacement failure
   restores the orphan definition, rolls back all `c4` columns, and leaves the
   Alembic revision at `e36bbec59bde`.
9. Migration downgrade/upgrade coverage, focused practice tests, and the full
   Python suite remain green.

All local Flask and test commands explicitly blank Slack credentials. No test
may initialize the application against production.

## Rollout

1. Implement and independently review the hotfix on a branch from merged
   `main`.
2. Run focused migration tests, the real release-lifecycle regression, the
   full Python suite, and the existing Node/Tailwind gates.
3. Merge a small hotfix PR.
4. Redeploy `tcsc-registration`; do not manually drop or stamp anything.
   Confirm pre-deploy logs contain no scheduler, Bolt, or Socket Mode startup.
5. Verify production revision `d8b2c6f4a901`, all four `c4` columns, canonical
   summary-table defaults/constraints, exactly 30 backfilled identities, and
   zero week/surface conflicts.
6. Test `/tcsc practice-preview` through Render in `C07G9RTMRT3` as the sole
   Socket Mode consumer.
7. End the practice-writer quiet window only after the deployed Preview passes.
8. Run the production seed dry run and stop for fresh digest approval.

If pre-deploy fails again, the old production service remains live. Stop and
inspect read-only state; never stamp a revision or repeat a commit whose
post-commit verification is unknown.
