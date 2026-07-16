from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.practices.plan_reactions import (
    EVERGREEN_PLAN_REACTION,
    MAX_PLAN_REACTION_NAME,
    PlanReactionValidationError,
    build_plan_reaction_catalog,
    format_plan_reaction_legend,
    format_plan_reaction_lines,
    format_reaction_name_for_fallback,
    format_supplemental_reaction_fallback,
    format_supplemental_reaction_sentence,
    normalize_plan_reactions,
    parse_plan_reaction_lines,
    plan_reaction_names,
    resolve_default_plan_reactions,
    resolve_plan_reaction_defaults,
    validate_authorized_plan_reactions,
)


def source(source_id, name, options):
    return SimpleNamespace(
        id=source_id,
        name=name,
        default_plan_reactions=options,
    )


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
        [source(10, "Intervals", duplicate)],
        [
            source(
                1,
                "Rollerski",
                duplicate + [{
                    "emoji": "hatching_chick",
                    "label": "New to rollerskiing",
                }],
            ),
            source(2, "Run", []),
        ],
    )
    assert result == duplicate + [{"emoji": "hatching_chick", "label": "New to rollerskiing"}]


def test_resolver_rejects_same_emoji_with_two_labels():
    with pytest.raises(PlanReactionValidationError, match="conflicting labels") as error:
        resolve_default_plan_reactions(
            [source(10, "Intervals", [{"emoji": "evergreen_tree", "label": "Endurance"}])],
            [
                source(1, "Rollerski", [{"emoji": "evergreen_tree", "label": "New skier"}]),
                source(2, "Run", []),
            ],
        )
    assert "Workout Type Intervals" in str(error.value)
    assert "Activity Rollerski" in str(error.value)


@pytest.mark.parametrize(
    ("practice_types", "activities", "expected_field"),
    [
        (
            [source(10, "Malformed Type", "not-a-list")],
            [],
            "types",
        ),
        (
            [],
            [
                source(1, "Malformed Activity", "not-a-list"),
                source(2, "Second Activity", []),
            ],
            "activities",
        ),
    ],
)
def test_settings_source_normalization_errors_identify_the_selector_field(
    practice_types,
    activities,
    expected_field,
):
    with pytest.raises(PlanReactionValidationError) as error:
        resolve_plan_reaction_defaults(practice_types, activities)

    assert error.value.field == expected_field


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


@pytest.mark.parametrize(
    "line_break",
    ["\n", "\r", "\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029"],
)
@pytest.mark.parametrize("position", ["leading", "embedded", "trailing"])
def test_every_unicode_line_break_is_rejected_in_plan_labels(
    line_break, position
):
    labels = {
        "leading": f"{line_break}First",
        "embedded": f"First{line_break}Second",
        "trailing": f"First{line_break}",
    }
    with pytest.raises(PlanReactionValidationError, match="single line"):
        normalize_plan_reactions([{
            "emoji": "evergreen_tree",
            "label": labels[position],
        }])


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
        [source(20, "Zulu", [{"emoji": "z", "label": "Zulu"}]),
         source(10, "Alpha", [{"emoji": "a", "label": "Alpha"}])],
        [
            source(1, "Beta", [{"emoji": "b", "label": "Beta"}]),
            source(2, "Gamma", []),
        ],
    )
    assert [item["emoji"] for item in ordered] == ["a", "z", "b"]
    with pytest.raises(PlanReactionValidationError, match="more than 4"):
        resolve_default_plan_reactions(
            [source(10, "Type", [
                {"emoji": f"type_{index}", "label": f"Type {index}"}
                for index in range(3)
            ])],
            [
                source(1, "Activity", [
                    {"emoji": f"activity_{index}", "label": f"Activity {index}"}
                    for index in range(2)
                ]),
                source(2, "Other Activity", []),
            ],
        )


@pytest.mark.parametrize("activity_count", [0, 1])
def test_activity_defaults_do_not_apply_before_multisport(activity_count):
    run = source(1, "Run", [{"emoji": "athletic_shoe", "label": "runner"}])
    result = resolve_plan_reaction_defaults([], [run][:activity_count])
    assert result.snapshot == []
    assert result.unconfigured_activity_names == ()


