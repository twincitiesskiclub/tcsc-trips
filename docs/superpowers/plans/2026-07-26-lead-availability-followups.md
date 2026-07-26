# Lead availability — post-review follow-ups (P4)

Executes the "fix soon after" list from
`docs/superpowers/notes/2026-07-26-lead-availability-handoff.md`. These are the
findings the whole-branch review triaged as non-blocking, with the shadow month
as the buffer. All five are independent.

## Context

Branch `lead-availability`. The feature replaces availability-by-Google-Sheet
for practice leads: a monthly job drafts the next 4 weeks of practices
(`is_draft=True`, invisible to members), a readiness digest chases the missing
details, a director opens a Slack poll where leads react with letter emoji to
the sessions they can lead, non-responders get DM nudges, and the practice admin
form's lead picker shows availability + load so assignment is an informed human
call. Blocks become member-visible via
`POST /admin/availability/polls/<id>/publish`.

## Global Constraints

These bind every task. Violating any of them is a defect regardless of what an
individual task says.

1. **The test database IS the real local development database**
   (`postgresql://tcsc:tcsc@localhost:5432/tcsc_trips`). `db.create_all()` and
   `db.drop_all()` are FORBIDDEN. Read `tests/practices/conftest.py` before
   writing any test and follow its conventions exactly: `try/finally` cleanup
   with `db.session.rollback()` FIRST, year-2099-or-later dates, `"TEST "`
   string prefixes, ids captured as plain ints before the `try`, and assertion
   queries scoped to the rows the test itself created (never an unscoped
   `Model.query.count()`).
2. **Delete practices through the ORM** (`db.session.delete(obj)`), never
   `Practice.query.filter_by(...).delete()` — a bulk delete skips the
   `practice_types_junction` rows and dies on a foreign-key violation, leaving
   debris in the dev database.
3. **Run tests with `.venv/bin/python`**, never `env/` (a stale macOS
   virtualenv that does not work):
   `.venv/bin/python -m pytest tests/ -q --ignore=tests/wix_scrape`.
   `tests/wix_scrape` has pre-existing unrelated collection errors.
4. **Status fields are plain strings, not Python Enums.** `UserStatus` and
   `UserSeasonStatus` in `app/constants.py` are simple classes — never call
   `.value` on them. Only `MemberType` is a true Enum. `PracticeStatus` in
   `app/practices/interfaces.py` IS an Enum, so `PracticeStatus.CANCELLED.value`
   is correct for comparing against `Practice.status`.
5. **Timestamps are UTC in the database, displayed US Central.** Use
   `now_central_naive()` / `today_central()` from `app/utils.py`, never
   `datetime.now()` or `datetime.utcnow()` in new code. `poll.opened_at` is
   written with `now_central_naive()`; mixing clocks shifts nudge boundaries by
   5-6 hours.
6. **All Slack post updates for a practice go through
   `refresh_practice_posts()`** (`app/slack/practices/refresh.py`). Do not
   update announcement/collab/summary posts individually.
7. **Slack-facing code must never raise.** Every function that talks to Slack in
   this feature catches `SlackApiError`, `TimeoutError` AND bare `Exception`,
   logs, and returns a result dict — a Slack outage must not fail the caller.
   `get_slack_client()` raises `ValueError` when `SLACK_BOT_TOKEN` is unset,
   which is not a `SlackApiError`.
8. **Fail safe, not open.** Shadow mode defaults ON; `shadow_roster` fails
   closed (empty means nobody is nudged, never fall back to the live pool);
   letter emoji are validated against `emoji.list` before any poll opens.
   Preserve these defaults.
9. **Do not reword director-approved Slack copy** in
   `app/slack/blocks/availability.py`. It was previewed in a real channel and
   signed off. New copy you add is yours to write; existing strings are not.
10. **No new dependencies.** No new pip packages, no new npm packages.
11. Run the full Python suite before reporting DONE and include the counts.
    Baseline is **1439 passing**. JS tests: `npm run test:practice-reactions`,
    baseline **62 passing**.

---

## Task 1 — An open poll's Slack message goes stale when a practice is edited

**Problem.** A director opens an availability poll listing 12 sessions with
their date, location and activity type. Someone then edits one of those
practices — moves it to a different location, changes the type. The poll message
in Slack keeps showing the old details forever. Leads are reacting to
`:letter_g:` based on information that is no longer true.

