# Task 3 Report: Idempotent draft generation

## What was created

- `app/practices/drafting.py` — `expected_slots(start_date, weeks=4) -> list[datetime]` and
  `generate_draft_block(start_date, weeks=4) -> list[Practice]`, implemented exactly as specified
  in the brief (no logic deviations).
- `tests/practices/test_drafting.py` — 4 tests, following the brief's test bodies verbatim for
  assertions/values, with two additions required by the task's safety constraints:
  1. Local `app` / `db_session` fixtures (the brief's test snippet referenced `db_session` but
     never defined it — every other file in `tests/practices/` defines its own copy of this
     fixture rather than relying on a shared conftest, e.g. `tests/practices/test_draft_exclusion.py`
     and `tests/practices/test_practice_draft_schema.py`; followed that pattern).
  2. Cleanup for every row created against the real local dev database:
     - `practice_days` fixture now `yield`s and deletes the `AppConfig` row it created in
       teardown (the brief's version set it and never removed it).
     - `test_generate_creates_drafts`, `test_generate_is_idempotent`, and
       `test_generate_skips_slots_that_already_have_a_real_practice` wrap the assertions in
       `try/finally` and delete every `Practice` row they created (and the `existing` row in the
       last test), matching the pattern in `tests/practices/test_draft_exclusion.py`.
     - `test_generate_is_idempotent`'s final assertion was changed from the brief's unscoped
       `Practice.query.count() == 6` to `Practice.query.filter(Practice.date.in_(slots)).count() == 6`
       (scoped to the exact slots this test creates). An unscoped count would see any existing
       practices in the local dev database — the task instructions explicitly called out this
       exact mistake from a previous review.

No other files were touched.

## TDD sequence

1. Wrote the failing test file, confirmed the exact expected failure:
   ```
   .venv/bin/python -m pytest tests/practices/test_drafting.py -v
   ...
   ModuleNotFoundError: No module named 'app.practices.drafting'
   ```
2. Implemented `app/practices/drafting.py` verbatim from the brief.
3. Reran and confirmed all 4 pass:
   ```
   .venv/bin/python -m pytest tests/practices/test_drafting.py -v
   tests/practices/test_drafting.py::test_expected_slots_covers_active_days_only PASSED
   tests/practices/test_drafting.py::test_generate_creates_drafts PASSED
   tests/practices/test_drafting.py::test_generate_is_idempotent PASSED
   tests/practices/test_drafting.py::test_generate_skips_slots_that_already_have_a_real_practice PASSED
   4 passed, 38 warnings in 1.22s
   ```
4. Ran the file a second consecutive time to confirm no state leaked from the first run (proof
   idempotency holds at the DB level, not just within a single fixture lifecycle) — 4 passed again,
   identical output.
5. Committed: `99f6772 feat(practices): idempotent draft block generation`.
6. Full suite:
   ```
   .venv/bin/python -m pytest tests/ -q --ignore=tests/wix_scrape
   1279 passed, 3048 warnings in 55.23s
   ```
   Baseline was 1275; 1279 = 1275 + 4 new tests, no regressions.

## Cleanup verification

Queried the real local dev DB directly (not through pytest) both after the standalone test-file
run and after the full-suite run:
```python
AppConfig.get('practice_days')  # -> None
Practice.query.filter(date range Aug 3 - Sep 1 2026).count()  # -> 0
```
Both zero in both cases — no orphan rows left behind.

## Anything surprising

- The brief's test snippet was not directly runnable as given: it referenced `db_session` without
  defining it, and had zero cleanup for the `AppConfig` row and the `Practice` rows it creates.
  This repo's convention (confirmed by grepping every `tests/practices/*.py` file) is that each
  test file defines its own `app`/`db_session` fixtures rather than sharing a conftest, so those
  were added locally rather than introducing a new shared conftest.
- Confirmed there is currently no persisted `practice_days` AppConfig row in the local dev DB (a
  seed migration inserts a default with `ON CONFLICT (key) DO NOTHING`, but it hadn't landed a row
  here), so the fixture's `AppConfig.set` was safe to add/remove without risking clobbering a real
  admin-configured value — explicit teardown was still added regardless, since that's the point of
  the task's safety constraint and this could differ in another environment.
- This report file (`.superpowers/sdd/task-3-report.md`) already existed with content from an
  unrelated earlier task ("Registration service" / events system) that reused the same task-number
  filename — it has been overwritten with this task's report.
- No other implementation deviations from the brief.

STATUS: DONE

## Fix round 1

### Fix 1 — cleanup not guaranteed on assertion failure

`test_generate_is_idempotent` (and, on audit, `test_generate_creates_drafts` and
`test_generate_skips_slots_that_already_have_a_real_practice`) cleaned up by iterating the list
`generate_draft_block` returned. That's only correct if the returned list is a complete and
accurate record of every row the call under test created — an assumption the idempotency test
itself was built to falsify. In `test_generate_is_idempotent`, only the *first* call's return value
was tracked; the second call's rows (the ones idempotency is supposed to prevent, and exactly the
rows that exist when the test is failing) were never deleted.

