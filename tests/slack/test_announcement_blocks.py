import json
from dataclasses import replace
from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

import app.slack.blocks as slack_blocks
import app.slack.blocks.announcements as announcement_blocks
from app.practices.interfaces import AnnouncementConditions, PracticeStatus
from app.practices.plan_reactions import EVERGREEN_PLAN_REACTION
from app.slack.blocks.announcements import (
    _activity_label,
    build_combined_lift_blocks,
    build_practice_announcement_blocks,
    build_practice_details_blocks,
)
from app.slack.blocks.text import (
    FALLBACK_TEXT_MAX,
    HEADER_TEXT_MAX,
    SECTION_TEXT_MAX,
)


def _act(name, gear_required=None):
    return SimpleNamespace(name=name, gear_required=gear_required)


def _practice(**over):
    base = dict(
        id=42,
        date=datetime(2026, 7, 13, 18, 0),  # July 13 2026 is a Monday
        status=PracticeStatus.SCHEDULED,
        activities=[_act("Classic Ski")],
        practice_types=[SimpleNamespace(name="Intervals", has_intervals=True)],
        location=SimpleNamespace(
            name="Theodore Wirth",
            spot="Trailhead",
            address="1301 Theodore Wirth Pkwy",
            google_maps_url="https://maps.example/wirth",
            latitude=None,
            longitude=None,
            parking_notes="Chalet lot; arrive early.",
            social_location=SimpleNamespace(
                name="Utepils Brewing", google_maps_url=None
            ),
        ),
        social_location=SimpleNamespace(
            name="Utepils Brewing", google_maps_url=None
        ),
        workout_description="5 x 4min @ threshold, 2min easy between.",
        logistics_notes="Meet at the flagpole.",
        plan_reactions=[],
        has_social=True,
        is_dark_practice=False,
        leads=[
            SimpleNamespace(
                role=SimpleNamespace(name="COACH"),
                slack_user_id="U1",
                display_name="Anders",
            )
        ],
    )
    base.update(over)
    return SimpleNamespace(**base)


def _weather(
    temp=25,
    feels=18,
    summary="cloudy, light snow",
    wind_speed=12,
    wind_dir="NW",
    alerts=(),
):
    return SimpleNamespace(
        temperature_f=temp,
        feels_like_f=feels,
        conditions_summary=summary,
        wind_speed_mph=wind_speed,
        wind_direction=wind_dir,
        alerts=list(alerts) if alerts is not None else None,
    )


def _trail():
    return SimpleNamespace(
        ski_quality="good",
        groomed=True,
        report_url="https://trails.example/report",
    )


def daylight_for(practice_date, sunset_hour, sunset_minute):
    sunset_local = practice_date.replace(
        hour=sunset_hour,
        minute=sunset_minute,
        tzinfo=ZoneInfo("America/Chicago"),
    )
    sunset_utc = sunset_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    return SimpleNamespace(
        sunset=sunset_utc,
        civil_twilight_end=sunset_utc + timedelta(hours=1),
    )


@pytest.fixture
def practice_info():
    return _practice()


@pytest.fixture
def conditions(practice_info):
    return AnnouncementConditions(
        weather=_weather(),
        daylight=daylight_for(practice_info.date, 20, 59),
        air_quality=78,
        trail_conditions=_trail(),
        duration_minutes=90,
    )


@pytest.fixture
def empty_conditions():
    return AnnouncementConditions()


def _block_text(block):
    if block.get("type") in {"header", "section"}:
        return block.get("text", {}).get("text", "")
    if block.get("type") == "context":
        return "\n".join(
            element.get("text", "") for element in block.get("elements", [])
        )
    return ""


def rendered_text(blocks):
    return "\n".join(filter(None, (_block_text(block) for block in blocks)))


def _block_index(blocks, needle):
    return next(
        index for index, block in enumerate(blocks) if needle in _block_text(block)
    )


def _assert_no_adjacent_dividers(blocks):
    assert all(
        left.get("type") != "divider" or right.get("type") != "divider"
        for left, right in zip(blocks, blocks[1:])
    )


def _assert_urgent_precedes_location_and_workout(blocks, needle):
    assert _block_index(blocks, needle) < _block_index(blocks, "*Where:*")
    assert _block_index(blocks, needle) < _block_index(blocks, "*Workout")


