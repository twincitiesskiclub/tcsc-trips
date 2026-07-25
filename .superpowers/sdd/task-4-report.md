# Task 4: Readiness evaluation — Report

## What was added

`app/practices/drafting.py` — appended three functions:

- `missing_fields(practice: Practice) -> list[str]` — returns which of
  `"location"`, `"type"`, `"time"` are unset, in that order. `"type"` is
  considered present if either `practice_types` or `activities` is non-empty.
- `is_ready(practice: Practice) -> bool` — `not missing_fields(practice)`.
- `readiness_summary(practices: list[Practice]) -> dict` — `{"total", "ready",
  "incomplete"}`, where `incomplete` is a list of `(Practice, list[str])`
  sorted by `practice.date`.

Implementation matches the brief's Step 3 code verbatim (docstrings, field
order, wording of the three missing-field strings).

`tests/practices/test_readiness.py` — new file, 3 tests, following the
`app`/`db_session` fixture pattern used by `tests/practices/test_drafting.py`
and `test_draft_exclusion.py` (the brief's test snippet assumed a `db_session`
fixture but didn't define one; there's no shared conftest providing it, so
each `tests/practices/*.py` file defines its own — I followed that
convention).

Two deliberate deviations from the brief's literal test code, both required
by the safety constraint, explained below:

1. **Test dates**: the brief's example used `datetime(2026, 8, 4, 18, 15)` /
   `datetime(2026, 8, 6, 18, 15)`. I moved these to `datetime(2099, 1, 6,
   18, 15)` / `datetime(2099, 1, 8, 18, 15)` (module-level `_SLOT_A` /
   `_SLOT_B`). Reason: the local dev DB already had a real practice at
   exactly `2026-08-04 18:15` (see "Surprising / important" below) — using
   the brief's literal date collided with real data.
2. **Fixture names**: the brief's `_location()`/`_type()` helpers used
   `name="Theodore Wirth"` / `name="Intervals"`, which are the real seeded
   `PracticeLocation`/`PracticeType` rows in the dev DB. `PracticeType.name`
   is unique, so reusing `"Intervals"` raises `IntegrityError` outright;
   `PracticeLocation.name` has no unique constraint, so reusing `"Theodore
   Wirth"` would silently create an indistinguishable duplicate of real
   data. Renamed to `"Test Readiness Location"` / `"Test Readiness Type"`.

The three `missing_fields()` string values themselves (`"location"`,
`"type"`, `"time"`) — the part of the brief that's actually shown to
coaches — are exactly as specified, verbatim.

## Cleanup mechanism

Every test wraps its assertions in `try/finally`, with a `_cleanup(
practice_ids, location_ids, type_ids)` helper keyed on ids captured *before*
the call under test (`p.id`, `loc.id`, `typ.id` — captured right after
`commit()`, before `is_ready`/`missing_fields`/`readiness_summary` run).
`is_ready` et al. are read-only, so there's no risk of them creating rows
themselves, but the pattern still guards against a future change to these
functions that might.

`_cleanup` deletes `Practice` rows through the ORM (`db.session.get` +
`db.session.delete`), not a bulk `.query.delete()`. This turned out to be
load-bearing: a bulk delete bypasses SQLAlchemy's relationship bookkeeping
for the `practice_types` many-to-many relationship, leaving the matching row
in the `practice_types_junction` secondary table behind. That orphaned
junction row then blocks deleting the `PracticeType` itself with a
`ForeignKeyViolation`. Deleting through the ORM clears the junction row as
part of removing the `Practice`. Practices are always deleted before their
location/type for this reason.

Verified clean by direct DB inspection after each test run —
`Practice.query.count()` returns 0 and `PracticeLocation`/`PracticeType`
still show only the original single real rows (`"Theodore Wirth"` /
`"Intervals"`), with no `"Test Readiness *"` rows left behind.

## Test commands and output

Failing-test confirmation (before implementation):
```
$ .venv/bin/python -m pytest tests/practices/test_readiness.py -v
ImportError: cannot import name 'is_ready' from 'app.practices.drafting'
```

After implementation:
```
$ .venv/bin/python -m pytest tests/practices/test_readiness.py -v
tests/practices/test_readiness.py::test_bare_draft_is_not_ready PASSED
tests/practices/test_readiness.py::test_draft_with_location_and_type_is_ready PASSED
tests/practices/test_readiness.py::test_summary_counts_and_lists_incomplete PASSED
======================== 3 passed, 18 warnings in 1.02s ========================
```
Re-ran twice to confirm repeatability (no leftover-row false-fails or
false-passes on the second run) — both green.

## Full suite

