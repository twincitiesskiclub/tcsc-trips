# Lead availability branch — handoff

> **Status:** DEPLOYED to production 2026-07-27 (PR #224, merge `8a24d56`).
> Shadow mode ON, roster set. See "Production state after deploy" below for
> what is live and what still needs a human.
> **Prepared:** 2026-07-26. **Updated:** 2026-07-26, after the second
> whole-branch review.
> **Branch:** `lead-availability`, 89 commits on top of `main` (base `0b229ec`).
> **Tests:** 1536 Python (baseline before the branch: 1270), 81 JS.
> **Migrations:** single head `539ad532aeb3`, dev DB at head, chain linear and reversible.
> Nothing merged. Nothing has posted to the club's real Slack channels except the
> readiness digest, which is live by design (see Shadow mode).

## Suggested next-session prompt

> Read `docs/superpowers/notes/2026-07-26-lead-availability-handoff.md` completely.
> Decisions are applied and the second whole-branch review is closed out. What is
> left is the shadow month: merge, deploy, set `lead_availability.shadow_roster`,
> and watch the list under "What to watch during the shadow month". Use `.venv`,
> not `env/`. The test database is the real local dev database — follow
> `tests/practices/conftest.py` conventions exactly.
> `.superpowers/sdd/progress.md` is the full task-by-task ledger if you need the
> reasoning behind any decision.

## Production state after deploy (2026-07-27)

Merged as `8a24d56`; Render's release phase ran 4 migrations
(`d4e7f9a1b2c3` → `539ad532aeb3`). Verified against prod, read-only:

- All four `lead_availability_*` tables exist; both new `practices` columns are
  NOT NULL with server defaults.
- **77 existing practices, 0 drafts** — the backfill left every pre-existing
  practice published, so nothing vanished from a member-visible surface.
- Site returns 200.

**The live pool is 57 people, not the 10–17 this document assumed.** 67 carry an
eligible tag; 10 are ALUMNI without a coach tag and are excluded by the ALUMNI
rule; the remaining 57 are all Slack-linked and DM-able. Re-check three things
before shadow mode is turned off, all of which were reasoned about at ~15
people: the lead picker renders one row per candidate, `_load_counts` scans
lead history for the whole pool on every picker load, and
`lead_availability_responses`' composite index leads with `poll_id`.

**Config set in prod:**

| Key | Value |
|---|---|
| `lead_availability.shadow_roster` | 6 UIDs — Ellie Thorsgaard, Rob Rutscher, Chris Frenier, Jacob Dean, Alex Gude, Augie Witkowski |
| `lead_availability.shadow_mode` | no row → defaults ON (correct) |
| everything else `lead_availability.*` | no row → config/practices.yaml defaults |

**Two open items:**

1. **Alex Gude and Augie Witkowski are on the roster but not in
   `#collab-asset-mgmt-practices`, which is a PRIVATE channel** — so they can't
   self-join. As it stands they would be enrolled as participants, DM'd a
   permalink to a message they cannot open, stay PENDING through all three
   nudges, and their silence would read as "didn't respond" rather than
   "couldn't". Either invite them or drop them from the roster.
2. **`practice_days` has no active Saturday.** Active slots are Tue 18:15,
   Thu 18:05 and Thu 19:20. The row exists, so the Tue/Thu/Sat fallback in
   `default_practice_days()` never applies and no Saturday practice will be
   drafted. Fine for summer; add one before ski season.

The Aug 1 08:00 bootstrap is the first thing that will run. Its readiness digest
posts to the **real** coaches channel (not shadow-gated, by design), so that is
what coaches see first.

## What the branch is

Replaces five years of collecting practice-lead availability by Google Sheet:

1. A monthly job (1st, 08:00 Central) drafts practices through the end of *next*
   month with `is_draft=True` — invisible to every member-facing surface.
2. A readiness digest posts to the coaches/directors channel listing which drafts
   still lack location, activity type or time. A daily 09:00 job chases the gaps
   **as replies in that digest's thread**, so the channel isn't spammed.
3. The practices director opens a Slack poll — one message listing the block's
   sessions, each tagged with a custom letter emoji (`:letter_a:`…). Leads react
   to the sessions they can lead; ✅ means "that's everything, even if I picked
   nothing".
4. Reactions become availability rows, reconciled against `reactions.get` before
   every nudge and at close.
5. Non-responders get a DM nudge — first on calendar day 3, max 3, ≥2 days apart.
6. The practice admin form's lead picker shows each candidate's availability,
   load (in-block and 90-day) and response staleness.
7. The director publishes the block, which flips `is_draft=False`.

Assignment stays a human judgment call by design. Substitutions are out of scope.

Design: `docs/superpowers/specs/2026-07-25-lead-availability-design.md`.
Plans: `docs/superpowers/plans/2026-07-25-{draft-practices-and-readiness,lead-availability-poll,lead-picker-integration}.md`
and `docs/superpowers/plans/2026-07-26-lead-availability-followups.md` (P4).
Ledger with every decision and deferred finding: `.superpowers/sdd/progress.md`.

## Publishing — read this before touching it

**The unit of publishing is the availability block, not the week.** One click per
month, from the poll that collected that block's availability, weeks before any
of those practices reach their own Sunday:

```
POST /admin/availability/polls/<id>/publish
```

The UI is the poll cards on the practices list page. Three honest states per
poll: a `Publish N practices` button when `publishable > 0`; *"N drafts need
details before publishing"* when `unpublished > 0` but `publishable == 0`;
*"All published"* only when `unpublished == 0`.

**Do not add a week-level or automatic publish.** The Sunday evening flow already
puts the coming week in front of members with nobody clicking anything — the
public weekly summary at Sun 20:30 plus the announcement job, both reading
`published_practices()`. An earlier iteration of this branch added a
`publish_week_drafts` button on the Sunday coach post and a batch banner on the
practices list; both were removed as regressions (`4b8f89b`).
`tests/js/draft_publish.test.js` asserts they stay gone.

Two deliberate exceptions, both kept:
- **Drafts still appear in the Sunday coach post**, flagged not actionable. That
  post used to query `published_practices()`, so drafts were invisible in the one
  place coaches would look *and* each drafted slot rendered as an empty "Add
  Practice" placeholder inviting a duplicate on top of the draft. A draft still
  sitting in the coming week means it never made it into a poll — nothing else
  would catch that.
- **Single-practice publish in the list drawer**, via
  `POST /admin/practices/publish`. A draft whose block never got a poll would
  otherwise have no route to being published at all.

Publishing does **not** post the announcement. The announcement job already scans
`published_practices()` for rows with no `slack_message_ts`, so flipping the flag
hands the practice to the existing pipeline with its timing rules intact.
Publishing does call `refresh_practice_posts(change_type='create')`.

`coach_visible_practices()` in `app/practices/service.py` is the deliberate,
greppable counterpart to `published_practices()` — it INCLUDES drafts and is for
coach/director surfaces only. Never use it for anything a member can see.

## Open decisions — all three resolved 2026-07-26

**1. `open_poll` posture after a failed DB commit — resolved: leave nothing
behind.** Rob's call was no manual cleanup. On commit failure `open_poll` now
rolls back *and* `chat_delete`s the message it just posted, so a failed open is a
true no-op and the director simply clicks open again — which is safe precisely
because the poll is back to DRAFT. Nobody can have reacted to a message that
lived for the length of one failed commit, so no record is lost. The older
loud-log-naming-the-live-ts path survives for the case where the cleanup delete
*also* fails: two independent failures, and the only one that still needs a
person. (`785bf03`)

**2. Nudge/close ordering — resolved: skip that day's nudge.** Schedule times
are unchanged (nudge 08:00, close 08:30). `participants_to_nudge()` now returns
nothing once `today > poll.ends_on`, so the morning after a block ends nobody is
DMed even though the poll is still OPEN for another 30 minutes. The gate is the
poll's own `ends_on` rather than "has the close job run yet", so the two
schedules can be reordered later without reintroducing the stray DM. Two
existing MAX_NUDGES tests drove `now` past `ends_on`; both were moved inside the
block window so they still exercise the ceiling instead of passing on the new
gate. (`66e5e07`)

**3. Pre-deploy prod query — resolved: nothing to do.** Queried prod read-only
on 2026-07-26: `practice_leads` holds 73 `coach` and 102 `lead` rows and **zero
`assist` rows**, on any practice, past or future. So there is no cleanup, no
migration and no code change needed.

For the record, since the question came up: nothing about the role key changed.
`role='assist'` is still a valid value (`LeadRole.ASSIST`,
`app/practices/interfaces.py`), the rows still read, and announcements still
render them. What changed in `b2a64bc` is that the practice *edit* path used to
delete every `PracticeLead` row for the practice and rewrite them from the form,
and now deletes only `role in ('coach', 'lead')` — deliberately, so historical
assists survive an edit. Since the form no longer offers an assists field, no
submission can clear an assist row; on a *future* practice that would mean a row
that still shows in announcements with no UI to remove it. Prod has none, so the
preserve-history branch is inert. If assist rows ever reappear, the cheap fix is
to scope the preservation to practices whose date is in the past.

## Recommended before merge

**Done.** The second whole-branch review ran at `785bf03` across five scopes;
see "The second whole-branch review" below. All five blockers are fixed and the
suite is green at 1536 Python / 81 JS.

## What P4 fixed, and what it found

The five "fix soon after" items all landed. The process also found three more
problems, two worse than anything on the original list.

**Confirmed and fixed — measured, not estimated:**

- **The monthly draft window was shorter than the month it ran on.**
  `expected_slots` normalised week 0 back to the Monday *before* `start_date` then
  dropped earlier slots, so a `weeks=4` window covered only `28 - weekday` days
  forward while the job fires monthly. **15 of 91 slots over 8 months were never
  drafted** — only a Monday-the-1st month came out clean. Those practices never
  existed as rows, so `build_poll` couldn't mention them and the next run never
  looked back; they'd surface as empty "Add Practice" placeholders in the week they
  happened with zero availability collected. Now an explicit horizon
  (`end_of_next_month`), so consecutive runs deliberately overlap —
  `generate_draft_block` is idempotent. **After: 0 of 157 slots missed over 12
  runs.** A twelve-consecutive-months test asserts the no-skip property with an
  independently enumerated expectation.
- **`_shadow_mode()` failed OPEN on a JSON-null config row.** `AppConfig.get`
  returns `config.value` whenever the *row* exists, so `bool(None)` flipped shadow
  OFF and routed the poll to the live 64-member channel. Verified: no row → shadow
  ON; null row → shadow ON; explicit `False` → live (the deliberate opt-out, still
  works).
- **The block-level publish gate had zero callers.** The route existed and was
  tested, `GET /admin/availability/` returned the counts, but nothing rendered
  them — while the coach Slack post told directors to "publish the availability
  block it belongs to". Now wired (Task 8).
- **Deleting a polled practice raised `ForeignKeyViolation`** — branch-introduced,
  since those tables are new here. Fixed with an ORM cascade from the `Practice`
  side (`cascade="all, delete"`, not `delete-orphan`, so the poll and other
  sessions survive). Every practice-delete path in the app goes through
  `db.session.delete()`, which is why the ORM cascade is sufficient.
- **The monthly digest under-reported by a whole month.** It labelled the range
  from `today` but summarised only `created`, which after the first run holds only
  the *following* month's rows — so it read "13 of 13 ready" while that month's
  other 13 drafts sat inside the stated range, absent from the counts and the
  incomplete list. Now summarises over `drafted_practices_in_window`.
- **The done emoji is now snapshotted on the poll row** (migration
  `539ad532aeb3`). It had become config-readable but resolved at call time, so
  editing the config mid-poll would demote every already-DONE participant and
  re-DM leads who'd declared themselves finished — the exact bug class the letter
  emoji were hardened against by persisting emoji+position. Reads go through
  `poll.resolved_done_emoji`, which falls back to config for pre-migration rows;
  `open_poll` backfills before the poll goes OPEN.
- Both nudge gates were hours-vs-calendar-days, not just the first: the 72h
  first-nudge rule *and* the `MIN_DAYS_BETWEEN_NUDGES` spacing check (which
  slipped a follow-up from day 5 to day 6 over 30 seconds).
- `practice_days` defaults diverged — drafting was Tue+Thu while three
  coach/admin sites were Tue+Thu+**Saturday**. Now one shared
  `default_practice_days()`, returning a fresh copy of a tuple so aliasing can't
  recur.
- Editing a practice now re-renders any OPEN poll's Slack message. Emoji letters
  stay pinned to surviving sessions, so a dropped line never shifts letters under
  reactions already given.
- A deleted digest post no longer stops the readiness chase silently — the stale
  record is cleared and the nudge retries top-level.
- ALUMNI are filtered from the availability pool unless coach-tagged (Rob's call).
- `EmojiSupplyError` on the create-poll route is a 400 naming the fix, not a 500.
- `loadLeadPicker` had no try/catch while all three sibling loaders did, so a
  rejected fetch left "Loading…" on screen forever. Both failure paths now render
  an in-place error.
- `availability_warning` (a new practice created inside an OPEN poll gets no
  letter and no availability) now reaches the admin, via a sessionStorage handoff
  because the create page redirects in ~800ms.

## The second whole-branch review (2026-07-26)

Five reviewers, one per scope: availability core, drafting/publishing,
scheduler + Slack, routes + frontend, tests + migrations. Every finding acted
on below was independently verified against the code first, and two were proved
empirically rather than argued.

**Five blockers, all fixed.** In severity order:

- **The close-job tests closed every OPEN poll in the database.**
  `run_close_expired_polls_job` filters `status == OPEN AND ends_on < today`
  with no other scope, and three tests patched `today_central` to 2099 — so
  they swept the whole table. Against this dev DB that silently CLOSES a live
  shadow poll: nudges stop, the picker treats partial availability as final,
  recovery is a manual UPDATE. Proved by planting a poll dated 2026-08-31 and
  watching the new `protect_foreign_polls` fixture restore it three times, once
  per job test. (`1538bf3`)
- **Three suites deleted real near-term practices.**
  `test_lead_candidates_endpoint` and `test_admin_practice_leads_needed` both
  reserved `2026-08-04 18:15` — a real Tuesday nine days out, at the exact time
  every availability suite treats as the club's slot — and the first had no
  collision guard at all. `test_drafting`'s four generation tests swept real
  `2026-08-03..16` with a helper that documents deleting rows "regardless of
  who created it". All now on reserved 2099 windows. (`8e704af`)
- **A lead picker that failed to load turned Save into "delete all leads".**
  The container is server-rendered with a "Loading…" placeholder, so
  `collectLeadIds()` took the picker branch whether or not it had rendered, and
  the form always submits `lead_ids`. Both a failed load and a Save during the
  load window (`loadLeadPicker()` is called without `await`) produced `[]`,
  which `edit_practice` reads as "delete every lead" — then
  `refresh_practice_posts` rewrote the member-facing announcement without them.
  (`cd56b88`)
- **Shadow-mode containment and the ALUMNI exclusion were both inert for DMs.**
  Found independently by two reviewers in different file scopes.
  `participants_to_nudge` selected on `poll_id` + PENDING alone, but
  `_participant()` creates a row for anyone who reacts, and `reconcile_poll`
  (run immediately before `send_nudges`) resets a withdrawn reaction to
  PENDING. So a non-roster coach in the shadow channel who tapped a pill and
  untapped it got DMed — during the month whose entire purpose is that no real
  lead is. (`6478dd9`)
- **An empty `time` in `practice_days` erased a whole weekday**, and `"25:00"`
  killed the bootstrap job outright — the same silent-absence class this branch
  exists to eliminate, one cleared form field away. (`2420e7e`)

**Also fixed:** an abandoned DRAFT poll bricking its date range (cancelling the
shadow-mode confirm dialog — the thing the dialog is *for* — left a poll
nothing could open or discard); three missing `db.session.rollback()`s that let
one poll's DB error poison every later poll in the run; stored XSS in the
detail rails (member names from the public registration form, admin CSP allows
`unsafe-inline`); the poll seeding past Slack's 23-reactions-per-user cap and
reporting success anyway; no warning when a practice is *rescheduled* into an
open poll; assigned leads outside the pool being invisible and dropped on save;
availability recorded for cancelled sessions; and 17 `db.create_all()` calls
that could wedge a developer's migration chain (all removable — the suite is
green without them — now guarded by `tests/test_no_create_all.py`).

One finding was against this session's own earlier work: deleting the orphaned
Slack message assumed a raising `commit()` means nothing was written, which is
false when the connection drops *after* Postgres commits. Now re-reads the row
first. (`34b7e89`)

## Known minors — none blocking

- A **native** done emoji other than `white_check_mark` still blocks the poll:
  `NATIVE_EMOJI` is hardcoded, so `emoji.list` never confirms it and `open_poll`
  refuses. Declined deliberately — it now refuses *loudly naming the right config
  key*, which beats opening a poll whose DONE reaction nobody can give. Close it
  with a small native allowlist if you care.
- The daily nudge's start label is still `today` while the bootstrap's is
  `min(drafted)`, so the same block can read "Sep 3 – Oct 29" then "Sep 2 – Oct 29".
- Four copies of `innerHTML = <p class="rail-error">${err.message}</p>` in
  `_detail_context.js` (all escaped now, but still four copies).
- `lead_availability_responses`'s composite unique index leads with `poll_id`, so
  practice_id-only / user_id-only lookups are unindexed. Fine at 10–17 leads.
- No detector for a draft whose date has already passed — it simply never
  announces and ages quietly into the past. (The *new* detector,
  `undrafted_next_month`, catches a month nobody drafted, which is a different
  hole.)
- `_publish_counts` is an N+1 over poll → mappings → practice → types on every
  practices-list load. ~350 round trips at ten polls; add `joinedload` if the
  page feels slow.
- Every save still deletes and recreates `PracticeLead` rows, so a director
  editing workout text silently resets lead *confirmations* to Pending.
  Pre-existing, but newly consequential now that this form is the normal
  assignment path. Diffing ids instead would fix it.
- `README`-level: `test_practice_post.py` in the repo root is a manual script, not
  a pytest file.

**Corrected from the previous handoff:** the claimed "discarded tuple
assertions" minor was wrong. An AST scan over every changed test file found
zero `assert (expr, "msg")` tuples — they are bare expression statements, so
the assertion *does* fire and only the message string is dead. Not a
correctness problem.

## Deploy-order constraints

- Do **not** enable `lead_availability_nudge` in an environment where poll closing
  does not exist — with nothing closing polls, every historical poll is reconciled
  and nudged forever. Resolved on this branch (`lead_availability_close`, daily
  08:30 Central); the ordering issue from Open decision 2 is closed too, since
  the nudge now gates on the poll's own `ends_on`.
- **Confirm the `practice_days` AppConfig row exists in prod, and that it includes
  Saturday.** The dev database has no row at all, so everything falls back to
  `default_practice_days()`. If prod is the same, verify the fallback matches the
  real schedule before the first bootstrap fires.
- Set `lead_availability.shadow_roster` before anything runs. Unset means zero
  nudges with only a warning — a shadow month that produces no data looks
  identical to one that worked.
- Local `main` is **8 commits ahead of `origin/main`** (all of them the design
  spec, the three implementation plans and `scripts/preview_lead_availability_ui.py`,
  committed to main but never pushed). A PR opened against `origin/main` will
  therefore include those commits alongside the branch's own. Push `main` first
  if you want the PR diff to be the feature alone.

## Shadow mode

Defaults **ON**. Config keys are AppConfig, so no deploy is needed to change them.

| Key | Behavior |
|---|---|
| `lead_availability.shadow_mode` | Default `True` when unset **or null**. An explicit `False` is a deliberate opt-out and routes live |
| `lead_availability.shadow_roster` | List of Slack user IDs. **Fails closed** — unset/empty/unknown-UID means nobody is nudged, never a fallback to the live pool |

Shadow channel: `#collab-asset-mgmt-practices` (`C0B3Y71PG92`, 5 members). Live
coordination channel: `C02J4DGCFL2` (64 members). When shadowed: the poll posts to
the shadow channel, the participant pool is the roster, and DMs reach only the
roster. Shadow-ness is decided at poll *creation* and persisted on the poll, so
toggling config later cannot retarget an existing poll. The admin UI confirms the
resolved channel by name before the open step.

**The readiness digest is NOT shadow-gated** — it posts to the real
`COLLAB_CHANNEL_ID` from day one, daily at 09:00 whenever anything is incomplete.
That's intended (drafts are invisible to members, so it's safe), but it is the
first real-Slack side effect of this branch and coaches will see it before
anything else.

