"""Practice-specific Slack operations.

This package re-exports all public symbols from its sub-modules so that
existing imports like ``from app.slack.practices import post_practice_announcement``
continue to work without change.
"""

from app.slack.practices._config import (
    _config_cache,
    _load_config,
    reload_config,
    _get_announcement_channel,
    _get_escalation_channel,
    LOGGING_CHANNEL_ID,
    PRACTICES_CORE_CHANNEL_ID,
    COORD_CHANNEL_ID,
    COLLAB_CHANNEL_ID,
    KJ_SLACK_ID,
    ADMIN_SLACK_IDS,
    FALLBACK_COACH_IDS,
)
from app.slack.practices.announcements import (
    post_practice_announcement,
    post_combined_lift_announcement,
    update_practice_announcement,
    update_practice_post,
    is_combined_lift_practice,
    update_combined_lift_post,
    update_practice_slack_post,
)
from app.slack.practices.cancellations import (
    post_cancellation_proposal,
    update_cancellation_decision,
    post_cancellation_notice,
    update_practice_as_cancelled,
)
from app.slack.practices.leads import (
    send_lead_availability_request,
    send_workout_reminder,
    send_lead_checkin_dm,
    post_substitution_request,
    post_24h_lead_confirmation,
)
from app.slack.practices.coach_review import (
    post_48h_workout_reminder,
    post_daily_practice_recap,
    create_practice_log_thread,
    post_collab_review,
    update_collab_post,
    log_collab_edit,
    log_practice_edit,
    post_coach_weekly_summary,
    log_coach_summary_edit,
    get_practice_coach_ids,
    escalate_practice_review,
)
from app.slack.practices.rsvp import (
    post_thread_reply,
    update_going_list_thread,
    update_practice_rsvp_counts,
    log_rsvp_action,
)
from app.slack.practices.app_home import (
    publish_app_home,
)

__all__ = [
    # _config
    "_config_cache",
    "_load_config",
    "reload_config",
    "_get_announcement_channel",
    "_get_escalation_channel",
    "LOGGING_CHANNEL_ID",
    "PRACTICES_CORE_CHANNEL_ID",
    "COORD_CHANNEL_ID",
    "COLLAB_CHANNEL_ID",
    "KJ_SLACK_ID",
    "ADMIN_SLACK_IDS",
    "FALLBACK_COACH_IDS",
    # announcements
    "post_practice_announcement",
    "post_combined_lift_announcement",
    "update_practice_announcement",
    "update_practice_post",
    "is_combined_lift_practice",
    "update_combined_lift_post",
    "update_practice_slack_post",
    # cancellations
    "post_cancellation_proposal",
    "update_cancellation_decision",
    "post_cancellation_notice",
    "update_practice_as_cancelled",
    # leads
    "send_lead_availability_request",
    "send_workout_reminder",
    "send_lead_checkin_dm",
    "post_substitution_request",
    "post_24h_lead_confirmation",
    # coach_review
    "post_48h_workout_reminder",
    "post_daily_practice_recap",
    "create_practice_log_thread",
    "post_collab_review",
    "update_collab_post",
    "log_collab_edit",
    "log_practice_edit",
    "post_coach_weekly_summary",
    "log_coach_summary_edit",
    "get_practice_coach_ids",
    "escalate_practice_review",
    # rsvp
    "post_thread_reply",
    "update_going_list_thread",
    "update_practice_rsvp_counts",
    "log_rsvp_action",
    # app_home
    "publish_app_home",
]
