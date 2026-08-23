from datetime import date
from unittest.mock import patch

import pytest

from app import create_app
from app.models import db, User, VerificationAttempt
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
