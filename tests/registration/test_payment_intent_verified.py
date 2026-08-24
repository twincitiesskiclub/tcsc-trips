from datetime import datetime, timedelta, date
from unittest.mock import patch, MagicMock
import logging

import pytest

from app import create_app
from app.models import db, Payment, Season, User, UserSeason
from app.constants import PaymentType, UserSeasonStatus

EMAIL = "pi-verified@test.com"
PHONE = "+16125550190"
METADATA_USER_EMAIL = "pi-metadata-user@test.com"
NEW_EMAIL = "never-seen-before@test.com"
UNRESOLVED_EMAIL = "unresolved-user-id@test.com"


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
def fixtures(app):
    with app.app_context():
        now = datetime.utcnow()
        s = Season(name="PI Test", year=2098, price_cents=15000,
                   season_type='winter',
                   start_date=date(2098, 11, 1), end_date=date(2099, 3, 1),
                   returning_start=now - timedelta(days=1),
                   returning_end=now + timedelta(days=30),
                   new_start=now - timedelta(days=1),
                   new_end=now + timedelta(days=30))
        old = Season(name="PI Old", year=2088, price_cents=15000,
                     season_type='winter',
                     start_date=date(2088, 11, 1), end_date=date(2089, 3, 1))
        u = User(email=EMAIL, first_name="Pat", last_name="Payer",
                 phone_e164=PHONE)
        metadata_user = User(
            email=METADATA_USER_EMAIL,
            first_name="Metadata",
            last_name="User",
        )
        db.session.add_all([s, old, u, metadata_user])
        db.session.commit()
        db.session.add(UserSeason(user_id=u.id, season_id=old.id,
                                  registration_type="new",
                                  registration_date=date(2088, 10, 1),
                                  status=UserSeasonStatus.ACTIVE))
        db.session.commit()
        yield {
            "season_id": s.id,
            "user_id": u.id,
            "metadata_user_id": metadata_user.id,
        }
        Payment.query.filter_by(season_id=s.id).delete()
        Payment.query.filter(
            Payment.payment_intent_id.like("pi_verified_webhook_%")
        ).delete(synchronize_session=False)
        UserSeason.query.filter_by(season_id=s.id).delete()
        UserSeason.query.filter_by(user_id=u.id).delete()
        db.session.commit()
        unresolved_user = User.get_by_email(UNRESOLVED_EMAIL)
        if unresolved_user:
            db.session.delete(unresolved_user)
        db.session.delete(User.query.get(u.id))
        db.session.delete(User.query.get(metadata_user.id))
        db.session.delete(Season.query.get(s.id))
        db.session.delete(Season.query.get(old.id))
        db.session.commit()


def _set_identity(client, user_id=None):
    with client.session_transaction() as sess:
        sess["verified_identity"] = {
            "phone_e164": PHONE, "user_id": user_id,
            "ts": datetime.utcnow().isoformat()}


def _intent_mock():
    m = MagicMock()
    m.id, m.client_secret, m.amount, m.status = "pi_x", "cs_x", 15000, "requires_payment_method"
    return m


def _apply_succeeded_webhook(metadata, payment_intent_id):
    from app.routes.payments import webhook_received
    from flask import current_app

    payload = {
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": payment_intent_id,
                "amount": 15000,
                "metadata": metadata,
            }
        },
    }
    with patch.dict(
        "os.environ",
        {"FLASK_ENV": "development", "STRIPE_WEBHOOK_SECRET": ""},
    ):
        with current_app.test_request_context(
            "/webhook", method="POST", json=payload,
        ):
            with patch("app.routes.payments.send_payment_notification"):
                response = webhook_received()
    assert response.status_code == 200


@patch("app.routes.payments.stripe.PaymentIntent.create", return_value=_intent_mock())
def test_verified_returning_gets_automatic_capture(mock_create, client, fixtures):
    _set_identity(client, user_id=fixtures["user_id"])
    resp = client.post("/create-season-payment-intent", json={
        "season_id": fixtures["season_id"], "email": EMAIL, "name": "Pat Payer"})
    assert resp.status_code == 200
    kwargs = mock_create.call_args.kwargs
    assert kwargs["capture_method"] == "automatic"
    assert kwargs["metadata"]["member_type"] == "RETURNING"
    assert kwargs["metadata"]["verified"] == "true"


@patch("app.routes.payments.stripe.PaymentIntent.create", return_value=_intent_mock())
def test_unverified_is_always_manual_new(mock_create, client, fixtures):
    # No session identity: even though EMAIL belongs to a returning member,
    # the typed email must not grant automatic capture.
    resp = client.post("/create-season-payment-intent", json={
        "season_id": fixtures["season_id"], "email": EMAIL, "name": "Pat Payer"})
    assert resp.status_code == 200
    kwargs = mock_create.call_args.kwargs
    assert kwargs["capture_method"] == "manual"
    assert kwargs["metadata"]["member_type"] == "NEW"
    assert kwargs["metadata"]["verified"] == "false"


