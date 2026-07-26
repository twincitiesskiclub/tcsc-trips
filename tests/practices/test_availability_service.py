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
from sqlalchemy import text

from app.constants import UserStatus
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


def test_eligible_leads_excludes_alumni_without_a_coach_tag(db_session):
    """A lapsed member who kept a lead tag should stop getting availability DMs.

    ALUMNI is not a blanket exclusion (see the next test) — coaches at this
    club are routinely ALUMNI-status while actively coaching. The line is the
    coach tag: a lead-tagged alumnus has stepped back from the club, and DMing
    them every block is how the bot earns a mute.
    """
    lapsed = _tagged_user("Lapsed")
    lapsed.status = UserStatus.ALUMNI
    db_session.commit()

    try:
        names = {u.first_name for u in eligible_leads()}
        assert "TEST Lapsed" not in names
    finally:
        _cleanup_users([lapsed])


def test_eligible_leads_keeps_alumni_who_coach(db_session):
    """The reason ALUMNI can't be filtered wholesale.

    Real head/assistant coaches hold ALUMNI status while actively coaching —
    the same carve-out the Slack tier logic makes. Dropping them would empty
    the pool of exactly the people who run practice.
    """
    head = _tagged_user("AlumHead", "HEAD_COACH")
    assistant = _tagged_user("AlumAssistant", "ASSISTANT_COACH")
    head.status = UserStatus.ALUMNI
    assistant.status = UserStatus.ALUMNI
    db_session.commit()

    try:
        names = {u.first_name for u in eligible_leads()}
        assert "TEST AlumHead" in names
        assert "TEST AlumAssistant" in names
    finally:
        _cleanup_users([head, assistant])


def test_eligible_leads_still_excludes_dropped_coaches(db_session):
    """DROPPED outranks the coach carve-out — removed for cause means removed."""
    dropped = _tagged_user("DroppedCoach", "HEAD_COACH")
    dropped.status = UserStatus.DROPPED
    db_session.commit()

    try:
        names = {u.first_name for u in eligible_leads()}
        assert "TEST DroppedCoach" not in names
    finally:
        _cleanup_users([dropped])


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

        # OPEN and the ts must be *committed*, not just pending on the
        # session -- rollback would discard uncommitted state.
        poll_id = poll.id
        db.session.rollback()
        stored = db.session.get(LeadAvailabilityPoll, poll_id)
        assert stored.status == PollStatus.OPEN
        assert stored.message_ts == "1785.1"
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


def test_open_poll_commit_failure_reports_the_live_ts_and_rolls_back(db_session, app):
    """A failed commit after the Slack post must not crash, must not claim
    success, and must name the ts of the message that IS live -- that ts
    exists nowhere else once the exception is swallowed, and a human needs
    it to recover. The session must be rolled back so the caller isn't left
    with a poisoned transaction, and the poll must land back in a clean
    DRAFT state (no half-written OPEN with a dangling ts).
    """
    ready = _ready_practice(4)
    db_session.commit()
    poll = build_poll(_START, _END)
    poll_id = poll.id

    def _abort_transaction():
        # Poison the transaction at the DB level before "failing", so the
        # session-usable assertion below is genuine: without open_poll's
        # rollback, PostgreSQL keeps the transaction aborted and every
        # later query raises (PendingRollbackError / InFailedSqlTransaction)
        # rather than trivially passing.
        db.session.execute(text("SELECT 1/0"))

    try:
        client = MagicMock()
        client.chat_postMessage.return_value = {"ok": True, "ts": "1785.99"}

        with patch("app.practices.availability.validate_emoji_available", return_value=(True, [])), \
             patch("app.practices.availability.get_slack_client", return_value=client), \
             patch.object(db.session, "commit", side_effect=_abort_transaction):
            result = open_poll(poll)

        assert result["success"] is False
        assert "1785.99" in result["error"], \
            "the error must name the live message ts -- it is the only place it survives"
        client.reactions_add.assert_not_called(), \
            "the poll never became OPEN, so there is nothing to seed onto"

        # Genuine session-usable check (see _abort_transaction above): this
        # query raises unless open_poll rolled the aborted transaction back.
        stored = db.session.get(LeadAvailabilityPoll, poll_id)
        assert stored.status == PollStatus.DRAFT
        assert stored.message_ts is None, \
            "rollback must discard the half-written ts, not leave it dangling"
    finally:
        _cleanup_practices([ready], poll)


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


def test_open_poll_refuses_to_re_post_an_already_open_poll(db_session, app):
    """Fix for: calling open_poll twice posts a second Slack message and
    overwrites poll.message_ts, orphaning the first message's reactions --
    a later reconcile_poll against the orphaned ts sees zero reactions and
    wipes every stored response. Once a poll is no longer DRAFT, open_poll
    must refuse rather than post again.
    """
    ready = _ready_practice(4)
    db_session.commit()
    poll = build_poll(_START, _END)
    poll.status = PollStatus.OPEN
    poll.message_ts = "111111.1111"
    db_session.commit()

    try:
        client = MagicMock()
        with patch("app.practices.availability.validate_emoji_available", return_value=(True, [])), \
             patch("app.practices.availability.get_slack_client", return_value=client):
            result = open_poll(poll)

        assert result["success"] is False
        assert str(poll.id) in result["error"]
        client.chat_postMessage.assert_not_called(), \
            "must never post a second time once the poll is no longer DRAFT"
        assert poll.message_ts == "111111.1111", \
            "the original message_ts must survive untouched"
    finally:
        _cleanup_practices([ready], poll)