## What to watch during the shadow month

- **The block boundary.** After the first bootstrap, diff the drafted dates
  against the configured slots for the whole month. This is where the drafting bug
  showed up, and it shows up as an *absence* — nothing will page you.
- `shadow_roster is unset or empty` in the logs: one line per nudge run, and it
  means the month is a no-op.
- **Which channel the first poll landed in.** Verify the ts appears in
  `C0B3Y71PG92`, not `C02J4DGCFL2`.
- Reaction volume vs. response rows. If leads react and
  `LeadAvailabilityResponse` stays empty, suspect a missing `reactions:read` scope
  or the bot not being in the shadow channel. `reconcile_poll` logs the Slack
  error and the nudge job then correctly skips nudging — silent but progress-free.
- Expect a burst of `refresh` warnings on the first block publish (~3 per
  practice: announcement, coach summary and weekly summary are all legitimately
  absent for a practice published weeks early). Don't read them as failures.
- **Signals it's going wrong:** a poll whose `unpublished` count stays non-zero
  after its leads are assigned; the coach post's "⚠ N practices … still a draft"
  footer appearing on a Sunday; a week reaching Sun 20:30 with an empty public
  summary.

## Operational notes

**Environment.** The checked-in `env/` virtualenv is a stale macOS one and does
not work. Use `.venv`:

