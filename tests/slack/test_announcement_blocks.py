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
    BLOCKS_MAX,
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
    assert "*📝 Notes*" in text and "Meet at the flagpole." in text
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


def test_multiple_ordinary_alerts_share_one_section_without_copy_changes(
    practice_info, conditions
):
    alerts = [
        SimpleNamespace(headline="Heat Advisory", event=None),
        SimpleNamespace(headline="Air Quality Alert", event=None),
    ]
    conditions = replace(conditions, weather=_weather(alerts=alerts))

    blocks = build_practice_announcement_blocks(practice_info, conditions)
    alert_sections = [
        block for block in blocks
        if block.get("type") == "section"
        and "⚠️" in block.get("text", {}).get("text", "")
    ]
    fallback = announcement_blocks.build_practice_fallback_text(
        practice_info, conditions
    )

    assert len(alert_sections) == 1
    assert "⚠️ Heat Advisory\n⚠️ Air Quality Alert" in (
        alert_sections[0]["text"]["text"]
    )
    assert "⚠️ Heat Advisory ⚠️ Air Quality Alert" in fallback
    assert "more active alerts" not in rendered_text(blocks)


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


def _rsvp_context(blocks):
    matches = [
        block for block in blocks
        if block.get("type") == "context"
        and block.get("elements")
        and block["elements"][0].get("text", "").startswith("Bop ")
    ]
    assert len(matches) == 1
    return matches[0]


@pytest.mark.parametrize(
    ("reactions", "supplemental"),
    [
        ([], ""),
        (
            [{"emoji": "hatching_chick", "label": "new rollerskier"}],
            " In addition to your attendance emoji, hit a :hatching_chick: "
            "for new rollerskier.",
        ),
        (
            [
                {"emoji": "hatching_chick", "label": "new rollerskier"},
                {"emoji": "athletic_shoe", "label": "runner"},
            ],
            " In addition to your attendance emoji, hit a :hatching_chick: "
            "for new rollerskier and a :athletic_shoe: for runner.",
        ),
        (
            [
                {"emoji": "hatching_chick", "label": "new rollerskier"},
                {
                    "emoji": "older_adult::skin-tone-4",
                    "label": "experienced rollerskier",
                },
                {"emoji": "athletic_shoe", "label": "runner"},
            ],
            " In addition to your attendance emoji, hit a :hatching_chick: "
            "for new rollerskier, a :older_adult::skin-tone-4: for experienced "
            "rollerskier, and a :athletic_shoe: for runner.",
        ),
        (
            [
                {"emoji": "hatching_chick", "label": "new rollerskier"},
                {"emoji": "older_adult", "label": "experienced rollerskier"},
                {"emoji": "athletic_shoe", "label": "runner"},
                {"emoji": "evergreen_tree", "label": "endurance"},
            ],
            " In addition to your attendance emoji, hit a :hatching_chick: "
            "for new rollerskier, a :older_adult: for experienced rollerskier, "
            "a :athletic_shoe: for runner, and a :evergreen_tree: for endurance.",
        ),
    ],
)
def test_standalone_rsvp_uses_conditional_line_break(
    practice_info, conditions, reactions, supplemental
):
    practice_info.plan_reactions = reactions
    block = _rsvp_context(
        build_practice_announcement_blocks(practice_info, conditions)
    )
    separator = "\n" if supplemental else " "
    assert block["elements"] == [{
        "type": "mrkdwn",
        "text": (
            "Bop :white_check_mark: so we'll know you'll be there."
            f"{supplemental}{separator}"
            "Running late? Reply in the thread. <!channel>"
        ),
    }]
    assert len(block["elements"][0]["text"].splitlines()) == (
        2 if supplemental else 1
    )


