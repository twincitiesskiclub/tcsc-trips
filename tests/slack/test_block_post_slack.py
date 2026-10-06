from datetime import date, datetime
from unittest.mock import MagicMock

import pytest

from app.models import db
from app.practices import blocks
from app.practices.availability_models import LeadAvailabilityPoll
from app.practices.models import Practice
from app.slack.practices._config import PRACTICES_CORE_CHANNEL_ID


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
