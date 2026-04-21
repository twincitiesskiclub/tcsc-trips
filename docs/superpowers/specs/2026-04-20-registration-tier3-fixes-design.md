# Registration Tier 3 Fixes — Design Spec

Six independent polish/security fixes from the 10-agent registration validation audit.

## Fix 14: Statement Descriptor on PaymentIntents

**Pattern:** `TCSC_SEASON_2026`, `TCSC_TRIP_BIRKIE`, `TCSC_SOCIAL_YOGA`

Stripe limits `statement_descriptor` to 22 characters. Only allows alphanumeric, spaces, and `_`, `-`, `.`.

**Helper function** in `payments.py`:

```python
def build_statement_descriptor(payment_type, identifier):
    prefix = f"TCSC_{payment_type}_"
    sanitized = re.sub(r'[^A-Z0-9_ .-]', '', identifier.upper())
    descriptor = (prefix + sanitized)[:22]
    return descriptor
```

**Apply to all three PaymentIntent.create() calls:**
- Season: `build_statement_descriptor("SEASON", str(season.year))` → `TCSC_SEASON_2026`
- Trip: `build_statement_descriptor("TRIP", trip.name)` → `TCSC_TRIP_BIRKIE` (truncated at 22)
- Social: `build_statement_descriptor("SOCIAL", social_event.name)` → `TCSC_SOCIAL_YOGA`

Also add `description` to trip and social event intents (season already has one from Tier 2 fix):
- Trip: `f"TCSC Trip - {trip.name}"`
- Social: `f"TCSC Social Event - {social_event.name}"`

**Files:** `app/routes/payments.py`

## Fix 20: Central Time Display for Registration Windows

Register `format_datetime_central` from `app/utils.py` as a Jinja template filter named `central_time`. The function already handles naive-UTC-to-Central conversion.

**In `app/__init__.py`:**
```python
@app.template_filter('central_time')
def central_time_filter(dt, fmt='%b %d, %Y %I:%M %p CT'):
    return format_datetime_central(dt, fmt)
```

**Replace in templates** (8 occurrences total):
- `index.html` lines 42, 45, 48, 50: Change `season.X.strftime('%b %d, %Y %I:%M %p UTC')` to `season.X|central_time`
- `season_detail.html` lines 60, 63, 66, 68: Same replacement

Display format: `"Oct 15, 2026 11:59 PM CT"` — uses "CT" instead of timezone-aware "%Z" (which would show "CDT"/"CST" depending on DST) to keep it simple for members.

**Files:** `app/__init__.py`, `app/templates/index.html`, `app/templates/season_detail.html`

## Fix 21: Autocomplete Attributes on Registration Form

Add standard HTML autocomplete attributes to `season_register.html` inputs:

| Input | Current | New `autocomplete` |
|-------|---------|-------------------|
| `firstName` | (none) | `given-name` |
| `lastName` | (none) | `family-name` |
| `phone` | (none) | `tel` |
| `dob` | (none) | `bday` |
| `pronouns` | (none) | (leave as-is, no standard value) |
| `tshirtSize` | (none) | (leave as-is, no standard value) |
| `emergencyName` | (none) | `off` |
| `emergencyRelation` | (none) | `off` |
| `emergencyPhone` | (none) | `off` |
| `emergencyEmail` | (none) | `off` |

Emergency contact fields use `off` to prevent browsers from autofilling the user's own info into contact fields.

**Files:** `app/templates/season_register.html`

## Fix 23: Open Redirect in OAuth Login

Validate `next` parameter in `auth.py` login route. Only accept relative URLs (start with `/`, don't start with `//`, don't contain `://`).

```python
def is_safe_redirect_url(url):
    if not url:
        return False
    return url.startswith('/') and not url.startswith('//') and '://' not in url
```

Apply in the login route: if `next` param fails validation, fall back to admin page URL.

**Files:** `app/routes/auth.py`

## Fix 24: Stripe Refund Pending Status

Stripe can return `refund.status = 'pending'` for bank-originated refunds. Current code treats anything other than `'succeeded'` as failure.

Change the check in two places:
- `payments.py:304` (individual refund): `if refund.status not in ('succeeded', 'pending'):`
- `payments.py:427` (bulk refund): same change

In both cases, set local `payment.status = 'refunded'` regardless of whether Stripe says `succeeded` or `pending` — the refund is initiated and will complete.

**Files:** `app/routes/payments.py`

## Fix 25: Cardholder Autocomplete

Change `autocomplete="cardholder"` to `autocomplete="cc-name"` on the cardholder name input in the registration form. `cc-name` is the W3C standard value for credit card holder name.

**Files:** `app/templates/season_register.html`
