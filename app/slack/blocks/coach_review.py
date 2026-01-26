"""Block Kit builders for coach review and weekly summary messages."""

from datetime import datetime
from typing import Optional
from app.practices.interfaces import PracticeInfo, LeadRole

from app.slack.blocks.announcements import _get_day_suffix


def _practice_needs_attention(practice: PracticeInfo) -> bool:
    """Check if practice needs attention (missing coach, lead, or workout).

    Args:
        practice: PracticeInfo to check

    Returns:
        True if practice is missing coach, lead, or workout description
    """
    has_coach = any(l.role == LeadRole.COACH for l in (practice.leads or []))
    has_lead = any(l.role == LeadRole.LEAD for l in (practice.leads or []))
    has_workout = bool(practice.workout_description)

    return not (has_coach and has_lead and has_workout)


def build_coach_weekly_summary_blocks(
    practices: list[PracticeInfo],
    expected_days: list[dict],
    week_start: 'datetime'
) -> list[dict]:
    """Build Block Kit blocks for weekly coach review summary.

    Creates a compact summary showing all practices for the week with Edit buttons.
    For days without practices, shows placeholders with "Add Practice" buttons.

    Args:
        practices: List of PracticeInfo for existing practices
        expected_days: List of dicts with day/time/active from config
            e.g., [{"day": "tuesday", "time": "18:00", "active": true}]
        week_start: Monday of the week being displayed

    Returns:
        List of Slack Block Kit blocks
    """
    from datetime import timedelta

    blocks = []

    # Calculate week end for header
    week_end = week_start + timedelta(days=6)
    week_range = f"{week_start.strftime('%B %-d')}-{week_end.strftime('%-d, %Y')}"

    # Build practice lookup by day of week (list per day for multiple practices)
    practice_by_day = {}
    for p in practices:
        day_lower = p.date.strftime('%A').lower()
        if day_lower not in practice_by_day:
            practice_by_day[day_lower] = []
        practice_by_day[day_lower].append(p)

    # Track which practices have been shown (by practice ID)
    shown_practice_ids = set()

    # ==========================================================================
    # HEADER
    # ==========================================================================
    # Count practices needing attention
    incomplete_count = sum(1 for p in practices if _practice_needs_attention(p))

    header_text = f":clipboard: Coach Review: Week of {week_range}"
    if incomplete_count > 0:
        header_text += f" | :warning: {incomplete_count} need attention"

    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": header_text,
            "emoji": True
        }
    })

    blocks.append({"type": "divider"})

    # ==========================================================================
    # EACH EXPECTED DAY
    # ==========================================================================
    for day_config in expected_days:
        if not day_config.get('active', True):
            continue

        day_name = day_config['day'].lower()
        default_time = day_config.get('time', '18:00')

        # Calculate the actual date for this day of week
        days_map = {'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                    'friday': 4, 'saturday': 5, 'sunday': 6}
        day_offset = days_map.get(day_name, 0)
        day_date = week_start + timedelta(days=day_offset)

        # Find the next unshown practice for this day
        practice = None
        day_practices = practice_by_day.get(day_name, [])
        for p in day_practices:
            if p.id not in shown_practice_ids:
                practice = p
                shown_practice_ids.add(p.id)
                break

        if practice:
            # ==========================================================
            # EXISTING PRACTICE
            # ==========================================================
            day_num = practice.date.strftime('%-d')
            day_suffix = _get_day_suffix(int(day_num))
            time_str = practice.date.strftime('%I:%M %p').lstrip('0')
            day_full = practice.date.strftime('%A')
            month_short = practice.date.strftime('%b')

            # Location and types
            location_name = practice.location.name if practice.location else "TBD"
            location_spot = practice.location.spot if practice.location and practice.location.spot else None
            full_location = f"{location_name} - {location_spot}" if location_spot else location_name

            type_names = ", ".join([t.name for t in practice.practice_types]) if practice.practice_types else ""

            # Header line with date/time only (location/activities/types shown in fields section below)
            header_text = f":calendar: *{day_full}, {month_short} {day_num}{day_suffix} at {time_str}*"

            # Add warning badge if incomplete
            needs_attention = _practice_needs_attention(practice)
            if needs_attention:
                header_text += " :warning:"

            # Header section (no accessory - Edit button moved to bottom for mobile)
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": header_text
                }
            })

            # ==========================================================
            # TWO-COLUMN FIELDS: Location/Types + Warmup/Cooldown
            # ==========================================================
            fields = []

            # LEFT COLUMN: Location + Activities + Types
            location_col = f"*:round_pushpin: Location*\n{full_location}"
            if practice.activities:
                activity_names = ", ".join([a.name for a in practice.activities])
                location_col += f"\n:skier: {activity_names}"
            if type_names:
                location_col += f" | :snowflake: {type_names}"
            fields.append({"type": "mrkdwn", "text": location_col})

            # RIGHT COLUMN: Warmup + Cooldown (truncated to 40 chars each)
            warmup_cooldown = "*:fire: Warmup / :ice_cube: Cooldown*\n"
            if practice.warmup_description:
                warmup = practice.warmup_description[:40] + "..." if len(practice.warmup_description) > 40 else practice.warmup_description
                warmup_cooldown += f"{warmup}\n"
            else:
                warmup_cooldown += "_No warmup_\n"

            if practice.cooldown_description:
                cooldown = practice.cooldown_description[:40] + "..." if len(practice.cooldown_description) > 40 else practice.cooldown_description
                warmup_cooldown += cooldown
            else:
                warmup_cooldown += "_No cooldown_"
            fields.append({"type": "mrkdwn", "text": warmup_cooldown})

            blocks.append({
                "type": "section",
                "fields": fields
            })

            # ==========================================================
            # FULL-WIDTH WORKOUT SECTION (no truncation)
            # ==========================================================
            if practice.workout_description:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*:nerd_face: Workout*\n{practice.workout_description}"
                    }
                })
            else:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": ":warning: *Workout:* _Not entered yet - click Edit to add_"
                    }
                })

            # ==========================================================
            # CONTEXT: Flags + Coaches + Leads (de-emphasized, combined)
            # ==========================================================
            combined_parts = []

            # Flags
            if practice.is_dark_practice:
                combined_parts.append(":new_moon: Dark")
            if practice.has_social:
                combined_parts.append(":tropical_drink: Social")

            # Coaches (with warning if missing)
            coaches = [l for l in practice.leads if l.role == LeadRole.COACH]
            if coaches:
                coach_names = [f"<@{c.slack_user_id}>" if c.slack_user_id else c.display_name for c in coaches]
                combined_parts.append(f":male-teacher: {', '.join(coach_names)}")
            else:
                combined_parts.append(":warning: No coach")

            # Leads (with warning if missing)
            leads = [l for l in practice.leads if l.role == LeadRole.LEAD]
            if leads:
                lead_names = [f"<@{l.slack_user_id}>" if l.slack_user_id else l.display_name for l in leads]
                combined_parts.append(f":people_holding_hands: {', '.join(lead_names)}")
            else:
                combined_parts.append(":warning: No lead")

            blocks.append({
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": " | ".join(combined_parts)}]
            })

            # ==========================================================
            # EDIT BUTTON (at bottom for better mobile UX)
            # ==========================================================
            edit_button = {
                "type": "button",
                "text": {"type": "plain_text", "text": ":pencil2: Edit", "emoji": True},
                "action_id": "edit_practice_full",
                "value": str(practice.id)
            }
            if needs_attention:
                edit_button["style"] = "danger"

            blocks.append({
                "type": "actions",
                "elements": [edit_button]
            })

        else:
            # ==========================================================
            # PLACEHOLDER - NO PRACTICE FOR THIS DAY
            # ==========================================================
            day_num = day_date.strftime('%-d')
            day_suffix = _get_day_suffix(int(day_num))
            day_full = day_date.strftime('%A')
            month_short = day_date.strftime('%b')

            # Format time for display (e.g., "6:00 pm")
            slot_time = day_config.get('time', '18:00')
            try:
                display_time = datetime.strptime(slot_time, '%H:%M').strftime('%-I:%M %p').lower()
            except ValueError:
                display_time = slot_time

            # Section with accessory Add Practice button (single block, not section + actions)
            # Button value encodes date|day|time for slot-specific defaults lookup
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":calendar: *{day_full}, {month_short} {day_num}{day_suffix} at {display_time}* — _No practice scheduled_"
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":heavy_plus_sign: Add Practice", "emoji": True},
                    "action_id": "create_practice_from_summary",
                    "value": f"{day_date.strftime('%Y-%m-%d')}|{day_name}|{slot_time}",
                    "style": "primary"
                }
            })

        blocks.append({"type": "divider"})

    # ==========================================================================
    # FOOTER
    # ==========================================================================
    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": ":bulb: Click *Edit* to update workout details. Changes will notify this thread unless unchecked."
        }]
    })

    return blocks


