"""Generate draft practices from the practice_days schedule.

Drafts are invisible to members (see published_practices()) and exist so
coaches and directors can fill in location, type and time before lead
availability is collected against them.
"""

from datetime import date, datetime, timedelta

from flask import current_app

from app.models import AppConfig, db
from app.practices.models import Practice

WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

DEFAULT_PRACTICE_DAYS = [
    {"day": "tuesday", "time": "18:00", "active": True},
    {"day": "thursday", "time": "18:00", "active": True},
]


def expected_slots(start_date: date, weeks: int = 4) -> list[datetime]:
    """Datetimes the practice_days config implies over the window.

    Weeks are normalised to the Monday of the week containing start_date so
    the window has stable, predictable boundaries — but no slot earlier than
    start_date itself is ever returned. The first week may therefore be
    partial; that's correct for "the next N weeks starting today."
    """
    config = AppConfig.get("practice_days", DEFAULT_PRACTICE_DAYS) or []
    slots: list[datetime] = []

    for week in range(weeks):
        week_start = start_date + timedelta(days=7 * week)
        # Normalise to the Monday of that week so the window is stable.
        week_start -= timedelta(days=week_start.weekday())
        for entry in config:
            if not entry.get("active", True):
                continue
            weekday = WEEKDAYS.get(str(entry.get("day", "")).lower())
            if weekday is None:
                continue
            raw_time = str(entry.get("time", "18:00"))
            try:
                hour, minute = (int(part) for part in raw_time.split(":", 1))
            except ValueError:
                current_app.logger.warning(
                    "practice_days entry has unparseable time %r; skipping", raw_time
                )
                continue
            day = week_start + timedelta(days=weekday)
            if day < start_date:
                continue
            slots.append(datetime(day.year, day.month, day.day, hour, minute))

    return sorted(slots)


def generate_draft_block(start_date: date, weeks: int = 4) -> list[Practice]:
    """Create draft practices for any slot that has none. Returns new rows only.

    Idempotent: the job re-runs on redeploy, manual trigger and APScheduler
    misfire grace, and duplicated practices would be visible chaos.
    """
    slots = expected_slots(start_date, weeks)
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

    if created:
        db.session.commit()
        current_app.logger.info(
            "Drafted %d practices for %s (+%d weeks)", len(created), start_date, weeks
        )
    return created