def test_activity_label_single():
    assert _activity_label([_act("Classic Ski")]) == "Classic Ski"


def test_activity_label_multiple_joined_with_plus():
    assert _activity_label(
        [_act("Classic Ski"), _act("Skate Ski")]
    ) == "Classic Ski + Skate Ski"


def test_activity_label_empty_falls_back_to_practice():
    assert _activity_label([]) == "Practice"


def test_hero_header_is_day_activity_time(practice_info, conditions):
    blocks = build_practice_announcement_blocks(practice_info, conditions)
    assert blocks[0]["type"] == "header"
    assert blocks[0]["text"]["text"] == "Monday · Classic Ski at 6:00 PM"


def test_hero_has_where_workout_notes_and_social(practice_info, conditions):
    text = rendered_text(
        build_practice_announcement_blocks(practice_info, conditions)
    )
    assert "*Where:*" in text and "Theodore Wirth - Trailhead" in text
    assert "*Workout · Intervals*" in text
    assert "*📌 Notes*" in text and "Meet at the flagpole." in text
    assert "Social after at Utepils Brewing" in text


def test_hero_omits_notes_and_social_when_absent(practice_info, conditions):
    practice_info.logistics_notes = None
    practice_info.has_social = False
    text = rendered_text(
        build_practice_announcement_blocks(practice_info, conditions)
    )
    assert "Notes" not in text
    assert "Social after" not in text


def test_summer_practice_ending_before_sunset_has_no_headlamp(
    practice_info, conditions
):
    conditions = replace(
        conditions,
        daylight=daylight_for(practice_info.date, 20, 59),
    )
    text = rendered_text(
        build_practice_announcement_blocks(practice_info, conditions)
    )
    assert "headlamp" not in text.lower()


def test_practice_ending_after_sunset_promotes_headlamp(
    practice_info, conditions
):
    conditions = replace(
        conditions,
        daylight=daylight_for(practice_info.date, 16, 53),
    )
    blocks = build_practice_announcement_blocks(practice_info, conditions)
    assert "Headlamp required" in rendered_text(blocks)
    _assert_urgent_precedes_location_and_workout(blocks, "Headlamp required")


def test_practice_ending_exactly_at_sunset_requires_headlamp(
    practice_info, conditions
):
    conditions = replace(
        conditions,
        daylight=daylight_for(practice_info.date, 19, 30),
    )
    assert "Headlamp required" in rendered_text(
        build_practice_announcement_blocks(practice_info, conditions)
    )


def test_explicit_dark_practice_requires_headlamp_without_daylight(
    practice_info, conditions
):
    practice_info.is_dark_practice = True
    conditions = replace(conditions, daylight=None)
    assert "Headlamp required" in rendered_text(
        build_practice_announcement_blocks(practice_info, conditions)
    )


def test_absent_daylight_does_not_infer_headlamp(practice_info, conditions):
    conditions = replace(conditions, daylight=None)
    text = rendered_text(
        build_practice_announcement_blocks(practice_info, conditions)
    )
    assert "headlamp" not in text.lower()


def test_active_alert_is_promoted_before_location_and_workout(
    practice_info, conditions
):
    alert = SimpleNamespace(headline="Heat Advisory", event="Heat Advisory")
    conditions = replace(conditions, weather=_weather(alerts=[alert]))
    blocks = build_practice_announcement_blocks(practice_info, conditions)
    _assert_urgent_precedes_location_and_workout(blocks, "Heat Advisory")


def test_unhealthy_air_quality_is_promoted_before_location_and_workout(
    practice_info, conditions
):
    conditions = replace(conditions, air_quality=121)
    blocks = build_practice_announcement_blocks(practice_info, conditions)
    assert "Air quality 121" in rendered_text(blocks)
    _assert_urgent_precedes_location_and_workout(blocks, "Air quality 121")


@pytest.mark.parametrize(
    "notice",
    ["📍 Location changed", "🕐 Time changed"],
)
def test_explicit_location_or_time_notice_is_promoted_before_details(
    practice_info, conditions, notice
):
    blocks = build_practice_announcement_blocks(
        practice_info,
        conditions,
        announcement_notice=notice,
    )
    assert notice in rendered_text(blocks)
    _assert_urgent_precedes_location_and_workout(blocks, notice)


