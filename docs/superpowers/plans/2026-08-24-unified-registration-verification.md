# Unified Registration Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every season registrant start at phone entry and verify by SMS, with all branch decisions made by one server-side resolver instead of the client.

**Architecture:** A pure function `resolve_registration_step()` in `app/seasons/resolution.py` returns one of seven outcomes given a verified-identity session, a season, the current time, and an optional late-link invite payload. A thin endpoint exposes it. `app/static/script.js` stops deciding anything and renders the verdict it is handed. The new-member skip link is deleted, so SMS verification is the only front door.

**Tech Stack:** Flask, SQLAlchemy, Alembic, pytest with a live PostgreSQL 18 container, vanilla JS (no framework), Twilio Verify, Resend, Stripe.

**Spec:** `docs/superpowers/specs/2026-08-24-unified-registration-verification-design.md`

## Global Constraints

- **Status fields are plain strings, not Enums.** `UserStatus` and `UserSeasonStatus` in `app/constants.py` are simple classes. Never call `.value` on them. Only `MemberType` is a true Enum.
- **Prices are in cents.** `season.price_cents` is an integer.
- **Timestamps are UTC in the database.** Use `app/utils.py` helpers (`now_central_naive()`, `today_central()`) for display-facing dates, `datetime.utcnow()` for comparisons against window bounds.
- **Capture method is a business rule.** Season/new = `manual`, season/returning = `automatic`, trips = always `manual`, events = `automatic`. Do not "simplify" this.
- **Dev entrypoint is `./scripts/dev.sh`.** Never hand-run `flask run`; you get no database and no Stripe webhooks.
- **Tests need the local PostgreSQL container.** `docker start tcsc-postgres` first. `tests/_db_guard.py` blocks non-local databases.
- **Copy rules, enforced on every member-facing string in this feature:**
  - Headline 6 words or fewer.
  - Body 2 sentences, 25 words maximum.
  - Second person, active, present tense. "We texted you a code," never "A code has been sent."
  - Buttons are verbs. "Text me a code," not "Continue."
  - Never blame the member. "That code didn't match," not "You entered an invalid code."
  - Every screen touching a card says what happens to it, in the fewest words that are still true.
  - **No em dashes.** Periods and commas.
- **Alembic head at plan time is `6fe27563d4aa`.** Chain new migrations from the then-current head, not blindly from this value.

---

## File Structure

**Create**
- `app/seasons/resolution.py`: the resolver. One public function, seven outcome constants. No Flask imports and no request access, so it is testable as a plain function.
- `tests/registration/test_resolution.py`: one test per outcome, plus the precedence pairs.
- `migrations/versions/<rev>_add_review_note_to_user_seasons.py`
- Phase 2: `migrations/versions/<rev>_add_registration_reminders.py`

**Modify**
- `app/models.py`: the `UserSeason.review_note` column, and the Phase 2 `RegistrationReminder` model.
- `app/routes/verify.py`: `/api/verify/resolve` and `/api/verify/email/lookup`.
- `app/routes/registration.py`: the POST path calls the resolver. Drops the inline identity logic and the `status` shim.
- `app/routes/payments.py`: drops the email-mismatch demotion, adds `user_id` to intent metadata.
- `app/utils.py`: drops status validation from `validate_registration_form`.
- `app/templates/season_register.html`: deletes the skip link, adds the outcome panels, copy pass.
- `app/static/script.js`: renders verdicts, deletes branch logic, copy pass.
- `config/sms.yaml`: the Phase 2 reminder template.
- `app/scheduler.py`: the Phase 2 cron sweep.

---

## Task 1: The resolver

**Files:**
- Create: `app/seasons/resolution.py`
- Test: `tests/registration/test_resolution.py`

**Interfaces:**
- Consumes: `User.get_by_phone()`, `User.is_returning`, `UserSeason.get_for_user_season()`, `Season.is_open_for()`. All existing.
- Produces: `resolve_registration_step(identity, season, now, invite_payload=None) -> tuple[str, dict]` and the seven module-level outcome constants `VERIFY_PHONE`, `NEED_EMAIL`, `ALREADY_REGISTERED`, `WINDOW_NOT_YET_OPEN`, `WINDOW_ENDED`, `WIZARD_RETURNING`, `WIZARD_NEW`. Every later task imports from here.

- [ ] **Step 1: Write the failing tests**

Create `tests/registration/test_resolution.py`:

