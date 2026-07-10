"""Tests for the Slack 'Add Practice' (create) modal builder.

Covers the coach/lead pickers added so coaches can assign people at creation
time from the weekly coach-summary 'Add Practice' button.
"""

from datetime import datetime

from app.slack.modals import build_practice_create_modal


def _blocks_by_id(modal):
    return {b.get("block_id"): b for b in modal["blocks"] if b.get("block_id")}


def test_create_modal_has_coach_and_lead_pickers():
    eligible_coaches = [(1, "Alice Coach", "U1"), (2, "Bob Coach", "U2")]
    eligible_leads = [(3, "Carol Lead", "U3")]
    modal = build_practice_create_modal(
        datetime(2026, 6, 9, 18, 0),
        "18:00",
        locations=[(10, "Theodore Wirth")],
        eligible_coaches=eligible_coaches,
        eligible_leads=eligible_leads,
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
    )
    coaches = _blocks_by_id(modal)["coaches_block"]["element"]
    initial = {o["value"] for o in coaches.get("initial_options", [])}
    assert initial == {"2"}, "default coach_ids should be pre-selected"


def test_create_modal_omits_pickers_when_no_people():
    """No eligible people -> no coach/lead blocks (graceful, like the edit modal)."""
    modal = build_practice_create_modal(
        datetime(2026, 6, 9, 18, 0), "18:00", locations=[(10, "Theodore Wirth")]
    )
    blocks = _blocks_by_id(modal)
    assert "coaches_block" not in blocks
    assert "leads_block" not in blocks
