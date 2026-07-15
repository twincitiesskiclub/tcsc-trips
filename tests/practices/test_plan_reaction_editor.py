import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.practices.plan_reaction_editor import (
    PLAN_REACTION_EDITOR_VERSION,
    PlanReactionEditorState,
    SuppressedPlanReaction,
    active_plan_reaction_snapshot,
    add_catalog_plan_reaction,
    build_plan_reaction_editor_state,
    deserialize_plan_reaction_editor_state,
    reconcile_plan_reaction_editor_state,
    remove_plan_reaction,
    reserved_plan_reaction_slots,
    restore_plan_reaction_defaults,
    serialize_plan_reaction_editor_state,
    undo_plan_reaction,
)
from app.practices.plan_reactions import (
    EVERGREEN_PLAN_REACTION,
    PlanReactionCatalogOption,
    PlanReactionValidationError,
)


RUN_PLAN_REACTION = {"emoji": "athletic_shoe", "label": "runner"}
NEW_ROLLERSKIER_PLAN_REACTION = {
    "emoji": "hatching_chick",
    "label": "new rollerskier",
}
EXPERIENCED_ROLLERSKIER_PLAN_REACTION = {
    "emoji": "older_adult::skin-tone-4",
    "label": "experienced rollerskier",
}
FOUR_APPROVED_ROWS = [
    EVERGREEN_PLAN_REACTION,
    NEW_ROLLERSKIER_PLAN_REACTION,
    EXPERIENCED_ROLLERSKIER_PLAN_REACTION,
    RUN_PLAN_REACTION,
]


def source(source_id, name, options):
    return SimpleNamespace(
        id=source_id,
        name=name,
        default_plan_reactions=options,
    )


@pytest.fixture
def sources():
    return SimpleNamespace(
        intervals=source(10, "Intervals", [EVERGREEN_PLAN_REACTION]),
        run=source(1, "Run", [RUN_PLAN_REACTION]),
        trail_run=source(4, "Trail Run", [RUN_PLAN_REACTION]),
        rollerski=source(
            2,
            "Rollerski",
            [
                NEW_ROLLERSKIER_PLAN_REACTION,
                EXPERIENCED_ROLLERSKIER_PLAN_REACTION,
            ],
        ),
        strength=source(3, "Strength", []),
        conflicting_type=source(
            11,
            "Conflicting",
            [{"emoji": "athletic_shoe", "label": "type runner"}],
        ),
        overflow_type=source(
            12,
            "Overflow",
            [
                {"emoji": "snowflake", "label": "snow"},
                {"emoji": "zap", "label": "speed"},
                {"emoji": "turtle", "label": "easy"},
            ],
        ),
    )


def test_create_starts_from_current_effective_defaults(sources):
    result = build_plan_reaction_editor_state(
        practice_types=[sources.intervals],
        activities=[sources.run, sources.rollerski],
        saved_snapshot=None,
    )

    assert result.blocking_error is None
    assert active_plan_reaction_snapshot(result.state) == FOUR_APPROVED_ROWS
    assert all(row.inherited_source_keys for row in result.state.rows)
    assert result.state.last_valid_type_ids == (sources.intervals.id,)
    assert result.state.last_valid_activity_ids == (
        sources.run.id,
        sources.rollerski.id,
    )


def test_existing_empty_snapshot_suppresses_current_defaults(sources):
    result = build_plan_reaction_editor_state(
        practice_types=[sources.intervals],
        activities=[sources.run, sources.rollerski],
        saved_snapshot=[],
    )

    assert result.state.rows == []
    assert {item.emoji for item in result.state.suppressed} == {
        "evergreen_tree",
        "athletic_shoe",
        "hatching_chick",
        "older_adult::skin-tone-4",
    }


def test_edit_reconstructs_inherited_custom_label_and_protected_snapshot(sources):
    saved = [
        {"emoji": "athletic_shoe", "label": "trail runner"},
        {"emoji": "wheel", "label": "classic rollerski"},
    ]
    result = build_plan_reaction_editor_state(
        practice_types=[],
        activities=[sources.run, sources.rollerski],
        saved_snapshot=saved,
    )

    shoe, wheel = result.state.rows
    assert shoe.label == "trail runner"
    assert shoe.inherited_source_keys == (f"activity:{sources.run.id}",)
    assert shoe.protected_order is None
    assert wheel.protected_order == 1