def test_types_always_apply_and_two_distinct_activities_enable_activity_defaults():
    intervals = source(10, "Intervals", [EVERGREEN_PLAN_REACTION])
    run = source(1, "Run", [{"emoji": "athletic_shoe", "label": "runner"}])
    ski = source(2, "Skate Rollerski", [
        {"emoji": "hatching_chick", "label": "new rollerskier"},
        {"emoji": "older_adult::skin-tone-4", "label": "experienced rollerskier"},
    ])
    result = resolve_plan_reaction_defaults([intervals], [ski, run, run])
    assert result.snapshot == [
        EVERGREEN_PLAN_REACTION,
        {"emoji": "athletic_shoe", "label": "runner"},
        {"emoji": "hatching_chick", "label": "new rollerskier"},
        {"emoji": "older_adult::skin-tone-4", "label": "experienced rollerskier"},
    ]
    assert result.rows[1].source_keys == ("activity:1",)


def test_multisport_names_unconfigured_activities_without_blocking():
    result = resolve_plan_reaction_defaults(
        [],
        [source(2, "Strength", []), source(1, "Run", [])],
    )
    assert result.snapshot == []
    assert result.unconfigured_activity_names == ("Run", "Strength")


def test_catalog_deduplicates_exact_pairs_but_keeps_distinct_labels_for_one_key():
    catalog = build_plan_reaction_catalog(
        [source(10, "Intervals", [EVERGREEN_PLAN_REACTION])],
        [
            source(1, "Run", [{"emoji": "athletic_shoe", "label": "runner"}]),
            source(2, "Trail Run", [{"emoji": "athletic_shoe", "label": "trail runner"}]),
            source(3, "Duplicate", [{"emoji": "athletic_shoe", "label": "runner"}]),
        ],
    )
    assert [(item.emoji, item.label) for item in catalog] == [
        ("evergreen_tree", "Endurance instead of intervals"),
        ("athletic_shoe", "runner"),
        ("athletic_shoe", "trail runner"),
    ]
    assert len({item.option_id for item in catalog}) == 3


def test_authorization_allows_custom_descriptions_but_not_unknown_keys():
    catalog = build_plan_reaction_catalog([], [
        source(1, "Run", [{"emoji": "athletic_shoe", "label": "runner"}]),
    ])
    assert validate_authorized_plan_reactions(
        [{"emoji": "athletic_shoe", "label": "Run group"}], catalog=catalog
    ) == [{"emoji": "athletic_shoe", "label": "Run group"}]
    with pytest.raises(PlanReactionValidationError, match="not configured in Settings"):
        validate_authorized_plan_reactions(
            [{"emoji": "wheel", "label": "rollerski"}], catalog=catalog
        )


def test_full_edit_authorization_protects_only_saved_snapshot_keys():
    saved = [{"emoji": "wheel", "label": "rollerski"}]
    assert validate_authorized_plan_reactions(
        [{"emoji": "wheel", "label": "classic rollerski"}],
        catalog=(),
        protected_snapshot=saved,
    ) == [{"emoji": "wheel", "label": "classic rollerski"}]


def test_skin_tone_bare_and_wrapped_names_normalize_and_round_trip():
    expected = [{
        "emoji": "older_adult::skin-tone-4",
        "label": "experienced rollerskier",
    }]
    assert parse_plan_reaction_lines(
        "older_adult::skin-tone-4 experienced rollerskier"
    ) == expected
    assert parse_plan_reaction_lines(
        ":older_adult::skin-tone-4: experienced rollerskier"
    ) == expected
    assert format_plan_reaction_lines(expected) == (
        ":older_adult::skin-tone-4: experienced rollerskier"
    )
    assert plan_reaction_names(expected) == ["older_adult::skin-tone-4"]


def test_different_skin_tones_on_one_base_remain_distinct_names():
    reactions = normalize_plan_reactions([
        {"emoji": "older_adult::skin-tone-3", "label": "Group three"},
        {"emoji": "older_adult::skin-tone-4", "label": "Group four"},
    ])
    assert plan_reaction_names(reactions) == [
        "older_adult::skin-tone-3",
        "older_adult::skin-tone-4",
    ]


@pytest.mark.parametrize(
    "emoji",
    [
        "older_adult::skin-tone-1",
        "older_adult::skin-tone-7",
        "older_adult::skin-tone-4::skin-tone-5",
        "older_adult:skin-tone-4",
        "::skin-tone-4",
        "older_adult::skin_tone_4",
    ],
)
def test_malformed_skin_tone_names_are_rejected(emoji):
    with pytest.raises(PlanReactionValidationError, match="Slack emoji shortcode"):
        normalize_plan_reactions([{"emoji": emoji, "label": "Choice"}])


