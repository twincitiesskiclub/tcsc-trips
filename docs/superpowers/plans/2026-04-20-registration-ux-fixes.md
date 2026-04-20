# Registration UX Critical Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 6 critical UX issues in the season registration flow before opening membership registration.

**Architecture:** All fixes are targeted edits to existing files — one CSS import, two template updates, one JS validation addition, one JS loading state improvement, and one backend parameter addition. No new files, no new dependencies, no schema changes.

**Tech Stack:** Flask/Jinja2 templates, vanilla JavaScript, CSS, Stripe Python SDK

---

## Task 1: Import `_registration.css` in `main.css`

**Files:**
- Modify: `app/static/css/styles/main.css`

- [ ] **Step 1: Add the import line**

In `app/static/css/styles/main.css`, add the registration component import after the `_buttons.css` import (line 7):

```css
@import 'components/_registration.css';
```

The full file should look like:
```css
@import 'base/_tokens.css';
@import 'base/_reset.css';
@import 'layout/_layout.css';
@import 'components/_header.css';
@import 'components/_trips.css';
@import 'components/_forms.css';
@import 'components/_buttons.css';
@import 'components/_registration.css';
@import 'components/_triathlon.css';
@import 'states/_states.css';
@import 'animations/_animations.css';
@import 'utils/_media-queries.css';
```

- [ ] **Step 2: Verify by loading the registration page**

Run: `./scripts/dev.sh`

Navigate to a season registration page. Verify:
- Form container is wider (~700px max-width, not 480px)
- Fieldsets have no browser-default borders
- Radio groups are left-aligned with proper spacing
- Legends are styled (18px, 600 weight, primary color)
- On mobile (narrow browser), form stacks cleanly with reduced padding

- [ ] **Step 3: Commit**

```bash
git add app/static/css/styles/main.css
git commit -m "fix: import _registration.css in main.css

Registration-specific styling (700px container, fieldset resets,
radio groups, mobile breakpoints) was never loaded."
```

---

## Task 2: Add Flash Message Rendering to Registration Page

**Files:**
- Modify: `app/templates/season_register.html`

- [ ] **Step 1: Add flash message block**

In `app/templates/season_register.html`, insert the following immediately after the opening `<div class="sr-form-container">` tag (line 32) and before the `<form>` tag (line 33):

```html
        <div class="sr-form-container">
          {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
              <div class="registration-notice" style="background: #fde8e8; border-left-color: #e53e3e;">
                <i style="color: #e53e3e;">&#9888;</i>
                <div>
                  {% for category, message in messages %}
                    <p style="color: #c53030; margin: 0;">{{ message }}</p>
                  {% endfor %}
                </div>
              </div>
            {% endif %}
          {% endwith %}
          <form class="sr-payment-form registration-form" ...>
```

- [ ] **Step 2: Verify flash messages display**

Test by temporarily adding a flash in the registration GET handler, or by submitting invalid data that triggers server-side validation (e.g., returning member trying to register as new). Verify:
- Error message appears in a red-bordered notice box above the form
- Text is readable (dark red on light red background)
- Box uses the existing `.registration-notice` layout (flex, gap, left border)

- [ ] **Step 3: Commit**

```bash
git add app/templates/season_register.html
git commit -m "fix: render flash messages on registration page

Server-side validation errors were invisible — flash_error() was
called but the template never rendered get_flashed_messages()."
```

---

## Task 3: Client-Side Required Field Validation Before Stripe Payment

**Files:**
- Modify: `app/static/script.js`
- Modify: `app/static/css/styles/components/_registration.css`

- [ ] **Step 1: Add `.field-error` CSS class**

Append to the end of `app/static/css/styles/components/_registration.css`:

```css
.field-error {
  border-color: #e53e3e !important;
  box-shadow: 0 0 0 1px #e53e3e;
}
```

- [ ] **Step 2: Add validation function in `script.js`**

In `app/static/script.js`, insert the following function inside the `if (registrationForm && document.getElementById('card-element'))` block, after the `showError` function (after line 439):

```javascript
    function validateRequiredFields() {
      let valid = true;
      // Clear previous error highlights
      registrationForm.querySelectorAll('.field-error').forEach(el => {
        el.classList.remove('field-error');
      });

      // Check text/email/tel/date inputs and selects
      registrationForm.querySelectorAll('input[required], select[required]').forEach(field => {
        if (field.type === 'radio') return; // handled separately
        if (field.type === 'checkbox') {
          if (!field.checked) {
            field.classList.add('field-error');
            valid = false;
          }
          return;
        }
        if (!field.value.trim()) {
          field.classList.add('field-error');
          valid = false;
        }
      });

      // Check radio groups — find all required radio names
      const radioNames = new Set();
      registrationForm.querySelectorAll('input[type="radio"][required]').forEach(r => {
        radioNames.add(r.name);
      });
      radioNames.forEach(name => {
        const checked = registrationForm.querySelector(`input[name="${name}"]:checked`);
        if (!checked) {
          registrationForm.querySelectorAll(`input[name="${name}"]`).forEach(r => {
            r.classList.add('field-error');
          });
          valid = false;
        }
      });

      return valid;
    }
```

