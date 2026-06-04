"""Block Kit builders for practice announcements."""

from typing import Optional
from urllib.parse import quote_plus
from app.practices.interfaces import (
    PracticeInfo,
    WeatherConditions,
    TrailCondition,
    LeadRole,
)
from app.utils import utc_naive_to_central_naive


def _activity_label(activities) -> str:
    """Header activity label. Names are pre-normalized in the DB, so join them
    verbatim. Falls back to 'Practice' when no activity is set."""
    names = [a.name for a in (activities or []) if getattr(a, "name", None)]
    if not names:
        return "Practice"
    return " + ".join(names)


def build_practice_announcement_blocks(practice, *args, **kwargs) -> list[dict]:
    """Hero (top message) for a single practice announcement.

    Weather/trail/daylight/AQI live in the threaded details reply, not here.
    Extra positional/keyword args are accepted and ignored for backward
    compatibility with old callers that passed weather/trail.
    """
    blocks = []

    day = practice.date.strftime('%A')
    time_str = practice.date.strftime('%I:%M %p').lstrip('0')
    activity = _activity_label(practice.activities)

    # HEADER: {day} · {activity} at {time}
    blocks.append({
        "type": "header",
        "text": {"type": "plain_text", "text": f"{day} · {activity} at {time_str}", "emoji": True},
    })

    # WHERE + address
    location_name = practice.location.name if practice.location else "TBD"
    spot = practice.location.spot if practice.location and practice.location.spot else None
    where = f"{location_name} - {spot}" if spot else location_name
    where_text = f"*Where:* {where}"
    addr = _address_link(practice.location) if practice.location else None
    if addr:
        where_text += f"\n📍 {addr}"
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": where_text}})

    blocks.append({"type": "divider"})

    # WORKOUT · type
    type_names = ", ".join(t.name for t in practice.practice_types) if practice.practice_types else ""
    workout_label = f"*Workout · {type_names}*" if type_names else "*Workout*"
    if practice.workout_description:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"{workout_label}\n{practice.workout_description}"}})

    # NOTES (logistics)
    if getattr(practice, "logistics_notes", None):
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*📌 Notes*\n{practice.logistics_notes}"}})

    # SOCIAL
    if practice.has_social:
        social = getattr(practice, "social_location", None) or (practice.location.social_location if practice.location else None)
        if social and getattr(social, "name", None):
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"🍹 *Social after at {social.name}*"}})
        else:
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "🍹 *Social after!*"}})

    blocks.append({"type": "divider"})

    # RSVP CTA (emoji reactions)
    has_intervals = any('intervals' in t.name.lower() for t in practice.practice_types) if practice.practice_types else False
    if has_intervals:
        cta_text = ("Bop :white_check_mark: so we'll know you'll be there. "
                    ":evergreen_tree: if you'll be there but doing endurance instead. "
                    "Running late? Reply in the thread. <!channel>")
    else:
        cta_text = ("Bop :white_check_mark: so we'll know you'll be there. "
                    "Running late? Reply in the thread. <!channel>")
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": cta_text}})

    # COACH / LEADS (context)
    coaches, leads = [], []
    for lead in (practice.leads or []):
        mention = f"<@{lead.slack_user_id}>" if lead.slack_user_id else (lead.display_name or "Unknown")
        role = lead.role.name if hasattr(lead.role, "name") else str(lead.role)
        if role == "COACH":
            coaches.append(mention)
        elif role in ("LEAD", "ASSIST"):
            leads.append(mention)
    cl = []
    if coaches:
        cl.append(f"👨‍🏫 Coach {', '.join(coaches)}")
    if leads:
        cl.append(f"🧑‍🤝‍🧑 Leads {', '.join(leads)}")
    if cl:
        blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": " · ".join(cl)}]})

    return blocks


def _gear_list(practice) -> list[str]:
    items = []
    for activity in (practice.activities or []):
        gear = getattr(activity, "gear_required", None)
        if not gear:
            continue
        items.extend(gear if isinstance(gear, list) else [gear])
    seen = set()
    return [g for g in items if not (g in seen or seen.add(g))]


def build_practice_details_blocks(
    practice,
    weather=None,
    trail_conditions=None,
    daylight=None,
    air_quality=None,
) -> list[dict]:
    """Threaded 'Practice Details' reply: parking, gear, conditions.

    air_quality is an int AQI value (or None). Sunset uses comma + 'bring a
    headlamp' (no em dash) when the practice starts at/after sunset.
    """
    blocks = [{"type": "header", "text": {"type": "plain_text", "text": "Practice Details", "emoji": True}}]

    # Parking + Gear (one section, blank-line separated)
    parts = []
    parking = practice.location.parking_notes if practice.location else None
    if parking:
        parts.append(f"*Parking*\n{parking}")
    gear = _gear_list(practice)
    if gear:
        parts.append(f"*Gear*\n{', '.join(gear)}")
    if parts:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "\n\n".join(parts)}})

    # Conditions
    cond = []
    if weather:
        temp = f"🌡️ {weather.temperature_f:.0f}°F"
        if weather.feels_like_f is not None and abs(weather.feels_like_f - weather.temperature_f) > 3:
            temp += f" (feels {weather.feels_like_f:.0f}°)"
        if getattr(weather, "conditions_summary", None):
            temp += f", {weather.conditions_summary}"
        if getattr(weather, "alerts", None):
            temp += f". ⚠️ {weather.alerts[0].headline}"
        else:
            temp += ". No alerts."
        cond.append(temp)
        if getattr(weather, "wind_speed_mph", None):
            direction = getattr(weather, "wind_direction", None)
            cond.append(f"💨 Wind {direction + ' ' if direction else ''}{weather.wind_speed_mph:.0f} mph")
    if daylight and getattr(daylight, "sunset", None):
        # sunset is stored as naive UTC; practice.date is naive Central. Convert
        # once so both the comparison and the displayed time are Central.
        sunset_central = utc_naive_to_central_naive(daylight.sunset)
        sunset_str = sunset_central.strftime('%I:%M %p').lstrip('0')
        if practice.date >= sunset_central:
            cond.append(f"🔦 Sunset {sunset_str}, bring a headlamp")
        else:
            cond.append(f"☀️ Sunset {sunset_str}")
    if air_quality is not None and air_quality > 49:
        cond.append(f"🌫️ AQI {air_quality}")
    if trail_conditions:
        trail = f"🎿 Trails: {trail_conditions.ski_quality.replace('_', ' ').title()}"
        if trail_conditions.groomed:
            trail += ", Groomed"
        if getattr(trail_conditions, "report_url", None):
            trail += f" · <{trail_conditions.report_url}|Trail report>"
        cond.append(trail)
    if cond:
        blocks.append({"type": "divider"})
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*Conditions*\n" + "\n".join(cond)}})

    return blocks


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