def test_urgent_exceptions_have_stable_member_facing_order(
    practice_info, conditions
):
    alert = SimpleNamespace(headline="Heat Advisory", event="Heat Advisory")
    conditions = replace(
        conditions,
        weather=_weather(alerts=[alert]),
        daylight=daylight_for(practice_info.date, 16, 53),
        air_quality=121,
    )
    text = rendered_text(
        build_practice_announcement_blocks(
            practice_info,
            conditions,
            announcement_notice="📍 Location changed",
        )
    )
    assert text.index("📍 Location changed") < text.index("Heat Advisory")
    assert text.index("Heat Advisory") < text.index("Air quality 121")
    assert text.index("Air quality 121") < text.index("Headlamp required")


def test_routine_conditions_stay_out_of_the_hero(practice_info, conditions):
    text = rendered_text(
        build_practice_announcement_blocks(practice_info, conditions)
    )
    assert "Parking" not in text
    assert "Wind" not in text
    assert "🎿 Trails:" not in text
    assert "AQI" not in text
    assert "No alerts" not in text


def test_alert_fetch_absence_never_invents_no_alerts(practice_info, conditions):
    conditions = replace(conditions, weather=_weather(alerts=None))
    hero = rendered_text(
        build_practice_announcement_blocks(practice_info, conditions)
    )
    details = rendered_text(build_practice_details_blocks(practice_info, conditions))
    assert "No alerts" not in hero
    assert "No alerts" not in details


def test_missing_weather_snapshot_is_rendered_without_an_alert_claim(
    practice_info, conditions
):
    conditions = replace(conditions, weather=None)
    hero = rendered_text(
        build_practice_announcement_blocks(practice_info, conditions)
    )
    details = rendered_text(build_practice_details_blocks(practice_info, conditions))
    assert "No alerts" not in hero
    assert "No alerts" not in details


def test_aqi_100_stays_in_details_while_101_moves_to_hero(
    practice_info, conditions
):
    at_100 = replace(conditions, air_quality=100)
    hero_100 = rendered_text(
        build_practice_announcement_blocks(practice_info, at_100)
    )
    details_100 = rendered_text(build_practice_details_blocks(practice_info, at_100))
    assert "Air quality 100" not in hero_100
    assert "AQI 100" in details_100

    at_101 = replace(conditions, air_quality=101)
    hero_101 = rendered_text(
        build_practice_announcement_blocks(practice_info, at_101)
    )
    details_101 = rendered_text(build_practice_details_blocks(practice_info, at_101))
    assert "Air quality 101" in hero_101
    assert "AQI 101" not in details_101


def test_missing_workout_uses_exact_placeholder_without_adjacent_dividers(
    practice_info, conditions
):
    practice_info.workout_description = None
    practice_info.logistics_notes = None
    practice_info.has_social = False
    blocks = build_practice_announcement_blocks(practice_info, conditions)
    assert "Workout details coming soon." in rendered_text(blocks)
    _assert_no_adjacent_dividers(blocks)


def test_saved_plan_reactions_use_exact_rsvp_and_plan_grammar(
    practice_info, conditions
):
    practice_info.plan_reactions = [EVERGREEN_PLAN_REACTION]
    text = rendered_text(
        build_practice_announcement_blocks(practice_info, conditions)
    )
    assert "Bop ✅ if you're coming." in text
    assert "Your Practice Plan:" in text
    assert ":evergreen_tree: Endurance instead of intervals" in text
    assert "Optional:" not in text
    assert text.count(":evergreen_tree:") == 1


def test_plan_heading_is_absent_without_saved_reactions(practice_info, conditions):
    text = rendered_text(
        build_practice_announcement_blocks(practice_info, conditions)
    )
    assert "Your Practice Plan:" not in text


def test_rsvp_omits_root_channel_and_running_late_copy(practice_info, conditions):
    text = rendered_text(
        build_practice_announcement_blocks(practice_info, conditions)
    )
    assert "Bop ✅ if you're coming." in text
    assert "Running late" not in text
    assert "<!channel>" not in text


