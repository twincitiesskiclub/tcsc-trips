"""
Air Quality Index (AQI) integration using EPA AirNow API.

Provides AQI data for practice locations to ensure member safety.
"""

import logging
import os
import time
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass
import requests

logger = logging.getLogger(__name__)

# AirNow API endpoints
AIRNOW_FORECAST_URL = "https://www.airnowapi.org/aq/forecast/latLong/"
AIRNOW_CURRENT_URL = "https://www.airnowapi.org/aq/observation/latLong/current/"

# Rate limiting
MIN_REQUEST_INTERVAL_SECONDS = 10
_last_request_time: Optional[float] = None

# Simple cache
_cache: dict = {}
CACHE_TTL_MINUTES = 30


@dataclass
class AirQualityInfo:
    """Air quality information for a location."""
    aqi: int
    category: str  # Good, Moderate, Unhealthy for Sensitive Groups, Unhealthy, etc.
    pollutant: str  # Primary pollutant (PM2.5, O3, etc.)
    reporting_area: str
    date_observed: datetime
    source: str = 'AirNow'

    @property
    def is_safe_for_exercise(self) -> bool:
        """AQI <= 100 is generally safe for outdoor exercise."""
        return self.aqi <= 100

    @property
    def requires_cancellation(self) -> bool:
        """AQI >= 151 (Unhealthy) requires cancellation per spec."""
        return self.aqi >= 151


def _should_rate_limit() -> bool:
    """Check if we should rate limit the next request."""
    global _last_request_time
    if _last_request_time is None:
        return False
    elapsed = time.time() - _last_request_time
    return elapsed < MIN_REQUEST_INTERVAL_SECONDS


def _update_rate_limit():
    """Update the last request timestamp."""
    global _last_request_time
    _last_request_time = time.time()


def _get_cache_key(lat: float, lon: float) -> str:
    """Generate cache key from coordinates (rounded to reduce cache misses)."""
    return f"{round(lat, 2)}:{round(lon, 2)}"


def _is_cache_valid(cache_entry: dict) -> bool:
    """Check if a cache entry is still valid."""
    if not cache_entry:
        return False
    cached_at = cache_entry.get('cached_at')
    if not cached_at:
        return False
    age = datetime.utcnow() - cached_at
    return age < timedelta(minutes=CACHE_TTL_MINUTES)


def get_air_quality(lat: float, lon: float) -> Optional[AirQualityInfo]:
    """
    Get current air quality for a location.

    Args:
        lat: Latitude
        lon: Longitude

    Returns:
        AirQualityInfo dataclass or None if unavailable
    """
    logger.info(f"Fetching air quality for ({lat}, {lon})")

    # Check cache first
    cache_key = _get_cache_key(lat, lon)
    if cache_key in _cache and _is_cache_valid(_cache[cache_key]):
        logger.info("Returning cached AQI data")
        return _cache[cache_key]['data']

    # Get API key from environment
    api_key = os.environ.get('AIRNOW_API_KEY')
    if not api_key:
        logger.warning("AIRNOW_API_KEY not configured - AQI checks disabled")
        return None

    # Rate limit check
    if _should_rate_limit():
        wait_time = MIN_REQUEST_INTERVAL_SECONDS - (time.time() - _last_request_time)
        logger.warning(f"Rate limiting AirNow request, waiting {wait_time:.1f}s")
        time.sleep(wait_time)

    try:
        # Query current observations
        params = {
            'format': 'application/json',
            'latitude': lat,
            'longitude': lon,
            'distance': 50,  # Search within 50 miles
            'API_KEY': api_key
        }

        response = requests.get(AIRNOW_CURRENT_URL, params=params, timeout=10)
        _update_rate_limit()
        response.raise_for_status()

        data = response.json()

        if not data:
            logger.warning("No AQI data available for location")
            return None

        # AirNow returns a list of observations, one per pollutant
        # Find the one with the highest AQI (worst air quality)
        worst = max(data, key=lambda x: x.get('AQI', 0))

        aqi_info = AirQualityInfo(
            aqi=worst.get('AQI', 0),
            category=(worst.get('Category') or {}).get('Name', 'Unknown'),
            pollutant=worst.get('ParameterName', 'Unknown'),
            reporting_area=worst.get('ReportingArea', 'Unknown'),
            date_observed=datetime.utcnow()
        )

        logger.info(f"AQI: {aqi_info.aqi} ({aqi_info.category}) - {aqi_info.pollutant}")

        # Cache the result
        _cache[cache_key] = {
            'data': aqi_info,
            'cached_at': datetime.utcnow()
        }

        return aqi_info

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch AQI data: {e}")
        return None
    except (KeyError, ValueError, TypeError) as e:
        logger.error(f"Failed to parse AQI response: {e}")
        return None


def clear_cache():
    """Clear the AQI cache (useful for testing)."""
    global _cache
    _cache = {}
    logger.info("Cleared AQI cache")
