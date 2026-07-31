from datetime import datetime, timedelta

import pytest

from app.constants import UserStatus
from app.models import db, Trip, User
from app.trips import service
from app.trips.models import TripRegistration, TripRegistrationStatus, TripSeries


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
        custom_questions=QUESTIONS,
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
    registration = service.create_registration(trip, _payload())
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
    registration = service.create_registration(trip, payload)
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


def test_duplicate_registration_rejected(db_session):
    series = _series()
    trip = _edition(series)
    _member()
    db.session.commit()
    service.create_registration(trip, _payload())
    with pytest.raises(service.TripRegistrationError) as excinfo:
        service.create_registration(trip, _payload())
    assert "email" in excinfo.value.errors
    assert "already" in excinfo.value.errors["email"].lower()


def test_capacity_counts_pending_and_confirmed(db_session):
    series = _series()
    trip = _edition(series)  # capacity 2
    user_a = _member()
    user_b = _member("trip-second@example.com")
    db.session.commit()
    reg = service.create_registration(trip, _payload())
    reg.status = TripRegistrationStatus.PENDING
    db.session.commit()
    second = service.create_registration(
        trip, _payload(email="trip-second@example.com"))
    second.status = TripRegistrationStatus.CONFIRMED
    db.session.commit()
    assert service.capacity_available(trip) is False


def test_expire_stale_pending(db_session):
    series = _series()
    trip = _edition(series)
    _member()
    db.session.commit()
    registration = service.create_registration(trip, _payload())
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
