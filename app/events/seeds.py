"""Seed payload builders for events created by data migrations."""

from copy import deepcopy
from datetime import datetime

from app.events.templates import get_template


_DRY_TRI_DESCRIPTION = """Roll. Ride. Run.

TCSC's fall race combines rollerskiing, mountain biking, and trail running at Carver Park Reserve. Race solo, as a relay team of three, or in the run-only 6K. Open to everyone, not just TCSC members.

2026 times to be confirmed

- 7:30 AM — Packet pickup
- 9:00 AM — Long course Wave 1
- 9:05 AM — Long course Wave 2
- 9:30 AM — Short course
- TBD — Run-only 6K start
"""

_PARTICIPANT_GUIDE_URL = (
    "https://docs.google.com/document/d/"
    "14DYvbi9gYWKBf5l3jUw5JZHBa_0G9GQvz3l3xZzE3ME/"
    "edit?usp=sharing"
)


def build_dry_tri_2026() -> dict:
    """Return the complete business-data payload for the 2026 Dry Tri."""
    template = get_template("dry_tri")
    if template is None:
        raise ValueError("Required event template 'dry_tri' was not found")

    price_options = [
        {
            "name": option["name"],
            "description": option.get("description"),
            "price_cents": option["price_cents"],
            "member_price_cents": None,
            "participant_roles": deepcopy(
                option.get("participant_roles", ["Participant"])
            ),
            "sort_order": option.get("sort_order", index),
            "active": option.get("active", True),
        }
        for index, option in enumerate(template["price_options"])
    ]

    return {
        "slug": "dry-tri-2026",
        "name": "TCSC Dry Triathlon 2026",
        "description": _DRY_TRI_DESCRIPTION,
        "location": "Carver Park Reserve — Parley Lake, Victoria",
        "event_date": datetime(2026, 10, 24, 9, 0),
        "signup_start": datetime(2026, 7, 25, 0, 0),
        "signup_end": datetime(2026, 10, 22, 23, 59),
        "capacity": None,
        "status": "draft",
        "audience": "both",
        "details_url": _PARTICIPANT_GUIDE_URL,
        "discount_code": None,
        "custom_questions": deepcopy(template["custom_questions"]),
        "template_key": "dry_tri",
        "price_options": price_options,
    }
