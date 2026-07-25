# Lead Availability & Scheduling — Design

**Date:** 2026-07-25
**Status:** Approved design, pending implementation plan
**Channel of record:** `#coord-practices-leads-assists` (`C02J4DGCFL2`)

## Problem

Practice leads are scheduled by hand, and have been for five years. The current cycle repeats
every 2–6 weeks and has run roughly thirty times:

1. A practices director posts "fill out your availability by \<date\>" with `@channel`
2. One to four reminder messages follow, usually @-mentioning 10–17 laggards individually
3. The director hand-builds a schedule in a Google Sheet
4. The schedule is posted **as a screenshot**, plus another mass @-mention
5. Substitutions get negotiated ad hoc in-thread

Nine different availability spreadsheets have been used since December 2022. In June 2026 the
directors moved availability collection to emoji reactions on a Slack post, which members
preferred ("quicker and convenient").

### Costs evidenced in the channel history

| Cost | Evidence |
|---|---|
| Chasing availability | The dominant labor. Dozens of nags; "not to sound like a broken record" |
| Spreadsheet access friction | "requesting editing rights", "access denied", "the list stopped at S" — recurs every season |
| Stale or misread availability | "I updated the spreadsheet to unavailable… is anyone willing to lead?"; "there's some error reading from the spreadsheet"; "6/26 doesn't pull the right data" |
| Schedule is an image | Not queryable. Jan 2025: *"the automation that does the practice posts does not indicate who is leading Friday strength"* |
| No load balancing | The stated goal is to "spread out the load", but nobody tracks who has led how often |
| Bus factor | One director carried this nearly alone for two years, repeatedly apologizing for delays while travelling |

### What is already working, and must not be automated away

Substitutions. Forty-plus sub requests appear in the log and nearly all resolve within minutes
by a volunteer replying "I can!". This is the healthy, social part of the channel and is
explicitly **out of scope**.

## Goals

- Eliminate manual availability chasing and manual transcription into a spreadsheet
- Give directors availability and load data *inside the tool where they already assign leads*
- Keep lead selection a human judgment call
- Give leads a lower-friction experience than today, not merely a different one

## Non-goals

- Automated substitution handling
- Lead capability profiles (roller-ski capable, classic vs skate, pace group, location reach)
- Automatic or algorithmic assignment of leads
- Coach scheduling — coaches remain directly assigned by directors

## Design overview

```
MONTHLY (1st, 08:00 Central)      job: practice_block_bootstrap
  └─ Draft the next 4 weeks of practices from practice_days config
     (is_draft=True — invisible to members, no announcements fire)
  └─ Post a digest to #coord-coaches-practices with a readiness count,
     each row reusing the existing edit_practice_full modal

COACHES + DIRECTORS fill in location, type, time
  └─ Bot re-nudges after 3 days while any draft is incomplete
  └─ "Send availability poll" stays disabled until every draft is ready
     │
     └─ Director triggers the poll  ← human gate, deliberately not a timer

POLL OPENS                        → #coord-practices-leads-assists
  └─ One post per block, one lettered emoji per session (🇦 … 🇱)
  └─ Leads react to every session they can lead; react again to undo
  └─ ✅ means "that's everything from me"
  └─ Bot maintains a threaded reply with coverage

DAILY (08:00 Central)             job: lead_availability_nudge
  └─ DM only people who have neither reacted nor hit ✅
  └─ First nudge at day 3, max 3 sends, 2 days apart

SUNDAY                            → existing practice create/edit form
  └─ Lead picker shows availability, response state, and load counts
  └─ Director assigns 1–3 leads
  └─ Publish → is_draft=False → refresh_practice_posts() unchanged
```

The poll is **director-triggered rather than scheduled**, because practice details are genuinely
not ready on a fixed date — the head coach's own words: *"August is 90% set but if anything
changes I will alert this thread."* A timer would fire polls against stale locations, which is
the failure members already complain about.

## Why emoji reactions rather than buttons

Buttons were designed and rejected. A Slack channel message is a single object rendered
identically for all 64 members, so a button cannot show *your* state — it reads "I can lead"
whether or not you already signed up, and it cannot say "Withdraw" for just you.

