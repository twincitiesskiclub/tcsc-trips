"""Assemble per-location conditions for the public marketing-site API.

Thin adapters around the real Skipper integrations (NWS weather and the
SkinnySkI trail scraper). Each adapter returns None on any failure so the
endpoint degrades gracefully instead of erroring.
"""
from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from app.conditions.birkie import build_birkie_status
from app.conditions.locations import LOCATIONS, Location
from app.conditions.wax import recommend_wax
from app.integrations import trail_conditions as _trail_integration
from app.integrations import weather as _weather_integration
from app.practices.interfaces import WeatherConditions
from app.utils import now_central_naive

logger = logging.getLogger(__name__)

CENTRAL_TZ = ZoneInfo('America/Chicago')


def get_weather(lat: float, lon: float) -> WeatherConditions | None:
    """Current weather via the NWS hourly forecast, one upstream call.

    The integration exposes get_weather_forecast(lat, lon, target_datetime)
    returning a WeatherConditions dataclass; the period closest to now is
    treated as current. Each call also fetches the uncached /alerts endpoint,
    so callers should read both temperature_f and feels_like_f from this
    single result rather than calling twice. Returns None on any failure.
    """
    try:
        return _weather_integration.get_weather_forecast(lat, lon, now_central_naive())
    except Exception as e:
        logger.warning(f"Weather lookup failed for ({lat},{lon}): {e}")
        return None


def get_trail_conditions(name: str) -> str | None:
    """Snow/ski quality string for a venue via the SkinnySkI scraper.

    The integration fuzzy-matches the given name against scraped reports, so
    callers pass the canonical venue name (e.g. 'Hyland Lake Park Reserve',
    which avoids mismatching St. Paul's 'Highland Park'). Returns the
    ski_quality string (e.g. 'good', 'fair') or None on any failure.
    """
    try:
        condition = _trail_integration.get_trail_conditions(name)
        if condition is None:
            return None
        return condition.ski_quality
    except Exception as e:
        logger.warning(f"Trail conditions lookup failed for '{name}': {e}")
        return None


def _build_location_entry(loc: Location) -> dict:
    """Build the per-location dict for the API response."""
    weather = get_weather(loc.lat, loc.lon)
    temp_f = weather.temperature_f if weather is not None else None
    wind_chill_f = weather.feels_like_f if weather is not None else None
    snow_conditions = get_trail_conditions(loc.skinnyski_name)

    wax_band = recommend_wax(temp_f) if temp_f is not None else None

    return {
        'id': loc.id,
        'name': loc.name,
        'temp_f': round(temp_f) if temp_f is not None else None,
        'wind_chill_f': round(wind_chill_f) if wind_chill_f is not None else None,
        'snow_conditions': snow_conditions,
        'wax_band': wax_band.slug if wax_band is not None else None,
        'wax_label': wax_band.label if wax_band is not None else None,
    }


def build_conditions_response() -> dict:
    """Assemble the full /api/conditions payload."""
    locations = [_build_location_entry(loc) for loc in LOCATIONS]

    # Birkie fever reuses the Telemark entry's trail report (one scraper
    # call serves both the cell and the status).
    telemark = next((entry for entry in locations if entry['id'] == 'telemark'), None)
    birkie = build_birkie_status(
        datetime.now(CENTRAL_TZ).date(),
        telemark['snow_conditions'] if telemark else None,
    )

    response = {
        'updated_at': datetime.now(CENTRAL_TZ).isoformat(),
        'locations': locations,
        'birkie': birkie,
    }

    if all(loc['temp_f'] is None for loc in locations):
        response['error'] = 'upstream unavailable'

    return response
