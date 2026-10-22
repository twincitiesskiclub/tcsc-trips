"""Exact-copy contracts for the push-notification text of @channel posts.

The notification is the plain `text` field Slack shows on the lock screen. It
carries only when, where and what, then sends the member into Slack.
"""

from datetime import date, datetime
from types import SimpleNamespace

from app.practices.interfaces import AnnouncementConditions, PracticeStatus
from app.slack.blocks.announcements import (
    build_combined_fallback_text,
    build_practice_fallback_text,
)
from app.slack.blocks.summary import build_weekly_summary_fallback_text


MONDAY = date(2026, 7, 13)


def _named(*names):
    return [SimpleNamespace(name=name) for name in names]


def _practice(
    when=datetime(2026, 7, 13, 18, 15),
    *,
    activities=("Pole Run",),
    types=("Intervals",),
    location="Theodore Wirth",
    status=PracticeStatus.SCHEDULED,
    emoji=None,
    practice_id=1,
):
    return SimpleNamespace(
        id=practice_id,
        date=when,
        status=status,
        activities=_named(*activities),
        practice_types=_named(*types),
        location=SimpleNamespace(name=location) if location else None,
        workout_description="2x3m L3 -> 4-6x3m L4",
        logistics_notes="Meet at the chalet.",
        has_social=True,
        social_location=SimpleNamespace(name="Utepils"),
        plan_reactions=[{"emoji": "evergreen_tree", "label": "Endurance"}],
        slack_session_emoji=emoji,
        cancellation_reason="Lightning" if status == PracticeStatus.CANCELLED else None,
    )


def _single(practice, today=MONDAY):
    return build_practice_fallback_text(
        practice, AnnouncementConditions(), today=today
    )


def _strength(hour, minute, *, day=13, emoji="six", **over):
    over.setdefault("activities", ("Strength",))
    over.setdefault("types", ("Circuit",))
    over.setdefault("location", "Balance Fitness Studio")
    return _practice(
        datetime(2026, 7, day, hour, minute),
        emoji=emoji,
        practice_id=hour * 100 + minute,
        **over,
    )


def _combined(practices, today=MONDAY):
    return build_combined_fallback_text(practices, today=today)


# Single practice ------------------------------------------------------------


def test_same_day_practice_reads_today_with_time_place_kind_and_rsvp():
    assert _single(_practice()) == (
        "Today 6:15 PM at Theodore Wirth. Pole Run intervals. RSVP ✅ in Slack."
    )


def test_morning_practice_posted_the_night_before_reads_tomorrow():
    practice = _practice(datetime(2026, 7, 14, 7, 0))
    assert _single(practice).startswith("Tomorrow 7:00 AM at Theodore Wirth.")


def test_practice_further_out_uses_the_weekday_name():
    practice = _practice(datetime(2026, 7, 18, 9, 0))
    assert _single(practice).startswith("Saturday 9:00 AM at Theodore Wirth.")


def test_multiple_activities_and_types_join_with_plus():
    practice = _practice(
        activities=("Pole Hike, Pole Run", "Skate/Classic Rollerski"),
        types=("Intervals", "Technique"),
    )
    assert (
        "Pole Hike, Pole Run + Skate/Classic Rollerski intervals + technique."
        in _single(practice)
    )


def test_activity_and_type_with_the_same_name_appear_once():
    practice = _practice(activities=("Kickoff",), types=("Kickoff",))
    assert "at Theodore Wirth. Kickoff. RSVP" in _single(practice)


def test_type_alone_is_capitalized():
    practice = _practice(activities=(), types=("Intervals",))
    assert "at Theodore Wirth. Intervals. RSVP" in _single(practice)


def test_missing_kind_and_location_are_dropped_not_printed():
    practice = _practice(activities=(), types=(), location=None)
    assert _single(practice) == "Today 6:15 PM. RSVP ✅ in Slack."


def test_notification_leaves_out_workout_notes_social_status_and_conditions():
    fallback = _single(_practice())
    for left_out in (
        "Status", "Workout", "L4", "chalet", "Utepils", "Social",
        "Headlamp", "evergreen", "Running late", "&gt;",
    ):
        assert left_out not in fallback


