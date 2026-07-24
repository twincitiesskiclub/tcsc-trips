# Generic Events System + Dry Tri 2026 — Design

**Date:** 2026-07-24
**Status:** Approved (brainstormed with Rob; feedback from Mitchell, Dry Tri admin)

## Problem

The 2025 Dry Tri used a static page (`/dryland-triathlon`) linking to two Google Forms
for registration and bit.ly links for payment. Registration and payment were
disconnected, and roster management lived in Google Sheets. Mitchell's 2026 asks:

1. Update date and times for 2026.
2. Add a run-only 6K option at $30 (long and short course stay same-priced).
3. Registration info and payment in one place.

Rob additionally wants full registration management in the admin interface via a
**generic Events system** that can host races, socials, and other events for members
and the public — with event registrations kept strictly separate from the member
registration tables (User/UserSeason).

## Decisions Made

- **Pricing:** Individual $55, Team of 3 $105, Run-only 6K $30. Long/short course
  same price. Run-only is individual-only.
- **2026 date/times:** placeholder — Sat Oct 24, 2026, with 2025 schedule times
  (7:30 packet pickup, 9:00/9:05 long course waves, 9:30 short course). The
  participant guide has not been updated for 2026; Mitchell confirms final
  date/times and they get edited in admin. Event ships as `draft`.
- **Member discount:** discount code field at checkout (code shared in Slack), which
  unlocks per-price-option member pricing. No auto-detection by email.
- **Teams:** one captain registers the whole team, enters all 3 participants'
  details, pays once ($105).
- **Socials fold in:** SocialEvent is migrated into the Events system and retired.
  Events carry an `audience` setting (`internal` / `external` / `both`).
- **Templates:** premade per-event-type question sets and price options
  (`config/event_templates.yaml`), seeded from the 2025 Google Forms.

## Architecture

New package `app/events/` (mirroring `app/practices/`):

```
app/events/
  __init__.py
  models.py        # Event, EventPriceOption, EventRegistration, EventParticipant
  templates.py     # load/validate config/event_templates.yaml, apply to new events
  service.py       # registration creation, capacity, pricing, stale-pending cleanup
app/routes/
  events.py        # public: event page, register endpoint
  admin_events.py  # admin: /admin/events CRUD, registrations grid data, CSV export
```

Payments reuse the existing `Payment` table, Stripe webhook, and refund endpoints.

## Data Model

All tables are new and have **no foreign keys to User/UserSeason**. Event
registrants never create or touch member rows (consistent with the stub-user
prevention design: only season payments create Users).

### Event (`events`)

| Field | Type | Notes |
|---|---|---|
| id, slug (unique), name | | slug e.g. `dry-tri-2026` |
| description | Text | supports schedule details, markdown-ish paragraphs |
| location | String | |
| event_date | DateTime | primary start; naive US Central like SocialEvent |
| signup_start, signup_end | DateTime | registration window |
| capacity | Integer, nullable | null = unlimited; counts registrations |
| status | String | `draft` / `active` / `closed` |
| audience | String | `internal` / `external` / `both` — external/both listed on homepage; internal reachable by direct link only |
| details_url | String, nullable | participant guide link |
| discount_code | String, nullable | case-insensitive match at checkout |
| custom_questions | JSON | list, see below |
| template_key | String, nullable | template the event was created from (informational) |
| created_at, updated_at | | |

### EventPriceOption (`event_price_options`)

| Field | Type | Notes |
|---|---|---|
| id, event_id (FK) | | |
| name | String | "Individual", "Team of 3", "Run-only 6K" |
| description | String, nullable | shown under the option |
| price_cents | Integer | |
| member_price_cents | Integer, nullable | applied when a valid discount code is entered; null = code gives no discount on this option |
| participant_roles | JSON | e.g. `["Participant"]` or `["Rollerskier", "Mountain Biker", "Trail Runner"]`; length drives how many participant blocks the form renders |
| sort_order | Integer | |
| active | Boolean | inactive options hidden from the public form |

### EventRegistration (`event_registrations`)

