# SMS-First Season Registration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Phone-first season registration: verify the member's cell with a Twilio Verify code, match to their record by normalized phone (email-code fallback via Resend), prefill the wizard, derive returning/new server-side, and send confirmation/invite texts.

**Architecture:** A new `app/verify/` module owns codes, rate limits, and the session identity. New JSON endpoints under `/api/verify/*` drive a new "step 0" in the existing 4-step wizard. The registration POST and season payment-intent endpoint switch from the client-claimed status radio to the verified session. SMS sending is one thin function reading templates from `config/sms.yaml`.

**Tech Stack:** Flask, SQLAlchemy, Alembic (flask db), pytest with PostgreSQL fixtures, `requests` (already a dependency) for the Twilio Verify / Twilio Messaging / Resend REST APIs. No new packages.

**Spec:** `docs/superpowers/specs/2026-08-23-sms-registration-design.md`

## Global Constraints

- Prices in cents; timestamps UTC in DB (use `datetime.utcnow` like neighboring code, or helpers in `app/utils.py`).
- `UserStatus` / `UserSeasonStatus` are plain string classes, NOT Enums — never call `.value`.
- Capture method is the business rule: season new member = `manual`, season returning = `automatic`. Unverified registrations are ALWAYS `manual`.
- Phone canonical form is E.164 `+1XXXXXXXXXX`, US-only. `phone_e164` is indexed, NOT unique.
- SMS bodies are plain GSM-7, no emoji, one segment, and end with "Reply STOP to opt out".
- Verification failure must degrade, never hard-block a registration.
- No em dashes in any user-facing copy.
- Env vars (already in dev `.env`): `TWILIO_ACCOUNT_SID`, `TWILIO_API_KEY_SID`, `TWILIO_API_KEY_SECRET`, `TWILIO_VERIFY_SERVICE_SID=VAc3db44e72c904154c4892c8c89afc911`, `TWILIO_MESSAGING_SERVICE_SID=MG1d94fd27cac61678a41e94914c56cccb`, `RESEND_API_KEY`.
- Tests run against the local PostgreSQL (`postgresql://tcsc:tcsc@localhost:5432/tcsc_trips`); per-area conftest pattern is in `tests/trips/conftest.py`. All Twilio/Resend HTTP is mocked in tests — the outbound guard will fail the suite otherwise.
- Work on branch `sms-registration` (create from main). Commit after every task.

---

### Task 1: Phone normalization helper

**Files:**
- Modify: `app/utils.py` (add function near `validate_phone`, ~line 133)
- Test: `tests/registration/test_phone_normalization.py` (new)

**Interfaces:**
- Produces: `normalize_phone_e164(raw: str | None) -> str | None` in `app/utils.py`. Later tasks import it from `app.utils`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/registration/test_phone_normalization.py
import pytest

from app.utils import normalize_phone_e164


@pytest.mark.parametrize("raw,expected", [
    ("612-867-7165", "+16128677165"),          # prod's dashed format
    ("6128677165", "+16128677165"),            # bare 10 digits
    ("16129985285", "+16129985285"),           # 11 digits leading 1
    ("+17634397034", "+17634397034"),          # already E.164
    ("(612) 867-7165", "+16128677165"),        # parens and spaces
    ("612.867.7165", "+16128677165"),          # dots
    (" 612 867 7165 ", "+16128677165"),        # whitespace
])
def test_normalizes_us_formats(raw, expected):
    assert normalize_phone_e164(raw) == expected


@pytest.mark.parametrize("raw", [
    None, "", "   ", "555-0100",               # 7-digit local number: rejected
    "911", "1", "123456789",                   # too short
    "612867716512", "26128677165",             # 12 digits / 11 not starting with 1
    "+447911123456",                           # non-US
    "not a phone",
])
def test_rejects_non_nanp(raw):
    assert normalize_phone_e164(raw) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source env/bin/activate && pytest tests/registration/test_phone_normalization.py -v`
Expected: FAIL with `ImportError: cannot import name 'normalize_phone_e164'`

- [ ] **Step 3: Implement**

Add to `app/utils.py` directly below `validate_phone`:

```python
def normalize_phone_e164(raw):
    """Normalize a US phone number to E.164 (+1XXXXXXXXXX).

    Accepts 10 digits or 11 digits with a leading 1, in any common
    formatting. Returns None for anything else (including non-US numbers) —
    callers treat None as "no usable phone", never as an error.
    """
    if not raw:
        return None
    digits = re.sub(r'\D', '', raw)
    if len(digits) == 11 and digits.startswith('1'):
        digits = digits[1:]
    if len(digits) != 10:
        return None
    return '+1' + digits
```

(`re` is already imported in `app/utils.py`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/registration/test_phone_normalization.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add app/utils.py tests/registration/test_phone_normalization.py
git commit -m "feat(verify): add normalize_phone_e164 helper"
```

---

### Task 2: Schema — new columns, verification tables, backfill migration

**Files:**
- Modify: `app/models.py` (User ~line 102, UserSeason ~line 301; new models at end of file)
- Create: migration via `flask db migrate`
- Test: `tests/registration/test_models_verify.py` (new)

**Interfaces:**
- Produces:
  - `User.phone_e164` (String(16), nullable, indexed), `User.phone_verified_at` (DateTime), `User.email_verified_at` (DateTime), `User.sms_opt_out` (Boolean, nullable=False, default False)
  - `User.get_by_phone(cls, phone_e164) -> list[User]` (list, because non-unique)
  - `UserSeason.needs_review` (Boolean, nullable=False, default False)
  - `VerificationCode` model: `id, email (String(255), indexed), code_hash (String(64)), created_at, expires_at, attempts (Integer, default 0), consumed_at (DateTime, nullable)`
  - `VerificationAttempt` model: `id, target (String(64), indexed), channel (String(10)), ip (String(45), indexed), created_at (DateTime, indexed)`

- [ ] **Step 1: Write the failing tests**

```python
# tests/registration/test_models_verify.py
from datetime import datetime

import pytest

from app import create_app
from app.models import db, User, VerificationCode, VerificationAttempt


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"
    )
    return app


@pytest.fixture
def db_session(app):
    with app.app_context():
        yield db
        db.session.rollback()
        for email in ("verify-a@test.com", "verify-b@test.com"):
            u = User.query.filter_by(email=email).one_or_none()
            if u:
                db.session.delete(u)
        VerificationCode.query.filter(
            VerificationCode.email.like("verify-%@test.com")).delete(
            synchronize_session=False)
        VerificationAttempt.query.filter(
            VerificationAttempt.target.like("+1612555%")).delete(
            synchronize_session=False)
        db.session.commit()


def test_two_users_can_share_phone_e164(db_session):
    a = User(email="verify-a@test.com", first_name="A", last_name="One",
             phone_e164="+16125550101")
    b = User(email="verify-b@test.com", first_name="B", last_name="Two",
             phone_e164="+16125550101")
    db.session.add_all([a, b])
    db.session.commit()  # must NOT raise — phone_e164 is not unique
    assert [u.email for u in User.get_by_phone("+16125550101")] == [
        "verify-a@test.com", "verify-b@test.com"]


def test_verification_code_row_roundtrip(db_session):
    code = VerificationCode(
        email="verify-a@test.com", code_hash="a" * 64,
        expires_at=datetime.utcnow())
    db.session.add(code)
    db.session.commit()
    assert code.attempts == 0 and code.consumed_at is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/registration/test_models_verify.py -v`
Expected: FAIL with `ImportError` (VerificationCode) / AttributeError

- [ ] **Step 3: Add model changes**

In `app/models.py`, inside `class User` after `phone = db.Column(db.String(20))`:

```python
    phone_e164 = db.Column(db.String(16), index=True)  # +1XXXXXXXXXX; NOT unique (households share numbers)
    phone_verified_at = db.Column(db.DateTime)
    email_verified_at = db.Column(db.DateTime)
    sms_opt_out = db.Column(db.Boolean, nullable=False, default=False, server_default='false')
```

After `get_by_email` classmethod:

```python
    @classmethod
    def get_by_phone(cls, phone_e164):
        """All users sharing this normalized phone, oldest first.

        Returns a list — phone_e164 is deliberately non-unique.
        """
        return cls.query.filter_by(phone_e164=phone_e164).order_by(cls.id).all()
```

In `class UserSeason` after `status`:

```python
    needs_review = db.Column(db.Boolean, nullable=False, default=False, server_default='false')
```

At the end of `app/models.py`:

```python
class VerificationCode(db.Model):
    """Emailed 6-digit codes. Phone codes live in Twilio Verify, not here."""
    __tablename__ = 'verification_codes'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    code_hash = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    consumed_at = db.Column(db.DateTime)


class VerificationAttempt(db.Model):
    """Send-attempt log used only for rate limiting."""
    __tablename__ = 'verification_attempts'

    id = db.Column(db.Integer, primary_key=True)
    target = db.Column(db.String(64), nullable=False, index=True)  # phone_e164 or email
    channel = db.Column(db.String(10), nullable=False)  # 'sms' | 'email'
    ip = db.Column(db.String(45), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
```

- [ ] **Step 4: Generate the migration and add the backfill**

Run: `source env/bin/activate && flask db migrate -m "phone_e164, verification tables, needs_review"`

Then EDIT the generated migration's `upgrade()` to append a backfill after the schema ops (the digit-extraction mirrors `normalize_phone_e164`; SQL because the migration must not import app code):

```python
    # Backfill phone_e164 from the legacy phone column (US numbers only).
    op.execute("""
        UPDATE users SET phone_e164 = sub.e164 FROM (
            SELECT id, '+1' || right(digits, 10) AS e164 FROM (
                SELECT id, regexp_replace(phone, '[^0-9]', '', 'g') AS digits
                FROM users WHERE phone IS NOT NULL AND phone <> ''
            ) d
            WHERE length(digits) = 10
               OR (length(digits) = 11 AND left(digits, 1) = '1')
        ) sub
        WHERE users.id = sub.id
    """)
```

