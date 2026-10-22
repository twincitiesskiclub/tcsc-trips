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


# --- Slack send and reveal ---------------------------------------------------

from unittest.mock import MagicMock, patch

from app.models import SlackUser
from app.trips import scholarships


def _linked_member(slack_uid="U_TEST_TRIP"):
    slack_user = SlackUser(slack_uid=slack_uid, email="trip-member@example.com")
    db.session.add(slack_user)
    db.session.flush()
    user = _member()
    user.slack_user_id = slack_user.id
    db.session.flush()
    return user


@patch("app.trips.scholarships.get_slack_client")
def test_send_dm_stores_message_ref(get_client, db_session, current_season):
    client = MagicMock()
    client.chat_postMessage.return_value = {"channel": "D1", "ts": "1.2"}
    get_client.return_value = client
    scholarship = _scholarship(_linked_member(), current_season)
    assert scholarships.send_scholarship_dm(scholarship) is True
    assert client.chat_postMessage.call_args.kwargs["channel"] == "U_TEST_TRIP"
    assert scholarship.slack_channel_id == "D1"
    assert scholarship.slack_message_ts == "1.2"
    assert scholarship.sent_at is not None


@patch("app.trips.scholarships.get_slack_client")
def test_send_dm_without_slack_link_returns_false(
        get_client, db_session, current_season):
    scholarship = _scholarship(_member(), current_season)
    assert scholarships.send_scholarship_dm(scholarship) is False
    assert scholarship.sent_at is None
    get_client.assert_not_called()


@patch("app.trips.scholarships.get_slack_client")
def test_send_dm_swallows_slack_error(get_client, db_session, current_season):
    get_client.return_value.chat_postMessage.side_effect = RuntimeError("boom")
    scholarship = _scholarship(_linked_member(), current_season)
    assert scholarships.send_scholarship_dm(scholarship) is False
    assert scholarship.sent_at is None


def test_reveal_sets_claimed_at(db_session, current_season):
    scholarship = _scholarship(_linked_member(), current_season)
    blocks = scholarships.reveal(scholarship.id, "U_TEST_TRIP")
    assert scholarship.code in str(blocks)
    assert scholarship.claimed_at is not None


def test_reveal_is_idempotent(db_session, current_season):
    scholarship = _scholarship(_linked_member(), current_season)
    first = scholarships.reveal(scholarship.id, "U_TEST_TRIP")
    claimed_at = scholarship.claimed_at
    second = scholarships.reveal(scholarship.id, "U_TEST_TRIP")
    assert second == first
    assert scholarship.claimed_at == claimed_at


def test_reveal_rejects_other_user(db_session, current_season):
    scholarship = _scholarship(_linked_member(), current_season)
    assert scholarships.reveal(scholarship.id, "U_SOMEONE_ELSE") is None
    assert scholarship.claimed_at is None
    assert scholarships.reveal(999999999, "U_TEST_TRIP") is None


def test_reveal_mentions_registration_already_applied(db_session, current_season):
    user = _linked_member()
    scholarship = _scholarship(user, current_season)
    _registration(_trip(), user, scholarship, TripRegistrationStatus.PENDING)
    blocks = scholarships.reveal(scholarship.id, "U_TEST_TRIP")
    assert "Already applied to Hayward Training Trip" in str(blocks)


def test_handle_reveal_click_updates_the_message(db_session, current_season):
    scholarship = _scholarship(_linked_member(), current_season)
    client = MagicMock()
    body = {"user": {"id": "U_TEST_TRIP"}, "channel": {"id": "D1"},
            "message": {"ts": "1.2"}}
    action = {"value": str(scholarship.id)}
    assert scholarships.handle_reveal_click(body, action, client) is True
    kwargs = client.chat_update.call_args.kwargs
    assert kwargs["channel"] == "D1" and kwargs["ts"] == "1.2"
    assert scholarship.code in str(kwargs["blocks"])


def test_handle_reveal_click_ignores_stranger(db_session, current_season):
    scholarship = _scholarship(_linked_member(), current_season)
    client = MagicMock()
    body = {"user": {"id": "U_SOMEONE_ELSE"}, "channel": {"id": "D1"},
            "message": {"ts": "1.2"}}
    assert scholarships.handle_reveal_click(
        body, {"value": str(scholarship.id)}, client) is False
    client.chat_update.assert_not_called()


def test_open_trips_window(db_session):
    now = datetime.utcnow()
    open_trip = _trip()
    _trip(slug="test-trip-models-2028", name="Closed",
          signup_end=now - timedelta(hours=1))
    _trip(slug="test-trip-models-2029", name="Draft", status="draft")
    names = [t.name for t in scholarships.open_trips(now)
             if t.slug.startswith("test-trip-models")]
    assert names == [open_trip.name]
