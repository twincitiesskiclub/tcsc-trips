from datetime import datetime, timedelta
from copy import deepcopy
import re
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.constants import UserStatus
from app.models import db, Trip, User
from app.trips.questions import default_builtin_questions
from app.trips.models import TripProfile, TripRegistration, TripRegistrationStatus, TripSeries
from app.trips.questions import DIETARY_OTHER


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
        custom_questions=default_builtin_questions() + QUESTIONS,
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
    assert "css/styles/main.css" in html
    assert 'id="gate-section"' in html
    assert "Member check" in html
    assert "TEST Trip 2027 registration | Twin Cities Ski Club" in html
    assert "member-email" in html
    assert "Which task?" in html
    assert "trip-registration-data" in html


def test_trip_page_links_to_register_flow(client, public_trip):
    response = client.get("/test-trip-routes")
    html = response.get_data(as_text=True)
    assert "/test-trip-routes/register" in html
    assert "sr-payment-form" not in html


def test_trip_page_renders_closed_registration_notice(client, db_session):
    now = datetime.utcnow()
    series = TripSeries(slug="test-trip-routes", name="TEST Trip",
                        destination="Testville")
    db.session.add(series)
    db.session.flush()
    trip = Trip(
        slug="test-trip-routes-2027", name="TEST Trip 2027",
        destination="Testville", series_id=series.id,
        max_participants_standard=20, max_participants_extra=5,
        start_date=now + timedelta(days=30),
        end_date=now + timedelta(days=32),
        signup_start=now - timedelta(days=30),
        signup_end=now - timedelta(days=1),
        price_low=10000, price_high=15000, status="active",
        custom_questions=default_builtin_questions() + QUESTIONS,
    )
    db.session.add(trip)
    db.session.commit()

    response = client.get("/test-trip-routes")
    html = response.get_data(as_text=True)
    assert "Trip registration has closed." in html
    assert 'class="notice notice--info"' in html
    assert 'role="status"' in html


PROFILE_FIELDS = {
    "carpool": ("can_drive", "seat_capacity", "bike_capacity", "hitch_size"),
    "region_code": ("region_code",),
    "dietary": ("dietary_restrictions", "dietary_other"),
    "tent": ("has_tent",),
}


@pytest.mark.parametrize("asked", [None, *PROFILE_FIELDS])
@pytest.mark.parametrize("existing", [False, True])
@patch("app.routes.trips.stripe.PaymentIntent.create")
def test_post_only_writes_enabled_profile_columns(
        create_intent, client, public_trip, asked, existing):
    _, trip, user = public_trip
    previous = dict(can_drive=True, seat_capacity=7, bike_capacity=4, hitch_size="2",
                    region_code="9", dietary_restrictions=["Vegan"],
                    dietary_other="Previous needs", has_tent=True)
    if existing:
        db.session.add(TripProfile(user_id=user.id, **previous))
    trip.custom_questions = [q | {"enabled": q["builtin"] == asked}
                             for q in default_builtin_questions()] + QUESTIONS
    db.session.commit()
    payload = _payload()
    # Disabled fields are ignored even when a stale or tampered client sends them.
    for builtin, fields in PROFILE_FIELDS.items():
        if builtin != asked:
            payload["profile"].update({field: {"invalid": True} for field in fields})
    create_intent.return_value = _intent()
    response = client.post("/test-trip-routes/register", json=payload)
    assert response.status_code == 200, response.get_json()
    db.session.expire_all()
    expected = dict(can_drive=False, seat_capacity=None, bike_capacity=None, hitch_size="",
                    region_code="4", dietary_restrictions=[], dietary_other="", has_tent=None)
    for builtin, fields in PROFILE_FIELDS.items():
        for field in fields:
            if builtin == asked:
                value = expected[field]
            elif existing:
                value = previous[field]
            else:
                value = {"dietary_restrictions": [], "dietary_other": ""}.get(field)
            assert getattr(user.trip_profile, field) == value, field
    registration = db.session.get(TripRegistration, response.get_json()["registrationId"])
    assert registration.answers == {"chore_preference": "Cooking"}


@patch("app.routes.trips.stripe.PaymentIntent.create")
def test_optional_region_accepts_blank(create_intent, client, public_trip):
    _, trip, user = public_trip
    trip.custom_questions = [q | {"required": False} if q.get("builtin") == "region_code" else q
                             for q in trip.custom_questions]
    db.session.commit()
    create_intent.return_value = _intent()
    payload = _payload()
    payload["profile"]["region_code"] = " "
    response = client.post("/test-trip-routes/register", json=payload)
    assert response.status_code == 200
    assert user.trip_profile.region_code == ""


@patch("app.routes.trips.stripe.PaymentIntent.create")
def test_required_dietary_and_trip_specific_options(create_intent, client, public_trip):
    _, trip, user = public_trip
    trip.custom_questions = [q | {"required": True, "options": ["Sesame allergy", DIETARY_OTHER]}
                             if q.get("builtin") == "dietary" else q for q in trip.custom_questions]
    db.session.commit()
    payload = _payload()
    for invalid in ([], ["Vegetarian"], "Sesame allergy"):
        payload["profile"]["dietary_restrictions"] = invalid
        response = client.post("/test-trip-routes/register", json=payload)
        assert response.status_code == 400
        assert "profile.dietary_restrictions" in response.get_json()["error"]
        create_intent.assert_not_called()
    payload["profile"].update(dietary_restrictions=["Sesame allergy", DIETARY_OTHER],
                              dietary_other="Also avoid celery")
    create_intent.return_value = _intent()
    response = client.post("/test-trip-routes/register", json=payload)
    assert response.status_code == 200
    assert user.trip_profile.dietary_restrictions == ["Sesame allergy", DIETARY_OTHER]
    assert user.trip_profile.dietary_other == "Also avoid celery"


def test_register_renders_stored_order_with_disabled_builtins_omitted(client, public_trip):
    _, trip, _ = public_trip
    carpool, region, dietary, tent = default_builtin_questions()
    trip.custom_questions = [deepcopy(QUESTIONS[0]), tent, region | {"required": False},
                             carpool | {"enabled": False}, dietary]
    db.session.commit()
    html = client.get("/test-trip-routes/register").get_data(as_text=True)
    assert re.findall(r'data-(?:builtin|question-key)="([^"]+)"', html) == [
        "chore_preference", "tent", "region_code", "dietary"]
    assert 'id="driver-details"' not in html
    region_input = re.search(r'<input id="profile-region"[^>]*>', html)[0]
    assert "required" not in region_input
    assert 'maxlength="10"' in region_input
    assert 'href="https://bit.ly/TCSCmap"' in html
    assert re.findall(r'<section id="([^"]+)" data-step-section', html) == [
        "gate-section", "trip-questions", "payment-section"]


def test_no_enabled_questions_omits_survey_and_progress_step(client, public_trip):
    _, trip, _ = public_trip
    trip.custom_questions = [q | {"enabled": False} for q in default_builtin_questions()]
    db.session.commit()
    html = client.get("/test-trip-routes/register").get_data(as_text=True)
    assert 'id="trip-questions"' not in html
    assert 'href="#trip-questions"' not in html
    assert html.count('data-step-link') == 2
