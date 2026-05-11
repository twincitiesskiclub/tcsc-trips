"""Tests for tier transition notifications."""

from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def app():
    from app import create_app
    app = create_app()
    with app.app_context():
        yield app


class TestSendTierTransitionNotification:

    @patch('app.notifications.slack.requests.post')
    @patch('app.notifications.slack.os.environ.get', return_value='https://hooks.slack.com/test')
    def test_sends_demotion_notification(self, mock_env, mock_post, app):
        from app.notifications.slack import send_tier_transition_notification

        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()

        result = send_tier_transition_notification(
            name='Jane Doe',
            email='jane@example.com',
            from_tier='multi_channel_guest',
            to_tier='single_channel_guest',
            reason='inactive 90+ days',
        )

        assert result is True
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        assert 'Jane Doe' in payload['text']
        assert 'jane@example.com' in payload['text']
        assert 'MCG → SCG' in payload['text']
        assert 'inactive 90+ days' in payload['text']

    @patch('app.notifications.slack.requests.post')
    @patch('app.notifications.slack.os.environ.get', return_value='https://hooks.slack.com/test')
    def test_sends_reactivation_notification(self, mock_env, mock_post, app):
        from app.notifications.slack import send_tier_transition_notification

        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()

        result = send_tier_transition_notification(
            name='Jane Doe',
            email='jane@example.com',
            from_tier='single_channel_guest',
            to_tier='multi_channel_guest',
            reason='self-service reactivation',
        )

        assert result is True
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        assert 'SCG → MCG' in payload['text']
        assert 'self-service reactivation' in payload['text']

    @patch('app.notifications.slack.os.environ.get', return_value=None)
    def test_returns_false_when_no_webhook(self, mock_env, app):
        from app.notifications.slack import send_tier_transition_notification

        result = send_tier_transition_notification(
            name='Jane Doe',
            email='jane@example.com',
            from_tier='full_member',
            to_tier='multi_channel_guest',
            reason='1 season not registered',
        )

        assert result is False


class TestSendSyncSummaryNotification:

    @patch('app.notifications.slack.requests.post')
    @patch('app.notifications.slack.os.environ.get', return_value='https://hooks.slack.com/test')
    def test_summary_includes_counts(self, mock_env, mock_post, app):
        from app.notifications.slack import send_sync_summary_notification

        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()

        result_obj = MagicMock()
        result_obj.role_changes = 12
        result_obj.channel_adds = 47
        result_obj.channel_removals = 8
        result_obj.invites_sent = 3
        result_obj.errors = []

        ok = send_sync_summary_notification(result_obj, dry_run=False)

        assert ok is True
        payload = mock_post.call_args[1]['json']
        assert 'Channel sync complete' in payload['text']
        assert '12' in payload['text']
        assert '47' in payload['text']
        assert '8' in payload['text']
        assert '3' in payload['text']
        assert 'live' in payload['text']

    @patch('app.notifications.slack.requests.post')
    @patch('app.notifications.slack.os.environ.get', return_value='https://hooks.slack.com/test')
    def test_summary_labels_dry_run(self, mock_env, mock_post, app):
        from app.notifications.slack import send_sync_summary_notification

        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()

        result_obj = MagicMock()
        result_obj.role_changes = 0
        result_obj.channel_adds = 0
        result_obj.channel_removals = 0
        result_obj.invites_sent = 0
        result_obj.errors = []

        send_sync_summary_notification(result_obj, dry_run=True)
        payload = mock_post.call_args[1]['json']
        assert 'DRY RUN' in payload['text']

    @patch('app.notifications.slack.os.environ.get', return_value=None)
    def test_summary_returns_false_when_no_webhook(self, mock_env, app):
        from app.notifications.slack import send_sync_summary_notification

        result_obj = MagicMock()
        result_obj.role_changes = 0
        result_obj.channel_adds = 0
        result_obj.channel_removals = 0
        result_obj.invites_sent = 0
        result_obj.errors = []

        assert send_sync_summary_notification(result_obj, dry_run=False) is False
