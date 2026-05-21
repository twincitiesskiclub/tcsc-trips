# Late Registration Link Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an admin generate a per-email, 7-day signed URL that bypasses the closed season-registration window for one person.

**Architecture:** Signed token built with `itsdangerous.URLSafeTimedSerializer` (already a Flask dependency). Token payload = `{season_id, email}`. The existing `season_register` route reads `?invite=<token>`, and if the signature/email/season check out, skips the `is_open_for` window gate. One-time-use emerges from the existing `UserSeason` uniqueness — once registered, a re-submitted link is rejected with "already used." No schema changes.

**Tech Stack:** Flask, itsdangerous 2.2.0, SQLAlchemy, Tabulator.js (admin grid), pytest with local PostgreSQL.

**Reference spec:** `docs/superpowers/specs/2026-05-21-late-registration-link-design.md`

---

## File Structure

**New files:**
- `app/late_link.py` — token generate / verify helpers (~30 lines).
- `tests/registration/__init__.py` — empty package marker.
- `tests/registration/test_late_link.py` — pytest coverage for the helper and the registration-route bypass.

**Modified files:**
- `app/routes/admin.py` — one new route `POST /admin/seasons/<id>/late-link`.
- `app/routes/registration.py` — read `?invite=<token>`, narrow bypass of `is_open_for`, already-registered short-circuit, GET pre-fill.
- `app/templates/season_register.html` — make email field render `readonly` + pre-filled when `invite_email` is in template context; keep hidden input behavior off (token round-trips via URL only).
- `app/static/admin_seasons.js` — add "Late link" action button + modal flow.

Boundaries are clean: token logic lives in one file, the route changes are mechanical, the JS lives with the rest of the seasons admin code.

---

### Task 1: Add the token helper

**Files:**
- Create: `app/late_link.py`

- [ ] **Step 1: Create the helper file**

```python
# app/late_link.py
"""Signed, time-limited tokens that grant late-registration access for one email."""
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from flask import current_app

from .utils import normalize_email

SALT = "late-registration"
MAX_AGE_SECONDS = 7 * 24 * 3600  # 7 days


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=SALT)


def generate(season_id: int, email: str) -> str:
    """Return a signed token for (season_id, normalized email)."""
    payload = {"season_id": int(season_id), "email": normalize_email(email)}
    return _serializer().dumps(payload)


def verify(token: str) -> dict | None:
    """Return the payload dict if the token is valid and not expired, else None."""
    if not token:
        return None
    try:
        return _serializer().loads(token, max_age=MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None
```

- [ ] **Step 2: Smoke-check the import**

Run: `python -c "from app import create_app; app=create_app(); ctx=app.app_context(); ctx.push(); from app.late_link import generate, verify; t=generate(1,'a@b.com'); print(verify(t))"`
Expected: prints `{'season_id': 1, 'email': 'a@b.com'}` (or with whatever `normalize_email` returns) without exceptions.

- [ ] **Step 3: Commit**

```bash
git add app/late_link.py
git commit -m "feat(late-link): add signed token helper for late registration"
```

---

### Task 2: Unit tests for the token helper

**Files:**
- Create: `tests/registration/__init__.py` (empty file)
- Create: `tests/registration/test_late_link.py`

- [ ] **Step 1: Create the package marker**

Create empty file `tests/registration/__init__.py` (zero bytes).

- [ ] **Step 2: Write failing tests**

```python
# tests/registration/test_late_link.py
"""Tests for the late-registration token helper."""
import time
from unittest.mock import patch

import pytest

from app import create_app
from app.late_link import MAX_AGE_SECONDS, generate, verify


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key"
    return app


class TestLateLinkToken:
    def test_roundtrip_returns_payload(self, app):
        with app.app_context():
            token = generate(42, "Foo@Bar.com")
            payload = verify(token)
            assert payload == {"season_id": 42, "email": "foo@bar.com"}

    def test_tampered_token_returns_none(self, app):
        with app.app_context():
            token = generate(1, "x@y.com")
            tampered = token[:-2] + ("AA" if token[-2:] != "AA" else "BB")
            assert verify(tampered) is None

    def test_wrong_secret_returns_none(self, app):
        with app.app_context():
            token = generate(1, "x@y.com")
        app.config["SECRET_KEY"] = "different-secret"
        with app.app_context():
            assert verify(token) is None

    def test_expired_token_returns_none(self, app):
        with app.app_context():
            token = generate(1, "x@y.com")
            # itsdangerous checks max_age against time.time(); jump forward 8 days.
            future = time.time() + MAX_AGE_SECONDS + 60
            with patch("itsdangerous.timed.time.time", return_value=future):
                assert verify(token) is None

    def test_empty_token_returns_none(self, app):
        with app.app_context():
            assert verify("") is None
            assert verify(None) is None
```

