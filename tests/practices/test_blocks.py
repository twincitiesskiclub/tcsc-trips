"""Two-week blocks: anchor math, the daily block job, opening a poll.

Real local DB; year 2099 dates; see tests/practices/conftest.py.
"""

from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import text

from app.models import AppConfig, db
from app.practices import blocks
from app.practices.availability_models import LeadAvailabilityPoll, PollStatus
from app.practices.models import Practice

ANCHOR = date(2099, 1, 5)  # a Monday


def test_block_start_for_is_stable_across_dst_and_new_year():
    anchor = date(2026, 10, 26)
    assert blocks.block_start_for(date(2026, 11, 1), anchor) == date(2026, 10, 26)   # DST ends
    assert blocks.block_start_for(date(2026, 11, 9), anchor) == date(2026, 11, 9)
    assert blocks.block_start_for(date(2027, 1, 3), anchor) == date(2026, 12, 21)
    assert blocks.block_start_for(date(2027, 1, 4), anchor) == date(2027, 1, 4)


def test_blocks_due_from_the_post_day_on():
    anchor = date(2026, 10, 26)
    assert blocks.blocks_due(date(2026, 10, 18), anchor) == []                       # Sun before post day
    assert blocks.blocks_due(date(2026, 10, 19), anchor) == [date(2026, 10, 26)]     # post day
    assert blocks.blocks_due(date(2026, 10, 20), anchor) == [date(2026, 10, 26)]     # missed Monday
    assert blocks.blocks_due(date(2026, 11, 2), anchor) == [date(2026, 10, 26), date(2026, 11, 9)]


def test_no_block_before_the_anchor():
    """Deploy lands mid Oct 12-25: that block is the cutover script's job."""
    assert blocks.blocks_due(date(2026, 10, 14), date(2026, 10, 26)) == []


def test_block_anchor_reads_appconfig_and_falls_back(db_session):
    key = "lead_availability.block_anchor"
    row = AppConfig.query.filter_by(key=key).first()
    existed = row is not None
    original = row.value if existed else None
    try:
        AppConfig.set(key, "2099-01-05")
        db.session.commit()
        assert blocks.block_anchor() == date(2099, 1, 5)
        AppConfig.set(key, "not a date")
        db.session.commit()
        assert blocks.block_anchor() == blocks.DEFAULT_ANCHOR
    finally:
        db.session.rollback()
        row = AppConfig.query.filter_by(key=key).first()
        if existed:
            row.value = original
        elif row is not None:
            db.session.delete(row)
        db.session.commit()


def _practice(day, hour=18, minute=15, *, is_draft=True):
    p = Practice(date=datetime(2099, 1, day, hour, minute),
                 day_of_week=datetime(2099, 1, day).strftime("%A"),
                 is_draft=is_draft, leads_needed=2, logistics_notes="TEST blocks")
    db.session.add(p)
    db.session.commit()
    return p.id


def _cleanup(practice_ids=(), starts_on=None):
    db.session.rollback()
    if starts_on is not None:
        for poll in LeadAvailabilityPoll.query.filter_by(starts_on=starts_on).all():
            db.session.delete(poll)
        db.session.commit()
    for pid in practice_ids:
        p = db.session.get(Practice, pid)
        if p is not None:
            db.session.delete(p)
    db.session.commit()


@pytest.fixture()
def slack_posts(monkeypatch):
    calls = {"post": [], "wed": []}

    def fake_post(poll):
        calls["post"].append(poll.id)
        poll.block_post_ts = "1.000"
        db.session.commit()
        return True

    def fake_wed(poll):
        calls["wed"].append(poll.id)
        poll.wednesday_reminder_sent_at = datetime(2099, 1, 1)
        db.session.commit()
        return True

    monkeypatch.setattr(blocks, "post_block_post", fake_post)
    monkeypatch.setattr(blocks, "post_wednesday_reply", fake_wed)
    monkeypatch.setattr(blocks, "refresh_block_post", lambda poll, **k: True)
    monkeypatch.setattr(blocks, "generate_draft_block", lambda s, e: [])
    return calls


