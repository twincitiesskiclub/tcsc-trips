from datetime import datetime, timedelta, date
from unittest.mock import patch, MagicMock

import pytest

from app import create_app
from app.models import db, Season, User, UserSeason
from app.constants import UserSeasonStatus

EMAIL = "pi-verified@test.com"
PHONE = "+16125550190"


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
        db.session.add_all([s, old, u])
        db.session.commit()
        db.session.add(UserSeason(user_id=u.id, season_id=old.id,
                                  registration_type="new",
                                  registration_date=date(2088, 10, 1),
                                  status=UserSeasonStatus.ACTIVE))
        db.session.commit()
        yield {"season_id": s.id, "user_id": u.id}
        UserSeason.query.filter_by(user_id=u.id).delete()
        db.session.commit()
        db.session.delete(User.query.get(u.id))
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
