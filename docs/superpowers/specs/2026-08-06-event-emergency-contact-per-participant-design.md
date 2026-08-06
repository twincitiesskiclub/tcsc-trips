# Event Emergency Contact Per Participant - Design

**Date:** 2026-08-06
**Status:** Approved (design approved interactively 2026-08-06)

## Context & Problem

Event registrations (Dry Tri) collect one emergency contact per checkout. A
Relay Triathlon checkout covers three participants who may be three different
people, but the form collects a single emergency contact for the whole team.
Rob wants one emergency contact per participant, for every registration type.

Current state on `main`:

- `EventRegistration.emergency_contact_name` / `emergency_contact_phone`
  (both NOT NULL) hold the per-checkout contact.
- The form has a standalone "Emergency contact" section, always shown,
  required, independent of the selected price option.
- `create_registration()` in `app/events/service.py` requires both fields at
  the registration level.
- The admin roster/CSV shows one "Emergency contact" column per registration
  row.
- Production has one real Dry Tri registration whose data must survive.

## Decision

Move the emergency contact from the registration to the participant. Every
participant supplies exactly one emergency contact (name + phone), for all
price options. The registration-level columns are dropped.

Rejected alternatives:

- Keep the registration-level contact and add per-participant contacts only
  for team options: two homes for the same data, inconsistent export.
- Model as scoped custom questions: the questions system has no
  per-participant machinery.

## Data Model

`EventParticipant` gains:

- `emergency_contact_name` (String(255), NOT NULL)
- `emergency_contact_phone` (String(50), NOT NULL)

`EventRegistration` loses `emergency_contact_name` and
`emergency_contact_phone`.

### Migration (single revision)

1. Add both columns to `event_participants`, nullable.
2. Backfill each participant from its parent registration's values.
3. Alter both columns to NOT NULL.
4. Drop both columns from `event_registrations`.

Downgrade reverses: re-add registration columns (backfill from each
registration's first participant, then NOT NULL), drop participant columns.

## Registration Form

- Remove the standalone "Emergency contact" section from
  `app/templates/events/registration.html`.
- In `renderParticipants()` (`app/static/event_registration.js`), each
  participant card gains a third row: "Emergency contact name" and
  "Emergency contact phone" (tel), both required, with the hint
  "Someone who is not participating with you."
- Field ids follow the existing pattern
  (`participant-N-emergency_contact_name`), so `createInputField`'s
  `data-participant-field` mechanism, value preservation across option
  switches, and payload collection work unchanged.

  Note: `createInputField` derives `data-participant-field` via
  `field.split('-').pop()`, which returns the full key here because the
  suffix uses underscores (`emergency_contact_name`), matching how
  `date_of_birth` already works.
- `collectPayload()` stops sending registration-level
  `emergency_contact_name` / `emergency_contact_phone`; they ride along
  inside each participant object instead.
- Server field-error mapping for the two removed top-level keys is dropped;
  participant errors surface through the existing participants error path.

## Server Validation

In `app/events/service.py`:

- `_validate_participants()` requires `emergency_contact_name` and
  `emergency_contact_phone` per participant, same trimming rules as the
  other participant fields.
- The registration-level required-field loop for the two emergency fields is
  removed, as are the constructor arguments on `EventRegistration`.
- `EventParticipant` construction passes both new fields.

## Admin Roster / CSV

In `app/routes/admin_events.py`:

- Remove the registration-level "Emergency contact" column.
- Each `participant_N` cell gains the contact, e.g.
  `Rollerskier: Jo Smith (2001-03-04, jo@x.com, 555-1234; emergency: Pat Smith 555-9999)`.
- Still one row per checkout.

## Error Handling

- Missing per-participant emergency fields produce participant-indexed
  validation errors exactly like missing name/email/phone today.
- Browser-side `required` attributes give first-line feedback; server
  validation remains authoritative.

## Testing

- Update `tests/events/` payload helpers to carry the fields per participant.
- Validation cases: missing name, missing phone, per participant position;
  registration-level keys no longer accepted or required.
- Roster export: emergency info appears inside each participant cell; the
  standalone column is gone.
- Migration verified against the dev DB (upgrade + downgrade), with a
  registration row present to prove the backfill.

## Out of Scope

- Trip registrations (the trip-registration-redesign branch) collect no
  emergency contact today; whether they should mirror this is a separate
  decision on that project.
- Relationship/email fields for the emergency contact (name + phone only,
  matching what the event form collects today).
