from datetime import date, datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy import text

from app.models import db
from app.practices import blocks
from app.practices.availability_models import LeadAvailabilityPoll
from app.practices.models import Practice
from app.slack.practices._config import COORD_CHANNEL_ID, PRACTICES_CORE_CHANNEL_ID


@pytest.fixture()
def block(db_session):
    db.session.rollback()
    practice = Practice(date=datetime(2099, 1, 20, 18, 15), day_of_week="Tuesday",
                        is_draft=True, leads_needed=2, logistics_notes="TEST b5")
    db.session.add(practice)
    db.session.commit()
    poll = blocks.create_block_poll(date(2099, 1, 19), date(2099, 2, 1))
    ids = (practice.id, poll.id)
    yield poll
    db.session.rollback()
    stored = db.session.get(LeadAvailabilityPoll, ids[1])
    if stored is not None:
        db.session.delete(stored)
    db.session.commit()
    p = db.session.get(Practice, ids[0])
    if p is not None:
        db.session.delete(p)
    db.session.commit()


@pytest.fixture()
def client(monkeypatch):
    fake = MagicMock()
    fake.chat_postMessage.return_value = {"ts": "9.000"}
    monkeypatch.setattr("app.practices.blocks.get_slack_client", lambda: fake)
    return fake


def test_post_block_post_records_the_ts(block, client):
    assert blocks.post_block_post(block) is True
    assert block.block_post_ts == "9.000"
    assert client.chat_postMessage.call_args.kwargs["channel"] == PRACTICES_CORE_CHANNEL_ID


def test_post_block_post_never_raises(block, client):
    client.chat_postMessage.side_effect = RuntimeError("slack down")
    assert blocks.post_block_post(block) is False
    assert block.block_post_ts is None


def test_refresh_updates_in_place(block, client):
    block.block_post_ts = "9.000"
    db.session.commit()
    assert blocks.refresh_block_post(block) is True
    assert client.chat_update.call_args.kwargs["ts"] == "9.000"
    assert client.chat_update.call_args.kwargs["channel"] == PRACTICES_CORE_CHANNEL_ID


def test_refresh_without_a_post_is_a_no_op(block, client):
    assert blocks.refresh_block_post(block) is False
    client.chat_update.assert_not_called()


def test_wednesday_reply_threads_and_marks_sent(block, client):
    block.block_post_ts = "9.000"
    db.session.commit()
    assert blocks.post_wednesday_reply(block) is True
    kwargs = client.chat_postMessage.call_args.kwargs
    assert kwargs["thread_ts"] == "9.000"
    assert kwargs["channel"] == PRACTICES_CORE_CHANNEL_ID
    assert "Nobody has opened the lead poll for *Jan 19 – Feb 1* yet." in str(kwargs["blocks"])
    assert "for Jan 19 – Feb 1 yet" in kwargs["text"]
    assert block.wednesday_reminder_sent_at is not None


def test_practice_edit_refreshes_its_block_post(block, client):
    from app.slack.practices.refresh import PRACTICE_SURFACES, _refresh_block_post

    block.block_post_ts = "9.000"
    db.session.commit()
    practice = Practice.query.filter_by(logistics_notes="TEST b5").one()
    assert _refresh_block_post(practice, "edit") == {"success": True}
    assert "block_post" in {surface.name for surface in PRACTICE_SURFACES}


@pytest.fixture()
def assigned(block):
    """The block after the team finished: poll closed, block post up."""
    block.status = "closed"
    block.block_post_ts = "9.000"
    db.session.commit()
    return block


def _poll(poll_id):
    db.session.expire_all()
    return db.session.get(LeadAvailabilityPoll, poll_id)


def test_post_lead_schedule_posts_once_and_drops_the_button(assigned, client):
    client.chat_postMessage.return_value = {"ts": "5.000"}
    assert blocks.post_lead_schedule(assigned.id) == {"success": True, "ts": "5.000"}
    posted = client.chat_postMessage.call_args.kwargs
    assert posted["channel"] == COORD_CHANNEL_ID
    assert "Lead schedule · Jan 19 – Feb 1" in str(posted["blocks"])
    assert _poll(assigned.id).schedule_ts == "5.000"
    block_post = [c.kwargs for c in client.chat_update.call_args_list
                  if c.kwargs["channel"] == PRACTICES_CORE_CHANNEL_ID]
    assert "block_schedule_post" not in str(block_post[-1]["blocks"])

    again = blocks.post_lead_schedule(assigned.id)
    assert again == {"success": False, "error": "The schedule is already posted."}
    assert client.chat_postMessage.call_count == 1


def test_post_lead_schedule_while_another_click_holds_the_lock(assigned, client):
    poll_id = assigned.id
    with db.engine.connect() as other:
        trans = other.begin()
        other.execute(text("SELECT id FROM lead_availability_polls WHERE id = :id FOR UPDATE"),
                      {"id": poll_id})
        result = blocks.post_lead_schedule(poll_id)
        trans.rollback()
    assert result["success"] is False
    client.chat_postMessage.assert_not_called()


def test_failed_schedule_post_can_be_retried(assigned, client):
    client.chat_postMessage.side_effect = RuntimeError("slack down")
    result = blocks.post_lead_schedule(assigned.id)
    assert result["success"] is False
    assert _poll(assigned.id).schedule_ts is None


def test_refresh_updates_the_schedule_post_once_posted(assigned, client):
    blocks.refresh_block_post(assigned)
    assert {c.kwargs["channel"] for c in client.chat_update.call_args_list} == {
        PRACTICES_CORE_CHANNEL_ID}

    assigned.schedule_ts = "5.000"
    db.session.commit()
    client.chat_update.reset_mock()
    assert blocks.refresh_block_post(assigned) is True
    updated = {c.kwargs["channel"]: c.kwargs for c in client.chat_update.call_args_list}
    assert updated[COORD_CHANNEL_ID]["ts"] == "5.000"
    assert "Lead schedule" in str(updated[COORD_CHANNEL_ID]["blocks"])
    assert updated[PRACTICES_CORE_CHANNEL_ID]["ts"] == "9.000"


def test_rows_mention_linked_leads_and_name_the_rest(block):
    from app.models import SlackUser, User
    from app.practices.models import PracticeLead

    slack = SlackUser(slack_uid="UTESTSCHED1", full_name="TEST Sched")
    linked = User(first_name="TEST Sched", last_name="Linked",
                  email="test-sched-linked@example.invalid", slack_user=slack)
    unlinked = User(first_name="TEST Sched", last_name="Plain",
                    email="test-sched-plain@example.invalid")
    db.session.add_all([linked, unlinked])
    db.session.commit()
    ids = (linked.id, unlinked.id, slack.id)
    try:
        practice = Practice.query.filter_by(logistics_notes="TEST b5").one()
        practice.leads.append(PracticeLead(user_id=ids[0], role="lead"))
        practice.leads.append(PracticeLead(user_id=ids[1], role="lead"))
        db.session.commit()
        row = blocks.block_post_rows(block)[0]
        assert row["lead_mentions"] == ["<@UTESTSCHED1>", "TEST Sched P"]
        assert row["leads"] == ["TEST Sched L", "TEST Sched P"]
    finally:
        db.session.rollback()
        for lead in PracticeLead.query.filter(PracticeLead.user_id.in_(ids[:2])).all():
            db.session.delete(lead)
        db.session.commit()
        for model, i in ((User, ids[0]), (User, ids[1]), (SlackUser, ids[2])):
            row = db.session.get(model, i)
            if row is not None:
                db.session.delete(row)
            db.session.commit()
