"""Tests for User.get_slack_tier() activity-based logic."""

from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, PropertyMock

import pytest
import uuid


class FakeTag:
    def __init__(self, name):
        self.name = name


class FakeSlackUser:
    def __init__(self, last_slack_activity=None, slack_days_active=None, slack_messages_posted=None):
        self.last_slack_activity = last_slack_activity
        self.slack_days_active = slack_days_active
        self.slack_messages_posted = slack_messages_posted


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
            su = user.slack_user
            if (su and su.last_slack_activity
                    and (datetime.utcnow() - su.last_slack_activity).days < threshold_days):
                messages = su.slack_messages_posted or 0
                days_active = su.slack_days_active or 0
                if messages >= 1 or days_active >= 3:
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

    def test_two_season_alumni_recent_activity_with_messages_is_mcg(self):
        slack_user = FakeSlackUser(
            last_slack_activity=datetime.utcnow() - timedelta(days=30),
            slack_messages_posted=1,
            slack_days_active=1,
        )
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

    def test_two_season_alumni_activity_just_under_threshold_with_engagement_is_mcg(self):
        slack_user = FakeSlackUser(
            last_slack_activity=datetime.utcnow() - timedelta(days=89),
            slack_messages_posted=1,
            slack_days_active=1,
        )
        user = FakeUser(status='ALUMNI', seasons_since_active=2, slack_user=slack_user)
        assert get_slack_tier_under_test(user) == 'multi_channel_guest'

    def test_three_season_alumni_recent_activity_with_engagement_is_mcg(self):
        slack_user = FakeSlackUser(
            last_slack_activity=datetime.utcnow() - timedelta(days=10),
            slack_messages_posted=1,
            slack_days_active=1,
        )
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

    def test_two_season_alumni_recent_no_engagement_is_scg(self):
        """The bug case: date_last_active bumped by admin call, but no real activity."""
        slack_user = FakeSlackUser(
            last_slack_activity=datetime.utcnow() - timedelta(days=1),
            slack_messages_posted=0,
            slack_days_active=1,
        )
        user = FakeUser(status='ALUMNI', seasons_since_active=2, slack_user=slack_user)
        assert get_slack_tier_under_test(user) == 'single_channel_guest'

    def test_two_season_alumni_with_one_message_is_mcg(self):
        slack_user = FakeSlackUser(
            last_slack_activity=datetime.utcnow() - timedelta(days=10),
            slack_messages_posted=1,
            slack_days_active=1,
        )
        user = FakeUser(status='ALUMNI', seasons_since_active=2, slack_user=slack_user)
        assert get_slack_tier_under_test(user) == 'multi_channel_guest'

    def test_two_season_alumni_with_three_days_active_is_mcg(self):
        slack_user = FakeSlackUser(
            last_slack_activity=datetime.utcnow() - timedelta(days=10),
            slack_messages_posted=0,
            slack_days_active=3,
        )
        user = FakeUser(status='ALUMNI', seasons_since_active=2, slack_user=slack_user)
        assert get_slack_tier_under_test(user) == 'multi_channel_guest'

    def test_two_season_alumni_with_two_days_active_no_messages_is_scg(self):
        slack_user = FakeSlackUser(
            last_slack_activity=datetime.utcnow() - timedelta(days=10),
            slack_messages_posted=0,
            slack_days_active=2,
        )
        user = FakeUser(status='ALUMNI', seasons_since_active=2, slack_user=slack_user)
        assert get_slack_tier_under_test(user) == 'single_channel_guest'

    def test_two_season_alumni_old_activity_with_many_messages_is_scg(self):
        """90-day window is required even with real engagement signals."""
        slack_user = FakeSlackUser(
            last_slack_activity=datetime.utcnow() - timedelta(days=120),
            slack_messages_posted=10,
            slack_days_active=20,
        )
        user = FakeUser(status='ALUMNI', seasons_since_active=2, slack_user=slack_user)
        assert get_slack_tier_under_test(user) == 'single_channel_guest'


