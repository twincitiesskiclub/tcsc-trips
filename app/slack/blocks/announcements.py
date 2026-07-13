"""Block Kit builders for practice announcements."""

from datetime import timedelta
from typing import Optional
from urllib.parse import quote_plus

from app.practices.interfaces import (
    AnnouncementConditions,
    PracticeInfo,
    PracticeStatus,
    TrailCondition,
    WeatherConditions,
)
from app.practices.plan_reactions import (
    format_reaction_name_for_fallback,
    format_supplemental_reaction_fallback,
    format_supplemental_reaction_sentence,
)
from app.slack.blocks.fallback import (
    allocate_fallback_component_limits,
    plainify_fallback_fragment,
)
from app.slack.blocks.text import (
    CONTEXT_TEXT_MAX,
    FALLBACK_TEXT_MAX,
    HEADER_TEXT_MAX,
    SECTION_TEXT_MAX,
    guard_fallback_text,
    guard_slack_blocks,
    truncate_slack_text,
)
from app.utils import utc_naive_to_central_naive


_SPACER = "\n\u200b"
_WORKOUT_PLACEHOLDER = "Workout details coming soon."
_FALLBACK_STATUS_MAX = 80
_FALLBACK_LOCATION_MAX = 250
_FALLBACK_WORKOUT_MAX = 1000
_FALLBACK_NOTES_MAX = 600
_FALLBACK_SOCIAL_MAX = 250
_FALLBACK_NOTICE_MAX = 250
_FALLBACK_ALERTS_MAX = 550
_DETAILS_FALLBACK_PARKING_MAX = 1000
_DETAILS_FALLBACK_GEAR_MAX = 800
_DETAILS_FALLBACK_CONDITIONS_MAX = 1700
_COMBINED_CANCELLATION_REASON_MAX = 600
_COMBINED_FALLBACK_NOTICE_MAX = 150
_COMBINED_FALLBACK_LOCATION_MAX = 160
_COMBINED_FALLBACK_REASON_MAX = 150
_COMBINED_FALLBACK_SHARED_WORKOUT_MAX = 700
_COMBINED_FALLBACK_SESSION_WORKOUT_MAX = 220
_COMBINED_FALLBACK_SHARED_NOTES_MAX = 500
_COMBINED_FALLBACK_SESSION_NOTES_MAX = 140
_COMBINED_FALLBACK_SHARED_SOCIAL_MAX = 200
_COMBINED_FALLBACK_SESSION_SOCIAL_MAX = 100
_ACTIVE_ALERTS_VISIBLE_MAX = 20
_RUNNING_LATE_LINE = "Running late? Reply in the thread. <!channel>"
_FALLBACK_RUNNING_LATE = "Running late? Reply in the thread."
_STANDALONE_ATTENDANCE = (
    "Bop :white_check_mark: so we'll know you'll be there."
)
_STANDALONE_FALLBACK_ATTENDANCE = (
    "RSVP with the white check mark reaction so we'll know you'll be there."
)


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


def _rsvp_context_block(
    attendance_sentence,
    reactions,
    *,
    surface,
    practice_id=None,
):
    supplemental = format_supplemental_reaction_sentence(reactions)
    required = f"{attendance_sentence}\n{_RUNNING_LATE_LINE}"
    if supplemental:
        budget = CONTEXT_TEXT_MAX - len(required) - 1
        supplemental = truncate_slack_text(
            supplemental,
            max(1, budget),
            field="plan_reactions",
            surface=surface,
            practice_id=practice_id,
        )
    first_line = attendance_sentence
    if supplemental:
        first_line += " " + supplemental
    return {
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": f"{first_line}\n{_RUNNING_LATE_LINE}",
        }],
    }


def _fallback_with_reserved_tail(
    parts,
    tail,
    *,
    surface,
    practice_id=None,
):
    body = " ".join(
        plainify_fallback_fragment(str(part).strip()) for part in parts
        if part and str(part).strip()
    )
    tail = plainify_fallback_fragment(str(tail).strip())
    separator_length = 1 if body and tail else 0
    body_budget = max(0, FALLBACK_TEXT_MAX - len(tail) - separator_length)
    if body and len(body) > body_budget:
        body = (
            truncate_slack_text(
                body,
                body_budget,
                field="fallback_body",
                surface=surface,
                practice_id=practice_id,
            )
            if body_budget > 0
            else ""
        )
    value = " ".join(part for part in (body, tail) if part)
    return guard_fallback_text(
        value,
        surface=surface,
        practice_id=practice_id,
    )


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


