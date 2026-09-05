from datetime import datetime, timedelta

import pytest

from app.constants import UserStatus
from app.models import db, Trip, User
from app.trips import service
from app.trips.questions import default_builtin_questions
from app.trips.models import TripProfile, TripRegistration, TripRegistrationStatus, TripSeries


QUESTIONS = [
    {"key": "departure_time", "label": "Departure?", "type": "multi_choice",
     "options": ["Fri AM", "Fri PM"], "max_selections": 2, "required": True},
    {"key": "can_stop", "label": "Stop for food?", "type": "yes_no",
     "required": True},
    {"key": "stop_where", "label": "Where?", "type": "text", "required": True,
     "visible_if": {"question": "can_stop", "equals": "yes"}},
]

PROFILE = {
    "can_drive": "yes", "seat_capacity": "3", "bike_capacity": "0",
    "hitch_size": "", "region_code": "4",
    "dietary_restrictions": ["Vegetarian"], "dietary_other": "",
    "has_tent": "no",
}


def _series(slug="test-trip-service"):
    series = TripSeries(slug=slug, name="TEST Trip", destination="Testville")
    db.session.add(series)
    db.session.flush()
    return series


def _edition(series, slug="test-trip-service-2027", **overrides):
    fields = dict(
        slug=slug, name="TEST Trip 2027", destination="Testville",
        series_id=series.id, max_participants_standard=2,
        max_participants_extra=0,
        start_date=datetime(2099, 1, 10), end_date=datetime(2099, 1, 12),
        signup_start=datetime.utcnow() - timedelta(days=1),
        signup_end=datetime.utcnow() + timedelta(days=30),
        price_low=10000, price_high=15000, status="active",
        custom_questions=default_builtin_questions() + QUESTIONS,
    )
    fields.update(overrides)
    trip = Trip(**fields)
    db.session.add(trip)
    db.session.flush()
    return trip


def _member(email="trip-member@example.com", status=UserStatus.ACTIVE):
    user = User(first_name="Test", last_name="Member",
                email=email, status=status)
    db.session.add(user)
    db.session.flush()
    return user


def _payload(**overrides):
    payload = {
        "email": "trip-member@example.com", "price_tier": "low",
        "profile": dict(PROFILE),
        "answers": {"departure_time": ["Fri AM"], "can_stop": "no"},
    }
    payload.update(overrides)
    return payload


def test_lookup_active_member_rejects_inactive(db_session):
    _member("trip-inactive@example.com", status=UserStatus.ALUMNI)
    db.session.commit()
    assert service.lookup_active_member("trip-inactive@example.com") is None
    assert service.lookup_active_member("Trip-Inactive@Example.com ") is None


def test_create_registration_happy_path(db_session):
    series = _series()
    trip = _edition(series)
    user = _member()
    db.session.commit()
    registration, previous_intent_id = service.create_registration(trip, _payload())
    assert previous_intent_id is None
    assert registration.status == TripRegistrationStatus.PENDING_PAYMENT
    assert registration.amount_cents == 10000
    assert registration.answers == {"departure_time": ["Fri AM"],
                                    "can_stop": "no"}
    assert user.trip_profile.seat_capacity == 3
    assert user.trip_profile.can_drive is True


def test_hidden_conditional_answer_not_required_and_not_stored(db_session):
    series = _series()
    trip = _edition(series)
    _member()
    db.session.commit()
    payload = _payload(answers={"departure_time": ["Fri AM"],
                                "can_stop": "no",
                                "stop_where": "should be dropped"})
    registration, _ = service.create_registration(trip, payload)
    assert "stop_where" not in registration.answers


def test_visible_conditional_answer_required(db_session):
    series = _series()
    trip = _edition(series)
    _member()
    db.session.commit()
    payload = _payload(answers={"departure_time": ["Fri AM"],
                                "can_stop": "yes"})
    with pytest.raises(service.TripRegistrationError) as excinfo:
        service.create_registration(trip, payload)
    assert "answers.stop_where" in excinfo.value.errors


