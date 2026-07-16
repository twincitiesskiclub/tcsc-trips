"""Tests for centralized refresh_practice_posts function."""

from contextlib import nullcontext
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest

from app.slack.practices.refresh import (
    refresh_practice_posts,
    _refresh_announcement,
    _refresh_collab,
    _refresh_coach_summary,
    _refresh_weekly_summary,
    _post_edit_logs,
)
from app.slack.practices import refresh as refreshmod
from app.slack.practices.rsvp import update_practice_rsvp_counts


class FakePractice:
    """Minimal Practice stand-in for testing dispatch logic."""

    def __init__(self, **kwargs):
        self.id = kwargs.get('id', 1)
        self.date = kwargs.get('date', datetime(2026, 7, 14, 18, 15))
        self.cancellation_reason = kwargs.get('cancellation_reason')
        self.plan_reactions = kwargs.get('plan_reactions', [])
        self.slack_session_emoji = kwargs.get('slack_session_emoji')
        self.slack_message_ts = kwargs.get('slack_message_ts')
        self.slack_channel_id = kwargs.get('slack_channel_id')
        self.slack_collab_message_ts = kwargs.get('slack_collab_message_ts')
        self.slack_coach_summary_ts = kwargs.get('slack_coach_summary_ts')
        self.slack_weekly_summary_ts = kwargs.get('slack_weekly_summary_ts')


class TestRefreshDispatch:
    """Test that refresh_practice_posts routes to the right sub-functions."""

    def test_skips_all_when_no_slack_fields(self):
        practice = FakePractice()
        with patch.object(
            refreshmod,
            "find_summary_post",
            return_value=None,
            create=True,
        ):
            results = refresh_practice_posts(practice)
        assert results['announcement']['skipped'] == 'absent'
        assert results['collab']['skipped'] == 'absent'
        assert results['coach_summary']['skipped'] == 'absent'
        assert results['weekly_summary']['skipped'] == 'absent'

    def test_edit_logs_skipped_when_no_actor(self):
        practice = FakePractice()
        results = refresh_practice_posts(practice, change_type='edit', actor_slack_id=None)
        assert 'edit_logs' not in results

    def test_edit_logs_skipped_for_rsvp(self):
        practice = FakePractice(slack_message_ts='123', slack_channel_id='C123')
        with patch('app.slack.practices.refresh._refresh_announcement', return_value={'success': True}):
            results = refresh_practice_posts(practice, change_type='rsvp', actor_slack_id='U123')
        assert 'edit_logs' not in results

    def test_weekly_rsvp_is_not_applicable_even_without_timestamp(self):
        practice = FakePractice()

        results = refresh_practice_posts(
            practice,
            change_type="rsvp",
            notify=False,
        )

        assert results["weekly_summary"] == {"skipped": "not_applicable"}

    def test_same_week_edit_does_not_refresh_previous_week(self):
        practice = FakePractice(date=datetime(2026, 7, 14, 18, 15))

        with patch(
            "app.slack.practices.refresh.PRACTICE_SURFACES", []
        ), patch.object(
            refreshmod,
            "refresh_registered_practice_summaries",
            create=True,
        ) as refresh_previous:
            results = refresh_practice_posts(
                practice,
                change_type="edit",
                notify=False,
                previous_date=datetime(2026, 7, 16, 18, 15),
            )

        refresh_previous.assert_not_called()
        assert "previous_coach_summary" not in results
        assert "previous_weekly_summary" not in results

    def test_cross_week_edit_maps_previous_results_without_rerunning_surfaces(
        self,
    ):
        practice = FakePractice(date=datetime(2026, 7, 14, 18, 15))
        previous_date = datetime(2026, 7, 7, 18, 15)
        previous_results = {
            "coach_summary": {"success": True},
            "weekly_summary": {"skipped": "absent"},
        }

        with patch(
            "app.slack.practices.refresh.PRACTICE_SURFACES", []
        ), patch.object(
            refreshmod,
            "refresh_registered_practice_summaries",
            return_value=previous_results,
            create=True,
        ) as refresh_previous:
            results = refresh_practice_posts(
                practice,
                change_type="edit",
                notify=False,
                previous_date=previous_date,
            )

        refresh_previous.assert_called_once_with(previous_date)
        assert results == {
            "previous_coach_summary": {"success": True},
            "previous_weekly_summary": {"skipped": "absent"},
        }


