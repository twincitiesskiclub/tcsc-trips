from types import SimpleNamespace
from datetime import datetime

from app.slack.blocks.announcements import (
    _activity_label,
    build_practice_announcement_blocks,
    build_practice_details_blocks,
)


def _act(name):
    return SimpleNamespace(name=name, gear_required=None)


def test_activity_label_single():
    assert _activity_label([_act("Classic Ski")]) == "Classic Ski"


def test_activity_label_multiple_joined_with_plus():
    assert _activity_label([_act("Classic Ski"), _act("Skate Ski")]) == "Classic Ski + Skate Ski"


def test_activity_label_empty_falls_back_to_practice():
    assert _activity_label([]) == "Practice"


def _practice(**over):
    base = dict(
        date=datetime(2026, 12, 27, 12, 0),  # Dec 27 2026 is a Sunday
        activities=[_act("Classic Ski")],
        practice_types=[SimpleNamespace(name="Intervals")],
        location=SimpleNamespace(
            name="Theodore Wirth", spot="Trailhead",
            address="1301 Theodore Wirth Pkwy", google_maps_url="https://maps.example/wirth",
            latitude=None, longitude=None, parking_notes="Chalet lot; arrive early.",
            social_location=SimpleNamespace(name="Utepils Brewing", google_maps_url=None),
        ),
        social_location=SimpleNamespace(name="Utepils Brewing", google_maps_url=None),
        workout_description="5 x 4min @ threshold, 2min easy between.",
        logistics_notes="Meet at the flagpole.",
        has_social=True,
        leads=[SimpleNamespace(role=SimpleNamespace(name="COACH"), slack_user_id="U1", display_name="Anders")],
    )
    base.update(over)
    return SimpleNamespace(**base)


def _all_text(blocks):
    out = []
    for b in blocks:
        if b.get("type") == "header":
            out.append(b["text"]["text"])
        elif b.get("type") == "section":
            out.append(b["text"]["text"])
        elif b.get("type") == "context":
            out.extend(e["text"] for e in b["elements"])
    return "\n".join(out)


def test_hero_header_is_day_activity_time():
    blocks = build_practice_announcement_blocks(_practice())
    assert blocks[0]["type"] == "header"
    assert blocks[0]["text"]["text"] == "Sunday · Classic Ski at 12:00 PM"


def test_hero_has_where_and_workout_and_notes():
    text = _all_text(build_practice_announcement_blocks(_practice()))
    assert "*Where:*" in text and "Theodore Wirth - Trailhead" in text
    assert "*Workout · Intervals*" in text
    assert "*📌 Notes*" in text and "Meet at the flagpole." in text
    assert "Social after at Utepils Brewing" in text


def test_hero_intervals_cta_has_evergreen():
    text = _all_text(build_practice_announcement_blocks(_practice()))
    assert ":evergreen_tree:" in text


def test_hero_no_intervals_cta_omits_evergreen():
    p = _practice(practice_types=[SimpleNamespace(name="Distance")])
    text = _all_text(build_practice_announcement_blocks(p))
    assert ":evergreen_tree:" not in text


def test_hero_omits_notes_and_social_when_absent():
    p = _practice(logistics_notes=None, has_social=False)
    text = _all_text(build_practice_announcement_blocks(p))
    assert "Notes" not in text
    assert "Social after" not in text


def test_hero_no_emdash_anywhere():
    import json
    blob = json.dumps(build_practice_announcement_blocks(_practice()))
    assert "—" not in blob and "–" not in blob
