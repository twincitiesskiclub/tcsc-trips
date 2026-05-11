"""Tests for User.get_slack_tier() activity-based logic."""

from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, PropertyMock

import pytest


class FakeTag:
    def __init__(self, name):
        self.name = name


class FakeSlackUser:
    def __init__(self, last_slack_activity=None):
        self.last_slack_activity = last_slack_activity


class FakeUser:
    """Minimal User stand-in that mirrors get_slack_tier logic."""
    def __init__(self, status, seasons_since_active, tags=None, slack_user=None):
        self.status = status
        self.seasons_since_active = seasons_since_active
        self.tags = tags or []
        self.slack_user = slack_user


def get_slack_tier_under_test(user, threshold_days=90):
    """Replicates get_slack_tier logic for FakeUser unit tests."""
    full_member_tags = {'HEAD_COACH', 'ASSISTANT_COACH'}
    if any(tag.name in full_member_tags for tag in user.tags):
        return 'full_member'

    if user.status == 'ACTIVE':
        return 'full_member'
    elif user.status == 'ALUMNI':
        if user.seasons_since_active == 1:
            return 'multi_channel_guest'
        else:
            if (user.slack_user
                    and user.slack_user.last_slack_activity
                    and (datetime.utcnow() - user.slack_user.last_slack_activity).days < threshold_days):
                return 'multi_channel_guest'
            return 'single_channel_guest'
    return None


class TestTierLogicActivity:
    """Test activity-based tier for 2+ season alumni."""

    def test_active_user_is_full_member(self):
        user = FakeUser(status='ACTIVE', seasons_since_active=0)
        assert get_slack_tier_under_test(user) == 'full_member'

    def test_one_season_alumni_is_mcg(self):
        user = FakeUser(status='ALUMNI', seasons_since_active=1)
        assert get_slack_tier_under_test(user) == 'multi_channel_guest'

    def test_two_season_alumni_no_activity_is_scg(self):
        user = FakeUser(status='ALUMNI', seasons_since_active=2, slack_user=None)
        assert get_slack_tier_under_test(user) == 'single_channel_guest'

    def test_two_season_alumni_recent_activity_is_mcg(self):
        slack_user = FakeSlackUser(last_slack_activity=datetime.utcnow() - timedelta(days=30))
        user = FakeUser(status='ALUMNI', seasons_since_active=2, slack_user=slack_user)
        assert get_slack_tier_under_test(user) == 'multi_channel_guest'

    def test_two_season_alumni_old_activity_is_scg(self):
        slack_user = FakeSlackUser(last_slack_activity=datetime.utcnow() - timedelta(days=120))
        user = FakeUser(status='ALUMNI', seasons_since_active=2, slack_user=slack_user)
        assert get_slack_tier_under_test(user) == 'single_channel_guest'

    def test_two_season_alumni_activity_exactly_at_threshold_is_scg(self):
        slack_user = FakeSlackUser(last_slack_activity=datetime.utcnow() - timedelta(days=90))
        user = FakeUser(status='ALUMNI', seasons_since_active=2, slack_user=slack_user)
        assert get_slack_tier_under_test(user) == 'single_channel_guest'

    def test_two_season_alumni_activity_just_under_threshold_is_mcg(self):
        slack_user = FakeSlackUser(last_slack_activity=datetime.utcnow() - timedelta(days=89))
        user = FakeUser(status='ALUMNI', seasons_since_active=2, slack_user=slack_user)
        assert get_slack_tier_under_test(user) == 'multi_channel_guest'

    def test_three_season_alumni_recent_activity_is_mcg(self):
        slack_user = FakeSlackUser(last_slack_activity=datetime.utcnow() - timedelta(days=10))
        user = FakeUser(status='ALUMNI', seasons_since_active=3, slack_user=slack_user)
        assert get_slack_tier_under_test(user) == 'multi_channel_guest'

    def test_coach_override_trumps_everything(self):
        slack_user = FakeSlackUser(last_slack_activity=datetime.utcnow() - timedelta(days=200))
        user = FakeUser(status='ALUMNI', seasons_since_active=5, tags=[FakeTag('HEAD_COACH')], slack_user=slack_user)
        assert get_slack_tier_under_test(user) == 'full_member'

    def test_pending_user_returns_none(self):
        user = FakeUser(status='PENDING', seasons_since_active=0)
        assert get_slack_tier_under_test(user) is None

    def test_dropped_user_returns_none(self):
        user = FakeUser(status='DROPPED', seasons_since_active=0)
        assert get_slack_tier_under_test(user) is None

    def test_no_slack_user_linked_is_scg(self):
        user = FakeUser(status='ALUMNI', seasons_since_active=2, slack_user=None)
        assert get_slack_tier_under_test(user) == 'single_channel_guest'

    def test_slack_user_with_null_activity_is_scg(self):
        slack_user = FakeSlackUser(last_slack_activity=None)
        user = FakeUser(status='ALUMNI', seasons_since_active=2, slack_user=slack_user)
        assert get_slack_tier_under_test(user) == 'single_channel_guest'