class TestRefreshAnnouncement:
    """Test announcement update routing by change_type."""

    def test_skips_when_no_ts(self):
        practice = FakePractice()
        assert _refresh_announcement(practice, 'edit') == {
            'success': True,
            'skipped': 'absent',
        }

    def test_timestamp_without_channel_is_an_error(self):
        practice = FakePractice(slack_message_ts='123')

        assert _refresh_announcement(practice, 'delete') == {
            'success': False,
            'error': 'Slack message has no channel',
        }

    @patch('app.slack.practices.announcements.update_practice_slack_post')
    def test_edit_calls_update_practice_slack_post(self, mock_update):
        mock_update.return_value = {'success': True}
        practice = FakePractice(slack_message_ts='123', slack_channel_id='C123')
        result = _refresh_announcement(practice, 'edit')
        mock_update.assert_called_once_with(
            practice,
            announcement_notice=None,
            previous_plan_reactions=None,
        )

    @patch('app.slack.practices.announcements.update_practice_slack_post')
    def test_edit_forwards_temporary_announcement_context(self, mock_update):
        mock_update.return_value = {'success': True}
        practice = FakePractice(slack_message_ts='123', slack_channel_id='C123')
        previous = [{"emoji": "old_choice", "label": "Old choice"}]

        result = _refresh_announcement(
            practice,
            'edit',
            announcement_notice="📍 Location updated, check Where below.",
            previous_plan_reactions=previous,
        )

        assert result == {'success': True}
        mock_update.assert_called_once_with(
            practice,
            announcement_notice="📍 Location updated, check Where below.",
            previous_plan_reactions=previous,
        )

    @patch('app.slack.practices.cancellations.update_practice_as_cancelled')
    def test_cancel_calls_update_as_cancelled(self, mock_cancel):
        mock_cancel.return_value = {'success': True}
        practice = FakePractice(slack_message_ts='123', slack_channel_id='C123')
        with patch(
            'app.slack.practices.announcements.is_combined_lift_practice',
            return_value=False,
        ):
            result = _refresh_announcement(practice, 'cancel')
        mock_cancel.assert_called_once_with(practice, 'Admin')

    @pytest.mark.parametrize(
        'notice_result',
        [
            {'success': True},
            {'success': False, 'error': 'thread failed'},
        ],
    )
    def test_cancel_combined_rebuilds_root_then_posts_best_effort_notice(
        self, notice_result,
    ):
        practice = FakePractice(
            slack_message_ts='123',
            slack_channel_id='C123',
            slack_session_emoji='six',
            cancellation_reason='Facility closed',
        )
        with patch(
            'app.slack.practices.announcements.is_combined_lift_practice',
            return_value=True,
        ), patch(
            'app.slack.practices.announcements.update_combined_lift_post',
            return_value={'success': True},
        ) as mock_rebuild, patch(
            'app.slack.practices.cancellations.post_combined_cancellation_thread_notice',
            return_value=notice_result,
        ) as mock_notice, patch(
            'app.slack.practices.cancellations.update_practice_as_cancelled',
        ) as mock_standalone:
            result = _refresh_announcement(practice, 'cancel')

        assert result == {'success': True}
        mock_rebuild.assert_called_once_with(practice)
        mock_notice.assert_called_once_with(practice)
        mock_standalone.assert_not_called()

    def test_failed_combined_rebuild_does_not_post_cancellation_notice(self):
        practice = FakePractice(
            slack_message_ts='123',
            slack_channel_id='C123',
            slack_session_emoji='six',
        )
        with patch(
            'app.slack.practices.announcements.is_combined_lift_practice',
            return_value=True,
        ), patch(
            'app.slack.practices.announcements.update_combined_lift_post',
            return_value={'success': False, 'error': 'root failed'},
        ), patch(
            'app.slack.practices.cancellations.post_combined_cancellation_thread_notice',
        ) as mock_notice:
            result = _refresh_announcement(practice, 'cancel')

        assert result == {'success': False, 'error': 'root failed'}
        mock_notice.assert_not_called()

    def test_delete_routes_through_safe_announcement_removal(self):
        practice = FakePractice(slack_message_ts='123', slack_channel_id='C123')
        with patch(
            'app.slack.practices.announcements.remove_practice_from_announcement',
            return_value={'success': True},
            create=True,
        ) as mock_remove, patch(
            'app.slack.client.get_slack_client',
        ) as mock_client:
            result = _refresh_announcement(practice, 'delete')

        assert result == {'success': True}
        mock_remove.assert_called_once_with(practice)
        mock_client.assert_not_called()

    @patch('app.slack.practices.rsvp.update_practice_rsvp_counts')
    def test_rsvp_calls_update_counts(self, mock_rsvp):
        mock_rsvp.return_value = {'success': True}
        practice = FakePractice(slack_message_ts='123', slack_channel_id='C123')
        result = _refresh_announcement(practice, 'rsvp')
        mock_rsvp.assert_called_once_with(practice)


