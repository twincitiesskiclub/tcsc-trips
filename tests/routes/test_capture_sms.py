"""Capturing a season hold texts the member only when that capture is what
got them in (PENDING_LOTTERY -> ACTIVE). Returning members whose hold was a
conservative fallback already got a confirmation and stay quiet."""
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app import create_app
from app.constants import PaymentType, UserSeasonStatus
from app.models import db, Payment, Season, User, UserSeason

NEW_EMAIL = "cap-new@test.com"
RET_EMAIL = "cap-returning@test.com"


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
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["user"] = {"email": "admin@twincitiesskiclub.org"}
    return c


@pytest.fixture
def fixtures(app):
    with app.app_context():
        season = Season(name="Cap Test", year=2096, price_cents=20500,
                        season_type="winter",
                        start_date=date(2096, 11, 1), end_date=date(2097, 3, 1))
        new = User(email=NEW_EMAIL, first_name="Nia", last_name="New",
                   phone_e164="+16125550201")
        ret = User(email=RET_EMAIL, first_name="Rae", last_name="Returning",
                   phone_e164="+16125550202")
        db.session.add_all([season, new, ret])
        db.session.commit()
        db.session.add_all([
            UserSeason(user_id=new.id, season_id=season.id,
                       registration_type="new", registration_date=date.today(),
                       status=UserSeasonStatus.PENDING_LOTTERY),
            UserSeason(user_id=ret.id, season_id=season.id,
                       registration_type="returning",
                       registration_date=date.today(),
                       status=UserSeasonStatus.ACTIVE),
            Payment(payment_intent_id="pi_cap_test_new", email=NEW_EMAIL,
                    name="Nia New", amount=20500, status="requires_capture",
                    payment_type=PaymentType.SEASON, season_id=season.id,
                    user_id=new.id),
            Payment(payment_intent_id="pi_cap_test_ret", email=RET_EMAIL,
                    name="Rae Returning", amount=20500,
                    status="requires_capture",
                    payment_type=PaymentType.SEASON, season_id=season.id,
                    user_id=ret.id),
        ])
        db.session.commit()
        ids = {
            "season_id": season.id, "new_id": new.id, "ret_id": ret.id,
            "new_payment_id": Payment.get_by_payment_intent("pi_cap_test_new").id,
            "ret_payment_id": Payment.get_by_payment_intent("pi_cap_test_ret").id,
        }
        yield ids
        db.session.expire_all()
        Payment.query.filter(Payment.payment_intent_id.in_(
            ["pi_cap_test_new", "pi_cap_test_ret"])).delete(synchronize_session="fetch")
        UserSeason.query.filter(UserSeason.season_id == season.id).delete(
            synchronize_session="fetch")
        for e in (NEW_EMAIL, RET_EMAIL):
            db.session.delete(User.query.filter_by(email=e).one())
        db.session.delete(Season.query.get(season.id))
        db.session.commit()


def _stripe_ok(mock_stripe):
    mock_stripe.PaymentIntent.retrieve.return_value = MagicMock(status="requires_capture")
    mock_stripe.PaymentIntent.capture.return_value = MagicMock(status="succeeded")
    mock_stripe.error.StripeError = Exception


@patch("app.routes.payments.send_sms")
@patch("app.routes.payments.stripe")
def test_capture_of_lottery_hold_texts_accepted(mock_stripe, mock_sms, client, app, fixtures):
    _stripe_ok(mock_stripe)
    resp = client.post(f"/admin/payments/{fixtures['new_payment_id']}/capture")
    assert resp.status_code == 200, resp.data

    mock_sms.assert_called_once()
    user, template = mock_sms.call_args.args
    assert user.id == fixtures["new_id"]
    assert template == "accepted"
    assert mock_sms.call_args.kwargs == {"season_name": "Cap Test", "amount": "$205.00"}
    with app.app_context():
        us = UserSeason.get_for_user_season(fixtures["new_id"], fixtures["season_id"])
        assert us.status == UserSeasonStatus.ACTIVE
        assert us.payment_date is not None


@patch("app.routes.payments.send_sms")
@patch("app.routes.payments.stripe")
def test_capture_of_returning_hold_stays_quiet(mock_stripe, mock_sms, client, fixtures):
    _stripe_ok(mock_stripe)
    resp = client.post(f"/admin/payments/{fixtures['ret_payment_id']}/capture")
    assert resp.status_code == 200, resp.data
    mock_sms.assert_not_called()


@patch("app.routes.payments.send_sms")
@patch("app.routes.payments.stripe")
def test_bulk_capture_texts_each_lottery_member_once(mock_stripe, mock_sms, client, app, fixtures):
    _stripe_ok(mock_stripe)
    resp = client.post("/admin/payments/bulk-capture", json={
        "payment_ids": [fixtures["new_payment_id"], fixtures["ret_payment_id"]]})
    assert resp.status_code == 200, resp.data
    assert all(r["success"] for r in resp.get_json()["results"])

    assert mock_sms.call_count == 1
    assert mock_sms.call_args.args[0].id == fixtures["new_id"]
    assert mock_sms.call_args.args[1] == "accepted"
    with app.app_context():
        for uid in (fixtures["new_id"], fixtures["ret_id"]):
            assert Payment.query.filter_by(user_id=uid).one().status == "succeeded"


@patch("app.routes.payments.send_sms")
@patch("app.routes.payments.stripe")
def test_failed_capture_sends_nothing(mock_stripe, mock_sms, client, fixtures):
    mock_stripe.PaymentIntent.retrieve.return_value = MagicMock(status="canceled")
    resp = client.post(f"/admin/payments/{fixtures['new_payment_id']}/capture")
    assert resp.status_code == 400
    mock_sms.assert_not_called()
