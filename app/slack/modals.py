"""Slack modal view builders for practice interactions."""

from typing import Optional
from app.practices.interfaces import PracticeInfo, LeadRole


def _build_practice_flags_element(practice: PracticeInfo) -> dict:
    """Build checkboxes element for practice flags, properly handling initial_options.

    Args:
        practice: Practice information

    Returns:
        Checkboxes element dict with initial_options only if there are selected options
    """
    element = {
        "type": "checkboxes",
        "action_id": "practice_flags",
        "options": [
            {
                "text": {"type": "plain_text", "text": "🌙 Dark practice (headlamp required)"},
                "value": "is_dark_practice"
            },
            {
                "text": {"type": "plain_text", "text": "🍕 Social afterwards"},
                "value": "has_social"
            }
        ]
    }

    # Build initial options list - only include if there are selected options
    initial_options = []
    if practice.is_dark_practice:
        initial_options.append({
            "text": {"type": "plain_text", "text": "🌙 Dark practice (headlamp required)"},
            "value": "is_dark_practice"
        })
    if practice.has_social:
        initial_options.append({
            "text": {"type": "plain_text", "text": "🍕 Social afterwards"},
            "value": "has_social"
        })

    # Only add initial_options key if there are selected options (Slack rejects null/empty)
    if initial_options:
        element["initial_options"] = initial_options

    return element


def _build_person_multi_select(
    action_id: str,
    placeholder: str,
    eligible_users: list,
    current_assignments: list
) -> dict:
    """Build multi_static_select element for coach/lead selection.

    Args:
        action_id: Unique action ID for the element
        placeholder: Placeholder text when nothing selected
        eligible_users: List of (user_id, name, slack_uid) tuples
        current_assignments: List of PracticeLeadInfo for current assignments

    Returns:
        multi_static_select element dict
    """
    options = [
        {"text": {"type": "plain_text", "text": name[:75]}, "value": str(uid)}
        for uid, name, _ in eligible_users
    ]

    element = {
        "type": "multi_static_select",
        "action_id": action_id,
        "placeholder": {"type": "plain_text", "text": placeholder},
        "options": options
    }

    # Set initial selections from current assignments
    current_ids = {str(a.user_id) for a in current_assignments}
    initial = [opt for opt in options if opt["value"] in current_ids]
    if initial:
        element["initial_options"] = initial

    return element


def build_practice_edit_modal(practice: PracticeInfo) -> dict:
    """Build modal for editing practice details.

    Args:
        practice: Practice information

    Returns:
        Slack modal view payload
    """
    return {
        "type": "modal",
        "callback_id": "practice_edit",
        "private_metadata": str(practice.id),
        "title": {
            "type": "plain_text",
            "text": "Edit Practice"
        },
        "submit": {
            "type": "plain_text",
            "text": "Save"
        },
        "close": {
            "type": "plain_text",
            "text": "Cancel"
        },
        "blocks": [
            {
                "type": "input",
                "block_id": "date_block",
                "label": {
                    "type": "plain_text",
                    "text": "Date"
                },
                "element": {
                    "type": "datepicker",
                    "action_id": "practice_date",
                    "initial_date": practice.date.strftime('%Y-%m-%d')
                }
            },
            {
                "type": "input",
                "block_id": "location_block",
                "optional": True,
                "label": {
                    "type": "plain_text",
                    "text": "Meeting Spot Details"
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": "location_notes",
                    "multiline": True,
                    "initial_value": practice.location.spot if practice.location and practice.location.spot else ""
                }
            },
            {
                "type": "input",
                "block_id": "warmup_block",
                "optional": True,
                "label": {
                    "type": "plain_text",
                    "text": "Warmup Description"
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": "warmup_description",
                    "multiline": True,
                    "initial_value": practice.warmup_description or ""
                }
            },
            {
                "type": "input",
                "block_id": "workout_block",
                "optional": True,
                "label": {
                    "type": "plain_text",
                    "text": "Main Workout Description"
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": "workout_description",
                    "multiline": True,
                    "initial_value": practice.workout_description or ""
                }
            },
            {
                "type": "input",
                "block_id": "cooldown_block",
                "optional": True,
                "label": {
                    "type": "plain_text",
                    "text": "Cooldown Description"
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": "cooldown_description",
                    "multiline": True,
                    "initial_value": practice.cooldown_description or ""
                }
            }
        ]
    }


