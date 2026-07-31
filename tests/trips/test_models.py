from datetime import datetime, timedelta

from app.models import db, Trip, User
from app.constants import UserStatus
from app.trips.models import (
    TripProfile,
    TripRegistration,
    TripRegistrationStatus,
    TripSeries,
)


def _series(slug="test-trip-models"):
    series = TripSeries(
        slug=slug, name="TEST Trip", destination="Testville",
        slack_channel_name="test-trip-channel",
    )
    db.session.add(series)
    db.session.flush()
    return series


def _edition(series, slug="test-trip-models-2027", start=None, status="active"):
    start = start or datetime(2099, 1, 10)
    trip = Trip(
        slug=slug, name="TEST Trip 2027", destination="Testville",
        series_id=series.id,
        max_participants_standard=20, max_participants_extra=5,
        start_date=start, end_date=start + timedelta(days=2),
        signup_start=datetime.utcnow() - timedelta(days=1),
        signup_end=datetime.utcnow() + timedelta(days=30),
        price_low=10000, price_high=15000, status=status,
        custom_questions=[],
    )
    db.session.add(trip)
    db.session.flush()
    return trip


def test_series_edition_relationship_and_current_edition(db_session):
    series = _series()
    edition = _edition(series)
    db.session.commit()
    assert edition in series.editions
    assert series.current_edition().id == edition.id


def test_current_edition_prefers_upcoming_active_over_past(db_session):
    series = _series()
    past = _edition(series, slug="test-trip-models-2027",
                    start=datetime(2020, 1, 10))
    upcoming = _edition(series, slug="test-trip-routes-2027",
                        start=datetime(2099, 1, 10))
    db.session.commit()
    assert series.current_edition().id == upcoming.id


def test_registration_unique_per_member_per_edition(db_session):
    series = _series()
    edition = _edition(series)
    user = User(first_name="Test", last_name="Member",
                email="trip-member@example.com", status=UserStatus.ACTIVE)
    db.session.add(user)
    db.session.flush()
    reg = TripRegistration(
        trip_id=edition.id, user_id=user.id,
        status=TripRegistrationStatus.PENDING_PAYMENT,
        answers={}, price_tier="low", amount_cents=10000,
    )
    db.session.add(reg)
    db.session.commit()
    import sqlalchemy.exc
    import pytest as _pytest
    dupe = TripRegistration(
        trip_id=edition.id, user_id=user.id,
        status=TripRegistrationStatus.PENDING_PAYMENT,
        answers={}, price_tier="low", amount_cents=10000,
    )
    db.session.add(dupe)
    with _pytest.raises(sqlalchemy.exc.IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_trip_profile_one_row_per_user(db_session):
    user = User(first_name="Test", last_name="Member",
                email="trip-member@example.com", status=UserStatus.ACTIVE)
    db.session.add(user)
    db.session.flush()
    profile = TripProfile(
        user_id=user.id, can_drive=True, seat_capacity=3,
        bike_capacity=2, hitch_size="2", region_code="4",
        dietary_restrictions=["Vegetarian"], dietary_other="",
        has_tent=False,
    )
    db.session.add(profile)
    db.session.commit()
    assert user.trip_profile.seat_capacity == 3
