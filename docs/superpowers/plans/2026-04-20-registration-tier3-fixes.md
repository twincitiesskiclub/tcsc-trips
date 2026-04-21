# Registration Tier 3 Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Six independent polish/security fixes from the registration validation audit — statement descriptors, Central time display, autocomplete attributes, open redirect fix, refund pending status, and cardholder autocomplete.

**Architecture:** All fixes are independent single-file or two-file changes. No new models, no migrations, no new dependencies. The fixes touch `payments.py`, `auth.py`, `__init__.py`, `index.html`, `season_detail.html`, and `season_register.html`.

**Tech Stack:** Flask, Stripe API, Jinja2 template filters, pytz (already in use)

---

### Task 1: Statement Descriptor on PaymentIntents

**Files:**
- Modify: `app/routes/payments.py:1-2` (add `import re`)
- Modify: `app/routes/payments.py:17-59` (trip PaymentIntent — add descriptor + description)
- Modify: `app/routes/payments.py:485-498` (season PaymentIntent — add descriptor)
- Modify: `app/routes/payments.py:532-544` (social PaymentIntent — add descriptor + description)

- [ ] **Step 1: Add helper function and import**

At the top of `app/routes/payments.py`, add `import re` to the imports, then add the helper function before the first route:

```python
import re

def build_statement_descriptor(payment_type, identifier):
    prefix = f"TCSC_{payment_type}_"
    sanitized = re.sub(r'[^A-Z0-9_ .\-]', '', identifier.upper())
    return (prefix + sanitized)[:22]
```

Place this function after the `payments = Blueprint(...)` line and before the first `@payments.route`.

- [ ] **Step 2: Add descriptor to trip PaymentIntent**

In the `create_payment()` function, add `statement_descriptor` and `description` to the `stripe.PaymentIntent.create()` call. Find:

```python
        intent = stripe.PaymentIntent.create(
            amount=int(amount * 100),  # Convert to cents
            currency='usd',
            capture_method='manual',  # Always manual for trips (lottery system)
            receipt_email=email,
```

Replace with:

```python
        intent = stripe.PaymentIntent.create(
            amount=int(amount * 100),  # Convert to cents
            currency='usd',
            capture_method='manual',  # Always manual for trips (lottery system)
            receipt_email=email,
            statement_descriptor=build_statement_descriptor('TRIP', trip.name if trip else 'UNKNOWN'),
            description=f"TCSC Trip - {trip.name}" if trip else "TCSC Trip Registration",
```

- [ ] **Step 3: Add descriptor to season PaymentIntent**

In the `create_season_payment_intent()` function, find:

```python
        intent = stripe.PaymentIntent.create(
            amount=season.price_cents,
            currency='usd',
            capture_method=capture_method,
            receipt_email=email,
            description=f"TCSC {season.name} Membership",
```

Replace with:

```python
        intent = stripe.PaymentIntent.create(
            amount=season.price_cents,
            currency='usd',
            capture_method=capture_method,
            receipt_email=email,
            statement_descriptor=build_statement_descriptor('SEASON', str(season.year)),
            description=f"TCSC {season.name} Membership",
```

- [ ] **Step 4: Add descriptor and description to social event PaymentIntent**

In the `create_social_event_payment_intent()` function, find:

```python
        intent = stripe.PaymentIntent.create(
            amount=social_event.price,
            currency='usd',
            capture_method='automatic',  # Immediate charge - no lottery
            receipt_email=email,
```

Replace with:

```python
        intent = stripe.PaymentIntent.create(
            amount=social_event.price,
            currency='usd',
            capture_method='automatic',  # Immediate charge - no lottery
            receipt_email=email,
            statement_descriptor=build_statement_descriptor('SOCIAL', social_event.name),
            description=f"TCSC Social Event - {social_event.name}",
```

- [ ] **Step 5: Commit**

```bash
git add app/routes/payments.py
git commit -m "feat: add statement descriptors and descriptions to PaymentIntents"
```

---

### Task 2: Central Time Display for Registration Windows

**Files:**
- Modify: `app/__init__.py:71-102` (add template filter)
- Modify: `app/templates/index.html:42,45,48,50` (replace UTC with filter)
- Modify: `app/templates/season_detail.html:60,63,66,68` (replace UTC with filter)

- [ ] **Step 1: Add central_time template filter**

In `app/__init__.py`, inside the `register_template_filters(app)` function, add the following after the existing `format_date` filter (after line 102):

