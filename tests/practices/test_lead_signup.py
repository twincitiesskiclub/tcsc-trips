"""The Lead button: anyone in the lead pool takes an open spot.

Real local DB; year 2099 dates; see tests/practices/conftest.py.
"""

from datetime import date, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.models import SlackUser, Tag, User, db
from app.practices import blocks
from app.practices.availability_models import LeadAvailabilityPoll
from app.practices.interfaces import PracticeStatus
from app.practices.models import Practice, PracticeLead

START, END = date(2099, 1, 19), date(2099, 2, 1)


def _user(name, *, in_pool=True, slack=True):
    suffix = uuid4().hex[:10]
    su = SlackUser(slack_uid=f"TEST-SIGNUP-{suffix}") if slack else None
    user = User(first_name=f"TEST {name}", last_name="Signup",
                email=f"test-signup-{suffix}@example.invalid", slack_user=su)
    if in_pool:
        tag = Tag.query.filter_by(name="PRACTICES_LEAD").first() or Tag(
            name="PRACTICES_LEAD", display_name="Practices Lead")
        user.tags = [tag]
    db.session.add(user)
    db.session.commit()
    return user.id, (su.slack_uid if su else None), (su.id if su else None)


@pytest.fixture()
def env(db_session, monkeypatch):
    """A 2099 practice in a block whose schedule is posted, plus patched Slack."""
    db.session.rollback()
    practice = Practice(date=datetime(2099, 1, 20, 18, 15), day_of_week="Tuesday",
                        is_draft=False, leads_needed=2, logistics_notes="TEST signup")
    db.session.add(practice)
    db.session.commit()
    poll = blocks.create_block_poll(START, END)
    poll.schedule_ts = "7.000"
    db.session.commit()
    refreshes = []
    monkeypatch.setattr("app.slack.practices.refresh_practice_posts",
                        lambda p, **kw: refreshes.append((p.id, kw)) or {})
    client = MagicMock()
    monkeypatch.setattr(blocks, "get_slack_client", lambda: client)
    monkeypatch.setattr(blocks, "now_central_naive", lambda: datetime(2099, 1, 1, 9, 0))
    made = {"users": [], "slack": []}

    def user(name, **kw):
        uid, slack_uid, sid = _user(name, **kw)
        made["users"].append(uid)
        if sid:
            made["slack"].append(sid)
        return uid, slack_uid

    pid = practice.id
    yield {"pid": pid, "client": client, "refreshes": refreshes, "user": user}
    db.session.rollback()
    for lead in PracticeLead.query.filter_by(practice_id=pid).all():
        db.session.delete(lead)
    p = db.session.get(Practice, pid)
    if p is not None:
        db.session.delete(p)
    for poll in LeadAvailabilityPoll.query.filter_by(starts_on=START).all():
        db.session.delete(poll)
    db.session.commit()
    for uid in made["users"]:
        u = db.session.get(User, uid)
        if u is not None:
            db.session.delete(u)
    db.session.commit()
    for sid in made["slack"]:
        s = db.session.get(SlackUser, sid)
        if s is not None:
            db.session.delete(s)
    db.session.commit()


def _leads(pid):
    db.session.expire_all()
    return sorted((l.user_id, l.role) for l in db.session.get(Practice, pid).leads)


def _add(pid, uid, role="lead"):
    db.session.get(Practice, pid).leads.append(PracticeLead(user_id=uid, role=role))
    db.session.commit()


def test_sign_up_adds_refreshes_and_thanks_in_the_thread(env):
    pid = env["pid"]
    partner, partner_slack = env["user"]("Partner")
    _add(pid, partner)
    uid, slack_uid = env["user"]("Mike")
    assert blocks.sign_up_as_lead(pid, slack_uid) == {"success": True}
    assert _leads(pid) == sorted([(partner, "lead"), (uid, "lead")])
    assert env["refreshes"] == [(pid, {"change_type": "edit", "notify": False})]
    reply = env["client"].chat_postMessage.call_args.kwargs
    assert reply["thread_ts"] == "7.000"
    assert reply["text"] == (f":raised_hands: <@{slack_uid}> is leading Tue 1/20 · 6:15p "
                             f"with <@{partner_slack}>")


