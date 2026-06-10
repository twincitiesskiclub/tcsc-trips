"""Assemble per-location conditions for the public marketing-site API.

Thin adapters around the real Skipper integrations (NWS weather and the
SkinnySkI trail scraper). Each adapter returns None on any failure so the
endpoint degrades gracefully instead of erroring.
"""
from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from app.conditions.locations import LOCATIONS, Location
from app.conditions.wax import recommend_wax
from app.integrations import trail_conditions as _trail_integration
from app.integrations import weather as _weather_integration
from app.utils import now_central_naive

logger = logging.getLogger(__name__)

CENTRAL_TZ = ZoneInfo('America/Chicago')


def get_current_temp_f(lat: float, lon: float) -> float | None:
    """Current temperature in Fahrenheit via the NWS hourly forecast.

    The integration exposes get_weather_forecast(lat, lon, target_datetime)
    returning a WeatherConditions dataclass; the period closest to now is
    treated as current. Returns None on any failure.
    """
    try:
        weather = _weather_integration.get_weather_forecast(lat, lon, now_central_naive())
        return weather.temperature_f
    except Exception as e:
        logger.warning(f"Weather lookup failed for ({lat},{lon}): {e}")
        return None


def get_wind_chill_f(lat: float, lon: float) -> float | None:
    """Feels-like temperature (wind chill or heat index) in Fahrenheit.

    Uses WeatherConditions.feels_like_f; the underlying forecast call is
    cached by the integration, so this does not duplicate the API hit.
    Returns None on any failure.
    """
    try:
        weather = _weather_integration.get_weather_forecast(lat, lon, now_central_naive())
        return weather.feels_like_f
    except Exception as e:
        logger.warning(f"Wind chill lookup failed for ({lat},{lon}): {e}")
        return None


def get_trail_conditions(slug: str) -> str | None:
    """Snow/ski quality string for a location slug via the SkinnySkI scraper.

    The integration takes a location name and fuzzy-matches against scraped
    reports, so the slug is de-slugged before lookup. Returns the ski_quality
    string (e.g. 'good', 'fair') or None on any failure.
    """
    try:
        condition = _trail_integration.get_trail_conditions(slug.replace('-', ' '))
        if condition is None:
            return None
        return condition.ski_quality
    except Exception as e:
        logger.warning(f"Trail conditions lookup failed for '{slug}': {e}")
        return None


def _build_location_entry(loc: Location) -> dict:
    """Build the per-location dict for the API response."""
    temp_f = get_current_temp_f(loc.lat, loc.lon)
    wind_chill_f = get_wind_chill_f(loc.lat, loc.lon)
    snow_conditions = get_trail_conditions(loc.skinnyski_slug)

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

    response = {
        'updated_at': datetime.now(CENTRAL_TZ).isoformat(),
        'locations': locations,
    }

    if all(loc['temp_f'] is None for loc in locations):
        response['error'] = 'upstream unavailable'

    return response