- [ ] **Step 3: Run tests, expect them to PASS (helper already exists)**

Run: `pytest tests/registration/test_late_link.py -v`
Expected: 5 passed.

If the expiry test fails because itsdangerous v2 uses a different time source, swap the patch target to `itsdangerous.serializer.time.time` or whatever the installed module exposes — verify with `python -c "import itsdangerous.timed; print(itsdangerous.timed.__file__)"` and grep that file for `time.time`.

- [ ] **Step 4: Commit**

```bash
git add tests/registration/__init__.py tests/registration/test_late_link.py
git commit -m "test(late-link): cover token roundtrip, tamper, expiry"
```

---

### Task 3: Wire the registration route to recognize an invite

**Files:**
- Modify: `app/routes/registration.py` (top of file + body of `season_register`)

- [ ] **Step 1: Add the import**

At the top of `app/routes/registration.py`, with the other `from ..` imports, add:

```python
from .. import late_link
```

(If a relative-style won't resolve, use `from app import late_link`. Check the file's existing import style.)

- [ ] **Step 2: Read and verify the invite at the top of `season_register`**

In `app/routes/registration.py`, immediately after the `now_utc = times['utc']` line (around line 57), insert:

```python
    invite_token = request.args.get('invite')
    invite_payload = late_link.verify(invite_token) if invite_token else None
    invite_season_match = (
        invite_payload is not None
        and invite_payload.get('season_id') == season_id
    )
```

- [ ] **Step 3: Bypass the window check on POST when the invite matches the submitted email**

Find the existing POST block:

```python
            # Check if registration window is open for this user type
            member_type_str = 'returning' if is_returning else 'new'
            if not season.is_open_for(member_type_str, now_utc):
                status_msg = "returning members" if is_returning else "new members"
                flash_error(f'Sorry, the registration window for {status_msg} is currently closed.')
                return redirect(url_for('registration.season_register', season_id=season_id))
```

Replace it with:

```python
            # Check if registration window is open for this user type
            member_type_str = 'returning' if is_returning else 'new'
            invite_valid_for_email = (
                invite_season_match
                and invite_payload.get('email') == email
            )
            if invite_token and not invite_valid_for_email:
                # Token present but signature/expiry/email mismatch — explain why.
                if invite_payload is None:
                    flash_error('This link is invalid or has expired. Please ask an admin for a new one.')
                elif not invite_season_match:
                    flash_error('This link is for a different season.')
                else:
                    flash_error('This link was issued for a different email.')
                return redirect(url_for('registration.season_register', season_id=season_id, invite=invite_token))
            if not invite_valid_for_email and not season.is_open_for(member_type_str, now_utc):
                status_msg = "returning members" if is_returning else "new members"
                flash_error(f'Sorry, the registration window for {status_msg} is currently closed.')
                return redirect(url_for('registration.season_register', season_id=season_id))
```

- [ ] **Step 4: Already-registered short-circuit when using an invite**

Insert the following block **after** `user = User.get_by_email(email)` (line ~63) and **before** the `payment_intent_id` lookup:

```python
            if invite_token and user is not None:
                existing_us = UserSeason.get_for_user_season(user.id, season.id)
                if existing_us and existing_us.status in (UserSeasonStatus.ACTIVE, UserSeasonStatus.PENDING_LOTTERY):
                    flash_error("This link has already been used — you're already registered for this season.")
                    return redirect(url_for('registration.season_register', season_id=season_id))
```

Verify `UserSeason` and `UserSeasonStatus` are already imported at the top of the file. If not, add them — match the existing model-import style.

- [ ] **Step 5: Allow GET to render the form when the invite is valid even if the window is closed**

In the same file, find this block (around line 171):

```python
    # --- GET Request Handling ---
    if not season.is_any_registration_open(now_utc):
```

Change the condition to:

```python
    # --- GET Request Handling ---
    if not season.is_any_registration_open(now_utc) and not invite_season_match:
```

And change the final render line (around line 186) from:

```python
    return render_template('season_register.html', season=season)
```

to:

```python
    return render_template(
        'season_register.html',
        season=season,
        invite_token=invite_token if invite_season_match else None,
        invite_email=invite_payload.get('email') if invite_season_match else None,
    )
```

- [ ] **Step 6: Sanity start**

Run: `python -c "from app import create_app; create_app()"`
Expected: no exception (catches import / syntax breakage).

- [ ] **Step 7: Commit**