def test_existing_drafts_still_get_a_block_post(db_session, slack_posts):
    """generate_draft_block returns [] when sessions already exist (prod on Oct 19)."""
    start = date(2099, 1, 19)
    pid = _practice(20)
    try:
        result = blocks.ensure_block(start, today=date(2099, 1, 12))
        poll = LeadAvailabilityPoll.query.filter_by(starts_on=start).one()
        assert poll.status == PollStatus.DRAFT
        assert poll.block_post_ts == "1.000"
        assert result["posted"] is True
    finally:
        _cleanup([pid], start)


def test_ensure_block_is_idempotent(db_session, slack_posts):
    start = date(2099, 1, 19)
    pid = _practice(20)
    try:
        blocks.ensure_block(start, today=date(2099, 1, 12))
        blocks.ensure_block(start, today=date(2099, 1, 13))
        assert len(slack_posts["post"]) == 1
        assert LeadAvailabilityPoll.query.filter_by(starts_on=start).count() == 1
    finally:
        _cleanup([pid], start)


def test_failed_block_post_is_retried_next_run(db_session, slack_posts, monkeypatch):
    start = date(2099, 1, 19)
    pid = _practice(20)
    try:
        monkeypatch.setattr(blocks, "post_block_post", lambda poll: False)
        blocks.ensure_block(start, today=date(2099, 1, 12))
        assert LeadAvailabilityPoll.query.filter_by(starts_on=start).one().block_post_ts is None
        monkeypatch.undo()
        calls = []
        monkeypatch.setattr(blocks, "post_block_post", lambda poll: calls.append(poll.id) or True)
        monkeypatch.setattr(blocks, "generate_draft_block", lambda s, e: [])
        monkeypatch.setattr(blocks, "post_wednesday_reply", lambda poll: True)
        blocks.ensure_block(start, today=date(2099, 1, 13))
        assert calls
    finally:
        _cleanup([pid], start)


def test_no_sessions_means_no_post(db_session, slack_posts):
    start = date(2099, 2, 2)
    try:
        result = blocks.ensure_block(start, today=date(2099, 1, 26))
        assert result.get("skipped") == "no_sessions"
        assert LeadAvailabilityPoll.query.filter_by(starts_on=start).count() == 0
    finally:
        _cleanup((), start)


def test_wednesday_reply_once_and_after_a_missed_wednesday(db_session, slack_posts):
    start = date(2099, 1, 19)
    pid = _practice(20)
    try:
        blocks.ensure_block(start, today=date(2099, 1, 12))      # Mon: post only
        assert slack_posts["wed"] == []
        blocks.ensure_block(start, today=date(2099, 1, 15))      # Thu: missed Wed, still sent
        blocks.ensure_block(start, today=date(2099, 1, 16))      # Fri: not again
        assert len(slack_posts["wed"]) == 1
    finally:
        _cleanup([pid], start)


def test_no_wednesday_reply_once_opened(db_session, slack_posts):
    start = date(2099, 1, 19)
    pid = _practice(20)
    try:
        blocks.ensure_block(start, today=date(2099, 1, 12))
        poll = LeadAvailabilityPoll.query.filter_by(starts_on=start).one()
        poll.status = PollStatus.OPEN
        db.session.commit()
        blocks.ensure_block(start, today=date(2099, 1, 14))
        assert slack_posts["wed"] == []
    finally:
        _cleanup([pid], start)


@pytest.fixture()
def fake_open(monkeypatch):
    def fake(poll):
        poll.status = PollStatus.OPEN
        poll.message_ts = "2.000"
        db.session.commit()
        return {"success": True, "poll_id": poll.id, "ts": "2.000"}

    monkeypatch.setattr(blocks, "open_poll", fake)
    monkeypatch.setattr(blocks, "refresh_block_post", lambda poll, **k: True)


