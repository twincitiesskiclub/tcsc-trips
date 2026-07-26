"""Nudge eligibility — the cadence rules are the whole point.

Adapted from the task brief for this repo's real-database test conventions
(see tests/practices/conftest.py): year-2099 dates, "TEST " prefixed rows,
and try/finally cleanup with rollback-first. The brief's literal fixtures
used bare integers (1, 2, 3) for LeadAvailabilityParticipant.user_id and a
"user_id" kwarg on SlackUser; neither is valid against the actual
FK-constrained schema (users.id is a foreign key on participants, and
SlackUser has no user_id column -- the FK lives on User.slack_user_id), so
every participant here is backed by a real User row, matching the fix
already made for this same brief mismatch in
tests/slack/test_availability_reactions.py.

Every ``_cleanup(poll_id, user_ids)`` call below is passed plain ints
captured immediately after ``flush()``/``commit()``, never the ORM objects'
``.id`` attributes evaluated at the finally site. Python evaluates a call's
arguments before invoking it, so ``_cleanup(poll.id, [user.id])`` would
resolve ``poll.id``/``user.id`` *before* ``_cleanup``'s own
``db.session.rollback()`` ever runs. On a session already poisoned by a
failing assertion (e.g. a prior statement raised, leaving the transaction
aborted), that attribute access hits SQLAlchemy's expired-attribute refresh
and raises ``PendingRollbackError`` -- so the rollback that's supposed to
make cleanup safe never executes, and rows leak. Capturing the ids as plain
ints up front sidesteps ORM attribute access entirely at the finally site.
"""

from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

from slack_sdk.errors import SlackApiError

from app.models import AppConfig, SlackUser, Tag, User, db
from app.practices.availability import (
    eligible_leads,
    participants_to_nudge,
    send_nudges,
    shadow_roster_leads,
    sync_participants,
)
from app.practices.availability_models import (
    LeadAvailabilityParticipant,
    LeadAvailabilityPoll,
    ParticipantStatus,
    PollStatus,
)

OPENED = datetime(2099, 7, 21, 9, 0)
_STARTS_ON = date(2099, 7, 21)
_ENDS_ON = date(2099, 8, 13)


def _poll(db_session, is_shadow=False, opened_at=OPENED):
    poll = LeadAvailabilityPoll(
        starts_on=_STARTS_ON, ends_on=_ENDS_ON,
        channel_id="TEST-CHANNEL-NUDGE", message_ts="1.1",
        status=PollStatus.OPEN, opened_at=opened_at, is_shadow=is_shadow,
    )
    db_session.add(poll)
    db_session.flush()
    return poll


def _user(db_session, name, with_slack=False, in_pool=True):
    """A real User row -- LeadAvailabilityParticipant.user_id is FK-constrained
    to users.id, so a bare int (as in the brief's literal fixtures) would
    violate the constraint against this real Postgres dev database.

    Tagged PRACTICES_LEAD by default, because participants_to_nudge now
    re-checks the poll's pool and an untagged user is (correctly) never
    nudged. Tagging for real rather than patching eligible_leads() keeps these
    cadence tests exercising the actual pool rules; the tag row is
    get-or-create and never deleted, matching the fixed reference-data
    convention in test_availability_service.py. Pass in_pool=False for the
    tests that specifically need somebody outside the pool.
    """
    suffix = uuid4().hex
    slack_user_id = None
    if with_slack:
        slack_user = SlackUser(slack_uid=f"TEST-U-{suffix}")
        db_session.add(slack_user)
        db_session.flush()
        slack_user_id = slack_user.id
    user = User(first_name=f"TEST {name}", last_name="Nudge",
                email=f"test-nudge-{name.lower()}-{suffix}@example.test",
                slack_user_id=slack_user_id)
    if in_pool:
        tag = Tag.query.filter_by(name="PRACTICES_LEAD").first() or Tag(
            name="PRACTICES_LEAD", display_name="Practices Lead")
        db_session.add(tag)
        user.tags = [tag]
    db_session.add(user)
    db_session.flush()
    return user


def _participant(db_session, poll, user, **kw):
    p = LeadAvailabilityParticipant(poll_id=poll.id, user_id=user.id, **kw)
    db_session.add(p)
    db_session.flush()
    return p