def _urgent_exception_categories(practice, conditions, announcement_notice=None):
    categories = []
    if announcement_notice:
        categories.append(("announcement_notice", [str(announcement_notice)]))

    alerts = []
    for alert in (getattr(conditions.weather, "alerts", None) or []):
        headline = getattr(alert, "headline", None) or getattr(alert, "event", None)
        if headline:
            alerts.append(f"⚠️ {headline}")
    if alerts:
        categories.append(("weather_alert_headlines", alerts))

    if conditions.air_quality is not None and conditions.air_quality >= 101:
        categories.append(
            ("air_quality", [f"🌫️ Air quality {conditions.air_quality}"])
        )

    if _requires_headlamp(
        practice, conditions.daylight, conditions.duration_minutes
    ):
        sunset_local = _sunset_local(conditions.daylight)
        categories.append(
            (
                "headlamp",
                [
                    (
                        "🔦 Headlamp required · Sunset "
                        f"{sunset_local.strftime('%-I:%M %p')}"
                    )
                    if sunset_local
                    else "🔦 Headlamp required"
                ],
            )
        )
    return categories


def _urgent_exception_lines(practice, conditions, announcement_notice=None):
    return [
        line
        for _, lines in _urgent_exception_categories(
            practice,
            conditions,
            announcement_notice=announcement_notice,
        )
        for line in lines
    ]


