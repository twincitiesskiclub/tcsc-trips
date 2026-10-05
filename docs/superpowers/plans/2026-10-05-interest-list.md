# Interest List Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prospective members can join an interest list from the marketing site or from tcsc.ski while registration is closed, and admins can view, export and prune it.

**Architecture:** One new table (`interest_signups`) with no link to `User`. One write path, `POST tcsc.ski/interest`, CSRF-exempt so the static marketing site's plain HTML form can post to it, and always answered with a page on tcsc.ski. Admins get a list page that labels each row with a matching member's status by reading `User` at request time, plus a CSV export and per-row delete.

**Tech Stack:** Flask, SQLAlchemy, Alembic (Flask-Migrate), Jinja, `main.css` (public tcsc.ski), Tailwind (admin and Astro site), Astro 7, pytest, `node --test`.

**Spec:** `docs/superpowers/specs/2026-10-05-interest-list-design.md`

## Global Constraints

- Work in the worktree `/workspace/tcsc-trips/.worktrees/interest-list` on branch `interest-list`. Never commit to `main`; Render deploys every commit on main.
- Python tests run against the scratch DB, never the dev DB (the dev DB `tcsc_trips` sits at an old revision). Every pytest command in this plan is:
  `DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test /workspace/tcsc-trips/.venv/bin/pytest <paths> -q`
- Migrations on the scratch DB:
  `env TCSC_MIGRATION_ONLY=1 SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= FLASK_SECRET_KEY=x DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test FLASK_APP=app.py /workspace/tcsc-trips/.venv/bin/flask db upgrade`
- Never call `db.create_all()` in tests (`tests/test_no_create_all.py` enforces it). Test rows use emails ending `@interest-test.example` and are deleted before and after each test.
- Call it the "interest list" in code and admin. Never "waitlist"; that word already means lottery losers in admin.
- Form field names are a contract between the Astro form and the Flask route: `name`, `email`, `phone`, and the honeypot `website`.
- Timestamps are stored as naive UTC (`datetime.utcnow()`), displayed in Central via `utc_naive_to_central_naive()` or the `central_time` Jinja filter.
- SMS consent copy, verbatim: `We'll text you when registration opens. Reply STOP to opt out.`
- No em dashes in any user-facing copy.
- The app sends nothing to the list. No email, no SMS, no scheduler job.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Phone numbers in the CSV.** The existing CSV sanitizer prefixes any value starting with `+` with an apostrophe, which would turn `+16125550101` into `'+16125550101` and break imports into a texting tool. Phones are server-normalized, so the phone column skips the sanitizer. Name and email are typed by strangers and go through it. Test in Task 3.
2. **Oversized input.** A 300-character email or name must give a form error, not a 500 from the database. Test in Task 1.
3. **Member email case.** Members created before email normalization can have mixed-case `User.email` ("Sam@Example.com"). A lowercase signup must still match. Test in Task 1.
4. **Double submit.** Two submissions of the same new email can race past the lookup. The loser hits the unique constraint and must still get the thanks page, not a 500. Test in Task 1.
5. **Marketing site CSP.** `render.yaml` sets `form-action 'self'` on the static site, so browsers would silently block the `/join` form from posting to tcsc.ski. Task 4 adds `https://tcsc.ski` and a site test pins it.

---

## File map

| File | Status | Responsibility |
|---|---|---|
| `app/interest/__init__.py` | create | package marker |
| `app/interest/models.py` | create | `InterestSignup` model |
| `app/interest/service.py` | create | validate, save (upsert), member-status lookup |
| `migrations/versions/7a1c5e9d3b20_add_interest_signups.py` | create | table |
| `app/__init__.py` | modify | import model, register two blueprints |
| `app/routes/interest.py` | create | public `GET/POST /interest` |
| `app/routes/admin_interest.py` | create | admin page, CSV, delete |
| `app/templates/_interest_form.html` | create | the tcsc.ski form partial |
| `app/templates/interest.html` | create | standalone form page and error re-render |
| `app/templates/interest_thanks.html` | create | success page |
| `app/templates/index.html` | modify | include partial when registration is not open |
| `app/templates/season_detail.html` | modify | include partial when the season is closed |
| `app/templates/admin/interest_list.html` | create | admin table |
| `app/templates/admin/partials/sidebar.html` | modify | nav link |
| `tests/practices/test_practice_migration_release.py` | modify | bump `HEAD_REVISION` |
| `tests/interest/` | create | all Python tests for this feature |
| `site/src/pages/join.astro` | create | marketing-site form page |
| `site/src/content/pages/home.yaml` | modify | CTA urls and closed label |
| `site/src/components/registrationCta.ts` | modify | fallback urls and label |
| `site/tests/contentRefinements.test.mjs` | modify | coming-soon CTAs now target `/join` |
| `site/tests/seasonFallback.test.mjs` | modify | closed fallback strip now targets `/join` |
| `site/tests/joinPage.test.mjs` | create | built `/join` page and CSP checks |
| `site/package.json` | modify | add the new site test to `test:refinement` |
| `render.yaml` | modify | static site CSP `form-action` |

---

### Task 1: Model, migration and service

**Files:**
- Create: `app/interest/__init__.py`, `app/interest/models.py`, `app/interest/service.py`
- Create: `migrations/versions/7a1c5e9d3b20_add_interest_signups.py`
- Modify: `app/__init__.py` (model import, next to the other `# noqa: F401` model imports near line 15)
- Modify: `tests/practices/test_practice_migration_release.py:28`
- Test: `tests/interest/__init__.py`, `tests/interest/conftest.py`, `tests/interest/test_service.py`

**Interfaces:**
- Produces:
  - `app.interest.models.InterestSignup` with columns `id, name, email, phone_e164, sms_consent_at, created_at`
  - `app.interest.service.FIELDS: tuple[str, ...] = ('name', 'email', 'phone')`
  - `app.interest.service.HONEYPOT: str = 'website'`
  - `app.interest.service.validate(form) -> tuple[dict[str, str], dict[str, str]]` returns `(values, errors)`; `values` holds the trimmed typed strings for every key in `FIELDS`; `errors` maps a field name to a message and is empty when valid
  - `app.interest.service.save_signup(values: dict) -> None` upserts by normalized email
  - `app.interest.service.rows_with_member_status() -> list[dict]`, each `{'signup': InterestSignup, 'member_status': str}`, newest signup first, `member_status` is `''` when no member matches
  - Test fixtures in `tests/interest/conftest.py`: `app`, `client`, `admin_client`, `TEST_DOMAIN = '@interest-test.example'`

