import json
from datetime import datetime, timedelta

import pytest

from app.models import db, Trip
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