Reactions solve this natively: your own reaction is highlighted for you, and undo is tapping it
again. Additional consequences:

- **No message re-rendering.** Slack maintains reaction counts itself, so the bot never calls
  `chat.update` on the poll post. This removes the `chat.update` concurrency hazard entirely —
  that method has no compare-and-swap, no `hash` or ETag, and silently last-writes-wins — along
  with the Tier 3 rate-limit debouncing a button design would have required.
- **Zero new interaction to learn**, and denser than twelve button rows.
- **Proven in this codebase.** `reaction_added` and `reaction_removed` handlers already exist at
  `app/slack/bolt_app.py:1175` and `:1180` for practice RSVPs.

Accepted costs: the reaction pill row renders at the bottom of the message rather than beside
each line, so mapping 🇩 back to its session costs a glance at the legend; per-row coverage hints
must live in a threaded reply; and stray reactions are noise the bot ignores.

### Evidence behind the post's content

- **Names stay visible.** Zou, Meir & Parkes (CSCW 2015), 345,297 open vs 7,390 hidden Doodle
  polls: mean availability 0.53 open vs 0.39 hidden. Slack shows reactors on hover natively.
- **Empty sessions are surfaced, not hidden.** The same study found open polls produced
  *significantly higher* uptake on the least popular slots (p < 10⁻⁵). Empty slots attract
  volunteers.
- **Half-covered sessions get their own nudge.** That study also found middling slots are the
  ones neglected, while empty and full both do fine.
- **No response-rate counter.** Descriptive-norm messaging that advertises low participation
  produces documented boomerang effects. The threaded reply states a need
  ("3 sessions still have nobody"), never a participation statistic ("9 of 24 responded").
- **✅ exists because pure opt-in is ambiguous.** Check-all-that-apply research (Smyth et al.
  2006, replicated by Pew 2019) shows people mark the obvious few and stop scanning;
  forced-choice yields ~8pp more endorsement. Twelve forced marks is the spreadsheet that
  already failed. One ✅ buys three distinguishable states — never responded / responded-none /
  responded-with-picks — which is what makes targeted nudging possible at all.
- **Nudge cadence.** Number of contacts is the strongest lever on response, but 1–2 reminders
  capture most of the lift and 3–4 is the ceiling; first reminder at day 3–5. Personalising
  reminder *content* has near-zero effect; targeting the *audience* is the entire win.

## Schema

### Changes to `Practice`

| Column | Type | Rationale |
|---|---|---|
| `is_draft` | `Boolean, not null, default False` | Backfills `False`, so every existing row and code path is unchanged. Drafts must be explicitly excluded from announcement, weekly-summary, and Skipper paths — an auditable set of guard additions, rather than overloading `status`, which cancellation logic already reads. |
| `leads_needed` | `Integer, not null, default 2` | Validated 1–3. Drives coverage reporting and the picker's "needs 2, has 0" state. |

`PracticeStatus` is **not** extended — no `DRAFT` member is added.

### New tables

```
lead_availability_polls
  id, starts_on, ends_on, is_shadow,
  status (draft | open | closed),
  channel_id, message_ts, coverage_thread_ts,
  created_at, opened_at, closed_at

lead_availability_poll_practices        -- deterministic emoji ↔ practice mapping
  poll_id, practice_id, emoji, position
  UNIQUE(poll_id, emoji), UNIQUE(poll_id, practice_id)

lead_availability_participants          -- drives nudging and completion tracking
  poll_id, user_id,
  status (pending | responded | done | opted_out),
  last_nudged_at, nudge_count
  UNIQUE(poll_id, user_id)

lead_availability_responses             -- a row means "available"; undo deletes it
  poll_id, practice_id, user_id, responded_at,
  source (reaction | admin),
  answered_for_date, answered_for_location_id   -- staleness snapshot
  UNIQUE(poll_id, practice_id, user_id)
```

`lead_availability_poll_practices` carries the emoji because inbound reaction events identify
only an emoji name; the mapping must be persisted to resolve a reaction to a practice, and must
survive the practice list changing.

