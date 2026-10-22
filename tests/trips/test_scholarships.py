import re
from datetime import datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.constants import UserStatus
from app.models import db, Trip, User
from app.trips.models import (
    TripRegistration, TripRegistrationStatus, TripScholarship, TripSeries,
)
from app.trips.scholarships import (
    active_registration, generate_code, scholarship_state,
)


def _member(email="trip-member@example.com", first_name="Mira",
            status=UserStatus.ACTIVE):
    user = User(first_name=first_name, last_name="Member", email=email,
                status=status)
    db.session.add(user)
    db.session.flush()
    return user


def _trip(slug="test-trip-models-2027", name="Hayward Training Trip",
          series_slug="test-trip-models", **overrides):
    series = TripSeries.query.filter_by(slug=series_slug).first()
    if series is None:
        series = TripSeries(slug=series_slug, name=name, destination="Hayward")
        db.session.add(series)
        db.session.flush()
    fields = dict(
        slug=slug, name=name, destination="Hayward", series_id=series.id,
        max_participants_standard=10, max_participants_extra=0,
        start_date=datetime(2099, 1, 10), end_date=datetime(2099, 1, 12),
        signup_start=datetime.utcnow() - timedelta(days=1),
        signup_end=datetime.utcnow() + timedelta(days=30),
        price_low=11000, price_high=13000, status="active",
    )
    fields.update(overrides)
    trip = Trip(**fields)
    db.session.add(trip)
    db.session.flush()
    return trip


def _scholarship(user, season, **overrides):
    fields = dict(user_id=user.id, season_id=season.id, code=generate_code())
    fields.update(overrides)
    scholarship = TripScholarship(**fields)
    db.session.add(scholarship)
    db.session.flush()
    return scholarship


def _registration(trip, user, scholarship, status, **overrides):
    fields = dict(trip_id=trip.id, user_id=user.id, status=status,
                  price_tier="low", amount_cents=trip.price_low,
                  scholarship_id=scholarship.id)
    fields.update(overrides)
    registration = TripRegistration(**fields)
    db.session.add(registration)
    db.session.flush()
    return registration


def test_generate_code_format():
    assert re.fullmatch(
        r"TCSC-[ABCDEFGHJKMNPQRSTUVWXYZ23456789]{6}", generate_code())


def test_default_amount_is_100_dollars(db_session, current_season):
    scholarship = _scholarship(_member(), current_season)
    assert scholarship.amount_cents == 10000


def test_state_available_without_registrations(db_session, current_season):
    scholarship = _scholarship(_member(), current_season)
    assert scholarship_state(scholarship) == "available"
    assert active_registration(scholarship) is None


def test_state_held_by_pending(db_session, current_season):
    user = _member()
    scholarship = _scholarship(user, current_season)
    registration = _registration(
        _trip(), user, scholarship, TripRegistrationStatus.PENDING)
    assert scholarship_state(scholarship) == "held"
    assert active_registration(scholarship) == registration


def test_state_used_by_confirmed(db_session, current_season):
    user = _member()
    scholarship = _scholarship(user, current_season)
    _registration(_trip(), user, scholarship, TripRegistrationStatus.CONFIRMED)
    assert scholarship_state(scholarship) == "used"


def test_state_freed_by_cancelled(db_session, current_season):
    user = _member()
    scholarship = _scholarship(user, current_season)
    _registration(_trip(), user, scholarship, TripRegistrationStatus.CANCELLED)
    assert scholarship_state(scholarship) == "available"


def test_state_ignores_stale_pending_payment(db_session, current_season):
    user = _member()
    scholarship = _scholarship(user, current_season)
    _registration(_trip(), user, scholarship,
                  TripRegistrationStatus.PENDING_PAYMENT,
                  created_at=datetime.utcnow() - timedelta(hours=2))
    assert scholarship_state(scholarship) == "available"


def test_unique_per_member_season(db_session, current_season):
    user = _member()
    _scholarship(user, current_season)
    with pytest.raises(IntegrityError):
        _scholarship(user, current_season)
    db.session.rollback()