def _bounded_active_alerts(
    lines,
    max_chars,
    *,
    separator,
    surface,
    practice_id,
):
    """Bound active alerts as one semantic group with an honest overflow count."""
    visible = list(lines[:_ACTIVE_ALERTS_VISIBLE_MAX])
    hidden_count = max(0, len(lines) - len(visible))
    overflow = (
        f"+{hidden_count} more active alerts" if hidden_count else None
    )
    full_text = separator.join(visible + ([overflow] if overflow else []))
    if len(full_text) <= max_chars:
        return full_text

    reserved = len(overflow or "")
    item_count = len(visible) + (1 if overflow else 0)
    reserved += len(separator) * max(0, item_count - 1)
    item_budget = max(1, (max_chars - reserved) // max(1, len(visible)))
    bounded = [
        truncate_slack_text(
            line,
            item_budget,
            field="weather_alert_headlines",
            surface=surface,
            practice_id=practice_id,
        )
        for line in visible
    ]
    if overflow:
        bounded.append(overflow)
    return separator.join(bounded)


def _workout_text(practice):
    return str(getattr(practice, "workout_description", None) or "").strip() or (
        _WORKOUT_PLACEHOLDER
    )


def _practice_status_label(practice):
    status = getattr(practice, "status", None)
    value = getattr(status, "value", status)
    return str(value or "unknown").replace("_", " ").title()


def _sentence(prefix, value):
    return f"{prefix}{value}{'' if value.endswith('…') else '.'}"


def build_practice_announcement_blocks(
    practice,
    conditions: AnnouncementConditions,
    *,
    announcement_notice=None,
) -> list[dict]:
    """Build the standalone practice announcement from one conditions snapshot."""
    header_prefix = f"{practice.date:%A} · "
    header_suffix = f" at {practice.date.strftime('%-I:%M %p')}"
    activity = truncate_slack_text(
        _activity_label(practice.activities),
        max(1, HEADER_TEXT_MAX - len(header_prefix) - len(header_suffix)),
        field="activity_label",
        surface="practice_announcement",
        practice_id=practice.id,
    )
    header_group = [{
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": header_prefix + activity + header_suffix,
            "emoji": True,
        },
    }]

    urgent_categories = _urgent_exception_categories(
        practice, conditions, announcement_notice=announcement_notice
    )
    for field, lines in urgent_categories:
        category_texts = [
            _bounded_active_alerts(
                lines,
                SECTION_TEXT_MAX - len(_SPACER),
                separator="\n",
                surface="practice_announcement",
                practice_id=practice.id,
            )
        ] if field == "weather_alert_headlines" else ["\n".join(lines)]
        for category_text in category_texts:
            urgent_text = truncate_slack_text(
                category_text,
                SECTION_TEXT_MAX - len(_SPACER),
                field=field,
                surface="practice_announcement",
                practice_id=practice.id,
            )
            header_group.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": urgent_text + _SPACER},
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
        str(item.name) for item in (practice.practice_types or [])
    )
    if type_names:
        type_prefix = "*Workout · "
        type_suffix = "*"
        type_names = truncate_slack_text(
            type_names,
            max(
                1,
                SECTION_TEXT_MAX
                - len(type_prefix)
                - len(type_suffix)
                - 1
                - len(_SPACER)
                - len(_WORKOUT_PLACEHOLDER),
            ),
            field="practice_type_names",
            surface="practice_announcement",
            practice_id=practice.id,
        )
        workout_label = type_prefix + type_names + type_suffix
    else:
        workout_label = "*Workout*"
    workout_prefix = f"{workout_label}\n"
    workout = _workout_text(practice)
    workout = truncate_slack_text(
        workout,
        max(1, SECTION_TEXT_MAX - len(workout_prefix) - len(_SPACER)),
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
        notes_prefix = "*📝 Notes*\n"
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

    ending_group = [
        _rsvp_context_block(
            _STANDALONE_ATTENDANCE,
            getattr(practice, "plan_reactions", None) or [],
            surface="practice_announcement",
            practice_id=practice.id,
        )
    ]

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
    if content["parking"]:
        parking_prefix = "*Parking*\n"
        parking = truncate_slack_text(
            content["parking"],
            SECTION_TEXT_MAX - len(parking_prefix),
            field="parking_notes",
            surface="practice_details",
            practice_id=practice.id,
        )
        sections.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": parking_prefix + parking},
        })
    if content["gear"]:
        gear_prefix = "*Gear*\n"
        gear = truncate_slack_text(
            ", ".join(content["gear"]),
            SECTION_TEXT_MAX - len(gear_prefix),
            field="gear_required",
            surface="practice_details",
            practice_id=practice.id,
        )
        sections.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": gear_prefix + gear},
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
    status = truncate_slack_text(
        _practice_status_label(practice),
        _FALLBACK_STATUS_MAX,
        field="practice_status",
        surface="practice_fallback",
        practice_id=practice.id,
    )
    location = truncate_slack_text(
        practice.location.name if practice.location else "TBD",
        _FALLBACK_LOCATION_MAX,
        field="location_name",
        surface="practice_fallback",
        practice_id=practice.id,
    )
    workout = truncate_slack_text(
        _workout_text(practice),
        _FALLBACK_WORKOUT_MAX,
        field="workout_description",
        surface="practice_fallback",
        practice_id=practice.id,
    )
    parts = [
        f"Status: {status}.",
        (
            f"{practice.date.strftime('%A, %B %-d')} at "
            f"{practice.date.strftime('%-I:%M %p')} at {location}."
        ),
        f"Workout: {workout}",
    ]
    notes = str(getattr(practice, "logistics_notes", None) or "").strip()
    if notes:
        parts.append(
            "Notes: "
            + truncate_slack_text(
                notes,
                _FALLBACK_NOTES_MAX,
                field="logistics_notes",
                surface="practice_fallback",
                practice_id=practice.id,
            )
        )
    if getattr(practice, "has_social", False):
        social = getattr(practice, "social_location", None)
        social_name = str(getattr(social, "name", None) or "").strip()
        if social_name:
            bounded_name = truncate_slack_text(
                social_name,
                _FALLBACK_SOCIAL_MAX,
                field="social_location_name",
                surface="practice_fallback",
                practice_id=practice.id,
            )
            parts.append(f"Social after at {bounded_name}.")
        else:
            parts.append("Social after practice.")
    urgent_categories = _urgent_exception_categories(
        practice, conditions, announcement_notice=announcement_notice
    )
    urgent_budgets = {
        "announcement_notice": _FALLBACK_NOTICE_MAX,
        "weather_alert_headlines": _FALLBACK_ALERTS_MAX,
    }
    for field, lines in urgent_categories:
        budget = urgent_budgets.get(field, 100)
        if field == "weather_alert_headlines":
            parts.append(_bounded_active_alerts(
                lines,
                budget,
                separator=" ",
                surface="practice_fallback",
                practice_id=practice.id,
            ))
        else:
            parts.append(truncate_slack_text(
                " ".join(lines),
                budget,
                field=field,
                surface="practice_fallback",
                practice_id=practice.id,
            ))
    tail_parts = [_STANDALONE_FALLBACK_ATTENDANCE]
    supplemental = format_supplemental_reaction_fallback(
        getattr(practice, "plan_reactions", None) or []
    )
    if supplemental:
        tail_parts.append(supplemental)
    tail_parts.append(_FALLBACK_RUNNING_LATE)
    return _fallback_with_reserved_tail(
        parts,
        " ".join(tail_parts),
        surface="practice_announcement",
        practice_id=practice.id,
    )