def _cleanup(poll_id=None, user_ids=None):
    """Delete only the rows this test created.

    Rolls back first so a poisoned session (e.g. a prior statement that
    raised and left the transaction aborted) doesn't turn this cleanup
    itself into an error that leaves debris behind for the next test.
    Deleting the poll first cascades to its participants (poll_id FK); each
    user's slack_user (if any) must go after the user, since User.slack_user_id
    is the FK pointing at it.

    Callers must pass plain ints captured before entering the try block --
    see the module docstring for why passing ``poll.id`` / ``user.id``
    directly at the call site defeats the rollback below.
    """
    db.session.rollback()
    if poll_id is not None:
        poll = db.session.get(LeadAvailabilityPoll, poll_id)
        if poll is not None:
            db.session.delete(poll)
    db.session.flush()
    for user_id in (user_ids or []):
        user = db.session.get(User, user_id)
        if user is None:
            continue
        slack_user_id = user.slack_user_id
        db.session.delete(user)
        db.session.flush()
        if slack_user_id is not None:
            slack_user = db.session.get(SlackUser, slack_user_id)
            if slack_user is not None:
                db.session.delete(slack_user)
    db.session.commit()


def test_nobody_is_nudged_before_day_three(db_session):
    poll = _poll(db_session)
    user = _user(db_session, "Ada")
    poll_id, user_id = poll.id, user.id
    _participant(db_session, poll, user, status=ParticipantStatus.PENDING)
    db_session.commit()

    try:
        assert participants_to_nudge(poll, now=OPENED + timedelta(days=2)) == []
    finally:
        _cleanup(poll_id, [user_id])


def test_pending_participant_is_nudged_on_day_three(db_session):
    poll = _poll(db_session)
    user = _user(db_session, "Ada")
    poll_id, user_id = poll.id, user.id
    p = _participant(db_session, poll, user, status=ParticipantStatus.PENDING)
    participant_id = p.id
    db_session.commit()

    try:
        due = participants_to_nudge(poll, now=OPENED + timedelta(days=3))
        assert [x.id for x in due] == [participant_id]
    finally:
        _cleanup(poll_id, [user_id])


def test_responded_and_done_and_opted_out_are_never_nudged(db_session):
    poll = _poll(db_session)
    users = [_user(db_session, f"U{i}") for i in range(3)]
    poll_id, user_ids = poll.id, [u.id for u in users]
    for user, status in zip(users, (ParticipantStatus.RESPONDED, ParticipantStatus.DONE,
                                     ParticipantStatus.OPTED_OUT)):
        _participant(db_session, poll, user, status=status)
    db_session.commit()

    try:
        assert participants_to_nudge(poll, now=OPENED + timedelta(days=10)) == []
    finally:
        _cleanup(poll_id, user_ids)


def test_nudges_are_spaced_at_least_two_days(db_session):
    poll = _poll(db_session)
    user = _user(db_session, "Ada")
    poll_id, user_id = poll.id, user.id
    _participant(db_session, poll, user, status=ParticipantStatus.PENDING,
                 nudge_count=1, last_nudged_at=OPENED + timedelta(days=3))
    db_session.commit()

    try:
        assert participants_to_nudge(poll, now=OPENED + timedelta(days=4)) == []
        assert len(participants_to_nudge(poll, now=OPENED + timedelta(days=5))) == 1
    finally:
        _cleanup(poll_id, [user_id])


def test_three_nudges_is_the_ceiling(db_session):
    poll = _poll(db_session)
    user = _user(db_session, "Ada")
    poll_id, user_id = poll.id, user.id
    _participant(db_session, poll, user, status=ParticipantStatus.PENDING,
                 nudge_count=3, last_nudged_at=OPENED + timedelta(days=7))
    db_session.commit()

    try:
        # Day 20 is still inside the block (ends 2099-08-13): past the end,
        # participants_to_nudge short-circuits on the ended-block gate and
        # this would pass without MAX_NUDGES doing any work.
        assert participants_to_nudge(poll, now=OPENED + timedelta(days=20)) == [], \
            "3 sends is the ceiling; more trains people to mute the bot"
    finally:
        _cleanup(poll_id, [user_id])