class TestLegacyRsvpCountRefresh:
    def _practice(self):
        return SimpleNamespace(
            id=42,
            date=datetime(2026, 7, 14, 18, 15),
            slack_channel_id="C123",
            slack_message_ts="1710000000.000100",
        )

    def _rsvp_model(self, count=3):
        model = MagicMock()
        model.query.filter_by.return_value.count.return_value = count
        return model

    def test_modern_root_without_legacy_count_block_skips_chat_update(self):
        client = MagicMock()
        client.conversations_history.return_value = {
            "messages": [
                {
                    "text": "Modern accessible fallback",
                    "blocks": [
                        {
                            "type": "context",
                            "elements": [
                                {
                                    "type": "mrkdwn",
                                    "text": ":evergreen_tree: Plan choice",
                                }
                            ],
                        }
                    ],
                }
            ]
        }

        with patch(
            "app.slack.practices.rsvp.get_slack_client",
            return_value=client,
        ), patch(
            "app.practices.models.PracticeRSVP",
            self._rsvp_model(),
        ), patch(
            "app.slack.practices.rsvp.current_app",
            SimpleNamespace(logger=MagicMock()),
        ):
            result = update_practice_rsvp_counts(self._practice())

        assert result == {
            "success": True,
            "skipped": "no_legacy_count_block",
        }
        client.chat_update.assert_not_called()

    def test_legacy_count_update_preserves_complete_existing_fallback_text(self):
        client = MagicMock()
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": "Practice"}},
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": ":white_check_mark: *1 going* — _see thread for list_",
                    }
                ],
            },
        ]
        client.conversations_history.return_value = {
            "messages": [
                {
                    "text": "Complete accessible fallback",
                    "blocks": blocks,
                }
            ]
        }

        with patch(
            "app.slack.practices.rsvp.get_slack_client",
            return_value=client,
        ), patch(
            "app.practices.models.PracticeRSVP",
            self._rsvp_model(count=4),
        ), patch(
            "app.slack.practices.rsvp.current_app",
            SimpleNamespace(logger=MagicMock()),
        ):
            result = update_practice_rsvp_counts(self._practice())

        assert result == {"success": True}
        client.chat_update.assert_called_once_with(
            channel="C123",
            ts="1710000000.000100",
            blocks=[
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "Practice"},
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": ":white_check_mark: *4 going* — _see thread for list_",
                        }
                    ],
                },
            ],
            text="Complete accessible fallback",
        )


class TestRefreshCollab:
    """Test collab post update routing."""

    def test_skips_when_no_ts(self):
        practice = FakePractice()
        assert _refresh_collab(practice, 'edit')['skipped'] is True

    @patch('app.slack.practices.coach_review.update_collab_post')
    def test_calls_update_collab_post(self, mock_update):
        mock_update.return_value = {'success': True}
        practice = FakePractice(slack_collab_message_ts='456')
        result = _refresh_collab(practice, 'edit')
        mock_update.assert_called_once_with(practice)


