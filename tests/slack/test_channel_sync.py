"""Tests for channel sync helpers added in the redesign."""

from unittest.mock import patch, MagicMock

import pytest

from app.slack.channel_sync import (
    ChannelSyncResult,
    get_managed_channel_ids,
)


@pytest.fixture
def app():
    from app import create_app
    app = create_app()
    with app.app_context():
        yield app


class TestGetManagedChannelIds:
    """Test helper that collects all managed channel IDs across tiers."""

    def test_returns_union_of_all_tier_channels(self):
        config = {
            'channels': {
                'full_member': ['ch-a', 'ch-b', 'ch-c'],
                'multi_channel_guest': ['ch-a', 'ch-b'],
                'single_channel_guest': ['ch-d'],
            }
        }
        name_to_id = {
            'ch-a': 'CA',
            'ch-b': 'CB',
            'ch-c': 'CC',
            'ch-d': 'CD',
        }

        result = get_managed_channel_ids(config, name_to_id)

        assert result == {'CA', 'CB', 'CC', 'CD'}

    def test_skips_unknown_channels(self):
        config = {
            'channels': {
                'full_member': ['ch-a', 'ch-missing'],
                'multi_channel_guest': [],
                'single_channel_guest': [],
            }
        }
        name_to_id = {'ch-a': 'CA'}

        result = get_managed_channel_ids(config, name_to_id)

        assert result == {'CA'}


class TestPrivateChannelPreservationLogic:
    """Test the merge logic used inside sync_single_user for MCG transitions."""

    def test_merge_preserves_private_channels(self):
        managed_ids = {'C_ANN', 'C_CHAT', 'C_GEAR'}
        target_mcg_ids = {'C_ANN', 'C_CHAT', 'C_GEAR'}
        current_user_channels = {'C_ANN', 'C_CHAT', 'C_GEAR', 'C_BOOKCLUB', 'C_SOCCER'}

        private_to_preserve = current_user_channels - managed_ids
        merged = target_mcg_ids | private_to_preserve

        assert 'C_BOOKCLUB' in merged
        assert 'C_SOCCER' in merged
        assert len(merged) == 5

    def test_merge_with_no_private_channels(self):
        managed_ids = {'C_ANN', 'C_CHAT'}
        target_mcg_ids = {'C_ANN', 'C_CHAT'}
        current_user_channels = {'C_ANN', 'C_CHAT'}

        private_to_preserve = current_user_channels - managed_ids
        merged = target_mcg_ids | private_to_preserve

        assert merged == target_mcg_ids