- [ ] **Step 5: Run the migration and the tests**

Run: `flask db upgrade && pytest tests/registration/test_models_verify.py tests/registration/test_phone_normalization.py -v`
Expected: migration applies cleanly; tests PASS

- [ ] **Step 6: Verify the backfill on dev data**

Run: `docker exec tcsc-postgres psql -U tcsc -d tcsc_trips -c "select count(*) filter (where phone_e164 is not null) as filled, count(*) filter (where phone is not null and phone <> '') as had_phone from users;"`
Expected: `filled` == `had_phone` (dev data is uniformly XXX-XXX-XXXX)

- [ ] **Step 7: Commit**

```bash
git add app/models.py migrations/versions/ tests/registration/test_models_verify.py
git commit -m "feat(verify): phone_e164 + verified timestamps + verification tables, with backfill"
```

---

### Task 3: Provider clients (Twilio Verify, Twilio SMS, Resend)

**Files:**
- Create: `app/verify/__init__.py` (empty), `app/verify/providers.py`
- Modify: `app/config.py` (add env reads in `configure_app` next to the Stripe block, ~line 8)
- Test: `tests/registration/test_providers.py` (new)

**Interfaces:**
- Produces (in `app.verify.providers`):
  - `class ProviderError(Exception)` with attribute `code` (provider error code, int or None)
  - `twilio_verify_start(phone_e164: str) -> None` (raises ProviderError on failure)
  - `twilio_verify_check(phone_e164: str, code: str) -> bool` (True iff approved; ProviderError on transport failure)
  - `twilio_send_sms(phone_e164: str, body: str) -> None` (raises ProviderError; `err.code == 21610` means recipient opted out)
  - `resend_send_code(email: str, first_name: str | None, code: str) -> None` (raises ProviderError)
- Consumes: env vars from Global Constraints via `os.getenv`.

- [ ] **Step 1: Write the failing tests** (mock `requests` — never hit the network)

```python
# tests/registration/test_providers.py
from unittest.mock import patch, MagicMock

import pytest

from app.verify import providers
from app.verify.providers import ProviderError


def _resp(status=200, body=None):
    m = MagicMock()
    m.status_code = status
    m.json.return_value = body or {}
    return m


@patch("app.verify.providers.requests.post")
def test_verify_start_posts_to_verify_api(mock_post):
    mock_post.return_value = _resp(201, {"status": "pending"})
    providers.twilio_verify_start("+16128677165")
    url = mock_post.call_args.args[0]
    assert "verify.twilio.com" in url and "/Verifications" in url
    assert mock_post.call_args.kwargs["data"] == {
        "To": "+16128677165", "Channel": "sms"}


@patch("app.verify.providers.requests.post")
def test_verify_check_true_only_on_approved(mock_post):
    mock_post.return_value = _resp(200, {"status": "approved"})
    assert providers.twilio_verify_check("+16128677165", "123456") is True
    mock_post.return_value = _resp(200, {"status": "pending"})
    assert providers.twilio_verify_check("+16128677165", "000000") is False


@patch("app.verify.providers.requests.post")
def test_verify_start_raises_provider_error_with_code(mock_post):
    mock_post.return_value = _resp(429, {"code": 60203, "message": "Max send attempts reached"})
    with pytest.raises(ProviderError) as exc:
        providers.twilio_verify_start("+16128677165")
    assert exc.value.code == 60203


@patch("app.verify.providers.requests.post")
def test_send_sms_surfaces_opt_out_code(mock_post):
    mock_post.return_value = _resp(400, {"code": 21610, "message": "unsubscribed"})
    with pytest.raises(ProviderError) as exc:
        providers.twilio_send_sms("+16128677165", "hi")
    assert exc.value.code == 21610


@patch("app.verify.providers.requests.post")
def test_resend_send_code_uses_club_sender(mock_post):
    mock_post.return_value = _resp(200, {"id": "abc"})
    providers.resend_send_code("rob@example.com", "Rob", "482913")
    payload = mock_post.call_args.kwargs["json"]
    assert payload["from"] == "Twin Cities Ski Club <club@tcsc.ski>"
    assert payload["subject"] == "Your TCSC code: 482913"
    assert "482913" in payload["text"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/registration/test_providers.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Implement**

`app/config.py` — inside `configure_app`, after the Stripe block (no hard failure when unset; the app must boot without SMS in degraded mode):

```python
    app.config['TWILIO_ACCOUNT_SID'] = os.getenv('TWILIO_ACCOUNT_SID')
    app.config['TWILIO_API_KEY_SID'] = os.getenv('TWILIO_API_KEY_SID')
    app.config['TWILIO_API_KEY_SECRET'] = os.getenv('TWILIO_API_KEY_SECRET')
    app.config['TWILIO_VERIFY_SERVICE_SID'] = os.getenv('TWILIO_VERIFY_SERVICE_SID')
    app.config['TWILIO_MESSAGING_SERVICE_SID'] = os.getenv('TWILIO_MESSAGING_SERVICE_SID')
    app.config['RESEND_API_KEY'] = os.getenv('RESEND_API_KEY')
```

`app/verify/providers.py`:

```python
"""Thin HTTP clients for Twilio Verify, Twilio Messaging, and Resend.

Every function either succeeds or raises ProviderError. Callers own the
policy (rate limits, degradation copy); this module owns transport only.
"""
import requests
from flask import current_app

TIMEOUT = 10


class ProviderError(Exception):
    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


def _twilio_auth():
    return (current_app.config['TWILIO_API_KEY_SID'],
            current_app.config['TWILIO_API_KEY_SECRET'])


def _raise_for_twilio(resp):
    if resp.status_code >= 400:
        try:
            body = resp.json()
        except ValueError:
            body = {}
        raise ProviderError(body.get('message', f'HTTP {resp.status_code}'),
                            code=body.get('code'))


def twilio_verify_start(phone_e164):
    sid = current_app.config['TWILIO_VERIFY_SERVICE_SID']
    if not sid:
        raise ProviderError('Twilio Verify is not configured')
    resp = requests.post(
        f'https://verify.twilio.com/v2/Services/{sid}/Verifications',
        auth=_twilio_auth(), data={'To': phone_e164, 'Channel': 'sms'},
        timeout=TIMEOUT)
    _raise_for_twilio(resp)


def twilio_verify_check(phone_e164, code):
    sid = current_app.config['TWILIO_VERIFY_SERVICE_SID']
    if not sid:
        raise ProviderError('Twilio Verify is not configured')
    resp = requests.post(
        f'https://verify.twilio.com/v2/Services/{sid}/VerificationCheck',
        auth=_twilio_auth(), data={'To': phone_e164, 'Code': code},
        timeout=TIMEOUT)
    # A check against an expired/unknown verification returns 404 — treat as
    # a plain wrong-code failure, not an outage.
    if resp.status_code == 404:
        return False
    _raise_for_twilio(resp)
    return resp.json().get('status') == 'approved'


def twilio_send_sms(phone_e164, body):
    account = current_app.config['TWILIO_ACCOUNT_SID']
    service = current_app.config['TWILIO_MESSAGING_SERVICE_SID']
    if not (account and service):
        raise ProviderError('Twilio Messaging is not configured')
    resp = requests.post(
        f'https://api.twilio.com/2010-04-01/Accounts/{account}/Messages.json',
        auth=_twilio_auth(),
        data={'To': phone_e164, 'MessagingServiceSid': service, 'Body': body},
        timeout=TIMEOUT)
    _raise_for_twilio(resp)


def resend_send_code(email, first_name, code):
    api_key = current_app.config['RESEND_API_KEY']
    if not api_key:
        raise ProviderError('Resend is not configured')
    greeting = f'Hi {first_name}!' if first_name else 'Hi!'
    resp = requests.post(
        'https://api.resend.com/emails',
        headers={'Authorization': f'Bearer {api_key}'},
        json={
            'from': 'Twin Cities Ski Club <club@tcsc.ski>',
            'to': [email],
            'subject': f'Your TCSC code: {code}',
            'text': (f"{greeting} Here is your Twin Cities Ski Club "
                     f"verification code: {code}. It expires in 10 minutes. "
                     "Didn't request this? Just ignore it."),
        },
        timeout=TIMEOUT)
    if resp.status_code >= 400:
        raise ProviderError(f'Resend HTTP {resp.status_code}')
```

Tests need an app context for `current_app` — add to the test file:

```python
@pytest.fixture(autouse=True)
def app_ctx():
    from app import create_app
    app = create_app()
    app.config.update(
        TESTING=True,
        TWILIO_ACCOUNT_SID="AC_test", TWILIO_API_KEY_SID="SK_test",
        TWILIO_API_KEY_SECRET="secret", TWILIO_VERIFY_SERVICE_SID="VA_test",
        TWILIO_MESSAGING_SERVICE_SID="MG_test", RESEND_API_KEY="re_test",
    )
    with app.app_context():
        yield
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/registration/test_providers.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add app/verify/ app/config.py tests/registration/test_providers.py
git commit -m "feat(verify): Twilio Verify / Messaging / Resend provider clients"
```

---

### Task 4: Verification service — email codes, rate limits, session identity

**Files:**
- Create: `app/verify/service.py`
- Test: `tests/registration/test_verify_service.py` (new)

**Interfaces:**
- Consumes: `app.verify.providers` functions (Task 3), `VerificationCode`/`VerificationAttempt` models (Task 2).
- Produces (in `app.verify.service`):
  - `rate_limit_ok(target: str, ip: str) -> bool` — False when >= 3 sends per target per 10 min OR >= 10 per ip per hour
  - `start_phone_verification(phone_e164, ip) -> tuple[bool, str]` — (ok, user-facing error copy)
  - `check_phone_verification(phone_e164, code) -> bool`
  - `start_email_verification(email, first_name, ip) -> tuple[bool, str]`
  - `check_email_verification(email, code) -> bool`
  - `set_verified_identity(phone_e164, user_id=None)` / `get_verified_identity() -> dict | None` — Flask session, keys `phone_e164`, `user_id`, `ts`; TTL 2 hours enforced on read
  - Module constant `IDENTITY_TTL_SECONDS = 7200`

- [ ] **Step 1: Write the failing tests**

```python
# tests/registration/test_verify_service.py
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from app import create_app
from app.models import db, VerificationCode, VerificationAttempt
from app.verify import service
from app.verify.providers import ProviderError

