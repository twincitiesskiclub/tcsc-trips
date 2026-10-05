"""A bot-created practice becomes member-visible on its own once it has a
location and a type. There is no publish button.

Read tests/practices/conftest.py before adding to this file: this runs
against the real local dev database.
"""

from datetime import datetime

import pytest

from app.models import db
from app.practices.interfaces import PracticeStatus
from app.practices.models import Practice, PracticeLocation, PracticeType
from app.practices.publishing import (
    announcement_run_time,
    publish_blockers,
    publish_if_ready,
)
from app.practices.service import published_practices

_PREFIX = "TEST publishing"


@pytest.fixture()
def location(db_session):
    db.session.rollback()
    row = PracticeLocation(name=f"{_PREFIX} Location")
    db.session.add(row)
    db.session.commit()
    row_id = row.id
    yield row
    db.session.rollback()
    stale = db.session.get(PracticeLocation, row_id)
    if stale is not None:
        db.session.delete(stale)
    db.session.commit()


@pytest.fixture()
def practice_type(db_session):
    db.session.rollback()
    row = PracticeType.query.filter_by(name=f"{_PREFIX} Type").first()
    if row is None:
        row = PracticeType(name=f"{_PREFIX} Type")
        db.session.add(row)
        db.session.commit()
    row_id = row.id
    yield row
    db.session.rollback()
    stale = db.session.get(PracticeType, row_id)
    if stale is not None:
        db.session.delete(stale)
    db.session.commit()


def _make_hidden(location=None, practice_type=None, *, when=None):
    when = when or datetime(2099, 3, 3, 18, 15)
    practice = Practice(
        date=when,
        day_of_week=when.strftime("%A"),
        is_draft=True,
        leads_needed=2,
        location_id=location.id if location else None,
        logistics_notes=f"{_PREFIX} row",
    )
    if practice_type is not None:
        practice.practice_types = [practice_type]
    db.session.add(practice)
    db.session.commit()
    return practice


def _delete_practice(practice_id):
    db.session.rollback()
    practice = db.session.get(Practice, practice_id)
    if practice is not None:
        db.session.delete(practice)
    db.session.commit()


@pytest.fixture(autouse=True)
def announce_calls(monkeypatch):
    """Never post from these tests; record late-announcement requests."""
    calls = []

    def fake_job(app, channel_override=None, now_override=None):
        calls.append(now_override)

    monkeypatch.setattr("app.scheduler.run_practice_announcements_job", fake_job)
    return calls


def test_a_complete_hidden_practice_becomes_member_visible(db_session, location, practice_type):
    practice = _make_hidden(location, practice_type)
    practice_id = practice.id
    try:
        assert published_practices().filter(Practice.id == practice_id).first() is None
        assert publish_if_ready(practice) is True
        assert published_practices().filter(Practice.id == practice_id).first() is not None
    finally:
        _delete_practice(practice_id)


def test_missing_location_stays_hidden(db_session, practice_type):
    practice = _make_hidden(None, practice_type)
    practice_id = practice.id
    try:
        assert publish_if_ready(practice) is False
        assert db.session.get(Practice, practice_id).is_draft is True
    finally:
        _delete_practice(practice_id)


def test_missing_type_stays_hidden(db_session, location):
    practice = _make_hidden(location, None)
    practice_id = practice.id
    try:
        assert publish_if_ready(practice) is False
        assert publish_blockers(practice) == ["type"]
    finally:
        _delete_practice(practice_id)


def test_cancelled_stays_hidden(db_session, location, practice_type):
    practice = _make_hidden(location, practice_type)
    practice_id = practice.id
    try:
        practice.status = PracticeStatus.CANCELLED.value
        db.session.commit()
        assert publish_if_ready(practice) is False
        assert db.session.get(Practice, practice_id).is_draft is True
    finally:
        _delete_practice(practice_id)


def test_visibility_is_one_way(db_session, location, practice_type):
    practice = _make_hidden(location, practice_type)
    practice_id = practice.id
    try:
        publish_if_ready(practice)
        practice.location_id = None
        db.session.commit()
        assert publish_if_ready(practice) is False
        assert db.session.get(Practice, practice_id).is_draft is False
    finally:
        _delete_practice(practice_id)


def test_already_visible_is_a_no_op(db_session, location, practice_type):
    practice = _make_hidden(location, practice_type)
    practice_id = practice.id
    try:
        practice.is_draft = False
        db.session.commit()
        assert publish_if_ready(practice) is False
    finally:
        _delete_practice(practice_id)


def test_announcement_run_time_evening_and_morning():
    assert announcement_run_time(datetime(2099, 3, 3, 18, 15)) == datetime(2099, 3, 3, 8, 0)
    assert announcement_run_time(datetime(2099, 3, 3, 12, 0)) == datetime(2099, 3, 3, 8, 0)
    assert announcement_run_time(datetime(2099, 3, 3, 9, 0)) == datetime(2099, 3, 2, 20, 0)


def test_filled_on_its_own_day_is_announced_now(db_session, location, practice_type, announce_calls):
    practice = _make_hidden(location, practice_type, when=datetime(2099, 3, 3, 18, 15))
    practice_id = practice.id
    try:
        publish_if_ready(practice, now=datetime(2099, 3, 3, 10, 0))
        assert announce_calls == [datetime(2099, 3, 3, 8, 0)]
    finally:
        _delete_practice(practice_id)


def test_filled_before_its_run_is_left_to_the_job(db_session, location, practice_type, announce_calls):
    practice = _make_hidden(location, practice_type, when=datetime(2099, 3, 3, 18, 15))
    practice_id = practice.id
    try:
        publish_if_ready(practice, now=datetime(2099, 3, 3, 7, 59))
        assert announce_calls == []
    finally:
        _delete_practice(practice_id)


def test_morning_practice_filled_after_the_evening_run_is_announced(db_session, location, practice_type, announce_calls):
    practice = _make_hidden(location, practice_type, when=datetime(2099, 3, 3, 9, 0))
    practice_id = practice.id
    try:
        publish_if_ready(practice, now=datetime(2099, 3, 2, 21, 0))
        assert announce_calls == [datetime(2099, 3, 2, 20, 0)]
    finally:
        _delete_practice(practice_id)


def test_a_past_practice_is_never_announced(db_session, location, practice_type, announce_calls):
    practice = _make_hidden(location, practice_type, when=datetime(2099, 3, 3, 18, 15))
    practice_id = practice.id
    try:
        publish_if_ready(practice, now=datetime(2099, 3, 3, 20, 0))
        assert announce_calls == []
    finally:
        _delete_practice(practice_id)
