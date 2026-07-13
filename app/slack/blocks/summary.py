"""Block Kit and fallback builders for the calendar-week practice summary."""

from datetime import date, datetime, timedelta
from itertools import groupby

from app.practices.interfaces import PracticeStatus
from app.slack.blocks.text import guard_fallback_text, guard_slack_blocks


ACTIVITY_TYPE_NAME_MAX = 48
PRACTICE_KIND_MAX = 72
LOCATION_NAME_MAX = 72
CANCELLATION_REASON_MAX = 120
FORECAST_TEMPERATURE_MAX = 16
FORECAST_CONDITIONS_MAX = 96


def _limited_component(value, max_chars):
    text = str(value or "")
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _week_date(value):
    result = value.date() if isinstance(value, datetime) else value
    if not isinstance(result, date) or result.weekday() != 0:
        raise ValueError("week_start must be a Monday")
    return result


def _format_week_range(week_start):
    start = _week_date(week_start)
    end = start + timedelta(days=6)
    if start.year == end.year and start.month == end.month:
        return f"{start:%B} {start.day}–{end.day}"
    if start.year == end.year:
        return f"{start:%B} {start.day}–{end:%B} {end.day}"
    return (
        f"{start:%B} {start.day}, {start.year}–"
        f"{end:%B} {end.day}, {end.year}"
    )


def _status_value(practice):
    return getattr(practice.status, "value", practice.status)


def _is_cancelled(practice):
    return _status_value(practice) == PracticeStatus.CANCELLED.value


def _practice_kind(practice):
    raw_activities = [
        str(item.name or "") for item in (practice.activities or [])
    ]
    raw_types = [
        str(item.name or "") for item in (practice.practice_types or [])
    ]
    activities = [
        _limited_component(name, ACTIVITY_TYPE_NAME_MAX)
        for name in raw_activities
    ]
    types = [
        _limited_component(name, ACTIVITY_TYPE_NAME_MAX)
        for name in raw_types
    ]
    if len(activities) == 1 and len(types) == 1:
        if raw_activities[0].casefold() == raw_types[0].casefold():
            return activities[0]
        return _limited_component(
            f"{activities[0]} {types[0].lower()}",
            PRACTICE_KIND_MAX,
        )

    names = []
    seen = set()
    for raw_name in raw_activities + raw_types:
        folded = raw_name.casefold()
        if folded not in seen:
            names.append(
                _limited_component(raw_name, ACTIVITY_TYPE_NAME_MAX)
            )
            seen.add(folded)
    return _limited_component(
        " · ".join(names) or "Practice",
        PRACTICE_KIND_MAX,
    )


def _location_name(practice):
    name = practice.location.name if practice.location else "TBD"
    return _limited_component(name, LOCATION_NAME_MAX)


def _cancellation_reason(practice):
    return _limited_component(
        practice.cancellation_reason or "Cancelled",
        CANCELLATION_REASON_MAX,
    )


def _forecast_line(practice, weather_data):
    if _is_cancelled(practice):
        return None
    weather = (weather_data or {}).get(practice.id)
    if not weather:
        return None
    temperature = weather.get("temp_f", weather.get("temperature_f"))
    conditions = weather.get("conditions", weather.get("conditions_summary"))
    values = []
    if temperature is not None:
        values.append(
            _limited_component(
                f"{round(temperature):.0f}°F",
                FORECAST_TEMPERATURE_MAX,
            )
        )
    if conditions:
        values.append(
            _limited_component(conditions, FORECAST_CONDITIONS_MAX)
        )
    return "Forecast: " + ", ".join(values) if values else None


def _natural_days(values):
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f"{values[0]} and {values[1]}"
    return ", ".join(values[:-1]) + f", and {values[-1]}"


def _weekly_day_text(day_practices, weather_data):
    first = day_practices[0]
    if len(day_practices) == 1:
        lines = [
            f"*{first.date.strftime('%A, %B %-d')} · "
            f"{first.date.strftime('%-I:%M %p')}*"
        ]
        if _is_cancelled(first):
            lines.append(f"CANCELLED · {_cancellation_reason(first)}")
            lines.append(f"{_practice_kind(first)} · {_location_name(first)}")
        else:
            lines.append(f"{_practice_kind(first)} · {_location_name(first)}")
            forecast = _forecast_line(first, weather_data)
            if forecast:
                lines.append(forecast)
        return "\n".join(lines)

    lines = [f"*{first.date.strftime('%A, %B %-d')}*"]
    for practice in day_practices:
        if _is_cancelled(practice):
            lines.append(
                f"{practice.date.strftime('%-I:%M %p')} · CANCELLED · "
                f"{_cancellation_reason(practice)} · "
                f"{_practice_kind(practice)} · {_location_name(practice)}"
            )
        else:
            lines.append(
                f"{practice.date.strftime('%-I:%M %p')} · "
                f"{_practice_kind(practice)} · {_location_name(practice)}"
            )
            forecast = _forecast_line(practice, weather_data)
            if forecast:
                lines.append(forecast)
    return "\n".join(lines)


def build_weekly_summary_blocks(practices, *, week_start, weather_data=None):
    """Build one guarded Slack section for each represented calendar date."""
    start = _week_date(week_start)
    ordered = sorted(practices, key=lambda item: (item.date, item.id))
    heading = f"Practices this week · {_format_week_range(start)}"
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": heading, "emoji": True},
        }
    ]

    if not ordered:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "No practices scheduled this week.",
                },
            }
        )
        return guard_slack_blocks(blocks, surface="weekly_summary")

    for _, day_items in groupby(ordered, key=lambda item: item.date.date()):
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": _weekly_day_text(list(day_items), weather_data),
                },
            }
        )

    active_days = []
    for practice in ordered:
        abbreviation = practice.date.strftime("%a")
        if not _is_cancelled(practice) and abbreviation not in active_days:
            active_days.append(abbreviation)
    if active_days:
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": (
                            f"Daily details posted {_natural_days(active_days)}. "
                            "· <!channel>"
                        ),
                    }
                ],
            }
        )

    return guard_slack_blocks(blocks, surface="weekly_summary")


def build_weekly_summary_fallback_text(
    practices,
    *,
    week_start,
    weather_data=None,
):
    """Build the complete screen-reader and notification fallback."""
    start = _week_date(week_start)
    ordered = sorted(practices, key=lambda item: (item.date, item.id))
    lines = [f"Practices this week · {_format_week_range(start)}."]
    if not ordered:
        lines.append("No practices scheduled this week.")

    for practice in ordered:
        prefix = (
            f"{practice.date.strftime('%A, %B %-d at %-I:%M %p')} — "
            f"{_practice_kind(practice)} at {_location_name(practice)}"
        )
        if _is_cancelled(practice):
            lines.append(
                f"{prefix} — CANCELLED: "
                f"{_cancellation_reason(practice)}."
            )
        else:
            forecast = _forecast_line(practice, weather_data)
            lines.append(prefix + (f" — {forecast}." if forecast else "."))

    return guard_fallback_text(
        " ".join(lines),
        surface="weekly_summary",
    )
