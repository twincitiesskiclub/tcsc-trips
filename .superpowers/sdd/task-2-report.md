# Task 2 Report: `published_practices()` helper and draft guards

Branch: `lead-availability`
Commit: `2da03d3` — "feat(practices): route member-visible reads through published_practices()"

Note: this file previously held a report for an unrelated "Task 2" (event
templates config/loader) from a different plan. That content has been
replaced with the report for this task (lead-availability, Task 2:
`published_practices()` helper and draft guards), per the explicit report
path given in this task's instructions.

## Helper added

`app/practices/service.py` (end of file):

```python
def published_practices():
    """Practice query excluding drafts.

    Drafts exist so availability can be collected against real details before
    members see anything, so every member-visible read must go through here.
    Returns a Query, so callers keep chaining .filter()/.order_by() as before.
    """
    from app.practices.models import Practice

    return Practice.query.filter(Practice.is_draft.is_(False))
```

## Call sites changed (10 of 10)

Each site had `Practice.query.filter(` swapped for `published_practices().filter(`, with an added `from app.practices.service import published_practices` import at the appropriate scope (function-local where the existing `Practice` import was function-local, module-level import block otherwise). No existing filter argument was altered.

1. `app/scheduler.py:463` — `_get_upcoming_strength_practices` (weekly unannounced-strength lookup)
2. `app/scheduler.py:523` (was `:522`) — `run_practice_announcements_job`, morning-run window
3. `app/scheduler.py:544` (was `:543`) — `run_practice_announcements_job`, evening-run window
4. `app/slack/practices/refresh.py:328` (was `:331`) — `_refresh_coach_summary_for_week`
5. `app/slack/practices/refresh.py:411` (was `:414`) — `_refresh_weekly_summary_for_week`
6. `app/agent/routines/morning_check.py:65` (was `:64`) — `run_morning_check`
7. `app/agent/routines/lead_verification.py:135` (was `:134`) — lead-verification window query
8. `app/agent/routines/weekly_summary.py:64` (was `:63`) — `run_weekly_summary`
9. `app/agent/routines/pre_practice.py:50` (was `:49`) — 48h workout-reminder window
10. `app/agent/routines/pre_practice.py:153` (was `:152`) — 24h lead-confirmation window

Line numbers shifted by +1 to +3 after adding import lines; confirmed via `grep -n "Practice.query"` across all six watched files returns zero matches post-change.

## Test added

`tests/practices/test_draft_exclusion.py` — three tests, following the brief's bodies verbatim with two additions required to satisfy the safety constraints:

- Added `app`/`db_session` fixtures (the brief's snippet used `db_session` but didn't define it — following the pattern in `tests/practices/test_practice_draft_schema.py`).
- Wrapped each DB-writing test in `try/finally` that deletes the created `Practice` rows, since the test DB is the real local dev DB and the brief's snippet had no cleanup.
- Hardened the guard test (`test_no_member_facing_query_uses_bare_practice_query`) per the judgment call in the task instructions: it now strips `#`-comments before checking for `Practice.query`, so a comment mentioning the string can't produce a false positive, and the failure message explicitly says to replace with `published_practices()` from `app.practices.service`.

## Test commands and output

