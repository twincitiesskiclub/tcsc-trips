"""Database-backed coverage for Slack reaction attendance routing."""

from datetime import datetime
from uuid import uuid4

import pytest

from app import create_app
from app.models import SlackUser, User, db
from app.practices.interfaces import PracticeStatus, RSVPStatus
from app.practices.models import Practice, PracticeRSVP
from app.slack.practices.reactions import handle_attendance_reaction
import app.slack.bolt_app as bolt_module


TEST_PREFIX = "rrt-"


def _cleanup_test_records():
    practices = Practice.query.filter(
        Practice.airtable_id.like(f"{TEST_PREFIX}%")
    ).all()
    practice_ids = [practice.id for practice in practices]
    if practice_ids:
        PracticeRSVP.query.filter(
            PracticeRSVP.practice_id.in_(practice_ids)
        ).delete(synchronize_session=False)
    for practice in practices:
        db.session.delete(practice)

    users = User.query.filter(
        User.email.like(f"{TEST_PREFIX}%@example.test")
    ).all()
    user_ids = [user.id for user in users]
    if user_ids:
        PracticeRSVP.query.filter(
            PracticeRSVP.user_id.in_(user_ids)
        ).delete(synchronize_session=False)
    for user in users:
        db.session.delete(user)

    SlackUser.query.filter(
        SlackUser.slack_uid.like(f"{TEST_PREFIX}%")
    ).delete(synchronize_session=False)
    db.session.commit()


@pytest.fixture
def app():
    application = create_app()
    application.config.update(TESTING=True, SECRET_KEY="test-secret-key")
    return application


@pytest.fixture
def db_session(app):
    with app.app_context():
        db.create_all()
        _cleanup_test_records()
        yield db
        db.session.rollback()
        _cleanup_test_records()


@pytest.fixture
def linked_user(db_session):
    suffix = uuid4().hex
    slack_user = SlackUser(slack_uid=f"{TEST_PREFIX}{suffix}")
    db.session.add(slack_user)
    db.session.flush()
    user = User(
        slack_user_id=slack_user.id,
        first_name="Reaction",
        last_name="Tester",
        email=f"{TEST_PREFIX}{suffix}@example.test",
    )
    db.session.add(user)
    db.session.commit()
    return user, slack_user.slack_uid


def _practice(
    db_session,
    *,
    hour=18,
    channel="C-REACTION-TEST",
    message_ts="1710000000.000100",
    session_emoji=None,
    status=PracticeStatus.SCHEDULED.value,
    plan_reactions=None,
):
    practice = Practice(
        date=datetime(2026, 7, 14, hour, 15),
        day_of_week="Tuesday",
        status=status,
        slack_channel_id=channel,
        slack_message_ts=message_ts,
        slack_session_emoji=session_emoji,
        plan_reactions=plan_reactions or [],
        airtable_id=f"{TEST_PREFIX}{uuid4().hex}",
    )
    db.session.add(practice)
    db.session.commit()
    return practice


def _react(practice, slack_user_id, reaction, *, removed=False):
    return handle_attendance_reaction(
        channel=practice.slack_channel_id,
        message_ts=practice.slack_message_ts,
        reaction=reaction,
        slack_user_id=slack_user_id,
        removed=removed,
    )


def _rsvps_for(practice, user=None):
    query = PracticeRSVP.query.filter_by(practice_id=practice.id)
    if user is not None:
        query = query.filter_by(user_id=user.id)
    return query


def test_standalone_checkmark_creates_going_rsvp(db_session, linked_user):
    user, slack_user_id = linked_user
    practice = _practice(db_session)

    result = _react(practice, slack_user_id, "white_check_mark")

    assert result == {
        "success": True,
        "action": "upserted",
        "practice_id": practice.id,
    }
    rsvp = _rsvps_for(practice, user).one()
    assert (rsvp.practice_id, rsvp.user_id, rsvp.status) == (
        practice.id,
        user.id,
        RSVPStatus.GOING.value,
    )
    assert rsvp.slack_user_id == slack_user_id


def test_standalone_checkmark_upserts_existing_rsvp_to_going(
    db_session, linked_user
):
    user, slack_user_id = linked_user
    practice = _practice(db_session)
    rsvp = PracticeRSVP(
        practice_id=practice.id,
        user_id=user.id,
        status=RSVPStatus.MAYBE.value,
    )
    db.session.add(rsvp)
    db.session.commit()

    result = _react(practice, slack_user_id, "white_check_mark")

    assert result["action"] == "upserted"
    assert _rsvps_for(practice, user).one().status == RSVPStatus.GOING.value


def test_removing_checkmark_deletes_only_matching_going_rsvp(
    db_session, linked_user
):
    user, slack_user_id = linked_user
    practice = _practice(db_session)
    db.session.add(
        PracticeRSVP(
            practice_id=practice.id,
            user_id=user.id,
            status=RSVPStatus.GOING.value,
            slack_user_id=slack_user_id,
        )
    )
    db.session.commit()

    result = _react(
        practice, slack_user_id, "white_check_mark", removed=True
    )

    assert result == {
        "success": True,
        "action": "removed",
        "practice_id": practice.id,
    }
    assert _rsvps_for(practice, user).count() == 0


def test_removing_checkmark_leaves_non_going_rsvp_untouched(
    db_session, linked_user
):
    user, slack_user_id = linked_user
    practice = _practice(db_session)
    rsvp = PracticeRSVP(
        practice_id=practice.id,
        user_id=user.id,
        status=RSVPStatus.MAYBE.value,
        slack_user_id=slack_user_id,
    )
    db.session.add(rsvp)
    db.session.commit()

    result = _react(
        practice, slack_user_id, "white_check_mark", removed=True
    )

    assert result == {
        "success": True,
        "ignored": "no_matching_going_rsvp",
    }
    assert _rsvps_for(practice, user).one().status == RSVPStatus.MAYBE.value


