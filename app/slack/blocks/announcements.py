"""Block Kit builders for practice announcements."""

from datetime import timedelta
from typing import Optional
from urllib.parse import quote_plus

from app.practices.interfaces import (
    AnnouncementConditions,
    LeadRole,
    PracticeInfo,
    TrailCondition,
    WeatherConditions,
)
from app.practices.plan_reactions import format_plan_reaction_legend
from app.slack.blocks.text import (
    SECTION_TEXT_MAX,
    guard_fallback_text,
    guard_slack_blocks,
    truncate_slack_text,
)
from app.utils import utc_naive_to_central_naive


_SPACER = "\n\u200b"


def _activity_label(activities) -> str:
    """Header activity label. Names are pre-normalized in the DB, so join them
    verbatim. Falls back to 'Practice' when no activity is set."""
    names = [a.name for a in (activities or []) if getattr(a, "name", None)]
    if not names:
        return "Practice"
    return " + ".join(names)


def _join_block_groups(groups):
    blocks = []
    for group in groups:
        if not group:
            continue
        if blocks:
            blocks.append({"type": "divider"})
        blocks.extend(group)
    return blocks


def _practice_end(practice, duration_minutes):
    return practice.date + timedelta(minutes=duration_minutes)


def _sunset_local(daylight):
    sunset = getattr(daylight, "sunset", None) if daylight else None
    return utc_naive_to_central_naive(sunset) if sunset else None


def _requires_headlamp(practice, daylight, duration_minutes):
    if getattr(practice, "is_dark_practice", False):
        return True
    sunset_local = _sunset_local(daylight)
    return bool(
        sunset_local
        and _practice_end(practice, duration_minutes) >= sunset_local
    )


def _urgent_exception_lines(practice, conditions, announcement_notice=None):
    lines = []
    if announcement_notice:
        lines.append(announcement_notice)

    for alert in (getattr(conditions.weather, "alerts", None) or []):
        headline = getattr(alert, "headline", None) or getattr(alert, "event", None)
        if headline:
            lines.append(f"⚠️ {headline}")

    if conditions.air_quality is not None and conditions.air_quality >= 101:
        lines.append(f"🌫️ Air quality {conditions.air_quality}")

    if _requires_headlamp(
        practice, conditions.daylight, conditions.duration_minutes
    ):
        sunset_local = _sunset_local(conditions.daylight)
        lines.append(
            f"🔦 Headlamp required · Sunset {sunset_local.strftime('%-I:%M %p')}"
            if sunset_local
            else "🔦 Headlamp required"
        )
    return lines


def build_practice_announcement_blocks(
    practice,
    conditions: AnnouncementConditions,
    *,
    announcement_notice=None,
) -> list[dict]:
    """Build the standalone practice announcement from one conditions snapshot."""
    header_group = [{
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": (
                f"{practice.date:%A} · {_activity_label(practice.activities)} at "
                f"{practice.date.strftime('%-I:%M %p')}"
            ),
            "emoji": True,
        },
    }]

    urgent = _urgent_exception_lines(
        practice, conditions, announcement_notice=announcement_notice
    )
    if urgent:
        header_group.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "\n".join(urgent) + _SPACER},
        })

    location_name = practice.location.name if practice.location else "TBD"
    spot = (
        practice.location.spot
        if practice.location and practice.location.spot
        else None
    )
    where_text = f"*Where:* {location_name + (' - ' + spot if spot else '')}"
    address = _address_link(practice.location) if practice.location else None
    if address:
        where_text += f"\n📍 {address}"
    header_group.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": where_text + _SPACER},
    })

    type_names = ", ".join(
        item.name for item in (practice.practice_types or [])
    )
    workout_label = f"*Workout · {type_names}*" if type_names else "*Workout*"
    workout_prefix = f"{workout_label}\n"
    workout = (
        str(practice.workout_description).strip()
        if getattr(practice, "workout_description", None)
        else "Workout details coming soon."
    )
    workout = truncate_slack_text(
        workout,
        SECTION_TEXT_MAX - len(workout_prefix) - len(_SPACER),
        field="workout_description",
        surface="practice_announcement",
        practice_id=practice.id,
    )
    workout_group = [{
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": workout_prefix + workout + _SPACER,
        },
    }]

    if getattr(practice, "logistics_notes", None):
        notes_prefix = "*📌 Notes*\n"
        notes = truncate_slack_text(
            practice.logistics_notes,
            SECTION_TEXT_MAX - len(notes_prefix) - len(_SPACER),
            field="logistics_notes",
            surface="practice_announcement",
            practice_id=practice.id,
        )
        workout_group.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": notes_prefix + notes + _SPACER,
            },
        })

    if practice.has_social:
        social = getattr(practice, "social_location", None)
        social_text = (
            f"🍹 *Social after at {social.name}*"
            if social and getattr(social, "name", None)
            else "🍹 *Social after!*"
        )
        workout_group.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": social_text + _SPACER},
        })

    rsvp_lines = ["Bop ✅ if you're coming."]
    if getattr(practice, "plan_reactions", None):
        rsvp_lines.extend([
            "",
            "*Your Practice Plan:*",
            format_plan_reaction_legend(practice.plan_reactions),
        ])
    ending_group = [{
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": "\n".join(rsvp_lines)}],
    }]

    coaches, leads = [], []
    for lead in (practice.leads or []):
        mention = (
            f"<@{lead.slack_user_id}>"
            if lead.slack_user_id
            else lead.display_name or "Unknown"
        )
        role_name = getattr(lead.role, "name", str(lead.role)).upper()
        if role_name == "COACH":
            coaches.append(mention)
        elif role_name in {"LEAD", "ASSIST"}:
            leads.append(mention)
    lead_parts = []
    if coaches:
        lead_parts.append(f"👨‍🏫 Coach {', '.join(coaches)}")
    if leads:
        lead_parts.append(f"🧑‍🤝‍🧑 Leads {', '.join(leads)}")
    if lead_parts:
        ending_group.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": " · ".join(lead_parts)}
            ],
        })

    return guard_slack_blocks(
        _join_block_groups([header_group, workout_group, ending_group]),
        surface="practice_announcement",
        practice_id=practice.id,
    )


