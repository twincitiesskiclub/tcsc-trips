"""Candidate ranking for the lead picker.

Dates use year 2099 and user/location names carry a "TEST " prefix (with a
unique email suffix) per tests/practices/conftest.py -- this suite runs
against the real local dev database, and the brief's own example dates
(August 2026) are now the real near future, so they can't be used here
without risking a collision with real practice data. See
tests/practices/test_availability_service.py for the same convention.

eligible_leads() is a live, unscoped query over all PRACTICES_LEAD /
PRACTICES_DIRECTOR / HEAD_COACH / ASSISTANT_COACH tagged users, so assertions
use membership/subset checks against the rows this test created rather than
asserting the full result set -- a real tagged member showing up in the dev
DB must not make this suite start failing.
"""

import uuid
from datetime import date, datetime

from app.models import Tag, User, db
from app.practices.availability_models import (
    LeadAvailabilityParticipant,
    LeadAvailabilityPoll,
    LeadAvailabilityPollPractice,
    LeadAvailabilityResponse,
    ParticipantStatus,
    PollStatus,
)
from app.practices.lead_candidates import lead_candidates
from app.practices.models import Practice, PracticeLead, PracticeLocation


def _lead_user(name):
    tag = Tag.query.filter_by(name="PRACTICES_LEAD").first()
    if tag is None:
        tag = Tag(name="PRACTICES_LEAD", display_name="Practices Lead")
        db.session.add(tag)
        db.session.flush()
    unique = uuid.uuid4().hex[:8]
    user = User(first_name=f"TEST {name}", last_name="Candidate",
                email=f"test-leadcand-{name.lower()}-{unique}@example.invalid")
    user.tags = [tag]
    db.session.add(user)
    db.session.flush()
    return user


def _practice(day, location_id=None):
    p = Practice(date=datetime(2099, 8, day, 18, 15), day_of_week="Tuesday",
                 leads_needed=2, location_id=location_id)
    db.session.add(p)
    db.session.flush()
    return p


def _open_poll(practice):
    poll = LeadAvailabilityPoll(
        starts_on=date(2099, 8, 1), ends_on=date(2099, 8, 31),
        channel_id="C1", message_ts="1.1", status=PollStatus.OPEN,
        opened_at=datetime(2099, 8, 1),
    )
    db.session.add(poll)
    db.session.flush()
    db.session.add(LeadAvailabilityPollPractice(
        poll_id=poll.id, practice_id=practice.id, emoji="letter_a", position=0))
    db.session.flush()
    return poll


def _available(poll, practice, user, *, snapshot=True):
    db.session.add(LeadAvailabilityResponse(
        poll_id=poll.id, practice_id=practice.id, user_id=user.id, source="reaction",
        answered_for_date=practice.date if snapshot else datetime(2020, 1, 1),
        answered_for_location_id=practice.location_id if snapshot else None,
    ))
    db.session.add(LeadAvailabilityParticipant(
        poll_id=poll.id, user_id=user.id, status=ParticipantStatus.RESPONDED))
    db.session.flush()


def _cleanup(*, users=(), practices=(), polls=(), locations=()):
    """FK-safe teardown, in an order that survives a poisoned session.

    Rolls back first so a prior failed statement doesn't turn this cleanup
    itself into a PendingRollbackError that leaves debris behind for the next
    test to trip over. All ids passed in must already be plain ints captured
    before the caller's `try` block -- evaluating `obj.id` here, after a
    failed assertion, is exactly how test debris has leaked into the dev
    database before.

    Order: PracticeLead rows (they reference practices but nothing references
    them) -> polls (cascade deletes their poll-practice/participant/response
    rows, which reference both polls and practices) -> practices -> locations
    -> user tag links -> users.
    """
    db.session.rollback()

    practice_ids = list(practices)
    if practice_ids:
        PracticeLead.query.filter(
            PracticeLead.practice_id.in_(practice_ids)
        ).delete(synchronize_session=False)

    for poll_id in polls:
        obj = db.session.get(LeadAvailabilityPoll, poll_id)
        if obj is not None:
            db.session.delete(obj)
    db.session.flush()

    if practice_ids:
        Practice.query.filter(Practice.id.in_(practice_ids)).delete(synchronize_session=False)
    if locations:
        PracticeLocation.query.filter(
            PracticeLocation.id.in_(list(locations))
        ).delete(synchronize_session=False)

    for user_id in users:
        obj = db.session.get(User, user_id)
        if obj is not None:
            obj.tags = []
    db.session.flush()
    for user_id in users:
        obj = db.session.get(User, user_id)
        if obj is not None:
            db.session.delete(obj)

    db.session.commit()


