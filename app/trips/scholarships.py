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