def test_authored_slack_tokens_are_plainified():
    practice = _practice(location="Wirth <!channel> :wave:")
    fallback = _single(practice)
    assert "<!channel>" not in fallback
    assert ":wave:" not in fallback


def test_cancelled_practice_says_so_and_drops_the_rsvp():
    practice = _practice(status=PracticeStatus.CANCELLED)
    assert _single(practice) == (
        "Cancelled. Today 6:15 PM at Theodore Wirth. Pole Run intervals."
    )


# Combined strength ----------------------------------------------------------


def test_same_day_sessions_share_one_meridiem_and_ask_for_session_rsvp():
    practices = [_strength(18, 5), _strength(19, 20, emoji="seven")]
    assert _combined(practices) == (
        "Today 6:05 or 7:20 PM at Balance Fitness Studio. Strength circuit. "
        "RSVP ✅ for your session in Slack."
    )


def test_sessions_across_noon_keep_both_meridiems():
    practices = [_strength(11, 0), _strength(18, 5, emoji="seven")]
    assert _combined(practices).startswith(
        "Today 11:00 AM or 6:05 PM at Balance Fitness Studio."
    )


def test_sessions_on_different_days_name_each_day():
    practices = [_strength(18, 5), _strength(18, 5, day=14, emoji="seven")]
    assert _combined(practices).startswith(
        "Today 6:05 PM or tomorrow 6:05 PM at Balance Fitness Studio."
    )


def test_sessions_at_different_locations_name_each_location():
    practices = [
        _strength(18, 5),
        _strength(19, 20, emoji="seven", location="Hyland"),
    ]
    assert _combined(practices).startswith(
        "Today 6:05 PM at Balance Fitness Studio or 7:20 PM at Hyland."
    )


def test_cancelled_session_drops_out_of_the_times():
    practices = [
        _strength(18, 5, status=PracticeStatus.CANCELLED),
        _strength(19, 20, emoji="seven"),
    ]
    assert _combined(practices).startswith(
        "Today 7:20 PM at Balance Fitness Studio. Strength circuit. RSVP"
    )


def test_all_sessions_cancelled_says_so_and_drops_the_rsvp():
    practices = [
        _strength(18, 5, status=PracticeStatus.CANCELLED),
        _strength(19, 20, emoji="seven", status=PracticeStatus.CANCELLED),
    ]
    assert _combined(practices) == (
        "Cancelled. Today 6:05 or 7:20 PM at Balance Fitness Studio. "
        "Strength circuit."
    )


# Weekly summary -------------------------------------------------------------


def _week(*days, cancelled=()):
    return [
        _practice(
            datetime(2026, 7, day, 18, 0),
            practice_id=day,
            status=(
                PracticeStatus.CANCELLED if day in cancelled
                else PracticeStatus.SCHEDULED
            ),
        )
        for day in days
    ]


def _weekly(practices):
    return build_weekly_summary_fallback_text(practices, week_start=MONDAY)


def test_weekly_counts_practice_days_and_names_them():
    practices = _week(14, 16) + [_practice(datetime(2026, 7, 16, 19, 20))]
    assert _weekly(practices) == (
        "2 practices this week, Tuesday and Thursday. "
        "See the week's plan in Slack."
    )


def test_weekly_with_one_day_is_singular():
    assert _weekly(_week(14)) == (
        "1 practice this week, Tuesday. See the week's plan in Slack."
    )


def test_weekly_lists_many_days_without_oxford_comma():
    assert _weekly(_week(14, 15, 16, 18, 19)) == (
        "5 practices this week, Tuesday, Wednesday, Thursday, Saturday "
        "and Sunday. See the week's plan in Slack."
    )


def test_weekly_skips_cancelled_days():
    assert _weekly(_week(14, 16, cancelled=(16,))).startswith(
        "1 practice this week, Tuesday."
    )


def test_weekly_with_nothing_active_says_no_practices():
    assert _weekly([]) == "No practices scheduled this week."
    assert _weekly(_week(14, cancelled=(14,))) == (
        "No practices scheduled this week."
    )