def _gear_list(practice) -> list[str]:
    items = []
    for activity in (practice.activities or []):
        gear = getattr(activity, "gear_required", None)
        if not gear:
            continue
        items.extend(gear if isinstance(gear, list) else [gear])
    seen = set()
    return [item for item in items if not (item in seen or seen.add(item))]


def _details_content(practice, conditions):
    parking = practice.location.parking_notes if practice.location else None
    gear = _gear_list(practice)
    block_conditions = []
    plain_conditions = []

    weather = conditions.weather
    if weather:
        temperature = f"🌡️ {weather.temperature_f:.0f}°F"
        feels_like = getattr(weather, "feels_like_f", None)
        if feels_like is not None and abs(feels_like - weather.temperature_f) > 3:
            temperature += f" (feels {feels_like:.0f}°)"
        if getattr(weather, "conditions_summary", None):
            temperature += f", {weather.conditions_summary}"
        block_conditions.append(temperature)
        plain_conditions.append(temperature)

        if getattr(weather, "wind_speed_mph", None):
            direction = getattr(weather, "wind_direction", None)
            wind = (
                f"💨 Wind {direction + ' ' if direction else ''}"
                f"{weather.wind_speed_mph:.0f} mph"
            )
            block_conditions.append(wind)
            plain_conditions.append(wind)

    sunset_local = _sunset_local(conditions.daylight)
    if sunset_local:
        sunset = f"☀️ Sunset {sunset_local.strftime('%-I:%M %p')}"
        block_conditions.append(sunset)
        plain_conditions.append(sunset)

    if conditions.air_quality is not None and 50 <= conditions.air_quality <= 100:
        air = f"🌫️ AQI {conditions.air_quality}"
        block_conditions.append(air)
        plain_conditions.append(air)

    trail = conditions.trail_conditions
    if trail:
        trail_block = f"🎿 Trails: {trail.ski_quality.replace('_', ' ').title()}"
        trail_plain = trail_block
        if trail.groomed:
            trail_block += ", Groomed"
            trail_plain += ", Groomed"
        if getattr(trail, "report_url", None):
            trail_block += f" · <{trail.report_url}|Trail report>"
            trail_plain += f" · Trail report: {trail.report_url}"
        block_conditions.append(trail_block)
        plain_conditions.append(trail_plain)

    return {
        "parking": parking,
        "gear": gear,
        "block_conditions": block_conditions,
        "plain_conditions": plain_conditions,
    }


def build_practice_details_blocks(
    practice, conditions: AnnouncementConditions
) -> list[dict]:
    """Build the optional routine-details thread reply."""
    content = _details_content(practice, conditions)
    sections = []
    logistics = []
    if content["parking"]:
        logistics.append(f"*Parking*\n{content['parking']}")
    if content["gear"]:
        logistics.append(f"*Gear*\n{', '.join(content['gear'])}")
    if logistics:
        sections.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "\n\n".join(logistics)},
        })
    if content["block_conditions"]:
        sections.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "*Conditions*\n" + "\n".join(content["block_conditions"])
                ),
            },
        })
    if not sections:
        return []

    blocks = [{
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": "Practice Details",
            "emoji": True,
        },
    }]
    for index, section in enumerate(sections):
        if index:
            blocks.append({"type": "divider"})
        blocks.append(section)
    return guard_slack_blocks(
        blocks,
        surface="practice_details",
        practice_id=practice.id,
    )