def test_one_two_three_one_transition_preserves_only_surviving_origins(sources):
    initial = build_plan_reaction_editor_state(
        practice_types=[sources.intervals],
        activities=[sources.run],
        saved_snapshot=None,
    ).state
    two = reconcile_plan_reaction_editor_state(
        initial,
        practice_types=[sources.intervals],
        activities=[sources.run, sources.rollerski],
    ).state
    shoe = next(row for row in two.rows if row.emoji == "athletic_shoe")
    shoe.label = "Run or walk"
    three = reconcile_plan_reaction_editor_state(
        two,
        practice_types=[sources.intervals],
        activities=[sources.run, sources.rollerski, sources.strength],
    ).state
    one = reconcile_plan_reaction_editor_state(
        three,
        practice_types=[sources.intervals],
        activities=[sources.run],
    ).state

    assert active_plan_reaction_snapshot(one) == [EVERGREEN_PLAN_REACTION]
    assert one.unconfigured_activity_names == ()


def test_catalog_and_protected_origins_survive_inherited_source_disappearance(
    sources,
):
    state = build_plan_reaction_editor_state(
        practice_types=[],
        activities=[sources.run],
        saved_snapshot=[{"emoji": "athletic_shoe", "label": "saved runner"}],
    ).state
    option = PlanReactionCatalogOption(
        option_id="shoe",
        emoji="athletic_shoe",
        label="runner",
        source_keys=(f"activity:{sources.run.id}",),
    )
    state = add_catalog_plan_reaction(state, option)
    inherited = reconcile_plan_reaction_editor_state(
        state,
        practice_types=[],
        activities=[sources.run, sources.rollerski],
    ).state
    returned = reconcile_plan_reaction_editor_state(
        inherited,
        practice_types=[],
        activities=[sources.run],
    ).state

    assert len(returned.rows) == 1
    assert returned.rows[0].label == "saved runner"
    assert returned.rows[0].protected_order == 0
    assert returned.rows[0].catalog_order == 0
    assert returned.rows[0].inherited_source_keys == ()


def test_adding_a_suppressed_catalog_option_clears_its_tombstone(sources):
    state = build_plan_reaction_editor_state(
        practice_types=[],
        activities=[sources.run, sources.rollerski],
        saved_snapshot=[],
    ).state
    option = PlanReactionCatalogOption(
        option_id="shoe",
        emoji="athletic_shoe",
        label="runner",
        source_keys=(f"activity:{sources.run.id}",),
    )

    added = add_catalog_plan_reaction(state, option)
    reconciled = reconcile_plan_reaction_editor_state(
        added,
        practice_types=[],
        activities=[sources.run, sources.rollerski],
    ).state

    assert "athletic_shoe" not in {item.emoji for item in added.suppressed}
    shoe = next(row for row in reconciled.rows if row.emoji == "athletic_shoe")
    assert shoe.catalog_order == 0
    assert shoe.inherited_source_keys == (f"activity:{sources.run.id}",)


def test_adding_a_suppressed_applicable_default_recovers_inherited_origin_now(
    sources,
):
    state = build_plan_reaction_editor_state(
        practice_types=[sources.intervals],
        activities=[sources.run, sources.strength],
        saved_snapshot=[RUN_PLAN_REACTION],
    ).state
    option = PlanReactionCatalogOption(
        option_id="tree",
        emoji=EVERGREEN_PLAN_REACTION["emoji"],
        label=EVERGREEN_PLAN_REACTION["label"],
        source_keys=(f"type:{sources.intervals.id}",),
    )

    added = add_catalog_plan_reaction(state, option)

    tree = next(row for row in added.rows if row.emoji == "evergreen_tree")
    assert tree.inherited_source_keys == (f"type:{sources.intervals.id}",)
    assert tree.inherited_order == 0
    assert tree.catalog_order == 0
    assert not added.suppressed
    assert active_plan_reaction_snapshot(added) == [
        EVERGREEN_PLAN_REACTION,
        RUN_PLAN_REACTION,
    ]


