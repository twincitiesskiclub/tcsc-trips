# Practice Summary Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Coach and public weekly-summary Slack posts canonical per calendar week so empty weeks, late creates, and cross-week edits update the correct messages.

**Architecture:** Add one `PracticeSummaryPost` registry keyed by `(week_start, surface)` and keep the existing per-practice timestamp columns only as compatibility mirrors. Scheduled posting stages the canonical identity in the same compensated transaction as the legacy links; mutation refreshes resolve the registry by week and update source and destination weeks independently.

**Tech Stack:** Python 3.13, Flask, Flask-SQLAlchemy/SQLAlchemy, Alembic, PostgreSQL, Slack Bolt/Web API, pytest.

## Global Constraints

- `PracticeSummaryPost` is the only new model: one row per Monday `week_start` and `surface` (`coach_summary` or `weekly_summary`).
- A production post must register its `channel_id` and `message_ts`, even when the week is empty. Dry runs and channel-override previews never register.
- Keep `Practice.slack_coach_summary_ts` and `Practice.slack_weekly_summary_ts` as compatibility mirrors; do not remove or treat them as authoritative.
- Create refreshes a registered week but never creates an unscheduled summary.
- Cross-week edits refresh distinct source and destination weeks; never apply one week's timestamp to another week's content.
- Delete refreshes the affected week while excluding the not-yet-committed row.
- Admin Create/Edit and Slack Create/Quick Edit/Full Edit use the same registry-backed refresh behavior.
- Keep the local companion stopped and do not post to Slack while implementing or testing.
- Run persistent PostgreSQL tests serially.
- Use TDD for every behavior change and preserve the untracked `env` symlink.

---

## File Map

- Modify `app/practices/models.py`: define `PracticeSummaryPost`.
- Modify `app/practices/__init__.py`: export the model.
- Create `migrations/versions/d8b2c6f4a901_add_practice_summary_posts.py`: create and conflict-check/backfill the registry.
- Create `app/slack/practices/summary_posts.py`: canonical week calculation, registry lookup/staging, and constants.
- Modify `app/agent/routines/weekly_summary.py`: register public posts, including empty weeks, inside existing compensation.
- Modify `app/slack/practices/coach_review.py`: register Coach posts and resolve Coach edit-log targets from the registry.
- Modify `app/slack/practices/refresh.py`: refresh summaries through registry identity and refresh both weeks after a move.
- Modify `app/routes/admin_practices.py`: refresh summaries after Create and pass `previous_date` after Edit.
- Modify `app/slack/bolt_app.py`: pass `previous_date` from both edit paths and use the shared Create refresh in the background worker.
- Create focused registry, migration, posting, cross-week, and adapter tests under `tests/practices`, `tests/agent`, `tests/routes`, and `tests/slack`.

### Task 1: Add the Canonical Summary Registry and Safe Backfill

**Files:**

- Modify: `app/practices/models.py`
- Modify: `app/practices/__init__.py`
- Create: `migrations/versions/d8b2c6f4a901_add_practice_summary_posts.py`
- Create: `tests/practices/test_practice_summary_posts.py`
- Create: `tests/practices/test_practice_summary_post_migration.py`

**Interfaces:**

- Produces `PracticeSummaryPost` with fields `week_start`, `surface`, `channel_id`, and `message_ts`.
- Enforces `uq_practice_summary_post_week_surface` and `ck_practice_summary_post_surface`.
- Migration revision `d8b2c6f4a901` follows `c4f1a8e2d9b7` and backfills only non-conflicting legacy identities.

- [ ] **Step 1: Write failing model and migration tests**

Create a model test that proves one identity per surface/week and allows the two surfaces to coexist:

```python
def test_summary_identity_is_unique_per_week_and_surface(app):
    with app.app_context():
        coach = PracticeSummaryPost(
            week_start=date(2026, 7, 13),
            surface="coach_summary",
            channel_id="C-COACH",
            message_ts="100.1",
        )
        public = PracticeSummaryPost(
            week_start=date(2026, 7, 13),
            surface="weekly_summary",
            channel_id="C-PUBLIC",
            message_ts="100.2",
        )
        db.session.add_all([coach, public])
        db.session.commit()

        db.session.add(PracticeSummaryPost(
            week_start=date(2026, 7, 13),
            surface="weekly_summary",
            channel_id="C-OTHER",
            message_ts="100.3",
        ))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
```

