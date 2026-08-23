"""Volunteer-interest question: validation helper + registration route storage."""
from datetime import datetime, timedelta, date
from unittest.mock import patch

import pytest

from app import create_app
from app.models import db, Season, User, UserSeason
from app.utils import validate_volunteer_selections

EMAIL = "reg-volunteer@test.com"
PHONE = "+16125550177"


# --- Unit: validate_volunteer_selections ---

def test_single_interest_is_valid():
    interests, committees, errors = validate_volunteer_selections(
        ["practice_lead"], [])
    assert errors == []
    assert interests == ["practice_lead"]
    assert committees == []


def test_no_interests_is_rejected():
    _, _, errors = validate_volunteer_selections([], [])
    assert errors, "at least one volunteer interest should be required"


def test_committee_interest_requires_a_committee():
    _, _, errors = validate_volunteer_selections(["committee"], [])
    assert errors


def test_committee_with_picks_is_valid():
    interests, committees, errors = validate_volunteer_selections(
        ["committee"], ["social", "dry_tri"])
    assert errors == []
    assert committees == ["social", "dry_tri"]


def test_committees_cleared_when_committee_not_selected():
    interests, committees, errors = validate_volunteer_selections(
        ["event_volunteer"], ["social"])
    assert errors == []
    assert committees == []


def test_unknown_keys_are_rejected():
    _, _, errors = validate_volunteer_selections(["bake_sale"], [])
    assert errors
    _, _, errors = validate_volunteer_selections(["committee"], ["yachting"])
    assert errors


# --- Route: answers stored on UserSeason ---

@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"
    )
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def season(app):
    with app.app_context():
        now = datetime.utcnow()
        s = Season(name="Volunteer Test", year=2099, price_cents=15000,
                   season_type='winter',
                   start_date=date(2099, 11, 1), end_date=date(2100, 3, 1),
                   returning_start=now - timedelta(days=1),
                   returning_end=now + timedelta(days=30),
                   new_start=now - timedelta(days=1),
                   new_end=now + timedelta(days=30))
        db.session.add(s)
        db.session.commit()
        yield s.id
        UserSeason.query.filter_by(season_id=s.id).delete()
        u = User.query.filter_by(email=EMAIL).one_or_none()
        if u:
            db.session.delete(u)
        db.session.delete(Season.query.get(s.id))
        db.session.commit()


FORM = dict(
    firstName="Vol", lastName="Unteer", email=EMAIL, pronouns="",
    dob="1994-01-15", phone="612-555-0177", technique="skate",
    tshirtSize="M", experience="3-7", emergencyName="Em Contact",
    emergencyRelation="friend", emergencyPhone="612-555-0189",
    emergencyEmail="em@example.com", payment_intent_id="pi_test_volunteer",
)


def _set_identity(client, user_id=None):
    with client.session_transaction() as sess:
        sess["verified_identity"] = {
            "phone_e164": PHONE, "user_id": user_id,
            "ts": datetime.utcnow().isoformat()}


@patch("app.routes.registration.send_sms", return_value=True)
def test_registration_stores_volunteer_answers(mock_sms, client, app, season):
    _set_identity(client)
    resp = client.post(
        f"/seasons/{season}/register",
        data={**FORM,
              "volunteerInterests": ["event_volunteer", "committee"],
              "volunteerCommittees": ["adventures"]})
    assert resp.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email=EMAIL).one()
        us = UserSeason.get_for_user_season(user.id, season)
        assert us.volunteer_interests == ["event_volunteer", "committee"]
        assert us.volunteer_committees == ["adventures"]


@patch("app.routes.registration.send_sms", return_value=True)
def test_registration_without_interests_is_rejected(mock_sms, client, app, season):
    _set_identity(client)
    resp = client.post(f"/seasons/{season}/register", data=FORM,
                       follow_redirects=False)
    assert resp.status_code == 302
    with app.app_context():
        assert User.query.filter_by(email=EMAIL).one_or_none() is None


@patch("app.routes.registration.send_sms", return_value=True)
def test_stray_committees_not_stored(mock_sms, client, app, season):
    _set_identity(client)
    resp = client.post(
        f"/seasons/{season}/register",
        data={**FORM,
              "volunteerInterests": ["practice_lead"],
              "volunteerCommittees": ["social"]})
    assert resp.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email=EMAIL).one()
        us = UserSeason.get_for_user_season(user.id, season)
        assert us.volunteer_interests == ["practice_lead"]
        assert us.volunteer_committees == []
