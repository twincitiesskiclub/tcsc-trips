"""Stats for the daily season registration recap.

Pure data layer: queries only. Slack rendering lives in
app/slack/season_recap.py, scheduling in app/scheduler.py.
"""
from datetime import timedelta

from app.constants import UserSeasonStatus
from app.models import UserSeason
from app.utils import utc_naive_to_central_naive

# PENDING_LOTTERY and ACTIVE count as registrations; any dropped status
# does not. (Status values are plain strings, not Enums.)
COUNTED_STATUSES = (UserSeasonStatus.PENDING_LOTTERY, UserSeasonStatus.ACTIVE)


def _counted_rows(season_id):
    return UserSeason.query.filter(
        UserSeason.season_id == season_id,
        UserSeason.status.in_(COUNTED_STATUSES),
    ).all()


def _split_counts(rows):
    new = sum(1 for r in rows if r.registration_type == 'new')
    returning = sum(1 for r in rows if r.registration_type == 'returning')
    return {"new": new, "returning": returning, "total": len(rows)}


def _window(start_utc, end_utc, for_date):
    """Central-date view of a UTC window; None when it isn't fully set,
    matching Season.is_open_for's both-ends-required rule."""
    if not (start_utc and end_utc):
        return None
    start = utc_naive_to_central_naive(start_utc).date()
    end = utc_naive_to_central_naive(end_utc).date()
    is_open = start <= for_date <= end
    return {
        "start": start,
        "end": end,
        "is_open": is_open,
        "day_number": (for_date - start).days + 1 if is_open else None,
        "days_remaining": (end - for_date).days if is_open else None,
        "length_days": (end - start).days + 1,
    }


def should_post(season, today):
    """The cadence gate: post while a window is open, and for 7 days after
    the last one closes so leadership sees the final tally settle."""
    windows = [w for w in (
        _window(season.returning_start, season.returning_end, today),
        _window(season.new_start, season.new_end, today),
    ) if w]
    if not windows:
        return False
    if any(w["is_open"] for w in windows):
        return True
    last_end = max(w["end"] for w in windows)
    return 0 <= (today - last_end).days <= 7


def build_recap(season, for_date):
    """Stats dict for the recap covering the Central date `for_date`."""
    season_rows = _counted_rows(season.id)
    day_rows = [r for r in season_rows if r.registration_date == for_date]
    prev_rows = [r for r in season_rows
                 if r.registration_date == for_date - timedelta(days=1)]

    totals = _split_counts(season_rows)
    limit = season.registration_limit
    totals["registration_limit"] = limit
    totals["pct_of_limit"] = (
        round(100 * totals["total"] / limit) if limit else None)

    return {
        "season_id": season.id,
        "season_name": season.name,
        "for_date": for_date,
        "yesterday": _split_counts(day_rows),
        "previous_day_total": len(prev_rows),
        "season_totals": totals,
        "windows": {
            "returning": _window(
                season.returning_start, season.returning_end, for_date),
            "new": _window(season.new_start, season.new_end, for_date),
        },
    }
