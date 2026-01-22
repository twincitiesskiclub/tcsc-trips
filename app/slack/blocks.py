"""Slack Block Kit builders for practice-related messages."""

from datetime import datetime
from typing import Optional
from app.practices.interfaces import (
    PracticeInfo,
    WeatherConditions,
    TrailCondition,
    CancellationProposal,
    PracticeEvaluation,
    LeadRole,
    PracticeStatus
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
    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": "Bop that :white_check_mark: so we'll know you'll be there. If you're running late, drop a comment in the thread. <!channel>"
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
    - Day 1: ✅ white_check_mark
    - Day 2: ☑️ ballot_box_with_check

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
    # HEADER: :weight_lifter: _TCSC Lift_ • Wed & Fri
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

            # Header line with date/time/location
            header_text = f":calendar: *{day_full}, {month_short} {day_num}{day_suffix} at {time_str}*"
            context_parts = [f":round_pushpin: {full_location}"]

            # Show activities (ski technique: Classic, Skate, etc.)
            if practice.activities:
                activity_names = ", ".join([a.name for a in practice.activities])
                context_parts.append(f":skier: {activity_names}")

            # Show practice types (workout type: Intervals, Distance, etc.)
            if type_names:
                context_parts.append(f":snowflake: {type_names}")

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{header_text}\n{' | '.join(context_parts)}"
                }
            })

            # Workout details (combined into one block)
            workout_lines = []
            if practice.warmup_description:
                # Truncate long descriptions
                warmup = practice.warmup_description[:100] + "..." if len(practice.warmup_description) > 100 else practice.warmup_description
                workout_lines.append(f":fire: *Warmup:* {warmup}")
            if practice.workout_description:
                workout = practice.workout_description[:150] + "..." if len(practice.workout_description) > 150 else practice.workout_description
                workout_lines.append(f":nerd_face: *Workout:* {workout}")
            if practice.cooldown_description:
                cooldown = practice.cooldown_description[:100] + "..." if len(practice.cooldown_description) > 100 else practice.cooldown_description
                workout_lines.append(f":ice_cube: *Cooldown:* {cooldown}")

            if workout_lines:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "\n".join(workout_lines)
                    }
                })
            else:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "_No workout details yet. Click Edit to add._"
                    }
                })

            # Flags (dark practice, social)
            flags = []
            if practice.is_dark_practice:
                flags.append(":new_moon: Dark practice")
            if practice.social_location:
                flags.append(f":tropical_drink: Social after")

            if flags:
                blocks.append({
                    "type": "context",
                    "elements": [{
                        "type": "mrkdwn",
                        "text": " | ".join(flags)
                    }]
                })

            # Coach/Lead display
            coach_lead_parts = []
            coaches = [l for l in practice.leads if l.role == LeadRole.COACH]
            leads = [l for l in practice.leads if l.role == LeadRole.LEAD]

            if coaches:
                coach_names = [f"<@{c.slack_user_id}>" if c.slack_user_id else c.display_name for c in coaches]
                coach_lead_parts.append(f":male-teacher: {', '.join(coach_names)}")

            if leads:
                lead_names = [f"<@{l.slack_user_id}>" if l.slack_user_id else l.display_name for l in leads]
                coach_lead_parts.append(f":people_holding_hands: {', '.join(lead_names)}")

            if coach_lead_parts:
                blocks.append({
                    "type": "context",
                    "elements": [{
                        "type": "mrkdwn",
                        "text": " | ".join(coach_lead_parts)
                    }]
                })

            # Edit button
            blocks.append({
                "type": "actions",
                "elements": [{
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":pencil2: Edit", "emoji": True},
                    "action_id": "edit_practice_full",
                    "value": str(practice.id)
                }]
            })

        else:
            # ==========================================================
            # PLACEHOLDER - NO PRACTICE FOR THIS DAY
            # ==========================================================
            day_num = day_date.strftime('%-d')
            day_suffix = _get_day_suffix(int(day_num))
            day_full = day_date.strftime('%A')
            month_short = day_date.strftime('%b')

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":calendar: *{day_full}, {month_short} {day_num}{day_suffix}* — _No practice scheduled_"
                }
            })

            # Add Practice button with date as value
            blocks.append({
                "type": "actions",
                "elements": [{
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":heavy_plus_sign: Add Practice", "emoji": True},
                    "action_id": "create_practice_from_summary",
                    "value": day_date.strftime('%Y-%m-%d')
                }]
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
        expires_str = proposal.expires_at.strftime('%I:%M %p')
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


def build_weekly_summary_blocks(
    practices: list[PracticeInfo],
    weather_data: Optional[dict] = None
) -> list[dict]:
    """Build blocks for weekly practice summary.

    Creates a visually appealing, scannable summary grouped by day with
    weather info and social indicators.

    Args:
        practices: List of upcoming practices
        weather_data: Optional dict mapping practice.id to weather info dict
                      with keys: temp_f, feels_like_f, conditions, precipitation_chance

    Returns:
        List of Slack Block Kit blocks
    """
    from itertools import groupby

    blocks = []
    weather_data = weather_data or {}

    # Calculate week date range from practices
    if practices:
        sorted_dates = sorted([p.date for p in practices])
        start_date = sorted_dates[0]
        end_date = sorted_dates[-1]
        # Format: "Week of January 6-12, 2025"
        if start_date.month == end_date.month:
            week_range = f"Week of {start_date.strftime('%B')} {start_date.day}-{end_date.day}, {start_date.year}"
        else:
            week_range = f"Week of {start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}"
    else:
        week_range = "This Week's Practices"

    # Header
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": week_range,
            "emoji": True
        }
    })

    # Subtitle
    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": ":ski: *TCSC Practice Schedule*"
        }]
    })

    blocks.append({"type": "divider"})

    if not practices:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "No practices scheduled this week."
            }
        })
        return blocks

    # Sort practices by date
    sorted_practices = sorted(practices, key=lambda p: p.date)

    # Group by day
    for day_date, day_practices_iter in groupby(sorted_practices, key=lambda p: p.date.date()):
        day_practices = list(day_practices_iter)

        # Day header: 📅 Tuesday, Jan 7
        day_header = f":calendar: *{day_date.strftime('%A, %b %-d')}*"
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": day_header
            }
        })

        # Each practice for this day
        for practice in day_practices:
            practice_lines = []

            # Check if cancelled or holiday
            is_cancelled = practice.status == PracticeStatus.CANCELLED
            is_holiday = (practice.cancellation_reason and
                          'holiday' in practice.cancellation_reason.lower())

            if is_cancelled:
                # Cancelled practice - show in italics
                if is_holiday:
                    practice_lines.append(f":christmas_tree: _No Practice — {practice.cancellation_reason or 'Happy Holidays!'}_")
                else:
                    practice_lines.append(f":no_entry_sign: _Cancelled — {practice.cancellation_reason or 'See announcements'}_")
            else:
                # Active practice
                # Time with AM/PM emoji
                hour = practice.date.hour
                time_emoji = ":sunrise:" if hour < 12 else ":crescent_moon:"
                time_str = practice.date.strftime('%-I:%M %p').lower()

                # Activities/types
                if practice.practice_types:
                    activities = ", ".join([t.name for t in practice.practice_types])
                elif practice.activities:
                    activities = ", ".join([a.name for a in practice.activities])
                else:
                    activities = "Practice"

                practice_lines.append(f"{time_emoji} *{time_str}* — {activities}")

                # Location
                location = practice.location.name if practice.location else "TBD"
                practice_lines.append(f":round_pushpin: {location}")

                # Weather (if available)
                weather = weather_data.get(practice.id)
                if weather:
                    temp = weather.get('temp_f', weather.get('temperature_f'))
                    conditions = weather.get('conditions', weather.get('conditions_summary', ''))
                    if temp is not None:
                        weather_line = f":thermometer: {int(temp)}°F"
                        if conditions:
                            weather_line += f", {conditions}"
                        practice_lines.append(weather_line)

                # Social indicator
                if practice.has_social:
                    if practice.social_location:
                        practice_lines.append(f":beers: Social after at {practice.social_location.name}")
                    else:
                        practice_lines.append(":beers: Social after!")

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "\n".join(practice_lines)
                }
            })

        blocks.append({"type": "divider"})

    # Footer with @channel
    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": ":memo: Daily details posted Tue-Thu | <!channel>"
        }]
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
    # HEADER: 📋 Practice: Day, Month Day at Time
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