def build_practice_details_fallback_text(
    practice,
    conditions: AnnouncementConditions,
    *,
    max_chars=FALLBACK_TEXT_MAX,
):
    """Build notification fallback text from the normalized Details content."""
    content = _details_content(practice, conditions)
    prefix = f"Practice details for {practice.date.strftime('%A, %B %-d')}."
    components = []
    if content["parking"]:
        parking = truncate_slack_text(
            plainify_fallback_fragment(content["parking"]),
            _DETAILS_FALLBACK_PARKING_MAX,
            field="parking_notes",
            surface="practice_details_fallback",
            practice_id=practice.id,
        )
        components.append(("Parking: ", parking, "parking_notes"))
    if content["gear"]:
        gear = truncate_slack_text(
            plainify_fallback_fragment(", ".join(content["gear"])),
            _DETAILS_FALLBACK_GEAR_MAX,
            field="gear_required",
            surface="practice_details_fallback",
            practice_id=practice.id,
        )
        components.append(("Gear: ", gear, "gear_required"))
    if content["plain_conditions"]:
        conditions_text = truncate_slack_text(
            plainify_fallback_fragment(" ".join(content["plain_conditions"])),
            _DETAILS_FALLBACK_CONDITIONS_MAX,
            field="conditions",
            surface="practice_details_fallback",
            practice_id=practice.id,
        )
        components.append(("Conditions: ", conditions_text, "conditions"))

    fixed_length = len(prefix) + sum(
        1 + len(label) + 1 for label, _value, _field in components
    )
    limits = allocate_fallback_component_limits(
        [value for _label, value, _field in components],
        budget=max_chars - fixed_length,
    )
    parts = [prefix]
    for (label, value, field), limit in zip(components, limits):
        bounded = (
            truncate_slack_text(
                value,
                limit,
                field=field,
                surface="practice_details_fallback",
                practice_id=practice.id,
            )
            if limit > 0 else ""
        )
        parts.append(_sentence(label, bounded))
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


def _status_value(practice):
    return getattr(practice.status, "value", practice.status)


def _is_cancelled(practice):
    return _status_value(practice) == PracticeStatus.CANCELLED.value


def _combined_date_label(practices):
    first = practices[0].date.date()
    last = practices[-1].date.date()
    if first == last:
        return f"{first:%B} {first.day}"
    if first.year == last.year and first.month == last.month:
        return f"{first:%B} {first.day}–{last.day}"
    if first.year == last.year:
        return f"{first:%B} {first.day}–{last:%B} {last.day}"
    return (
        f"{first:%B} {first.day}, {first.year}–"
        f"{last:%B} {last.day}, {last.year}"
    )


def _all_sessions_same_date(practices):
    dates = {practice.date.date() for practice in practices}
    return len(dates) == 1


def _combined_session_when(practice, *, same_day):
    if same_day:
        return practice.date.strftime("%-I:%M %p")
    return (
        f"{practice.date.strftime('%A, %B %-d')} · "
        f"{practice.date.strftime('%-I:%M %p')}"
    )


def _combined_owner_label(practice, *, same_day):
    if same_day:
        return practice.date.strftime("%-I:%M %p")
    return practice.date.strftime("%A at %-I:%M %p")


def _join_with_or(items):
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} or {items[1]}"
    return f"{', '.join(items[:-1])}, or {items[-1]}"