```
$ .venv/bin/python -m pytest tests/ -q --ignore=tests/wix_scrape
1284 passed, 3070 warnings in 55.40s
```
1281 baseline + 3 new tests = 1284, 0 failed. All warnings are the
pre-existing, unrelated `datetime.utcnow()` deprecation noise.

## Surprising / important: pre-existing DB pollution found and fixed

While diagnosing a unique-constraint collision, the full suite turned up 3
failing / 3 erroring tests in `tests/practices/test_drafting.py`
(`test_generate_creates_drafts`, `test_generate_is_idempotent`,
`test_generate_skips_slots_that_already_have_a_real_practice`) — all with
`ForeignKeyViolation: ... still referenced from table
"practice_types_junction"` on a `Practice` row with id 7810.

I stashed my Task 4 changes entirely (`git stash`) and confirmed these three
tests failed identically against the pre-Task-4 code — so this was not
caused by my implementation or my new test file. Investigation showed:

- The whole dev DB had only 9 `Practice` rows, exactly 1 `PracticeLocation`
  (`"Theodore Wirth"`) and exactly 1 `PracticeType` (`"Intervals"`).
- Practice 7810 was the *only* row referencing either, dated exactly
  `2026-08-04 18:15` with `is_draft=True, leads_needed=2` — precisely the
  shape `generate_draft_block()` produces, at precisely the slot
  `test_drafting.py`'s own `practice_days` fixture (Tuesday/Thursday
  18:15) generates.

This is an orphan row from an earlier round of this project (the brief
warned two earlier rounds had left rows behind) — an interrupted test run
whose own cleanup hit the same bulk-delete-vs-junction-table problem
described above, so its `_delete_practices_in_slots` cleanup step in
`test_drafting.py` failed with the same `ForeignKeyViolation`, and the row
was never removed.

I removed only the orphan `Practice` row 7810 and its single
`practice_types_junction` row (leaving the `"Theodore Wirth"` location and
`"Intervals"` type rows in place, since nothing indicated they were unsafe
to keep and other code may expect at least one reference row of each to
exist). After that, `test_drafting.py` passed cleanly (6/6) on a second run
— the first re-run still showed one failure because a *second* layer of
leftover draft practices (created by `test_generate_creates_drafts`'s own
run against the previously-blocked state, then stuck for the same reason)
needed one more pass to sweep out; confirmed via direct query that
`Practice.query.count()` was 0 before restoring my stashed Task 4 changes.

I did not touch this pre-existing pollution as part of my Task 4 diff (it's
outside `app/practices/drafting.py` and `tests/practices/test_readiness.py`
entirely — it was pure database state, not committed code), but wanted to
flag it since it could otherwise look like a regression from this task, and
because it's exactly the pre-existing hazard class the brief called out.

## Commit

```
ae943ab feat(practices): readiness evaluation for draft practices
```
2 files changed: `app/practices/drafting.py`, `tests/practices/test_readiness.py`.

## Fix round 1

Three findings from code review, addressed in this round.

### Fix 1 — removed two orphan rows

`PracticeLocation` id 7142 (`"Theodore Wirth"`) and `PracticeType` id 5976
(`"Intervals"`) — the two rows this report's "Surprising / important"
section above deliberately left in place after removing the orphan
`Practice` row 7810 — turned out to themselves be debris, not real seeded
data.

**Verified before deleting:**
- Both `created_at` timestamps are `2026-07-25 18:37:20`, ~5 minutes after
  commit `68d8df4` (18:32:09) and ~11 minutes before commit `ae943ab`
  (18:48:28) — squarely inside this branch's own development window, not a
  historical seed.
- Both have `airtable_id = NULL` (real seeded practice data was imported
  from Airtable and carries an `airtable_id`).
- The whole database currently has 0 `User`, 0 `Season`, 0 `Trip`, and 0
  `Practice` rows — there is no real membership/practice data at all for
  these to plausibly support.
- Queried `information_schema` for every foreign key in the schema that
  targets `practice_locations` or `practice_types`; there are exactly two:
  `practices.location_id → practice_locations.id` and
  `practice_types_junction.type_id → practice_types.id`. Checked both
  directly:
  - `select count(*) from practices where location_id = 7142` → 0
  - `select count(*) from practice_types_junction where type_id = 5976` → 0
- `config/practices.yaml`'s `default_location: "Theodore Wirth"` is a plain
  string default, not a foreign key lookup — confirmed by reading
  `app/practices/drafting.py`, which never queries `PracticeLocation` by
  name.