`lead_availability_responses` needs no `available` boolean — presence *is* availability, and
`reaction_removed` deletes the row.

### Eligible pool

Computed live from the `PRACTICES_LEAD`, `PRACTICES_DIRECTOR`, `HEAD_COACH`, and
`ASSISTANT_COACH` tags, with participant rows created lazily. This fixes a failure that recurs
every season — new leads joining mid-block and finding themselves missing from the sheet, or the
alphabetical roster "stopping at S".

### Assists

`PracticeLead.role` continues to accept `'assist'` so historical rows remain readable, but the
role is removed from the create/edit UI and from all new writes. Practices take 1–3 leads,
default 2.

## Slack surfaces

### Availability poll

One post per block in `#coord-practices-leads-assists`, listing each session as
`<emoji> <day date> · <time> · <location> · <type>`, grouped under week headings, with the emoji
in a hard-left column so it reads as an index against the reaction row.

Emoji are assigned deterministically by chronological position. **Regional indicators
(🇦–🇱) are the intended set, but the exact Slack shortcodes and cross-client rendering must be
verified before implementation proceeds** — adjacent regional indicators can combine into flags
in some contexts. A documented fallback set is required if verification fails.

`✅` is reserved for "that's everything from me" and is never a session.

### Coverage reply

A threaded reply the bot maintains, listing sessions with nobody, sessions below
`leads_needed`, and sessions covered. Updated on a debounce (~30s). This is the only Slack
message the bot rewrites.

### Nudge DM

Sent only to participants whose status is `pending`. First at day 3, maximum 3 sends, spaced 2
days apart. Contains a link to the poll message and a "sitting this block out" affordance that
sets `opted_out` and ends nudging for that block.

### Reconciliation

Reaction events can be missed during a deploy or outage. On poll close, and before each nudge
run, the bot calls `reactions.get` on the poll message and reconciles stored responses against
actual reactions. Requires the `reactions:read` scope — **verify it is granted before
implementation**.

Reactions from users outside the eligible pool are recorded and flagged rather than discarded, so
a willing non-tagged member is visible to the director rather than silently dropped.

## Admin picker

New endpoint `GET /admin/practices/<id>/lead-candidates` feeding the existing dropdown in the
practice create/edit form:

```
Leads (needs 2)
  ▸ micah      available · led 0 this block · 2 in 90d
  ▸ Katrin     available · led 1 this block · 4 in 90d
  ─────────────────────────────────────────
    Augie      no response
    Chris      unavailable
```

Available and least-loaded first. Unavailable people remain selectable but sort last and are
labelled — the system informs the choice, it never blocks it.

Load counts are computed from `PracticeLead` rows with `role='lead'`: `led_in_block` within the
poll window, and `led_last_90d` on a trailing window. No coupling to `Season`.

A response is **stale** when the practice's date/time or location no longer matches the
`answered_for_date` / `answered_for_location_id` snapshot taken when the response was recorded.
Stale responses still appear in the picker but carry a warning, since somebody who volunteered
for a Wirth trail run did not necessarily volunteer for the Hyland rollerski it became.

Staleness is deliberately **not** derived from `Practice.updated_at`. That column has `onupdate`
and fires on any edit — a workout description tweak would mark every response stale and train
directors to ignore the warning. Only date/time and location change whether someone can lead;
the snapshot captures exactly those.

This addresses the failure behind "I updated the spreadsheet to unavailable… is anyone willing to
lead?" and "6/26 doesn't pull the right data".

## Background jobs

| Job | Schedule | Purpose |
|---|---|---|
| `practice_block_bootstrap` | Monthly, 1st, 08:00 | Draft the next 4 weeks; post readiness digest |
| `practice_block_readiness_nudge` | Daily, 09:00 | Remind directors while drafts are incomplete |
| `lead_availability_nudge` | Daily, 08:00 | DM non-responders; reconcile reactions first |

All Central, registered in `app/scheduler.py` under the existing single-worker file lock.

## Rollout

### Phase 0 — UI preview (before any pipeline is built)

Real renders of every bot-authored message are posted to `#collab-asset-mgmt-practices`
(`C0B3Y71PG92`) and reviewed on both desktop and mobile before implementation proceeds. Surfaces
to preview:

