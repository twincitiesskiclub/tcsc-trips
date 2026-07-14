"""Source contracts for the inline Plan-reaction defaults editor."""

from pathlib import Path


CONFIG_TEMPLATE = (
    Path(__file__).resolve().parents[2]
    / "app"
    / "templates"
    / "admin"
    / "practices"
    / "config.html"
)


def _save_plan_reactions_source():
    source = CONFIG_TEMPLATE.read_text()
    start = source.index("    function savePlanReactions() {")
    end = source.index("\n    const callbacks =", start)
    return source[start:end]


def test_incomplete_plan_reaction_waits_neutrally_without_mutation_or_focus():
    function_source = _save_plan_reactions_source()
    branch_start = function_source.index("        if (incomplete) {")
    save_start = function_source.index(
        "        setStatus('Saving\\u2026', false);", branch_start
    )
    incomplete_branch = function_source[branch_start:save_start]

    assert "setStatus('Complete both fields to save.', false);" in incomplete_branch
    assert "return;" in incomplete_branch
    assert "AdminUI.mutate(" not in incomplete_branch
    assert ".focus()" not in incomplete_branch


def test_complete_plan_reaction_keeps_success_and_server_error_states():
    function_source = _save_plan_reactions_source()

    assert "setStatus('Saving\\u2026', false);" in function_source
    assert "AdminUI.mutate(" in function_source
    assert "setStatus('Saved.', false);" in function_source
    assert "setStatus(error.message, true);" in function_source
