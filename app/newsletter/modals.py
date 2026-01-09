"""Slack modal builders for newsletter/dispatch interactions."""

import yaml
from pathlib import Path
from typing import Optional


def _load_submission_types() -> list[dict]:
    """Load submission types from config/newsletter.yaml.

    Returns:
        List of submission type dicts with 'value', 'label', 'description' keys.
        Falls back to defaults if config is not available.
    """
    config_path = Path(__file__).parent.parent.parent / 'config' / 'newsletter.yaml'

    defaults = [
        {"value": "spotlight", "label": "Member Spotlight", "description": "Highlight a fellow member's achievement"},
        {"value": "content", "label": "Story or Content", "description": "Share a story, tip, or interesting content"},
        {"value": "event", "label": "Event Announcement", "description": "Announce an upcoming club or community event"},
        {"value": "announcement", "label": "Official Announcement", "description": "Official club news or policy updates"},
    ]

    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            return config.get('newsletter', {}).get('submission_types', defaults)
    except (FileNotFoundError, yaml.YAMLError):
        return defaults


def build_dispatch_submission_modal(initial_type: Optional[str] = None) -> dict:
    """Build the /dispatch submission modal.

    Creates a modal for members to submit content to the Weekly Dispatch newsletter.

    Fields:
    - Submission Type: static_select with options from config
    - Content: plain_text_input (multiline)
    - Attribution: checkboxes for "Include my name"

    Args:
        initial_type: Optional initial selection for submission type.

    Returns:
        Slack modal view payload.
    """
    submission_types = _load_submission_types()

    # Build options for static_select
    type_options = []
    initial_option = None

    for st in submission_types:
        option = {
            "text": {
                "type": "plain_text",
                "text": st['label']
            },
            "value": st['value']
        }
        type_options.append(option)

        # Set initial option if specified
        if initial_type and st['value'] == initial_type:
            initial_option = option

    # Build type selector element
    type_element = {
        "type": "static_select",
        "action_id": "submission_type",
        "placeholder": {
            "type": "plain_text",
            "text": "Select submission type"
        },
        "options": type_options
    }

    if initial_option:
        type_element["initial_option"] = initial_option

    # Build description text showing what each type means
    description_parts = ["*Submission Types:*"]
    for st in submission_types:
        description_parts.append(f"- *{st['label']}*: {st.get('description', '')}")
    description_text = "\n".join(description_parts)

    return {
        "type": "modal",
        "callback_id": "dispatch_submission",
        "title": {
            "type": "plain_text",
            "text": "Submit to Dispatch"
        },
        "submit": {
            "type": "plain_text",
            "text": "Submit"
        },
        "close": {
            "type": "plain_text",
            "text": "Cancel"
        },
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": ":newspaper: *Submit content for the Weekly Dispatch*\n\nYour submission will be reviewed and may be included in the next newsletter."
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "input",
                "block_id": "type_block",
                "label": {
                    "type": "plain_text",
                    "text": "What type of submission is this?"
                },
                "element": type_element
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": description_text
                    }
                ]
            },
            {
                "type": "input",
                "block_id": "content_block",
                "label": {
                    "type": "plain_text",
                    "text": "Your Content"
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": "submission_content",
                    "multiline": True,
                    "min_length": 10,
                    "max_length": 3000,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Write your submission here. Be descriptive - this will help the editors include your content effectively."
                    }
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "input",
                "block_id": "attribution_block",
                "optional": True,
                "label": {
                    "type": "plain_text",
                    "text": "Attribution"
                },
                "element": {
                    "type": "checkboxes",
                    "action_id": "permission_to_name",
                    "options": [
                        {
                            "text": {
                                "type": "mrkdwn",
                                "text": "*You may include my name*"
                            },
                            "description": {
                                "type": "plain_text",
                                "text": "Your name may appear alongside your submission"
                            },
                            "value": "include_name"
                        }
                    ]
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": ":lock: _By default, submissions are anonymous. Check the box above if you'd like to be credited._"
                    }
                ]
            }
        ]
    }


def build_dispatch_confirmation_blocks(
    submission_type: str,
    content_preview: str,
    permission_to_name: bool
) -> list[dict]:
    """Build blocks for the submission confirmation ephemeral message.

    Args:
        submission_type: The type of submission (e.g., 'spotlight', 'content')
        content_preview: First 100 chars of the submitted content
        permission_to_name: Whether the user allowed name attribution

    Returns:
        List of Slack Block Kit blocks for the confirmation message.
    """
    # Get the label for the submission type
    submission_types = _load_submission_types()
    type_label = submission_type.title()
    for st in submission_types:
        if st['value'] == submission_type:
            type_label = st['label']
            break

    attribution_text = "Yes - your name may be included" if permission_to_name else "No - anonymous submission"

    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": ":white_check_mark: *Your submission has been received!*\n\nThe newsletter editors will review your content for the next Weekly Dispatch."
            }
        },
        {
            "type": "divider"
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Type:*\n{type_label}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Attribution:*\n{attribution_text}"
                }
            ]
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Preview:*\n_{content_preview}{'...' if len(content_preview) >= 100 else ''}_"
            }
        }
    ]
