"""Pick the one event a public page describes for an event series.

The marketing site's Dry Tri page and tcsc.ski/tri both ask "which Dry Tri
is current?" and must get the same answer, so the rule lives here once.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta

from ..utils import central_naive_to_utc_naive, utc_naive_to_central_naive
from .models import Audience, EventStatus


def race_day_end(event_date: datetime) -> datetime:
    """Naive UTC instant of the Central midnight that ends the event's day.

    Matches endOfCentralDay in site/src/lib/eventState.ts, so the API keeps
    serving today's race for exactly as long as the page calls it current.
    """
    central = utc_naive_to_central_naive(event_date)
    next_midnight = datetime.combine(central.date() + timedelta(days=1), time())
    return central_naive_to_utc_naive(next_midnight)


def select_public_event(events, template_key: str, now: datetime):
    """Soonest event whose race day has not ended, else the most recent past one.

    Drafts and internal events never reach a public page. A closed event
    still counts: it stopped taking signups but the race is still on.
    """
    candidates = [
        event
        for event in events
        if event.template_key == template_key
        and event.status != EventStatus.DRAFT
        and event.audience != Audience.INTERNAL
    ]
    upcoming = [event for event in candidates if race_day_end(event.event_date) > now]
    if upcoming:
        return min(upcoming, key=lambda event: event.event_date)
    if candidates:
        return max(candidates, key=lambda event: event.event_date)
    return None
