"""
National Weather Service (NWS) API integration for weather data.

The NWS API is free and requires no API key. It provides hourly forecasts
and weather alerts for US locations.

API Documentation: https://www.weather.gov/documentation/services-web-api
"""

import logging
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.practices.interfaces import WeatherConditions, WeatherAlert

logger = logging.getLogger(__name__)

# NWS API requires a User-Agent header
USER_AGENT = "TCSC Practice Management (contact@twincitiesskiclub.org)"
BASE_URL = "https://api.weather.gov"

# Thresholds for extreme conditions
EXTREME_COLD_THRESHOLD_F = -10.0
EXTREME_HEAT_THRESHOLD_F = 95.0

# Cache TTL
GRID_CACHE_HOURS = 24  # Grid coordinates don't change
FORECAST_CACHE_MINUTES = 15  # Weather forecasts update frequently

# Forecast cache with 15-minute TTL
_forecast_cache = {}


def _is_forecast_cache_valid(cache_entry: dict) -> bool:
    """Check if a forecast cache entry is still valid."""
    if not cache_entry:
        return False
    cached_at = cache_entry.get('cached_at')
    if not cached_at or not isinstance(cached_at, datetime):
        return False
    age = datetime.utcnow() - cached_at
    return age < timedelta(minutes=FORECAST_CACHE_MINUTES)


def _get_session() -> requests.Session:
    """Create a requests session with retry logic and proper headers."""
    session = requests.Session()
    session.headers.update({
        'User-Agent': USER_AGENT,
        'Accept': 'application/geo+json'
    })

    # Retry on connection errors and 5xx errors
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


@lru_cache(maxsize=100)
def _get_grid_coordinates(lat: float, lon: float) -> dict:
    """
    Get NWS grid coordinates for a lat/lon point.

    This is cached for 24 hours since grid coordinates don't change.
    Cache key is rounded to 4 decimal places (~11 meters) to improve hit rate.

    Returns dict with: gridId, gridX, gridY, forecastHourly URL
    """
    # Round coordinates to reduce cache misses for nearby points
    lat_rounded = round(lat, 4)
    lon_rounded = round(lon, 4)

    logger.info(f"Fetching NWS grid coordinates for {lat_rounded},{lon_rounded}")

    session = _get_session()
    url = f"{BASE_URL}/points/{lat_rounded},{lon_rounded}"

    try:
        response = session.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        properties = data.get('properties', {})

        grid_info = {
            'gridId': properties.get('gridId'),
            'gridX': properties.get('gridX'),
            'gridY': properties.get('gridY'),
            'forecastHourly': properties.get('forecastHourly'),
            'forecastOffice': properties.get('forecastOffice')
        }

        logger.info(f"Grid coordinates: {grid_info['gridId']} ({grid_info['gridX']},{grid_info['gridY']})")
        return grid_info

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch grid coordinates: {e}")
        raise


def _get_hourly_forecast(grid_id: str, grid_x: int, grid_y: int) -> list[dict]:
    """
    Get hourly forecast for a grid point.

    Returns list of hourly forecast periods.
    Cached for 15 minutes to reduce API calls.
    """
    # Create cache key from grid coordinates
    cache_key = f"{grid_id}:{grid_x}:{grid_y}"

    # Check cache first
    cache_entry = _forecast_cache.get(cache_key)
    if _is_forecast_cache_valid(cache_entry):
        logger.info(f"Using cached forecast for grid {grid_id} ({grid_x},{grid_y})")
        return cache_entry['periods']

    logger.info(f"Fetching hourly forecast for grid {grid_id} ({grid_x},{grid_y})")

    session = _get_session()
    url = f"{BASE_URL}/gridpoints/{grid_id}/{grid_x},{grid_y}/forecast/hourly"

    try:
        response = session.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        periods = data.get('properties', {}).get('periods', [])
        logger.info(f"Retrieved {len(periods)} hourly forecast periods")

        # Store in cache
        _forecast_cache[cache_key] = {
            'periods': periods,
            'cached_at': datetime.utcnow()
        }

        return periods

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch hourly forecast: {e}")
        raise


def _find_closest_forecast(periods: list[dict], target_datetime: datetime) -> Optional[dict]:
    """
    Find the forecast period closest to the target datetime.

    NWS provides hourly forecasts with startTime for each period.
    """
    if not periods:
        return None

    closest_period = None
    min_diff = None

    for period in periods:
        start_time_str = period.get('startTime')
        if not start_time_str:
            continue

        # Parse ISO 8601 datetime
        try:
            start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
            # Convert to naive datetime in UTC for comparison
            start_time_naive = start_time.replace(tzinfo=None) if start_time.tzinfo else start_time
            target_naive = target_datetime.replace(tzinfo=None) if target_datetime.tzinfo else target_datetime

            diff = abs((start_time_naive - target_naive).total_seconds())

            if min_diff is None or diff < min_diff:
                min_diff = diff
                closest_period = period
        except ValueError as e:
            logger.warning(f"Failed to parse forecast time {start_time_str}: {e}")
            continue

    if closest_period:
        logger.info(f"Found forecast {min_diff/3600:.1f} hours from target time")

    return closest_period


def _calculate_wind_chill(temp_f: float, wind_mph: float) -> float:
    """
    Calculate wind chill using NWS formula.

    Formula only valid for temps <= 50F and wind >= 3 mph.
    """
    if temp_f > 50 or wind_mph < 3:
        return temp_f

    wind_chill = (35.74 + 0.6215 * temp_f -
                  35.75 * (wind_mph ** 0.16) +
                  0.4275 * temp_f * (wind_mph ** 0.16))

    return round(wind_chill, 1)