```python
from datetime import datetime, timedelta, date

import pytest

from app import create_app
from app.constants import UserSeasonStatus, UserStatus
from app.models import db, Season, User, UserSeason
from app.seasons import resolution

PHONE_A = "+16125550301"
PHONE_B = "+16125550302"


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"
    )
    return app


@pytest.fixture
def ctx(app):
    with app.app_context():
        yield


@pytest.fixture
def season(ctx):
    now = datetime.utcnow()
    s = Season(name="Resolution Test", year=2098, price_cents=15000,
               season_type='winter',
               start_date=date(2098, 11, 1), end_date=date(2099, 3, 1),
               returning_start=now - timedelta(days=1),
               returning_end=now + timedelta(days=30),
               new_start=now - timedelta(days=1),
               new_end=now + timedelta(days=30))
    db.session.add(s)
    db.session.commit()
    yield s
    UserSeason.query.filter_by(season_id=s.id).delete()
    db.session.delete(Season.query.get(s.id))
    db.session.commit()


def make_user(email, phone, first="Test"):
    u = User(email=email, first_name=first, last_name="Case",
             status=UserStatus.PENDING, phone_e164=phone,
             phone="612-555-0301", date_of_birth=date(1990, 1, 1),
             tshirt_size="M", emergency_contact_name="Em",
             emergency_contact_relation="friend",
             emergency_contact_phone="612-555-0999",
             emergency_contact_email="em@test.com")
    db.session.add(u)
    db.session.commit()
    return u


def ident(phone, user_id=None):
    return {'phone_e164': phone, 'user_id': user_id,
            'ts': datetime.utcnow().isoformat()}


def cleanup(*users):
    for u in users:
        UserSeason.query.filter_by(user_id=u.id).delete()
        db.session.delete(u)
    db.session.commit()


def test_no_identity_asks_for_phone(season):
    outcome, ctxd = resolution.resolve_registration_step(
        None, season, datetime.utcnow())
    assert outcome == resolution.VERIFY_PHONE


def test_verified_phone_no_match_is_new(season):
    outcome, ctxd = resolution.resolve_registration_step(
        ident(PHONE_A), season, datetime.utcnow())
    assert outcome == resolution.WIZARD_NEW
    assert ctxd['member_type'] == 'new'
    assert ctxd['first_name'] is None


def test_shared_phone_needs_email(season):
    a = make_user("share-a@test.com", PHONE_B, "Jane")
    b = make_user("share-b@test.com", PHONE_B, "Sam")
    try:
        outcome, ctxd = resolution.resolve_registration_step(
            ident(PHONE_B), season, datetime.utcnow())
        assert outcome == resolution.NEED_EMAIL
    finally:
        cleanup(a, b)


def test_resolved_active_history_is_returning(season):
    u = make_user("ret@test.com", PHONE_A, "Rita")
    past = Season(name="Past", year=2097, price_cents=1000,
                  season_type='winter',
                  start_date=date(2097, 11, 1), end_date=date(2098, 3, 1))
    db.session.add(past)
    db.session.commit()
    db.session.add(UserSeason(user_id=u.id, season_id=past.id,
                              registration_type='new',
                              registration_date=date(2097, 10, 1),
                              status=UserSeasonStatus.ACTIVE))
    db.session.commit()
    try:
        outcome, ctxd = resolution.resolve_registration_step(
            ident(PHONE_A, u.id), season, datetime.utcnow())
        assert outcome == resolution.WIZARD_RETURNING
        assert ctxd['first_name'] == "Rita"
    finally:
        UserSeason.query.filter_by(user_id=u.id).delete()
        db.session.commit()
        cleanup(u)
        db.session.delete(Season.query.get(past.id))
        db.session.commit()


def test_resolved_without_active_history_is_new(season):
    """Registered last year, lost the lottery. Known row, new pricing."""
    u = make_user("lost@test.com", PHONE_A, "Lou")
    try:
        outcome, ctxd = resolution.resolve_registration_step(
            ident(PHONE_A, u.id), season, datetime.utcnow())
        assert outcome == resolution.WIZARD_NEW
        assert ctxd['first_name'] == "Lou"
    finally:
        cleanup(u)


def test_already_registered_stops_before_the_form(season):
    u = make_user("dupe@test.com", PHONE_A, "Dana")
    db.session.add(UserSeason(user_id=u.id, season_id=season.id,
                              registration_type='new',
                              registration_date=date.today(),
                              status=UserSeasonStatus.PENDING_LOTTERY))
    db.session.commit()
    try:
        outcome, ctxd = resolution.resolve_registration_step(
            ident(PHONE_A, u.id), season, datetime.utcnow())
        assert outcome == resolution.ALREADY_REGISTERED
        assert ctxd['status'] == UserSeasonStatus.PENDING_LOTTERY
        assert ctxd['season_name'] == season.name
    finally:
        cleanup(u)


def test_dropped_registration_does_not_block(season):
    u = make_user("dropped@test.com", PHONE_A, "Drew")
    db.session.add(UserSeason(user_id=u.id, season_id=season.id,
                              registration_type='new',
                              registration_date=date.today(),
                              status=UserSeasonStatus.DROPPED_LOTTERY))
    db.session.commit()
    try:
        outcome, _ = resolution.resolve_registration_step(
            ident(PHONE_A, u.id), season, datetime.utcnow())
        assert outcome == resolution.WIZARD_NEW
    finally:
        cleanup(u)


def test_window_not_yet_open_carries_the_date(season):
    season.new_start = datetime.utcnow() + timedelta(days=4)
    season.new_end = datetime.utcnow() + timedelta(days=40)
    db.session.commit()
    outcome, ctxd = resolution.resolve_registration_step(
        ident(PHONE_A), season, datetime.utcnow())
    assert outcome == resolution.WINDOW_NOT_YET_OPEN
    assert ctxd['member_type'] == 'new'
    assert ctxd['opens_at'] == season.new_start


def test_window_ended_carries_the_date(season):
    season.new_start = datetime.utcnow() - timedelta(days=40)
    season.new_end = datetime.utcnow() - timedelta(days=4)
    db.session.commit()
    outcome, ctxd = resolution.resolve_registration_step(
        ident(PHONE_A), season, datetime.utcnow())
    assert outcome == resolution.WINDOW_ENDED
    assert ctxd['closed_at'] == season.new_end


def test_unconfigured_window_reads_as_not_yet_open(season):
    season.new_start = None
    season.new_end = None
    db.session.commit()
    outcome, ctxd = resolution.resolve_registration_step(
        ident(PHONE_A), season, datetime.utcnow())
    assert outcome == resolution.WINDOW_NOT_YET_OPEN
    assert ctxd['opens_at'] is None


def test_valid_invite_bypasses_a_closed_window(season):
    season.new_start = datetime.utcnow() - timedelta(days=40)
    season.new_end = datetime.utcnow() - timedelta(days=4)
    db.session.commit()
    outcome, _ = resolution.resolve_registration_step(
        ident(PHONE_A), season, datetime.utcnow(),
        invite_payload={'season_id': season.id, 'email': 'x@test.com'})
    assert outcome == resolution.WIZARD_NEW


def test_invite_for_another_season_does_not_bypass(season):
    season.new_start = datetime.utcnow() - timedelta(days=40)
    season.new_end = datetime.utcnow() - timedelta(days=4)
    db.session.commit()
    outcome, _ = resolution.resolve_registration_step(
        ident(PHONE_A), season, datetime.utcnow(),
        invite_payload={'season_id': season.id + 9999, 'email': 'x@test.com'})
    assert outcome == resolution.WINDOW_ENDED


def test_already_registered_beats_a_closed_window(season):
    """Precedence: 'you're already in' is more useful than 'you're too late'."""
    u = make_user("both@test.com", PHONE_A, "Bo")
    db.session.add(UserSeason(user_id=u.id, season_id=season.id,
                              registration_type='new',
                              registration_date=date.today(),
                              status=UserSeasonStatus.PENDING_LOTTERY))
    season.new_start = datetime.utcnow() - timedelta(days=40)
    season.new_end = datetime.utcnow() - timedelta(days=4)
    db.session.commit()
    try:
        outcome, _ = resolution.resolve_registration_step(
            ident(PHONE_A, u.id), season, datetime.utcnow())
        assert outcome == resolution.ALREADY_REGISTERED
    finally:
        cleanup(u)


def test_shared_phone_beats_already_registered(season):
    """Unresolved multi-match cannot claim anyone's registration."""
    a = make_user("multi-a@test.com", PHONE_B, "Jane")
    b = make_user("multi-b@test.com", PHONE_B, "Sam")
    db.session.add(UserSeason(user_id=a.id, season_id=season.id,
                              registration_type='new',
                              registration_date=date.today(),
                              status=UserSeasonStatus.PENDING_LOTTERY))
    db.session.commit()
    try:
        outcome, _ = resolution.resolve_registration_step(
            ident(PHONE_B), season, datetime.utcnow())
        assert outcome == resolution.NEED_EMAIL
    finally:
        cleanup(a, b)


def test_stale_user_id_falls_back_to_phone_match(season):
    """A session pointing at a deleted account must not crash."""
    outcome, _ = resolution.resolve_registration_step(
        ident(PHONE_A, 99999999), season, datetime.utcnow())
    assert outcome == resolution.WIZARD_NEW
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
docker start tcsc-postgres
source env/bin/activate
pytest tests/registration/test_resolution.py -v
```

Expected: collection error, `ModuleNotFoundError: No module named 'app.seasons.resolution'`.

- [ ] **Step 3: Write the resolver**

Create `app/seasons/resolution.py`:

```python
"""Which registration screen a visitor should see.

One function, one verdict. The client renders it; the client does not
decide it. Keeping the rule here means every edge case is a pytest case
instead of a jsdom case, and a bug surfaces before merge rather than in
a member's browser at noon on opening day.
"""
from app.constants import UserSeasonStatus
from app.models import User, UserSeason

VERIFY_PHONE = 'verify_phone'
NEED_EMAIL = 'need_email'
ALREADY_REGISTERED = 'already_registered'
WINDOW_NOT_YET_OPEN = 'window_not_yet_open'
WINDOW_ENDED = 'window_ended'
WIZARD_RETURNING = 'wizard_returning'
WIZARD_NEW = 'wizard_new'

# A registration in either of these states occupies the member's spot.
# Anything DROPPED_* left the season, so they may register again.
HOLDS_A_SPOT = (UserSeasonStatus.ACTIVE, UserSeasonStatus.PENDING_LOTTERY)


def resolve_registration_step(identity, season, now, invite_payload=None):
    """Return (outcome, context) for this visitor and season.

    identity: the verified-identity session dict from
        app.verify.service.get_verified_identity(), or None.
    season: a Season row.
    now: UTC datetime, compared against the season's window bounds.
    invite_payload: a verified late-link payload, or None. A valid one
        for this season suppresses both window outcomes, matching what
        season_register and create_season_payment_intent already do.

    Outcomes are checked in a deliberate order; see the design doc.
    """
    if not identity:
        return VERIFY_PHONE, {}

    user = None
    if identity.get('user_id'):
        # A stale id (account deleted between steps) resolves to None and
        # falls through to the phone match rather than raising.
        user = User.query.get(identity['user_id'])

    if user is None:
        matches = User.get_by_phone(identity['phone_e164'])
        if len(matches) > 1:
            # Households share numbers. The phone cannot say which member
            # this is, so an email code has to. Checked before
            # already_registered so an unresolved visitor can never be
            # shown someone else's registration.
            return NEED_EMAIL, {'reason': 'multiple'}

    if user is not None:
        user_season = UserSeason.get_for_user_season(user.id, season.id)
        if user_season is not None and user_season.status in HOLDS_A_SPOT:
            return ALREADY_REGISTERED, {
                'first_name': user.first_name,
                'season_name': season.name,
                'status': user_season.status,
                'member_type': user_season.registration_type,
            }

    is_returning = bool(user is not None and user.is_returning)
    member_type = 'returning' if is_returning else 'new'

    invite_ok = (invite_payload is not None
                 and invite_payload.get('season_id') == season.id)

    if not invite_ok and not season.is_open_for(member_type, now):
        if is_returning:
            start, end = season.returning_start, season.returning_end
        else:
            start, end = season.new_start, season.new_end
        # is_open_for treats a half-configured window as closed, so an
        # unset bound reads as "not yet", never as "you missed it".
        if start is None or end is None:
            return WINDOW_NOT_YET_OPEN, {'member_type': member_type,
                                         'opens_at': None}
        if now < start:
            return WINDOW_NOT_YET_OPEN, {'member_type': member_type,
                                         'opens_at': start}
        return WINDOW_ENDED, {'member_type': member_type, 'closed_at': end}

    outcome = WIZARD_RETURNING if is_returning else WIZARD_NEW
    return outcome, {
        'first_name': user.first_name if user is not None else None,
        'member_type': member_type,
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
pytest tests/registration/test_resolution.py -v
```

Expected: 15 passed.

- [ ] **Step 5: Commit**

```bash
git add app/seasons/resolution.py tests/registration/test_resolution.py
git commit -m "Add registration step resolver

One function decides which screen a registrant sees. Pure, so every
edge case is a pytest case."
```

---