Replaced per-test tracked-list cleanup with a shared helper, `_delete_practices_in_slots(slots)`,
that does a scoped bulk delete by the slot datetimes the test computed via `expected_slots(...)`
up front (before calling `generate_draft_block`) — independent of what the function under test
did or returned:

```python
def _delete_practices_in_slots(slots):
    Practice.query.filter(Practice.date.in_(slots)).delete(synchronize_session=False)
    db.session.commit()
```

Applied to all three tests that create `Practice` rows. This also simplified
`test_generate_skips_slots_that_already_have_a_real_practice`, since the scoped delete covers both
the drafted rows and the manually-inserted "existing" real practice (its date is in `slots`) in one
statement.

**Verified the fix holds under failure, not just success.** Temporarily broke collision detection
in `generate_draft_block` (`app/practices/drafting.py`):

```python
taken = set()  # TEMP: broken collision detection for test verification
```

Ran the idempotent test in isolation:

```
.venv/bin/python -m pytest tests/practices/test_drafting.py::test_generate_is_idempotent -v
...
FAILED tests/practices/test_drafting.py::test_generate_is_idempotent - Assert...
INFO app:drafting.py:90 Drafted 6 practices for 2026-08-03 (+2 weeks)
INFO app:drafting.py:90 Drafted 6 practices for 2026-08-03 (+2 weeks)
1 failed, 26 warnings in 1.11s
```

The test correctly failed (both calls drafted 6 — 12 rows created instead of 6). Then queried the
real dev DB directly (not through pytest) to confirm cleanup still ran:

```python
Practice.query.filter(Practice.date >= date(2026,8,1), Practice.date < date(2026,9,1)).count()
# -> 0
```

Zero orphan rows despite the deliberate failure. Restored the real collision-detection query
(`taken = {row.date for row in Practice.query.with_entities(Practice.date).filter(Practice.date.in_(slots)).all()}`)
and reran — all 6 tests in the file pass again.

### Fix 2 — `expected_slots` emitting dates before `start_date`

Test-first. Added two tests to `tests/practices/test_drafting.py` against the *unmodified*
`expected_slots` (stashed the not-yet-written implementation fix via `git stash push -- app/practices/drafting.py` to test against the original code):

- `test_expected_slots_excludes_dates_before_start_date` — `expected_slots(date(2026, 8, 5), weeks=1)`
  (Wed Aug 5) must not include the Tuesday Aug 4 slot that Monday-normalisation would otherwise
  produce.
- `test_expected_slots_full_first_week_when_start_is_monday` — `expected_slots(date(2026, 8, 3), weeks=1)`
  (Mon Aug 3, i.e. start_date already on the week boundary) must still return the full 3-slot first
  week, proving the fix doesn't over-trim.

Ran against the original code:

```
.venv/bin/python -m pytest tests/practices/test_drafting.py -v
...
tests/practices/test_drafting.py::test_expected_slots_excludes_dates_before_start_date FAILED
tests/practices/test_drafting.py::test_expected_slots_full_first_week_when_start_is_monday PASSED
...
1 failed, 5 passed
```

Failed for the exact stated reason: `datetime(2026, 8, 4, 18, 15)` (before start_date) was present
in the result. The "full first week" test already passed against the original code — expected,
since it's the regression guard rather than the failing case.

Restored the implementation fix (`git stash pop`) in `app/practices/drafting.py`: kept the Monday
normalisation but added an early `continue` for any candidate day earlier than `start_date`:

```python
day = week_start + timedelta(days=weekday)
if day < start_date:
    continue
slots.append(datetime(day.year, day.month, day.day, hour, minute))
```

Reran the file: all 6 tests pass.

### Full suite

```
.venv/bin/python -m pytest tests/ -q --ignore=tests/wix_scrape
1281 passed, 3052 warnings in 55.28s
```

1281 = 1279 baseline + 2 new Fix-2 tests. No regressions.

### Dev DB orphan check (final)

Queried the real local dev DB directly after the full-suite run:

```python
AppConfig.get('practice_days')  # -> None
Practice.query.filter(Practice.date >= date(2026,8,1), Practice.date < date(2026,9,1)).count()  # -> 0
```

Both zero — no orphan rows left behind by this round's changes or verification steps.

STATUS: DONE
