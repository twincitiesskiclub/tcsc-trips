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


def _ref(kind, name, reactions=()):
    from app.practices.models import PracticeActivity, PracticeType
    model = PracticeType if kind == "type" else PracticeActivity
    row = model(name=name, default_plan_reactions=list(reactions))
    db.session.add(row)
    db.session.commit()
    return row.id


def _delete_rows(model, ids):
    db.session.rollback()
    for i in ids:
        row = db.session.get(model, i)
        if row is not None:
            db.session.delete(row)
    db.session.commit()


@pytest.fixture()
def refresh_calls(monkeypatch):
    calls = []
    monkeypatch.setattr("app.slack.practices.refresh_practice_posts",
                        lambda *a, **k: calls.append(k) or {})
    return calls


def test_save_assignment_replaces_only_lead_rows_and_writes_details(
        db_session, refresh_calls):
    from app.models import User
    from app.practices.models import (
        PracticeActivity, PracticeLead, PracticeLocation, PracticeType)

    db.session.rollback()
    users = [User(first_name=f"TEST C2 {i}", last_name="Assign",
                  email=f"test-c2-{i}@example.invalid") for i in range(3)]
    db.session.add_all(users)
    loc = PracticeLocation(name="TEST Assign Loc")
    db.session.add(loc)
    db.session.commit()
    user_ids = [u.id for u in users]
    loc_id = loc.id
    type_id = _ref("type", "TEST Assign Type")
    act_id = _ref("activity", "TEST Assign Act")
    pid = _practice(20)
    try:
        practice = db.session.get(Practice, pid)
        practice.leads.append(PracticeLead(user_id=user_ids[0], role="coach"))
        practice.leads.append(PracticeLead(user_id=user_ids[1], role="lead"))
        db.session.commit()
        blocks.save_assignment(pid, lead_ids=[user_ids[2], user_ids[2]],
                               location_id=loc_id, type_ids=[type_id],
                               activity_ids=[act_id])
        db.session.expire_all()
        practice = db.session.get(Practice, pid)
        roles = sorted((l.user_id, l.role) for l in practice.leads)
        assert roles == sorted([(user_ids[0], "coach"), (user_ids[2], "lead")])
        assert practice.location_id == loc_id
        assert [t.id for t in practice.practice_types] == [type_id]
        assert [a.id for a in practice.activities] == [act_id]
        assert practice.is_draft is False  # location + type made it visible
        assert len(refresh_calls) == 1
        assert refresh_calls[0]["change_type"] == "edit"
        assert refresh_calls[0]["notify"] is False
        assert refresh_calls[0]["announcement_notice"] == (
            "📍 Location updated, check Where below.")
        # location None keeps the existing one
        blocks.save_assignment(pid, lead_ids=[], location_id=None,
                               type_ids=[type_id], activity_ids=[act_id])
        db.session.expire_all()
        assert db.session.get(Practice, pid).location_id == loc_id
    finally:
        _cleanup([pid])
        db.session.rollback()
        _delete_rows(PracticeType, [type_id])
        _delete_rows(PracticeActivity, [act_id])
        _delete_rows(PracticeLocation, [loc_id])
        for uid in user_ids:
            u = db.session.get(User, uid)
            if u is not None:
                db.session.delete(u)
        db.session.commit()


