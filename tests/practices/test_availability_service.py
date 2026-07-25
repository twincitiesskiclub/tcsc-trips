"""Poll construction and opening.

Dates use year 2099 and names/locations/types carry a "TEST " prefix per
tests/practices/conftest.py — this suite runs against the real local dev
database, and 2026 (the year the brief's own example used) is now the real
near future, so it can't be used here without risking a collision with real
practice data. Tag rows (PRACTICES_LEAD, HEAD_COACH, ...) are get-or-create
and are never deleted: they are fixed reference data (seeded by migration
36f58dc97c0c), not test debris, matching the existing convention in
tests/newsletter/test_coach_rotation.py.
"""

import uuid
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from app.models import Tag, User, db
from app.practices.availability import (
    PollNotReadyError,
    build_poll,
    eligible_leads,
    open_poll,
)
from app.practices.availability_models import LeadAvailabilityPoll, PollStatus
from app.practices.interfaces import PracticeStatus
from app.practices.models import Practice, PracticeLocation, PracticeType

_START = date(2099, 8, 1)
_END = date(2099, 8, 31)


def _ready_practice(day, hour=18, minute=15):
    location = PracticeLocation(name="TEST Availability Location")
    ptype = PracticeType(name=f"TEST Availability Type {day}")
    db.session.add_all([location, ptype])
    db.session.flush()
    p = Practice(date=datetime(2099, 8, day, hour, minute),
                 day_of_week="Tuesday", is_draft=True, location_id=location.id)
    p.practice_types = [ptype]
    db.session.add(p)
    db.session.flush()
    return p


def _cleanup_practices(practices, poll=None):
    """Delete a poll (cascades to its practice mappings) then the practices
    and their locations/types. Order matters: LeadAvailabilityPollPractice
    has a NOT NULL FK to practices, so the poll must go first; Practice has
    FKs to location/type, so practices must go before those.

    Rolls back first so a poisoned session (e.g. a prior statement that
    raised and left the transaction aborted) doesn't turn this cleanup
    itself into a PendingRollbackError that leaves debris behind for the
    next test to trip over.
    """
    db.session.rollback()
    if poll is not None:
        stored = db.session.get(type(poll), poll.id)
        if stored is not None:
            db.session.delete(stored)
        db.session.flush()

    location_ids = {p.location_id for p in practices if p.location_id}
    type_ids = {t.id for p in practices for t in p.practice_types}
    for p in practices:
        obj = db.session.get(Practice, p.id)
        if obj is not None:
            db.session.delete(obj)
    db.session.flush()
    if type_ids:
        PracticeType.query.filter(PracticeType.id.in_(type_ids)).delete(synchronize_session=False)
    if location_ids:
        PracticeLocation.query.filter(PracticeLocation.id.in_(location_ids)).delete(synchronize_session=False)
    db.session.commit()


# Matches the seed data in migration 36f58dc97c0c: the admin roles page
# renders display_name, so a get-or-create fallback must not invent a
# different one (that leaked a "PRACTICES_LEAD/PRACTICES_LEAD" badge before).
_TAG_DISPLAY_NAMES = {
    "PRACTICES_LEAD": "Practices Lead",
    "HEAD_COACH": "Head Coach",
    "ASSISTANT_COACH": "Assistant Coach",
    "PRACTICES_DIRECTOR": "Practices Director",
}


def _tagged_user(name, tag_name="PRACTICES_LEAD"):
    tag = Tag.query.filter_by(name=tag_name).first() or Tag(
        name=tag_name, display_name=_TAG_DISPLAY_NAMES.get(tag_name, tag_name))
    db.session.add(tag)
    unique = uuid.uuid4().hex[:8]
    user = User(first_name=f"TEST {name}", last_name="Availability",
                email=f"test-availability-{name.lower()}-{unique}@example.invalid")
    user.tags = [tag]
    db.session.add(user)
    db.session.flush()
    return user


def _cleanup_users(users):
    db.session.rollback()
    for user in users:
        obj = db.session.get(User, user.id)
        if obj is not None:
            obj.tags = []
    db.session.flush()
    for user in users:
        obj = db.session.get(User, user.id)
        if obj is not None:
            db.session.delete(obj)
    db.session.commit()


def test_eligible_leads_comes_from_tags(db_session):
    lead = _tagged_user("Ada")
    coach = _tagged_user("Coach", "HEAD_COACH")
    untagged = User(first_name="TEST Nobody", last_name="Availability",
                     email=f"test-availability-nobody-{uuid.uuid4().hex[:8]}@example.invalid")
    db_session.add(untagged)
    db_session.commit()

    try:
        names = {u.first_name for u in eligible_leads()}
        assert "TEST Ada" in names and "TEST Coach" in names
        assert "TEST Nobody" not in names, "untagged members are not asked"
    finally:
        _cleanup_users([lead, coach, untagged])


def test_build_poll_assigns_emoji_in_chronological_order(db_session):
    later = _ready_practice(6)
    earlier = _ready_practice(4)
    db_session.commit()

    poll = None
    try:
        poll = build_poll(_START, _END)

        assert [m.practice_id for m in poll.practices] == [earlier.id, later.id]
        assert [m.emoji for m in poll.practices] == ["letter_a", "letter_b"]
        assert [m.position for m in poll.practices] == [0, 1]
        assert poll.status == PollStatus.DRAFT
    finally:
        _cleanup_practices([earlier, later], poll)


