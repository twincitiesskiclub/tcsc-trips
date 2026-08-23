"""Slack backfill for the volunteer-interest question: blocks, eligibility,
sending, and submit handling."""
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app import create_app
from app.constants import UserSeasonStatus
from app.models import db, Season, SlackUser, User, UserSeason
from app.slack.blocks.volunteer import (
    build_volunteer_ask_blocks,
    build_volunteer_thanks_blocks,
)
from app.slack.volunteer_backfill import (
    backfill_stats,
    eligible_members,
    process_volunteer_submit,
    send_backfill_asks,
)

EMAILS = ("volbf-a@test.com", "volbf-b@test.com",
          "volbf-c@test.com", "volbf-d@test.com")


# --- Blocks ---

def test_ask_blocks_have_form_elements():
    blocks = build_volunteer_ask_blocks("Sam", 42)
    flat = str(blocks)
    assert "Hey Sam!" in flat
    checkboxes = [e for b in blocks if b.get("type") == "actions"
                  for e in b["elements"] if e["type"] == "checkboxes"]
    assert len(checkboxes) == 1
    assert [o["value"] for o in checkboxes[0]["options"]] == [
        "practice_lead", "event_volunteer", "committee"]
    selects = [e for b in blocks if b.get("type") == "actions"
               for e in b["elements"] if e["type"] == "multi_static_select"]
    assert len(selects) == 1
    buttons = [e for b in blocks if b.get("type") == "actions"
               for e in b["elements"] if e["type"] == "button"]
    assert buttons[0]["value"] == "42"


def test_ask_blocks_error_variant_preserves_picks():
    blocks = build_volunteer_ask_blocks(
        "Sam", 42, error="You picked Join a committee. Which one(s)?",
        selected_interests=["committee"], selected_committees=[])
    flat = str(blocks)
    assert "Which one(s)?" in flat
    checkboxes = [e for b in blocks if b.get("type") == "actions"
                  for e in b["elements"] if e["type"] == "checkboxes"][0]
    assert [o["value"] for o in checkboxes.get("initial_options", [])] == ["committee"]


def test_thanks_blocks_name_the_picks():
    blocks = build_volunteer_thanks_blocks(
        "Sam", ["event_volunteer", "committee"], ["social"])
    flat = str(blocks)
    assert "Thanks, Sam!" in flat
    assert "Volunteer at an event" in flat
    assert "Social" in flat


# --- DB-backed: eligibility, send, submit ---

@pytest.fixture
def fixtures(app):
    with app.app_context():
        s = Season(name="VolBF Test", year=2095, price_cents=15000,
                   season_type="winter",
                   start_date=date(2095, 11, 1), end_date=date(2096, 3, 1))
        db.session.add(s)
        slack_a = SlackUser(slack_uid="UVOLA")
        slack_b = SlackUser(slack_uid="UVOLB")
        slack_d = SlackUser(slack_uid="UVOLD")
        db.session.add_all([slack_a, slack_b, slack_d])
        db.session.commit()

        # a: no answer, linked Slack -> eligible
        a = User(email=EMAILS[0], first_name="Aay", last_name="Vol",
                 slack_user_id=slack_a.id)
        # b: already answered -> not eligible
        b = User(email=EMAILS[1], first_name="Bee", last_name="Vol",
                 slack_user_id=slack_b.id)
        # c: no Slack link -> counted but not DMable
        c = User(email=EMAILS[2], first_name="Cee", last_name="Vol")
        # d: asked an hour ago -> skipped by cooldown
        d = User(email=EMAILS[3], first_name="Dee", last_name="Vol",
                 slack_user_id=slack_d.id)
        db.session.add_all([a, b, c, d])
        db.session.commit()

        def us(user, **kw):
            return UserSeason(user_id=user.id, season_id=s.id,
                              registration_type="new",
                              registration_date=date(2095, 10, 1),
                              status=UserSeasonStatus.ACTIVE, **kw)

        db.session.add_all([
            us(a),
            us(b, volunteer_interests=["practice_lead"],
               volunteer_committees=[]),
            us(c),
            us(d, volunteer_asked_at=datetime.utcnow() - timedelta(hours=1)),
        ])
        db.session.commit()
        ids = {"season_id": s.id,
               "a": a.id, "b": b.id, "c": c.id, "d": d.id}
        yield ids
        db.session.rollback()
        UserSeason.query.filter_by(season_id=s.id).delete()
        for email in EMAILS:
            u = User.query.filter_by(email=email).one_or_none()
            if u:
                db.session.delete(u)
        for uid in ("UVOLA", "UVOLB", "UVOLD"):
            su = SlackUser.query.filter_by(slack_uid=uid).one_or_none()
            if su:
                db.session.delete(su)
        db.session.delete(Season.query.get(s.id))
        db.session.commit()


