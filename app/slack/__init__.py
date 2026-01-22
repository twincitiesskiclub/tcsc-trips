"""Slack API integration module.

Includes:
- bolt_app: Slack Bolt app for handling all interactions (events, commands, modals)
- client: WebClient wrappers for bot and user tokens
- sync: User profile synchronization (bi-directional)
- channel_sync: Automated channel membership management
- admin_api: Undocumented admin APIs for role changes
- practices: Practice-specific Slack operations
- blocks: Block Kit builders for practice messages
- commands: Slash command handlers (/tcsc)
- modals: Modal view builders for interactions

The Bolt app is used via Flask routes in app/routes/slack_interactivity.py.
It provides automatic signature verification and cleaner handler patterns.
"""

from app.slack.client import (
    get_slack_client,
    get_slack_user_client,
    send_direct_message,
    get_channel_id_by_name
)

from app.slack.practices import (
    post_practice_announcement,
    post_cancellation_proposal,
    update_cancellation_decision,
    post_cancellation_notice,
    update_practice_as_cancelled,
    send_lead_availability_request,
    update_practice_announcement
)

from app.slack.commands import handle_tcsc_command

__all__ = [
    'get_slack_client',
    'get_slack_user_client',
    'send_direct_message',
    'get_channel_id_by_name',
    'post_practice_announcement',
    'post_cancellation_proposal',
    'update_cancellation_decision',
    'post_cancellation_notice',
    'update_practice_as_cancelled',
    'send_lead_availability_request',
    'update_practice_announcement',
    'handle_tcsc_command'
]
