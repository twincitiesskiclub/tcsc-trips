from types import SimpleNamespace

import pytest

from app.practices.plan_reactions import (
    PlanReactionValidationError,
    format_plan_reaction_legend,
    format_plan_reaction_lines,
    normalize_plan_reactions,
    parse_plan_reaction_lines,
    resolve_default_plan_reactions,
)


def source(name, options):
    return SimpleNamespace(name=name, default_plan_reactions=options)


def test_parse_and_format_colon_wrapped_lines():
    parsed = parse_plan_reaction_lines(
        ":evergreen_tree: Endurance instead of intervals\n:athletic_shoe: Run"
    )
    assert parsed == [
        {"emoji": "evergreen_tree", "label": "Endurance instead of intervals"},
        {"emoji": "athletic_shoe", "label": "Run"},
    ]
    assert format_plan_reaction_lines(parsed).splitlines()[0].startswith(":evergreen_tree:")
    assert format_plan_reaction_legend(parsed) == (
        ":evergreen_tree: Endurance instead of intervals · :athletic_shoe: Run"
    )


def test_legend_escapes_member_supplied_slack_markup():
    assert format_plan_reaction_legend([
        {"emoji": "evergreen_tree", "label": "Easy < 60 min & social > speed"}
    ]) == ":evergreen_tree: Easy &lt; 60 min &amp; social &gt; speed"


def test_resolver_orders_types_then_activities_and_deduplicates_identical_pair():
    duplicate = [{"emoji": "evergreen_tree", "label": "Endurance instead of intervals"}]
    result = resolve_default_plan_reactions(
        [source("Intervals", duplicate)],
        [source("Rollerski", duplicate + [{"emoji": "hatching_chick", "label": "New to rollerskiing"}])],
    )
    assert result == duplicate + [{"emoji": "hatching_chick", "label": "New to rollerskiing"}]


def test_resolver_rejects_same_emoji_with_two_labels():
    with pytest.raises(PlanReactionValidationError, match="conflicting labels") as error:
        resolve_default_plan_reactions(
            [source("Intervals", [{"emoji": "evergreen_tree", "label": "Endurance"}])],
            [source("Rollerski", [{"emoji": "evergreen_tree", "label": "New skier"}])],
        )
    assert "Workout Type Intervals" in str(error.value)
    assert "Activity Rollerski" in str(error.value)


@pytest.mark.parametrize("emoji", ["white_check_mark", "six", "ballot_box_with_check"])
def test_reserved_attendance_emoji_is_rejected(emoji):
    with pytest.raises(PlanReactionValidationError, match="reserved"):
        normalize_plan_reactions([{"emoji": emoji, "label": "Not allowed"}])


def test_more_than_four_and_multiline_label_are_rejected():
    with pytest.raises(PlanReactionValidationError, match="at most 4"):
        normalize_plan_reactions([
            {"emoji": f"custom_{index}", "label": f"Choice {index}"}
            for index in range(5)
        ])
    with pytest.raises(PlanReactionValidationError, match="single line"):
        normalize_plan_reactions([{"emoji": "evergreen_tree", "label": "One\nTwo"}])


def test_bare_shortcode_empty_and_four_value_boundaries():
    assert parse_plan_reaction_lines("evergreen_tree Endurance") == [
        {"emoji": "evergreen_tree", "label": "Endurance"}
    ]
    assert parse_plan_reaction_lines("") == []
    assert len(normalize_plan_reactions([
        {"emoji": f"choice_{index}", "label": f"Choice {index}"}
        for index in range(4)
    ])) == 4


def test_label_length_and_shortcode_wrapping_boundaries():
    assert normalize_plan_reactions([
        {"emoji": "evergreen_tree", "label": "L" * 80}
    ])[0]["label"] == "L" * 80
    with pytest.raises(PlanReactionValidationError, match="80 characters"):
        normalize_plan_reactions([
            {"emoji": "evergreen_tree", "label": "L" * 81}
        ])
    for invalid in (":evergreen_tree Endurance", "evergreen_tree: Endurance"):
        with pytest.raises(PlanReactionValidationError, match="Line 1"):
            parse_plan_reaction_lines(invalid)


def test_resolver_sorts_sources_and_rejects_effective_overflow():
    ordered = resolve_default_plan_reactions(
        [source("Zulu", [{"emoji": "z", "label": "Zulu"}]),
         source("Alpha", [{"emoji": "a", "label": "Alpha"}])],
        [source("Beta", [{"emoji": "b", "label": "Beta"}])],
    )
    assert [item["emoji"] for item in ordered] == ["a", "z", "b"]
    with pytest.raises(PlanReactionValidationError, match="more than 4"):
        resolve_default_plan_reactions(
            [source("Type", [
                {"emoji": f"type_{index}", "label": f"Type {index}"}
                for index in range(3)
            ])],
            [source("Activity", [
                {"emoji": f"activity_{index}", "label": f"Activity {index}"}
                for index in range(2)
            ])],
        )
