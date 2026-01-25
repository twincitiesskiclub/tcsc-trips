"""Block Kit builders for weekly practice summary."""

from typing import Optional
from app.practices.interfaces import PracticeInfo, PracticeStatus


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

        # Day header
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
