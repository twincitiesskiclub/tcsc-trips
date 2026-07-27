"""Publishing a draft is what makes a practice member-visible.

The whole drafting/availability flow is worthless if nothing ever flips
`is_draft` back to False: announcements, `/tcsc practice`, App Home, the
coach weekly summary and every Skipper routine read through
`published_practices()`, which excludes drafts. The first test here is
deliberately the one the branch was missing — an end-to-end assertion that a
practice actually becomes visible to members.

Read tests/practices/conftest.py before adding to this file: this runs
against the real local dev database.
"""

from datetime import datetime

import pytest

from app.models import db
from app.practices.drafting import missing_fields
from app.practices.interfaces import PracticeStatus
from app.practices.models import Practice, PracticeLocation, PracticeType
from app.practices.publishing import (
    NotReadyToPublishError,
    publish_practice,
    publish_practices,
)
from app.practices.service import published_practices

# Year 2099 + "TEST " prefixes so any leaked row is unmistakably debris.
# See tests/practices/conftest.py, point 3.
_PREFIX = "TEST publishing"


@pytest.fixture()
def location(db_session):
    """A throwaway location, since a draft needs one to be publishable."""
    db.session.rollback()
    row = PracticeLocation(name=f"{_PREFIX} Location")
    db.session.add(row)
    db.session.commit()
    row_id = row.id
    yield row
    db.session.rollback()
    stale = PracticeLocation.query.filter_by(id=row_id).first()
    if stale is not None:
        db.session.delete(stale)
    db.session.commit()


@pytest.fixture()
def practice_type(db_session):
    row = PracticeType.query.filter_by(name=f"{_PREFIX} Type").first()
    if row is None:
        db.session.rollback()
        row = PracticeType(name=f"{_PREFIX} Type")
        db.session.add(row)
        db.session.commit()
    row_id = row.id
    yield row
    db.session.rollback()
    stale = PracticeType.query.filter_by(id=row_id).first()
    if stale is not None:
        db.session.delete(stale)
    db.session.commit()


def _make_draft(location=None, practice_type=None, *, day=1):
    """A draft practice in 2099, optionally missing its details."""
    when = datetime(2099, 3, day, 18, 15)
    practice = Practice(
        date=when,
        day_of_week=when.strftime("%A"),
        is_draft=True,
        leads_needed=2,
        location_id=location.id if location else None,
        logistics_notes=f"{_PREFIX} row",
    )
    if practice_type is not None:
        practice.practice_types = [practice_type]
    db.session.add(practice)
    db.session.commit()
    return practice


def _delete_practice(practice_id):
    """Scoped delete of exactly the row a test made.

    Goes through the ORM rather than `Practice.query.filter_by(...).delete()`:
    a bulk delete skips the `practice_types_junction` rows and dies on a
    foreign-key violation, leaving the practice behind in the dev database —
    the exact debris tests/practices/conftest.py exists to prevent.
    """
    db.session.rollback()
    practice = Practice.query.filter_by(id=practice_id).first()
    if practice is not None:
        db.session.delete(practice)
    db.session.commit()


@pytest.fixture(autouse=True)
def no_slack(monkeypatch):
    """Never touch Slack from these tests; record the calls instead."""
    calls = []

    def fake_refresh(practice, change_type="edit", **kwargs):
        calls.append({"practice_id": practice.id, "change_type": change_type, **kwargs})
        return {"announcement": {"skipped": "absent"}}

    monkeypatch.setattr(
        "app.slack.practices.refresh.refresh_practice_posts", fake_refresh
    )
    return calls


def test_publishing_a_ready_draft_makes_it_member_visible(
    db_session, location, practice_type
):
    """The assertion the branch never had: members can actually see it.

    published_practices() is the single gate every member-facing surface
    reads through, so appearing in it is the real definition of published.
    """
    practice = _make_draft(location, practice_type)
    practice_id = practice.id
    try:
        assert (
            published_practices().filter(Practice.id == practice_id).first() is None
        ), "a draft must start out invisible to members"

        result = publish_practice(practice)

        assert result["success"] is True
        assert practice.is_draft is False
        assert (
            published_practices().filter(Practice.id == practice_id).first()
            is not None
        ), "a published practice must be visible through published_practices()"
    finally:
        _delete_practice(practice_id)


def test_publish_fans_the_change_out_to_slack(
    db_session, location, practice_type, no_slack
):
    """change_type='create' — the surfaces are seeing this practice for the
    first time, exactly as if it had just been created by hand."""
    practice = _make_draft(location, practice_type)
    practice_id = practice.id
    try:
        publish_practice(practice, actor_slack_id="U0TEST")

        assert len(no_slack) == 1
        assert no_slack[0]["practice_id"] == practice_id
        assert no_slack[0]["change_type"] == "create"
        assert no_slack[0]["actor_slack_id"] == "U0TEST"
    finally:
        _delete_practice(practice_id)