@pytest.mark.parametrize(
    "reaction",
    ["evergreen_tree", "athletic_shoe", "question", "thumbsup", "x"],
)
def test_non_attendance_reactions_are_ignored(
    db_session, linked_user, reaction
):
    _user, slack_user_id = linked_user
    practice = _practice(
        db_session,
        plan_reactions=[
            {"emoji": "evergreen_tree", "label": "Endurance"},
            {"emoji": "athletic_shoe", "label": "Running shoes"},
        ],
    )

    result = _react(practice, slack_user_id, reaction)

    assert result == {"success": True, "ignored": "not_attendance"}
    assert _rsvps_for(practice).count() == 0


def test_persisted_combined_emoji_routes_only_to_exact_sibling(
    db_session, linked_user
):
    user, slack_user_id = linked_user
    six = _practice(db_session, hour=18, session_emoji="six")
    seven = _practice(db_session, hour=19, session_emoji="seven")

    result = _react(six, slack_user_id, "six")

    assert result["practice_id"] == six.id
    assert PracticeRSVP.query.filter_by(
        practice_id=six.id, user_id=user.id, status=RSVPStatus.GOING.value
    ).count() == 1
    assert PracticeRSVP.query.filter_by(practice_id=seven.id).count() == 0


@pytest.mark.parametrize("reaction", ["evergreen_tree", "athletic_shoe"])
def test_plan_reactions_do_not_route_combined_practices(
    db_session, linked_user, reaction
):
    _user, slack_user_id = linked_user
    six = _practice(
        db_session,
        hour=18,
        session_emoji="six",
        plan_reactions=[{"emoji": reaction, "label": "Plan choice"}],
    )
    seven = _practice(
        db_session,
        hour=19,
        session_emoji="seven",
        plan_reactions=[{"emoji": reaction, "label": "Plan choice"}],
    )

    result = _react(six, slack_user_id, reaction)

    assert result == {"success": True, "ignored": "not_attendance"}
    assert _rsvps_for(six).count() == 0
    assert _rsvps_for(seven).count() == 0


def test_blank_multi_sibling_legacy_root_persists_session_emoji_once(
    db_session, linked_user
):
    _user, slack_user_id = linked_user
    six = _practice(db_session, hour=18)
    seven = _practice(db_session, hour=19)

    result = _react(six, slack_user_id, "seven")

    assert result["practice_id"] == seven.id
    assert _rsvps_for(seven).one().practice_id == seven.id
    assert (six.slack_session_emoji, seven.slack_session_emoji) == (
        "six",
        "seven",
    )


def test_partial_legacy_mapping_preserves_saved_and_assigns_only_blank(
    db_session, linked_user
):
    user, slack_user_id = linked_user
    six = _practice(db_session, hour=18, session_emoji="six")
    seven = _practice(db_session, hour=19)

    result = _react(six, slack_user_id, "seven")

    assert result["practice_id"] == seven.id
    assert six.slack_session_emoji == "six"
    assert seven.slack_session_emoji == "seven"
    assert _rsvps_for(seven, user).one().status == RSVPStatus.GOING.value


def test_cancelled_practice_is_ignored(db_session, linked_user):
    _user, slack_user_id = linked_user
    practice = _practice(
        db_session, status=PracticeStatus.CANCELLED.value
    )

    result = _react(practice, slack_user_id, "white_check_mark")

    assert result == {"success": True, "ignored": "cancelled"}
    assert _rsvps_for(practice).count() == 0


def test_same_timestamp_in_another_channel_is_not_linked(
    db_session, linked_user
):
    _user, slack_user_id = linked_user
    other_channel_practice = _practice(db_session, channel="C-OTHER")

    result = handle_attendance_reaction(
        channel="C-NOT-LINKED",
        message_ts=other_channel_practice.slack_message_ts,
        reaction="white_check_mark",
        slack_user_id=slack_user_id,
    )

    assert result == {"success": True, "ignored": "message_not_linked"}
    assert _rsvps_for(other_channel_practice).count() == 0


def test_unlinked_slack_user_is_ignored(db_session):
    practice = _practice(db_session)

    result = _react(
        practice, f"{TEST_PREFIX}unlinked", "white_check_mark"
    )

    assert result == {"success": True, "ignored": "unlinked_user"}
    assert _rsvps_for(practice).count() == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("channel", None),
        ("message_ts", None),
        ("reaction", None),
        ("slack_user_id", None),
    ],
)
def test_invalid_reaction_event_is_ignored(
    db_session, linked_user, field, value
):
    _user, slack_user_id = linked_user
    practice = _practice(db_session)
    event = {
        "channel": practice.slack_channel_id,
        "message_ts": practice.slack_message_ts,
        "reaction": "white_check_mark",
        "slack_user_id": slack_user_id,
    }
    event[field] = value

    result = handle_attendance_reaction(**event)

    assert result == {"success": True, "ignored": "invalid_event"}
    assert _rsvps_for(practice).count() == 0


def test_bolt_reaction_removed_delegates_with_removed_true(monkeypatch):
    calls = []
    event = {
        "item": {"type": "message", "channel": "C-ROOT", "ts": "root.1"},
        "reaction": "white_check_mark",
        "user": "U-MEMBER",
    }
    monkeypatch.setattr(
        bolt_module,
        "_delegate_reaction_event",
        lambda delegated, *, removed: calls.append((delegated, removed)),
    )

    bolt_module._handle_reaction_removed(event)

    assert calls == [(event, True)]