# ---------------------------------------------------------------------------
# Task 4: nudge boundaries are calendar days, not hour deltas. The nudge job
# runs at a fixed 08:00 Central, so a 72-hour rule skips the day-3 run for any
# poll opened after 08:00 on day 0 (70 hours old at Thursday 08:00 for a
# Monday 10:00 open) and the first nudge slips to day 4. Same class of bug in
# the last_nudged_at spacing check: a day-3 send recorded at 08:00:30 leaves
# the day-5 08:00:00 run 30 seconds short of 48 hours, slipping it to day 6.
# These tests drive `now` at the job's real fixed run time to pin both
# boundaries exactly.
# ---------------------------------------------------------------------------

# Poll opened mid-morning Monday 2099-07-21; the daily job runs at 08:00.
_OPENED_DAY0_1000 = datetime(2099, 7, 21, 10, 0)
_RUN_DAY2 = datetime(2099, 7, 23, 8, 0)
_RUN_DAY3 = datetime(2099, 7, 24, 8, 0)
_RUN_DAY4 = datetime(2099, 7, 25, 8, 0)
_RUN_DAY5 = datetime(2099, 7, 26, 8, 0)


def test_poll_opened_midmorning_gets_first_nudge_on_the_day3_run(db_session):
    poll = _poll(db_session, opened_at=_OPENED_DAY0_1000)
    user = _user(db_session, "Ada")
    poll_id, user_id = poll.id, user.id
    participant_id = _participant(
        db_session, poll, user, status=ParticipantStatus.PENDING).id
    db_session.commit()

    try:
        due = participants_to_nudge(poll, now=_RUN_DAY3)
        assert [x.id for x in due] == [participant_id], (
            "a poll opened 10:00 on day 0 is only 70 hours old at the day-3 "
            "08:00 run; a 72-hour rule skips it and the first nudge slips to "
            "day 4 -- the boundary must be calendar days"
        )
    finally:
        _cleanup(poll_id, [user_id])


def test_poll_opened_midmorning_is_not_nudged_on_the_day2_run(db_session):
    poll = _poll(db_session, opened_at=_OPENED_DAY0_1000)
    user = _user(db_session, "Ada")
    poll_id, user_id = poll.id, user.id
    _participant(db_session, poll, user, status=ParticipantStatus.PENDING)
    db_session.commit()

    try:
        assert participants_to_nudge(poll, now=_RUN_DAY2) == [], (
            "day 2 is too early -- an off-by-one in the permissive direction "
            "DMs everyone every morning"
        )
    finally:
        _cleanup(poll_id, [user_id])


def test_poll_opened_just_before_midnight_still_nudges_on_the_day3_run(db_session):
    poll = _poll(db_session, opened_at=datetime(2099, 7, 21, 23, 59))
    user = _user(db_session, "Ada")
    poll_id, user_id = poll.id, user.id
    participant_id = _participant(
        db_session, poll, user, status=ParticipantStatus.PENDING).id
    db_session.commit()

    try:
        due = participants_to_nudge(poll, now=_RUN_DAY3)
        assert [x.id for x in due] == [participant_id], (
            "23:59 on day 0 still counts as day 0 -- the day-3 run must nudge"
        )
    finally:
        _cleanup(poll_id, [user_id])


def test_spacing_is_calendar_days_across_fixed_morning_runs(db_session):
    """Nudged on the day-3 run -> skipped on day 4, eligible on day 5.

    last_nudged_at carries 08:00:30 because the job never fires at exactly
    :00.000 -- under an hours-based rule the day-5 08:00:00 run would be 30
    seconds short of 48 hours and slip to day 6.
    """
    poll = _poll(db_session, opened_at=_OPENED_DAY0_1000)
    user = _user(db_session, "Ada")
    poll_id, user_id = poll.id, user.id
    _participant(db_session, poll, user, status=ParticipantStatus.PENDING,
                 nudge_count=1, last_nudged_at=datetime(2099, 7, 24, 8, 0, 30))
    db_session.commit()

    try:
        assert participants_to_nudge(poll, now=_RUN_DAY4) == [], \
            "nudged yesterday -- MIN_DAYS_BETWEEN_NUDGES = 2 must hold"
        assert len(participants_to_nudge(poll, now=_RUN_DAY5)) == 1, (
            "two calendar days after the last nudge -- due again even though "
            "the wall-clock gap is 30 seconds short of 48 hours"
        )
    finally:
        _cleanup(poll_id, [user_id])


