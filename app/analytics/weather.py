"""Historical weather fetching and cache-only session enrichment.

Only fetch_missing_weather uses the network or commits. Rebuilds call
apply_weather, which reads the cache and calculates sunset locally.
"""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
import logging

import requests
from sqlalchemy.dialects.postgresql import insert

from app.analytics.models import PracticeSession, WeatherHour
from app.integrations.daylight import get_daylight_info
from app.models import db
from app.utils import CENTRAL_TZ, today_central

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"
HOURLY_VARS = ("temperature_2m", "apparent_temperature", "precipitation", "snowfall", "snow_depth", "wind_speed_10m", "weather_code")

_INCH_FACTORS = {"mm": 1 / 25.4, "cm": 1 / 2.54, "m": 1 / 0.0254, "inch": 1, "ft": 12}
_START_FIELDS = ("temp_f", "feels_like_f", "wind_mph", "snow_depth_in", "weather_code")


def to_inches(value, unit: str) -> float | None:
    """Convert a documented precipitation/depth unit; reject unknown units."""
    if unit not in _INCH_FACTORS:
        raise ValueError(f"Unknown Open-Meteo length unit: {unit!r}")
    return None if value is None else float(value) * _INCH_FACTORS[unit]


def fetch_hours(lat: float, lon: float, start: date, end: date, *, http_get=requests.get) -> list[dict]:
    """Fetch a complete response as naive Central hours, or log and return []."""
    try:
        response = http_get(OPEN_METEO_URL, params={
            "latitude": lat, "longitude": lon,
            "start_date": start.isoformat(), "end_date": end.isoformat(),
            "hourly": ",".join(HOURLY_VARS), "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph", "precipitation_unit": "inch",
            "timezone": "America/Chicago",
        }, timeout=30)
        if response.status_code != 200:
            raise ValueError(f"HTTP {response.status_code}")
        body = response.json()
        if body.get("error"):
            raise ValueError("API error response")
        hourly, units = body["hourly"], body["hourly_units"]
        for variable, expected in {
            "temperature_2m": "°F", "apparent_temperature": "°F",
            "wind_speed_10m": "mp/h", "weather_code": "wmo code",
        }.items():
            if units[variable] != expected:
                raise ValueError(f"Unknown Open-Meteo {variable} unit: {units[variable]!r}")
        for variable in ("precipitation", "snowfall", "snow_depth"):
            to_inches(None, units[variable])  # Validate even if every value is null.
        times = hourly["time"]
        if any(len(hourly[variable]) != len(times) for variable in HOURLY_VARS):
            raise ValueError("Mismatched hourly array lengths")
        hours = []
        for index, timestamp in enumerate(times):
            hour = datetime.fromisoformat(timestamp)
            if hour.tzinfo is not None:
                hour = hour.astimezone(CENTRAL_TZ).replace(tzinfo=None)
            hours.append({
                "hour_local": hour,
                "temp_f": hourly["temperature_2m"][index],
                "feels_like_f": hourly["apparent_temperature"][index],
                "wind_mph": hourly["wind_speed_10m"][index],
                "weather_code": hourly["weather_code"][index],
                "precip_in": to_inches(hourly["precipitation"][index], units["precipitation"]),
                "snowfall_in": to_inches(hourly["snowfall"][index], units["snowfall"]),
                "snow_depth_in": to_inches(hourly["snow_depth"][index], units["snow_depth"]),
            })
        return hours
    except Exception as exc:
        logger.warning("Open-Meteo fetch failed for (%s, %s), %s to %s: %s", lat, lon, start, end, exc)
        return []


def session_weather(start: datetime, hours: dict[datetime, WeatherHour]) -> dict:
    """Use the start hour and sum available observations in the given windows.

    Missing/null observations are excluded from sums. An entirely unknown
    window stays null, rather than being reported as zero precipitation.
    """
    if start.tzinfo is not None:
        start = start.astimezone(CENTRAL_TZ).replace(tzinfo=None)
    hour = start.replace(minute=0, second=0, microsecond=0)
    first = hours.get(hour)
    result = {field: getattr(first, field, None) for field in _START_FIELDS}

    def total(field, offsets):
        values = [getattr(hours.get(hour + timedelta(hours=offset)), field, None) for offset in offsets]
        known = [value for value in values if value is not None]
        return sum(known) if known else None

    result.update(
        precip_in=total("precip_in", range(2)),
        snowfall_in=total("snowfall_in", range(2)),
        snowfall_prior_24h_in=total("snowfall_in", range(-24, 0)),
    )
    return result


