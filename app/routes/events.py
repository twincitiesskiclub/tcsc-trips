"""Public pages and registration checkout for generic events."""

from datetime import datetime, timedelta

from flask import Blueprint, abort, jsonify, render_template, request, session
import stripe

from ..auth import is_allowed_domain
from ..constants import PaymentType
from ..errors import json_error
from ..events.models import Event, EventStatus, RegistrationStatus
from ..events.service import (
    RegistrationError,
    capacity_available,
    compute_price,
    create_registration,
    discount_code_matches,
    expire_stale_pending,
)
from ..models import db
from .payments import build_statement_descriptor, stripe_idempotency_options


events = Blueprint("events", __name__)

# The discount check answers "is this a real code?", so throttle guessing.
# Keyed by client rather than session because a signed-cookie counter is
# bypassed by discarding the cookie. Per-process, so the effective ceiling is
# this limit times the gunicorn worker count.
DISCOUNT_ATTEMPT_LIMIT = 10
DISCOUNT_ATTEMPT_WINDOW = timedelta(minutes=15)
_discount_attempts: dict[str, list[datetime]] = {}


def _is_admin_session():
    user = session.get("user", {})
    return is_allowed_domain(user.get("email"))


def _discount_attempts_exhausted(event_id):
    """Record this check and report whether the client is over the limit."""
    now = datetime.utcnow()
    cutoff = now - DISCOUNT_ATTEMPT_WINDOW
    for key, stamps in list(_discount_attempts.items()):
        fresh = [stamp for stamp in stamps if stamp > cutoff]
        if fresh:
            _discount_attempts[key] = fresh
        else:
            del _discount_attempts[key]

    key = f"{request.remote_addr}:{event_id}"
    attempts = _discount_attempts.setdefault(key, [])
    attempts.append(now)
    return len(attempts) > DISCOUNT_ATTEMPT_LIMIT


def _event_registration_data(event, price_options):
    return {
        "slug": event.slug,
        "priceOptions": [
            {
                "id": option.id,
                "name": option.name,
                "description": option.description or "",
                "priceCents": option.price_cents,
                "participantRoles": (
                    option.participant_roles or ["Participant"]
                ),
            }
            for option in price_options
        ],
        "customQuestions": event.custom_questions or [],
    }


@events.get("/events/<slug>")
def get_event_page(slug):
    """Render an active event or an authenticated draft preview."""
    event = Event.query.filter_by(slug=slug).first_or_404()
    draft_preview = (
        event.status == EventStatus.DRAFT and _is_admin_session()
    )
    if event.status != EventStatus.ACTIVE and not draft_preview:
        abort(404)

    expire_stale_pending(event)
    price_options = [option for option in event.price_options if option.active]
    now = datetime.utcnow()
    has_capacity = capacity_available(event)
    registration_open = (
        event.signup_start <= now <= event.signup_end
        and has_capacity
        and bool(price_options)
    )

    registration_message = None
    if not price_options:
        registration_message = "Registration options are not available yet."
    elif now < event.signup_start:
        registration_message = "Registration has not opened yet."
    elif now > event.signup_end:
        registration_message = "Registration is closed."
    elif not has_capacity:
        registration_message = "This event is sold out."

    return render_template(
        "events/registration.html",
        event=event,
        price_options=price_options,
        draft_preview=draft_preview,
        registration_open=registration_open,
        registration_message=registration_message,
        registration_data=_event_registration_data(event, price_options),
    )


@events.post("/events/<slug>/discount")
def check_event_discount(slug):
    """Report the prices a code unlocks without ever publishing the code."""
    event = Event.query.filter_by(slug=slug).first_or_404()
    draft_preview = (
        event.status == EventStatus.DRAFT and _is_admin_session()
    )
    if event.status != EventStatus.ACTIVE and not draft_preview:
        abort(404)

    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return json_error({"code": "Request body must be a JSON object."})

    code = payload.get("code")
    if not isinstance(code, str):
        code = ""

    if _discount_attempts_exhausted(event.id) or not discount_code_matches(
        event,
        code,
    ):
        return jsonify({"valid": False})

    return jsonify(
        {
            "valid": True,
            "options": [
                {
                    "id": option.id,
                    "priceCents": compute_price(option, event, code)[0],
                }
                for option in event.price_options
                if option.active
            ],
        }
    )


@events.post("/events/<slug>/register")
def register_for_event(slug):
    """Validate an event registration and start its payment, if needed."""
    event = Event.query.filter_by(slug=slug).first_or_404()
    allow_draft = (
        event.status == EventStatus.DRAFT and _is_admin_session()
    )
    if event.status == EventStatus.DRAFT and not allow_draft:
        abort(404)

    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return json_error(
            {"registration": "Request body must be a JSON object."}
        )
    try:
        registration = create_registration(
            event,
            payload,
            allow_draft=allow_draft,
        )
    except RegistrationError as exc:
        return json_error(exc.errors)

    if registration.amount_cents == 0:
        registration.status = RegistrationStatus.CONFIRMED
        db.session.commit()
        return jsonify(
            {
                "free": True,
                "registrationId": registration.id,
            }
        )

    first_participant_name = registration.participants[0].name
    try:
        intent = stripe.PaymentIntent.create(
            amount=registration.amount_cents,
            currency="usd",
            capture_method="automatic",
            receipt_email=registration.contact_email,
            statement_descriptor=build_statement_descriptor(
                "EVENT",
                event.name,
            ),
            description=f"TCSC Event - {event.name}",
            metadata={
                "payment_type": PaymentType.EVENT,
                "event_id": str(event.id),
                "registration_id": str(registration.id),
                "email": registration.contact_email,
                "name": first_participant_name,
            },
            **stripe_idempotency_options(),
        )
    except Exception as exc:
        return json_error(str(exc), 500)

    registration.payment_intent_id = intent.id
    db.session.commit()
    return jsonify(
        {
            "clientSecret": intent.client_secret,
            "registrationId": registration.id,
            "amountCents": registration.amount_cents,
        }
    )