def build_rsvp_modal(
    practice: PracticeInfo,
    current_status: Optional[str] = None,
    rsvp_counts: Optional[dict[str, int]] = None
) -> dict:
    """Build modal for RSVP with optional notes.

    Args:
        practice: Practice information
        current_status: Current RSVP status if exists
        rsvp_counts: Dict with keys 'going', 'maybe', 'not_going' for current counts

    Returns:
        Slack modal view payload
    """
    date_str = practice.date.strftime('%A, %B %d at %I:%M %p')
    location = practice.location.name if practice.location else 'TBD'

    # Build RSVP counts summary if available
    rsvp_summary = ""
    if rsvp_counts:
        going = rsvp_counts.get('going', 0)
        maybe = rsvp_counts.get('maybe', 0)
        rsvp_summary = f"\n{going} going, {maybe} maybe"

    # Determine initial option
    initial_option = None
    if current_status:
        status_map = {
            'going': 'going',
            'not_going': 'not_going',
            'maybe': 'maybe'
        }
        initial_option = status_map.get(current_status)

    options = [
        {
            "text": {"type": "plain_text", "text": ":white_check_mark: Going", "emoji": True},
            "value": "going"
        },
        {
            "text": {"type": "plain_text", "text": ":grey_question: Maybe", "emoji": True},
            "value": "maybe"
        },
        {
            "text": {"type": "plain_text", "text": ":x: Not Going", "emoji": True},
            "value": "not_going"
        }
    ]

    element_config = {
        "type": "static_select",
        "action_id": "rsvp_status",
        "placeholder": {
            "type": "plain_text",
            "text": "Select your status"
        },
        "options": options
    }

    if initial_option:
        element_config["initial_option"] = next(
            (opt for opt in options if opt["value"] == initial_option),
            options[0]
        )

    return {
        "type": "modal",
        "callback_id": "practice_rsvp",
        "private_metadata": str(practice.id),
        "title": {
            "type": "plain_text",
            "text": "RSVP to Practice"
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
                    "text": f"*{date_str}*\nLocation: {location}{rsvp_summary}"
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "input",
                "block_id": "status_block",
                "label": {
                    "type": "plain_text",
                    "text": "Attendance"
                },
                "element": element_config
            },
            {
                "type": "input",
                "block_id": "notes_block",
                "optional": True,
                "label": {
                    "type": "plain_text",
                    "text": "Notes (optional)"
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": "rsvp_notes",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Any additional info (e.g., arriving late, bringing friends)"
                    }
                }
            }
        ]
    }


def build_workout_modal(practice: PracticeInfo) -> dict:
    """Build modal for coach to enter workout details.

    Args:
        practice: Practice information

    Returns:
        Slack modal view payload
    """
    date_str = practice.date.strftime('%A, %B %d')

    return {
        "type": "modal",
        "callback_id": "workout_entry",
        "private_metadata": str(practice.id),
        "title": {
            "type": "plain_text",
            "text": "Add Workout Details"
        },
        "submit": {
            "type": "plain_text",
            "text": "Post"
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
                    "text": f"*Practice: {date_str}*"
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "input",
                "block_id": "warmup_block",
                "label": {
                    "type": "plain_text",
                    "text": "Warmup"
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": "warmup_description",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "e.g., 15 min easy ski, focus on balance"
                    },
                    "initial_value": practice.warmup_description or ""
                }
            },
            {
                "type": "input",
                "block_id": "workout_block",
                "label": {
                    "type": "plain_text",
                    "text": "Main Workout"
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": "workout_description",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "e.g., 5 x 4min @ threshold (2min rest)"
                    },
                    "initial_value": practice.workout_description or ""
                }
            },
            {
                "type": "input",
                "block_id": "cooldown_block",
                "optional": True,
                "label": {
                    "type": "plain_text",
                    "text": "Cooldown"
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": "cooldown_description",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "e.g., 10 min easy, stretching"
                    },
                    "initial_value": practice.cooldown_description or ""
                }
            },
            {
                "type": "input",
                "block_id": "notes_block",
                "optional": True,
                "label": {
                    "type": "plain_text",
                    "text": "Additional Notes"
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": "workout_notes",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Weather, trail conditions, adjustments, etc."
                    }
                }
            }
        ]
    }