def test_suppression_clears_only_after_all_original_sources_disappear(sources):
    state = build_plan_reaction_editor_state(
        practice_types=[],
        activities=[sources.run, sources.rollerski],
        saved_snapshot=[],
    ).state
    still_suppressed = reconcile_plan_reaction_editor_state(
        state,
        practice_types=[],
        activities=[sources.run, sources.strength],
    ).state
    assert "athletic_shoe" in {
        item.emoji for item in still_suppressed.suppressed
    }

    absent = reconcile_plan_reaction_editor_state(
        still_suppressed,
        practice_types=[],
        activities=[sources.rollerski],
    ).state
    assert "athletic_shoe" not in {item.emoji for item in absent.suppressed}

    returned = reconcile_plan_reaction_editor_state(
        absent,
        practice_types=[],
        activities=[sources.run, sources.strength],
    ).state
    assert "athletic_shoe" in {row.emoji for row in returned.rows}


def test_partial_source_disappearance_keeps_serializable_original_suppression(
    sources,
):
    state = build_plan_reaction_editor_state(
        practice_types=[],
        activities=[sources.run, sources.trail_run],
        saved_snapshot=[],
    ).state
    partial = reconcile_plan_reaction_editor_state(
        state,
        practice_types=[],
        activities=[sources.run, sources.strength],
    ).state

    assert partial.suppressed == [
        SuppressedPlanReaction(
            "athletic_shoe",
            (
                f"activity:{sources.run.id}",
                f"activity:{sources.trail_run.id}",
            ),
        )
    ]
    assert deserialize_plan_reaction_editor_state(
        serialize_plan_reaction_editor_state(partial)
    ) == partial


def test_suppression_expires_when_emoji_mapping_disappears_from_same_source(
    sources,
):
    snow = {"emoji": "snowflake", "label": "snow"}
    speed = {"emoji": "zap", "label": "speed"}
    configurable = source(5, "Configurable", [snow, speed])
    state = build_plan_reaction_editor_state(
        practice_types=[],
        activities=[configurable, sources.strength],
        saved_snapshot=[speed],
    ).state

    configurable.default_plan_reactions = [speed]
    mapping_absent = reconcile_plan_reaction_editor_state(
        state,
        practice_types=[],
        activities=[configurable, sources.strength],
    ).state

    assert "snowflake" not in {
        item.emoji for item in mapping_absent.suppressed
    }

    configurable.default_plan_reactions = [snow, speed]
    mapping_returned = reconcile_plan_reaction_editor_state(
        mapping_absent,
        practice_types=[],
        activities=[configurable, sources.strength],
    ).state
    assert "snowflake" in {row.emoji for row in mapping_returned.rows}


def test_remove_and_undo_preserve_description_emoji_row_id_and_slot(sources):
    state = build_plan_reaction_editor_state(
        practice_types=[],
        activities=[sources.run, sources.rollerski],
        saved_snapshot=None,
    ).state
    row = state.rows[0]
    row.label = "edited description"

    removed = remove_plan_reaction(state, row.row_id)
    assert removed.rows[0].removed is True
    assert removed.rows[0].emoji == row.emoji
    assert removed.rows[0].label == "edited description"
    assert reserved_plan_reaction_slots(removed) == len(removed.rows)
    assert state.rows[0].removed is False

    restored = undo_plan_reaction(removed, row.row_id)
    assert restored.rows[0].removed is False
    assert restored.rows[0].row_id == row.row_id