def test_save_assignment_type_change_resets_plan_reactions_but_unchanged_keeps(
        db_session, refresh_calls):
    from app.practices.models import PracticeType

    db.session.rollback()
    old_id = _ref("type", "TEST Assign Old", [{"emoji": "snowflake", "label": "Old"}])
    new_id = _ref("type", "TEST Assign New", [{"emoji": "fire", "label": "New"}])
    pid = _practice(22)
    custom = [{"emoji": "tada", "label": "Custom"}]
    try:
        practice = db.session.get(Practice, pid)
        practice.practice_types = [db.session.get(PracticeType, old_id)]
        practice.plan_reactions = custom
        db.session.commit()
        blocks.save_assignment(pid, lead_ids=[], location_id=None,
                               type_ids=[old_id], activity_ids=[])
        db.session.expire_all()
        assert db.session.get(Practice, pid).plan_reactions == custom
        blocks.save_assignment(pid, lead_ids=[], location_id=None,
                               type_ids=[new_id], activity_ids=[])
        db.session.expire_all()
        reactions = db.session.get(Practice, pid).plan_reactions
        assert [r["emoji"] for r in reactions] == ["fire"]
        assert refresh_calls[-1]["previous_plan_reactions"] == custom
    finally:
        _cleanup([pid])
        _delete_rows(PracticeType, [old_id, new_id])


def test_validate_assignment_flags_conflicting_type_defaults(db_session):
    from app.practices.models import PracticeType

    db.session.rollback()
    a = _ref("type", "TEST Assign A", [{"emoji": "fire", "label": "One"}])
    b = _ref("type", "TEST Assign B", [{"emoji": "fire", "label": "Two"}])
    try:
        assert blocks.validate_assignment([a], []) is None
        block_id, message = blocks.validate_assignment([a, b], [])
        assert block_id == "types" and message
    finally:
        _delete_rows(PracticeType, [a, b])


def test_assign_modal_data_lists_available_first(db_session):
    from app.models import User
    from app.practices.availability_models import LeadAvailabilityResponse

    db.session.rollback()
    u = User(first_name="TEST C2", last_name="Avail", email="test-c2-av@example.invalid")
    db.session.add(u)
    db.session.commit()
    uid = u.id
    pid = _practice(21)
    starts = date(2099, 1, 19)
    try:
        assert blocks.assign_modal_data(999999999) is None
        data = blocks.assign_modal_data(pid)
        assert data["available_text"] is None and data["available"] == []
        poll = LeadAvailabilityPoll(starts_on=starts, ends_on=date(2099, 2, 1),
                                    status=PollStatus.OPEN, message_ts="1.1", channel_id="CTEST")
        db.session.add(poll)
        db.session.commit()
        db.session.add(LeadAvailabilityResponse(poll_id=poll.id, practice_id=pid, user_id=uid))
        db.session.commit()
        data = blocks.assign_modal_data(pid)
        assert data["available_text"] == "Available: TEST C2 A"
        assert [i for i, _ in data["available"]] == [uid]
        assert data["practice_id"] == pid and data["initial_ids"] == []
        assert data["location_id"] is None
        assert data["type_ids"] == [] and data["activity_ids"] == []
    finally:
        _cleanup([pid], starts_on=starts)
        db.session.rollback()
        u = db.session.get(User, uid)
        if u is not None:
            db.session.delete(u)
        db.session.commit()


def test_run_block_job_isolates_a_failing_block(db_session, monkeypatch):
    starts = [date(2099, 1, 5), date(2099, 1, 19)]
    ran = []

    def fake_ensure(start, today):
        if start == starts[0]:
            raise RuntimeError("boom")
        ran.append(start)
        return {"start": start, "posted": True}

    monkeypatch.setattr(blocks, "blocks_due", lambda today, anchor: starts)
    monkeypatch.setattr(blocks, "ensure_block", fake_ensure)
    results = blocks.run_block_job(date(2099, 1, 1))
    assert ran == [starts[1]]
    assert results[0] == {"start": starts[0], "error": "boom"}
    assert results[1]["posted"] is True


def test_wednesday_reply_does_not_need_the_block_post(db_session, slack_posts, monkeypatch):
    start = date(2099, 1, 19)
    pid = _practice(20)
    try:
        monkeypatch.setattr(blocks, "post_block_post", lambda poll: False)
        blocks.ensure_block(start, today=date(2099, 1, 15))
        assert LeadAvailabilityPoll.query.filter_by(starts_on=start).one().block_post_ts is None
        assert len(slack_posts["wed"]) == 1
    finally:
        _cleanup([pid], start)