def build_practice_edit_full_modal(
    practice: PracticeInfo,
    locations: list = None,
    eligible_coaches: list = None,
    eligible_leads: list = None
) -> dict:
    """Build modal for full practice editing from collab channel.

    Includes all editable fields except date/time and practice types.
    Used by coaches/practices team to update practice details.

    Args:
        practice: Practice information
        locations: List of (id, name) tuples for location dropdown
        eligible_coaches: List of (user_id, name, slack_uid) tuples for coach selection
        eligible_leads: List of (user_id, name, slack_uid) tuples for lead selection

    Returns:
        Slack modal view payload
    """
    date_str = practice.date.strftime('%A, %B %d at %I:%M %p')
    location_name = practice.location.name if practice.location else 'TBD'

    # Practice types for context (read-only)
    practice_types = ", ".join([t.name for t in practice.practice_types]) if practice.practice_types else "General"

    # Build location dropdown options
    location_options = []
    initial_location = None
    if locations:
        for loc_id, loc_name in locations:
            option = {
                "text": {"type": "plain_text", "text": loc_name},
                "value": str(loc_id)
            }
            location_options.append(option)
            if practice.location and practice.location.id == loc_id:
                initial_location = option

    # Build location element
    if location_options:
        location_element = {
            "type": "static_select",
            "action_id": "location_id",
            "placeholder": {"type": "plain_text", "text": "Select a location"},
            "options": location_options
        }
        if initial_location:
            location_element["initial_option"] = initial_location
    else:
        # Fallback to text input if no locations provided
        location_element = {
            "type": "plain_text_input",
            "action_id": "location_id",
            "initial_value": location_name
        }

    # Build blocks dynamically
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{date_str}*\n:round_pushpin: {location_name} | {practice_types}"
            }
        },
        {"type": "divider"},
        {
            "type": "input",
            "block_id": "location_block",
            "label": {"type": "plain_text", "text": "Location"},
            "element": location_element
        },
        {
            "type": "input",
            "block_id": "warmup_block",
            "optional": True,
            "label": {"type": "plain_text", "text": "Warmup"},
            "element": {
                "type": "plain_text_input",
                "action_id": "warmup_description",
                "multiline": True,
                "placeholder": {"type": "plain_text", "text": "e.g., 15 min easy ski, focus on balance"},
                "initial_value": practice.warmup_description or ""
            }
        },
        {
            "type": "input",
            "block_id": "workout_block",
            "optional": True,
            "label": {"type": "plain_text", "text": "Main Workout"},
            "element": {
                "type": "plain_text_input",
                "action_id": "workout_description",
                "multiline": True,
                "placeholder": {"type": "plain_text", "text": "e.g., 5 x 4min @ threshold (2min rest)"},
                "initial_value": practice.workout_description or ""
            }
        },
        {
            "type": "input",
            "block_id": "cooldown_block",
            "optional": True,
            "label": {"type": "plain_text", "text": "Cooldown"},
            "element": {
                "type": "plain_text_input",
                "action_id": "cooldown_description",
                "multiline": True,
                "placeholder": {"type": "plain_text", "text": "e.g., 10 min easy, stretching"},
                "initial_value": practice.cooldown_description or ""
            }
        }
    ]

    # Add coach multi-select if eligible coaches provided
    if eligible_coaches:
        current_coaches = [l for l in practice.leads if l.role == LeadRole.COACH]
        blocks.append({
            "type": "input",
            "block_id": "coaches_block",
            "optional": True,
            "label": {"type": "plain_text", "text": "Coaches"},
            "element": _build_person_multi_select(
                "coach_ids", "Select coach(es)", eligible_coaches, current_coaches
            )
        })

    # Add lead multi-select if eligible leads provided
    if eligible_leads:
        current_leads = [l for l in practice.leads if l.role == LeadRole.LEAD]
        blocks.append({
            "type": "input",
            "block_id": "leads_block",
            "optional": True,
            "label": {"type": "plain_text", "text": "Practice Leads"},
            "element": _build_person_multi_select(
                "lead_ids", "Select lead(s)", eligible_leads, current_leads
            )
        })

    # Add flags and notification blocks
    blocks.extend([
        {
            "type": "input",
            "block_id": "flags_block",
            "optional": True,
            "label": {"type": "plain_text", "text": "Options"},
            "element": _build_practice_flags_element(practice)
        },
        {
            "type": "input",
            "block_id": "notify_block",
            "optional": True,
            "label": {"type": "plain_text", "text": "Notification"},
            "element": {
                "type": "checkboxes",
                "action_id": "notify_update",
                "options": [
                    {
                        "text": {"type": "mrkdwn", "text": "*Post update notification*"},
                        "description": {"type": "plain_text", "text": "Notify the thread about this change"},
                        "value": "notify"
                    }
                ],
                "initial_options": [
                    {
                        "text": {"type": "mrkdwn", "text": "*Post update notification*"},
                        "description": {"type": "plain_text", "text": "Notify the thread about this change"},
                        "value": "notify"
                    }
                ]
            }
        }
    ])

    return {
        "type": "modal",
        "callback_id": "practice_edit_full",
        "private_metadata": str(practice.id),
        "title": {"type": "plain_text", "text": "Edit Practice"},
        "submit": {"type": "plain_text", "text": "Save Changes"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": blocks
    }


def build_practice_create_modal(practice_date: 'datetime', default_time: str, locations: list = None,
                                channel_id: str = None, message_ts: str = None) -> dict:
    """Build modal for creating a new practice from weekly summary.

    Args:
        practice_date: Date for the new practice
        default_time: Default time string (e.g., "18:00")
        locations: List of (id, name) tuples for location dropdown
        channel_id: Channel where the summary post lives (for updating)
        message_ts: Timestamp of the summary post (for updating)

    Returns:
        Slack modal view payload
    """
    date_str = practice_date.strftime('%A, %B %-d')

    # Build metadata with date, channel, and message_ts
    import json
    metadata = json.dumps({
        'date': practice_date.strftime('%Y-%m-%d'),
        'channel_id': channel_id,
        'message_ts': message_ts
    })

    # Build location dropdown options
    location_options = []
    if locations:
        for loc_id, loc_name in locations:
            option = {
                "text": {"type": "plain_text", "text": loc_name},
                "value": str(loc_id)
            }
            location_options.append(option)

    # Build location element
    if location_options:
        location_element = {
            "type": "static_select",
            "action_id": "location_id",
            "placeholder": {"type": "plain_text", "text": "Select a location"},
            "options": location_options
        }
    else:
        # Fallback to text input if no locations provided
        location_element = {
            "type": "plain_text_input",
            "action_id": "location_id",
            "placeholder": {"type": "plain_text", "text": "Enter location name"}
        }

    return {
        "type": "modal",
        "callback_id": "practice_create",
        "private_metadata": metadata,
        "title": {
            "type": "plain_text",
            "text": "Add Practice"
        },
        "submit": {
            "type": "plain_text",
            "text": "Create Practice"
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
                    "text": f"*Creating practice for {date_str}*"
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "input",
                "block_id": "location_block",
                "label": {
                    "type": "plain_text",
                    "text": "Location"
                },
                "element": location_element
            },
            {
                "type": "input",
                "block_id": "time_block",
                "label": {
                    "type": "plain_text",
                    "text": "Time"
                },
                "element": {
                    "type": "timepicker",
                    "action_id": "practice_time",
                    "initial_time": default_time,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select time"
                    }
                }
            },
            {
                "type": "input",
                "block_id": "warmup_block",
                "optional": True,
                "label": {
                    "type": "plain_text",
                    "text": "Warmup"
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": "warmup_description",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "e.g., 15 min easy ski, focus on balance"
                    }
                }
            },
            {
                "type": "input",
                "block_id": "workout_block",
                "optional": True,
                "label": {
                    "type": "plain_text",
                    "text": "Main Workout"
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": "workout_description",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "e.g., 5 x 4min @ threshold (2min rest)"
                    }
                }
            },
            {
                "type": "input",
                "block_id": "cooldown_block",
                "optional": True,
                "label": {
                    "type": "plain_text",
                    "text": "Cooldown"
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": "cooldown_description",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "e.g., 10 min easy, stretching"
                    }
                }
            },
            {
                "type": "input",
                "block_id": "flags_block",
                "optional": True,
                "label": {
                    "type": "plain_text",
                    "text": "Options"
                },
                "element": {
                    "type": "checkboxes",
                    "action_id": "practice_flags",
                    "options": [
                        {
                            "text": {"type": "mrkdwn", "text": "*Dark practice*"},
                            "description": {"type": "plain_text", "text": "Practice after sunset, bring lights"},
                            "value": "is_dark_practice"
                        }
                    ]
                }
            }
        ]
    }


def build_lead_substitution_modal(practice: PracticeInfo) -> dict:
    """Build modal for lead to request substitution.

    Args:
        practice: Practice information

    Returns:
        Slack modal view payload
    """
    date_str = practice.date.strftime('%A, %B %d at %I:%M %p')
    location = practice.location.name if practice.location else 'TBD'

    return {
        "type": "modal",
        "callback_id": "lead_substitution",
        "private_metadata": str(practice.id),
        "title": {
            "type": "plain_text",
            "text": "Request Substitute"
        },
        "submit": {
            "type": "plain_text",
            "text": "Send Request"
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
                    "text": f"*{date_str}*\nLocation: {location}"
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "input",
                "block_id": "reason_block",
                "label": {
                    "type": "plain_text",
                    "text": "Reason"
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": "substitution_reason",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Let the team know why you need a sub"
                    }
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "_Your request will be posted to #practices-team_"
                }
            }
        ]
    }
