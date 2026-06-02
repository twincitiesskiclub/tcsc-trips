"""Tests for the practice person (coach/lead) multi-select builder."""

from types import SimpleNamespace

from app.slack.modals import _build_person_multi_select


def _assigned(user_id, display_name="Someone"):
    return SimpleNamespace(user_id=user_id, display_name=display_name)


def test_eligible_users_become_options():
    eligible = [(1, "Alice A", "U1"), (2, "Bob B", "U2")]
    el = _build_person_multi_select("coach_ids", "Pick coaches", eligible, [])
    values = {o["value"] for o in el["options"]}
    assert values == {"1", "2"}
    assert "initial_options" not in el


def test_assigned_user_outside_eligible_is_preserved():
    eligible = [(1, "Alice A", "U1"), (2, "Bob B", "U2")]
    assigned = [_assigned(3, "Carol C")]  # not in eligible list
    el = _build_person_multi_select("coach_ids", "Pick coaches", eligible, assigned)
    option_values = {o["value"] for o in el["options"]}
    assert "3" in option_values, "assigned user must survive even if not eligible"
    init_values = {o["value"] for o in el["initial_options"]}
    assert init_values == {"3"}


def test_assigned_user_with_blank_name_gets_fallback_label():
    assigned = [_assigned(7, "")]
    el = _build_person_multi_select("coach_ids", "Pick coaches", [], assigned)
    added = next(o for o in el["options"] if o["value"] == "7")
    assert added["text"]["text"].strip() != ""
