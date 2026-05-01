# Stub User Prevention Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop creating stub `users` rows when a Stripe payment is authorized for a member type whose registration window is closed, and clean up the three existing stubs in production.

**Architecture:** Add an `is_open_for(member_type)` gate at the top of the `/create-season-payment-intent` route so a PaymentIntent is never created (and the webhook never fires) when the user's window is closed. The form-POST window check at `app/routes/registration.py:78` stays as defense-in-depth. A one-shot script handles the three existing stubs by cancelling their held PaymentIntents and deleting the orphan `users` / `user_seasons` rows.

**Tech Stack:** Flask, SQLAlchemy, Stripe Python SDK, pytest, PostgreSQL

**Spec:** `docs/superpowers/specs/2026-05-01-stub-user-prevention-design.md`

---

## File Structure

- **Modify** `app/routes/payments.py` — add window-check at top of `create_season_payment_intent`. Add `from datetime import datetime` to imports.
- **Create** `tests/routes/__init__.py` — package marker (the `tests/routes/` dir doesn't exist yet).
- **Create** `tests/routes/test_payments.py` — pytest module covering the new gate.
- **Create** `scripts/cleanup_stub_registrations.py` — one-shot script for production cleanup.

---

## Task 1: Add the window-check gate in `create_season_payment_intent`

**Files:**
- Modify: `app/routes/payments.py:1-10` (add datetime import) and `app/routes/payments.py:464-518` (add gate inside `create_season_payment_intent`)
- Create: `tests/routes/__init__.py`
- Create: `tests/routes/test_payments.py`

- [ ] **Step 1.1: Create `tests/routes/__init__.py`**

```python
```

(Empty file — package marker. Use `Write` with empty content.)

- [ ] **Step 1.2: Write the failing test**

Create `tests/routes/test_payments.py`:

```python
"""Tests for app.routes.payments."""

from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest

from app import create_app
from app.models import db, Season


@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        'postgresql://tcsc:tcsc@localhost:5432/tcsc_trips'
    )
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db_session(app):
    with app.app_context():
        db.create_all()
        yield db
        db.session.rollback()


@pytest.fixture
def season_returning_only(app, db_session):
    """A season where only the RETURNING window is currently open."""
    now = datetime.utcnow()
    with app.app_context():
        season = Season(
            name=f'Test Season {now.timestamp()}',
            season_type='winter',
            year=now.year,
            start_date=now.date(),
            end_date=(now + timedelta(days=180)).date(),
            price_cents=10500,
            returning_start=now - timedelta(days=1),
            returning_end=now + timedelta(days=1),
            new_start=now + timedelta(days=2),
            new_end=now + timedelta(days=10),
        )
        db.session.add(season)
        db.session.commit()
        season_id = season.id
    yield season_id
    with app.app_context():
        s = Season.query.get(season_id)
        if s:
            db.session.delete(s)
            db.session.commit()


class TestCreateSeasonPaymentIntentWindowGate:
    """Regression tests: do not create a PaymentIntent when the user's
    registration window is closed."""

    @patch('app.routes.payments.stripe')
    def test_new_member_blocked_when_new_window_closed(
        self, mock_stripe, client, season_returning_only
    ):
        # NEW window opens in 2 days; only RETURNING is open right now.
        resp = client.post(
            '/create-season-payment-intent',
            json={
                'season_id': season_returning_only,
                'email': 'brand-new-user@example.com',
                'name': 'Brand New',
            },
        )

        assert resp.status_code == 400
        body = resp.get_json()
        assert 'not currently open' in body['error'].lower()
        assert 'new' in body['error'].lower()
        mock_stripe.PaymentIntent.create.assert_not_called()

    @patch('app.routes.payments.stripe')
    def test_returning_member_allowed_when_returning_window_open(
        self, mock_stripe, client, season_returning_only, db_session, app
    ):
        # Seed an existing returning member (has an ACTIVE prior UserSeason).
        from app.models import User, UserSeason
        from app.constants import UserStatus, UserSeasonStatus

        with app.app_context():
            other_season = Season(
                name='Prior Season for Returning Test',
                season_type='winter',
                year=2024,
                start_date=datetime(2024, 1, 1).date(),
                end_date=datetime(2024, 6, 1).date(),
                price_cents=10000,
            )
            db.session.add(other_season)
            db.session.flush()
            user = User(
                email='returning@example.com',
                first_name='Re',
                last_name='Turning',
                status=UserStatus.ACTIVE,
            )
            db.session.add(user)
            db.session.flush()
            us = UserSeason(
                user_id=user.id,
                season_id=other_season.id,
                registration_type='returning',
                status=UserSeasonStatus.ACTIVE,
            )
            db.session.add(us)
            db.session.commit()

        mock_stripe.PaymentIntent.create.return_value = MagicMock(
            client_secret='cs_test_xyz',
            id='pi_test_123',
            amount=10500,
            status='requires_payment_method',
        )

        resp = client.post(
            '/create-season-payment-intent',
            json={
                'season_id': season_returning_only,
                'email': 'returning@example.com',
                'name': 'Re Turning',
            },
        )

        assert resp.status_code == 200
        mock_stripe.PaymentIntent.create.assert_called_once()
```

- [ ] **Step 1.3: Run the new tests, verify they fail**

Run:

```bash
source env/bin/activate && pytest tests/routes/test_payments.py -v
```

Expected: both `test_new_member_blocked_when_new_window_closed` FAILS (it currently returns 200 because the gate doesn't exist) and `test_returning_member_allowed_when_returning_window_open` may pass or fail depending on existing behavior. The first failure is the one we care about.

- [ ] **Step 1.4: Add datetime import to `app/routes/payments.py`**

In `app/routes/payments.py`, replace the import block at lines 1-10:

```python
from flask import Blueprint, jsonify, request
import re
import stripe
import os
from datetime import datetime
from ..models import db, Payment, Season, UserSeason, User, Trip, SocialEvent
from ..auth import admin_required
from ..constants import MemberType, StripeEvent, UserStatus, UserSeasonStatus, PaymentType
from ..errors import json_error, json_success
from ..utils import normalize_email, today_central
from ..notifications.slack import send_payment_notification
```

(Only the `from datetime import datetime` line is new.)

- [ ] **Step 1.5: Add the window-check gate inside `create_season_payment_intent`**

In `app/routes/payments.py`, locate `create_season_payment_intent` (currently `def create_season_payment_intent():` near line 465). Find these lines (currently around 477-478):

```python
        user = User.get_by_email(email)
        member_type = MemberType.RETURNING.value if user and user.is_returning else MemberType.NEW.value
```

Immediately AFTER those two lines, insert:

```python
        # Reject if the registration window for this member_type is closed.
        # Prevents stub User rows from being created via the webhook when the
        # form POST would have rejected the registration anyway.
        if not season.is_open_for(member_type.lower(), datetime.utcnow()):
            return json_error(
                f"Registration for {member_type.lower()} members is not currently open."
            )
```

Note: `season` is already in scope from the earlier `season = Season.query.get(season_id)` lookup.

- [ ] **Step 1.6: Run the tests, verify they pass**

Run:

```bash
source env/bin/activate && pytest tests/routes/test_payments.py -v
```

Expected: both tests PASS.

- [ ] **Step 1.7: Run the full test suite to confirm nothing regressed**

Run:

```bash
source env/bin/activate && pytest -q
```

Expected: all tests pass (124 existing + 2 new = 126).

- [ ] **Step 1.8: Commit**

```bash
git add app/routes/payments.py tests/routes/__init__.py tests/routes/test_payments.py
git commit -m "$(cat <<'EOF'
fix: block payment-intent creation when registration window is closed

Prevents stub User rows when a NEW member tries to register before the
new-member window opens (or vice versa). The form POST already rejects
the request, but Stripe was being called first, the webhook fired, and
a stub User + held PaymentIntent were left behind.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Create the cleanup script

**Files:**
- Create: `scripts/cleanup_stub_registrations.py`

- [ ] **Step 2.1: Create the script**

Create `scripts/cleanup_stub_registrations.py`:

```python
#!/usr/bin/env python3
"""Clean up stub User registrations for a given season.

A "stub" registration is a UserSeason whose linked User has none of:
date_of_birth, phone, tshirt_size, emergency_contact_name. These rows
result from the legacy bug where a Stripe payment-intent webhook created
a User row before the form POST submitted personal info — when the form
POST then failed (e.g., closed registration window), the User stayed in
that empty state and the PaymentIntent stayed in 'requires_capture'.

For each stub the script:
  1. Prints user, user_season, and linked Payment details.
  2. Prompts y/N.
  3. On 'y':
     - If a linked Payment exists with Stripe status 'requires_capture',
       cancels the PaymentIntent in Stripe and updates Payment.status.
     - Deletes the UserSeason row.
     - Deletes the User row only if there are no other user_seasons
       and no other payments. Otherwise leaves the User intact.
  4. Commits per user so partial runs are safe.

Usage:
    python scripts/cleanup_stub_registrations.py <season_id>

Set DATABASE_URL in env (or .env) before running. For production:
    DATABASE_URL=postgresql://... python scripts/cleanup_stub_registrations.py 4
"""

import os
import sys

import stripe
from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.models import db, User, UserSeason, Payment, Season


def find_stub_user_seasons(season_id):
    """Return UserSeason rows for the season whose User has no personal info."""
    return (
        UserSeason.query
        .join(User, User.id == UserSeason.user_id)
        .filter(UserSeason.season_id == season_id)
        .filter(User.date_of_birth.is_(None))
        .filter((User.phone.is_(None)) | (User.phone == ''))
        .filter((User.tshirt_size.is_(None)) | (User.tshirt_size == ''))
        .filter((User.emergency_contact_name.is_(None)) | (User.emergency_contact_name == ''))
        .all()
    )


def find_linked_payment(user, season_id):
    """Find the most recent Payment for this user+season, by user_id or email."""
    by_user = (
        Payment.query
        .filter_by(user_id=user.id, season_id=season_id)
        .order_by(Payment.created_at.desc())
        .first()
    )
    if by_user:
        return by_user
    return (
        Payment.query
        .filter_by(email=user.email, season_id=season_id)
        .order_by(Payment.created_at.desc())
        .first()
    )


def cancel_payment_intent(payment):
    """Cancel the Stripe PaymentIntent if it's still in requires_capture.

    Returns the new local Payment.status value (or current value if no change).
    """
    if not payment:
        return None
    try:
        intent = stripe.PaymentIntent.retrieve(payment.payment_intent_id)
    except stripe.error.StripeError as exc:
        print(f"    Stripe retrieve failed: {exc}")
        return payment.status
    print(f"    Stripe status: {intent.status}")
    if intent.status != 'requires_capture':
        print(f"    Not capturable; leaving as-is.")
        return payment.status
    try:
        cancelled = stripe.PaymentIntent.cancel(payment.payment_intent_id)
        print(f"    Cancelled. New Stripe status: {cancelled.status}")
        return cancelled.status
    except stripe.error.StripeError as exc:
        print(f"    Stripe cancel failed: {exc}")
        return payment.status


def cleanup_one(user_season):
    """Cancel hold, delete UserSeason, and conditionally delete User."""
    user = user_season.user
    payment = find_linked_payment(user, user_season.season_id)

    print(f"\nUser #{user.id}  {user.email}  ({user.first_name} {user.last_name})")
    print(f"  UserSeason: season={user_season.season_id} status={user_season.status} type={user_season.registration_type}")
    if payment:
        print(f"  Payment #{payment.id}: ${payment.amount/100:.2f} status={payment.status} pi={payment.payment_intent_id}")
    else:
        print("  Payment: (none found)")

    confirm = input("  Cancel + delete this stub? (y/N): ").strip().lower()
    if confirm != 'y':
        print("  Skipped.")
        return

    if payment:
        new_status = cancel_payment_intent(payment)
        if new_status and new_status != payment.status:
            payment.status = new_status

    db.session.delete(user_season)

    other_seasons = UserSeason.query.filter(
        UserSeason.user_id == user.id,
        UserSeason.season_id != user_season.season_id,
    ).count()
    other_payments = Payment.query.filter(
        Payment.user_id == user.id,
    ).count()
    if other_seasons == 0 and other_payments == 0:
        db.session.delete(user)
        print(f"  Deleted User #{user.id} and UserSeason.")
    else:
        print(
            f"  Deleted UserSeason. Kept User #{user.id} "
            f"(other_seasons={other_seasons}, other_payments={other_payments})."
        )

    db.session.commit()


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/cleanup_stub_registrations.py <season_id>")
        sys.exit(1)
    try:
        season_id = int(sys.argv[1])
    except ValueError:
        print("season_id must be an integer")
        sys.exit(1)

    stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
    if not stripe.api_key:
        print("STRIPE_SECRET_KEY is not set")
        sys.exit(1)

    app = create_app()
    with app.app_context():
        season = Season.query.get(season_id)
        if not season:
            print(f"Season #{season_id} not found")
            sys.exit(1)
        print(f"Scanning Season #{season.id} '{season.name}' for stub registrations...")

        stubs = find_stub_user_seasons(season_id)
        if not stubs:
            print("No stub registrations found.")
            return

        print(f"Found {len(stubs)} stub registration(s).")
        for us in stubs:
            try:
                cleanup_one(us)
            except Exception as exc:
                db.session.rollback()
                print(f"  ERROR: {exc}")
                continue


if __name__ == '__main__':
    main()
```

- [ ] **Step 2.2: Smoke-test the script against the local dev database**

Verify the script imports and shows usage without crashing.

Run:

```bash
source env/bin/activate && python scripts/cleanup_stub_registrations.py
```

Expected: Prints `Usage: python scripts/cleanup_stub_registrations.py <season_id>` and exits 1.

Run:

```bash
source env/bin/activate && python scripts/cleanup_stub_registrations.py 99999
```

Expected: Prints `Season #99999 not found` and exits 1. (If your local dev DB has no `seasons` rows yet, this still verifies the import path and the Season lookup branch.)

- [ ] **Step 2.3: Commit**

```bash
git add scripts/cleanup_stub_registrations.py
git commit -m "$(cat <<'EOF'
chore: add cleanup script for stub season registrations

One-shot script that finds UserSeason rows whose linked User has no
personal info, cancels the held Stripe PaymentIntent, and deletes the
orphan rows. Used to remediate stubs left behind by the pre-fix bug.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Production rollout (manual checklist — do not automate)

**Files:** none (operational steps; do not commit anything)

- [ ] **Step 3.1: Confirm deploy of Task 1 reached production**

Render auto-deploys on merges to `main` (see `Procfile` and `scripts/release.sh`). Confirm the latest deploy in Render dashboard includes the new commit from Task 1 before proceeding.

- [ ] **Step 3.2: Re-verify the three stubs are still present in production**

Run from the local machine, with the production database URL pointed at the same DB used in `test_practice_post.py`:

```bash
source env/bin/activate && python -c "
import psycopg2
conn = psycopg2.connect('postgresql://heidi:c1y7XzSne5jVDEOVRBy4ODUoHWDJv8jK@dpg-d4nrbauuk2gs73frosqg-a.oregon-postgres.render.com/tcsc_trips_db_6k97')
cur = conn.cursor()
cur.execute('''
SELECT u.id, u.email, u.first_name, u.last_name
FROM user_seasons us JOIN users u ON u.id = us.user_id
WHERE us.season_id = 4
  AND u.date_of_birth IS NULL
  AND (u.phone IS NULL OR u.phone = '')
  AND (u.tshirt_size IS NULL OR u.tshirt_size = '')
  AND (u.emergency_contact_name IS NULL OR u.emergency_contact_name = '');
''')
for r in cur.fetchall(): print(r)
"
```

Expected output (3 rows):

```
(265, 'scottjetsettrainer@gmail.com', 'Scott', 'Darragh')
(266, 'waldooutside@gmail.com', 'Bradley', 'Waldorf')
(267, 'marie.alundgren@gmail.com', 'Marie Amie', 'Lundgren')
```

If the row count differs, STOP and reassess before running the cleanup script.

- [ ] **Step 3.3: Run the cleanup script against production**

(The script bootstraps its own sys.path so PYTHONPATH does not need to be set.)

Run:

```bash
source env/bin/activate && \
DATABASE_URL='postgresql://heidi:c1y7XzSne5jVDEOVRBy4ODUoHWDJv8jK@dpg-d4nrbauuk2gs73frosqg-a.oregon-postgres.render.com/tcsc_trips_db_6k97' \
python scripts/cleanup_stub_registrations.py 4
```

For each of the three users, review the printed details and confirm with `y`. Expected per user:
- Stripe status reported as `requires_capture`.
- After confirmation: `Cancelled. New Stripe status: canceled`.
- `Deleted User #<id> and UserSeason.`

- [ ] **Step 3.4: Verify cleanup**

Re-run the verification query from Step 3.2. Expected output: 0 rows.

- [ ] **Step 3.5: Send outreach emails (manual)**

- Scott (`scottjetsettrainer@gmail.com`): explain that a partial registration attempt was cleaned up, no charge was made, and ask him to register once the new-member window opens (May 2 21:00 CT).
- Marie (`marie.alundgren@gmail.com`): same message as Scott.
- Bradley (`waldooutside@gmail.com`): confirm that the duplicate authorization on this email has been voided; his real registration under `bmwaldorf54@gmail.com` is fine, no action needed.

- [ ] **Step 3.6: Mark complete**

Verify in the admin Members grid that no Season-4 user shows up with empty info. The fix is done.

---

## Self-Review Notes

- **Spec coverage:** Part 1 (close the door) → Task 1. Part 2 (cleanup script) → Task 2. Part 3 (outreach) → Task 3. Test plan from spec (unit test + manual verification) → Steps 1.2–1.7. Rollout sequence from spec → Task 3 ordering. Risks (Stripe cancel failure, cascade) → script's try/except and `other_seasons/other_payments` guard.
- **No placeholders:** every step has the literal code or command and expected output.
- **Type consistency:** `stripe.PaymentIntent` API matches Stripe SDK. `Season.is_open_for` signature `(member_type: str, when: datetime)` matches `app/models.py:289`. `UserSeason` join via `User.id == UserSeason.user_id` matches the `user_seasons.user_id` PK.
