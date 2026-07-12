from contextlib import contextmanager
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from zoneinfo import ZoneInfo

from app.scheduler import run_practice_announcements_job


class _Column:
    def __ge__(self, _other):
        return object()

    def __le__(self, _other):
        return object()

    def __lt__(self, _other):
        return object()

    def in_(self, _values):
        return object()

    def is_(self, _value):
        return object()


class _Query:
    def __init__(self, practices):
        self.practices = practices

    def filter(self, *_criteria):
        return self

    def order_by(self, *_columns):
        return self

    def all(self):
        return self.practices


class _FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 7, 14, 8, 0, tzinfo=tz or ZoneInfo("UTC"))


def test_scheduler_delegates_conditions_lookup_to_announcement_layer():
    practice = SimpleNamespace(
        id=42,
        date=datetime(2026, 7, 14, 18, 15),
        location=SimpleNamespace(latitude=44.99, longitude=-93.32),
        practice_types=[],
        activities=[],
    )
    fake_practice_model = SimpleNamespace(
        date=_Column(),
        status=_Column(),
        slack_message_ts=_Column(),
        query=_Query([practice]),
    )

    @contextmanager
    def app_context():
        yield

    app = SimpleNamespace(app_context=app_context, logger=MagicMock())

    with patch("app.scheduler.datetime", _FixedDateTime), patch(
        "app.practices.models.Practice", fake_practice_model
    ), patch(
        "app.slack.practices.post_practice_announcement",
        return_value={"success": True},
    ) as mock_post, patch(
        "app.slack.practices.post_combined_lift_announcement"
    ), patch(
        "app.integrations.weather.get_weather_for_location"
    ) as mock_weather:
        run_practice_announcements_job(app, channel_override="practice-test")

    mock_weather.assert_not_called()
    mock_post.assert_called_once_with(
        practice, channel_override="practice-test"
    )