```python
    @app.template_filter('central_time')
    def central_time_filter(dt, fmt='%b %d, %Y %I:%M %p CT'):
        from .utils import format_datetime_central
        return format_datetime_central(dt, fmt)
```

- [ ] **Step 2: Update index.html — replace 4 UTC occurrences**

In `app/templates/index.html`, replace each of these 4 lines:

Line 42 — find:
```html
<span class="sub-status">Returning member window closes {{ season.returning_end.strftime('%b %d, %Y %I:%M %p UTC') }}.</span>
```
Replace with:
```html
<span class="sub-status">Returning member window closes {{ season.returning_end|central_time }}.</span>
```

Line 45 — find:
```html
<span class="sub-status">New member window closes {{ season.new_end.strftime('%b %d, %Y %I:%M %p UTC') }}.</span>
```
Replace with:
```html
<span class="sub-status">New member window closes {{ season.new_end|central_time }}.</span>
```

Line 48 — find:
```html
<span class="status-upcoming">Registration opens for returning members on {{ season.returning_start.strftime('%b %d, %Y %I:%M %p UTC') }}.</span>
```
Replace with:
```html
<span class="status-upcoming">Registration opens for returning members on {{ season.returning_start|central_time }}.</span>
```

Line 50 — find:
```html
<span class="status-upcoming">Registration opens for new members on {{ season.new_start.strftime('%b %d, %Y %I:%M %p UTC') }}.</span>
```
Replace with:
```html
<span class="status-upcoming">Registration opens for new members on {{ season.new_start|central_time }}.</span>
```

- [ ] **Step 3: Update season_detail.html — replace 4 UTC occurrences**

In `app/templates/season_detail.html`, make the same 4 replacements:

Line 60 — find:
```html
<span class="sub-status">Returning member window closes {{ season.returning_end.strftime('%b %d, %Y %I:%M %p UTC') }}.</span>
```
Replace with:
```html
<span class="sub-status">Returning member window closes {{ season.returning_end|central_time }}.</span>
```

Line 63 — find:
```html
<span class="sub-status">New member window closes {{ season.new_end.strftime('%b %d, %Y %I:%M %p UTC') }}.</span>
```
Replace with:
```html
<span class="sub-status">New member window closes {{ season.new_end|central_time }}.</span>
```

Line 66 — find:
```html
<span class="status-upcoming">Registration opens for returning members on {{ season.returning_start.strftime('%b %d, %Y %I:%M %p UTC') }}.</span>
```
Replace with:
```html
<span class="status-upcoming">Registration opens for returning members on {{ season.returning_start|central_time }}.</span>
```

Line 68 — find:
```html
<span class="status-upcoming">Registration opens for new members on {{ season.new_start.strftime('%b %d, %Y %I:%M %p UTC') }}.</span>
```
Replace with:
```html
<span class="status-upcoming">Registration opens for new members on {{ season.new_start|central_time }}.</span>
```

- [ ] **Step 4: Commit**

```bash
git add app/__init__.py app/templates/index.html app/templates/season_detail.html
git commit -m "fix: display registration window times in Central instead of UTC"
```

---

### Task 3: Autocomplete Attributes on Registration Form

**Files:**
- Modify: `app/templates/season_register.html` (10 input fields)

- [ ] **Step 1: Add autocomplete to personal info fields**

In `app/templates/season_register.html`, update these 4 inputs:

Find:
```html
<input class="sr-input" type="text" id="firstName" name="firstName" placeholder="First Name" required>
```
Replace with:
```html
<input class="sr-input" type="text" id="firstName" name="firstName" placeholder="First Name" autocomplete="given-name" required>
```

Find:
```html
<input class="sr-input" type="text" id="lastName" name="lastName" placeholder="Last Name" required>
```
Replace with:
```html
<input class="sr-input" type="text" id="lastName" name="lastName" placeholder="Last Name" autocomplete="family-name" required>
```

Find:
```html
<input class="sr-input" type="date" id="dob" name="dob" placeholder="Date of Birth" required>
```
Replace with:
```html
<input class="sr-input" type="date" id="dob" name="dob" placeholder="Date of Birth" autocomplete="bday" required>
```

Find:
```html
<input class="sr-input" type="tel" id="phone" name="phone" placeholder="Phone Number" required>
```
Replace with:
```html
<input class="sr-input" type="tel" id="phone" name="phone" placeholder="Phone Number" autocomplete="tel" required>
```

- [ ] **Step 2: Add autocomplete="off" to emergency contact fields**