def test_build_poll_refuses_incomplete_drafts(db_session):
    ready = _ready_practice(4)
    bare = Practice(date=datetime(2099, 8, 6, 18, 15), day_of_week="Thursday", is_draft=True)
    db_session.add(bare)
    db_session.commit()

    poll = None
    try:
        with pytest.raises(PollNotReadyError) as exc:
            build_poll(_START, _END)
        assert "location" in str(exc.value)
        assert LeadAvailabilityPoll.query.filter_by(
            starts_on=_START, ends_on=_END
        ).first() is None, "a refused build must leave no poll row behind"
    finally:
        _cleanup_practices([ready, bare], poll)


def test_open_poll_refuses_when_emoji_are_missing(db_session, app):
    ready = _ready_practice(4)
    db_session.commit()
    poll = build_poll(_START, _END)

    try:
        client = MagicMock()
        with patch("app.practices.availability.validate_emoji_available",
                   return_value=(False, ["letter_a"])), \
             patch("app.practices.availability.get_slack_client", return_value=client):
            result = open_poll(poll)

        assert result["success"] is False
        assert "letter_a" in result["error"]
        client.chat_postMessage.assert_not_called(), \
            "never post a poll nobody can answer"
        assert poll.status == PollStatus.DRAFT
    finally:
        _cleanup_practices([ready], poll)


def test_open_poll_posts_and_seeds_reactions(db_session, app):
    first = _ready_practice(4)
    second = _ready_practice(6)
    db_session.commit()
    poll = build_poll(_START, _END)

    try:
        client = MagicMock()
        client.chat_postMessage.return_value = {"ok": True, "ts": "1785.1"}

        with patch("app.practices.availability.validate_emoji_available", return_value=(True, [])), \
             patch("app.practices.availability.get_slack_client", return_value=client):
            result = open_poll(poll)

        assert result["success"] is True
        assert poll.status == PollStatus.OPEN
        assert poll.message_ts == "1785.1"

        seeded = [c.kwargs["name"] for c in client.reactions_add.call_args_list]
        assert seeded == ["letter_a", "letter_b", "white_check_mark"], \
            "seed each session emoji plus done, so members tap rather than search"
    finally:
        _cleanup_practices([first, second], poll)


def test_open_poll_seeding_survives_a_reaction_failure(db_session, app):
    """Seeding reactions is deliberately best-effort: the message is already
    posted and the poll already committed as OPEN by the time seeding runs,
    so one failed reactions_add must be logged, not raised, and seeding must
    keep going for the remaining emoji rather than stopping partway through.
    """
    first = _ready_practice(4)
    second = _ready_practice(6)
    db_session.commit()
    poll = build_poll(_START, _END)

    try:
        client = MagicMock()
        client.chat_postMessage.return_value = {"ok": True, "ts": "1785.1"}
        client.reactions_add.side_effect = [None, TimeoutError("boom"), None]

        with patch("app.practices.availability.validate_emoji_available", return_value=(True, [])), \
             patch("app.practices.availability.get_slack_client", return_value=client):
            result = open_poll(poll)

        assert result["success"] is True
        assert poll.status == PollStatus.OPEN
        assert client.reactions_add.call_count == 3, \
            "a failed reaction must not stop seeding of the remaining emoji"
    finally:
        _cleanup_practices([first, second], poll)


def test_build_poll_excludes_cancelled_practices(db_session):
    """A cancelled practice must not get a letter emoji or block the poll --
    otherwise leads are asked to cover a session that isn't happening, and a
    cancelled-but-incomplete practice would refuse the whole poll for a
    detail (location, type) the director has no reason to fill in.
    """
    live = _ready_practice(4)
    cancelled = _ready_practice(6)
    cancelled.status = PracticeStatus.CANCELLED.value
    db_session.commit()

    poll = None
    try:
        poll = build_poll(_START, _END)

        assert [m.practice_id for m in poll.practices] == [live.id]
        assert [m.emoji for m in poll.practices] == ["letter_a"]
    finally:
        _cleanup_practices([live, cancelled], poll)


def test_build_poll_targets_channel_by_shadow_flag(db_session):
    """is_shadow=True must route to the shadow channel, never the live
    #coord-practices-leads-assists channel -- during the shadow month that
    is the one thing standing between a test poll and 64 real members.
    """
    from app.slack.practices._config import COORD_CHANNEL_ID

    live_practice = _ready_practice(4)
    db_session.commit()
    live_poll = None
    try:
        live_poll = build_poll(_START, _END, is_shadow=False)
        assert live_poll.channel_id == COORD_CHANNEL_ID
    finally:
        _cleanup_practices([live_practice], live_poll)

    shadow_practice = _ready_practice(4)
    db_session.commit()
    shadow_poll = None
    try:
        shadow_poll = build_poll(_START, _END, is_shadow=True)
        assert shadow_poll.channel_id == "C0B3Y71PG92"
        assert shadow_poll.channel_id != COORD_CHANNEL_ID
    finally:
        _cleanup_practices([shadow_practice], shadow_poll)


def test_open_poll_survives_a_non_slack_api_error(db_session, app):
    """get_slack_client() raises plain ValueError when SLACK_BOT_TOKEN is
    unset, and transport failures raise TimeoutError -- neither is a
    SlackApiError, so a bare `except SlackApiError` would let this crash the
    caller instead of returning a clean failure result.
    """
    ready = _ready_practice(4)
    db_session.commit()
    poll = build_poll(_START, _END)

    try:
        with patch("app.practices.availability.validate_emoji_available", return_value=(True, [])), \
             patch("app.practices.availability.get_slack_client", side_effect=ValueError("SLACK_BOT_TOKEN not configured")):
            result = open_poll(poll)

        assert result["success"] is False
        assert "SLACK_BOT_TOKEN" in result["error"]
        assert poll.status == PollStatus.DRAFT
    finally:
        _cleanup_practices([ready], poll)