def test_context_budget_preserves_attendance_and_complete_second_line(monkeypatch):
    monkeypatch.setattr(
        announcement_blocks,
        "format_supplemental_reaction_sentence",
        lambda reactions: "s" * 3_000,
    )
    block = announcement_blocks._rsvp_context_block(
        "Bop :white_check_mark: so we'll know you'll be there.",
        [],
        surface="practice_announcement",
        practice_id=42,
    )
    text = block["elements"][0]["text"]
    assert len(text) <= 2_000
    assert text.startswith(
        "Bop :white_check_mark: so we'll know you'll be there. "
    )
    assert text.endswith("\nRunning late? Reply in the thread. <!channel>")
    assert len(text.splitlines()) == 2


def test_coach_context_stays_separate_from_rsvp_context(practice_info, conditions):
    blocks = build_practice_announcement_blocks(practice_info, conditions)
    rsvp = _rsvp_context(blocks)
    coach = next(
        block for block in blocks
        if block.get("type") == "context"
        and "Coach <@U1>" in str(block.get("elements"))
    )
    assert rsvp is not coach
    assert "Coach" not in rsvp["elements"][0]["text"]


def test_member_facing_notes_heading_uses_memo_icon(practice_info, conditions):
    blocks = build_practice_announcement_blocks(practice_info, conditions)
    notes = next(
        block["text"]["text"] for block in blocks
        if block.get("type") == "section"
        and "Meet at the flagpole" in block.get("text", {}).get("text", "")
    )
    assert notes.startswith("*📝 Notes*\n")
    assert "📌" not in notes


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


def test_long_activity_preserves_fixed_header_time_suffix(
    practice_info, conditions, caplog
):
    practice_info.activities = [_act("a" * 255)]
    header = build_practice_announcement_blocks(
        practice_info, conditions
    )[0]["text"]["text"]
    assert len(header) <= HEADER_TEXT_MAX
    assert header.startswith("Monday · ")
    assert header.endswith(" at 6:00 PM")
    assert "activity_label" in caplog.text


def test_many_long_practice_types_preserve_workout_placeholder(
    practice_info, conditions, caplog
):
    practice_info.practice_types = [
        SimpleNamespace(name=f"Type {index} " + "t" * 255, has_intervals=False)
        for index in range(30)
    ]
    practice_info.workout_description = None
    workout = next(
        block["text"]["text"]
        for block in build_practice_announcement_blocks(practice_info, conditions)
        if block.get("type") == "section"
        and block.get("text", {}).get("text", "").startswith("*Workout")
    )
    assert len(workout) <= SECTION_TEXT_MAX
    assert "Workout details coming soon." in workout
    assert "practice_type_names" in caplog.text


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


def test_long_parking_cannot_remove_gear_from_details(
    practice_info, empty_conditions
):
    practice_info.location.parking_notes = "p" * 4_000
    practice_info.activities = [_act("Classic Ski", ["Classic skis"])]
    blocks = build_practice_details_blocks(practice_info, empty_conditions)
    text = rendered_text(blocks)
    assert "*Parking*" in text
    assert "*Gear*\nClassic skis" in text
    _assert_no_adjacent_dividers(blocks)


def test_details_has_no_em_dash(practice_info, conditions):
    blob = json.dumps(build_practice_details_blocks(practice_info, conditions))
    assert "—" not in blob and "–" not in blob


def test_standalone_fallback_has_exact_plain_rsvp_tail(
    practice_info, conditions
):
    practice_info.plan_reactions = [
        {"emoji": "hatching_chick", "label": "new rollerskier"},
        {
            "emoji": "older_adult::skin-tone-4",
            "label": "experienced rollerskier",
        },
        {"emoji": "athletic_shoe", "label": "runner"},
    ]
    fallback = announcement_blocks.build_practice_fallback_text(
        practice_info, conditions
    )
    assert fallback.endswith(
        "RSVP with the white check mark reaction so we'll know you'll be there. "
        "Additional reactions: hatching chick for new rollerskier; "
        "older adult, skin tone 4 for experienced rollerskier; "
        "athletic shoe for runner. Running late? Reply in the thread."
    )
    assert "<!channel>" not in fallback
    assert ":hatching_chick:" not in fallback


