from unittest.mock import patch, MagicMock

import pytest

from app import create_app
from app.models import db, User
from app.slack.channel_sync import invite_new_members, ChannelSyncResult

EMAIL = "invite-sms@test.com"


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
        u = User(email=EMAIL, first_name="Inv", last_name="Itee",
                 phone_e164="+16125550170")
        db.session.add(u)
        db.session.commit()
        yield
        db.session.delete(User.query.filter_by(email=EMAIL).one())
        db.session.commit()


@patch("app.slack.channel_sync.send_sms", return_value=True)
@patch("app.slack.channel_sync.invite_user_by_email")
def test_sms_nudge_after_successful_invite(mock_invite, mock_sms, app, user):
    with app.app_context():
        result = ChannelSyncResult()
        invite_new_members(
            db_email_to_tier={EMAIL: "full_member"}, slack_emails=set(),
            exception_emails=set(), target_channel_ids=["C1"], team_id="T1",
            invitation_message="welcome", dry_run=False, result=result)
    mock_sms.assert_called_once()
    assert mock_sms.call_args.args[1] == "slack_invite"


@patch("app.slack.channel_sync.send_sms")
@patch("app.slack.channel_sync.invite_user_by_email")
def test_dry_run_sends_no_sms(mock_invite, mock_sms, app, user):
    with app.app_context():
        result = ChannelSyncResult()
        invite_new_members(
            db_email_to_tier={EMAIL: "full_member"}, slack_emails=set(),
            exception_emails=set(), target_channel_ids=["C1"], team_id="T1",
            invitation_message="welcome", dry_run=True, result=result)
    mock_sms.assert_not_called()
