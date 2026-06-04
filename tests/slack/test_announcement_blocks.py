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
