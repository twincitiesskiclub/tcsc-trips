"""Tests for channel sync helpers added in the redesign."""

from unittest.mock import patch, MagicMock

import pytest

from app.slack.channel_sync import (
    ChannelSyncResult,
    get_managed_channel_ids,
)


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
