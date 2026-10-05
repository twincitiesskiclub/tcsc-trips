"""Admin poll trigger."""

import uuid
from datetime import datetime
from unittest.mock import patch

from app.models import db
from app.practices.availability import PollNotReadyError
from app.practices.availability_emoji import EmojiSupplyError
from app.practices.availability_models import LeadAvailabilityPoll
from app.practices.models import Practice, PracticeLocation, PracticeType
from app.slack.practices._config import COORD_CHANNEL_ID

# A date range not touched by any other suite (test_availability_service.py
# and friends use Aug 2099) so this module's DB assertions can't collide with
# another test's in-flight fixture data.
_DEFAULT_TEST_START = "2099-09-01"
_DEFAULT_TEST_END = "2099-09-30"


def test_create_reports_incomplete_drafts_as_a_400(admin_client):
    with patch("app.routes.admin_availability.create_block_poll",
               side_effect=PollNotReadyError("Tue 8/11 needs location")):
        response = admin_client.post("/admin/availability/polls/create", json={
            "starts_on": "2026-08-01", "ends_on": "2026-08-31",
        })

    assert response.status_code == 400
    assert "needs location" in response.get_json()["error"]


def test_create_reports_emoji_shortage_as_a_400(admin_client):
    """Too many sessions for the configured letters is a 4xx, not a 500.

    A 500 tells the director nothing; the message names the actual fix (add
    letters to config/practices.yaml, or split the block), so it has to reach
    them instead of being swallowed by the generic error handler.
    """
    with patch("app.routes.admin_availability.create_block_poll",
               side_effect=EmojiSupplyError(
                   "poll needs 30 distinct emoji but only 26 are configured")):
        response = admin_client.post("/admin/availability/polls/create", json={
            "starts_on": "2026-08-01", "ends_on": "2026-10-31",
        })

    assert response.status_code == 400
    assert "only 26 are configured" in response.get_json()["error"]


def _ready_practice_range():
    """One complete draft practice so create_block_poll() + map_sessions() succeeds end-to-end."""
    suffix = uuid.uuid4().hex[:8]
    location = PracticeLocation(name=f"TEST Create Poll Location {suffix}")
    ptype = PracticeType(name=f"TEST Create Poll Type {suffix}")
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


def test_create_always_targets_the_leads_channel(admin_client, db_session):
    practice, location, ptype = _ready_practice_range()
    poll_id = None
    try:
        response = admin_client.post("/admin/availability/polls/create", json={
            "starts_on": _DEFAULT_TEST_START, "ends_on": _DEFAULT_TEST_END,
        })
        body = response.get_json()
        assert body["success"] is True
        poll_id = body["poll_id"]
        assert body["channel_id"] == COORD_CHANNEL_ID
        assert "is_shadow" not in body
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