- [ ] **Step 1: Write the test fixtures**

`tests/interest/__init__.py` is empty. `tests/interest/conftest.py`:

```python
"""Fixtures for the interest list tests.

Uses whatever DATABASE_URL the run exported (the scratch DB, see the plan),
unlike tests/routes/conftest.py which hardcodes the dev DB. Every row these
tests write uses TEST_DOMAIN and is wiped before and after each test.
"""
import pytest

from app import create_app
from app.interest.models import InterestSignup
from app.models import User, db

TEST_DOMAIN = '@interest-test.example'


@pytest.fixture
def app():
    application = create_app()
    application.config.update(TESTING=True)
    return application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_client(client):
    with client.session_transaction() as sess:
        sess['user'] = {'email': 'tester@twincitiesskiclub.org', 'name': 'Tester'}
    return client


@pytest.fixture(autouse=True)
def _wipe(app):
    def wipe():
        with app.app_context():
            InterestSignup.query.filter(
                InterestSignup.email.like(f'%{TEST_DOMAIN}')
            ).delete(synchronize_session=False)
            User.query.filter(
                db.func.lower(User.email).like(f'%{TEST_DOMAIN}')
            ).delete(synchronize_session=False)
            db.session.commit()
    wipe()
    yield
    wipe()
```

- [ ] **Step 2: Write the failing service tests**

`tests/interest/test_service.py`:

```python
from unittest.mock import patch

from app.interest import service
from app.interest.models import InterestSignup
from app.models import User, db

from .conftest import TEST_DOMAIN

EMAIL = f'sam{TEST_DOMAIN}'


def form(**overrides):
    base = {'name': 'Sam Skier', 'email': EMAIL, 'phone': ''}
    base.update(overrides)
    return base


def test_validate_accepts_minimal_form(app):
    values, errors = service.validate(form())
    assert errors == {}
    assert values == {'name': 'Sam Skier', 'email': EMAIL, 'phone': ''}


def test_validate_trims_and_keeps_typed_values(app):
    values, errors = service.validate(form(name='  Sam  ', phone=' 612-555-0101 '))
    assert errors == {}
    assert values['name'] == 'Sam'
    assert values['phone'] == '612-555-0101'


def test_validate_requires_name_and_email(app):
    _, errors = service.validate({'name': ' ', 'email': ''})
    assert set(errors) == {'name', 'email'}


def test_validate_rejects_malformed_email(app):
    for bad in ('sam', 'sam@', '@x.com', 'sam@localhost'):
        _, errors = service.validate(form(email=bad))
        assert 'email' in errors, bad


def test_validate_rejects_bad_phone(app):
    _, errors = service.validate(form(phone='12345'))
    assert 'phone' in errors


def test_validate_rejects_oversized_fields(app):
    _, errors = service.validate(form(name='x' * 201, email='x' * 250 + TEST_DOMAIN))
    assert set(errors) == {'name', 'email'}


def test_save_creates_row_without_phone(app):
    with app.app_context():
        service.save_signup(form())
        row = InterestSignup.query.filter_by(email=EMAIL).one()
        assert row.name == 'Sam Skier'
        assert row.phone_e164 is None
        assert row.sms_consent_at is None
        assert row.created_at is not None


def test_save_with_phone_stamps_consent(app):
    with app.app_context():
        service.save_signup(form(phone='(612) 555-0101'))
        row = InterestSignup.query.filter_by(email=EMAIL).one()
        assert row.phone_e164 == '+16125550101'
        assert row.sms_consent_at is not None


def test_save_upserts_on_email_case_and_clears_dropped_phone(app):
    with app.app_context():
        service.save_signup(form(phone='612-555-0101'))
        service.save_signup(form(name='Samantha', email=EMAIL.upper(), phone=''))
        rows = InterestSignup.query.filter_by(email=EMAIL).all()
        assert len(rows) == 1
        assert rows[0].name == 'Samantha'
        assert rows[0].phone_e164 is None
        assert rows[0].sms_consent_at is None


def test_save_survives_a_concurrent_insert(app):
    """Two submits of one new email can both miss the lookup; the second
    insert hits the unique constraint and must not raise."""
    with app.app_context():
        service.save_signup(form())
        with patch.object(service, '_existing', return_value=None):
            service.save_signup(form(name='Second'))
        assert InterestSignup.query.filter_by(email=EMAIL).count() == 1


def test_member_status_matches_email_case_insensitively(app):
    with app.app_context():
        db.session.add(User(email=f'Sam{TEST_DOMAIN}', first_name='Sam',
                            last_name='Member', status='ACTIVE'))
        db.session.commit()
        service.save_signup(form())
        rows = [r for r in service.rows_with_member_status()
                if r['signup'].email == EMAIL]
        assert rows[0]['member_status'] == 'ACTIVE'


def test_member_status_matches_phone(app):
    with app.app_context():
        db.session.add(User(email=f'other{TEST_DOMAIN}', first_name='O',
                            last_name='Ther', status='ALUMNI',
                            phone_e164='+16125550199'))
        db.session.commit()
        service.save_signup(form(phone='612-555-0199'))
        rows = [r for r in service.rows_with_member_status()
                if r['signup'].email == EMAIL]
        assert rows[0]['member_status'] == 'ALUMNI'


def test_member_status_blank_without_match(app):
    with app.app_context():
        service.save_signup(form())
        rows = [r for r in service.rows_with_member_status()
                if r['signup'].email == EMAIL]
        assert rows[0]['member_status'] == ''
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test /workspace/tcsc-trips/.venv/bin/pytest tests/interest -q`
Expected: collection error, `ModuleNotFoundError: No module named 'app.interest'`.

- [ ] **Step 4: Write the model**

`app/interest/__init__.py` is empty. `app/interest/models.py`:

```python
from datetime import datetime

from app.models import db


class InterestSignup(db.Model):
    """Someone who wants to hear when registration opens.

    Not a member. Rows here never create or update a User; the admin page
    only reads User to label rows that match an existing account.
    """
    __tablename__ = 'interest_signups'
    __table_args__ = (
        db.UniqueConstraint('email', name='uq_interest_signups_email'),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone_e164 = db.Column(db.String(20))
    # Set whenever a phone is saved: the consent line sits under the field.
    sms_consent_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
```

In `app/__init__.py`, next to `from .trips import models as trips_models  # noqa: F401 ...`, add:

```python
from .interest import models as interest_models  # noqa: F401  (register tables with SQLAlchemy)
```

- [ ] **Step 5: Write the migration and apply it to the scratch DB**

`migrations/versions/7a1c5e9d3b20_add_interest_signups.py`:

```python
"""Add interest_signups.

Revision ID: 7a1c5e9d3b20
Revises: c3f9a1e7d2b4
Create Date: 2026-10-05
"""
from alembic import op
import sqlalchemy as sa

revision = "7a1c5e9d3b20"
down_revision = "c3f9a1e7d2b4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "interest_signups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone_e164", sa.String(20)),
        sa.Column("sms_consent_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("email", name="uq_interest_signups_email"),
    )


def downgrade():
    op.drop_table("interest_signups")
```

In `tests/practices/test_practice_migration_release.py` change line 28 to `HEAD_REVISION = "7a1c5e9d3b20"`.

Run the scratch-DB migration command from Global Constraints.
Expected: `Running upgrade c3f9a1e7d2b4 -> 7a1c5e9d3b20, Add interest_signups.`

- [ ] **Step 6: Write the service**

`app/interest/service.py`:

```python
"""Interest list: people who want to hear when registration opens.

They are not members. Nothing here writes to User; rows_with_member_status
only reads it so admins can see who has since joined.
"""
from datetime import datetime

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from app.models import User, db
from app.utils import normalize_email, normalize_phone_e164

from .models import InterestSignup

# The form contract shared with site/src/pages/join.astro and
# app/templates/_interest_form.html. tests/interest/test_form_contract.py
# checks both templates against these names.
FIELDS = ('name', 'email', 'phone')
HONEYPOT = 'website'

MAX_NAME = 200
MAX_EMAIL = 255


def validate(form):
    """Return (values, errors). values are the trimmed typed strings, kept so
    an error re-render shows what the person entered."""
    values = {f: (form.get(f) or '').strip() for f in FIELDS}
    errors = {}

    if not values['name']:
        errors['name'] = 'Enter your name.'
    elif len(values['name']) > MAX_NAME:
        errors['name'] = 'That name is too long.'

    email = normalize_email(values['email'])
    local, _, domain = email.partition('@')
    if not local or '.' not in domain or domain.startswith('.') or domain.endswith('.'):
        errors['email'] = 'Enter a valid email address.'
    elif len(email) > MAX_EMAIL:
        errors['email'] = 'That email address is too long.'

    if values['phone'] and not normalize_phone_e164(values['phone']):
        errors['phone'] = 'Enter a 10-digit US cell number, or leave it blank.'

    return values, errors


def _existing(email):
    return InterestSignup.query.filter_by(email=email).first()


def save_signup(values):
    """Insert or update the row for this email. Resubmitting replaces name and
    phone; a resubmit without a phone withdraws SMS consent."""
    email = normalize_email(values['email'])
    phone = normalize_phone_e164(values['phone'])

    row = _existing(email)
    if row is None:
        row = InterestSignup(email=email)
        db.session.add(row)
    row.name = values['name']
    row.phone_e164 = phone
    row.sms_consent_at = datetime.utcnow() if phone else None
    try:
        db.session.commit()
    except IntegrityError:
        # A concurrent submit of the same new email won the insert. Their
        # row stands; this person still sees the thanks page.
        db.session.rollback()


def rows_with_member_status():
    """Every signup, newest first, labeled with a matching User's status.

    Email match wins over phone match, because households share phones.
    """
    signups = InterestSignup.query.order_by(InterestSignup.created_at.desc()).all()
    if not signups:
        return []

    emails = {s.email for s in signups}
    phones = {s.phone_e164 for s in signups if s.phone_e164}
    users = User.query.filter(or_(
        func.lower(User.email).in_(emails),
        User.phone_e164.in_(phones),
    )).all()

    by_email = {u.email.lower(): u.status for u in users}
    by_phone = {}
    for u in users:
        if u.phone_e164:
            by_phone.setdefault(u.phone_e164, u.status)

    return [
        {
            'signup': s,
            'member_status': by_email.get(s.email) or by_phone.get(s.phone_e164) or '',
        }
        for s in signups
    ]
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test /workspace/tcsc-trips/.venv/bin/pytest tests/interest tests/practices/test_practice_migration_release.py tests/test_no_create_all.py -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add app/interest app/__init__.py migrations/versions/7a1c5e9d3b20_add_interest_signups.py tests/interest tests/practices/test_practice_migration_release.py
git commit -m "Interest list: model, migration and service

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Public form route and tcsc.ski pages

**Files:**
- Create: `app/routes/interest.py`
- Create: `app/templates/_interest_form.html`, `app/templates/interest.html`, `app/templates/interest_thanks.html`
- Modify: `app/__init__.py` (import and register `interest` blueprint)
- Modify: `app/templates/index.html` (after the season `{% endif %}` near line 69)
- Modify: `app/templates/season_detail.html` (between the season card's closing `</div>` and the "Back to Home" block near line 83)
- Test: `tests/interest/test_routes.py`, `tests/interest/test_form_contract.py`

**Interfaces:**
- Consumes: `service.validate`, `service.save_signup`, `service.FIELDS`, `service.HONEYPOT` from Task 1.
- Produces: Flask endpoints `interest.interest_form` (`GET /interest`) and `interest.interest_submit` (`POST /interest`). The partial `_interest_form.html` reads optional `values` and `errors` dicts from its context.

- [ ] **Step 1: Write the failing route tests**

`tests/interest/test_routes.py`:

```python
from app.interest.models import InterestSignup

from .conftest import TEST_DOMAIN

EMAIL = f'pat{TEST_DOMAIN}'


def post(client, **fields):
    data = {'name': 'Pat Prospect', 'email': EMAIL, 'phone': '', 'website': ''}
    data.update(fields)
    return client.post('/interest', data=data)


def count(app):
    with app.app_context():
        return InterestSignup.query.filter_by(email=EMAIL).count()


def test_get_renders_form(client):
    resp = client.get('/interest')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'name="email"' in html
    assert "Reply STOP to opt out." in html


def test_post_saves_and_thanks(app, client):
    resp = post(client)
    assert resp.status_code == 200
    assert "You're on the list" in resp.get_data(as_text=True)
    assert count(app) == 1


def test_resubmit_shows_same_thanks(app, client):
    post(client)
    resp = post(client, name='Pat Again')
    assert resp.status_code == 200
    assert "You're on the list" in resp.get_data(as_text=True)
    assert count(app) == 1


def test_honeypot_thanks_but_saves_nothing(app, client):
    resp = post(client, website='http://spam.example')
    assert resp.status_code == 200
    assert "You're on the list" in resp.get_data(as_text=True)
    assert count(app) == 0


