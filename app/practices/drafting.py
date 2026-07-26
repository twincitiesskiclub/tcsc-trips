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

# The built-in schedule when no `practice_days` AppConfig row exists — which
# is the live state of dev (and, as far as we know, prod) today, so this
# default IS the schedule, not a formality. It lives here because this module
# owns the practice_days schedule semantics (see the module docstring), and it
# is imported by every other site that defaults the key (coach weekly summary,
# post refresh, the admin settings endpoint): the drafting copy once said
# Tue/Thu while the coach post said Tue/Thu/Sat, so Saturday practices were
# never drafted while the coach post rendered a permanent empty Saturday
# "Add Practice" placeholder — the duplicate-on-top-of-a-draft trap that
# coach_visible_practices() exists to prevent. One constant, one schedule.
DEFAULT_PRACTICE_DAYS = [
    {"day": "tuesday", "time": "18:00", "active": True},
    {"day": "thursday", "time": "18:00", "active": True},
    {"day": "saturday", "time": "09:00", "active": True},
]


def end_of_next_month(day: date) -> date:
    """Last day of the month after `day`'s month.

    This is the drafting horizon: the bootstrap job runs on the 1st, and
    drafting through the end of *next* month means every configured slot is
    covered by at least two consecutive runs. The previous window — a week
    count normalised back to the Monday of start_date's week — covered only
    `28 - weekday(1st)` days forward, so the tail of most months was never
    drafted by ANY run. The month-long overlap between runs is harmless
    because generate_draft_block() is idempotent.
    """
    year = day.year
    month = day.month + 2
    if month > 12:
        month -= 12
        year += 1
    return date(year, month, 1) - timedelta(days=1)


def expected_slots(start_date: date, end_date: date) -> list[datetime]:
    """Datetimes the practice_days config implies from start_date through
    end_date, both inclusive.

    Walked day by day rather than week by week on purpose: the old
    Monday-normalised weeks window silently shortened the forward range by
    start_date.weekday() days (see end_of_next_month above). No slot earlier
    than start_date is ever returned.
    """
    config = AppConfig.get("practice_days", DEFAULT_PRACTICE_DAYS) or []

    times_by_weekday: dict[int, list[tuple[int, int]]] = {}
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
    misfire grace — and consecutive monthly runs deliberately overlap by a
    whole month (see end_of_next_month) — so duplicated practices would be
    visible chaos.
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


def is_ready(practice: Practice) -> bool:
    """True when a draft has enough detail for someone to judge availability."""
    return not missing_fields(practice)


def drafted_practices_in_window(start_date: date, end_date: date) -> list[Practice]:
    """Draft practices scheduled within the window (inclusive), ordered by date.

    This is the mirror image of published_practices() in app/practices/service.py:
    that helper exists to keep drafts OUT of member-visible listings, while this
    one exists to deliberately query FOR drafts — it backs the readiness nudge,
    whose whole purpose is tracking incomplete drafts before they're published.
    Kept here (rather than inlined in the scheduler) so the one place scheduler
    jobs read draft rows from is a reviewed, named function rather than an
    ad hoc `Practice.query.filter(...)`.
    """
    return (
        Practice.query.filter(
            Practice.is_draft.is_(True),
            Practice.date >= datetime.combine(start_date, datetime.min.time()),
            Practice.date <= datetime.combine(end_date, datetime.max.time()),
        )
        .order_by(Practice.date)
        .all()
    )


def readiness_summary(practices: list[Practice]) -> dict:
    """Counts plus the incomplete drafts and what each is missing."""
    incomplete = [(p, missing_fields(p)) for p in practices if not is_ready(p)]
    return {
        "total": len(practices),
        "ready": len(practices) - len(incomplete),
        "incomplete": sorted(incomplete, key=lambda pair: pair[0].date),
    }
