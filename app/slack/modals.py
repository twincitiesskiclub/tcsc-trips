"""Slack modal view builders for practice interactions."""

from types import SimpleNamespace
from typing import Optional

from app.practices.interfaces import PracticeInfo, LeadRole
from app.practices.plan_reaction_editor import build_plan_reaction_editor_state
from app.practices.plan_reactions import (
    EVERGREEN_PLAN_REACTION,
    build_plan_reaction_catalog,
)
from app.slack.practice_reaction_editor import (
    SLACK_OPTION_TEXT_MAX_CHARS,
    apply_current_view_values,
    build_practice_reaction_blocks,
    encode_practice_reaction_metadata,
)


def _bounded_option_text(value: str) -> str:
    if len(value) <= SLACK_OPTION_TEXT_MAX_CHARS:
        return value
    return f"{value[: SLACK_OPTION_TEXT_MAX_CHARS - 1]}…"


def _build_practice_flags_element(practice=None, *, is_dark_practice=False, has_social=False) -> dict:
    """Build checkboxes element for practice flags, properly handling initial_options.

    When practice is provided (edit modal), reads flags from it.
    When kwargs are provided (create modal), uses them directly.

    Args:
        practice: Practice information (optional, for edit modal)
        is_dark_practice: Default dark practice flag (for create modal)
        has_social: Default has_social flag (for create modal)

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

    # Determine flag values from practice object or kwargs
    dark_checked = practice.is_dark_practice if practice else is_dark_practice
    social_checked = practice.has_social if practice else has_social

    # Build initial options list - only include if there are selected options
    initial_options = []
    if dark_checked:
        initial_options.append({
            "text": {"type": "plain_text", "text": "🌙 Dark practice (headlamp required)"},
            "value": "is_dark_practice"
        })
    if social_checked:
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
        {
            "text": {"type": "plain_text", "text": _bounded_option_text(name)},
            "value": str(uid),
        }
        for uid, name, _ in eligible_users
    ]

    # Always include currently-assigned users, even if they are no longer in
    # the eligible list (e.g. missing a coach tag or Slack link). Otherwise the
    # modal cannot pre-select them and a re-save silently drops the assignment.
    eligible_ids = {str(uid) for uid, _, _ in eligible_users}
    for assignment in current_assignments:
        aid = str(assignment.user_id)
        if aid not in eligible_ids:
            label = _bounded_option_text(
                getattr(assignment, "display_name", None)
                or f"Unknown (uid {assignment.user_id})"
            )
            options.append({
                "text": {"type": "plain_text", "text": label},
                "value": aid,
            })
            eligible_ids.add(aid)

    element = {
        "type": "multi_static_select",
        "action_id": action_id,
        "placeholder": {"type": "plain_text", "text": placeholder},
        "options": options,
    }

    # Set initial selections from current assignments
    current_ids = {str(a.user_id) for a in current_assignments}
    initial = [opt for opt in options if opt["value"] in current_ids]
    if initial:
        element["initial_options"] = initial

    return element


def _build_activity_type_multi_select(
    action_id: str,
    placeholder: str,
    all_options: list,
    current_selections: list
) -> dict:
    """Build multi-select element for activities or types.

    Args:
        action_id: Slack action ID for the element
        placeholder: Placeholder text
        all_options: List of (id, name) tuples
        current_selections: List of current activity/type objects with .id and .name

    Returns:
        Slack multi_static_select element dict
    """
    options = [
        {
            "text": {
                "type": "plain_text",
                "text": _bounded_option_text(name),
            },
            "value": str(id)
        }
        for id, name in all_options
    ]

    current_ids = {(item.id if hasattr(item, 'id') else item) for item in current_selections}
    initial_options = [
        opt for opt in options
        if int(opt["value"]) in current_ids
    ]

    element = {
        "type": "multi_static_select",
        "action_id": action_id,
        "placeholder": {"type": "plain_text", "text": placeholder},
        "options": options
    }

    if initial_options:
        element["initial_options"] = initial_options

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
                "block_id": "notes_block",
                "optional": True,
                "label": {
                    "type": "plain_text",
                    "text": "Notes / Logistics"
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": "logistics_notes",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Weather, trail conditions, meeting spot, adjustments, etc."
                    },
                    "initial_value": practice.logistics_notes or ""
                }
            }
        ]
    }


def build_practice_edit_full_modal(
    practice: PracticeInfo,
    locations: list = None,
    eligible_coaches: list = None,
    eligible_leads: list = None,
    all_activities: list = None,
    all_types: list = None,
    *,
    reaction_editor,
    reaction_catalog,
    current_values=None,
) -> dict:
    """Build modal for full practice editing from collab channel.

    Includes all editable fields except date/time and practice types.
    Used by coaches/practices team to update practice details.

    Args:
        practice: Practice information
        locations: List of (id, name) tuples for location dropdown
        eligible_coaches: List of (user_id, name, slack_uid) tuples for coach selection
        eligible_leads: List of (user_id, name, slack_uid) tuples for lead selection
        all_activities: List of (id, name) tuples for activity multi-select
        all_types: List of (id, name) tuples for type multi-select

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
                "text": {
                    "type": "plain_text",
                    "text": _bounded_option_text(loc_name),
                },
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
        {"type": "divider"}
    ]

    # Add activities multi-select if provided
    if all_activities:
        blocks.append({
            "type": "input",
            "block_id": "activities_block",
            "dispatch_action": True,
            "optional": True,
            "label": {"type": "plain_text", "text": "Activities"},
            "element": _build_activity_type_multi_select(
                "activity_ids", "Select activities", all_activities, practice.activities
            )
        })

    # Add types multi-select if provided
    if all_types:
        blocks.append({
            "type": "input",
            "block_id": "types_block",
            "dispatch_action": True,
            "optional": True,
            "label": {"type": "plain_text", "text": "Practice Types"},
            "element": _build_activity_type_multi_select(
                "type_ids", "Select practice types", all_types, practice.practice_types
            )
        })

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

    # Add location and practice authoring blocks.
    blocks.extend([
        {
            "type": "input",
            "block_id": "location_block",
            "label": {"type": "plain_text", "text": "Location"},
            "element": location_element
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
                "max_length": 2500,
                "placeholder": {"type": "plain_text", "text": "e.g., 5 x 4min @ threshold (2min rest)"},
                "initial_value": practice.workout_description or ""
            }
        },
        {
            "type": "input",
            "block_id": "notes_block",
            "optional": True,
            "label": {"type": "plain_text", "text": "Notes / Logistics"},
            "element": {
                "type": "plain_text_input",
                "action_id": "logistics_notes",
                "multiline": True,
                "max_length": 2500,
                "placeholder": {
                    "type": "plain_text",
                    "text": "Weather, trail conditions, meeting spot, adjustments, etc."
                },
                "initial_value": practice.logistics_notes or ""
            }
        }
    ])
    blocks.extend(
        build_practice_reaction_blocks(
            reaction_editor,
            reaction_catalog,
            allow_restore=True,
        )
    )

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

    modal = {
        "type": "modal",
        "callback_id": "practice_edit_full",
        "private_metadata": encode_practice_reaction_metadata(
            mode="edit",
            context={"practice_id": practice.id},
            state=reaction_editor,
        ),
        "title": {"type": "plain_text", "text": "Edit Practice"},
        "submit": {"type": "plain_text", "text": "Save Changes"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": blocks
    }
    apply_current_view_values(modal["blocks"], current_values)
    return modal


def build_practice_create_modal(
    practice_date: 'datetime', default_time: str, locations: list = None,
    channel_id: str = None, message_ts: str = None,
    all_activities: list = None, all_types: list = None,
    slot_defaults: dict = None, silent_defaults: dict = None,
    eligible_coaches: list = None, eligible_leads: list = None,
    *,
    reaction_editor,
    reaction_catalog,
    current_values=None,
    view_mode="create",
    preview_config=None,
) -> dict:
    """Build modal for creating a new practice from weekly summary.

    Args:
        practice_date: Date for the new practice
        default_time: Default time string (e.g., "18:00")
        locations: List of (id, name) tuples for location dropdown
        channel_id: Channel where the summary post lives (for updating)
        message_ts: Timestamp of the summary post (for updating)
        all_activities: List of (id, name) tuples for activity multi-select
        all_types: List of (id, name) tuples for type multi-select
        slot_defaults: Dict of default field values from config (location_id, workout,
            coach_ids, lead_ids, etc.); coach_ids/lead_ids pre-select the pickers
        silent_defaults: Dict of defaults applied silently on submit (social_location_id)
        eligible_coaches: List of (user_id, name, slack_uid) tuples for the coach picker
        eligible_leads: List of (user_id, name, slack_uid) tuples for the lead picker
        reaction_editor: Prepared structured reaction working state
        reaction_catalog: Prepared global Settings reaction catalog
        current_values: Complete current Slack view state to preserve on rebuild
        view_mode: Metadata mode, either Create or Preview
        preview_config: Complete synthetic configuration for DB-free Preview rebuilds

    Returns:
        Slack modal view payload
    """
    date_str = practice_date.strftime('%A, %B %-d')
    defaults = slot_defaults or {}

    # Build metadata with date, channel, message_ts, and silent defaults
    metadata_dict = {
        'date': practice_date.strftime('%Y-%m-%d'),
        'channel_id': channel_id,
        'message_ts': message_ts
    }
    if silent_defaults:
        metadata_dict['silent'] = silent_defaults
    metadata_context = (
        {"preview": True}
        if view_mode == "preview"
        else metadata_dict
    )

    # Build location dropdown options
    location_options = []
    if locations:
        for loc_id, loc_name in locations:
            option = {
                "text": {
                    "type": "plain_text",
                    "text": _bounded_option_text(loc_name),
                },
                "value": str(loc_id)
            }
            location_options.append(option)

    # Build location element with optional default pre-selection
    if location_options:
        location_element = {
            "type": "static_select",
            "action_id": "location_id",
            "placeholder": {"type": "plain_text", "text": "Select a location"},
            "options": location_options
        }
        # Pre-select location from defaults
        default_location_id = defaults.get('location_id')
        if default_location_id:
            for opt in location_options:
                if opt["value"] == str(default_location_id):
                    location_element["initial_option"] = opt
                    break
    else:
        # Fallback to text input if no locations provided
        location_element = {
            "type": "plain_text_input",
            "action_id": "location_id",
            "placeholder": {"type": "plain_text", "text": "Enter location name"}
        }

    # Build blocks dynamically
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Creating practice for {date_str}*"
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
            "block_id": "time_block",
            "label": {"type": "plain_text", "text": "Time"},
            "element": {
                "type": "timepicker",
                "action_id": "practice_time",
                "initial_time": default_time,
                "placeholder": {"type": "plain_text", "text": "Select time"}
            }
        }
    ]

    # Workout (with optional default)
    workout_default = defaults.get('workout', '')
    workout_element = {
        "type": "plain_text_input",
        "action_id": "workout_description",
        "multiline": True,
        "max_length": 2500,
        "placeholder": {"type": "plain_text", "text": "e.g., 5 x 4min @ threshold (2min rest)"}
    }
    if workout_default:
        workout_element["initial_value"] = workout_default
    blocks.append({
        "type": "input",
        "block_id": "workout_block",
        "optional": True,
        "label": {"type": "plain_text", "text": "Main Workout"},
        "element": workout_element
    })

    # Activities multi-select (with optional defaults)
    if all_activities:
        default_activity_ids = defaults.get('activity_ids', [])
        blocks.append({
            "type": "input",
            "block_id": "activities_block",
            "dispatch_action": True,
            "optional": True,
            "label": {"type": "plain_text", "text": "Activities"},
            "element": _build_activity_type_multi_select(
                "activity_ids", "Select activities", all_activities, default_activity_ids
            )
        })

    # Types multi-select (with optional defaults)
    if all_types:
        default_type_ids = defaults.get('type_ids', [])
        blocks.append({
            "type": "input",
            "block_id": "types_block",
            "dispatch_action": True,
            "optional": True,
            "label": {"type": "plain_text", "text": "Practice Types"},
            "element": _build_activity_type_multi_select(
                "type_ids", "Select practice types", all_types, default_type_ids
            )
        })

    blocks.extend(
        build_practice_reaction_blocks(
            reaction_editor,
            reaction_catalog,
            allow_restore=False,
        )
    )

    # Coaches multi-select, pre-selected from slot defaults (coach_ids)
    if eligible_coaches:
        default_coaches = [SimpleNamespace(user_id=cid, display_name=None)
                           for cid in defaults.get('coach_ids', [])]
        blocks.append({
            "type": "input",
            "block_id": "coaches_block",
            "optional": True,
            "label": {"type": "plain_text", "text": "Coaches"},
            "element": _build_person_multi_select(
                "coach_ids", "Select coach(es)", eligible_coaches, default_coaches
            )
        })

    # Leads multi-select, pre-selected from slot defaults (lead_ids)
    if eligible_leads:
        default_leads = [SimpleNamespace(user_id=lid, display_name=None)
                         for lid in defaults.get('lead_ids', [])]
        blocks.append({
            "type": "input",
            "block_id": "leads_block",
            "optional": True,
            "label": {"type": "plain_text", "text": "Practice Leads"},
            "element": _build_person_multi_select(
                "lead_ids", "Select lead(s)", eligible_leads, default_leads
            )
        })

    # Flags (dark practice, social) with optional default
    default_is_dark = defaults.get('is_dark_practice', False)
    blocks.append({
        "type": "input",
        "block_id": "flags_block",
        "optional": True,
        "label": {"type": "plain_text", "text": "Options"},
        "element": _build_practice_flags_element(is_dark_practice=default_is_dark)
    })

    modal = {
        "type": "modal",
        "callback_id": "practice_create",
        "private_metadata": encode_practice_reaction_metadata(
            mode=view_mode,
            context=metadata_context,
            state=reaction_editor,
            preview_config=preview_config,
        ),
        "title": {"type": "plain_text", "text": "Add Practice"},
        "submit": {"type": "plain_text", "text": "Create Practice"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": blocks
    }
    apply_current_view_values(modal["blocks"], current_values)
    return modal


def build_practice_preview_modal(practice_date: 'datetime') -> dict:
    """Build a discard-only preview of the production practice create modal."""
    intervals = SimpleNamespace(
        id=1,
        name="Intervals",
        default_plan_reactions=[dict(EVERGREEN_PLAN_REACTION)],
    )
    run = SimpleNamespace(
        id=1,
        name="Run",
        default_plan_reactions=[
            {"emoji": "athletic_shoe", "label": "runner"}
        ],
    )
    rollerski = SimpleNamespace(
        id=2,
        name="Skate/Classic Rollerski",
        default_plan_reactions=[
            {"emoji": "hatching_chick", "label": "new rollerskier"},
            {
                "emoji": "older_adult::skin-tone-4",
                "label": "experienced rollerskier",
            },
        ],
    )
    strength = SimpleNamespace(
        id=3,
        name="Strength",
        default_plan_reactions=[],
    )
    practice_types = [intervals]
    activities = [run, rollerski, strength]
    selected_activities = [run, rollerski]
    reaction_editor = build_plan_reaction_editor_state(
        practice_types=practice_types,
        activities=selected_activities,
        saved_snapshot=None,
    ).state
    reaction_catalog = build_plan_reaction_catalog(
        practice_types,
        activities,
    )
    locations = [(1, "Theodore Wirth - Trailhead")]
    slot_defaults = {
        "location_id": 1,
        "activity_ids": [1, 2],
        "type_ids": [1],
        "coach_ids": [1],
        "lead_ids": [2],
    }
    eligible_coaches = [(1, "Preview Coach", "U_PREVIEW_COACH")]
    eligible_leads = [(2, "Preview Lead", "U_PREVIEW_LEAD")]
    preview_config = {
        "practice_date": practice_date.strftime("%Y-%m-%d"),
        "default_time": "18:15",
        "locations": [
            {"id": location_id, "name": name}
            for location_id, name in locations
        ],
        "practice_types": [
            {
                "id": source.id,
                "name": source.name,
                "default_plan_reactions": [
                    dict(pair) for pair in source.default_plan_reactions
                ],
            }
            for source in practice_types
        ],
        "activities": [
            {
                "id": source.id,
                "name": source.name,
                "default_plan_reactions": [
                    dict(pair) for pair in source.default_plan_reactions
                ],
            }
            for source in activities
        ],
        "slot_defaults": dict(slot_defaults),
        "eligible_coaches": [
            {"user_id": user_id, "name": name, "slack_uid": slack_uid}
            for user_id, name, slack_uid in eligible_coaches
        ],
        "eligible_leads": [
            {"user_id": user_id, "name": name, "slack_uid": slack_uid}
            for user_id, name, slack_uid in eligible_leads
        ],
    }
    modal = build_practice_create_modal(
        practice_date,
        "18:15",
        locations=locations,
        all_activities=[(source.id, source.name) for source in activities],
        all_types=[(source.id, source.name) for source in practice_types],
        slot_defaults=slot_defaults,
        eligible_coaches=eligible_coaches,
        eligible_leads=eligible_leads,
        reaction_editor=reaction_editor,
        reaction_catalog=reaction_catalog,
        view_mode="preview",
        preview_config=preview_config,
    )
    modal.update({
        "title": {"type": "plain_text", "text": "Practice Preview"},
        "submit": {"type": "plain_text", "text": "Close Preview"},
        "callback_id": "practice_preview",
    })
    return modal


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
