"""Practice-specific Slack operations."""

import os
import yaml
from datetime import datetime
from typing import Optional
from flask import current_app
from slack_sdk.errors import SlackApiError

from app.models import db

from app.slack.client import get_slack_client, send_direct_message, get_channel_id_by_name
from app.slack.blocks import (
    build_practice_announcement_blocks,
    build_combined_lift_blocks,
    build_cancellation_proposal_blocks,
    build_cancellation_decision_update,
    build_lead_confirmation_blocks,
    build_practice_cancelled_notice,
    build_substitution_request_blocks,
    build_app_home_blocks,
    build_rsvp_summary_context,
    build_collab_practice_blocks
)
from app.practices.models import Practice, CancellationRequest
from app.practices.interfaces import (
    PracticeInfo,
    CancellationProposal,
    WeatherConditions,
    TrailCondition,
    PracticeEvaluation
)

# Module-level config cache (loaded once per process)
_config_cache = None


def _load_config() -> dict:
    """Load Skipper configuration from YAML (cached after first load)."""
    global _config_cache
    if _config_cache is None:
        config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'skipper.yaml')
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


def post_practice_announcement(
    practice: Practice,
    weather: Optional[WeatherConditions] = None,
    trail_conditions: Optional[TrailCondition] = None,
    channel_override: Optional[str] = None
) -> dict:
    """Post practice announcement to #practices channel.

    Also immediately posts the going list thread reply so there's always
    a linkable thread for RSVPs.

    Args:
        practice: Practice SQLAlchemy model
        weather: Weather conditions (optional)
        trail_conditions: Trail conditions (optional)
        channel_override: Optional channel name to override default (e.g., 'general')

    Returns:
        dict with keys:
        - success: bool
        - message_ts: str (only if success=True)
        - error: str (only if success=False)
    """
    client = get_slack_client()

    # Determine channel - use override if provided
    if channel_override:
        channel_id = get_channel_id_by_name(channel_override.lstrip('#'))
    else:
        channel_id = _get_announcement_channel()

    if not channel_id:
        return {'success': False, 'error': 'Could not find announcement channel'}

    # Convert SQLAlchemy model to PracticeInfo dataclass
    from app.practices.service import convert_practice_to_info
    practice_info = convert_practice_to_info(practice)

    # Build blocks
    blocks = build_practice_announcement_blocks(practice_info, weather, trail_conditions)

    try:
        response = client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text=f"Practice on {practice.date.strftime('%A, %B %d')}",  # Fallback text
            unfurl_links=False,
            unfurl_media=False
        )

        message_ts = response.get('ts')
        current_app.logger.info(f"Posted practice announcement for practice #{practice.id} (ts: {message_ts})")

        # Save slack info to practice
        practice.slack_message_ts = message_ts
        practice.slack_channel_id = channel_id
        db.session.commit()

        # Add pre-seeded checkmark emoji for RSVP
        try:
            client.reactions_add(
                channel=channel_id,
                timestamp=message_ts,
                name="white_check_mark"
            )
        except Exception as e:
            current_app.logger.warning(f"Could not add checkmark reaction: {e}")

        # Create logging thread in #tcsc-logging
        try:
            create_practice_log_thread(practice)
        except Exception as e:
            current_app.logger.warning(f"Could not create practice log thread: {e}")

        return {
            'success': True,
            'message_ts': message_ts,
            'channel_id': channel_id
        }

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error posting practice announcement: {error_msg}")
        return {'success': False, 'error': error_msg}


def post_combined_lift_announcement(
    practices: list[Practice],
    channel_override: Optional[str] = None
) -> dict:
    """Post combined lift announcement for multiple lift practices.

    Used when 2-3 lift practices (e.g., Wed + Fri at Balance Fitness) should
    be announced together in a single message with per-day RSVP emojis.

    Args:
        practices: List of Practice SQLAlchemy models (2-3 practices)
        channel_override: Optional channel name to override default

    Returns:
        dict with keys:
        - success: bool
        - message_ts: str (only if success=True)
        - channel_id: str (only if success=True)
        - error: str (only if success=False)
    """
    if not practices:
        return {'success': False, 'error': 'No practices provided'}

    client = get_slack_client()

    # Determine channel
    if channel_override:
        channel_id = get_channel_id_by_name(channel_override.lstrip('#'))
    else:
        channel_id = _get_announcement_channel()

    if not channel_id:
        return {'success': False, 'error': 'Could not find announcement channel'}

    # Convert SQLAlchemy models to PracticeInfo dataclasses
    from app.practices.service import convert_practice_to_info
    practice_infos = [convert_practice_to_info(p) for p in practices]

    # Build combined blocks
    blocks = build_combined_lift_blocks(practice_infos)

    # Sort practices by date for consistent emoji assignment
    sorted_practices = sorted(practices, key=lambda p: p.date)

    # Build fallback text with all days
    days = [p.date.strftime('%A') for p in sorted_practices]
    days_str = " & ".join(days)

    try:
        response = client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text=f"TCSC Lift - {days_str}",
            unfurl_links=False,
            unfurl_media=False
        )

        message_ts = response.get('ts')
        practice_ids = [p.id for p in sorted_practices]
        current_app.logger.info(f"Posted combined lift announcement for practices {practice_ids} (ts: {message_ts})")

        # Save slack info to all practices
        for practice in sorted_practices:
            practice.slack_message_ts = message_ts
            practice.slack_channel_id = channel_id
        db.session.commit()

        # Add RSVP emojis for each day (different emoji per day)
        rsvp_emojis = ["white_check_mark", "ballot_box_with_check", "heavy_check_mark"]
        for i, practice in enumerate(sorted_practices):
            emoji = rsvp_emojis[i] if i < len(rsvp_emojis) else "white_check_mark"
            try:
                client.reactions_add(
                    channel=channel_id,
                    timestamp=message_ts,
                    name=emoji
                )
            except Exception as e:
                current_app.logger.warning(f"Could not add {emoji} reaction: {e}")

        return {
            'success': True,
            'message_ts': message_ts,
            'channel_id': channel_id
        }

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error posting combined lift announcement: {error_msg}")
        return {'success': False, 'error': error_msg}


