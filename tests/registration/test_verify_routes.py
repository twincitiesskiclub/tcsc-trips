from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest

from app import create_app
from app.constants import UserStatus
from app.models import db, Season, User, VerificationAttempt
from app.verify.service import RATE_LIMIT_MSG

PHONE_RAW = "612-555-0177"
PHONE = "+16125550177"
EMAIL = "verify-routes@test.com"
PROBE_EMAIL = "verify-routes-probe@test.com"


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


@patch("app.routes.verify.service.check_phone_verification", return_value=True)
def test_email_start_rate_limits_miss_probing(mock_check, client, app):
    # A verified-phone session with no matching user still needs to
    # establish an identity before hitting email/start.
    client.post("/api/verify/phone/check",
                json={"phone": "612-555-0166", "code": "123456"})
    try:
        for _ in range(3):
            resp = client.post("/api/verify/email/start",
                               json={"email": PROBE_EMAIL})
            assert resp.get_json() == {"ok": True, "exists": False}
        # 4th probe against the same target within the window is throttled.
        resp = client.post("/api/verify/email/start",
                           json={"email": PROBE_EMAIL})
        body = resp.get_json()
        assert body == {"ok": False, "error": RATE_LIMIT_MSG}
    finally:
        with app.app_context():
            db.session.rollback()
            VerificationAttempt.query.filter_by(target=PROBE_EMAIL).delete()
            db.session.commit()


def test_client_ip_uses_last_xff_entry(app):
    from app.routes.verify import _client_ip
    with app.test_request_context(headers={"X-Forwarded-For": "fake, real"}):
        assert _client_ip() == "real"
    with app.test_request_context(environ_overrides={"REMOTE_ADDR": "9.9.9.9"}):
        # No header at all falls back to the connecting address.
        assert _client_ip() == "9.9.9.9"


def test_resolve_without_identity_asks_for_phone(client, season):
    resp = client.get(f'/api/verify/resolve?season_id={season}')
    assert resp.status_code == 200
    assert resp.get_json()['outcome'] == 'verify_phone'


def test_resolve_not_yet_open_labels_utc_timestamp(client, season):
    registration_season = Season.query.get(season)
    registration_season.new_start = datetime.utcnow() + timedelta(days=4)
    registration_season.new_end = datetime.utcnow() + timedelta(days=40)
    db.session.commit()
    with client.session_transaction() as sess:
        sess['verified_identity'] = {
            'phone_e164': '+16125550378', 'user_id': None,
            'ts': datetime.utcnow().isoformat()}

    body = client.get(f'/api/verify/resolve?season_id={season}').get_json()

    assert body['outcome'] == 'window_not_yet_open'
    assert body['context']['opens_at'].endswith('+00:00')


def test_resolve_unknown_season_404s(client):
    assert client.get('/api/verify/resolve?season_id=99999999').status_code == 404


def test_disclaim_drops_the_account_but_keeps_the_phone(client, season):
    """The payment route has no disclaim signal of its own; this is it."""
    with client.session_transaction() as sess:
        sess['verified_identity'] = {
            'phone_e164': '+16125550377', 'user_id': 4242,
            'ts': datetime.utcnow().isoformat()}
    assert client.post('/api/verify/disclaim').get_json() == {'ok': True}
    with client.session_transaction() as sess:
        ident = sess['verified_identity']
    assert ident['user_id'] is None
    assert ident['phone_e164'] == '+16125550377'
    assert ident['disclaimed_user_id'] == 4242


def test_disclaim_keeps_the_marker_across_a_second_click(client):
    with client.session_transaction() as sess:
        sess['verified_identity'] = {
            'phone_e164': '+16125550377', 'user_id': 4242,
            'ts': datetime.utcnow().isoformat()}

    assert client.post('/api/verify/disclaim').get_json() == {'ok': True}
    assert client.post('/api/verify/disclaim').get_json() == {'ok': True}

    with client.session_transaction() as sess:
        ident = sess['verified_identity']
    assert ident['disclaimed_user_id'] == 4242
    assert ident['user_id'] is None


@patch("app.routes.verify.service.check_phone_verification", return_value=True)
def test_phone_check_clears_disclaimed_identity(mock_check, client):
    with client.session_transaction() as sess:
        sess['verified_identity'] = {
            'phone_e164': '+16125550377', 'user_id': None,
            'disclaimed_user_id': 4242,
            'ts': datetime.utcnow().isoformat()}

    response = client.post('/api/verify/phone/check', json={
        'phone': '612-555-0199', 'code': '123456'})

    assert response.get_json()['match'] == 'none'
    with client.session_transaction() as sess:
        ident = sess['verified_identity']
    assert ident['disclaimed_user_id'] is None


def test_disclaim_without_an_identity_is_refused(client):
    resp = client.post('/api/verify/disclaim')
    assert resp.status_code == 400
    assert resp.get_json()['ok'] is False


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
    try:
        with app.app_context():
            VerificationAttempt.query.filter(
                VerificationAttempt.ip == '127.0.0.1',
                VerificationAttempt.target.like('probe%'),
            ).delete(synchronize_session=False)
            db.session.commit()
        seen_limit = False
        for i in range(15):
            body = client.post('/api/verify/email/lookup',
                               json={'email': f'probe{i}@test.com'}).get_json()
            if body['ok'] is False:
                seen_limit = True
                break
        assert seen_limit, "lookup never rate-limited across 15 distinct probes"
    finally:
        with app.app_context():
            db.session.rollback()
            VerificationAttempt.query.filter(
                VerificationAttempt.target.like('probe%@test.com'),
                VerificationAttempt.channel == 'email',
            ).delete(synchronize_session=False)
            db.session.commit()
