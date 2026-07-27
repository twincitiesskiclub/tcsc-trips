"""Only the shadow roster gets DM'd. End to end, counting real DM calls.

The narrow unit tests in test_availability_nudge.py pin participants_to_nudge's
filtering. This pins the property the shadow month actually depends on: that
running the real nudge job, against a poll built the way the admin route builds
it, produces a Slack DM for roster members and NOBODY else — including people
who are in the live eligible pool, and people who got a participant row by
reacting to the poll rather than by being invited to it.

Written because that guarantee was inert once already: participant rows have a
second creation path (a reaction from anyone Slack-linked), and selecting nudge
targets on poll_id + PENDING alone let non-roster members be DM'd during the
one month whose entire purpose is that no real lead is.
"""

import uuid
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from app.models import AppConfig, SlackUser, Tag, User, db
from app.practices.availability import send_nudges
from app.practices.availability_models import (
    LeadAvailabilityParticipant,
    LeadAvailabilityPoll,
    ParticipantStatus,
    PollStatus,
)

_STARTS_ON = date(2099, 6, 8)
_ENDS_ON = date(2099, 6, 30)
_OPENED = datetime(2099, 6, 8, 9, 0)
_RUN = datetime(2099, 6, 11, 8, 0)  # day 3: everyone below is due a first nudge


def _person(name, *, tagged):
    """A Slack-linked user, optionally in the live eligible pool."""
    suffix = uuid.uuid4().hex[:10]
    slack_user = SlackUser(slack_uid=f"TEST-SHADOW-{suffix}")
    db.session.add(slack_user)
    db.session.flush()
    user = User(first_name=f"TEST {name}", last_name="Containment",
                email=f"test-containment-{name.lower()}-{suffix}@example.invalid",
                slack_user_id=slack_user.id)
    if tagged:
        tag = Tag.query.filter_by(name="PRACTICES_LEAD").first() or Tag(
            name="PRACTICES_LEAD", display_name="Practices Lead")
        db.session.add(tag)
        user.tags = [tag]
    db.session.add(user)
    db.session.flush()
    return user, slack_user.slack_uid


@pytest.fixture
def preserve_shadow_roster(db_session):
    """Save/restore the roster row -- prod's real one lives under this key."""
    existing = AppConfig.query.filter_by(key="lead_availability.shadow_roster").first()
    had_row = existing is not None
    original = (existing.value, existing.description, existing.category) if had_row else None
    yield
    db.session.rollback()
    if had_row:
        value, description, category = original
        AppConfig.set(key="lead_availability.shadow_roster", value=value,
                      description=description, category=category)
    else:
        AppConfig.query.filter_by(key="lead_availability.shadow_roster").delete()
    db.session.commit()


def test_a_shadow_poll_dms_the_roster_and_nobody_else(db_session, app, preserve_shadow_roster):
    roster_member, roster_uid = _person("Roster", tagged=True)
    # In the LIVE pool but not on the roster: the 57-person population that
    # must hear nothing during the shadow month.
    live_pool_member, live_uid = _person("LivePool", tagged=True)
    # Not in the pool at all, but reacted to the poll -- this is the path that
    # created participant rows the pool filter used to miss entirely.
    reactor, reactor_uid = _person("Reactor", tagged=False)

    poll = LeadAvailabilityPoll(
        starts_on=_STARTS_ON, ends_on=_ENDS_ON,
        channel_id="C0B3Y71PG92", message_ts="1.1",
        status=PollStatus.OPEN, opened_at=_OPENED, is_shadow=True,
    )
    db_session.add(poll)
    db_session.flush()

    # All three PENDING and all three due, so only the pool gate can separate them.
    for person in (roster_member, live_pool_member, reactor):
        db_session.add(LeadAvailabilityParticipant(
            poll_id=poll.id, user_id=person.id, status=ParticipantStatus.PENDING))

    AppConfig.set(key="lead_availability.shadow_roster", value=[roster_uid],
                  description="test", category="practices")
    db_session.commit()

    poll_id = poll.id
    user_ids = [roster_member.id, live_pool_member.id, reactor.id]
    slack_user_ids = [u.slack_user_id for u in (roster_member, live_pool_member, reactor)]

    try:
        client = MagicMock()
        with patch("app.slack.practices.availability_nudge.get_slack_client",
                   return_value=client), \
             patch("app.slack.practices.availability_nudge.poll_permalink",
                   return_value="https://example.invalid/p"):
            result = send_nudges(poll, now=_RUN)

        dm_targets = [c.kwargs["channel"] for c in client.chat_postMessage.call_args_list]

        assert dm_targets == [roster_uid], (
            "exactly one DM, to the roster member. Got: "
            f"{dm_targets} (live-pool={live_uid}, reactor={reactor_uid})"
        )
        assert result["sent"] == 1
        assert live_uid not in dm_targets, \
            "a live-pool lead must hear nothing during the shadow month"
        assert reactor_uid not in dm_targets, \
            "reacting to the poll must not enroll someone for DMs"
    finally:
        db.session.rollback()
        stored = db.session.get(LeadAvailabilityPoll, poll_id)
        if stored is not None:
            db.session.delete(stored)
        db.session.flush()
        for user_id in user_ids:
            user = db.session.get(User, user_id)
            if user is not None:
                user.tags = []
                db.session.delete(user)
        db.session.flush()
        for slack_user_id in slack_user_ids:
            slack_user = db.session.get(SlackUser, slack_user_id)
            if slack_user is not None:
                db.session.delete(slack_user)
        db.session.commit()


def test_an_empty_roster_dms_absolutely_nobody(db_session, app, preserve_shadow_roster):
    """Fail closed. A roster that resolves to nothing must send zero DMs, never
    fall back to the live pool -- a misconfiguration that DMs 57 people is the
    exact disaster shadow mode exists to prevent.
    """
    pool_member, pool_uid = _person("PoolOnly", tagged=True)

    poll = LeadAvailabilityPoll(
        starts_on=_STARTS_ON, ends_on=_ENDS_ON,
        channel_id="C0B3Y71PG92", message_ts="1.2",
        status=PollStatus.OPEN, opened_at=_OPENED, is_shadow=True,
    )
    db_session.add(poll)
    db_session.flush()
    db_session.add(LeadAvailabilityParticipant(
        poll_id=poll.id, user_id=pool_member.id, status=ParticipantStatus.PENDING))

    AppConfig.set(key="lead_availability.shadow_roster", value=[],
                  description="test", category="practices")
    db_session.commit()

    poll_id, user_id = poll.id, pool_member.id
    slack_user_id = pool_member.slack_user_id

    try:
        client = MagicMock()
        with patch("app.slack.practices.availability_nudge.get_slack_client",
                   return_value=client):
            result = send_nudges(poll, now=_RUN)

        assert client.chat_postMessage.call_count == 0, (
            f"an empty roster must DM nobody; it DM'd {pool_uid}"
        )
        assert result == {"sent": 0, "skipped": 0}
    finally:
        db.session.rollback()
        stored = db.session.get(LeadAvailabilityPoll, poll_id)
        if stored is not None:
            db.session.delete(stored)
        db.session.flush()
        user = db.session.get(User, user_id)
        if user is not None:
            user.tags = []
            db.session.delete(user)
        db.session.flush()
        slack_user = db.session.get(SlackUser, slack_user_id)
        if slack_user is not None:
            db.session.delete(slack_user)
        db.session.commit()