def post_cancellation_proposal(
    proposal: CancellationRequest,
    evaluation: Optional[PracticeEvaluation] = None
) -> dict:
    """Post cancellation proposal to escalation channel (#practices-team).

    Args:
        proposal: CancellationRequest SQLAlchemy model
        evaluation: Practice evaluation data (optional)

    Returns:
        dict with keys:
        - success: bool
        - message_ts: str (only if success=True)
        - error: str (only if success=False)
    """
    client = get_slack_client()
    channel_id = _get_escalation_channel()

    if not channel_id:
        return {'success': False, 'error': 'Could not find escalation channel'}

    # Convert SQLAlchemy model to CancellationProposal dataclass
    from app.practices.service import convert_cancellation_to_proposal
    proposal_info = convert_cancellation_to_proposal(proposal)

    # Build blocks
    blocks = build_cancellation_proposal_blocks(proposal_info, evaluation)

    try:
        response = client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text=f"Practice cancellation proposal - {proposal.reason_type}"  # Fallback text
        )

        message_ts = response.get('ts')
        current_app.logger.info(f"Posted cancellation proposal #{proposal.id} (ts: {message_ts})")

        return {
            'success': True,
            'message_ts': message_ts,
            'channel_id': channel_id
        }

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error posting cancellation proposal: {error_msg}")
        return {'success': False, 'error': error_msg}


def update_cancellation_decision(
    proposal: CancellationRequest,
    approved: bool,
    decided_by_name: str
) -> dict:
    """Update cancellation proposal message with decision.

    Args:
        proposal: CancellationRequest with slack_message_ts set
        approved: Whether cancellation was approved
        decided_by_name: Name/mention of person who decided

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    if not proposal.slack_message_ts or not proposal.slack_channel_id:
        return {'success': False, 'error': 'No Slack message to update'}

    client = get_slack_client()

    # Convert to dataclass
    from app.practices.service import convert_cancellation_to_proposal
    proposal_info = convert_cancellation_to_proposal(proposal)

    # Build updated blocks
    blocks = build_cancellation_decision_update(proposal_info, approved, decided_by_name)

    try:
        client.chat_update(
            channel=proposal.slack_channel_id,
            ts=proposal.slack_message_ts,
            blocks=blocks,
            text=f"Decision: {'Cancelled' if approved else 'Continuing'}"
        )

        current_app.logger.info(f"Updated cancellation proposal #{proposal.id} with decision")
        return {'success': True}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error updating cancellation decision: {error_msg}")
        return {'success': False, 'error': error_msg}


def post_cancellation_notice(practice: Practice) -> dict:
    """Post cancellation notice to announcement channel.

    Args:
        practice: Cancelled practice

    Returns:
        dict with keys:
        - success: bool
        - message_ts: str (only if success=True)
        - error: str (only if success=False)
    """
    client = get_slack_client()
    channel_id = _get_announcement_channel()

    if not channel_id:
        return {'success': False, 'error': 'Could not find announcement channel'}

    # Convert to dataclass
    from app.practices.service import convert_practice_to_info
    practice_info = convert_practice_to_info(practice)

    # Build blocks
    blocks = build_practice_cancelled_notice(practice_info)

    try:
        response = client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text=f"Practice cancelled: {practice.date.strftime('%A, %B %d')}"
        )

        message_ts = response.get('ts')
        current_app.logger.info(f"Posted cancellation notice for practice #{practice.id}")

        # If there was an original announcement, update it too
        if practice.slack_message_ts and practice.slack_channel_id:
            try:
                client.chat_update(
                    channel=practice.slack_channel_id,
                    ts=practice.slack_message_ts,
                    blocks=blocks,
                    text=f"CANCELLED: Practice on {practice.date.strftime('%A, %B %d')}"
                )
            except SlackApiError as e:
                current_app.logger.warning(f"Could not update original announcement: {e}")

        return {
            'success': True,
            'message_ts': message_ts
        }

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error posting cancellation notice: {error_msg}")
        return {'success': False, 'error': error_msg}


def update_practice_as_cancelled(practice: Practice, decided_by_name: str) -> dict:
    """Update practice announcement to show cancelled status.

    Instead of posting a new cancellation notice, this:
    1. Updates the original practice post with cancelled styling
    2. Posts a thread reply with cancellation details

    Args:
        practice: Cancelled practice (with cancellation_reason set)
        decided_by_name: Slack mention of person who approved cancellation

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    # Must have original message to update
    if not practice.slack_message_ts or not practice.slack_channel_id:
        return {'success': False, 'error': 'No original practice post to update'}

    client = get_slack_client()

    # Build cancelled header block
    cancelled_header = {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": ":x: *CANCELLED* :x:"
        }
    }

    # Build info about the cancelled practice
    date_str = practice.date.strftime('%A, %B %-d at %-I:%M %p')
    location = practice.location.name if practice.location else "TBD"

    cancelled_info = f"~{date_str} at {location}~"
    if practice.cancellation_reason:
        cancelled_info += f"\n\n*Reason:* {practice.cancellation_reason}"

    cancelled_details = {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": cancelled_info
        }
    }

    blocks = [cancelled_header, {"type": "divider"}, cancelled_details]

    try:
        # Update the original practice post
        client.chat_update(
            channel=practice.slack_channel_id,
            ts=practice.slack_message_ts,
            blocks=blocks,
            text=f"CANCELLED: Practice on {practice.date.strftime('%A, %B %d')}"
        )

        # Post a thread reply with cancellation notice
        thread_text = f":x: This practice has been cancelled"
        if practice.cancellation_reason:
            thread_text += f": {practice.cancellation_reason}"
        thread_text += f"\n\nDecision by {decided_by_name}"

        client.chat_postMessage(
            channel=practice.slack_channel_id,
            thread_ts=practice.slack_message_ts,
            text=thread_text
        )

        current_app.logger.info(f"Updated practice #{practice.id} as cancelled")
        return {'success': True}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error updating practice as cancelled: {error_msg}")
        return {'success': False, 'error': error_msg}


