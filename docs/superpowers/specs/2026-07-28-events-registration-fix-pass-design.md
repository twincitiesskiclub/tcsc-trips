# Events Registration Fix Pass — Design

**Date:** 2026-07-28
**Driver:** Feedback from the club's events organizer after reviewing the Dry Tri 2026 draft.
**Scope:** Public event registration form + admin event editor. No schema migration.

## Background

The generic Events system shipped 2026-07-25 (`docs/superpowers/specs/2026-07-24-generic-events-system-design.md`).
The Dry Tri 2026 event is seeded in production as a **draft** with zero registrations, so
behavioural changes here carry no risk to live registrant data.

Custom questions are currently **per-event**: every question renders for every price option.
The organizer needs them to differ by which entry option the registrant picked, and needs to
manage that themselves in `/admin/events` rather than through a code change.

### Production state (read-only query, 2026-07-27)

| Price option | Price | Member price |
|---|---|---|
| Individual Triathlon | $55.00 | $35.00 |
| Relay Triathlon | $105.00 | $75.00 |
| Run-only 6K | $30.00 | $15.00 |

Event discount code: `TCSC2026`. This is verified working — `compute_price` requires the event
code to be set, to match case-insensitively, and the option to carry a `member_price_cents`;
all three hold for all three options.

Two facts from that query shape the design:

1. **Live option names differ from the YAML template.** Production uses "Individual Triathlon"
   and "Relay Triathlon"; `config/event_templates.yaml` says "Individual" and "Team of 3".
   Question scoping references options by name, so the template names are updated to match
   production to prevent drift.
2. **The admin template dropdown is a money footgun.** On the edit form, changing it replaces
   price options *and* questions, which would wipe the member prices above and silently disable
   `TCSC2026`. This pass adds a confirmation guard.

## Out of scope

- Migrating the live event's `custom_questions` JSON. The organizer will edit it in
  `/admin/events` — that is the point of the feature.
- Homepage event-card description rendering (a five-line schedule inside a card would break the
  card layout; the card should collapse).
- The stale `pickleball` draft event in production.
- Discount-code hardening (single shared guessable string, no membership check, no usage cap).
  Flagged to the user as a policy question, not changed here.

## Changes

### 1. Description line breaks

`event.description` renders inside a plain `<p>`, so HTML collapses its newlines. The stored
text already contains the intended blank lines and `- 7:30 AM` schedule bullets.

**Fix:** `white-space: pre-line` on the description paragraph in
`app/templates/events/registration.html`. Rendering-only; no data change.

### 2. Drop the registration-contact section

The "Registration contact" section (email + phone) is removed from the public form. Participant
information is sufficient.

`EventRegistration.contact_email` and `contact_phone` are `NOT NULL` and feed the Stripe
`receipt_email`, the payment metadata, the admin roster, and the CSV export. Rather than migrate
them to nullable, the server **derives** them from participant #1:

- `create_registration` no longer requires `contact_email` / `contact_phone` in the payload.
- After participant validation succeeds, `contact_email` = participant 1's email and
  `contact_phone` = participant 1's phone.
- Any client-supplied `contact_email` / `contact_phone` is **ignored**, not trusted.
- If participant validation fails, the participant errors surface as they do today; no
  `contact_email` error is emitted.

Consequence to accept: the Stripe receipt goes to participant #1, so for a relay team it lands on
whoever was entered first. The roster's `contact_email` / `contact_phone` columns remain and now
duplicate participant 1 — kept, because roster consumers already read them.

### 3. Team name moves into participant details

The team-name field moves from the removed contact section into the "Participant details"
section, rendered above the participant cards and shown only when the selected option has more
than one participant role. Server-side validation is unchanged — `team_name` is already required
when `option.participant_count > 1`.

Because it is now rendered by `event_registration.js` alongside participants rather than living
in static markup, the `showServerErrors` field map keeps its `team_name` entry pointing at the
same element id.

### 4. Per-option question scoping

Each custom question gains an optional `price_options` field: a list of price-option **names**
the question applies to. Absent, missing, or empty means **all options** — so every existing
question keeps its current behaviour with no data change.

```yaml
- key: course
  label: "Which race will you participate in?"
  type: choice
  options: [...]
  required: true
  price_options: ["Individual Triathlon", "Relay Triathlon"]
```