EMAIL = "verify-svc@test.com"
PHONE = "+16125550142"


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
        db.session.rollback()
        VerificationCode.query.filter_by(email=EMAIL).delete()
        VerificationAttempt.query.filter(
            VerificationAttempt.target.in_([EMAIL, PHONE])).delete(
            synchronize_session=False)
        db.session.commit()


@patch("app.verify.service.providers.resend_send_code")
def test_email_code_roundtrip(mock_send, ctx):
    ok, _ = service.start_email_verification(EMAIL, "Rob", ip="1.2.3.4")
    assert ok
    code = mock_send.call_args.args[2]  # the generated 6-digit code
    assert len(code) == 6 and code.isdigit()
    assert service.check_email_verification(EMAIL, code) is True
    # consumed: same code fails a second time
    assert service.check_email_verification(EMAIL, code) is False


@patch("app.verify.service.providers.resend_send_code")
def test_email_code_wrong_attempts_exhaust(mock_send, ctx):
    service.start_email_verification(EMAIL, "Rob", ip="1.2.3.4")
    code = mock_send.call_args.args[2]
    for _ in range(5):
        assert service.check_email_verification(EMAIL, "000000") is False
    # 5 wrong attempts kill the code even if correct afterward
    assert service.check_email_verification(EMAIL, code) is False


@patch("app.verify.service.providers.resend_send_code")
def test_new_request_invalidates_old_code(mock_send, ctx):
    service.start_email_verification(EMAIL, "Rob", ip="1.2.3.4")
    old = mock_send.call_args.args[2]
    service.start_email_verification(EMAIL, "Rob", ip="1.2.3.4")
    new = mock_send.call_args.args[2]
    assert service.check_email_verification(EMAIL, old) is False
    assert service.check_email_verification(EMAIL, new) is True


@patch("app.verify.service.providers.resend_send_code")
def test_target_rate_limit(mock_send, ctx):
    for _ in range(3):
        ok, _ = service.start_email_verification(EMAIL, "Rob", ip="1.2.3.4")
        assert ok
    ok, msg = service.start_email_verification(EMAIL, "Rob", ip="1.2.3.4")
    assert not ok and "wait" in msg.lower()


@patch("app.verify.service.providers.twilio_verify_start",
       side_effect=ProviderError("down"))
def test_phone_start_degrades_with_friendly_copy(mock_start, ctx):
    ok, msg = service.start_phone_verification(PHONE, ip="1.2.3.4")
    assert not ok
    assert "email" in msg.lower()  # points at the email path


def test_identity_ttl(app):
    with app.test_request_context():
        service.set_verified_identity(PHONE, user_id=7)
        ident = service.get_verified_identity()
        assert ident["phone_e164"] == PHONE and ident["user_id"] == 7
        # expire it
        from flask import session
        session["verified_identity"]["ts"] = (
            datetime.utcnow() - timedelta(hours=3)).isoformat()
        assert service.get_verified_identity() is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/registration/test_verify_service.py -v`
Expected: FAIL with ModuleNotFoundError (service)

- [ ] **Step 3: Implement `app/verify/service.py`**

```python
"""Verification policy: code lifecycle, rate limits, session identity.

Phone codes live in Twilio Verify; email codes live in VerificationCode.
All user-facing error strings originate here so copy stays in one place.
"""
import hashlib
import secrets
from datetime import datetime, timedelta

from flask import current_app, session

from app.models import db, VerificationCode, VerificationAttempt
from app.verify import providers
from app.verify.providers import ProviderError

CODE_TTL_MINUTES = 10
MAX_CODE_ATTEMPTS = 5
RATE_TARGET_MAX = 3          # sends per target per window
RATE_TARGET_WINDOW_MIN = 10
RATE_IP_MAX = 10             # sends per ip per hour
IDENTITY_TTL_SECONDS = 7200

RATE_LIMIT_MSG = ("We've sent several codes already. The latest one is the "
                  "valid one. Please wait a few minutes before requesting "
                  "another.")
SMS_DOWN_MSG = ("Text messages aren't going through right now. This is on "
                "us, not you. Continue with email verification instead.")
EMAIL_DOWN_MSG = ("We couldn't send the email just now. Please try again in "
                  "a minute, or continue without verification.")


def _hash_code(email, code):
    return hashlib.sha256(f"{email}:{code}".encode()).hexdigest()


def rate_limit_ok(target, ip):
    now = datetime.utcnow()
    target_count = VerificationAttempt.query.filter(
        VerificationAttempt.target == target,
        VerificationAttempt.created_at > now - timedelta(minutes=RATE_TARGET_WINDOW_MIN),
    ).count()
    if target_count >= RATE_TARGET_MAX:
        return False
    ip_count = VerificationAttempt.query.filter(
        VerificationAttempt.ip == ip,
        VerificationAttempt.created_at > now - timedelta(hours=1),
    ).count()
    return ip_count < RATE_IP_MAX


def _record_attempt(target, channel, ip):
    db.session.add(VerificationAttempt(target=target, channel=channel, ip=ip))
    db.session.commit()


def start_phone_verification(phone_e164, ip):
    if not rate_limit_ok(phone_e164, ip):
        return False, RATE_LIMIT_MSG
    _record_attempt(phone_e164, 'sms', ip)
    try:
        providers.twilio_verify_start(phone_e164)
    except ProviderError as exc:
        current_app.logger.warning("verify: sms start failed for %s: %s",
                                   phone_e164, exc)
        return False, SMS_DOWN_MSG
    return True, ''


def check_phone_verification(phone_e164, code):
    try:
        return providers.twilio_verify_check(phone_e164, code)
    except ProviderError as exc:
        current_app.logger.warning("verify: sms check failed for %s: %s",
                                   phone_e164, exc)
        return False


def start_email_verification(email, first_name, ip):
    if not rate_limit_ok(email, ip):
        return False, RATE_LIMIT_MSG
    _record_attempt(email, 'email', ip)
    # New request invalidates anything outstanding for this email.
    VerificationCode.query.filter_by(email=email, consumed_at=None).update(
        {'consumed_at': datetime.utcnow()})
    code = f"{secrets.randbelow(1000000):06d}"
    db.session.add(VerificationCode(
        email=email, code_hash=_hash_code(email, code),
        expires_at=datetime.utcnow() + timedelta(minutes=CODE_TTL_MINUTES)))
    db.session.commit()
    try:
        providers.resend_send_code(email, first_name, code)
    except ProviderError as exc:
        current_app.logger.warning("verify: email send failed for %s: %s",
                                   email, exc)
        return False, EMAIL_DOWN_MSG
    return True, ''


def check_email_verification(email, code):
    row = (VerificationCode.query
           .filter_by(email=email, consumed_at=None)
           .order_by(VerificationCode.created_at.desc())
           .first())
    if row is None or row.expires_at < datetime.utcnow():
        return False
    if row.attempts >= MAX_CODE_ATTEMPTS:
        return False
    if row.code_hash != _hash_code(email, code.strip()):
        row.attempts += 1
        db.session.commit()
        return False
    row.consumed_at = datetime.utcnow()
    db.session.commit()
    return True


def set_verified_identity(phone_e164, user_id=None):
    session['verified_identity'] = {
        'phone_e164': phone_e164,
        'user_id': user_id,
        'ts': datetime.utcnow().isoformat(),
    }


def get_verified_identity():
    ident = session.get('verified_identity')
    if not ident:
        return None
    ts = datetime.fromisoformat(ident['ts'])
    if datetime.utcnow() - ts > timedelta(seconds=IDENTITY_TTL_SECONDS):
        session.pop('verified_identity', None)
        return None
    return ident


def clear_verified_identity():
    session.pop('verified_identity', None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/registration/test_verify_service.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add app/verify/service.py tests/registration/test_verify_service.py
git commit -m "feat(verify): code lifecycle, rate limits, session identity"
```

---

### Task 5: Verify API endpoints

**Files:**
- Create: `app/routes/verify.py`
- Modify: `app/__init__.py` (register blueprint alongside the existing `app.register_blueprint(...)` calls — grep for `register_blueprint`)
- Test: `tests/registration/test_verify_routes.py` (new)

**Interfaces:**
- Consumes: `app.verify.service` (Task 4), `normalize_phone_e164` (Task 1), `User.get_by_phone` (Task 2).
- Produces blueprint `verify_api` with:
  - `POST /api/verify/phone/start` `{phone}` → 200 `{ok: true}` | 200 `{ok: false, error}` | 400 `{ok: false, error}` (unparseable phone)
  - `POST /api/verify/phone/check` `{phone, code}` → `{ok: true, match: 'one'|'none'|'multiple', firstName?}` | `{ok: false, error}`. On `match:'one'` sets session identity with user_id and stamps `phone_verified_at`; otherwise identity has `user_id: None`.
  - `POST /api/verify/email/start` `{email}` → `{ok: true, exists: bool}` | `{ok: false, error}` (exists=False means no member at that email; no code sent)
  - `POST /api/verify/email/check` `{email, code}` → `{ok: true}` | `{ok: false, error}`. On success attaches session phone to that user (`phone_e164`, `phone` display form, both verified timestamps) and upgrades session identity with user_id.
  - `GET /api/verify/prefill` → `{verified: bool, memberType: 'returning'|'new'|null, user: {...}|null}` where `user` contains firstName, lastName, email, pronouns, dob (YYYY-MM-DD), phone, technique, tshirtSize, experience, emergencyName, emergencyRelation, emergencyPhone, emergencyEmail. `user` is non-null only when the session identity carries a user_id.

- [ ] **Step 1: Write the failing tests**

```python
# tests/registration/test_verify_routes.py
from datetime import date
from unittest.mock import patch

import pytest

from app import create_app
from app.models import db, User

PHONE_RAW = "612-555-0177"
PHONE = "+16125550177"
EMAIL = "verify-routes@test.com"


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"
    )
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def member(app):
    with app.app_context():
        u = User(email=EMAIL, first_name="Vera", last_name="Route",
                 phone="612-555-0177", phone_e164=PHONE,
                 date_of_birth=date(1995, 3, 2),
                 emergency_contact_name="Max Route")
        db.session.add(u)
        db.session.commit()
        uid = u.id
    yield uid
    with app.app_context():
        u = User.query.get(uid)
        if u:
            db.session.delete(u)
            db.session.commit()