```bash
.venv/bin/python -m pytest tests/ -q --ignore=tests/wix_scrape   # 1494 passing
npm run test:practice-reactions                                  # 74 passing
```

`tests/wix_scrape` has pre-existing unrelated collection errors.

**The test database is the real local dev database.** Test debris leaked into it
five separate times during this branch. `tests/practices/conftest.py` documents
the conventions adopted in response: no `create_all`/`drop_all`, `try/finally`
cleanup with `db.session.rollback()` FIRST, year-2099+ dates, `"TEST "` prefixes,
ids captured as plain ints before the `try`, scoped queries. Follow them exactly.
Two additions learned this session: **delete practices through the ORM**
(`db.session.delete(obj)`) — a bulk `.delete()` skips `practice_types_junction`
rows and dies on an FK violation, leaving the row behind; and **save/restore any
`AppConfig` row a test touches**, never unconditionally delete it.

**Migration round-trips** can be tested safely: `test_practice_migration_release.py`
has a `release_schema` fixture that creates a throwaway `practice_release_<uuid>`
schema and drops it CASCADE in a `finally`. Use it rather than downgrading the
shared dev database.

**Letter emoji are infrastructure.** `:letter_a:`…`:letter_z:` are custom
workspace emoji configured in `config/practices.yaml` (`letter_emoji`). They were
renamed once during design and that silently broke a live poll, which is why the
full set is validated against `emoji.list` before any poll opens — if they're
renamed or deleted again, polls refuse to open, by design.
`lead_availability_poll_practices` stores both emoji name and position so ordering
survives a rename, and as of `539ad532aeb3` the done emoji is snapshotted too.