def test_modifier_cannot_bypass_reserved_attendance_base():
    with pytest.raises(PlanReactionValidationError, match="reserved"):
        normalize_plan_reactions([{
            "emoji": "white_check_mark::skin-tone-4",
            "label": "Not allowed",
        }])


def test_normalized_reaction_name_length_boundary():
    suffix = "::skin-tone-4"
    allowed = "x" * (MAX_PLAN_REACTION_NAME - len(suffix)) + suffix
    assert normalize_plan_reactions([{
        "emoji": allowed,
        "label": "Allowed",
    }])[0]["emoji"] == allowed
    with pytest.raises(PlanReactionValidationError, match="80 characters"):
        normalize_plan_reactions([{
            "emoji": "x" * (MAX_PLAN_REACTION_NAME - len(suffix) + 1) + suffix,
            "label": "Too long",
        }])


@pytest.mark.parametrize(
    ("reactions", "expected"),
    [
        ([], ""),
        (
            [{"emoji": "hatching_chick", "label": "new rollerskier"}],
            "In addition to your attendance emoji, hit a :hatching_chick: "
            "for new rollerskier.",
        ),
        (
            [
                {"emoji": "hatching_chick", "label": "new rollerskier"},
                {"emoji": "athletic_shoe", "label": "runner"},
            ],
            "In addition to your attendance emoji, hit a :hatching_chick: "
            "for new rollerskier and a :athletic_shoe: for runner.",
        ),
        (
            [
                {"emoji": "hatching_chick", "label": "new rollerskier"},
                {
                    "emoji": "older_adult::skin-tone-4",
                    "label": "experienced rollerskier",
                },
                {"emoji": "athletic_shoe", "label": "runner"},
            ],
            "In addition to your attendance emoji, hit a :hatching_chick: "
            "for new rollerskier, a :older_adult::skin-tone-4: for experienced "
            "rollerskier, and a :athletic_shoe: for runner.",
        ),
        (
            [
                {"emoji": "hatching_chick", "label": "new rollerskier"},
                {"emoji": "older_adult", "label": "experienced rollerskier"},
                {"emoji": "athletic_shoe", "label": "runner"},
                {"emoji": "evergreen_tree", "label": "endurance"},
            ],
            "In addition to your attendance emoji, hit a :hatching_chick: "
            "for new rollerskier, a :older_adult: for experienced rollerskier, "
            "a :athletic_shoe: for runner, and a :evergreen_tree: for endurance.",
        ),
    ],
)
def test_supplemental_instruction_has_exact_zero_to_four_choice_grammar(
    reactions, expected
):
    assert format_supplemental_reaction_sentence(reactions) == expected


def test_supplemental_fallback_uses_plain_names_and_semicolon_grammar():
    reactions = [
        {"emoji": "hatching_chick", "label": "new rollerskier"},
        {
            "emoji": "older_adult::skin-tone-4",
            "label": "experienced rollerskier",
        },
        {"emoji": "athletic_shoe", "label": "runner"},
    ]
    assert format_reaction_name_for_fallback(
        "older_adult::skin-tone-4"
    ) == "older adult, skin tone 4"
    assert format_reaction_name_for_fallback("six") == "six"
    assert format_supplemental_reaction_fallback(reactions) == (
        "Additional reactions: hatching chick for new rollerskier; "
        "older adult, skin tone 4 for experienced rollerskier; "
        "athletic shoe for runner."
    )
    assert format_supplemental_reaction_fallback(reactions[:1]) == (
        "Additional reaction: hatching chick for new rollerskier."
    )


def test_display_labels_normalize_punctuation_without_mutating_saved_values():
    reactions = [
        {"emoji": "hatching_chick", "label": "New <skier>?!  "},
        {"emoji": "athletic_shoe", "label": "Runner."},
    ]
    original = deepcopy(reactions)
    assert format_supplemental_reaction_sentence(reactions) == (
        "In addition to your attendance emoji, hit a :hatching_chick: "
        "for New &lt;skier&gt; and a :athletic_shoe: for Runner."
    )
    assert format_supplemental_reaction_fallback(reactions) == (
        "Additional reactions: hatching chick for New <skier>; "
        "athletic shoe for Runner."
    )
    assert reactions == original


@pytest.mark.parametrize("label", [".", "?!", "...   "])
def test_punctuation_only_label_is_rejected(label):
    with pytest.raises(PlanReactionValidationError, match="label is required"):
        normalize_plan_reactions([{"emoji": "snowflake", "label": label}])
