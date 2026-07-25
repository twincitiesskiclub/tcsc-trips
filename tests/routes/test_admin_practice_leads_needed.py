"""leads_needed validation and assists retirement."""

from datetime import datetime

import pytest

from app.models import db
from app.practices.models import Practice, PracticeLead, PracticeLocation


# The reserved date/time these tests post against. Owning an exact,
# unmistakable moment (rather than relying on each test remembering to
# register the practice_id it created) means teardown can sweep up any row
# that landed here, including ones created by a code path this test suite
# didn't anticipate -- e.g. a validation bug that lets a bad request through.
_TEST_DATE = datetime(2026, 8, 4, 18, 15)


# `location_id: 1` below is a hardcoded value from the task brief. The dev
# database's practice_locations table is currently empty and its id sequence
# is well past 1, so id=1 is not naturally present. This fixture creates it
# only if missing, and only removes it again if this fixture was the one
# that created it, per tests/practices/conftest.py's cleanup conventions.
@pytest.fixture(autouse=True)
def practice_location_1(db_session):
    collisions = Practice.query.filter(Practice.date == _TEST_DATE).count()
    assert collisions == 0, (
        "Reserved test date for leads_needed tests already has practices; "
        "refusing to run against unexpected dev-db state"
    )

    existing = db.session.get(PracticeLocation, 1)
    created = False
    if existing is None:
        location = PracticeLocation(id=1, name="TEST Location 1")
        db.session.add(location)
        db.session.commit()
        created = True

    yield

    db.session.rollback()
    owned_practices = Practice.query.filter(Practice.date == _TEST_DATE).all()
    for practice in owned_practices:
        PracticeLead.query.filter_by(practice_id=practice.id).delete()
        db.session.delete(practice)
    db.session.commit()

    if created:
        location = db.session.get(PracticeLocation, 1)
        if location is not None:
            db.session.delete(location)
            db.session.commit()


# These tests hit the real /admin/practices/create route against the real
# dev database. That route best-effort calls refresh_practice_posts() after
# commit, which would otherwise post live messages to the club's actual
# Slack workspace (SLACK_BOT_TOKEN is configured in this environment). This
# autouse fixture no-ops that call for every test in this module, matching
# the pattern used in tests/routes/test_admin_practices_routes.py.
@pytest.fixture(autouse=True)
def no_slack_refresh(monkeypatch):
    monkeypatch.setattr(
        "app.slack.practices.refresh_practice_posts",
        lambda *args, **kwargs: {},
    )


@pytest.mark.parametrize("value", [0, 4, -1, "two"])
def test_invalid_leads_needed_is_rejected(admin_client, value):
    response = admin_client.post("/admin/practices/create", json={
        "date": "2026-08-04T18:15:00",
        "location_id": 1,
        "leads_needed": value,
    })
    assert response.status_code == 400
    assert "leads_needed" in response.get_json()["error"].lower()


def test_valid_leads_needed_is_stored(admin_client, db_session):
    response = admin_client.post("/admin/practices/create", json={
        "date": "2026-08-04T18:15:00",
        "location_id": 1,
        "leads_needed": 3,
    })
    assert response.status_code == 200
    practice = Practice.query.get(response.get_json()["practice_id"])
    assert practice.leads_needed == 3


def test_leads_needed_defaults_to_two_when_omitted(admin_client):
    response = admin_client.post("/admin/practices/create", json={
        "date": "2026-08-04T18:15:00",
        "location_id": 1,
    })
    assert response.status_code == 200
    practice = Practice.query.get(response.get_json()["practice_id"])
    assert practice.leads_needed == 2


def test_assist_ids_are_ignored(admin_client):
    response = admin_client.post("/admin/practices/create", json={
        "date": "2026-08-04T18:15:00",
        "location_id": 1,
        "assist_ids": [1, 2],
    })
    assert response.status_code == 200
    practice_id = response.get_json()["practice_id"]
    assists = PracticeLead.query.filter_by(practice_id=practice_id, role="assist").count()
    assert assists == 0, "the assist role is retired; no new assist rows may be written"
