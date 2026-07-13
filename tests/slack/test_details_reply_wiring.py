"""Tests for the threaded 'Practice Details' reply wiring.

Verifies that _upsert_details_reply (and the three functions that call it)
correctly post a new threaded reply when slack_details_ts is absent, and
update an existing one when it is present.

Uses unittest.mock throughout - no live Slack calls.
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call
import pytest

from slack_sdk.errors import SlackApiError


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
    p.date = datetime(2026, 7, 14, 18, 15)
    p.location_id = 10
    p.plan_reactions = []
    p.practice_types = []
    # Location with coordinates so _gather_conditions can run (mocked out)
    loc = MagicMock()
    loc.name = "Wirth Park"
    loc.latitude = 44.99
    loc.longitude = -93.32
    p.location = loc
    return p


def _make_practice_info():
    return SimpleNamespace(
        id=42,
        date=datetime(2026, 7, 14, 18, 15),
        location=None,
        activities=[],
    )


# ---------------------------------------------------------------------------
# Direct tests of _upsert_details_reply
# ---------------------------------------------------------------------------

class TestGatherConditions:
    """Test _gather_conditions best-effort daylight + AQI fetch."""

    @pytest.fixture(autouse=True)
    def _stub_trail_lookup(self, monkeypatch):
        monkeypatch.setattr(
            "app.integrations.trail_conditions.get_trail_conditions",
            lambda _location_name: None,
        )

    def _practice_with_coords(self, lat=44.99, lon=-93.32):
        from datetime import datetime
        p = MagicMock()
        p.id = 7
        p.date = datetime(2026, 12, 29, 12, 0)
        loc = MagicMock()
        loc.name = "Wirth Park"
        loc.latitude = lat
        loc.longitude = lon
        p.location = loc
        return p

    def test_no_latlon_still_fetches_trails_by_location_name(self, app_context):
        from app.slack.practices.announcements import _gather_conditions

        p = self._practice_with_coords(lat=None, lon=None)

        with patch("app.integrations.daylight.get_daylight_info") as mock_day, \
             patch("app.integrations.air_quality.get_air_quality") as mock_aqi, \
             patch("app.integrations.weather.get_weather_for_location") as mock_wx, \
             patch("app.integrations.trail_conditions.get_trail_conditions", return_value="TRAIL") as mock_trail:
            conditions = _gather_conditions(p)

        assert conditions.weather is None
        assert conditions.daylight is None
        assert conditions.air_quality is None
        assert conditions.trail_conditions == "TRAIL"
        mock_wx.assert_not_called()
        mock_day.assert_not_called()
        mock_aqi.assert_not_called()
        mock_trail.assert_called_once_with("Wirth Park")

    def test_no_location_returns_none_none_none(self, app_context):
        from app.slack.practices.announcements import _gather_conditions

        p = MagicMock()
        p.id = 7
        p.location = None

        conditions = _gather_conditions(p)
        assert conditions.weather is None
        assert conditions.daylight is None
        assert conditions.air_quality is None

    def test_weather_fetch_fails_returns_none_weather(self, app_context):
        from app.slack.practices.announcements import _gather_conditions

        p = self._practice_with_coords()
        daylight_obj = SimpleNamespace(sunset="something")
        aqi_obj = SimpleNamespace(aqi=78)

        with patch("app.integrations.weather.get_weather_for_location", side_effect=Exception("nws boom")), \
             patch("app.integrations.daylight.get_daylight_info", return_value=daylight_obj), \
             patch("app.integrations.air_quality.get_air_quality", return_value=aqi_obj):
            conditions = _gather_conditions(p)

        assert conditions.weather is None
        assert conditions.daylight is daylight_obj
        assert conditions.air_quality == 78

    def test_daylight_raises_but_aqi_and_weather_succeed(self, app_context):
        from app.slack.practices.announcements import _gather_conditions

        p = self._practice_with_coords()
        aqi_obj = SimpleNamespace(aqi=78)
        weather_obj = SimpleNamespace(temperature_f=32.0)

        with patch("app.integrations.weather.get_weather_for_location", return_value=weather_obj), \
             patch("app.integrations.daylight.get_daylight_info", side_effect=Exception("astral boom")), \
             patch("app.integrations.air_quality.get_air_quality", return_value=aqi_obj):
            conditions = _gather_conditions(p)

        assert conditions.weather is weather_obj
        assert conditions.daylight is None
        assert conditions.air_quality == 78

    def test_aqi_none_yields_none_aqi(self, app_context):
        from app.slack.practices.announcements import _gather_conditions

        p = self._practice_with_coords()
        daylight_obj = SimpleNamespace(sunset="something")
        weather_obj = SimpleNamespace(temperature_f=28.0)

        with patch("app.integrations.weather.get_weather_for_location", return_value=weather_obj), \
             patch("app.integrations.daylight.get_daylight_info", return_value=daylight_obj), \
             patch("app.integrations.air_quality.get_air_quality", return_value=None):
            conditions = _gather_conditions(p)

        assert conditions.weather is weather_obj
        assert conditions.daylight is daylight_obj
        assert conditions.air_quality is None

    def test_all_succeed_returns_weather_daylight_aqi(self, app_context):
        from app.slack.practices.announcements import _gather_conditions

        p = self._practice_with_coords()
        daylight_obj = SimpleNamespace(sunset="something")
        aqi_obj = SimpleNamespace(aqi=42)
        weather_obj = SimpleNamespace(temperature_f=20.0)

        with patch("app.integrations.weather.get_weather_for_location", return_value=weather_obj), \
             patch("app.integrations.daylight.get_daylight_info", return_value=daylight_obj), \
             patch("app.integrations.air_quality.get_air_quality", return_value=aqi_obj):
            conditions = _gather_conditions(p)

        assert conditions.weather is weather_obj
        assert conditions.daylight is daylight_obj
        assert conditions.air_quality == 42

    def test_gather_conditions_returns_an_immutable_snapshot(self, app_context):
        from dataclasses import FrozenInstanceError

        from app.practices.interfaces import AnnouncementConditions
        from app.slack.practices.announcements import _gather_conditions

        practice = self._practice_with_coords(lat=None, lon=None)
        conditions = _gather_conditions(practice)

        assert isinstance(conditions, AnnouncementConditions)
        assert conditions.duration_minutes == 90
        with pytest.raises(FrozenInstanceError):
            conditions.duration_minutes = 105

    def test_gather_conditions_uses_injected_weather_without_refetch(
        self, monkeypatch, app_context
    ):
        from app.slack.practices.announcements import _gather_conditions

        practice = self._practice_with_coords()
        supplied = object()
        monkeypatch.setattr(
            "app.integrations.weather.get_weather_for_location",
            lambda *args, **kwargs: pytest.fail("weather was fetched twice"),
        )
        conditions = _gather_conditions(practice, weather=supplied)
        assert conditions.weather is supplied
        assert conditions.duration_minutes == 90

    def test_gather_conditions_does_not_refetch_explicit_none(
        self, monkeypatch, app_context
    ):
        from app.slack.practices.announcements import _gather_conditions

        practice = self._practice_with_coords()
        monkeypatch.setattr(
            "app.integrations.weather.get_weather_for_location",
            lambda *args, **kwargs: pytest.fail("explicit None was refetched"),
        )
        assert _gather_conditions(practice, weather=None).weather is None

    def test_gather_conditions_preserves_injected_trail_conditions(
        self, app_context
    ):
        from app.slack.practices.announcements import _gather_conditions

        practice = self._practice_with_coords(lat=None, lon=None)
        supplied = object()

        assert (
            _gather_conditions(practice, trail_conditions=supplied).trail_conditions
            is supplied
        )

    def test_gather_conditions_does_not_refetch_explicit_none_trails(
        self, monkeypatch, app_context
    ):
        from app.slack.practices.announcements import _gather_conditions

        practice = self._practice_with_coords(lat=None, lon=None)
        monkeypatch.setattr(
            "app.integrations.trail_conditions.get_trail_conditions",
            lambda *_args, **_kwargs: pytest.fail(
                "explicit None trails were refetched"
            ),
        )

        assert (
            _gather_conditions(practice, trail_conditions=None).trail_conditions
            is None
        )

    def test_trail_fetch_failure_is_logged_and_fails_open(
        self, caplog, app_context
    ):
        from app.slack.practices.announcements import _gather_conditions

        practice = self._practice_with_coords(lat=None, lon=None)
        with patch(
            "app.integrations.trail_conditions.get_trail_conditions",
            side_effect=Exception("skinny ski down"),
        ), caplog.at_level("WARNING"):
            conditions = _gather_conditions(practice)

        assert conditions.trail_conditions is None
        assert "trail conditions fetch failed for practice #7" in caplog.text
        assert "skinny ski down" in caplog.text

    def test_gather_conditions_accepts_zero_coordinates(
        self, monkeypatch, app_context
    ):
        from app.slack.practices.announcements import _gather_conditions

        practice = self._practice_with_coords(lat=0.0, lon=0.0)
        called = []
        monkeypatch.setattr(
            "app.integrations.weather.get_weather_for_location",
            lambda *args, **kwargs: called.append(args) or None,
        )
        _gather_conditions(practice)
        assert called


class TestPracticeConfig:
    def test_default_duration_must_be_positive(self, monkeypatch, caplog, app_context):
        from app.slack.practices import _config

        monkeypatch.setattr(
            _config,
            "_practice_config_cache",
            {"practices": {"default_duration_minutes": 105}},
        )
        assert _config.get_default_duration_minutes() == 105

        monkeypatch.setattr(
            _config,
            "_practice_config_cache",
            {"practices": {"default_duration_minutes": 0}},
        )
        with caplog.at_level("WARNING"):
            assert _config.get_default_duration_minutes() == 90
        assert "Invalid practice duration; using 90 minutes" in caplog.text

    def test_reload_config_resets_practice_config_cache(
        self, monkeypatch, app_context
    ):
        from app.slack.practices import _config

        monkeypatch.setattr(_config, "_config_cache", {"cached": "skipper"})
        monkeypatch.setattr(_config, "_practice_config_cache", {"cached": "practice"})

        reloaded = _config.reload_config()

        assert reloaded is _config._config_cache
        assert _config._practice_config_cache is None


class TestUpsertDetailsReply:
    """Test _upsert_details_reply in isolation."""

    def _call(
        self,
        client,
        practice,
        practice_info=None,
        daylight=None,
        aqi=None,
        blocks=None,
        commit_error=None,
        rollback_error=None,
    ):
        from app.slack.practices.announcements import _upsert_details_reply

        if practice_info is None:
            practice_info = _make_practice_info()

        default_blocks = blocks if blocks is not None else [{"type": "section", "text": {"type": "mrkdwn", "text": "details"}}]

        from app.practices.interfaces import AnnouncementConditions

        conditions = AnnouncementConditions(daylight=daylight, air_quality=aqi)
        with patch("app.slack.practices.announcements.build_practice_details_blocks", return_value=default_blocks), \
             patch("app.slack.practices.announcements.build_practice_details_fallback_text", return_value="Complete practice details", create=True), \
             patch("app.slack.practices.announcements.db") as mock_db:
            if commit_error is not None:
                mock_db.session.commit.side_effect = commit_error
            if rollback_error is not None:
                mock_db.session.rollback.side_effect = rollback_error
            result = _upsert_details_reply(
                client, practice, practice_info, conditions
            )
            return mock_db, result

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
        assert kwargs["text"] == "Complete practice details"

    def test_new_post_saves_slack_details_ts(self):
        """After a new thread reply, slack_details_ts is saved via db.session.commit."""
        client = MagicMock()
        client.chat_postMessage.return_value = {"ts": "9999.0001"}
        practice = _make_practice(slack_details_ts=None)

        mock_db, _ = self._call(client, practice)

        assert practice.slack_details_ts == "9999.0001"
        mock_db.session.commit.assert_called_once()

    @pytest.mark.parametrize(
        ("cleanup_error", "commit_effects", "expected_outcome"),
        [
            (None, [RuntimeError("database commit failed")], "cleaned"),
            (
                "cant_delete_message",
                [RuntimeError("database commit failed"), None],
                "recovered",
            ),
            (
                "cant_delete_message",
                [
                    RuntimeError("database commit failed"),
                    RuntimeError("recovery commit failed"),
                ],
                "ambiguous",
            ),
        ],
    )
    def test_new_details_commit_failure_compensates_or_recovers_once(
        self,
        app_context,
        caplog,
        cleanup_error,
        commit_effects,
        expected_outcome,
    ):
        client = MagicMock()
        client.chat_postMessage.return_value = {"ts": "9999.0001"}
        if cleanup_error:
            client.chat_delete.side_effect = SlackApiError(
                "cleanup failed", {"error": cleanup_error}
            )
        practice = _make_practice(slack_details_ts=None)

        mock_db, result = self._call(
            client,
            practice,
            commit_error=commit_effects,
        )

        assert result["success"] is (expected_outcome == "recovered")
        if expected_outcome == "recovered":
            assert result["recovered"] is True
            assert result["message_ts"] == "9999.0001"
            assert practice.slack_details_ts == "9999.0001"
        else:
            assert "database commit failed" in result["error"]
            assert practice.slack_details_ts is None
        if expected_outcome == "ambiguous":
            assert result["ambiguous_orphan"] == {
                "channel_id": "CTEST",
                "message_ts": "9999.0001",
            }
            assert "channel=CTEST ts=9999.0001" in caplog.text
        else:
            assert "ambiguous_orphan" not in result
        assert mock_db.session.commit.call_count == (
            2 if cleanup_error else 1
        )
        assert mock_db.session.rollback.call_count == (
            2 if expected_outcome == "ambiguous" else 1
        )
        client.chat_delete.assert_called_once_with(
            channel="CTEST", ts="9999.0001"
        )

    def test_details_compensation_survives_rollback_failure(self, app_context):
        client = MagicMock()
        client.chat_postMessage.return_value = {"ts": "9999.0001"}
        practice = _make_practice(slack_details_ts=None)

        _mock_db, result = self._call(
            client,
            practice,
            commit_error=RuntimeError("commit failed"),
            rollback_error=RuntimeError("rollback failed"),
        )

        assert result["success"] is False
        assert result["cleanup"] == {"success": True}
        assert practice.slack_details_ts is None
        client.chat_delete.assert_called_once_with(
            channel="CTEST", ts="9999.0001"
        )

    def test_existing_ts_calls_chat_update(self):
        """When slack_details_ts is already set, chat_update is used instead."""
        client = MagicMock()
        practice = _make_practice(slack_details_ts="8888.0001")

        self._call(client, practice)

        client.chat_update.assert_called_once()
        kwargs = client.chat_update.call_args[1]
        assert kwargs["ts"] == "8888.0001"
        assert kwargs["channel"] == "CTEST"
        assert kwargs["text"] == "Complete practice details"
        # Must NOT post a new thread message
        client.chat_postMessage.assert_not_called()

    def test_existing_ts_no_db_commit(self):
        """Updating an existing reply must not trigger an extra db commit."""
        client = MagicMock()
        practice = _make_practice(slack_details_ts="8888.0001")

        mock_db, _ = self._call(client, practice)

        mock_db.session.commit.assert_not_called()

    def test_empty_blocks_skips_slack_call(self):
        """When build_practice_details_blocks returns empty list, nothing is posted."""
        client = MagicMock()
        practice = _make_practice(slack_details_ts=None)

        self._call(client, practice, blocks=[])

        client.chat_postMessage.assert_not_called()
        client.chat_update.assert_not_called()
        client.chat_delete.assert_not_called()

    def test_empty_blocks_delete_stale_reply_then_clear_and_commit(self):
        client = MagicMock()
        practice = _make_practice(slack_details_ts="222.333")

        mock_db, result = self._call(client, practice, blocks=[])

        client.chat_delete.assert_called_once_with(
            channel="CTEST", ts="222.333"
        )
        assert practice.slack_details_ts is None
        mock_db.session.commit.assert_called_once_with()
        assert result == {"success": True, "deleted": True}

    def test_failed_stale_reply_delete_retains_timestamp(self, app_context):
        client = MagicMock()
        client.chat_delete.side_effect = SlackApiError(
            "delete failed", {"error": "cant_delete_message"}
        )
        practice = _make_practice(slack_details_ts="222.333")

        mock_db, result = self._call(client, practice, blocks=[])

        assert practice.slack_details_ts == "222.333"
        mock_db.session.commit.assert_not_called()
        assert result["success"] is False

    def test_details_commit_failure_rolls_back_before_restore_and_can_retry(
        self, app_context
    ):
        from app.practices.interfaces import AnnouncementConditions
        from app.slack.practices.announcements import _upsert_details_reply

        client = MagicMock()
        practice = _make_practice(slack_details_ts="222.333")
        rollback_states = []

        with patch(
            "app.slack.practices.announcements.build_practice_details_blocks",
            return_value=[],
        ), patch("app.slack.practices.announcements.db") as mock_db:
            mock_db.session.commit.side_effect = [
                RuntimeError("database commit failed"),
                None,
            ]
            mock_db.session.rollback.side_effect = lambda: rollback_states.append(
                practice.slack_details_ts
            )
            client.chat_delete.side_effect = [
                None,
                SlackApiError("missing", {"error": "message_not_found"}),
            ]

            first = _upsert_details_reply(
                client,
                practice,
                _make_practice_info(),
                AnnouncementConditions(),
            )
            second = _upsert_details_reply(
                client,
                practice,
                _make_practice_info(),
                AnnouncementConditions(),
            )

        assert first == {"success": False, "error": "database commit failed"}
        assert rollback_states == [None]
        assert second == {"success": True, "deleted": True}
        assert practice.slack_details_ts is None
        assert client.chat_delete.call_count == 2
        assert mock_db.session.commit.call_count == 2
        mock_db.session.rollback.assert_called_once_with()

    def test_slack_exception_is_swallowed(self, app_context):
        """A Slack API error must not propagate - best-effort only."""
        client = MagicMock()
        client.chat_postMessage.side_effect = Exception("slack down")
        practice = _make_practice(slack_details_ts=None)

        # Should not raise
        from app.slack.practices.announcements import _upsert_details_reply
        from app.practices.interfaces import AnnouncementConditions

        with patch("app.slack.practices.announcements.build_practice_details_blocks",
                   return_value=[{"type": "section"}]), \
             patch("app.slack.practices.announcements.build_practice_details_fallback_text",
                   return_value="Complete practice details", create=True), \
             patch("app.slack.practices.announcements.db"):
            result = _upsert_details_reply(
                client,
                practice,
                _make_practice_info(),
                AnnouncementConditions(),
            )

        assert result["success"] is False


# ---------------------------------------------------------------------------
# Integration-style wiring tests
# ---------------------------------------------------------------------------

class TestPostPracticeAnnouncementWiring:
    """post_practice_announcement calls _upsert_details_reply after the hero commit."""

    def test_gathers_once_and_surfaces_failed_details_result(
        self, app_context, caplog
    ):
        from app.slack.practices.announcements import post_practice_announcement
        from app.practices.interfaces import AnnouncementConditions

        practice = _make_practice(slack_message_ts=None, slack_details_ts=None)
        practice.plan_reactions = [
            {"emoji": "evergreen_tree", "label": "Endurance option"}
        ]
        practice_info = _make_practice_info()
        conditions = AnnouncementConditions()
        expected_fallback = (
            "Status: Scheduled. Tuesday, July 14 at 6:15 PM at Test Park. "
            "Workout: 5 x 4 minutes. RSVP with ✅."
        )
        expected_details = {
            "success": False,
            "error": "recovery commit failed",
            "ambiguous_orphan": {
                "channel_id": "CTEST",
                "message_ts": "2222.0001",
            },
        }

        with patch("app.slack.practices.announcements.get_slack_client") as mock_get_client, \
             patch("app.slack.practices.announcements.get_channel_id_by_name", return_value="CTEST"), \
             patch("app.slack.practices.announcements._get_announcement_channel", return_value="CTEST"), \
             patch("app.practices.service.convert_practice_to_info", return_value=practice_info), \
             patch("app.slack.practices.announcements._gather_conditions", return_value=conditions) as mock_gather, \
             patch("app.slack.practices.announcements.build_practice_announcement_blocks", return_value=[{"type": "header"}]) as mock_hero, \
             patch("app.slack.practices.announcements.build_practice_fallback_text", return_value=expected_fallback, create=True) as mock_fallback, \
             patch("app.slack.practices.announcements._upsert_details_reply", return_value=expected_details) as mock_upsert, \
             patch("app.slack.practices.announcements._seed_plan_reactions", create=True) as mock_seed, \
             patch("app.slack.practices.announcements.db") as mock_db, \
             patch("app.slack.practices.coach_review.create_practice_log_thread", create=True):
            mock_client = MagicMock()
            mock_client.chat_postMessage.return_value = {"ts": "1111.0001"}
            mock_get_client.return_value = mock_client

            result = post_practice_announcement(
                practice, weather=None, trail_conditions="TRAIL"
            )

        assert result.get("success") is True
        assert result["details"] == expected_details
        assert "root linked but Details sync failed" in caplog.text
        assert "2222.0001" in caplog.text
        mock_gather.assert_called_once_with(
            practice, weather=None, trail_conditions="TRAIL"
        )
        mock_hero.assert_called_once_with(practice_info, conditions)
        mock_fallback.assert_called_once_with(practice_info, conditions)
        mock_upsert.assert_called_once_with(
            mock_client, practice, practice_info, conditions
        )
        mock_seed.assert_called_once_with(mock_client, practice)
        assert mock_client.chat_postMessage.call_args.kwargs["text"] == expected_fallback
        mock_db.session.commit.assert_called_once_with()

    def test_root_identity_is_committed_before_all_secondary_work(
        self, app_context
    ):
        from app.slack.practices.announcements import post_practice_announcement

        practice = _make_practice(slack_message_ts=None, slack_details_ts=None)
        events = []

        def commit_root_identity():
            assert practice.slack_channel_id == "CTEST"
            assert practice.slack_message_ts == "1111.0001"
            events.append("root_commit")

        with patch("app.slack.practices.announcements.get_slack_client") as mock_get_client, \
             patch("app.slack.practices.announcements._get_announcement_channel", return_value="CTEST"), \
             patch("app.practices.service.convert_practice_to_info", return_value=_make_practice_info()), \
             patch("app.slack.practices.announcements._gather_conditions"), \
             patch("app.slack.practices.announcements.build_practice_announcement_blocks", return_value=[]), \
             patch("app.slack.practices.announcements.build_practice_fallback_text", return_value="complete fallback"), \
             patch("app.slack.practices.announcements._upsert_details_reply", side_effect=lambda *_args: events.append("details") or {"success": True}), \
             patch("app.slack.practices.announcements._seed_plan_reactions", side_effect=lambda *_args: events.append("reactions")), \
             patch("app.slack.practices.announcements.db") as mock_db, \
             patch("app.slack.practices.coach_review.create_practice_log_thread", side_effect=lambda *_args: events.append("log"), create=True):
            client = MagicMock()
            client.chat_postMessage.side_effect = lambda **_kwargs: (
                events.append("root_write") or {"ts": "1111.0001"}
            )
            mock_get_client.return_value = client
            mock_db.session.commit.side_effect = commit_root_identity

            result = post_practice_announcement(practice)

        assert result["success"] is True
        assert events == [
            "root_write",
            "root_commit",
            "details",
            "reactions",
            "log",
        ]

    def test_missing_root_timestamp_does_not_mutate_or_commit(self, app_context):
        from app.slack.practices.announcements import post_practice_announcement

        practice = _make_practice(
            slack_message_ts=None,
            slack_channel_id="C-ORIGINAL",
            slack_details_ts=None,
        )
        practice.slack_session_emoji = "six"
        client = MagicMock()
        client.chat_postMessage.return_value = {}

        with patch(
            "app.slack.practices.announcements.get_slack_client",
            return_value=client,
        ), patch(
            "app.slack.practices.announcements._get_announcement_channel",
            return_value="CTEST",
        ), patch(
            "app.practices.service.convert_practice_to_info",
            return_value=_make_practice_info(),
        ), patch(
            "app.slack.practices.announcements._conditions_for_render"
        ), patch(
            "app.slack.practices.announcements.build_practice_announcement_blocks",
            return_value=[],
        ), patch(
            "app.slack.practices.announcements.build_practice_fallback_text",
            return_value="complete fallback",
        ), patch(
            "app.slack.practices.announcements._upsert_details_reply"
        ) as details, patch(
            "app.slack.practices.announcements._seed_plan_reactions"
        ) as reactions, patch(
            "app.slack.practices.announcements.db"
        ) as mock_db:
            result = post_practice_announcement(practice)

        assert result == {
            "success": False,
            "error": "Slack did not return a message timestamp",
        }
        assert (
            practice.slack_channel_id,
            practice.slack_message_ts,
            practice.slack_session_emoji,
        ) == ("C-ORIGINAL", None, "six")
        mock_db.session.commit.assert_not_called()
        details.assert_not_called()
        reactions.assert_not_called()

    @pytest.mark.parametrize(
        ("cleanup_error", "commit_effects", "expected_outcome"),
        [
            (None, [RuntimeError("database commit failed")], "cleaned"),
            (
                "cant_delete_message",
                [RuntimeError("database commit failed"), None],
                "recovered",
            ),
            (
                "cant_delete_message",
                [
                    RuntimeError("database commit failed"),
                    RuntimeError("recovery commit failed"),
                ],
                "ambiguous",
            ),
        ],
    )
    def test_root_link_commit_failure_compensates_or_recovers_once(
        self,
        app_context,
        caplog,
        cleanup_error,
        commit_effects,
        expected_outcome,
    ):
        from app.slack.practices.announcements import post_practice_announcement

        practice = _make_practice(
            slack_message_ts=None,
            slack_channel_id="C-ORIGINAL",
            slack_details_ts=None,
        )
        practice.slack_session_emoji = "six"
        client = MagicMock()
        client.chat_postMessage.return_value = {"ts": "1111.0001"}
        if cleanup_error:
            client.chat_delete.side_effect = SlackApiError(
                "cleanup failed", {"error": cleanup_error}
            )

        with patch(
            "app.slack.practices.announcements.get_slack_client",
            return_value=client,
        ), patch(
            "app.slack.practices.announcements._get_announcement_channel",
            return_value="CTEST",
        ), patch(
            "app.practices.service.convert_practice_to_info",
            return_value=_make_practice_info(),
        ), patch(
            "app.slack.practices.announcements._conditions_for_render"
        ), patch(
            "app.slack.practices.announcements.build_practice_announcement_blocks",
            return_value=[],
        ), patch(
            "app.slack.practices.announcements.build_practice_fallback_text",
            return_value="complete fallback",
        ), patch(
            "app.slack.practices.announcements._upsert_details_reply",
            return_value={"success": True, "message_ts": "details.1"},
        ) as details, patch(
            "app.slack.practices.announcements._seed_plan_reactions"
        ) as reactions, patch(
            "app.slack.practices.announcements.db"
        ) as mock_db:
            mock_db.session.commit.side_effect = commit_effects
            result = post_practice_announcement(practice)

        assert result["success"] is (expected_outcome == "recovered")
        assert "safe_to_fallback" not in result
        if expected_outcome == "recovered":
            assert result["recovered"] is True
            assert result["details"] == {
                "success": True,
                "message_ts": "details.1",
            }
            assert (
                practice.slack_channel_id,
                practice.slack_message_ts,
                practice.slack_session_emoji,
            ) == ("CTEST", "1111.0001", None)
            details.assert_called_once()
            reactions.assert_called_once()
        else:
            assert "database commit failed" in result["error"]
            assert (
                practice.slack_channel_id,
                practice.slack_message_ts,
                practice.slack_session_emoji,
            ) == ("C-ORIGINAL", None, "six")
            details.assert_not_called()
            reactions.assert_not_called()
        if expected_outcome == "ambiguous":
            assert result["ambiguous_orphan"] == {
                "channel_id": "CTEST",
                "message_ts": "1111.0001",
            }
            assert "channel=CTEST ts=1111.0001" in caplog.text
        else:
            assert "ambiguous_orphan" not in result
        assert mock_db.session.rollback.call_count == (
            2 if expected_outcome == "ambiguous" else 1
        )
        assert mock_db.session.commit.call_count == (
            2 if cleanup_error else 1
        )
        client.chat_delete.assert_called_once_with(
            channel="CTEST", ts="1111.0001"
        )

    def test_generic_root_post_failure_is_contained_without_mutation(
        self, app_context
    ):
        from app.slack.practices.announcements import post_practice_announcement

        practice = _make_practice(
            slack_message_ts=None,
            slack_channel_id="C-ORIGINAL",
            slack_details_ts=None,
        )
        practice.slack_session_emoji = "six"
        client = MagicMock()
        client.chat_postMessage.side_effect = RuntimeError("network interrupted")

        with patch(
            "app.slack.practices.announcements.get_slack_client",
            return_value=client,
        ), patch(
            "app.slack.practices.announcements._get_announcement_channel",
            return_value="CTEST",
        ), patch(
            "app.practices.service.convert_practice_to_info",
            return_value=_make_practice_info(),
        ), patch(
            "app.slack.practices.announcements._conditions_for_render"
        ), patch(
            "app.slack.practices.announcements.build_practice_announcement_blocks",
            return_value=[],
        ), patch(
            "app.slack.practices.announcements.build_practice_fallback_text",
            return_value="complete fallback",
        ), patch("app.slack.practices.announcements.db") as mock_db:
            result = post_practice_announcement(practice)

        assert result == {"success": False, "error": "network interrupted"}
        assert (
            practice.slack_channel_id,
            practice.slack_message_ts,
            practice.slack_session_emoji,
        ) == ("C-ORIGINAL", None, "six")
        mock_db.session.commit.assert_not_called()
        client.chat_delete.assert_not_called()

    def test_explicit_none_weather_is_not_refetched(self, app_context):
        from app.slack.practices.announcements import post_practice_announcement

        practice = _make_practice(slack_message_ts=None, slack_details_ts=None)

        with patch("app.slack.practices.announcements.get_slack_client") as mock_get_client, \
             patch("app.slack.practices.announcements.get_channel_id_by_name", return_value="CTEST"), \
             patch("app.slack.practices.announcements._get_announcement_channel", return_value="CTEST"), \
             patch("app.practices.service.convert_practice_to_info", return_value=_make_practice_info()), \
             patch("app.slack.practices.announcements.build_practice_announcement_blocks", return_value=[]), \
             patch("app.slack.practices.announcements.build_practice_fallback_text", return_value="complete fallback", create=True), \
             patch("app.slack.practices.announcements._upsert_details_reply"), \
             patch("app.slack.practices.announcements._seed_plan_reactions", create=True), \
             patch("app.integrations.weather.get_weather_for_location") as mock_weather, \
             patch("app.integrations.trail_conditions.get_trail_conditions", return_value=None), \
             patch("app.integrations.daylight.get_daylight_info", return_value=None), \
             patch("app.integrations.air_quality.get_air_quality", return_value=None), \
             patch("app.slack.practices.announcements.db"), \
             patch("app.slack.practices.coach_review.create_practice_log_thread", create=True):
            mock_client = MagicMock()
            mock_client.chat_postMessage.return_value = {"ts": "1111.0001"}
            mock_get_client.return_value = mock_client

            result = post_practice_announcement(practice, weather=None)

        assert result.get("success") is True
        mock_weather.assert_not_called()

    def test_omitted_weather_is_fetched_once(self, app_context):
        from app.slack.practices.announcements import post_practice_announcement

        practice = _make_practice(slack_message_ts=None, slack_details_ts=None)
        fetched = object()

        with patch("app.slack.practices.announcements.get_slack_client") as mock_get_client, \
             patch("app.slack.practices.announcements.get_channel_id_by_name", return_value="CTEST"), \
             patch("app.slack.practices.announcements._get_announcement_channel", return_value="CTEST"), \
             patch("app.practices.service.convert_practice_to_info", return_value=_make_practice_info()), \
             patch("app.slack.practices.announcements.build_practice_announcement_blocks", return_value=[]), \
             patch("app.slack.practices.announcements.build_practice_fallback_text", return_value="complete fallback", create=True), \
             patch("app.slack.practices.announcements._upsert_details_reply"), \
             patch("app.slack.practices.announcements._seed_plan_reactions", create=True), \
             patch("app.integrations.weather.get_weather_for_location", return_value=fetched) as mock_weather, \
             patch("app.integrations.trail_conditions.get_trail_conditions", return_value=None), \
             patch("app.integrations.daylight.get_daylight_info", return_value=None), \
             patch("app.integrations.air_quality.get_air_quality", return_value=None), \
             patch("app.slack.practices.announcements.db"), \
             patch("app.slack.practices.coach_review.create_practice_log_thread", create=True):
            mock_client = MagicMock()
            mock_client.chat_postMessage.return_value = {"ts": "1111.0001"}
            mock_get_client.return_value = mock_client

            result = post_practice_announcement(practice)

        assert result.get("success") is True
        mock_weather.assert_called_once()

    def test_explicit_none_trails_are_not_refetched(self, app_context):
        from app.slack.practices.announcements import post_practice_announcement

        practice = _make_practice(slack_message_ts=None, slack_details_ts=None)

        with patch("app.slack.practices.announcements.get_slack_client") as mock_get_client, \
             patch("app.slack.practices.announcements._get_announcement_channel", return_value="CTEST"), \
             patch("app.practices.service.convert_practice_to_info", return_value=_make_practice_info()), \
             patch("app.slack.practices.announcements.build_practice_announcement_blocks", return_value=[]), \
             patch("app.slack.practices.announcements.build_practice_fallback_text", return_value="complete fallback"), \
             patch("app.slack.practices.announcements._upsert_details_reply"), \
             patch("app.slack.practices.announcements._seed_plan_reactions"), \
             patch("app.integrations.trail_conditions.get_trail_conditions") as mock_trails, \
             patch("app.integrations.daylight.get_daylight_info", return_value=None), \
             patch("app.integrations.air_quality.get_air_quality", return_value=None), \
             patch("app.slack.practices.announcements.db"), \
             patch("app.slack.practices.coach_review.create_practice_log_thread", create=True):
            client = MagicMock()
            client.chat_postMessage.return_value = {"ts": "1111.0001"}
            mock_get_client.return_value = client

            result = post_practice_announcement(
                practice, weather=None, trail_conditions=None
            )

        assert result["success"] is True
        mock_trails.assert_not_called()

    def test_omitted_trails_are_fetched_once_for_the_shared_snapshot(
        self, app_context
    ):
        from app.slack.practices.announcements import post_practice_announcement

        practice = _make_practice(slack_message_ts=None, slack_details_ts=None)
        fetched = object()

        with patch("app.slack.practices.announcements.get_slack_client") as mock_get_client, \
             patch("app.slack.practices.announcements._get_announcement_channel", return_value="CTEST"), \
             patch("app.practices.service.convert_practice_to_info", return_value=_make_practice_info()), \
             patch("app.slack.practices.announcements.build_practice_announcement_blocks", return_value=[]), \
             patch("app.slack.practices.announcements.build_practice_fallback_text", return_value="complete fallback"), \
             patch("app.slack.practices.announcements._upsert_details_reply") as mock_upsert, \
             patch("app.slack.practices.announcements._seed_plan_reactions"), \
             patch("app.integrations.trail_conditions.get_trail_conditions", return_value=fetched) as mock_trails, \
             patch("app.integrations.daylight.get_daylight_info", return_value=None), \
             patch("app.integrations.air_quality.get_air_quality", return_value=None), \
             patch("app.slack.practices.announcements.db"), \
             patch("app.slack.practices.coach_review.create_practice_log_thread", create=True):
            client = MagicMock()
            client.chat_postMessage.return_value = {"ts": "1111.0001"}
            mock_get_client.return_value = client

            result = post_practice_announcement(practice, weather=None)

        assert result["success"] is True
        mock_trails.assert_called_once_with("Wirth Park")
        assert mock_upsert.call_args.args[3].trail_conditions is fetched

    def test_initial_post_seeds_checkmark_and_saved_plan_reactions(self, app_context):
        from app.slack.practices.announcements import post_practice_announcement

        practice = _make_practice(slack_message_ts=None, slack_details_ts=None)
        practice.plan_reactions = [
            {"emoji": "snowflake", "label": "Short route"}
        ]

        with patch("app.slack.practices.announcements.get_slack_client") as mock_get_client, \
             patch("app.slack.practices.announcements.get_channel_id_by_name", return_value="CTEST"), \
             patch("app.slack.practices.announcements._get_announcement_channel", return_value="CTEST"), \
             patch("app.practices.service.convert_practice_to_info", return_value=_make_practice_info()), \
             patch("app.slack.practices.announcements._gather_conditions"), \
             patch("app.slack.practices.announcements.build_practice_announcement_blocks", return_value=[]), \
             patch("app.slack.practices.announcements.build_practice_fallback_text", return_value="complete fallback", create=True), \
             patch("app.slack.practices.announcements._upsert_details_reply") as mock_upsert, \
             patch("app.slack.practices.announcements.db"), \
             patch("app.slack.practices.coach_review.create_practice_log_thread", create=True):

            mock_client = MagicMock()
            mock_client.chat_postMessage.return_value = {"ts": "1111.0001"}
            mock_client.reactions_add = MagicMock()
            mock_get_client.return_value = mock_client

            result = post_practice_announcement(practice)

        assert result.get("success") is True
        mock_upsert.assert_called_once()
        assert mock_client.reactions_add.call_args_list == [
            call(channel="CTEST", timestamp="1111.0001", name="white_check_mark"),
            call(channel="CTEST", timestamp="1111.0001", name="snowflake"),
        ]

    def test_malformed_legacy_plan_json_cannot_fail_a_successful_root_post(
        self, app_context
    ):
        from app.slack.practices.announcements import post_practice_announcement

        practice = _make_practice(slack_message_ts=None, slack_details_ts=None)
        practice.plan_reactions = [
            {"emoji": "white_check_mark", "label": "Legacy reserved value"}
        ]

        with patch("app.slack.practices.announcements.get_slack_client") as mock_get_client, \
             patch("app.slack.practices.announcements._get_announcement_channel", return_value="CTEST"), \
             patch("app.practices.service.convert_practice_to_info", return_value=_make_practice_info()), \
             patch("app.slack.practices.announcements._gather_conditions"), \
             patch("app.slack.practices.announcements.build_practice_announcement_blocks", return_value=[]), \
             patch("app.slack.practices.announcements.build_practice_fallback_text", return_value="complete fallback"), \
             patch("app.slack.practices.announcements._upsert_details_reply", return_value={"success": True}) as mock_upsert, \
             patch("app.slack.practices.announcements.db"), \
             patch("app.slack.practices.coach_review.create_practice_log_thread", create=True):
            client = MagicMock()
            client.chat_postMessage.return_value = {"ts": "1111.0001"}
            mock_get_client.return_value = client

            result = post_practice_announcement(practice)

        assert result["success"] is True
        mock_upsert.assert_called_once()
        client.reactions_add.assert_called_once_with(
            channel="CTEST",
            timestamp="1111.0001",
            name="white_check_mark",
        )


class TestUpdatePracticeAnnouncementWiring:
    """Standalone update entry points share one complete render snapshot."""

    @pytest.mark.parametrize("entrypoint", ["announcement", "post"])
    def test_update_uses_complete_fallback_and_shared_snapshot(
        self, app_context, entrypoint
    ):
        from app.slack.practices.announcements import update_practice_announcement
        from app.slack.practices.announcements import update_practice_post
        from app.practices.interfaces import AnnouncementConditions

        practice = _make_practice(slack_message_ts="1234.5678", slack_details_ts=None)
        practice_info = _make_practice_info()
        conditions = AnnouncementConditions()
        expected_fallback = "complete expected fallback"

        with patch("app.slack.practices.announcements.get_slack_client") as mock_get_client, \
             patch("app.practices.service.convert_practice_to_info", return_value=practice_info), \
             patch("app.slack.practices.announcements._gather_conditions", return_value=conditions) as mock_gather, \
             patch("app.slack.practices.announcements.build_practice_announcement_blocks", return_value=[]) as mock_hero, \
             patch("app.slack.practices.announcements.build_practice_fallback_text", return_value=expected_fallback, create=True) as mock_fallback, \
             patch("app.slack.practices.announcements._upsert_details_reply") as mock_upsert, \
             patch("app.slack.practices.announcements._reconcile_plan_reactions", create=True):

            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            result = (
                update_practice_announcement(practice)
                if entrypoint == "announcement"
                else update_practice_post(practice)
            )

        assert result.get("success") is True
        mock_gather.assert_called_once_with(practice)
        mock_hero.assert_called_once_with(
            practice_info, conditions, announcement_notice=None
        )
        mock_fallback.assert_called_once_with(
            practice_info, conditions, announcement_notice=None
        )
        mock_upsert.assert_called_once_with(
            mock_client, practice, practice_info, conditions
        )
        assert mock_client.chat_update.call_args.kwargs["text"] == expected_fallback

    def test_plan_reaction_change_reconciles_only_the_diff(self, app_context):
        from app.slack.practices.announcements import update_practice_announcement

        practice = _make_practice()
        practice.plan_reactions = [
            {"emoji": "new_choice", "label": "New choice"}
        ]
        previous = [{"emoji": "old_choice", "label": "Old choice"}]

        with patch("app.slack.practices.announcements.get_slack_client") as mock_get_client, \
             patch("app.practices.service.convert_practice_to_info", return_value=_make_practice_info()), \
             patch("app.slack.practices.announcements._gather_conditions"), \
             patch("app.slack.practices.announcements.build_practice_announcement_blocks", return_value=[]), \
             patch("app.slack.practices.announcements.build_practice_fallback_text", return_value="complete fallback", create=True), \
             patch("app.slack.practices.announcements._upsert_details_reply"):
            client = MagicMock()
            mock_get_client.return_value = client

            result = update_practice_announcement(
                practice, previous_plan_reactions=previous
            )

        assert result["success"] is True
        client.reactions_remove.assert_called_once_with(
            channel="CTEST", timestamp="1234.5678", name="old_choice"
        )
        client.reactions_add.assert_called_once_with(
            channel="CTEST", timestamp="1234.5678", name="new_choice"
        )

    def test_malformed_legacy_plan_json_cannot_fail_a_successful_root_update(
        self, app_context
    ):
        from app.slack.practices.announcements import update_practice_announcement

        practice = _make_practice()
        practice.plan_reactions = [
            {"emoji": "white_check_mark", "label": "Legacy reserved value"}
        ]

        with patch("app.slack.practices.announcements.get_slack_client") as mock_get_client, \
             patch("app.practices.service.convert_practice_to_info", return_value=_make_practice_info()), \
             patch("app.slack.practices.announcements._gather_conditions"), \
             patch("app.slack.practices.announcements.build_practice_announcement_blocks", return_value=[]), \
             patch("app.slack.practices.announcements.build_practice_fallback_text", return_value="complete fallback"), \
             patch("app.slack.practices.announcements._upsert_details_reply", return_value={"success": True}) as mock_upsert:
            client = MagicMock()
            mock_get_client.return_value = client

            result = update_practice_announcement(
                practice,
                previous_plan_reactions=[
                    {"emoji": "old_choice", "label": "Old choice"}
                ],
            )

        assert result["success"] is True
        mock_upsert.assert_called_once()
        client.reactions_remove.assert_not_called()
        client.reactions_add.assert_not_called()

    def test_backfill_path_new_thread_reply(self, app_context):
        """When slack_details_ts is None on an existing post, a new reply is created."""
        from app.slack.practices.announcements import _upsert_details_reply

        client = MagicMock()
        client.chat_postMessage.return_value = {"ts": "NEW.TS"}
        practice = _make_practice(slack_message_ts="1234.5678", slack_details_ts=None)

        from app.practices.interfaces import AnnouncementConditions

        with patch("app.slack.practices.announcements.build_practice_details_blocks",
                   return_value=[{"type": "section"}]), \
             patch("app.slack.practices.announcements.build_practice_details_fallback_text",
                   return_value="Complete practice details", create=True), \
             patch("app.slack.practices.announcements.db") as mock_db:
            _upsert_details_reply(
                client,
                practice,
                _make_practice_info(),
                AnnouncementConditions(),
            )

        client.chat_postMessage.assert_called_once()
        assert practice.slack_details_ts == "NEW.TS"
        mock_db.session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# Combined-lift details reply tests
# ---------------------------------------------------------------------------

def _make_group_practices(n=2, existing_details_ts=None):
    """Return n fake Practice instances that share a common slack_message_ts."""
    shared_ts = "COMBINED.1234"
    channel_id = "CCOMBINED"
    practices = []
    for i in range(n):
        p = MagicMock()
        p.id = 100 + i
        p.slack_message_ts = shared_ts
        p.slack_channel_id = channel_id
        p.slack_details_ts = existing_details_ts
        loc = MagicMock()
        loc.latitude = 44.99
        loc.longitude = -93.32
        p.location = loc
        practices.append(p)
    return practices


class TestUpsertCombinedDetailsReply:
    """Tests for _upsert_combined_details_reply."""

    def _blocks(self):
        return [{"type": "header", "text": {"type": "plain_text", "text": "Practice Details"}}]

    def test_new_post_calls_chat_postMessage_with_thread_ts_and_no_broadcast(self, app_context):
        """When no practice has slack_details_ts set, a new thread reply is posted."""
        from app.slack.practices.announcements import _upsert_combined_details_reply

        client = MagicMock()
        client.chat_postMessage.return_value = {"ts": "REPLY.TS"}
        practices = _make_group_practices(2)

        with patch("app.practices.service.convert_practice_to_info",
                   return_value=_make_practice_info()), \
             patch("app.slack.practices.announcements.build_practice_details_blocks",
                   return_value=self._blocks()), \
             patch("app.slack.practices.announcements.db") as mock_db:
            _upsert_combined_details_reply(client, practices)

        client.chat_postMessage.assert_called_once()
        kw = client.chat_postMessage.call_args[1]
        assert kw["thread_ts"] == "COMBINED.1234"
        assert kw["reply_broadcast"] is False
        assert kw["unfurl_links"] is False
        assert kw["unfurl_media"] is False
        mock_db.session.commit.assert_called_once()

    def test_new_post_saves_details_ts_to_all_practices(self, app_context):
        """After a new reply, slack_details_ts is saved to every practice in the group."""
        from app.slack.practices.announcements import _upsert_combined_details_reply

        client = MagicMock()
        client.chat_postMessage.return_value = {"ts": "REPLY.TS"}
        practices = _make_group_practices(3)

        with patch("app.practices.service.convert_practice_to_info",
                   return_value=_make_practice_info()), \
             patch("app.slack.practices.announcements.build_practice_details_blocks",
                   return_value=self._blocks()), \
             patch("app.slack.practices.announcements.db"):
            _upsert_combined_details_reply(client, practices)

        for p in practices:
            assert p.slack_details_ts == "REPLY.TS", \
                f"Practice #{p.id} should have slack_details_ts='REPLY.TS'"

    @pytest.mark.parametrize("cleanup_error", [None, "cant_delete_message"])
    def test_new_combined_details_commit_failure_restores_and_compensates(
        self, app_context, cleanup_error
    ):
        from app.slack.practices.announcements import (
            _upsert_combined_details_reply,
        )

        client = MagicMock()
        client.chat_postMessage.return_value = {"ts": "REPLY.TS"}
        if cleanup_error:
            client.chat_delete.side_effect = SlackApiError(
                "cleanup failed", {"error": cleanup_error}
            )
        practices = _make_group_practices(2)

        with patch(
            "app.practices.service.convert_practice_to_info",
            return_value=_make_practice_info(),
        ), patch(
            "app.slack.practices.announcements.build_practice_details_blocks",
            return_value=self._blocks(),
        ), patch("app.slack.practices.announcements.db") as mock_db:
            mock_db.session.commit.side_effect = RuntimeError(
                "database commit failed"
            )
            result = _upsert_combined_details_reply(client, practices)

        assert result["success"] is False
        assert "database commit failed" in result["error"]
        assert result["cleanup"]["success"] is (cleanup_error is None)
        if cleanup_error:
            assert result["ambiguous_orphan"] == {
                "channel_id": "CCOMBINED",
                "message_ts": "REPLY.TS",
            }
        else:
            assert "ambiguous_orphan" not in result
        assert all(p.slack_details_ts is None for p in practices)
        assert mock_db.session.rollback.call_count == (
            2 if cleanup_error else 1
        )
        client.chat_delete.assert_called_once_with(
            channel="CCOMBINED", ts="REPLY.TS"
        )

    def test_existing_ts_calls_chat_update(self, app_context):
        """When any practice in the group has slack_details_ts, chat_update is used."""
        from app.slack.practices.announcements import _upsert_combined_details_reply

        client = MagicMock()
        practices = _make_group_practices(2, existing_details_ts="OLD.TS")

        with patch("app.practices.service.convert_practice_to_info",
                   return_value=_make_practice_info()), \
             patch("app.slack.practices.announcements.build_practice_details_blocks",
                   return_value=self._blocks()), \
             patch("app.slack.practices.announcements.db") as mock_db:
            _upsert_combined_details_reply(client, practices)

        client.chat_update.assert_called_once()
        kw = client.chat_update.call_args[1]
        assert kw["ts"] == "OLD.TS"
        client.chat_postMessage.assert_not_called()
        mock_db.session.commit.assert_called_once()

    def test_empty_blocks_skips_slack_call(self, app_context):
        """When build_practice_details_blocks returns empty, no Slack call is made."""
        from app.slack.practices.announcements import _upsert_combined_details_reply

        client = MagicMock()
        practices = _make_group_practices(2)

        with patch("app.practices.service.convert_practice_to_info",
                   return_value=_make_practice_info()), \
             patch("app.slack.practices.announcements.build_practice_details_blocks",
                   return_value=[]), \
             patch("app.slack.practices.announcements.db"):
            _upsert_combined_details_reply(client, practices)

        client.chat_postMessage.assert_not_called()
        client.chat_update.assert_not_called()

    def test_existing_reply_is_deleted_when_details_become_empty(self, app_context):
        from app.slack.practices.announcements import _upsert_combined_details_reply

        client = MagicMock()
        practices = _make_group_practices(2, existing_details_ts="OLD.TS")

        with patch(
            "app.slack.practices.announcements.build_practice_details_blocks",
            return_value=[],
        ), patch("app.slack.practices.announcements.db") as mock_db:
            result = _upsert_combined_details_reply(client, practices)

        assert result == {"success": True, "deleted": True}
        client.chat_delete.assert_called_once_with(
            channel="CCOMBINED", ts="OLD.TS"
        )
        assert all(p.slack_details_ts is None for p in practices)
        mock_db.session.commit.assert_called_once()

    def test_missing_stale_combined_details_is_an_idempotent_delete(
        self, app_context
    ):
        from app.slack.practices.announcements import (
            _upsert_combined_details_reply,
        )

        client = MagicMock()
        client.chat_delete.side_effect = SlackApiError(
            "missing", {"error": "message_not_found"}
        )
        practices = _make_group_practices(2, existing_details_ts="OLD.TS")

        with patch(
            "app.slack.practices.announcements.build_practice_details_blocks",
            return_value=[],
        ), patch("app.slack.practices.announcements.db") as mock_db:
            result = _upsert_combined_details_reply(client, practices)

        assert result == {"success": True, "deleted": True}
        assert all(p.slack_details_ts is None for p in practices)
        mock_db.session.commit.assert_called_once_with()

    def test_delete_failure_retains_every_details_timestamp(self, app_context):
        from app.slack.practices.announcements import _upsert_combined_details_reply

        client = MagicMock()
        client.chat_delete.side_effect = RuntimeError("delete failed")
        practices = _make_group_practices(2, existing_details_ts="OLD.TS")

        with patch(
            "app.slack.practices.announcements.build_practice_details_blocks",
            return_value=[],
        ), patch("app.slack.practices.announcements.db") as mock_db:
            result = _upsert_combined_details_reply(client, practices)

        assert result["success"] is False
        assert all(p.slack_details_ts == "OLD.TS" for p in practices)
        mock_db.session.rollback.assert_called_once()

    def test_divergent_details_are_labelled_with_saved_session_reactions(
        self, app_context
    ):
        from app.slack.practices.announcements import _combined_details_payload

        practices = _make_group_practices(2)
        practices[0].date = datetime(2026, 7, 14, 18, 15)
        practices[0].slack_session_emoji = "six"
        practices[1].date = datetime(2026, 7, 15, 19, 15)
        practices[1].slack_session_emoji = "seven"
        first = [{
            "type": "header",
            "text": {"type": "plain_text", "text": "Practice Details"},
        }, {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "Parking A"},
        }]
        second = [{
            "type": "header",
            "text": {"type": "plain_text", "text": "Practice Details"},
        }, {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "Parking B"},
        }]

        with patch(
            "app.slack.practices.announcements.convert_practice_to_info",
            side_effect=lambda item: item,
        ), patch(
            "app.slack.practices.announcements.build_practice_details_blocks",
            side_effect=[first, second],
        ), patch(
            "app.slack.practices.announcements.build_practice_details_fallback_text",
            side_effect=["Details A", "Details B"],
        ):
            blocks, fallback = _combined_details_payload(practices)

        text = "\n".join(
            block.get("text", {}).get("text", "") for block in blocks
        )
        assert ":six: Tuesday at 6:15 PM" in text
        assert ":seven: Wednesday at 7:15 PM" in text
        assert "Parking A" in text and "Parking B" in text
        assert ":six: Details A" in fallback
        assert ":seven: Details B" in fallback

    def test_exception_is_swallowed(self, app_context):
        """Errors in _upsert_combined_details_reply must not propagate."""
        from app.slack.practices.announcements import _upsert_combined_details_reply

        client = MagicMock()
        client.chat_postMessage.side_effect = Exception("slack boom")
        practices = _make_group_practices(2)

        with patch("app.practices.service.convert_practice_to_info",
                   return_value=_make_practice_info()), \
             patch("app.slack.practices.announcements.build_practice_details_blocks",
                   return_value=self._blocks()), \
             patch("app.slack.practices.announcements.db"):
            # Must not raise
            _upsert_combined_details_reply(client, practices)


class TestPostCombinedLiftAnnouncementWiring:
    """post_combined_lift_announcement calls _upsert_combined_details_reply."""

    def test_combined_details_reply_called_after_post(self, app_context):
        """On initial combined-lift post, _upsert_combined_details_reply is invoked."""
        from datetime import datetime
        from app.slack.practices.announcements import post_combined_lift_announcement

        # Use real datetime objects so sorted() and strftime() work without stubs
        practices = _make_group_practices(2)
        practices[0].date = datetime(2026, 1, 21, 18, 0)  # Wednesday
        practices[1].date = datetime(2026, 1, 23, 18, 0)  # Friday

        with patch("app.slack.practices.announcements.get_slack_client") as mock_get_client, \
             patch("app.slack.practices.announcements._get_announcement_channel", return_value="CCOMBINED"), \
             patch("app.practices.service.convert_practice_to_info", return_value=_make_practice_info()), \
             patch("app.slack.practices.announcements.build_combined_lift_blocks", return_value=[]), \
             patch("app.slack.practices.announcements.build_combined_fallback_text", return_value="Combined Strength"), \
             patch("app.slack.practices.announcements.assign_combined_session_emojis", return_value={"success": True, "emojis": {100: "six", 101: "seven"}}), \
             patch("app.slack.practices.announcements._seed_combined_reactions"), \
             patch("app.slack.practices.announcements._upsert_combined_details_reply") as mock_upsert, \
             patch("app.slack.practices.announcements.db"):

            mock_client = MagicMock()
            mock_client.chat_postMessage.return_value = {"ts": "COMBINED.1234"}
            mock_get_client.return_value = mock_client

            result = post_combined_lift_announcement(practices)

        assert result.get("success") is True
        mock_upsert.assert_called_once()
        # The list passed should contain the sorted practices
        call_practices = mock_upsert.call_args[0][1]
        assert len(call_practices) == 2


class TestUpdateCombinedLiftPostWiring:
    """update_combined_lift_post calls _upsert_combined_details_reply."""

    def test_combined_details_reply_called_on_update(self, app_context):
        """When update_combined_lift_post runs, _upsert_combined_details_reply is called."""
        from datetime import datetime
        from app.slack.practices.announcements import update_combined_lift_post

        practice = _make_group_practices(1)[0]
        practice.date = datetime(2026, 1, 21, 18, 0)

        with patch("app.slack.practices.announcements.get_slack_client") as mock_get_client, \
             patch("app.slack.practices.announcements.get_announcement_siblings") as mock_siblings, \
             patch("app.practices.service.convert_practice_to_info", return_value=_make_practice_info()), \
             patch("app.slack.practices.announcements.build_combined_lift_blocks", return_value=[]), \
             patch("app.slack.practices.announcements.build_combined_fallback_text", return_value="Combined Strength"), \
             patch("app.slack.practices.announcements.assign_combined_session_emojis", return_value={"success": True, "emojis": {100: "six", 101: "seven"}}), \
             patch("app.slack.practices.announcements._reconcile_combined_plan_reactions"), \
             patch("app.slack.practices.announcements._upsert_combined_details_reply") as mock_upsert, \
             patch("app.slack.practices.announcements.db"):

            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            # Mock the DB query to return two practices sharing the ts
            sibling = _make_group_practices(1)[0]
            sibling.id = 101
            sibling.date = datetime(2026, 1, 23, 18, 0)
            all_practices = [practice, sibling]
            mock_siblings.return_value = all_practices

            update_combined_lift_post(practice)

        mock_upsert.assert_called_once()
        call_practices = mock_upsert.call_args[0][1]
        assert len(call_practices) == 2


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