| Field | Type | Notes |
|---|---|---|
| id, event_id (FK), price_option_id (FK) | | |
| contact_email, contact_phone | String | registrant/captain |
| team_name | String, nullable | required by form when option has >1 role |
| emergency_contact_name, emergency_contact_phone | String | one per registration (matches 2025 team form) |
| answers | JSON | `{question_key: answer}` for the event's custom questions |
| amount_cents | Integer | actual price charged (after discount) |
| discount_applied | Boolean | |
| status | String | `pending_payment` / `confirmed` / `cancelled` / `refunded` |
| payment_intent_id | String, nullable | set at intent creation; webhook correlates |
| created_at, updated_at | | |

### EventParticipant (`event_participants`)

| Field | Type | Notes |
|---|---|---|
| id, registration_id (FK) | | |
| position | Integer | 1-based, matches `participant_roles` order |
| role_label | String | copied from price option at registration time |
| name | String | first and last |
| date_of_birth | Date | |
| email, phone | String | |

### Payment changes

- New nullable `event_registration_id` FK on `payments`.
- New `payment_type` value `event` (added to `PaymentType` constants).
- `social_event_id` column and `social_event` payment type removed after migration.

### Custom questions JSON shape

```json
[
  {
    "key": "course",
    "label": "Which race will you participate in?",
    "help_text": null,
    "type": "choice",            // "choice" | "text"
    "options": ["Long course (18K roll, 17K ride, 11K run)",
                 "Short course (9K roll, 9K ride, 6K run)"],
    "required": true
  }
]
```

Registration-level only (no per-participant questions). Answers are
display-and-export data; nothing branches on them server-side.

## Event Templates

`config/event_templates.yaml` — follows the existing `config/*.yaml` pattern.
Creating an event from a template **copies** price options and questions into the
event; edits after creation never touch the template.

Templates shipped:

