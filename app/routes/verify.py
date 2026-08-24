"""JSON endpoints for the registration verification step (step 0)."""
from datetime import datetime

from flask import Blueprint, jsonify, request

from app import late_link
from app.models import db, Season, User
from app.seasons.resolution import resolve_registration_step
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


@verify_api.route('/api/verify/disclaim', methods=['POST'])
def disclaim():
    """The "Not [name]?" action drops the account link, not the phone.

    Without this, clicking "Not [name]?" changes nothing on the server. The
    session keeps pointing at the account the registrant just said they are
    not, and every downstream reader believes it. That matters most at
    /create-season-payment-intent, which receives no disclaim signal of its
    own and would otherwise auto-capture a full charge against a returning
    member's classification for someone who belongs in the new-member
    lottery on a manual hold.

    The phone stays: it really was verified. Only the identity claim goes.
    """
    identity = service.get_verified_identity()
    if not identity:
        return jsonify(ok=False, error='Verify your number first.'), 400
    service.set_verified_identity(identity['phone_e164'], user_id=None)
    return jsonify(ok=True)


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
