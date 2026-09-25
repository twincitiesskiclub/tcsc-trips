from datetime import date, datetime

import pytest
from sqlalchemy import inspect, UniqueConstraint

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
                                      role="rsvp", emoji="six", source="reaction"))
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
                                   role="rsvp", source="reaction") if field == "user_id" else session)
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
