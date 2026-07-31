# Trip Registration Redesign — Design

**Date:** 2026-07-31
**Status:** Approved pending final review

## Context & Problem

Trip signup today is two disconnected systems: a Slack Workflow Builder form
(answers land in a Slack List) and a payment page on tcsc.ski (a `Payment` row
with `trip_id` — there is no trip registration model at all). Admins reconcile
the two by hand. Ranked pains:

1. **Reconciliation** — matching Slack List rows to Stripe holds by name/email.
2. **Payment completion** — people fill the form and never pay (or vice versa).
3. **Logistics** — carpool/tent/food data is trapped in a Slack List, hard to
   use for actual trip planning.

The events system (July 2026) already solved the same shape natively:
`Event` + `custom_questions` JSON, `EventRegistration` + `answers` JSON,
admin question-builder UI, template library. Trips adopt that pattern.

## Goals

- One flow, one record: form answers + member + payment hold created
  atomically. An unpaid registration cannot exist, so reconciliation
  disappears structurally.
- Structured logistics data that admins can filter, sort, and export.
- Mitchell can edit each trip's questions in a visual builder; every
  historical trip's questions ship pre-seeded as templates.
- Trips recur yearly without destroying history (series/editions).
- Slack becomes discovery + lifecycle (unfurls, announcement post,
  auto-invite, DMs), not data entry.
- **The member-facing form and the admin builder must be genuinely pleasant
  to use** — mobile-first, grouped, fast. UX quality is a requirement of this
  build, not a polish pass.

## Non-Goals (explicitly deferred)

- **Member auth** (phone OTP primary, email code, Google) — separate follow-up
  project. Until then trips use the season-registration pattern: enter an
  email, server verifies it belongs to a current-season ACTIVE member.
- **Pre-filling answers** from stored profile data — deferred to the auth
  project (pre-filling on a bare email check would leak member info). Profile
  data is write-only for now.
- **Waitlist** — v1 closes a tier when it fills. Revisit after we see how
  often trips fill.
- **Trip leads/roles on the Trip object** and announcement-post live-refresh.
- **Carpool auto-suggestion** — v1 delivers the structured data; smart
  matching comes later.
- **Payment flow changes** — manual capture holds stay exactly as they are
  (understood by everyone on the trip). Note for the future: Stripe manual
  holds expire after 7 days, so roster confirmation must continue to happen
  within 7 days of each signup. Revisit (saved-card, charge-on-confirm) later.

## Decisions Log

| Decision | Choice |
|---|---|
| Form location | Web (tcsc.ski), Slack is the front door |
| Identity for v1 | Email gate against registered ACTIVE members (season-reg pattern) |
| Pre-fill | None until auth project |
| Payments | Unchanged: manual capture, admin captures on roster confirm |
| Capacity | Count PENDING+CONFIRMED per tier, close tier when full |
| Recurrence | TripSeries (permanent) + Trip editions (yearly) |
| Slack announcement | Link unfurling (primary) + admin "post announcement" button (comparison) |
| Slack lifecycle in scope | Auto-invite to trip channel on confirm; bot DM on registration + confirmation |

## Data Model

### TripSeries (new)

The permanent identity of a recurring trip.

- `slug` (unique, e.g. `birkie`) — the public URL never changes
- `name`, `destination`
- `slack_channel_name` — lives on the series; the channel persists year over year
- bespoke page content association (existing `trips/{slug}.html` templates map
  to series)

### Trip (becomes the yearly edition)

Existing table, re-parented: `series_id` FK, plus new `custom_questions`
(JSON, same schema events uses). Keeps dates, signup window, `price_low` /
`price_high`, `max_participants_standard` / `max_participants_extra`, status.

`tcsc.ski/<slug>` resolves series → current/upcoming edition. Past editions
stay browsable in admin with full rosters.

**Migration:** each existing trip becomes a series holding its current data as
the first edition. Existing payments keep their `trip_id` untouched.

### TripRegistration (new — mirrors EventRegistration)

- `trip_id` (edition), `user_id`, unique together — one registration per
  member per trip; a second visit says "you're already signed up"
- `status`: `PENDING` (hold placed) → `CONFIRMED` (captured) | `CANCELLED`
- `answers` JSON, `price_tier`, `amount_cents`, `payment_intent_id`
- Created only when the Stripe hold succeeds — no hold, no row.

### TripProfile (new — one row per user, real columns)

