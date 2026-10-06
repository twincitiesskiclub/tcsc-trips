# Lead availability, simplified

2026-10-05. Revises `docs/superpowers/specs/2026-07-25-lead-availability-design.md`
(PR #224, deployed 2026-07-27, never used). The lead side of that design stays.
The practices team's side is rebuilt.

## Problem

PR #224 works, but nobody uses it, and its draft step has already cost real
practices.

- **The poll could not open.** `build_poll()` refuses until every draft in range
  has a location and a type. Drafts are created with neither, two months ahead.
  Chris fills a practice about a week out, so the poll was never openable.
- **The readiness digest is noise.** It chases two months of drafts every morning
  in #collab-coaches-practices and has said "0 ready" daily since Sep 1. Its copy
  ("the poll unlocks once all of them are set") is also wrong for a scoped poll.
- **Manual publish fails silently.** Drafts for Sep 1, Sep 3 (x2) and Sep 10 (x2)
  were never published and never announced, and no other practice exists on
  those dates. The Sep 10 rows were edited on 9/6 and still stayed hidden.
  Practice 101 (kickoff) needed a script to publish.
- **Results are invisible.** The only place to see who can lead is one practice
  edit page at a time, each listing the whole 60-person pool.
- **Publishing races the weekly summary.** Chris publishes on Sunday at about
  20:30, the minute the member weekly summary runs.

## Goals

- Every two weeks, the practices team (Chris, Ellie, Jacob) spends a few minutes
  in one Slack post: open the poll, see coverage, assign leads.
- A bot-created practice can never be silently held back. It shows up for members
  as soon as it has the details members need.
- Leads keep the reaction poll exactly as designed in July.

## Non-goals

- Changing how leads answer (reactions on one public post, ✅ for done, DM
  reminders).
- Automatic assignment. A person picks every lead.
- Automatic poll opening. A person presses the button.
- Substitutions, capability profiles, coach scheduling (same as July).

## Build principles

This is a v2 of a system that never ran: prod has 0 polls, 0 participants and 0
responses. Keep it simple.

- **Replace, don't adapt.** No backward compatibility, no data backfill, no
  feature flags. July code that the new flow doesn't need is deleted, along with
  its tests.
- **Reuse what works.** `generate_draft_block`, `poll_rows`, the reaction handler,
  `reconcile_poll`, the nudge rules, `refresh_practice_posts`, the full edit modal
  and the existing never-raise Slack pattern stay as they are unless this spec
  names a change.
- **No new states when an existing one fits.** Polls keep three statuses: `draft`,
  `open`, `closed`. Concurrency uses a database row lock, not a status.
- **Few new files.** `app/practices/blocks.py` (block job, `open_block_poll`,
  block-post data), `app/slack/blocks/block_post.py` (Block Kit for the block post
  and Assign modal), and handlers added where the existing Slack actions live.
- **Each phase should remove about as much code as it adds.**

## Decisions

| Question | Decision |
|---|---|
| What must a session have before the poll opens? | Date and time only. Missing details show as "Location TBD"; the poll line updates when they are filled in. |
| Block length and timing | Two weeks, Monday to Sunday, handled one week ahead. Same scope for the team and for leads. |
| Draft and publish | No publish step. A bot-created session becomes member-visible automatically once it has a location and a type. |
| Who opens the poll | A person, from a button in Slack (main path) or on the admin page (fallback). |
| Results and assignment | One live block post in #practices-core with an Assign button per session. |
| Assign modal | Available people as one line of text, plus one dropdown to choose leads. |
| Coaches | Shown on the session row, not counted toward leads needed. |
| Rollout | Cut over at deploy. Shadow mode is deleted. |

## Rhythm

Blocks start on Mondays two weeks apart, anchored on **Mon 2026-10-26**. The
anchor is the AppConfig key `lead_availability.block_anchor`, so the cycle can be
shifted without a deploy.

Block starts are computed on `date` objects: `S` is a block start when
`(S - anchor).days % 14 == 0`, with today from `today_central()`. DST (Nov 1)
and year boundaries cannot shift it; the cron's `America/Chicago` timezone
handles the clock change.

For each block starting on Monday `S`:

| When | What |
|---|---|
| From `S - 7` (normally Mon 09:00) | Block job creates the block's sessions, its poll row (DRAFT) and the block post. |
| `S - 7` onward | Someone on the team presses Open poll. |
| From `S - 5` (normally Wed 09:00) | One thread reply on the block post if the poll is still unopened. |
| Poll day 3, then 2+ days apart, max 3, 08:00 | Nudge DMs to leads who have not answered (unchanged rules). |
| Every Sun 08:00 | Coach weekly summary, which now also covers hidden practices and offers Open poll for the coming week. |
| `S + 14` Mon 08:30 | Poll closes (unchanged: the morning after `ends_on`). |

### Block job

One daily job, `run_lead_block_job`, 09:00 Central. It acts on state, not on the
date it happens to run, so a missed Monday (deploy, misfire, Slack outage) is
caught the next morning:

1. For the block `S` with `S - 7 <= today <= S + 13` (the upcoming block from its
   post day on, then the current one): if no poll row exists for `(S, S + 13)`,
   create the sessions and the row and post the block post. If the row exists
   with a null `block_post_ts`, retry the post.
2. If `today >= S - 5`, the poll is still `draft` and `wednesday_reminder_sent_at`
   is null, post the Wednesday reply.

An admin action "Run block job now" on `/admin/practices/` triggers it by hand,
following the existing weekly-summary trigger route. That makes deploy day safe:
a deploy after Mon Oct 19 09:00 still gets its block post the same day.

### Scheduler changes

- Removed: `practice_block_bootstrap` (1st, 08:00), `practice_block_readiness_nudge`
  (daily 09:00).
- Added: `lead_block_job` (daily 09:00).
- Changed: `run_lead_availability_nudge_job` (08:00) re-renders each open poll's
  block post after its reconcile. `run_close_expired_polls_job` (08:30) also closes
  `draft` rows past `ends_on`, and re-renders the block post on close.

First regular cycle: block post Mon Oct 19 for Oct 26 to Nov 8. The current block
(Oct 12 to 25) is handled by the cutover (see Rollout).

## Sessions and visibility

### Creating sessions

The block job calls `generate_draft_block(S, S + 13)` (unchanged, idempotent on
exact datetime) and creates the block's `LeadAvailabilityPoll` row in DRAFT.
`generate_draft_block` returns new rows only, and prod already has drafts through
Nov 26, so its return value says nothing about whether the block has sessions.
The block covers every practice in its date range, whoever created it. The job
logs an error and posts nothing only when `expected_slots(S, S + 13)` is empty
and no practice exists in the range. The monthly bootstrap job and
`undrafted_next_month()` go away.

`build_poll()`'s "replace an abandoned DRAFT poll" branch goes away: DRAFT now
means "block post is up, poll not opened yet", which is a normal state.

Sessions are drafted with `leads_needed = 2`, as today. The admin edit form
already sets it per practice.

`is_draft` keeps its meaning in the code ("hidden from members") and its
boundary: `published_practices()` for member surfaces, `coach_visible_practices()`
for team surfaces. In copy, the team sees "hidden from members", never "draft".

### Visible when ready

`publish_if_ready(practice)` in `app/practices/publishing.py`: if the practice is
hidden and `publish_blockers()` is empty (location set, a practice type or
activity set, not cancelled), set `is_draft = False`, commit, and fan out
`refresh_practice_posts(change_type='create')` as `publish_practice()` does
today. Otherwise do nothing. One way only: clearing a location later never hides
a practice again.

Called after every save that can complete a practice:

- admin edit route (`app/routes/admin_practices.py`)
- Slack full edit modal submission (`app/slack/bolt_app.py`)
- the Sunday coach summary run (a sweep for anything a script or missed path left
  behind)

Practices created by hand (admin create form, Slack create modal) keep today's
behavior: visible immediately. Only bot-created sessions start hidden.

**Late publish gets announced.** The announcement job posts today's evening
practices at 08:00 and tomorrow's morning practices at 20:00. A practice's run
"has passed" when, for a practice on day D at or after 12:00, it is after D 08:00;
for one before 12:00, after D-1 20:00 (mirroring `run_practice_announcements_job`).
If `publish_if_ready()` publishes a practice whose run has passed and it has no
`slack_message_ts`, it re-runs the announcement job's selection and posting for
that one window (extracted from `run_practice_announcements_job` into a function
both call), so strength-session combining still applies. If a compatible session
was already announced on its own or in a group, the late one posts standalone.
A Tuesday session filled in at 10:00 Tuesday is announced at 10:00.

### Sunday coach summary

`post_coach_weekly_summary()` (Sun 08:00, #collab-coaches-practices) already lists
the coming week's practices, hidden ones included, with Edit buttons. Changes:

- It first sweeps the week's hidden practices through `publish_if_ready()`.
- Hidden-practice copy becomes "Hidden from members until it has a location"
  (or "a type"). The footer stops saying "publish the availability block it
  belongs to" and says how many practices members can't see yet, and why.
- If the coming week's block poll is still DRAFT, it adds an Open poll button.
  (Per-row ":warning: No lead" warnings already exist; no separate shortfall
  line.)

No separate Saturday job.

## Block post

One message per block in #practices-core (`PRACTICES_CORE_CHANNEL_ID`; moved from
#collab-coaches-practices on 2026-10-06). Its
channel and ts live on the block's poll row. Channel membership is the only
permission gate, the same as the existing Fill in and Edit buttons.

### Before opening

```
Lead poll · Oct 26 – Nov 8
Tue 10/27 · 6:15p · Theodore Wirth · Bounding
Thu 10/29 · 6:05p · Balance Fitness Studio · Strength
Thu 10/29 · 7:20p · Balance Fitness Studio · Strength
Tue 11/3 · 6:15p · location TBD
...
Opening posts this list to <#C02J4DGCFL2> for leads to react to.
Missing details are fine; the poll updates when you fill them in.
[Open poll]  [Edit a session ▾]
```

"Edit a session" is a select of the block's sessions that opens the existing full
edit modal. Cancelled sessions are not listed.

### Opening

Open poll (block post button, Wednesday reply button, Sunday summary button, or
the admin card) calls one service function, `open_block_poll(poll, opened_by)`:

1. Lock the poll row (`SELECT ... FOR UPDATE NOWAIT`) and hold the lock through
   the Slack post and the commit. If the lock is taken, or the row is no longer
   `draft`, answer the clicker with an ephemeral "Chris already opened this poll"
   and stop. If the process dies mid-open, Postgres releases the lock with the
   transaction, so nothing gets stuck. Today's `open_poll()` checks status in
   Python and has no such guard.
2. Map letters to every non-cancelled practice in the block's date range, in date
   order, hidden or not. (Today's `build_poll()` maps drafts only, which under
   "visible when ready" would drop every session the team already filled in.)
3. Validate emoji, post to #coord-practices-leads-assists (`COORD_CHANNEL_ID`),
   seed reactions, mark OPEN with `opened_by_slack_uid` (the clicker's Slack id,
   rendered as `<@uid>`, so a clicker with no linked member still shows). On failure, roll back (the poll stays `draft`)
   and show the error to the clicker.
4. Re-render the block post in its open state.

No readiness gate. The 22-session cap stays (a two-week block is 6 today).

### After opening

```
Lead poll · Oct 26 – Nov 8
Opened by Chris F, Mon 10/19 · see the poll
🟡 A  Tue 10/27 · 6:15p · Theodore Wirth · Bounding        [Assign]
      Leads: Katrin S · needs 1 more
🟢 B  Thu 10/29 · 6:05p · Balance Fitness Studio · Strength [Assign]
      Coach: KJ · Leads: Ellie T
🔴 C  Thu 10/29 · 7:20p · Balance Fitness Studio · Strength [Assign]
      No leads yet
...
31 of 60 leads have answered. Reminders go to the rest Sat and Mon.
```

- Dot: green when assigned leads ≥ `leads_needed`; yellow when some are assigned
  or someone is available; red when nobody is assigned and nobody is available.
  Coaches are shown ("Coach: KJ") and not counted.
- A session cancelled after opening stays on the post, struck through, with its
  letter, so the letters still line up with the leads poll.
- The footer counts only people in the lead pool. Its reminder days are computed
  from `opened_at` and the nudge rules, and the sentence disappears after the
  last nudge.

Re-rendered by `refresh_block_post(poll)`:

- after an Assign save or any practice create, edit, cancel or delete, as a new
  `refresh_practice_posts` surface that finds the block by date range, so every
  save path updates it
- each morning inside the 08:00 nudge job, after its reconcile
- when the poll closes

Not on individual reactions. Only the bot edits this message.

### Closed state

Rows and Assign buttons stay (late changes still happen), the context line reads
"Poll closed Mon 11/9", and the footer is dropped.

A `closed` poll with no `message_ts` is a block whose availability was collected
outside the app (used once, for Oct 12 to 25). Its post renders the same way
without letters or a poll link, and its context line reads "Availability
collected outside the app". No extra status.

### Wednesday reply

Wed 09:00 of the post week, if the poll is still DRAFT, one reply: "Nobody has
opened the lead poll for Oct 26 – Nov 8 yet. The first practice is Tue 10/27."
with [Open poll]. Threaded on the block post, or posted top-level if the block
post is missing. Sent once (`wednesday_reminder_sent_at`).

### Admin fallback

`/admin/practices/` loses the date pickers and the Open Availability Poll toolbar
button. The current block's card shows an Open poll button while it is DRAFT,
calling the same `open_block_poll()`. Cards lose their publish buttons.

## Assign modal

```
Assign leads · Tue 10/27
6:15p · Theodore Wirth · Bounding · needs 2
Available: Katrin S, Micah R, Dana P
Leads  [ Katrin S ×  ▾ ]
```

- "Available" is everyone with a response row for this session, by name. "nobody
  yet" when the poll is open and empty; "poll not opened yet" before opening; no
  line at all when the poll never posted (see Rollout).
- One `multi_static_select` with two option groups: "Available" and "Everyone
  else" (the rest of `eligible_leads()`, alphabetical, plus anyone already
  assigned who is outside the pool). Prefilled with current leads. No maximum.
  60 people is under Slack's 100-option cap.
- Saving replaces this practice's `role='lead'` rows only (coaches untouched),
  then calls `refresh_practice_posts(change_type='edit', notify=False)`, which
  re-renders the block post and any announcement already posted without posting
  "edited by" replies in their threads.

The admin edit page's lead picker and the full edit modal's lead field stay. All
three write `role='lead'` rows, and the full modal already keeps assignees who
are outside its own list.

## Leads side

Unchanged from July and PR #224: poll copy, letter emoji, ✅, reconcile, nudge
rules, auto-close. Changes:

- **Missing details.** `poll_rows()` already renders "TBD" and "Practice". Copy
  becomes "Location TBD".
- **Late sessions get a letter.** A practice created in, or moved into, an open
  poll's range gets the next letter, appended at the end, its reaction seeded,
  and the poll message rewritten. Existing letters never move.
- **Letters only count up.** The poll stores `next_position`. Deleting a practice
  cascades its mapping away but leaves its pill and reactions on the message, so
  reusing its letter would hand a new session someone else's answers. A new
  session always takes `next_position`, which `open_block_poll` sets to the
  number of sessions it mapped.
- **Both save paths.** The availability-poll surface in `refresh.py` adds
  `create` to `AVAILABILITY_POLL_CHANGE_TYPES` and, before rendering, looks up
  OPEN polls by date range (today it finds polls only through the mapping table,
  so an unmapped practice never matches) and appends a mapping at
  `next_position` when missing. The admin form and the Slack modal both reach it.
  It replaces `_uncovered_by_open_poll_warning()`, which only the admin path
  called. If no letter is left (22 cap), log an error; the session's leads are assigned by hand.
- **Moved out of range.** Rare, and left alone. A session rescheduled into
  another block keeps its letter and line in its original poll (the line shows
  the new date, and reactions still mean "I can lead this practice"). Block posts
  list practices by date range, so it moves to its new block's post. If the new
  block's poll opens later, it gets a letter there too, and the picker reads the
  newer poll.

## Poll statuses

| Status | Meaning | Nudge job | Close job | Block post | Assign "Available" line |
|---|---|---|---|---|---|
| `draft` | Block post up, poll not opened | skip | close past `ends_on` | before-opening state | "poll not opened yet" |
| `open` | Poll posted | reconcile, nudge, re-render | close past `ends_on` | open state | names |
| `closed` | Block over, or never posted | skip | done | closed state | names, or no line if never posted |

Reactions only ever match an `open` poll's message (unchanged).
`lead_candidates._poll_for_practice()` keeps reading `open` and `closed`.

## Removed

- `run_practice_block_bootstrap_job`, `run_practice_readiness_nudge_job`,
  `post_readiness_digest`, the readiness digest blocks, and the summary-post
  bookkeeping (`find_readiness_digest_post`, `stage_readiness_digest_post`, the
  `readiness_digest` surface value)
- shadow mode: `_shadow_mode()`, `shadow_roster_leads()`, the shadow branch of
  `_target_channel()`, the shadow branches of `sync_participants()` and
  `participants_to_nudge()`, the admin JS channel-confirm dialog, and the
  `lead_availability.shadow_mode` / `shadow_roster` / `shadow_channel_id`
  AppConfig rows. Polls always post to `COORD_CHANNEL_ID`. The `is_shadow`
  column stays, always false. A missing config row can no longer route a poll
  to a test channel.
- the readiness gate and draft-only filter in `build_poll()`, and its
  abandoned-DRAFT replacement
- poll date pickers and `POST /admin/availability/polls/create` as a date-range
  API
- `POST /admin/practices/publish`, `POST /admin/availability/polls/<id>/publish`,
  the drawer's Publish this practice button, poll card publish buttons
- `tests/js/draft_publish.test.js`'s "no week-level publish" assertions, replaced
  by "no publish control exists"; the `lead-availability` skill's invariant about
  automatic publish, rewritten to describe visible-when-ready

## Data changes

On `lead_availability_polls`:

- `block_post_ts` (nullable string; the channel is always `PRACTICES_CORE_CHANNEL_ID`)
- `opened_by_slack_uid` (nullable string)
- `wednesday_reminder_sent_at` (nullable timestamp)
- `next_position` (integer, default 0; no backfill, the table is empty in prod)

New AppConfig key `lead_availability.block_anchor` (ISO date, default
`2026-10-26`).

The `readiness_digest` value stays in the `practice_summary_posts` check
constraint and its three rows stay put: nothing writes them any more, and the
cleanup script reads them. The migration bumps `HEAD_REVISION` in
`tests/practices/test_practice_migration_release.py`.

## Error handling

- Every Slack call in the new code follows the existing never-raise pattern and
  logs at WARNING or above (Render shows only WARNING+).
- Block post fails to post: the poll row still exists, the admin card still
  offers Open poll, and the next run of the block job retries.
- Block post edit fails: logged; the next edit or the next morning's refresh
  repairs it.

## Testing

Follow `tests/practices/conftest.py` exactly (real dev DB, 2099 dates, `TEST `
prefixes, rollback-first cleanup). New coverage:

- `publish_if_ready` from each save path; one way; cancelled stays hidden;
  hand-created practices unaffected; late publish triggers the announcement
- block job: idempotent on state, a missed Monday caught Tuesday, retry of a
  failed block post, Wednesday reply after a missed Wednesday, anchor arithmetic
  across Nov 1 and Dec 31, existing drafts in range still produce a block post
- `open_block_poll`: a second open while locked or after opening is refused,
  failure leaves the poll `draft`, published and hidden sessions both mapped,
  letters in date order
- letters: append keeps positions; a deleted session's letter is never reused
- late publish: "passed" boundaries at 08:00 and 20:00, Thursday strength pair
  combined, standalone when its partner was already announced
- status table: every row above, including close of `draft` and a never-posted
  `closed` block's rendering
- block post render: dot rules, coaches shown not counted, cancelled struck
  through, `leads_needed` 1 and 3, footer days from `opened_at`
- Assign: replaces only lead rows, outside-pool assignees preserved, option groups
- Sunday summary: sweep, hidden copy, Open poll when DRAFT

## Rollout

Cut over at deploy. Shadow mode is deleted in the build, so there is nothing to
flip.

### Delivery phases

Each phase is its own PR, merged and deployed in order.

- **A. Visible when ready, and removals.** `publish_if_ready` on all three paths
  with the late-announcement rule, Sunday summary changes, removal of the
  bootstrap, readiness digest, publish surfaces and shadow mode. Stops the
  silent-hold failure on its own.
- **B. Block cycle.** Daily block job, poll statuses, `open_block_poll`, block
  post in all states, Wednesday reply, admin card and "Run block job now". Must be
  live before Mon Oct 19 09:00, or run by hand that day.
- **C. Assign and letters.** Assign modal, `next_position` append, the Oct 12-25
  assignment post. If C slips past
  Oct 12, skip cutover step 1 and Chris assigns Oct 12-25 in the admin picker,
  which still works.

The demo below covers all three phases before the first merge.

**Before merge: demo.** A demo script posts every surface to Rob's DM with the
TCSC bot, built from the real Block Kit builders with example data: block post
before and after opening, Wednesday reply, Assign modal (open and empty states,
rendered as messages since a modal needs a click to open), leads poll with a TBD
row and a late-added letter, nudge DM, Sunday summary changes. Admin screens
(practice list card, drawer) as screenshots. Rob gives feedback before merge.

**At deploy (prod one-offs, `TCSC_MIGRATION_ONLY=1`, `SLACK_APP_TOKEN` unset):**

1. **Oct 12 to 25 assignment post.** Chris already collected availability by hand
   for this block. Create its poll row as `closed` with no `message_ts` and post
   its block post: session rows with Assign buttons, no Open poll button, no
   Available line, no leads poll in #coord-practices-leads-assists.
2. **Clean up #collab-coaches-practices.** Read the three `readiness_digest`
   summary-post records (Aug 1, Sep 1, Oct 1 anchors) for the parent messages,
   list each parent and its thread replies (`conversations.replies`) for Rob, and
   after his OK delete them with `chat.delete` (the bot can delete its own
   messages). Do not scan the channel: coach weekly summaries are bot posts there
   too.
3. Delete stale drafts 111-115 (Sep 1, 3, 3, 10, 10).
4. **Heads-up to leads.** Before Oct 19, Chris (or Rob) posts one short note in
   #coord-practices-leads-assists: the poll now comes from the bot every other
   Monday, react with letters, ✅ when done (it means "done answering" here, not
   "confirm the schedule" as in Chris's posts), and reminders stop once you
   react. Drafted during the demo pass.
5. Mon Oct 19 09:00: the first regular block post (Oct 26 to Nov 8) goes out on
   its own.

**After launch:** explainer artifact for Chris, Ellie and Jacob, written against
the shipped build.
