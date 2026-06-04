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


def _weather(temp=25, feels=18, summary="cloudy, light snow", wind_speed=12, wind_dir="NW", alerts=None):
    return SimpleNamespace(
        temperature_f=temp, feels_like_f=feels, conditions_summary=summary,
        wind_speed_mph=wind_speed, wind_direction=wind_dir, alerts=alerts or [],
    )


def _daylight(hour=16, minute=38):
    return SimpleNamespace(sunset=datetime(2026, 12, 29, hour, minute), civil_twilight_end=datetime(2026, 12, 29, hour + 1, minute))


def test_details_has_parking_gear_and_conditions():
    p = _practice()
    p.location.parking_notes = "Chalet lot; arrive early."
    p.activities = [SimpleNamespace(name="Classic Ski", gear_required=["Classic skis", "kick wax"])]
    text = _all_text(build_practice_details_blocks(p, weather=_weather(), daylight=_daylight()))
    assert "*Parking*" in text and "Chalet lot" in text
    assert "*Gear*" in text and "Classic skis" in text
    assert "*Conditions*" in text
    assert "💨 Wind NW 12 mph" in text
    assert "☀️ Sunset 4:38 PM" in text


def test_details_headlamp_when_practice_after_sunset():
    p = _practice(date=datetime(2026, 12, 29, 16, 0))  # 4pm start, sunset 3:38pm
    text = _all_text(build_practice_details_blocks(p, weather=_weather(), daylight=_daylight(hour=15, minute=38)))
    assert "🔦 Sunset 3:38 PM, bring a headlamp" in text
    assert "—" not in text


def test_details_aqi_shown_above_49_value_only():
    text = _all_text(build_practice_details_blocks(_practice(), weather=_weather(), daylight=_daylight(), air_quality=78))
    assert "🌫️ AQI 78" in text
    assert "Sensitive" not in text and "Unhealthy" not in text


def test_details_aqi_hidden_at_or_below_49():
    text = _all_text(build_practice_details_blocks(_practice(), weather=_weather(), daylight=_daylight(), air_quality=42))
    assert "AQI" not in text


def test_details_no_emdash():
    import json
    blob = json.dumps(build_practice_details_blocks(_practice(), weather=_weather(), daylight=_daylight(hour=12, minute=10), air_quality=80))
    assert "—" not in blob and "–" not in blob
