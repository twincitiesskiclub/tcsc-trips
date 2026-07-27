"""The availability poll surface in the practice-refresh dispatcher.

Editing a practice must update any OPEN poll message that covers it, so
leads never react to a session line whose location/type is no longer true.

Dates use year 2099 and names carry a "TEST " prefix per
tests/practices/conftest.py — this suite runs against the real local dev
database. Ids are captured as plain ints via _capture() BEFORE each test's
try block; cleanup deletes the poll first (its practice mappings cascade),
then practices, then their locations/types, and always rolls back first so
a poisoned session can't leave debris behind.
"""

import json
import logging
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
    _log_refresh_results,
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


def _capture(practices, polls, extra_location_ids=()):
    """Snapshot cleanup ids as plain ints, BEFORE the test's try block.

    Reading .id / .location_id / .practice_types off ORM objects after a
    rollback() is undefined — the conftest convention is to capture ids
    early, so _cleanup() only ever touches ints.
    """
    return {
        "poll_ids": [poll.id for poll in polls if poll is not None],
        "practice_ids": [practice.id for practice in practices],
        "location_ids": (
            {p.location_id for p in practices if p.location_id}
            | set(extra_location_ids)
        ),
        "type_ids": {t.id for p in practices for t in p.practice_types},
    }


def _cleanup(ids):
    """Poll first (mappings cascade), then practices, then their refs."""
    db.session.rollback()
    for poll_id in ids["poll_ids"]:
        stored = db.session.get(LeadAvailabilityPoll, poll_id)
        if stored is not None:
            db.session.delete(stored)
    db.session.flush()

    for practice_id in ids["practice_ids"]:
        stored = db.session.get(Practice, practice_id)
        if stored is not None:
            db.session.delete(stored)
    db.session.flush()
    if ids["type_ids"]:
        PracticeType.query.filter(
            PracticeType.id.in_(ids["type_ids"])
        ).delete(synchronize_session=False)
    if ids["location_ids"]:
        PracticeLocation.query.filter(
            PracticeLocation.id.in_(ids["location_ids"])
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
    ids = _capture(
        [practice], [poll], extra_location_ids={old_location_id}
    )

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
        _cleanup(ids)


def test_draft_poll_is_not_updated(db_session):
    """DRAFT has no Slack message yet — nothing to update."""
    practice = _practice(4, "TEST Draft Loc", "TEST Refresh Type B")
    poll = _poll([practice], PollStatus.DRAFT, None)
    ids = _capture([practice], [poll])

    client = MagicMock()
    try:
        with patch("app.slack.client.get_slack_client", return_value=client):
            result = _refresh_availability_poll(practice, "edit")

        assert result == {"skipped": "no_poll"}
        client.chat_update.assert_not_called()
    finally:
        _cleanup(ids)


def test_closed_poll_is_not_updated(db_session):
    """Availability collection is over; rewriting history would mislead."""
    practice = _practice(4, "TEST Closed Loc", "TEST Refresh Type C")
    poll = _poll([practice], PollStatus.CLOSED, "1785.2")
    ids = _capture([practice], [poll])

    client = MagicMock()
    try:
        with patch("app.slack.client.get_slack_client", return_value=client):
            result = _refresh_availability_poll(practice, "edit")

        assert result == {"skipped": "no_poll"}
        client.chat_update.assert_not_called()
    finally:
        _cleanup(ids)


def test_practice_covered_by_no_poll_returns_skipped(db_session):
    practice = _practice(4, "TEST Pollless Loc", "TEST Refresh Type D")
    db_session.commit()
    ids = _capture([practice], [])

    client = MagicMock()
    try:
        with patch("app.slack.client.get_slack_client", return_value=client):
            result = _refresh_availability_poll(practice, "edit")

        assert result == {"skipped": "no_poll"}
        client.chat_update.assert_not_called()
    finally:
        _cleanup(ids)


def test_cancelled_practice_is_dropped_from_the_poll_message(db_session):
    """A cancelled practice must not keep soliciting availability, while the
    poll's other sessions keep their lines (and their letter emoji)."""
    cancelled = _practice(4, "TEST Cancelled Loc", "TEST Refresh Type E")
    kept = _practice(6, "TEST Kept Loc", "TEST Refresh Type F")
    poll = _poll([cancelled, kept], PollStatus.OPEN, "1785.3")

    cancelled.status = PracticeStatus.CANCELLED.value
    db_session.commit()
    ids = _capture([cancelled, kept], [poll])

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
        _cleanup(ids)


def test_delete_drops_the_practice_while_its_row_still_exists(db_session):
    """The delete route refreshes BEFORE db.session.delete(practice), so the
    surface must exclude the doomed practice itself rather than wait for the
    row to disappear."""
    doomed = _practice(4, "TEST Doomed Loc", "TEST Refresh Type G")
    kept = _practice(6, "TEST Survivor Loc", "TEST Refresh Type H")
    poll = _poll([doomed, kept], PollStatus.OPEN, "1785.4")
    ids = _capture([doomed, kept], [poll])

    client = MagicMock()
    try:
        with patch("app.slack.client.get_slack_client", return_value=client):
            result = _refresh_availability_poll(doomed, "delete")

        assert result["success"] is True
        rendered = json.dumps(client.chat_update.call_args.kwargs["blocks"])
        assert "TEST Doomed Loc" not in rendered
        assert "TEST Survivor Loc" in rendered
    finally:
        _cleanup(ids)


def test_slack_failure_is_contained_and_other_surfaces_still_run(db_session):
    practice = _practice(4, "TEST Failure Loc", "TEST Refresh Type I")
    poll = _poll([practice], PollStatus.OPEN, "1785.5")
    ids = _capture([practice], [poll])

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
        _cleanup(ids)


def test_partial_failure_reports_the_polls_that_did_update(db_session):
    """When several polls cover a practice and one fails, the failure dict
    still carries the ids that DID update, so logs show what went through."""
    practice = _practice(4, "TEST Partial Loc", "TEST Refresh Type J")
    poll_ok = _poll([practice], PollStatus.OPEN, "1785.6")
    poll_bad = _poll([practice], PollStatus.OPEN, "1785.7")
    ids = _capture([practice], [poll_ok, poll_bad])
    ok_id, bad_id = poll_ok.id, poll_bad.id

    client = MagicMock()

    def update(**kwargs):
        if kwargs["ts"] == "1785.7":
            raise TimeoutError("slack transport down")
        return {"ok": True}

    client.chat_update.side_effect = update
    try:
        with patch("app.slack.client.get_slack_client", return_value=client):
            result = _refresh_availability_poll(practice, "edit")

        assert result["success"] is False
        assert f"poll #{bad_id}" in result["error"]
        assert result["polls"] == [ok_id]
    finally:
        _cleanup(ids)


def test_no_poll_skip_is_not_logged_as_a_missing_post(caplog):
    """'No poll covers this practice' is the normal case for any ordinary
    edit — it must not trip the WARNING that flags genuinely absent posts."""
    practice = MagicMock(id=999999)
    results = {"availability_poll": {"skipped": "no_poll"}}

    with caplog.at_level(
        logging.WARNING, logger="app.slack.practices.refresh"
    ):
        _log_refresh_results(practice, "edit", results)

    assert caplog.records == []


def test_registry_includes_the_availability_poll_surface():
    from app.slack.practices.refresh import PRACTICE_SURFACES

    surface = {s.name: s for s in PRACTICE_SURFACES}["availability_poll"]
    # The poll's ts lives on the poll row, not the practice, so the
    # practice-level presence gate must not apply.
    assert surface.ts_field is None
    assert surface.applies_to == {"edit", "cancel", "delete"}