def test_max_nudges_still_caps_at_fixed_morning_runs(db_session):
    poll = _poll(db_session, opened_at=_OPENED_DAY0_1000)
    user = _user(db_session, "Ada")
    poll_id, user_id = poll.id, user.id
    _participant(db_session, poll, user, status=ParticipantStatus.PENDING,
                 nudge_count=3, last_nudged_at=datetime(2099, 7, 28, 8, 0, 30))
    db_session.commit()

    try:
        # Inside the block window on purpose -- see test_three_nudges_is_the
        # _ceiling: a `now` past ends_on passes on the ended-block gate instead.
        assert participants_to_nudge(poll, now=datetime(2099, 8, 10, 8, 0)) == []
    finally:
        _cleanup(poll_id, [user_id])


def test_nobody_is_nudged_once_the_block_has_ended(db_session):
    """The nudge job runs 08:00 and the close job 08:30, so the morning after
    a block's last day the poll is still OPEN when nudges are computed. DMing
    someone for availability on a block that has already finished is noise
    they can do nothing about, so that final run is skipped -- on the poll's
    own dates, not on the close job having got there first.
    """
    poll = _poll(db_session)
    user = _user(db_session, "Ada")
    poll_id, user_id = poll.id, user.id
    _participant(db_session, poll, user, status=ParticipantStatus.PENDING)
    db_session.commit()

    try:
        # 08:00 on the block's last day: still due, the block is live today.
        assert len(participants_to_nudge(
            poll, now=datetime(_ENDS_ON.year, _ENDS_ON.month, _ENDS_ON.day, 8, 0))) == 1

        # 08:00 the next morning, 30 minutes before the close job runs.
        day_after = _ENDS_ON + timedelta(days=1)
        assert participants_to_nudge(
            poll, now=datetime(day_after.year, day_after.month, day_after.day, 8, 0)) == [], \
            "the block ended yesterday; there is nothing left to volunteer for"
    finally:
        _cleanup(poll_id, [user_id])


def test_sync_participants_adds_new_leads_only(db_session):
    poll = _poll(db_session)
    existing_user = _user(db_session, "Existing")
    new_user = _user(db_session, "New")
    poll_id = poll.id
    user_ids = [existing_user.id, new_user.id]
    _participant(db_session, poll, existing_user, status=ParticipantStatus.RESPONDED)
    db_session.commit()

    try:
        with patch("app.practices.availability.eligible_leads",
                   return_value=[existing_user, new_user]):
            added = sync_participants(poll)

        assert added == 1
        assert LeadAvailabilityParticipant.query.filter_by(poll_id=poll_id).count() == 2
    finally:
        _cleanup(poll_id, user_ids)


def test_send_nudges_records_the_send(db_session, app):
    poll = _poll(db_session)
    user = _user(db_session, "Ada", with_slack=True)
    poll_id, user_id = poll.id, user.id
    _participant(db_session, poll, user, status=ParticipantStatus.PENDING)
    db_session.commit()

    client = MagicMock()
    client.chat_getPermalink.return_value = {"permalink": "https://slack/p/1"}

    try:
        with patch("app.slack.practices.availability_nudge.get_slack_client",
                   return_value=client):
            result = send_nudges(poll, now=OPENED + timedelta(days=3))

        assert result["sent"] == 1
        participant = LeadAvailabilityParticipant.query.filter_by(
            poll_id=poll_id, user_id=user_id).one()
        assert participant.nudge_count == 1
        assert participant.last_nudged_at is not None
    finally:
        _cleanup(poll_id, [user_id])


# ---------------------------------------------------------------------------
# Fix 3: a failed DM must not consume that person's nudge budget, and
# send_nudges must default `now` to now_central_naive() rather than
# datetime.utcnow(). Both behaviours previously passed with 7/7 tests green
# even when broken -- these two tests close that gap.
# ---------------------------------------------------------------------------

