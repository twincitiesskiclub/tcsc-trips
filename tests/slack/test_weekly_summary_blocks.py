"""Exact-copy contracts for the member-facing calendar-week summary."""

from datetime import date, datetime, timedelta

import pytest

from app.practices.interfaces import (
    PracticeActivityInfo,
    PracticeInfo,
    PracticeLocationInfo,
    PracticeStatus,
    PracticeTypeInfo,
)
from app.slack.blocks.summary import (
    build_weekly_summary_blocks,
    build_weekly_summary_fallback_text,
)


def practice(
    practice_id,
    when,
    *,
    activity="Run",
    practice_type=None,
    location="Theodore Wirth",
    status=PracticeStatus.SCHEDULED,
    reason=None,
):
    return PracticeInfo(
        id=practice_id,
        date=when,
        day_of_week=when.strftime("%A"),
        status=status,
        location=PracticeLocationInfo(id=practice_id, name=location),
        activities=(
            [PracticeActivityInfo(id=practice_id, name=activity)]
            if activity
            else []
        ),
        practice_types=(
            [PracticeTypeInfo(id=practice_id, name=practice_type)]
            if practice_type
            else []
        ),
        cancellation_reason=reason,
    )


def header_text(blocks):
    return blocks[0]["text"]["text"]


def section_texts(blocks):
    return [
        block["text"]["text"]
        for block in blocks
        if block["type"] == "section"
    ]


@pytest.mark.parametrize(
    ("week_start", "expected"),
    [
        (date(2026, 7, 13), "📅 Practices this week · July 13–19"),
        (date(2026, 7, 27), "📅 Practices this week · July 27–August 2"),
        (
            date(2026, 12, 28),
            "📅 Practices this week · December 28, 2026–January 3, 2027",
        ),
    ],
)
def test_heading_uses_one_calendar_emoji_and_explicit_full_week(
    week_start, expected
):
    blocks = build_weekly_summary_blocks(
        [practice(1, datetime.combine(week_start, datetime.min.time()).replace(hour=18))],
        week_start=week_start,
    )
    assert blocks[0]["text"]["text"] == expected
    day_text = "\n".join(
        block["text"]["text"] for block in blocks
        if block.get("type") == "section"
    )
    assert "📅" not in day_text


def test_one_semantic_section_per_date_has_exact_copy_and_chronological_rows():
    sessions = [
        practice(
            1,
            datetime(2026, 7, 14, 18, 15),
            practice_type="Intervals",
        ),
        practice(
            3,
            datetime(2026, 7, 16, 19, 20),
            activity="Strength",
            location="Balance Fitness",
        ),
        practice(
            2,
            datetime(2026, 7, 16, 18, 5),
            activity="Strength",
            location="Balance Fitness",
        ),
    ]

    blocks = build_weekly_summary_blocks(
        sessions,
        week_start=date(2026, 7, 13),
        weather_data={1: {"temp_f": 78.2, "conditions": "partly cloudy"}},
    )

    assert section_texts(blocks) == [
        "*Tuesday, July 14 · 6:15 PM*\n"
        "Run intervals · Theodore Wirth\n"
        "Forecast: 78°F, partly cloudy",
        "*Thursday, July 16*\n"
        "6:05 PM · Strength · Balance Fitness\n"
        "7:20 PM · Strength · Balance Fitness",
    ]
    assert "|" not in "\n".join(section_texts(blocks))


def test_cancelled_row_uses_stop_sign_and_suppresses_forecast():
    cancelled = practice(
        2,
        datetime(2026, 8, 2, 9, 0),
        status=PracticeStatus.CANCELLED,
        reason="Heat warning",
    )
    blocks = build_weekly_summary_blocks(
        [cancelled],
        week_start=date(2026, 7, 27),
        weather_data={2: {"temp_f": 92, "conditions": "hot"}},
    )
    text = "\n".join(
        block["text"]["text"] for block in blocks
        if block.get("type") == "section"
    )
    assert "🚫 CANCELLED · Heat warning" in text
    assert text.count("🚫") == 1
    assert "Forecast:" not in text