1. The availability poll, with all twelve session rows and the emoji pre-seeded as reactions
2. The coverage thread reply, in all three states — nothing covered, partially covered, fully
   covered
3. The nudge DM
4. The monthly readiness digest to coaches and directors

This is a throwaway script posting static Block Kit, not the real feature. Its purpose is to
settle layout questions while they are still cheap to change, and it is the **only** way to
resolve the regional-indicator risk: whether 🇦–🇱 render as intended as reactions, in order,
without adjacent pairs combining into flags, across the clients members actually use.

Exit condition: the directors are satisfied with the layout, and the emoji set is confirmed or a
fallback chosen.

### Phase 1 — Shadow mode

The first month runs shadowed, configured through `AppConfig` so exiting needs no deploy:

```
lead_availability.shadow_mode         → true
lead_availability.shadow_channel_id   → C0B3Y71PG92   (#collab-asset-mgmt-practices, 5 members)
lead_availability.shadow_roster       → [practice director slack IDs]
```

When enabled, exactly three things change: the poll posts to the shadow channel; the participant
pool is the shadow roster rather than the live tag pool; nudge DMs reach only that roster.
Assignment, publishing, and announcements are untouched code paths.

**Member-facing surfaces are shadowed. Director-facing surfaces run live from day one** — the
monthly bootstrap and the readiness digest to `#coord-coaches-practices`. Directors adapting to a
new monthly cadence of setting locations, types, and times is a behavior change, not a code path,
and cannot be rehearsed in a shadow channel. Running it live is safe because drafts are invisible
to members until published.

The existing manual process continues in parallel throughout the shadow month, so there is no
cutover risk.

### Exit criteria

1. One full 4-week block bootstrapped with every practice having location, type, and time set
   before the poll opened
2. A poll completed end-to-end in the shadow channel, with directors reacting and reconciliation
   verified against `reactions.get`
3. At least one week's leads assigned from the picker rather than the spreadsheet
4. The nudge job demonstrated stopping correctly on both response and opt-out

## Testing

Shadow mode and automated tests catch different failures. Slack surfaces are best validated by
shadow mode. The following are pure logic over fixtures, are cheap, and cover hazards shadow mode
will not surface:

- **Bootstrap idempotency** — the monthly job re-running (redeploy, manual trigger, scheduler
  lock hiccup) must not create a second set of practices for dates already drafted
- **Nudge eligibility** — an off-by-one in "last nudged 2 days ago" would DM everyone every
  morning; in shadow mode that is 5 tolerant people, in production it is how the bot gets muted
- **Emoji ↔ practice resolution**, including reactions to unmapped emoji and to a practice
  removed after the poll opened
- **Reconciliation** against a `reactions.get` payload that disagrees with stored state
- **Candidate ranking** — availability, response state, and load ordering

This matches the existing split, where `tests/slack/` covers block builders and the refresh
dispatcher but not live posting.

## Open risks

| Risk | Mitigation |
|---|---|
| Regional-indicator shortcodes may not render as intended across clients | Resolved in Phase 0 by posting a real message; fallback set chosen there if needed |
| `reactions:read` scope may not be granted | Verify before implementation; reconciliation depends on it |
| Practice list changes after a poll opens | Emoji mapping is persisted; affected responses marked stale |
| A practice is deleted mid-poll | `lead_availability_poll_practices` and responses cascade; its emoji is retired, not reassigned |

## References

- `app/practices/models.py` — `Practice`, `PracticeLead`
- `app/routes/admin_practices.py:318` — `create_practice`, already accepts `lead_ids`
- `app/slack/bolt_app.py:1175`, `:1180` — existing reaction handlers
- `app/slack/practices/_config.py` — channel constants. Note `COLLAB_CHANNEL_ID`'s comment is
  stale: `C04AUHEDBSR` is now named `coord-coaches-practices`.
- Zou, Meir & Parkes, *Strategic Voting Behavior in Doodle Polls*, CSCW 2015
- Smyth, Dillman, Christian & Stern, *Comparing Check-All and Forced-Choice Question Formats*,
  Public Opinion Quarterly 2006
