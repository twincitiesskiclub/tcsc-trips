"""
Daylight calculations using the astral library.

Provides sunrise/sunset times and civil twilight information for ski practice scheduling.
"""

import logging
from datetime import datetime, timedelta, timezone
from astral import LocationInfo
from astral.sun import sun

from app.practices.interfaces import DaylightInfo

logger = logging.getLogger(__name__)


def get_daylight_info(lat: float, lon: float, date: datetime) -> DaylightInfo:
    """
    Get daylight information for a specific location and date.

    Args:
        lat: Latitude
        lon: Longitude
        date: Date to calculate for (time component ignored)

    Returns:
        DaylightInfo dataclass with sunrise, sunset, and twilight times
    """
    logger.info(f"Calculating daylight for ({lat},{lon}) on {date.date()}")

    # Create location info
    # Name and region are not critical for calculations
    location = LocationInfo(
        name="Practice Location",
        region="Minnesota",
        timezone="America/Chicago",
        latitude=lat,
        longitude=lon
    )

    # Calculate sun times for the given date
    # astral returns timezone-aware datetimes in the location's timezone
    try:
        s = sun(location.observer, date=date.date())

        sunrise = s['sunrise']
        sunset = s['sunset']
        dawn = s['dawn']  # Civil twilight begin
        dusk = s['dusk']  # Civil twilight end

        # Calculate day length in hours using local times (before UTC conversion)
        day_length = (sunset - sunrise).total_seconds() / 3600.0

        # Convert to naive UTC for consistency with rest of app
        sunrise_utc = sunrise.astimezone(timezone.utc).replace(tzinfo=None)
        sunset_utc = sunset.astimezone(timezone.utc).replace(tzinfo=None)
        dawn_utc = dawn.astimezone(timezone.utc).replace(tzinfo=None)
        dusk_utc = dusk.astimezone(timezone.utc).replace(tzinfo=None)

        daylight_info = DaylightInfo(
            date=date,
            latitude=lat,
            longitude=lon,
            sunrise=sunrise_utc,
            sunset=sunset_utc,
            civil_twilight_begin=dawn_utc,
            civil_twilight_end=dusk_utc,
            day_length_hours=round(day_length, 2)
        )

        logger.info(f"Daylight: {day_length:.1f} hours, "
                   f"sunrise: {sunrise_utc.strftime('%H:%M')}, "
                   f"sunset: {sunset_utc.strftime('%H:%M')}")

        return daylight_info

    except Exception as e:
        logger.error(f"Failed to calculate daylight info: {e}")
        raise


def is_after_dark(lat: float, lon: float, practice_datetime: datetime) -> bool:
    """
    Determine if a practice time is after dark (after civil twilight ends).

    Civil twilight is when the sun is 6 degrees below horizon -
    sufficient light for outdoor activities without artificial lighting.

    Args:
        lat: Latitude
        lon: Longitude
        practice_datetime: Practice start time

    Returns:
        True if practice is after dark, False otherwise
    """
    logger.info(f"Checking if {practice_datetime} is after dark at ({lat},{lon})")

    try:
        daylight_info = get_daylight_info(lat, lon, practice_datetime)

        # Compare practice time to civil twilight end
        # If practice starts after dusk, it's a dark practice
        # Convert practice_datetime to naive UTC for comparison
        if practice_datetime.tzinfo:
            # Convert to UTC first, then strip tzinfo
            practice_utc = practice_datetime.astimezone(timezone.utc).replace(tzinfo=None)
        else:
            # Assume naive datetime is already in UTC
            practice_utc = practice_datetime
        is_dark = practice_utc >= daylight_info.civil_twilight_end

        logger.info(f"Practice {'is' if is_dark else 'is not'} after dark "
                   f"(dusk at {daylight_info.civil_twilight_end.strftime('%H:%M')})")

        return is_dark

    except Exception as e:
        logger.error(f"Failed to check dark status: {e}")
        # Default to False (assume daylight) on error
        return False


def is_during_twilight(lat: float, lon: float, practice_datetime: datetime) -> bool:
    """
    Determine if a practice time is during civil twilight.

    Useful for practices that start in daylight but may finish in dusk.

    Args:
        lat: Latitude
        lon: Longitude
        practice_datetime: Practice start time

    Returns:
        True if during twilight period, False otherwise
    """
    try:
        daylight_info = get_daylight_info(lat, lon, practice_datetime)

        # Check if time is between sunset and dusk
        # Convert practice_datetime to naive UTC for comparison
        if practice_datetime.tzinfo:
            # Convert to UTC first, then strip tzinfo
            practice_utc = practice_datetime.astimezone(timezone.utc).replace(tzinfo=None)
        else:
            # Assume naive datetime is already in UTC
            practice_utc = practice_datetime
        in_twilight = (daylight_info.sunset <= practice_utc <
                      daylight_info.civil_twilight_end)

        return in_twilight

    except Exception as e:
        logger.error(f"Failed to check twilight status: {e}")
        return False
