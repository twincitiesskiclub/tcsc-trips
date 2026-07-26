"""The query in post_coach_weekly_summary, not just the block builder.

This is the seam the publish bug actually lived in: the block builder can badge
drafts perfectly and it makes no difference if the query feeding it filters
drafts out. Covered separately from test_coach_summary_drafts.py (which tests
the builder against hand-made PracticeInfo) because only a real query against
a real draft row proves the gate is the right one.

Real local dev database — year 2126 reserved week, "TEST " marker, cleanup in
a finally. See tests/practices/conftest.py.
"""

import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app import create_app
from app.models import db
from app.practices.models import Practice, PracticeLocation, PracticeType

# A real Monday — verified, not assumed. The block builder places each practice
# by weekday name against the practice_days config, so a week_start that isn't
# actually a Monday silently shifts every slot and the practice matches nothing.
_WEEK_START = datetime(2126, 11, 4)  # Monday; +1 = Tue 11/5, +3 = Thu 11/7
_MARKER = "TEST coach summary drafts"


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
def drafted_week(db_session):
    db.session.rollback()
    week_end = _WEEK_START + timedelta(days=7)
    collisions = Practice.query.filter(
        Practice.date >= _WEEK_START, Practice.date < week_end,
    ).count()
    assert collisions == 0, (
        "Reserved coach-summary test week contains existing rows; refusing to "
        "mutate persistent data"
    )

    location = PracticeLocation(name=f"{_MARKER} Location")
    ptype = PracticeType(name=f"{_MARKER} Type")
    db.session.add_all([location, ptype])
    db.session.flush()
    draft = Practice(
        date=_WEEK_START + timedelta(days=1, hours=18, minutes=15),
        day_of_week="Tuesday", is_draft=True, location_id=location.id,
        workout_description=f"{_MARKER} workout", logistics_notes=_MARKER,
    )
    draft.practice_types = [ptype]
    db.session.add(draft)
    db.session.commit()

    ids = {"draft": draft.id, "location": location.id, "type": ptype.id}
    try:
        yield ids
    finally:
        db.session.rollback()
        row = db.session.get(Practice, ids["draft"])
        if row is not None:
            db.session.delete(row)
        db.session.flush()
        for model, key in ((PracticeType, "type"), (PracticeLocation, "location")):
            stale = db.session.get(model, ids[key])
            if stale is not None:
                db.session.delete(stale)
        db.session.commit()


def _post(week_start=_WEEK_START):
    """Run the real function with Slack stubbed, return the blocks it built."""
    client = MagicMock()
    client.chat_postMessage.return_value = {"ts": "111.222"}
    with patch("app.slack.practices.coach_review.get_slack_client",
               return_value=client), \
         patch("app.slack.practices.coach_review.stage_summary_post"):
        from app.slack.practices.coach_review import post_coach_weekly_summary
        result = post_coach_weekly_summary(week_start)
    return result, client


def test_the_sunday_post_shows_a_drafted_practice(db_session, drafted_week):
    """The bug: this post read published_practices(), so the practices coaches
    were supposed to fill in never appeared in the post asking them to."""
    result, client = _post()

    assert result["success"] is True
    text = json.dumps(client.chat_postMessage.call_args.kwargs["blocks"])
    assert _MARKER in text, "the drafted practice must appear in the post"
    assert "Draft" in text
    assert "publish_week_drafts" not in text, (
        "flagged, not actioned — publishing belongs to the availability poll"
    )


def test_the_drafted_slot_does_not_also_invite_a_duplicate(db_session, drafted_week):
    """Tuesday has a draft, so it must not also render "No practice scheduled"
    with an Add Practice button — that is how a second practice lands on top of
    the draft."""
    _result, client = _post()

    blocks = client.chat_postMessage.call_args.kwargs["blocks"]
    tuesday = _WEEK_START + timedelta(days=1)
    assert tuesday.strftime("%A") == "Tuesday", "the fixture's draft day moved"
    placeholders = [
        block for block in blocks
        if block.get("accessory", {}).get("action_id")
        == "create_practice_from_summary"
        and f"Tuesday, {tuesday.strftime('%b')} {tuesday.strftime('%-d')}"
        in json.dumps(block)
    ]

    assert placeholders == [], (
        "the drafted Tuesday must not offer Add Practice"
    )
