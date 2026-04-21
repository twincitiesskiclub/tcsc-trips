# Registration Tier 2 Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 6 payment/webhook/validation bugs in the season registration flow before launch.

**Architecture:** All changes are surgical edits to three existing files — no new files, no migrations, no new dependencies. Each fix is independent and can be committed separately.

**Tech Stack:** Flask, SQLAlchemy, Stripe API, PostgreSQL

---

### Task 1: Canceled webhook cleans up UserSeason

**Files:**
- Modify: `app/routes/payments.py:208-213`

- [ ] **Step 1: Update the PAYMENT_CANCELED handler**

Replace lines 208-213 with:

```python
        elif event_type == StripeEvent.PAYMENT_CANCELED:
            payment = Payment.get_by_payment_intent(data_object.id)
            if payment:
                payment.status = 'canceled'
                if payment.payment_type == PaymentType.SEASON and payment.season_id:
                    user = User.get_by_email(payment.email)
                    if user:
                        user_season = UserSeason.get_for_user_season(user.id, payment.season_id)
                        if user_season:
                            user_season.status = UserSeasonStatus.DROPPED_VOLUNTARY
                            user.sync_status()
                db.session.commit()
```

- [ ] **Step 2: Verify the app starts**

Run: `python -c "from app import create_app; app = create_app(); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/routes/payments.py
git commit -m "fix: clean up UserSeason when payment hold is canceled"
```

---

### Task 2: Duplicate registration guard

**Files:**
- Modify: `app/routes/payments.py:449-495` (`create_season_payment_intent`)

- [ ] **Step 1: Add duplicate check before Stripe call**

After the `member_type` derivation (after line 463) and before the capture method logic (before line 465), add:

```python
        existing_payment = Payment.query.filter(
            Payment.email == email,
            Payment.season_id == int(season_id),
            Payment.status.notin_(['canceled', 'refunded'])
        ).first()
        if existing_payment:
            return json_error('You have already registered for this season.')
```

- [ ] **Step 2: Verify the app starts**

Run: `python -c "from app import create_app; app = create_app(); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/routes/payments.py
git commit -m "fix: prevent duplicate season payment intents"
```

---

### Task 3: Require payment_intent_id on registration POST

**Files:**
- Modify: `app/routes/registration.py:65-69`

- [ ] **Step 1: Add required check for payment_intent_id**

Replace lines 65-69 with:

```python
            payment_intent_id = form.get('payment_intent_id')
            if not payment_intent_id:
                flash_error('Payment is required to complete registration.')
                return redirect(url_for('registration.season_register', season_id=season_id))
            existing_payment = Payment.get_by_payment_intent(payment_intent_id)
```

- [ ] **Step 2: Verify the app starts**

Run: `python -c "from app import create_app; app = create_app(); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/routes/registration.py
git commit -m "fix: require payment_intent_id for registration"
```

---

### Task 4: Webhook returns 500 on errors

**Files:**
- Modify: `app/routes/payments.py:217-218`

- [ ] **Step 1: Change error response to 500**

Replace lines 217-218 with:

```python
    except Exception as e:
        return json_error('Webhook processing failed', 500)
```

- [ ] **Step 2: Verify the app starts**

Run: `python -c "from app import create_app; app = create_app(); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/routes/payments.py
git commit -m "fix: return 500 on webhook errors for Stripe retries"
```

---

### Task 5: Align validation constants to DB columns

**Files:**
- Modify: `app/constants.py:68,70`

- [ ] **Step 1: Update the constants**

Change line 68 from `MAX_PHONE_LENGTH = 30` to:
```python
MAX_PHONE_LENGTH = 20
```

Change line 70 from `MAX_RELATION_LENGTH = 100` to:
```python
MAX_RELATION_LENGTH = 50
```

- [ ] **Step 2: Verify the app starts**

Run: `python -c "from app import create_app; app = create_app(); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/constants.py
git commit -m "fix: align validation constants to DB column sizes"
```

---

### Task 6: Fail-closed webhook signature verification

**Files:**
- Modify: `app/routes/payments.py:62-78`

- [ ] **Step 1: Add production guard**

Replace lines 62-78 with:

```python
def webhook_received():
    webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
    request_data = request.get_json()

    try:
        if webhook_secret:
            signature = request.headers.get('stripe-signature')
            event = stripe.Webhook.construct_event(
                payload=request.data,
                sig_header=signature,
                secret=webhook_secret
            )
            data = event['data']
        elif os.getenv('FLASK_ENV') == 'development':
            data = request_data['data']
            event = request_data
        else:
            return json_error('Webhook signature verification not configured', 500)
```

- [ ] **Step 2: Verify the app starts**

Run: `python -c "from app import create_app; app = create_app(); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/routes/payments.py
git commit -m "fix: reject unverified webhooks outside development"
```
