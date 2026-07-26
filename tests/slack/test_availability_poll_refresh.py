"""The availability poll surface in the practice-refresh dispatcher.

Editing a practice must update any OPEN poll message that covers it, so
leads never react to a session line whose location/type is no longer true.

Dates use year 2099 and names carry a "TEST " prefix per
tests/practices/conftest.py — this suite runs against the real local dev
database. Cleanup deletes the poll first (its practice mappings cascade),
then practices, then their locations/types, and always rolls back first so
a poisoned session can't leave debris behind.
"""

import json
from datetime import date, datetime
from unittest.mock import MagicMock, patch

from app.models import db
from app.practices.availability_models import (
    LeadAvailabilityPoll,
    LeadAvailabilityPollPractice,
    PollStatus,
)
from app.practices.interfaces import PracticeStatus
from app.practices.models import Practice, PracticeLocation, PracticeType
from app.slack.practices.refresh import (
    _refresh_availability_poll,
    refresh_practice_posts,
)

_LETTERS = ["letter_a", "letter_b", "letter_c"]


def _practice(day, location_name, type_name):
    location = PracticeLocation(name=location_name)
    ptype = PracticeType(name=type_name)
    db.session.add_all([location, ptype])
    db.session.flush()
    practice = Practice(
        date=datetime(2099, 8, day, 18, 15),
        day_of_week="Tuesday",
        is_draft=True,
        location_id=location.id,
    )
    practice.practice_types = [ptype]
    db.session.add(practice)
    db.session.flush()
    return practice


def _poll(practices, status, message_ts):
    poll = LeadAvailabilityPoll(
        starts_on=date(2099, 8, 1),
        ends_on=date(2099, 8, 31),
        status=status,
        channel_id="TEST_C_POLL",
        message_ts=message_ts,
    )
    db.session.add(poll)
    db.session.flush()
    for position, practice in enumerate(practices):
        db.session.add(LeadAvailabilityPollPractice(
            poll_id=poll.id,
            practice_id=practice.id,
            emoji=_LETTERS[position],
            position=position,
        ))
    db.session.commit()
    return poll


def _cleanup(practices, polls, extra_location_ids=()):
    """Poll first (mappings cascade), then practices, then their refs."""
    db.session.rollback()
    for poll in polls:
        if poll is None:
            continue
        stored = db.session.get(LeadAvailabilityPoll, poll.id)
        if stored is not None:
            db.session.delete(stored)
    db.session.flush()

    location_ids = {p.location_id for p in practices if p.location_id}
    location_ids.update(extra_location_ids)
    type_ids = {t.id for p in practices for t in p.practice_types}
    for practice in practices:
        stored = db.session.get(Practice, practice.id)
        if stored is not None:
            db.session.delete(stored)
    db.session.flush()
    if type_ids:
        PracticeType.query.filter(
            PracticeType.id.in_(type_ids)
        ).delete(synchronize_session=False)
    if location_ids:
        PracticeLocation.query.filter(
            PracticeLocation.id.in_(location_ids)
        ).delete(synchronize_session=False)
    db.session.commit()


def test_edit_updates_open_poll_message_with_new_location(db_session):
    """The full dispatcher path: an edit rewrites the poll at the poll's own
    channel/ts, and the rebuilt blocks carry the practice's NEW location."""
    practice = _practice(4, "TEST Old Lodge", "TEST Refresh Type A")
    old_location_id = practice.location_id
    poll = _poll([practice], PollStatus.OPEN, "1785.1")

    new_location = PracticeLocation(name="TEST New Lodge")
    db_session.add(new_location)
    db_session.flush()
    practice.location_id = new_location.id
    db_session.commit()

    client = MagicMock()
    try:
        with patch("app.slack.client.get_slack_client", return_value=client):
            results = refresh_practice_posts(
                practice, change_type="edit", notify=False
            )

        assert results["availability_poll"]["success"] is True
        client.chat_update.assert_called_once()
        kwargs = client.chat_update.call_args.kwargs
        assert kwargs["channel"] == "TEST_C_POLL"
        assert kwargs["ts"] == "1785.1"
        rendered = json.dumps(kwargs["blocks"])
        assert "TEST New Lodge" in rendered
        assert "TEST Old Lodge" not in rendered
    finally:
        _cleanup([practice], [poll], extra_location_ids={old_location_id})


