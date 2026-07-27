# Stub User Prevention — Design

**Date:** 2026-05-01
**Status:** Draft (awaiting user review)
**Author:** brainstorming session

## Problem

Three users registered for Season 4 (2026 Spring/Summer) ended up with stub records: only `email`, `first_name`, `last_name` populated; `date_of_birth`, `phone`, `tshirt_size`, `emergency_contact_*`, `ski_experience`, `preferred_technique` all `NULL`. Each has `created_at == updated_at` (the row was inserted and never updated), `user.status = PENDING`, `user_season.status = PENDING_LOTTERY`, and a Stripe PaymentIntent in `requires_capture` (the customer's card is held but not charged).

Affected rows in production:

| user_id | email | name | created (UTC) | Payment |
|---|---|---|---|---|
| 265 | scottjetsettrainer@gmail.com | Scott Darragh | 2026-04-24 20:37 | Pay#159 (`pi_3TPqU1...`) $105 held |
| 266 | waldooutside@gmail.com | Bradley Waldorf | 2026-04-29 01:18 | Pay#204 (`pi_3TRMlR...`) $105 held |
| 267 | marie.alundgren@gmail.com | Marie Amie Lundgren | 2026-05-01 00:07 | Pay#214 (`pi_3TS4cW...`) $105 held |

Bradley (u266) re-registered successfully ~2 minutes later as u88 with `bmwaldorf54@gmail.com`. Scott and Marie have no successful registration.

The remaining 60 successful Season 4 registrations have all required fields populated. The form-POST capture path itself works correctly. The leak is in how a payment can be authorized *before* the form POST runs.

## Root cause

Registration has two writes that can decouple:

1. JS calls `POST /create-season-payment-intent` (`app/routes/payments.py:464`). Stripe creates a PaymentIntent.
2. JS confirms the card with Stripe. Stripe authorizes and fires `payment_intent.amount_capturable_updated`.
3. The webhook (`app/routes/payments.py:108-126`) creates `User(email, first_name, last_name, status=PENDING)` + `UserSeason(PENDING_LOTTERY)` + `Payment` from PaymentIntent metadata only — no DOB, phone, emergency contact, etc.
4. JS then submits the form to `POST /seasons/<id>/register`.
5. The form POST handler (`app/routes/registration.py:124-126`) finds the existing user and `setattr`s the rest of the fields.

If step 5 never runs, the stub from step 3 is left behind.

The dominant trigger: `create-season-payment-intent` does **not** check whether the registration window is open for the user's member type. The form POST does (`registration.py:78`). So a NEW user can hit the page when only the *returning* window is open, get a payment intent created, have Stripe authorize the card → webhook creates the stub → form POST gets rejected at the window check → user is redirected with a flash error → stub and held card remain.

This explains all three cases:
- Marie (May 1): new window opens May 2 — she was a NEW member trying before her window.
- Bradley (Apr 29): tried as NEW with a wrong email before the new window opened, then re-registered correctly as RETURNING with his other email.
- Scott (Apr 24): tried before either window opened (likely held an old form tab open or the window was edited later).

Other failure modes that produce the same pattern (form-POST validation failure, network drop between Stripe confirm and form submit, browser close) are out of scope for this fix.

## Goals

- **Prevent new stubs** from being created via the closed-window path.
- **Clean up the three existing stubs** and their held PaymentIntents.
- **Communicate** with affected users so Scott and Marie can re-register and Bradley knows the duplicate is resolved.

## Non-goals

- No general "cancel held PaymentIntent on form-POST failure" safety net (deferred — not the leak that's actually happening).
- No restructure of the webhook to remove user creation entirely (deferred — closing the door is sufficient for the observed cases).
- No changes to trip or social-event payment intent flows.
- No admin UI for stub-user management (one-shot script is enough for this edge case).

## Design

### Part 1 — Close the door

In `app/routes/payments.py:create_season_payment_intent`, after the existing `member_type` lookup and before creating the Stripe PaymentIntent, add:

```python
if not season.is_open_for(member_type.lower(), datetime.utcnow()):
    return json_error(
        f"Registration for {member_type.lower()} members is not currently open."
    )
```

Notes:
- `Season.is_open_for` (`app/models.py:289`) expects lowercase `'new'` / `'returning'`; `MemberType.*.value` is uppercase, hence `.lower()`.
- Returns a 4xx-style JSON error consistent with the existing `json_error` calls in the same handler.
- The frontend (`app/static/script.js:528`) already surfaces `paymentIntentData.error` to the user via `showError`, so no JS changes are required.
- `payments.py` does not currently import `datetime`; add `from datetime import datetime` to the imports at the top of the file.

The form-POST window check at `registration.py:78` stays as defense-in-depth.

### Part 2 — Cleanup script for existing stubs

New file: `scripts/cleanup_stub_registrations.py`

Behavior:
1. Accepts a season id as argument: `python scripts/cleanup_stub_registrations.py <season_id>`.
2. Queries `UserSeason` for the season joined to `User`, finds rows where every one of these fields is NULL: `date_of_birth`, `phone`, `tshirt_size`, `emergency_contact_name`. (Same predicate used in the investigation query.)
3. For each match, prints the user, their UserSeason, and the linked Payment (status, payment_intent_id, amount).
4. Prompts `[y/N]` per user to perform the cleanup. On `y`:
   - If the linked Payment exists and its Stripe status is `requires_capture`, call `stripe.PaymentIntent.cancel(payment_intent_id)` and set local `Payment.status` to the returned status. If the Payment is already in a terminal state (`canceled`, `succeeded`, `refunded`), skip the Stripe call and log the current status.
   - Delete the `UserSeason` row.
   - Delete the `User` row only if they have no other `user_seasons` and no other `payments`. Otherwise leave the User intact and just delete the UserSeason; print a note.
5. Commits per user so a partial run is safe.
6. The script lives alongside other one-shot scripts in `scripts/` (matches `seed_former_members.py`, `add_practice_leads.py` conventions).

For the three affected users:
- **u265 Scott** — full cleanup (no other seasons, no other payments).
- **u266 Bradley waldooutside@** — full cleanup (his real account is u88, separate user).
- **u267 Marie** — full cleanup.

### Part 3 — Outreach

Manual emails to the affected users:
- Scott (`scottjetsettrainer@gmail.com`) — explain the issue, confirm no charge, ask him to re-register once the new-member window opens (May 2 21:00 UTC).
- Marie (`marie.alundgren@gmail.com`) — same as Scott.
- Bradley (`waldooutside@gmail.com`) — confirm the duplicate authorization on this email has been voided, his real registration under `bmwaldorf54@gmail.com` is fine.

Outreach is a manual step performed after the cleanup script runs successfully; it is not part of the code changes.

## Testing plan

- Add a unit test for `create_season_payment_intent` that asserts:
  - Closed window for a NEW email returns 400-style JSON error and does not call `stripe.PaymentIntent.create`. (Mock Stripe.)
  - Open window proceeds normally.
- Manual verification on local dev:
  - Open a season where only one window is open. Submit registration as the other member type. Confirm error is shown in the form and no User/Payment row is created.
  - Re-confirm successful end-to-end registration in the open window still works.

## Rollout

1. Merge code change (Part 1) and tests.
2. Deploy to production (Render auto-deploys on merge to main per `Procfile`/`scripts/release.sh`).
3. Run `scripts/cleanup_stub_registrations.py 4` against production with prompts; cancel each held PaymentIntent and delete each stub.
4. Send the outreach emails (Part 3).
5. Spot-check the admin members grid to confirm the three users are gone.

## Risks and mitigations

- **Risk:** `stripe.PaymentIntent.cancel` fails (e.g., already captured by some race). **Mitigation:** Script catches the exception, logs, and continues; manual reconciliation if needed.
- **Risk:** Deleting a User cascades unexpectedly. **Mitigation:** The User model's relationships (`payments`, `user_seasons`, `tags`, `status_changes`) all use `lazy=True` without `cascade='delete'`. Script explicitly checks the user has no other related rows before deleting; otherwise it leaves the User and only removes the UserSeason.
- **Risk:** A future season config edit could re-introduce a window where one type is open and another isn't. **Mitigation:** Part 1 catches this at the API; the existing form-POST check stays as a second layer.
