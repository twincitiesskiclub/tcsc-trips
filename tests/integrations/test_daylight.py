from datetime import datetime
from zoneinfo import ZoneInfo

from app.integrations.daylight import get_daylight_info


def test_daylight_uses_the_practice_local_calendar_date():
    starts_at = datetime(2026, 7, 7, 18, 15)  # production stores naive Central
    daylight = get_daylight_info(
        lat=44.9778,
        lon=-93.2650,
        date=starts_at,
    )

    sunset_local = daylight.sunset.replace(tzinfo=ZoneInfo("UTC")).astimezone(
        ZoneInfo("America/Chicago")
    )
    assert sunset_local.date() == starts_at.date()
    assert sunset_local.hour == 21
    assert daylight.sunset.tzinfo is None