- [ ] **Step 3: Call validation before payment in submit handler**

In the submit event handler (line 455), add the validation call immediately after `toggleLoadingState(true)` (after line 463) and before the `try` block:

Replace:
```javascript
      showError('');
      isSubmitting = true;
      toggleLoadingState(true);

      try {
        // Get payment info from form
```

With:
```javascript
      showError('');
      isSubmitting = true;
      toggleLoadingState(true);

      // Validate required fields before touching Stripe
      if (!validateRequiredFields()) {
        showError('Please fill in all required fields before submitting.');
        isSubmitting = false;
        toggleLoadingState(false);
        return;
      }

      try {
        // Get payment info from form
```

- [ ] **Step 4: Verify validation works**

Load the registration page, leave required fields empty, click "Register & Pay". Verify:
- Empty fields get a red border
- Error message shows "Please fill in all required fields before submitting."
- No Stripe API call is made (check Network tab)
- Button re-enables so user can fix and retry
- After filling fields, submission proceeds normally

- [ ] **Step 5: Commit**

```bash
git add app/static/script.js app/static/css/styles/components/_registration.css
git commit -m "fix: validate required fields before creating Stripe payment

Previously the form went straight to Stripe payment intent creation
without checking if required fields were filled. Users could get
charged with an invalid form that the server would then reject."
```

---

## Task 4: Loading Spinner on Submit Button

**Files:**
- Modify: `app/templates/season_register.html`
- Modify: `app/static/script.js`
- Modify: `app/static/css/styles/components/_registration.css`

- [ ] **Step 1: Add spin animation to `_registration.css`**

Append to `app/static/css/styles/components/_registration.css` (after the `.field-error` rule from Task 3):

```css
#button-spinner {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
```

- [ ] **Step 2: Update submit button HTML**

In `app/templates/season_register.html`, replace lines 144-146:

```html
            <button type="submit" class="sr-button" id="register-btn">
              <span>Register & Pay</span>
            </button>
```

With:

```html
            <button type="submit" class="registration-button" id="register-btn">
              <span id="button-text">Register & Pay</span>
              <span id="button-spinner" style="display: none;">
                <svg width="20" height="20" viewBox="0 0 20 20" class="spin">
                  <circle cx="10" cy="10" r="8" stroke="currentColor" stroke-width="2" fill="none" stroke-dasharray="40" stroke-dashoffset="10"/>
                </svg>
                Processing...
              </span>
            </button>
```

- [ ] **Step 3: Update `toggleLoadingState()` in `script.js`**

In `app/static/script.js`, replace the `toggleLoadingState` function (lines 441-444):

```javascript
    function toggleLoadingState(isLoading) {
      const btn = document.getElementById('register-btn');
      if (btn) btn.disabled = isLoading;
    }
```

With:

```javascript
    function toggleLoadingState(isLoading) {
      const btn = document.getElementById('register-btn');
      const text = document.getElementById('button-text');
      const spinner = document.getElementById('button-spinner');
      if (btn) btn.disabled = isLoading;
      if (text) text.style.display = isLoading ? 'none' : 'inline';
      if (spinner) spinner.style.display = isLoading ? 'inline-flex' : 'none';
    }
```

- [ ] **Step 4: Verify spinner behavior**

