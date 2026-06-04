"""Tests for the threaded 'Practice Details' reply wiring.

Verifies that _upsert_details_reply (and the three functions that call it)
correctly post a new threaded reply when slack_details_ts is absent, and
update an existing one when it is present.

Uses unittest.mock throughout - no live Slack calls.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_practice(slack_message_ts="1234.5678", slack_channel_id="CTEST", slack_details_ts=None):
    """Return a minimal fake Practice model instance."""
    p = MagicMock()
    p.id = 42
    p.slack_message_ts = slack_message_ts
    p.slack_channel_id = slack_channel_id
    p.slack_details_ts = slack_details_ts
    # Location with coordinates so _gather_conditions can run (mocked out)
    loc = MagicMock()
    loc.latitude = 44.99
    loc.longitude = -93.32
    p.location = loc
    return p


def _make_practice_info():
    return SimpleNamespace(id=42)


# ---------------------------------------------------------------------------
# Direct tests of _upsert_details_reply
# ---------------------------------------------------------------------------

class TestGatherConditions:
    """Test _gather_conditions best-effort daylight + AQI fetch."""

    def _practice_with_coords(self, lat=44.99, lon=-93.32):
        from datetime import datetime
        p = MagicMock()
        p.id = 7
        p.date = datetime(2026, 12, 29, 12, 0)
        loc = MagicMock()
        loc.latitude = lat
        loc.longitude = lon
        p.location = loc
        return p

    def test_no_latlon_returns_none_none_none_without_calling_integrations(self, app_context):
        from app.slack.practices.announcements import _gather_conditions

        p = self._practice_with_coords(lat=None, lon=None)

        with patch("app.integrations.daylight.get_daylight_info") as mock_day, \
             patch("app.integrations.air_quality.get_air_quality") as mock_aqi, \
             patch("app.integrations.weather.get_weather_for_location") as mock_wx:
            weather, daylight, aqi = _gather_conditions(p)

        assert weather is None
        assert daylight is None
        assert aqi is None
        mock_wx.assert_not_called()
        mock_day.assert_not_called()
        mock_aqi.assert_not_called()

    def test_no_location_returns_none_none_none(self, app_context):
        from app.slack.practices.announcements import _gather_conditions

        p = MagicMock()
        p.id = 7
        p.location = None

        weather, daylight, aqi = _gather_conditions(p)
        assert weather is None
        assert daylight is None
        assert aqi is None

    def test_weather_fetch_fails_returns_none_weather(self, app_context):
        from app.slack.practices.announcements import _gather_conditions

        p = self._practice_with_coords()
        daylight_obj = SimpleNamespace(sunset="something")
        aqi_obj = SimpleNamespace(aqi=78)

        with patch("app.integrations.weather.get_weather_for_location", side_effect=Exception("nws boom")), \
             patch("app.integrations.daylight.get_daylight_info", return_value=daylight_obj), \
             patch("app.integrations.air_quality.get_air_quality", return_value=aqi_obj):
            weather, daylight, aqi = _gather_conditions(p)

        assert weather is None
        assert daylight is daylight_obj
        assert aqi == 78

    def test_daylight_raises_but_aqi_and_weather_succeed(self, app_context):
        from app.slack.practices.announcements import _gather_conditions

        p = self._practice_with_coords()
        aqi_obj = SimpleNamespace(aqi=78)
        weather_obj = SimpleNamespace(temperature_f=32.0)

        with patch("app.integrations.weather.get_weather_for_location", return_value=weather_obj), \
             patch("app.integrations.daylight.get_daylight_info", side_effect=Exception("astral boom")), \
             patch("app.integrations.air_quality.get_air_quality", return_value=aqi_obj):
            weather, daylight, aqi = _gather_conditions(p)

        assert weather is weather_obj
        assert daylight is None
        assert aqi == 78

    def test_aqi_none_yields_none_aqi(self, app_context):
        from app.slack.practices.announcements import _gather_conditions

        p = self._practice_with_coords()
        daylight_obj = SimpleNamespace(sunset="something")
        weather_obj = SimpleNamespace(temperature_f=28.0)

        with patch("app.integrations.weather.get_weather_for_location", return_value=weather_obj), \
             patch("app.integrations.daylight.get_daylight_info", return_value=daylight_obj), \
             patch("app.integrations.air_quality.get_air_quality", return_value=None):
            weather, daylight, aqi = _gather_conditions(p)

        assert weather is weather_obj
        assert daylight is daylight_obj
        assert aqi is None

    def test_all_succeed_returns_weather_daylight_aqi(self, app_context):
        from app.slack.practices.announcements import _gather_conditions

        p = self._practice_with_coords()
        daylight_obj = SimpleNamespace(sunset="something")
        aqi_obj = SimpleNamespace(aqi=42)
        weather_obj = SimpleNamespace(temperature_f=20.0)

        with patch("app.integrations.weather.get_weather_for_location", return_value=weather_obj), \
             patch("app.integrations.daylight.get_daylight_info", return_value=daylight_obj), \
             patch("app.integrations.air_quality.get_air_quality", return_value=aqi_obj):
            weather, daylight, aqi = _gather_conditions(p)

        assert weather is weather_obj
        assert daylight is daylight_obj
        assert aqi == 42


class TestUpsertDetailsReply:
    """Test _upsert_details_reply in isolation."""

    def _call(self, client, practice, practice_info=None, weather=None, trail_conditions=None,
              daylight=None, aqi=None, blocks=None):
        from app.slack.practices.announcements import _upsert_details_reply

        if practice_info is None:
            practice_info = _make_practice_info()

        # Patch _gather_conditions to return controlled values
        # Patch build_practice_details_blocks to return controlled blocks
        default_blocks = blocks if blocks is not None else [{"type": "section", "text": {"type": "mrkdwn", "text": "details"}}]

        with patch("app.slack.practices.announcements._gather_conditions", return_value=(None, daylight, aqi)), \
             patch("app.slack.practices.announcements.build_practice_details_blocks", return_value=default_blocks), \
             patch("app.slack.practices.announcements.db") as mock_db:
            _upsert_details_reply(client, practice, practice_info, weather=weather, trail_conditions=trail_conditions)
            return mock_db

    def test_new_post_calls_chat_postMessage_with_thread_ts(self):
        """When slack_details_ts is None a threaded reply is posted."""
        client = MagicMock()
        client.chat_postMessage.return_value = {"ts": "9999.0001"}
        practice = _make_practice(slack_details_ts=None)

        self._call(client, practice)

        client.chat_postMessage.assert_called_once()
        kwargs = client.chat_postMessage.call_args[1]
        assert kwargs["thread_ts"] == "1234.5678"
        assert kwargs["reply_broadcast"] is False
        assert kwargs["channel"] == "CTEST"

    def test_new_post_saves_slack_details_ts(self):
        """After a new thread reply, slack_details_ts is saved via db.session.commit."""
        client = MagicMock()
        client.chat_postMessage.return_value = {"ts": "9999.0001"}
        practice = _make_practice(slack_details_ts=None)

        mock_db = self._call(client, practice)

        assert practice.slack_details_ts == "9999.0001"
        mock_db.session.commit.assert_called_once()

    def test_existing_ts_calls_chat_update(self):
        """When slack_details_ts is already set, chat_update is used instead."""
        client = MagicMock()
        practice = _make_practice(slack_details_ts="8888.0001")

        self._call(client, practice)

        client.chat_update.assert_called_once()
        kwargs = client.chat_update.call_args[1]
        assert kwargs["ts"] == "8888.0001"
        assert kwargs["channel"] == "CTEST"
        # Must NOT post a new thread message
        client.chat_postMessage.assert_not_called()

    def test_existing_ts_no_db_commit(self):
        """Updating an existing reply must not trigger an extra db commit."""
        client = MagicMock()
        practice = _make_practice(slack_details_ts="8888.0001")

        mock_db = self._call(client, practice)

        mock_db.session.commit.assert_not_called()

    def test_empty_blocks_skips_slack_call(self):
        """When build_practice_details_blocks returns empty list, nothing is posted."""
        client = MagicMock()
        practice = _make_practice(slack_details_ts=None)

        self._call(client, practice, blocks=[])

        client.chat_postMessage.assert_not_called()
        client.chat_update.assert_not_called()

    def test_slack_exception_is_swallowed(self, app_context):
        """A Slack API error must not propagate - best-effort only."""
        client = MagicMock()
        client.chat_postMessage.side_effect = Exception("slack down")
        practice = _make_practice(slack_details_ts=None)

        # Should not raise
        from app.slack.practices.announcements import _upsert_details_reply
        with patch("app.slack.practices.announcements._gather_conditions", return_value=(None, None, None)), \
             patch("app.slack.practices.announcements.build_practice_details_blocks",
                   return_value=[{"type": "section"}]), \
             patch("app.slack.practices.announcements.db"):
            # Should complete without raising
            _upsert_details_reply(client, practice, _make_practice_info())


# ---------------------------------------------------------------------------
# Integration-style wiring tests
# ---------------------------------------------------------------------------

class TestPostPracticeAnnouncementWiring:
    """post_practice_announcement calls _upsert_details_reply after the hero commit."""

    def test_details_reply_posted_after_hero(self, app_context):
        """On initial post, _upsert_details_reply is called with weather+trail."""
        from app.slack.practices.announcements import post_practice_announcement

        practice = _make_practice(slack_message_ts=None, slack_details_ts=None)

        with patch("app.slack.practices.announcements.get_slack_client") as mock_get_client, \
             patch("app.slack.practices.announcements.get_channel_id_by_name", return_value="CTEST"), \
             patch("app.slack.practices.announcements._get_announcement_channel", return_value="CTEST"), \
             patch("app.practices.service.convert_practice_to_info", return_value=_make_practice_info()), \
             patch("app.slack.practices.announcements.build_practice_announcement_blocks", return_value=[]), \
             patch("app.slack.practices.announcements._upsert_details_reply") as mock_upsert, \
             patch("app.slack.practices.announcements.db"), \
             patch("app.slack.practices.coach_review.create_practice_log_thread", create=True):

            mock_client = MagicMock()
            mock_client.chat_postMessage.return_value = {"ts": "1111.0001"}
            mock_client.reactions_add = MagicMock()
            mock_get_client.return_value = mock_client

            result = post_practice_announcement(practice, weather="WEATHER", trail_conditions="TRAIL")

        assert result.get("success") is True
        mock_upsert.assert_called_once()
        assert mock_upsert.call_args[1].get("weather") == "WEATHER"
        assert mock_upsert.call_args[1].get("trail_conditions") == "TRAIL"


class TestUpdatePracticeAnnouncementWiring:
    """update_practice_announcement calls _upsert_details_reply with weather."""

    def test_details_upserted_with_weather(self, app_context):
        from app.slack.practices.announcements import update_practice_announcement

        practice = _make_practice(slack_message_ts="1234.5678", slack_details_ts=None)

        with patch("app.slack.practices.announcements.get_slack_client") as mock_get_client, \
             patch("app.practices.service.convert_practice_to_info", return_value=_make_practice_info()), \
             patch("app.slack.practices.announcements.build_practice_announcement_blocks", return_value=[]), \
             patch("app.slack.practices.announcements._upsert_details_reply") as mock_upsert, \
             patch("app.slack.practices.announcements.db"):

            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            result = update_practice_announcement(practice, weather="W2", trail_conditions="T2")

        assert result.get("success") is True
        mock_upsert.assert_called_once()
        assert mock_upsert.call_args[1].get("weather") == "W2"
        assert mock_upsert.call_args[1].get("trail_conditions") == "T2"

    def test_details_upserted_with_existing_ts(self, app_context):
        """With an existing slack_details_ts, the update path is exercised."""
        from app.slack.practices.announcements import update_practice_announcement

        practice = _make_practice(slack_message_ts="1234.5678", slack_details_ts="OLD.TS")

        with patch("app.slack.practices.announcements.get_slack_client") as mock_get_client, \
             patch("app.practices.service.convert_practice_to_info", return_value=_make_practice_info()), \
             patch("app.slack.practices.announcements.build_practice_announcement_blocks", return_value=[]), \
             patch("app.slack.practices.announcements._upsert_details_reply") as mock_upsert, \
             patch("app.slack.practices.announcements.db"):

            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            update_practice_announcement(practice)

        mock_upsert.assert_called_once()


class TestUpdatePracticePostWiring:
    """update_practice_post (edit path) calls _upsert_details_reply without weather."""

    def test_details_upserted_no_weather(self, app_context):
        from app.slack.practices.announcements import update_practice_post

        practice = _make_practice(slack_message_ts="1234.5678", slack_details_ts=None)

        with patch("app.slack.practices.announcements.get_slack_client") as mock_get_client, \
             patch("app.practices.service.convert_practice_to_info", return_value=_make_practice_info()), \
             patch("app.slack.practices.announcements.build_practice_announcement_blocks", return_value=[]), \
             patch("app.slack.practices.announcements._upsert_details_reply") as mock_upsert, \
             patch("app.slack.practices.announcements.db"):

            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            result = update_practice_post(practice)

        assert result.get("success") is True
        mock_upsert.assert_called_once()
        # No weather or trail passed on the edit path
        assert mock_upsert.call_args[1].get("weather") is None
        assert mock_upsert.call_args[1].get("trail_conditions") is None

    def test_backfill_path_new_thread_reply(self, app_context):
        """When slack_details_ts is None on an existing post, a new reply is created."""
        from app.slack.practices.announcements import _upsert_details_reply

        client = MagicMock()
        client.chat_postMessage.return_value = {"ts": "NEW.TS"}
        practice = _make_practice(slack_message_ts="1234.5678", slack_details_ts=None)

        with patch("app.slack.practices.announcements._gather_conditions", return_value=(None, None, None)), \
             patch("app.slack.practices.announcements.build_practice_details_blocks",
                   return_value=[{"type": "section"}]), \
             patch("app.slack.practices.announcements.db") as mock_db:
            _upsert_details_reply(client, practice, _make_practice_info())

        client.chat_postMessage.assert_called_once()
        assert practice.slack_details_ts == "NEW.TS"
        mock_db.session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app_context():
    """Provide a minimal Flask app context for tests that import current_app."""
    from flask import Flask
    app = Flask(__name__)
    app.config["TESTING"] = True
    with app.app_context():
        yield app