def test_active_week_uses_fixed_non_day_specific_footer():
    practices = [
        practice(1, datetime(2026, 7, 27, 6, 0)),
        practice(2, datetime(2026, 7, 27, 18, 0)),
        practice(3, datetime(2026, 7, 30, 18, 0)),
    ]
    contexts = [
        block for block in build_weekly_summary_blocks(
            practices, week_start=date(2026, 7, 27)
        )
        if block.get("type") == "context"
    ]
    assert contexts == [{
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": (
                "📝 Full practice details will be posted before each practice. "
                "· <!channel>"
            ),
        }],
    }]


def test_all_cancelled_week_omits_footer():
    cancelled = practice(
        1,
        datetime(2026, 7, 27, 18, 0),
        status=PracticeStatus.CANCELLED,
        reason="Heat warning",
    )
    blocks = build_weekly_summary_blocks(
        [cancelled], week_start=date(2026, 7, 27)
    )
    assert not any(block.get("type") == "context" for block in blocks)


def test_weekly_fallback_remains_plain_and_has_no_broadcast_token():
    practices = [
        practice(1, datetime(2026, 7, 27, 18, 0)),
        practice(
            2,
            datetime(2026, 8, 2, 9, 0),
            status=PracticeStatus.CANCELLED,
            reason="Heat warning",
        ),
    ]
    fallback = build_weekly_summary_fallback_text(
        practices, week_start=date(2026, 7, 27)
    )
    for forbidden in ("📅", "🚫", "📝", "<!channel>"):
        assert forbidden not in fallback
    assert "Practices this week · July 27–August 2." in fallback
    assert "CANCELLED: Heat warning" in fallback


def test_weekly_fallback_plainifies_authored_slack_control_tokens():
    authored = "support <!channel> :wave:"
    active = practice(
        1,
        datetime(2026, 7, 27, 18, 0),
        activity=authored,
        location=authored,
    )
    cancelled = practice(
        2,
        datetime(2026, 8, 2, 9, 0),
        status=PracticeStatus.CANCELLED,
        reason=authored,
    )

    fallback = build_weekly_summary_fallback_text(
        [active, cancelled],
        week_start=date(2026, 7, 27),
        weather_data={1: {"temp_f": 78, "conditions": authored}},
    )

    assert "<!channel>" not in fallback
    assert ":wave:" not in fallback
    assert active.activities[0].name == authored
    assert cancelled.cancellation_reason == authored


def test_fallback_has_full_range_and_every_active_or_cancelled_row():
    active = practice(
        1,
        datetime(2026, 7, 14, 18, 15),
        practice_type="Intervals",
    )
    cancelled = practice(
        2,
        datetime(2026, 7, 16, 18, 5),
        activity="Strength",
        location="Balance Fitness",
        status=PracticeStatus.CANCELLED,
        reason="Heat warning",
    )

    fallback = build_weekly_summary_fallback_text(
        [cancelled, active],
        week_start=date(2026, 7, 13),
        weather_data={
            1: {"temp_f": 78.2, "conditions": "partly cloudy"},
            2: {"temp_f": 101, "conditions": "dangerously hot"},
        },
    )

    assert fallback == (
        "Practices this week · July 13–19. "
        "Tuesday, July 14 at 6:15 PM — Run intervals at Theodore Wirth — "
        "Forecast: 78°F, partly cloudy. "
        "Thursday, July 16 at 6:05 PM — Strength at Balance Fitness — "
        "CANCELLED: Heat warning."
    )


def test_empty_week_has_heading_and_clear_copy_without_footer():
    blocks = build_weekly_summary_blocks([], week_start=date(2026, 7, 13))
    fallback = build_weekly_summary_fallback_text(
        [], week_start=date(2026, 7, 13)
    )

    assert header_text(blocks) == "📅 Practices this week · July 13–19"
    assert section_texts(blocks) == ["No practices scheduled this week."]
    assert not [block for block in blocks if block["type"] == "context"]
    assert fallback == (
        "Practices this week · July 13–19. No practices scheduled this week."
    )


@pytest.mark.parametrize(
    "builder",
    [build_weekly_summary_blocks, build_weekly_summary_fallback_text],
)
def test_builders_require_an_explicit_monday(builder):
    with pytest.raises(TypeError):
        builder([])
    with pytest.raises(ValueError, match="week_start must be a Monday"):
        builder([], week_start=date(2026, 7, 14))


