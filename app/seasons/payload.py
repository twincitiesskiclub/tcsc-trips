"""Shape the public ``/api/season`` body.

Carries timestamps only. There is deliberately no computed open/closed state:
a state decided here is wrong the moment a window boundary passes, and the
marketing site is a static build that would keep serving it. The site derives
state in the browser from these timestamps instead.
"""
from __future__ import annotations

from datetime import datetime

from .selection import select_season


def _iso(value: datetime | None) -> str | None:
    """Naive-UTC column to an explicit Z-suffixed ISO 8601 string."""
    if value is None:
        return None
    return value.replace(microsecond=0).isoformat() + 'Z'


def serialize_season(season) -> dict:
    return {
        'name': season.name,
        'season_type': season.season_type,
        'year': season.year,
        'price_cents': season.price_cents,
        'returning_start': _iso(season.returning_start),
        'returning_end': _iso(season.returning_end),
        'new_start': _iso(season.new_start),
        'new_end': _iso(season.new_end),
    }


def build_season_payload(seasons, now: datetime) -> dict:
    """One rule, applied per type and then across everything."""
    seasons = list(seasons)
    by_type = {}
    for season_type in sorted({s.season_type for s in seasons if s.season_type}):
        chosen = select_season(
            [s for s in seasons if s.season_type == season_type], now
        )
        if chosen is not None:
            by_type[season_type] = serialize_season(chosen)

    primary = select_season(seasons, now)
    return {
        'generated_at': _iso(now),
        'primary': serialize_season(primary) if primary is not None else None,
        'by_type': by_type,
    }
