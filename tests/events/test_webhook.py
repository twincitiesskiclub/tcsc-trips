"""Stripe webhook tests for generic event registrations."""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from app.events.models import (
    Event,
    EventPriceOption,
    EventRegistration,
    EventStatus,
    RegistrationStatus,
)
from app.models import Payment, User


@pytest.fixture
def unknown_payment_cleanup(db_session):
    intent_id = "pi_unknown_payment_type"
    Payment.query.filter_by(payment_intent_id=intent_id).delete()
    db_session.session.commit()
    yield intent_id
    Payment.query.filter_by(payment_intent_id=intent_id).delete()
    db_session.session.commit()


@pytest.fixture
def pending_registration(db_session):
    now = datetime.utcnow()
    event = Event(
        slug="payment-link-test",
        name="Webhook Test Event",
        location="Test Trails",
        event_date=now + timedelta(days=30),
        signup_start=now - timedelta(days=1),
        signup_end=now + timedelta(days=1),
        status=EventStatus.ACTIVE,
    )
    option = EventPriceOption(
        name="Registration",
        price_cents=5500,
        participant_roles=["Participant"],
    )
    event.price_options.append(option)
    db_session.session.add(event)
    db_session.session.flush()
    registration = EventRegistration(
        event_id=event.id,
        price_option_id=option.id,
        contact_email="event-guest@example.com",
        contact_phone="555-0100",
        emergency_contact_name="Emergency Contact",
        emergency_contact_phone="555-0199",
        answers={},
        amount_cents=5500,
        status=RegistrationStatus.PENDING_PAYMENT,
        payment_intent_id="pi_event_webhook",
    )
    db_session.session.add(registration)
    db_session.session.commit()
    return registration


def _webhook_payload(event_type, registration_id, intent_id="pi_event_webhook"):
    return {
        "type": event_type,
        "data": {
            "object": {
                "id": intent_id,
                "amount": 5500,
                "metadata": {
                    "payment_type": "event",
                    "event_id": "999",
                    "registration_id": str(registration_id),
                    "email": "event-guest@example.com",
                    "name": "Event Guest",
                },
            }
        },
    }


def _post_development_webhook(client, payload):
    with patch.dict(
        "os.environ",
        {"FLASK_ENV": "development", "STRIPE_WEBHOOK_SECRET": ""},
    ):
        return client.post("/webhook", json=payload)


@patch("app.routes.payments.send_payment_notification")
def test_succeeded_event_payment_confirms_without_creating_user(
    notify,
    client,
    db_session,
    pending_registration,
):
    registration_id = pending_registration.id
    user_count_before = User.query.count()

    with patch("app.routes.payments.User.get_by_email") as get_user:
        response = _post_development_webhook(
            client,
            _webhook_payload("payment_intent.succeeded", registration_id),
        )

    assert response.status_code == 200
    get_user.assert_not_called()
    db_session.session.expire_all()
    registration = db_session.session.get(
        EventRegistration,
        registration_id,
    )
    payment = Payment.get_by_payment_intent("pi_event_webhook")
    assert registration.status == RegistrationStatus.CONFIRMED
    assert payment.event_registration_id == registration_id
    assert payment.user_id is None
    assert payment.payment_type == "event"
    assert payment.email == "event-guest@example.com"
    assert payment.name == "Event Guest"
    assert payment.amount == 5500
    assert payment.status == "succeeded"
    assert User.query.count() == user_count_before
    notify.assert_called_once_with(
        name="Event Guest",
        amount_cents=5500,
        email="event-guest@example.com",
        payment_intent_id="pi_event_webhook",
    )


@patch("app.routes.payments.send_payment_notification")
def test_succeeded_event_webhook_replay_is_idempotent(
    _notify,
    client,
    pending_registration,
):
    payload = _webhook_payload(
        "payment_intent.succeeded",
        pending_registration.id,
    )

    first = _post_development_webhook(client, payload)
    second = _post_development_webhook(client, payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert Payment.query.filter_by(
        payment_intent_id="pi_event_webhook",
    ).count() == 1


@patch("app.routes.payments.send_payment_notification")
def test_succeeded_event_with_missing_registration_still_records_payment(
    _notify,
    client,
):
    response = _post_development_webhook(
        client,
        _webhook_payload(
            "payment_intent.succeeded",
            999999,
            intent_id="pi_event_missing_registration",
        ),
    )

    assert response.status_code == 200
    payment = Payment.get_by_payment_intent(
        "pi_event_missing_registration",
    )
    assert payment is not None
    assert payment.event_registration_id is None
    assert payment.user_id is None


def test_canceled_event_intent_cancels_pending_registration(
    client,
    db_session,
    pending_registration,
):
    registration_id = pending_registration.id

    response = _post_development_webhook(
        client,
        _webhook_payload("payment_intent.canceled", registration_id),
    )

    assert response.status_code == 200
    db_session.session.expire_all()
    registration = db_session.session.get(
        EventRegistration,
        registration_id,
    )
    assert registration.status == RegistrationStatus.CANCELLED


@patch("app.routes.payments.send_payment_notification")
def test_unknown_payment_type_logs_and_records_payment(
    _notify,
    client,
    caplog,
    unknown_payment_cleanup,
):
    intent_id = unknown_payment_cleanup
    payload = {
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": intent_id,
                "amount": 3200,
                "metadata": {
                    "payment_type": "legacy_unknown",
                    "email": "unknown@example.com",
                    "name": "Unknown Payment",
                },
            }
        },
    }

    response = _post_development_webhook(client, payload)

    assert response.status_code == 200
    payment = Payment.get_by_payment_intent(intent_id)
    assert payment is not None
    assert payment.payment_type == "legacy_unknown"
    assert payment.status == "succeeded"
    assert "unknown payment_type" in caplog.text