Find:
```html
<input class="sr-input" type="text" id="emergencyName" name="emergencyName" placeholder="Contact's Full Name" required>
```
Replace with:
```html
<input class="sr-input" type="text" id="emergencyName" name="emergencyName" placeholder="Contact's Full Name" autocomplete="off" required>
```

Find:
```html
<input class="sr-input" type="text" id="emergencyRelation" name="emergencyRelation" placeholder="Relationship" required>
```
Replace with:
```html
<input class="sr-input" type="text" id="emergencyRelation" name="emergencyRelation" placeholder="Relationship" autocomplete="off" required>
```

Find:
```html
<input class="sr-input" type="tel" id="emergencyPhone" name="emergencyPhone" placeholder="Contact's Phone Number" required>
```
Replace with:
```html
<input class="sr-input" type="tel" id="emergencyPhone" name="emergencyPhone" placeholder="Contact's Phone Number" autocomplete="off" required>
```

Find:
```html
<input class="sr-input" type="email" id="emergencyEmail" name="emergencyEmail" placeholder="Contact's Email Address" required>
```
Replace with:
```html
<input class="sr-input" type="email" id="emergencyEmail" name="emergencyEmail" placeholder="Contact's Email Address" autocomplete="off" required>
```

- [ ] **Step 3: Fix cardholder autocomplete (Fix 25)**

In the same file, find:
```html
<input class="sr-input" type="text" id="name" name="name" placeholder="Full Name" autocomplete="cardholder" required />
```
Replace with:
```html
<input class="sr-input" type="text" id="name" name="name" placeholder="Full Name" autocomplete="cc-name" required />
```

- [ ] **Step 4: Commit**

```bash
git add app/templates/season_register.html
git commit -m "fix: add standard autocomplete attributes to registration form inputs"
```

---

### Task 4: Open Redirect in OAuth Login

**Files:**
- Modify: `app/routes/auth.py:1-12` (add validation, apply to login route)

- [ ] **Step 1: Add URL validation and apply to login route**

In `app/routes/auth.py`, add the validation function and update the login route. Find:

```python
@auth.route('/login')
def login():
    session['next_url'] = request.args.get('next') or url_for('admin.get_admin_page')
```

Replace with:

```python
def _is_safe_redirect_url(url):
    return bool(url) and url.startswith('/') and not url.startswith('//') and '://' not in url

@auth.route('/login')
def login():
    next_url = request.args.get('next')
    session['next_url'] = next_url if _is_safe_redirect_url(next_url) else url_for('admin.get_admin_page')
```

- [ ] **Step 2: Commit**

```bash
git add app/routes/auth.py
git commit -m "fix: validate OAuth next_url to prevent open redirect"
```

---

### Task 5: Stripe Refund Pending Status

**Files:**
- Modify: `app/routes/payments.py:304-305` (individual refund)
- Modify: `app/routes/payments.py:427-429` (bulk refund)

- [ ] **Step 1: Fix individual refund handler**

In `app/routes/payments.py`, find the individual refund check:

```python
            if refund.status != 'succeeded':
                return json_error(f'Refund failed - status: {refund.status}')
```

Replace with:

```python
            if refund.status not in ('succeeded', 'pending'):
                return json_error(f'Refund failed - status: {refund.status}')
```

- [ ] **Step 2: Fix bulk refund handler**

In the same file, find the bulk refund check:

```python
                    if refund.status != 'succeeded':
                        results.append({'id': payment_id, 'success': False, 'error': f'Refund failed - status: {refund.status}'})
                        continue
```

Replace with:

```python
                    if refund.status not in ('succeeded', 'pending'):
                        results.append({'id': payment_id, 'success': False, 'error': f'Refund failed - status: {refund.status}'})
                        continue
```

- [ ] **Step 3: Commit**

```bash
git add app/routes/payments.py
git commit -m "fix: accept Stripe refund 'pending' status as success"
```

---

### Task 6: Verify All Changes

- [ ] **Step 1: Run existing tests to verify no regressions**

```bash
cd /Users/rob/env/tcsc-trips
python -m pytest tests/ -v --tb=short
```

Expected: All existing tests pass. None of our changes touch tested code paths.

- [ ] **Step 2: Quick smoke test — verify app starts**

```bash
cd /Users/rob/env/tcsc-trips
source env/bin/activate
FLASK_ENV=development python -c "from app import create_app; app = create_app(); print('App created OK')"
```

Expected: `App created OK` — confirms the template filter registration and payments.py import changes don't break app startup.