def test_available_sorts_before_unavailable(db_session):
    practice = _practice(4)
    poll = _open_poll(practice)
    quiet = _lead_user("Zoe")
    keen = _lead_user("Ada")
    _available(poll, practice, keen)
    db_session.commit()

    practice_id, poll_id = practice.id, poll.id
    quiet_id, keen_id = quiet.id, keen.id

    try:
        rows = lead_candidates(practice)
        by_id = {r["user_id"]: r for r in rows}
        assert keen_id in by_id and quiet_id in by_id, \
            "unavailable people are ranked down, never removed"
        assert rows[0]["user_id"] == keen_id
        assert rows[0]["available"] is True
        assert by_id[quiet_id]["available"] is False
    finally:
        _cleanup(users=[quiet_id, keen_id], practices=[practice_id], polls=[poll_id])


def test_least_loaded_available_lead_comes_first(db_session):
    practice = _practice(4)
    poll = _open_poll(practice)
    busy = _lead_user("Busy")
    fresh = _lead_user("Fresh")
    _available(poll, practice, busy)
    _available(poll, practice, fresh)

    others = []
    for day in (11, 13):
        other = _practice(day)
        db_session.add(PracticeLead(practice_id=other.id, user_id=busy.id, role="lead"))
        others.append(other)
    db_session.commit()

    practice_id, poll_id = practice.id, poll.id
    busy_id, fresh_id = busy.id, fresh.id
    other_ids = [o.id for o in others]

    try:
        rows = lead_candidates(practice)
        by_id = {r["user_id"]: r for r in rows}
        assert by_id[fresh_id]["led_in_block"] == 0
        assert by_id[busy_id]["led_in_block"] == 2
        # Among these two, the least-loaded available lead ranks first.
        idx = [r["user_id"] for r in rows if r["user_id"] in (fresh_id, busy_id)]
        assert idx == [fresh_id, busy_id]
    finally:
        _cleanup(users=[busy_id, fresh_id], practices=[practice_id] + other_ids, polls=[poll_id])


def test_assist_rows_are_not_counted_as_load(db_session):
    practice = _practice(4)
    poll = _open_poll(practice)
    user = _lead_user("Ada")
    _available(poll, practice, user)
    other = _practice(11)
    db_session.add(PracticeLead(practice_id=other.id, user_id=user.id, role="assist"))
    db_session.commit()

    practice_id, poll_id, user_id, other_id = practice.id, poll.id, user.id, other.id

    try:
        rows = lead_candidates(practice)
        by_id = {r["user_id"]: r for r in rows}
        assert by_id[user_id]["led_in_block"] == 0, \
            "the assist role is retired and must not count"
    finally:
        _cleanup(users=[user_id], practices=[practice_id, other_id], polls=[poll_id])


def test_response_is_stale_when_location_changed(db_session):
    location = PracticeLocation(name="TEST Wirth")
    db_session.add(location)
    db_session.flush()
    practice = _practice(4, location_id=location.id)
    poll = _open_poll(practice)
    user = _lead_user("Ada")
    _available(poll, practice, user)
    db_session.commit()

    moved = PracticeLocation(name="TEST Hyland")
    db_session.add(moved)
    db_session.flush()
    practice.location_id = moved.id
    db_session.commit()

    practice_id, poll_id, user_id = practice.id, poll.id, user.id
    location_id, moved_id = location.id, moved.id

    try:
        rows = lead_candidates(practice)
        by_id = {r["user_id"]: r for r in rows}
        assert by_id[user_id]["stale"] is True, \
            "volunteering for Wirth is not volunteering for Hyland"
    finally:
        _cleanup(users=[user_id], practices=[practice_id], polls=[poll_id],
                 locations=[location_id, moved_id])


def test_workout_edit_does_not_make_a_response_stale(db_session):
    practice = _practice(4)
    poll = _open_poll(practice)
    user = _lead_user("Ada")
    _available(poll, practice, user)
    db_session.commit()

    practice.workout_description = "TEST edited after they answered"
    db_session.commit()

    practice_id, poll_id, user_id = practice.id, poll.id, user.id

    try:
        rows = lead_candidates(practice)
        by_id = {r["user_id"]: r for r in rows}
        assert by_id[user_id]["stale"] is False, \
            "only date/time and location decide availability; text edits must not warn"
    finally:
        _cleanup(users=[user_id], practices=[practice_id], polls=[poll_id])


def test_responded_flag_distinguishes_silence_from_unavailable(db_session):
    practice = _practice(4)
    poll = _open_poll(practice)
    silent = _lead_user("Silent")
    declined = _lead_user("Declined")
    db_session.add(LeadAvailabilityParticipant(
        poll_id=poll.id, user_id=declined.id, status=ParticipantStatus.DONE))
    db_session.commit()

    practice_id, poll_id = practice.id, poll.id
    silent_id, declined_id = silent.id, declined.id

    try:
        rows = {r["user_id"]: r for r in lead_candidates(practice)}
        assert rows[silent_id]["responded"] is False
        assert rows[declined_id]["responded"] is True
        assert rows[declined_id]["available"] is False
    finally:
        _cleanup(users=[silent_id, declined_id], practices=[practice_id], polls=[poll_id])