def test_standalone_fallback_without_supplement_has_exact_plain_tail(
    practice_info, conditions
):
    practice_info.plan_reactions = []
    fallback = announcement_blocks.build_practice_fallback_text(
        practice_info, conditions
    )
    assert fallback.endswith(
        "RSVP with the white check mark reaction so we'll know you'll be there. "
        "Running late? Reply in the thread."
    )


def test_standalone_fallback_plainifies_authored_slack_control_tokens(
    practice_info, conditions
):
    authored = "support <!channel> :wave:"
    practice_info.location.name = authored
    practice_info.workout_description = authored
    practice_info.logistics_notes = authored
    practice_info.social_location.name = authored
    practice_info.plan_reactions = [{
        "emoji": "evergreen_tree",
        "label": authored,
    }]

    fallback = announcement_blocks.build_practice_fallback_text(
        practice_info,
        conditions,
        announcement_notice=authored,
    )

    assert "<!channel>" not in fallback
    assert ":wave:" not in fallback
    assert "support" in fallback
    assert practice_info.plan_reactions[0]["label"] == authored
    assert practice_info.workout_description == authored


def test_standalone_fallback_plainification_is_total_for_long_colon_tokens(
    practice_info, conditions
):
    token = ":" + ("a" * 81) + ":"
    practice_info.workout_description = f"Workout {token}"

    fallback = announcement_blocks.build_practice_fallback_text(
        practice_info,
        conditions,
    )

    assert token not in fallback
    assert "a" * 81 in fallback
    assert practice_info.workout_description == f"Workout {token}"


def test_reserved_fallback_helper_never_truncates_required_tail():
    tail = (
        "RSVP with the white check mark reaction so we'll know you'll be there. "
        "Running late? Reply in the thread."
    )
    fallback = announcement_blocks._fallback_with_reserved_tail(
        ["body " * 2_000],
        tail,
        surface="practice_announcement",
        practice_id=42,
    )
    assert len(fallback) <= FALLBACK_TEXT_MAX
    assert fallback.endswith(tail)


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
    assert fallback.endswith(
        "RSVP with the white check mark reaction so we'll know you'll be there. "
        "Additional reaction: evergreen tree for Endurance instead of intervals. "
        "Running late? Reply in the thread."
    )
    assert "Parking" not in fallback
    assert "Wind" not in fallback
    assert "Trails" not in fallback


def test_announcement_fallback_normal_copy_includes_root_only_member_content(
    practice_info, empty_conditions
):
    practice_info.plan_reactions = [EVERGREEN_PLAN_REACTION]

    fallback = announcement_blocks.build_practice_fallback_text(
        practice_info,
        empty_conditions,
    )

    assert fallback == (
        "Status: Scheduled. "
        "Monday, July 13 at 6:00 PM at Theodore Wirth. "
        "Workout: 5 x 4min @ threshold, 2min easy between. "
        "Notes: Meet at the flagpole. "
        "Social after at Utepils Brewing. "
        "RSVP with the white check mark reaction so we'll know you'll be there. "
        "Additional reaction: evergreen tree for Endurance instead of intervals. "
        "Running late? Reply in the thread."
    )


def test_announcement_fallback_names_generic_social_when_destination_is_missing(
    practice_info, empty_conditions
):
    practice_info.social_location = None

    fallback = announcement_blocks.build_practice_fallback_text(
        practice_info,
        empty_conditions,
    )

    assert "Social after practice." in fallback


def test_long_root_content_cannot_remove_social_rsvp_or_supplement(
    practice_info, empty_conditions
):
    practice_info.workout_description = "Workout start " + ("w" * 2_500)
    practice_info.logistics_notes = "Notes start " + ("n" * 2_500)
    practice_info.social_location.name = "Social destination " + ("s" * 2_500)
    practice_info.plan_reactions = [EVERGREEN_PLAN_REACTION]

    fallback = announcement_blocks.build_practice_fallback_text(
        practice_info,
        empty_conditions,
    )

    assert "Workout start" in fallback
    assert "Notes start" in fallback
    assert "Social after at Social destination" in fallback
    assert fallback.endswith(
        "RSVP with the white check mark reaction so we'll know you'll be there. "
        "Additional reaction: evergreen tree for Endurance instead of intervals. "
        "Running late? Reply in the thread."
    )
    assert len(fallback) <= FALLBACK_TEXT_MAX