def _combined_mapping(practices, *, plain):
    same_day = _all_sessions_same_date(practices)
    active = [practice for practice in practices if not _is_cancelled(practice)]
    if not active:
        return None
    pairs = []
    for practice in active:
        reaction = (
            format_reaction_name_for_fallback(practice.slack_session_emoji)
            if plain
            else f":{practice.slack_session_emoji}:"
        )
        when = (
            practice.date.strftime("%-I:%M %p")
            if same_day
            else practice.date.strftime("%a at %-I:%M %p")
        )
        pairs.append(f"{reaction} for {when}")
    return _join_with_or(pairs)


def _combined_attendance_sentence(practices, *, plain):
    mapping = _combined_mapping(practices, plain=plain)
    if not mapping:
        return None
    prefix = "RSVP with" if plain else "Bop"
    return f"{prefix} {mapping} so we'll know you'll be there."


def _shared_plan_reactions(practices):
    snapshots = [
        tuple((item["emoji"], item["label"]) for item in (p.plan_reactions or []))
        for p in practices
    ]
    if not snapshots or any(snapshot != snapshots[0] for snapshot in snapshots[1:]):
        return []
    return [
        {"emoji": emoji, "label": label}
        for emoji, label in snapshots[0]
    ]


def _same_value(practices, getter):
    values = [getter(practice) for practice in practices]
    return all(value == values[0] for value in values[1:]), values[0]


def _normalized_shared_text(value):
    return " ".join(str(value or "").split())


def _same_normalized_text(practices, getter):
    display_values = [
        str(getter(practice) or "").strip() for practice in practices
    ]
    comparison_values = [
        _normalized_shared_text(value) for value in display_values
    ]
    return (
        all(
            value == comparison_values[0]
            for value in comparison_values[1:]
        ),
        display_values[0],
    )


def _social_value(practice):
    social = getattr(practice, "social_location", None)
    return (
        bool(practice.has_social),
        getattr(social, "id", None),
        _normalized_shared_text(getattr(social, "name", None)),
    )


def _social_line(practice):
    if not practice.has_social:
        return None
    social = getattr(practice, "social_location", None)
    return (
        f"🍹 *Social after at {social.name}*"
        if social and social.name else "🍹 *Social after!*"
    )


def _combined_lead_line(practice):
    coaches, leads = [], []
    for lead in (practice.leads or []):
        mention = (
            f"<@{lead.slack_user_id}>"
            if lead.slack_user_id else lead.display_name or "Unknown"
        )
        role_name = getattr(lead.role, "name", str(lead.role)).upper()
        if role_name == "COACH":
            coaches.append(mention)
        elif role_name in {"LEAD", "ASSIST"}:
            leads.append(mention)
    parts = []
    if coaches:
        parts.append(f"Coach {', '.join(coaches)}")
    if leads:
        parts.append(f"Leads {', '.join(leads)}")
    return " · ".join(parts)


def _combined_session_text(practice, *, same_day):
    when = _combined_session_when(practice, same_day=same_day)
    first_line = (
        f"*CANCELLED · {when}*" if _is_cancelled(practice) else f"*{when}*"
    )
    location = practice.location.name if practice.location else "TBD"
    spot = (
        practice.location.spot
        if practice.location and practice.location.spot else None
    )
    lines = [first_line, location + (f" - {spot}" if spot else "")]
    lead_line = _combined_lead_line(practice)
    if lead_line:
        lines.append(lead_line)
    if _is_cancelled(practice):
        reason_prefix = "Reason: "
        available = max(
            0,
            SECTION_TEXT_MAX
            - len("\n".join(lines))
            - len("\n" + reason_prefix),
        )
        reason_limit = min(_COMBINED_CANCELLATION_REASON_MAX, available)
        if reason_limit > 1:
            reason = truncate_slack_text(
                practice.cancellation_reason or "Cancelled",
                reason_limit,
                field="cancellation_reason",
                surface="combined_practice_announcement",
                practice_id=practice.id,
            )
            lines.append(reason_prefix + reason)
    return "\n".join(lines)


