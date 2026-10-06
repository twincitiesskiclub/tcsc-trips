"""Pick the one event a public page describes for an event series.

The marketing site's Dry Tri page and tcsc.ski/tri both ask "which Dry Tri
is current?" and must get the same answer, so the rule lives here once.
"""
from __future__ import annotations

from datetime import datetime

from .models import Audience, EventStatus


def select_public_event(events, template_key: str, now: datetime):
    """Soonest event on or after ``now``, else the most recent past one.

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
    upcoming = [event for event in candidates if event.event_date >= now]
    if upcoming:
        return min(upcoming, key=lambda event: event.event_date)
    if candidates:
        return max(candidates, key=lambda event: event.event_date)
    return None
