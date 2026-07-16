"""Adapter coverage for the legacy Slack Quick Edit modal."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app import create_app
from app.models import db
from app.practices.models import Practice
import app.slack.bolt_app as bolt_module


QUICK_EDIT_SOURCE_DATE = datetime(2126, 9, 3, 18, 15)
QUICK_EDIT_DESTINATION_DATE = QUICK_EDIT_SOURCE_DATE + timedelta(days=7)
QUICK_EDIT_AIRTABLE_ID = "Slack Quick Edit Refresh Test Practice"


@pytest.fixture
def app():
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret-key"
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = (
        "postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"
    )
    return flask_app


@pytest.fixture
def db_session(app):
    with app.app_context():
        db.create_all()
        yield db
        db.session.rollback()


@pytest.fixture
def quick_edit_practice(db_session):
    """Own two reserved weeks and delete only the row created here."""
    source_week = (
        QUICK_EDIT_SOURCE_DATE
        - timedelta(days=QUICK_EDIT_SOURCE_DATE.weekday())
    ).replace(hour=0, minute=0, second=0, microsecond=0)
    destination_week = (
        QUICK_EDIT_DESTINATION_DATE
        - timedelta(days=QUICK_EDIT_DESTINATION_DATE.weekday())
    ).replace(hour=0, minute=0, second=0, microsecond=0)
    reserved_end = destination_week + timedelta(days=7)
    collisions = Practice.query.filter(
        Practice.date >= source_week,
        Practice.date < reserved_end,
    ).count()
    assert collisions == 0, (
        "Reserved Slack Quick Edit test weeks contain existing rows; "
        "refusing to mutate persistent data"
    )

    practice = Practice(
        date=QUICK_EDIT_SOURCE_DATE,
        day_of_week=QUICK_EDIT_SOURCE_DATE.strftime("%A"),
        status="scheduled",
        workout_description="Original quick workout",
        airtable_id=QUICK_EDIT_AIRTABLE_ID,
    )
    db.session.add(practice)
    db.session.commit()
    owned = SimpleNamespace(
        practice_id=practice.id,
        previous_date=practice.date,
    )

    yield owned

    db.session.rollback()
    practice = db.session.get(Practice, owned.practice_id)
    if practice is not None:
        db.session.delete(practice)
        db.session.commit()


def test_quick_edit_forwards_previous_date_to_shared_refresh(
    db_session,
    quick_edit_practice,
    monkeypatch,
):
    refresh_calls = []

    def record_refresh(practice, **kwargs):
        refresh_calls.append((practice.id, practice.date, kwargs))

    monkeypatch.setattr(
        "app.slack.practices.refresh_practice_posts",
        record_refresh,
    )
    ack = MagicMock()

    bolt_module._handle_practice_quick_edit_submission(
        ack=ack,
        body={"user": {"id": "U-QUICK-EDIT-TEST"}},
        view={
            "private_metadata": str(quick_edit_practice.practice_id),
            "state": {
                "values": {
                    "date_block": {
                        "practice_date": {
                            "selected_date_time": int(
                                QUICK_EDIT_DESTINATION_DATE.timestamp()
                            ),
                        },
                    },
                    "workout_block": {
                        "workout_description": {
                            "value": "Moved quick workout",
                        },
                    },
                },
            },
        },
        logger=MagicMock(),
    )

    ack.assert_called_once_with()
    assert len(refresh_calls) == 1
    practice_id, refreshed_date, kwargs = refresh_calls[0]
    assert practice_id == quick_edit_practice.practice_id
    assert refreshed_date == QUICK_EDIT_DESTINATION_DATE
    assert kwargs == {
        "change_type": "edit",
        "actor_slack_id": "U-QUICK-EDIT-TEST",
        "previous_date": quick_edit_practice.previous_date,
    }
    db.session.expire_all()
    saved = db.session.get(Practice, quick_edit_practice.practice_id)
    assert saved.date == QUICK_EDIT_DESTINATION_DATE
    assert saved.workout_description == "Moved quick workout"