Create PostgreSQL migration tests using an isolated schema. The success case creates a minimal legacy `practices` table, inserts rows spanning two weeks, runs `upgrade()`, and asserts exactly one row per linked week/surface. The conflict case inserts two distinct public timestamps in one week and asserts `upgrade()` raises `DBAPIError` containing `conflicting legacy practice summary timestamps`. Downgrade must remove the table.

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
env/bin/pytest tests/practices/test_practice_summary_posts.py tests/practices/test_practice_summary_post_migration.py -q
```

Expected: collection fails because the model and migration module do not exist.

- [ ] **Step 3: Add the minimal model**

Add to `app/practices/models.py`:

```python
class PracticeSummaryPost(db.Model):
    """Canonical Slack identity for one weekly practice-summary surface."""

    __tablename__ = "practice_summary_posts"

    id = db.Column(db.Integer, primary_key=True)
    week_start = db.Column(db.Date, nullable=False)
    surface = db.Column(db.String(32), nullable=False)
    channel_id = db.Column(db.String(50))
    message_ts = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        db.UniqueConstraint(
            "week_start",
            "surface",
            name="uq_practice_summary_post_week_surface",
        ),
        db.CheckConstraint(
            "surface IN ('coach_summary', 'weekly_summary')",
            name="ck_practice_summary_post_surface",
        ),
    )
```

Export it from `app/practices/__init__.py`.

- [ ] **Step 4: Add the conflict-checking migration**

Create the Alembic revision with this complete `upgrade()` behavior:

```python
revision = "d8b2c6f4a901"
down_revision = "c4f1a8e2d9b7"


def upgrade():
    op.create_table(
        "practice_summary_posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("surface", sa.String(32), nullable=False),
        sa.Column("channel_id", sa.String(50)),
        sa.Column("message_ts", sa.String(50), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "week_start", "surface",
            name="uq_practice_summary_post_week_surface",
        ),
        sa.CheckConstraint(
            "surface IN ('coach_summary', 'weekly_summary')",
            name="ck_practice_summary_post_surface",
        ),
    )
    op.execute(sa.text("""
        DO $$
        BEGIN
          IF EXISTS (
            WITH legacy AS (
              SELECT date_trunc('week', date)::date AS week_start,
                     'coach_summary'::text AS surface,
                     slack_coach_summary_ts AS message_ts
              FROM practices WHERE slack_coach_summary_ts IS NOT NULL
              UNION ALL
              SELECT date_trunc('week', date)::date,
                     'weekly_summary'::text,
                     slack_weekly_summary_ts
              FROM practices WHERE slack_weekly_summary_ts IS NOT NULL
            )
            SELECT 1 FROM legacy
            GROUP BY week_start, surface
            HAVING count(DISTINCT message_ts) > 1
          ) THEN
            RAISE EXCEPTION
              'conflicting legacy practice summary timestamps';
          END IF;
        END $$;
    """))
    op.execute(sa.text("""
        INSERT INTO practice_summary_posts
            (week_start, surface, channel_id, message_ts)
        SELECT date_trunc('week', date)::date,
               'coach_summary', NULL, min(slack_coach_summary_ts)
        FROM practices
        WHERE slack_coach_summary_ts IS NOT NULL
        GROUP BY date_trunc('week', date)::date
        UNION ALL
        SELECT date_trunc('week', date)::date,
               'weekly_summary', NULL, min(slack_weekly_summary_ts)
        FROM practices
        WHERE slack_weekly_summary_ts IS NOT NULL
        GROUP BY date_trunc('week', date)::date
    """))


def downgrade():
    op.drop_table("practice_summary_posts")