```bash
git add app/routes/registration.py
git commit -m "feat(late-link): bypass closed season window for valid invite token"
```

---

### Task 4: Pre-fill and lock the email on the registration form

**Files:**
- Modify: `app/templates/season_register.html`

- [ ] **Step 1: Replace the email field**

Find this block (around line 59-62):

```html
            <div class="form-field">
              <label class="form-field__label" for="email">Email Address</label>
              <input class="form-input" type="email" id="email" name="email" placeholder="Email Address" autocomplete="email" required>
            </div>
```

Replace with:

```html
            <div class="form-field">
              <label class="form-field__label" for="email">Email Address</label>
              {% if invite_email %}
                <input class="form-input" type="email" id="email" name="email" value="{{ invite_email }}" readonly autocomplete="email" required>
                <p class="form-field__hint">This invite was issued for {{ invite_email }}.</p>
              {% else %}
                <input class="form-input" type="email" id="email" name="email" placeholder="Email Address" autocomplete="email" required>
              {% endif %}
            </div>
```

(If `form-field__hint` is not a class used elsewhere in this template, drop the `<p>` line — keep the change minimal. Check by grepping the template directory.)

- [ ] **Step 2: Smoke-render**

Start the dev server (`./scripts/dev.sh`), then in a browser visit `/seasons/<some-id>/register?invite=fake` — the form should still render with the regular email input (token is invalid so `invite_email` is `None`). Then stop the server.

- [ ] **Step 3: Commit**

```bash
git add app/templates/season_register.html
git commit -m "feat(late-link): pre-fill and lock email when invite present"
```

---

### Task 5: Admin route to generate a link

**Files:**
- Modify: `app/routes/admin.py`

- [ ] **Step 1: Add the import**

Near the existing `from ..` imports at the top of `app/routes/admin.py`, add:

```python
from .. import late_link
from ..utils import normalize_email
```

If `normalize_email` is already imported, skip that line.

- [ ] **Step 2: Add the route**

Add this function near the existing season admin routes (after `get_admin_seasons` at line ~331):

```python
@admin.route('/admin/seasons/<int:season_id>/late-link', methods=['POST'])
@admin_required
def generate_late_link(season_id):
    season = Season.query.get_or_404(season_id)
    email_raw = (request.json or {}).get('email') if request.is_json else request.form.get('email')
    if not email_raw or '@' not in email_raw:
        return jsonify({'success': False, 'error': 'A valid email is required.'}), 400
    email = normalize_email(email_raw)
    token = late_link.generate(season.id, email)
    url = url_for('registration.season_register', season_id=season.id, invite=token, _external=True)
    return jsonify({'success': True, 'url': url, 'email': email})
```

- [ ] **Step 3: Manual smoke test**

Start the dev server and run from another shell:

```bash
curl -s -X POST http://localhost:5001/admin/seasons/1/late-link \
  -H 'Content-Type: application/json' \
  -d '{"email":"test@example.com"}' \
  --cookie "session=<paste-an-admin-session-cookie>"
```

(If grabbing a cookie is too fiddly, defer the end-to-end check to Task 7 where we test against a logged-in browser session.)

Expected JSON: `{"success": true, "url": "http://localhost:5001/seasons/1/register?invite=...", "email": "test@example.com"}`.

- [ ] **Step 4: Commit**

```bash
git add app/routes/admin.py
git commit -m "feat(late-link): admin route to generate per-email late-registration URL"
```

---

### Task 6: Admin UI — button + modal

**Files:**
- Modify: `app/static/admin_seasons.js`

- [ ] **Step 1: Add the button to the Actions column**

In `app/static/admin_seasons.js`, find the `Actions` column formatter (around line 73-92). Inside the function, after the Edit and Export links and before the Delete button, add the late-link button. The current block:

```javascript
                    let html = `<div class="admin-actions">
                        <a href="/admin/seasons/${data.id}/edit" class="admin-btn admin-btn-sm admin-btn-primary">Edit</a>
                        <a href="/admin/seasons/${data.id}/export" class="admin-btn admin-btn-sm admin-btn-secondary">Export</a>`;

                    if (!data.is_current) {
                        html += `<button class="admin-btn admin-btn-sm admin-btn-success" onclick="activateSeason(${data.id}, '${data.name.replace(/'/g, "\\'")}')">Activate</button>`;
                    }

                    html += `<button class="admin-btn admin-btn-sm admin-btn-danger" onclick="confirmDeleteSeason(${data.id}, '${data.name.replace(/'/g, "\\'")}')">Delete</button>
                    </div>`;
                    return html;
