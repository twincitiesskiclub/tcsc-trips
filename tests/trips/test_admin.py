import json
import csv
from datetime import datetime, timedelta
from io import StringIO

import pytest

from app.constants import UserStatus
from app.models import db, Trip
from app.models import Payment, User
from app.trips.models import TripProfile, TripRegistration, TripRegistrationStatus
from app.trips.models import TripSeries


@pytest.fixture
def admin_client(client):
    with client.session_transaction() as session:
        session["user"] = {"email": "admin@twincitiesskiclub.org"}
    return client


def _series_with_edition(db_session, slug="test-trip-admin",
                         edition_slug="test-trip-admin-2027"):
    series = TripSeries(slug=slug, name="TEST Trip", destination="Testville",
                        slack_channel_name="test-channel")
    db.session.add(series)
    db.session.flush()
    trip = Trip(
        slug=edition_slug, name="TEST Trip 2027", destination="Testville",
        series_id=series.id, max_participants_standard=20,
        max_participants_extra=5,
        start_date=datetime(2099, 1, 10), end_date=datetime(2099, 1, 12),
        signup_start=datetime(2098, 11, 1), signup_end=datetime(2098, 12, 31),
        price_low=10000, price_high=15000, status="active",
        custom_questions=[{"key": "chore_preference", "label": "Which task?",
                           "type": "choice",
                           "options": ["Cooking", "Cleaning"],
                           "required": True}],
    )
    db.session.add(trip)
    db.session.commit()
    return series, trip


def test_new_edition_clones_questions_and_prices(admin_client, db_session):
    series, trip = _series_with_edition(db_session)
    response = admin_client.post(f"/admin/trips/{trip.id}/new-edition")
    assert response.status_code == 200
    new_id = response.get_json()["id"]
    clone = db_session.session.get(Trip, new_id)
    assert clone.series_id == series.id
    assert clone.status == "draft"
    assert clone.custom_questions == trip.custom_questions
    assert clone.custom_questions is not trip.custom_questions
    assert clone.price_low == trip.price_low
    assert clone.slug == "test-trip-admin-2100"  # 2099-01-10 + 364d -> 2100
    assert clone.start_date == trip.start_date + timedelta(days=364)


def test_new_trip_duplicate_series_keeps_submitted_questions(
        admin_client, db_session):
    series, _ = _series_with_edition(db_session)
    questions = [{"key": "survivor", "label": "Submitted survivor label",
                  "type": "text", "options": [], "required": False}]
    trip_count = Trip.query.count()
    series_count = TripSeries.query.count()
    form = {
        "series_slug": series.slug,
        "name": "TEST Trip 2028", "slug": "test-trip-admin-2028",
        "destination": "Testville",
        "max_participants_standard": "20", "max_participants_extra": "5",
        "start_date": "2100-01-09", "end_date": "2100-01-11",
        "signup_start": "2099-11-01T00:00",
        "signup_end": "2099-12-31T00:00",
        "price_low": "100", "price_high": "150",
        "description": "Duplicate-series test", "status": "draft",
        "template_key": "blank",
        "custom_questions_json": json.dumps(questions),
    }

    response = admin_client.post("/admin/trips/new", data=form)

    assert response.status_code == 400
    body = response.get_data(as_text=True)
    assert "Submitted survivor label" in body
    assert series.slug in body
    assert "already exists" in body
    assert Trip.query.count() == trip_count
    assert TripSeries.query.count() == series_count


def test_edit_saves_custom_questions_json(admin_client, db_session):
    series, trip = _series_with_edition(db_session)
    questions = [{"key": "vibe", "label": "Vibe?", "type": "choice",
                  "options": ["Early bird", "Night owl"], "required": True}]
    form = {
        "name": trip.name, "destination": trip.destination,
        "max_participants_standard": "20", "max_participants_extra": "5",
        "start_date": "2099-01-10", "end_date": "2099-01-12",
        "signup_start": "2098-11-01T00:00", "signup_end": "2098-12-31T00:00",
        "price_low": "100", "price_high": "150",
        "description": "", "status": "active",
        "custom_questions_json": json.dumps(questions),
    }
    response = admin_client.post(f"/admin/trips/{trip.id}/edit", data=form)
    assert response.status_code in (200, 302)
    db_session.session.expire_all()
    assert trip.custom_questions == questions


def test_edit_rejects_invalid_question_json(admin_client, db_session):
    series, trip = _series_with_edition(db_session)
    form = {
        "name": trip.name, "destination": trip.destination,
        "max_participants_standard": "20", "max_participants_extra": "5",
        "start_date": "2099-01-10", "end_date": "2099-01-12",
        "signup_start": "2098-11-01T00:00", "signup_end": "2098-12-31T00:00",
        "price_low": "100", "price_high": "150",
        "description": "", "status": "active",
        "custom_questions_json": json.dumps([{"key": "bad"}]),
    }
    response = admin_client.post(f"/admin/trips/{trip.id}/edit", data=form)
    assert response.status_code == 400
    db_session.session.expire_all()
    assert trip.custom_questions[0]["key"] == "chore_preference"


def _registered_member(db_session, trip, email="trip-member@example.com"):
    user = User(first_name="Test", last_name="Member", email=email,
                status=UserStatus.ACTIVE)
    db.session.add(user)
    db.session.flush()
    db.session.add(TripProfile(user_id=user.id, can_drive=True,
                               seat_capacity=3, region_code="4",
                               dietary_restrictions=["Vegetarian"],
                               dietary_other="", has_tent=None))
    registration = TripRegistration(
        trip_id=trip.id, user_id=user.id,
        status=TripRegistrationStatus.PENDING,
        answers={"chore_preference": "Cooking"},
        price_tier="low", amount_cents=10000,
        payment_intent_id="pi_trip_admin",
    )
    db.session.add(registration)
    db.session.add(Payment(payment_intent_id="pi_trip_admin",
                           email=email, name="Test Member", amount=10000,
                           status="requires_capture", payment_type="trip",
                           trip_id=trip.id, user_id=user.id))
    db.session.commit()
    return user, registration


def test_roster_data_has_profile_and_question_columns(admin_client, db_session):
    series, trip = _series_with_edition(db_session)
    _registered_member(db_session, trip)
    response = admin_client.get(f"/admin/trips/{trip.id}/registrations/data")
    body = response.get_json()
    keys = [c["key"] for c in body["columns"]]
    assert "region_code" in keys
    assert "chore_preference" in keys
    row = body["registrations"][0]
    assert row["member"] == "Test Member"
    assert row["chore_preference"] == "Cooking"
    assert row["region_code"] == "4"
    assert row["payment_status"] == "requires_capture"
    assert row["payment_id"] is not None


def test_roster_csv_export(admin_client, db_session):
    series, trip = _series_with_edition(db_session)
    _registered_member(db_session, trip)
    response = admin_client.get(
        f"/admin/trips/{trip.id}/registrations/export.csv")
    reader = csv.DictReader(StringIO(response.get_data(as_text=True)))
    rows = list(reader)
    assert rows[0]["Member"] == "Test Member"
    assert rows[0]["Region"] == "4"
