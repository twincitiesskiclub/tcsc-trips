"""Block Kit builders for practice announcements."""

from typing import Optional
from app.practices.interfaces import (
    PracticeInfo,
    WeatherConditions,
    TrailCondition,
    LeadRole,
)


def build_practice_announcement_blocks(
    practice: PracticeInfo,
    weather: Optional[WeatherConditions] = None,
    trail_conditions: Optional[TrailCondition] = None,
    rsvp_counts: Optional[dict[str, int]] = None
) -> list[dict]:
    """Build Block Kit blocks for practice announcement.

    Compact layout optimized to stay under Slack's ~10 block limit to avoid
    "View full message" collapse. Target: 8-9 blocks max.

    Args:
        practice: Practice information
        weather: Current weather conditions (if available)
        trail_conditions: Trail conditions (if available)
        rsvp_counts: Dict with keys 'going', 'maybe', 'not_going' (if available)

    Returns:
        List of Slack Block Kit blocks
    """
    blocks = []

    # Format date and time
    day = practice.date.strftime('%A')  # e.g., "Sunday"
    short_month = practice.date.strftime('%b')  # e.g., "Dec"
    day_num = practice.date.strftime('%-d')  # e.g., "29"
    day_suffix = _get_day_suffix(int(day_num))  # e.g., "th"
    time_str = practice.date.strftime('%I:%M %p').lstrip('0')  # e.g., "12:00 PM"

    # Get type and location info
    type_names = ", ".join([t.name for t in practice.practice_types]) if practice.practice_types else ""
    location_name = practice.location.name if practice.location else "TBD"
    location_spot = practice.location.spot if practice.location and practice.location.spot else None

    # Build full location string
    full_location = location_name
    if location_spot:
        full_location = f"{location_name} - {location_spot}"

    # ==========================================================================
    # HEADER: :clipboard: _TCSC_ • Day, Month Dayth at Time
    # ==========================================================================
    header_text = f":clipboard: _TCSC_ • {day}, {short_month} {day_num}{day_suffix} at {time_str}"

    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": f"*{header_text}*"}
    })

    # ==========================================================================
    # CONTEXT: Location | Practice Types | Social (if applicable)
    # ==========================================================================
    context_parts = [f":round_pushpin: {full_location}"]

    # Show activities (ski technique: Classic, Skate, etc.)
    if practice.activities:
        activity_names = ", ".join([a.name for a in practice.activities])
        context_parts.append(f":skier: {activity_names}")

    # Show practice types (workout type: Intervals, Distance, etc.)
    if type_names:
        context_parts.append(f":snowflake: {type_names}")

    # Add social info to context line if there's a social
    if practice.has_social:
        if practice.location and practice.location.social_location:
            social = practice.location.social_location
            social_text = f":tropical_drink: Social after at {social.name}"
            if social.google_maps_url:
                social_text += f" <{social.google_maps_url}|:world_map:>"
            context_parts.append(social_text)
        else:
            context_parts.append(":tropical_drink: Social after!")

    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": " | ".join(context_parts)
        }]
    })

    # ==========================================================================
    # WEATHER + TRAIL CONDITIONS (combined context line, right under location)
    # ==========================================================================
    conditions_parts = []

    if weather:
        # Temperature and conditions
        temp_text = f":thermometer: *{weather.temperature_f:.0f}°F*"
        if weather.feels_like_f and abs(weather.feels_like_f - weather.temperature_f) > 3:
            temp_text += f" (feels {weather.feels_like_f:.0f}°)"
        if weather.conditions_summary:
            temp_text += f" {weather.conditions_summary}"
        conditions_parts.append(temp_text)

        # Alert (if any)
        if weather.alerts:
            conditions_parts.append(f":warning: {weather.alerts[0].headline}")

    if trail_conditions:
        trail_text = f":ski: Trails: {trail_conditions.ski_quality.replace('_', ' ').title()}"
        if trail_conditions.groomed:
            trail_text += " (Groomed)"
        if trail_conditions.report_url:
            trail_text += f" <{trail_conditions.report_url}|Report>"
        conditions_parts.append(trail_text)

    if conditions_parts:
        blocks.append({
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": " | ".join(conditions_parts)
            }]
        })

    # ==========================================================================
    # WORKOUT SECTION (wide)
    # ==========================================================================
    if practice.workout_description:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*:nerd_face: Workout*\n{practice.workout_description}"
            }
        })

    # ==========================================================================
    # WARMUP / COOLDOWN (two columns)
    # ==========================================================================
    warmup_cooldown_fields = []
    if practice.warmup_description:
        warmup_cooldown_fields.append({
            "type": "mrkdwn",
            "text": f"*:fire: Warmup*\n{practice.warmup_description}"
        })
    if practice.cooldown_description:
        warmup_cooldown_fields.append({
            "type": "mrkdwn",
            "text": f"*:ice_cube: Cooldown*\n{practice.cooldown_description}"
        })

    if warmup_cooldown_fields:
        blocks.append({
            "type": "section",
            "fields": warmup_cooldown_fields
        })

    # ==========================================================================
    # LOCATION DETAILS: Address, Parking, Gear (combined section with fields)
    # ==========================================================================
    location_fields = []

    if practice.location and practice.location.address:
        location_fields.append({
            "type": "mrkdwn",
            "text": f"*:world_map: Address*\n{practice.location.address}"
        })

    if practice.location and practice.location.parking_notes:
        location_fields.append({
            "type": "mrkdwn",
            "text": f"*:car: Parking*\n{practice.location.parking_notes}"
        })

    # Build gear list
    gear_items = []
    if practice.activities:
        for activity in practice.activities:
            if hasattr(activity, 'gear_required') and activity.gear_required:
                if isinstance(activity.gear_required, list):
                    gear_items.extend(activity.gear_required)
                else:
                    gear_items.append(activity.gear_required)
    if gear_items:
        seen = set()
        unique_gear = [x for x in gear_items if not (x in seen or seen.add(x))]
        location_fields.append({
            "type": "mrkdwn",
            "text": f"*:school_satchel: Gear*\n{', '.join(unique_gear)}"
        })

    if location_fields:
        blocks.append({
            "type": "section",
            "fields": location_fields
        })

    # ==========================================================================
    # COACH / LEADS (context line)
    # ==========================================================================
    coaches = []
    leads = []
    if practice.leads:
        for lead in practice.leads:
            if lead.slack_user_id:
                mention = f"<@{lead.slack_user_id}>"
            else:
                mention = lead.display_name or "Unknown"
            if lead.role == LeadRole.COACH:
                coaches.append(mention)
            elif lead.role in (LeadRole.LEAD, LeadRole.ASSIST):
                leads.append(mention)

    coach_lead_parts = []
    if coaches:
        coach_lead_parts.append(f":male-teacher: Coach {', '.join(coaches)}")
    if leads:
        coach_lead_parts.append(f":people_holding_hands: Leads {', '.join(leads)}")

    if coach_lead_parts:
        blocks.append({
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": " | ".join(coach_lead_parts)
            }]
        })

    # ==========================================================================
    # RSVP CTA: Encourage emoji reactions
    # ==========================================================================
    # Check if this practice includes intervals
    has_intervals = any(t.name.lower() == 'intervals' for t in practice.practice_types) if practice.practice_types else False

    if has_intervals:
        cta_text = "Bop :white_check_mark: so we'll know you'll be there. :evergreen_tree: if you'll be there but doing endurance. Running late? Drop a comment in the thread. <!channel>"
    else:
        cta_text = "Bop :white_check_mark: so we'll know you'll be there. Running late? Drop a comment in the thread. <!channel>"

    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": cta_text
        }]
    })

    return blocks


