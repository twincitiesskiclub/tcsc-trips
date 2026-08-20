from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from app.constants import UserStatus
from app.models import db, Trip, User
from app.trips.models import TripRegistration, TripRegistrationStatus, TripSeries


@pytest.fixture
def pending_registration(db_session):
    series = TripSeries(slug="test-trip-webhook", name="TEST Trip",
                        destination="Testville")
    db.session.add(series)
    db.session.flush()
    trip = Trip(
        slug="test-trip-webhook-2027", name="TEST Trip 2027",
        destination="Testville", series_id=series.id,
        max_participants_standard=20, max_participants_extra=0,
        start_date=datetime(2099, 1, 10), end_date=datetime(2099, 1, 12),
        signup_start=datetime.utcnow() - timedelta(days=1),
        signup_end=datetime.utcnow() + timedelta(days=30),
        price_low=10000, price_high=15000, status="active",
        custom_questions=[],
    )
    user = User(first_name="Test", last_name="Member",
                email="trip-member@example.com", status=UserStatus.ACTIVE)
    db.session.add_all([trip, user])
    db.session.flush()
    registration = TripRegistration(
        trip_id=trip.id, user_id=user.id,
        status=TripRegistrationStatus.PENDING_PAYMENT,
        answers={}, price_tier="low", amount_cents=10000,
        payment_intent_id="pi_trip_webhook",
    )
    db.session.add(registration)
    db.session.commit()
    return registration


def _webhook_payload(event_type, registration_id, trip_id,
                     intent_id="pi_trip_webhook"):
    return {"type": event_type, "data": {"object": {
        "id": intent_id, "amount": 10000,
        "metadata": {"payment_type": "trip",
                     "trip_id": str(trip_id),
                     "registration_id": str(registration_id),
                     "email": "trip-member@example.com",
                     "name": "Test Member",
                     "member_type": "returning"}}}}


def _post_development_webhook(client, payload):
    with patch.dict("os.environ", {"FLASK_ENV": "development",
                                   "STRIPE_WEBHOOK_SECRET": ""}):
        return client.post("/webhook", json=payload)


def test_capturable_marks_registration_pending(client, db_session,
                                               pending_registration):
    payload = _webhook_payload("payment_intent.amount_capturable_updated",
                               pending_registration.id,
                               pending_registration.trip_id)
    response = _post_development_webhook(client, payload)
    assert response.status_code == 200
    db_session.session.expire_all()
    assert pending_registration.status == TripRegistrationStatus.PENDING


@patch("app.routes.payments.send_payment_notification")
def test_succeeded_confirms_registration(notify, client, db_session,
                                         pending_registration):
    payload = _webhook_payload("payment_intent.succeeded",
                               pending_registration.id,
                               pending_registration.trip_id)
    response = _post_development_webhook(client, payload)
    assert response.status_code == 200
    db_session.session.expire_all()
    assert pending_registration.status == TripRegistrationStatus.CONFIRMED


def test_canceled_cancels_registration(client, db_session,
                                       pending_registration):
    payload = _webhook_payload("payment_intent.canceled",
                               pending_registration.id,
                               pending_registration.trip_id)
    response = _post_development_webhook(client, payload)
    assert response.status_code == 200
    db_session.session.expire_all()
    assert pending_registration.status == TripRegistrationStatus.CANCELLED


def test_missing_registration_id_does_not_error(client, db_session,
                                                pending_registration):
    payload = _webhook_payload("payment_intent.amount_capturable_updated",
                               pending_registration.id,
                               pending_registration.trip_id)
    del payload["data"]["object"]["metadata"]["registration_id"]
    response = _post_development_webhook(client, payload)
    assert response.status_code == 200  # legacy trip intents lack the key


@patch("app.routes.payments.trip_slack")
def test_capturable_sends_registration_dm(trip_slack, client, db_session,
                                          pending_registration):
    payload = _webhook_payload("payment_intent.amount_capturable_updated",
                               pending_registration.id,
                               pending_registration.trip_id)
    _post_development_webhook(client, payload)
    trip_slack.send_registration_dm.assert_called_once()
    (called_registration,) = trip_slack.send_registration_dm.call_args.args
    assert called_registration.id == pending_registration.id


@patch("app.routes.payments.send_payment_notification")
@patch("app.routes.payments.trip_slack")
def test_succeeded_sends_confirmation_and_invite(trip_slack, notify, client,
                                                 db_session,
                                                 pending_registration):
    from app.trips.models import TripRegistrationStatus
    pending_registration.status = TripRegistrationStatus.PENDING
    db_session.session.commit()
    payload = _webhook_payload("payment_intent.succeeded",
                               pending_registration.id,
                               pending_registration.trip_id)
    _post_development_webhook(client, payload)
    trip_slack.send_confirmation_dm.assert_called_once()
    (called_registration,) = trip_slack.send_confirmation_dm.call_args.args
    assert called_registration.id == pending_registration.id
    trip_slack.invite_to_trip_channel.assert_called_once()
    (called_registration,) = trip_slack.invite_to_trip_channel.call_args.args
    assert called_registration.id == pending_registration.id


@patch("app.routes.payments.send_payment_notification")
@patch("app.routes.payments.trip_slack")
def test_repeat_succeeded_webhook_does_not_re_dm(trip_slack, notify, client,
                                                 db_session,
                                                 pending_registration):
    from app.trips.models import TripRegistrationStatus
    pending_registration.status = TripRegistrationStatus.CONFIRMED
    db_session.session.commit()
    payload = _webhook_payload("payment_intent.succeeded",
                               pending_registration.id,
                               pending_registration.trip_id)
    _post_development_webhook(client, payload)
    trip_slack.send_confirmation_dm.assert_not_called()