def test_many_long_alerts_cannot_exhaust_the_reserved_fallback_tail(
    practice_info, empty_conditions
):
    practice_info.workout_description = "w" * 2_500
    practice_info.logistics_notes = "n" * 2_500
    practice_info.social_location.name = "s" * 2_500
    practice_info.plan_reactions = [EVERGREEN_PLAN_REACTION]
    alerts = [
        SimpleNamespace(headline=f"Alert {index} " + ("a" * 100), event=None)
        for index in range(1_000)
    ]
    conditions = replace(empty_conditions, weather=_weather(alerts=alerts))

    fallback = announcement_blocks.build_practice_fallback_text(
        practice_info,
        conditions,
        announcement_notice="m" * 2_500,
    )
    blocks = build_practice_announcement_blocks(
        practice_info,
        conditions,
        announcement_notice="m" * 2_500,
    )
    text = rendered_text(blocks)

    assert "Notes:" in fallback
    assert "Social after at" in fallback
    assert fallback.endswith(
        "RSVP with the white check mark reaction so we'll know you'll be there. "
        "Additional reaction: evergreen tree for Endurance instead of intervals. "
        "Running late? Reply in the thread."
    )
    assert "+980 more active alerts" in fallback
    assert len(fallback) <= FALLBACK_TEXT_MAX
    assert len(blocks) <= BLOCKS_MAX
    assert "+980 more active alerts" in text
    for required in (
        "Monday · Classic Ski at 6:00 PM",
        "Alert 0",
        "*Where:*",
        "*Workout",
        "*📝 Notes*",
        "Social after at",
        "Bop :white_check_mark: so we'll know you'll be there.",
        "In addition to your attendance emoji",
        "Running late? Reply in the thread. <!channel>",
    ):
        assert required in text


def test_announcement_fallback_includes_plain_practice_status(
    practice_info, conditions
):
    fallback = announcement_blocks.build_practice_fallback_text(
        practice_info, conditions
    )
    assert "Status: Scheduled." in fallback
    assert "Monday, July 13 at 6:00 PM at Theodore Wirth." in fallback


def test_announcement_fallback_uses_missing_workout_placeholder(
    practice_info, conditions
):
    practice_info.workout_description = None
    fallback = announcement_blocks.build_practice_fallback_text(
        practice_info, conditions
    )
    assert "Workout: Workout details coming soon." in fallback


def test_whitespace_only_workout_uses_placeholder_in_hero_and_fallback(
    practice_info, conditions
):
    practice_info.workout_description = " \n\t "
    hero = rendered_text(
        build_practice_announcement_blocks(practice_info, conditions)
    )
    fallback = announcement_blocks.build_practice_fallback_text(
        practice_info, conditions
    )
    assert "Workout details coming soon." in hero
    assert "Workout: Workout details coming soon." in fallback


def test_long_alerts_cannot_remove_later_hero_promotions(
    practice_info, conditions
):
    alerts = [
        SimpleNamespace(headline=f"Alert {index} " + "a" * 4_000, event=None)
        for index in range(2)
    ]
    conditions = replace(
        conditions,
        weather=_weather(alerts=alerts),
        daylight=daylight_for(practice_info.date, 16, 53),
        air_quality=121,
    )
    blocks = build_practice_announcement_blocks(practice_info, conditions)
    text = rendered_text(blocks)
    assert "Alert 0" in text
    assert "Alert 1" in text
    assert "Air quality 121" in text
    assert "Headlamp required" in text
    _assert_urgent_precedes_location_and_workout(blocks, "Air quality 121")
    _assert_urgent_precedes_location_and_workout(blocks, "Headlamp required")