def test_removed_inherited_only_row_disappears_with_source_and_returns_fresh(
    sources,
):
    state = build_plan_reaction_editor_state(
        practice_types=[],
        activities=[sources.run, sources.rollerski],
        saved_snapshot=None,
    ).state
    shoe = next(row for row in state.rows if row.emoji == "athletic_shoe")
    shoe.label = "stale edit"
    state = remove_plan_reaction(state, shoe.row_id)
    state = reconcile_plan_reaction_editor_state(
        state,
        practice_types=[],
        activities=[sources.rollerski],
    ).state
    assert "athletic_shoe" not in {row.emoji for row in state.rows}

    state = reconcile_plan_reaction_editor_state(
        state,
        practice_types=[],
        activities=[sources.run, sources.strength],
    ).state
    fresh = next(row for row in state.rows if row.emoji == "athletic_shoe")
    assert fresh.label == "runner"
    assert fresh.removed is False


def test_four_removed_rows_still_block_a_fifth_catalog_option(sources):
    state = build_plan_reaction_editor_state(
        practice_types=[sources.intervals],
        activities=[sources.run, sources.rollerski],
        saved_snapshot=None,
    ).state
    for row in list(state.rows):
        state = remove_plan_reaction(state, row.row_id)

    with pytest.raises(PlanReactionValidationError, match="at most 4"):
        add_catalog_plan_reaction(
            state,
            PlanReactionCatalogOption(
                option_id="fifth",
                emoji="bike",
                label="bike",
                source_keys=("activity:9",),
            ),
        )


def test_unknown_remove_and_undo_targets_are_rejected(sources):
    state = build_plan_reaction_editor_state(
        practice_types=[sources.intervals],
        activities=[],
        saved_snapshot=None,
    ).state

    with pytest.raises(PlanReactionValidationError, match="Unknown reaction row"):
        remove_plan_reaction(state, "missing")
    with pytest.raises(
        PlanReactionValidationError,
        match="Unknown removed reaction row",
    ):
        undo_plan_reaction(state, state.rows[0].row_id)


def test_invalid_reconciliation_preserves_last_valid_rows_and_blocks_state(sources):
    state = build_plan_reaction_editor_state(
        practice_types=[],
        activities=[sources.run, sources.rollerski],
        saved_snapshot=None,
    ).state
    state.add_open = True
    before = serialize_plan_reaction_editor_state(state)

    result = reconcile_plan_reaction_editor_state(
        state,
        practice_types=[sources.conflicting_type],
        activities=[sources.run, sources.rollerski],
    )

    assert result.blocking_error and "conflicting labels" in result.blocking_error
    assert serialize_plan_reaction_editor_state(result.state)["rows"] == before["rows"]
    assert result.state.blocking_error == result.blocking_error
    assert result.state.add_open is False
    assert state.blocking_error is None
    assert state.add_open is True


def test_initial_invalid_edit_keeps_saved_snapshot_as_last_valid_state(sources):
    saved = [{"emoji": "wheel", "label": "saved protected row"}]

    result = build_plan_reaction_editor_state(
        practice_types=[sources.conflicting_type],
        activities=[sources.run, sources.rollerski],
        saved_snapshot=saved,
    )

    assert result.blocking_error
    assert [(row.emoji, row.label) for row in result.state.rows] == [
        ("wheel", "saved protected row")
    ]
    assert result.state.rows[0].protected_order == 0
    assert result.resolution is None


def test_initial_overflow_edit_keeps_saved_snapshot_as_last_valid_state(sources):
    saved = [{"emoji": "wheel", "label": "saved protected row"}]

    result = build_plan_reaction_editor_state(
        practice_types=[sources.overflow_type],
        activities=[sources.run, sources.rollerski],
        saved_snapshot=saved,
    )

    assert result.blocking_error and "more than 4" in result.blocking_error
    assert [(row.emoji, row.label) for row in result.state.rows] == [
        ("wheel", "saved protected row")
    ]


def test_restore_is_atomic_and_clears_all_practice_specific_working_state(sources):
    original = build_plan_reaction_editor_state(
        practice_types=[],
        activities=[sources.run, sources.rollerski],
        saved_snapshot=[{"emoji": "wheel", "label": "protected"}],
    ).state
    original = remove_plan_reaction(original, original.rows[0].row_id)

    restored = restore_plan_reaction_defaults(
        original,
        practice_types=[sources.intervals],
        activities=[sources.run, sources.rollerski],
    )

    assert restored.blocking_error is None
    assert active_plan_reaction_snapshot(restored.state) == FOUR_APPROVED_ROWS
    assert not restored.state.suppressed
    assert all(row.protected_order is None for row in restored.state.rows)
    assert all(row.catalog_order is None for row in restored.state.rows)
    assert restored.state.next_row_number >= original.next_row_number