class TestUserGetSlackTierIntegration:
    """Integration tests against the real User model.

    These exercise the production User.get_slack_tier() method (not the
    replica) so they catch drift between unit-test logic and production code.
    """

    @pytest.fixture
    def app(self):
        from app import create_app
        app = create_app()
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = (
            'postgresql://tcsc:tcsc@localhost:5432/tcsc_trips'
        )
        return app

    @pytest.fixture
    def db_session(self, app):
        from app.models import db
        with app.app_context():
            db.create_all()
            yield db.session

    def _unique_email(self, prefix='test'):
        return f'{prefix}-{uuid.uuid4().hex[:8]}@example.com'

    def test_real_active_user_is_full_member(self, db_session, app):
        """ACTIVE user with seasons_since_active=0 -> full_member."""
        from app.models import User
        from app.constants import UserStatus

        user = User(
            email=self._unique_email('active'),
            first_name='Active',
            last_name='Test',
            status=UserStatus.ACTIVE,
            seasons_since_active=0,
        )
        db_session.add(user)
        db_session.commit()
        try:
            assert user.get_slack_tier() == 'full_member'
        finally:
            db_session.delete(user)
            db_session.commit()

    def test_real_alumni_one_season_is_mcg(self, db_session, app):
        """ALUMNI with seasons_since_active=1 -> multi_channel_guest."""
        from app.models import User
        from app.constants import UserStatus

        user = User(
            email=self._unique_email('alumni1'),
            first_name='Alumni',
            last_name='One',
            status=UserStatus.ALUMNI,
            seasons_since_active=1,
        )
        db_session.add(user)
        db_session.commit()
        try:
            assert user.get_slack_tier() == 'multi_channel_guest'
        finally:
            db_session.delete(user)
            db_session.commit()

    def test_real_alumni_two_seasons_recent_activity_is_mcg(self, db_session, app):
        """ALUMNI 2+ seasons with Slack activity 30 days ago -> multi_channel_guest."""
        from app.models import User, SlackUser
        from app.constants import UserStatus

        slack_user = SlackUser(
            slack_uid=f'U{uuid.uuid4().hex[:8].upper()}',
            last_slack_activity=datetime.utcnow() - timedelta(days=30),
            slack_messages_posted=1,
            slack_days_active=1,
        )
        db_session.add(slack_user)
        db_session.flush()  # get slack_user.id before commit

        user = User(
            email=self._unique_email('alumni2-recent'),
            first_name='Alumni',
            last_name='TwoRecent',
            status=UserStatus.ALUMNI,
            seasons_since_active=2,
            slack_user_id=slack_user.id,
        )
        db_session.add(user)
        db_session.commit()
        try:
            assert user.get_slack_tier() == 'multi_channel_guest'
        finally:
            db_session.delete(user)
            db_session.flush()
            db_session.delete(slack_user)
            db_session.commit()

    def test_real_alumni_two_seasons_stale_activity_is_scg(self, db_session, app):
        """ALUMNI 2+ seasons with Slack activity 120 days ago -> single_channel_guest."""
        from app.models import User, SlackUser
        from app.constants import UserStatus

        slack_user = SlackUser(
            slack_uid=f'U{uuid.uuid4().hex[:8].upper()}',
            last_slack_activity=datetime.utcnow() - timedelta(days=120),
        )
        db_session.add(slack_user)
        db_session.flush()

        user = User(
            email=self._unique_email('alumni2-stale'),
            first_name='Alumni',
            last_name='TwoStale',
            status=UserStatus.ALUMNI,
            seasons_since_active=2,
            slack_user_id=slack_user.id,
        )
        db_session.add(user)
        db_session.commit()
        try:
            assert user.get_slack_tier() == 'single_channel_guest'
        finally:
            db_session.delete(user)
            db_session.flush()
            db_session.delete(slack_user)
            db_session.commit()