def test_long_standalone_content_preserves_complete_required_tail(
    practice_info, conditions
):
    practice_info.workout_description = "w" * 10_000
    practice_info.logistics_notes = "n" * 10_000
    practice_info.plan_reactions = [
        {"emoji": "evergreen_tree", "label": "Endurance instead"}
    ]
    fallback = announcement_blocks.build_practice_fallback_text(
        practice_info, conditions
    )
    assert fallback.endswith(
        "RSVP with the white check mark reaction so we'll know you'll be there. "
        "Additional reaction: evergreen tree for Endurance instead. "
        "Running late? Reply in the thread."
    )
    assert len(fallback) <= FALLBACK_TEXT_MAX


def test_configured_duration_variance_controls_fallback_headlamp(
    practice_info, conditions
):
    sunset = daylight_for(practice_info.date, 19, 30)
    short_conditions = replace(
        conditions,
        weather=None,
        daylight=sunset,
        duration_minutes=60,
    )
    long_conditions = replace(
        conditions,
        weather=_weather(
            alerts=[SimpleNamespace(headline="a" * 4_000, event=None)]
        ),
        daylight=sunset,
        duration_minutes=120,
    )
    assert "Headlamp required" not in announcement_blocks.build_practice_fallback_text(
        practice_info, short_conditions
    )
    assert "Headlamp required" in announcement_blocks.build_practice_fallback_text(
        practice_info, long_conditions
    )


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


@pytest.mark.parametrize(
    ("authored", "expected"),
    [
        ("Ends with a period.", "Ends with a period."),
        ("Ends with a question?", "Ends with a question?"),
        ("Ends with excitement!", "Ends with excitement!"),
        ("Already truncated…", "Already truncated…"),
        ("Needs punctuation", "Needs punctuation."),
    ],
)
def test_details_fallback_adds_only_missing_terminal_punctuation(
    practice_info, empty_conditions, authored, expected
):
    practice_info.location.parking_notes = authored

    fallback = announcement_blocks.build_practice_details_fallback_text(
        practice_info,
        empty_conditions,
    )

    assert fallback == (
        f"Practice details for Monday, July 13. Parking: {expected}"
    )
    assert practice_info.location.parking_notes == authored


def test_details_fallback_plainification_is_total_for_long_colon_tokens(
    practice_info, conditions
):
    token = ":" + ("a" * 81) + ":"
    practice_info.location.parking_notes = f"Parking {token}"

    fallback = announcement_blocks.build_practice_details_fallback_text(
        practice_info,
        conditions,
    )

    assert token not in fallback
    assert "a" * 81 in fallback
    assert practice_info.location.parking_notes == f"Parking {token}"


def test_long_parking_cannot_remove_details_fallback_gear_or_conditions(
    practice_info, conditions
):
    practice_info.location.parking_notes = "p" * 10_000
    practice_info.activities = [_act("Classic Ski", ["Classic skis"])]
    fallback = announcement_blocks.build_practice_details_fallback_text(
        practice_info, conditions
    )
    assert "Gear: Classic skis." in fallback
    assert "Conditions:" in fallback
    assert "💨 Wind NW 12 mph" in fallback
    assert "☀️ Sunset 8:59 PM" in fallback
    assert len(fallback) <= FALLBACK_TEXT_MAX


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
        slack_session_emoji="six",
        activities=[_act("Strength")],
        practice_types=[],
        has_social=False,
        logistics_notes=None,
    )
    p2 = _practice(
        date=datetime(2027, 1, 1, 18, 0),
        slack_session_emoji="seven",
        activities=[_act("Strength")],
        practice_types=[],
        has_social=False,
        logistics_notes=None,
    )
    blocks = build_combined_lift_blocks([p1, p2])
    blob = json.dumps(blocks)
    assert "Warmup" not in blob and "Cooldown" not in blob
    assert "—" not in blob
