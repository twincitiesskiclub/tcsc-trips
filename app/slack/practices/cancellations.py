"""Cancellation workflow operations."""

from typing import Optional
from flask import current_app
from slack_sdk.errors import SlackApiError

from app.slack.client import get_slack_client
from app.slack.blocks import (
    build_cancellation_proposal_blocks,
    build_cancellation_decision_update,
    build_practice_cancelled_notice,
)
from app.practices.models import Practice, CancellationRequest
from app.practices.interfaces import PracticeEvaluation

from app.slack.practices._config import _get_announcement_channel, _get_escalation_channel


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
