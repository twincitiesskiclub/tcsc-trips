"""leads_needed validation and assists retirement."""

from datetime import datetime

import pytest

from app.models import db, User
from app.practices.interfaces import PracticeStatus
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


@pytest.mark.parametrize("value", [0, 4, -1, "two", True, False])
def test_invalid_leads_needed_is_rejected(admin_client, value):
    response = admin_client.post("/admin/practices/create", json={
        "date": "2026-08-04T18:15:00",
        "location_id": 1,
        "leads_needed": value,
    })
    assert response.status_code == 400
    assert "leads_needed" in response.get_json()["error"].lower()


# `create_practice` and `edit_practice` each carry their own, independent
# `isinstance(leads_needed, bool)` guard (the edit route does not delegate to
# create's validation). Booleans are `int` instances in Python, so without
# this guard `{"leads_needed": true}` would be silently accepted and stored
# as `1`. The parametrize above only exercises the create-route copy of the
# guard; this test pins the edit-route copy the same way.
@pytest.mark.parametrize("value", [True, False])
def test_invalid_leads_needed_is_rejected_on_edit(admin_client, value):
    create_response = admin_client.post("/admin/practices/create", json={
        "date": "2026-08-04T18:15:00",
        "location_id": 1,
    })
    assert create_response.status_code == 200
    practice_id = create_response.get_json()["practice_id"]

    response = admin_client.post(f"/admin/practices/{practice_id}/edit", json={
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


def test_editing_practice_preserves_historical_assist_role(admin_client, db_session):
    """`edit_practice` rebuilds staffing by deleting existing `PracticeLead`
    rows and re-adding from the request, but the delete is scoped to
    `role.in_(('coach', 'lead'))` specifically so historical `role='assist'`
    rows survive. The admin UI no longer sends `assist_ids` on save, so an
    unscoped delete would silently erase years of assist history the next
    time any practice is edited. This seeds a practice with an existing
    assist row plus a lead and a coach row, then edits it the way the current
    UI actually does -- only `coach_ids`/`lead_ids`, no `assist_ids` -- and
    asserts the assist row is still there afterward.
    """
    coach_user = User(
        first_name="TEST", last_name="Coach",
        email="test.leads-needed-coach@example.invalid", status="ACTIVE",
    )
    lead_user = User(
        first_name="TEST", last_name="Lead",
        email="test.leads-needed-lead@example.invalid", status="ACTIVE",
    )
    assist_user = User(
        first_name="TEST", last_name="Assist",
        email="test.leads-needed-assist@example.invalid", status="ACTIVE",
    )
    db.session.add_all([coach_user, lead_user, assist_user])
    db.session.flush()

    practice = Practice(
        date=_TEST_DATE,
        day_of_week=_TEST_DATE.strftime("%A"),
        location_id=1,
        status=PracticeStatus.SCHEDULED.value,
    )
    db.session.add(practice)
    db.session.flush()

    db.session.add_all([
        PracticeLead(practice_id=practice.id, user_id=coach_user.id, role="coach"),
        PracticeLead(practice_id=practice.id, user_id=lead_user.id, role="lead"),
        PracticeLead(practice_id=practice.id, user_id=assist_user.id, role="assist"),
    ])
    db.session.commit()

    try:
        response = admin_client.post(f"/admin/practices/{practice.id}/edit", json={
            "coach_ids": [coach_user.id],
            "lead_ids": [lead_user.id],
        })
        assert response.status_code == 200

        remaining_roles = [
            row.role
            for row in PracticeLead.query.filter_by(practice_id=practice.id).all()
        ]
        assert "assist" in remaining_roles, (
            "editing a practice with only coach_ids/lead_ids must not delete "
            "historical role='assist' rows"
        )
    finally:
        db.session.rollback()
        PracticeLead.query.filter_by(practice_id=practice.id).delete()
        db.session.delete(practice)
        db.session.delete(coach_user)
        db.session.delete(lead_user)
        db.session.delete(assist_user)
        db.session.commit()
