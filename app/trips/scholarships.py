"""Trip scholarships: one-time per-member discount codes sent by Slack DM."""
import secrets
from datetime import datetime

from app.trips.models import TripRegistrationStatus
from app.trips.service import PENDING_HOLD_WINDOW

CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O/1/I/L
CODE_LENGTH = 6


def generate_code():
    suffix = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
    return f"TCSC-{suffix}"


def _is_active(registration, now):
    if registration.status in (TripRegistrationStatus.PENDING,
                               TripRegistrationStatus.CONFIRMED):
        return True
    return (registration.status == TripRegistrationStatus.PENDING_PAYMENT
            and registration.created_at >= now - PENDING_HOLD_WINDOW)


def active_registration(scholarship, now=None):
    """The registration holding or using this scholarship, confirmed first."""
    now = now or datetime.utcnow()
    active = [r for r in scholarship.registrations if _is_active(r, now)]
    active.sort(key=lambda r: r.status != TripRegistrationStatus.CONFIRMED)
    return active[0] if active else None


def scholarship_state(scholarship, now=None):
    registration = active_registration(scholarship, now)
    if registration is None:
        return "available"
    if registration.status == TripRegistrationStatus.CONFIRMED:
        return "used"
    return "held"


MISMATCH_ERROR = "That code doesn't match this member."
MINIMUM_CHARGE_CENTS = 50  # Stripe's smallest USD charge


def resolve_code(user, trip, raw_code):
    """Return (scholarship, None), (None, error), or (None, None) if blank."""
    from app.trips.models import TripScholarship
    code = (raw_code or "").strip().upper() if isinstance(raw_code, str) else ""
    if not code:
        return None, None
    scholarship = TripScholarship.query.filter_by(code=code).first()
    if scholarship is None or scholarship.user_id != user.id:
        return None, MISMATCH_ERROR
    holder = active_registration(scholarship)
    if holder is not None and holder.trip_id != trip.id:
        return None, f"This code is already in use on {holder.trip.name}."
    return scholarship, None


def discounted_amount(price_cents, scholarship):
    return max(price_cents - scholarship.amount_cents, MINIMUM_CHARGE_CENTS)