class TestSyncSingleUserMCGTransition:
    """Exercise the MCG branch of sync_single_user with mocks."""

    @patch('app.slack.channel_sync.send_tier_transition_notification')
    @patch('app.slack.channel_sync.change_user_role')
    @patch('app.slack.channel_sync.get_user_channels')
    @patch('app.slack.channel_sync.needs_role_change', return_value=True)
    @patch('app.slack.channel_sync.User.get_by_email', return_value=None)
    @patch('app.slack.channel_sync.Season.get_current', return_value=None)
    def test_mcg_transition_merges_private_channels(
        self, mock_season, mock_user, mock_needs, mock_get_chans, mock_change_role, mock_notify, app
    ):
        from app.slack.channel_sync import sync_single_user, ChannelSyncResult

        # User is currently in 5 channels — 3 managed, 2 private
        mock_get_chans.return_value = {'C_ANN', 'C_CHAT', 'C_GEAR', 'C_BOOKCLUB', 'C_SOCCER'}

        slack_user = {
            'id': 'U_TEST',
            'profile': {'email': 'test@example.com'},
            'is_restricted': False,
            'is_ultra_restricted': False,
        }
        managed = {'C_ANN', 'C_CHAT', 'C_GEAR', 'C_SCG'}
        target_mcg = {'C_ANN', 'C_CHAT', 'C_GEAR'}
        result = ChannelSyncResult()

        sync_single_user(
            slack_user=slack_user,
            target_tier='multi_channel_guest',
            target_channel_ids=target_mcg,
            full_member_channel_ids=set(),
            managed_channel_ids=managed,
            channel_id_to_properties={},
            team_id='T_TEST',
            dry_run=True,
            result=result,
            notify_per_transition=False,
        )

        # change_user_role called with merged list (3 managed + 2 private)
        assert mock_change_role.called
        passed_channels = set(mock_change_role.call_args.kwargs['channel_ids'])
        assert passed_channels == {'C_ANN', 'C_CHAT', 'C_GEAR', 'C_BOOKCLUB', 'C_SOCCER'}
        # Notification NOT fired because notify_per_transition=False
        assert not mock_notify.called
        # Trace recorded
        assert any('PRESERVE_PRIVATE' in t for t in result.traces)
        assert result.role_changes == 1

    @patch('app.slack.channel_sync.send_tier_transition_notification')
    @patch('app.slack.channel_sync.change_user_role')
    @patch('app.slack.channel_sync.get_user_channels')
    @patch('app.slack.channel_sync.needs_role_change', return_value=True)
    @patch('app.slack.channel_sync.User.get_by_email', return_value=None)
    @patch('app.slack.channel_sync.Season.get_current', return_value=None)
    def test_mcg_transition_with_no_private_channels(
        self, mock_season, mock_user, mock_needs, mock_get_chans, mock_change_role, mock_notify, app
    ):
        from app.slack.channel_sync import sync_single_user, ChannelSyncResult

        # User only in managed channels — no private to preserve
        mock_get_chans.return_value = {'C_ANN', 'C_CHAT'}

        slack_user = {
            'id': 'U_TEST',
            'profile': {'email': 'test@example.com'},
            'is_restricted': False,
            'is_ultra_restricted': False,
        }
        managed = {'C_ANN', 'C_CHAT', 'C_GEAR'}
        target_mcg = {'C_ANN', 'C_CHAT'}
        result = ChannelSyncResult()

        sync_single_user(
            slack_user=slack_user,
            target_tier='multi_channel_guest',
            target_channel_ids=target_mcg,
            full_member_channel_ids=set(),
            managed_channel_ids=managed,
            channel_id_to_properties={},
            team_id='T_TEST',
            dry_run=True,
            result=result,
            notify_per_transition=False,
        )

        assert mock_change_role.called
        passed_channels = set(mock_change_role.call_args.kwargs['channel_ids'])
        assert passed_channels == {'C_ANN', 'C_CHAT'}
        assert not any('PRESERVE_PRIVATE' in t for t in result.traces)

    @patch('app.slack.channel_sync.send_tier_transition_notification')
    @patch('app.slack.channel_sync.change_user_role')
    @patch('app.slack.channel_sync.get_user_channels')
    @patch('app.slack.channel_sync.needs_role_change', return_value=True)
    @patch('app.slack.channel_sync.User.get_by_email', return_value=None)
    @patch('app.slack.channel_sync.Season.get_current', return_value=None)
    def test_mcg_transition_fires_notification_when_flag_on(
        self, mock_season, mock_user, mock_needs, mock_get_chans, mock_change_role, mock_notify, app
    ):
        from app.slack.channel_sync import sync_single_user, ChannelSyncResult

        mock_get_chans.return_value = set()
        slack_user = {
            'id': 'U_TEST',
            'profile': {'email': 'test@example.com'},
            'is_restricted': False,
            'is_ultra_restricted': False,
        }
        result = ChannelSyncResult()

        sync_single_user(
            slack_user=slack_user,
            target_tier='multi_channel_guest',
            target_channel_ids={'C_ANN'},
            full_member_channel_ids=set(),
            managed_channel_ids={'C_ANN'},
            channel_id_to_properties={},
            team_id='T_TEST',
            dry_run=True,
            result=result,
            notify_per_transition=True,
        )

        assert mock_notify.called
        assert mock_notify.call_args.kwargs['to_tier'] == 'multi_channel_guest'


# Channel IDs used across the stable-tier tests
C_WELCOME = 'C_WELCOME'
C_REACTIVATE = 'C_REACTIVATE'
C_CHAT = 'C_CHAT'
C_ALUMNI = 'C_ALUMNI'
C_BOOKCLUB = 'C_BOOKCLUB'


