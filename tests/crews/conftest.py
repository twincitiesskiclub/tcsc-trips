"""Fixtures for tests/crews.

Run against a scratch DB, never the shared dev DB:
    DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test pytest tests/crews
Routes commit, so ``world`` commits its rows and deletes everything it made
afterwards (crew rows go with the season through ON DELETE CASCADE). All
names and emails are made up.
"""
import os
import uuid
from datetime import date

import pytest

from app import create_app
from app.analytics.models import PracticeAttendance, PracticeSession
from app.models import SlackUser, Season, Tag, User, UserSeason, UserTag, db
from tests._db_guard import LOCAL_TEST_DB


@pytest.fixture
def app():
    os.environ.setdefault("TCSC_MIGRATION_ONLY", "1")  # no scheduler in tests
    application = create_app()
    application.config.update(
        TESTING=True,
        SECRET_KEY="test-secret-key",
        SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", LOCAL_TEST_DB),
    )
    return application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_client(client):
    with client.session_transaction() as sess:
        sess["user"] = {"email": "tester@twincitiesskiclub.org", "name": "Tester"}
    return client


class World:
    """A season with members, a board tag, a Slack user and practice history."""

    def __init__(self):
        tag = uuid.uuid4().hex[:8]
        self.tag = tag
        self.seasons, self.users, self.sessions, self.slack_users = [], [], [], []
        self.board_tag = Tag.query.filter_by(name="BOARD_MEMBER").one_or_none()
        self.made_tag = self.board_tag is None
        if self.made_tag:
            self.board_tag = Tag(name="BOARD_MEMBER", display_name="Board Member")
            db.session.add(self.board_tag)
        self.legacy = self.season(f"Legacy {tag}", "legacy", date(2020, 1, 1))
        self.spring = self.season(f"2099 Spring/Summer {tag}", "spring", date(2099, 4, 1))
        self.fall = self.season(f"2099 Fall/Winter {tag}", "fall", date(2099, 9, 1))
        db.session.flush()

    def season(self, name, kind, start):
        s = Season(name=name, season_type=kind, year=start.year, start_date=start,
                   end_date=date(start.year, 12, 31))
        db.session.add(s)
        self.seasons.append(s)
        return s

    def member(self, first, last, *, pronouns=None, dob=None, ski="7+", board=False,
               seasons=(), slack_uid=None):
        u = User(first_name=first, last_name=last, email=f"{first.lower()}.{self.tag}@example.com",
                 pronouns=pronouns, date_of_birth=dob, ski_experience=ski, status="ACTIVE")
        if slack_uid:
            su = SlackUser(slack_uid=slack_uid, full_name=f"{first} {last}")
            db.session.add(su)
            db.session.flush()
            self.slack_users.append(su)
            u.slack_user_id = su.id
        db.session.add(u)
        db.session.flush()
        self.users.append(u)
        for s in (self.fall, *seasons):
            db.session.add(UserSeason(user_id=u.id, season_id=s.id, registration_type="returning",
                                      registration_date=s.start_date, status="ACTIVE"))
        if board:
            db.session.add(UserTag(user_id=u.id, tag_id=self.board_tag.id))
        db.session.flush()
        return u

    def attended(self, user, label, when):
        ps = PracticeSession(session_key=f"crews-{self.tag}-{len(self.sessions)}", era="template",
                             date=when, day_of_week="Tuesday", season_label=label,
                             group_key=f"crews-{self.tag}")
        db.session.add(ps)
        db.session.flush()
        self.sessions.append(ps)
        db.session.add(PracticeAttendance(session_id=ps.id, person_key=f"user:{user.id}",
                                          user_id=user.id, role="rsvp", source="reaction"))
        db.session.flush()

    def cleanup(self):
        db.session.rollback()
        ids = [u.id for u in self.users]
        PracticeAttendance.query.filter(PracticeAttendance.user_id.in_(ids)).delete(synchronize_session=False)
        PracticeSession.query.filter(PracticeSession.id.in_([s.id for s in self.sessions])).delete(
            synchronize_session=False)
        UserTag.query.filter(UserTag.user_id.in_(ids)).delete(synchronize_session=False)
        UserSeason.query.filter(UserSeason.user_id.in_(ids)).delete(synchronize_session=False)
        User.query.filter(User.id.in_(ids)).delete(synchronize_session=False)
        SlackUser.query.filter(SlackUser.id.in_([s.id for s in self.slack_users])).delete(
            synchronize_session=False)
        Season.query.filter(Season.id.in_([s.id for s in self.seasons])).delete(synchronize_session=False)
        if self.made_tag:
            Tag.query.filter_by(id=self.board_tag.id).delete()
        db.session.commit()


@pytest.fixture
def world(app):
    with app.app_context():
        w = World()
        db.session.commit()
        try:
            yield w
        finally:
            w.cleanup()
