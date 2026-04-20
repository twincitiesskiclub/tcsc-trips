# Registration UX Critical Fixes — Design Spec

## Context

10-agent validation audit of the registration system identified 6 critical UX issues that must be fixed before opening season membership registration. These are all user-facing problems that would confuse or block real members during signup.

## Fix 1: Import `_registration.css`

**Problem:** `app/static/css/styles/components/_registration.css` (220 lines) exists but is never imported in `main.css`. All registration-specific styling is dead code.

**Change:** Add one line to `app/static/css/styles/main.css`:
```css
@import 'components/_registration.css';
```
Add it after `_buttons.css` (line 7) since registration styles depend on form and button base styles.

**Files:** `app/static/css/styles/main.css`

---

## Fix 2: Flash Message Rendering

**Problem:** `season_register.html` never calls `get_flashed_messages()`. Server-side validation errors (wrong member type, closed window, bad DOB, etc.) flash errors and redirect, but users see nothing.

**Change:** Add a flash message block at the top of the form container (before the `<form>` element), inside `.sr-form-container`. Render errors with a visible red alert style.

```html
{% with messages = get_flashed_messages(with_categories=true) %}
  {% if messages %}
    <div class="registration-notice" style="background: #fde8e8; border-left-color: #e53e3e;">
      <i style="color: #e53e3e;">!</i>
      <div>
        {% for category, message in messages %}
          <p style="color: #c53030;">{{ message }}</p>
        {% endfor %}
      </div>
    </div>
  {% endif %}
{% endwith %}
```

Uses the existing `.registration-notice` class from `_registration.css` (which will now be loaded via Fix 1) with inline color overrides for error state. No new CSS file needed.

**Files:** `app/templates/season_register.html`

---

## Fix 3: Client-Side Required Field Check Before Payment

**Problem:** The form submit handler in `script.js` proceeds directly to Stripe payment intent creation without checking if required fields are filled. Users get charged/held even with blank required fields.

**Change:** Add a validation function that runs BEFORE `createPaymentIntent()` in the submit handler. It checks all `[required]` inputs/selects in the form:
- For text/email/tel/date inputs: value must be non-empty after trim
- For radio groups: at least one in each `name` group must be checked
- For checkboxes: must be checked
- For selects: value must be non-empty

On failure:
- Add a `field-error` CSS class to invalid fields (red border)
- Show a message in the existing `#card-errors` element: "Please fill in all required fields before submitting."
- Reset `isSubmitting` and button state so user can fix and retry
- Do NOT proceed to Stripe

On valid:
- Remove any `field-error` classes
- Proceed with existing payment flow

Add `.field-error` style to `_registration.css`:
```css
.field-error {
  border-color: #e53e3e !important;
  box-shadow: 0 0 0 1px #e53e3e;
}
```

**Files:** `app/static/script.js`, `app/static/css/styles/components/_registration.css`

---

## Fix 4: Loading Spinner on Submit Button

**Problem:** The submit button only gets `disabled` during payment processing (5-10 seconds). No visual feedback that anything is happening.

**Change:** Update the button HTML to include a spinner and text wrapper:
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

Also change the button class from `sr-button` to `registration-button` (which already has proper styling in `_registration.css`).

Update `toggleLoadingState()` in `script.js` to swap visibility:
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

Add spin animation to `_registration.css`:
```css
.spin {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
```

**Files:** `app/templates/season_register.html`, `app/static/script.js`, `app/static/css/styles/components/_registration.css`

---

## Fix 5: PaymentIntent Description

**Problem:** No `description` parameter on `stripe.PaymentIntent.create()`. Receipts show just an amount with no context.

**Change:** Add `description` to the season payment intent creation in `app/routes/payments.py`:
```python
intent = stripe.PaymentIntent.create(
    amount=season.price_cents,
    currency='usd',
    capture_method=capture_method,
    receipt_email=email,
    description=f"TCSC {season.name} Membership",
    metadata={...}
)
```

The description appears on Stripe receipts and in the Stripe dashboard. Keep it short and human-readable.

**Files:** `app/routes/payments.py` (line ~471)

---

## Fix 6: Improved Success Page

**Problem:** New members get no confirmation at registration time. Success page has minimal info.

**Change:** Pass additional context from the registration route to the success template:
- `amount_display` — formatted dollar amount (e.g., "$150.00")
- `member_type` — "new" or "returning"
- `season` — already passed

Update `registration.py` (around line 158):
```python
amount_display = f"${season.price_cents / 100:.2f}" if season.price_cents else None
return render_template('season_success.html',
    season=season,
    payment_hold=payment_hold,
    amount_display=amount_display,
    member_type=member_type
)
```

Update `season_success.html` to show:
- Amount held/charged
- Clear next-steps messaging per member type
- "Save this page" suggestion for new members
- Registration date

New member message: "A hold of {amount} has been placed on your card. Your card will NOT be charged until your membership is confirmed. You'll receive a receipt email at that time."

Returning member message: "Your card has been charged {amount}. Your membership is confirmed for {season.name}. You'll receive a receipt from Stripe shortly."

Both: contact email, back-to-home button (styled properly with `registration-button` class or inline styles since `_registration.css` will be loaded).

**Files:** `app/routes/registration.py`, `app/templates/season_success.html`

---

## Out of Scope

- Transactional email service (deferred)
- `statement_descriptor` (nice-to-have, not launch-blocking)
- Duplicate registration guard (Tier 2 fix, separate spec)
- Full client-side validation matching server rules (chose minimal approach)
- CSRF protection (Tier 2, separate spec)