## Task 2: `UserSeason.review_note`

**Files:**
- Modify: `app/models.py:322` (immediately after the `needs_review` column)
- Create: `migrations/versions/<rev>_add_review_note_to_user_seasons.py`
- Test: `tests/registration/test_resolution.py` (append)

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `UserSeason.review_note`, nullable `String(255)`. Tasks 6 and 8 write it; the admin review page reads it.

- [ ] **Step 1: Write the failing test**

Append to `tests/registration/test_resolution.py`:

```python
def test_review_note_defaults_to_null(season):
    u = make_user("note@test.com", PHONE_A, "Nora")
    us = UserSeason(user_id=u.id, season_id=season.id,
                    registration_type='new',
                    registration_date=date.today(),
                    status=UserSeasonStatus.PENDING_LOTTERY)
    db.session.add(us)
    db.session.commit()
    try:
        assert us.review_note is None
        us.review_note = "no verified phone"
        db.session.commit()
        assert UserSeason.get_for_user_season(
            u.id, season.id).review_note == "no verified phone"
    finally:
        cleanup(u)
```

- [ ] **Step 2: Run it to verify it fails**

```bash
pytest tests/registration/test_resolution.py::test_review_note_defaults_to_null -v
```

Expected: FAIL, `AttributeError: 'UserSeason' object has no attribute 'review_note'`.

- [ ] **Step 3: Add the column**

In `app/models.py`, directly below the `needs_review` column in `class UserSeason`:

```python
    needs_review = db.Column(db.Boolean, nullable=False, default=False, server_default='false')
    # Why the row was flagged, for the admin review page. "claims Jane R.
    # (id 412), couldn't verify email" beats a bare checkbox.
    review_note = db.Column(db.String(255))
```

- [ ] **Step 4: Generate and inspect the migration**

```bash
source env/bin/activate
flask db migrate -m "add review_note to user_seasons"
```

Open the generated file under `migrations/versions/`. It must contain exactly this and nothing else (Alembic autogenerate sometimes picks up unrelated drift; delete anything that is not this column):

```python
def upgrade():
    op.add_column('user_seasons',
                  sa.Column('review_note', sa.String(length=255), nullable=True))


def downgrade():
    op.drop_column('user_seasons', 'review_note')
```

Confirm `down_revision` points at the current head. Check with:

```bash
flask db heads
```

- [ ] **Step 5: Apply it and run the test**

```bash
flask db upgrade
pytest tests/registration/test_resolution.py::test_review_note_defaults_to_null -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/models.py migrations/versions/ tests/registration/test_resolution.py
git commit -m "Add UserSeason.review_note

needs_review says something is off. This says what."
```

---

## Task 3: Resolve and email-lookup endpoints

**Files:**
- Modify: `app/routes/verify.py`
- Test: `tests/registration/test_verify_routes.py` (append)

**Interfaces:**
- Consumes: `resolve_registration_step`, `WIZARD_NEW`, `NEED_EMAIL` and siblings from Task 1.
- Produces: `GET /api/verify/resolve?season_id=N[&invite=TOKEN]` returning `{outcome, context, user}`, and `POST /api/verify/email/lookup` returning `{ok, exists}`. Task 4 and Task 5 call both.

The resolve endpoint folds in the prefill payload so the client makes one call, not two. `/api/verify/prefill` stays for now; Task 5 removes its last caller.

- [ ] **Step 1: Write the failing tests**

`tests/registration/test_verify_routes.py` already has `app` and `client` fixtures but no season fixture. Add this one first:

```python
@pytest.fixture
def season(app):
    with app.app_context():
        now = datetime.utcnow()
        s = Season(name="Verify Route Test", year=2095, price_cents=15000,
                   season_type='winter',
                   start_date=date(2095, 11, 1), end_date=date(2096, 3, 1),
                   returning_start=now - timedelta(days=1),
                   returning_end=now + timedelta(days=30),
                   new_start=now - timedelta(days=1),
                   new_end=now + timedelta(days=30))
        db.session.add(s)
        db.session.commit()
        yield s.id
        db.session.delete(Season.query.get(s.id))
        db.session.commit()
```

Add `Season` and `VerificationAttempt` to the module's `app.models` import, `UserStatus` to its `app.constants` import, and `from datetime import date, timedelta` alongside the existing `datetime` import. Then append the tests:

```python
def test_resolve_without_identity_asks_for_phone(client, season):
    resp = client.get(f'/api/verify/resolve?season_id={season}')
    assert resp.status_code == 200
    assert resp.get_json()['outcome'] == 'verify_phone'


def test_resolve_unknown_season_404s(client):
    assert client.get('/api/verify/resolve?season_id=99999999').status_code == 404


def test_email_lookup_reports_existence_without_sending(client, app):
    with app.app_context():
        u = User(email="lookup@test.com", first_name="Look", last_name="Up",
                 status=UserStatus.PENDING, date_of_birth=date(1990, 1, 1),
                 tshirt_size="M", emergency_contact_name="Em",
                 emergency_contact_relation="friend",
                 emergency_contact_phone="612-555-0999",
                 emergency_contact_email="em@test.com")
        db.session.add(u)
        db.session.commit()
        uid = u.id
    try:
        hit = client.post('/api/verify/email/lookup',
                          json={'email': 'lookup@test.com'}).get_json()
        assert hit == {'ok': True, 'exists': True}
        miss = client.post('/api/verify/email/lookup',
                           json={'email': 'nobody@test.com'}).get_json()
        assert miss == {'ok': True, 'exists': False}
    finally:
        with app.app_context():
            db.session.delete(User.query.get(uid))
            db.session.commit()


def test_email_lookup_is_rate_limited(client, app):
    """Otherwise it is an unlimited membership-enumeration oracle."""
    with app.app_context():
        VerificationAttempt.query.delete()
        db.session.commit()
    seen_limit = False
    for i in range(15):
        body = client.post('/api/verify/email/lookup',
                           json={'email': f'probe{i}@test.com'}).get_json()
        if body['ok'] is False:
            seen_limit = True
            break
    assert seen_limit, "lookup never rate-limited across 15 distinct probes"
```

- [ ] **Step 2: Run them to verify they fail**

```bash
pytest tests/registration/test_verify_routes.py -v -k "resolve or lookup"
```

Expected: FAIL with 404s, because neither route exists.

- [ ] **Step 3: Add the endpoints**

In `app/routes/verify.py`, add these imports at the top:

```python
from app import late_link
from app.models import Season
from app.seasons.resolution import resolve_registration_step
```

Then append both routes:

```python
def _prefill_payload(user):
    """The wizard's starting values for a resolved member."""
    if user is None:
        return None
    return {
        'firstName': user.first_name,
        'lastName': user.last_name,
        'email': user.email,
        'pronouns': user.pronouns,
        'dob': user.date_of_birth.isoformat() if user.date_of_birth else None,
        'phone': user.phone,
        'technique': user.preferred_technique,
        'tshirtSize': user.tshirt_size,
        'experience': user.ski_experience,
        'emergencyName': user.emergency_contact_name,
        'emergencyRelation': user.emergency_contact_relation,
        'emergencyPhone': user.emergency_contact_phone,
        'emergencyEmail': user.emergency_contact_email,
    }


@verify_api.route('/api/verify/resolve')
def resolve():
    """What screen should this visitor see? One call, one verdict."""
    season = Season.query.get_or_404(request.args.get('season_id', type=int))
    identity = service.get_verified_identity()
    invite_payload = late_link.verify(request.args.get('invite'))
    outcome, context = resolve_registration_step(
        identity, season, datetime.utcnow(), invite_payload)
    user = None
    if identity and identity.get('user_id'):
        user = User.query.get(identity['user_id'])
    # Datetimes go out as ISO strings; the client only ever formats them.
    serialized = {
        k: (v.isoformat() if hasattr(v, 'isoformat') else v)
        for k, v in context.items()
    }
    return jsonify(outcome=outcome, context=serialized,
                   user=_prefill_payload(user))


@verify_api.route('/api/verify/email/lookup', methods=['POST'])
def email_lookup():
    """Does this email belong to an account? Detection only, no code sent.

    Rate-limited on the same counters as the send endpoints. Without that
    this is an unlimited "is X a member?" oracle.
    """
    email = normalize_email((request.get_json() or {}).get('email', ''))
    if not email:
        return jsonify(ok=False, error='Enter an email address.'), 400
    ip = _client_ip()
    if not service.rate_limit_ok(email, ip):
        return jsonify(ok=False, error=service.RATE_LIMIT_MSG)
    service._record_attempt(email, 'email', ip)
    return jsonify(ok=True, exists=User.get_by_email(email) is not None)
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
pytest tests/registration/test_verify_routes.py -v -k "resolve or lookup"
```

Expected: 4 passed.

- [ ] **Step 5: Run the whole registration suite for regressions**

