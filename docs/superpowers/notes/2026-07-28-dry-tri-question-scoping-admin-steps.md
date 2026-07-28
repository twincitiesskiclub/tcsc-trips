# Dry Tri 2026 — admin steps after the question-scoping deploy

The per-option question feature ships in code, but the **live event keeps its own
copy of the questions JSON**. Production still has the five old unscoped
questions until someone edits them in the admin. These are those steps.

Production state at time of writing (event is `draft`, **0 registrations**, so
nothing here can disturb a registrant):

| Price option | Price | Member price |
|---|---|---|
| Individual Triathlon | $55.00 | $35.00 |
| Relay Triathlon | $105.00 | $75.00 |
| Run-only 6K | $30.00 | $15.00 |

Discount code on the event: `TCSC2026`.

## Fast path: re-apply the dry_tri template

The `dry_tri` template in `config/event_templates.yaml` now matches production
exactly — same option names, descriptions, prices, and member prices — and
carries the correctly scoped questions. So the quickest correct route is:

1. `/admin/events` → **TCSC Dry Triathlon 2026** → Edit.
2. Set **Event template** to **Dry Tri (race)** and accept the confirmation.
3. Save. Spot-check the three options and their questions on
   `/events/dry-tri-2026`.

What this does and does not touch:

- **Replaced:** price options and custom questions, with values identical to
  what is already there apart from the question scopes.
- **Untouched:** description, dates, location, capacity, status, and the
  `TCSC2026` discount code. The dropdown only rewrites the two hidden JSON
  fields client-side; the edit route never calls `apply_template`.
- **Caveat:** it deletes and recreates the price option rows, so they get new
  IDs. Harmless at 0 registrations, but `_replace_price_options` refuses to
  remove an option that has registrations — so once anyone signs up, the
  dropdown becomes a hard error. Do this before the event goes active.

The confirmation prompt exists because for an event whose admin config has
drifted from its template (the migrated socials, or a hand-tuned future Dry
Tri), the same click would discard that drift, including member prices.

## Manual path

Use this if the template and the live event have diverged, or you would rather
not recreate the price option rows.

1. Go to `/admin/events`, open **TCSC Dry Triathlon 2026** → Edit.
2. In **Custom questions**, each question now has an **Applies to options** row
   with a checkbox per price option. Nothing checked = asked for every option.
3. Edit the existing `competition_gender` question:
   - Options (one per line): `Men`, `Women`, `Non-binary`
   - Applies to options: check **Individual Triathlon** and **Run-only 6K**
4. Add a second question with the **same key** `competition_gender`:
   - Label: `Competition gender`, Type: Choice, Required: yes
   - Options: `Men`, `Women`, `Mixed`
   - Applies to options: check **Relay Triathlon** only
   Sharing the key is deliberate — the two variants land in one
   `competition_gender` column in the registrations CSV. The save is rejected if
   the scopes ever overlap, so they cannot both apply to the same option.
5. Leave `club` and `city_state` with nothing checked (asked of everyone).
6. On `course` and `wave`, check **Individual Triathlon** and **Relay
   Triathlon** only. That is what stops run-only entrants being asked which
   course and wave they want.
7. Save, then open `/events/dry-tri-2026` (admin session shows the draft) and
   click through all three options to confirm the questions change.

## What to expect on the public page

- No "Registration contact" section. Participant details are the only contact
  collected, and the Stripe receipt goes to **participant #1** — for a relay
  team, whoever is entered first.
- Team name sits with the participant details and appears only for the relay
  option.
- The event description now renders its line breaks, so the schedule list shows
  one item per line.

## Open question for the organizers

`TCSC2026` is a single shared code with no membership check and no usage cap —
anyone who has the string gets member pricing (about 36% off). If it is meant to
be member-only, use something unguessable and distribute it through the member
Slack or newsletter.