```

Legacy `channel_id` is nullable because the old row model never stored a summary-specific channel. Runtime refresh resolves the known Coach/public fallback and saves the successful channel on the registry row.

- [ ] **Step 5: Run the focused tests and migration lineage check**

```bash
env/bin/pytest tests/practices/test_practice_summary_posts.py tests/practices/test_practice_summary_post_migration.py -q
DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips env/bin/flask db heads
```

Expected: both tests pass and the only head is `d8b2c6f4a901`.

- [ ] **Step 6: Commit**

```bash
git add app/practices/models.py app/practices/__init__.py migrations/versions/d8b2c6f4a901_add_practice_summary_posts.py tests/practices/test_practice_summary_posts.py tests/practices/test_practice_summary_post_migration.py
git commit -m "feat(practices): register weekly Slack summaries"
```

### Task 2: Add Focused Registry Helpers

**Files:**

- Create: `app/slack/practices/summary_posts.py`
- Create: `tests/slack/test_practice_summary_registry.py`

**Interfaces:**

- Produces `COACH_SUMMARY = "coach_summary"` and `WEEKLY_SUMMARY = "weekly_summary"`.
- Produces `week_start_date(value: date | datetime) -> date`.
- Produces `find_summary_post(value, surface) -> PracticeSummaryPost | None`.
- Produces `stage_summary_post(*, value, surface, channel_id, message_ts, practices=()) -> PracticeSummaryPost`; it mutates the session but never commits.
- Produces `summary_post_channel(record) -> str | None`, resolving legacy null channels only through the existing configured channel helpers.

- [ ] **Step 1: Write failing helper tests**

```python
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (date(2026, 7, 13), date(2026, 7, 13)),
        (date(2026, 7, 19), date(2026, 7, 13)),
        (datetime(2026, 7, 16, 18, 5), date(2026, 7, 13)),
    ],
)
def test_week_start_date_is_monday(value, expected):
    assert week_start_date(value) == expected


def test_stage_summary_post_upserts_identity_and_legacy_links(app):
    with app.app_context():
        practice = make_practice(datetime(2026, 7, 14, 18, 15))
        record = stage_summary_post(
            value=practice.date,
            surface=WEEKLY_SUMMARY,
            channel_id="C-WEEK",
            message_ts="100.1",
            practices=[practice],
        )
        db.session.commit()
        assert record.week_start == date(2026, 7, 13)
        assert record.channel_id == "C-WEEK"
        assert practice.slack_weekly_summary_ts == "100.1"

        same = stage_summary_post(
            value=practice.date,
            surface=WEEKLY_SUMMARY,
            channel_id="C-WEEK",
            message_ts="100.2",
            practices=[practice],
        )
        assert same.id == record.id
        assert same.message_ts == "100.2"
```

Also test that `practices=[]` creates the registry row, unknown surfaces raise
`ValueError`, and `stage_summary_post` never calls `db.session.commit()`.

- [ ] **Step 2: Run tests and verify RED**

```bash
env/bin/pytest tests/slack/test_practice_summary_registry.py -q
```

Expected: import failure for `app.slack.practices.summary_posts`.

- [ ] **Step 3: Implement the helpers**

Use one attribute map and no generic repository layer:

```python
COACH_SUMMARY = "coach_summary"
WEEKLY_SUMMARY = "weekly_summary"
SUMMARY_SURFACES = (COACH_SUMMARY, WEEKLY_SUMMARY)
_LEGACY_TS_FIELDS = {
    COACH_SUMMARY: "slack_coach_summary_ts",
    WEEKLY_SUMMARY: "slack_weekly_summary_ts",
}


def week_start_date(value):
    day = value.date() if isinstance(value, datetime) else value
    return day - timedelta(days=day.weekday())


def find_summary_post(value, surface):
    if surface not in SUMMARY_SURFACES:
        raise ValueError(f"Unknown practice summary surface: {surface}")
    return PracticeSummaryPost.query.filter_by(
        week_start=week_start_date(value), surface=surface
    ).one_or_none()


def stage_summary_post(
    *, value, surface, channel_id, message_ts, practices=()
):
    record = find_summary_post(value, surface)
    if record is None:
        record = PracticeSummaryPost(
            week_start=week_start_date(value), surface=surface
        )
        db.session.add(record)
    record.channel_id = channel_id
    record.message_ts = message_ts
    field = _LEGACY_TS_FIELDS[surface]
    for practice in practices:
        setattr(practice, field, message_ts)
    return record