**Approved copy is director-signed.** Real Slack renders were previewed in
`#collab-asset-mgmt-practices` via `scripts/preview_lead_availability_ui.py`
(`--layout block-letters|week-numbers`, `--clean`). The approved copy is
reproduced verbatim in `app/slack/blocks/availability.py` — do not reword it
without re-previewing.

## Key files

| File | Role |
|---|---|
| `app/practices/drafting.py` | `end_of_next_month`, `expected_slots(start, end)`, `generate_draft_block` (idempotent), `default_practice_days()`, `missing_fields` |
| `app/practices/availability.py` | Poll build/open/close, reconcile, `eligible_leads()` |
| `app/practices/availability_emoji.py` | Emoji assignment + validation, `done_emoji()`, `EmojiSupplyError` |
| `app/practices/publishing.py` | `publish_practice`, `publish_practices`, `publish_blockers` |
| `app/practices/service.py` | `published_practices()` (excludes drafts) vs `coach_visible_practices()` (includes them, coach surfaces only) |
| `app/routes/admin_availability.py` | Poll create/open, `publish_poll_block`, `_shadow_mode()` |
| `app/slack/blocks/availability.py` | Director-approved poll/nudge/digest copy |
| `app/slack/practices/refresh.py` | Surface registry, incl. the `availability_poll` surface |
| `app/scheduler.py` | `_block_anchor`, bootstrap (1st 08:00), readiness nudge (09:00), availability nudge (08:00), poll close (08:30) |
| `app/static/admin_practices.js` | Poll cards + publish, draft badges, lead picker |
| `tests/practices/conftest.py` | Dev-DB test conventions — read before writing tests |
| `.superpowers/sdd/progress.md` | Full ledger: every task, decision and deferred finding |