def build_combined_lift_blocks(practices, *, announcement_notice=None):
    """Build a guarded combined Strength root from persisted session values."""
    ordered = sorted(practices, key=lambda item: (item.date, item.id))
    if not ordered:
        return []
    if any(not item.slack_session_emoji for item in ordered):
        raise ValueError("Combined builders require persisted session reactions")
    same_day = _all_sessions_same_date(ordered)
    active = [practice for practice in ordered if not _is_cancelled(practice)]
    shared_plan = _shared_plan_reactions(ordered)

    header_group = [{
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": f"Strength practices · {_combined_date_label(ordered)}",
            "emoji": True,
        },
    }]
    if announcement_notice:
        header_group.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": announcement_notice + _SPACER},
        })
    session_group = [{
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": _combined_session_text(practice, same_day=same_day),
        },
    } for practice in ordered]

    representative = ordered[0]
    same_workout, shared_workout = _same_normalized_text(
        ordered, lambda item: str(item.workout_description or "").strip()
    )
    same_notes, shared_notes = _same_normalized_text(
        ordered, lambda item: str(item.logistics_notes or "").strip()
    )
    same_social, _ = _same_value(ordered, _social_value)
    workout_group = []

    workout_rows = [(representative, shared_workout)] if same_workout else [
        (practice, str(practice.workout_description or "").strip())
        for practice in ordered
    ]
    for owner, value in workout_rows:
        type_names = ", ".join(item.name for item in (owner.practice_types or []))
        owner_label = "" if same_workout else (
            f"{_combined_owner_label(owner, same_day=same_day)} · "
        )
        workout_label = (
            f"*{owner_label}Workout · {type_names}*"
            if type_names else f"*{owner_label}Workout*"
        )
        workout_prefix = f"{workout_label}\n"
        workout = truncate_slack_text(
            value or _WORKOUT_PLACEHOLDER,
            SECTION_TEXT_MAX - len(workout_prefix),
            field="workout_description",
            surface="combined_practice_announcement",
            practice_id=owner.id,
        )
        workout_group.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": workout_prefix + workout},
        })

    notes_rows = [(representative, shared_notes)] if same_notes else [
        (practice, str(practice.logistics_notes or "").strip())
        for practice in ordered
    ]
    for owner, value in notes_rows:
        if not value:
            continue
        notes_prefix = "*📝 Notes*\n"
        if not same_notes:
            notes_prefix += (
                f"*{_combined_owner_label(owner, same_day=same_day)}*\n"
            )
        notes = truncate_slack_text(
            value,
            SECTION_TEXT_MAX - len(notes_prefix),
            field="logistics_notes",
            surface="combined_practice_announcement",
            practice_id=owner.id,
        )
        workout_group.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": notes_prefix + notes},
        })

    social_rows = [representative] if same_social else ordered
    for owner in social_rows:
        social_text = _social_line(owner)
        if not social_text:
            continue
        prefix = "" if same_social else (
            f"{_combined_owner_label(owner, same_day=same_day)} · "
        )
        workout_group.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": prefix + social_text},
        })

    ending_group = []
    attendance = (
        _combined_attendance_sentence(ordered, plain=False) if active else None
    )
    if attendance:
        ending_group.append(_rsvp_context_block(
            attendance,
            shared_plan,
            surface="combined_practice_announcement",
            practice_id=representative.id,
        ))

    return guard_slack_blocks(
        _join_block_groups([
            header_group, session_group, workout_group, ending_group,
        ]),
        surface="combined_practice_announcement",
        practice_id=representative.id,
    )