def test_restore_allocates_fresh_row_ids_that_stale_values_cannot_target(sources):
    original = build_plan_reaction_editor_state(
        practice_types=[sources.intervals],
        activities=[sources.run, sources.rollerski],
        saved_snapshot=None,
    ).state
    old_row_ids = {row.row_id for row in original.rows}
    stale_view_values = {
        f"practice_reaction_row_{row.row_id}": f"stale {row.emoji}"
        for row in original.rows
    }

    restored = restore_plan_reaction_defaults(
        original,
        practice_types=[sources.intervals],
        activities=[sources.run, sources.rollerski],
    ).state

    restored_row_ids = {row.row_id for row in restored.rows}
    assert old_row_ids.isdisjoint(restored_row_ids)
    assert all(
        f"practice_reaction_row_{row.row_id}" not in stale_view_values
        for row in restored.rows
    )
    assert restored.next_row_number == (
        original.next_row_number + len(restored.rows)
    )


def test_failed_restore_keeps_original_working_state_atomically(sources):
    original = build_plan_reaction_editor_state(
        practice_types=[],
        activities=[sources.run, sources.rollerski],
        saved_snapshot=[],
    ).state
    original.add_open = True
    before = serialize_plan_reaction_editor_state(original)

    result = restore_plan_reaction_defaults(
        original,
        practice_types=[sources.conflicting_type],
        activities=[sources.run, sources.rollerski],
    )

    after = serialize_plan_reaction_editor_state(result.state)
    assert result.blocking_error and "conflicting labels" in result.blocking_error
    assert after["rows"] == before["rows"]
    assert after["suppressed"] == before["suppressed"]
    assert after["last_valid_type_ids"] == before["last_valid_type_ids"]
    assert after["last_valid_activity_ids"] == before["last_valid_activity_ids"]
    assert result.state.add_open is False
    assert original.add_open is True


def test_temporary_blank_labels_survive_actions_but_not_active_snapshot(sources):
    state = build_plan_reaction_editor_state(
        practice_types=[sources.intervals],
        activities=[],
        saved_snapshot=None,
    ).state
    state.rows[0].label = ""

    removed = remove_plan_reaction(state, state.rows[0].row_id)
    round_tripped = deserialize_plan_reaction_editor_state(
        serialize_plan_reaction_editor_state(removed)
    )
    restored = undo_plan_reaction(round_tripped, state.rows[0].row_id)

    assert restored.rows[0].label == ""
    with pytest.raises(PlanReactionValidationError, match="label is required"):
        active_plan_reaction_snapshot(restored)


def test_metadata_round_trip_preserves_removed_labels_and_rejects_unknown_version(
    sources,
):
    state = build_plan_reaction_editor_state(
        practice_types=[sources.intervals],
        activities=[sources.run],
        saved_snapshot=None,
    ).state
    state.rows[0].label = ""
    state = remove_plan_reaction(state, state.rows[0].row_id)

    payload = serialize_plan_reaction_editor_state(
        state,
        omit_active_labels=True,
    )

    assert deserialize_plan_reaction_editor_state(payload) == state
    with pytest.raises(PlanReactionValidationError, match="editor metadata"):
        deserialize_plan_reaction_editor_state({"version": 99, "rows": []})