Semi-stable facts, stored structured because logistics queries need them:
`can_drive`, `seat_capacity`, `bike_capacity`, `hitch_size`, `region_code`,
`dietary_restrictions` (JSON list + other-text), `has_tent`. Updated on every
registration submit. Per-trip answers (departure time, bed/room sharing,
chores, activities, vibe, event choice, borrow requests) stay in `answers`.

## Member Flow

1. Trip page (from a Slack unfurl/announcement or anywhere) → `/trips/<slug>/register`.
2. Email gate: server verifies current-season ACTIVE member
   (`api_is_returning_member` pattern). Friendly failure with a pointer to
   season registration.
3. Form reveals in topic groups — *Getting there*, *Sleeping*, *Food*,
   *Activities/Extras* — one continuous mobile-first Tailwind page with
   visible progress, not a wizard.
4. Price tier + Stripe payment element on the same page. One submit:
   validate → upsert TripProfile → create TripRegistration + manual-capture
   hold atomically. Failed card ⇒ nothing persists.
5. Confirmation page; bot DM (persistent, not ephemeral) with trip details
   and their answers.

## Question Builder

Reuses the events builder pattern (row editor, server-side validation via the
events `validate_question` approach) with additions:

- Types: short text, single select, multi-select **with "pick up to N" cap**
  (departure times), yes/no.
- **Conditional visibility:** a question may declare "show only when yes/no
  question X = Yes" — covers the driver follow-ups (seats, bikes, hitch).
  Deliberately limited to yes/no parents; no logic trees.
- Required/optional flags, helper text (e.g. the region-map link).

### Templates & Seeds

Trip templates work like `events/templates.py`. Seeded from the six provided
historical forms: Cuyuna (camping), GBC, Pre-Birkie, Sisu, Birkie, Hayward.
The five race-weekend forms share a common base (departure times, driving,
region, dietary, chore preference, bed/room sharing) plus per-trip extras
(event/distance choice, cabin vibe). Mitchell starts every trip from done.

**Seed-data gap:** the full option lists for departure-time questions (and any
options not visible in the provided screenshots) must be pulled from the
existing Slack workflows during implementation.

## Admin Experience

- **Editions:** series page → "New edition" clones last year's questions,
  prices, capacities; update dates; publish.
- **Question editor:** visual builder as above, on the edition.
- **Roster:** registration rows — member, dynamic answer columns (events
  pattern), payment status, capture/cancel per person and in bulk. This is
  where roster confirmation (capture) happens, within the 7-day hold window
  as today.
- **Logistics:** filter/sort roster by any answer or profile column (drivers
  with seats, region groups, dietary rollup); CSV export.
- **"Post announcement to Slack" button** on the edition — bot posts a
  generated Block Kit card (dates, prices, window, Sign up button) to the
  trip channel or a chosen channel.

## Slack Integration (this build)

- **Link unfurling (primary):** app registered for tcsc.ski unfurls — any
  pasted trip link anywhere in the workspace renders a rich card with a
  Sign up button.
- **Announcement button** (above) — kept alongside unfurling to compare which
  works better in practice.
- **Auto-invite:** on registration confirmation (capture), bot invites the
  member to the series' Slack channel — channel membership ≙ roster.
- **DMs:** bot DM on registration (receipt + answers) and on confirmation.
- Existing Workflow Builder form and Slack List retire once this ships.

## Error Handling

- Unknown/inactive email → clear message + season-registration pointer.
- Window closed / not open yet → existing trip-page messaging.
- Capacity: tier closes at cap (PENDING+CONFIRMED count); full trip shows
  "trip full" message.
- Stripe webhooks drive status transitions (capture → CONFIRMED,
  cancel/refund → CANCELLED), mirroring events.
- Slack failures (invite/DM/unfurl) log and never block registration.

## Testing

pytest, mirroring the events suites: email gate, window + capacity
enforcement, question validation (types, caps, conditionals), atomic
registration+hold creation, webhook transitions, template seeding,
series/edition resolution, migration correctness. Heed the known dev-DB
mutation leaks in `tests/events/` — don't add new ones.

## Sequencing After This Build

1. **Auth project:** phone OTP (primary), email code, Google; verified-phone
   capture club-wide; pre-fill turns on; member portal begins.
2. Waitlist, carpool auto-suggestion, trip leads/roles, live-refreshing
   announcement posts, saved-card payment revisit.