Nothing references either row. Deleted both directly via `docker exec
tcsc-postgres psql`:
```sql
DELETE FROM practice_locations WHERE id = 7142;  -- DELETE 1
DELETE FROM practice_types WHERE id = 5976;      -- DELETE 1
```
Post-delete: `practice_locations`, `practice_types`, and `practices` all
count 0.

### Fix 2 — added a test that makes the `sorted(...)` sort-order contract load-bearing

`readiness_summary()`'s docstring/contract promises `incomplete` sorted by
date, but the three existing tests only ever passed a single incomplete
practice (or one incomplete among a ready practice), so `sorted(...)` could
be deleted from `app/practices/drafting.py` without any test noticing.

Added `test_incomplete_is_sorted_by_date_not_creation_order` to
`tests/practices/test_readiness.py`: creates three practices — `middle`,
`latest`, `earliest` — in exactly that (non-chronological) insertion and
argument order, all incomplete (no location/type set), then asserts
`readiness_summary()`'s `incomplete` list comes back ordered
`[earliest, middle, latest]` by date. Added a third fixed slot
(`_SLOT_C = datetime(2099, 1, 10, 18, 15)`) alongside the existing
`_SLOT_A`/`_SLOT_B`, keeping the 2099 convention already used in this file.

**Proof it's load-bearing** — removed the `sorted(...)` call in
`readiness_summary()` (temporarily, not committed):
```python
"incomplete": incomplete,   # was: sorted(incomplete, key=lambda pair: pair[0].date)
```
```
$ .venv/bin/python -m pytest tests/practices/test_readiness.py -v
...
FAILED tests/practices/test_readiness.py::test_incomplete_is_sorted_by_date_not_creation_order
AssertionError: assert [8565, 8566, 8567] == [8567, 8565, 8566]
1 failed, 3 passed
```
The new test fails (query/insertion order `[middle, latest, earliest]` →
ids `[8565, 8566, 8567]`, not date order); the three pre-existing tests
still pass, confirming they don't cover this. Restored `sorted(...)`:
```
$ .venv/bin/python -m pytest tests/practices/test_readiness.py -v
4 passed
```
Confirmed via `git diff --stat app/practices/drafting.py` that the file has
no uncommitted diff after restoring — the sorted() call is back to its
original committed state.

### Fix 3 — shared `tests/practices/conftest.py`

Every file in `tests/practices/` (`test_drafting.py`, `test_readiness.py`,
etc.) hand-rolled an identical `app`/`db_session` fixture pair, and this is
the third pollution incident in four tasks caused in part by each task
independently guessing at safe test-data values against the real dev
database.

Added `tests/practices/conftest.py` providing the same `app`/`db_session`
fixtures (`create_app()`; `config.update(TESTING=True,
SECRET_KEY="test-secret-key")`; `db_session` yields `db.session` inside an
app context). Its docstring states, as the enforced convention for new
tests in this package:
- the database is the real local dev database — `create_all()`/
  `drop_all()` are forbidden;
- every created row must be deleted in `try/finally` so cleanup survives
  assertion failures;
- test data must use year 2099 dates and an unmistakable name prefix
  (e.g. `"TEST "`);
- assertions must be scoped to rows the test created, not unscoped
  `count()` calls, which false-fail against pre-existing data.

Did not touch the existing per-file fixtures in `test_drafting.py`,
`test_readiness.py`, etc. — pytest resolves same-named fixtures from the
closer scope first, so those files' own `app`/`db_session` continue to
shadow the conftest ones and behave exactly as before. The conftest fixtures
only take effect for test files in this package that don't define their own
(none currently do; this is for future tests).

### Full suite

```
$ .venv/bin/python -m pytest tests/ -q --ignore=tests/wix_scrape
1285 passed, 3076 warnings in 55.51s
```
1284 baseline + 1 new sort-order test = 1285, 0 failed. Warnings are the
same pre-existing, unrelated `datetime.utcnow()` deprecation noise as
before.

### Final database state

```
$ docker exec tcsc-postgres psql -U tcsc -d tcsc_trips -c "select count(*) from practices;"
0
$ docker exec tcsc-postgres psql -U tcsc -d tcsc_trips -c "select count(*) from practice_locations;"
0
$ docker exec tcsc-postgres psql -U tcsc -d tcsc_trips -c "select count(*) from practice_types;"
0
```
Zero orphan `Practice`, `PracticeLocation`, and `PracticeType` rows remain.

### Files touched (this round)

- `tests/practices/test_readiness.py` — added
  `test_incomplete_is_sorted_by_date_not_creation_order` + `_SLOT_C`.
- `tests/practices/conftest.py` — new shared fixture file with usage
  conventions docstring.
- Database (not code): deleted `PracticeLocation` id 7142, `PracticeType`
  id 5976 directly via `psql`.