Responses already get stale-flagged: `LeadAvailabilityResponse` stores a
date/location snapshot and the lead picker marks a response stale when the
practice has moved underneath it (that mechanism works, leave it alone). What is
missing is updating the *post*.

**What to build.** Register the availability poll as a new surface in the
practice-refresh dispatcher, so editing a practice updates any OPEN poll that
covers it.

- `app/slack/practices/refresh.py` has a `PracticeSurface` registry
  (`PRACTICE_SURFACES`) and its docstring already anticipates this: "Adding a
  new surface (e.g. a future lead-scheduling DM) is one registry entry — no
  changes to `refresh_practice_posts()` or any call site." Follow that.
- The surface's refresh function must find every poll with
  `status == PollStatus.OPEN` that has a `LeadAvailabilityPollPractice` row for
  this practice, rebuild its blocks with the existing
  `poll_rows(poll)` + `build_poll_blocks(rows, start_label, end_label)` from
  `app/practices/availability.py` and `app/slack/blocks/availability.py`, and
  `chat_update` the message at `poll.channel_id` / `poll.message_ts`.
  Reuse those existing builders — do not write a second block builder.
- Derive `start_label` / `end_label` exactly as `open_poll()` does:
  `poll.starts_on.strftime("%B %-d")` and `poll.ends_on.strftime("%b %-d")`.
- `ts_field` on the registry entry: a poll's ts lives on the poll row, not on
  the practice, so the practice-level `is_present` check does not apply — pass
  `None` for `ts_field` (the same thing `coach_summary` and `weekly_summary`
  do) and handle "no poll covers this practice" by returning
  `{"skipped": "absent"}` from the refresh function itself.
- Applies to which change types: `edit`, `cancel` and `delete` at minimum. A
  cancelled or deleted practice must not keep soliciting availability. For
  `delete`, the practice row is gone or going — read what you need before it
  disappears, and do not crash if the mapping row cascaded away.
- Never raise (Global Constraint 7). A poll refresh failure returns
  `{"success": False, "error": ...}` and must not stop the other surfaces or
  fail the edit.

**Tests.** `tests/slack/` (Slack surfaces) and/or
`tests/practices/`. Required cases:

- Editing a practice covered by an OPEN poll calls `chat_update` on that poll's
  channel + `message_ts`, and the new blocks contain the practice's NEW location.
- A poll in `DRAFT` status is not updated (it has no `message_ts` yet).
- A poll in `CLOSED` status is not updated (availability collection is over;
  rewriting history would be misleading).
- A practice covered by no poll returns skipped, and does not raise.
- A Slack failure returns `success: False` and does not prevent the other
  surfaces in `refresh_practice_posts()` from running.

---

## Task 2 — The readiness nudge re-posts an identical digest every morning

**Problem.** `run_practice_readiness_nudge_job` (`app/scheduler.py`, daily
09:00 Central) re-posts the whole readiness digest as a NEW channel message
every single morning while any drafted practice still lacks location, type or
time. Directors are live from day one, so this lands immediately and trains
people to ignore the channel.

**Decision from the practices director (Rob):** don't dedupe or escalate — keep
the daily cadence, but **post the nudge as a reply in the thread of the original
digest post** instead of as a new channel message. Threaded replies don't spam
the channel.

**What to build.**

