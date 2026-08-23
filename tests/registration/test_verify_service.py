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