def send_lead_availability_request(practice: Practice, user_slack_id: str) -> dict:
    """Send DM to practice lead requesting confirmation.

    Args:
        practice: Practice SQLAlchemy model
        user_slack_id: Slack user ID of the lead

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    # Convert to dataclass
    from app.practices.service import convert_practice_to_info
    practice_info = convert_practice_to_info(practice)

    # Build blocks
    blocks = build_lead_confirmation_blocks(practice_info)

    client = get_slack_client()

    try:
        response = client.chat_postMessage(
            channel=user_slack_id,
            blocks=blocks,
            text=f"Lead confirmation needed for practice on {practice.date.strftime('%A, %B %d')}"
        )

        current_app.logger.info(f"Sent lead confirmation request to {user_slack_id} for practice #{practice.id}")
        return {'success': True}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error sending lead confirmation request: {error_msg}")
        return {'success': False, 'error': error_msg}


def update_practice_announcement(
    practice: Practice,
    weather: Optional[WeatherConditions] = None,
    trail_conditions: Optional[TrailCondition] = None
) -> dict:
    """Update an existing practice announcement message.

    Args:
        practice: Practice SQLAlchemy model with slack_message_ts set
        weather: Updated weather conditions (optional)
        trail_conditions: Updated trail conditions (optional)

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    if not practice.slack_message_ts or not practice.slack_channel_id:
        return {'success': False, 'error': 'No Slack message to update'}

    client = get_slack_client()

    # Convert to dataclass
    from app.practices.service import convert_practice_to_info
    practice_info = convert_practice_to_info(practice)

    # Build updated blocks
    blocks = build_practice_announcement_blocks(practice_info, weather, trail_conditions)

    try:
        client.chat_update(
            channel=practice.slack_channel_id,
            ts=practice.slack_message_ts,
            blocks=blocks,
            text=f"Practice on {practice.date.strftime('%A, %B %d')}"
        )

        current_app.logger.info(f"Updated practice announcement for practice #{practice.id}")
        return {'success': True}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error updating practice announcement: {error_msg}")
        return {'success': False, 'error': error_msg}