- **`dry_tri`** — price options: Individual $55 (roles: Participant), Team of 3
  $105 (roles: Rollerskier / Mountain Biker / Trail Runner, help text "If the same
  participant will complete this leg, enter their information again"), Run-only 6K
  $30 (roles: Participant). Questions (from the 2025 forms): competition gender
  (choice: Men / Women / Mixed non-binary), club(s) or team(s) represented (text,
  optional), city/state (text), course selection (choice: long / short), preferred
  wave (choice: Wave 1 / Wave 2 / Wave 3, optional).
- **`social`** — one price option ("Registration"), no custom questions.
- **`blank`** — no options, no questions.

Year-over-year reuse also supported by a **Duplicate** admin action (copies an
existing event with a new slug/dates, no registrations).

## Registration + Payment Flow

1. **GET `/events/<slug>`** — public page: event info, schedule, guide link, and
   the registration form. Form sections: price option picker → N participant
   blocks (per `participant_roles`) → contact + team name + emergency contact →
   custom questions → optional discount code → Stripe card element. Page follows
   current public styling (Tailwind migration skill applies).
2. **POST `/events/<slug>/register`** — server-side validation: event `active`,
   within signup window, capacity available, price option active, required fields
   and questions present, participant count matches roles, discount code checked
   case-insensitively. Server computes price (never trusts client), creates
   `EventRegistration` (`pending_payment`) + `EventParticipant` rows, then creates
   a Stripe PaymentIntent: `capture_method='automatic'`, `receipt_email`,
   statement descriptor `TCSC_EVENT_*`, metadata
   `{payment_type: 'event', event_id, registration_id, email, name}`. Returns
   `clientSecret`.
3. Client confirms payment via Stripe Elements (same pattern as
   `social_event.js`).
4. **Webhook** `payment_intent.succeeded` — creates the Payment row with
   `event_registration_id`, flips registration to `confirmed`, sends the existing
   Slack payment notification. Idempotent, like current handlers. **No User row is
   created or looked up for event payments.**
5. Payment failure/cancel: registration stays `pending_payment` and ages out.

**Capacity:** available = capacity − (confirmed + pending_payment younger than
1 hour). Stale pending registrations don't hold spots; a cleanup in `service.py`
marks pending registrations older than 24h as `cancelled` (run opportunistically
on event page load — no new scheduler job needed).

**Confirmation:** Stripe email receipt only. The app sends no emails itself
(SMS notifications can hook in later via the SMS transition project).

## Admin UI

New **Events** tab at `/admin/events` (Tabulator pattern, `admin_events.js`):

- **Events grid** — name, date, audience, status, confirmed/capacity, revenue.
  Actions: New Event (template picker → pre-filled editor), Edit, Duplicate,
  activate/close, Delete (draft-only).
- **Event editor** — core fields plus inline row editors for price options
  (name, price, member price, roles) and custom questions (label, type, options,
  required, help text).
- **Registrations view** (per event) — grid of registrations with participant
  columns and one column per custom question key; filter/sort; **CSV export**
  (race-day roster, replaces the Google Sheet); per-price-option counts;
  Cancel/Refund action wired to the existing refund endpoint — a refund flips the
  registration to `refunded`.
- Existing **Payments tab** shows `payment_type='event'` rows automatically.
- **Social Events tab removed** (replaced by Events).

Admin API endpoints mirror existing conventions:
`GET /admin/events/data`, `POST /admin/events/create`, `POST /admin/events/<id>/edit`,
`POST /admin/events/<id>/duplicate`, `POST /admin/events/<id>/delete`,
`GET /admin/events/<id>/registrations/data`, `GET /admin/events/<id>/registrations/export.csv`,
`POST /admin/events/registrations/<id>/cancel`.

## Public Pages & Routing

- Homepage lists `active` events with audience `external`/`both` (replacing the
  social-event listing); a badge distinguishes event types if useful.
- `/events/<slug>` — unified info + registration page.
- `/dryland-triathlon` → 302 to `/events/dry-tri-2026`.
- `/social/<slug>` → 302 to `/events/<slug>` (slugs preserved by migration).

## Socials Migration

One Alembic migration (schema) + data migration:

1. Create the four event tables; add `payments.event_registration_id`.
2. For each `SocialEvent`: create an `Event` (template_key `social`, audience
   `internal`, same slug/name/date/price/status mapping) with one price option.
3. For each Payment with `social_event_id`: create a backfilled `confirmed`
   `EventRegistration` (contact from payment name/email, one participant row from
   the payment name), link `payment.event_registration_id`, set
   `payment_type='event'`.
4. Drop `payments.social_event_id`, drop `social_events`; remove the SocialEvent
   model, `socials.py` routes (replaced by redirect), templates, and admin tab.

Statuses map: SocialEvent `draft`→`draft`, active/open→`active`, past→`closed`.

## Dry Tri 2026 Seed

Created from the `dry_tri` template as **draft** (activated manually after
Mitchell confirms):

- Slug `dry-tri-2026`, Sat **Oct 24, 2026** (placeholder — guide still shows 2025),
  Carver Park Reserve (Parley Lake), schedule text with 2025 times as placeholders,
  participant guide `details_url`, audience `both`.
- Price options $55 / $105 / $30; `member_price_cents` left null and discount code
  unset until Rob/Mitchell decide the member discount amount (editable in admin).

## Error Handling

- Registration POST returns field-level validation errors as JSON (same
  `json_error` convention as payments routes).
- Sold out / window closed / draft event: the public page renders an informative
  state instead of the form; POST re-validates and rejects.
- Webhook receiving an intent whose registration is missing logs and still records
  the Payment (mirrors current defensive handling).
- Stripe failures at intent creation surface as a friendly error; registration
  stays `pending_payment` and ages out.

## Testing

pytest with PostgreSQL fixtures, `tests/events/`:

- Model + template loading/validation (`event_templates.yaml` parse, copy-on-create).
- Registration service: pricing (with/without discount code), participant count
  enforcement, capacity math including stale-pending aging.
- Flow: register endpoint → intent metadata → webhook confirm; idempotent webhook.
- No-User invariant: event registration/webhook never creates a User row.
- Socials migration: row counts, payment links, status mapping (tested against a
  seeded pre-migration fixture).
- Redirects: `/dryland-triathlon`, `/social/<slug>`.
- Admin: events/registrations data endpoints, CSV export contents.

## Out of Scope

- Auto member detection by email; per-participant custom questions; waitlists;
  lottery/manual capture for events; SMS/email confirmations beyond the Stripe
  receipt; results/timing; Team Finder (stays a linked spreadsheet); folding
  Trips into Events.

## Implementation Notes

- Implementation will use Codex (sol, max effort) subagents for build tasks with
  Fable as planner/judge/reviewer, per Rob.
- Follow-ups for Rob/Mitchell: final 2026 date + start times (incl. run-only 6K
  start), member discount amount + code word, whether run-only finishers get swag
  (affects nothing in code).
