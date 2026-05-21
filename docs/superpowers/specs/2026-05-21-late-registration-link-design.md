# Late Registration Link — Design

**Date:** 2026-05-21
**Status:** Approved (brainstorming)

## Problem

Season registration windows close on a fixed date. Occasionally someone needs to register after the window has closed (a returning member who missed the deadline, a new member referred late, etc.). Today the only path is to manually reopen the window for everyone, which isn't what we want.

We need a way for an admin to grant a single person late access without modifying the schema or relaxing the date gate for the public.

## Goals

- Admin can generate a per-person late-registration URL from the admin UI.
- The recipient can complete normal season registration even after the window has closed.
- Re-use is naturally prevented (one registration per email per season).
- No new database tables or migrations.
- Small surface area: a token helper, a generation route, a tiny UI affordance, and a narrow bypass in the existing registration route.

## Non-goals

- No revocation list, no usage logs beyond standard request logs.
- No support for editing an already-completed registration via the link.
- No CLI generation path (admin UI only).
- No bulk link generation.

## Approach

Signed URL using `itsdangerous.URLSafeTimedSerializer` (already a Flask dependency). The token encodes the season ID and the recipient's email, signed with `FLASK_SECRET_KEY` and salt `"late-registration"`. Expiration is enforced server-side via `max_age` (7 days).

This is the smallest possible design that meets the requirements. No state needs to be stored about the token itself; one-time-use emerges from the existing `UserSeason` uniqueness — once the recipient registers, the next attempt to use the link sees an existing `UserSeason` and is blocked.

## Token

- Serializer: `itsdangerous.URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="late-registration")`
- Payload: `{"season_id": int, "email": normalized_email_str}`
- Max age on verify: `7 * 24 * 3600` seconds (7 days)
- URL shape: `/seasons/<season_id>/register?invite=<token>`

## Components

### `app/late_link.py` (new, ~25 lines)

Two functions:

- `generate(season_id: int, email: str) -> str` — normalizes email, dumps payload, returns the token string.
- `verify(token: str) -> dict | None` — loads the token with `max_age=7*24*3600`, returns the payload dict on success or `None` on bad signature / expiration. Callers handle messaging.

Reasoning lives here so the route stays thin and the helper is easy to unit-test.

### `app/routes/admin.py` — new route

`POST /admin/seasons/<int:season_id>/late-link`

- Auth: existing `@admin_required` decorator (whatever the other `/admin/seasons/*` routes use).
- Body: `email` (form field).
- Validates that the season exists. Normalizes the email. Generates the token. Returns JSON `{"url": "<full_url>"}` built from `url_for("registration.season_register", season_id=..., _external=True) + "?invite=" + token`.

No model changes. No new template page — it's an XHR endpoint feeding the modal.

### `app/templates/admin/seasons.html` + `app/static/admin_seasons.js`

Add a per-row action "Generate late link" to the Tabulator grid. Clicking opens a small modal with:

- One text input: email.
- "Generate" button — POSTs to the route above.
- On success: replaces input area with the returned URL in a read-only field plus a "Copy" button. Admin copies the link and sends it through whatever channel they prefer (Slack DM, email, etc.).
- On failure: inline error message.

Follows the existing admin toast / modal conventions in the file.

### `app/routes/registration.py` — bypass logic

In `season_register(season_id)` at `app/routes/registration.py:52`:

1. At the top of the function (both GET and POST), read `request.args.get("invite")`. If present, call `late_link.verify(token)`. Compute `invite_payload` (dict or `None`).
2. Determine `invite_valid_for_email(email)` as: `invite_payload is not None and invite_payload["season_id"] == season_id and normalize_email(email) == invite_payload["email"]`.
3. On **POST**:
   - Read the submitted email and normalize it.
   - If an invite token is present, look up the user by email. If a user exists and has a `UserSeason` for this season with status `ACTIVE` or `PENDING_LOTTERY`, flash `"This link has already been used — you're already registered."` and redirect. This produces the "one-time" UX without changing how non-invite duplicate-registration is handled.
   - Replace the current window check (`if not season.is_open_for(...)`) with: `if not invite_valid_for_email(email) and not season.is_open_for(member_type_str, now_utc):` — i.e., a valid invite for the submitted email bypasses the window. Everything else (member type consistency, form validation, payment) is unchanged.
4. On **GET**:
   - The token is read **only from `request.args["invite"]`** — never from a form body. The form `action` keeps the `?invite=<token>` query string so it round-trips to POST. No hidden field.
   - If `invite_payload` is valid and `season.is_open_for(...)` is false, render the form with the email pre-filled (and `readonly`) using `invite_payload["email"]`.
   - If `invite_payload` is invalid (bad signature or expired) **and** the window is closed, fall through to the existing closed-window UX — do not flash. (A late link that doesn't unlock anything is indistinguishable from no link at all from the user's perspective.) On the POST side, the same invalid token will fail the bypass check and produce the standard "window closed" error, which is acceptable.

### Failure messages

Each results in `flash_error(...)` + redirect to `/seasons`:

| Condition | Message |
|---|---|
| Token signature invalid (on POST) | "This link is invalid." |
| Token expired (on POST) | "This link has expired. Please ask an admin for a new one." |
| Email submitted ≠ token's email | "This link was issued for a different email." |
| Already registered for this season via invite | "This link has already been used — you're already registered." |

On GET, an invalid or expired token silently falls through to the existing closed-window UX rather than flashing — so a broken link looks the same as no link.

## Data flow

```
Admin (browser)
   │  click "Generate late link" → modal → email
   ▼
POST /admin/seasons/<id>/late-link
   │  late_link.generate(season_id, email) → token
   │  build absolute URL
   ▼
Admin copies URL, sends it externally
   ▼
Recipient (browser)
   │  GET /seasons/<id>/register?invite=<token>
   │  late_link.verify(token) → payload (signature + 7d expiration)
   │  render form with email locked
   ▼
POST /seasons/<id>/register?invite=<token>
   │  re-verify token, compare email
   │  if existing UserSeason → "already used"
   │  else bypass is_open_for, run normal flow
   ▼
UserSeason created → link is now effectively consumed
```

## Error handling

- All token failures: flash + redirect, never 500.
- Admin route returns JSON errors with appropriate status codes (400 for bad email, 404 for missing season).
- Form validation, Stripe authorization, member-type consistency checks are unchanged from the existing route. The invite only loosens the window gate.

## Testing

Pytest in `tests/registration/test_late_link.py` (new file, four cases):

1. Valid token + closed window + new email → registration succeeds, `UserSeason` row created.
2. Expired token (mock time or pass `max_age=-1` style fixture) → rejected with friendly message.
3. Wrong email submitted (form email ≠ token email) → rejected.
4. Token for an email that already has a UserSeason → blocked with "already used" message.

`late_link.generate` / `verify` round-trip is covered implicitly by case 1; no separate unit test needed.

## Out of scope / explicitly deferred

- Revocation. If a link leaks, the admin's recourse today is `FLASK_SECRET_KEY` rotation, which invalidates all signed state. We accept this.
- Audit log of who generated which link. Standard request logs are sufficient.
- Per-link expiration override. Fixed at 7 days.
- CLI generation. UI only.

## Files touched

- New: `app/late_link.py`, `tests/registration/test_late_link.py`.
- Edit: `app/routes/registration.py` (~20 lines added), `app/routes/admin.py` (~15 lines added), `app/templates/admin/seasons.html` and/or `app/static/admin_seasons.js` (small modal addition).

No migrations. No new dependencies.