def test_multi_choice_cap_and_invalid_option_rejected(db_session):
    series = _series()
    trip = _edition(series)
    _member()
    db.session.commit()
    payload = _payload(answers={"departure_time": ["Fri AM", "Fri PM", "Sat"],
                                "can_stop": "no"})
    with pytest.raises(service.TripRegistrationError) as excinfo:
        service.create_registration(trip, payload)
    assert "answers.departure_time" in excinfo.value.errors


@pytest.mark.parametrize("status", [TripRegistrationStatus.PENDING, TripRegistrationStatus.CONFIRMED])
def test_duplicate_registration_rejected(db_session, status):
    series = _series()
    trip = _edition(series)
    _member()
    db.session.commit()
    registration, _ = service.create_registration(trip, _payload())
    registration.status = status
    db.session.commit()
    with pytest.raises(service.TripRegistrationError) as excinfo:
        service.create_registration(trip, _payload())
    assert "email" in excinfo.value.errors
    assert "already" in excinfo.value.errors["email"].lower()


@pytest.mark.parametrize("status", [TripRegistrationStatus.PENDING_PAYMENT, TripRegistrationStatus.CANCELLED])
def test_unpaid_registration_reused(db_session, status):
    trip = _edition(_series())
    user = _member()
    db.session.commit()
    registration, _ = service.create_registration(trip, _payload())
    original_id = registration.id
    registration.status = status
    registration.payment_intent_id = "pi_previous"
    registration.created_at = datetime.utcnow() - timedelta(hours=2)
    db.session.commit()
    before_retry = datetime.utcnow()
    payload = _payload(price_tier="high", answers={"departure_time": ["Fri PM"], "can_stop": "no"})
    payload["profile"]["seat_capacity"] = "5"

    retried, previous_intent_id = service.create_registration(trip, payload)

    db.session.expire_all()
    assert retried.id == original_id
    assert previous_intent_id == "pi_previous"
    assert retried.status == TripRegistrationStatus.PENDING_PAYMENT
    assert retried.answers == payload["answers"]
    assert retried.price_tier == "high"
    assert retried.amount_cents == trip.price_high
    assert retried.payment_intent_id is None
    assert before_retry <= retried.created_at <= datetime.utcnow()
    assert user.trip_profile.seat_capacity == 5
    assert TripRegistration.query.filter_by(trip_id=trip.id, user_id=user.id).count() == 1


def test_retry_validates_before_changing_pending_registration(db_session):
    trip = _edition(_series())
    _member()
    db.session.commit()
    registration, _ = service.create_registration(trip, _payload())
    registration.payment_intent_id = "pi_previous"
    db.session.commit()
    created_at = registration.created_at
    with pytest.raises(service.TripRegistrationError):
        service.create_registration(trip, _payload(price_tier="invalid", answers={}))
    db.session.expire_all()
    assert registration.created_at == created_at
    assert registration.payment_intent_id == "pi_previous"
    assert registration.answers == _payload()["answers"]


def test_retry_does_not_double_count_own_capacity_hold(db_session):
    trip = _edition(_series(), max_participants_standard=1)
    _member()
    db.session.commit()
    registration, _ = service.create_registration(trip, _payload())
    assert service.capacity_available(trip) is False

    retried, _ = service.create_registration(trip, _payload())

    assert retried.id == registration.id
    assert service._active_count(trip) == 1


def test_expired_hold_retry_cannot_displace_another_member(db_session):
    trip = _edition(_series(), max_participants_standard=1)
    _member()
    _member("trip-second@example.com")
    db.session.commit()
    registration, _ = service.create_registration(trip, _payload())
    registration.created_at = datetime.utcnow() - timedelta(hours=2)
    db.session.commit()
    service.create_registration(trip, _payload(email="trip-second@example.com"))
    with pytest.raises(service.TripRegistrationError) as excinfo:
        service.create_registration(trip, _payload())
    assert excinfo.value.errors == {"trip": "This trip is full."}


def test_capacity_counts_pending_and_confirmed(db_session):
    series = _series()
    trip = _edition(series)  # capacity 2
    user_a = _member()
    user_b = _member("trip-second@example.com")
    db.session.commit()
    reg, _ = service.create_registration(trip, _payload())
    reg.status = TripRegistrationStatus.PENDING
    db.session.commit()
    second, _ = service.create_registration(
        trip, _payload(email="trip-second@example.com"))
    second.status = TripRegistrationStatus.CONFIRMED
    db.session.commit()
    assert service.capacity_available(trip) is False


