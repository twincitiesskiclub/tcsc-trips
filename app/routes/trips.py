from datetime import datetime

import stripe
from flask import Blueprint, render_template, request

from ..constants import PaymentType
from ..errors import json_error
from ..models import Trip
from ..trips import service
from ..trips.models import TripSeries
from ..trips.questions import enabled_questions
from ..utils import format_datetime_central, normalize_email
from .payments import build_statement_descriptor, stripe_idempotency_options

trips = Blueprint('trips', __name__)


def _resolve_series(slug):
    """Public trip URLs are SERIES slugs; legacy edition slugs still resolve
    via their parent series so old links keep working."""
    series = TripSeries.query.filter_by(slug=slug).first()
    if series is None:
        edition = Trip.query.filter_by(slug=slug).first()
        series = edition.series if edition else None
    return series


def _registration_state(trip):
    now = datetime.utcnow()
    if trip.status == 'active' and trip.signup_start <= now <= trip.signup_end:
        return True, None
    if trip.status != 'active':
        return False, 'Trip registration is not currently open.'
    if now < trip.signup_start:
        opens_at = format_datetime_central(trip.signup_start)
        return False, f'Trip registration opens {opens_at}.'
    return False, 'Trip registration has closed.'


@trips.route('/<slug>')
def get_trip_page(slug):
    series = _resolve_series(slug)
    trip = series.current_edition() if series else None
    if trip is None:
        from flask import abort
        abort(404)
    registration_open, registration_message = _registration_state(trip)
    return render_template(
        f'trips/{series.slug}.html',
        trip=trip,
        series=series,
        registration_open=registration_open,
        registration_message=registration_message,
    )


@trips.route('/<slug>/register')
def get_trip_register_page(slug):
    series = _resolve_series(slug)
    trip = series.current_edition() if series else None
    if trip is None:
        from flask import abort
        abort(404)
    service.expire_stale_pending(trip)
    registration_open, registration_message = _registration_state(trip)
    registration_data = {
        'slug': series.slug,
        'priceLow': trip.price_low,
        'priceHigh': trip.price_high,
        'customQuestions': trip.custom_questions or [],
    }
    return render_template(
        'trips/register.html',
        trip=trip,
        series=series,
        registration_open=registration_open,
        registration_message=registration_message,
        registration_data=registration_data,
        questions=enabled_questions(trip.custom_questions),
    )


@trips.route('/api/trips/member-check', methods=['POST'])
def member_check():
    data = request.get_json(silent=True) or {}
    email = normalize_email(data.get('email', ''))
    return {'eligible': service.lookup_active_member(email) is not None}


@trips.route('/<slug>/register', methods=['POST'])
def register_for_trip(slug):
    series = _resolve_series(slug)
    trip = series.current_edition() if series else None
    if trip is None:
        return json_error('Trip not found', 404)
    payload = request.get_json(silent=True) or {}
    try:
        registration = service.create_registration(trip, payload)
    except service.TripRegistrationError as exc:
        return json_error(exc.errors)

    try:
        intent = stripe.PaymentIntent.create(
            amount=registration.amount_cents,
            currency='usd',
            capture_method='manual',  # Always manual for trips (lottery system)
            receipt_email=registration.user.email,
            statement_descriptor=build_statement_descriptor('TRIP', trip.name),
            description=f"TCSC Trip - {trip.name}",
            metadata={
                'payment_type': PaymentType.TRIP,
                'trip_id': str(trip.id),
                'trip_slug': series.slug,
                'registration_id': str(registration.id),
                'price_tier': registration.price_tier,
                'email': registration.user.email,
                'name': registration.user.full_name,
            },
            **stripe_idempotency_options(),
        )
    except Exception as exc:
        # Row stays PENDING_PAYMENT; the 1h capacity window and 24h sweep
        # (service.py) handle abandonment - mirrors events.
        return json_error(str(exc), 500)

    from ..models import db
    registration.payment_intent_id = intent.id
    db.session.commit()
    return {
        'clientSecret': intent.client_secret,
        'registrationId': registration.id,
        'amountCents': registration.amount_cents,
    }
