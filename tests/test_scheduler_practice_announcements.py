from contextlib import contextmanager
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from zoneinfo import ZoneInfo

import app.scheduler as scheduler
from app.scheduler import run_practice_announcements_job


class _Column:
    def __ge__(self, _other):
        return object()

    def __le__(self, _other):
        return object()

    def __lt__(self, _other):
        return object()

    def in_(self, _values):
        return object()

    def is_(self, _value):
        return object()


class _Query:
    def __init__(self, practices):
        self.practices = practices

    def filter(self, *_criteria):
        return self

    def order_by(self, *_columns):
        return self

    def all(self):
        return self.practices


class _FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 7, 14, 8, 0, tzinfo=tz or ZoneInfo("UTC"))


def test_scheduler_delegates_conditions_lookup_to_announcement_layer():
    practice = SimpleNamespace(
        id=42,
        date=datetime(2026, 7, 14, 18, 15),
        location=SimpleNamespace(latitude=44.99, longitude=-93.32),
        practice_types=[],
        activities=[],
    )
    fake_practice_model = SimpleNamespace(
        date=_Column(),
        status=_Column(),
        slack_message_ts=_Column(),
        query=_Query([practice]),
    )

    @contextmanager
    def app_context():
        yield

    app = SimpleNamespace(app_context=app_context, logger=MagicMock())

    with patch("app.scheduler.datetime", _FixedDateTime), patch(
        "app.practices.models.Practice", fake_practice_model
    ), patch(
        "app.slack.practices.post_practice_announcement",
        return_value={"success": True},
    ) as mock_post, patch(
        "app.slack.practices.post_combined_lift_announcement"
    ), patch(
        "app.integrations.weather.get_weather_for_location"
    ) as mock_weather:
        run_practice_announcements_job(app, channel_override="practice-test")

    mock_weather.assert_not_called()
    mock_post.assert_called_once_with(
        practice, channel_override="practice-test"
    )


def _tag(tag_id, name):
    return SimpleNamespace(id=tag_id, name=name)


def _strength_practice(
    practice_id,
    day,
    *,
    location_id=10,
    workout="3 x 8 strength circuit",
    notes="Bring indoor shoes",
    has_social=False,
    social_id=None,
    social_name=None,
    plan=None,
    strength_source="activity",
):
    strength = _tag(1, "Strength")
    activities = [strength] if strength_source == "activity" else []
    practice_types = [strength] if strength_source == "type" else []
    return SimpleNamespace(
        id=practice_id,
        date=datetime(2026, 7, day, 18, 15),
        location_id=location_id,
        location=SimpleNamespace(id=location_id, name=f"Gym {location_id}"),
        workout_description=workout,
        logistics_notes=notes,
        has_social=has_social,
        social_location_id=social_id,
        social_location=(
            SimpleNamespace(id=social_id, name=social_name)
            if social_id is not None or social_name is not None
            else None
        ),
        activities=activities,
        practice_types=practice_types,
        plan_reactions=list(plan or []),
        slack_session_emoji=None,
    )


def _run_scheduler(window, all_strength=None, combined_result=None):
    fake_practice_model = SimpleNamespace(
        date=_Column(),
        status=_Column(),
        slack_message_ts=_Column(),
        query=_Query(window),
    )

    @contextmanager
    def app_context():
        yield

    app = SimpleNamespace(app_context=app_context, logger=MagicMock())
    stack = [
        patch("app.scheduler.datetime", _FixedDateTime),
        patch("app.practices.models.Practice", fake_practice_model),
        patch(
            "app.scheduler._get_upcoming_strength_practices",
            return_value=list(all_strength if all_strength is not None else window),
        ),
        patch(
            "app.slack.practices.post_practice_announcement",
            return_value={"success": True},
        ),
        patch(
            "app.slack.practices.post_combined_lift_announcement",
            return_value=combined_result or {"success": True},
        ),
        patch("app.scheduler.db", create=True),
    ]
    entered = [item.start() for item in stack]
    try:
        run_practice_announcements_job(app, channel_override="practice-test")
    finally:
        for item in reversed(stack):
            item.stop()
    return entered[3], entered[4], entered[5]


def test_compatibility_key_normalizes_text_and_sorts_tags_but_not_plan_order():
    first = _strength_practice(
        1,
        14,
        workout=" 3 x 8   strength circuit ",
        notes=" Bring   indoor shoes ",
        plan=[
            {"emoji": "evergreen_tree", "label": "Endurance"},
            {"emoji": "athletic_shoe", "label": "Run"},
        ],
    )
    first.activities = [_tag(2, "Mobility"), _tag(1, "Strength")]
    second = _strength_practice(
        2,
        15,
        plan=[
            {"emoji": "evergreen_tree", "label": "Endurance"},
            {"emoji": "athletic_shoe", "label": "Run"},
        ],
    )
    second.activities = [_tag(1, "Strength"), _tag(2, "Mobility")]

    assert scheduler.combined_compatibility_key(first) == (
        scheduler.combined_compatibility_key(second)
    )

    second.plan_reactions.reverse()
    assert scheduler.combined_compatibility_key(first) != (
        scheduler.combined_compatibility_key(second)
    )


