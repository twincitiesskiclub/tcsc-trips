from unittest.mock import patch

import pytest

from app.analytics.models import SlackReactionEvent
from app.analytics.reaction_log import record_reaction_event
import app.slack.bolt_app as bolt_module


def test_records_add_and_remove_for_archived_channel(db_session):
    assert record_reaction_event(channel="C042G463AQ1", message_ts="4072435200.000100",
                                 emoji="six", slack_uid="UFAKE0009", removed=False,
                                 event_ts="4072435201.1", commit=False)
    assert record_reaction_event(channel="C042G463AQ1", message_ts="4072435200.000100",
                                 emoji="six", slack_uid="UFAKE0009", removed=True, commit=False)
    rows = SlackReactionEvent.query.filter_by(slack_uid="UFAKE0009").order_by(SlackReactionEvent.id).all()
    assert [r.action for r in rows] == ["added", "removed"]


def test_ignores_other_channels(db_session):
    assert record_reaction_event(channel="COTHER", message_ts="1.1", emoji="six",
                                 slack_uid="UFAKE0010", removed=False, commit=False) is False
    assert SlackReactionEvent.query.filter_by(slack_uid="UFAKE0010").count() == 0


def test_never_raises(db_session):
    with patch("app.analytics.reaction_log.db.session.add", side_effect=RuntimeError("boom")):
        assert record_reaction_event(channel="C042G463AQ1", message_ts="1.1", emoji="six",
                                     slack_uid="UFAKE0011", removed=False, commit=False) is False


def test_delegate_returns_attendance_result_even_if_log_fails(app):
    event = {"item": {"type": "message", "channel": "C042G463AQ1", "ts": "1.1"},
             "reaction": "six", "user": "UFAKE0012", "event_ts": "1.2"}
    with patch("app.slack.practices.reactions.handle_attendance_reaction",
               return_value={"success": True, "ignored": "message_not_linked"}), \
         patch("app.analytics.reaction_log.record_reaction_event",
               side_effect=RuntimeError("should be swallowed")) as rec, \
         patch.object(bolt_module, "get_app_context", return_value=app.app_context()):
        result = bolt_module._delegate_reaction_event(event, removed=False)
    assert result == {"success": True, "ignored": "message_not_linked"}
    assert rec.called


@pytest.mark.parametrize("removed", [False, True])
def test_delegate_logs_after_attendance_and_preserves_result(app, removed):
    calls = []
    expected = {"success": True, "ignored": "message_not_linked"}
    event = {"item": {"type": "message", "channel": "C042G463AQ1", "ts": "1.1"},
             "reaction": "six", "user": "UFAKE0012", "event_ts": "1.2"}

    def attendance(**kwargs):
        calls.append("attendance")
        return expected

    def record(**kwargs):
        calls.append("log")
        return True

    with patch("app.slack.practices.reactions.handle_attendance_reaction",
               side_effect=attendance) as handler, \
         patch("app.analytics.reaction_log.record_reaction_event",
               side_effect=record) as rec, \
         patch.object(bolt_module, "get_app_context", return_value=app.app_context()):
        assert bolt_module._delegate_reaction_event(event, removed=removed) is expected

    assert calls == ["attendance", "log"]
    handler.assert_called_once_with(channel="C042G463AQ1", message_ts="1.1",
                                    reaction="six", slack_user_id="UFAKE0012",
                                    removed=removed)
    rec.assert_called_once_with(channel="C042G463AQ1", message_ts="1.1",
                                emoji="six", slack_uid="UFAKE0012",
                                removed=removed, event_ts="1.2")


def test_delegate_preserves_attendance_exception_when_log_also_fails(app):
    error = RuntimeError("attendance failed")
    event = {"item": {"type": "message", "channel": "C042G463AQ1", "ts": "1.1"},
             "reaction": "six", "user": "UFAKE0012"}
    with patch("app.slack.practices.reactions.handle_attendance_reaction",
               side_effect=error), \
         patch("app.analytics.reaction_log.record_reaction_event",
               side_effect=RuntimeError("log failed")) as rec, \
         patch.object(bolt_module, "get_app_context", return_value=app.app_context()):
        with pytest.raises(RuntimeError) as caught:
            bolt_module._delegate_reaction_event(event, removed=True)
    assert caught.value is error
    rec.assert_called_once()


def test_delegate_ignores_non_message_events():
    with patch("app.slack.practices.reactions.handle_attendance_reaction") as handler, \
         patch("app.analytics.reaction_log.record_reaction_event") as rec:
        assert bolt_module._delegate_reaction_event(
            {"item": {"type": "file", "file": "FFAKE0001"}}, removed=False
        ) is None
    handler.assert_not_called()
    rec.assert_not_called()


@pytest.mark.parametrize("operation", ["flush", "commit"])
def test_database_failure_rolls_back(db_session, operation):
    with patch(f"app.analytics.reaction_log.db.session.{operation}",
               side_effect=RuntimeError("write failed")):
        assert record_reaction_event(
            channel="C042G463AQ1", message_ts="1.1", emoji="six",
            slack_uid="UFAKE0011", removed=False, commit=operation == "commit",
        ) is False
    assert SlackReactionEvent.query.filter_by(slack_uid="UFAKE0011").count() == 0


def test_rollback_failure_never_raises(db_session):
    with patch("app.analytics.reaction_log.db.session.add",
               side_effect=RuntimeError("write failed")), \
         patch("app.analytics.reaction_log.db.session.rollback",
               side_effect=RuntimeError("rollback failed")):
        assert record_reaction_event(
            channel="C042G463AQ1", message_ts="1.1", emoji="six",
            slack_uid="UFAKE0011", removed=False,
        ) is False
