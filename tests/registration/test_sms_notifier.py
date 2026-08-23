from unittest.mock import patch

import pytest

from app import create_app
from app.models import db, User
from app.notifications.sms import send_sms
from app.verify.providers import ProviderError

EMAIL = "sms-notify@test.com"


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"
    )
    return app


@pytest.fixture
def user(app):
    with app.app_context():
        u = User(email=EMAIL, first_name="Sam", last_name="Sender",
                 phone_e164="+16125550166")
        db.session.add(u)
        db.session.commit()
        yield u
        db.session.delete(User.query.get(u.id))
        db.session.commit()


@patch("app.notifications.sms.twilio_send_sms")
def test_sends_rendered_template(mock_send, app, user):
    with app.app_context():
        ok = send_sms(user, "confirmation_returning",
                      season_name="2026-27", amount="$150.00")
    assert ok is True
    body = mock_send.call_args.args[1]
    assert "2026-27" in body and "$150.00" in body
    assert body.endswith("Reply STOP to opt out")


@patch("app.notifications.sms.twilio_send_sms")
def test_skips_opted_out_and_phoneless(mock_send, app, user):
    with app.app_context():
        u = User.query.get(user.id)
        u.sms_opt_out = True
        assert send_sms(u, "slack_invite") is False
        u.sms_opt_out = False
        u.phone_e164 = None
        assert send_sms(u, "slack_invite") is False
    mock_send.assert_not_called()


@patch("app.notifications.sms.twilio_send_sms",
       side_effect=ProviderError("unsubscribed", code=21610))
def test_records_opt_out_on_21610(mock_send, app, user):
    with app.app_context():
        assert send_sms(User.query.get(user.id), "slack_invite") is False
        assert User.query.get(user.id).sms_opt_out is True


@patch("app.notifications.sms.twilio_send_sms",
       side_effect=ProviderError("boom"))
def test_never_raises(mock_send, app, user):
    with app.app_context():
        assert send_sms(User.query.get(user.id), "slack_invite") is False