def test_phone_start_rejects_garbage(client):
    resp = client.post("/api/verify/phone/start", json={"phone": "abc"})
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False


@patch("app.routes.verify.service.check_phone_verification", return_value=True)
@patch("app.routes.verify.service.start_phone_verification",
       return_value=(True, ""))
def test_phone_check_match_one(mock_start, mock_check, client, member, app):
    client.post("/api/verify/phone/start", json={"phone": PHONE_RAW})
    resp = client.post("/api/verify/phone/check",
                       json={"phone": PHONE_RAW, "code": "123456"})
    body = resp.get_json()
    assert body == {"ok": True, "match": "one", "firstName": "Vera"}
    # phone_verified_at stamped
    with app.app_context():
        assert User.query.get(member).phone_verified_at is not None
    # prefill now available
    pre = client.get("/api/verify/prefill").get_json()
    assert pre["verified"] is True
    assert pre["user"]["firstName"] == "Vera"
    assert pre["user"]["dob"] == "1995-03-02"


@patch("app.routes.verify.service.check_phone_verification", return_value=True)
def test_phone_check_no_match(mock_check, client):
    resp = client.post("/api/verify/phone/check",
                       json={"phone": "612-555-0199", "code": "123456"})
    assert resp.get_json()["match"] == "none"


@patch("app.routes.verify.service.check_phone_verification", return_value=False)
def test_phone_check_wrong_code(mock_check, client):
    resp = client.post("/api/verify/phone/check",
                       json={"phone": PHONE_RAW, "code": "000000"})
    assert resp.get_json()["ok"] is False


@patch("app.routes.verify.service.check_email_verification", return_value=True)
@patch("app.routes.verify.service.check_phone_verification", return_value=True)
def test_email_check_attaches_phone(mock_pcheck, mock_echeck, client, app):
    with app.app_context():
        u = User(email=EMAIL, first_name="Vera", last_name="Route")
        db.session.add(u)
        db.session.commit()
        uid = u.id
    try:
        # phone verified but unmatched
        client.post("/api/verify/phone/check",
                    json={"phone": "612-555-0198", "code": "123456"})
        resp = client.post("/api/verify/email/check",
                           json={"email": EMAIL, "code": "654321"})
        assert resp.get_json()["ok"] is True
        with app.app_context():
            u = User.query.get(uid)
            assert u.phone_e164 == "+16125550198"
            assert u.phone_verified_at is not None
            assert u.email_verified_at is not None
    finally:
        with app.app_context():
            u = User.query.get(uid)
            if u:
                db.session.delete(u)
                db.session.commit()


def test_prefill_unverified(client):
    pre = client.get("/api/verify/prefill").get_json()
    assert pre == {"verified": False, "memberType": None, "user": None}


def test_email_check_requires_verified_phone_in_session(client, member):
    resp = client.post("/api/verify/email/check",
                       json={"email": EMAIL, "code": "654321"})
    assert resp.get_json()["ok"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/registration/test_verify_routes.py -v`
Expected: FAIL (404s / ModuleNotFoundError)

- [ ] **Step 3: Implement `app/routes/verify.py`**

```python
"""JSON endpoints for the registration verification step (step 0)."""
from datetime import datetime

from flask import Blueprint, jsonify, request

from app.models import db, User
from app.utils import normalize_email, normalize_phone_e164, format_phone_display
from app.verify import service

verify_api = Blueprint('verify_api', __name__)


def _client_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr or '?').split(',')[0].strip()


@verify_api.route('/api/verify/phone/start', methods=['POST'])
def phone_start():
    data = request.get_json() or {}
    phone = normalize_phone_e164(data.get('phone'))
    if not phone:
        return jsonify(ok=False, error='Please enter a 10-digit US cell number.'), 400
    ok, error = service.start_phone_verification(phone, ip=_client_ip())
    return jsonify(ok=ok, error=error or None)


@verify_api.route('/api/verify/phone/check', methods=['POST'])
def phone_check():
    data = request.get_json() or {}
    phone = normalize_phone_e164(data.get('phone'))
    code = (data.get('code') or '').strip()
    if not phone or not code:
        return jsonify(ok=False, error='Missing phone or code.'), 400
    if not service.check_phone_verification(phone, code):
        return jsonify(ok=False, error="That code didn't match. Check the text and try again.")
    matches = User.get_by_phone(phone)
    if len(matches) == 1:
        user = matches[0]
        user.phone_verified_at = datetime.utcnow()
        db.session.commit()
        service.set_verified_identity(phone, user_id=user.id)
        return jsonify(ok=True, match='one', firstName=user.first_name)
    service.set_verified_identity(phone, user_id=None)
    return jsonify(ok=True, match='multiple' if matches else 'none')


@verify_api.route('/api/verify/email/start', methods=['POST'])
def email_start():
    ident = service.get_verified_identity()
    if not ident:
        return jsonify(ok=False, error='Verify your phone first.'), 400
    email = normalize_email((request.get_json() or {}).get('email', ''))
    user = User.get_by_email(email)
    if not user:
        return jsonify(ok=True, exists=False)
    ok, error = service.start_email_verification(
        email, user.first_name, ip=_client_ip())
    return jsonify(ok=ok, exists=True, error=error or None)


@verify_api.route('/api/verify/email/check', methods=['POST'])
def email_check():
    ident = service.get_verified_identity()
    if not ident:
        return jsonify(ok=False, error='Verify your phone first.'), 400
    data = request.get_json() or {}
    email = normalize_email(data.get('email', ''))
    code = (data.get('code') or '').strip()
    user = User.get_by_email(email)
    if not user or not service.check_email_verification(email, code):
        return jsonify(ok=False, error="That code didn't match. Check your email and try again.")
    user.phone_e164 = ident['phone_e164']
    user.phone = format_phone_display(ident['phone_e164'])
    user.phone_verified_at = datetime.utcnow()
    user.email_verified_at = datetime.utcnow()
    db.session.commit()
    service.set_verified_identity(ident['phone_e164'], user_id=user.id)
    return jsonify(ok=True)


@verify_api.route('/api/verify/prefill')
def prefill():
    ident = service.get_verified_identity()
    if not ident:
        return jsonify(verified=False, memberType=None, user=None)
    user = User.query.get(ident['user_id']) if ident.get('user_id') else None
    if not user:
        return jsonify(verified=True, memberType='new', user=None)
    return jsonify(
        verified=True,
        memberType='returning' if user.is_returning else 'new',
        user={
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
        })
```

Add to `app/utils.py` (below `normalize_phone_e164`):

```python
def format_phone_display(phone_e164):
    """+16128677165 -> 612-867-7165, the format prod data already uses."""
    if not phone_e164 or len(phone_e164) != 12:
        return phone_e164
    d = phone_e164[2:]
    return f"{d[0:3]}-{d[3:6]}-{d[6:10]}"
```

Register in `app/__init__.py` next to the other blueprints:

```python
    from app.routes.verify import verify_api
    app.register_blueprint(verify_api)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/registration/test_verify_routes.py tests/registration/ -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add app/routes/verify.py app/__init__.py app/utils.py tests/registration/test_verify_routes.py
git commit -m "feat(verify): step-0 JSON endpoints (phone/email codes, prefill)"
```

---

### Task 6: SMS notifier and templates

**Files:**
- Create: `app/notifications/sms.py`, `config/sms.yaml`
- Test: `tests/registration/test_sms_notifier.py` (new)

**Interfaces:**
- Consumes: `providers.twilio_send_sms` (Task 3), `User.phone_e164`/`sms_opt_out` (Task 2).
- Produces: `send_sms(user, template_key: str, **kwargs) -> bool` in `app.notifications.sms`. Template keys: `confirmation_returning` (kwargs: season_name, amount), `confirmation_lottery` (kwargs: season_name), `slack_invite` (no kwargs). Never raises; returns False and logs on any failure; sets `user.sms_opt_out = True` on Twilio error 21610.

- [ ] **Step 1: Create `config/sms.yaml`**

```yaml
# Member-facing SMS templates. Plain GSM-7, no emoji, one segment each.
templates:
  confirmation_returning: "TCSC: You're registered for the {season_name} season! Your card was charged {amount}. See you out there. Reply STOP to opt out"
  confirmation_lottery: "TCSC: You're in the lottery for the {season_name} season! There's a hold on your card, but you're only charged if you get a spot. We'll be in touch. Reply STOP to opt out"
  slack_invite: "TCSC: Welcome to the club! Your Slack invite just landed in your email. That's where everything happens, so come say hi. Reply STOP to opt out"
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/registration/test_sms_notifier.py
from unittest.mock import patch

import pytest

from app import create_app
from app.models import db, User
from app.notifications.sms import send_sms
from app.verify.providers import ProviderError