```

`summary_post_channel()` returns a non-empty `record.channel_id` first. For a
legacy null Coach channel it returns `COLLAB_CHANNEL_ID`; for a legacy null
public channel it calls `_get_announcement_channel()`. It does not commit.

- [ ] **Step 4: Run focused tests and commit**

```bash
env/bin/pytest tests/slack/test_practice_summary_registry.py -q
git add app/slack/practices/summary_posts.py tests/slack/test_practice_summary_registry.py
git commit -m "feat(slack): resolve weekly summary identities"
```

Expected: focused tests pass.

### Task 3: Register Public and Coach Posts, Including Empty Weeks

**Files:**

- Modify: `app/agent/routines/weekly_summary.py`
- Modify: `app/slack/practices/coach_review.py`
- Modify: `tests/agent/test_weekly_summary.py`
- Create: `tests/slack/test_coach_summary_posting.py`

**Interfaces:**

- Both production posting functions call `stage_summary_post(...)` before their link commit.
- Existing compensation remains one attempt: clean up the new Slack post; if cleanup fails, retry the known registry/link commit once; otherwise report `ambiguous_orphan`.
- Channel-override previews do not call `stage_summary_post`.

- [ ] **Step 1: Add failing public-post tests**

Replace the old empty-week expectation with:

```python
def test_empty_production_week_registers_refresh_identity():
    outcome = run_with_query(
        FakeQuery([]), week_start=date(2026, 7, 13), dry_run=False
    )
    outcome.stage_summary_post.assert_called_once_with(
        value=date(2026, 7, 13),
        surface="weekly_summary",
        channel_id="C-WEEK",
        message_ts="1783980000.000100",
        practices=[],
    )
    assert outcome.result["refresh_linked"] is True
    outcome.db.session.commit.assert_called_once_with()
```

Extend the non-empty, preview, commit-cleanup, recovered, and ambiguous tests
to assert registry staging occurs only in production and occurs on both the
initial and recovery commit attempts.

- [ ] **Step 2: Add failing Coach-post tests**

Pin an empty production Coach week, a non-empty week, a channel override, and
the same three commit-failure outcomes. Each successful production call must
stage `surface="coach_summary"` with `COLLAB_CHANNEL_ID`; override calls must
post but never stage or commit.

- [ ] **Step 3: Run the posting tests and verify RED**

```bash
env/bin/pytest tests/agent/test_weekly_summary.py tests/slack/test_coach_summary_posting.py -q
```

Expected: empty production weeks still skip persistence, Coach posting lacks
registry staging/compensation, and the new assertions fail.

- [ ] **Step 4: Stage the public registry row inside existing compensation**

Remove the `if not practices: ... refresh_linked=False` return. Update
`apply_links()` so every production post stages the canonical row:

```python
def apply_links():
    stage_summary_post(
        value=start,
        surface=WEEKLY_SUMMARY,
        channel_id=channel_id,
        message_ts=message_ts,
        practices=practices,
    )