class TestErrorIsolation:
    """Test that failures in one post type don't block others."""

    def test_announcement_error_returns_error_dict(self):
        practice = FakePractice(slack_message_ts='123', slack_channel_id='C123')
        with patch('app.slack.practices.announcements.update_practice_slack_post', side_effect=Exception("boom")):
            result = _refresh_announcement(practice, 'edit')
        assert result['success'] is False
        assert 'boom' in result['error']

    def test_failed_delete_announcement_blocks_later_surfaces(self):
        from app.slack.practices.refresh import PracticeSurface

        calls = []
        practice = FakePractice(slack_message_ts='123', slack_channel_id='C123')
        surfaces = [
            PracticeSurface(
                'announcement', 'slack_message_ts', ['delete'],
                lambda *_args, **_kwargs: calls.append('announcement') or {
                    'success': False, 'error': 'root failed'
                },
            ),
            PracticeSurface(
                'collab', 'slack_message_ts', ['delete'],
                lambda *_args, **_kwargs: calls.append('collab') or {
                    'success': True
                },
            ),
            PracticeSurface(
                'weekly_summary', 'slack_message_ts', ['delete'],
                lambda *_args, **_kwargs: calls.append('weekly') or {
                    'success': True
                },
            ),
        ]

        with patch('app.slack.practices.refresh.PRACTICE_SURFACES', surfaces):
            results = refresh_practice_posts(practice, change_type='delete')

        assert calls == ['announcement']
        assert results['collab'] == {'skipped': 'blocked_by_announcement'}
        assert results['weekly_summary'] == {
            'skipped': 'blocked_by_announcement'
        }

    def test_successful_delete_announcement_does_not_block_later_failures(self):
        from app.slack.practices.refresh import PracticeSurface

        calls = []
        practice = FakePractice(slack_message_ts='123', slack_channel_id='C123')
        surfaces = [
            PracticeSurface(
                'announcement', 'slack_message_ts', ['delete'],
                lambda *_args, **_kwargs: calls.append('announcement') or {
                    'success': True
                },
            ),
            PracticeSurface(
                'weekly_summary', 'slack_message_ts', ['delete'],
                lambda *_args, **_kwargs: calls.append('weekly') or {
                    'success': False, 'error': 'weekly failed'
                },
            ),
        ]

        with patch('app.slack.practices.refresh.PRACTICE_SURFACES', surfaces):
            results = refresh_practice_posts(practice, change_type='delete')

        assert calls == ['announcement', 'weekly']
        assert results['weekly_summary']['success'] is False

    def test_collab_error_returns_error_dict(self):
        practice = FakePractice(slack_collab_message_ts='456')
        with patch('app.slack.practices.coach_review.update_collab_post', side_effect=Exception("boom")):
            result = _refresh_collab(practice, 'edit')
        assert result['success'] is False
        assert 'boom' in result['error']


class TestSurfaceRegistry:
    """Test the declarative PracticeSurface registry."""

    def test_registry_covers_known_surfaces(self):
        from app.slack.practices.refresh import PRACTICE_SURFACES
        names = {s.name for s in PRACTICE_SURFACES}
        assert names == {
            "announcement", "collab", "coach_summary", "weekly_summary"
        }

    def test_surface_skips_when_ts_absent(self):
        from app.slack.practices.refresh import PracticeSurface
        calls = []
        s = PracticeSurface(
            "x", "slack_message_ts", ["edit"],
            lambda p, c: calls.append(c) or {"success": True},
        )
        practice = FakePractice()  # no slack_message_ts
        assert s.refresh(practice, "edit") == {"skipped": "absent"}
        assert calls == []

    def test_surface_skips_when_change_type_not_applicable(self):
        from app.slack.practices.refresh import PracticeSurface
        calls = []
        s = PracticeSurface(
            "x", "slack_message_ts", ["edit"],
            lambda p, c: calls.append(c) or {"success": True},
        )
        practice = FakePractice(slack_message_ts="1")
        assert s.refresh(practice, "rsvp") == {"skipped": "not_applicable"}
        assert calls == []

    def test_surface_runs_when_applicable_and_present(self):
        from app.slack.practices.refresh import PracticeSurface
        s = PracticeSurface(
            "x", "slack_message_ts", ["edit"],
            lambda p, c, **context: {
                "success": True,
                "ct": c,
                "context": context,
            },
        )
        practice = FakePractice(slack_message_ts="1")
        assert s.refresh(practice, "edit", notice="temporary") == {
            "success": True,
            "ct": "edit",
            "context": {"notice": "temporary"},
        }

    def test_surface_without_row_timestamp_gate_runs_when_applicable(self):
        calls = []
        surface = refreshmod.PracticeSurface(
            "registered_week",
            None,
            ["edit"],
            lambda practice, change_type: calls.append(
                (practice.id, change_type)
            ) or {"success": True},
        )
        practice = FakePractice(id=42)

        assert surface.refresh(practice, "edit") == {"success": True}
        assert calls == [(42, "edit")]