def send_workout_reminder(practice: Practice, coach_slack_id: str) -> dict:
    """Send DM to coach requesting workout submission.

    Args:
        practice: Practice SQLAlchemy model
        coach_slack_id: Slack user ID of the coach

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    client = get_slack_client()

    # Build message
    date_str = practice.date.strftime('%A, %B %d at %I:%M %p')
    location = practice.location.name if practice.location else "TBD"

    message = (
        f":clipboard: Hi! You're scheduled to coach practice on *{date_str}* at *{location}*.\n\n"
        f"Could you submit the workout plan? Members like to see it in advance to plan their participation.\n\n"
        f"Thanks!"
    )

    try:
        response = client.chat_postMessage(
            channel=coach_slack_id,
            text=message
        )

        current_app.logger.info(f"Sent workout reminder to {coach_slack_id} for practice #{practice.id}")
        return {'success': True}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error sending workout reminder to {coach_slack_id}: {error_msg}")
        return {'success': False, 'error': error_msg}


def send_lead_checkin_dm(practice: Practice) -> dict:
    """Send group DM to practices directors + lead for lead check-in.

    Used by 4pm/10pm lead verification checks when a lead hasn't confirmed
    by reacting to the practice post.

    Args:
        practice: Practice SQLAlchemy model

    Returns:
        dict with keys:
        - success: bool
        - channel_id: str (only if success=True)
        - error: str (only if success=False)
    """
    from app.models import Tag
    from app.slack.client import open_conversation, get_slack_client
    from app.utils import format_datetime_central

    # Get practices directors by tag
    director_slack_ids = []
    practices_director_tag = Tag.query.filter_by(name='PRACTICES_DIRECTOR').first()
    if practices_director_tag:
        for user in practices_director_tag.users:
            if user.slack_user and user.slack_user.slack_uid:
                director_slack_ids.append(user.slack_user.slack_uid)

    # Fallback admin IDs if no directors are tagged
    ADMIN_FALLBACK_IDS = ["U02JP5QNQFS", "U02K5TKMQH3", "U02J6R6CZS7"]  # augie, simon, rob

    if not director_slack_ids:
        current_app.logger.warning("No PRACTICES_DIRECTOR users found, using admin fallback")
        director_slack_ids = ADMIN_FALLBACK_IDS

    # Get lead Slack IDs
    lead_slack_ids = []
    lead_mentions = []
    for lead in practice.leads:
        if lead.role == 'lead' and lead.user and lead.user.slack_user:
            lead_slack_ids.append(lead.user.slack_user.slack_uid)
            lead_mentions.append(f"<@{lead.user.slack_user.slack_uid}>")

    if not lead_slack_ids:
        current_app.logger.warning(f"No Slack IDs for leads of practice #{practice.id}")
        return {'success': False, 'error': 'No lead Slack IDs found'}

    # Combine all participants (deduplicate)
    all_participants = list(set(director_slack_ids + lead_slack_ids))

    if len(all_participants) < 2:
        return {'success': False, 'error': 'Not enough participants for group DM'}

    # Open the group conversation
    conv_result = open_conversation(all_participants)
    if not conv_result.get('success'):
        return conv_result

    channel_id = conv_result.get('channel_id')

    # Build the message
    time_str = format_datetime_central(practice.date, '%-I:%M %p')
    location = practice.location.name if practice.location else "TBD"
    practice_types = ", ".join([t.name for t in practice.practice_types]) if practice.practice_types else "Practice"
    lead_mention_text = " ".join(lead_mentions)
    director_mention_text = ", ".join(f"<@{uid}>" for uid in director_slack_ids)

    # Determine if evening or morning practice for message
    is_tonight = practice.date.date() == datetime.utcnow().date()
    time_label = "Tonight" if is_tonight else "Tomorrow"

    message = (
        f":clipboard: *Practice Check-In*\n\n"
        f"*{time_label}* — {time_str}\n"
        f"{practice_types} at {location}\n\n"
        f"---\n\n"
        f"Hey {lead_mention_text}! Just verifying you're good to lead {time_label.lower()}.\n\n"
        f":white_check_mark: React to the practice post or reply here to confirm!\n\n"
        f"If you need a sub, post to <#C02J4DGCFL2|coord-practices-leads-assists>.\n"
        f"If you need to go over anything, {director_mention_text} are here."
    )

    client = get_slack_client()

    try:
        client.chat_postMessage(
            channel=channel_id,
            text=message,
            unfurl_links=False,
            unfurl_media=False
        )

        current_app.logger.info(f"Sent lead check-in DM for practice #{practice.id} to {len(all_participants)} participants")
        return {'success': True, 'channel_id': channel_id}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error sending lead check-in DM: {error_msg}")
        return {'success': False, 'error': error_msg}


def post_substitution_request(
    practice: Practice,
    requester_slack_id: str,
    reason: str
) -> dict:
    """Post substitution request to escalation channel (#practices-team).

    Args:
        practice: Practice SQLAlchemy model
        requester_slack_id: Slack ID of the person requesting a sub
        reason: Reason for needing a substitute

    Returns:
        dict with keys:
        - success: bool
        - message_ts: str (only if success=True)
        - error: str (only if success=False)
    """
    client = get_slack_client()
    channel_id = _get_escalation_channel()

    if not channel_id:
        return {'success': False, 'error': 'Could not find escalation channel'}

    # Convert to dataclass
    from app.practices.service import convert_practice_to_info
    practice_info = convert_practice_to_info(practice)

    # Build blocks
    blocks = build_substitution_request_blocks(practice_info, requester_slack_id, reason)

    try:
        response = client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text=f"Substitute needed for practice on {practice.date.strftime('%A, %B %d')}"
        )

        message_ts = response.get('ts')
        current_app.logger.info(f"Posted substitution request for practice #{practice.id} (ts: {message_ts})")

        return {
            'success': True,
            'message_ts': message_ts,
            'channel_id': channel_id
        }

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error posting substitution request: {error_msg}")
        return {'success': False, 'error': error_msg}


def publish_app_home(user_slack_id: str) -> dict:
    """Publish the App Home view for a user.

    Args:
        user_slack_id: Slack user ID

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    from datetime import timedelta
    from app.practices.models import PracticeRSVP, PracticeLead
    from app.models import User

    client = get_slack_client()

    # Get upcoming practices (next 14 days)
    now = datetime.utcnow()
    end_date = now + timedelta(days=14)

    practices = Practice.query.filter(
        Practice.date >= now,
        Practice.date <= end_date
    ).order_by(Practice.date).all()

    # Convert to dataclass
    from app.practices.service import convert_practice_to_info
    practice_infos = [convert_practice_to_info(p) for p in practices]

    # Get user's RSVPs
    user_rsvps = {}
    user_lead_practices = []

    # Find user by slack ID
    user = User.query.join(User.slack_user).filter_by(slack_uid=user_slack_id).first()

    if user:
        # Get user's RSVPs for these practices
        practice_ids = [p.id for p in practices]
        rsvps = PracticeRSVP.query.filter(
            PracticeRSVP.practice_id.in_(practice_ids),
            PracticeRSVP.user_id == user.id
        ).all()

        for rsvp in rsvps:
            user_rsvps[rsvp.practice_id] = rsvp.status

        # Get user's lead assignments
        lead_assignments = PracticeLead.query.filter(
            PracticeLead.practice_id.in_(practice_ids),
            PracticeLead.user_id == user.id
        ).all()
        user_lead_practices = [la.practice_id for la in lead_assignments]

    # Build blocks
    blocks = build_app_home_blocks(practice_infos, user_rsvps, user_lead_practices)

    try:
        client.views_publish(
            user_id=user_slack_id,
            view={
                "type": "home",
                "blocks": blocks
            }
        )

        current_app.logger.info(f"Published app home for user {user_slack_id}")
        return {'success': True}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error publishing app home: {error_msg}")
        return {'success': False, 'error': error_msg}


def post_thread_reply(
    practice: Practice,
    message: str,
    user_mention: Optional[str] = None
) -> dict:
    """Post a threaded reply to a practice announcement.

    Args:
        practice: Practice SQLAlchemy model with slack_message_ts set
        message: Message text to post
        user_mention: Optional Slack user ID to mention

    Returns:
        dict with keys:
        - success: bool
        - message_ts: str (only if success=True)
        - error: str (only if success=False)
    """
    if not practice.slack_message_ts or not practice.slack_channel_id:
        return {'success': False, 'error': 'No Slack message to reply to'}

    client = get_slack_client()

    # Build message with optional mention
    text = message
    if user_mention:
        text = f"<@{user_mention}> {message}"

    try:
        response = client.chat_postMessage(
            channel=practice.slack_channel_id,
            thread_ts=practice.slack_message_ts,
            text=text
        )

        message_ts = response.get('ts')
        current_app.logger.info(f"Posted thread reply for practice #{practice.id}")

        return {
            'success': True,
            'message_ts': message_ts
        }

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error posting thread reply: {error_msg}")
        return {'success': False, 'error': error_msg}


def update_going_list_thread(practice: Practice) -> dict:
    """Update (or create) a thread reply showing who's going to practice.

    Posts a context-sized reply in the thread with mentions of all "going" RSVPs.

    Args:
        practice: Practice SQLAlchemy model with slack_message_ts set

    Returns:
        dict with keys:
        - success: bool
        - message_ts: str (only if success=True and new message created)
        - error: str (only if success=False)
    """
    if not practice.slack_message_ts or not practice.slack_channel_id:
        return {'success': False, 'error': 'No Slack message to update'}

    from app.practices.models import PracticeRSVP
    from app.models import User

    client = get_slack_client()

    # Get all "going" RSVPs with their Slack user IDs
    going_rsvps = PracticeRSVP.query.filter_by(
        practice_id=practice.id,
        status='going'
    ).all()

    # Build list of mentions
    mentions = []
    for rsvp in going_rsvps:
        if rsvp.slack_user_id:
            mentions.append(f"<@{rsvp.slack_user_id}>")
        elif rsvp.user:
            # Try to get Slack ID from linked user
            if rsvp.user.slack_user:
                mentions.append(f"<@{rsvp.user.slack_user.slack_uid}>")
            else:
                mentions.append(rsvp.user.first_name)

    # Build the going list text
    count = len(mentions)
    if count == 0:
        going_text = ":white_check_mark: *Going (0):* No one yet - be the first!"
    else:
        going_text = f":white_check_mark: *Going ({count}):* {', '.join(mentions)}"

    try:
        # Search thread for our existing going list message
        result = client.conversations_replies(
            channel=practice.slack_channel_id,
            ts=practice.slack_message_ts,
            limit=20
        )

        messages = result.get('messages', [])
        existing_ts = None

        # Find our going list message (starts with :white_check_mark: *Going)
        for msg in messages:
            text = msg.get('text', '')
            if text.startswith(':white_check_mark: *Going'):
                existing_ts = msg.get('ts')
                break

        if existing_ts:
            # Update existing message
            client.chat_update(
                channel=practice.slack_channel_id,
                ts=existing_ts,
                text=going_text
            )
            current_app.logger.info(f"Updated going list for practice #{practice.id}")
            return {'success': True}
        else:
            # Post new thread reply
            response = client.chat_postMessage(
                channel=practice.slack_channel_id,
                thread_ts=practice.slack_message_ts,
                text=going_text
            )
            message_ts = response.get('ts')
            current_app.logger.info(f"Posted going list for practice #{practice.id}")
            return {'success': True, 'message_ts': message_ts}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error updating going list: {error_msg}")
        return {'success': False, 'error': error_msg}


def update_practice_rsvp_counts(practice: Practice) -> dict:
    """Update practice announcement with current going count.

    Updates the last context block in the message with the current going count.

    Args:
        practice: Practice SQLAlchemy model with slack_message_ts set

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    if not practice.slack_message_ts or not practice.slack_channel_id:
        return {'success': False, 'error': 'No Slack message to update'}

    from app.practices.models import PracticeRSVP

    client = get_slack_client()

    # Get going count
    going_count = PracticeRSVP.query.filter_by(
        practice_id=practice.id,
        status='going'
    ).count()

    try:
        # Get the current message
        result = client.conversations_history(
            channel=practice.slack_channel_id,
            latest=practice.slack_message_ts,
            inclusive=True,
            limit=1
        )

        messages = result.get('messages', [])
        if not messages:
            return {'success': False, 'error': 'Original message not found'}

        current_blocks = messages[0].get('blocks', [])

        # Find and update the going count context block
        # It contains ":white_check_mark:" and mentions "going"
        # Search backwards from the end (it's near the end of the message)
        going_context_idx = None
        for i in range(len(current_blocks) - 1, -1, -1):
            block = current_blocks[i]
            if block.get('type') == 'context':
                elements = block.get('elements', [])
                for el in elements:
                    text = el.get('text', '')
                    if ':white_check_mark:' in text and 'going' in text:
                        going_context_idx = i
                        break
            if going_context_idx is not None:
                break

        if going_context_idx is not None:
            current_blocks[going_context_idx] = {
                "type": "context",
                "elements": [{
                    "type": "mrkdwn",
                    "text": f":white_check_mark: *{going_count} going* — _see thread for list_"
                }]
            }

        # Update message
        client.chat_update(
            channel=practice.slack_channel_id,
            ts=practice.slack_message_ts,
            blocks=current_blocks,
            text=f"Practice on {practice.date.strftime('%A, %B %d')}"
        )

        current_app.logger.info(f"Updated going count for practice #{practice.id}: {going_count}")
        return {'success': True}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error updating going count: {error_msg}")
        return {'success': False, 'error': error_msg}


# =============================================================================
# Channel IDs
# =============================================================================

LOGGING_CHANNEL_ID = "C0A5VEV86Q6"  # #tcsc-logging
PRACTICES_CORE_CHANNEL_ID = "C0535SLU7TR"  # #practices-core (daily recaps + proposals)
COORD_CHANNEL_ID = "C02J4DGCFL2"  # #coord-practices-leads-assists (24h lead reminders)


# KJ's Slack ID for 48h check tagging
KJ_SLACK_ID = "U02K45N1JEV"


def post_48h_workout_reminder(
    practices_needing_workout: list,
    channel_override: Optional[str] = None
) -> dict:
    """Post 48h workout reminder to #collab-coaches-practices.

    Tags @kj as a safety check before practices go live.

    Args:
        practices_needing_workout: List of Practice objects missing workouts
        channel_override: Optional channel name to override default (e.g., 'general')

    Returns:
        dict with keys:
        - success: bool
        - message_ts: str (if success)
        - error: str (if failure)
    """
    from app.practices.service import convert_practice_to_info

    if not practices_needing_workout:
        return {'success': True, 'message_ts': None, 'skipped': True}

    client = get_slack_client()

    # Determine channel - use override if provided
    if channel_override:
        channel_id = get_channel_id_by_name(channel_override.lstrip('#'))
    else:
        channel_id = COLLAB_CHANNEL_ID

    # Build message blocks
    blocks = []

    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": ":memo: Workout Check - 48 Hours Out",
            "emoji": True
        }
    })

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"<@{KJ_SLACK_ID}> The following practice(s) need workout descriptions before posting:"
        }
    })

    blocks.append({"type": "divider"})

    for practice in practices_needing_workout:
        practice_info = convert_practice_to_info(practice)
        time_str = practice_info.date.strftime('%A, %b %-d at %-I:%M %p')
        location = practice_info.location.name if practice_info.location else "TBD"

        # Get coach names
        coaches = [lead for lead in practice.leads if lead.role == 'coach']
        coach_text = ", ".join([f"<@{c.user.slack_user.slack_uid}>" for c in coaches
                               if c.user and c.user.slack_user]) or "No coach assigned"

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{time_str}*\n:round_pushpin: {location}\n:bust_in_silhouette: {coach_text}"
            }
        })

    try:
        response = client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text="48h Workout Check",
            unfurl_links=False,
            unfurl_media=False
        )

        message_ts = response.get('ts')
        current_app.logger.info(f"Posted 48h workout reminder (ts: {message_ts})")

        return {
            'success': True,
            'message_ts': message_ts,
            'channel_id': channel_id
        }

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error posting 48h workout reminder: {error_msg}")
        return {'success': False, 'error': error_msg}


def post_24h_lead_confirmation(
    practices_needing_confirmation: list,
    channel_override: Optional[str] = None
) -> dict:
    """Post 24h lead confirmation request to #coord-practices-leads-assists.

    Tags the assigned leads for each practice needing confirmation.

    Args:
        practices_needing_confirmation: List of tuples (Practice, lead_slack_ids)
        channel_override: Optional channel name to override default (e.g., 'general')

    Returns:
        dict with keys:
        - success: bool
        - message_ts: str (if success)
        - error: str (if failure)
    """
    from app.practices.service import convert_practice_to_info

    if not practices_needing_confirmation:
        return {'success': True, 'message_ts': None, 'skipped': True}

    client = get_slack_client()

    # Determine channel - use override if provided
    if channel_override:
        channel_id = get_channel_id_by_name(channel_override.lstrip('#'))
    else:
        channel_id = COORD_CHANNEL_ID

    # Build message blocks
    blocks = []

    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": ":clock1: Lead Confirmation - Tomorrow's Practices",
            "emoji": True
        }
    })

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "Please confirm your availability for tomorrow's practice(s):"
        }
    })

    blocks.append({"type": "divider"})

    for practice, lead_slack_ids in practices_needing_confirmation:
        practice_info = convert_practice_to_info(practice)
        time_str = practice_info.date.strftime('%-I:%M %p')
        location = practice_info.location.name if practice_info.location else "TBD"

        # Build lead mentions
        lead_mentions = " ".join([f"<@{uid}>" for uid in lead_slack_ids]) or "No lead assigned"

        # Practice type info
        type_names = ", ".join([t.name for t in practice_info.practice_types]) if practice_info.practice_types else "Practice"

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{lead_mentions}\n*{time_str}* - {type_names} at *{location}*"
            }
        })

        # Add confirm/need-sub buttons
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":white_check_mark: I'll be there", "emoji": True},
                    "style": "primary",
                    "action_id": "lead_confirm",
                    "value": str(practice.id)
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":sos: Need a sub", "emoji": True},
                    "style": "danger",
                    "action_id": "lead_need_sub",
                    "value": str(practice.id)
                }
            ]
        })

        blocks.append({"type": "divider"})

    try:
        response = client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text="24h Lead Confirmation",
            unfurl_links=False,
            unfurl_media=False
        )

        message_ts = response.get('ts')
        current_app.logger.info(f"Posted 24h lead confirmation (ts: {message_ts})")

        return {
            'success': True,
            'message_ts': message_ts,
            'channel_id': channel_id
        }

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error posting 24h lead confirmation: {error_msg}")
        return {'success': False, 'error': error_msg}


def post_daily_practice_recap(
    evaluations: list[dict],
    channel_override: Optional[str] = None
) -> dict:
    """Post daily practice conditions recap to #practices-core.

    Called by morning_check routine at 7am when there are practices today.
    Shows weather, trail conditions, lead status, and any cancellation proposals.

    Args:
        evaluations: List of dicts with keys:
            - practice: PracticeInfo
            - evaluation: PracticeEvaluation (or None)
            - summary: str
            - is_go: bool
            - proposal_id: int (if cancellation proposed)
        channel_override: Optional channel name to override default (e.g., 'general')

    Returns:
        dict with keys:
        - success: bool
        - message_ts: str (if success)
        - error: str (if failure)
    """
    from app.slack.blocks import build_daily_practice_recap_blocks

    client = get_slack_client()

    # Determine channel - use override if provided
    if channel_override:
        channel_id = get_channel_id_by_name(channel_override.lstrip('#'))
    else:
        channel_id = PRACTICES_CORE_CHANNEL_ID

    # Check if any proposals were created
    has_proposals = any(e.get('proposal_id') for e in evaluations)

    # Build blocks
    blocks = build_daily_practice_recap_blocks(evaluations, has_proposals)

    try:
        response = client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text="Daily Practice Conditions Recap",
            unfurl_links=False,
            unfurl_media=False
        )

        message_ts = response.get('ts')
        current_app.logger.info(f"Posted daily practice recap (ts: {message_ts})")

        return {
            'success': True,
            'message_ts': message_ts,
            'channel_id': channel_id
        }

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error posting daily practice recap: {error_msg}")
        return {'success': False, 'error': error_msg}


def create_practice_log_thread(practice: Practice) -> dict:
    """Create a logging thread for a practice in #tcsc-logging.

    Posts the initial message that will serve as the parent for RSVP logs.

    Args:
        practice: Practice SQLAlchemy model

    Returns:
        dict with keys:
        - success: bool
        - message_ts: str (only if success=True)
        - error: str (only if success=False)
    """
    client = get_slack_client()

    # Format practice info for log header
    date_str = practice.date.strftime('%A, %B %d')
    time_str = practice.date.strftime('%-I:%M %p').replace(' AM', 'am').replace(' PM', 'pm')
    location = practice.location.name if practice.location else "TBD"
    practice_types = ', '.join([t.name for t in practice.practice_types]) if practice.practice_types else "Practice"

    log_text = f":thread: *Practice Log: {date_str}*\n{practice_types} @ {location} ({time_str})"

    try:
        response = client.chat_postMessage(
            channel=LOGGING_CHANNEL_ID,
            text=log_text,
            unfurl_links=False,
            unfurl_media=False
        )

        message_ts = response.get('ts')
        practice.slack_log_message_ts = message_ts
        db.session.commit()

        current_app.logger.info(f"Created practice log thread for practice #{practice.id}")
        return {'success': True, 'message_ts': message_ts}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error creating practice log thread: {error_msg}")
        return {'success': False, 'error': error_msg}


def log_rsvp_action(practice: Practice, slack_user_id: str, action: str) -> dict:
    """Log an RSVP action to the practice's logging thread.

    Args:
        practice: Practice SQLAlchemy model with slack_log_message_ts set
        slack_user_id: Slack user ID who performed the action
        action: 'going' or 'removed'

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    if not practice.slack_log_message_ts:
        return {'success': False, 'error': 'No log thread for this practice'}

    client = get_slack_client()

    # Format the log message
    timestamp = datetime.now().strftime('%-I:%M %p')
    if action == 'going':
        log_text = f":white_check_mark: <@{slack_user_id}> RSVP'd going ({timestamp})"
    else:
        log_text = f":wave: <@{slack_user_id}> removed their RSVP ({timestamp})"

    try:
        client.chat_postMessage(
            channel=LOGGING_CHANNEL_ID,
            thread_ts=practice.slack_log_message_ts,
            text=log_text,
            unfurl_links=False,
            unfurl_media=False
        )

        current_app.logger.info(f"Logged RSVP action for practice #{practice.id}: {action}")
        return {'success': True}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error logging RSVP action: {error_msg}")
        return {'success': False, 'error': error_msg}


# =============================================================================
# Coach Review Workflow (to #collab-coaches-practices)
# =============================================================================

COLLAB_CHANNEL_ID = "C04AUHEDBSR"  # #collab-coaches-practices

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


def post_collab_review(practice: Practice) -> dict:
    """Post practice review request to #collab-coaches-practices.

    This is posted before the practice announcement so coaches can review
    and approve the practice details.

    Args:
        practice: Practice SQLAlchemy model

    Returns:
        dict with keys:
        - success: bool
        - message_ts: str (only if success=True)
        - channel_id: str (only if success=True)
        - error: str (only if success=False)
    """
    client = get_slack_client()

    # Convert SQLAlchemy model to PracticeInfo dataclass
    from app.practices.service import convert_practice_to_info
    practice_info = convert_practice_to_info(practice)

    # Build blocks (not approved yet)
    blocks = build_collab_practice_blocks(
        practice_info,
        approved=practice.coach_approved,
        approved_by=practice.approved_by_slack_uid,
        approved_at=practice.approved_at
    )

    try:
        response = client.chat_postMessage(
            channel=COLLAB_CHANNEL_ID,
            blocks=blocks,
            text=f"Practice review: {practice.date.strftime('%A, %B %d')}",  # Fallback text
            unfurl_links=False,
            unfurl_media=False
        )

        message_ts = response.get('ts')
        current_app.logger.info(f"Posted collab review for practice #{practice.id} (ts: {message_ts})")

        # Save collab message info to practice
        practice.slack_collab_message_ts = message_ts
        db.session.commit()

        # Also create logging thread if not already created
        if not practice.slack_log_message_ts:
            try:
                create_practice_log_thread(practice)
            except Exception as e:
                current_app.logger.warning(f"Could not create practice log thread: {e}")

        return {
            'success': True,
            'message_ts': message_ts,
            'channel_id': COLLAB_CHANNEL_ID
        }

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error posting collab review: {error_msg}")
        return {'success': False, 'error': error_msg}


def update_practice_post(practice: Practice) -> dict:
    """Update the main practice announcement post with current data.

    Args:
        practice: Practice SQLAlchemy model with slack_message_ts set

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    if not practice.slack_message_ts or not practice.slack_channel_id:
        return {'success': False, 'error': 'No practice message to update'}

    client = get_slack_client()

    # Convert SQLAlchemy model to PracticeInfo dataclass
    from app.practices.service import convert_practice_to_info
    practice_info = convert_practice_to_info(practice)

    # Build updated blocks (without weather/trail data)
    blocks = build_practice_announcement_blocks(practice_info)

    try:
        client.chat_update(
            channel=practice.slack_channel_id,
            ts=practice.slack_message_ts,
            blocks=blocks,
            text=f"Practice on {practice.date.strftime('%A, %B %d')}"
        )

        current_app.logger.info(f"Updated practice post for practice #{practice.id}")
        return {'success': True}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error updating practice post: {error_msg}")
        return {'success': False, 'error': error_msg}


def update_collab_post(practice: Practice) -> dict:
    """Update the collab review post with current practice data.

    Args:
        practice: Practice SQLAlchemy model with slack_collab_message_ts set

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    if not practice.slack_collab_message_ts:
        return {'success': False, 'error': 'No collab message to update'}

    client = get_slack_client()

    # Convert SQLAlchemy model to PracticeInfo dataclass
    from app.practices.service import convert_practice_to_info
    practice_info = convert_practice_to_info(practice)

    # Build updated blocks
    blocks = build_collab_practice_blocks(
        practice_info,
        approved=practice.coach_approved,
        approved_by=practice.approved_by_slack_uid,
        approved_at=practice.approved_at
    )

    try:
        client.chat_update(
            channel=COLLAB_CHANNEL_ID,
            ts=practice.slack_collab_message_ts,
            blocks=blocks,
            text=f"Practice review: {practice.date.strftime('%A, %B %d')}"
        )

        current_app.logger.info(f"Updated collab post for practice #{practice.id}")
        return {'success': True}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error updating collab post: {error_msg}")
        return {'success': False, 'error': error_msg}


def log_collab_edit(practice: Practice, slack_user_id: str) -> dict:
    """Log an edit action to the collab post thread.

    Args:
        practice: Practice SQLAlchemy model with slack_collab_message_ts set
        slack_user_id: Slack user ID who made the edit

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    if not practice.slack_collab_message_ts:
        return {'success': False, 'error': 'No collab message to add thread to'}

    client = get_slack_client()
    timestamp = datetime.now().strftime('%-I:%M %p')
    log_text = f":pencil2: <@{slack_user_id}> updated this practice at {timestamp}"

    try:
        client.chat_postMessage(
            channel=COLLAB_CHANNEL_ID,
            thread_ts=practice.slack_collab_message_ts,
            text=log_text,
            unfurl_links=False,
            unfurl_media=False
        )

        current_app.logger.info(f"Logged collab edit for practice #{practice.id}")
        return {'success': True}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error logging collab edit: {error_msg}")
        return {'success': False, 'error': error_msg}


def log_practice_edit(practice: Practice, slack_user_id: str) -> dict:
    """Log an edit action to the practice announcement thread.

    Args:
        practice: Practice SQLAlchemy model with slack_message_ts set
        slack_user_id: Slack user ID who made the edit

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    if not practice.slack_message_ts or not practice.slack_channel_id:
        return {'success': False, 'error': 'No practice message to add thread to'}

    client = get_slack_client()
    log_text = f":pencil2: <@{slack_user_id}> updated the workout"

    try:
        client.chat_postMessage(
            channel=practice.slack_channel_id,
            thread_ts=practice.slack_message_ts,
            text=log_text,
            unfurl_links=False,
            unfurl_media=False
        )

        current_app.logger.info(f"Logged practice edit for practice #{practice.id}")
        return {'success': True}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error logging practice edit: {error_msg}")
        return {'success': False, 'error': error_msg}


def post_coach_weekly_summary(
    week_start: datetime,
    channel_override: Optional[str] = None
) -> dict:
    """Post weekly coach review summary to #collab-coaches-practices.

    Creates a summary post showing all practices for the week with Edit buttons.
    For days without practices, shows placeholders with "Add Practice" buttons.
    Tags users with HEAD_COACH role for review.

    Args:
        week_start: Monday of the week to summarize
        channel_override: Optional channel name to override default (e.g., 'general')

    Returns:
        dict with keys:
        - success: bool
        - message_ts: str (if success)
        - error: str (only if success=False)
    """
    from datetime import timedelta
    from app.models import AppConfig, db, Tag, User
    from app.practices.service import convert_practice_to_info
    from app.slack.blocks import build_coach_weekly_summary_blocks

    # Get expected practice days from config
    expected_days = AppConfig.get('practice_days', [
        {"day": "tuesday", "time": "18:00", "active": True},
        {"day": "thursday", "time": "18:00", "active": True},
        {"day": "saturday", "time": "09:00", "active": True}
    ])

    # Query practices for the week
    week_end = week_start + timedelta(days=7)
    practices = Practice.query.filter(
        Practice.date >= week_start,
        Practice.date < week_end
    ).order_by(Practice.date).all()

    # Convert to PracticeInfo
    practice_infos = [convert_practice_to_info(p) for p in practices]

    # Build blocks
    blocks = build_coach_weekly_summary_blocks(practice_infos, expected_days, week_start)

    # Determine channel - use override if provided
    if channel_override:
        channel_id = get_channel_id_by_name(channel_override.lstrip('#'))
    else:
        channel_id = COLLAB_CHANNEL_ID

    # Get users with HEAD_COACH tag to mention
    review_tags = Tag.query.filter(Tag.name == 'HEAD_COACH').all()
    mentions = []
    for tag in review_tags:
        for user in tag.users:
            if user.slack_user and user.slack_user.slack_uid:
                mentions.append(f"<@{user.slack_user.slack_uid}>")

    # Add mentions as a context block at the end if we have any
    if mentions:
        unique_mentions = list(dict.fromkeys(mentions))  # Remove duplicates, preserve order
        blocks.append({
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": f":eyes: {' '.join(unique_mentions)} — please review this week's practices"
            }]
        })

    # Post to channel
    client = get_slack_client()
    try:
        response = client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text=f"Coach Review: Week of {week_start.strftime('%B %-d')}",
            unfurl_links=False,
            unfurl_media=False
        )

        message_ts = response.get('ts')
        current_app.logger.info(f"Posted coach weekly summary (ts: {message_ts})")

        # Save message_ts to each practice's slack_coach_summary_ts
        for practice in practices:
            practice.slack_coach_summary_ts = message_ts
        db.session.commit()

        return {'success': True, 'message_ts': message_ts, 'channel_id': channel_id}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error posting coach weekly summary: {error_msg}")
        return {'success': False, 'error': error_msg}