```

Keep the existing rollback, Slack cleanup, one recovery commit, and ambiguous
orphan result. `restore_originals()` restores only in-memory legacy fields;
the session rollback restores the registry row.

- [ ] **Step 5: Give Coach posting the same bounded compensation**

After `chat_postMessage`, reject a missing timestamp. Return immediately for a
channel override without staging. For production, stage the Coach identity,
commit, and on failure follow the same cleanup/recovery shape as the public
routine using `_delete_slack_message`. Preserve the existing result keys and
add `refresh_linked`, `cleanup`, `recovered`, or `ambiguous_orphan` where
applicable.

- [ ] **Step 6: Run focused tests and commit**

```bash
env/bin/pytest tests/agent/test_weekly_summary.py tests/slack/test_coach_summary_posting.py -q
git add app/agent/routines/weekly_summary.py app/slack/practices/coach_review.py tests/agent/test_weekly_summary.py tests/slack/test_coach_summary_posting.py
git commit -m "fix(slack): persist empty weekly summary identities"
```

Expected: all posting and compensation tests pass.

### Task 4: Refresh Registered Source and Destination Weeks

**Files:**

- Modify: `app/slack/practices/refresh.py`
- Modify: `app/slack/practices/coach_review.py`
- Modify: `tests/slack/test_refresh.py`
- Modify: `tests/slack/test_refresh_delete_exclusion.py`
- Create: `tests/slack/test_cross_week_summary_refresh.py`

**Interfaces:**

- Extends `refresh_practice_posts(..., previous_date=None)`.
- Produces `refresh_registered_practice_summaries(value, *, exclude_practice_id=None) -> dict[str, dict]` so delete recovery can rebuild a week without re-running announcement or collab work.
- Summary surfaces resolve `PracticeSummaryPost` from `summary_date or practice.date`; registry entries, not row timestamps, determine channel/ts.
- A cross-week edit adds `previous_coach_summary` and `previous_weekly_summary` results while the existing keys describe the destination week.
- Extends `log_coach_summary_edit(..., channel_id=None, message_ts=None)` so the caller supplies the current registry identity.

- [ ] **Step 1: Write failing cross-week tests**

Create week A and week B, two registry rows per week, and practices in each.
Move one practice A→B in the database, then call:

```python
results = refresh_practice_posts(
    moved,
    change_type="edit",
    previous_date=datetime(2026, 7, 7, 18, 15),
)
```

Patch the two builders to capture practice IDs by message timestamp. Assert:

```python
assert updates["coach-A"] == [remaining_a.id]
assert updates["public-A"] == [remaining_a.id]
assert updates["coach-B"] == [existing_b.id, moved.id]
assert updates["public-B"] == [existing_b.id, moved.id]
assert results["previous_coach_summary"]["success"] is True
assert results["previous_weekly_summary"]["success"] is True
```

Add cases where only source or destination is registered, and where the moved
practice was the only source member: the source post still updates with empty
content and its registry row remains.

- [ ] **Step 2: Convert same-week/delete tests to canonical registry fixtures**

Change `tests/slack/test_refresh_delete_exclusion.py` so the fixture creates
one `PracticeSummaryPost` per surface. Keep the existing assertions that a
pending delete is excluded and cancellation remains visible. Add an assertion
that the exact registered channel and timestamp are used even when the
practice's legacy mirror contains a different timestamp.

- [ ] **Step 3: Run refresh tests and verify RED**

```bash
env/bin/pytest tests/slack/test_refresh.py tests/slack/test_refresh_delete_exclusion.py tests/slack/test_cross_week_summary_refresh.py -q
```

Expected: refresh still derives the week from the new date and uses stale row
timestamps; source-week assertions fail.

- [ ] **Step 4: Implement the independent week-level refresh helper**

Extract the current Coach and public builder/update bodies behind two focused
week functions. Then expose:

```python
def refresh_registered_practice_summaries(
    value,
    *,
    exclude_practice_id=None,
):
    return {
        "coach_summary": _refresh_coach_summary_for_week(
            value,
            exclude_practice_id=exclude_practice_id,
        ),
        "weekly_summary": _refresh_weekly_summary_for_week(
            value,
            exclude_practice_id=exclude_practice_id,
        ),
    }
```

Each week function resolves its own `PracticeSummaryPost`, returns
`{"skipped": "absent"}` when none exists, queries the full current week, and
applies `Practice.id != exclude_practice_id` only when explicitly supplied.
This helper never commits practice mutations and never touches announcement or
collab surfaces.

Update `_week_bounds` to accept both `date` and `datetime`, because delete
recovery supplies a canonical Monday date:

```python
def _week_bounds(value):
    start = datetime.combine(week_start_date(value), time.min)
    return start, start + timedelta(days=7)
```

- [ ] **Step 5: Make dispatcher summary surfaces registry-backed**

Allow a `PracticeSurface` with `ts_field=None` to run its refresh function
without row-level presence gating:

```python
def is_present(self, practice):
    return self.ts_field is None or bool(
        getattr(practice, self.ts_field, None)
    )
```

Register both summary surfaces with `ts_field=None`. In each summary refresh:

```python
target_date = summary_date or practice.date
record = find_summary_post(target_date, COACH_SUMMARY)
if record is None:
    return {"skipped": "absent"}
