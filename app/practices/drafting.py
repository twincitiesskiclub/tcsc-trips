"""Draft sessions from the practice_days schedule.

The block job (app/practices/blocks.py) calls generate_draft_block() for each
two-week block. Drafted sessions are hidden from members (see
published_practices()) until publish_if_ready() finds a location and a type.
"""

from datetime import date, datetime, timedelta

from flask import current_app

from app.models import AppConfig, db
from app.practices.models import Practice

WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

# The built-in schedule when no `practice_days` AppConfig row exists — which
# is the live state of dev (and, as far as we know, prod) today, so this
# default IS the schedule, not a formality. It lives here because this module
# owns the practice_days schedule semantics (see the module docstring), and
# every other site that defaults the key (coach weekly summary, post refresh,
# the admin settings endpoint) imports default_practice_days() below: the
# drafting copy once said Tue/Thu while the coach post said Tue/Thu/Sat, so
# Saturday practices were never drafted while the coach post rendered a
# permanent empty Saturday "Add Practice" placeholder — the
# duplicate-on-top-of-a-draft trap coach_visible_practices() exists to
# prevent. One source, one schedule. A tuple so the sequence itself can't be
# appended to in place.
DEFAULT_PRACTICE_DAYS = (
    {"day": "tuesday", "time": "18:00", "active": True},
    {"day": "thursday", "time": "18:00", "active": True},
    {"day": "saturday", "time": "09:00", "active": True},
)


def default_practice_days() -> list[dict]:
    """A fresh copy of the default schedule, safe to hand to any caller.

    AppConfig.get(key, default) returns the default object itself when the
    row is missing, so passing the shared constant would let one consumer's
    in-place edit (e.g. entry['active'] = False) silently corrupt the
    drafting schedule process-wide until restart. Every read site uses this
    helper instead of the constant.
    """
    return [dict(entry) for entry in DEFAULT_PRACTICE_DAYS]


def expected_slots(start_date: date, end_date: date) -> list[datetime]:
    """Datetimes the practice_days config implies from start_date through
    end_date, both inclusive.

    Walked day by day rather than week by week on purpose: the old
    Monday-normalised weeks window silently shortened the forward range by
    start_date.weekday() days. No slot earlier
    than start_date is ever returned.
    """
    config = AppConfig.get("practice_days", default_practice_days()) or []

    times_by_weekday: dict[int, list[tuple[int, int]]] = {}
    for entry in config:
        if not entry.get("active", True):
            continue
        weekday = WEEKDAYS.get(str(entry.get("day", "")).lower())
        if weekday is None:
            continue
        # `or "18:00"`, not just a dict default: the admin UI's
        # <input type="time"> submits "" when the field is cleared, and an
        # empty string would otherwise fail to parse and drop this weekday out
        # of the whole horizon -- a silent absence, which is the failure class
        # this module exists to eliminate. A stored "" now means "the default
        # time", which is the least surprising reading of an unset field.
        raw_time = str(entry.get("time") or "18:00")
        try:
            hour, minute = (int(part) for part in raw_time.split(":", 1))
            # Range-checked here, inside the guard, because an out-of-range
            # hour parses cleanly as an int and only explodes when the datetime
            # is constructed below -- which used to happen outside any try and
            # took down the whole block run for one
            # bad config row.
            datetime(2000, 1, 1, hour, minute)
        except ValueError:
            current_app.logger.warning(
                "practice_days entry for %s has an unusable time %r; skipping "
                "that entry (no practices will be drafted for it)",
                entry.get("day"), raw_time,
            )
            continue
        times_by_weekday.setdefault(weekday, []).append((hour, minute))

    slots: list[datetime] = []
    day = start_date
    while day <= end_date:
        for hour, minute in times_by_weekday.get(day.weekday(), []):
            slots.append(datetime(day.year, day.month, day.day, hour, minute))
        day += timedelta(days=1)

    return sorted(slots)


def generate_draft_block(start_date: date, end_date: date) -> list[Practice]:
    """Create draft practices for any slot that has none. Returns new rows only.

    Idempotent: the job re-runs on redeploy, manual trigger and APScheduler
    misfire grace, and the block job re-runs daily, so duplicated practices
    would be visible chaos.
    """
    slots = expected_slots(start_date, end_date)
    if not slots:
        return []

    taken = {
        row.date
        for row in Practice.query.with_entities(Practice.date)
        .filter(Practice.date.in_(slots))
        .all()
    }

    created: list[Practice] = []
    for slot in slots:
        if slot in taken:
            continue
        practice = Practice(
            date=slot,
            day_of_week=slot.strftime("%A"),
            is_draft=True,
            leads_needed=2,
        )
        db.session.add(practice)
        created.append(practice)
        # Mark the slot taken NOW: practice_days can hold two entries with
        # the same day and time (update_practice_days does not dedupe), and
        # expected_slots then yields the datetime twice — without this, one
        # admin-UI duplicate would double-draft the slot in the one function
        # whose idempotency is load-bearing.
        taken.add(slot)

    if created:
        db.session.commit()
        current_app.logger.info(
            "Drafted %d practices for %s..%s", len(created), start_date, end_date
        )
    return created


def missing_fields(practice: Practice) -> list[str]:
    """Which of the details that decide whether someone can lead are unset.

    Location, type and time are exactly the three things the spec identifies as
    determining availability, so they are what gate the poll.
    """
    missing: list[str] = []
    if not practice.location_id:
        missing.append("location")
    if not practice.practice_types and not practice.activities:
        missing.append("type")
    if not practice.date:
        missing.append("time")
    return missing
