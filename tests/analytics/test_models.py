from datetime import date, datetime

import pytest
from sqlalchemy import inspect, UniqueConstraint
from sqlalchemy.exc import IntegrityError

from app import analytics
from app.analytics.models import AnalyticsCorrection, PracticeAttendance, PracticeSession, SlackArchiveMessage
from app.models import db, User
from app.practices.models import Practice, PracticeLocation


def test_analytics_tables_exist_with_key_columns(db_session):
    insp = inspect(db.engine)
    tables = set(insp.get_table_names())
    assert {"slack_archive_messages", "slack_reaction_events", "practice_sessions",
            "practice_attendance", "weather_hours", "analytics_corrections"} <= tables
    cols = {c["name"] for c in insp.get_columns("practice_sessions")}
    assert {"session_key", "format", "slot", "rsvp_count", "temp_f",
            "minutes_after_sunset", "flags", "needs_review"} <= cols
    att = {c["name"] for c in insp.get_columns("practice_attendance")}
    assert {"slack_uid", "role", "emoji", "slot", "source"} <= att


def test_attendance_rows_cascade_with_session(db_session):
    s = PracticeSession(session_key="test:cascade", era="template", date=date(2099, 1, 1),
                        day_of_week="Thursday", season_label="2098 Fall/Winter",
                        group_key="test:cascade")
    db_session.add(s)
    db_session.flush()
    db_session.add(PracticeAttendance(session_id=s.id, slack_uid="UFAKE0001",
                                      person_key="slack:UFAKE0001", role="rsvp", emoji="six", source="reaction"))
    db_session.flush()
    db_session.delete(s)
    db_session.flush()
    assert PracticeAttendance.query.filter_by(slack_uid="UFAKE0001").count() == 0


@pytest.mark.parametrize("field,parent", [
    ("practice_id", lambda: Practice(date=datetime(2099, 1, 1, 18), day_of_week="Thursday")),
    ("location_id", lambda: PracticeLocation(name="Invented deletion test venue")),
    ("source_message_id", lambda: SlackArchiveMessage(channel_id="CFAKEDELETE", ts="4070959200.000001",
        text="Invented archive row", posted_at=datetime(2099, 1, 1), raw={})),
    ("user_id", lambda: User(first_name="Invented", last_name="Member", email="analytics-delete@example.invalid")),
])
def test_deleting_source_preserves_analytics_with_null_fk(db_session, field, parent):
    source = parent()
    db_session.add(source)
    db_session.flush()
    session = PracticeSession(session_key="test:delete", group_key="test:delete", era="template",
                              date=date(2099, 1, 1), day_of_week="Thursday", season_label="2099")
    db_session.add(session)
    db_session.flush()
    dependent = (PracticeAttendance(session_id=session.id, slack_uid="UFAKE0001",
                                   person_key="slack:UFAKE0001", role="rsvp",
                                   source="reaction") if field == "user_id" else session)
    setattr(dependent, field, source.id)
    db_session.add(dependent)
    db_session.flush()
    db_session.delete(source)
    db_session.flush()
    db_session.refresh(dependent)
    assert getattr(dependent, field) is None
    fk = next(iter(dependent.__table__.c[field].foreign_keys))
    assert fk.ondelete == "SET NULL"


@pytest.mark.parametrize("model,column,name", [
    (PracticeSession, "session_key", "uq_practice_sessions_session_key"),
    (AnalyticsCorrection, "key", "uq_analytics_corrections_key"),
])
def test_unique_constraints_have_stable_names(db_session, model, column, name):
    assert any(c.name == name and list(c.columns.keys()) == [column]
               for c in model.__table__.constraints if isinstance(c, UniqueConstraint))
    assert any(c["name"] == name and c["column_names"] == [column]
               for c in inspect(db.engine).get_unique_constraints(model.__tablename__))


def test_channel_tuples():
    assert analytics.TRIP_CHANNEL == "C068ECRE0PQ"
    assert set(analytics.EVENT_CHANNELS) == {"C0B2VN1LU11", "C02HXN45214", "C02J1FDSBHT", "C046XRWC4NR"}
    assert analytics.CANDIDATE_CHANNELS == analytics.SESSION_CHANNELS + analytics.EVENT_CHANNELS
    assert set(analytics.REACTION_CANDIDATE_CHANNELS) == {"C042G463AQ1", "C03FKTTHNHW", "C0B2VN1LU11", "C02HXN45214"}
    assert set(analytics.REACTION_CANDIDATE_CHANNELS) <= set(analytics.CANDIDATE_CHANNELS)
    assert analytics.LINEAGE_CHANNELS == analytics.CANDIDATE_CHANNELS + (analytics.TRIP_CHANNEL,)
    assert "C02HXN45214" not in analytics.SYNC_CHANNELS          # archived, imported once
    assert "C03FKTTHNHW" not in analytics.SYNC_CHANNELS
    assert set(analytics.LINEAGE_CHANNELS) <= set(analytics.CHANNELS)
    assert "trip" in analytics.CATEGORIES and "practice" in analytics.CATEGORIES


def _session(**overrides):
    values = dict(session_key="trip:cuyuna:2099", era="trip", kind="trip", category="trip",
                  date=date(2099, 9, 1), day_of_week="Tuesday", season_label="2099 Fall/Winter",
                  group_key="trip:cuyuna:2099")
    values.update(overrides)
    return PracticeSession(**values)


def test_trip_session_with_name_only_signup(db_session):
    session = _session()
    db_session.add(session)
    db_session.flush()
    db_session.add(PracticeAttendance(session_id=session.id, slack_uid=None,
                                      person_key="name:pat example", role="signup", source="reaction"))
    db_session.flush()
    assert session.reported_count is None


def test_person_key_is_the_uniqueness_key(db_session):
    session = _session()
    db_session.add(session)
    db_session.flush()
    for _ in range(2):
        db_session.add(PracticeAttendance(session_id=session.id, slack_uid="UFAKE0001",
                                          person_key="slack:UFAKE0001", role="decline",
                                          emoji="x", source="reaction"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_bad_category_rejected(db_session):
    db_session.add(_session(category="picnic"))
    with pytest.raises(IntegrityError):
        db_session.flush()