@patch("app.routes.payments.stripe.PaymentIntent.create", return_value=_intent_mock())
def test_verified_identity_with_different_email_still_auto_captures(
        mock_create, client, fixtures):
    # Session identity points at returning member A, and the intent is for a
    # different typed email. Under the phone-is-primary rule that is a
    # profile edit, not grounds for a hold. This is the fix for the stuck
    # requires_capture rows from the PR #241 launch, where a verified
    # returning member who changed their email needed manual capture
    # within 7 days.
    _set_identity(client, user_id=fixtures["user_id"])
    resp = client.post("/create-season-payment-intent", json={
        "season_id": fixtures["season_id"],
        "email": "pi-someone-else@test.com", "name": "Pat Payer"})
    assert resp.status_code == 200
    kwargs = mock_create.call_args.kwargs
    assert kwargs["capture_method"] == "automatic"
    assert kwargs["metadata"]["member_type"] == "RETURNING"
    assert kwargs["metadata"]["verified"] == "true"
    assert kwargs["metadata"]["user_id"] == str(fixtures["user_id"])


@patch("app.routes.payments.stripe.PaymentIntent.create", return_value=_intent_mock())
def test_unverified_intent_carries_no_user_id(mock_create, client, fixtures):
    resp = client.post("/create-season-payment-intent", json={
        "season_id": fixtures["season_id"], "email": EMAIL, "name": "Pat Payer"})
    assert resp.status_code == 200
    assert mock_create.call_args.kwargs["metadata"]["user_id"] == ""


@patch("app.routes.payments.stripe.PaymentIntent.create", return_value=_intent_mock())
def test_webhook_prefers_metadata_user_id_over_email(mock_create, client, app, fixtures):
    """Otherwise a verified member using a new address gets a duplicate stub."""
    uid = fixtures["user_id"]
    with app.app_context():
        before = User.query.count()
    metadata = {
        'email': NEW_EMAIL, 'name': 'Pat Payer',
        'season_id': str(fixtures["season_id"]),
        'member_type': 'RETURNING', 'payment_type': PaymentType.SEASON,
        'verified': 'true', 'user_id': str(uid),
    }
    with app.app_context():
        payment_intent_id = "pi_verified_webhook_resolved_season"
        _apply_succeeded_webhook(metadata, payment_intent_id)
        assert User.query.count() == before, "webhook created a duplicate stub"
        payment = Payment.get_by_payment_intent(payment_intent_id)
        assert payment.user_id == uid


def test_webhook_does_not_create_member_for_unresolved_metadata_user_id(
        app, fixtures, caplog):
    payment_intent_id = "pi_verified_webhook_unresolved_season"
    with app.app_context():
        missing_user_id = (db.session.query(db.func.max(User.id)).scalar() or 0) + 1
        before_users = User.query.count()
        before_user_seasons = UserSeason.query.count()
        metadata = {
            'email': UNRESOLVED_EMAIL, 'name': 'Missing Member',
            'season_id': str(fixtures["season_id"]),
            'member_type': 'RETURNING', 'payment_type': PaymentType.SEASON,
            'verified': 'true', 'user_id': str(missing_user_id),
        }

        with caplog.at_level(logging.WARNING):
            _apply_succeeded_webhook(metadata, payment_intent_id)

        assert User.query.count() == before_users
        assert User.get_by_email(UNRESOLVED_EMAIL) is None
        assert UserSeason.query.count() == before_user_seasons
        payment = Payment.get_by_payment_intent(payment_intent_id)
        assert payment is not None
        assert payment.user_id is None
        assert payment_intent_id in caplog.text
        assert str(missing_user_id) in caplog.text


def test_trip_webhook_ignores_metadata_user_id_and_matches_by_email(
        app, fixtures):
    payment_intent_id = "pi_verified_webhook_trip_email_match"
    metadata = {
        'email': EMAIL, 'name': 'Pat Payer',
        'member_type': 'RETURNING', 'payment_type': PaymentType.TRIP,
        'user_id': str(fixtures["metadata_user_id"]),
    }

    with app.app_context():
        _apply_succeeded_webhook(metadata, payment_intent_id)
        payment = Payment.get_by_payment_intent(payment_intent_id)
        assert payment is not None
        assert payment.user_id == fixtures["user_id"]
        assert payment.user_id != fixtures["metadata_user_id"]