def build_collab_practice_blocks(
    practice: PracticeInfo,
    approved: bool = False,
    approved_by: Optional[str] = None,
    approved_at: Optional[datetime] = None
) -> list[dict]:
    """Build Block Kit blocks for coach review post in #collab-coaches-practices.

    Shows practice details with Approve/Edit buttons for coaches to review
    before the practice is announced.

    Args:
        practice: Practice information
        approved: Whether the practice has been approved
        approved_by: Slack UID of approver (if approved)
        approved_at: Timestamp of approval (if approved)

    Returns:
        List of Slack Block Kit blocks
    """
    blocks = []

    # Format date and time
    day = practice.date.strftime('%A')  # e.g., "Sunday"
    short_month = practice.date.strftime('%b')  # e.g., "Dec"
    day_num = practice.date.strftime('%-d')  # e.g., "29"
    day_suffix = _get_day_suffix(int(day_num))
    time_str = practice.date.strftime('%I:%M %p').lstrip('0')  # e.g., "12:00 PM"

    # Location info
    location_name = practice.location.name if practice.location else "TBD"
    location_spot = practice.location.spot if practice.location and practice.location.spot else None
    full_location = f"{location_name} - {location_spot}" if location_spot else location_name

    # ==========================================================================
    # HEADER: Practice: Day, Month Day at Time
    # ==========================================================================
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": f":clipboard: Practice: {day}, {short_month} {day_num}{day_suffix} at {time_str}",
            "emoji": True
        }
    })

    # ==========================================================================
    # CONTEXT: Location and Practice Types
    # ==========================================================================
    context_parts = [f":round_pushpin: {full_location}"]
    if practice.practice_types:
        type_names = ", ".join([t.name for t in practice.practice_types])
        context_parts.append(f":ski: {type_names}")

    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": " | ".join(context_parts)}]
    })

    blocks.append({"type": "divider"})

    # ==========================================================================
    # WORKOUT DETAILS (full text, not truncated)
    # ==========================================================================
    if practice.warmup_description:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*:fire: Warmup*\n{practice.warmup_description}"
            }
        })

    if practice.workout_description:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*:nerd_face: Workout*\n{practice.workout_description}"
            }
        })

    if practice.cooldown_description:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*:ice_cube: Cooldown*\n{practice.cooldown_description}"
            }
        })

    # If no workout info at all, show placeholder
    if not any([practice.warmup_description, practice.workout_description, practice.cooldown_description]):
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "_No workout details entered yet. Click Edit to add._"
            }
        })

    blocks.append({"type": "divider"})

    # ==========================================================================
    # FLAGS (dark practice, social)
    # ==========================================================================
    flags = []
    if practice.is_dark_practice:
        flags.append(":crescent_moon: Dark practice")
    if practice.has_social:
        social_name = ""
        if practice.location and practice.location.social_location:
            social_name = f" at {practice.location.social_location.name}"
        flags.append(f":tropical_drink: Social after{social_name}")

    if flags:
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": " | ".join(flags)}]
        })

    # ==========================================================================
    # APPROVAL STATUS AND/OR BUTTONS
    # ==========================================================================
    if approved:
        # Show approval status
        approval_time = approved_at.strftime('%I:%M %p').lstrip('0') if approved_at else ""
        blocks.append({
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": f":white_check_mark: *Approved by <@{approved_by}>*" + (f" at {approval_time}" if approval_time else "")
            }]
        })
        # Still show Edit button after approval
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":pencil2: Edit", "emoji": True},
                    "action_id": "edit_practice_full",
                    "value": str(practice.id)
                }
            ]
        })
    else:
        # Show Approve and Edit buttons
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":white_check_mark: Approve", "emoji": True},
                    "style": "primary",
                    "action_id": "approve_practice",
                    "value": str(practice.id)
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":pencil2: Edit", "emoji": True},
                    "action_id": "edit_practice_full",
                    "value": str(practice.id)
                }
            ]
        })

    return blocks