def test_open_block_poll_maps_and_records_the_opener(db_session, fake_open):
    start = date(2099, 1, 19)
    pids = [_practice(20), _practice(22, is_draft=False)]
    try:
        poll = blocks.create_block_poll(start, date(2099, 2, 1))
        result = blocks.open_block_poll(poll.id, "U0OPENER")
        assert result["success"] is True
        db.session.expire_all()
        poll = db.session.get(LeadAvailabilityPoll, poll.id)
        assert poll.opened_by_slack_uid == "U0OPENER"
        assert [m.practice_id for m in poll.practices] == pids
    finally:
        _cleanup(pids, start)


def test_second_open_is_refused_and_names_the_opener(db_session, fake_open):
    start = date(2099, 1, 19)
    pids = [_practice(20)]
    try:
        poll = blocks.create_block_poll(start, date(2099, 2, 1))
        blocks.open_block_poll(poll.id, "U0FIRST")
        again = blocks.open_block_poll(poll.id, "U0SECOND")
        assert again["success"] is False
        assert "<@U0FIRST>" in again["error"]
    finally:
        _cleanup(pids, start)


def test_open_while_another_open_holds_the_lock_is_refused(db_session, fake_open):
    start = date(2099, 1, 19)
    pids = [_practice(20)]
    try:
        poll = blocks.create_block_poll(start, date(2099, 2, 1))
        poll_id = poll.id
        with db.engine.connect() as other:
            trans = other.begin()
            other.execute(text(
                "SELECT id FROM lead_availability_polls WHERE id = :id FOR UPDATE"),
                {"id": poll_id})
            result = blocks.open_block_poll(poll_id, "U0SECOND")
            trans.rollback()
        assert result["success"] is False
        assert db.session.get(LeadAvailabilityPoll, poll_id).status == PollStatus.DRAFT
    finally:
        _cleanup(pids, start)


def test_failed_open_leaves_the_poll_draft(db_session, monkeypatch):
    start = date(2099, 1, 19)
    pids = [_practice(20)]
    monkeypatch.setattr(blocks, "open_poll", lambda poll: {"success": False, "error": "boom"})
    monkeypatch.setattr(blocks, "refresh_block_post", lambda poll, **k: True)
    try:
        poll = blocks.create_block_poll(start, date(2099, 2, 1))
        result = blocks.open_block_poll(poll.id, "U0X")
        assert result == {"success": False, "error": "boom"}
        db.session.expire_all()
        poll = db.session.get(LeadAvailabilityPoll, poll.id)
        assert poll.status == PollStatus.DRAFT
        assert poll.practices == []
    finally:
        _cleanup(pids, start)


def test_open_sees_status_committed_by_another_connection(db_session, fake_open):
    """A poll already loaded in this session must be refreshed under the lock."""
    start = date(2099, 1, 19)
    pids = [_practice(20)]
    try:
        poll = blocks.create_block_poll(start, date(2099, 2, 1))
        poll_id = poll.id
        assert db.session.get(LeadAvailabilityPoll, poll_id).status == PollStatus.DRAFT
        with db.engine.begin() as other:
            other.execute(text(
                "UPDATE lead_availability_polls SET status='open', "
                "opened_by_slack_uid='U0FIRST' WHERE id=:id"), {"id": poll_id})
        result = blocks.open_block_poll(poll_id, "U0SECOND")
        assert result["success"] is False
        assert "<@U0FIRST>" in result["error"]
    finally:
        _cleanup(pids, start)


def test_reminder_days_follow_the_nudge_rules():
    opened = datetime(2099, 1, 12, 19, 0)  # Mon evening
    assert blocks.reminder_days(opened, date(2099, 2, 1), date(2099, 1, 12)) == [
        date(2099, 1, 15), date(2099, 1, 17), date(2099, 1, 19)]
    assert blocks.reminder_days(opened, date(2099, 2, 1), date(2099, 1, 17)) == [
        date(2099, 1, 19)]
    assert blocks.reminder_days(opened, date(2099, 2, 1), date(2099, 1, 19)) == []
    # A Wednesday open
    wed = datetime(2099, 1, 14, 9, 0)
    assert blocks.reminder_days(wed, date(2099, 2, 1), date(2099, 1, 14)) == [
        date(2099, 1, 17), date(2099, 1, 19), date(2099, 1, 21)]
