"""Stats for the daily season registration recap.

Pure data layer: queries only. Slack rendering lives in
app/slack/season_recap.py, scheduling in app/scheduler.py.
"""
from datetime import timedelta

from app.constants import (
    UserSeasonStatus, VOLUNTEER_COMMITTEES, VOLUNTEER_INTERESTS,
)
from app.models import Season, UserSeason
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
    """Post only on Central dates with an open registration window."""
    windows = [w for w in (
        _window(season.returning_start, season.returning_end, today),
        _window(season.new_start, season.new_end, today),
    ) if w]
    return any(w["is_open"] for w in windows)


def _anchor_date(season):
    """The season's registration-open anchor: earliest window start, as a
    Central date. None when no window start is set."""
    starts = [s for s in (season.returning_start, season.new_start) if s]
    if not starts:
        return None
    return utc_naive_to_central_naive(min(starts)).date()


def _prior_season(season, for_date):
    """Most recent earlier season of the same type that has registrations,
    compared at the same day-offset from its own anchor."""
    anchor = _anchor_date(season)
    if anchor is None:
        return None
    candidates = Season.query.filter(
        Season.season_type == season.season_type,
        Season.id != season.id,
    ).all()
    dated = []
    for candidate in candidates:
        candidate_anchor = _anchor_date(candidate)
        if candidate_anchor and candidate_anchor < anchor:
            dated.append((candidate_anchor, candidate))
    dated.sort(key=lambda pair: pair[0], reverse=True)

    offset = (for_date - anchor).days
    if offset < 0:
        return None
    for prior_anchor, prior in dated:
        rows = _counted_rows(prior.id)
        if not rows:
            continue
        cutoff = prior_anchor + timedelta(days=offset)
        return {
            "name": prior.name,
            "count_at_same_point": sum(
                1 for r in rows if r.registration_date <= cutoff),
            "final_count": len(rows),
        }
    return None


def _volunteer_summary(day_rows):
    """Get Involved answers among the day's registrations. Null interests
    means the question was never asked (pre-question registrant); an empty
    list means they answered and declined -- both count as unanswered here,
    only actual opt-ins are tallied."""
    answered = [r for r in day_rows if r.volunteer_interests]
    interests = {}
    committees = {}
    for row in answered:
        for key in row.volunteer_interests:
            label = VOLUNTEER_INTERESTS.get(key, key)
            interests[label] = interests.get(label, 0) + 1
        if 'committee' in row.volunteer_interests:
            for key in (row.volunteer_committees or []):
                label = VOLUNTEER_COMMITTEES.get(key, key)
                committees[label] = committees.get(label, 0) + 1
    return {
        "answered": len(answered),
        "of": len(day_rows),
        "interests": interests,
        "committees": committees,
    }


def _highlights(for_date, day_rows, season_rows):
    """Fun lines, each included only when true."""
    lines = []
    day_total = len(day_rows)

    # Biggest day of the season so far (ties don't count, nor does 1).
    daily = {}
    for row in season_rows:
        if row.registration_date < for_date:
            daily[row.registration_date] = daily.get(row.registration_date, 0) + 1
    if day_total > 1 and day_total > max(daily.values(), default=0):
        lines.append(
            f"Biggest day of the season so far: {day_total} registrations.")

    # Crossed a multiple of 50 (measured through for_date, so an early
    # same-morning registration can't claim yesterday's milestone).
    through = sum(1 for r in season_rows if r.registration_date <= for_date)
    before = through - day_total
    if through >= 50 and through // 50 > before // 50:
        lines.append(f"Crossed {(through // 50) * 50} total registrations.")

    # Households: two registrations sharing a verified phone number.
    phones = {}
    for row in day_rows:
        phone = row.user.phone_e164 if row.user else None
        if phone:
            phones[phone] = phones.get(phone, 0) + 1
    shared = sum(1 for count in phones.values() if count >= 2)
    if shared == 1:
        lines.append("A household registered together (shared phone number).")
    elif shared > 1:
        lines.append(
            f"{shared} households registered together (shared phone numbers).")

    return lines


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
        "prior_season": _prior_season(season, for_date),
        "volunteer": _volunteer_summary(day_rows),
        "needs_review": UserSeason.query.filter_by(
            season_id=season.id, needs_review=True).count(),
        "highlights": _highlights(for_date, day_rows, season_rows),
    }
