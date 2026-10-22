"""Trip scholarships: one-time per-member discount codes sent by Slack DM."""
import secrets
from datetime import datetime

from flask import current_app

from app.models import db, Trip
from app.slack.blocks.trips import (
    build_scholarship_offer_blocks, build_scholarship_revealed_blocks,
    scholarship_offer_fallback, scholarship_revealed_fallback,
)
from app.slack.client import get_slack_client
from app.trips.models import TripRegistrationStatus, TripScholarship
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


def _slack_uid(user):
    if user and user.slack_user and user.slack_user.slack_uid:
        return user.slack_user.slack_uid
    return None


def open_trips(now=None):
    """Trips taking registrations right now, soonest close first."""
    now = now or datetime.utcnow()
    trips = Trip.query.filter(
        Trip.status == "active", Trip.series_id.isnot(None),
        Trip.signup_start <= now, Trip.signup_end >= now,
    ).order_by(Trip.signup_end).all()
    return trips


def send_scholarship_dm(scholarship):
    """Post the offer DM and remember it. Never raises."""
    slack_uid = _slack_uid(scholarship.user)
    if not slack_uid:
        current_app.logger.info(
            "trip scholarship: no linked SlackUser for scholarship %s",
            scholarship.id)
        return False
    try:
        response = get_slack_client().chat_postMessage(
            channel=slack_uid,
            blocks=build_scholarship_offer_blocks(scholarship),
            text=scholarship_offer_fallback(scholarship))
        scholarship.slack_channel_id = response["channel"]
        scholarship.slack_message_ts = response["ts"]
        scholarship.sent_at = datetime.utcnow()
        db.session.commit()
        return True
    except Exception as exc:
        db.session.rollback()
        current_app.logger.warning(
            "trip scholarship: DM failed for scholarship %s: %s",
            scholarship.id, exc)
        return False


def reveal(scholarship_id, slack_uid, now=None):
    """Blocks showing the code to its member, or None for anyone else."""
    from app.slack.trips import base_url
    scholarship = db.session.get(TripScholarship, scholarship_id)
    if scholarship is None or _slack_uid(scholarship.user) != slack_uid:
        return None
    now = now or datetime.utcnow()
    if scholarship.claimed_at is None:
        scholarship.claimed_at = now
        db.session.commit()
    return build_scholarship_revealed_blocks(
        scholarship, active_registration(scholarship, now), open_trips(now),
        base_url())


def handle_reveal_click(body, action, client):
    """The "Get my code" button: swap the offer for the code in place."""
    try:
        scholarship_id = int(action["value"])
        blocks = reveal(scholarship_id, body["user"]["id"])
        if blocks is None:
            current_app.logger.warning(
                "trip scholarship: %s clicked scholarship %s they don't own",
                body["user"]["id"], scholarship_id)
            return False
        scholarship = db.session.get(TripScholarship, scholarship_id)
        client.chat_update(
            channel=body["channel"]["id"], ts=body["message"]["ts"],
            blocks=blocks, text=scholarship_revealed_fallback(scholarship))
        return True
    except Exception as exc:
        current_app.logger.warning(
            "trip scholarship: reveal failed: %s", exc)
        return False
