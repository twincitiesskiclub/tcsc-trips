"""Block Kit builders for App Home tab."""

from typing import Optional
from app.practices.interfaces import PracticeInfo, PracticeStatus

from app.slack.blocks.dispatch import build_dispatch_submission_section


def build_app_home_blocks(
    upcoming_practices: list[PracticeInfo],
    user_rsvps: dict[int, str],
    user_lead_practices: list[int],
    rsvp_counts: Optional[dict[int, dict[str, int]]] = None
) -> list[dict]:
    """Build blocks for the App Home tab.

    Args:
        upcoming_practices: List of upcoming practices (next 14 days)
        user_rsvps: Dict mapping practice_id to RSVP status
        user_lead_practices: List of practice IDs where user is a lead
        rsvp_counts: Optional dict mapping practice_id to RSVP counts dict

    Returns:
        List of Slack Block Kit blocks
    """
    blocks = []
    rsvp_counts = rsvp_counts or {}

    # Header with club branding
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": "Twin Cities Ski Club Practices",
            "emoji": True
        }
    })

    blocks.append({"type": "divider"})

    # User's lead assignments (highlight section)
    lead_practices = [p for p in upcoming_practices if p.id in user_lead_practices]
    if lead_practices:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*You're Leading*"
            }
        })

        for practice in lead_practices:
            date_str = practice.date.strftime('%A, %b %-d, %Y')
            time_str = practice.date.strftime('%I:%M %p').lstrip('0')
            location = practice.location.name if practice.location else "TBD"

            lead_text = f"*{date_str}* at {time_str} CT\n:round_pushpin: {location}"

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": lead_text
                }
            })

        blocks.append({"type": "divider"})

    # Upcoming practices header
    practice_count = len(upcoming_practices)
    header_text = f"*Upcoming Practices* ({practice_count} in next 14 days)"
    if practice_count > 10:
        header_text += " - showing first 10"
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": header_text
        }
    })

    if not upcoming_practices:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "_No practices scheduled. Check back soon!_"
            }
        })
    else:
        for practice in upcoming_practices[:10]:  # Limit to 10
            practice_rsvp_counts = rsvp_counts.get(practice.id, {})
            blocks.extend(_build_practice_card(practice, user_rsvps, user_lead_practices, practice_rsvp_counts))

    # Add Submit to Dispatch section
    blocks.extend(build_dispatch_submission_section())

    return blocks


def _build_practice_card(
    practice: PracticeInfo,
    user_rsvps: dict[int, str],
    user_lead_practices: list[int],
    rsvp_counts: Optional[dict[str, int]] = None
) -> list[dict]:
    """Build a compact practice card.

    Target structure (2-3 blocks per practice):
        *Tuesday, Jan 15* at 6:00 PM CT
        Theodore Wirth - Trailhead 4 :crescent_moon: :beers:
        Skate | All Levels
        :white_check_mark: 8 going

        [RSVP button]
        ---

    Returns a list of blocks for a single practice.
    """
    blocks = []
    rsvp_counts = rsvp_counts or {}

    # Check if cancelled
    is_cancelled = practice.status == PracticeStatus.CANCELLED

    # Date formatting (include year for clarity)
    date_str = practice.date.strftime('%A, %b %-d, %Y')
    time_str = practice.date.strftime('%I:%M %p').lstrip('0')

    # Location info
    location_name = practice.location.name if practice.location else "TBD"
    location_spot = practice.location.spot if practice.location and practice.location.spot else None

    # Build badges (meaningful indicators only)
    badges = []
    if practice.is_dark_practice:
        badges.append(":crescent_moon:")
    if practice.has_social:
        badges.append(":beers:")

    badge_str = " ".join(badges) if badges else ""

    # Get technique from activities (e.g., "Classic", "Skate")
    technique = ""
    if practice.activities:
        activity_names = [a.name for a in practice.activities]
        technique = ", ".join(activity_names)

    # Get skill level from practice types (e.g., "All Levels", "Intervals")
    skill_level = ""
    if practice.practice_types:
        type_names = [t.name for t in practice.practice_types]
        skill_level = ", ".join(type_names)

    # RSVP status for user
    rsvp_status = user_rsvps.get(practice.id)

    if is_cancelled:
        # Cancelled practice - strikethrough and muted
        card_text = f"~*{date_str}*~ at ~{time_str} CT~\n:no_entry_sign: *CANCELLED*"
        if practice.cancellation_reason:
            card_text += f"\n_{practice.cancellation_reason}_"

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": card_text
            }
        })
    else:
        # Build compact card text
        # Line 1: Date and time
        card_lines = [f"*{date_str}* at {time_str} CT"]

        # Line 2: Location with badges
        location_line = f":round_pushpin: {location_name}"
        if location_spot:
            location_line += f" - {location_spot}"
        if badge_str:
            location_line += f" {badge_str}"
        card_lines.append(location_line)

        # Line 3: Technique | Skill level (if available)
        info_parts = []
        if technique:
            info_parts.append(technique)
        if skill_level:
            info_parts.append(skill_level)
        if info_parts:
            card_lines.append(" | ".join(info_parts))

        # Line 4: RSVP count (going only, keep it simple)
        going_count = rsvp_counts.get('going', 0)
        if going_count > 0:
            card_lines.append(f":white_check_mark: {going_count} going")

        card_text = "\n".join(card_lines)

        # Build RSVP button - show current status or prompt to RSVP
        if rsvp_status == 'going':
            button_text = ":white_check_mark: Going"
            button_style = None  # No special style, already confirmed
        elif rsvp_status == 'maybe':
            button_text = ":grey_question: Maybe"
            button_style = None
        elif rsvp_status == 'not_going':
            button_text = ":x: Not Going"
            button_style = None
        else:
            button_text = "RSVP"
            button_style = "primary"  # Encourage action

        button_block = {
            "type": "button",
            "text": {
                "type": "plain_text",
                "text": button_text,
                "emoji": True
            },
            "action_id": "home_rsvp",
            "value": str(practice.id)
        }
        if button_style:
            button_block["style"] = button_style

        # Single section with text and button accessory
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": card_text
            },
            "accessory": button_block
        })

    # Divider between practices
    blocks.append({"type": "divider"})

    return blocks