EMAIL = "sms-notify@test.com"


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"
    )
    return app


@pytest.fixture
def user(app):
    with app.app_context():
        u = User(email=EMAIL, first_name="Sam", last_name="Sender",
                 phone_e164="+16125550166")
        db.session.add(u)
        db.session.commit()
        yield u
        db.session.delete(User.query.get(u.id))
        db.session.commit()


@patch("app.notifications.sms.twilio_send_sms")
def test_sends_rendered_template(mock_send, app, user):
    with app.app_context():
        ok = send_sms(user, "confirmation_returning",
                      season_name="2026-27", amount="$150.00")
    assert ok is True
    body = mock_send.call_args.args[1]
    assert "2026-27" in body and "$150.00" in body
    assert body.endswith("Reply STOP to opt out")


@patch("app.notifications.sms.twilio_send_sms")
def test_skips_opted_out_and_phoneless(mock_send, app, user):
    with app.app_context():
        u = User.query.get(user.id)
        u.sms_opt_out = True
        assert send_sms(u, "slack_invite") is False
        u.sms_opt_out = False
        u.phone_e164 = None
        assert send_sms(u, "slack_invite") is False
    mock_send.assert_not_called()


@patch("app.notifications.sms.twilio_send_sms",
       side_effect=ProviderError("unsubscribed", code=21610))
def test_records_opt_out_on_21610(mock_send, app, user):
    with app.app_context():
        assert send_sms(User.query.get(user.id), "slack_invite") is False
        assert User.query.get(user.id).sms_opt_out is True


@patch("app.notifications.sms.twilio_send_sms",
       side_effect=ProviderError("boom"))
def test_never_raises(mock_send, app, user):
    with app.app_context():
        assert send_sms(User.query.get(user.id), "slack_invite") is False
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/registration/test_sms_notifier.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 4: Implement `app/notifications/sms.py`**

```python
"""Member-facing SMS. One entry point; a failed text never fails its caller."""
import os

import yaml
from flask import current_app

from app.models import db
from app.verify.providers import ProviderError, twilio_send_sms

_TEMPLATES = None


def _templates():
    global _TEMPLATES
    if _TEMPLATES is None:
        path = os.path.join(current_app.root_path, '..', 'config', 'sms.yaml')
        with open(path) as fh:
            _TEMPLATES = yaml.safe_load(fh)['templates']
    return _TEMPLATES


def send_sms(user, template_key, **kwargs):
    """Render config/sms.yaml template_key and text it to user.phone_e164.

    Returns True on send, False on skip or failure. Never raises.
    """
    try:
        if not user.phone_e164 or user.sms_opt_out:
            return False
        body = _templates()[template_key].format(**kwargs)
        twilio_send_sms(user.phone_e164, body)
        current_app.logger.info("sms: sent %s to user %s", template_key, user.id)
        return True
    except ProviderError as exc:
        if exc.code == 21610:  # recipient has replied STOP
            user.sms_opt_out = True
            db.session.commit()
        current_app.logger.warning(
            "sms: %s to user %s failed: %s", template_key, user.id, exc)
        return False
    except Exception as exc:
        current_app.logger.warning(
            "sms: %s to user %s failed: %s", template_key, user.id, exc)
        return False
```

(`yaml` is already a dependency — the practices/newsletter configs use it.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/registration/test_sms_notifier.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add app/notifications/sms.py config/sms.yaml tests/registration/test_sms_notifier.py
git commit -m "feat(sms): member SMS notifier with yaml templates and opt-out capture"
```

---

### Task 7: Registration POST — verified identity replaces the status radio

**Files:**
- Modify: `app/routes/registration.py:53-218` (`season_register`)
- Test: `tests/registration/test_season_register_verified.py` (new)

**Interfaces:**
- Consumes: `service.get_verified_identity()` / `clear_verified_identity()` (Task 4), `normalize_phone_e164`, `format_phone_display` (Tasks 1/5), `send_sms` (Task 6), `UserSeason.needs_review` (Task 2).
- Produces: POST behavior later tasks and the frontend rely on:
  - The form no longer sends `status`; a hidden `continue_unverified` field ("1" when the member chose the flagged unverified path) is read.
  - Response semantics otherwise unchanged (`season_success.html` render on success).

- [ ] **Step 1: Write the failing tests**

```python
# tests/registration/test_season_register_verified.py
from datetime import datetime, timedelta, date
from unittest.mock import patch

import pytest

from app import create_app
from app.models import db, Season, User, UserSeason

EMAIL = "reg-verified@test.com"
PHONE = "+16125550188"


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"
    )
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def season(app):
    with app.app_context():
        now = datetime.utcnow()
        s = Season(name="Verify Test", year=2099, price_cents=15000,
                   start_date=date(2099, 11, 1), end_date=date(2100, 3, 1),
                   returning_start=now - timedelta(days=1),
                   returning_end=now + timedelta(days=30),
                   new_start=now - timedelta(days=1),
                   new_end=now + timedelta(days=30))
        db.session.add(s)
        db.session.commit()
        yield s.id
        UserSeason.query.filter_by(season_id=s.id).delete()
        u = User.query.filter_by(email=EMAIL).one_or_none()
        if u:
            db.session.delete(u)
        db.session.delete(Season.query.get(s.id))
        db.session.commit()


FORM = dict(
    firstName="Reg", lastName="Verified", email=EMAIL, pronouns="",
    dob="1994-01-15", phone="612-555-0188", technique="skate",
    tshirtSize="M", experience="intermediate", emergencyName="Em Contact",
    emergencyRelation="friend", emergencyPhone="612-555-0189",
    emergencyEmail="em@example.com", payment_intent_id="pi_test_verify",
)


def _set_identity(client, user_id=None):
    with client.session_transaction() as sess:
        sess["verified_identity"] = {
            "phone_e164": PHONE, "user_id": user_id,
            "ts": datetime.utcnow().isoformat()}


@patch("app.routes.registration.send_sms", return_value=True)
def test_verified_new_member_gets_e164_and_lottery_sms(mock_sms, client, app, season):
    _set_identity(client)
    resp = client.post(f"/seasons/{season}/register", data=FORM)
    assert resp.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email=EMAIL).one()
        assert user.phone_e164 == PHONE
        assert user.phone_verified_at is not None
        us = UserSeason.get_for_user_season(user.id, season)
        assert us.needs_review is False
    assert mock_sms.call_args.args[1] == "confirmation_lottery"


@patch("app.routes.registration.send_sms", return_value=True)
def test_unverified_flags_needs_review(mock_sms, client, app, season):
    # no session identity at all + explicit continue_unverified
    resp = client.post(f"/seasons/{season}/register",
                       data={**FORM, "continue_unverified": "1"})
    assert resp.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email=EMAIL).one()
        us = UserSeason.get_for_user_season(user.id, season)
        assert us.needs_review is True
        assert user.phone_verified_at is None
        assert user.phone_e164 == "+16125550188"  # normalized, but unverified


def test_unverified_without_flag_is_rejected(client, app, season):
    resp = client.post(f"/seasons/{season}/register", data=FORM,
                       follow_redirects=False)
    assert resp.status_code == 302  # bounced back with flash error


@patch("app.routes.registration.send_sms", return_value=True)
def test_new_email_collision_without_flag_rejected(mock_sms, client, app, season):
    with app.app_context():
        db.session.add(User(email=EMAIL, first_name="Old", last_name="Row"))
        db.session.commit()
    _set_identity(client)  # verified phone, but user_id None -> "new" path
    resp = client.post(f"/seasons/{season}/register", data=FORM,
                       follow_redirects=False)
    assert resp.status_code == 302  # collision guard fired


@patch("app.routes.registration.send_sms", return_value=True)
def test_verified_returning_member_updates_own_row(mock_sms, client, app, season):
    with app.app_context():
        u = User(email=EMAIL, first_name="Old", last_name="Name")
        db.session.add(u)
        db.session.commit()
        uid = u.id
    _set_identity(client, user_id=uid)
    resp = client.post(f"/seasons/{season}/register", data=FORM)
    assert resp.status_code == 200
    with app.app_context():
        user = User.query.get(uid)
        assert user.first_name == "Reg"  # updated in place, no duplicate row
        assert User.query.filter_by(email=EMAIL).count() == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/registration/test_season_register_verified.py -v`
Expected: FAIL (the `status` KeyError path / no needs_review handling)

- [ ] **Step 3: Rework `season_register` POST**

In `app/routes/registration.py`:

Imports at top:

```python
from ..utils import (get_current_times, normalize_email, normalize_phone_e164,
                     format_phone_display, format_datetime_central,
                     today_central, validate_registration_form)
from ..verify.service import get_verified_identity, clear_verified_identity
from ..notifications.sms import send_sms
```

Replace the identity/claim section (current lines 70-117, from `email = normalize_email(...)` through the `client_claimed_status` checks) with:

```python
            form = request.form
            email = normalize_email(form['email'])
            identity = get_verified_identity()
            verified_user = None
            if identity and identity.get('user_id'):
                verified_user = User.query.get(identity['user_id'])

            continue_unverified = form.get('continue_unverified') == '1'
            if identity is None and not continue_unverified:
                # Session expired or the member skipped step 0 entirely.
                flash_error('Your verification expired. Please verify your '
                            'number again — your answers are saved.')
                return redirect(url_for('registration.season_register',
                                        season_id=season_id))

            if verified_user is not None:
                user = verified_user
                if email != user.email and User.get_by_email(email):
                    flash_error('That email already belongs to another '
                                'member. Please use a different one.')
                    return redirect(url_for('registration.season_register',
                                            season_id=season_id))
            else:
                user = None
                existing = User.get_by_email(email)
                if existing is not None:
                    if continue_unverified:
                        # Flagged path: reuse the row, admin will review.
                        user = existing
                    else:
                        flash_error('That email already has a member account. '
                                    'Go back and verify with this email, or '
                                    'choose "Continue anyway" if you can no '
                                    'longer receive mail there.')
                        return redirect(url_for('registration.season_register',
                                                season_id=season_id))

            verified = identity is not None and verified_user is not None

            if invite_token and user is not None:
                existing_us = UserSeason.get_for_user_season(user.id, season.id)
                if existing_us and existing_us.status in (
                        UserSeasonStatus.ACTIVE, UserSeasonStatus.PENDING_LOTTERY):
                    flash_error("This link has already been used — you're "
                                "already registered for this season.")
                    return redirect(url_for('registration.season_register',
                                            season_id=season_id))

            payment_intent_id = form.get('payment_intent_id')
            if not payment_intent_id:
                flash_error('Payment is required to complete registration.')
                return redirect(url_for('registration.season_register',
                                        season_id=season_id))
            existing_payment = Payment.get_by_payment_intent(payment_intent_id)

            # Returning only when the identity is verified; unverified
            # registrations are treated as new (manual capture) and reviewed.
            is_returning = bool(verified and user and user.is_returning)
            member_type_str = 'returning' if is_returning else 'new'