```bash
pytest tests/registration/ -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add app/routes/verify.py tests/registration/test_verify_routes.py
git commit -m "Add /api/verify/resolve and /api/verify/email/lookup

Resolve folds in prefill so the client makes one call. Lookup carries
the same rate limit as the send endpoints so it is not an enumeration
oracle."
```

---

## Task 4: Client renders verdicts

**Files:**
- Modify: `app/templates/season_register.html:69-131` (the `#section-verify` block)
- Modify: `app/static/script.js:455-880` (the step 0 block)

**Interfaces:**
- Consumes: `GET /api/verify/resolve` from Task 3.
- Produces: a JS function `applyVerdict(body)` that switches on `body.outcome` and shows exactly one panel. Task 5 extends it with the in-wizard email panel; Task 10 adds the reminder button.

This is the task that deletes the skip link. After it, phone verification is the only front door.

- [ ] **Step 1: Add the outcome panels to the template**

In `app/templates/season_register.html`, delete this block entirely (it is the `verify-skip-link` paragraph inside `#verify-phone-entry`):

```html
            <p class="form-field__hint" style="margin-top: 16px;">
              <a href="#" id="verify-skip-link">New to TCSC? Start here.</a>
              (Skied with us before? Verify above. Registering as new puts you in the new-member lottery.)
            </p>
```

Then add these three panels immediately after the closing `</div>` of `#verify-email-entry`, still inside `#section-verify`:

```html
          <div id="verify-already-registered" hidden>
            <h3 class="form-section__title" id="already-registered-title"></h3>
            <p id="already-registered-detail"></p>
            <a class="btn btn--full" href="https://tcsc.ski">Back to tcsc.ski</a>
          </div>

          <div id="verify-window-wait" hidden>
            <h3 class="form-section__title" id="window-wait-title"></h3>
            <p>We'll pick up right where you left off.</p>
          </div>

          <div id="verify-window-ended" hidden>
            <h3 class="form-section__title" id="window-ended-title"></h3>
            <p>Text an organizer and we'll see what we can do.</p>
          </div>
```

- [ ] **Step 2: Replace the client's decision logic**

In `app/static/script.js`, inside the step 0 block, add these helpers next to `enterWizard`:

```javascript
    const VERIFY_PANELS = [
      'verify-phone-entry', 'verify-code-entry', 'verify-email-entry',
      'verify-already-registered', 'verify-window-wait', 'verify-window-ended'
    ];

    function showOnlyVerifyPanel(id) {
      VERIFY_PANELS.forEach(panel => { if (panel !== id) hide(panel); });
      if (id) show(id);
      verifySection.hidden = false;
      registrationForm.hidden = true;
      if (progressBar) progressBar.hidden = true;
    }

    function formatWindowDate(iso) {
      if (!iso) return null;
      return new Date(iso).toLocaleString('en-US', {
        weekday: 'short', month: 'short', day: 'numeric',
        hour: 'numeric', minute: '2-digit', timeZone: 'America/Chicago'
      });
    }

    // The server decided. This only renders.
    function applyVerdict(body) {
      const ctx = body.context || {};
      switch (body.outcome) {
        case 'verify_phone':
          showOnlyVerifyPanel('verify-phone-entry');
          return;

        case 'need_email':
          byId('verify-email-msg').textContent =
            "More than one member shares this number. Enter the email you use with the club.";
          showOnlyVerifyPanel('verify-email-entry');
          byId('verify-email').focus();
          return;

        case 'already_registered': {
          byId('already-registered-title').textContent =
            `You're already registered for ${ctx.season_name}.`;
          byId('already-registered-detail').textContent =
            ctx.status === 'ACTIVE'
              ? "Your card was charged. See you out there."
              : "Your card has a hold. We charge it only if you get a lottery spot.";
          showOnlyVerifyPanel('verify-already-registered');
          return;
        }

        case 'window_not_yet_open': {
          const who = ctx.member_type === 'returning' ? 'Returning member' : 'New member';
          const when = formatWindowDate(ctx.opens_at);
          byId('window-wait-title').textContent = when
            ? `${who} registration opens ${when}.`
            : `${who} registration isn't open yet.`;
          showOnlyVerifyPanel('verify-window-wait');
          return;
        }

        case 'window_ended': {
          const who = ctx.member_type === 'returning' ? 'Returning member' : 'New member';
          const when = formatWindowDate(ctx.closed_at);
          byId('window-ended-title').textContent = when
            ? `${who} registration closed ${when}.`
            : `${who} registration is closed.`;
          showOnlyVerifyPanel('verify-window-ended');
          return;
        }

        case 'wizard_returning':
        case 'wizard_new':
          if (body.user) applyPrefill({ memberType: ctx.member_type, user: body.user });
          else setPaymentStatusLine(ctx.member_type);
          enterWizard({ continueUnverified: false, firstName: ctx.first_name });
          return;

        default:
          showOnlyVerifyPanel('verify-phone-entry');
      }
    }

    async function resolveAndRender() {
      const invite = new URLSearchParams(window.location.search).get('invite');
      const seasonId = registrationForm.dataset.seasonId;
      let url = `/api/verify/resolve?season_id=${encodeURIComponent(seasonId)}`;
      if (invite) url += `&invite=${encodeURIComponent(invite)}`;
      const resp = await fetch(url);
      return resp.json();
    }
```

- [ ] **Step 3: Route every success path through the verdict**

Replace the body of `checkPhoneCode`'s success branch. Delete this:

```javascript
        phoneVerified = true;
        if (body.match === 'one') {
          await verifiedPrefillThenEnter(body.firstName);
          return;
        }
        // 'none' and 'multiple' both route to the email step; only the copy differs.
        if (body.match === 'multiple') {
          byId('verify-email-msg').textContent =
            "More than one member shares this number, so we'll match you by email " +
            "instead. Enter the email you've used with the club.";
        }
        hide('verify-code-entry');
        show('verify-email-entry');
        byId('verify-email').focus();
```

Replace with:

```javascript
        phoneVerified = true;
        applyVerdict(await resolveAndRender());
```

That single change is the consolidation: a phone matching nobody now falls through to `wizard_new` instead of being pushed at the alumni email step.

In `checkEmailCode`, replace `await verifiedPrefillThenEnter(null);` with:

```javascript
        applyVerdict(await resolveAndRender());
```

Delete the now-unused `verifiedPrefillThenEnter` function and the `fetchPrefill` function.

Replace the whole resume-after-refresh IIFE at the end of the step 0 block with:

```javascript
    // Resume after a refresh. The server re-decides; the client never
    // guesses. An expired identity lands back on step 0 with an
    // explanation, never a silent downgrade to the flagged path.
    (async () => {
      let entry = null;
      try {
        entry = storedWizardEntry();
        const body = await resolveAndRender();
        if (body.outcome !== 'verify_phone') {
          phoneVerified = true;
          applyVerdict(body);
          return;
        }
      } catch (e) {
        entry = storedWizardEntry();
      }
      if (entry === '1') {
        // They took an escape hatch earlier; keep them on that path.
        enterWizard({ continueUnverified: true });
        return;
      }
      if (entry === '0') show('verify-expired-notice');
    })();
```

- [ ] **Step 4: Delete the skip link's handler**

Remove this block from `script.js`:

```javascript
    byId('verify-skip-link').addEventListener('click', e => {
      e.preventDefault();
      setPaymentStatusLine('new');
      enterWizard({ continueUnverified: !phoneVerified });
    });
```

Update the comment above the remaining hatches to:

```javascript
    // Escape hatches. Verification is mandatory, but registration never
    // hard-blocks. Both links take the flagged path: new-member lottery,
    // manual capture, admin review.
```

- [ ] **Step 5: Verify by hand**

```bash
./scripts/dev.sh
```

Open `http://localhost:5001/seasons/<id>/register` and confirm:
- There is no "New to TCSC? Start here." link.
- A number with no account lands in the wizard, not the email step.
- A number on one account with a registration this season shows the already-registered panel.
- Refreshing mid-wizard keeps you in the wizard.

- [ ] **Step 6: Commit**

```bash
git add app/templates/season_register.html app/static/script.js
git commit -m "Client renders resolver verdicts, skip link deleted

Phone verification is now the only front door. A number matching
nobody falls through to the new-member wizard instead of the alumni
email step."
```

---

## Task 5: In-wizard email correlation

**Files:**
- Modify: `app/templates/season_register.html` (the `#email` field in `#section-about`)
- Modify: `app/static/script.js`

**Interfaces:**
- Consumes: `POST /api/verify/email/lookup` and `GET /api/verify/resolve` from Task 3, `applyVerdict` from Task 4.
- Produces: nothing later tasks import.

The rule, from the spec: a phone that resolved someone can freely change their email. A phone that matched nobody, typing an email that belongs to an account, is forced into the returning flow.

