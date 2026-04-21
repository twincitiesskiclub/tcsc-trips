# Registration Tier 2 Fixes — Design Spec

Pre-launch fixes for payment/webhook logic, data integrity, and security in the season registration flow.

## Fix 1: Canceled Webhook Cleans Up UserSeason

**File:** `app/routes/payments.py` lines 208-213

The `payment_intent.canceled` handler only updates `payment.status`. When a hold expires or is canceled externally, the UserSeason stays `PENDING_LOTTERY` forever.

**Change:** After updating payment status, if `payment_type == SEASON` and `season_id` exists, look up the user by email, find their UserSeason, set status to `DROPPED_VOLUNTARY`, and call `sync_status()`. Same pattern as the refund handler (lines 302-309).

## Fix 2: Duplicate Registration Guard

**File:** `app/routes/payments.py` `create_season_payment_intent`

No check prevents creating multiple payment intents for the same email + season.

**Change:** Before creating the Stripe PaymentIntent, query for an existing Payment with matching `email`, `season_id`, and `status` not in `('canceled', 'refunded')`. If found, return a JSON error. This prevents double-charges (returning) and orphaned holds (new).

## Fix 3: Require payment_intent_id on Registration POST

**File:** `app/routes/registration.py` line 66

The `payment_intent_id` field is optional. A direct POST without it creates User + UserSeason with no payment.

**Change:** If `payment_intent_id` is missing or empty, flash an error and redirect back to the form.

## Fix 4: Webhook Returns 500 on Errors

**File:** `app/routes/payments.py` line 217-218

The catch-all returns `json_error(str(e))` which is HTTP 400. Stripe treats 4xx as permanent failures and won't retry.

**Change:** Return `json_error('Webhook processing failed', 500)`. This lets Stripe retry on transient failures without leaking internal error details.

## Fix 5: Align Validation Constants to DB Columns

**File:** `app/constants.py` lines 68, 70

`MAX_PHONE_LENGTH = 30` but `User.phone` is `String(20)`. `MAX_RELATION_LENGTH = 100` but `emergency_contact_relation` is `String(50)`.

**Change:** Set `MAX_PHONE_LENGTH = 20` and `MAX_RELATION_LENGTH = 50`. No migration.

## Fix 6: Fail-Closed Webhook Signature Verification

**File:** `app/routes/payments.py` lines 67-78

When `STRIPE_WEBHOOK_SECRET` is unset, webhooks are accepted without verification.

**Change:** If `webhook_secret` is falsy and `FLASK_ENV != 'development'`, return a 500 error. Only allow unverified webhooks in local development.