class TestSyncSingleUserStableTierChannelRepair:
    """SCG/MCG users whose role doesn't change still get missing channels added."""

    @patch('app.slack.channel_sync.add_user_to_channel', return_value=True)
    @patch('app.slack.channel_sync.change_user_role')
    @patch('app.slack.channel_sync.get_user_channels')
    @patch('app.slack.channel_sync.needs_role_change', return_value=False)
    @patch('app.slack.channel_sync.User.get_by_email', return_value=None)
    @patch('app.slack.channel_sync.Season.get_current', return_value=None)
    def test_scg_missing_target_channel_gets_added(
        self, mock_season, mock_user, mock_needs, mock_get_chans,
        mock_change_role, mock_add_channel, app
    ):
        """SCG user in welcome-only should be added to tcsc-reactivate-me."""
        from app.slack.channel_sync import sync_single_user, ChannelSyncResult

        # User is currently only in the workspace default channel
        mock_get_chans.return_value = {C_WELCOME}

        slack_user = {
            'id': 'U_SCG',
            'profile': {'email': 'claire@example.com'},
            'is_restricted': False,
            'is_ultra_restricted': True,  # SCG
        }
        result = ChannelSyncResult()

        sync_single_user(
            slack_user=slack_user,
            target_tier='single_channel_guest',
            target_channel_ids={C_REACTIVATE},
            full_member_channel_ids=set(),
            managed_channel_ids={C_REACTIVATE},
            channel_id_to_properties={
                C_REACTIVATE: {'name': 'tcsc-reactivate-me', 'is_public': False},
                C_WELCOME: {'name': 'welcome-to-tcsc', 'is_public': True},
            },
            team_id='T_TEST',
            dry_run=True,
            result=result,
            notify_per_transition=False,
        )

        # Should add tcsc-reactivate-me
        mock_add_channel.assert_called_once_with('U_SCG', C_REACTIVATE, 'claire@example.com', True)
        # Role change must NOT be called
        mock_change_role.assert_not_called()
        assert result.channel_adds == 1
        # No PRESERVE_PRIVATE trace (that's an MCG role-change concept)
        assert not any('PRESERVE_PRIVATE' in t for t in result.traces)

    @patch('app.slack.channel_sync.add_user_to_channel', return_value=True)
    @patch('app.slack.channel_sync.change_user_role')
    @patch('app.slack.channel_sync.get_user_channels')
    @patch('app.slack.channel_sync.needs_role_change', return_value=False)
    @patch('app.slack.channel_sync.User.get_by_email', return_value=None)
    @patch('app.slack.channel_sync.Season.get_current', return_value=None)
    def test_mcg_missing_managed_channel_gets_added(
        self, mock_season, mock_user, mock_needs, mock_get_chans,
        mock_change_role, mock_add_channel, app
    ):
        """MCG user missing one managed channel gets it added; private channel untouched."""
        from app.slack.channel_sync import sync_single_user, ChannelSyncResult

        # User is in two managed MCG channels + one private channel they joined manually
        mock_get_chans.return_value = {C_WELCOME, C_CHAT, C_BOOKCLUB}

        slack_user = {
            'id': 'U_MCG',
            'profile': {'email': 'mcg@example.com'},
            'is_restricted': True,   # MCG
            'is_ultra_restricted': False,
        }
        managed = {C_WELCOME, C_CHAT, C_ALUMNI}
        target_mcg = {C_WELCOME, C_CHAT, C_ALUMNI}
        result = ChannelSyncResult()

        sync_single_user(
            slack_user=slack_user,
            target_tier='multi_channel_guest',
            target_channel_ids=target_mcg,
            full_member_channel_ids=set(),
            managed_channel_ids=managed,
            channel_id_to_properties={
                C_WELCOME: {'name': 'welcome-to-tcsc', 'is_public': True},
                C_CHAT: {'name': 'general-chat', 'is_public': False},
                C_ALUMNI: {'name': 'alumni-corner', 'is_public': False},
                C_BOOKCLUB: {'name': 'book-club', 'is_public': False},
            },
            team_id='T_TEST',
            dry_run=True,
            result=result,
            notify_per_transition=False,
        )

        # Only C_ALUMNI should be added (the missing managed MCG channel)
        mock_add_channel.assert_called_once_with('U_MCG', C_ALUMNI, 'mcg@example.com', True)
        # Role change must NOT be called
        mock_change_role.assert_not_called()
        assert result.channel_adds == 1

    @patch('app.slack.channel_sync.add_user_to_channel', return_value=True)
    @patch('app.slack.channel_sync.change_user_role')
    @patch('app.slack.channel_sync.get_user_channels')
    @patch('app.slack.channel_sync.needs_role_change', return_value=False)
    @patch('app.slack.channel_sync.User.get_by_email', return_value=None)
    @patch('app.slack.channel_sync.Season.get_current', return_value=None)
    def test_scg_no_op_when_channels_already_correct(
        self, mock_season, mock_user, mock_needs, mock_get_chans,
        mock_change_role, mock_add_channel, app
    ):
        """SCG user already in the correct channels — no adds, no role change."""
        from app.slack.channel_sync import sync_single_user, ChannelSyncResult

        # User already has both expected channels
        mock_get_chans.return_value = {C_WELCOME, C_REACTIVATE}

        slack_user = {
            'id': 'U_SCG2',
            'profile': {'email': 'noop@example.com'},
            'is_restricted': False,
            'is_ultra_restricted': True,  # SCG
        }
        result = ChannelSyncResult()

        sync_single_user(
            slack_user=slack_user,
            target_tier='single_channel_guest',
            target_channel_ids={C_REACTIVATE},
            full_member_channel_ids=set(),
            managed_channel_ids={C_REACTIVATE},
            channel_id_to_properties={
                C_REACTIVATE: {'name': 'tcsc-reactivate-me', 'is_public': False},
                C_WELCOME: {'name': 'welcome-to-tcsc', 'is_public': True},
            },
            team_id='T_TEST',
            dry_run=True,
            result=result,
            notify_per_transition=False,
        )

        mock_add_channel.assert_not_called()
        mock_change_role.assert_not_called()
        assert result.channel_adds == 0
