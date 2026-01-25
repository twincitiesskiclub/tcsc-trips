"""Block Kit builders for lead confirmation and substitution messages."""

from app.practices.interfaces import PracticeInfo


def build_lead_confirmation_blocks(practice: PracticeInfo) -> list[dict]:
    """Build blocks for lead confirmation request.

    Args:
        practice: Practice information

    Returns:
        List of Slack Block Kit blocks
    """
    blocks = []

    date_str = practice.date.strftime('%A, %B %d at %I:%M %p')
    location = practice.location.name if practice.location else "TBD"

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"You're scheduled to lead practice on *{date_str}* at *{location}*"
        }
    })

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "Can you confirm your availability?"
        }
    })

    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": ":white_check_mark: I'll be there"},
                "style": "primary",
                "action_id": "lead_confirm",
                "value": str(practice.id)
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": ":sos: Need a sub"},
                "style": "danger",
                "action_id": "lead_need_sub",
                "value": str(practice.id)
            }
        ]
    })

    return blocks


def build_substitution_request_blocks(
    practice: PracticeInfo,
    requester_slack_id: str,
    reason: str
) -> list[dict]:
    """Build blocks for lead substitution request.

    Args:
        practice: Practice information
        requester_slack_id: Slack ID of the person requesting a sub
        reason: Reason for needing a substitute

    Returns:
        List of Slack Block Kit blocks
    """
    blocks = []

    date_str = practice.date.strftime('%A, %B %d at %I:%M %p')
    location = practice.location.name if practice.location else "TBD"

    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": ":sos: Substitute Needed"
        }
    })

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"<@{requester_slack_id}> needs a substitute for practice on *{date_str}* at *{location}*"
        }
    })

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"*Reason:* {reason}"
        }
    })

    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": "Please reply in thread if you can cover this practice."
        }]
    })

    return blocks