def test_failed_dm_does_not_consume_nudge_budget(db_session, app):
    poll = _poll(db_session)
    ok_user = _user(db_session, "Ok", with_slack=True)
    fail_user = _user(db_session, "Fail", with_slack=True)
    poll_id = poll.id
    ok_id, fail_id = ok_user.id, fail_user.id
    ok_slack_uid = ok_user.slack_user.slack_uid
    fail_slack_uid = fail_user.slack_user.slack_uid
    _participant(db_session, poll, ok_user, status=ParticipantStatus.PENDING)
    _participant(db_session, poll, fail_user, status=ParticipantStatus.PENDING)
    db_session.commit()

    client = MagicMock()
    client.chat_getPermalink.return_value = {"permalink": "https://slack/p/1"}

    def _post_message(channel, **kwargs):
        if channel == fail_slack_uid:
            raise SlackApiError("boom", {"error": "channel_not_found"})
        assert channel == ok_slack_uid
        return {"ts": "123.456"}

    client.chat_postMessage.side_effect = _post_message

    try:
        with patch("app.slack.practices.availability_nudge.get_slack_client",
                   return_value=client):
            result = send_nudges(poll, now=OPENED + timedelta(days=3))

        assert result == {"sent": 1, "skipped": 1}

        ok_participant = LeadAvailabilityParticipant.query.filter_by(
            poll_id=poll_id, user_id=ok_id).one()
        fail_participant = LeadAvailabilityParticipant.query.filter_by(
            poll_id=poll_id, user_id=fail_id).one()

        assert ok_participant.nudge_count == 1
        assert ok_participant.last_nudged_at is not None

        assert fail_participant.nudge_count == 0, \
            "a failed DM must not consume the nudge budget -- they haven't " \
            "actually been reminded, so the next run must retry"
        assert fail_participant.last_nudged_at is None
    finally:
        _cleanup(poll_id, [ok_id, fail_id])


def test_send_nudges_defaults_now_to_now_central_naive(db_session, app):
    poll = _poll(db_session)
    user = _user(db_session, "Ada", with_slack=True)
    poll_id, user_id = poll.id, user.id
    _participant(db_session, poll, user, status=ParticipantStatus.PENDING)
    db_session.commit()

    fixed_now = OPENED + timedelta(days=3)
    client = MagicMock()
    client.chat_getPermalink.return_value = {"permalink": "https://slack/p/1"}
    client.chat_postMessage.return_value = {"ts": "123.456"}

    try:
        with patch("app.practices.availability.now_central_naive", return_value=fixed_now), \
             patch("app.slack.practices.availability_nudge.get_slack_client",
                   return_value=client):
            result = send_nudges(poll)  # no `now=` -- must default correctly

        assert result["sent"] == 1
        participant = LeadAvailabilityParticipant.query.filter_by(
            poll_id=poll_id, user_id=user_id).one()
        assert participant.last_nudged_at == fixed_now, (
            "send_nudges must default `now` to now_central_naive(); reverting "
            "to datetime.utcnow() reintroduces a 5-6 hour skew at the day-3 "
            "boundary, and this is the only test that reaches send_nudges "
            "without passing now= explicitly"
        )
    finally:
        _cleanup(poll_id, [user_id])


# ---------------------------------------------------------------------------
# Fix 1: shadow mode must restrict who gets nudged. `sync_participants` must
# resolve the shadow roster (not the live tag pool) when poll.is_shadow, and
# must fail closed -- an unset/empty roster nudges nobody, never falls back
# to eligible_leads().
# ---------------------------------------------------------------------------

def test_shadow_poll_uses_the_shadow_roster_not_the_live_pool(db_session):
    poll = _poll(db_session, is_shadow=True)
    roster_user = _user(db_session, "Roster", with_slack=True)
    live_user = _user(db_session, "Live")  # would come back from eligible_leads()
    poll_id = poll.id
    user_ids = [roster_user.id, live_user.id]
    roster_slack_uid = roster_user.slack_user.slack_uid
    db_session.commit()

    try:
        with patch("app.models.AppConfig.get", return_value=[roster_slack_uid]), \
             patch("app.practices.availability.eligible_leads",
                   return_value=[roster_user, live_user]):
            added = sync_participants(poll)

        assert added == 1
        participant_user_ids = {
            row.user_id for row in
            LeadAvailabilityParticipant.query.filter_by(poll_id=poll_id).all()
        }
        assert participant_user_ids == {roster_user.id}, (
            "a shadow poll must only ever add the shadow roster as "
            "participants -- eligible_leads() (the live pool) must not be "
            "consulted at all"
        )
    finally:
        _cleanup(poll_id, user_ids)