- [ ] **Step 1: Add the collision panel**

In `app/templates/season_register.html`, directly after the `#email` field's closing `</div>` inside `#section-about`:

```html
            <div id="email-collision" class="notice notice--info" hidden>
              <p style="margin: 0 0 12px;"><strong>We found your account.</strong>
                Verify this email and we'll pull your info in.</p>
              <button type="button" class="btn" id="email-collision-send">Email me a code</button>
              <div id="email-collision-code-row" hidden style="margin-top: 16px;">
                <div class="form-field">
                  <label class="form-field__label" for="email-collision-code">Verification Code</label>
                  <input class="form-input" type="text" id="email-collision-code"
                         inputmode="numeric" autocomplete="one-time-code" maxlength="8"
                         placeholder="6-digit code">
                </div>
                <button type="button" class="btn" id="email-collision-check">Verify</button>
              </div>
              <p class="form-field__hint" style="margin-top: 16px;">
                <a href="#" id="email-collision-dead">Can't reach that inbox?</a>
              </p>
            </div>
```

- [ ] **Step 2: Wire the blur check**

Add to `script.js` inside the step 0 block, after `applyVerdict`:

```javascript
    // Email correlation inside the wizard. Only fires when the phone
    // matched nobody: a resolved member owns their email outright and can
    // change it freely, which is the phone-is-primary rule.
    let phoneResolvedMember = false;

    async function checkEmailCollision() {
      if (phoneResolvedMember) return;
      const emailField = byId('email');
      const value = emailField.value.trim();
      if (!value || !value.includes('@')) return;
      let body;
      try {
        body = await postJson('/api/verify/email/lookup', { email: value });
      } catch (e) {
        return;  // Detection is a convenience. Never block typing on it.
      }
      if (!body.ok || !body.exists) {
        hide('email-collision');
        return;
      }
      hide('email-collision-code-row');
      show('email-collision');
    }

    byId('email').addEventListener('blur', checkEmailCollision);

    byId('email-collision-send').addEventListener('click', async () => {
      const btn = byId('email-collision-send');
      btn.disabled = true;
      try {
        const body = await postJson('/api/verify/email/start',
                                    { email: byId('email').value.trim() });
        if (!body.ok) {
          showVerifyError(body.error || "We couldn't send that code. Try again in a minute.");
          return;
        }
        show('email-collision-code-row');
        byId('email-collision-code').focus();
      } finally {
        btn.disabled = false;
      }
    });

    byId('email-collision-check').addEventListener('click', async () => {
      const btn = byId('email-collision-check');
      btn.disabled = true;
      try {
        const body = await postJson('/api/verify/email/check', {
          email: byId('email').value.trim(),
          code: byId('email-collision-code').value.replace(/\s+/g, '')
        });
        if (!body.ok) {
          showVerifyError(body.error || "That code didn't match. Check your email and try again.");
          return;
        }
        hide('email-collision');
        // Linking may flip them to returning, or reveal a registration
        // they already have, or a window that isn't open. Re-ask.
        applyVerdict(await resolveAndRender());
      } finally {
        btn.disabled = false;
      }
    });

    // Last resort, not an opt-out. Someone who cannot reach the inbox on
    // a matched account still gets to register; an organizer links the
    // history afterward.
    byId('email-collision-dead').addEventListener('click', e => {
      e.preventDefault();
      hide('email-collision');
      byId('continue-unverified').value = '1';
      show('unverified-notice');
      rememberWizardEntered(true);
      setPaymentStatusLine('new');
    });
```

- [ ] **Step 3: Set `phoneResolvedMember` from the verdict**

In `applyVerdict`, in the `wizard_returning` / `wizard_new` case, before `enterWizard`:

```javascript
          phoneResolvedMember = !!ctx.first_name;
```

A resolved member always has a first name in the context; an unmatched phone always has `null`.

- [ ] **Step 4: Verify by hand**

```bash
./scripts/dev.sh
```

With a number that matches no account:
- Type an email belonging to an existing member, tab out. The collision panel appears and no email is sent.
- Fix the typo to a free address. The panel goes away.
- Request and enter a code. The panel closes and the wizard reflects the linked account.

With a number that matches one account, typing any free email must show no panel at all.

- [ ] **Step 5: Commit**

```bash
git add app/templates/season_register.html app/static/script.js
git commit -m "Correlate email inside the wizard

A phone that matched nobody, typing a known email, is forced into the
returning flow. A resolved member owns their email and can change it."
```

---

## Task 6: POST path uses the resolver

**Files:**
- Modify: `app/routes/registration.py:70-200` (the POST branch of `season_register`)
- Modify: `app/utils.py:253-256`
- Test: `tests/registration/test_season_register_verified.py` (append)

**Interfaces:**
- Consumes: `resolve_registration_step` and outcome constants from Task 1, `UserSeason.review_note` from Task 2.
- Produces: nothing later tasks import.

- [ ] **Step 1: Write the failing tests**

Append to `tests/registration/test_season_register_verified.py`:

```python
def test_unverified_registration_records_why(client, app, season):
    with client.session_transaction() as sess:
        sess.pop('verified_identity', None)
    form = dict(FORM, continue_unverified='1')
    client.post(f'/seasons/{season}/register', data=form,
                follow_redirects=True)
    with app.app_context():
        u = User.query.filter_by(email=EMAIL).one_or_none()
        assert u is not None
        us = UserSeason.get_for_user_season(u.id, season)
        assert us.needs_review is True
        assert us.review_note == "no verified phone"


def test_disclaimed_identity_does_not_get_returning_pricing(client, app, season):
    """'Not Jane?' must not be priced as Jane.

    The session still carries Jane's user_id at this point, so the route
    has to scrub it before the resolver sees it.
    """
    with app.app_context():
        jane = User(email="jane-disclaim@test.com", first_name="Jane",
                    last_name="Owner", status=UserStatus.ACTIVE,
                    phone_e164=PHONE, date_of_birth=date(1990, 1, 1),
                    tshirt_size="M", emergency_contact_name="Em",
                    emergency_contact_relation="friend",
                    emergency_contact_phone="612-555-0999",
                    emergency_contact_email="em@test.com")
        db.session.add(jane)
        db.session.commit()
        past = Season(name="Disclaim Past", year=2087, price_cents=1000,
                      season_type='winter', start_date=date(2087, 11, 1),
                      end_date=date(2088, 3, 1))
        db.session.add(past)
        db.session.commit()
        db.session.add(UserSeason(user_id=jane.id, season_id=past.id,
                                  registration_type='new',
                                  registration_date=date(2087, 10, 1),
                                  status=UserSeasonStatus.ACTIVE))
        db.session.commit()
        jane_id, past_id = jane.id, past.id
    with client.session_transaction() as sess:
        sess['verified_identity'] = {
            'phone_e164': PHONE, 'user_id': jane_id,
            'ts': datetime.utcnow().isoformat()}
    # EMAIL differs from Jane's, plus continue_unverified: the disclaim flow.
    client.post(f'/seasons/{season}/register',
                data=dict(FORM, continue_unverified='1'),
                follow_redirects=True)
    try:
        with app.app_context():
            u = User.query.filter_by(email=EMAIL).one_or_none()
            us = UserSeason.get_for_user_season(u.id, season)
            assert us.registration_type == 'new'
            assert us.status == UserSeasonStatus.PENDING_LOTTERY
            assert us.needs_review is True
            assert "Jane Owner" in us.review_note
    finally:
        with app.app_context():
            UserSeason.query.filter_by(user_id=jane_id).delete()
            db.session.commit()
            db.session.delete(User.query.get(jane_id))
            db.session.delete(Season.query.get(past_id))
            db.session.commit()


def test_verified_new_member_is_not_flagged(client, app, season):
    with client.session_transaction() as sess:
        sess['verified_identity'] = {
            'phone_e164': PHONE, 'user_id': None,
            'ts': datetime.utcnow().isoformat()}
    client.post(f'/seasons/{season}/register', data=dict(FORM),
                follow_redirects=True)
    with app.app_context():
        u = User.query.filter_by(email=EMAIL).one_or_none()
        us = UserSeason.get_for_user_season(u.id, season)
        assert us.needs_review is False
        assert us.review_note is None
        assert us.registration_type == 'new'
        assert u.phone_verified_at is not None
```

- [ ] **Step 2: Run them to verify they fail**

```bash
pytest tests/registration/test_season_register_verified.py -v -k "records_why or not_flagged or disclaimed"
```

Expected: FAIL. `review_note` is never written, and the disclaim test fails on `registration_type == 'returning'` because the resolver still sees Jane's id.

- [ ] **Step 3: Derive member type from the resolver**

In `app/routes/registration.py`, add the import:

```python
from ..seasons.resolution import (resolve_registration_step, WIZARD_RETURNING,
                                  ALREADY_REGISTERED)
```