week_start, week_end = _week_bounds(target_date)
```

Use `record.message_ts` and `summary_post_channel(record)`. When a legacy null
Coach channel succeeds through one of the existing fallback channels, save
that channel on the record best-effort. For delete, continue filtering
`Practice.id != practice.id`.

- [ ] **Step 6: Refresh the previous week exactly once**

Extend the dispatcher signature:

```python
def refresh_practice_posts(
    practice,
    change_type="edit",
    actor_slack_id=None,
    notify=True,
    announcement_notice=None,
    previous_plan_reactions=None,
    previous_date=None,
):
```

After the normal destination surfaces, if `change_type == "edit"` and the
Monday for `previous_date` differs from `practice.date`, call
`refresh_registered_practice_summaries(previous_date)`. Store its two results
under `previous_coach_summary` and `previous_weekly_summary`. Do not re-run
announcement, collab, reactions, or edit logs for the source week. Each normal
summary-surface wrapper forwards `exclude_practice_id=practice.id` to its own
week function when `change_type == "delete"`; recovery uses the public helper
with no exclusion.

- [ ] **Step 7: Resolve Coach edit logs from the destination registry**

In `_post_edit_logs`, load the current week's Coach record. Only call
`log_coach_summary_edit` when it exists, passing its channel and timestamp.
Update the logging function to use explicit arguments when supplied and retain
its old argument behavior only as a compatibility fallback.

- [ ] **Step 8: Run focused tests and commit**

```bash
env/bin/pytest tests/slack/test_refresh.py tests/slack/test_refresh_delete_exclusion.py tests/slack/test_cross_week_summary_refresh.py -q
git add app/slack/practices/refresh.py app/slack/practices/coach_review.py tests/slack/test_refresh.py tests/slack/test_refresh_delete_exclusion.py tests/slack/test_cross_week_summary_refresh.py
git commit -m "fix(slack): refresh summaries by calendar week"
```

Expected: source/destination, missing-summary, empty-source, same-week, delete,
and logging tests pass.

### Task 5: Wire Every Create and Edit Adapter to the Shared Refresh

**Files:**

- Modify: `app/routes/admin_practices.py`
- Modify: `app/slack/bolt_app.py`
- Modify: `tests/routes/test_admin_practices_routes.py`
- Modify: `tests/routes/test_admin_practice_plan_reactions.py`
- Modify: `tests/slack/test_practice_create_modal.py`
- Modify: `tests/slack/test_practice_edit_full.py`
- Create: `tests/slack/test_practice_quick_edit.py`

**Interfaces:**

- Admin Create calls `refresh_practice_posts(practice, change_type="create")` after commit.
- Admin Edit passes its already captured `previous_date`.
- Slack Quick Edit captures `previous_date` before mutation and passes it.
- Full Edit post-save passes the existing `previous_date` argument.
- Slack Create background worker accepts `practice_id`, reloads the row, and calls the shared `create` refresh before sending confirmation.

- [ ] **Step 1: Add failing Admin adapter tests**

Patch `app.slack.practices.refresh_practice_posts`. Assert successful Admin
Create calls it once with the committed practice and `change_type="create"`.
Assert a cross-week Admin Edit passes the exact old datetime as
`previous_date`. A summary failure is best-effort for Create and must not roll
back or claim that the row was not created.

- [ ] **Step 2: Add failing Slack adapter tests**

For Quick Edit and Full Edit, assert the post-save dispatcher receives the old
date and forwards it to `refresh_practice_posts`. For Slack Create, run the
background helper synchronously with a saved `practice_id`; assert it reloads
that row and calls:

```python
refresh_practice_posts(practice, change_type="create", notify=False)
```

The helper still posts the existing ephemeral confirmation. If refresh fails,
it logs the result and still sends truthful creation confirmation because the
database row is already committed.

- [ ] **Step 3: Run adapter tests and verify RED**

```bash
env/bin/pytest tests/routes/test_admin_practices_routes.py tests/routes/test_admin_practice_plan_reactions.py tests/slack/test_practice_create_modal.py tests/slack/test_practice_edit_full.py tests/slack/test_practice_quick_edit.py -q
```

Expected: Admin Create does not refresh, old dates are not forwarded, and the
Slack background helper only rebuilds Coach Review directly.

- [ ] **Step 4: Wire the Admin routes**

After Admin Create commits, call the dispatcher inside a contained best-effort
block and log failures. In Admin Edit, add `previous_date=previous_date` to the
existing call. Remove `_week_coach_summary_ts`; canonical discovery now belongs
to the registry.

- [ ] **Step 5: Wire Slack Quick Edit and Full Edit**

Capture `previous_date = practice.date` before applying the timestamp in Quick
Edit and pass it to the dispatcher. In `_run_practice_edit_full_post_save`, add
`previous_date=previous_date` to the existing dispatcher call.

- [ ] **Step 6: Replace the Slack Create one-surface rebuild**

Pass `practice_id` into `_post_practice_create_updates`. Inside its application
context, reload `Practice`, call the shared `create` refresh with
`notify=False`, log per-surface failures, then send the existing ephemeral
confirmation. Delete the duplicated Coach query/builder/update code from that
helper. Keep the originating Coach timestamp mirror on the created row for
compatibility.

- [ ] **Step 7: Run adapter and adjacent regressions, then commit**

```bash
env/bin/pytest tests/routes/test_admin_practices_routes.py tests/routes/test_admin_practice_plan_reactions.py tests/slack/test_practice_create_modal.py tests/slack/test_practice_edit_full.py tests/slack/test_practice_quick_edit.py tests/slack/test_cross_week_summary_refresh.py -q
git add app/routes/admin_practices.py app/slack/bolt_app.py tests/routes/test_admin_practices_routes.py tests/routes/test_admin_practice_plan_reactions.py tests/slack/test_practice_create_modal.py tests/slack/test_practice_edit_full.py tests/slack/test_practice_quick_edit.py
git commit -m "fix(practices): refresh summaries after create and moves"
```

Expected: all adapter tests pass without external Slack calls.

### Task 6: Verify Summary Identity End to End

**Files:**

- No planned file changes; this task verifies the committed Tasks 1–5.

**Interfaces:**

- No new interface; this is the integration gate before the delete-recovery plan.

- [ ] **Step 1: Run every summary-focused suite serially**

```bash
env/bin/pytest tests/practices/test_practice_summary_posts.py tests/practices/test_practice_summary_post_migration.py tests/slack/test_practice_summary_registry.py tests/agent/test_weekly_summary.py tests/slack/test_coach_summary_posting.py tests/slack/test_refresh.py tests/slack/test_refresh_delete_exclusion.py tests/slack/test_cross_week_summary_refresh.py tests/routes/test_admin_practices_routes.py tests/slack/test_practice_create_modal.py tests/slack/test_practice_edit_full.py tests/slack/test_practice_quick_edit.py -q
```

Expected: all pass.

- [ ] **Step 2: Check the migration graph and source hygiene**

```bash
DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips env/bin/flask db heads
git diff --check
rg -n "slack_(coach|weekly)_summary_ts" app/slack/practices/refresh.py
```

Expected: one Alembic head (`d8b2c6f4a901`), clean diff, and no authoritative
summary update still reads a per-practice timestamp.

- [ ] **Step 3: Request a focused code review**

Ask the reviewer to verify migration/backfill safety, production-versus-preview
registration, cross-week two-sided updates, empty-week identity, delete
exclusion, and all Admin/Slack adapters. Fix only confirmed findings with a
new failing regression first.

- [ ] **Step 4: Commit any review-only corrections**

If no changes are required, do not create an empty commit. Otherwise:

```bash
git add app/practices/models.py app/practices/__init__.py migrations/versions/d8b2c6f4a901_add_practice_summary_posts.py app/slack/practices/summary_posts.py app/agent/routines/weekly_summary.py app/slack/practices/coach_review.py app/slack/practices/refresh.py app/routes/admin_practices.py app/slack/bolt_app.py tests/practices/test_practice_summary_posts.py tests/practices/test_practice_summary_post_migration.py tests/slack/test_practice_summary_registry.py tests/agent/test_weekly_summary.py tests/slack/test_coach_summary_posting.py tests/slack/test_refresh.py tests/slack/test_refresh_delete_exclusion.py tests/slack/test_cross_week_summary_refresh.py tests/routes/test_admin_practices_routes.py tests/routes/test_admin_practice_plan_reactions.py tests/slack/test_practice_create_modal.py tests/slack/test_practice_edit_full.py tests/slack/test_practice_quick_edit.py
git commit -m "fix(slack): harden weekly summary identity"
```
