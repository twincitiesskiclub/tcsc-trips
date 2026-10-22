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


def issue_scholarships(user_ids, amount_cents):
    """Create and DM one scholarship per member; one result dict per id."""
    from sqlalchemy.exc import IntegrityError

    from app.constants import UserStatus
    from app.models import Season, User

    season = Season.get_current()
    if season is None:
        raise ValueError("No current season.")
    results = []
    for user_id in user_ids:
        user = db.session.get(User, user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            results.append({"user_id": user_id,
                            "name": user.full_name if user else "",
                            "status": "not_active"})
            continue
        result = {"user_id": user.id, "name": user.full_name}
        if TripScholarship.query.filter_by(
                user_id=user.id, season_id=season.id).first():
            results.append(dict(result, status="already_has_one"))
            continue
        scholarship = None
        for _ in range(5):  # a code collision is the only expected failure
            try:
                with db.session.begin_nested():
                    scholarship = TripScholarship(
                        user_id=user.id, season_id=season.id,
                        amount_cents=amount_cents, code=generate_code())
                    db.session.add(scholarship)
                break
            except IntegrityError:
                scholarship = None
        if scholarship is None:
            results.append(dict(result, status="send_failed"))
            continue
        db.session.commit()
        if _slack_uid(user) is None:
            status = "no_slack"
        elif send_scholarship_dm(scholarship):
            status = "sent"
        else:
            status = "send_failed"
        results.append(dict(result, status=status))
    return results


def scholarship_rows(season):
    from app.models import User
    from app.utils import format_datetime_central

    def when(dt):
        return format_datetime_central(dt, "%b %-d, %-I:%M %p") if dt else ""

    rows = []
    scholarships = TripScholarship.query.join(User).filter(
        TripScholarship.season_id == season.id).all()
    now = datetime.utcnow()
    for scholarship in scholarships:
        registration = active_registration(scholarship, now)
        rows.append({
            "id": scholarship.id,
            "name": scholarship.user.full_name,
            "email": scholarship.user.email,
            "code": scholarship.code,
            "amount_cents": scholarship.amount_cents,
            "sent_at": when(scholarship.sent_at),
            "claimed_at": when(scholarship.claimed_at),
            "state": scholarship_state(scholarship, now),
            "trip_name": registration.trip.name if registration else "",
        })
    rows.sort(key=lambda row: row["name"].lower())
    return rows


def link_registrations(registration_ids, dry_run=True):
    """Attach existing registrations to their members' scholarships.

    For members who registered before their DM arrived. The amount is left
    alone so the row keeps matching its Stripe hold; the $ comes back as a
    refund after capture.
    """
    from app.models import Season
    from app.trips.models import TripRegistration

    season = Season.get_current()
    lines = []
    for registration_id in registration_ids:
        registration = db.session.get(TripRegistration, registration_id)
        if registration is None:
            lines.append(f"{registration_id}: refused, no such registration")
            continue
        label = (f"{registration_id} {registration.user.full_name} "
                 f"({registration.trip.name})")
        scholarship = season and TripScholarship.query.filter_by(
            user_id=registration.user_id, season_id=season.id).first()
        if not scholarship:
            lines.append(f"{label}: refused, member has no scholarship")
            continue
        holder = active_registration(scholarship)
        if holder is not None and holder.id != registration.id:
            lines.append(
                f"{label}: refused, code already in use on {holder.trip.name}")
            continue
        if dry_run:
            lines.append(f"{label}: would link {scholarship.code}")
            continue
        registration.scholarship_id = scholarship.id
        db.session.commit()
        lines.append(f"{label}: linked {scholarship.code}")
    return lines