def build_combined_fallback_text(practices, *, announcement_notice=None):
    """Build complete notification text for every combined session."""
    ordered = sorted(practices, key=lambda item: (item.date, item.id))
    if not ordered:
        return guard_fallback_text(
            "Strength practice details unavailable.",
            surface="combined_practice_announcement",
        )
    if any(not item.slack_session_emoji for item in ordered):
        raise ValueError("Combined builders require persisted session reactions")
    lines = [f"Strength practices · {_combined_date_label(ordered)}."]
    if announcement_notice:
        lines.append(truncate_slack_text(
            announcement_notice,
            _COMBINED_FALLBACK_NOTICE_MAX,
            field="announcement_notice",
            surface="combined_practice_fallback",
            practice_id=ordered[0].id,
        ))
    for practice in ordered:
        location = truncate_slack_text(
            practice.location.name if practice.location else "TBD",
            _COMBINED_FALLBACK_LOCATION_MAX,
            field="location_name",
            surface="combined_practice_fallback",
            practice_id=practice.id,
        )
        if _is_cancelled(practice):
            reason = truncate_slack_text(
                practice.cancellation_reason or "Cancelled",
                _COMBINED_FALLBACK_REASON_MAX,
                field="cancellation_reason",
                surface="combined_practice_fallback",
                practice_id=practice.id,
            )
            status = f"CANCELLED: {reason}"
        else:
            status = "Active"
        lines.append(
            f"{practice.date.strftime('%A, %B %-d at %-I:%M %p')}; "
            f"{status}; {location}."
        )
    representative = ordered[0]
    same_workout, shared_workout = _same_normalized_text(
        ordered,
        lambda item: str(item.workout_description or "").strip()
        or _WORKOUT_PLACEHOLDER,
    )
    if same_workout:
        workout = truncate_slack_text(
            shared_workout,
            _COMBINED_FALLBACK_SHARED_WORKOUT_MAX,
            field="workout_description",
            surface="combined_practice_fallback",
            practice_id=representative.id,
        )
        lines.append(f"Workout: {workout}")
    else:
        for practice in ordered:
            workout = truncate_slack_text(
                str(practice.workout_description or "").strip()
                or _WORKOUT_PLACEHOLDER,
                _COMBINED_FALLBACK_SESSION_WORKOUT_MAX,
                field="workout_description",
                surface="combined_practice_fallback",
                practice_id=practice.id,
            )
            lines.append(
                f"{practice.date.strftime('%A at %-I:%M %p')} workout: "
                f"{workout}"
            )
    same_notes, shared_notes = _same_normalized_text(
        ordered, lambda item: str(item.logistics_notes or "").strip()
    )
    if same_notes and shared_notes:
        notes = truncate_slack_text(
            shared_notes,
            _COMBINED_FALLBACK_SHARED_NOTES_MAX,
            field="logistics_notes",
            surface="combined_practice_fallback",
            practice_id=representative.id,
        )
        lines.append(f"Notes: {notes}")
    elif not same_notes:
        for practice in ordered:
            notes = str(practice.logistics_notes or "").strip()
            if not notes:
                continue
            notes = truncate_slack_text(
                notes,
                _COMBINED_FALLBACK_SESSION_NOTES_MAX,
                field="logistics_notes",
                surface="combined_practice_fallback",
                practice_id=practice.id,
            )
            lines.append(
                f"{practice.date.strftime('%A at %-I:%M %p')} notes: {notes}"
            )
    same_social, _shared_social = _same_value(ordered, _social_value)
    social_rows = [representative] if same_social else ordered
    for practice in social_rows:
        if not practice.has_social:
            continue
        social = getattr(practice, "social_location", None)
        social_name = str(getattr(social, "name", None) or "").strip()
        social_limit = (
            _COMBINED_FALLBACK_SHARED_SOCIAL_MAX
            if same_social else _COMBINED_FALLBACK_SESSION_SOCIAL_MAX
        )
        if social_name:
            social_name = truncate_slack_text(
                social_name,
                social_limit,
                field="social_location_name",
                surface="combined_practice_fallback",
                practice_id=practice.id,
            )
            social_text = f"Social after at {social_name}."
        else:
            social_text = "Social after practice."
        if same_social:
            lines.append(social_text)
        else:
            lines.append(
                f"{practice.date.strftime('%A at %-I:%M %p')} {social_text}"
            )
    attendance = _combined_attendance_sentence(ordered, plain=True)
    if not attendance:
        return guard_fallback_text(
            plainify_fallback_fragment(" ".join(lines)),
            surface="combined_practice_announcement",
            practice_id=representative.id,
        )

    tail_parts = [attendance]
    supplemental = format_supplemental_reaction_fallback(
        _shared_plan_reactions(ordered)
    )
    if supplemental:
        tail_parts.append(supplemental)
    tail_parts.append(_FALLBACK_RUNNING_LATE)
    return _fallback_with_reserved_tail(
        lines,
        " ".join(tail_parts),
        surface="combined_practice_announcement",
        practice_id=representative.id,
    )
