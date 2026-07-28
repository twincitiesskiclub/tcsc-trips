from datetime import datetime

from app.events.seeds import build_dry_tri_2026
from app.events.templates import get_template


PARTICIPANT_GUIDE_URL = (
    "https://docs.google.com/document/d/"
    "14DYvbi9gYWKBf5l3jUw5JZHBa_0G9GQvz3l3xZzE3ME/"
    "edit?usp=sharing"
)


def test_dry_tri_2026_builder_returns_exact_event_fields():
    payload = build_dry_tri_2026()

    assert payload["slug"] == "dry-tri-2026"
    assert payload["name"] == "TCSC Dry Triathlon 2026"
    assert (
        payload["location"]
        == "Carver Park Reserve — Parley Lake, Victoria"
    )
    assert payload["event_date"] == datetime(2026, 10, 24, 9, 0)
    assert payload["signup_start"] == datetime(2026, 7, 25, 0, 0)
    assert payload["signup_end"] == datetime(2026, 10, 22, 23, 59)
    assert payload["status"] == "draft"
    assert payload["audience"] == "both"
    assert payload["details_url"] == PARTICIPANT_GUIDE_URL
    assert payload["discount_code"] is None
    assert payload["template_key"] == "dry_tri"


def test_dry_tri_2026_builder_includes_placeholder_schedule():
    description = build_dry_tri_2026()["description"]

    assert "Roll. Ride. Run." in description
    assert "2026 times to be confirmed" in description
    assert "7:30 AM — Packet pickup" in description
    assert "9:00 AM — Long course Wave 1" in description
    assert "9:05 AM — Long course Wave 2" in description
    assert "9:30 AM — Short course" in description
    assert "TBD — Run-only 6K start" in description


def test_dry_tri_2026_builder_copies_dry_tri_template():
    payload = build_dry_tri_2026()
    options = payload["price_options"]
    questions = payload["custom_questions"]

    assert [option["price_cents"] for option in options] == [
        5500,
        10500,
        3000,
    ]
    run_only = next(
        option for option in options if option["name"] == "Run-only 6K"
    )
    assert run_only["participant_roles"] == ["Participant"]
    assert all(option["member_price_cents"] is None for option in options)

    assert len(questions) == 6
    assert [question["required"] for question in questions] == [
        True,
        True,
        False,
        True,
        True,
        False,
    ]
    assert questions == get_template("dry_tri")["custom_questions"]
