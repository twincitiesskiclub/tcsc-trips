"""Exact-copy contracts for the member-facing calendar-week summary."""

from datetime import date, datetime

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
        (date(2026, 7, 13), "Practices this week · July 13–19"),
        (date(2026, 7, 27), "Practices this week · July 27–August 2"),
        (
            date(2026, 12, 28),
            "Practices this week · December 28, 2026–January 3, 2027",
        ),
    ],
)
def test_heading_uses_the_explicit_full_calendar_week(week_start, expected):
    sessions = [
        practice(1, datetime.combine(week_start, datetime.min.time()).replace(hour=18))
    ]

    blocks = build_weekly_summary_blocks(sessions, week_start=week_start)

    assert header_text(blocks) == expected


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


def test_cancelled_session_stays_visible_without_weather():
    cancelled = practice(
        9,
        datetime(2026, 7, 16, 18, 5),
        activity="Strength",
        location="Balance Fitness",
        status=PracticeStatus.CANCELLED,
        reason="Heat warning",
    )

    blocks = build_weekly_summary_blocks(
        [cancelled],
        week_start=date(2026, 7, 13),
        weather_data={9: {"temp_f": 101, "conditions": "dangerously hot"}},
    )
    rendered = "\n".join(section_texts(blocks))

    assert "CANCELLED · Heat warning" in rendered
    assert "Strength · Balance Fitness" in rendered
    assert "Forecast" not in rendered
    assert "101" not in rendered


def test_footer_uses_unique_active_weekdays_and_natural_language():
    sessions = [
        practice(1, datetime(2026, 7, 14, 18, 15)),
        practice(2, datetime(2026, 7, 16, 18, 5), activity="Strength"),
        practice(3, datetime(2026, 7, 16, 19, 20), activity="Strength"),
        practice(4, datetime(2026, 7, 18, 9, 0)),
        practice(
            5,
            datetime(2026, 7, 17, 18, 0),
            status=PracticeStatus.CANCELLED,
            reason="Rest day",
        ),
    ]

    blocks = build_weekly_summary_blocks(sessions, week_start=date(2026, 7, 13))
    contexts = [
        element["text"]
        for block in blocks
        if block["type"] == "context"
        for element in block["elements"]
    ]

    assert contexts == ["Daily details posted Tue, Thu, and Sat. · <!channel>"]
    assert "Tue–Thu" not in " ".join(contexts)
    assert "Tue-Thu" not in " ".join(contexts)


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

    assert header_text(blocks) == "Practices this week · July 13–19"
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