**Schema validation** (`app/events/templates.py::_validate_question`): if present,
`price_options` must be a list of strings.

**Public rendering** (`registration.html` + `event_registration.js`): all questions render once.
On option change, questions outside the selected option's scope are hidden *and their inputs
disabled*, so both `form.checkValidity()` and `collectPayload()` skip them. Enabling and
disabling — rather than adding and removing DOM — preserves any answer the registrant already
typed if they switch options and switch back.

**Server filtering** (`app/events/service.py`): `_validate_answers` receives only the questions
in scope for the chosen option. Out-of-scope answers are neither required nor stored, so a
client cannot smuggle in an answer to a question its option should not have been asked.

**Unresolvable scopes fail open to shown.** A scope naming a price option that no longer exists
falls back to rendering the question, matching the codebase's fail-open convention. A required
question appearing when it need not is benign; silently dropping one is not.

### 5. Disjoint-scope duplicate keys

`_validated_questions` in `app/routes/admin_events.py` currently rejects any duplicate key. It is
relaxed to allow a repeated key **only when the scopes of every question sharing it are pairwise
disjoint and none of them is unscoped** (an unscoped question means all options, so it can never
be disjoint from anything). Overlapping or unscoped duplicates still raise.

This lets one logical question with per-option answer sets occupy a single roster column.

Two supporting changes:

- **Admin save validates scope names.** Every name in a `price_options` list must match a price
  option being saved with the event, so the editor cannot create an orphaned scope. (The public
  renderer still fails open, for data that predates this check.)
- **`_registration_columns` dedupes question columns by key**, preserving first-seen order.
  Without this, the two `competition_gender` variants would emit two identical columns.

### 6. Dry Tri question content

Delivered via the mechanism above, in `config/event_templates.yaml`. Price option names in the
template are also renamed to match production.

| Question | Individual Triathlon | Relay Triathlon | Run-only 6K |
|---|---|---|---|
| `competition_gender` | Men / Women / **Non-binary** | Men / Women / **Mixed** | Men / Women / **Non-binary** |
| `club` | yes | yes | yes |
| `city_state` | yes | yes | yes |
| `course` | yes | yes | — |
| `wave` | yes | yes | — |

`competition_gender` is two entries sharing one key with disjoint scopes: one scoped to
Individual + Run-only offering Non-binary, one scoped to Relay offering Mixed. The run-only 6K is
an individual entry, so it takes the non-binary set. Run-only participants are asked neither
`course` nor `wave`.

### 7. Admin editor

- **"Applies to options" control per question:** a checkbox per current price-option name, none
  checked meaning all options. Checkboxes are built from the live `priceRows` in the editor, so
  renaming an option and then scoping a question works within a single unsaved edit. Questions
  re-render on price-option `change` (blur), not `input`, to avoid stealing focus mid-typing.
- **Template dropdown confirmation:** on an existing event, changing the template prompts for
  confirmation before replacing price options and questions, because doing so silently discards
  member prices.

## Testing

`tests/events/` has 38 references to the contact fields across 6 files; all registration payload
fixtures drop `contact_email` / `contact_phone`.

New coverage:

- Contact email and phone are derived from participant 1; a client-supplied contact value is
  ignored.
- A question scoped to other options is neither required nor stored for the chosen option.
- An unscoped question still applies to every option.
- A scope naming an unknown option falls open to applying.
- Duplicate keys with disjoint scopes save; overlapping or unscoped duplicates raise.
- Admin save rejects a scope naming a nonexistent price option.
- Roster columns contain exactly one `competition_gender` column.
- The `dry_tri` template loads with the scoped questions and matches the table in §6.

## Files

| File | Change |
|---|---|
| `app/templates/events/registration.html` | `pre-line` description; remove contact section; move team name; render scoped questions |
| `app/static/event_registration.js` | Team name in participant section; scope-driven enable/disable; drop contact from payload |
| `app/events/service.py` | Derive contact from participant 1; filter questions by option scope |
| `app/events/templates.py` | Validate optional `price_options` on a question |
| `app/routes/admin_events.py` | Disjoint-scope key rule; validate scope names; dedupe question columns |
| `app/static/admin_events.js` | Scope checkboxes; template-change confirmation |
| `config/event_templates.yaml` | Scoped Dry Tri questions; option names matched to production |
| `tests/events/*.py` | Drop contact fields; new scoping/derivation coverage |
