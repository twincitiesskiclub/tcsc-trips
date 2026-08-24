"""Verification policy: code lifecycle, rate limits, session identity.

Phone codes live in Twilio Verify; email codes live in VerificationCode.
All user-facing error strings originate here so copy stays in one place.
"""
import hashlib
import secrets
from datetime import datetime, timedelta

from flask import current_app, session

from app.models import db, VerificationCode, VerificationAttempt
from app.utils import normalize_email
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
                "us, not you. Use the \"Can't receive texts?\" link below "
                "to continue.")
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
    email = normalize_email(email)
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
    email = normalize_email(email)
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


def set_verified_identity(phone_e164, user_id=None, disclaimed_user_id=None):
    session['verified_identity'] = {
        'phone_e164': phone_e164,
        'user_id': user_id,
        'disclaimed_user_id': disclaimed_user_id,
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
