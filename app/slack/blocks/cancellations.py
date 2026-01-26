"""Block Kit builders for practice cancellation messages."""

from typing import Optional
from app.practices.interfaces import (
    PracticeInfo,
    CancellationProposal,
    PracticeEvaluation,
)


def build_cancellation_proposal_blocks(
    proposal: CancellationProposal,
    evaluation: Optional[PracticeEvaluation] = None
) -> list[dict]:
    """Build Block Kit blocks for cancellation proposal.

    Args:
        proposal: Cancellation proposal
        evaluation: Practice evaluation data (if available)

    Returns:
        List of Slack Block Kit blocks
    """
    blocks = []

    # Header
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": ":warning: Practice Cancellation Proposal"
        }
    })

    # Reason summary
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"*Reason:* {proposal.reason_type.replace('_', ' ').title()}\n{proposal.reason_summary}"
        }
    })

    # Evaluation details if available
    if evaluation:
        # Weather violations
        if evaluation.violations:
            violation_text = "*Threshold Violations:*\n"
            for v in evaluation.violations:
                icon = ":warning:" if v.severity == "warning" else ":x:"
                violation_text += f"{icon} {v.message}\n"

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": violation_text
                }
            })

        # Weather conditions
        if evaluation.weather:
            w = evaluation.weather
            weather_text = f"*Current Conditions:*\n"
            weather_text += f"Temperature: {w.temperature_f:.0f}°F (feels like {w.feels_like_f:.0f}°F)\n"
            weather_text += f"Wind: {w.wind_speed_mph:.0f} mph"
            if w.wind_gust_mph:
                weather_text += f" (gusts to {w.wind_gust_mph:.0f} mph)"

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": weather_text
                }
            })

        # AI recommendation
        if evaluation.recommendation:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Weather Assessment:*\n_{evaluation.recommendation}_"
                }
            })

    # Timeout warning
    if proposal.expires_at:
        from app.utils import format_datetime_central
        expires_str = format_datetime_central(proposal.expires_at, '%I:%M %p')
        blocks.append({
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": f":clock1: Decision needed by {expires_str}. Practice continues if no response."
            }]
        })

    blocks.append({"type": "divider"})

    # Approval buttons
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Approve Cancellation"},
                "style": "danger",
                "action_id": "cancellation_approve",
                "value": str(proposal.id)
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Reject - Keep Practice"},
                "style": "primary",
                "action_id": "cancellation_reject",
                "value": str(proposal.id)
            }
        ]
    })

    return blocks


def build_cancellation_decision_update(
    proposal: CancellationProposal,
    approved: bool,
    decided_by_name: str
) -> list[dict]:
    """Build blocks showing cancellation decision.

    Args:
        proposal: Cancellation proposal
        approved: Whether cancellation was approved
        decided_by_name: Name/mention of person who decided

    Returns:
        List of Slack Block Kit blocks
    """
    blocks = []

    if approved:
        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": ":x: Practice Cancelled"
            }
        })

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Cancelled by:* {decided_by_name}\n*Reason:* {proposal.reason_summary}"
            }
        })
    else:
        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": ":white_check_mark: Practice Continuing"
            }
        })

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Decision by:* {decided_by_name}\nCancellation proposal was rejected. Practice will continue as scheduled."
            }
        })

    if proposal.decision_notes:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Notes:* {proposal.decision_notes}"
            }
        })

    return blocks


def build_practice_cancelled_notice(practice: PracticeInfo) -> list[dict]:
    """Build blocks for practice cancellation notice.

    Args:
        practice: Cancelled practice

    Returns:
        List of Slack Block Kit blocks
    """
    blocks = []

    date_str = practice.date.strftime('%A, %B %d at %I:%M %p')
    location = practice.location.name if practice.location else ""

    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": ":x: Practice Cancelled"
        }
    })

    cancel_text = f"The practice scheduled for *{date_str}*"
    if location:
        cancel_text += f" at *{location}*"
    cancel_text += " has been cancelled."

    if practice.cancellation_reason:
        cancel_text += f"\n\n*Reason:* {practice.cancellation_reason}"

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": cancel_text
        }
    })

    return blocks