def test_first_sign_up_has_no_with(env):
    uid, slack_uid = env["user"]("Solo")
    blocks.sign_up_as_lead(env["pid"], slack_uid)
    assert env["client"].chat_postMessage.call_args.kwargs["text"] == (
        f":raised_hands: <@{slack_uid}> is leading Tue 1/20 · 6:15p")


def test_outside_the_pool_or_unlinked_is_refused(env):
    _, slack_uid = env["user"]("Outsider", in_pool=False)
    for who in (slack_uid, "UNKNOWN-TEST-UID"):
        result = blocks.sign_up_as_lead(env["pid"], who)
        assert result == {"success": False, "error":
                          "Leading is open to the lead pool. Want in? Ask in this thread."}
    assert _leads(env["pid"]) == []
    env["client"].chat_postMessage.assert_not_called()


def test_already_on_it_in_any_role(env):
    uid, slack_uid = env["user"]("Coach")
    _add(env["pid"], uid, role="coach")
    assert blocks.sign_up_as_lead(env["pid"], slack_uid) == {
        "success": False, "error": "You're already on it."}


def test_full_session_is_refused(env):
    pid = env["pid"]
    for name in ("One", "Two"):
        _add(pid, env["user"](name)[0])
    _, slack_uid = env["user"]("Late")
    assert blocks.sign_up_as_lead(pid, slack_uid) == {
        "success": False, "error": "Just filled, thanks!"}


def test_leads_needed_one_fills_with_one(env):
    pid = env["pid"]
    db.session.get(Practice, pid).leads_needed = 1
    db.session.commit()
    _, first = env["user"]("First")
    _, second = env["user"]("Second")
    assert blocks.sign_up_as_lead(pid, first)["success"] is True
    assert blocks.sign_up_as_lead(pid, second)["error"] == "Just filled, thanks!"


def test_cancelled_started_or_gone_is_refused(env, monkeypatch):
    pid = env["pid"]
    _, slack_uid = env["user"]("Eager")
    practice = db.session.get(Practice, pid)
    practice.status = PracticeStatus.CANCELLED.value
    db.session.commit()
    assert blocks.sign_up_as_lead(pid, slack_uid)["error"] == "That practice was cancelled."
    practice = db.session.get(Practice, pid)
    practice.status = PracticeStatus.SCHEDULED.value
    db.session.commit()
    monkeypatch.setattr(blocks, "now_central_naive", lambda: datetime(2099, 1, 20, 18, 15))
    assert blocks.sign_up_as_lead(pid, slack_uid)["error"] == "That practice already started."
    assert blocks.sign_up_as_lead(999999999, slack_uid)["error"] == "That practice is gone."
    assert _leads(pid) == []


def test_a_held_lock_is_refused(env):
    pid = env["pid"]
    _, slack_uid = env["user"]("Racer")
    with db.engine.connect() as other:
        trans = other.begin()
        other.execute(text("SELECT id FROM practices WHERE id = :id FOR UPDATE"), {"id": pid})
        result = blocks.sign_up_as_lead(pid, slack_uid)
        trans.rollback()
    assert result == {"success": False,
                      "error": "Someone just signed up. Try again in a second."}
    assert _leads(pid) == []


def test_failed_thread_reply_keeps_the_sign_up(env):
    env["client"].chat_postMessage.side_effect = RuntimeError("slack down")
    uid, slack_uid = env["user"]("Kept")
    assert blocks.sign_up_as_lead(env["pid"], slack_uid) == {"success": True}
    assert _leads(env["pid"]) == [(uid, "lead")]


def test_no_reply_before_the_schedule_is_posted(env):
    poll = LeadAvailabilityPoll.query.filter_by(starts_on=START).one()
    poll.schedule_ts = None
    db.session.commit()
    _, slack_uid = env["user"]("Early")
    assert blocks.sign_up_as_lead(env["pid"], slack_uid) == {"success": True}
    env["client"].chat_postMessage.assert_not_called()