def test_shadow_poll_with_empty_roster_fails_closed(db_session):
    """An unset or empty shadow_roster config must nudge nobody -- it must
    NOT silently fall back to the live tag pool. A misconfiguration that DMs
    everyone is the exact disaster shadow mode exists to prevent.
    """
    poll = _poll(db_session, is_shadow=True)
    live_user = _user(db_session, "Live")
    poll_id = poll.id
    user_ids = [live_user.id]
    db_session.commit()

    try:
        with patch("app.models.AppConfig.get", return_value=[]), \
             patch("app.practices.availability.eligible_leads",
                   return_value=[live_user]) as eligible_mock:
            added = sync_participants(poll)

        assert added == 0
        assert LeadAvailabilityParticipant.query.filter_by(poll_id=poll_id).count() == 0
        eligible_mock.assert_not_called()
    finally:
        _cleanup(poll_id, user_ids)


def test_non_shadow_poll_uses_the_live_pool(db_session):
    poll = _poll(db_session, is_shadow=False)
    live_user = _user(db_session, "Live")
    poll_id = poll.id
    user_ids = [live_user.id]
    db_session.commit()

    try:
        with patch("app.practices.availability.eligible_leads",
                   return_value=[live_user]) as eligible_mock, \
             patch("app.practices.availability.shadow_roster_leads") as shadow_mock:
            added = sync_participants(poll)

        assert added == 1
        eligible_mock.assert_called_once()
        shadow_mock.assert_not_called()
        assert {
            row.user_id for row in
            LeadAvailabilityParticipant.query.filter_by(poll_id=poll_id).all()
        } == {live_user.id}
    finally:
        _cleanup(poll_id, user_ids)


def test_shadow_roster_null_config_row_resolves_to_an_empty_roster(db_session):
    """A `lead_availability.shadow_roster` row storing JSON null must fail
    closed to an empty roster, exactly like a missing row -- AppConfig.get
    returns the row's value (None) whenever the row exists, and falling back
    to the live tag pool here would DM the real 10-17 person lead pool during
    the shadow month.

    Writes a REAL null row rather than mocking AppConfig.get: mocking the
    getter would merely stipulate that a null row yields None instead of
    proving it. Save/restore, never unconditional delete -- real
    configuration lives in this database.
    """
    key = "lead_availability.shadow_roster"
    db.session.rollback()
    existing = AppConfig.query.filter_by(key=key).first()
    had_row = existing is not None
    original = (
        (existing.value, existing.description, existing.category)
        if had_row else None
    )
    AppConfig.set(key=key, value=None, description="TEST null roster",
                  category="practices")
    db.session.commit()
    try:
        assert shadow_roster_leads() == [], (
            "a JSON-null shadow_roster row must resolve to an empty roster, "
            "never fall back to the live tag pool"
        )
    finally:
        db.session.rollback()
        if had_row:
            value, description, category = original
            AppConfig.set(key=key, value=value,
                          description=description, category=category)
        else:
            AppConfig.query.filter_by(key=key).delete()
        db.session.commit()


def test_shadow_roster_leads_resolves_slack_uids_to_users(db_session):
    """Unit-level check on shadow_roster_leads() itself, independent of
    sync_participants: unknown slack uids in the roster are skipped rather
    than raising, and a known one resolves to its User via SlackUser.
    """
    user = _user(db_session, "Roster", with_slack=True)
    user_id = user.id
    slack_uid = user.slack_user.slack_uid
    db_session.commit()

    try:
        with patch("app.models.AppConfig.get",
                   return_value=[slack_uid, "TEST-UNKNOWN-UID"]):
            result = shadow_roster_leads()
        assert [u.id for u in result] == [user_id]
    finally:
        _cleanup(None, [user_id])


