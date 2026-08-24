"""Stats for the daily season registration recap.

Pure data layer: queries only. Slack rendering lives in
app/slack/season_recap.py, scheduling in app/scheduler.py.
"""
from datetime import timedelta

from app.constants import UserSeasonStatus
from app.models import UserSeason

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
    }