Replace this line:

```python
            is_returning = bool(verified_user is not None and user and user.is_returning)
```

with:

```python
            # One rule, one place. The POST must not be able to disagree
            # with the screen the member was just looking at.
            #
            # The session dict still carries the disclaimed user_id, so it
            # has to be scrubbed before the resolver sees it. Otherwise
            # someone who just said "I'm not Jane" would be priced as Jane.
            resolver_identity = identity
            if identity is not None and identity_disclaimed:
                resolver_identity = {**identity, 'user_id': None}
            outcome, _ = resolve_registration_step(
                resolver_identity, season, now_utc,
                invite_payload if invite_season_match else None)
            if outcome == ALREADY_REGISTERED:
                flash_error("You're already registered for this season.")
                return redirect(url_for('registration.season_register',
                                        season_id=season_id))
            is_returning = (outcome == WIZARD_RETURNING)
```

**Ordering matters.** The `identity_disclaimed` block in Step 4 must execute *before* this resolver call. It already sits earlier in the function; leave it there and do not move the resolver call above it.

- [ ] **Step 4: Record why a row was flagged**

Replace the `needs_review` computation block with:

```python
            # needs_review is about account-MATCH confidence, computed from
            # pre-creation state. review_note says which of the three ways
            # it went wrong so the admin page does not have to guess.
            review_note = None
            if identity is None:
                review_note = "no verified phone"
            elif identity_disclaimed:
                review_note = (f"claims not to be {verified_user.first_name} "
                               f"{verified_user.last_name} (id {verified_user.id})"
                               )[:255] if verified_user else "disclaimed a match"
            elif user is not None and verified_user is None:
                review_note = f"claimed existing account {user.email}, email unverified"[:255]
            needs_review = review_note is not None
```

Note: `identity_disclaimed` is computed before `verified_user` is set to `None`, so capture the name into a local before that reassignment. Change the disclaim block to:

```python
            identity_disclaimed = (
                continue_unverified
                and verified_user is not None
                and email != normalize_email(verified_user.email)
            )
            disclaimed_name = None
            disclaimed_id = None
            if identity_disclaimed:
                disclaimed_name = verified_user.full_name
                disclaimed_id = verified_user.id
                verified_user = None
```

and use those in the note:

```python
            elif identity_disclaimed:
                review_note = f"claims not to be {disclaimed_name} (id {disclaimed_id})"[:255]
```

- [ ] **Step 5: Write `review_note` onto the row**

In both the create and update branches of the `UserSeason` block, add `review_note=review_note` alongside `needs_review=needs_review` for the constructor, and `user_season.review_note = review_note` alongside the existing assignment for the update branch.

- [ ] **Step 6: Delete the status shim**

In `app/routes/registration.py`, replace:

```python
            validation_form = form.copy()
            validation_form['status'] = 'returning_former' if is_returning else 'new'
            is_valid, validation_errors = validate_registration_form(validation_form, user_fields.get('date_of_birth'))
```

with:

```python
            is_valid, validation_errors = validate_registration_form(
                form, user_fields.get('date_of_birth'))
```

In `app/utils.py`, delete these four lines from `validate_registration_form`:

```python
    # Member status
    valid, msg = validate_choice(form.get('status', ''), VALID_MEMBER_STATUSES, 'Member status')
    if not valid:
        errors.append(msg)
```

Then check whether `VALID_MEMBER_STATUSES` and `validate_choice` still have other callers:

```bash
grep -rn "VALID_MEMBER_STATUSES\|validate_choice" app/ tests/
```

Remove the now-unused import only if nothing else uses it.

- [ ] **Step 7: Run the tests**

```bash
pytest tests/registration/ -v
```

Expected: all pass, including the two new ones.

- [ ] **Step 8: Commit**

```bash
git add app/routes/registration.py app/utils.py tests/registration/test_season_register_verified.py
git commit -m "POST derives member type from the resolver

One rule, one place. The POST can no longer disagree with the screen
the member was looking at. Records why a row was flagged, and drops
the dead status shim."
```

---

## Task 7: Payment and capture

**Files:**
- Modify: `app/routes/payments.py:664-722`
- Test: `tests/registration/test_payment_intent_verified.py` (append)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `user_id` in Stripe PaymentIntent metadata, read by the webhook.

- [ ] **Step 1: Write the failing test**

`tests/registration/test_payment_intent_verified.py:100` currently has `test_verified_identity_with_different_email_demotes_to_manual_new`, which asserts exactly the behavior this task removes. **Rewrite that test in place** rather than adding alongside it. Replace the whole function with:

```python
@patch("app.routes.payments.stripe.PaymentIntent.create", return_value=_intent_mock())
def test_verified_identity_with_different_email_still_auto_captures(
        mock_create, client, fixtures):
    # Session identity points at returning member A, and the intent is for a
    # different typed email. Under the phone-is-primary rule that is a
    # profile edit, not grounds for a hold. This is the fix for the stuck
    # requires_capture rows from the PR #241 launch, where a verified
    # returning member who changed their email needed manual capture
    # within 7 days.
    _set_identity(client, user_id=fixtures["user_id"])
    resp = client.post("/create-season-payment-intent", json={
        "season_id": fixtures["season_id"],
        "email": "pi-someone-else@test.com", "name": "Pat Payer"})
    assert resp.status_code == 200
    kwargs = mock_create.call_args.kwargs
    assert kwargs["capture_method"] == "automatic"
    assert kwargs["metadata"]["member_type"] == "RETURNING"
    assert kwargs["metadata"]["verified"] == "true"
    assert kwargs["metadata"]["user_id"] == str(fixtures["user_id"])
```

Then append one more, covering the metadata addition on the unverified path:

```python
@patch("app.routes.payments.stripe.PaymentIntent.create", return_value=_intent_mock())
def test_unverified_intent_carries_no_user_id(mock_create, client, fixtures):
    resp = client.post("/create-season-payment-intent", json={
        "season_id": fixtures["season_id"], "email": EMAIL, "name": "Pat Payer"})
    assert resp.status_code == 200
    assert mock_create.call_args.kwargs["metadata"]["user_id"] == ""
```

Both reuse the module's existing `fixtures`, `_set_identity`, and `_intent_mock` helpers. `fixtures` already builds a returning user (ACTIVE in a past season) with `phone_e164=PHONE` and yields `{"season_id", "user_id"}`.

- [ ] **Step 2: Run it to verify it fails**

```bash
pytest tests/registration/test_payment_intent_verified.py -v -k "different_email or no_user_id"
```

Expected: FAIL. The route still demotes to `manual`/`NEW` and emits no `user_id` key.

- [ ] **Step 3: Drop the demotion**

In `app/routes/payments.py`, delete these lines and their comment block:

```python
        # A typed email that differs from the verified account's email means
        # the payer is not (or no longer claims to be) that account - e.g.
        # the "Not [name]?" disclaim flow. Demote to new/manual so money is
        # only auto-captured for a proven returning match. The legitimate
        # verified-member-changing-email case just gets a hold instead of an
        # instant charge; an admin captures it. Conservative and money-safe.
        if verified_user is not None and email != normalize_email(verified_user.email):
            verified_user = None
```

Replace with:

```python
        # No email check here on purpose. A verified phone that resolved to
        # one account IS that member, so changing their email is a profile
        # edit, not grounds to demote them to a hold. The "Not [name]?"
        # disclaim flow clears user_id from the session upstream, so it
        # never reaches this line with a stale match.
```

- [ ] **Step 4: Add `user_id` to the metadata**

In the same function's `stripe.PaymentIntent.create` call, add to `metadata`:

```python
                # The webhook matches on email today, so a member typing a
                # new address can get a duplicate stub User. This change
                # makes email edits more common, so carry the id.
                'user_id': str(verified_user.id) if verified_user else '',
```

- [ ] **Step 5: Run the tests**

```bash
pytest tests/registration/ -v
```

Expected: all pass. The rewritten demotion test is the deliberate expectation change; say so in the commit body.

- [ ] **Step 6: Commit**

```bash
git add app/routes/payments.py tests/registration/test_payment_intent_verified.py
git commit -m "Phone match earns automatic capture regardless of email

Fixes the stuck requires_capture rows: a verified returning member who
typed a new address was held instead of charged. Carries user_id in
intent metadata so the webhook stops making duplicate stubs."
```

---

## Task 8: Copy pass

**Files:**
- Modify: `app/templates/season_register.html`
- Modify: `app/static/script.js`

**Interfaces:** none. This task changes strings only.

Apply the Global Constraints copy rules to every member-facing string in the flow.

- [ ] **Step 1: Rewrite the strings**

In `app/templates/season_register.html`:

| Element | Was | Becomes |
|---|---|---|
| `#unverified-notice` | "You're continuing without a verified match, so you'll be registered as a new member and entered in the new-member lottery. An organizer will review your registration and link any membership history." | "You'll register as a new member and join the lottery. An organizer will check for past membership." |
| `#verify-email-msg` | "Your number's verified. We just don't have it on file yet (most alumni don't). Enter the email you've used with the club and we'll link you up." | "Enter the email you use with the club and we'll link your account." |
| `#verify-expired-notice` | "Your verification expired. Verify your number again and your answers will be right where you left them." | "Your verification expired. Verify again and your answers are still here." |
| Code-entry hint | "Registering on a computer? The code went to your phone. It may not light up if Do Not Disturb is on." | "On a computer? The code went to your phone." |
| `#verify-cant-text-link` | "Can't receive texts?" | unchanged, already 3 words |
| `#verify-email-dead-link` | "That email doesn't work for me anymore" | "Can't reach that inbox?" |
| Volunteer intro | "TCSC is 100% volunteer-run, and the season goes best when everyone pitches in. Pick at least one way you'd like to help. We'll follow up based on what you choose." | "TCSC is all volunteers. Pick at least one way you'd like to help." |

In `app/static/script.js`:

| String | Was | Becomes |
|---|---|---|
| Welcome banner | "Welcome back, {name}! We filled in what we have on file. Give it a once-over and finish up." | "Welcome back, {name}. We filled in what we have. Give it a once-over." |
| Returning payment line | "You're registering as a returning member. Your card will be charged ${amount} today." | "Your card will be charged ${amount} today." |
| New payment line | "You're registering as a new member. We'll place a hold on your card; you're only charged if you get a spot in the lottery." | "We'll hold ${amount} on your card. We charge it only if you get a lottery spot." |
| Unknown payment line | "We'll confirm your membership type at checkout." | unchanged |

The new-member payment line needs the amount, which `setPaymentStatusLine` already has in scope as `priceDollars`.

- [ ] **Step 2: Check the rules held**

```bash
grep -n '—' app/templates/season_register.html app/static/script.js
```

Expected: no output. Then read each changed string and confirm it is 2 sentences or fewer and under 25 words.

- [ ] **Step 3: Verify by hand**

```bash
./scripts/dev.sh
```

Walk every panel and confirm nothing overflows its container on a 375px viewport.

- [ ] **Step 4: Commit**

```bash
git add app/templates/season_register.html app/static/script.js
git commit -m "Copy pass on the registration flow

Friendly, clear, concise. Two sentences, 25 words, no em dashes.
The unverified notice went from 34 words to 17."
```

---

## Task 9: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md` (the "Phone Verification (season registration)" section)

**Interfaces:** none.

- [ ] **Step 1: Rewrite the section**

Replace the existing "Phone Verification (season registration)" section with:

```markdown
## Phone Verification (season registration)

Every registrant verifies by SMS. There is no new-member bypass; the phone
is the identity proof. Member identity is a verified phone
(`User.phone_e164`, E.164, indexed, deliberately NOT unique because
households share numbers). Codes: Twilio Verify for SMS, `VerificationCode`
+ Resend for the email fallback. The verified identity lives in the Flask
session (`app/verify/service.py`, 2-hour TTL).

**One resolver decides everything.** `app/seasons/resolution.py` returns one
of seven outcomes given the session identity, a season, the time, and an
optional late-link payload. The client renders that verdict and decides
nothing itself. Both `/api/verify/resolve` and the registration POST call
it, so the two can never disagree. Add branches there, never in
`script.js`.

A verified phone matching one account IS that member: no email code, and
they may change their email freely without losing automatic capture. Email
verification survives in two places only, a phone matching 2+ accounts and
a phone matching none whose typed email hits an existing account.

Unverified registrations degrade to manual capture plus
`UserSeason.needs_review`, with `review_note` saying why. The admin review
page (`/admin/registration-review?season_id=N`) must be checked before
running a lottery. SMS templates live in `config/sms.yaml`; `send_sms()`
never raises.
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "Document the resolver in CLAUDE.md"
```

---

## Phase 1 complete

Tasks 1 through 9 are one shippable change. Open the PR here. Render auto-deploys every commit on main, so this must go through a PR rather than a direct push.

---

## Task 10: Reminder table

**Files:**
- Modify: `app/models.py`
- Create: `migrations/versions/<rev>_add_registration_reminders.py`
- Test: `tests/registration/test_registration_reminders.py`

**Interfaces:**
- Produces: `RegistrationReminder` with columns `id`, `phone_e164`, `season_id`, `member_type`, `created_at`, `sent_at`, and classmethod `RegistrationReminder.due(now)`. Tasks 11 and 12 use both.

- [ ] **Step 1: Write the failing test**

Create `tests/registration/test_registration_reminders.py`:

```python
from datetime import datetime, timedelta, date

import pytest

from app import create_app
from app.models import db, Season, RegistrationReminder

PHONE = "+16125550401"


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"
    )
    return app


@pytest.fixture
def season(app):
    with app.app_context():
        now = datetime.utcnow()
        s = Season(name="Reminder Test", year=2096, price_cents=15000,
                   season_type='winter',
                   start_date=date(2096, 11, 1), end_date=date(2097, 3, 1),
                   new_start=now - timedelta(minutes=5),
                   new_end=now + timedelta(days=30))
        db.session.add(s)
        db.session.commit()
        yield s
        RegistrationReminder.query.filter_by(season_id=s.id).delete()
        db.session.delete(Season.query.get(s.id))
        db.session.commit()


def test_due_finds_unsent_rows_whose_window_opened(app, season):
    with app.app_context():
        db.session.add(RegistrationReminder(
            phone_e164=PHONE, season_id=season.id, member_type='new'))
        db.session.commit()
        due = RegistrationReminder.due(datetime.utcnow())
        assert [r.phone_e164 for r in due] == [PHONE]


def test_due_skips_already_sent(app, season):
    with app.app_context():
        db.session.add(RegistrationReminder(
            phone_e164=PHONE, season_id=season.id, member_type='new',
            sent_at=datetime.utcnow()))
        db.session.commit()
        assert RegistrationReminder.due(datetime.utcnow()) == []


def test_due_skips_windows_still_closed(app, season):
    with app.app_context():
        season_row = Season.query.get(season.id)
        season_row.new_start = datetime.utcnow() + timedelta(days=3)
        db.session.add(RegistrationReminder(
            phone_e164=PHONE, season_id=season.id, member_type='new'))
        db.session.commit()
        assert RegistrationReminder.due(datetime.utcnow()) == []


def test_one_row_per_phone_season_type(app, season):
    from sqlalchemy.exc import IntegrityError
    with app.app_context():
        db.session.add(RegistrationReminder(
            phone_e164=PHONE, season_id=season.id, member_type='new'))
        db.session.commit()
        db.session.add(RegistrationReminder(
            phone_e164=PHONE, season_id=season.id, member_type='new'))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
```

- [ ] **Step 2: Run to verify it fails**

```bash
pytest tests/registration/test_registration_reminders.py -v
```

Expected: `ImportError: cannot import name 'RegistrationReminder'`.

- [ ] **Step 3: Add the model**

In `app/models.py`, after `class UserSeason`:

```python
class RegistrationReminder(db.Model):
    """Someone who arrived before their window opened and asked for a text.

    Keyed by phone, not user_id, on purpose. The people signing up for
    these mostly do not have an account yet.
    """
    __tablename__ = 'registration_reminders'

    id = db.Column(db.Integer, primary_key=True)
    phone_e164 = db.Column(db.String(20), nullable=False, index=True)
    season_id = db.Column(db.Integer, db.ForeignKey('seasons.id'), nullable=False)
    member_type = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    sent_at = db.Column(db.DateTime)

    __table_args__ = (
        db.UniqueConstraint('phone_e164', 'season_id', 'member_type',
                            name='uq_reminder_phone_season_type'),
    )

    @classmethod
    def due(cls, now):
        """Unsent reminders whose window is now open. Oldest first."""
        rows = (cls.query.filter(cls.sent_at.is_(None))
                .order_by(cls.created_at).all())
        return [r for r in rows
                if (season := Season.query.get(r.season_id)) is not None
                and season.is_open_for(r.member_type, now)]
```

- [ ] **Step 4: Generate, inspect, apply the migration**

```bash
flask db migrate -m "add registration_reminders"
```

Confirm the generated file creates the table with the unique constraint and the `phone_e164` index, and nothing else. Then:

```bash
flask db upgrade
pytest tests/registration/test_registration_reminders.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add app/models.py migrations/versions/ tests/registration/test_registration_reminders.py
git commit -m "Add RegistrationReminder

Keyed by phone, not user_id. The people signing up mostly do not have
an account yet."
```

---

## Task 11: The reminder button

**Files:**
- Modify: `app/routes/verify.py`
- Modify: `app/templates/season_register.html` (`#verify-window-wait`)
- Modify: `app/static/script.js` (`applyVerdict`, `window_not_yet_open` case)
- Test: `tests/registration/test_registration_reminders.py` (append)