def test_serialization_uses_complete_json_primitive_schema_and_omits_only_active_labels(
    sources,
):
    state = build_plan_reaction_editor_state(
        practice_types=[sources.intervals],
        activities=[sources.run, sources.rollerski],
        saved_snapshot=None,
    ).state
    state = remove_plan_reaction(state, state.rows[0].row_id)
    payload = serialize_plan_reaction_editor_state(state, omit_active_labels=True)

    assert set(payload) == {
        "version",
        "rows",
        "suppressed",
        "last_valid_type_ids",
        "last_valid_activity_ids",
        "next_row_number",
        "blocking_error",
        "unconfigured_activity_names",
        "effective_inherited_count",
        "add_open",
    }
    assert set(payload["rows"][0]) == {
        "row_id",
        "emoji",
        "label",
        "removed",
        "inherited_source_keys",
        "inherited_order",
        "protected_order",
        "catalog_order",
    }
    assert payload["rows"][0]["label"] == state.rows[0].label
    assert all(
        row_payload["label"] is None
        for row_payload in payload["rows"]
        if not row_payload["removed"]
    )
    assert json.loads(json.dumps(payload)) == payload


def test_metadata_rejects_noncanonical_row_sequence(sources):
    state = build_plan_reaction_editor_state(
        practice_types=[sources.intervals],
        activities=[sources.run, sources.rollerski],
        saved_snapshot=None,
    ).state
    payload = serialize_plan_reaction_editor_state(state)
    payload["rows"].reverse()

    with pytest.raises(
        PlanReactionValidationError,
        match="^Invalid reaction editor metadata$",
    ):
        deserialize_plan_reaction_editor_state(payload)


def test_metadata_rejects_origin_values_that_break_canonical_sequence(sources):
    state = build_plan_reaction_editor_state(
        practice_types=[sources.intervals],
        activities=[sources.run, sources.rollerski],
        saved_snapshot=None,
    ).state
    payload = serialize_plan_reaction_editor_state(state)
    first_order = payload["rows"][0]["inherited_order"]
    payload["rows"][0]["inherited_order"] = payload["rows"][1][
        "inherited_order"
    ]
    payload["rows"][1]["inherited_order"] = first_order

    with pytest.raises(
        PlanReactionValidationError,
        match="^Invalid reaction editor metadata$",
    ):
        deserialize_plan_reaction_editor_state(payload)


def test_metadata_rejects_inherited_order_outside_effective_count(sources):
    state = build_plan_reaction_editor_state(
        practice_types=[sources.intervals],
        activities=[],
        saved_snapshot=None,
    ).state
    payload = serialize_plan_reaction_editor_state(state)
    payload["rows"][0]["inherited_order"] = 1

    with pytest.raises(
        PlanReactionValidationError,
        match="^Invalid reaction editor metadata$",
    ):
        deserialize_plan_reaction_editor_state(payload)


def test_metadata_rejects_unrepresented_effective_inherited_count(sources):
    state = build_plan_reaction_editor_state(
        practice_types=[sources.intervals],
        activities=[],
        saved_snapshot=None,
    ).state
    payload = serialize_plan_reaction_editor_state(state)
    payload["effective_inherited_count"] = 2

    with pytest.raises(
        PlanReactionValidationError,
        match="^Invalid reaction editor metadata$",
    ):
        deserialize_plan_reaction_editor_state(payload)


def _empty_metadata(**changes):
    payload = {
        "version": PLAN_REACTION_EDITOR_VERSION,
        "rows": [],
        "suppressed": [],
        "last_valid_type_ids": [],
        "last_valid_activity_ids": [],
        "next_row_number": 0,
        "blocking_error": None,
        "unconfigured_activity_names": [],
        "effective_inherited_count": 0,
        "add_open": False,
    }
    payload.update(changes)
    return payload


def _metadata_row(
    number,
    emoji,
    *,
    label="label",
    removed=False,
    inherited_source_keys=None,
    inherited_order=None,
    protected_order=None,
    catalog_order=None,
):
    return {
        "row_id": f"r{number}",
        "emoji": emoji,
        "label": label,
        "removed": removed,
        "inherited_source_keys": list(inherited_source_keys or []),
        "inherited_order": inherited_order,
        "protected_order": protected_order,
        "catalog_order": number if catalog_order is None else catalog_order,
    }


