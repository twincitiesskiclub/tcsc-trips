"""Slack Block Kit builders for practice-related messages.

This package re-exports all public symbols from its sub-modules so that
existing imports like ``from app.slack.blocks import build_practice_announcement_blocks``
continue to work without change.
"""

from app.slack.blocks.announcements import (
    build_practice_announcement_blocks,
    build_combined_lift_blocks,
    _get_day_suffix,
)
from app.slack.blocks.cancellations import (
    build_cancellation_proposal_blocks,
    build_cancellation_decision_update,
    build_practice_cancelled_notice,
)
from app.slack.blocks.leads import (
    build_lead_confirmation_blocks,
    build_substitution_request_blocks,
)
from app.slack.blocks.coach_review import (
    _practice_needs_attention,
    build_coach_weekly_summary_blocks,
    build_collab_practice_blocks,
)
from app.slack.blocks.rsvp import (
    build_rsvp_buttons,
    build_rsvp_summary_context,
)
from app.slack.blocks.summary import (
    build_weekly_summary_blocks,
)
from app.slack.blocks.app_home import (
    build_app_home_blocks,
    _build_practice_card,
)
from app.slack.blocks.recap import (
    build_daily_practice_recap_blocks,
)
from app.slack.blocks.dispatch import (
    build_dispatch_submission_section,
)

__all__ = [
    # announcements
    "build_practice_announcement_blocks",
    "build_combined_lift_blocks",
    "_get_day_suffix",
    # cancellations
    "build_cancellation_proposal_blocks",
    "build_cancellation_decision_update",
    "build_practice_cancelled_notice",
    # leads
    "build_lead_confirmation_blocks",
    "build_substitution_request_blocks",
    # coach_review
    "_practice_needs_attention",
    "build_coach_weekly_summary_blocks",
    "build_collab_practice_blocks",
    # rsvp
    "build_rsvp_buttons",
    "build_rsvp_summary_context",
    # summary
    "build_weekly_summary_blocks",
    # app_home
    "build_app_home_blocks",
    "_build_practice_card",
    # recap
    "build_daily_practice_recap_blocks",
    # dispatch
    "build_dispatch_submission_section",
]