class TestRegisteredSummaryRefresh:
    def test_independent_helper_refreshes_only_the_two_week_surfaces(self):
        value = datetime(2026, 7, 13)

        with patch.object(
            refreshmod,
            "_refresh_coach_summary_for_week",
            return_value={"success": True},
            create=True,
        ) as refresh_coach, patch.object(
            refreshmod,
            "_refresh_weekly_summary_for_week",
            return_value={"skipped": "absent"},
            create=True,
        ) as refresh_weekly, patch.object(
            refreshmod,
            "_refresh_announcement",
        ) as refresh_announcement, patch.object(
            refreshmod,
            "_refresh_collab",
        ) as refresh_collab:
            result = refreshmod.refresh_registered_practice_summaries(
                value,
                exclude_practice_id=91,
            )

        assert result == {
            "coach_summary": {"success": True},
            "weekly_summary": {"skipped": "absent"},
        }
        refresh_coach.assert_called_once_with(
            value,
            exclude_practice_id=91,
        )
        refresh_weekly.assert_called_once_with(
            value,
            exclude_practice_id=91,
        )
        refresh_announcement.assert_not_called()
        refresh_collab.assert_not_called()


class TestCoachSummaryEditLogs:
    def test_edit_log_uses_destination_registry_identity(self):
        practice = FakePractice(
            slack_coach_summary_ts="stale-row-ts",
            date=datetime(2026, 7, 14, 18, 15),
        )
        record = SimpleNamespace(
            surface="coach_summary",
            channel_id="C-REGISTERED",
            message_ts="registered-ts",
        )

        with patch.object(
            refreshmod,
            "find_summary_post",
            return_value=record,
            create=True,
        ) as find_post, patch.object(
            refreshmod,
            "summary_post_channel",
            return_value="C-REGISTERED",
            create=True,
        ), patch(
            "app.slack.practices.coach_review.log_coach_summary_edit",
            return_value={"success": True},
        ) as log_coach:
            result = _post_edit_logs(practice, "U123")

        assert result == {"coach_summary_log": {"success": True}}
        find_post.assert_called_once_with(
            practice.date,
            refreshmod.COACH_SUMMARY,
        )
        log_coach.assert_called_once_with(
            practice,
            "U123",
            channel_id="C-REGISTERED",
            message_ts="registered-ts",
        )

    def test_edit_log_skips_stale_row_mirror_without_registry_record(self):
        practice = FakePractice(slack_coach_summary_ts="stale-row-ts")

        with patch.object(
            refreshmod,
            "find_summary_post",
            return_value=None,
            create=True,
        ), patch(
            "app.slack.practices.coach_review.log_coach_summary_edit",
        ) as log_coach:
            result = _post_edit_logs(practice, "U123")

        assert result == {}
        log_coach.assert_not_called()

    def test_log_function_prefers_explicit_registry_identity(self):
        from app.slack.practices import coach_review

        practice = FakePractice(slack_coach_summary_ts="stale-row-ts")
        client = MagicMock()

        with patch.object(
            coach_review,
            "get_slack_client",
            return_value=client,
        ), patch.object(
            coach_review,
            "current_app",
            SimpleNamespace(logger=MagicMock()),
        ):
            result = coach_review.log_coach_summary_edit(
                practice,
                "U123",
                channel_id="C-REGISTERED",
                message_ts="registered-ts",
            )

        assert result == {"success": True}
        client.chat_postMessage.assert_called_once_with(
            channel="C-REGISTERED",
            thread_ts="registered-ts",
            text=":pencil2: <@U123> updated *Tuesday, Jul 14* practice",
            unfurl_links=False,
            unfurl_media=False,
        )

    def test_log_function_retains_legacy_identity_fallback(self):
        from app.slack.practices import coach_review

        practice = FakePractice(slack_coach_summary_ts="legacy-row-ts")
        client = MagicMock()

        with patch.object(
            coach_review,
            "get_slack_client",
            return_value=client,
        ), patch.object(
            coach_review,
            "current_app",
            SimpleNamespace(logger=MagicMock()),
        ):
            result = coach_review.log_coach_summary_edit(practice, "U123")

        assert result == {"success": True}
        client.chat_postMessage.assert_called_once_with(
            channel=coach_review.COLLAB_CHANNEL_ID,
            thread_ts="legacy-row-ts",
            text=":pencil2: <@U123> updated *Tuesday, Jul 14* practice",
            unfurl_links=False,
            unfurl_media=False,
        )