```

becomes:

```javascript
                    let html = `<div class="admin-actions">
                        <a href="/admin/seasons/${data.id}/edit" class="admin-btn admin-btn-sm admin-btn-primary">Edit</a>
                        <a href="/admin/seasons/${data.id}/export" class="admin-btn admin-btn-sm admin-btn-secondary">Export</a>
                        <button class="admin-btn admin-btn-sm admin-btn-secondary" onclick="generateLateLink(${data.id}, '${data.name.replace(/'/g, "\\'")}')">Late Link</button>`;

                    if (!data.is_current) {
                        html += `<button class="admin-btn admin-btn-sm admin-btn-success" onclick="activateSeason(${data.id}, '${data.name.replace(/'/g, "\\'")}')">Activate</button>`;
                    }

                    html += `<button class="admin-btn admin-btn-sm admin-btn-danger" onclick="confirmDeleteSeason(${data.id}, '${data.name.replace(/'/g, "\\'")}')">Delete</button>
                    </div>`;
                    return html;
```

- [ ] **Step 2: Add the modal handler**

At the bottom of `app/static/admin_seasons.js`, append:

```javascript
function generateLateLink(seasonId, seasonName) {
    const email = window.prompt(`Generate late-registration link for "${seasonName}"\n\nEnter the recipient's email:`);
    if (!email) return;

    fetch(`/admin/seasons/${seasonId}/late-link`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim() })
    })
    .then(response => response.json())
    .then(data => {
        if (!data.success) {
            showToast(data.error || 'Failed to generate link', 'error');
            return;
        }
        // Show the URL in a way the admin can copy from. window.prompt's text
        // field is selected by default in most browsers, which is the easiest
        // copy UX without building a dedicated modal.
        window.prompt(`Late-registration link for ${data.email} (7-day expiry). Copy and send via Slack/email:`, data.url);
    })
    .catch(err => {
        showToast('Error: ' + err.message, 'error');
    });
}
```

(Yes, two `prompt()`s in a row is ugly. The TCSC admin UI is utilitarian and this matches the existing `confirm()`-based patterns. If the user later asks for a nicer modal, that's a follow-up.)

- [ ] **Step 3: Manual smoke test**

Run `./scripts/dev.sh`, log in as an admin, go to `/admin/seasons`, click "Late Link" on any season, enter an email, copy the URL out of the second prompt. Then open that URL in a private/incognito tab — even if the season window is closed, the registration form should load with the email pre-filled and locked.

- [ ] **Step 4: Commit**

```bash
git add app/static/admin_seasons.js
git commit -m "feat(late-link): add admin grid button to generate late-registration link"
```

---

### Task 7: End-to-end integration tests for the registration bypass

**Files:**
- Modify: `tests/registration/test_late_link.py` (append a new test class)

- [ ] **Step 1: Add fixtures and bypass tests**

Append the following to `tests/registration/test_late_link.py`:

```python
from datetime import datetime, timedelta

from app.constants import UserSeasonStatus, UserStatus
from app.late_link import generate
from app.models import Season, User, UserSeason, db


@pytest.fixture
def db_session(app):
    with app.app_context():
        db.create_all()
        yield db
        db.session.rollback()


@pytest.fixture
def closed_season(db_session):
    """A season whose new+returning registration windows are both in the past."""
    past_start = datetime.utcnow() - timedelta(days=30)
    past_end = datetime.utcnow() - timedelta(days=14)
    season = Season(
        name='Test Closed Season',
        year=2026,
        season_type='winter',
        start_date=datetime.utcnow().date() + timedelta(days=30),
        end_date=datetime.utcnow().date() + timedelta(days=120),
        returning_start=past_start,
        returning_end=past_end,
        new_start=past_start,
        new_end=past_end,
        price_cents=10000,
        registration_limit=100,
        is_current=False,
    )
    db.session.add(season)
    db.session.commit()
    yield season
    UserSeason.query.filter_by(season_id=season.id).delete()
    db.session.delete(season)
    db.session.commit()


@pytest.fixture
def client(app):
    return app.test_client()


