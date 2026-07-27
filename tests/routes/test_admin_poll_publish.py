"""Publishing an availability block from its poll.

This is the one place a human decides drafts become member-visible. The unit is
the poll — the same bucket of practices the leads were asked about — because
that is the batch the director actually thinks in: collect availability for a
block, assign leads, send the block live.

It is deliberately NOT the coming week. The Sunday evening flow (weekly summary
+ announcement job) already puts the coming week in front of members without
anyone clicking anything, and a block is published weeks before any of its
practices reach their own Sunday.

Real local dev database; year 2099 dates and "TEST " prefixes per
tests/practices/conftest.py.
"""

from datetime import date, datetime

import pytest

from app.models import db
from app.practices.availability_models import (
    LeadAvailabilityPoll,
    LeadAvailabilityPollPractice,
    PollStatus,
)
from app.practices.models import Practice, PracticeLocation, PracticeType
from app.practices.service import published_practices

_PREFIX = "TEST poll publish"
_STARTS = date(2099, 6, 1)
_ENDS = date(2099, 6, 30)


@pytest.fixture(autouse=True)
def no_slack(monkeypatch):
    monkeypatch.setattr(
        "app.slack.practices.refresh.refresh_practice_posts",
        lambda practice, change_type="edit", **kwargs: {},
    )


@pytest.fixture()
def poll(db_session):
    """A CLOSED poll over two drafts: one ready, one missing its location."""
    db.session.rollback()
    location = PracticeLocation(name=f"{_PREFIX} Location")
    ptype = PracticeType(name=f"{_PREFIX} Type")
    db.session.add_all([location, ptype])
    db.session.flush()

    ready = Practice(
        date=datetime(2099, 6, 2, 18, 15), day_of_week="Tuesday",
        is_draft=True, location_id=location.id, logistics_notes=_PREFIX,
    )
    blocked = Practice(
        date=datetime(2099, 6, 4, 18, 15), day_of_week="Thursday",
        is_draft=True, location_id=None, logistics_notes=_PREFIX,
    )
    ready.practice_types = [ptype]
    blocked.practice_types = [ptype]
    db.session.add_all([ready, blocked])
    db.session.flush()

    row = LeadAvailabilityPoll(
        starts_on=_STARTS, ends_on=_ENDS, status=PollStatus.CLOSED,
        channel_id="C0TEST", is_shadow=True,
    )
    db.session.add(row)
    db.session.flush()
    for position, practice in enumerate((ready, blocked)):
        db.session.add(LeadAvailabilityPollPractice(
            poll_id=row.id, practice_id=practice.id,
            emoji=f"letter_{'ab'[position]}", position=position,
        ))
    db.session.commit()

    ids = {"poll": row.id, "ready": ready.id, "blocked": blocked.id,
           "location": location.id, "type": ptype.id}
    try:
        yield ids
    finally:
        db.session.rollback()
        stored = db.session.get(LeadAvailabilityPoll, ids["poll"])
        if stored is not None:
            db.session.delete(stored)
        db.session.flush()
        for key in ("ready", "blocked"):
            practice = db.session.get(Practice, ids[key])
            if practice is not None:
                db.session.delete(practice)
        db.session.flush()
        for model, key in ((PracticeType, "type"), (PracticeLocation, "location")):
            stale = db.session.get(model, ids[key])
            if stale is not None:
                db.session.delete(stale)
        db.session.commit()


def test_publishing_a_block_makes_its_ready_practices_visible(admin_client, poll):
    response = admin_client.post(f"/admin/availability/polls/{poll['poll']}/publish")

    assert response.status_code == 200
    body = response.get_json()
    assert body["published"] == [poll["ready"]]
    assert (
        published_practices().filter(Practice.id == poll["ready"]).first()
        is not None
    )


def test_a_practice_missing_details_stays_a_draft(admin_client, poll):
    """Named in the response so the director knows what to go fix, rather than
    discovering weeks later that one practice never went out."""
    response = admin_client.post(f"/admin/availability/polls/{poll['poll']}/publish")

    body = response.get_json()
    assert body["skipped"] == [
        {"practice_id": poll["blocked"], "missing": ["location"]}
    ]
    assert (
        published_practices().filter(Practice.id == poll["blocked"]).first()
        is None
    )


def test_publishing_twice_is_harmless(admin_client, poll):
    admin_client.post(f"/admin/availability/polls/{poll['poll']}/publish")
    response = admin_client.post(f"/admin/availability/polls/{poll['poll']}/publish")

    body = response.get_json()
    assert body["published"] == []
    assert body["already_published"] == [poll["ready"]]


def test_publishing_an_unknown_poll_is_a_404(admin_client):
    response = admin_client.post("/admin/availability/polls/999999999/publish")

    assert response.status_code == 404


def test_publishing_requires_admin(client, poll):
    response = client.post(f"/admin/availability/polls/{poll['poll']}/publish")

    assert response.status_code in (302, 401, 403)
    assert (
        published_practices().filter(Practice.id == poll["ready"]).first() is None
    )


def test_the_dashboard_reports_what_is_left_to_publish(admin_client, poll):
    """The director needs to see a block still owes a publish without opening it."""
    response = admin_client.get("/admin/availability/")

    rows = {row["id"]: row for row in response.get_json()["polls"]}
    assert rows[poll["poll"]]["unpublished"] == 2
    assert rows[poll["poll"]]["publishable"] == 1

    admin_client.post(f"/admin/availability/polls/{poll['poll']}/publish")
    rows = {
        row["id"]: row
        for row in admin_client.get("/admin/availability/").get_json()["polls"]
    }
    assert rows[poll["poll"]]["unpublished"] == 1
    assert rows[poll["poll"]]["publishable"] == 0
