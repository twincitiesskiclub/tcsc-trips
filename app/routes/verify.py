"""JSON endpoints for the registration verification step (step 0)."""
from datetime import datetime

from flask import Blueprint, jsonify, request

from app.models import db, User
from app.utils import normalize_email, normalize_phone_e164, format_phone_display
from app.verify import service

verify_api = Blueprint('verify_api', __name__)


def _client_ip():
    return request.headers.get('X-Forwarded-For', '').split(',')[-1].strip() or request.remote_addr or '?'


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
    ip = _client_ip()
    if not service.rate_limit_ok(email, ip):
        return jsonify(ok=False, error=service.RATE_LIMIT_MSG)
    user = User.get_by_email(email)
    if not user:
        # Record this probe so an unlimited stream of misses against
        # different emails still gets capped by the per-IP rate limit.
        # start_email_verification does its own record on the hit path,
        # so exactly one attempt is recorded per request either way.
        service._record_attempt(email, 'email', ip)
        return jsonify(ok=True, exists=False)
    ok, error = service.start_email_verification(
        email, user.first_name, ip=ip)
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
