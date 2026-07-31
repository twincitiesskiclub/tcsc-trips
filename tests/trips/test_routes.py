from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.constants import UserStatus
from app.models import db, Trip, User
from app.trips.models import TripRegistration, TripRegistrationStatus, TripSeries


QUESTIONS = [
    {"key": "chore_preference", "label": "Which task?", "type": "choice",
     "options": ["Cooking", "Cleaning"], "required": True},
]


@pytest.fixture
def public_trip(db_session):
    series = TripSeries(slug="test-trip-routes", name="TEST Trip",
                        destination="Testville")
    db.session.add(series)
    db.session.flush()
    trip = Trip(
        slug="test-trip-routes-2027", name="TEST Trip 2027",
        destination="Testville", series_id=series.id,
        max_participants_standard=20, max_participants_extra=5,
        start_date=datetime(2099, 1, 10), end_date=datetime(2099, 1, 12),
        signup_start=datetime.utcnow() - timedelta(days=1),
        signup_end=datetime.utcnow() + timedelta(days=30),
        price_low=10000, price_high=15000, status="active",
        custom_questions=QUESTIONS,
    )
    user = User(first_name="Test", last_name="Member",
                email="trip-member@example.com", status=UserStatus.ACTIVE)
    db.session.add_all([trip, user])
    db.session.commit()
    return series, trip, user


def _intent(intent_id="pi_trip_test", amount=10000):
    return SimpleNamespace(id=intent_id, client_secret=f"cs_{intent_id}",
                           amount=amount, status="requires_payment_method")


def _payload():
    return {
        "email": "trip-member@example.com", "price_tier": "low",
        "profile": {"can_drive": "no", "seat_capacity": "",
                    "bike_capacity": "", "hitch_size": "",
                    "region_code": "4", "dietary_restrictions": [],
                    "dietary_other": "", "has_tent": ""},
        "answers": {"chore_preference": "Cooking"},
    }


def test_series_slug_resolves_to_current_edition(client, public_trip):
    series, trip, _ = public_trip
    response = client.get("/test-trip-routes/register")
    assert response.status_code == 200
    assert b"TEST Trip 2027" in response.data


def test_member_check_eligible_and_not(client, public_trip):
    ok = client.post("/api/trips/member-check",
                     json={"email": "Trip-Member@Example.com "})
    assert ok.get_json() == {"eligible": True}
    miss = client.post("/api/trips/member-check",
                       json={"email": "nobody@example.com"})
    assert miss.get_json() == {"eligible": False}


@patch("app.routes.trips.stripe.PaymentIntent.create")
def test_register_creates_pending_row_and_manual_capture_intent(
        create_intent, client, db_session, public_trip):
    series, trip, user = public_trip
    create_intent.return_value = _intent()
    response = client.post("/test-trip-routes/register", json=_payload(),
                           headers={"Idempotency-Key": "trip-attempt-1"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["clientSecret"] == "cs_pi_trip_test"
    kwargs = create_intent.call_args.kwargs
    assert kwargs["capture_method"] == "manual"
    assert kwargs["metadata"]["payment_type"] == "trip"
    assert kwargs["metadata"]["registration_id"] == str(body["registrationId"])
    assert kwargs["metadata"]["trip_id"] == str(trip.id)
    registration = db_session.session.get(
        TripRegistration, body["registrationId"])
    assert registration.status == TripRegistrationStatus.PENDING_PAYMENT
    assert registration.payment_intent_id == "pi_trip_test"


@patch("app.routes.trips.stripe.PaymentIntent.create")
def test_stripe_failure_leaves_registration_pending(
        create_intent, client, db_session, public_trip):
    create_intent.side_effect = RuntimeError("Stripe is unavailable")
    response = client.post("/test-trip-routes/register", json=_payload())
    assert response.status_code == 500
    registration = TripRegistration.query.order_by(
        TripRegistration.id.desc()).first()
    assert registration.status == TripRegistrationStatus.PENDING_PAYMENT
    assert registration.payment_intent_id is None


def test_register_validation_error_returns_field_errors(
        client, public_trip):
    payload = _payload()
    payload["answers"] = {}
    response = client.post("/test-trip-routes/register", json=payload)
    assert response.status_code == 400
    assert "answers.chore_preference" in response.get_json()["error"]


def test_register_page_renders_questions_and_gate(client, public_trip):
    response = client.get("/test-trip-routes/register")
    html = response.get_data(as_text=True)
    assert "css/tailwind-output.css" in html
    assert "1.</span> Member check" in html
    assert "member-email" in html
    assert "Which task?" in html
    assert "trip-registration-data" in html


def test_trip_page_links_to_register_flow(client, public_trip):
    response = client.get("/test-trip-routes")
    html = response.get_data(as_text=True)
    assert "/test-trip-routes/register" in html
    assert "sr-payment-form" not in html