@pytest.mark.parametrize(
    "payload",
    [
        _empty_metadata(
            suppressed=[
                {"emoji": "snowflake", "source_keys": ["activity:99"]}
            ],
            last_valid_activity_ids=[1, 2],
            effective_inherited_count=1,
        ),
        _empty_metadata(
            suppressed=[
                {"emoji": "snowflake", "source_keys": ["activity:1"]}
            ],
            last_valid_activity_ids=[1],
            effective_inherited_count=1,
        ),
    ],
    ids=["orphan-source", "preemptive-single-activity"],
)
def test_metadata_rejects_orphan_or_preemptive_suppression(payload):
    with pytest.raises(
        PlanReactionValidationError,
        match="^Invalid reaction editor metadata$",
    ):
        deserialize_plan_reaction_editor_state(payload)


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {"version": PLAN_REACTION_EDITOR_VERSION},
        _empty_metadata(extra="hostile"),
        _empty_metadata(version=99),
        _empty_metadata(rows="not rows"),
        _empty_metadata(rows=["not a row"]),
        _empty_metadata(
            rows=[
                _metadata_row(0, "snowflake"),
                _metadata_row(0, "zap", catalog_order=1),
            ],
            next_row_number=2,
        ),
        _empty_metadata(
            rows=[
                _metadata_row(0, "snowflake"),
                _metadata_row(1, "snowflake"),
            ],
            next_row_number=2,
        ),
        _empty_metadata(
            rows=[_metadata_row(index, f"choice_{index}") for index in range(5)],
            next_row_number=5,
        ),
        _empty_metadata(
            rows=[_metadata_row(0, "snowflake", catalog_order=-1)],
            next_row_number=1,
        ),
        _empty_metadata(
            rows=[
                _metadata_row(
                    0,
                    "snowflake",
                    inherited_source_keys=["bogus:1"],
                    inherited_order=0,
                    catalog_order=None,
                )
            ],
            next_row_number=1,
        ),
        _empty_metadata(effective_inherited_count=-1),
        _empty_metadata(next_row_number=-1),
        _empty_metadata(last_valid_activity_ids=[True]),
        _empty_metadata(
            rows=[_metadata_row(0, "snowflake", label=None, removed=True)],
            next_row_number=1,
        ),
        _empty_metadata(
            suppressed=[{"emoji": "snowflake", "source_keys": ["bad"]}],
        ),
    ],
    ids=[
        "none",
        "sequence-not-mapping",
        "missing-fields",
        "unknown-field",
        "unknown-version",
        "rows-not-list",
        "row-not-mapping",
        "duplicate-row-id",
        "duplicate-emoji",
        "more-than-four-rows",
        "negative-origin-order",
        "malformed-source-key",
        "negative-inherited-count",
        "negative-next-row-number",
        "boolean-source-id",
        "removed-label-omitted",
        "malformed-suppressed-source-key",
    ],
)
def test_hostile_metadata_is_rejected_with_adapter_safe_error(payload):
    with pytest.raises(
        PlanReactionValidationError,
        match="^Invalid reaction editor metadata$",
    ):
        deserialize_plan_reaction_editor_state(deepcopy(payload))


def test_deserialize_rehydrates_an_omitted_active_label_as_temporary_blank():
    payload = _empty_metadata(
        rows=[_metadata_row(0, "snowflake", label=None)],
        next_row_number=1,
    )

    state = deserialize_plan_reaction_editor_state(payload)

    assert isinstance(state, PlanReactionEditorState)
    assert state.rows[0].label == ""
    with pytest.raises(PlanReactionValidationError, match="label is required"):
        active_plan_reaction_snapshot(state)


def test_suppressed_dataclass_round_trips_as_source_key_tuple():
    state = PlanReactionEditorState(
        suppressed=[
            SuppressedPlanReaction(
                emoji="snowflake",
                source_keys=("type:10", "activity:2"),
            )
        ],
        last_valid_type_ids=(10,),
        last_valid_activity_ids=(2,),
        effective_inherited_count=1,
    )

    decoded = deserialize_plan_reaction_editor_state(
        serialize_plan_reaction_editor_state(state)
    )

    assert decoded == state
    assert decoded.suppressed[0].source_keys == ("type:10", "activity:2")
