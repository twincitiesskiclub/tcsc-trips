from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from app import create_app
from app.models import db, VerificationCode, VerificationAttempt
from app.verify import service
from app.verify.providers import ProviderError

EMAIL = "verify-svc@test.com"
PHONE = "+16125550142"
EMAIL_CASE_VARIANT = "svc-case@test.com"  # Used in normalization test


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
        VerificationCode.query.filter_by(email=EMAIL_CASE_VARIANT).delete()
        VerificationAttempt.query.filter(
            VerificationAttempt.target.in_([EMAIL, PHONE, EMAIL_CASE_VARIANT])).delete(
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
    assert "can't receive texts" in msg.lower()  # points at the reachable escape hatch


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


@patch("app.verify.service.providers.resend_send_code")
def test_email_normalization_closes_rate_limit_bypass(mock_send, ctx):
    """Verify email normalization prevents rate-limit bypass via case/whitespace variants."""
    # Start with mixed-case email with trailing space
    ok1, _ = service.start_email_verification("Svc-Case@Test.COM ", "Rob", ip="1.2.3.4")
    assert ok1

    # Second start with lowercased form should count against same rate limit
    ok2, _ = service.start_email_verification("svc-case@test.com", "Rob", ip="1.2.3.4")
    assert ok2

    # Third start with uppercase form should also count against same rate limit
    ok3, _ = service.start_email_verification("SVC-CASE@TEST.COM", "Rob", ip="1.2.3.4")
    assert ok3
    code_from_last = mock_send.call_args.args[2]

    # Fourth start should hit rate limit (max 3 per 10 min)
    ok4, msg = service.start_email_verification(" svc-case@test.com ", "Rob", ip="1.2.3.4")
    assert not ok4 and "wait" in msg.lower()

    # Verify code from last variant can be checked with normalized email
    assert service.check_email_verification("svc-case@test.com", code_from_last) is True


# --- Lookup pool: blur-time existence checks must not eat the send budget ---

LOOKUP_IP = "10.99.15.1"
LOOKUP_TARGET_PREFIX = "lookup-pool-"


def _lookup_targets(n):
    return [f"{LOOKUP_TARGET_PREFIX}{i}@test.com" for i in range(n)]


@pytest.fixture
def lookup_ctx(app):
    with app.app_context():
        yield
        db.session.rollback()
        VerificationAttempt.query.filter(
            VerificationAttempt.target.like(f"{LOOKUP_TARGET_PREFIX}%@test.com")
        ).delete(synchronize_session=False)
        VerificationAttempt.query.filter(
            VerificationAttempt.target == PHONE).delete(synchronize_session=False)
        db.session.commit()


@patch("app.verify.service.providers.twilio_verify_start")
def test_lookups_do_not_consume_the_send_ip_budget(mock_start, lookup_ctx):
    """Four people behind one router, three lookups each, must still be
    able to get an SMS code from that router."""
    for target in _lookup_targets(service.RATE_IP_MAX):
        assert service.lookup_rate_limit_ok(target, LOOKUP_IP)
        service._record_attempt(target, 'lookup', LOOKUP_IP)
    ok, msg = service.start_phone_verification(PHONE, ip=LOOKUP_IP)
    assert ok, msg
    assert mock_start.called


def test_lookup_ip_ceiling_refuses_the_thirty_first(lookup_ctx):
    targets = _lookup_targets(service.RATE_LOOKUP_IP_MAX + 1)
    for target in targets[:-1]:
        assert service.lookup_rate_limit_ok(target, LOOKUP_IP)
        service._record_attempt(target, 'lookup', LOOKUP_IP)
    assert service.lookup_rate_limit_ok(targets[-1], LOOKUP_IP) is False


def test_lookup_keeps_the_per_target_ceiling(lookup_ctx):
    target = _lookup_targets(1)[0]
    for _ in range(service.RATE_TARGET_MAX):
        assert service.lookup_rate_limit_ok(target, LOOKUP_IP)
        service._record_attempt(target, 'lookup', LOOKUP_IP)
    assert service.lookup_rate_limit_ok(target, LOOKUP_IP) is False


def test_send_ip_ceiling_is_unchanged_and_separate_from_lookups(lookup_ctx):
    targets = _lookup_targets(service.RATE_IP_MAX + 1)
    for target in targets[:-1]:
        assert service.rate_limit_ok(target, LOOKUP_IP)
        service._record_attempt(target, 'sms', LOOKUP_IP)
    # 11th send from this IP is refused ...
    assert service.rate_limit_ok(targets[-1], LOOKUP_IP) is False
    # ... while a lookup from the same IP is still fine: separate pool.
    assert service.lookup_rate_limit_ok(targets[-1], LOOKUP_IP) is True