def test_coach_and_lead_context_remains_after_contiguous_plan_legend(
    practice_info, conditions
):
    practice_info.plan_reactions = [EVERGREEN_PLAN_REACTION]
    practice_info.leads = [
        SimpleNamespace(
            role=SimpleNamespace(name="COACH"),
            slack_user_id="U1",
            display_name="Anders",
        ),
        SimpleNamespace(
            role=SimpleNamespace(name="LEAD"),
            slack_user_id="U2",
            display_name="Bea",
        ),
    ]
    blocks = build_practice_announcement_blocks(practice_info, conditions)
    rsvp_index = _block_index(blocks, "Bop ✅ if you're coming.")
    plan_index = _block_index(blocks, "Your Practice Plan:")
    coach_index = _block_index(blocks, "👨‍🏫 Coach <@U1>")
    lead_index = _block_index(blocks, "🧑‍🤝‍🧑 Leads <@U2>")
    assert rsvp_index == plan_index
    assert rsvp_index < coach_index == lead_index
    assert all(
        block.get("type") != "divider"
        for block in blocks[rsvp_index : coach_index + 1]
    )


def test_plan_labels_are_escaped_for_slack_mrkdwn(practice_info, conditions):
    practice_info.plan_reactions = [
        {"emoji": "evergreen_tree", "label": "Easy & steady <zone>"}
    ]
    text = rendered_text(
        build_practice_announcement_blocks(practice_info, conditions)
    )
    assert "Easy &amp; steady &lt;zone&gt;" in text
    assert "Easy & steady <zone>" not in text


def test_long_workout_uses_named_truncation_before_structural_guard(
    practice_info, conditions, caplog
):
    practice_info.workout_description = "w" * 4_000
    blocks = build_practice_announcement_blocks(practice_info, conditions)
    workout = next(
        block["text"]["text"]
        for block in blocks
        if block.get("type") == "section"
        and block.get("text", {}).get("text", "").startswith("*Workout")
    )
    assert len(workout) <= SECTION_TEXT_MAX
    assert workout.endswith("…\n\u200b")
    assert "workout_description" in caplog.text
    assert "practice_announcement" in caplog.text


def test_public_hero_guard_limits_long_header(practice_info, conditions):
    practice_info.activities = [_act("a" * 4_000)]
    blocks = build_practice_announcement_blocks(practice_info, conditions)
    assert len(blocks[0]["text"]["text"]) <= HEADER_TEXT_MAX


def test_hero_has_no_em_dash_and_no_adjacent_dividers(practice_info, conditions):
    blocks = build_practice_announcement_blocks(practice_info, conditions)
    blob = json.dumps(blocks)
    assert "—" not in blob and "–" not in blob
    _assert_no_adjacent_dividers(blocks)


def test_details_has_only_available_parking_gear_and_conditions(
    practice_info, conditions
):
    practice_info.activities = [
        _act("Classic Ski", ["Classic skis", "kick wax"])
    ]
    text = rendered_text(build_practice_details_blocks(practice_info, conditions))
    assert "Practice Details" in text
    assert "*Parking*" in text and "Chalet lot" in text
    assert "*Gear*" in text and "Classic skis" in text
    assert "*Conditions*" in text
    assert "🌡️ 25°F (feels 18°), cloudy, light snow" in text
    assert "💨 Wind NW 12 mph" in text
    assert "☀️ Sunset 8:59 PM" in text
    assert "🌫️ AQI 78" in text
    assert "🎿 Trails: Good, Groomed" in text
    assert "<https://trails.example/report|Trail report>" in text


def test_details_never_duplicates_alert_or_headlamp_promotions(
    practice_info, conditions
):
    alert = SimpleNamespace(headline="Heat Advisory", event="Heat Advisory")
    conditions = replace(
        conditions,
        weather=_weather(alerts=[alert]),
        daylight=daylight_for(practice_info.date, 16, 53),
        air_quality=121,
    )
    text = rendered_text(build_practice_details_blocks(practice_info, conditions))
    assert "Heat Advisory" not in text
    assert "headlamp" not in text.lower()
    assert "AQI 121" not in text
    assert "☀️ Sunset 4:53 PM" in text


def test_empty_details_returns_no_blocks(practice_info, empty_conditions):
    practice_info.location.parking_notes = None
    practice_info.activities = [_act("Classic Ski")]
    assert build_practice_details_blocks(practice_info, empty_conditions) == []


def test_details_dividers_only_separate_nonempty_sections(
    practice_info, conditions
):
    blocks = build_practice_details_blocks(practice_info, conditions)
    _assert_no_adjacent_dividers(blocks)
    assert blocks[0]["type"] == "header"
    assert blocks[-1]["type"] != "divider"


