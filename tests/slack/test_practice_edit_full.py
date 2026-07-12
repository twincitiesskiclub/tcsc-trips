from datetime import datetime

from app.practices.interfaces import PracticeInfo, PracticeStatus
from app.slack.modals import build_practice_edit_full_modal


def test_full_edit_modal_limits_workout_to_2500_characters():
    practice = PracticeInfo(
        id=42,
        date=datetime(2026, 7, 14, 18, 15),
        day_of_week="Tuesday",
        status=PracticeStatus.SCHEDULED,
        workout_description="5 x 4 minutes",
    )
    modal = build_practice_edit_full_modal(practice)
    blocks = {
        block["block_id"]: block
        for block in modal["blocks"]
        if "block_id" in block
    }
    assert blocks["workout_block"]["element"]["max_length"] == 2500