def test_publish_refuses_a_draft_that_is_missing_details(db_session, practice_type):
    """A member-visible practice with no location is a support ticket.

    The error names what is missing, since whoever clicked Publish is the
    person who has to go fix it.
    """
    practice = _make_draft(None, practice_type)
    practice_id = practice.id
    try:
        with pytest.raises(NotReadyToPublishError) as exc:
            publish_practice(practice)

        assert "location" in str(exc.value)
        assert practice.is_draft is True
        assert (
            published_practices().filter(Practice.id == practice_id).first() is None
        )
    finally:
        _delete_practice(practice_id)


def test_publishing_twice_is_a_no_op(db_session, location, practice_type, no_slack):
    """Two directors clicking Publish must not double-post to Slack."""
    practice = _make_draft(location, practice_type)
    practice_id = practice.id
    try:
        publish_practice(practice)
        result = publish_practice(practice)

        assert result["already_published"] is True
        assert len(no_slack) == 1, "the second publish must not re-fan to Slack"
    finally:
        _delete_practice(practice_id)


def test_bulk_publish_publishes_ready_and_reports_the_rest(
    db_session, location, practice_type, no_slack
):
    """The Sunday batch: publish what's ready, name what isn't.

    A batch that aborted on the first incomplete draft would leave the
    director clicking Publish once per fix.
    """
    ready = _make_draft(location, practice_type, day=1)
    incomplete = _make_draft(None, practice_type, day=2)
    ready_id, incomplete_id = ready.id, incomplete.id
    try:
        result = publish_practices([ready, incomplete])

        assert result["published"] == [ready_id]
        assert result["skipped"] == [
            {"practice_id": incomplete_id, "missing": ["location"]}
        ]
        assert ready.is_draft is False
        assert incomplete.is_draft is True
        assert [call["practice_id"] for call in no_slack] == [ready_id]
    finally:
        _delete_practice(ready_id)
        _delete_practice(incomplete_id)


def test_bulk_publish_ignores_already_published_practices(
    db_session, location, practice_type, no_slack
):
    """Selecting a whole week in the grid includes rows already live."""
    practice = _make_draft(location, practice_type)
    practice.is_draft = False
    db.session.commit()
    practice_id = practice.id
    try:
        result = publish_practices([practice])

        assert result["published"] == []
        assert result["skipped"] == []
        assert result["already_published"] == [practice_id]
        assert no_slack == []
    finally:
        _delete_practice(practice_id)


def test_slack_failure_does_not_unpublish(db_session, location, practice_type, monkeypatch):
    """The row is committed before Slack is touched.

    A Slack outage must not leave the practice invisible to members — that
    would silently undo the one thing the director asked for.
    """
    def boom(practice, change_type="edit", **kwargs):
        raise RuntimeError("TEST slack is down")

    monkeypatch.setattr(
        "app.slack.practices.refresh.refresh_practice_posts", boom
    )

    practice = _make_draft(location, practice_type)
    practice_id = practice.id
    try:
        result = publish_practice(practice)

        assert result["success"] is True
        assert (
            published_practices().filter(Practice.id == practice_id).first()
            is not None
        )
    finally:
        _delete_practice(practice_id)


def test_a_cancelled_draft_is_never_published(
    db_session, location, practice_type, no_slack
):
    """Publishing a cancelled draft would announce a practice that isn't happening.

    build_poll() already excludes CANCELLED practices from availability polls;
    the publish gate has to agree, or a cancelled draft caught in a week-wide
    batch reaches members as a real session.
    """
    practice = _make_draft(location, practice_type)
    practice.status = PracticeStatus.CANCELLED.value
    db.session.commit()
    practice_id = practice.id
    try:
        with pytest.raises(NotReadyToPublishError) as exc:
            publish_practice(practice)
        assert "cancelled" in str(exc.value).lower()

        result = publish_practices([practice])
        assert result["published"] == []
        assert result["skipped"] == [
            {"practice_id": practice_id, "missing": ["not cancelled"]}
        ]
        assert (
            published_practices().filter(Practice.id == practice_id).first() is None
        )
        assert no_slack == []
    finally:
        _delete_practice(practice_id)


def test_missing_fields_is_the_shared_readiness_gate(
    db_session, location, practice_type
):
    """Publishing and poll-building must agree on what 'ready' means.

    build_poll() refuses on the same three fields; if these two ever drift, a
    director could open an availability poll for a practice that cannot be
    published, or vice versa.
    """
    practice = _make_draft(location, practice_type)
    practice_id = practice.id
    try:
        assert missing_fields(practice) == []
        practice.location_id = None
        assert "location" in missing_fields(practice)
    finally:
        _delete_practice(practice_id)
