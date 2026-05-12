"""Tests for admin API activity fetch.

The implementation makes two calls:
  1. admin.analytics.getAvailableDateRange — returns {start_date, end_date}
  2. admin.analytics.getMemberAnalytics — returns {member_activity: [...], num_found, next_cursor_mark}
Tests mock both via side_effect on make_admin_request.
"""

from datetime import datetime
from unittest.mock import patch

import pytest

from app import create_app


RANGE_OK = {
    'ok': True,
    'start_date': '2025-04-10',
    'end_date': '2026-05-10',
    'date_last_updated': 1778502662,
    'date_last_indexed': 1778502662,
}


@pytest.fixture
def app():
    """Create a test Flask application."""
    app = create_app()
    app.config['TESTING'] = True
    return app


class TestFetchUserActivity:
    """Test fetch_user_activity admin API function."""

    @patch('app.slack.admin_api.make_admin_request')
    def test_returns_user_id_to_activity_dict(self, mock_request, app):
        from app.slack.admin_api import fetch_user_activity

        mock_request.side_effect = [
            RANGE_OK,
            {
                'ok': True,
                'num_found': 2,
                'next_cursor_mark': '',
                'member_activity': [
                    {
                        'user_id': 'U123',
                        'date_last_active': 1714000000,
                        'days_active': 5,
                        'messages_posted': 3,
                    },
                    {
                        'user_id': 'U456',
                        'date_last_active': 1713000000,
                        'days_active': 0,
                        'messages_posted': 0,
                    },
                ],
            },
        ]

        with app.app_context():
            result = fetch_user_activity()

        assert 'U123' in result
        assert 'U456' in result
        assert isinstance(result['U123']['last_active'], datetime)
        assert result['U123']['days_active'] == 5
        assert result['U123']['messages_posted'] == 3
        assert isinstance(result['U456']['last_active'], datetime)
        assert result['U456']['days_active'] == 0
        assert result['U456']['messages_posted'] == 0

    @patch('app.slack.admin_api.make_admin_request')
    def test_skips_members_with_zero_or_missing_activity(self, mock_request, app):
        """Bots, never-onboarded users have date_last_active = 0 or missing."""
        from app.slack.admin_api import fetch_user_activity

        mock_request.side_effect = [
            RANGE_OK,
            {
                'ok': True,
                'num_found': 3,
                'next_cursor_mark': '',
                'member_activity': [
                    {'user_id': 'U123', 'date_last_active': 1714000000},
                    {'user_id': 'U789', 'date_last_active': 0},
                    {'user_id': 'U000'},  # field missing entirely
                ],
            },
        ]

        with app.app_context():
            result = fetch_user_activity()

        assert 'U123' in result
        assert 'U789' not in result
        assert 'U000' not in result

    @patch('app.slack.admin_api.make_admin_request')
    def test_handles_pagination(self, mock_request, app):
        from app.slack.admin_api import fetch_user_activity

        mock_request.side_effect = [
            RANGE_OK,
            {
                'ok': True,
                'num_found': 2,
                'next_cursor_mark': 'cursor-page-2',
                'member_activity': [{'user_id': 'U1', 'date_last_active': 1714000000}],
            },
            {
                'ok': True,
                'num_found': 2,
                'next_cursor_mark': '',
                'member_activity': [{'user_id': 'U2', 'date_last_active': 1714000000}],
            },
        ]

        with app.app_context():
            result = fetch_user_activity()

        assert len(result) == 2
        assert 'U1' in result
        assert 'U2' in result
        # 1 range call + 2 analytics calls
        assert mock_request.call_count == 3

    @patch('app.slack.admin_api.make_admin_request')
    def test_returns_empty_dict_on_range_failure(self, mock_request, app):
        from app.slack.admin_api import fetch_user_activity

        mock_request.side_effect = Exception("API error")

        with app.app_context():
            result = fetch_user_activity()

        assert result == {}

    @patch('app.slack.admin_api.make_admin_request')
    def test_returns_empty_dict_on_analytics_failure(self, mock_request, app):
        from app.slack.admin_api import fetch_user_activity

        mock_request.side_effect = [RANGE_OK, Exception("analytics failed")]

        with app.app_context():
            result = fetch_user_activity()

        assert result == {}