def build_daily_practice_recap_blocks(
    evaluations: list[dict],
    has_proposals: bool = False
) -> list[dict]:
    """Build Block Kit blocks for daily practice recap.

    Posted to #practices-core at 7am daily when there are practices scheduled.
    Shows weather, trail conditions, lead status, and any warnings for each practice.

    Args:
        evaluations: List of dicts with keys:
            - practice: PracticeInfo
            - evaluation: PracticeEvaluation (or None)
            - summary: str (generated summary)
            - is_go: bool
            - proposal_id: int (if cancellation proposed)
        has_proposals: Whether any cancellation proposals were created

    Returns:
        List of Slack Block Kit blocks
    """
    blocks = []

    # Header
    today_str = datetime.now().strftime('%A, %B %-d')
    header_emoji = ":warning:" if has_proposals else ":clipboard:"
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": f"{header_emoji} Practice Conditions - {today_str}",
            "emoji": True
        }
    })

    if not evaluations:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "_No practices scheduled for today._"
            }
        })
        return blocks

    # Summary line
    total = len(evaluations)
    safe = sum(1 for e in evaluations if e.get('is_go', True))
    proposed = sum(1 for e in evaluations if e.get('proposal_id'))

    summary_parts = [f"*{total} practice{'s' if total != 1 else ''}* scheduled today"]
    if proposed > 0:
        summary_parts.append(f":warning: {proposed} cancellation proposal{'s' if proposed != 1 else ''}")
    elif safe == total:
        summary_parts.append(":white_check_mark: All conditions look good")

    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": " | ".join(summary_parts)}]
    })

    blocks.append({"type": "divider"})

    # Each practice
    for eval_data in evaluations:
        practice = eval_data.get('practice')
        evaluation = eval_data.get('evaluation')
        summary = eval_data.get('summary', '')
        is_go = eval_data.get('is_go', True)
        proposal_id = eval_data.get('proposal_id')

        if not practice:
            continue

        # Practice header line
        time_str = practice.date.strftime('%I:%M %p').lstrip('0')
        location = practice.location.name if practice.location else "TBD"
        status_emoji = ":warning:" if not is_go else ":white_check_mark:"

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{status_emoji} *{time_str}* at *{location}*"
            }
        })

        # Weather and conditions
        conditions_parts = []

        if evaluation and evaluation.weather:
            w = evaluation.weather
            temp_text = f":thermometer: {w.temperature_f:.0f}°F"
            if w.feels_like_f and abs(w.feels_like_f - w.temperature_f) > 3:
                temp_text += f" (feels {w.feels_like_f:.0f}°)"
            conditions_parts.append(temp_text)

            if w.wind_speed_mph:
                wind_text = f":dash: {w.wind_speed_mph:.0f} mph"
                if w.wind_gust_mph and w.wind_gust_mph > w.wind_speed_mph:
                    wind_text += f" (gusts {w.wind_gust_mph:.0f})"
                conditions_parts.append(wind_text)

            if w.precipitation_chance and w.precipitation_chance > 20:
                conditions_parts.append(f":cloud_with_rain: {w.precipitation_chance:.0f}%")

        if evaluation and evaluation.trail_conditions:
            t = evaluation.trail_conditions
            trail_text = f":ski: {t.ski_quality.replace('_', ' ').title()}"
            if t.groomed:
                trail_text += " (groomed)"
            conditions_parts.append(trail_text)

        if conditions_parts:
            blocks.append({
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": " | ".join(conditions_parts)}]
            })

        # Lead status
        if evaluation:
            lead_status = []
            if evaluation.has_confirmed_lead:
                lead_status.append(":white_check_mark: Lead confirmed")
            else:
                lead_status.append(":grey_question: Lead not confirmed")

            if evaluation.has_posted_workout:
                lead_status.append(":memo: Workout posted")

            if lead_status:
                blocks.append({
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": " | ".join(lead_status)}]
                })

        # Violations (if any)
        if evaluation and evaluation.violations:
            violation_text = ""
            for v in evaluation.violations:
                icon = ":warning:" if v.severity == "warning" else ":x:"
                violation_text += f"{icon} {v.message}\n"

            blocks.append({
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": violation_text.strip()}]
            })

        # Summary / recommendation
        if summary:
            blocks.append({
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f"_{summary}_"}]
            })

        # If there's a proposal, add action buttons
        if proposal_id and proposal_id != 'DRY_RUN':
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Approve Cancellation"},
                        "style": "danger",
                        "action_id": "cancellation_approve",
                        "value": str(proposal_id)
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Keep Practice"},
                        "style": "primary",
                        "action_id": "cancellation_reject",
                        "value": str(proposal_id)
                    }
                ]
            })

        blocks.append({"type": "divider"})

    return blocks


def build_dispatch_submission_section() -> list[dict]:
    """Build the Submit to Dispatch section for App Home.

    Creates a section with information about the Weekly Dispatch newsletter
    and a button to open the submission modal.

    Returns:
        List of Slack Block Kit blocks for the dispatch section.
    """
    return [
        {"type": "divider"},
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Weekly Dispatch",
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    ":newspaper: *Share your story with the club!*\n\n"
                    "Submit member spotlights, event announcements, stories, "
                    "or tips for the Weekly Dispatch newsletter."
                )
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": ":memo: Submit to Dispatch",
                        "emoji": True
                    },
                    "style": "primary",
                    "action_id": "open_dispatch_modal",
                    "value": "submit_dispatch"
                }
            ]
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "_You can also use `/dispatch` from any channel._"
                }
            ]
        }
    ]
