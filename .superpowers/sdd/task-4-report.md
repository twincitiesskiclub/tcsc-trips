# Task 4 Report: Public event registration and Stripe payment

## Implemented

- Added `GET /events/<slug>` for active events and admin-only draft previews.
  - Unknown and closed events return 404.
  - Anonymous draft requests return 404.
  - Admin draft previews show the required `DRAFT — admin preview` banner.
  - Stale pending registrations are expired before rendering.
  - Closed-window, sold-out, and missing-option states render without the form.
- Added `POST /events/<slug>/register`.
  - Uses `create_registration()` as the sole pricing and domain-validation path.
  - Returns field-level `RegistrationError.errors` JSON with status 400.
  - Creates automatic-capture USD PaymentIntents with the required descriptor,
    description, receipt email, event metadata, and forwarded idempotency key.
  - Stores the PaymentIntent ID and returns the client secret, registration ID,
    and server-computed amount.
  - Immediately confirms free registrations without calling Stripe.
  - Leaves committed registrations pending when Stripe intent creation fails.
  - Allows draft registrations only from an admin session.
- Added the public event registration template and vanilla JavaScript client.
  - Uses the existing public form components, CSRF helper, and Stripe Elements.
  - Renders active price options and serialized event data.
  - Dynamically rebuilds participant fields from each option's role list.
  - Shows team name only for multi-participant options.
  - Supports required text/choice custom questions and an optional discount code.
  - Handles both paid Stripe confirmation and immediate free confirmation.
  - Uses the existing payment/completed view swap.
- Added event payment webhook handling.
  - Supports both Stripe objects and plain dictionaries from the development
    webhook path.
  - Creates one idempotent `Payment` row for successful event payments.
  - Links the event registration, confirms it, and sends the payment notification.
  - Does not call `User.get_by_email` or create/link a `User`.
  - Logs a warning and still records payment when registration metadata is stale.
  - Cancels pending registrations for canceled event PaymentIntents.
- Changed `/tri` to a 302 redirect to `/events/dry-tri-2026`.
- Registered the `events` blueprint and added its GET endpoint to the
  Stripe-compatible payment-page CSP set.

## Files

Created:

- `app/routes/events.py`
- `app/templates/events/registration.html`
- `app/static/event_registration.js`
- `tests/events/test_routes.py`
- `tests/events/test_webhook.py`

Modified:

- `app/__init__.py`
- `app/routes/main.py`
- `app/routes/payments.py`
- `app/security.py`
- `tests/events/conftest.py`

## TDD evidence

RED:

```text
$ ./run-tests.sh tests/events/test_routes.py tests/events/test_webhook.py -q
14 failed, 1 passed in 1.49s
```

The failures showed the intended missing behavior: event pages returned 404,
the event route module did not exist for Stripe mocks, `/tri` still rendered
the legacy page, and development-mode event webhooks returned 500.

GREEN:

```text
$ ./run-tests.sh tests/events/test_routes.py tests/events/test_webhook.py -q
...............                                                          [100%]
15 passed in 1.31s
```

Focused regression checks:

```text
$ node --check app/static/event_registration.js
$ ./run-tests.sh tests/events/ tests/routes/test_payments.py tests/test_security.py -q
....................................................................     [100%]
68 passed, 6 warnings in 4.37s
```

## Full-suite tail

Command:

```text
$ ./run-tests.sh -q
```

Tail:

```text
........................................................................ [ 98%]
........................                                                 [100%]
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
1248 passed, 177 warnings in 51.38s
```

The warnings are existing SQLAlchemy `Query.get()` legacy warnings; Task 4
introduced no test failures.

## Self-review

- Endpoint response fields, Stripe parameters, metadata, status transitions,
  and draft-session behavior were checked against the binding brief.
- Pricing, discount, participant validation, capacity, and signup-window rules
  remain delegated to `app/events/service.py`.
- The event webhook returns before the legacy user lookup path. Tests assert
  both an unchanged user count and that `User.get_by_email` was not called.
- Payment replay is protected by `Payment.get_by_payment_intent`; the replay
  test verifies a single row.
- The free path confirms and commits before responding and never invokes Stripe.
- The Stripe failure path does not roll back or delete the pending registration.
- The frontend uses existing TCSC public form classes, keeps server pricing
  authoritative, avoids new dependencies, and preserves values when switching
  between participant-role configurations.
- Python compilation, JavaScript syntax, diff whitespace, focused regression
  tests, and the full suite all pass.

## Concerns

- Stripe Elements was exercised through mocked PaymentIntent route tests and a
  JavaScript syntax check, not a live Stripe browser session. This matches the
  test scope in the brief.
- The full suite still emits existing SQLAlchemy 2.x legacy warnings unrelated
  to this task.

STATUS: COMPLETE
