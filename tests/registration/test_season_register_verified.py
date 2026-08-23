from datetime import datetime, timedelta, date
from unittest.mock import patch

import pytest

from app import create_app
from app.models import db, Season, User, UserSeason

EMAIL = "reg-verified@test.com"
PHONE = "+16125550188"


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
        s = Season(name="Verify Test", year=2099, price_cents=15000,
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
    firstName="Reg", lastName="Verified", email=EMAIL, pronouns="",
    dob="1994-01-15", phone="612-555-0188", technique="skate",
    tshirtSize="M", experience="3-7", emergencyName="Em Contact",
    emergencyRelation="friend", emergencyPhone="612-555-0189",
    emergencyEmail="em@example.com", payment_intent_id="pi_test_verify",
)


def _set_identity(client, user_id=None):
    with client.session_transaction() as sess:
        sess["verified_identity"] = {
            "phone_e164": PHONE, "user_id": user_id,
            "ts": datetime.utcnow().isoformat()}


@patch("app.routes.registration.send_sms", return_value=True)
def test_verified_new_member_gets_e164_and_lottery_sms(mock_sms, client, app, season):
    _set_identity(client)
    resp = client.post(f"/seasons/{season}/register", data=FORM)
    assert resp.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email=EMAIL).one()
        assert user.phone_e164 == PHONE
        assert user.phone_verified_at is not None
        us = UserSeason.get_for_user_season(user.id, season)
        assert us.needs_review is False
    assert mock_sms.call_args.args[1] == "confirmation_lottery"


@patch("app.routes.registration.send_sms", return_value=True)
def test_unverified_flags_needs_review(mock_sms, client, app, season):
    # no session identity at all + explicit continue_unverified
    resp = client.post(f"/seasons/{season}/register",
                       data={**FORM, "continue_unverified": "1"})
    assert resp.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email=EMAIL).one()
        us = UserSeason.get_for_user_season(user.id, season)
        assert us.needs_review is True
        assert user.phone_verified_at is None
        assert user.phone_e164 == "+16125550188"  # normalized, but unverified


def test_unverified_without_flag_is_rejected(client, app, season):
    resp = client.post(f"/seasons/{season}/register", data=FORM,
                       follow_redirects=False)
    assert resp.status_code == 302  # bounced back with flash error


@patch("app.routes.registration.send_sms", return_value=True)
def test_new_email_collision_without_flag_rejected(mock_sms, client, app, season):
    with app.app_context():
        db.session.add(User(email=EMAIL, first_name="Old", last_name="Row"))
        db.session.commit()
    _set_identity(client)  # verified phone, but user_id None -> "new" path
    resp = client.post(f"/seasons/{season}/register", data=FORM,
                       follow_redirects=False)
    assert resp.status_code == 302  # collision guard fired


@patch("app.routes.registration.send_sms", return_value=True)
def test_verified_returning_member_updates_own_row(mock_sms, client, app, season):
    with app.app_context():
        u = User(email=EMAIL, first_name="Old", last_name="Name")
        db.session.add(u)
        db.session.commit()
        uid = u.id
    _set_identity(client, user_id=uid)
    resp = client.post(f"/seasons/{season}/register", data=FORM)
    assert resp.status_code == 200
    with app.app_context():
        user = User.query.get(uid)
        assert user.first_name == "Reg"  # updated in place, no duplicate row
        assert User.query.filter_by(email=EMAIL).count() == 1