```

(Keep the existing invite-token validation and window-check block that follows, unchanged, minus the deleted `client_claimed_status` checks.)

In the user-fields section, after `user_fields = dict(...)` add the normalized phone; and stamp verification on write:

```python
            phone_e164 = normalize_phone_e164(form['phone'])
            if identity is not None:
                # The verified number wins over whatever is typed in the form.
                phone_e164 = identity['phone_e164']
                user_fields['phone'] = format_phone_display(phone_e164)
```

After the `if user: ... else: user = User(...)` block:

```python
            user.phone_e164 = phone_e164
            if identity is not None:
                user.phone_verified_at = user.phone_verified_at or datetime.utcnow()
```

In the UserSeason create/update block, set review status (both branches):

```python
            needs_review = not verified
            # ... inside the create branch:
                user_season = UserSeason(
                    user_id=user.id,
                    season_id=season.id,
                    registration_type=member_type,
                    registration_date=today_central(),
                    status=UserSeasonStatus.ACTIVE if is_returning else UserSeasonStatus.PENDING_LOTTERY,
                    needs_review=needs_review,
                )
            # ... and in the update branch add:
                user_season.needs_review = needs_review
```

After `db.session.commit()` and before the success render:

```python
            amount_display = f"${season.price_cents / 100:.2f}" if season.price_cents else None
            if is_returning:
                send_sms(user, 'confirmation_returning',
                         season_name=season.name, amount=amount_display)
            else:
                send_sms(user, 'confirmation_lottery', season_name=season.name)
            clear_verified_identity()
```

Also delete the now-dead `/api/is_returning_member` client dependency LATER (Task 9 removes the frontend call; keep the endpoint itself for now — it is the documented revert path).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/registration/ -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add app/routes/registration.py tests/registration/test_season_register_verified.py
git commit -m "feat(registration): derive status from verified session, needs_review, confirmation SMS"
```

---

### Task 8: Payment intent — capture method from the verified session

**Files:**
- Modify: `app/routes/payments.py:651-720` (`create_season_payment_intent`)
- Test: `tests/registration/test_payment_intent_verified.py` (new)

**Interfaces:**
- Consumes: `get_verified_identity()` (Task 4).
- Produces: `POST /create-season-payment-intent` derives member_type/capture from the session, not the posted email. Metadata gains `'verified': 'true'|'false'`. Behavior matrix:
  - session identity with user_id whose user `is_returning` → RETURNING / `automatic`
  - session identity otherwise → NEW / `manual`
  - no session identity (degraded path) → NEW / `manual`, verified='false'
  - The email-based duplicate-payment guard and window checks stay.

- [ ] **Step 1: Write the failing tests**

```python
# tests/registration/test_payment_intent_verified.py
from datetime import datetime, timedelta, date
from unittest.mock import patch, MagicMock

import pytest

from app import create_app
from app.models import db, Season, User, UserSeason
from app.constants import UserSeasonStatus

EMAIL = "pi-verified@test.com"
PHONE = "+16125550190"


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"
    )
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def fixtures(app):
    with app.app_context():
        now = datetime.utcnow()
        s = Season(name="PI Test", year=2098, price_cents=15000,
                   start_date=date(2098, 11, 1), end_date=date(2099, 3, 1),
                   returning_start=now - timedelta(days=1),
                   returning_end=now + timedelta(days=30),
                   new_start=now - timedelta(days=1),
                   new_end=now + timedelta(days=30))
        old = Season(name="PI Old", year=2088, price_cents=15000,
                     start_date=date(2088, 11, 1), end_date=date(2089, 3, 1))
        u = User(email=EMAIL, first_name="Pat", last_name="Payer",
                 phone_e164=PHONE)
        db.session.add_all([s, old, u])
        db.session.commit()
        db.session.add(UserSeason(user_id=u.id, season_id=old.id,
                                  registration_type="new",
                                  registration_date=date(2088, 10, 1),
                                  status=UserSeasonStatus.ACTIVE))
        db.session.commit()
        yield {"season_id": s.id, "user_id": u.id}
        UserSeason.query.filter_by(user_id=u.id).delete()
        db.session.delete(User.query.get(u.id))
        db.session.delete(Season.query.get(s.id))
        db.session.delete(Season.query.get(old.id))
        db.session.commit()


def _set_identity(client, user_id=None):
    with client.session_transaction() as sess:
        sess["verified_identity"] = {
            "phone_e164": PHONE, "user_id": user_id,
            "ts": datetime.utcnow().isoformat()}


def _intent_mock():
    m = MagicMock()
    m.id, m.client_secret, m.amount, m.status = "pi_x", "cs_x", 15000, "requires_payment_method"
    return m


@patch("app.routes.payments.stripe.PaymentIntent.create", return_value=_intent_mock())
def test_verified_returning_gets_automatic_capture(mock_create, client, fixtures):
    _set_identity(client, user_id=fixtures["user_id"])
    resp = client.post("/create-season-payment-intent", json={
        "season_id": fixtures["season_id"], "email": EMAIL, "name": "Pat Payer"})
    assert resp.status_code == 200
    kwargs = mock_create.call_args.kwargs
    assert kwargs["capture_method"] == "automatic"
    assert kwargs["metadata"]["member_type"] == "RETURNING"
    assert kwargs["metadata"]["verified"] == "true"


@patch("app.routes.payments.stripe.PaymentIntent.create", return_value=_intent_mock())
def test_unverified_is_always_manual_new(mock_create, client, fixtures):
    # No session identity: even though EMAIL belongs to a returning member,
    # the typed email must not grant automatic capture.
    resp = client.post("/create-season-payment-intent", json={
        "season_id": fixtures["season_id"], "email": EMAIL, "name": "Pat Payer"})
    assert resp.status_code == 200
    kwargs = mock_create.call_args.kwargs
    assert kwargs["capture_method"] == "manual"
    assert kwargs["metadata"]["member_type"] == "NEW"
    assert kwargs["metadata"]["verified"] == "false"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/registration/test_payment_intent_verified.py -v`
Expected: `test_unverified_is_always_manual_new` FAILS (current code trusts the email)

- [ ] **Step 3: Rework the endpoint**

In `create_season_payment_intent` (`app/routes/payments.py:651`), add import `from app.verify.service import get_verified_identity` at the top of the file, then replace the member_type derivation block (`user = User.get_by_email(email)` / `member_type = ...`) with:

```python
        # Identity comes from the verified session, never the typed email.
        identity = get_verified_identity()
        verified_user = None
        if identity and identity.get('user_id'):
            verified_user = User.query.get(identity['user_id'])
        if verified_user is not None and verified_user.is_returning:
            member_type = MemberType.RETURNING.value
        else:
            member_type = MemberType.NEW.value
        verified = identity is not None and verified_user is not None
```

Replace the capture-method block with:

```python
        # Returning members are guaranteed a spot: charge immediately.
        # Everyone else (new or unverified) gets a hold; see CLAUDE.md.
        capture_method = 'automatic' if member_type == MemberType.RETURNING.value else 'manual'
```

Add to the metadata dict:

```python
                'verified': 'true' if verified else 'false',
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/registration/test_payment_intent_verified.py tests/registration/ tests/routes/ -v`
Expected: PASS (if an existing tests/routes/ test asserted the old email-derived behavior, update that test to set the session identity — the new behavior is the spec).

- [ ] **Step 5: Commit**

```bash
git add app/routes/payments.py tests/
git commit -m "feat(payments): capture method derives from verified session"
```

---

### Task 9: Wizard UI — step 0, prefill, emergency confirm, payment status line