Failing-first (Step 2):
```
$ .venv/bin/python -m pytest tests/practices/test_draft_exclusion.py -v
ImportError: cannot import name 'published_practices' from 'app.practices.service'
```
Confirmed failing for the expected reason (helper didn't exist yet).

After implementation (Step 5):
```
$ .venv/bin/python -m pytest tests/practices/test_draft_exclusion.py -v
tests/practices/test_draft_exclusion.py::test_published_practices_excludes_drafts PASSED
tests/practices/test_draft_exclusion.py::test_published_practices_is_chainable PASSED
tests/practices/test_draft_exclusion.py::test_no_member_facing_query_uses_bare_practice_query PASSED
3 passed in 0.90s
```

Full suite, before fixing fallout (first run after call-site edits, before touching any test file):
```
$ .venv/bin/python -m pytest tests/ -q --ignore=tests/wix_scrape
28 failed, 1247 passed
```

Full suite, after fixes described below:
```
$ .venv/bin/python -m pytest tests/ -q --ignore=tests/wix_scrape
1275 passed in 55.47s
```

Baseline was 1272 passing; 1272 + 3 new tests = 1275. No regressions, no skips.

## Surprising fallout (the main finding of this task)

The 28 failures were all pre-existing tests in `tests/test_scheduler_practice_announcements.py` (17) and `tests/agent/test_weekly_summary.py` (11) that stub out `Practice` entirely with a `SimpleNamespace` (fake columns + a fake `Query`) rather than hitting the real DB. `published_practices()` does its own independent `from app.practices.models import Practice` inside the function body (as specified by the brief), which is a *separate name resolution* from whatever the calling module has bound `Practice` to. Two distinct failure modes fell out of that:

1. **`tests/test_scheduler_practice_announcements.py`** patches `app.practices.models.Practice` itself (the true source module), which is exactly what `published_practices()`'s lazy import resolves against — so the patch *did* apply, but the fake `SimpleNamespace` model had no `is_draft` attribute. `Practice.is_draft.is_(False)` raised `AttributeError`, which was silently swallowed by `run_practice_announcements_job`'s outer `try/except Exception` (it only logs), producing 0 announcements instead of a visible crash. Fix: added `is_draft=_Column()` to both fake-model constructions in that file.

2. **`tests/agent/test_weekly_summary.py`** instead patches `routine.Practice` (the name bound inside `app.agent.routines.weekly_summary`, via `patch.object(routine, "Practice", ...)`), never touching `app.practices.models.Practice`. Since `published_practices()` bypasses that routine-local name and re-imports fresh from the source module, it silently fell through to the real, unpatched `Practice.query` — a genuine SQLAlchemy query against the actual (empty) local Postgres DB — rather than the test's `FakeQuery`. Fix: added `is_draft=Practice.is_draft` to `model_for()`, and added a second patch, `patch("app.practices.models.Practice", fake_practice_model)`, alongside the existing `patch.object(routine, "Practice", ...)`, so both the routine's own `Practice.date`/`.status` references and `published_practices()`'s independent import see the same fake object.

Neither of these is a correctness bug in production code — in production both names always resolve to the same real class — but it's a real coupling cost of the lazy-import design worth flagging: any future test that stubs `Practice` by patching a module-local import binding (rather than the source module) will silently bypass `published_practices()`'s internal filter. No production code changes were made to route around this; only the two test files' mocks were widened to also cover `is_draft` and the source-module patch target, per the task's instruction to treat the existing test suite as the regression safety net.

## Cleanup / safety verification

- `test_draft_exclusion.py`'s two DB-writing tests delete every row they create in a `finally` block.
- Verified directly against the local Postgres test DB (`postgresql://tcsc:tcsc@localhost:5432/tcsc_trips`) after the full suite run: `Practice.query.count()` returns `0` — no orphan rows left behind.
- No `db.create_all()` / `db.drop_all()` calls were added anywhere.

## Files touched

- `app/practices/service.py` — added `published_practices()`
- `app/scheduler.py` — 3 call sites
- `app/slack/practices/refresh.py` — 2 call sites
- `app/agent/routines/morning_check.py` — 1 call site
- `app/agent/routines/lead_verification.py` — 1 call site
- `app/agent/routines/weekly_summary.py` — 1 call site
- `app/agent/routines/pre_practice.py` — 2 call sites
- `tests/practices/test_draft_exclusion.py` — new, 3 tests
- `tests/test_scheduler_practice_announcements.py` — added `is_draft` to 2 fake models
- `tests/agent/test_weekly_summary.py` — added `is_draft` to `model_for`, added source-module patch in `run_with_query`

## Fix round 1

Review found the draft-exclusion conversion incomplete (3 member-facing call sites still bare) plus a fragile test and an undocumented import. Fixed all four findings.

### Fix 1 — three remaining leaks converted to `published_practices()`

- `app/slack/commands.py:74` (`_handle_practice_command`, backing `/tcsc practice`) — `Practice.query.filter(...)` → `published_practices().filter(...)`. Added `from app.practices.service import published_practices` at module level (alongside the existing `app.practices.models`/`app.practices.interfaces` imports). All three original filter args (`Practice.date >= today_start`, `Practice.date < week_end`, `Practice.status != 'cancelled'`) and the `.order_by(Practice.date)` were left untouched. Note: this file also has a legitimate `Practice.query.get(practice_id)` in `_handle_rsvp_command` (line ~157, RSVP-by-id) — correctly left alone, it's a by-id lookup, not a listing.
- `app/slack/practices/app_home.py:33` (`publish_app_home`) — same swap. Added the `published_practices` import function-locally (matching the file's existing style of function-local imports inside `publish_app_home`, e.g. `from app.utils import now_central_naive`), immediately above the query. Both original filter args (`Practice.date >= now`, `Practice.date <= end_date`) and the `order_by` preserved exactly.
- `app/slack/practices/coach_review.py:451` (`post_coach_weekly_summary`) — same swap. Added `from app.practices.service import published_practices` at module level, next to the existing `from app.practices.models import Practice`. Both original filter args (`Practice.date >= week_start`, `Practice.date < week_end`) and the `order_by` preserved exactly. This closes the specific contradiction called out in the brief: `refresh.py`'s `_refresh_coach_summary_for_week` already excluded drafts, so the Sunday summary and the first-edit refresh now agree.

### Fix 2 — guard test watchlist extended, with a narrowed grep

Added all three files to `watched` in `test_no_member_facing_query_uses_bare_practice_query`.

Caveat handling: I inspected all three files first (`grep -n "Practice.query"` against each). `app_home.py` and `coach_review.py` each have exactly one bare `Practice.query` usage — the listing query just converted — and no by-id lookups, so they could be watched as-is. `commands.py` has both the listing query (now converted) *and* a legitimate `Practice.query.get(practice_id)` by-id lookup in `_handle_rsvp_command`, which must not be flagged (fetching one specific practice to attach an RSVP is not a member-visible listing).

Rather than leaving `commands.py` off the watchlist, I narrowed the grep itself: it now matches the substring `"Practice.query.filter"` instead of bare `"Practice.query"`. This catches `.filter(` and `.filter_by(` (both used elsewhere for listings) but not `.get(`/`.get_or_404(` by-id lookups. I checked this doesn't weaken protection for the other six already-watched files: none of them contain any `Practice.query.get`/`.get_or_404`/`.all()`/`.order_by()`-without-`.filter` pattern that the narrower regex would miss (verified via `grep -n "Practice.query"` across all six — zero matches post-conversion, so there's nothing bare left to narrow past). A full repo grep (`grep -rn "Practice\.query" app/`) confirms the only `.filter`/`.filter_by` style listing queries left anywhere are in `app/practices/service.py` itself (the helper's own internal query, expected) and two files intentionally not on the watchlist (`app/slack/practices/announcements.py:1249`, `app/slack/practices/delete_recovery.py:63` — internal/recovery logic, not a fresh finding in scope here). Everything else bare is a `.get(`/`.get_or_404(` by-id lookup (admin detail pages, bolt_app.py button handlers acting on one practice_id from a payload).

Added a docstring to the guard test itself explaining the by-id exclusion, so a future reader doesn't have to re-derive why `commands.py` is watched despite containing a bare `Practice.query.get(`.

### Fix 3 — de-fragilized `test_published_practices_is_chainable`

Replaced `assert [p.id for p in found] == [live.id]` with membership assertions matching the sibling test's style:
```python
ids = [p.id for p in published_practices().filter(Practice.date >= soon).all()]
assert live.id in ids
assert draft.id not in ids, "a draft practice leaked through a chained filter"
```
Still genuinely load-bearing: reverting `published_practices()` to plain `Practice.query` (no `is_draft` filter) makes `draft.id in ids` true, so the second assertion fails. Verified this directly (see below) by reverting a converted call site to prove the *guard* test fails on regression; for this specific test I additionally hand-traced that the only way `draft.id not in ids` could pass is if the draft filter is actually applied, since both rows share the same date window and would otherwise both come back.

### Fix 4 — documented the function-local re-import in `app/practices/service.py`

Added a comment directly above the function-local `from app.practices.models import Practice` in `published_practices()` explaining that it's not redundant with the module-level import: it re-reads the current `app.practices.models.Practice` attribute at call time, which is what lets tests that do `patch("app.practices.models.Practice", ...)` (rather than patching a caller-local name) actually affect the helper.

### Unplanned fallout: `tests/slack/test_coach_summary_posting.py`

Converting `coach_review.py` reproduced the same coupling cost documented in the original task-2 report for `weekly_summary.py`. `tests/slack/test_coach_summary_posting.py::run_coach_summary` patches `coach_review.Practice` (the name bound locally in `coach_review`'s module namespace) with a `SimpleNamespace(query=FakeQuery(...), date=Practice.date)`. `published_practices()` bypasses that local binding entirely via its own independent import of `app.practices.models.Practice`, so all 7 tests in that file failed with `RuntimeError: Working outside of application context` (the real, unpatched `Practice.query` tried to hit a real Flask-SQLAlchemy session with no app context active in this unit-test module).

Fix, mirroring the prior round's pattern: added `is_draft=Practice.is_draft` to the `practice_model` `SimpleNamespace`, and added `patch("app.practices.models.Practice", practice_model)` alongside the existing `patch.object(coach_review, "Practice", practice_model)` in the `with` block, with a comment explaining why both patch targets are needed. No production code changes were required — only the test's mock surface needed widening, per the same reasoning as the original report's fallout section.

### Test commands and output

Guard-test regression check (temporarily reverted `coach_review.py`'s converted call site back to bare `Practice.query.filter(...)`, ran the guard test alone, confirmed it fails, then restored the fix):
```
$ .venv/bin/python -m pytest tests/practices/test_draft_exclusion.py::test_no_member_facing_query_uses_bare_practice_query -q
FAILED ... AssertionError: ... ['app/slack/practices/coach_review.py:452']
1 failed in 0.81s
```
After restoring:
```
$ .venv/bin/python -m pytest tests/practices/test_draft_exclusion.py -q
3 passed in 0.95s
```

Fallout discovered and fixed:
```
$ .venv/bin/python -m pytest tests/slack/test_coach_summary_posting.py -q
# before fix: 7 failed (RuntimeError: Working outside of application context)
# after fix:
.......                                                                  [100%]
7 passed in 0.79s
```

Full suite:
```
$ .venv/bin/python -m pytest tests/ -q --ignore=tests/wix_scrape
1275 passed, 3010 warnings in 55.21s
```
Matches the 1275 baseline exactly (no new tests added this round — Fix 2/3 modified existing tests rather than adding new ones; Fix 1's fallout fix only widened an existing test's mocks). No regressions.

### Cleanup / safety verification (this round)

- No new DB-writing tests were added this round; the two existing DB-writing tests in `test_draft_exclusion.py` still clean up in `finally` blocks (unchanged).
- Verified post-suite: `Practice.query.count()` against the local Postgres test DB returns `0`.
- No `db.create_all()` / `db.drop_all()` calls added.
- No production/runtime behavior changed beyond routing the three call sites through the existing `published_practices()` helper (same filter semantics, drafts now excluded).

### Files touched (this round)

- `app/practices/service.py` — comment only
- `app/slack/commands.py` — 1 call site + import
- `app/slack/practices/app_home.py` — 1 call site + import
- `app/slack/practices/coach_review.py` — 1 call site + import
- `tests/practices/test_draft_exclusion.py` — watchlist + narrowed grep + docstring; de-fragilized chainable test
- `tests/slack/test_coach_summary_posting.py` — widened `practice_model` mock + added source-module patch (fallout fix)