def test_public_details_guard_limits_long_section(practice_info, empty_conditions):
    practice_info.location.parking_notes = "p" * 4_000
    blocks = build_practice_details_blocks(practice_info, empty_conditions)
    section = next(block for block in blocks if block.get("type") == "section")
    assert len(section["text"]["text"]) <= SECTION_TEXT_MAX


def test_details_has_no_em_dash(practice_info, conditions):
    blob = json.dumps(build_practice_details_blocks(practice_info, conditions))
    assert "—" not in blob and "–" not in blob


def test_announcement_fallback_covers_hero_and_omits_routine_details(
    practice_info, conditions
):
    practice_info.plan_reactions = [EVERGREEN_PLAN_REACTION]
    alert = SimpleNamespace(headline="Heat Advisory", event="Heat Advisory")
    conditions = replace(conditions, weather=_weather(alerts=[alert]))
    fallback = announcement_blocks.build_practice_fallback_text(
        practice_info,
        conditions,
        announcement_notice="📍 Location changed",
    )
    assert "Monday, July 13 at 6:00 PM at Theodore Wirth." in fallback
    assert "Workout: 5 x 4min @ threshold, 2min easy between." in fallback
    assert "📍 Location changed" in fallback
    assert "Heat Advisory" in fallback
    assert "RSVP with ✅." in fallback
    assert (
        "Your Practice Plan: :evergreen_tree: Endurance instead of intervals."
        in fallback
    )
    assert "Parking" not in fallback
    assert "Wind" not in fallback
    assert "Trails" not in fallback


def test_announcement_fallback_uses_missing_workout_placeholder(
    practice_info, conditions
):
    practice_info.workout_description = None
    fallback = announcement_blocks.build_practice_fallback_text(
        practice_info, conditions
    )
    assert "Workout: Workout details coming soon." in fallback


def test_details_fallback_uses_same_plain_normalized_content(
    practice_info, conditions
):
    practice_info.activities = [
        _act("Classic Ski", ["Classic skis", "kick wax"])
    ]
    fallback = announcement_blocks.build_practice_details_fallback_text(
        practice_info, conditions
    )
    assert fallback.startswith("Practice details for Monday, July 13.")
    assert "Parking: Chalet lot; arrive early." in fallback
    assert "Gear: Classic skis, kick wax." in fallback
    assert "💨 Wind NW 12 mph" in fallback
    assert "☀️ Sunset 8:59 PM" in fallback
    assert "🌫️ AQI 78" in fallback
    assert "Trail report: https://trails.example/report" in fallback
    assert "<https://trails.example/report|Trail report>" not in fallback


def test_empty_details_fallback_contains_only_the_practice_date(
    practice_info, empty_conditions
):
    practice_info.location.parking_notes = None
    fallback = announcement_blocks.build_practice_details_fallback_text(
        practice_info, empty_conditions
    )
    assert fallback == "Practice details for Monday, July 13."


def test_fallbacks_are_guarded(practice_info, empty_conditions):
    practice_info.workout_description = "w" * 10_000
    announcement = announcement_blocks.build_practice_fallback_text(
        practice_info, empty_conditions
    )
    practice_info.location.parking_notes = "p" * 10_000
    details = announcement_blocks.build_practice_details_fallback_text(
        practice_info, empty_conditions
    )
    assert len(announcement) <= FALLBACK_TEXT_MAX
    assert len(details) <= FALLBACK_TEXT_MAX
    assert details.endswith("…")


def test_fallback_builders_are_reexported():
    assert (
        slack_blocks.build_practice_fallback_text
        is announcement_blocks.build_practice_fallback_text
    )
    assert (
        slack_blocks.build_practice_details_fallback_text
        is announcement_blocks.build_practice_details_fallback_text
    )


def test_combined_lift_header_uses_strength_and_no_warmup():
    p1 = _practice(
        date=datetime(2026, 12, 30, 18, 0),
        activities=[_act("Strength")],
        practice_types=[],
        has_social=False,
        logistics_notes=None,
    )
    p2 = _practice(
        date=datetime(2027, 1, 1, 18, 0),
        activities=[_act("Strength")],
        practice_types=[],
        has_social=False,
        logistics_notes=None,
    )
    blocks = build_combined_lift_blocks([p1, p2])
    blob = json.dumps(blocks)
    assert "Warmup" not in blob and "Cooldown" not in blob
    assert "—" not in blob
