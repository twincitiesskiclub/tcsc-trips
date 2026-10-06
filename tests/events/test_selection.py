from datetime import datetime
from types import SimpleNamespace

from app.events.selection import select_public_event

NOW = datetime(2026, 10, 6, 15, 0)


def _event(slug, when, status="active", audience="both", template_key="dry_tri"):
    return SimpleNamespace(
        slug=slug, event_date=when, status=status, audience=audience, template_key=template_key
    )


def test_soonest_upcoming_wins():
    events = [
        _event("2027", datetime(2027, 10, 23, 14)),
        _event("2026", datetime(2026, 10, 24, 14)),
        _event("2025", datetime(2025, 10, 25, 14)),
    ]
    assert select_public_event(events, "dry_tri", NOW).slug == "2026"


def test_most_recent_past_when_nothing_is_ahead():
    events = [_event("2024", datetime(2024, 10, 26, 14)), _event("2025", datetime(2025, 10, 25, 14))]
    assert select_public_event(events, "dry_tri", NOW).slug == "2025"


def test_closed_events_still_count():
    events = [_event("2026", datetime(2026, 10, 24, 14), status="closed")]
    assert select_public_event(events, "dry_tri", NOW).slug == "2026"


def test_drafts_internal_and_other_series_are_ignored():
    events = [
        _event("draft", datetime(2026, 10, 24, 14), status="draft"),
        _event("internal", datetime(2026, 10, 24, 14), audience="internal"),
        _event("pickleball", datetime(2026, 10, 24, 14), template_key="social"),
    ]
    assert select_public_event(events, "dry_tri", NOW) is None


def test_external_audience_counts():
    events = [_event("2026", datetime(2026, 10, 24, 14), audience="external")]
    assert select_public_event(events, "dry_tri", NOW).slug == "2026"
