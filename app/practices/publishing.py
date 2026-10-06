"""Bot-created practices become member-visible on their own.

The block job drafts sessions with `is_draft=True` ("hidden from members").
`publish_if_ready()` flips that flag the moment a practice has the details
members need, from every save path (admin edit, Slack full edit, the Sunday
coach summary sweep). There is no publish button: a manual publish step
silently held back the Sep 1, 3 and 10 practices.

Visibility is one way. Clearing a location later never hides a practice again.
"""

from datetime import datetime, timedelta

from flask import current_app

from app.models import db
from app.practices.drafting import missing_fields
from app.practices.interfaces import PracticeStatus
from app.utils import now_central_naive

_CANCELLED_BLOCKER = "not cancelled"


def publish_blockers(practice) -> list[str]:
    """What still keeps this practice hidden from members."""
    blockers = missing_fields(practice)
    if practice.status == PracticeStatus.CANCELLED.value:
        blockers.append(_CANCELLED_BLOCKER)
    return blockers


def announcement_run_time(practice_date: datetime) -> datetime:
    """When the announcement job picks this practice up.

    Mirrors run_practice_announcements_job: practices at or after 12:00 are
    announced by the 08:00 run that day, earlier ones by the 20:00 run the
    day before.
    """
    if practice_date.hour >= 12:
        return practice_date.replace(hour=8, minute=0, second=0, microsecond=0)
    day_before = practice_date - timedelta(days=1)
    return day_before.replace(hour=20, minute=0, second=0, microsecond=0)


def publish_if_ready(practice, *, now: datetime | None = None) -> bool:
    """Make a hidden practice visible if nothing blocks it. True if it flipped."""
    if not practice.is_draft or publish_blockers(practice):
        return False

    practice.is_draft = False
    db.session.commit()
    current_app.logger.info("Practice #%s is now visible to members", practice.id)

    now = now or now_central_naive()
    if (
        practice.slack_message_ts is None
        and practice.date > now
        and now >= announcement_run_time(practice.date)
    ):
        _announce_late(practice)
    return True


def _announce_late(practice) -> None:
    """Re-run the announcement job's window for this practice.

    Going through the job (instead of posting directly) keeps strength
    sessions combined. The job only posts practices with no slack_message_ts,
    so re-running a window is safe.
    """
    try:
        from app import scheduler

        scheduler.run_practice_announcements_job(
            current_app._get_current_object(),
            now_override=announcement_run_time(practice.date),
        )
    except Exception:
        current_app.logger.exception(
            "Practice #%s became visible after its announcement run, and the "
            "late announcement failed",
            practice.id,
        )