class TestRegistrationInviteBypass:
    """The registration route only checks the token's signature/expiry/email-match
    — payment and form validation are NOT covered here (out of scope for this
    feature). These tests use GET requests and inspect the rendered template /
    redirect behavior."""

    def test_get_with_valid_invite_renders_form_when_window_closed(self, app, client, closed_season):
        with app.app_context():
            token = generate(closed_season.id, 'guest@example.com')
        response = client.get(f'/seasons/{closed_season.id}/register?invite={token}', follow_redirects=False)
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert 'guest@example.com' in body
        assert 'readonly' in body

    def test_get_with_invalid_invite_redirects_when_window_closed(self, app, client, closed_season):
        response = client.get(f'/seasons/{closed_season.id}/register?invite=garbage', follow_redirects=False)
        # Existing closed-window UX: redirect (302) to home.
        assert response.status_code == 302

    def test_get_with_invite_for_other_season_redirects(self, app, client, closed_season):
        with app.app_context():
            token = generate(closed_season.id + 9999, 'guest@example.com')
        response = client.get(f'/seasons/{closed_season.id}/register?invite={token}', follow_redirects=False)
        assert response.status_code == 302

    def test_already_registered_short_circuits(self, app, client, closed_season):
        with app.app_context():
            user = User(email='already@example.com', status=UserStatus.ACTIVE, first_name='A', last_name='B')
            db.session.add(user)
            db.session.flush()
            db.session.add(UserSeason(
                user_id=user.id,
                season_id=closed_season.id,
                registration_type='new',
                registration_date=datetime.utcnow().date(),
                status=UserSeasonStatus.ACTIVE,
            ))
            db.session.commit()
            token = generate(closed_season.id, 'already@example.com')
        # POST minimally — we expect to be short-circuited before form validation runs.
        response = client.post(
            f'/seasons/{closed_season.id}/register?invite={token}',
            data={'email': 'already@example.com'},
            follow_redirects=False,
        )
        assert response.status_code == 302
        # Follow the redirect and confirm the flash message landed.
        followed = client.get(response.headers['Location'], follow_redirects=True)
        assert b'already been used' in followed.data
```

- [ ] **Step 2: Run the new tests**

Run: `pytest tests/registration/test_late_link.py -v`
Expected: 9 passed (5 from Task 2 plus 4 new).

If the `closed_season` fixture fails because `Season` requires fields this plan didn't list, open `app/models.py` around the `Season` class and add whatever non-nullable columns are missing — keep the values minimal.

- [ ] **Step 3: Commit**

```bash
git add tests/registration/test_late_link.py
git commit -m "test(late-link): integration tests for invite bypass + already-used"
```

---

### Task 8: Manual end-to-end pass

- [ ] **Step 1: Start the stack**

Run: `./scripts/dev.sh`. Wait for the Flask server to come up on port 5001.

- [ ] **Step 2: Generate a link as admin**

In a browser, log in at `/admin`. Go to `/admin/seasons`. Pick any season — ideally one whose registration windows are already in the past. Click **Late Link**. Enter an email you control (e.g. `you+late@yourdomain.com`). Copy the URL from the second prompt.

- [ ] **Step 3: Use the link in a fresh session**

Open the URL in a private/incognito window. Confirm:
  - The registration form renders even though the season window is closed.
  - The email field is pre-filled with the address you entered and is `readonly`.

- [ ] **Step 4: Complete the registration**

Fill in the rest of the form, submit, complete the Stripe authorization with a test card (4242…). Confirm you land on `season_success.html` and that the new `UserSeason` row exists in the DB (e.g. via `psql` against `tcsc-postgres`).

- [ ] **Step 5: Try the link again**

In the same incognito window, paste the URL again. Submit. Expected: redirect with the flash message "This link has already been used — you're already registered for this season."

- [ ] **Step 6: Try an expired/garbage link**

Hand-edit the token in the URL (change a few characters) and submit. Expected: redirect with the "This link is invalid or has expired" flash on the seasons listing.

- [ ] **Step 7: No commit needed**

Manual QA only. If anything failed, file a bug or fix and revisit the relevant task.

---

## Self-Review

- **Spec coverage:** All five sections of the spec (Token, Components — late_link.py, admin route, JS modal, registration route — Failure messages, Testing, Files touched) map to tasks 1–7. ✓
- **Placeholder scan:** No "TBD"/"TODO". Each step has either explicit code, an explicit command, or an explicit verification step.
- **Type consistency:** `late_link.generate(season_id, email)` and `late_link.verify(token) -> dict | None` are used consistently in tasks 1, 3, 5, 7. `invite_payload`, `invite_token`, `invite_season_match` are used with the same meaning across task 3. `UserSeasonStatus.ACTIVE` / `.PENDING_LOTTERY` are used consistently per `app/constants.py`.
- **Known fragilities flagged inline:**
  - `itsdangerous` time-patch target may differ by version (Task 2, Step 3).
  - `Season` model may require fields the fixture doesn't include (Task 7, Step 2).
  - `form-field__hint` class may not exist (Task 4, Step 1).
  These are all "if X fails, do Y" notes embedded in the step, so an executor isn't left blocked.
