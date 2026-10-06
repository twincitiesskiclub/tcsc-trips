"""Gates on /create-season-payment-intent that must fire BEFORE Stripe.

Each one is a production case from 2026-08-31 / 2026-09-01 where the card
was authorized and then the registration POST bounced, leaving a hold with
no registration behind it and no confirmation text.
"""
from datetime import datetime, timedelta, date
from unittest.mock import patch, MagicMock

import pytest

from app import create_app
from app.models import db, Payment, Season, User, UserSeason
from app.constants import PaymentType, UserSeasonStatus

EMAIL = "gate-member@test.com"
PHONE = "+16125550191"
UNMATCHED_PHONE = "+16125550192"
NEW_EMAIL = "gate-newcomer@test.com"


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
        s = Season(name="Gate Test", year=2097, price_cents=15000,
                   season_type='winter',
                   start_date=date(2097, 11, 1), end_date=date(2098, 3, 1),
                   returning_start=now - timedelta(days=1),
                   returning_end=now + timedelta(days=30),
                   new_start=now - timedelta(days=1),
                   new_end=now + timedelta(days=30))
        old = Season(name="Gate Old", year=2087, price_cents=15000,
                     season_type='winter',
                     start_date=date(2087, 11, 1), end_date=date(2088, 3, 1))
        u = User(email=EMAIL, first_name="Gate", last_name="Member",
                 phone_e164=PHONE)
        db.session.add_all([s, old, u])
        db.session.commit()
        db.session.add(UserSeason(user_id=u.id, season_id=old.id,
                                  registration_type="new",
                                  registration_date=date(2087, 10, 1),
                                  status=UserSeasonStatus.ACTIVE))
        db.session.commit()
        yield {"season_id": s.id, "user_id": u.id}
        Payment.query.filter_by(season_id=s.id).delete()
        UserSeason.query.filter_by(season_id=s.id).delete()
        UserSeason.query.filter_by(user_id=u.id).delete()
        db.session.commit()
        newcomer = User.get_by_email(NEW_EMAIL)
        if newcomer:
            db.session.delete(newcomer)
        db.session.delete(User.query.get(u.id))
        db.session.delete(Season.query.get(s.id))
        db.session.delete(Season.query.get(old.id))
        db.session.commit()


def _set_identity(client, phone=PHONE, user_id=None):
    with client.session_transaction() as sess:
        sess["verified_identity"] = {
            "phone_e164": phone, "user_id": user_id,
            "ts": datetime.utcnow().isoformat()}


def _intent_mock():
    m = MagicMock()
    m.id, m.client_secret, m.amount, m.status = (
        "pi_gate", "cs_gate", 15000, "requires_payment_method")
    return m


def _post(client, fixtures, email, **extra):
    body = {"season_id": fixtures["season_id"], "email": email,
            "name": "Gate Member"}
    body.update(extra)
    return client.post("/create-season-payment-intent", json=body)


# --- Expired identity (Simon Stouffer, 2026-09-02 03:31Z) ---

@patch("app.routes.payments.stripe.PaymentIntent.create", return_value=_intent_mock())
def test_expired_identity_is_refused_before_stripe(mock_create, client, fixtures):
    # No session identity and no escape hatch: the POST would bounce with
    # "verification expired", so the hold must never be placed.
    resp = _post(client, fixtures, NEW_EMAIL)
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["code"] == "verification_expired"
    assert "verif" in body["error"].lower()
    mock_create.assert_not_called()


@patch("app.routes.payments.stripe.PaymentIntent.create", return_value=_intent_mock())
def test_cant_text_escape_hatch_still_places_a_hold(mock_create, client, fixtures):
    # "Can't receive texts?" is a legitimate no-identity path; keep it.
    resp = _post(client, fixtures, NEW_EMAIL, continue_unverified=True)
    assert resp.status_code == 200
    assert mock_create.call_args.kwargs["capture_method"] == "manual"


# --- Unverified email collision (Alex Balasis, 2026-08-31 23:40Z) ---

@patch("app.routes.payments.stripe.PaymentIntent.create", return_value=_intent_mock())
def test_unverified_email_collision_is_refused_before_stripe(
        mock_create, client, fixtures):
    # Phone matched nobody, typed email belongs to an existing member, and
    # neither the email code nor "Can't reach that inbox?" was used. The
    # POST rejects exactly this, so the intent must not be created.
    _set_identity(client, phone=UNMATCHED_PHONE, user_id=None)
    resp = _post(client, fixtures, EMAIL)
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["code"] == "email_unverified"
    assert "already has a member account" in body["error"]
    mock_create.assert_not_called()


@patch("app.routes.payments.stripe.PaymentIntent.create", return_value=_intent_mock())
def test_dead_inbox_hatch_on_collision_places_a_hold(mock_create, client, fixtures):
    _set_identity(client, phone=UNMATCHED_PHONE, user_id=None)
    resp = _post(client, fixtures, EMAIL, continue_unverified=True)
    assert resp.status_code == 200
    assert mock_create.call_args.kwargs["capture_method"] == "manual"


@patch("app.routes.payments.stripe.PaymentIntent.create", return_value=_intent_mock())
def test_unmatched_phone_with_unclaimed_email_places_a_hold(
        mock_create, client, fixtures):
    # A genuinely new member: verified phone, email nobody owns.
    _set_identity(client, phone=UNMATCHED_PHONE, user_id=None)
    resp = _post(client, fixtures, NEW_EMAIL)
    assert resp.status_code == 200
    assert mock_create.call_args.kwargs["capture_method"] == "manual"


# --- Orphaned hold blocks every retry ---

def _orphan_hold(fixtures, user_id=None):
    p = Payment(payment_intent_id="pi_gate_orphan", email=EMAIL,
                name="Gate Member", amount=15000, status="requires_capture",
                payment_type=PaymentType.SEASON,
                season_id=fixtures["season_id"], user_id=user_id)
    db.session.add(p)
    db.session.commit()
    return p.id


@patch("app.routes.payments.stripe.PaymentIntent.cancel")
@patch("app.routes.payments.stripe.PaymentIntent.create", return_value=_intent_mock())
def test_hold_with_no_registration_is_canceled_and_replaced(
        mock_create, mock_cancel, app, client, fixtures):
    with app.app_context():
        orphan_id = _orphan_hold(fixtures)
    _set_identity(client, user_id=fixtures["user_id"])
    resp = _post(client, fixtures, EMAIL)
    assert resp.status_code == 200, resp.get_json()
    mock_cancel.assert_called_once_with("pi_gate_orphan")
    mock_create.assert_called_once()
    with app.app_context():
        assert Payment.query.get(orphan_id).status == "canceled"


@patch("app.routes.payments.stripe.PaymentIntent.cancel")
@patch("app.routes.payments.stripe.PaymentIntent.create", return_value=_intent_mock())
def test_hold_backed_by_a_registration_still_blocks(
        mock_create, mock_cancel, app, client, fixtures):
    with app.app_context():
        _orphan_hold(fixtures, user_id=fixtures["user_id"])
        db.session.add(UserSeason(
            user_id=fixtures["user_id"], season_id=fixtures["season_id"],
            registration_type="new", registration_date=date.today(),
            status=UserSeasonStatus.PENDING_LOTTERY))
        db.session.commit()
    _set_identity(client, user_id=fixtures["user_id"])
    resp = _post(client, fixtures, EMAIL)
    assert resp.status_code == 400
    assert "already registered" in resp.get_json()["error"]
    mock_cancel.assert_not_called()
    mock_create.assert_not_called()