def test_draft_poll_is_not_updated(db_session):
    """DRAFT has no Slack message yet — nothing to update."""
    practice = _practice(4, "TEST Draft Loc", "TEST Refresh Type B")
    poll = _poll([practice], PollStatus.DRAFT, None)

    client = MagicMock()
    try:
        with patch("app.slack.client.get_slack_client", return_value=client):
            result = _refresh_availability_poll(practice, "edit")

        assert result == {"skipped": "absent"}
        client.chat_update.assert_not_called()
    finally:
        _cleanup([practice], [poll])


def test_closed_poll_is_not_updated(db_session):
    """Availability collection is over; rewriting history would mislead."""
    practice = _practice(4, "TEST Closed Loc", "TEST Refresh Type C")
    poll = _poll([practice], PollStatus.CLOSED, "1785.2")

    client = MagicMock()
    try:
        with patch("app.slack.client.get_slack_client", return_value=client):
            result = _refresh_availability_poll(practice, "edit")

        assert result == {"skipped": "absent"}
        client.chat_update.assert_not_called()
    finally:
        _cleanup([practice], [poll])


def test_practice_covered_by_no_poll_returns_skipped(db_session):
    practice = _practice(4, "TEST Pollless Loc", "TEST Refresh Type D")
    db_session.commit()

    client = MagicMock()
    try:
        with patch("app.slack.client.get_slack_client", return_value=client):
            result = _refresh_availability_poll(practice, "edit")

        assert result == {"skipped": "absent"}
        client.chat_update.assert_not_called()
    finally:
        _cleanup([practice], [])


def test_cancelled_practice_is_dropped_from_the_poll_message(db_session):
    """A cancelled practice must not keep soliciting availability, while the
    poll's other sessions keep their lines (and their letter emoji)."""
    cancelled = _practice(4, "TEST Cancelled Loc", "TEST Refresh Type E")
    kept = _practice(6, "TEST Kept Loc", "TEST Refresh Type F")
    poll = _poll([cancelled, kept], PollStatus.OPEN, "1785.3")

    cancelled.status = PracticeStatus.CANCELLED.value
    db_session.commit()

    client = MagicMock()
    try:
        with patch("app.slack.client.get_slack_client", return_value=client):
            result = _refresh_availability_poll(cancelled, "cancel")

        assert result["success"] is True
        rendered = json.dumps(client.chat_update.call_args.kwargs["blocks"])
        assert "TEST Cancelled Loc" not in rendered
        assert "TEST Kept Loc" in rendered
        assert "letter_b" in rendered, \
            "surviving sessions keep their original letter emoji"
    finally:
        _cleanup([cancelled, kept], [poll])


def test_delete_drops_the_practice_while_its_row_still_exists(db_session):
    """The delete route refreshes BEFORE db.session.delete(practice), so the
    surface must exclude the doomed practice itself rather than wait for the
    row to disappear."""
    doomed = _practice(4, "TEST Doomed Loc", "TEST Refresh Type G")
    kept = _practice(6, "TEST Survivor Loc", "TEST Refresh Type H")
    poll = _poll([doomed, kept], PollStatus.OPEN, "1785.4")

    client = MagicMock()
    try:
        with patch("app.slack.client.get_slack_client", return_value=client):
            result = _refresh_availability_poll(doomed, "delete")

        assert result["success"] is True
        rendered = json.dumps(client.chat_update.call_args.kwargs["blocks"])
        assert "TEST Doomed Loc" not in rendered
        assert "TEST Survivor Loc" in rendered
    finally:
        _cleanup([doomed, kept], [poll])


def test_slack_failure_is_contained_and_other_surfaces_still_run(db_session):
    practice = _practice(4, "TEST Failure Loc", "TEST Refresh Type I")
    poll = _poll([practice], PollStatus.OPEN, "1785.5")

    client = MagicMock()
    client.chat_update.side_effect = TimeoutError("slack transport down")
    try:
        with patch("app.slack.client.get_slack_client", return_value=client):
            results = refresh_practice_posts(
                practice, change_type="edit", notify=False
            )

        assert results["availability_poll"]["success"] is False
        assert "slack transport down" in results["availability_poll"]["error"]
        # Every other registered surface still produced a result — the poll
        # failure neither raised nor short-circuited the dispatcher.
        for name in (
            "announcement", "collab", "coach_summary", "weekly_summary"
        ):
            assert name in results
    finally:
        _cleanup([practice], [poll])


def test_registry_includes_the_availability_poll_surface():
    from app.slack.practices.refresh import PRACTICE_SURFACES

    surface = {s.name: s for s in PRACTICE_SURFACES}["availability_poll"]
    # The poll's ts lives on the poll row, not the practice, so the
    # practice-level presence gate must not apply.
    assert surface.ts_field is None
    assert surface.applies_to == {"edit", "cancel", "delete"}