def _get_day_suffix(day: int) -> str:
    """Get ordinal suffix for day number (st, nd, rd, th)."""
    if 11 <= day <= 13:
        return 'th'
    return {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')


def build_combined_lift_blocks(
    practices: list[PracticeInfo],
    weather_data: Optional[dict] = None
) -> list[dict]:
    """Build Block Kit blocks for combined lift announcement (multiple days).

    Follows the same structure as build_practice_announcement_blocks but
    combines multiple practices (same workout) with different times/coaches.

    Uses different checkmark emojis for each day's RSVP:
    - Day 1: white_check_mark
    - Day 2: ballot_box_with_check

    Args:
        practices: List of lift practices to combine (2-3 practices)
        weather_data: Optional dict mapping practice.id to WeatherConditions

    Returns:
        List of Slack Block Kit blocks
    """
    blocks = []
    weather_data = weather_data or {}

    if not practices:
        return blocks

    # Sort by date
    sorted_practices = sorted(practices, key=lambda p: p.date)
    first_practice = sorted_practices[0]

    # Get location info (assume same for all lifts)
    location = first_practice.location
    location_name = location.name if location else "TBD"
    location_spot = location.spot if location and location.spot else None
    full_location = f"{location_name} - {location_spot}" if location_spot else location_name

    # Build day list for header
    days = [p.date.strftime('%a') for p in sorted_practices]
    days_str = " + ".join(days)

    # RSVP emoji mapping (supports up to 3 lift days)
    rsvp_emojis = [":white_check_mark:", ":ballot_box_with_check:", ":heavy_check_mark:"]

    # ==========================================================================
    # HEADER: :weight_lifter: _TCSC Lift_ - Wed & Fri
    # ==========================================================================
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": f":weight_lifter: _TCSC Lift_ • {days_str}",
            "emoji": True
        }
    })

    # ==========================================================================
    # CONTEXT: Location | Practice Types
    # ==========================================================================
    context_parts = [f":round_pushpin: {full_location}"]
    type_names = ", ".join([t.name for t in first_practice.practice_types]) if first_practice.practice_types else ""
    if type_names:
        context_parts.append(f":muscle: {type_names}")

    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": " | ".join(context_parts)
        }]
    })

    # ==========================================================================
    # SCHEDULE: Show each day's date and time
    # ==========================================================================
    schedule_lines = []
    for practice in sorted_practices:
        day_name = practice.date.strftime('%A')
        short_month = practice.date.strftime('%b')
        day_num = practice.date.strftime('%-d')
        day_suffix = _get_day_suffix(int(day_num))
        time_str = practice.date.strftime('%I:%M %p').lstrip('0')

        schedule_lines.append(f"*{day_name}, {short_month} {day_num}{day_suffix}* at {time_str}")

    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": " • ".join(schedule_lines)
        }]
    })

    # ==========================================================================
    # WORKOUT SECTION (shared - use first practice's workout)
    # ==========================================================================
    if first_practice.workout_description:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*:nerd_face: Workout*\n{first_practice.workout_description}"
            }
        })

    # ==========================================================================
    # WARMUP / COOLDOWN (two columns, shared)
    # ==========================================================================
    warmup_cooldown_fields = []
    if first_practice.warmup_description:
        warmup_cooldown_fields.append({
            "type": "mrkdwn",
            "text": f"*:fire: Warmup*\n{first_practice.warmup_description}"
        })
    if first_practice.cooldown_description:
        warmup_cooldown_fields.append({
            "type": "mrkdwn",
            "text": f"*:ice_cube: Cooldown*\n{first_practice.cooldown_description}"
        })

    if warmup_cooldown_fields:
        blocks.append({
            "type": "section",
            "fields": warmup_cooldown_fields
        })

    # ==========================================================================
    # LOCATION DETAILS: Address, Parking (shared)
    # ==========================================================================
    location_fields = []

    if location and location.address:
        location_fields.append({
            "type": "mrkdwn",
            "text": f"*:world_map: Address*\n{location.address}"
        })

    if location and location.parking_notes:
        location_fields.append({
            "type": "mrkdwn",
            "text": f"*:car: Parking*\n{location.parking_notes}"
        })

    if location_fields:
        blocks.append({
            "type": "section",
            "fields": location_fields
        })

    # ==========================================================================
    # COACH / LEADS (per day if different)
    # ==========================================================================
    coach_lead_parts = []
    for i, practice in enumerate(sorted_practices):
        emoji = rsvp_emojis[i] if i < len(rsvp_emojis) else ":white_check_mark:"
        day_short = practice.date.strftime('%a')

        coaches = []
        leads = []
        if practice.leads:
            for lead in practice.leads:
                if lead.slack_user_id:
                    mention = f"<@{lead.slack_user_id}>"
                else:
                    mention = lead.display_name or "Unknown"
                if lead.role == LeadRole.COACH:
                    coaches.append(mention)
                elif lead.role in (LeadRole.LEAD, LeadRole.ASSIST):
                    leads.append(mention)

        if coaches or leads:
            day_coaches = f"{day_short}: "
            parts = []
            if coaches:
                parts.append(f":male-teacher: {', '.join(coaches)}")
            if leads:
                parts.append(f":people_holding_hands: {', '.join(leads)}")
            day_coaches += " ".join(parts)
            coach_lead_parts.append(day_coaches)

    if coach_lead_parts:
        blocks.append({
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": " | ".join(coach_lead_parts)
            }]
        })

    # ==========================================================================
    # RSVP CTA
    # ==========================================================================
    rsvp_instructions = []
    for i, practice in enumerate(sorted_practices):
        emoji = rsvp_emojis[i] if i < len(rsvp_emojis) else ":white_check_mark:"
        day_short = practice.date.strftime('%a')
        time_str = practice.date.strftime('%I:%M %p').lstrip('0')
        rsvp_instructions.append(f"{emoji} {day_short} ({time_str})")

    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": f"RSVP: {' | '.join(rsvp_instructions)} — so we know you'll be there! <!channel>"
        }]
    })

    return blocks
