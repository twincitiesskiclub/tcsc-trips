"""Block Kit for the volunteer-interest backfill DM.

Sent to members who registered before the Get Involved question shipped.
The DM carries the whole form: interest checkboxes, a committee
multi-select, and a Submit button whose value is the season id. Copy
matches the web form's voice; keep the two in step.
"""

from app.constants import VOLUNTEER_INTERESTS, VOLUNTEER_COMMITTEES


def _plain(text: str) -> dict:
    return {"type": "plain_text", "text": text}


def _interest_option(key: str) -> dict:
    return {"text": _plain(VOLUNTEER_INTERESTS[key]), "value": key}


def _committee_option(key: str) -> dict:
    return {"text": _plain(VOLUNTEER_COMMITTEES[key]), "value": key}


def committee_short_label(key: str) -> str:
    """Committee label without its parenthetical, e.g. "Social"."""
    label = VOLUNTEER_COMMITTEES.get(key, key)
    return label.split(" (")[0]


def build_volunteer_ask_blocks(
    first_name: str,
    season_id: int,
    *,
    error: str | None = None,
    selected_interests: list[str] | None = None,
    selected_committees: list[str] | None = None,
) -> list[dict]:
    """The ask DM. On a validation error the message is re-rendered with the
    member's picks preserved (initial_options) and a hint line, so fixing the
    answer is one click, not a redo.
    """
    checkboxes = {
        "type": "checkboxes",
        "action_id": "volunteer_interests_input",
        "options": [_interest_option(k) for k in VOLUNTEER_INTERESTS],
    }
    if selected_interests:
        checkboxes["initial_options"] = [
            _interest_option(k) for k in selected_interests
            if k in VOLUNTEER_INTERESTS]

    select = {
        "type": "multi_static_select",
        "action_id": "volunteer_committees_input",
        "placeholder": _plain("Joining a committee? Pick which"),
        "options": [_committee_option(k) for k in VOLUNTEER_COMMITTEES],
    }
    if selected_committees:
        select["initial_options"] = [
            _committee_option(k) for k in selected_committees
            if k in VOLUNTEER_COMMITTEES]

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"Hey {first_name}! One thing we missed when you "
                    "registered: TCSC runs on volunteers, and we'd love "
                    "your help this season. Pick at least one:"
                ),
            },
        },
        {
            "type": "actions",
            "block_id": "volunteer_interests_block",
            "elements": [checkboxes],
        },
        {
            "type": "actions",
            "block_id": "volunteer_committees_block",
            "elements": [select],
        },
    ]

    if error:
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f":warning: {error}"}],
        })

    blocks.append({
        "type": "actions",
        "block_id": "volunteer_submit_block",
        "elements": [{
            "type": "button",
            "action_id": "volunteer_submit",
            "style": "primary",
            "text": _plain("Submit"),
            "value": str(season_id),
        }],
    })
    return blocks


def build_volunteer_thanks_blocks(
    first_name: str, interests: list[str], committees: list[str]
) -> list[dict]:
    """Replaces the ask once the answer is saved."""
    picks = [VOLUNTEER_INTERESTS.get(k, k) for k in interests]
    text = f"Thanks, {first_name}! You're down for: {', '.join(picks)}."
    if committees:
        names = ", ".join(committee_short_label(k) for k in committees)
        text += f" Committees: {names}."
    text += " We'll follow up soon."
    return [{
        "type": "section",
        "text": {"type": "mrkdwn", "text": f":white_check_mark: {text}"},
    }]