This task is the frontend; it has no pytest cycle. Verify each step by loading the page via `./scripts/dev.sh 5001` and exercising it, with Twilio live (dev `.env` has real keys — codes go to real phones, use Rob's cell only).

**Files:**
- Modify: `app/templates/season_register.html` (~250 lines: add step-0 section, remove the status radio block at lines 74-78, add emergency-confirm and payment-status-line markup)
- Modify: `app/static/script.js` (~588 lines: step-0 logic, prefill application, sessionStorage persistence; remove the `/api/is_returning_member` blur handler at lines 291-330)

**Interfaces:**
- Consumes: `/api/verify/*` endpoints exactly as specified in Task 5; form POST contract from Task 7 (`continue_unverified` hidden field, no `status` field).

- [ ] **Step 1: Template — add step 0 ahead of the wizard**

Insert before the progress bar in `season_register.html` (verify class names against the file — reuse existing `form-section`, `form-input`, `btn` classes):

```html
<section id="section-verify" class="form-section form-section--active">
  <h2 class="form-section__title">Let's find you</h2>
  <p class="form-section__subtitle">We'll text a code to confirm your number.</p>

  <div id="verify-phone-entry">
    <input class="form-input" type="tel" id="verify-phone" inputmode="tel"
           autocomplete="tel" placeholder="Your cell number">
    <button type="button" class="btn btn--primary" id="verify-send-btn">Text me a code</button>
    <p class="form-hint">
      <a href="#" id="verify-skip-link">New to TCSC? Start here.</a>
      (Skied with us before? Verify above. Registering as new puts you in the
      new-member lottery.)
    </p>
    <p class="form-hint"><a href="#" id="verify-cant-text-link">Can't receive texts?</a></p>
  </div>

  <div id="verify-code-entry" hidden>
    <p>We texted <span id="verify-phone-echo"></span>
       <a href="#" id="verify-edit-phone">Edit</a></p>
    <input class="form-input" type="text" id="verify-code" inputmode="numeric"
           autocomplete="one-time-code" maxlength="8" placeholder="6-digit code">
    <button type="button" class="btn btn--primary" id="verify-check-btn">Verify</button>
    <button type="button" class="btn" id="verify-resend-btn" disabled>Resend (30)</button>
    <p class="form-hint">Registering on a computer? The code went to your
       phone. It may not light up if Do Not Disturb is on.</p>
  </div>

  <div id="verify-email-entry" hidden>
    <p id="verify-email-msg">Your number's verified. We just don't have it on
       file yet (most alumni don't). Enter the email you've used with the club
       and we'll link you up.</p>
    <input class="form-input" type="email" id="verify-email" autocomplete="email"
           placeholder="Email you've used with the club">
    <button type="button" class="btn btn--primary" id="verify-email-send-btn">Email me a code</button>
    <div id="verify-email-code-row" hidden>
      <p>Enter the code we emailed to <span id="verify-email-echo"></span></p>
      <input class="form-input" type="text" id="verify-email-code"
             inputmode="numeric" autocomplete="one-time-code" maxlength="8">
      <button type="button" class="btn btn--primary" id="verify-email-check-btn">Verify</button>
    </div>
    <p class="form-hint"><a href="#" id="verify-email-dead-link">That email
       doesn't work for me anymore</a></p>
  </div>

  <div id="verify-error" class="form-error" hidden></div>
</section>
```

Remove the status radio block (the two `<input type="radio" name="status">` labels) and add inside the form:

```html
<input type="hidden" name="continue_unverified" id="continue-unverified" value="0">
```

Emergency section: wrap the existing four emergency inputs in `<div id="emergency-edit">` and add above them:

```html
<div id="emergency-confirm" hidden>
  <p>Still your emergency contact?</p>
  <p id="emergency-summary"></p>
  <button type="button" class="btn btn--primary" id="emergency-keep-btn">Yes, keep</button>
  <button type="button" class="btn" id="emergency-update-btn">Update</button>
</div>
```

Payment section, above the card element:

```html
<p id="payment-status-line" class="form-hint"></p>
```

- [ ] **Step 2: JS — step-0 controller + prefill + persistence**

In `app/static/script.js`, delete the `/api/is_returning_member` blur handler (lines 291-330) and everything that reads the status radios; add a step-0 module (top of the DOMContentLoaded handler). Core logic (adapt names to the file's existing helpers for section switching):

```javascript
const verify = {
  phone: null,
  async sendCode() {
    const resp = await fetch('/api/verify/phone/start', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({phone: document.getElementById('verify-phone').value})});
    const body = await resp.json();
    if (!body.ok) return showVerifyError(body.error);
    this.phone = document.getElementById('verify-phone').value;
    document.getElementById('verify-phone-echo').textContent = this.phone;
    show('verify-code-entry'); hide('verify-phone-entry');
    startResendCountdown(30);
  },
  async checkCode() {
    const resp = await fetch('/api/verify/phone/check', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({phone: this.phone,
        code: document.getElementById('verify-code').value})});
    const body = await resp.json();
    if (!body.ok) return showVerifyError(body.error);
    if (body.match === 'one') {
      await applyPrefill();      // fetch /api/verify/prefill, fill the form
      enterWizard();             // hide step 0, show step 1 with "Welcome back"
    } else {
      // 'none' and 'multiple' both route to the email step; only the copy differs
      if (body.match === 'multiple') {
        document.getElementById('verify-email-msg').textContent =
          "More than one member shares this number, so we'll match you by " +
          "email instead. Enter the email you've used with the club.";
      }
      show('verify-email-entry'); hide('verify-code-entry');
    }
  },
  // email send/check mirror the phone pair against /api/verify/email/*;
  // on email/check ok: await applyPrefill(); enterWizard();
};
```

Prefill application (`applyPrefill`): GET `/api/verify/prefill`; when `user` is non-null set each input by id (`firstName` → `#firstName` etc., matching the template's existing ids — read them from the file), set the email field, and for the emergency section populate `#emergency-summary` with `emergencyName (emergencyRelation), emergencyPhone` then show `#emergency-confirm` and hide `#emergency-edit`. "Yes, keep" advances; "Update" swaps the edit fields in. When `user` is null leave the form blank. Set the payment status line from `memberType`:

```javascript
function setPaymentStatusLine(memberType, priceDollars) {
  const el = document.getElementById('payment-status-line');
  el.textContent = memberType === 'returning'
    ? `You're registering as a returning member. Your card will be charged ${priceDollars} today.`
    : `You're registering as a new member. We'll place a hold on your card; you're only charged if you get a spot in the lottery.`;
}
```

Escape hatches: `#verify-skip-link` and `#verify-cant-text-link` both call `enterWizard()` with no prefill and set `#continue-unverified` to "1" ONLY for `#verify-email-dead-link` and `#verify-cant-text-link` flows that skip verification entirely; the plain "New to TCSC" link keeps "0" when the phone was verified (identity in session) and "1" when it wasn't. Rule: `continue_unverified = session-verified ? "0" : "1"` — track a local `phoneVerified` boolean set true after a successful `/api/verify/phone/check`.

Resend countdown: disable `#verify-resend-btn`, tick the label every second from 30, then enable; clicking calls `sendCode()` again.

Form persistence: on every `input` event in the form, save `FormData` entries (except payment fields) to `sessionStorage['tcsc-reg-' + seasonId]`; on page load, restore before prefill (prefill wins over stored values only when the field is empty). Clear the key on successful submit.

- [ ] **Step 3: Manual verification pass**

Run `./scripts/dev.sh 5001`, open the current season's register URL:
- Step 0 renders first, wizard hidden. Send a code to Rob's cell (612-867-7165), verify, confirm the match path prefires "Welcome back".
- Wrong code shows the error and does NOT clear the input.
- Refresh mid-wizard: fields restore from sessionStorage.
- Escape-hatch link shows the lottery warning copy.
Fix what's broken before committing.

- [ ] **Step 4: Run the full registration suite (backend unaffected, but confirm)**

Run: `pytest tests/registration/ -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/templates/season_register.html app/static/script.js
git commit -m "feat(registration): step-0 verify UI, prefill, emergency confirm, payment status line"
```

---

### Task 10: Slack invite SMS heads-up

**Files:**
- Modify: `app/slack/channel_sync.py:604-663` (`invite_new_members`)
- Test: `tests/slack/test_invite_sms_nudge.py` (new)

**Interfaces:**
- Consumes: `send_sms` (Task 6).
- Produces: after each successful (non-dry-run) `invite_user_by_email`, the invited user gets the `slack_invite` template. Dry-run sends nothing.

- [ ] **Step 1: Write the failing test**

```python
# tests/slack/test_invite_sms_nudge.py
from unittest.mock import patch, MagicMock

import pytest

from app import create_app
from app.models import db, User
from app.slack.channel_sync import invite_new_members, ChannelSyncResult

EMAIL = "invite-sms@test.com"


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"
    )
    return app


@pytest.fixture
def user(app):
    with app.app_context():
        u = User(email=EMAIL, first_name="Inv", last_name="Itee",
                 phone_e164="+16125550170")
        db.session.add(u)
        db.session.commit()
        yield
        db.session.delete(User.query.filter_by(email=EMAIL).one())
        db.session.commit()


@patch("app.slack.channel_sync.send_sms", return_value=True)
@patch("app.slack.channel_sync.invite_user_by_email")
def test_sms_nudge_after_successful_invite(mock_invite, mock_sms, app, user):
    with app.app_context():
        result = ChannelSyncResult()
        invite_new_members(
            db_email_to_tier={EMAIL: "full_member"}, slack_emails=set(),
            exception_emails=set(), target_channel_ids=["C1"], team_id="T1",
            invitation_message="welcome", dry_run=False, result=result)
    mock_sms.assert_called_once()
    assert mock_sms.call_args.args[1] == "slack_invite"


@patch("app.slack.channel_sync.send_sms")
@patch("app.slack.channel_sync.invite_user_by_email")
def test_dry_run_sends_no_sms(mock_invite, mock_sms, app, user):
    with app.app_context():
        result = ChannelSyncResult()
        invite_new_members(
            db_email_to_tier={EMAIL: "full_member"}, slack_emails=set(),
            exception_emails=set(), target_channel_ids=["C1"], team_id="T1",
            invitation_message="welcome", dry_run=True, result=result)
    mock_sms.assert_not_called()
```

(If `ChannelSyncResult()` requires constructor args, mirror how `tests/slack/` existing tests build it.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/slack/test_invite_sms_nudge.py -v`
Expected: FAIL (send_sms not importable from channel_sync)

- [ ] **Step 3: Implement**

In `app/slack/channel_sync.py`, add `from app.notifications.sms import send_sms` at the top, and in `invite_new_members` after `result.invites_sent += 1`:

```python
            if not dry_run and db_user is not None:
                send_sms(db_user, 'slack_invite')
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/slack/test_invite_sms_nudge.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/slack/channel_sync.py tests/slack/test_invite_sms_nudge.py
git commit -m "feat(slack): SMS heads-up after workspace invite"
```

---

### Task 11: Admin pre-lottery review report

**Files:**
- Modify: `app/routes/admin.py` (new route near the other season admin routes)
- Create: `app/templates/admin_registration_review.html`
- Test: `tests/registration/test_admin_review.py` (new)

**Interfaces:**
- Consumes: `UserSeason.needs_review` (Task 2), `admin_required` decorator (`app/auth.py:34`).
- Produces: `GET /admin/registration-review?season_id=N` (admin-gated) rendering two lists: (1) UserSeasons for that season with `needs_review=True`; (2) NEW-type registrations for that season whose registrant's `(lower(first_name), lower(last_name))` or `date_of_birth` matches a different User who has a past ACTIVE season.

- [ ] **Step 1: Write the failing test**

```python
# tests/registration/test_admin_review.py
from datetime import datetime, date, timedelta

import pytest

from app import create_app
from app.models import db, Season, User, UserSeason
from app.constants import UserSeasonStatus

EMAILS = ("rev-flagged@test.com", "rev-dupe-new@test.com", "rev-dupe-old@test.com")


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"
    )
    return app


@pytest.fixture
def client(app):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["user"] = {"email": "admin@tcskiclub.org"}  # match ALLOWED_EMAIL_DOMAIN; check app/auth.py
    return c


@pytest.fixture
def fixtures(app):
    with app.app_context():
        s = Season(name="Rev Test", year=2097, price_cents=15000,
                   start_date=date(2097, 11, 1), end_date=date(2098, 3, 1))
        old = Season(name="Rev Old", year=2087, price_cents=15000,
                     start_date=date(2087, 11, 1), end_date=date(2088, 3, 1))
        flagged = User(email=EMAILS[0], first_name="Flag", last_name="Ged")
        dupe_new = User(email=EMAILS[1], first_name="Dana", last_name="Dupe",
                        date_of_birth=date(1990, 5, 5))
        dupe_old = User(email=EMAILS[2], first_name="Dana", last_name="Dupe",
                        date_of_birth=date(1990, 5, 5))
        db.session.add_all([s, old, flagged, dupe_new, dupe_old])
        db.session.commit()
        db.session.add_all([
            UserSeason(user_id=flagged.id, season_id=s.id,
                       registration_type="new", registration_date=date.today(),
                       status=UserSeasonStatus.PENDING_LOTTERY, needs_review=True),
            UserSeason(user_id=dupe_new.id, season_id=s.id,
                       registration_type="new", registration_date=date.today(),
                       status=UserSeasonStatus.PENDING_LOTTERY),
            UserSeason(user_id=dupe_old.id, season_id=old.id,
                       registration_type="new", registration_date=date(2087, 10, 1),
                       status=UserSeasonStatus.ACTIVE),
        ])
        db.session.commit()
        yield s.id
        UserSeason.query.filter(UserSeason.user_id.in_(
            [flagged.id, dupe_new.id, dupe_old.id])).delete(synchronize_session=False)
        for e in EMAILS:
            db.session.delete(User.query.filter_by(email=e).one())
        db.session.delete(Season.query.get(s.id))
        db.session.delete(Season.query.get(old.id))
        db.session.commit()


def test_review_page_lists_flagged_and_fuzzy_dupes(client, fixtures):
    resp = client.get(f"/admin/registration-review?season_id={fixtures}")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "rev-flagged@test.com" in html      # needs_review list
    assert "rev-dupe-new@test.com" in html     # fuzzy-match list
    assert "rev-dupe-old@test.com" in html     # shown as the possible match
```

(Adjust the admin session shape to whatever `admin_required` at `app/auth.py:34` actually checks — read it first; the domain constant is `ALLOWED_EMAIL_DOMAIN`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/registration/test_admin_review.py -v`
Expected: FAIL with 404

- [ ] **Step 3: Implement**

Route in `app/routes/admin.py` (imports of `UserSeason`, `User`, `Season` already exist there):

```python
@admin.route('/admin/registration-review')
@admin_required
def registration_review():
    season_id = request.args.get('season_id', type=int)
    season = Season.query.get_or_404(season_id)

    flagged = (UserSeason.query
               .filter_by(season_id=season.id, needs_review=True)
               .join(User).order_by(User.last_name).all())

    # New registrations this season whose name or DOB matches a different
    # user who has actually been ACTIVE before — the "returning member who
    # registered as new" trap.
    new_regs = (UserSeason.query
                .filter_by(season_id=season.id, registration_type='new')
                .join(User).all())
    suspects = []
    for us in new_regs:
        u = us.user
        candidates = User.query.filter(
            User.id != u.id,
            db.or_(
                db.and_(db.func.lower(User.first_name) == u.first_name.lower(),
                        db.func.lower(User.last_name) == u.last_name.lower()),
                db.and_(User.date_of_birth != None,
                        User.date_of_birth == u.date_of_birth),
            )).all()
        matches = [c for c in candidates if c.is_returning]
        if matches:
            suspects.append({'registration': us, 'matches': matches})

    return render_template('admin_registration_review.html',
                           season=season, flagged=flagged, suspects=suspects)
```

`app/templates/admin_registration_review.html` (extend the same base template the other admin pages use — check `app/templates/admin*.html` for the block names):

```html
{% extends "admin_base.html" %}
{% block content %}
<h1>Registration review: {{ season.name }}</h1>

<h2>Unverified registrations ({{ flagged|length }})</h2>
<p>These members registered without completing verification. Confirm who they
are before the lottery runs; their payments are holds, nothing is charged yet.</p>
<table>
  <tr><th>Name</th><th>Email</th><th>Phone</th><th>Type</th><th>Date</th></tr>
  {% for us in flagged %}
  <tr>
    <td>{{ us.user.full_name }}</td><td>{{ us.user.email }}</td>
    <td>{{ us.user.phone or "" }}</td><td>{{ us.registration_type }}</td>
    <td>{{ us.registration_date }}</td>
  </tr>
  {% endfor %}
</table>

<h2>Possible returning members registered as new ({{ suspects|length }})</h2>
<p>Each row is a new registration whose name or birth date matches an existing
member with a past active season. If they are the same person, merge before
the lottery so they keep their returning spot.</p>
<table>
  <tr><th>New registration</th><th>Possible match</th></tr>
  {% for s in suspects %}
  <tr>
    <td>{{ s.registration.user.full_name }} ({{ s.registration.user.email }})</td>
    <td>{% for m in s.matches %}{{ m.full_name }} ({{ m.email }}){% if not loop.last %}, {% endif %}{% endfor %}</td>
  </tr>
  {% endfor %}
</table>
{% endblock %}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/registration/test_admin_review.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/routes/admin.py app/templates/admin_registration_review.html tests/registration/test_admin_review.py
git commit -m "feat(admin): pre-lottery registration review report"
```

---

### Task 12: Full-suite run, docs, and dry-run checklist

**Files:**
- Modify: `CLAUDE.md` (short section), `docs/superpowers/specs/2026-08-23-sms-registration-design.md` (status line)

- [ ] **Step 1: Full suite**

Run: `pytest --ignore=tests/events -q` (events failures are pre-existing dev-DB schema drift; see memory/CLAUDE.md)
Expected: everything green outside the known events drift. Fix regressions before proceeding.

- [ ] **Step 2: CLAUDE.md addition**

Add after the "Payment Flow" section:

```markdown
## Phone Verification (season registration)

Member identity for season registration is a verified phone (`User.phone_e164`,
E.164, indexed, deliberately NOT unique — households share numbers). Codes:
Twilio Verify for SMS, `VerificationCode` + Resend for the email fallback.
The verified identity lives in the Flask session (`app/verify/service.py`,
2-hour TTL) and is the ONLY source for returning-vs-new and capture method —
never trust a typed email for pricing. Unverified registrations degrade to
manual capture + `UserSeason.needs_review`; the admin review page
(`/admin/registration-review`) must be checked before running a lottery.
SMS templates live in `config/sms.yaml`; `send_sms()` never raises.
```

- [ ] **Step 3: Live dry run (with Rob)**

With `./scripts/dev.sh 5001` + Stripe CLI, using Rob's cell 612-867-7165:
1. Seed Rob's number on a returning-member test user; full flow: code → prefill → payment status line → test-mode charge → confirmation text arrives.
2. Clear the number from the user; email fallback with a real Resend code to a Rob-controlled inbox.
3. New-member identity with Rob's phone: hold placed, `needs_review` false, lottery text arrives; then trigger `invite_new_members` dry-run=False against a test tier map with the test user to see the Slack-invite nudge text.
4. Failure drills: wrong code x5, resend countdown, rate limit copy (4th send inside 10 min), degraded copy with `TWILIO_VERIFY_SERVICE_SID` temporarily unset.

- [ ] **Step 4: Commit + PR**

```bash
git add CLAUDE.md docs/
git commit -m "docs: phone verification conventions"
git push -u origin sms-registration
gh pr create --title "SMS-first season registration" --body "..."
```

PR body summarizes the spec; merging auto-deploys. Before merge: set the six env vars on Render (`mcp__render__update_environment_variables`).

---

## Self-review notes

- Spec coverage: normalization (T1), schema+backfill (T2), providers (T3), code lifecycle/rate limits/session (T4), endpoints+match logic (T5), SMS templates+opt-out (T6), flow rework+collision guard+degradation+confirmation texts (T7), capture derivation (T8), UI incl. emergency confirm, status line, escape hatches, persistence (T9), Slack nudge (T10), admin review (T11), docs+dry run (T12). Old `/api/is_returning_member` endpoint deliberately retained as the revert path (spec "Rollout").
- Not in any task, confirmed out of spec scope: lottery texts, RCS, trips/events adoption, voice channel, member accounts.
- Type consistency: `send_sms(user, key, **kwargs)` used identically in T6/T7/T10; identity dict keys `phone_e164`/`user_id`/`ts` in T4/T5/T7/T8; `continue_unverified` field in T7/T9.
