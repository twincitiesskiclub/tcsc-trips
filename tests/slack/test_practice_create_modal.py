"""Tests for the Slack 'Add Practice' (create) modal builder.

Covers the coach/lead pickers added so coaches can assign people at creation
time from the weekly coach-summary 'Add Practice' button.
"""

from datetime import datetime
from types import SimpleNamespace

from app.practices.plan_reaction_editor import build_plan_reaction_editor_state
from app.practices.plan_reactions import (
    EVERGREEN_PLAN_REACTION,
    build_plan_reaction_catalog,
)
from app.slack.bolt_app import _parse_practice_authoring_values
from app.slack.modals import build_practice_create_modal
from app.slack.practice_reaction_editor import (
    decode_practice_reaction_metadata,
)


def _blocks_by_id(modal):
    return {b.get("block_id"): b for b in modal["blocks"] if b.get("block_id")}


def _authoring_values(workout="", plan_text=""):
    return {
        "workout_block": {"workout_description": {"value": workout}},
        "plan_reactions_block": {"plan_reactions": {"value": plan_text}},
    }


def _reaction_inputs():
    intervals = SimpleNamespace(
        id=1,
        name="Intervals",
        default_plan_reactions=[EVERGREEN_PLAN_REACTION],
    )
    editor = build_plan_reaction_editor_state(
        practice_types=[intervals],
        activities=[],
        saved_snapshot=None,
    ).state
    return {
        "reaction_editor": editor,
        "reaction_catalog": build_plan_reaction_catalog([intervals], []),
    }


def test_create_modal_has_coach_and_lead_pickers():
    eligible_coaches = [(1, "Alice Coach", "U1"), (2, "Bob Coach", "U2")]
    eligible_leads = [(3, "Carol Lead", "U3")]
    modal = build_practice_create_modal(
        datetime(2026, 6, 9, 18, 0),
        "18:00",
        locations=[(10, "Theodore Wirth")],
        eligible_coaches=eligible_coaches,
        eligible_leads=eligible_leads,
        **_reaction_inputs(),
    )
    blocks = _blocks_by_id(modal)
    assert "coaches_block" in blocks, "create modal must expose a Coaches picker"
    assert "leads_block" in blocks, "create modal must expose a Leads picker"
    assert blocks["coaches_block"]["element"]["action_id"] == "coach_ids"
    assert blocks["leads_block"]["element"]["action_id"] == "lead_ids"


def test_create_modal_preselects_default_coaches():
    modal = build_practice_create_modal(
        datetime(2026, 6, 9, 18, 0),
        "18:00",
        locations=[(10, "Theodore Wirth")],
        eligible_coaches=[(1, "Alice Coach", "U1"), (2, "Bob Coach", "U2")],
        eligible_leads=[(3, "Carol Lead", "U3")],
        slot_defaults={"coach_ids": [2]},
        **_reaction_inputs(),
    )
    coaches = _blocks_by_id(modal)["coaches_block"]["element"]
    initial = {o["value"] for o in coaches.get("initial_options", [])}
    assert initial == {"2"}, "default coach_ids should be pre-selected"


def test_create_modal_omits_pickers_when_no_people():
    """No eligible people -> no coach/lead blocks (graceful, like the edit modal)."""
    modal = build_practice_create_modal(
        datetime(2026, 6, 9, 18, 0),
        "18:00",
        locations=[(10, "Theodore Wirth")],
        **_reaction_inputs(),
    )
    blocks = _blocks_by_id(modal)
    assert "coaches_block" not in blocks
    assert "leads_block" not in blocks


def test_create_uses_structured_reactions_and_dispatching_selectors():
    modal = build_practice_create_modal(
        datetime(2026, 7, 14, 18, 15),
        "18:15",
        locations=[(10, "Theodore Wirth")],
        all_activities=[(1, "Run"), (2, "Rollerski")],
        all_types=[(1, "Intervals")],
        slot_defaults={"activity_ids": [1, 2], "type_ids": [1]},
        **_reaction_inputs(),
    )
    blocks = _blocks_by_id(modal)

    assert "plan_reactions_block" not in blocks
    assert blocks["activities_block"]["dispatch_action"] is True
    assert blocks["types_block"]["dispatch_action"] is True
    assert blocks["practice_reaction_key_r0"]["text"]["text"] == (
        "*:evergreen_tree:*"
    )
    assert blocks["practice_reaction_row_r0"]["element"]["max_length"] == 80
    assert blocks["workout_block"]["element"]["max_length"] == 2500
    mode, context, state, preview = decode_practice_reaction_metadata(
        modal["private_metadata"]
    )
    assert mode == "create"
    assert context == {
        "date": "2026-07-14",
        "channel_id": None,
        "message_ts": None,
    }
    assert state.rows[0].emoji == "evergreen_tree"
    assert preview is None


def test_create_submission_uses_edited_visible_plan_value():
    fields, errors = _parse_practice_authoring_values(
        _authoring_values(
            workout="5 x 4 minutes",
            plan_text=":athletic_shoe: Run instead",
        ),
        include_plan_reactions=True,
    )
    assert errors == {}
    assert fields == {
        "workout_description": "5 x 4 minutes",
        "plan_reactions": [{"emoji": "athletic_shoe", "label": "Run instead"}],
    }


def test_create_submission_preserves_full_skin_tone_reaction_name():
    fields, errors = _parse_practice_authoring_values(
        _authoring_values(
            plan_text=":older_adult::skin-tone-4: experienced rollerskier"
        ),
        include_plan_reactions=True,
    )
    assert errors == {}
    assert fields["plan_reactions"] == [{
        "emoji": "older_adult::skin-tone-4",
        "label": "experienced rollerskier",
    }]


def test_create_submission_can_clear_prefilled_plan_value():
    fields, errors = _parse_practice_authoring_values(
        _authoring_values(plan_text=""), include_plan_reactions=True
    )
    assert errors == {}
    assert fields["plan_reactions"] == []


def test_create_submission_maps_invalid_plan_to_its_slack_block():
    fields, errors = _parse_practice_authoring_values(
        _authoring_values(
            plan_text=":evergreen_tree Endurance instead of intervals"
        ),
        include_plan_reactions=True,
    )
    assert "plan_reactions" not in fields
    assert errors == {
        "plan_reactions_block": "Line 1: use :emoji: Member-facing label"
    }


def test_authoring_rejects_tampered_oversized_workout():
    fields, errors = _parse_practice_authoring_values(
        _authoring_values(workout="x" * 2501), include_plan_reactions=False
    )
    assert len(fields["workout_description"]) == 2501
    assert errors == {
        "workout_block": "Workout must be 2,500 characters or fewer"
    }
