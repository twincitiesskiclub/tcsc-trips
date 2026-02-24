"""Tests for centralized refresh_practice_posts function."""

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


class FakePractice:
    """Minimal Practice stand-in for testing dispatch logic."""

    def __init__(self, **kwargs):
        self.id = kwargs.get('id', 1)
        self.slack_message_ts = kwargs.get('slack_message_ts')
        self.slack_channel_id = kwargs.get('slack_channel_id')
        self.slack_collab_message_ts = kwargs.get('slack_collab_message_ts')
        self.slack_coach_summary_ts = kwargs.get('slack_coach_summary_ts')
        self.slack_weekly_summary_ts = kwargs.get('slack_weekly_summary_ts')


class TestRefreshDispatch:
    """Test that refresh_practice_posts routes to the right sub-functions."""

    def test_skips_all_when_no_slack_fields(self):
        practice = FakePractice()
        results = refresh_practice_posts(practice)
        assert results['announcement']['skipped'] is True
        assert results['collab']['skipped'] is True
        assert results['coach_summary']['skipped'] is True
        assert results['weekly_summary']['skipped'] is True

    def test_edit_logs_skipped_when_no_actor(self):
        practice = FakePractice()
        results = refresh_practice_posts(practice, change_type='edit', actor_slack_id=None)
        assert 'edit_logs' not in results

    def test_edit_logs_skipped_for_rsvp(self):
        practice = FakePractice(slack_message_ts='123', slack_channel_id='C123')
        with patch('app.slack.practices.refresh._refresh_announcement', return_value={'success': True}):
            results = refresh_practice_posts(practice, change_type='rsvp', actor_slack_id='U123')
        assert 'edit_logs' not in results


class TestRefreshAnnouncement:
    """Test announcement update routing by change_type."""

    def test_skips_when_no_ts(self):
        practice = FakePractice()
        assert _refresh_announcement(practice, 'edit')['skipped'] is True

    @patch('app.slack.practices.announcements.update_practice_slack_post')
    def test_edit_calls_update_practice_slack_post(self, mock_update):
        mock_update.return_value = {'success': True}
        practice = FakePractice(slack_message_ts='123', slack_channel_id='C123')
        result = _refresh_announcement(practice, 'edit')
        mock_update.assert_called_once_with(practice)

    @patch('app.slack.practices.cancellations.update_practice_as_cancelled')
    def test_cancel_calls_update_as_cancelled(self, mock_cancel):
        mock_cancel.return_value = {'success': True}
        practice = FakePractice(slack_message_ts='123', slack_channel_id='C123')
        result = _refresh_announcement(practice, 'cancel')
        mock_cancel.assert_called_once_with(practice, 'Admin')

    @patch('app.slack.practices.rsvp.update_practice_rsvp_counts')
    def test_rsvp_calls_update_counts(self, mock_rsvp):
        mock_rsvp.return_value = {'success': True}
        practice = FakePractice(slack_message_ts='123', slack_channel_id='C123')
        result = _refresh_announcement(practice, 'rsvp')
        mock_rsvp.assert_called_once_with(practice)


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

    def test_collab_error_returns_error_dict(self):
        practice = FakePractice(slack_collab_message_ts='456')
        with patch('app.slack.practices.coach_review.update_collab_post', side_effect=Exception("boom")):
            result = _refresh_collab(practice, 'edit')
        assert result['success'] is False
        assert 'boom' in result['error']