Load registration page, fill in valid data, click submit. Verify:
- Button text changes from "Register & Pay" to spinning icon + "Processing..."
- Button is disabled (can't double-click)
- On error (e.g., invalid card), button reverts to "Register & Pay"
- Animation is smooth (no jank)

- [ ] **Step 5: Commit**

```bash
git add app/templates/season_register.html app/static/script.js app/static/css/styles/components/_registration.css
git commit -m "fix: add loading spinner to registration submit button

Users had no visual feedback during the 5-10 second payment
processing window. Button now shows a spinner and 'Processing...'
text while disabled."
```

---

## Task 5: Add Description to Season PaymentIntent

**Files:**
- Modify: `app/routes/payments.py:471-483`

- [ ] **Step 1: Add `description` parameter**

In `app/routes/payments.py`, find the `stripe.PaymentIntent.create()` call in `create_season_payment_intent` (around line 471). Add the `description` parameter:

Replace:
```python
        intent = stripe.PaymentIntent.create(
            amount=season.price_cents,
            currency='usd',
            capture_method=capture_method,
            receipt_email=email,
            metadata={
```

With:
```python
        intent = stripe.PaymentIntent.create(
            amount=season.price_cents,
            currency='usd',
            capture_method=capture_method,
            receipt_email=email,
            description=f"TCSC {season.name} Membership",
            metadata={
```

- [ ] **Step 2: Verify in Stripe test mode**

Run the dev server, complete a test registration. Check the Stripe Dashboard (test mode) for the new PaymentIntent. Verify:
- The "Description" field shows "TCSC [Season Name] Membership"
- This description will appear on receipt emails sent by Stripe

- [ ] **Step 3: Commit**

```bash
git add app/routes/payments.py
git commit -m "fix: add description to season PaymentIntent

Stripe receipts now show 'TCSC [Season] Membership' instead of
a bare amount with no context."
```

---

## Task 6: Improve Success Page

**Files:**
- Modify: `app/routes/registration.py:156-159`
- Modify: `app/templates/season_success.html`

- [ ] **Step 1: Pass additional context from registration route**

In `app/routes/registration.py`, replace lines 156-159:

```python
            db.session.commit()
            # flash('Registration submitted successfully!', 'success')
            payment_hold = not is_returning
            return render_template('season_success.html', season=season, payment_hold=payment_hold)
```

With:

```python
            db.session.commit()
            payment_hold = not is_returning
            amount_display = f"${season.price_cents / 100:.2f}" if season.price_cents else None
            return render_template('season_success.html',
                season=season,
                payment_hold=payment_hold,
                amount_display=amount_display,
                member_type=member_type
            )
```

- [ ] **Step 2: Update success page template**

Replace the entire contents of `app/templates/season_success.html` with:

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Registration Successful – TCSC</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <link rel="stylesheet" href="{{ url_for('static', filename='css/normalize.css') }}" />
    <link rel="stylesheet" href="{{ url_for('static', filename='css/styles/main.css') }}" />
  </head>
  <body>
    <div class="sr-root">
      <div class="sr-main">
        <header class="sr-header">
          <div class="sr-header__logo">
            <img src="{{ url_for('static', filename='images/tcsc-logo.svg') }}" alt="TCSC Logo">
          </div>
          <h1 class="sr-header__title">Registration Complete</h1>
        </header>
        <div class="sr-form-container">
          <div class="form-section">
            <h2>Thank you for registering!</h2>
            <p>Your registration for <strong>{{ season.name }}</strong> has been received.</p>

            {% if payment_hold %}
              <p>A hold of <strong>{{ amount_display }}</strong> has been placed on your card. Your card will <strong>not</strong> be charged until your membership is confirmed.</p>
              <p>You'll receive a receipt email from Stripe once your membership is confirmed and the charge is processed.</p>
              <p style="background: #f0f4ff; padding: 12px; border-radius: 6px; font-size: 14px;">
                <strong>Tip:</strong> Save this page or take a screenshot for your records.
              </p>
            {% else %}
              <p>Your card has been charged <strong>{{ amount_display }}</strong>. Your membership for <strong>{{ season.name }}</strong> is confirmed!</p>
              <p>You'll receive a receipt from Stripe shortly at the email address you provided.</p>
            {% endif %}

            <p>If you have any questions, please contact <a href="mailto:contact@twincitiesskiclub.org">contact@twincitiesskiclub.org</a>.</p>
          </div>
          <div style="text-align: center; margin-top: 24px;">
            <a href="/" class="registration-button" style="display: inline-block; text-decoration: none; max-width: 300px;">&larr; Back to Home</a>
          </div>
        </div>
      </div>
    </div>
  </body>
</html>
```

- [ ] **Step 3: Verify both member type success pages**

Test with a new member (payment hold) and returning member (immediate charge). Verify:
- New member sees: hold amount, "will not be charged until confirmed," save-page tip
- Returning member sees: charged amount, "membership is confirmed," receipt coming
- "Back to Home" link is styled as a button
- Page looks correct on mobile (narrow viewport)

- [ ] **Step 4: Commit**

```bash
git add app/routes/registration.py app/templates/season_success.html
git commit -m "fix: improve registration success page with payment details

Success page now shows the hold/charge amount, clear next-steps
messaging for new vs returning members, and a save-page tip for
new members who won't get a receipt until capture."
```

---

## Final Verification

- [ ] **Step 1: Full end-to-end test**

With dev server running, complete a full registration flow:
1. Load registration page — verify styling is correct (wide container, clean fieldsets)
2. Click submit with empty fields — verify red borders and error message appear, no Stripe call
3. Fill all fields, click submit — verify spinner shows "Processing..."
4. Complete payment — verify success page shows amount and correct messaging
5. Check Stripe Dashboard — verify PaymentIntent has description "TCSC [Season] Membership"

- [ ] **Step 2: Test error path**

Trigger a server-side validation error (e.g., use a returning member's email but select "New Member" radio). Verify flash message appears in red notice box above the form.
