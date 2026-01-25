"""Shared configuration, constants, and channel helpers for practice Slack operations."""

import os
import yaml
from typing import Optional
from flask import current_app

from app.slack.client import get_channel_id_by_name

# Module-level config cache (loaded once per process)
_config_cache = None


def _load_config() -> dict:
    """Load Skipper configuration from YAML (cached after first load)."""
    global _config_cache
    if _config_cache is None:
        config_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'config', 'skipper.yaml')
        with open(config_path, 'r') as f:
            _config_cache = yaml.safe_load(f)
    return _config_cache


def reload_config():
    """Force reload of config from disk (useful for testing or config changes)."""
    global _config_cache
    _config_cache = None
    return _load_config()


def _get_announcement_channel() -> Optional[str]:
    """Get announcement channel ID from config."""
    try:
        config = _load_config()
        channel_name = config.get('escalation', {}).get('announcement_channel', '#practices')
        # Remove # prefix if present
        channel_name = channel_name.lstrip('#')
        return get_channel_id_by_name(channel_name)
    except Exception as e:
        current_app.logger.error(f"Error loading announcement channel from config: {e}")
        return None


def _get_escalation_channel() -> Optional[str]:
    """Get escalation channel ID from config."""
    try:
        config = _load_config()
        channel_name = config.get('escalation', {}).get('channel', '#practices-team')
        # Remove # prefix if present
        channel_name = channel_name.lstrip('#')
        return get_channel_id_by_name(channel_name)
    except Exception as e:
        current_app.logger.error(f"Error loading escalation channel from config: {e}")
        return None


# =============================================================================
# Channel IDs
# =============================================================================

LOGGING_CHANNEL_ID = "C0A5VEV86Q6"  # #tcsc-logging
PRACTICES_CORE_CHANNEL_ID = "C0535SLU7TR"  # #practices-core (daily recaps + proposals)
COORD_CHANNEL_ID = "C02J4DGCFL2"  # #coord-practices-leads-assists (24h lead reminders)
COLLAB_CHANNEL_ID = "C04AUHEDBSR"  # #collab-coaches-practices

# KJ's Slack ID for 48h check tagging
KJ_SLACK_ID = "U02K45N1JEV"

# Admins to escalate to if practice not approved
ADMIN_SLACK_IDS = [
    "U02JP5QNQFS",  # @augie
    "U02K5TKMQH3",  # @simon
    "U02J6R6CZS7",  # @rob
]

# Fallback coaches if no coach assigned to practice
FALLBACK_COACH_IDS = [
    "U02K45N1JEV",  # @kj
    "U02JKQB04S8",  # @greg
]
