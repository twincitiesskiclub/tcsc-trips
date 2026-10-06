"""Shape one event for the public marketing site.

Public prices only. Member prices stay hidden until a code is verified on
tcsc.ski (PR #236), and the discount code is a secret, so neither is here.
Timestamps only, no open/closed state: see app/routes/season_api.py for why.
"""
from __future__ import annotations

from app.seasons.payload import _iso


def serialize_public_event(event, registration_path: str) -> dict:
    entries = sorted(
        (option for option in event.price_options if option.active),
        key=lambda option: option.sort_order,
    )
    return {
        "slug": event.slug,
        "name": event.name,
        "location": event.location,
        "description": event.description or "",
        "event_date": _iso(event.event_date),
        "signup_start": _iso(event.signup_start),
        "signup_end": _iso(event.signup_end),
        "registration_path": registration_path,
        "details_url": event.details_url,
        "entries": [
            {
                "name": option.name,
                "description": option.description or "",
                "price_cents": option.price_cents,
            }
            for option in entries
        ],
    }
