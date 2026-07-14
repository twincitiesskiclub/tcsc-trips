"""Contracts for the discard-only Slack Practice Preview."""

from datetime import datetime

from app.slack.modals import (
    build_practice_create_modal,
    build_practice_preview_modal,
)


PREVIEW_DATE = datetime(2026, 7, 14, 18, 15)
PREVIEW_REACTIONS = [
    {"emoji": "evergreen_tree", "label": "Endurance instead of intervals"},
    {"emoji": "hatching_chick", "label": "new rollerskier"},
    {
        "emoji": "older_adult::skin-tone-4",
        "label": "experienced rollerskier",
    },
    {"emoji": "athletic_shoe", "label": "runner"},
]


def _blocks_by_id(modal):
    return {
        block["block_id"]: block
        for block in modal["blocks"]
        if "block_id" in block
    }


def _expected_create_modal():
    return build_practice_create_modal(
        PREVIEW_DATE,
        "18:15",
        locations=[(1, "Theodore Wirth - Trailhead")],
        all_activities=[(1, "Rollerski"), (2, "Running")],
        all_types=[(1, "Intervals"), (2, "Technique")],
        slot_defaults={
            "location_id": 1,
            "activity_ids": [1],
            "type_ids": [1],
            "coach_ids": [1],
            "lead_ids": [2],
        },
        eligible_coaches=[(1, "Preview Coach", "U_PREVIEW_COACH")],
        eligible_leads=[(2, "Preview Lead", "U_PREVIEW_LEAD")],
        initial_plan_reactions=PREVIEW_REACTIONS,
    )


def test_preview_wraps_the_production_create_modal():
    expected = _expected_create_modal()
    expected.update({
        "title": {"type": "plain_text", "text": "Practice Preview"},
        "submit": {"type": "plain_text", "text": "Close Preview"},
        "callback_id": "practice_preview",
        "private_metadata": "",
    })

    assert build_practice_preview_modal(PREVIEW_DATE) == expected


def test_preview_prefills_synthetic_options_and_all_reaction_lines():
    blocks = _blocks_by_id(build_practice_preview_modal(PREVIEW_DATE))

    assert blocks["time_block"]["element"]["initial_time"] == "18:15"
    assert blocks["location_block"]["element"]["initial_option"]["value"] == "1"
    assert [
        option["value"]
        for option in blocks["activities_block"]["element"]["initial_options"]
    ] == ["1"]
    assert [
        option["value"]
        for option in blocks["types_block"]["element"]["initial_options"]
    ] == ["1"]
    assert [
        option["value"]
        for option in blocks["coaches_block"]["element"]["initial_options"]
    ] == ["1"]
    assert [
        option["value"]
        for option in blocks["leads_block"]["element"]["initial_options"]
    ] == ["2"]
    assert blocks["plan_reactions_block"]["element"]["initial_value"] == (
        ":evergreen_tree: Endurance instead of intervals\n"
        ":hatching_chick: new rollerskier\n"
        ":older_adult::skin-tone-4: experienced rollerskier\n"
        ":athletic_shoe: runner"
    )
