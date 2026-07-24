# Events System + Dry Tri 2026 — Deploy Handoff (2026-07-25, overnight)

## What shipped

Generic Events system per `docs/superpowers/specs/2026-07-24-generic-events-system-design.md`, built overnight via subagent-driven development (Codex gpt-5.6-sol workers, per-task + final reviews). Branch `events-system` → main. Full suite: **1270 passed** (baseline 1196).

- `app/events/` — Event / EventPriceOption / EventRegistration / EventParticipant models, template loader (`config/event_templates.yaml`: dry_tri, social, blank), registration service (server-side pricing, discount codes, capacity with stale-pending aging), Dry Tri seed builder.
- Public: `/events/<slug>` one-page register + pay (Stripe automatic capture). Draft events: 404 public, admin-session preview with DRAFT banner. `/tri` and `/dryland-triathlon` → 302 `/events/dry-tri-2026`. `/social/<slug>` → 302 `/events/<slug>`.
- Webhook: `payment_type='event'` path — idempotent, never touches User rows.
- Admin: `/admin/events` — CRUD from templates, duplicate, status, price option + custom question editors, registrations roster with CSV export (formula-injection sanitized), cancel/refund (shared Stripe refund helper).
- Social Events folded in: data migration converted social_events + payments → events/registrations, dropped old table/column, removed all SocialEvent code. Migrated socials have `audience='internal'` (not homepage-listed; direct links redirect).
- Migrations chain: `b433791f5783` (tables) → `c8f4a2d6e901` (fold + drops) → `d4e7f9a1b2c3` (idempotent Dry Tri seed).

## Dry Tri 2026 (seeded as DRAFT — not public until activated)

$55 Individual / $105 Team of 3 / $30 Run-only 6K (individual-only). Long/short same price. Questions: competition gender, club, city/state, course, wave — from the 2025 forms. **Placeholders needing Mitchell:** date Sat Oct 24 2026 + schedule times (2025 times shown, marked "to be confirmed"), run-only start time, member discount (set `discount_code` on the event + member prices per option in admin). Activate via admin Events tab → status → active.

## Follow-ups (from reviews; none blocking)

- Webhook: guard event path so replayed success can't flip a refunded registration back to confirmed / re-send Slack notification (transition only from pending_payment).
- Payments-tab refund of an event payment doesn't flip the linked registration to refunded (roster Cancel/Refund does) — wire or document.
- Reuse `_sanitize_csv_value` for the pre-existing season-members CSV export (same injection gap, predates this branch); add `\t`/`\r` to the prefix set.
- Server-side reserved-key check for custom question keys (collision with roster columns = display-only corruption).
- Coerce optional answer values to str server-side; a11y polish (drop aria-live on role=alert node, tabindex on completed-view h1); generic 500 messages on public payment endpoints (codebase-wide convention change); homepage card should truncate long descriptions; `EventStatus`/`Audience` constants in seeds.py; remove dead `socials.redirect_social` CSP entry.
- Dev-only: events test conftest deletes slug `dry-tri-2026` from the shared dev DB every run — re-seed by re-running the seed migration or use a test-only slug.

## Deploy expectations

Render preDeploy runs the migrations while old code still serves: expect ~a few minutes of homepage/admin-payments 500s between the fold migration committing and instance swap (self-heals). In-flight social PaymentIntents landing after migration are recorded with a warning and no event link — reconcile manually if any appear.
