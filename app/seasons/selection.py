"""Pick the one season the public marketing site should describe.

Deliberately NOT ``Season.is_current``: that flag is set by the "Activate
Season" admin action, which is a bulk write across every user's status.
Nobody is going to run it to correct the website, so the website must not
depend on it.
"""
from __future__ import annotations

from datetime import datetime


def span_start(season) -> datetime | None:
    """Earliest moment any registration window for this season opens."""
    starts = [s for s in (season.returning_start, season.new_start) if s]
    return min(starts) if starts else None


def span_end(season) -> datetime | None:
    """Latest moment any registration window for this season closes."""
    ends = [e for e in (season.returning_end, season.new_end) if e]
    return max(ends) if ends else None


def select_season(seasons, now: datetime):
    """The season taking registrations now, else the soonest one ahead, else
    the most recently ended. ``None`` when no season has a window at all.

    Ties break on ``id`` so a given database state always yields the same
    answer regardless of query ordering.
    """
    candidates = sorted(
        (s for s in seasons if span_start(s) is not None),
        key=lambda s: (span_start(s), s.id or 0),
    )
    if not candidates:
        return None

    for season in candidates:
        end = span_end(season)
        if span_start(season) <= now and (end is None or now <= end):
            return season

    for season in candidates:
        if span_start(season) > now:
            return season

    ended = [s for s in candidates if span_end(s) is not None]
    if ended:
        return max(ended, key=lambda s: (span_end(s), -(s.id or 0)))
    return None