def test_bad_phone_rerenders_with_values(app, client):
    resp = post(client, phone='12345')
    assert resp.status_code == 400
    html = resp.get_data(as_text=True)
    assert '10-digit US cell number' in html
    assert 'value="Pat Prospect"' in html
    assert 'value="12345"' in html
    assert count(app) == 0


def test_cross_origin_post_needs_no_csrf_token(app):
    """The marketing site cannot carry the app's CSRF token. Run with CSRF
    enforcement on (TESTING off) and prove an unrelated POST is still
    rejected, so the pass below is the exemption and not a disabled check."""
    app.config.update(TESTING=False, WTF_CSRF_ENABLED=True)
    c = app.test_client()
    resp = c.post('/interest',
                  data={'name': 'Pat Prospect', 'email': EMAIL, 'phone': ''},
                  headers={'Origin': 'https://twincitiesskiclub.org'})
    assert resp.status_code == 200
    assert count(app) == 1
    assert c.post('/admin/interest-list/1/delete').status_code == 400


def test_home_page_shows_form_when_registration_closed(client):
    # The scratch DB has no season with an open window today.
    html = client.get('/').get_data(as_text=True)
    assert 'action="/interest"' in html
```

The last line of `test_cross_origin_post_needs_no_csrf_token` posts to the admin delete route that Task 3 adds. It passes before Task 3 too: Flask runs `before_request` (where the CSRF check lives) before it raises a routing 404, so a token-less POST to any path gets 400.

`tests/interest/test_form_contract.py`:

```python
"""The two forms and the route must agree on field names."""
import re
from pathlib import Path

from app.interest.service import FIELDS, HONEYPOT

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = set(FIELDS) | {HONEYPOT}


def names_in(relative):
    return set(re.findall(r'\bname="([a-z_]+)"', (ROOT / relative).read_text()))


def test_app_partial_posts_the_fields_the_route_reads():
    assert names_in('app/templates/_interest_form.html') == EXPECTED
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test /workspace/tcsc-trips/.venv/bin/pytest tests/interest/test_routes.py tests/interest/test_form_contract.py -q`
Expected: FAIL. `/interest` returns 404 and the partial file does not exist.

- [ ] **Step 3: Write the route**

`app/routes/interest.py`:

```python
"""Public interest-list signup.

Both the marketing site's /join page and tcsc.ski's own pages post here. The
marketing site is another origin and cannot carry this app's CSRF token, so
the POST is exempt; the worst a forged POST can do is add a row, which a
direct POST could do anyway. Every response is a page on tcsc.ski: no
cross-site redirect.
"""
from flask import Blueprint, render_template, request

from app.interest import service
from app.security import csrf

interest = Blueprint('interest', __name__)


@interest.route('/interest', methods=['GET'])
def interest_form():
    return render_template('interest.html', values={}, errors={})


@interest.route('/interest', methods=['POST'])
@csrf.exempt
def interest_submit():
    if request.form.get(service.HONEYPOT):
        return render_template('interest_thanks.html')
    values, errors = service.validate(request.form)
    if errors:
        return render_template('interest.html', values=values, errors=errors), 400
    service.save_signup(values)
    return render_template('interest_thanks.html')
