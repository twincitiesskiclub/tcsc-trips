"""The Publish button on the Sunday coach review post.

The handler deliberately re-reads the week's drafts from the database rather
than trusting anything baked into the post: the Sunday post lives for a week,
and by the time someone clicks Publish the set of ready drafts has usually
changed (details filled in, a practice cancelled, one already published).

Runs against the real local dev database — year 2126 weeks are reserved here
the same way tests/slack/test_practice_quick_edit.py reserves its own, and
every row is deleted in a finally.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from app import create_app
from app.models import db
from app.practices.models import Practice, PracticeLocation, PracticeType
from app.practices.service import published_practices
import app.slack.bolt_app as bolt_module

# A real Monday, verified — 2126-10-05 is a Saturday, which this previously
# claimed was a Monday. The handler queries by date range so the assertions held
# either way, but a date whose comment lies about its weekday is a trap for the
# next person, and the day_of_week values below have to match reality.
_WEEK_START = datetime(2126, 10, 7)  # Monday; +1 = Tue 10/8, +3 = Thu 10/10
_MARKER = "TEST publish_week_drafts"


@pytest.fixture
def app():
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret-key"
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = (
        "postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"
    )
    return flask_app


@pytest.fixture
def db_session(app):
    with app.app_context():
        yield db.session


@pytest.fixture
def week(db_session):
    """A reserved week with a ready draft and one missing its location."""
    db.session.rollback()
    week_end = _WEEK_START + timedelta(days=7)
    collisions = Practice.query.filter(
        Practice.date >= _WEEK_START,
        Practice.date < week_end,
    ).count()
    assert collisions == 0, (
        "Reserved publish_week_drafts test week contains existing rows; "
        "refusing to mutate persistent data"
    )

    location = PracticeLocation(name=f"{_MARKER} Location")
    ptype = PracticeType(name=f"{_MARKER} Type")
    db.session.add_all([location, ptype])
    db.session.flush()

    ready = Practice(
        date=_WEEK_START + timedelta(days=1, hours=18, minutes=15),
        day_of_week="Tuesday", is_draft=True, location_id=location.id,
        logistics_notes=_MARKER,
    )
    ready.practice_types = [ptype]
    blocked = Practice(
        date=_WEEK_START + timedelta(days=3, hours=18, minutes=15),
        day_of_week="Thursday", is_draft=True, location_id=None,
        logistics_notes=_MARKER,
    )
    blocked.practice_types = [ptype]
    db.session.add_all([ready, blocked])
    db.session.commit()

    ids = {"ready": ready.id, "blocked": blocked.id,
           "location": location.id, "type": ptype.id}
    try:
        yield ids
    finally:
        db.session.rollback()
        for key in ("ready", "blocked"):
            row = db.session.get(Practice, ids[key])
            if row is not None:
                db.session.delete(row)
        db.session.flush()
        for model, key in ((PracticeType, "type"), (PracticeLocation, "location")):
            row = db.session.get(model, ids[key])
            if row is not None:
                db.session.delete(row)
        db.session.commit()


@pytest.fixture(autouse=True)
def no_refresh(monkeypatch):
    monkeypatch.setattr(
        "app.slack.practices.refresh.refresh_practice_posts",
        lambda practice, change_type="edit", **kwargs: {},
    )


def _click(week_start=_WEEK_START, client=None):
    ack = MagicMock()
    client = client or MagicMock()
    bolt_module._handle_publish_week_drafts(
        ack=ack,
        body={"user": {"id": "U0TEST"}, "channel": {"id": "C0TEST"}},
        action={"value": week_start.strftime("%Y-%m-%d")},
        client=client,
        logger=MagicMock(),
    )
    return ack, client


def test_clicking_publish_makes_the_ready_draft_visible(db_session, week):
    ack, client = _click()

    ack.assert_called_once()
    assert (
        published_practices().filter(Practice.id == week["ready"]).first()
        is not None
    )


def test_the_incomplete_draft_stays_a_draft(db_session, week):
    _click()

    assert (
        published_practices().filter(Practice.id == week["blocked"]).first()
        is None
    ), "a practice with no location must not reach members"


def test_the_clicker_is_told_what_happened(db_session, week):
    """Ephemeral, not a channel post: the result is feedback for the person who
    clicked, and the post itself already refreshes to show the new state."""
    _ack, client = _click()

    client.chat_postEphemeral.assert_called_once()
    text = client.chat_postEphemeral.call_args.kwargs["text"]
    assert "1" in text
    assert "location" in text, "name what is still blocking the other draft"


def test_a_week_with_nothing_ready_says_so(db_session, week):
    """Publishing twice in a row must not read as a success the second time."""
    _click()
    _ack, client = _click()

    text = client.chat_postEphemeral.call_args.kwargs["text"]
    assert "location" in text
    assert "Published 1" not in text


def test_a_bad_date_value_does_not_crash_the_handler(db_session):
    ack = MagicMock()
    client = MagicMock()
    bolt_module._handle_publish_week_drafts(
        ack=ack,
        body={"user": {"id": "U0TEST"}, "channel": {"id": "C0TEST"}},
        action={"value": "not-a-date"},
        client=client,
        logger=MagicMock(),
    )

    ack.assert_called_once()
    client.chat_postEphemeral.assert_called_once()
    assert "date" in client.chat_postEphemeral.call_args.kwargs["text"].lower()