# ---------------------------------------------------------------------------
# The pool gate has to bite at NUDGE time, not only at sync time.
#
# sync_participants is not the only way a participant row appears:
# _participant() in app/slack/practices/availability_reactions.py creates one
# for ANY Slack-linked user who reacts to the poll, with no pool check -- and
# reconcile_poll (which the nudge job runs immediately before send_nudges)
# resets such a row to PENDING once its reaction is withdrawn. So selecting
# nudge targets by poll_id + PENDING alone let a non-pool member be DMed,
# which defeats the two containment rules that matter most:
#
#   - shadow mode: the shadow channel holds real coaches who are not on the
#     roster, and the whole point of the shadow month is that no real lead is
#     DMed. Shadow-ness is persisted on the poll, so the gate uses that.
#   - the ALUMNI exclusion: a lapsed lead-tagged alumnus is deliberately out
#     of the pool because "DMing them every block is how the bot gets muted
#     by the people it depends on" (eligible_leads' own docstring).
#
# Filtering at nudge time rather than refusing to create the row keeps the
# availability record for someone who volunteered -- the reaction still counts
# -- while making sure the DM only goes to people who were actually asked.
# ---------------------------------------------------------------------------

def test_shadow_poll_does_not_nudge_a_participant_off_the_roster(db_session):
    poll = _poll(db_session, is_shadow=True)
    roster_user = _user(db_session, "Roster", with_slack=True)
    intruder = _user(db_session, "Intruder", with_slack=True, in_pool=False)
    poll_id = poll.id
    user_ids = [roster_user.id, intruder.id]
    roster_slack_uid = roster_user.slack_user.slack_uid
    # Both PENDING: the intruder's row is what a reaction-then-unreact leaves
    # behind, exactly as reconcile_poll would write it.
    _participant(db_session, poll, roster_user, status=ParticipantStatus.PENDING)
    _participant(db_session, poll, intruder, status=ParticipantStatus.PENDING)
    db_session.commit()

    try:
        with patch("app.models.AppConfig.get", return_value=[roster_slack_uid]):
            due = participants_to_nudge(poll, now=OPENED + timedelta(days=3))

        assert [p.user_id for p in due] == [roster_user.id], (
            "a shadow poll must only DM the shadow roster -- a participant row "
            "created by a reaction from someone off the roster must not be nudged"
        )
    finally:
        _cleanup(poll_id, user_ids)


def test_live_poll_does_not_nudge_a_participant_outside_the_eligible_pool(db_session):
    poll = _poll(db_session, is_shadow=False)
    lead = _user(db_session, "Lead", with_slack=True)
    outsider = _user(db_session, "Outsider", with_slack=True, in_pool=False)
    poll_id = poll.id
    user_ids = [lead.id, outsider.id]
    _participant(db_session, poll, lead, status=ParticipantStatus.PENDING)
    _participant(db_session, poll, outsider, status=ParticipantStatus.PENDING)
    db_session.commit()

    try:
        # No patching: the outsider genuinely carries no eligible tag, so the
        # real eligible_leads() excludes them. That is the state left behind
        # by an ALUMNI lead with no coach tag, a DROPPED member, or someone
        # whose tag was pulled mid-block.
        due = participants_to_nudge(poll, now=OPENED + timedelta(days=3))

        assert [p.user_id for p in due] == [lead.id], (
            "only people the pool rules say may be asked can be DMed"
        )
    finally:
        _cleanup(poll_id, user_ids)


def test_shadow_poll_with_an_unresolvable_roster_nudges_nobody(db_session):
    """Fail closed at nudge time too: an empty resolved roster must mean zero
    DMs, never "no filter, so everyone".
    """
    poll = _poll(db_session, is_shadow=True)
    someone = _user(db_session, "Someone", with_slack=True)
    poll_id = poll.id
    user_ids = [someone.id]
    _participant(db_session, poll, someone, status=ParticipantStatus.PENDING)
    db_session.commit()

    try:
        with patch("app.models.AppConfig.get", return_value=[]):
            due = participants_to_nudge(poll, now=OPENED + timedelta(days=3))

        assert due == [], (
            "an unset/empty shadow roster must nudge nobody -- an empty pool "
            "must not be treated as 'no filter'"
        )
    finally:
        _cleanup(poll_id, user_ids)
