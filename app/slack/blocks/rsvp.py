"""Block Kit builders for RSVP buttons and summary."""


def build_rsvp_buttons(practice_id: int) -> list[dict]:
    """Build RSVP action buttons.

    Args:
        practice_id: Practice ID

    Returns:
        List of Slack Block Kit blocks
    """
    return [{
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": ":white_check_mark: Going", "emoji": True},
                "style": "primary",
                "action_id": "rsvp_going",
                "value": str(practice_id)
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": ":grey_question: Maybe", "emoji": True},
                "action_id": "rsvp_maybe",
                "value": str(practice_id)
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": ":x: Not Going", "emoji": True},
                "action_id": "rsvp_not_going",
                "value": str(practice_id)
            }
        ]
    }]


def build_rsvp_summary_context(rsvp_counts: dict[str, int]) -> dict:
    """Build a context block showing RSVP counts.

    Args:
        rsvp_counts: Dict with keys 'going', 'maybe', 'not_going'

    Returns:
        Single context block dict
    """
    going = rsvp_counts.get('going', 0)
    maybe = rsvp_counts.get('maybe', 0)
    not_going = rsvp_counts.get('not_going', 0)

    return {
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": f":white_check_mark: {going} going  |  :grey_question: {maybe} maybe  |  :x: {not_going} not going"
        }]
    }