```

In `app/__init__.py` add `from .routes.interest import interest` beside the other route imports (alphabetical, after `from .routes.events import events`) and `app.register_blueprint(interest)` after `app.register_blueprint(events)`.

- [ ] **Step 4: Write the partial**

`app/templates/_interest_form.html`:

```html
{# Interest-list signup form. Field names are a contract with
   site/src/pages/join.astro and app/interest/service.py FIELDS;
   tests/interest/test_form_contract.py checks them. #}
{% set v = values or {} %}
{% set e = errors or {} %}
<div class="card">
  <span class="card__title">Get notified when registration opens</span>
  <p class="form-field__hint">Not a member yet? Leave your info and we'll reach out when the next registration window opens.</p>
  <form method="post" action="{{ url_for('interest.interest_submit') }}">
    <div class="form-field">
      <label class="form-field__label" for="interest-name">Name</label>
      <input class="form-input{% if e.name %} field-error{% endif %}" id="interest-name" name="name" type="text" autocomplete="name" maxlength="200" required value="{{ v.name or '' }}">
      {% if e.name %}<p class="form-field__hint" style="color: #c53030;">{{ e.name }}</p>{% endif %}
    </div>
    <div class="form-field">
      <label class="form-field__label" for="interest-email">Email</label>
      <input class="form-input{% if e.email %} field-error{% endif %}" id="interest-email" name="email" type="email" autocomplete="email" maxlength="255" required value="{{ v.email or '' }}">
      {% if e.email %}<p class="form-field__hint" style="color: #c53030;">{{ e.email }}</p>{% endif %}
    </div>
    <div class="form-field">
      <label class="form-field__label" for="interest-phone">Cell phone (optional)</label>
      <input class="form-input{% if e.phone %} field-error{% endif %}" id="interest-phone" name="phone" type="tel" inputmode="tel" autocomplete="tel" value="{{ v.phone or '' }}">
      {% if e.phone %}<p class="form-field__hint" style="color: #c53030;">{{ e.phone }}</p>{% endif %}
      <p class="form-field__hint">We'll text you when registration opens. Reply STOP to opt out.</p>
    </div>
    <div aria-hidden="true" style="position: absolute; left: -10000px;">
      <label for="interest-website">Leave this empty</label>
      <input id="interest-website" name="website" type="text" tabindex="-1" autocomplete="off">
    </div>
    <button class="btn btn--full" type="submit">Notify me</button>
  </form>
</div>
```

- [ ] **Step 5: Write the two standalone pages**

Both copy the `<head>` and page shell of `app/templates/index.html`.

`app/templates/interest.html`:

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Get notified · TCSC</title>
    <meta name="description" content="Hear from Twin Cities Ski Club when registration opens" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <link rel="icon" href="{{ url_for('static', filename='favicon.ico') }}" type="image/x-icon">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/normalize.css') }}" />
    <link rel="stylesheet" href="{{ url_for('static', filename='css/styles/main.css') }}" />
  </head>
  <body>
    <div class="page">
      <header class="page-header page-header--home">
        <img src="{{ url_for('static', filename='images/tcsc-logo.svg') }}" alt="TCSC Logo" class="page-header__logo page-header__logo--small">
        <div class="page-header__text">
          <h1 class="page-header__title">Twin Cities Ski Club</h1>
          <p class="page-header__subtitle">Get notified when registration opens</p>
        </div>
      </header>
      <div class="page-content">
        {% include '_interest_form.html' %}
        <div style="text-align: center; margin-top: 24px;">
          <a href="https://twincitiesskiclub.org" class="btn btn--secondary">&larr; twincitiesskiclub.org</a>
        </div>
      </div>
    </div>
  </body>
</html>
```

`app/templates/interest_thanks.html`: same `<head>` and header, with `<title>You're on the list · TCSC</title>`, and this page content:

```html
      <div class="page-content">
        <div class="card">
          <span class="card__title">You're on the list</span>
          <p class="form-field__hint">We'll email you when registration opens, and text you too if you left a number.</p>
        </div>
        <div style="text-align: center; margin-top: 24px;">
          <a href="https://twincitiesskiclub.org" class="btn btn--secondary">&larr; twincitiesskiclub.org</a>
        </div>
      </div>
```

- [ ] **Step 6: Include the partial on the home and season pages**

In `app/templates/index.html`, directly after the `{% endif %}` that closes `{% if season %}` (before `{% if trips %}`):

```html
        {% if not is_season_registration_open %}
        <div class="homepage-section">
          <div class="section-pill section-pill--membership">Get notified</div>
          <div style="margin-top: 16px;">
            {% include '_interest_form.html' %}
          </div>
        </div>
        {% endif %}
```

In `app/templates/season_detail.html`, between the season card's closing `</div>` and `<div style="text-align: center; margin-top: 24px;">`:

```html
        {% if not is_registration_open %}
        <div style="margin-top: 24px;">
          {% include '_interest_form.html' %}
        </div>
        {% endif %}
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test /workspace/tcsc-trips/.venv/bin/pytest tests/interest tests/test_security.py -q`
Expected: all pass. If `test_home_page_shows_form_when_registration_closed` fails because the scratch DB has an open season, check with `docker exec tcsc-postgres psql -U tcsc -d tcsc_trips_test -c "select id,name,returning_start,returning_end,new_start,new_end from season"` and report it rather than editing season rows.

- [ ] **Step 8: Commit**

```bash
git add app/routes/interest.py app/__init__.py app/templates/_interest_form.html app/templates/interest.html app/templates/interest_thanks.html app/templates/index.html app/templates/season_detail.html tests/interest/test_routes.py tests/interest/test_form_contract.py
git commit -m "Interest list: public signup form on tcsc.ski

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Admin page, CSV export and delete

**Files:**
- Create: `app/routes/admin_interest.py`, `app/templates/admin/interest_list.html`
- Modify: `app/__init__.py` (import and register `admin_interest_bp`)
- Modify: `app/templates/admin/partials/sidebar.html` (Members section, after the Roles link)
- Test: `tests/interest/test_admin.py`

**Interfaces:**
- Consumes: `service.rows_with_member_status()`, `InterestSignup` from Task 1; `admin_required` from `app/auth.py`; `utc_naive_to_central_naive` from `app/utils.py`.
- Produces: endpoints `admin_interest.interest_list` (`GET /admin/interest-list`), `admin_interest.interest_list_csv` (`GET /admin/interest-list/export.csv`), `admin_interest.interest_list_delete` (`POST /admin/interest-list/<int:signup_id>/delete`).

- [ ] **Step 1: Write the failing admin tests**

`tests/interest/test_admin.py`:

```python
import csv
import io

from app.interest import service
from app.interest.models import InterestSignup
from app.models import User, db

from .conftest import TEST_DOMAIN


def add(app, name, email, phone=''):
    with app.app_context():
        service.save_signup({'name': name, 'email': email, 'phone': phone})
        return InterestSignup.query.filter_by(email=email).one().id


def test_page_requires_admin(client):
    resp = client.get('/admin/interest-list')
    assert resp.status_code == 302


def test_page_lists_rows_with_member_status(app, admin_client):
    add(app, 'Pat Prospect', f'pat{TEST_DOMAIN}')
    with app.app_context():
        db.session.add(User(email=f'Mem{TEST_DOMAIN}', first_name='M',
                            last_name='Em', status='ACTIVE'))
        db.session.commit()
    add(app, 'Mem Ber', f'mem{TEST_DOMAIN}')
    html = admin_client.get('/admin/interest-list').get_data(as_text=True)
    assert f'pat{TEST_DOMAIN}' in html
    assert f'mem{TEST_DOMAIN}' in html
    assert 'ACTIVE' in html


def test_csv_has_every_row_and_raw_phone(app, admin_client):
    add(app, 'Pat Prospect', f'pat{TEST_DOMAIN}', '612-555-0101')
    resp = admin_client.get('/admin/interest-list/export.csv')
    assert resp.status_code == 200
    assert resp.mimetype == 'text/csv'
    rows = list(csv.DictReader(io.StringIO(resp.get_data(as_text=True))))
    mine = [r for r in rows if r['Email'] == f'pat{TEST_DOMAIN}']
    assert len(mine) == 1
    # Server-normalized phones skip the sanitizer: '+' must not gain a quote.
    assert mine[0]['Phone'] == '+16125550101'
    assert mine[0]['SMS consent'] != ''
    assert set(rows[0]) == {'Name', 'Email', 'Phone', 'Signed up',
                            'SMS consent', 'Member status'}


def test_csv_sanitizes_typed_text(app, admin_client):
    add(app, '=HYPERLINK("http://x")', f'evil{TEST_DOMAIN}')
    rows = list(csv.DictReader(io.StringIO(
        admin_client.get('/admin/interest-list/export.csv').get_data(as_text=True))))
    mine = [r for r in rows if r['Email'] == f'evil{TEST_DOMAIN}']
    assert mine[0]['Name'].startswith("'=")


def test_delete_removes_one_row(app, admin_client):
    keep = add(app, 'Keep', f'keep{TEST_DOMAIN}')
    drop = add(app, 'Drop', f'drop{TEST_DOMAIN}')
    resp = admin_client.post(f'/admin/interest-list/{drop}/delete')
    assert resp.status_code == 302
    with app.app_context():
        assert db.session.get(InterestSignup, drop) is None
        assert db.session.get(InterestSignup, keep) is not None


def test_delete_missing_row_is_404(admin_client):
    assert admin_client.post('/admin/interest-list/999999999/delete').status_code == 404
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test /workspace/tcsc-trips/.venv/bin/pytest tests/interest/test_admin.py -q`
Expected: FAIL with 404s.

- [ ] **Step 3: Write the admin routes**

`app/routes/admin_interest.py`:

```python
"""Admin view of the interest list: table, CSV export, per-row delete."""
import csv
import io
from datetime import date

from flask import Blueprint, Response, abort, flash, redirect, render_template, url_for

from app.auth import admin_required
from app.interest import service
from app.interest.models import InterestSignup
from app.models import db
from app.routes.admin_events import _sanitize_csv_value
from app.utils import utc_naive_to_central_naive

admin_interest_bp = Blueprint('admin_interest', __name__)

CSV_COLUMNS = ['Name', 'Email', 'Phone', 'Signed up', 'SMS consent', 'Member status']


def _central(dt):
    return utc_naive_to_central_naive(dt).strftime('%Y-%m-%d %H:%M') if dt else ''


@admin_interest_bp.route('/admin/interest-list')
@admin_required
def interest_list():
    return render_template('admin/interest_list.html',
                           rows=service.rows_with_member_status())


@admin_interest_bp.route('/admin/interest-list/export.csv')
@admin_required
def interest_list_csv():
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    for r in service.rows_with_member_status():
        s = r['signup']
        writer.writerow({
            # Name and email are typed by strangers; sanitize them. Phone and
            # timestamps are server-generated, and phones start with '+',
            # which the sanitizer would mangle.
            'Name': _sanitize_csv_value(s.name),
            'Email': _sanitize_csv_value(s.email),
            'Phone': s.phone_e164 or '',
            'Signed up': _central(s.created_at),
            'SMS consent': _central(s.sms_consent_at),
            'Member status': r['member_status'],
        })
    filename = f'interest-list-{date.today().isoformat()}.csv'
    return Response(out.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': f'attachment; filename="{filename}"'})


@admin_interest_bp.route('/admin/interest-list/<int:signup_id>/delete', methods=['POST'])
@admin_required
def interest_list_delete(signup_id):
    signup = db.session.get(InterestSignup, signup_id)
    if signup is None:
        abort(404)
    email = signup.email
    db.session.delete(signup)
    db.session.commit()
    flash(f'Removed {email} from the interest list.', 'success')
    return redirect(url_for('admin_interest.interest_list'))
```

In `app/__init__.py` add `from .routes.admin_interest import admin_interest_bp` (alphabetical, after `admin_events`) and `app.register_blueprint(admin_interest_bp)` after `app.register_blueprint(admin_events_bp)`.

- [ ] **Step 4: Write the admin template**

`app/templates/admin/interest_list.html`:

```html
{% extends 'admin/admin_base.html' %}

{% block title %}Interest list{% endblock %}

{% block content %}
<div class="flex items-center justify-between mb-6 flex-wrap gap-4">
    <div>
        <h1 class="text-2xl font-semibold text-tcsc-navy m-0">Interest list ({{ rows|length }})</h1>
        <p class="mt-1 text-sm text-zinc-500">People who asked to hear when registration opens. They are not members.
            "Member" shows a matching account by email or phone.</p>
    </div>
    <a href="{{ url_for('admin_interest.interest_list_csv') }}" class="bg-tcsc-navy text-white px-4 py-3 rounded-tcsc text-sm font-medium hover:opacity-90 transition-all">Export CSV</a>
</div>

<div class="bg-white p-6 rounded-tcsc border border-tcsc-gray-100">
    <div class="overflow-x-auto">
        <table class="w-full text-sm border-collapse">
            <thead>
                <tr class="text-left text-xs font-semibold uppercase text-zinc-500 border-b border-tcsc-gray-100">
                    <th class="py-2 pr-4">Name</th>
                    <th class="py-2 pr-4">Email</th>
                    <th class="py-2 pr-4">Phone</th>
                    <th class="py-2 pr-4">Signed up</th>
                    <th class="py-2 pr-4">Member</th>
                    <th class="py-2 pr-4"></th>
                </tr>
            </thead>
            <tbody>
                {% for r in rows %}
                <tr class="border-b border-tcsc-gray-100">
                    <td class="py-2 pr-4">{{ r.signup.name }}</td>
                    <td class="py-2 pr-4">{{ r.signup.email }}</td>
                    <td class="py-2 pr-4">{{ r.signup.phone_e164 or "" }}</td>
                    <td class="py-2 pr-4">{{ r.signup.created_at|central_time('%b %d, %Y') }}</td>
                    <td class="py-2 pr-4">{{ r.member_status }}</td>
                    <td class="py-2 pr-4 text-right">
                        <form method="post" action="{{ url_for('admin_interest.interest_list_delete', signup_id=r.signup.id) }}"
                              onsubmit="return confirm('Remove ' + {{ r.signup.email|tojson|forceescape }} + ' from the interest list?');">
                            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                            <button type="submit" class="text-red-600 hover:underline text-sm">Remove</button>
                        </form>
                    </td>
                </tr>
                {% else %}
                <tr><td class="py-3 text-zinc-500" colspan="6">Nobody on the list yet.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>
{% endblock %}
```

The email goes into the `onsubmit` JS through `tojson|forceescape`, not plain `{{ }}`. Autoescaped `'` becomes `&#39;`, which the attribute parser decodes back to `'` before the JS runs, so an address containing a quote (validation allows it) would break out of a hand-quoted string.

- [ ] **Step 5: Add the sidebar link**

In `app/templates/admin/partials/sidebar.html`, inside the Members section, after the Roles `</a>`:

```html
      <a href="{{ url_for('admin_interest.interest_list') }}"
         class="flex w-full items-center gap-3 rounded-lg px-2 py-2 text-sm font-medium transition-colors
                {% if request.endpoint == 'admin_interest.interest_list' %}bg-tcsc-navy/5 text-tcsc-navy{% else %}text-zinc-700 hover:bg-zinc-100{% endif %}">
        <svg class="w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 0 1-2.25 2.25h-15a2.25 2.25 0 0 1-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0 0 19.5 4.5h-15a2.25 2.25 0 0 0-2.25 2.25m19.5 0v.243a2.25 2.25 0 0 1-1.07 1.916l-7.5 4.615a2.25 2.25 0 0 1-2.36 0L3.32 8.91a2.25 2.25 0 0 1-1.07-1.916V6.75" />
        </svg>
        <span>Interest list</span>
      </a>
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test /workspace/tcsc-trips/.venv/bin/pytest tests/interest -q`
Expected: all pass, including `test_cross_origin_post_needs_no_csrf_token` from Task 2.

- [ ] **Step 7: Commit**

```bash
git add app/routes/admin_interest.py app/__init__.py app/templates/admin/interest_list.html app/templates/admin/partials/sidebar.html tests/interest/test_admin.py
git commit -m "Interest list: admin page, CSV export and delete

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Marketing site `/join` page and CTA routing

**Files:**
- Create: `site/src/pages/join.astro`
- Modify: `site/src/content/pages/home.yaml` (`cta_coming_soon_url`, `cta_closed_label`, `cta_closed_url`)
- Modify: `site/src/components/registrationCta.ts` (fallback urls and closed label)
- Modify: `site/tests/contentRefinements.test.mjs:113-170`
- Modify: `site/tests/seasonFallback.test.mjs:31-33`
- Create: `site/tests/joinPage.test.mjs`
- Modify: `site/package.json` (`test:refinement` list)
- Modify: `render.yaml:114` (static site CSP)
- Modify: `tests/interest/test_form_contract.py` (add the Astro check)

**Interfaces:**
- Consumes: `getRegistrationCta()` from `site/src/components/registrationCta.ts`, `datesLine()` from `site/src/lib/registrationCopy.ts`, `InnerPageLayout`. The POST target `https://tcsc.ski/interest` and the field names from Task 2.
- Produces: a built page at `dist/join.html` (the test build uses `build.format: 'file'`).

- [ ] **Step 1: Install site deps in the worktree**

Run: `cd site && npm ci`
Expected: completes. `site/node_modules` is gitignored.

- [ ] **Step 2: Write the failing tests**

Append to `tests/interest/test_form_contract.py`:

```python
def test_join_page_posts_the_fields_the_route_reads():
    assert names_in('site/src/pages/join.astro') == EXPECTED
```

`site/tests/joinPage.test.mjs`:

```js
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { JSDOM } from 'jsdom';

function page(slug) {
  const base = new URL('../dist/', import.meta.url);
  for (const candidate of [`${slug}/index.html`, `${slug}.html`]) {
    try {
      return readFileSync(new URL(candidate, base), 'utf8');
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
    }
  }
  throw new Error(`no built page for ${slug}`);
}

test('join page posts a plain form to tcsc.ski', () => {
  const { document } = new JSDOM(page('join')).window;
  const form = document.querySelector('form[action="https://tcsc.ski/interest"]');
  assert.ok(form, 'join page must post to https://tcsc.ski/interest');
  assert.equal(form.getAttribute('method'), 'post');
  assert.ok(form.querySelector('input[name="email"][type="email"][required]'));
  assert.ok(form.querySelector('input[name="name"][required]'));
  assert.ok(!form.querySelector('input[name="phone"][required]'), 'phone stays optional');
  assert.ok(form.textContent.includes("We'll text you when registration opens. Reply STOP to opt out."));
});

test('join page shows the opening dates when the season has them', () => {
  // scripts/test-build.mjs serves a fixture whose windows are in the future.
  const { document } = new JSDOM(page('join')).window;
  assert.match(document.body.textContent, /Returning members \w{3} \d{1,2}/);
});

test('static site CSP lets the join form post to tcsc.ski', () => {
  const blueprint = readFileSync(new URL('../../render.yaml', import.meta.url), 'utf8');
  assert.match(blueprint, /form-action 'self' https:\/\/tcsc\.ski;/);
});
```

In `site/package.json`, add `tests/joinPage.test.mjs` to the end of the `node --test` list in `test:refinement`.

In `site/tests/contentRefinements.test.mjs`, inside `wires the confirmed fall registration copy to the home CTA target`:

1. Replace

```js
  assert.equal(
    yamlScalar(source.home, 'cta_coming_soon_url'),
    `${MARKETING_ORIGIN}/#registration`,
  );
```

with

```js
  assert.equal(yamlScalar(source.home, 'cta_coming_soon_url'), `${MARKETING_ORIGIN}/join`);
  assert.equal(yamlScalar(source.home, 'cta_closed_url'), `${MARKETING_ORIGIN}/join`);
  assert.equal(yamlScalar(source.home, 'cta_closed_label'), 'Get notified');
```

2. Replace the block from `const outsideStrip = html.home.replace(registration, '');` through `for (const url of anchorTargets) assert.equal(url.pathname, '/');` with:

```js
  // While registration is coming_soon, the hero, nav and mobile CTAs send
  // people to the interest-list form on /join.
  const outsideStrip = html.home.replace(registration, '');
  const joinTargets = [...outsideStrip.matchAll(/<a\b([^>]*)>/gi)]
    .map(([, attributes]) => attributes.match(/\bhref=(['"])(.*?)\1/i))
    .filter(Boolean)
    .map((href) => new URL(decodeHtml(href[2]), MARKETING_ORIGIN))
    .filter((url) => url.origin === MARKETING_ORIGIN && url.pathname === '/join');

  assert.ok(
    joinTargets.length > 0,
    'hero/nav/mobile CTAs must target /join while registration is coming_soon',
  );
```

Leave the rest of that test (exactly one `id="registration"`, the strip button must not link to its own section) unchanged.

In `site/tests/seasonFallback.test.mjs`, replace the last two statements of the test:

```js
  // A closed build sends everyone to the interest-list form. That page links
  // returning members on to tcsc.ski, which reads the database live, so a
  // fallback build during an open window still gets members to registration.
  const strip = document.querySelector('#registration a[href]');
  assert.equal(strip.getAttribute('href'), 'https://twincitiesskiclub.org/join');
```

Add to `site/tests/joinPage.test.mjs`:

```js
test('join page links members on to tcsc.ski', () => {
  const { document } = new JSDOM(page('join')).window;
  assert.ok(document.querySelector('main a[href="https://tcsc.ski/"]'));
});
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test /workspace/tcsc-trips/.venv/bin/pytest tests/interest/test_form_contract.py -q`
Expected: FAIL, `join.astro` does not exist.

Run: `cd site && npm run test:refinement`
Expected: FAIL in `joinPage.test.mjs` (no built page) and `contentRefinements.test.mjs` (yaml still points at `#registration`).

- [ ] **Step 4: Write the page**

`site/src/pages/join.astro`:

```astro
---
// /join: the interest-list form. Every non-open registration CTA lands here.
// A plain HTML form, no client JS: it posts straight to the Flask app, which
// answers with its own thanks or error page on tcsc.ski. Field names are a
// contract with app/interest/service.py (tests/interest/test_form_contract.py).
// The static site's CSP must allow this form-action (render.yaml).
import InnerPageLayout from '@/layouts/InnerPageLayout.astro';
import { getRegistrationCta } from '@/components/registrationCta';
import { datesLine } from '@/lib/registrationCopy';

const action = import.meta.env.PUBLIC_INTEREST_URL ?? 'https://tcsc.ski/interest';
const cta = await getRegistrationCta();
const dates = datesLine(cta.windows);

const input =
  'mt-1 block w-full rounded-md border border-ink/20 bg-white px-3 py-2 text-ink focus:border-mint-deep focus:outline-none focus:ring-2 focus:ring-mint';
const label = 'block text-sm font-semibold text-navy';
---
<InnerPageLayout
  title="Get notified · Twin Cities Ski Club"
  description="Leave your email and we'll tell you when Twin Cities Ski Club registration opens."
  headline="Get notified when registration opens"
  subhead={dates ? `Next registration: ${dates}.` : "We'll reach out as soon as the next registration dates are set."}
>
  <div class="safe-inline-6 mx-auto max-w-xl px-6 py-12">
    <form method="post" action={action} class="space-y-5">
      <div>
        <label class={label} for="join-name">Name</label>
        <input class={input} id="join-name" name="name" type="text" autocomplete="name" maxlength="200" required />
      </div>
      <div>
        <label class={label} for="join-email">Email</label>
        <input class={input} id="join-email" name="email" type="email" autocomplete="email" maxlength="255" required />
      </div>
      <div>
        <label class={label} for="join-phone">Cell phone <span class="font-normal text-ink/60">(optional)</span></label>
        <input class={input} id="join-phone" name="phone" type="tel" inputmode="tel" autocomplete="tel" />
        <p class="mt-1 text-sm text-ink/70">We'll text you when registration opens. Reply STOP to opt out.</p>
      </div>
      <div aria-hidden="true" class="absolute -left-[10000px]">
        <label for="join-website">Leave this empty</label>
        <input id="join-website" name="website" type="text" tabindex="-1" autocomplete="off" />
      </div>
      <button type="submit" class="inline-flex items-center px-6 py-3 rounded-md bg-navy text-mint font-semibold text-sm transition-colors duration-150 hover:bg-navy-deep">Notify me</button>
    </form>
    <p class="mt-10 text-sm text-ink/70">
      Already a member? Registration and your account live at
      <a href="https://tcsc.ski/" class="font-semibold text-navy underline underline-offset-4">tcsc.ski</a>.
    </p>
  </div>
</InnerPageLayout>
```

If `astro check` reports an unknown color token (`ink`, `mint-deep`, `navy-deep`), use the nearest token from `site/tailwind.config.ts` or `site/src/styles/` instead. All of them appear in existing components.

- [ ] **Step 5: Point the CTAs at `/join`**

`site/src/content/pages/home.yaml`:

```yaml
cta_coming_soon_url: https://twincitiesskiclub.org/join
cta_closed_label: Get notified
cta_closed_url: https://twincitiesskiclub.org/join
```

`cta_coming_soon_label` stays `Fall registration dates`. It is editable in Keystatic.

`site/src/components/registrationCta.ts`, in the returned object:

```ts
    url_coming_soon: d?.cta_coming_soon_url ?? d?.cta_closed_url ?? '/join',
    label_closed: d?.cta_closed_label ?? 'Get notified',
    url_closed: d?.cta_closed_url ?? '/join',
```

Update the comment above `getRegistrationCta` that says a closed state's "destination is tcsc.ski, which reads the database live and shows the real opening date". The closed destination is now `/join`, which shows the dates from the same build plus the form. The safe-direction argument (fall back to `closed`, never `open`) still holds.

`render.yaml` line 114: change `form-action 'self';` to `form-action 'self' https://tcsc.ski;`.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test /workspace/tcsc-trips/.venv/bin/pytest tests/interest -q`
Expected: all pass.

Run: `cd site && npm run check && npm run test:refinement && npm run test:fallback` (`test:fallback` rebuilds the whole site twice; allow a few minutes)
Expected: `astro check` reports 0 errors; every `node --test` file passes.

- [ ] **Step 7: Commit**

```bash
git add site/src/pages/join.astro site/src/content/pages/home.yaml site/src/components/registrationCta.ts site/tests/contentRefinements.test.mjs site/tests/seasonFallback.test.mjs site/tests/joinPage.test.mjs site/package.json render.yaml tests/interest/test_form_contract.py
git commit -m "Marketing site: /join interest-list form; non-open CTAs land there

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: End-to-end check and PR

**Files:** none new. Screenshots go in the session scratchpad, not the repo.

- [ ] **Step 1: Run the full suites**

Run: `DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test /workspace/tcsc-trips/.venv/bin/pytest -q -x --ignore=test_practice_post.py`
Expected: no new failures compared with `main`. If anything fails, run the same test on a clean `main` checkout before blaming this branch.

Run: `cd site && npm run test:refinement && npm run test:sponsors`
Expected: pass.

- [ ] **Step 2: Walk the real flow**

Start Flask against the scratch DB in a herdr pane on a port in this project's block (see `/workspace/unraid-stacks/PORTS.md`), not the foreground. Build the site with `PUBLIC_INTEREST_URL=http://127.0.0.1:<port>/interest` and serve `site/dist` with `npx astro preview`, also in a herdr pane.

With headless Chromium (memory: playwright from `/workspace/resume` with the bookworm `.deb` libs on `LD_LIBRARY_PATH`), at 375px wide:
1. Open `/join`, fill the form, submit. Expect the tcsc.ski thanks page.
2. Submit again with a phone of `12345`. Expect the error re-render with typed values.
3. Open the tcsc.ski home page. Expect the "Get notified" section.
4. Log in as admin, open `/admin/interest-list`. Expect the row. Download the CSV and check the phone column has no apostrophe.

Screenshot steps 1, 3 and 4. Delete the test rows afterward.

- [ ] **Step 3: Push and open the PR**

```bash
git push -u origin interest-list
gh pr create --title "Interest list: get notified when registration opens" --body "$(cat <<'EOF'
## What

- Marketing site `/join` page: name, email, optional cell with SMS consent. Every non-open registration CTA now lands there.
- tcsc.ski shows the same form on the home page and on a closed season's page.
- `POST /interest` saves to a new `interest_signups` table. It never touches `User`.
- `/admin/interest-list`: table with each row's matching member status, CSV export, per-row remove.

Spec: `docs/superpowers/specs/2026-10-05-interest-list-design.md`

## Deploy notes

- One migration (`7a1c5e9d3b20`), applied by the release phase.
- `render.yaml` changes the static site's CSP `form-action` to allow `https://tcsc.ski`. Confirm the live header after deploy with `curl -sI https://twincitiesskiclub.org/join | grep -i content-security`. If Render didn't apply blueprint headers, set it in the dashboard, or the form silently does nothing.

## Testing

- `tests/interest/` (service, routes, CSRF exemption, admin, CSV, form-field contract)
- `site`: `astro check`, `test:refinement` including the new `joinPage.test.mjs`
- Manual walk at 375px: screenshots below

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Attach the screenshots to the PR as a comment.
