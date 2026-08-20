from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.constants import UserStatus
from app.models import db, SlackUser, Trip, User
from app.slack.blocks.trips import (
    build_confirmation_dm_blocks,
    build_registration_dm_blocks,
    build_trip_announcement_blocks,
    trip_announcement_fallback,
)
from app.slack import trips as slack_trips
from app.trips.models import TripRegistration, TripRegistrationStatus, TripSeries


@pytest.fixture
def linked_registration(db_session):
    series = TripSeries(slug="test-trip-slack", name="TEST Trip",
                        destination="Testville",
                        slack_channel_name="test-trip-channel")
    db.session.add(series)
    db.session.flush()
    trip = Trip(
        slug="test-trip-slack-2027", name="TEST Trip 2027",
        destination="Testville", series_id=series.id,
        max_participants_standard=20, max_participants_extra=0,
        start_date=datetime(2099, 1, 10), end_date=datetime(2099, 1, 12),
        signup_start=datetime.utcnow() - timedelta(days=1),
        signup_end=datetime.utcnow() + timedelta(days=30),
        price_low=10000, price_high=15000, status="active",
        custom_questions=[{
            "key": "chore_preference", "label": "Chore preference",
        }],
    )
    slack_user = SlackUser(slack_uid="U_TEST_TRIP", email="trip-member@example.com")
    db.session.add_all([trip, slack_user])
    db.session.flush()
    user = User(first_name="Test", last_name="Member",
                email="trip-member@example.com", status=UserStatus.ACTIVE,
                slack_user_id=slack_user.id)
    db.session.add(user)
    db.session.flush()
    registration = TripRegistration(
        trip_id=trip.id, user_id=user.id,
        status=TripRegistrationStatus.PENDING,
        answers={"chore_preference": "Cooking"},
        price_tier="low", amount_cents=10000,
        payment_intent_id="pi_trip_slack",
    )
    db.session.add(registration)
    db.session.commit()
    return registration


def test_announcement_blocks_have_signup_button(linked_registration):
    trip = linked_registration.trip
    blocks = build_trip_announcement_blocks(trip, trip.series, spots_left=5)
    actions = [b for b in blocks if b["type"] == "actions"]
    assert actions
    button = actions[0]["elements"][0]
    assert button["url"].endswith("/test-trip-slack/register")
    assert trip_announcement_fallback(trip)


def test_registration_dm_includes_answers(linked_registration):
    blocks = build_registration_dm_blocks(
        linked_registration, linked_registration.trip,
        linked_registration.trip.series)
    flat = str(blocks)
    assert "Cooking" in flat
    assert "Chore preference" in flat
    assert "chore_preference" not in flat
    assert "We'll DM you when the roster is confirmed." in flat


def test_send_confirmation_dm_with_seriesless_trip_returns_bool(
        db_session, linked_registration):
    trip = Trip(
        slug="test-trip-slack-seriesless", name="TEST Seriesless Trip",
        destination="Testville", series_id=None,
        max_participants_standard=20, max_participants_extra=0,
        start_date=datetime(2099, 2, 10), end_date=datetime(2099, 2, 12),
        signup_start=datetime.utcnow() - timedelta(days=1),
        signup_end=datetime.utcnow() + timedelta(days=30),
        price_low=10000, price_high=15000, status="active",
        custom_questions=[],
    )
    registration = TripRegistration(
        trip=trip, user=linked_registration.user,
        status=TripRegistrationStatus.CONFIRMED,
        answers={}, price_tier="low", amount_cents=10000,
        payment_intent_id="pi_trip_slack_seriesless",
    )
    db.session.add_all([trip, registration])
    db.session.flush()

    client = MagicMock()
    with patch("app.slack.trips.get_slack_client", return_value=client):
        result = slack_trips.send_confirmation_dm(registration)

    assert isinstance(result, bool)
    sent_text = client.chat_postMessage.call_args.kwargs["blocks"][0]["text"]["text"]
    assert sent_text.endswith("$100.00.")


def test_send_registration_dm_posts_to_slack_uid(linked_registration):
    client = MagicMock()
    with patch("app.slack.trips.get_slack_client", return_value=client):
        assert slack_trips.send_registration_dm(linked_registration) is True
    kwargs = client.chat_postMessage.call_args.kwargs
    assert kwargs["channel"] == "U_TEST_TRIP"
    assert kwargs["blocks"]


def test_send_dm_without_linked_slack_user_returns_false(db_session,
                                                         linked_registration):
    linked_registration.user.slack_user_id = None
    db.session.commit()
    client = MagicMock()
    with patch("app.slack.trips.get_slack_client", return_value=client):
        assert slack_trips.send_registration_dm(linked_registration) is False
    client.chat_postMessage.assert_not_called()


def test_invite_to_trip_channel(linked_registration):
    with patch("app.slack.trips.get_channel_id_by_name",
               return_value="C_TRIPCH") as get_channel, \
         patch("app.slack.trips.add_user_to_channel",
               return_value=True) as add:
        assert slack_trips.invite_to_trip_channel(linked_registration) is True
    get_channel.assert_called_once_with("test-trip-channel")
    add.assert_called_once_with("U_TEST_TRIP", "C_TRIPCH",
                                "trip-member@example.com")


def test_invite_without_channel_configured_returns_false(db_session,
                                                         linked_registration):
    linked_registration.trip.series.slack_channel_name = None
    db.session.commit()
    assert slack_trips.invite_to_trip_channel(linked_registration) is False


def test_unfurl_payload_for_trip_link(linked_registration):
    from app.slack.bolt_app import build_trip_unfurls
    trip = linked_registration.trip
    unfurls = build_trip_unfurls([
        {"url": "https://tcsc.ski/test-trip-slack/register"},
        {"url": "https://tcsc.ski/not-a-trip"},
    ])
    assert "https://tcsc.ski/test-trip-slack/register" in unfurls
    assert "https://tcsc.ski/not-a-trip" not in unfurls
    card = unfurls["https://tcsc.ski/test-trip-slack/register"]
    assert card["blocks"]
