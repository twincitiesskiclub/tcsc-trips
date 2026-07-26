# Lead availability branch — handoff

> **Status:** NOT ready to merge. One Critical open, two decisions needed from Rob.
> **Prepared:** 2026-07-26.
> **Branch:** `lead-availability`, 41 commits on top of `main` (base `0b229ec`).
> Nothing merged. Nothing has posted to the club's real Slack channel.

## Suggested next-session prompt

> Read `docs/superpowers/notes/2026-07-26-lead-availability-handoff.md`
> completely. Make the two pending decisions (publish control, ALUMNI
> nudging), implement the publish path with a test that a practice actually
> becomes member-visible, work the before-merge findings, then take the
> branch through review and merge. Use `.venv`, not `env/`. The test
> database is the real local dev database — follow
> `tests/practices/conftest.py` conventions exactly.

## What the branch is

Replaces five years of availability-by-Google-Sheet for practice leads:

1. Monthly job drafts the next 4 weeks of practices (`is_draft=True`,
   invisible to members)
2. Readiness digest to coaches/directors listing what details are missing;
   daily re-nudge while incomplete
3. Director opens a Slack poll — leads react with letter emoji
   (`:letter_a:`…) to sessions they can lead, ✅ = "that's everything,
   even if I picked nothing"
4. Reactions captured as availability rows, reconciled against
   `reactions.get` before every nudge and at close
5. Daily DM to non-responders only (first at day 3, max 3, 2 days apart)
6. Practice admin form's lead picker shows availability, load
   (block + 90d), and staleness so the director assigns with data

Assignment deliberately stays a human judgment call. Substitutions are out
of scope — that part of the channel works.

Design: `docs/superpowers/specs/2026-07-25-lead-availability-design.md`.
Plans: `docs/superpowers/plans/2026-07-25-{draft-practices-and-readiness,lead-availability-poll,lead-picker-integration}.md`.
Full task-by-task ledger with every deferred finding:
`.superpowers/sdd/progress.md`. Last fix round:
`.superpowers/sdd/final-fixes-report.md`.

## State

| What | Where it stands |
|---|---|
| Implementation | 19/19 tasks across 3 plans, each with an independent review + fix round |
| Tests | 1405 Python passing (baseline before branch: 1270), 55 JS passing |
| Migrations | Linear chain `d4e7f9a1b2c3 → 1b29976741b6 → 3d34ea39db0f`, round-tripped against a production-shaped clone |
| Whole-branch review | **Not ready to merge.** 4 Criticals; 3 fixed in `63f2726`, 1 open (below) |
| Slack | Only Phase 0 previews to the shadow channel. No production posts |

## THE BLOCKER: drafts are never published

Nothing on this branch sets `is_draft = False`. The whole-branch reviewer
traced the chain end to end: all four test practices finished still
`is_draft=True`, invisible to every member-facing surface — announcements,
`/tcsc practice`, App Home, coach weekly summary, Skipper routines all read
through `published_practices()`, which excludes drafts. A director can
draft, poll, and assign leads to a practice that no member will ever see.

This was a planning failure, not an implementation one. The design overview
names the step (`Publish → is_draft=False → refresh_practice_posts()`) and
no task was ever written for it. Nineteen per-task reviews each correctly
confirmed their own task; only a whole-branch trace could see the gap.

Note also: 1405 tests pass because nothing in the suite asserts a practice
ever becomes member-visible. When implementing the publish path, add that
assertion — the missing test is itself part of the gap.

## Decision 1 — where the publish control lives

| Option | Notes |
|---|---|
| Publish button per practice on the edit form | Matches the design overview's flow literally |
| Bulk publish on the practices list page | The Sunday workflow is a batch; publishes a block at once |
| Automatic once a practice has its full complement of leads | No extra click, but removes the explicit human gate |

Recommendation from the review: **bulk**. The Sunday workflow is a batch
operation, and twelve individual clicks is how a tool gets abandoned. The
other two are viable; per-practice is closest to the approved design,
auto-on-assignment trades the explicit gate for zero friction.

Whichever wins: publish must call `refresh_practice_posts()` so
announcements fire, and the new test must assert the practice appears in
`published_practices()` afterwards.

## Decision 2 — should ALUMNI leads be nudged?

