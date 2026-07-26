"""Admin poll trigger and shadow-mode routing."""

import uuid
from datetime import datetime
from unittest.mock import patch

import pytest

from app.models import AppConfig, db
from app.practices.availability import PollNotReadyError
from app.practices.availability_models import LeadAvailabilityPoll
from app.practices.models import Practice, PracticeLocation, PracticeType
from app.slack.practices._config import COORD_CHANNEL_ID

_SHADOW_MODE_KEY = "lead_availability.shadow_mode"
_SHADOW_CHANNEL_ID = "C0B3Y71PG92"
# A date range not touched by any other suite (test_availability_service.py
# and friends use Aug 2099) so this module's DB assertions can't collide with
# another test's in-flight fixture data.
_DEFAULT_TEST_START = "2099-09-01"
_DEFAULT_TEST_END = "2099-09-30"


@pytest.fixture(autouse=True)
def _restore_shadow_mode_config(db_session):
    """Save and restore the shadow-mode AppConfig row this module writes.

    `test_create_uses_shadow_flag_from_config` (and the default/explicit
    tests below) set a real AppConfig key (not a "TEST "-prefixed throwaway
    row) because that key is exactly what production reads. An unconditional
    delete after every test -- the previous behavior here -- would silently
    reset real shadow-mode configuration in the dev database every time this
    module ran, regardless of what a human had actually configured. Capture
    whatever was there before the test (if anything) and put it back exactly,
    deleting only if there was no row to begin with. Per
    tests/practices/conftest.py's cleanup convention: rollback first, since
    an assertion failure above can leave the session poisoned.
    """
    db.session.rollback()
    existing = AppConfig.query.filter_by(key=_SHADOW_MODE_KEY).first()
    had_row = existing is not None
    original = (
        (existing.value, existing.description, existing.category)
        if had_row else None
    )
    yield
    db.session.rollback()
    if had_row:
        value, description, category = original
        AppConfig.set(key=_SHADOW_MODE_KEY, value=value,
                      description=description, category=category)
    else:
        AppConfig.query.filter_by(key=_SHADOW_MODE_KEY).delete()
    db.session.commit()


def test_create_reports_incomplete_drafts_as_a_400(admin_client):
    with patch("app.routes.admin_availability.build_poll",
               side_effect=PollNotReadyError("Tue 8/11 needs location")):
        response = admin_client.post("/admin/availability/polls/create", json={
            "starts_on": "2026-08-01", "ends_on": "2026-08-31",
        })

    assert response.status_code == 400
    assert "needs location" in response.get_json()["error"]


def test_create_uses_shadow_flag_from_config(admin_client, db_session):
    AppConfig.set(key="lead_availability.shadow_mode", value=True,
                  description="t", category="practices")
    db.session.commit()

    with patch("app.routes.admin_availability.build_poll") as build:
        build.return_value = type(
            "P", (), {"id": 7, "channel_id": _SHADOW_CHANNEL_ID, "is_shadow": True})()
        admin_client.post("/admin/availability/polls/create", json={
            "starts_on": "2026-08-01", "ends_on": "2026-08-31",
        })

    assert build.call_args.kwargs["is_shadow"] is True


def _ready_practice_range():
    """One complete draft practice so build_poll() succeeds end-to-end."""
    suffix = uuid.uuid4().hex[:8]
    location = PracticeLocation(name=f"TEST Shadow Default Location {suffix}")
    ptype = PracticeType(name=f"TEST Shadow Default Type {suffix}")
    db.session.add_all([location, ptype])
    db.session.flush()
    practice = Practice(
        date=datetime(2099, 9, 8, 18, 15), day_of_week="Tuesday",
        is_draft=True, location_id=location.id,
    )
    practice.practice_types = [ptype]
    db.session.add(practice)
    db.session.commit()
    return practice, location, ptype


def _cleanup_ready_practice_range(practice, location, ptype, poll_id=None):
    db.session.rollback()
    if poll_id is not None:
        poll = db.session.get(LeadAvailabilityPoll, poll_id)
        if poll is not None:
            db.session.delete(poll)
        db.session.flush()
    stored_practice = db.session.get(Practice, practice.id)
    if stored_practice is not None:
        db.session.delete(stored_practice)
    db.session.flush()
    stored_type = db.session.get(PracticeType, ptype.id)
    if stored_type is not None:
        db.session.delete(stored_type)
    stored_location = db.session.get(PracticeLocation, location.id)
    if stored_location is not None:
        db.session.delete(stored_location)
    db.session.commit()


def test_create_defaults_to_shadow_channel_with_no_config_row(admin_client, db_session):
    """Fix 1: an unset shadow_mode key must resolve to the shadow channel,
    never the live 64-member channel -- there is no UI that writes this key,
    so "unset" is the state of every environment today.

    This test forces the "no row" state itself rather than asserting it as a
    precondition: the surrounding module-level fixture already captured
    whatever was really in the dev database before this test body ran (see
    `_restore_shadow_mode_config` above) and will put it back afterward, so
    deleting it here for the duration of this test is safe -- and it keeps
    this test correct even if a real config row exists when the suite runs.
    """
    AppConfig.query.filter_by(key=_SHADOW_MODE_KEY).delete()
    db.session.commit()
    practice, location, ptype = _ready_practice_range()
    poll_id = None
    try:
        response = admin_client.post("/admin/availability/polls/create", json={
            "starts_on": _DEFAULT_TEST_START, "ends_on": _DEFAULT_TEST_END,
        })
        body = response.get_json()
        assert body["success"] is True
        poll_id = body["poll_id"]
        assert body["is_shadow"] is True
        assert body["channel_id"] == _SHADOW_CHANNEL_ID
    finally:
        _cleanup_ready_practice_range(practice, location, ptype, poll_id)


def test_create_explicit_false_resolves_to_live_channel(admin_client, db_session):
    """An explicit `False` row is a deliberate act, so it must still route to
    the real coordination channel."""
    AppConfig.set(key=_SHADOW_MODE_KEY, value=False, description="t",
                  category="practices")
    db.session.commit()
    practice, location, ptype = _ready_practice_range()
    poll_id = None
    try:
        response = admin_client.post("/admin/availability/polls/create", json={
            "starts_on": _DEFAULT_TEST_START, "ends_on": _DEFAULT_TEST_END,
        })
        body = response.get_json()
        assert body["success"] is True
        poll_id = body["poll_id"]
        assert body["is_shadow"] is False
        assert body["channel_id"] == COORD_CHANNEL_ID
    finally:
        _cleanup_ready_practice_range(practice, location, ptype, poll_id)


def test_open_surfaces_missing_emoji_to_the_director(admin_client):
    with patch("app.routes.admin_availability.LeadAvailabilityPoll") as model, \
         patch("app.routes.admin_availability.open_poll") as opener:
        model.query.get_or_404.return_value = object()
        opener.return_value = {"success": False, "error": "missing workspace emoji letter_c"}
        response = admin_client.post("/admin/availability/polls/1/open")

    assert response.status_code == 400
    assert "letter_c" in response.get_json()["error"]
