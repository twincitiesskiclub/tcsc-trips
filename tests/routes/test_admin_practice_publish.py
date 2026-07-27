"""The publish-by-id endpoint behind the practices list drawer.

This is the escape hatch, not the main route: blocks are normally published
from the availability poll that collected leads for them (see
tests/routes/test_admin_poll_publish.py). It exists for a draft whose block
never got a poll, which would otherwise have no route to being published at
all. Its contract still matters — a partial success has to say exactly which
practices did not go out and why.

This runs against the real local dev database; see tests/routes/conftest.py
and tests/practices/conftest.py for the cleanup conventions (year 2099,
"TEST " prefixes, try/finally, rollback first, scoped queries).
"""

from datetime import datetime

import pytest

from app.models import db
from app.practices.models import Practice, PracticeLocation, PracticeType
from app.practices.service import published_practices

_PREFIX = "TEST publish route"


@pytest.fixture(autouse=True)
def no_slack(monkeypatch):
    """These tests exercise HTTP contracts, not Slack."""
    monkeypatch.setattr(
        "app.slack.practices.refresh.refresh_practice_posts",
        lambda practice, change_type="edit", **kwargs: {},
    )


@pytest.fixture()
def scratch(db_session):
    """A location and type the drafts can point at, cleaned up afterwards."""
    db.session.rollback()
    location = PracticeLocation(name=f"{_PREFIX} Location")
    ptype = PracticeType(name=f"{_PREFIX} Type")
    db.session.add_all([location, ptype])
    db.session.commit()
    created = []

    def make_draft(day, *, with_location=True):
        when = datetime(2099, 5, day, 18, 15)
        practice = Practice(
            date=when,
            day_of_week=when.strftime("%A"),
            is_draft=True,
            leads_needed=2,
            location_id=location.id if with_location else None,
            logistics_notes=f"{_PREFIX} row",
        )
        practice.practice_types = [ptype]
        db.session.add(practice)
        db.session.commit()
        created.append(practice.id)
        return practice

    try:
        yield make_draft
    finally:
        db.session.rollback()
        for practice_id in created:
            stored = db.session.get(Practice, practice_id)
            if stored is not None:
                db.session.delete(stored)
        db.session.flush()
        for row in (
            db.session.get(PracticeType, ptype.id),
            db.session.get(PracticeLocation, location.id),
        ):
            if row is not None:
                db.session.delete(row)
        db.session.commit()


def test_publish_makes_the_selected_drafts_member_visible(admin_client, scratch):
    first = scratch(4)
    second = scratch(5)
    ids = [first.id, second.id]

    response = admin_client.post("/admin/practices/publish", json={
        "practice_ids": ids,
    })

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert sorted(body["published"]) == sorted(ids)
    assert (
        published_practices().filter(Practice.id.in_(ids)).count() == 2
    ), "both practices must now be visible to members"


def test_publish_reports_drafts_that_are_missing_details(admin_client, scratch):
    """Partial success: publish what's ready, name what isn't.

    The director needs the list of what stayed behind — otherwise the only
    signal is a count that doesn't match what they asked for.
    """
    ready = scratch(6)
    incomplete = scratch(7, with_location=False)

    response = admin_client.post("/admin/practices/publish", json={
        "practice_ids": [ready.id, incomplete.id],
    })

    assert response.status_code == 200
    body = response.get_json()
    assert body["published"] == [ready.id]
    assert body["skipped"] == [
        {"practice_id": incomplete.id, "missing": ["location"]}
    ]
    assert published_practices().filter(Practice.id == incomplete.id).first() is None


def test_publish_requires_practice_ids(admin_client):
    response = admin_client.post("/admin/practices/publish", json={})

    assert response.status_code == 400
    assert "practice_ids" in response.get_json()["error"]


def test_publish_rejects_unknown_ids(admin_client, scratch):
    """A stale grid selection must not silently publish only part of itself."""
    practice = scratch(8)

    response = admin_client.post("/admin/practices/publish", json={
        "practice_ids": [practice.id, 999_999_999],
    })

    assert response.status_code == 404
    assert "999999999" in response.get_json()["error"]
    assert (
        published_practices().filter(Practice.id == practice.id).first() is None
    ), "nothing publishes when the selection references a missing practice"


def test_publish_requires_admin(client, scratch):
    practice = scratch(9)

    response = client.post("/admin/practices/publish", json={
        "practice_ids": [practice.id],
    })

    assert response.status_code in (302, 401, 403)
    assert published_practices().filter(Practice.id == practice.id).first() is None


def test_practices_data_exposes_draft_state(admin_client, scratch):
    """The grid can't badge or select drafts if the JSON never mentions them."""
    incomplete = scratch(10, with_location=False)

    response = admin_client.get("/admin/practices/data")

    assert response.status_code == 200
    rows = {
        row["id"]: row
        for row in response.get_json()["practices"]
        if row["id"] == incomplete.id
    }
    assert rows[incomplete.id]["is_draft"] is True
    assert rows[incomplete.id]["missing_details"] == ["location"]