def _calculate_heat_index(temp_f: float, humidity: float) -> float:
    """
    Calculate heat index using simplified formula.

    Only applies when temp >= 80F.
    """
    if temp_f < 80:
        return temp_f

    # Simplified heat index formula
    heat_index = (-42.379 + 2.04901523 * temp_f + 10.14333127 * humidity -
                  0.22475541 * temp_f * humidity - 0.00683783 * temp_f ** 2 -
                  0.05481717 * humidity ** 2 + 0.00122874 * temp_f ** 2 * humidity +
                  0.00085282 * temp_f * humidity ** 2 - 0.00000199 * temp_f ** 2 * humidity ** 2)

    return round(heat_index, 1)


def _parse_forecast_period(period: dict, target_datetime: datetime, alerts: list = None) -> WeatherConditions:
    """
    Parse a forecast period into WeatherConditions dataclass.
    """
    if alerts is None:
        alerts = []

    temp_f = float(period.get('temperature') or 0)

    # Parse wind speed, handling various formats
    wind_speed_str = period.get('windSpeed', '0 mph')
    try:
        wind_speed_mph = float(wind_speed_str.split()[0])
    except (ValueError, IndexError):
        wind_speed_mph = 0.0

    wind_direction = period.get('windDirection', '')
    precip_chance = float((period.get('probabilityOfPrecipitation') or {}).get('value') or 0)
    humidity = float((period.get('relativeHumidity') or {}).get('value') or 50)

    # Calculate feels-like temperature
    if temp_f <= 50 and wind_speed_mph >= 3:
        feels_like = _calculate_wind_chill(temp_f, wind_speed_mph)
    elif temp_f >= 80:
        feels_like = _calculate_heat_index(temp_f, humidity)
    else:
        feels_like = temp_f

    # Determine extreme conditions
    is_extreme_cold = feels_like < EXTREME_COLD_THRESHOLD_F
    is_extreme_heat = feels_like > EXTREME_HEAT_THRESHOLD_F

    # Check for lightning threat in short forecast
    short_forecast = period.get('shortForecast', '').lower()
    has_lightning = 'thunder' in short_forecast or 'lightning' in short_forecast

    return WeatherConditions(
        temperature_f=temp_f,
        feels_like_f=feels_like,
        wind_speed_mph=wind_speed_mph,
        wind_direction=wind_direction,
        precipitation_chance=precip_chance,
        conditions_summary=period.get('shortForecast', ''),
        humidity=humidity,
        has_lightning_threat=has_lightning,
        is_extreme_cold=is_extreme_cold,
        is_extreme_heat=is_extreme_heat,
        alerts=alerts,
        forecast_time=target_datetime,
        fetched_at=datetime.utcnow(),
        source='NWS'
    )


def get_weather_forecast(lat: float, lon: float, target_datetime: datetime) -> WeatherConditions:
    """
    Get weather conditions for a specific location and time.

    Args:
        lat: Latitude
        lon: Longitude
        target_datetime: Target datetime for forecast

    Returns:
        WeatherConditions dataclass

    Raises:
        requests.exceptions.RequestException: If API calls fail
    """
    logger.info(f"Getting weather for ({lat},{lon}) at {target_datetime}")

    # Get grid coordinates (cached)
    grid_info = _get_grid_coordinates(lat, lon)

    # Validate required grid coordinates
    if not grid_info.get('gridId') or grid_info.get('gridX') is None or grid_info.get('gridY') is None:
        raise ValueError(f"Could not determine NWS grid coordinates for ({lat},{lon})")

    # Get hourly forecast
    periods = _get_hourly_forecast(
        grid_info['gridId'],
        grid_info['gridX'],
        grid_info['gridY']
    )

    # Find closest forecast to target time
    closest_period = _find_closest_forecast(periods, target_datetime)

    if not closest_period:
        raise ValueError(f"No forecast data available for {target_datetime}")

    # Fetch weather alerts (before constructing dataclass)
    alerts = []
    try:
        alerts = get_weather_alerts(lat, lon)
    except Exception as e:
        logger.warning(f"Failed to fetch weather alerts: {e}")
        # Continue without alerts rather than failing

    # Parse into WeatherConditions with alerts included
    weather = _parse_forecast_period(closest_period, target_datetime, alerts)

    return weather


def get_weather_alerts(lat: float, lon: float) -> list[WeatherAlert]:
    """
    Get active weather alerts for a location.

    Args:
        lat: Latitude
        lon: Longitude

    Returns:
        List of WeatherAlert dataclasses
    """
    logger.info(f"Fetching weather alerts for ({lat},{lon})")

    session = _get_session()
    url = f"{BASE_URL}/alerts/active"
    params = {'point': f"{lat},{lon}"}

    try:
        response = session.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        features = data.get('features', [])
        alerts = []

        for feature in features:
            props = feature.get('properties', {})

            # Parse timestamps
            try:
                effective = datetime.fromisoformat(props.get('effective', '').replace('Z', '+00:00'))
                expires = datetime.fromisoformat(props.get('expires', '').replace('Z', '+00:00'))

                # Convert to naive UTC
                if effective.tzinfo:
                    effective = effective.replace(tzinfo=None)
                if expires.tzinfo:
                    expires = expires.replace(tzinfo=None)

                alert = WeatherAlert(
                    event=props.get('event', 'Unknown'),
                    severity=props.get('severity', 'Unknown').lower(),
                    headline=props.get('headline', ''),
                    description=props.get('description', ''),
                    effective=effective,
                    expires=expires
                )
                alerts.append(alert)

            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse alert: {e}")
                continue

        logger.info(f"Found {len(alerts)} active weather alerts")
        return alerts

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch weather alerts: {e}")
        # Return empty list rather than raising - alerts are supplementary
        return []


# Backwards compatibility alias (deprecated)
get_weather_for_location = get_weather_forecast
