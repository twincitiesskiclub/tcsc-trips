"""Pick the one season the public marketing site should describe.

Deliberately NOT ``Season.is_current``: that flag is set by the "Activate
Season" admin action, which is a bulk write across every user's status.
Nobody is going to run it to correct the website, so the website must not
depend on it.
"""
from __future__ import annotations

from datetime import datetime


def _windows(season):
    """The season's COMPLETE registration windows.

    A half-set window (a start with no end, or vice versa) is not a window
    at all. ``Season.is_open_for`` takes exactly this position -- see
    ``app/models.py:279``, ``if self.new_start and self.new_end`` -- and the
    admin form leaves all four fields optional, so half-set windows are
    reachable. Treating a missing end as "open indefinitely" would let one
    half-configured season outrank a season that is genuinely open today.
    """
    pairs = (
        (season.returning_start, season.returning_end),
        (season.new_start, season.new_end),
    )
    return [(start, end) for start, end in pairs if start and end]


def span_start(season) -> datetime | None:
    """Earliest moment any complete registration window opens."""
    windows = _windows(season)
    return min(start for start, _ in windows) if windows else None


def span_end(season) -> datetime | None:
    """Latest moment any complete registration window closes."""
    windows = _windows(season)
    return max(end for _, end in windows) if windows else None


def select_season(seasons, now: datetime):
    """The season taking registrations now, else the soonest one ahead, else
    the most recently ended. ``None`` when no season has a complete window.

    Ties break on ``id`` so a given database state always yields the same
    answer regardless of query ordering.
    """
    candidates = sorted(
        (s for s in seasons if span_start(s) is not None),
        key=lambda s: (span_start(s), s.id or 0),
    )
    if not candidates:
        return None

    # Every candidate has a complete window, so both bounds are non-null here.
    for season in candidates:
        if span_start(season) <= now <= span_end(season):
            return season

    for season in candidates:
        if span_start(season) > now:
            return season

    return max(candidates, key=lambda s: (span_end(s), -(s.id or 0)))