1. **Persist the digest's Slack identity** so the nudge can thread onto it.
   Reuse `PracticeSummaryPost` (`app/practices/models.py`) — it exists for
   exactly this ("Canonical Slack identity for one weekly practice-summary
   surface") and already has `channel_id` / `message_ts` plus the
   `find_summary_post` / `stage_summary_post` helpers in
   `app/slack/practices/summary_posts.py`.
   - Add a new surface constant `READINESS_DIGEST = "readiness_digest"`
     alongside the existing `COACH_SUMMARY` / `WEEKLY_SUMMARY`.
   - The table has a CHECK constraint
     `surface IN ('coach_summary', 'weekly_summary')` — it needs a migration to
     extend. The branch's chain currently ends at `3d34ea39db0f`; add exactly
     one migration on top of it, and make `downgrade()` real (restore the
     two-value constraint), not a `pass`.
   - The unique key is `(week_start, surface)`. A readiness digest belongs to a
     draft *block*, not a week — use the block's start date as the anchor and
     say so in a comment, so the next reader isn't confused by the column name.
2. **`post_readiness_digest`** (`app/slack/practices/drafts.py`) records the
   digest's channel + ts when it posts the initial digest.
3. **The daily nudge** posts into that thread (`chat_postMessage` with
   `thread_ts=<digest ts>`) rather than a new top-level message. If no digest
   post is on record for the current block (nothing to thread onto — e.g. the
   bootstrap job's post failed, or this is a block created before this change
   shipped), fall back to posting a normal top-level digest and record it, so
   the chase never silently stops.
4. Keep the existing "stay quiet when everything is ready" behaviour exactly as
   it is — a daily "all good" post is the thing the current code correctly
   avoids.

**Tests.** Extend `tests/test_scheduler_draft_jobs.py` and/or
`tests/slack/test_practice_draft_posting.py`. Required cases:

- The daily nudge posts with `thread_ts` set to the recorded digest ts, in the
  recorded channel.
- With no digest on record, the nudge posts top-level AND records its identity,
  so the next day threads onto it.
- Everything ready → still silent, nothing posted (this is existing behaviour;
  prove it did not regress).
- A Slack failure is logged and does not raise out of the scheduler job.
- The migration applies and reverses cleanly: after `downgrade()`, inserting
  `surface='readiness_digest'` is rejected again.

---

## Task 3 — A failed commit leaves a posted-but-DRAFT poll

**Problem.** In `open_poll()` (`app/practices/availability.py`) the Slack post
happens inside a `try/except` that returns a clean error dict, but the four
lines that follow it are outside any guard:

```python
poll.message_ts = response["ts"]
poll.status = PollStatus.OPEN
poll.opened_at = now_central_naive()
db.session.commit()
```

If that `commit()` raises (connection drop, constraint error), the poll message
is already live in Slack and leads can react to it, but the database still says
`status == DRAFT` with `message_ts == None`. Consequences: reaction lookups
match on `message_ts` so every reaction is orphaned and invisible; the nudge job
skips the poll because it isn't OPEN; and a later `open_poll()` call would
happily post a SECOND message (the re-entrancy guard checks `status != DRAFT`,
which is exactly the state a failed commit leaves behind).

**What to build.** Guard the commit. On failure:

- Roll back the session so it isn't left poisoned for the caller.
- Log at **error** level, including `poll.id` and the Slack `ts` of the message
  that IS live — a human needs those two values to recover, and the ts exists
  nowhere else once the exception is swallowed.
- Return `{"success": False, ...}` with an error that says the message posted
  but the poll could not be marked open, and names the ts. Do not claim success.
- Do not attempt to delete the Slack message as "cleanup" — that trades a
  recoverable inconsistency for a destroyed audit trail, and the delete can fail
  too.

Do not change the existing re-entrancy guard, the emoji validation, or the
reaction-seeding loop. Note the reaction seeding runs after the commit and is
already correctly best-effort; if the commit failed there is nothing to seed
onto, so return before it.

**Tests.** Extend the existing `open_poll` coverage in
`tests/practices/test_availability_service.py`. Required cases:

- A commit failure returns `success: False` and the error names the live ts.
- A commit failure leaves the session usable (a subsequent query works rather
  than raising `PendingRollbackError`).
- The happy path is unchanged: still commits, still OPEN, still seeds reactions.

---

## Task 4 — The first nudge lands on day 4, not day 3

**Problem.** `participants_to_nudge()` (`app/practices/availability.py`) gates
the first nudge on:

```python
if now - poll.opened_at < timedelta(days=FIRST_NUDGE_AFTER_DAYS):
    return []
```

with `FIRST_NUDGE_AFTER_DAYS = 3`. That is a 72-hour rule, but the nudge job
runs at a fixed 08:00 Central. A poll opened at 10:00 on Monday is only 70 hours
old at Thursday 08:00, so Thursday is skipped and the first nudge actually
arrives Friday — day 4. The intent (documented in the docstring as "First nudge
at day 3") is calendar days.

**What to build.** Make the boundary calendar-day based, so a poll opened any
time on day 0 gets its first nudge on the day-3 run regardless of the hour.
Compare dates, not a timedelta of hours.

Keep `MIN_DAYS_BETWEEN_NUDGES = 2` and `MAX_NUDGES = 3` semantics intact —
consider whether the same hours-vs-days problem affects the
`last_nudged_at` spacing check and fix it consistently if so. An off-by-one here
DMs everyone every morning, which is the fastest way to get the bot muted by the
people it depends on, so the tests must pin the boundary precisely.

Update the docstring so it describes what the code now does.

**Tests.** `tests/practices/test_availability_nudge.py` already covers this
area. Required cases (drive `now` explicitly, never the real clock):

- Poll opened 10:00 on day 0 → the day-3 08:00 run DOES nudge. This is the bug;
  assert it directly.
- The day-2 08:00 run does NOT nudge.
- Poll opened 23:59 on day 0 → the day-3 08:00 run still nudges.
- A participant nudged on day 3 is not nudged again on the day-4 run, and IS
  eligible on the day-5 run (`MIN_DAYS_BETWEEN_NUDGES = 2` preserved).
- `MAX_NUDGES = 3` still caps.

---

## Task 5 — Stuck "Loading…" in the lead picker, and the create/edit picker split

**Problem A.** `loadLeadPicker()` in
`app/templates/admin/practices/_detail_context.js`:

```javascript
const payload = await loadLeadCandidates(practiceId);
if (!payload) return; // loadLeadCandidates already showed a toast
```

The container starts as `<p class="pe-empty">Loading…</p>` (see
`app/templates/admin/practices/detail.html`, the `#lead-picker` div). On a fetch
failure this returns early, leaving "Loading…" on screen permanently — the
picker looks like it is still working. Every sibling loader in the same file
(`loadEvaluation`, `loadRSVPs`, `loadLeadConfirmations`) renders an in-place
error instead: `c.innerHTML = '<p class="rail-error">…</p>'`. Match the
siblings. The toast from `loadLeadCandidates` stays as-is.

**Problem B.** Two lead-picker code paths coexist and it isn't documented.
`detail.html` branches on `{% if practice %}`: edit mode gets the new ranked
availability picker (`#lead-picker`), create mode gets "Save the practice to see
lead availability." plus the older `#leads-summary` person-pill picker, because
`/admin/practices/<id>/lead-candidates` needs a practice id that does not exist
yet.

**Decision from the practices director (Rob): leave the split as-is.** Practices
are auto-drafted now, so edit mode is the real Sunday path and create is the
rare exception. Do NOT create a draft row on "New" (an abandoned form would
leave an orphan draft, and an orphan draft is invisible to members). Do NOT
rework the candidates endpoint to accept a date.

So Problem B is a **documentation-only** change: add a comment at the
`{% if practice %}` branch in `detail.html` recording that the split is
deliberate, why create mode has no ranked picker (no practice id → no candidates
endpoint), and that this was a product decision rather than an oversight. Keep
it to a few lines. Do not change the rendered markup or any behaviour.

**Tests.** `tests/js/lead_picker.test.js` already exercises this file's picker
helpers with jsdom; `npm run test:practice-reactions` runs the JS suite. Add a
case proving a failed candidate load replaces the "Loading…" text with a visible
error rather than leaving the loading state on screen. If `loadLeadPicker` is not
currently reachable from the test harness, exporting it the way the existing
tests export their helpers is acceptable; do not restructure the file beyond
what that needs.

---

## Task 6 — Deleting a practice that a poll covers raises IntegrityError

**Problem.** Found during Task 1's review and confirmed empirically against the
dev database. This branch added two tables with a foreign key to `practices.id`
and neither has `ON DELETE` behaviour or an ORM cascade from `Practice`:

- `lead_availability_poll_practices.practice_id`
  (`app/practices/availability_models.py:62`)
- `lead_availability_responses.practice_id` (same file, line 98)

So `db.session.delete(practice)` — which the admin delete route does at
`app/routes/admin_practices.py:716` — fails for any practice a poll covers:

```
psycopg2.errors.ForeignKeyViolation: update or delete on table "practices"
violates foreign key constraint
"lead_availability_poll_practices_practice_id_fkey"
```

The route wraps the delete in a broad `except Exception`, so a director deleting
a polled practice gets a failure with the Slack announcement already torn down
(`refresh_practice_posts(..., 'delete')` runs first, at line 689). This is
introduced by this branch, not pre-existing — the tables are new here.

**What to build.** Make deleting a practice remove its poll mapping and
availability response rows.

- Decide between a DB-level `ON DELETE CASCADE` (needs a migration to alter both
  constraints) and an ORM-level relationship cascade from `Practice`. Either is
  acceptable; pick one, and say in a comment why. Note that a poll's own
  `practices` / `responses` relationships already use
  `cascade="all, delete-orphan"` from the *poll* side — the missing direction is
  from the *practice* side.
- Deleting a practice must NOT delete the poll itself, or any other practice's
  rows. A poll that loses one session keeps collecting availability for the
  rest; Task 1 already made the poll's Slack message re-render without the
  removed session, and emoji letters stay pinned to the remaining sessions.
- If you add a migration, add exactly one on top of the branch's current head,
  and make `downgrade()` real (restore the constraints as they were), not a
  `pass`.

**Also fix in this task** (Minor findings from Task 1's review, same files):

1. `tests/slack/test_availability_poll_refresh.py:281-308` — `_cleanup` reads
   `.id` / `.location_id` / `.practice_types` off ORM objects *after*
   `db.session.rollback()`. The binding convention is to capture ids as plain
   ints *before* the `try`. It is safe today only by accident; make it follow
   the convention, as `old_location_id` in the same file already does.
2. `app/slack/practices/refresh.py` — when several polls cover a practice and
   one fails, the returned dict is `{"success": False, "error": ...}` and the
   ids of the polls that DID update are dropped. Include them (e.g.
   `"polls": updated`) in the failure dict too, so the logs show what went
   through.
3. `app/slack/practices/refresh.py` — the availability-poll surface returns
   `{"skipped": "absent"}` when no poll covers the practice, which is the
   common case for any ordinary practice edit. `_log_refresh_results()` logs
   every `"absent"` at WARNING, so normal edits now emit a spurious warning.
   Use a distinct skip value that reads as "nothing to do here" rather than
   "a post is missing", and leave `_log_refresh_results`'s treatment of genuine
   `"absent"` gaps for the other surfaces unchanged.

**Tests.** Required cases:

- Deleting a practice covered by an OPEN poll succeeds, and removes that
  practice's mapping row and its availability response rows.
- The poll itself survives, and the other sessions' mapping rows survive.
- The full delete route path works end to end for a polled practice (it is the
  route, not the model, that users hit).
- If you added a migration: it applies and reverses cleanly.

---

## Task 7 — Whole-branch review fixes (backend)

The final whole-branch review found a second silent-gap bug of the same shape as
the publish bug, plus a fail-open in the shadow-mode guard. I confirmed both
empirically against the dev database before writing this. Fix all of the
following; they are grouped here because they cluster in the drafting/config
code and share tests.

### 7a (CRITICAL) — the monthly draft window is shorter than the month, so the tail of most months is never drafted

`expected_slots` (`app/practices/drafting.py:26`) normalises week 0 back to the
Monday *before* `start_date`, then discards slots earlier than `start_date`. With
`weeks=4` the window therefore covers only `28 - start_date.weekday()` days
forward — but `run_practice_block_bootstrap_job` fires monthly, on the 1st.

Measured over 8 consecutive monthly runs with a Tue/Thu/Sat config, **15 of 91
slots are never drafted**:

```
2026-08-01 (Sat): drafts 08-01 .. 08-22   → missed 08-25, 08-27, 08-29
2026-09-01 (Tue): drafts 09-01 .. 09-26   → missed 09-29
2026-10-01 (Thu): drafts 10-01 .. 10-24   → missed 10-27, 10-29, 10-31
2026-11-01 (Sun): drafts 11-03 .. 11-21   → missed 11-24, 11-26, 11-28
2026-12-01 (Tue): drafts 12-01 .. 12-26   → missed 12-29, 12-31
```

Only a Monday-the-1st month is clean. Failure scenario: on 2026-08-01 the job
drafts Aug 1–22 and the digest honestly reports that range. The director polls
it, collects availability, assigns leads, publishes. Aug 25/27/29 **do not exist
as rows at all** — `build_poll` can't mention them because it only validates
practices that exist, and the Sept 1 run starts at Sept 1 and never looks back.
Those practices first surface as empty "Add Practice" placeholders in the coach
post of the week they happen, with zero availability collected — which is the
entire thing this feature exists to guarantee.

**Fix.** Stop expressing the window as a week count anchored to a shifted Monday.
Prefer an explicit horizon — draft through the end of *next* month — so
consecutive runs overlap harmlessly (`generate_draft_block` is already
idempotent, and its own test asserts that). Anchoring to the day after the last
existing drafted/scheduled slot with a generous `weeks` is also acceptable.
Whichever you choose, keep `expected_slots`'s existing contract that no slot
earlier than `start_date` is returned, and keep the digest's reported date range
honest about what was actually drafted.

**Required test:** run the bootstrap logic for twelve consecutive months and
assert that **no** configured slot in the spanned period is skipped. That
property is the one nothing on this branch asserts today — every existing case
in `tests/practices/test_drafting.py` starts from a Monday or tests only the
single-week exclusion.

Also fold in: the "blocks start on the 1st" rule is duplicated as
`start.replace(day=1)` at `app/scheduler.py:90` and `:134`, coupled only by
matching comments. Extract one `_block_anchor(today)` helper — you are touching
both functions anyway, and the readiness digest threads onto the anchor, so a
divergence between them silently breaks threading.

### 7b (CRITICAL) — `_shadow_mode()` fails OPEN on a null config row

`app/routes/admin_availability.py:31`. `AppConfig.get(key, default)` returns
`config.value` whenever the *row* exists, so a row storing JSON `null` yields
`bool(None) is False` → shadow OFF. Confirmed against the dev database:

```
no row      -> shadow_mode = True   channel = C0B3Y71PG92   (shadow, correct)
row = null  -> shadow_mode = False  channel = C02J4DGCFL2   (the LIVE 64-member channel)
```

The default-`True` guarantee only holds for a *missing* row, and
`AppConfig.set(key, None)` is one line away. Shadow mode exists specifically so a
misconfiguration cannot reach the live channel, so this must fail closed: treat a
`None` value exactly like a missing row. Apply the same reasoning to the
`lead_availability.shadow_roster` read in
`app/practices/availability.py:shadow_roster_leads` (it already handles falsy
correctly — verify, and add the `None`-row case to its test if missing).

Add a test for each: a JSON-`null` row resolves to shadow ON / an empty roster.

### 7c (IMPORTANT) — drafting's `practice_days` default omits Saturday

`DEFAULT_PRACTICE_DAYS` in `app/practices/drafting.py:20` is Tue+Thu.
`app/slack/practices/coach_review.py:446`, `app/slack/practices/refresh.py:348`
and `app/routes/admin_practices.py:1583` all default to Tue+Thu+**Saturday**. I
queried the dev database: there is **no `practice_days` row at all**. If
production matches, Saturday practices are never drafted while the coach post
renders a permanent empty Saturday "Add Practice" slot — the duplicate-on-top-of-
a-draft failure that `coach_visible_practices()` was added to prevent.

**Fix.** One shared default constant, imported by all four sites rather than
copied. Put it wherever it reads most naturally for this codebase and say why in
a comment.

### 7d (IMPORTANT) — a practice created inside an OPEN poll's range is invisible to that poll

`build_poll` (`app/practices/availability.py:137`) snapshots the practice set at
creation and persists the emoji mapping; `_refresh_availability_poll` only
touches polls already joined to that practice id. So `create_practice` for a date
inside an open poll's range gets no letter, no availability, and **no log line**.
Normally rare — except 7a guarantees it, because the missed tail-week practices
have to be created by hand.

**Fix.** On practice create, if an OPEN poll covers the new date, log at error
level naming the poll id and the practice, and surface it in the create route's
response so the admin UI can show it. Do NOT silently append a mapping row:
appending changes letters under reactions leads have already given, and the
emoji-position guarantee is load-bearing (see
`lead_availability_poll_practices.position`). A loud, actionable warning is the
correct behaviour here.

### 7e (before merge) — a deleted digest post stops the readiness chase silently

If the readiness digest message is deleted in Slack, the stored
`PracticeSummaryPost` record is never cleared, so every later nudge threads onto
a dead ts, fails, and only logs — the chase stops for the rest of the block,
which is the exact failure the top-level fallback was built to prevent. A coach
tidying the collab channel during a shadow month makes this likely, not
hypothetical.

**Fix.** In `app/slack/practices/drafts.py`, on a Slack error indicating the
thread parent is gone (`message_not_found` / `thread_not_found`), delete the
record and retry top-level. The record is only a cache of where to thread.

### 7f (before merge) — availability models still default to `datetime.utcnow`

`app/practices/availability_models.py` — `responded_at` (and any sibling
`created_at` on the availability models) default to `datetime.utcnow` while
`opened_at` uses `now_central_naive()`. Cosmetic to the day-3 rule, which
compares against `opened_at`, but `responded_at` is the timestamp a human reads
when debugging staleness during the shadow month, and a 5-6 hour skew against
`opened_at` in the same query result will cost someone an hour. Switch the new
availability models' defaults to `now_central_naive()`. Do not change models
outside this feature.

### 7g (minor, cheap) — `done_emoji` config key is never read

`config/practices.yaml:59` defines `lead_availability.done_emoji:
white_check_mark`, but `DONE_EMOJI` is hardcoded at
`app/practices/availability_emoji.py:26` and nothing reads the key. Editing the
config silently does nothing — and that module's whole argument is that the emoji
set lives in config precisely because a rename once broke a live poll. Read the
key (keeping the current value as the fallback), or delete it. While you are in
that file, it keeps its own module-level cache of `practices.yaml` instead of
reusing `_config.py::_load_practice_config`; consolidating fixes a drift trap if
`reload_config` is ever wired on one side only. Do both if consolidating is
straightforward; if it is not, do the `done_emoji` fix and report the rest as a
concern.

**Tests for 7c–7g:** cover each behaviour change. For 7g, prove a config value
actually reaches `DONE_EMOJI`'s consumer.

---

## Task 8 — Wire up the block-level publish control

**Problem.** `publish_poll_block` (`app/routes/admin_availability.py:76`) is the
documented human publish gate — the practices director's explicit decision is
that publishing happens per availability block, once, from the poll that
collected the leads. It has **zero callers**: nothing in `app/static/` or
`app/templates/` posts to it, and `GET /admin/availability/` is `jsonify`-only
with no template, so the `unpublished` / `publishable` counts it returns are
never rendered.

Meanwhile `app/slack/blocks/coach_review.py:297` tells coaches, in Slack, to
"publish the availability block it belongs to". A director who follows that
instruction finds nothing to click, and either leaves a whole block unpublished
(members see an empty week, and announcements never fire because
`slack_message_ts` stays NULL on a draft) or grinds through the practices-list
drawer one practice at a time.

**What to build.** A publish control for each recent poll, on the practices list
page (`app/templates/admin/practices/list.html` +
`app/static/admin_practices.js`). That page already has an "Availability poll"
toolbar row with date inputs and an "Open Availability Poll" button, and it
already knows how to call these endpoints — follow that established pattern
rather than building a new page.

Requirements:

- Fetch the polls from the existing `GET /admin/availability/` and show, per
  poll: its date range, status, session count, and its `unpublished` /
  `publishable` counts. Do not add a new endpoint; the data is already returned.
- A Publish button per poll that POSTs to
  `/admin/availability/polls/<id>/publish`. Show it only when that poll has
  something publishable, and follow the confirmation + toast + reload pattern the
  existing `openAvailabilityPoll()` uses in the same file.
- Report the result honestly: how many published, and for anything skipped, name
  the practice and what it still needs (the route returns `published`, `skipped`
  with `missing`, and `already_published`).
- A poll with `unpublished > 0` and `publishable == 0` must read as "these need
  details filled in", not as "nothing to do" — that distinction is the whole
  reason the route returns both counts.
- Do not add a week-level or list-level bulk publish. The Sunday evening flow
  already sends the coming week to members with no human in the loop; an earlier
  iteration of this branch added such a control and it was removed as a
  regression. `tests/js/draft_publish.test.js` asserts it stays gone — keep that
  test passing.
- Keep the existing per-practice drawer publish (the escape hatch for a draft
  whose block never got a poll).

**Tests.** Add jsdom cases to `tests/js/draft_publish.test.js` (already
registered in the `test:practice-reactions` script) for the rendering logic:
a poll with publishable drafts offers the button; a poll with unpublished but
zero publishable explains that details are missing instead of offering it; a
fully-published poll offers nothing. Keep the existing "no week-level publish
control" assertions passing.
