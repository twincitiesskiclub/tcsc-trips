"""Escalations and lead check-ins mention PRACTICES_DIRECTOR tag holders.

The helper test writes to the real local dev database (see conftest), so it
only flushes TEST-prefixed rows and rolls them back; it never commits.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.models import SlackUser, Tag, User
from app.slack.practices import coach_review, leads
from app.slack.practices.leads import practices_director_slack_ids


def test_helper_returns_slack_ids_of_tagged_users_with_slack(db_session):
    try:
        tag = Tag.query.filter_by(name="PRACTICES_DIRECTOR").first()
        if tag is None:
            tag = Tag(name="PRACTICES_DIRECTOR", display_name="Practices Director")
            db_session.add(tag)
        unique = uuid.uuid4().hex[:8]
        slack_uid = f"UTEST{unique}".upper()
        with_slack = User(
            first_name="TEST Director", last_name="WithSlack",
            email=f"test-director-slack-{unique}@example.invalid",
            slack_user=SlackUser(slack_uid=slack_uid),
        )
        without_slack = User(
            first_name="TEST Director", last_name="NoSlack",
            email=f"test-director-noslack-{unique}@example.invalid",
        )
        with_slack.tags = [tag]
        without_slack.tags = [tag]
        db_session.add_all([with_slack, without_slack])
        db_session.flush()

        ids = practices_director_slack_ids()

        assert slack_uid in ids
        assert None not in ids
    finally:
        db_session.rollback()


def test_helper_warns_when_no_one_holds_the_tag(app, caplog):
    with app.app_context(), patch.object(leads, "Tag") as tag_model:
        tag_model.query.filter_by.return_value.first.return_value = None
        assert practices_director_slack_ids() == []
    assert "No PRACTICES_DIRECTOR tag holders" in caplog.text


def _practice_with_lead(lead_uid="ULEAD"):
    lead_user = SimpleNamespace(slack_user=SimpleNamespace(slack_uid=lead_uid))
    return SimpleNamespace(
        id=7,
        date=MagicMock(),
        location=None,
        practice_types=[],
        slack_collab_message_ts="111.222",
        leads=[SimpleNamespace(role="lead", user=lead_user)],
    )


def _escalation_text(app, director_ids):
    client = MagicMock()
    with app.app_context(), \
            patch.object(coach_review, "practices_director_slack_ids",
                         return_value=director_ids), \
            patch.object(coach_review, "get_slack_client", return_value=client), \
            patch.object(coach_review, "FALLBACK_COACH_IDS", ["UCOACH"]), \
            patch.object(coach_review.db.session, "commit"):
        result = coach_review.escalate_practice_review(_practice_with_lead())
    assert result == {"success": True}
    return client.chat_postMessage.call_args.kwargs["text"]


def test_escalation_mentions_directors_not_hardcoded_admins(app):
    text = _escalation_text(app, ["UDIR1", "UDIR2"])
    assert "<@UCOACH> <@UDIR1> <@UDIR2>" in text
    assert "U02J6R6CZS7" not in text


def test_escalation_without_directors_mentions_coaches_only(app):
    text = _escalation_text(app, [])
    assert text.startswith(":warning: <@UCOACH> This practice")


def _checkin(app, director_ids, lead_uid="ULEAD"):
    client = MagicMock()
    with app.app_context(), \
            patch.object(leads, "practices_director_slack_ids",
                         return_value=director_ids), \
            patch("app.slack.client.open_conversation",
                  return_value={"success": True, "channel_id": "G1"}) as opened, \
            patch("app.slack.client.get_slack_client", return_value=client), \
            patch("app.utils.format_datetime_central", return_value="6:15 PM"):
        result = leads.send_lead_checkin_dm(_practice_with_lead(lead_uid))
    return result, opened, client


def test_checkin_dm_includes_directors(app):
    result, opened, client = _checkin(app, ["UDIR1", "UDIR2"])
    assert result["success"] is True
    assert sorted(opened.call_args.args[0]) == ["UDIR1", "UDIR2", "ULEAD"]
    text = client.chat_postMessage.call_args.kwargs["text"]
    assert "<@UDIR1>, <@UDIR2> are here." in text


def test_checkin_dm_without_directors_adds_no_one_else(app):
    """A lone lead is below the group DM's two-person minimum, so nothing
    is sent rather than pulling in hardcoded admins."""
    result, opened, client = _checkin(app, [], lead_uid="ULEAD")
    assert result == {"success": False, "error": "Not enough participants for group DM"}
    opened.assert_not_called()
    client.chat_postMessage.assert_not_called()


def test_hardcoded_admin_lists_are_gone():
    from app.slack.practices import _config

    assert not hasattr(_config, "ADMIN_SLACK_IDS")
    assert not hasattr(leads, "ADMIN_FALLBACK_IDS")
