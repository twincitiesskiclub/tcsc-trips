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