def test_two_compatible_strength_sessions_make_one_combined_call():
    practices = [_strength_practice(1, 14), _strength_practice(2, 15)]

    standalone, combined, _db = _run_scheduler(practices)

    standalone.assert_not_called()
    combined.assert_called_once_with(
        practices, channel_override="practice-test"
    )


@pytest.mark.parametrize(
    "change",
    [
        {"location_id": 11},
        {"workout": "Different circuit"},
        {"notes": "Different notes"},
        {"has_social": True, "social_id": 20, "social_name": "Cafe"},
        {
            "plan": [
                {"emoji": "athletic_shoe", "label": "Run"},
                {"emoji": "evergreen_tree", "label": "Endurance"},
            ]
        },
    ],
)
def test_incompatible_member_facing_content_posts_each_session_standalone(change):
    plan = [
        {"emoji": "evergreen_tree", "label": "Endurance"},
        {"emoji": "athletic_shoe", "label": "Run"},
    ]
    changed = {"plan": plan, **change}
    practices = [
        _strength_practice(1, 14, plan=plan),
        _strength_practice(2, 15, **changed),
    ]

    standalone, combined, _db = _run_scheduler(practices)

    combined.assert_not_called()
    assert [item.args[0].id for item in standalone.call_args_list] == [1, 2]


def test_different_social_destinations_post_each_session_standalone():
    practices = [
        _strength_practice(
            1,
            14,
            has_social=True,
            social_id=20,
            social_name="Cafe A",
        ),
        _strength_practice(
            2,
            15,
            has_social=True,
            social_id=21,
            social_name="Cafe B",
        ),
    ]

    standalone, combined, _db = _run_scheduler(practices)

    combined.assert_not_called()
    assert [item.args[0].id for item in standalone.call_args_list] == [1, 2]


@pytest.mark.parametrize("strength_source", ["activity", "type"])
def test_strength_from_activity_or_workout_type_uses_combined_path(strength_source):
    practices = [
        _strength_practice(1, 14, strength_source=strength_source),
        _strength_practice(2, 15, strength_source=strength_source),
    ]

    standalone, combined, _db = _run_scheduler(practices)

    standalone.assert_not_called()
    combined.assert_called_once()


def test_single_strength_session_posts_standalone():
    practice = _strength_practice(1, 14)

    standalone, combined, _db = _run_scheduler([practice])

    combined.assert_not_called()
    standalone.assert_called_once_with(
        practice, channel_override="practice-test"
    )


def test_future_incompatible_singleton_is_not_announced_early():
    current = _strength_practice(1, 14, location_id=10)
    future = _strength_practice(2, 15, location_id=11)

    standalone, combined, _db = _run_scheduler(
        [current], all_strength=[current, future]
    )

    combined.assert_not_called()
    standalone.assert_called_once_with(
        current, channel_override="practice-test"
    )


def test_four_compatible_sessions_post_only_current_window_members_standalone():
    practices = [_strength_practice(i, 13 + i) for i in range(1, 5)]

    standalone, combined, _db = _run_scheduler(
        practices[:2], all_strength=practices
    )

    combined.assert_not_called()
    assert [item.args[0].id for item in standalone.call_args_list] == [1, 2]


def test_two_independent_compatible_pairs_make_two_disjoint_combined_calls():
    practices = [
        _strength_practice(1, 14, location_id=10),
        _strength_practice(2, 15, location_id=10),
        _strength_practice(3, 16, location_id=11),
        _strength_practice(4, 17, location_id=11),
    ]

    standalone, combined, _db = _run_scheduler(practices)

    standalone.assert_not_called()
    groups = [[item.id for item in args.args[0]] for args in combined.call_args_list]
    assert groups == [[1, 2], [3, 4]]
    assert len({item for group in groups for item in group}) == 4


def test_safe_combined_validation_failure_falls_back_same_run_and_clears_values():
    practices = [_strength_practice(1, 14), _strength_practice(2, 15)]
    practices[0].slack_session_emoji = "six"
    practices[1].slack_session_emoji = "six"

    standalone, combined, mock_db = _run_scheduler(
        practices,
        combined_result={
            "success": False,
            "error": "invalid mapping",
            "safe_to_fallback": True,
        },
    )

    combined.assert_called_once()
    assert [item.args[0].id for item in standalone.call_args_list] == [1, 2]
    assert [item.slack_session_emoji for item in practices] == [None, None]
    mock_db.session.commit.assert_called_once()


def test_ambiguous_combined_failure_never_falls_back_to_duplicate_roots():
    practices = [_strength_practice(1, 14), _strength_practice(2, 15)]

    standalone, combined, _db = _run_scheduler(
        practices,
        combined_result={"success": False, "error": "network failure"},
    )

    combined.assert_called_once()
    standalone.assert_not_called()