def test_build_poll_refuses_a_second_poll_over_the_same_range(db_session):
    """Fix for: building twice over the same range yields two live polls
    that would both nudge leads about the same sessions."""
    first_practice = _ready_practice(4)
    db_session.commit()
    first_poll = build_poll(_START, _END)

    try:
        with pytest.raises(PollNotReadyError) as exc:
            build_poll(_START, _END)
        assert str(first_poll.id) in str(exc.value), \
            "the error must name the existing poll so the director can find it"
        assert LeadAvailabilityPoll.query.filter_by(
            starts_on=_START, ends_on=_END
        ).count() == 1, "a refused duplicate build must leave no second poll row behind"
    finally:
        _cleanup_practices([first_practice], first_poll)


def test_build_poll_refuses_a_partially_overlapping_open_poll(db_session):
    """The guard must compare ranges, not require an exact match."""
    from datetime import date as _date

    first_practice = _ready_practice(4)
    db_session.commit()
    first_poll = build_poll(_START, _END)
    first_poll.status = PollStatus.OPEN
    db_session.commit()

    later_start = _date(2099, 8, 20)
    later_end = _date(2099, 9, 15)
    try:
        with pytest.raises(PollNotReadyError) as exc:
            build_poll(later_start, later_end)
        assert str(first_poll.id) in str(exc.value)
    finally:
        _cleanup_practices([first_practice], first_poll)


def test_build_poll_allows_a_new_poll_once_the_old_one_is_closed(db_session):
    """A CLOSED poll must not block rebuilding the same range."""
    first_practice = _ready_practice(4)
    db_session.commit()
    first_poll = build_poll(_START, _END)
    first_poll.status = PollStatus.CLOSED
    db_session.commit()

    second_practice = _ready_practice(6)
    db_session.commit()
    second_poll = None
    try:
        second_poll = build_poll(_START, _END)
        assert second_poll.id != first_poll.id
    finally:
        # first_poll must be removed (and its poll-practice mapping to
        # first_practice cascaded away) before first_practice itself is
        # deleted below, or the FK from poll-practice -> practice would
        # dangle mid-cleanup.
        _cleanup_practices([], first_poll)
        _cleanup_practices([first_practice, second_practice], second_poll)


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


# ---------------------------------------------------------------------------
# Done-emoji snapshot: like the letter emoji, the done emoji is fixed per
# poll at build time. A config edit while a poll is open must not change
# which reactions count as "done" -- reconcile would demote every
# already-DONE participant and the nudge job would DM leads who had
# declared themselves finished.
# ---------------------------------------------------------------------------


def test_build_poll_snapshots_the_done_emoji(db_session):
    ready = _ready_practice(4)
    db_session.commit()
    poll = None
    try:
        with patch(
            "app.slack.practices._config._load_practice_config",
            return_value={"lead_availability": {"done_emoji": "TEST_snap_done"}},
        ):
            poll = build_poll(_START, _END)
        assert poll.done_emoji == "TEST_snap_done", (
            "build_poll must persist the config's done emoji on the poll row, "
            "exactly as it persists the letter mapping"
        )
    finally:
        _cleanup_practices([ready], poll)


def test_open_poll_validates_and_seeds_the_snapshotted_done_emoji(db_session, app):
    ready = _ready_practice(4)
    db_session.commit()
    poll = build_poll(_START, _END)
    poll.done_emoji = "TEST_snap_done"
    db_session.commit()
    try:
        client = MagicMock()
        client.chat_postMessage.return_value = {"ok": True, "ts": "999.1"}
        with patch(
            "app.practices.availability.validate_emoji_available",
            return_value=(True, []),
        ) as validate, patch(
            "app.practices.availability.get_slack_client", return_value=client
        ), patch(
            "app.slack.practices._config._load_practice_config",
            return_value={"lead_availability": {"done_emoji": "TEST_renamed_done"}},
        ):
            result = open_poll(poll)

        assert result["success"] is True
        assert validate.call_args.args[0][-1] == "TEST_snap_done", (
            "validation must check the poll's snapshot, not the current config"
        )
        seeded = [c.kwargs["name"] for c in client.reactions_add.call_args_list]
        assert "TEST_snap_done" in seeded
        assert "TEST_renamed_done" not in seeded, (
            "seeding the renamed config value would put a reaction on the "
            "message that the poll's accounting never counts"
        )
    finally:
        _cleanup_practices([ready], poll)


def test_open_poll_missing_done_emoji_names_the_done_config_key(db_session, app):
    """The refusal message must point at lead_availability.done_emoji when the
    DONE emoji is what's missing -- naming letter_emoji sends the director to
    the wrong key."""
    ready = _ready_practice(4)
    db_session.commit()
    poll = build_poll(_START, _END)
    poll.done_emoji = "TEST_custom_done"
    db_session.commit()
    try:
        client = MagicMock()
        client.emoji_list.return_value = {"emoji": {"letter_a": "u"}}
        with patch(
            "app.practices.availability_emoji.get_slack_client", return_value=client
        ), patch(
            "app.practices.availability.get_slack_client", return_value=client
        ):
            result = open_poll(poll)

        assert result["success"] is False
        assert "TEST_custom_done" in result["error"]
        assert "lead_availability.done_emoji" in result["error"]
        assert "letter_emoji" not in result["error"], (
            "no letter is missing here; naming letter_emoji is misdirection"
        )
        client.chat_postMessage.assert_not_called()
    finally:
        _cleanup_practices([ready], poll)