**Interfaces:**
- Consumes: `RegistrationReminder` from Task 10, the `window_not_yet_open` outcome from Task 1.
- Produces: `POST /api/verify/remind-me` taking `{season_id, member_type}` and returning `{ok}`.

- [ ] **Step 1: Write the failing test**

```python
def test_remind_me_requires_a_verified_phone(app, season):
    client = app.test_client()
    resp = client.post('/api/verify/remind-me',
                       json={'season_id': season.id, 'member_type': 'new'})
    assert resp.get_json()['ok'] is False


def test_remind_me_is_idempotent(app, season):
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['verified_identity'] = {
            'phone_e164': PHONE, 'user_id': None,
            'ts': datetime.utcnow().isoformat()}
    payload = {'season_id': season.id, 'member_type': 'new'}
    assert client.post('/api/verify/remind-me', json=payload).get_json()['ok']
    assert client.post('/api/verify/remind-me', json=payload).get_json()['ok']
    with app.app_context():
        assert RegistrationReminder.query.filter_by(
            phone_e164=PHONE, season_id=season.id).count() == 1
```

- [ ] **Step 2: Run to verify it fails**

```bash
pytest tests/registration/test_registration_reminders.py -v -k remind_me
```

Expected: 404 from a missing route.

- [ ] **Step 3: Add the endpoint**

In `app/routes/verify.py`:

```python
@verify_api.route('/api/verify/remind-me', methods=['POST'])
def remind_me():
    """Text me when my window opens. One tap, because the phone is verified."""
    identity = service.get_verified_identity()
    if not identity:
        return jsonify(ok=False, error='Verify your number first.'), 400
    data = request.get_json() or {}
    season_id = data.get('season_id')
    member_type = data.get('member_type')
    if member_type not in ('new', 'returning') or not season_id:
        return jsonify(ok=False, error='Missing season or member type.'), 400
    existing = RegistrationReminder.query.filter_by(
        phone_e164=identity['phone_e164'], season_id=int(season_id),
        member_type=member_type).one_or_none()
    if existing is None:
        db.session.add(RegistrationReminder(
            phone_e164=identity['phone_e164'], season_id=int(season_id),
            member_type=member_type))
        db.session.commit()
    return jsonify(ok=True)
```

Add `RegistrationReminder` to the `app.models` import at the top of the file.

- [ ] **Step 4: Add the button**

In `app/templates/season_register.html`, inside `#verify-window-wait`, replace the `<p>` with:

```html
            <button type="button" class="btn btn--full" id="window-wait-remind">Text me when it opens</button>
            <p id="window-wait-confirm" hidden>We'll text you when it opens.</p>
```

In `script.js`, in the `window_not_yet_open` case of `applyVerdict`, after setting the title:

```javascript
          hide('window-wait-confirm');
          show('window-wait-remind');
          byId('window-wait-remind').onclick = async () => {
            const btn = byId('window-wait-remind');
            btn.disabled = true;
            const body = await postJson('/api/verify/remind-me', {
              season_id: registrationForm.dataset.seasonId,
              member_type: ctx.member_type
            });
            if (body.ok) {
              hide('window-wait-remind');
              show('window-wait-confirm');
            } else {
              btn.disabled = false;
              showVerifyError(body.error || "We couldn't set that reminder. Try again in a minute.");
            }
          };
```

- [ ] **Step 5: Run the tests and commit**

```bash
pytest tests/registration/ -v
git add app/routes/verify.py app/templates/season_register.html app/static/script.js tests/registration/test_registration_reminders.py
git commit -m "Add the remind-me tap on window_not_yet_open"
```

---

## Task 12: The reminder sweep

**Files:**
- Modify: `config/sms.yaml`
- Modify: `app/scheduler.py`
- Modify: `app/routes/admin.py:662-684` (`seasons_data`) and `app/static/admin_seasons.js`
- Test: `tests/registration/test_registration_reminders.py` (append)

**Interfaces:**
- Consumes: `RegistrationReminder.due()` from Task 10.
- Produces: `send_due_registration_reminders()` in `app/scheduler.py`.

- [ ] **Step 1: Add the SMS template**

In `config/sms.yaml`, under `templates:`:

```yaml
  registration_open: "TCSC: {member_type} registration for the {season_name} season is open now. Sign up: {url} Reply STOP to opt out"
```

- [ ] **Step 2: Write the failing test**

```python
def test_sweep_sends_once_and_stamps(app, season, monkeypatch):
    from app import scheduler
    sent = []
    monkeypatch.setattr(scheduler, 'send_sms_to_phone',
                        lambda phone, template, **kw: sent.append((phone, template)))
    with app.app_context():
        db.session.add(RegistrationReminder(
            phone_e164=PHONE, season_id=season.id, member_type='new'))
        db.session.commit()
        scheduler.send_due_registration_reminders(app)
        assert sent == [(PHONE, 'registration_open')]
        row = RegistrationReminder.query.filter_by(phone_e164=PHONE).one()
        assert row.sent_at is not None
        sent.clear()
        scheduler.send_due_registration_reminders(app)
        assert sent == []
```

`send_sms()` takes a `User` and these rows have none, so `app/notifications/sms.py` needs a phone-only sender. Add it there, below `send_sms`:

```python
def send_sms_to_phone(phone_e164, template_key, **kwargs):
    """Text a raw number with no User row behind it.

    Same never-raises contract as send_sms(). Used by registration
    reminders, where the recipient has not registered yet by definition,
    so there is no user and no sms_opt_out flag to consult. A recipient
    who has replied STOP is refused by Twilio (code 21610) and logged.

    Returns True on send, False on skip or failure.
    """
    try:
        if not phone_e164:
            return False
        body = _templates()[template_key].format(**kwargs)
        twilio_send_sms(phone_e164, body)
        current_app.logger.info("sms: sent %s to %s", template_key, phone_e164)
        return True
    except Exception as exc:
        current_app.logger.warning(
            "sms: %s to %s failed: %s", template_key, phone_e164, exc)
        return False
```

Import it into `app/scheduler.py` alongside the existing `send_sms` import.

- [ ] **Step 3: Write the sweep**

In `app/scheduler.py`:

```python
def send_due_registration_reminders(app):
    """Text everyone whose window just opened. Idempotent by sent_at."""
    with app.app_context():
        now = datetime.utcnow()
        for reminder in RegistrationReminder.due(now):
            season = Season.query.get(reminder.season_id)
            send_sms_to_phone(
                reminder.phone_e164, 'registration_open',
                member_type=('Returning member'
                             if reminder.member_type == 'returning'
                             else 'New member'),
                season_name=season.name,
                url=url_for('registration.season_register',
                            season_id=season.id, _external=True))
            reminder.sent_at = datetime.utcnow()
            db.session.commit()
```

Register it alongside the other jobs, matching their `CronTrigger` style:

```python
    scheduler.add_job(
        func=send_due_registration_reminders,
        args=[app],
        trigger=CronTrigger(minute='*/5', timezone=CENTRAL_TZ),
        id='registration_reminders',
        replace_existing=True,
    )
```

Use whatever timezone constant the neighboring jobs use.

- [ ] **Step 4: Add the admin count**

`/admin/seasons` is JS-driven off `seasons_data`, so the count rides along in that JSON. In `app/routes/admin.py:662-684`, add one key to each season dict in `seasons_data`:

```python
            'reminders_waiting': RegistrationReminder.query.filter_by(
                season_id=s.id, sent_at=None).count(),
```

Add `RegistrationReminder` to the `app.models` import at the top of `app/routes/admin.py`.

Then render it in `app/static/admin_seasons.js` wherever the season card shows its registration windows, hidden when the count is zero:

```javascript
      season.reminders_waiting
        ? '<span class="badge">' + season.reminders_waiting + ' waiting for the window to open</span>'
        : ''
```

The label says what the number means, so nobody has to guess at noon on opening day.

- [ ] **Step 5: Run the tests and commit**

```bash
pytest tests/registration/ -v
git add config/sms.yaml app/scheduler.py app/notifications/sms.py app/routes/admin.py app/static/admin_seasons.js tests/registration/test_registration_reminders.py
git commit -m "Send registration reminders when a window opens

Cron sweep every 5 minutes, idempotent by sent_at. Matches every other
job in the scheduler and survives a restart."
```

---

## Final verification

- [ ] Full suite: `pytest tests/ -v`
- [ ] `grep -rn '—' app/templates/season_register.html app/static/script.js` returns nothing
- [ ] `grep -n 'verify-skip-link' app/` returns nothing
- [ ] Manual walk on `./scripts/dev.sh`, all seven outcomes
- [ ] `flask db heads` shows a single head
- [ ] PR opened. Never push straight to main; Render deploys every commit there.
