"""Admin poll trigger and shadow-mode routing."""

from unittest.mock import patch

import pytest

from app.models import AppConfig, db
from app.practices.availability import PollNotReadyError

_SHADOW_MODE_KEY = "lead_availability.shadow_mode"


@pytest.fixture(autouse=True)
def _cleanup_shadow_mode_config(db_session):
    """Remove the shadow-mode AppConfig row this module writes.

    `test_create_uses_shadow_flag_from_config` sets a real AppConfig key
    (not a "TEST "-prefixed throwaway row) because that key is exactly what
    production reads. Left behind, it would silently flip real poll creation
    into shadow mode in the dev database. Per tests/practices/conftest.py's
    cleanup convention: rollback first, since an assertion failure above can
    leave the session poisoned.
    """
    yield
    db.session.rollback()
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
        build.return_value = type("P", (), {"id": 7})()
        admin_client.post("/admin/availability/polls/create", json={
            "starts_on": "2026-08-01", "ends_on": "2026-08-31",
        })

    assert build.call_args.kwargs["is_shadow"] is True


def test_open_surfaces_missing_emoji_to_the_director(admin_client):
    with patch("app.routes.admin_availability.LeadAvailabilityPoll") as model, \
         patch("app.routes.admin_availability.open_poll") as opener:
        model.query.get_or_404.return_value = object()
        opener.return_value = {"success": False, "error": "missing workspace emoji letter_c"}
        response = admin_client.post("/admin/availability/polls/1/open")

    assert response.status_code == 400
    assert "letter_c" in response.get_json()["error"]