def test_expire_stale_pending(db_session):
    series = _series()
    trip = _edition(series)
    _member()
    db.session.commit()
    registration, _ = service.create_registration(trip, _payload())
    registration.created_at = datetime.utcnow() - timedelta(hours=25)
    db.session.commit()
    service.expire_stale_pending(trip)
    db.session.expire_all()
    assert registration.status == TripRegistrationStatus.CANCELLED


def test_bool_capacity_rejected(db_session):
    series = _series()
    trip = _edition(series)
    _member()
    db.session.commit()
    payload = _payload()
    payload["profile"]["seat_capacity"] = True
    with pytest.raises(service.TripRegistrationError) as excinfo:
        service.create_registration(trip, payload)
    assert "profile.seat_capacity" in excinfo.value.errors


def test_non_dict_payload_raises_registration_error(db_session):
    series = _series()
    trip = _edition(series)
    db.session.commit()
    with pytest.raises(service.TripRegistrationError):
        service.create_registration(trip, None)


def test_window_closed_rejected(db_session):
    series = _series()
    trip = _edition(series,
                    signup_end=datetime.utcnow() - timedelta(days=1))
    _member()
    db.session.commit()
    with pytest.raises(service.TripRegistrationError) as excinfo:
        service.create_registration(trip, _payload())
    assert "trip" in excinfo.value.errors


def test_all_optional_builtins_accept_blanks():
    questions = [q | {"required": False} for q in default_builtin_questions()]
    clean, errors = service.validate_profile(questions, {})
    assert errors == {}
    assert clean == dict(can_drive=None, has_tent=None, region_code="",
                         seat_capacity=None, bike_capacity=None, hitch_size="",
                         dietary_restrictions=[], dietary_other="")


@pytest.mark.parametrize("field, value", [
    ("can_drive", "maybe"), ("has_tent", "maybe"), ("region_code", "x" * 11),
    ("seat_capacity", -1), ("bike_capacity", 100), ("hitch_size", "3"),
])
def test_optional_builtins_still_validate_nonblank_answers(field, value):
    questions = [q | {"required": False} for q in default_builtin_questions()]
    _, errors = service.validate_profile(questions, PROFILE | {field: value})
    assert f"profile.{field}" in errors


def test_required_carpool_region_and_tent():
    questions = [q | {"required": True} for q in default_builtin_questions()]
    _, errors = service.validate_profile(questions, {})
    assert set(errors) == {"profile.can_drive", "profile.region_code",
                           "profile.dietary_restrictions", "profile.has_tent"}


def test_non_driver_details_ignored():
    clean, errors = service.validate_profile(default_builtin_questions(), PROFILE | {
        "can_drive": "no", "seat_capacity": "bad", "bike_capacity": "bad", "hitch_size": "bad"})
    assert errors == {}
    assert clean["seat_capacity"] is clean["bike_capacity"] is None
    assert clean["hitch_size"] == ""


@pytest.mark.parametrize("key, field, previous", [
    ("seats", "seat_capacity", 5), ("bikes", "bike_capacity", 4), ("hitch", "hitch_size", "2"),
])
@pytest.mark.parametrize("submitted", [None, "invalid"])
def test_disabled_carpool_followup_preserves_profile(db_session, key, field, previous, submitted):
    user = _member()
    profile = TripProfile(user_id=user.id, **{field: previous})
    db.session.add(profile)
    db.session.commit()
    questions = default_builtin_questions()
    questions[0]["followups"][key]["enabled"] = False
    payload = dict(PROFILE)
    if submitted is None:
        payload.pop(field)
    else:
        payload[field] = submitted

    clean, errors = service.validate_profile(questions, payload)

    assert errors == {}
    assert field not in clean
    service.upsert_profile(user, clean)
    db.session.commit()
    db.session.expire_all()
    assert getattr(user.trip_profile, field) == previous