`eligible_leads()` excludes DROPPED members but deliberately keeps ALUMNI,
because this club's coaches are legitimately ALUMNI-status while still
actively coaching — a blanket status filter would drop real coaches. The
open question is ALUMNI members holding a *lead* tag (not a coach tag):
should they get availability DMs? Unresolved; flagged during P2 Task 6
review. Options: leave as-is (they're tagged, they get asked), or filter
ALUMNI unless they hold `HEAD_COACH`/`ASSISTANT_COACH`.

## Deploy-order constraint

Do **not** enable `lead_availability_nudge` in an environment where poll
closing does not exist — with nothing closing polls, every historical poll
is reconciled and nudged forever. On this branch that's resolved
(`lead_availability_close`, daily 08:30 Central), but note the ordering:
the 08:00 nudge runs *before* the 08:30 close, so a final round of DMs can
go out the morning after a block ends. Acceptable, or swap the times.

Pre-deploy check: query prod for `role='assist'` PracticeLead rows on
FUTURE practices. The assist role is retired from the UI, so any existing
future assist would be unremovable via the form yet still show in
announcements.

## Shadow mode

Defaults **ON** as of `63f2726` — previously a missing config row resolved
to the live 64-member `#coord-practices-leads-assists` channel. Config
keys (AppConfig, no deploy needed to change):

| Key | Behavior |
|---|---|
| `lead_availability.shadow_mode` | Default `True` when unset |
| `lead_availability.shadow_roster` | List of Slack user IDs. **Fails closed** — unset/empty/unknown-UID means nobody is nudged, never falls back to the live pool |

Shadow channel: `#collab-asset-mgmt-practices` (`C0B3Y71PG92`, 5 members).
When shadowed: poll posts there, participant pool is the roster, DMs reach
only the roster. Director-facing surfaces (bootstrap, readiness digest to
`#coord-coaches-practices`) run live by design — drafts are invisible to
members, so that's safe.

The admin UI confirms the resolved channel by name before the open step;
shadow-ness is decided at create and persisted on the poll, so toggling the
config later cannot retarget an existing poll.

## Remaining findings — triage

Fixed already (63f2726): shadow default inversion, tests deleting real
AppConfig rows, `open_poll`/`build_poll` re-entrancy (a double-open
orphaned reactions and reconcile then deleted every stored response),
availability branch in `reactions.py` guarded so it can't take down
attendance RSVPs.

**Fix before merge:**

- The publish path (above), with a member-visibility test.
- `EmojiSupplyError` escapes the create-poll route as a 500. Should be a
  clear 4xx with the message (too many sessions for 26 letters).

**Fix soon after (shadow month is the buffer):**

- Editing a practice never updates an open poll's message. Responses get
  stale-flagged via the date/location snapshot, but the post itself keeps
  showing the old session details.
- The readiness nudge repeats identically every day with no dedupe or
  escalation. Directors are live from day one, so this lands immediately.
- Two coexisting lead-picker code paths: create mode keeps the old
  person-pill picker (no practice id → no candidates endpoint), edit mode
  has the new ranked picker. Could resolve by creating a draft row on
  "New" so an id always exists. Edit mode is the primary Sunday path since
  practices are auto-drafted.
- `loadLeadPicker` leaves a stuck "Loading..." on fetch failure; sibling
  loaders render an in-place error.
- The poll-open commit sits outside the error guard — a commit failure
  leaves a posted-but-DRAFT poll.
- First nudge effectively lands day 4, not day 3 (72h rule + 8am job).

**Fine as-is / opportunistic:**

- Duplicate module-level cache of `practices.yaml` instead of reusing
  `_config.py::_load_practice_config` (drift trap if `reload_config` is
  ever wired on one side only).
- Availability model `created_at` defaults still `datetime.utcnow` while
  `opened_at` uses `now_central_naive()` (the day-3 rule compares against
  `opened_at`, so this is cosmetic today).
- `availability_reactions` / `availability_nudge` not re-exported from the
  `app/slack/practices/__init__.py` barrel.
- `lead_availability_responses` composite unique leads with `poll_id`, so
  practice_id-only / user_id-only lookups are unindexed. Fine at club
  scale.
- `shadow_roster` has no isinstance guard (fails closed anyway).
- Stale "Assists" label at `app/static/admin_practices.js:301` and in the
  `practice_editor.js` docstring; dead `PracticeInfo.assist_user_ids`.
- `scheduler.py:663` broad except-Exception can hide a missing-column
  error (pre-existing, not introduced here).
- Test retrofits: `test_practice_draft_schema.py` predates the conftest
  conventions; `test_drafting.py::_delete_practices_in_slots` still uses
  the unsafe bulk-delete pattern.

## Operational notes

**Environment.** The checked-in `env/` virtualenv is a stale macOS one and
does not work. Use `.venv`. Run tests with:

```bash
.venv/bin/python -m pytest tests/ -q --ignore=tests/wix_scrape
```

`tests/wix_scrape` has pre-existing unrelated collection errors.

**The test database is the real local dev database.** Test debris leaked
into it five separate times during this branch. `tests/practices/conftest.py`
documents the conventions adopted in response: no `create_all`/`drop_all`,
`try/finally` cleanup with `db.session.rollback()` first, year-2099 dates,
`"TEST "` prefixes, ids captured as plain ints before the `try`, scoped
queries. Follow them exactly; the rollback-first rule exists because a
poisoned session otherwise skips cleanup and cascades failures into the
next test.

**Letter emoji are infrastructure.** `:letter_a:`…`:letter_z:` are custom
workspace emoji, configured in `config/practices.yaml`
(`letter_emoji` list). They were renamed once during design
(`regional_indicator_*` → `letter_*`) and that silently broke a live poll,
which is why the full set is validated against `emoji.list` before any poll
opens — if they're ever renamed or deleted again, polls refuse to open, by
design. `lead_availability_poll_practices` stores both emoji name and
position so ordering survives a rename.

**Approved copy is director-signed.** Real Slack renders were previewed in
`#collab-asset-mgmt-practices` via `scripts/preview_lead_availability_ui.py`
(`--layout block-letters|week-numbers`, `--clean`). The approved copy is
reproduced verbatim in `app/slack/blocks/availability.py` — do not reword
it without re-previewing.

## Key files

| File | Role |
|---|---|
| `app/practices/availability.py` | Poll build/open/close, reconcile, eligible pool |
| `app/practices/drafting.py` | Monthly draft generation, `drafted_practices_in_window` |
| `app/practices/availability_emoji.py` | Emoji assignment + validation, `EmojiSupplyError` |
| `app/routes/admin_availability.py` | Poll create/open routes, `_shadow_mode()` |
| `app/slack/blocks/availability.py` | Director-approved poll/nudge/digest copy |
| `app/slack/practices/` (`availability_reactions`, `availability_nudge`) | Reaction capture, nudge DMs |
| `app/scheduler.py` | 4 new jobs: bootstrap (1st 08:00), readiness nudge (09:00), availability nudge (08:00), poll close (08:30) |
| `app/static/admin_practices.js`, `practice_editor.js` | Lead picker UI |
| `tests/practices/conftest.py` | Dev-DB test conventions — read before writing tests |