class TestTemporaryAnnouncementNotice:
    def test_safety_note_posts_once_even_when_general_notifications_are_off(self):
        from app.slack.practices.refresh import PracticeSurface

        practice = FakePractice(
            slack_message_ts="123",
            slack_channel_id="C123",
        )
        notice = "🕒 Date or time updated, check the heading above."
        announcement = PracticeSurface(
            "announcement",
            "slack_message_ts",
            ["edit"],
            lambda _practice, _change_type, **_context: {"success": True},
        )

        with patch(
            "app.slack.practices.refresh.PRACTICE_SURFACES", [announcement]
        ), patch(
            "app.slack.practices.rsvp.post_thread_reply",
            return_value={"success": True, "message_ts": "456"},
        ) as mock_reply, patch(
            "app.slack.practices.refresh._post_edit_logs"
        ) as mock_logs:
            results = refresh_practice_posts(
                practice,
                change_type="edit",
                actor_slack_id=None,
                notify=False,
                announcement_notice=notice,
            )

        mock_reply.assert_called_once_with(
            practice, notice, user_mention=None
        )
        mock_logs.assert_not_called()
        assert results["announcement_change_note"]["success"] is True

    def test_safety_note_replaces_only_the_duplicate_announcement_edit_log(self):
        from app.slack.practices.refresh import PracticeSurface

        practice = FakePractice(
            slack_message_ts="123",
            slack_channel_id="C123",
        )
        notice = "📍 Location updated, check Where below."
        announcement = PracticeSurface(
            "announcement",
            "slack_message_ts",
            ["edit"],
            lambda _practice, _change_type, **_context: {"success": True},
        )

        with patch(
            "app.slack.practices.refresh.PRACTICE_SURFACES", [announcement]
        ), patch(
            "app.slack.practices.rsvp.post_thread_reply",
            return_value={"success": True, "message_ts": "456"},
        ), patch(
            "app.slack.practices.refresh._post_edit_logs",
            return_value={"coach_summary_log": {"success": True}},
        ) as mock_logs:
            refresh_practice_posts(
                practice,
                change_type="edit",
                actor_slack_id="U123",
                notify=True,
                announcement_notice=notice,
            )

        mock_logs.assert_called_once_with(
            practice, "U123", skip_announcement=True
        )

    def test_safety_note_exception_is_contained_and_edit_logs_continue(self):
        from app.slack.practices.refresh import PracticeSurface

        practice = FakePractice(
            slack_message_ts="123",
            slack_channel_id="C123",
        )
        announcement = PracticeSurface(
            "announcement",
            "slack_message_ts",
            ["edit"],
            lambda _practice, _change_type, **_context: {"success": True},
        )

        with patch(
            "app.slack.practices.refresh.PRACTICE_SURFACES", [announcement]
        ), patch(
            "app.slack.practices.rsvp.post_thread_reply",
            side_effect=RuntimeError("thread transport failed"),
        ), patch(
            "app.slack.practices.refresh._post_edit_logs",
            return_value={"announcement_log": {"success": True}},
        ) as mock_logs:
            results = refresh_practice_posts(
                practice,
                change_type="edit",
                actor_slack_id="U123",
                notify=True,
                announcement_notice="📍 Location updated, check Where below.",
            )

        assert results["announcement_change_note"] == {
            "success": False,
            "error": "thread transport failed",
        }
        assert results["edit_logs"] == {
            "announcement_log": {"success": True}
        }
        mock_logs.assert_called_once_with(
            practice, "U123", skip_announcement=False
        )

    @pytest.mark.parametrize(
        "invalid_result", [None, "unexpected", {}, {"success": "yes"}]
    )
    def test_invalid_safety_note_result_is_contained(
        self, invalid_result
    ):
        from app.slack.practices.refresh import PracticeSurface

        practice = FakePractice(
            slack_message_ts="123",
            slack_channel_id="C123",
        )
        announcement = PracticeSurface(
            "announcement",
            "slack_message_ts",
            ["edit"],
            lambda _practice, _change_type, **_context: {"success": True},
        )

        with patch(
            "app.slack.practices.refresh.PRACTICE_SURFACES", [announcement]
        ), patch(
            "app.slack.practices.rsvp.post_thread_reply",
            return_value=invalid_result,
        ):
            results = refresh_practice_posts(
                practice,
                change_type="edit",
                notify=False,
                announcement_notice="📍 Location updated, check Where below.",
            )

        assert results["announcement_change_note"]["success"] is False
        assert "invalid result" in results["announcement_change_note"][
            "error"
        ].lower()

    def test_full_slack_edit_passes_location_notice_and_previous_plan_snapshot(
        self,
    ):
        from app.slack.bolt_app import _handle_practice_edit_full_submission
        from app.practices.plan_reaction_editor import (
            build_plan_reaction_editor_state,
        )
        from app.slack.practice_reaction_editor import (
            encode_practice_reaction_metadata,
        )

        previous = [{"emoji": "old_choice", "label": "Old choice"}]
        submitted = [{"emoji": "new_choice", "label": "New choice"}]
        practice = MagicMock(
            id=42,
            date=datetime(2026, 7, 14, 18, 15),
            location_id=10,
            plan_reactions=previous,
            slack_message_ts=None,
        )
        state = build_plan_reaction_editor_state(
            practice_types=[],
            activities=[],
            saved_snapshot=submitted,
        ).state
        catalog_source = SimpleNamespace(
            id=1,
            name="Configured options",
            default_plan_reactions=submitted,
        )
        selected_sources = SimpleNamespace(
            practice_types=(),
            activities=(),
        )
        all_sources = SimpleNamespace(
            practice_types=(catalog_source,),
            activities=(),
        )
        ack = MagicMock()
        values = {
            "location_block": {
                "location_id": {"selected_option": {"value": "20"}}
            },
            "workout_block": {
                "workout_description": {"value": "6 x 3 minutes"}
            },
            "notes_block": {"logistics_notes": {"value": ""}},
            "activities_block": {
                "activity_ids": {"selected_options": []}
            },
            "types_block": {
                "type_ids": {"selected_options": []}
            },
            "practice_reaction_row_r0": {
                "practice_reaction_description": {"value": "New choice"}
            },
            "flags_block": {"practice_flags": {"selected_options": []}},
            "notify_block": {"notify_update": {"selected_options": []}},
        }

        with patch(
            "app.slack.bolt_app.get_app_context",
            return_value=nullcontext(),
        ), patch(
            "app.models.db.session.get", return_value=practice
        ), patch(
            "app.slack.bolt_app.load_selected_plan_reaction_sources",
            return_value=selected_sources,
        ), patch(
            "app.slack.bolt_app.load_all_plan_reaction_sources",
            return_value=all_sources,
        ), patch(
            "app.models.db.session.commit"
        ), patch(
            "app.slack.practices.refresh_practice_posts"
        ) as mock_refresh:
            _handle_practice_edit_full_submission(
                ack=ack,
                body={"user": {"id": "U123"}},
                view={
                    "callback_id": "practice_edit_full",
                    "private_metadata": encode_practice_reaction_metadata(
                        mode="edit",
                        context={"practice_id": 42},
                        state=state,
                    ),
                    "state": {"values": values},
                },
                logger=MagicMock(),
            )

        mock_refresh.assert_called_once_with(
            practice,
            change_type="edit",
            actor_slack_id="U123",
            notify=False,
            announcement_notice="📍 Location updated, check Where below.",
            previous_plan_reactions=previous,
        )