def log_coach_summary_edit(practice: Practice, slack_user_id: str) -> dict:
    """Log an edit action to the coach weekly summary thread.

    Args:
        practice: Practice SQLAlchemy model with slack_coach_summary_ts set
        slack_user_id: Slack user ID who made the edit

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    if not practice.slack_coach_summary_ts:
        return {'success': False, 'error': 'No summary message to add thread to'}

    client = get_slack_client()
    timestamp = datetime.now().strftime('%-I:%M %p')
    date_str = practice.date.strftime('%A, %b %-d')
    log_text = f":pencil2: <@{slack_user_id}> updated *{date_str}* practice at {timestamp}"

    try:
        client.chat_postMessage(
            channel=COLLAB_CHANNEL_ID,
            thread_ts=practice.slack_coach_summary_ts,
            text=log_text,
            unfurl_links=False,
            unfurl_media=False
        )

        current_app.logger.info(f"Logged coach summary edit for practice #{practice.id}")
        return {'success': True}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error logging coach summary edit: {error_msg}")
        return {'success': False, 'error': error_msg}


def get_practice_coach_ids(practice: Practice) -> list[str]:
    """Get Slack IDs of coaches assigned to this practice.

    Args:
        practice: Practice SQLAlchemy model

    Returns:
        List of Slack user IDs for assigned coaches
    """
    coach_ids = []
    if practice.leads:
        for lead in practice.leads:
            if lead.role == 'coach':
                if lead.user and lead.user.slack_user:
                    coach_ids.append(lead.user.slack_user.slack_uid)
    return coach_ids


def escalate_practice_review(practice: Practice) -> dict:
    """Post escalation thread reply tagging coaches and admins.

    Called when practice hasn't been approved by escalation deadline.

    Args:
        practice: Practice SQLAlchemy model with slack_collab_message_ts set

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    if not practice.slack_collab_message_ts:
        return {'success': False, 'error': 'No collab message to escalate'}

    client = get_slack_client()

    # Get coach IDs or use fallback
    coach_ids = get_practice_coach_ids(practice)
    if not coach_ids:
        coach_ids = FALLBACK_COACH_IDS

    # Build mentions
    mentions = [f"<@{uid}>" for uid in coach_ids]
    mentions.extend([f"<@{uid}>" for uid in ADMIN_SLACK_IDS])
    mention_text = " ".join(mentions)

    log_text = f":warning: {mention_text} This practice hasn't been reviewed yet. Please approve or edit."

    try:
        client.chat_postMessage(
            channel=COLLAB_CHANNEL_ID,
            thread_ts=practice.slack_collab_message_ts,
            text=log_text,
            unfurl_links=False,
            unfurl_media=False
        )

        # Mark as escalated
        practice.escalated = True
        db.session.commit()

        current_app.logger.info(f"Escalated practice review for practice #{practice.id}")
        return {'success': True}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error escalating practice review: {error_msg}")
        return {'success': False, 'error': error_msg}


