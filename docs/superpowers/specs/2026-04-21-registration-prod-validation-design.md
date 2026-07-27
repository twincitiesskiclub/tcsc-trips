# Registration Prod Validation — Design Spec

**Date:** 2026-04-21
**Goal:** Validate the polished registration flow works correctly in production before new member registration opens, using automated checks + manual browser steps for Stripe card entry.

## Overview

A multi-command Python script (`scripts/test_prod_registration.py`) that validates the full registration lifecycle in production. Two test users exercise both paths:

- **robertrutscher@gmail.com** — new member (manual capture, lottery flow)
- **robrutscher@gmail.com** — returning member (automatic capture, immediate activation)

The script follows the existing `test_practice_post.py` pattern: load `.env`, connect to prod DB directly, use Flask app context for SQLAlchemy queries, call Stripe SDK for payment operations.

## Constraints

- **Live Stripe keys** — real charges/holds; script must clean up via refund/cancel
- **No season activation** — won't trigger "Activate Season" since that affects all users
- **Admin endpoints are auth-gated** — script uses Stripe SDK directly for capture/refund rather than hitting admin HTTP endpoints
- **Webhook-driven DB updates** — after Stripe operations (capture, refund), the prod server's webhook handler updates DB records asynchronously; script polls DB until state converges

## Commands

### `walkthrough` — Full guided flow

Runs all phases sequentially with `input()` pauses for manual browser steps. Prints clear instructions at each pause. Exits early with a summary if any automated check fails.

### `pre-check` — Pre-flight validation

Automated checks before any registration:

1. **Season exists and is current** — query `Season` where `is_current=True`, print name/dates/price
2. **Registration windows open** — verify `returning_start <= now <= returning_end` and `new_start <= now <= new_end`
3. **Test emails clean** — no active/pending `Payment` for current season for either test email
4. **Returning member detection** — verify `robrutscher@gmail.com` is recognized as returning via `User.is_returning` property
5. **New member detection** — verify `robertrutscher@gmail.com` is NOT recognized as returning (or doesn't exist yet)
6. **API check** — call `POST /api/is_returning_member` on prod for both emails, verify correct JSON responses

Snapshot: saves pre-test state of both users (if they exist) to a JSON file (`/tmp/tcsc_test_snapshot.json`) for cleanup restoration.

### `verify-new` — After new member registers in browser

Checks after `robertrutscher@gmail.com` completes the registration form:

1. **User record** — exists with correct email, name fields populated
2. **UserSeason record** — exists for current season, `status = 'PENDING_LOTTERY'`, `registration_type = 'new'`
3. **Payment record** — exists with `status = 'requires_capture'`, `payment_type = 'season'`, correct season_id, amount matches season price
4. **Payment metadata** — payment linked to user, `payment_intent_id` starts with `pi_`
5. **User.status** — `PENDING` (derived from PENDING_LOTTERY UserSeason)

### `verify-returning` — After returning member registers in browser

Checks after `robrutscher@gmail.com` completes the registration form:

1. **User record** — exists with correct email, fields updated
2. **UserSeason record** — `status = 'ACTIVE'`, `registration_type = 'returning'`
3. **Payment record** — `status = 'succeeded'` (auto-captured), `payment_type = 'season'`, amount matches
4. **User.status** — `ACTIVE` (derived from ACTIVE UserSeason)
5. **User.derived_status** — matches `ACTIVE`

### `verify-duplicate` — Duplicate prevention

1. Call `POST /create-season-payment-intent` for `robertrutscher@gmail.com` — expect error response about already registered
2. Call `POST /create-season-payment-intent` for `robrutscher@gmail.com` — expect same error
3. Print the actual error messages for visual confirmation

### `capture-new` — Capture the new member's held payment

1. Look up the `requires_capture` Payment for `robertrutscher@gmail.com`
2. Call `stripe.PaymentIntent.capture(payment_intent_id)` via Stripe SDK
3. Poll DB (up to 30s, every 2s) waiting for webhook to update:
   - Payment.status → `succeeded`
   - UserSeason.status → `ACTIVE`
4. Verify `User.derived_status` = `ACTIVE`
5. Verify `User.get_slack_tier()` = `full_member`

### `verify-status` — Status and Slack tier verification

For both test users:

1. **User.status** — verify matches expected value
2. **User.derived_status** — matches User.status
3. **User.get_slack_tier()** — `full_member` for ACTIVE users
4. **UserSeason.status** — correct per member type and flow stage
5. **seasons_since_active** — 0 for active members

### `cleanup` — Refund payments and restore state

With confirmation prompt before executing:

1. **Refund returning member** — `stripe.Refund.create(payment_intent=pi_id)` for `robrutscher@gmail.com`
2. **Refund new member** (if captured) — same for `robertrutscher@gmail.com`; if still `requires_capture`, use `stripe.PaymentIntent.cancel(pi_id)` instead
3. **Poll for webhook processing** — wait for Payment statuses to update
4. **Delete test UserSeason records** — remove UserSeason rows for both test users for current season
5. **Delete test Payment records** — remove Payment rows for both test users for current season
6. **Restore user state** — if user existed before test, restore prior status from snapshot; if user was created by test (robertrutscher), delete the User record entirely
7. **Commit and verify** — confirm DB is clean

### `status` — Quick state check

Print current state of both test users:
- User exists? Status? derived_status? Slack tier?
- UserSeason for current season? Status?
- Payment for current season? Status? Stripe status?

## Implementation Details

### DB Connection

Same pattern as `test_practice_post.py`:
```python
load_dotenv()
PROD_DB_URL = "postgresql://..."  # from test_practice_post.py
os.environ['DATABASE_URL'] = PROD_DB_URL
from app import create_app
```

### Stripe SDK

Use `stripe` library directly (key loaded from `.env`):
```python
import stripe
stripe.api_key = os.environ['STRIPE_SECRET_KEY']
```

### Webhook Polling

After Stripe operations that trigger webhooks, poll DB with exponential backoff:
- Check every 2 seconds, up to 30 seconds total
- If state doesn't converge, print warning but don't fail hard (webhook might be slow)

### Duplicate Prevention Test

Hit the prod endpoint directly via `requests`:
```python
requests.post(f"{PROD_URL}/create-season-payment-intent", json={...})
```
Where `PROD_URL = "https://tcsc-trips.onrender.com"`.

### State Snapshot

Before any mutations, save to `/tmp/tcsc_test_snapshot.json`:
```json
{
  "robertrutscher@gmail.com": {
    "existed": false
  },
  "robrutscher@gmail.com": {
    "existed": true,
    "status": "ACTIVE",
    "seasons_since_active": 0,
    "user_season_status": null
  }
}
```

### Output Format

Each check prints a pass/fail line:
```
  ✓ UserSeason status: PENDING_LOTTERY
  ✗ Payment status: expected requires_capture, got succeeded
```

Summary at end of each command:
```
7/7 checks passed
```
or
```
5/7 checks passed — 2 FAILURES (see above)
```

## Walkthrough Command Flow

```
═══ TCSC Registration Prod Validation ═══

Step 1/8: Pre-flight checks
  [runs pre-check]

Step 2/8: Register NEW member (manual)
  → Open https://tcsc-trips.onrender.com/seasons/<id>/register
  → Email: robertrutscher@gmail.com
  → Complete form as new member, submit with card
  → Verify success page says "hold placed"
  Press Enter when done...

Step 3/8: Verify new member
  [runs verify-new]

Step 4/8: Register RETURNING member (manual)
  → Same URL
  → Email: robrutscher@gmail.com
  → Complete form as returning member, submit with card
  → Verify success page says "card charged"
  Press Enter when done...

Step 5/8: Verify returning member
  [runs verify-returning]

Step 6/8: Duplicate prevention
  [runs verify-duplicate]

Step 7/8: Capture new member payment
  [runs capture-new]

Step 8/8: Status & Slack tier verification
  [runs verify-status]

═══ All checks passed! ═══
Run 'cleanup' when ready to refund and remove test data.
```

## What This Does NOT Test

- **Browser rendering / CSS / JS UX** — walkthrough prompts you to visually confirm during manual steps
- **Season activation** — skipped to avoid affecting all real members
- **Slack channel sync execution** — only verifies tier computation, doesn't run actual sync
- **Registration window enforcement** — assumes windows are currently open; doesn't test closed-window rejection
- **Slack notification delivery** — walkthrough prompts you to check the Slack channel manually
