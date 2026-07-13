"""Scheduled weekly-summary orchestration contracts."""

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest
from sqlalchemy.sql import operators

from app.agent.routines import weekly_summary as routine
from app.practices.interfaces import PracticeStatus
from app.practices.models import Practice


class FakeQuery:
    def __init__(self, practices):
        self.practices = practices
        self.filters = ()
        self.order_columns = ()

    def filter(self, *criteria):
        self.filters = criteria
        return self

    def order_by(self, *columns):
        self.order_columns = columns
        return self

    def all(self):
        return self.practices


def model_for(query):
    return SimpleNamespace(
        query=query,
        date=Practice.date,
        status=Practice.status,
        id=Practice.id,
    )


def practice(
    practice_id,
    when,
    *,
    status=PracticeStatus.SCHEDULED.value,
    latitude=None,
    longitude=None,
):
    return SimpleNamespace(
        id=practice_id,
        date=when,
        status=status,
        location=SimpleNamespace(latitude=latitude, longitude=longitude),
        slack_weekly_summary_ts=None,
    )


def criterion_value(criteria, operator):
    matches = [item for item in criteria if item.operator is operator]
    assert len(matches) == 1
    return matches[0].right.value


def run_with_query(query, *, now=None, week_start=None, dry_run=True):
    now = now or datetime(2026, 7, 12, 20, 0)
    client = MagicMock()
    client.chat_postMessage.return_value = {"ts": "1783980000.000100"}
    fake_db = SimpleNamespace(session=MagicMock())
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "week"}}]
    fallback = "Complete calendar-week fallback"

    with patch.object(routine, "Practice", model_for(query)), patch.object(
        routine, "load_skipper_config", return_value={"agent": {"dry_run": dry_run}}
    ), patch.object(routine, "now_central_naive", return_value=now, create=True), patch.object(
        routine, "convert_practice_to_info", side_effect=lambda item: item
    ), patch.object(
        routine, "build_weekly_summary_blocks", return_value=blocks
    ) as build_blocks, patch.object(
        routine,
        "build_weekly_summary_fallback_text",
        return_value=fallback,
        create=True,
    ) as build_fallback, patch.object(
        routine, "get_slack_client", return_value=client
    ), patch.object(
        routine, "_get_announcement_channel", return_value="C-WEEK", create=True
    ), patch.object(
        routine, "db", fake_db, create=True
    ):
        result = routine.run_weekly_summary(week_start=week_start)

    return SimpleNamespace(
        result=result,
        client=client,
        db=fake_db,
        build_blocks=build_blocks,
        build_fallback=build_fallback,
        blocks=blocks,
        fallback=fallback,
    )


def test_sunday_targets_the_coming_monday_through_sunday():
    query = FakeQuery([])

    run_with_query(query, now=datetime(2026, 7, 12, 20, 0))

    assert criterion_value(query.filters, operators.ge) == datetime(2026, 7, 13)
    assert criterion_value(query.filters, operators.lt) == datetime(2026, 7, 20)


def test_explicit_week_start_is_deterministic_and_must_be_monday():
    query = FakeQuery([])

    outcome = run_with_query(
        query,
        now=datetime(2035, 1, 1, 12, 0),
        week_start=date(2026, 7, 13),
    )

    assert outcome.result["week_start"] == "2026-07-13T00:00:00"
    assert outcome.result["week_end"] == "2026-07-20T00:00:00"
    outcome.build_blocks.assert_called_once_with(
        [], week_start=date(2026, 7, 13), weather_data={}
    )
    outcome.build_fallback.assert_called_once_with(
        [], week_start=date(2026, 7, 13), weather_data={}
    )
    with pytest.raises(ValueError, match="week_start must be a Monday"):
        run_with_query(FakeQuery([]), week_start=date(2026, 7, 14))


def test_query_includes_only_weekly_surface_statuses():
    query = FakeQuery([])

    run_with_query(query, week_start=date(2026, 7, 13))

    status_criteria = [item for item in query.filters if item.operator is operators.in_op]
    assert len(status_criteria) == 1
    assert set(status_criteria[0].right.value) == {
        PracticeStatus.SCHEDULED.value,
        PracticeStatus.CONFIRMED.value,
        PracticeStatus.CANCELLED.value,
    }
    assert PracticeStatus.COMPLETED.value not in status_criteria[0].right.value
    assert len(query.order_columns) == 2


def test_active_weather_uses_non_none_coordinates_and_cancelled_skips_weather():
    sessions = [
        practice(1, datetime(2026, 7, 14, 18, 15), latitude=0, longitude=0),
        practice(
            2,
            datetime(2026, 7, 16, 18, 5),
            status=PracticeStatus.CONFIRMED.value,
            latitude=45.0,
            longitude=-93.0,
        ),
        practice(3, datetime(2026, 7, 18, 9, 0), latitude=None, longitude=-93.0),
        practice(
            4,
            datetime(2026, 7, 18, 10, 30),
            status=PracticeStatus.CANCELLED.value,
            latitude=44.0,
            longitude=-92.0,
        ),
    ]
    query = FakeQuery(sessions)
    weather = SimpleNamespace(temperature_f=78.2, conditions_summary="Clear")

    with patch.object(
        routine, "get_weather_for_location", return_value=weather
    ) as get_weather:
        outcome = run_with_query(
            query, week_start=date(2026, 7, 13), dry_run=True
        )

    assert get_weather.call_args_list == [
        call(lat=0, lon=0, target_datetime=datetime(2026, 7, 14, 18, 15)),
        call(
            lat=45.0,
            lon=-93.0,
            target_datetime=datetime(2026, 7, 16, 18, 5),
        ),
    ]
    expected_weather = {
        1: {"temp_f": 78.2, "conditions": "Clear"},
        2: {"temp_f": 78.2, "conditions": "Clear"},
    }
    outcome.build_blocks.assert_called_once_with(
        sessions,
        week_start=date(2026, 7, 13),
        weather_data=expected_weather,
    )
    outcome.build_fallback.assert_called_once_with(
        sessions,
        week_start=date(2026, 7, 13),
        weather_data=expected_weather,
    )


def test_post_uses_complete_fallback_and_saves_timestamp_to_every_row():
    sessions = [
        practice(1, datetime(2026, 7, 14, 18, 15)),
        practice(
            2,
            datetime(2026, 7, 16, 18, 5),
            status=PracticeStatus.CANCELLED.value,
        ),
    ]

    outcome = run_with_query(
        FakeQuery(sessions), week_start=date(2026, 7, 13), dry_run=False
    )

    outcome.client.chat_postMessage.assert_called_once_with(
        channel="C-WEEK",
        blocks=outcome.blocks,
        text=outcome.fallback,
    )
    assert [item.slack_weekly_summary_ts for item in sessions] == [
        "1783980000.000100",
        "1783980000.000100",
    ]
    outcome.db.session.commit.assert_called_once_with()
    assert outcome.result["fallback"] == outcome.fallback
    assert outcome.result["slack_posted"] is True


def test_dry_run_builds_full_preview_but_writes_nothing():
    session = practice(1, datetime(2026, 7, 14, 18, 15))

    outcome = run_with_query(
        FakeQuery([session]), week_start=date(2026, 7, 13), dry_run=True
    )

    assert outcome.result["fallback"] == outcome.fallback
    outcome.client.chat_postMessage.assert_not_called()
    outcome.db.session.commit.assert_not_called()
    assert session.slack_weekly_summary_ts is None