# =============================================================================
# Combined Lift Post Updates
# =============================================================================

def is_combined_lift_practice(practice: Practice) -> bool:
    """Check if practice is part of a combined lift post.

    A practice is part of a combined lift if:
    1. It has slack_message_ts set
    2. Another practice shares the same slack_message_ts

    Args:
        practice: Practice SQLAlchemy model

    Returns:
        True if practice is part of a combined post with other practices.
    """
    if not practice.slack_message_ts:
        return False

    # Count how many practices share this message_ts
    count = Practice.query.filter(
        Practice.slack_message_ts == practice.slack_message_ts
    ).count()

    return count > 1


def update_combined_lift_post(practice: Practice) -> dict:
    """Update combined lift announcement when any practice in it changes.

    Finds all practices sharing the same slack_message_ts and rebuilds
    the combined block structure.

    Args:
        practice: Practice SQLAlchemy model (one of the combined practices)

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    if not practice.slack_message_ts or not practice.slack_channel_id:
        return {'success': False, 'error': 'No Slack message to update'}

    client = get_slack_client()

    # Find all practices sharing this message_ts
    practices = Practice.query.filter(
        Practice.slack_message_ts == practice.slack_message_ts
    ).order_by(Practice.date).all()

    if not practices:
        return {'success': False, 'error': 'No practices found for this message'}

    # Convert to PracticeInfo dataclasses
    from app.practices.service import convert_practice_to_info
    practice_infos = [convert_practice_to_info(p) for p in practices]

    # Build combined blocks
    blocks = build_combined_lift_blocks(practice_infos)

    # Build fallback text with all days
    days = [p.date.strftime('%A') for p in practices]
    days_str = " & ".join(days)

    try:
        client.chat_update(
            channel=practice.slack_channel_id,
            ts=practice.slack_message_ts,
            blocks=blocks,
            text=f"TCSC Lift - {days_str}"
        )

        practice_ids = [p.id for p in practices]
        current_app.logger.info(f"Updated combined lift post for practices {practice_ids}")
        return {'success': True}

    except SlackApiError as e:
        error_msg = e.response.get('error', str(e))
        current_app.logger.error(f"Error updating combined lift post: {error_msg}")
        return {'success': False, 'error': error_msg}


def update_practice_slack_post(practice: Practice) -> dict:
    """Smart update that handles both individual and combined posts.

    Detects whether the practice is part of a combined lift post and
    uses the appropriate update function.

    Args:
        practice: Practice SQLAlchemy model

    Returns:
        dict with keys:
        - success: bool
        - error: str (only if success=False)
    """
    if not practice.slack_message_ts:
        return {'success': False, 'error': 'No Slack post to update'}

    if is_combined_lift_practice(practice):
        return update_combined_lift_post(practice)
    else:
        return update_practice_post(practice)