def _groups(sessions):
    groups = defaultdict(list)
    for session in sessions:
        if any(value is None for value in (session.lat, session.lon, session.date, session.start_time)):
            continue
        groups[(round(session.lat, 2), round(session.lon, 2))].append(session)
    return groups


def _start(session):
    return datetime.combine(session.date, session.start_time)


def _cached_hours(lat, lon, sessions):
    starts = [_start(session).replace(minute=0, second=0, microsecond=0) for session in sessions]
    rows = WeatherHour.query.filter(
        WeatherHour.lat == lat, WeatherHour.lon == lon,
        WeatherHour.hour_local >= min(starts) - timedelta(hours=24),
        WeatherHour.hour_local <= max(starts) + timedelta(hours=1),
    ).populate_existing().all()
    return {row.hour_local: row for row in rows}


def apply_weather(sessions: list[PracticeSession]) -> int:
    """Fill from cached hours and local astronomy; return cache-hit sessions.

    Sunset is calculated even when weather is not yet cached. No commit and
    no network access occur here.
    """
    filled = 0
    for (lat, lon), group in _groups(sessions).items():
        hours = _cached_hours(lat, lon, group)
        for session in group:
            start = _start(session)
            for field, value in session_weather(start, hours).items():
                setattr(session, field, value)
            sunset = get_daylight_info(session.lat, session.lon, start).sunset
            # The existing integration stores naive UTC; also accept aware
            # sunsets as described by the analytics adapter contract.
            if sunset.tzinfo is None:
                sunset = sunset.replace(tzinfo=timezone.utc)
            session.minutes_after_sunset = int((CENTRAL_TZ.localize(start) - sunset).total_seconds() / 60)
            if start.replace(minute=0, second=0, microsecond=0) in hours:
                filled += 1
    return filled


def fetch_missing_weather(*, today: date | None = None, http_get=requests.get) -> dict:
    """Fetch missing start hours older than the archive delay, then commit.

    Each location gets one date range, including the prior day for snowfall.
    Failures leave its hours absent so the next invocation retries them.
    """
    cutoff = (today if today is not None else today_central()) - timedelta(days=6)
    stats = {"locations": 0, "hours": 0, "sessions": 0, "errors": 0}
    candidates = PracticeSession.query.filter(PracticeSession.date <= cutoff).all()
    pending = []
    try:
        for (lat, lon), group in _groups(candidates).items():
            cached = _cached_hours(lat, lon, group)
            missing = [session for session in group
                       if _start(session).replace(minute=0, second=0, microsecond=0) not in cached]
            if not missing:
                continue
            stats["locations"] += 1
            pending.extend(missing)
            hours = fetch_hours(lat, lon, min(s.date for s in missing) - timedelta(days=1),
                                max(s.date for s in missing), http_get=http_get)
            if not hours:
                stats["errors"] += 1
                continue
            fetched_at = datetime.utcnow()
            # The cache's naive local key cannot distinguish repeated DST
            # hours. Keep the final observation, avoiding duplicate upsert keys.
            # Archive-lag placeholders must remain missing so a later run retries.
            unique = {hour["hour_local"]: dict(hour, lat=lat, lon=lon, fetched_at=fetched_at)
                      for hour in hours
                      if any(hour[field] is not None
                             for field in (*_START_FIELDS, "precip_in", "snowfall_in"))}
            rows = list(unique.values())
            for offset in range(0, len(rows), 1000):
                stmt = insert(WeatherHour).values(rows[offset:offset + 1000])
                db.session.execute(stmt.on_conflict_do_update(
                    index_elements=["lat", "lon", "hour_local"],
                    set_={key: stmt.excluded[key] for key in rows[0] if key not in ("lat", "lon", "hour_local")},
                ))
            stats["hours"] += len(rows)
        stats["sessions"] = apply_weather(pending)
        db.session.commit()
        return stats
    except Exception:
        db.session.rollback()
        raise