def test_eligible_members_filters_correctly(app, fixtures):
    with app.app_context():
        rows = eligible_members(fixtures["season_id"])
        assert [u.id for u, su in rows] == [fixtures["a"]]


def test_backfill_stats_counts(app, fixtures):
    with app.app_context():
        stats = backfill_stats(fixtures["season_id"])
        assert stats["eligible"] == 1
        assert stats["no_slack"] == 1
        assert stats["cooldown"] == 1


def test_send_backfill_asks_dms_and_stamps(app, fixtures):
    client = MagicMock()
    with app.app_context():
        with patch("app.slack.volunteer_backfill.get_slack_client",
                   return_value=client):
            result = send_backfill_asks(fixtures["season_id"])
        assert result["sent"] == 1
        assert result["failed"] == 0
        assert client.chat_postMessage.call_count == 1
        assert client.chat_postMessage.call_args.kwargs["channel"] == "UVOLA"
        stamped = UserSeason.get_for_user_season(
            fixtures["a"], fixtures["season_id"])
        assert stamped.volunteer_asked_at is not None
        # Stamped members are no longer eligible for a re-send
        assert eligible_members(fixtures["season_id"]) == []


def _state(interests, committees):
    return {
        "volunteer_interests_block": {
            "volunteer_interests_input": {
                "selected_options": [{"value": v} for v in interests]}},
        "volunteer_committees_block": {
            "volunteer_committees_input": {
                "selected_options": [{"value": v} for v in committees]}},
    }


def test_submit_writes_answer(app, fixtures):
    with app.app_context():
        result = process_volunteer_submit(
            "UVOLA", fixtures["season_id"],
            _state(["event_volunteer", "committee"], ["social"]))
        assert result["ok"] is True
        assert result["first_name"] == "Aay"
        us = UserSeason.get_for_user_season(
            fixtures["a"], fixtures["season_id"])
        assert us.volunteer_interests == ["event_volunteer", "committee"]
        assert us.volunteer_committees == ["social"]


def test_submit_requires_a_pick(app, fixtures):
    with app.app_context():
        result = process_volunteer_submit(
            "UVOLA", fixtures["season_id"], _state([], []))
        assert result["ok"] is False
        assert "at least one" in result["error"].lower()
        us = UserSeason.get_for_user_season(
            fixtures["a"], fixtures["season_id"])
        assert us.volunteer_interests is None


def test_submit_unknown_slack_user(app, fixtures):
    with app.app_context():
        result = process_volunteer_submit(
            "UNOBODY", fixtures["season_id"], _state(["practice_lead"], []))
        assert result["ok"] is False


# --- Admin endpoints ---

@pytest.fixture
def admin_client(app):
    app.config["WTF_CSRF_ENABLED"] = False
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["user"] = {"email": "admin@twincitiesskiclub.org"}
    return c


def test_preview_endpoint_returns_stats(admin_client, fixtures):
    resp = admin_client.get(
        f"/admin/seasons/{fixtures['season_id']}/volunteer-ask/preview")
    assert resp.status_code == 200
    assert resp.get_json() == {"eligible": 1, "no_slack": 1, "cooldown": 1}


def test_send_endpoint_sends(admin_client, fixtures):
    client = MagicMock()
    with patch("app.slack.volunteer_backfill.get_slack_client",
               return_value=client):
        resp = admin_client.post(
            f"/admin/seasons/{fixtures['season_id']}/volunteer-ask")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["sent"] == 1
    assert client.chat_postMessage.call_count == 1