def build_practice_fallback_text(
    practice,
    conditions: AnnouncementConditions,
    *,
    announcement_notice=None,
):
    """Build complete notification fallback text for the hero message."""
    location = practice.location.name if practice.location else "TBD"
    workout = (
        str(practice.workout_description).strip()
        if getattr(practice, "workout_description", None)
        else "Workout details coming soon."
    )
    workout = truncate_slack_text(
        workout,
        2500,
        field="workout_description",
        surface="practice_fallback",
        practice_id=practice.id,
    )
    parts = [
        (
            f"{practice.date.strftime('%A, %B %-d')} at "
            f"{practice.date.strftime('%-I:%M %p')} at {location}."
        ),
        f"Workout: {workout}",
    ]
    urgent = _urgent_exception_lines(
        practice, conditions, announcement_notice=announcement_notice
    )
    if urgent:
        parts.append(" ".join(urgent))
    parts.append("RSVP with ✅.")
    if getattr(practice, "plan_reactions", None):
        parts.append(
            "Your Practice Plan: "
            + format_plan_reaction_legend(practice.plan_reactions)
            + "."
        )
    fallback = " ".join(parts)
    return guard_fallback_text(
        fallback,
        surface="practice_announcement",
        practice_id=practice.id,
    )


def build_practice_details_fallback_text(
    practice, conditions: AnnouncementConditions
):
    """Build notification fallback text from the normalized Details content."""
    content = _details_content(practice, conditions)
    parts = [
        f"Practice details for {practice.date.strftime('%A, %B %-d')}."
    ]
    if content["parking"]:
        parts.append(f"Parking: {content['parking']}.")
    if content["gear"]:
        parts.append(f"Gear: {', '.join(content['gear'])}.")
    if content["plain_conditions"]:
        parts.append(
            "Conditions: " + " ".join(content["plain_conditions"]) + "."
        )
    return guard_fallback_text(
        " ".join(parts),
        surface="practice_details",
        practice_id=practice.id,
    )


def _get_day_suffix(day: int) -> str:
    """Get ordinal suffix for day number (st, nd, rd, th)."""
    if 11 <= day <= 13:
        return 'th'
    return {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')


def _address_link(location) -> Optional[str]:
    """Return mrkdwn for the Address field: the address string as a clickable link.

    Fallback chain so the address is tappable even when google_maps_url is unset.
    The visible label is always the address text; the URL never expands inline.
    Returns None when there is no address to show.
    """
    address = getattr(location, "address", None)
    if not address:
        return None

    url = getattr(location, "google_maps_url", None)
    if not url:
        lat = getattr(location, "latitude", None)
        lon = getattr(location, "longitude", None)
        if lat is not None and lon is not None:
            url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
        else:
            url = f"https://www.google.com/maps/search/?api=1&query={quote_plus(address)}"

    return f"<{url}|{address}>"


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

    # Header day label: dedupe so two same-day practices render as "Thu"
    # rather than "Thu + Thu".
    seen_days = []
    for p in sorted_practices:
        d = p.date.strftime('%a')
        if d not in seen_days:
            seen_days.append(d)
    days_str = " + ".join(seen_days)

    # Per-practice RSVP emojis. Hour-based when unique (e.g. :six: for 6:10 PM,
    # :seven: for 7:20 PM); falls back to checkmark variants if hours collide.
    from app.slack.client import get_combined_practice_emojis
    rsvp_emoji_names = get_combined_practice_emojis(sorted_practices)
    rsvp_emojis = [f":{name}:" for name in rsvp_emoji_names]

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
    # LOCATION DETAILS: Address, Parking (shared)
    # ==========================================================================
    location_fields = []

    address_md = _address_link(location) if location else None
    if address_md:
        location_fields.append({
            "type": "mrkdwn",
            "text": f"*:world_map: Address*\n{address_md}"
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

    # When all sessions are same-day, the header already names the day,
    # so per-slot labels switch to the time to avoid "Thu | Thu" repetition.
    all_same_day = len(seen_days) == 1

    # ==========================================================================
    # COACH / LEADS (per day if different)
    # ==========================================================================
    coach_lead_parts = []
    for i, practice in enumerate(sorted_practices):
        emoji = rsvp_emojis[i] if i < len(rsvp_emojis) else ":white_check_mark:"
        time_str = practice.date.strftime('%I:%M %p').lstrip('0')
        slot_label = time_str if all_same_day else practice.date.strftime('%a')

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
            day_coaches = f"{emoji} {slot_label}: "
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
    # RSVP CTA — matches the standalone announcement's "Bop ..." tone.
    # The schedule line above already shows which slot each emoji represents.
    # ==========================================================================
    if len(rsvp_emojis) == 1:
        emoji_list = rsvp_emojis[0]
    elif len(rsvp_emojis) == 2:
        emoji_list = f"{rsvp_emojis[0]} or {rsvp_emojis[1]}"
    else:
        emoji_list = ", ".join(rsvp_emojis[:-1]) + f", or {rsvp_emojis[-1]}"

    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": f"Bop {emoji_list} so we'll know you'll be there. Running late? Drop a comment in the thread. <!channel>"
        }]
    })

    return blocks