def test_weekly_outputs_apply_slack_length_guards():
    cancelled = practice(
        1,
        datetime(2026, 7, 14, 18, 15),
        status=PracticeStatus.CANCELLED,
        reason="x" * 5000,
    )

    blocks = build_weekly_summary_blocks(
        [cancelled], week_start=date(2026, 7, 13)
    )
    fallback = build_weekly_summary_fallback_text(
        [cancelled], week_start=date(2026, 7, 13)
    )

    assert max(len(text) for text in section_texts(blocks)) <= 3000
    assert len(fallback) <= 4000


def oversized_same_day_sessions():
    return [
        practice(
            1,
            datetime(2026, 7, 14, 17, 0),
            activity="Cancelled Strength",
            location="First Park",
            status=PracticeStatus.CANCELLED,
            reason="R" * 5000,
        ),
        practice(
            2,
            datetime(2026, 7, 14, 18, 0),
            activity="A" * 5000,
            practice_type="T" * 5000,
            location="L" * 5000,
        ),
        practice(
            3,
            datetime(2026, 7, 14, 19, 0),
            activity="Late Run",
            location="Final Trailhead",
        ),
    ]


def test_oversized_first_and_middle_rows_preserve_later_block_essentials():
    sessions = oversized_same_day_sessions()

    blocks = build_weekly_summary_blocks(
        sessions,
        week_start=date(2026, 7, 13),
        weather_data={2: {"temp_f": 80, "conditions": "C" * 5000}},
    )
    [day_text] = section_texts(blocks)

    assert len(day_text) <= 3000
    assert "5:00 PM · 🚫 CANCELLED ·" in day_text
    assert "Cancelled Strength · First Park" in day_text
    assert "6:00 PM ·" in day_text
    assert "Forecast: 80°F" in day_text
    assert "7:00 PM · Late Run · Final Trailhead" in day_text


def test_oversized_first_and_middle_rows_preserve_later_fallback_essentials():
    sessions = oversized_same_day_sessions()

    fallback = build_weekly_summary_fallback_text(
        sessions,
        week_start=date(2026, 7, 13),
        weather_data={2: {"temp_f": 80, "conditions": "C" * 5000}},
    )

    assert len(fallback) <= 4000
    assert "Tuesday, July 14 at 5:00 PM" in fallback
    assert "Cancelled Strength at First Park — CANCELLED:" in fallback
    assert "Tuesday, July 14 at 6:00 PM" in fallback
    assert "Forecast: 80°F" in fallback
    assert (
        "Tuesday, July 14 at 7:00 PM — Late Run at Final Trailhead"
        in fallback
    )


def test_high_count_weekly_fallback_preserves_every_practice_row():
    week_start = date(2026, 7, 13)
    sessions = []
    weather_data = {}
    for index in range(21):
        when = datetime.combine(
            week_start + timedelta(days=index // 3),
            datetime.min.time(),
        ).replace(hour=6 + (index % 3), minute=index)
        cancelled = index % 2 == 0
        sessions.append(practice(
            index + 1,
            when,
            activity=f"ROW-{index:02d}-" + ("a" * 70),
            location=f"SITE-{index:02d}-" + ("l" * 90),
            status=(
                PracticeStatus.CANCELLED
                if cancelled else PracticeStatus.SCHEDULED
            ),
            reason=(f"REASON-{index:02d}-" + ("r" * 150) if cancelled else None),
        ))
        if not cancelled:
            weather_data[index + 1] = {
                "temp_f": 70 + index,
                "conditions": f"WEATHER-{index:02d}-" + ("w" * 120),
            }

    fallback = build_weekly_summary_fallback_text(
        sessions,
        week_start=week_start,
        weather_data=weather_data,
    )

    assert len(fallback) <= 4_000
    for index, session in enumerate(sessions):
        assert session.date.strftime("%A, %B %-d at %-I:%M %p") in fallback
        assert f"ROW-{index:02d}" in fallback
        assert f"SITE-{index:02d}" in fallback
        if session.status == PracticeStatus.CANCELLED:
            assert f"CANCELLED: REASON-{index:02d}" in fallback
        else:
            assert f"Forecast: {70 + index}°F, WEATHER-{index:02d}" in fallback
