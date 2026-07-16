# Structured Practice Reaction Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace freeform practice-reaction authoring with a fixed-emoji structured editor across Slack and Admin, derive Activity defaults only for Multisport practices, and safely seed the historically approved Settings defaults.

**Architecture:** The Python domain layer remains authoritative for source loading, default resolution, catalog authorization, and ephemeral reaction-editor state. Slack renders that state as Block Kit and serializes only bounded working metadata; Admin mirrors the same state transitions in a small tested vanilla-JavaScript module while every submission is revalidated by Python. A committed evidence manifest feeds a dry-run-first, digest-approved seed command that never scrapes Slack or rewrites saved practice snapshots.

**Tech Stack:** Python 3.13, Flask, Flask-SQLAlchemy/SQLAlchemy, Slack Bolt and Block Kit, Jinja, vanilla JavaScript, Node 26, jsdom 29.1.1, pytest, and Node's built-in test runner.

## Global Constraints

- Preserve the existing JSON schema: ordered `{"emoji": "...", "label": "..."}` pairs in `PracticeType.default_plan_reactions`, `PracticeActivity.default_plan_reactions`, and `Practice.plan_reactions`; add no table or column.
- Two or more distinct valid Activities means Multisport. Unknown IDs are rejected and duplicates count once. Activity defaults are ignored at zero or one Activity and apply from every selected Activity at two or more; Workout Type defaults always apply.
- Do not add a Multisport Workout Type, flag, name heuristic, live Slack emoji picker, arbitrary practice-level shortcode entry, or member-choice persistence.
- Settings remains the only surface where emoji keys can be created or changed. Its existing editable-key, reorder, Remove, autosave, and neutral incomplete-row contract remain intact, including exact copy `Complete both fields to save.`
- Practice rows use a fixed emoji, one editable single-line description of at most 80 characters, Remove, and a dimmed text-labelled Removed state with Undo. There is no practice-level reordering.
- Removed rows preserve their latest description, emoji, and slot until submission. The four-slot limit counts the deduplicated union of active and removed inherited, protected-snapshot, and catalog rows.
- Use exact coach-facing labels `Add reaction` and `Restore defaults`; never display `one-off reaction`.
- Add is available only when effective inherited defaults are empty or a selected Multisport Activity is unconfigured, and only while fewer than four slots are reserved. Add choices come only from valid Settings pairs; used active/removed emoji keys are unavailable.
- Full Edit/Admin Edit accepts current Settings emoji keys plus keys in the saved snapshot. Create accepts current Settings keys only. A Settings key deleted while an editor is open must preserve entered text but block a newly introduced row until removed or replaced.
- Selector reconciliation changes only reaction state. Preserve unrelated form/modal values, customized descriptions, catalog origins, protected snapshot rows, suppression, Remove/Undo state, and canonical ordering exactly as specified in the approved design.
- A conflict or overflow keeps the selected selector value visible, preserves the last-valid reaction state, blocks Add and submission, and names the relevant source problem. Restore resolves first and changes nothing on failure.
- Slack selector Input blocks set `dispatch_action: true`; every action acknowledges before work and updates with the current view ID and hash. Action values are opaque row/option IDs, never raw emoji or labels.
- Slack private metadata is compact, versioned, validated, and at most 3,000 characters. Preview metadata contains a mode marker and synthetic sources but no practice/database target.
- Slack catalog pickers render at most 100 complete options; more is an explicit configuration error. Visible option text is at most 75 characters and may be ellipsized, while the complete validated label remains canonical.
- `/tcsc practice-preview` remains test-channel-only in `C07G9RTMRT3`, has no role lookup, derives four default rows from one interval Type plus Run and Rollerski Activities, and remains submission-ack-only with zero database, Slack-message, reaction, summary, or harness mutation.
- The historical runtime operation consumes a committed manifest and never queries Slack. It targets interval Types by `has_intervals` and the six exact approved Activity names, fills only empty values, treats exact values as no-ops, aborts atomically on different non-empty values or target drift, locks and rechecks before write, and never rewrites `Practice.plan_reactions`.
- Production insertion requires a fresh dry-run digest and explicit human approval immediately before `--commit --approve <digest>`; implementation must not commit the production seed without that approval.
- Preserve the announcement grammar, attendance/session reactions, accessibility fallback generation, saved-snapshot semantics, and every unrelated Slack/Admin workflow.
- Use TDD for every behavior change: write a focused failing test, confirm the expected failure, make the minimal implementation pass, then run adjacent regressions before committing.
- Do not touch the untracked `env` symlink, unrelated package-lock content, retained validation-harness state, or post anything to `#announcements-practices`.

---

## File Map

- Modify `app/practices/plan_reactions.py`: rich Multisport resolution, provenance, global Settings catalog, and submitted-key authorization.
- Create `app/practices/plan_reaction_queries.py`: strict distinct Activity/Type ID coercion and database loading.
- Create `app/practices/plan_reaction_editor.py`: Python working-state reconstruction, reconciliation, Remove/Undo/Add/Restore, snapshots, and serialization.
- Modify `app/routes/admin_practices.py`: strict source loading and authoritative reaction authorization for Admin Create/Edit/Restore.
- Create `app/static/practice_plan_reactions.js`: dependency-free Admin working-state model mirroring the Python rules.
- Create `app/static/practice_plan_reaction_editor.js`: practice-only fixed-key DOM controller; keep `app/static/plan_reactions.js` Settings-only.
- Modify `app/templates/admin/practices/detail.html`: accessible structured editor markup, fixed-key row styling, and mobile behavior.
- Modify `app/templates/admin/practices/_detail_script.js`: initialize/reconcile/submit the new practice editor without touching unrelated inputs.
- Modify `app/templates/admin/practices/config.html`: Activity helper copy only; retain Settings behavior.
- Modify `package.json` and `package-lock.json`: add the focused Node/jsdom test command and exact dev dependency.
- Create `app/slack/practice_reaction_editor.py`: Block Kit row rendering, catalog bounds, metadata codec, current-value preservation, and structured submission parsing.
- Modify `app/slack/modals.py`: structured rows and versioned metadata for Create, Preview, and Full Edit.
- Modify `app/slack/bolt_app.py`: strict Create/Edit submission handling and interactive selector/Remove/Undo/Add/Restore actions.
- Create `scripts/data/2026-07-15-practice-plan-reaction-history.json`: reviewed Slack-history evidence and approved insertion targets.
- Create `scripts/seed_practice_plan_reaction_defaults.py`: standalone dry-run/digest/lock/recheck/read-back operation.
- Modify/create focused tests under `tests/practices`, `tests/routes`, `tests/slack`, `tests/js`, and `tests/scripts`.

### Task 1: Make Default Resolution and Source Loading Authoritative

**Files:**

- Modify: `app/practices/plan_reactions.py`
- Create: `app/practices/plan_reaction_queries.py`
- Modify: `tests/practices/test_plan_reactions.py`
- Create: `tests/practices/test_plan_reaction_queries.py`

**Interfaces:**

- Produces `resolve_plan_reaction_defaults(practice_types, activities) -> PlanReactionResolution` and keeps `resolve_default_plan_reactions(...) -> list[dict[str, str]]` as a compatibility wrapper.
- Produces `build_plan_reaction_catalog(practice_types, activities) -> tuple[PlanReactionCatalogOption, ...]` and `validate_authorized_plan_reactions(value, *, catalog, protected_snapshot=(), source="Plan reactions") -> list[dict[str, str]]`.
- Produces `load_selected_plan_reaction_sources(session, *, activity_ids, type_ids) -> SelectedPlanReactionSources` and `load_all_plan_reaction_sources(session) -> SelectedPlanReactionSources` for every server adapter.

- [ ] **Step 1: Add failing Multisport, provenance, catalog, and authorization tests**

Update the test `source` helper so every source has a stable ID and add the following behavioral tests (retain all existing normalization and member-facing-format tests):

```python
def source(source_id, name, options):
    return SimpleNamespace(
        id=source_id,
        name=name,
        default_plan_reactions=options,
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
```

Create strict loader tests using real test database rows and the existing `db_session`/`app` fixture style:

```python
def test_loader_deduplicates_ids_before_multisport_count(app):
    with app.app_context():
        run = PracticeActivity(name="Run")
        db.session.add(run)
        db.session.commit()
        selected = load_selected_plan_reaction_sources(
            db.session, activity_ids=[str(run.id), run.id, run.id], type_ids=[]
        )
        assert [item.id for item in selected.activities] == [run.id]


@pytest.mark.parametrize("bad_id", [True, "", "abc", "1.5", None])
def test_loader_rejects_malformed_ids(app, bad_id):
    with app.app_context(), pytest.raises(
        PlanReactionSourceSelectionError, match="Activity IDs"
    ):
        load_selected_plan_reaction_sources(
            db.session, activity_ids=[bad_id], type_ids=[]
        )


def test_loader_rejects_unknown_ids_instead_of_returning_partial_selection(app):
    with app.app_context(), pytest.raises(
        PlanReactionSourceSelectionError, match="Unknown Activity ID"
    ):
        load_selected_plan_reaction_sources(
            db.session, activity_ids=[999999], type_ids=[]
        )
```

- [ ] **Step 2: Run focused tests and verify the intended RED state**

Run:

```bash
env/bin/pytest tests/practices/test_plan_reactions.py tests/practices/test_plan_reaction_queries.py -q
```

Expected: new tests fail on missing rich resolver/catalog/query symbols and the old one-Activity resolver tests fail because their fixtures/signatures have not yet been updated; existing validation tests remain green.

- [ ] **Step 3: Implement the rich resolver, catalog, and authorization**

Add immutable result types and authoritative helpers to `plan_reactions.py`:

```python
class PlanReactionValidationError(ValueError):
    """Validation error with optional adapter-safe field metadata."""

    def __init__(self, message: str, *, field: str | None = None,
                 row_id: str | None = None, emoji: str | None = None):
        super().__init__(message)
        self.field = field
        self.row_id = row_id
        self.emoji = emoji


@dataclass(frozen=True)
class ResolvedPlanReaction:
    emoji: str
    label: str
    source_keys: tuple[str, ...]


@dataclass(frozen=True)
class PlanReactionResolution:
    rows: tuple[ResolvedPlanReaction, ...]
    unconfigured_activity_names: tuple[str, ...] = ()

    @property
    def snapshot(self) -> list[dict[str, str]]:
        return [{"emoji": row.emoji, "label": row.label} for row in self.rows]


@dataclass(frozen=True)
class PlanReactionCatalogOption:
    option_id: str
    emoji: str
    label: str
    source_keys: tuple[str, ...]


@dataclass
class _MutableResolvedReaction:
    emoji: str
    label: str
    source_keys: list[str]
    source_names: list[str]


def _distinct_sources(items: Iterable, kind: str) -> list[tuple[str, object]]:
    by_key = {}
    for item in items or ():
        source_id = getattr(item, "id", None)
        name = str(getattr(item, "name", "") or "").strip()
        if isinstance(source_id, bool) or not isinstance(source_id, int) or not name:
            raise PlanReactionValidationError(f"Invalid {kind} reaction source")
        by_key.setdefault(f"{kind}:{source_id}", item)
    return sorted(by_key.items(), key=lambda pair: pair[1].name.casefold())


def resolve_plan_reaction_defaults(practice_types, activities):
    type_sources = _distinct_sources(practice_types, "type")
    activity_sources = _distinct_sources(activities, "activity")
    applicable = type_sources + (activity_sources if len(activity_sources) >= 2 else [])
    rows = []
    by_emoji = {}
    for source_key, item in applicable:
        source_name = (
            f"Workout Type {item.name}" if source_key.startswith("type:")
            else f"Activity {item.name}"
        )
        for option in normalize_plan_reactions(
            getattr(item, "default_plan_reactions", None) or [], source=source_name
        ):
            prior = by_emoji.get(option["emoji"])
            if prior and prior.label != option["label"]:
                prior_name = prior.source_names[0]
                raise PlanReactionValidationError(
                    f":{option['emoji']}: has conflicting labels in {prior_name} and {source_name}",
                    field="activities" if source_key.startswith("activity:") else "types",
                    emoji=option["emoji"],
                )
            if prior:
                prior.source_keys.append(source_key)
                prior.source_names.append(source_name)
                continue
            mutable = _MutableResolvedReaction(
                emoji=option["emoji"], label=option["label"],
                source_keys=[source_key], source_names=[source_name],
            )
            by_emoji[option["emoji"]] = mutable
            rows.append(mutable)
    if len(rows) > MAX_PLAN_REACTIONS:
        raise PlanReactionValidationError(
            f"Selected Activities and Workout Types produce more than {MAX_PLAN_REACTIONS} reactions",
            field="activities" if len(activity_sources) >= 2 else "types",
        )
    return PlanReactionResolution(
        rows=tuple(ResolvedPlanReaction(row.emoji, row.label, tuple(row.source_keys)) for row in rows),
        unconfigured_activity_names=(
            tuple(item.name for _, item in activity_sources if not item.default_plan_reactions)
            if len(activity_sources) >= 2 else ()
        ),
    )


def resolve_default_plan_reactions(practice_types, activities):
    return resolve_plan_reaction_defaults(practice_types, activities).snapshot


def build_plan_reaction_catalog(practice_types, activities):
    merged = {}
    ordered = []
    for source_key, item in _distinct_sources(practice_types, "type") + _distinct_sources(activities, "activity"):
        source_name = (
            f"Workout Type {item.name}" if source_key.startswith("type:")
            else f"Activity {item.name}"
        )
        for pair in normalize_plan_reactions(item.default_plan_reactions or [], source=source_name):
            key = (pair["emoji"], pair["label"])
            if key in merged:
                merged[key].append(source_key)
                continue
            merged[key] = [source_key]
            ordered.append(key)
    return tuple(
        PlanReactionCatalogOption(
            option_id=hashlib.sha256(
                json.dumps(key, separators=(",", ":"), ensure_ascii=True).encode()
            ).hexdigest()[:16],
            emoji=key[0], label=key[1], source_keys=tuple(merged[key]),
        )
        for key in ordered
    )


def validate_authorized_plan_reactions(
    value, *, catalog, protected_snapshot=(), source="Plan reactions"
):
    normalized = normalize_plan_reactions(value, source=source)
    allowed = {item.emoji for item in catalog}
    allowed.update(item["emoji"] for item in normalize_plan_reactions(
        list(protected_snapshot or []), source="Saved Plan reactions"
    ))
    for row in normalized:
        if row["emoji"] not in allowed:
            raise PlanReactionValidationError(
                f"{source}: :{row['emoji']}: is not configured in Settings",
                emoji=row["emoji"],
            )
    return normalized
```

Use a small private mutable dataclass for merge assembly; do not expose it as a public interface. Keep error strings compatible with existing tests.

- [ ] **Step 4: Implement strict database source loading**

Create `plan_reaction_queries.py` with:

```python
@dataclass(frozen=True)
class SelectedPlanReactionSources:
    practice_types: tuple[PracticeType, ...]
    activities: tuple[PracticeActivity, ...]


class PlanReactionSourceSelectionError(PlanReactionValidationError):
    def __init__(self, message: str, *, field: str):
        super().__init__(message)
        self.field = field


def _coerce_ids(values, *, label, field):
    result = []
    seen = set()
    for value in values or ():
        if isinstance(value, bool):
            raise PlanReactionSourceSelectionError(f"{label}: invalid ID", field=field)
        try:
            normalized = int(value)
        except (TypeError, ValueError):
            raise PlanReactionSourceSelectionError(f"{label}: invalid ID", field=field)
        if str(value).strip() != str(normalized) or normalized <= 0:
            raise PlanReactionSourceSelectionError(f"{label}: invalid ID", field=field)
        if normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return tuple(result)


def _load_exact(session, model, ids, *, label, field):
    if not ids:
        return ()
    records = session.query(model).filter(model.id.in_(ids)).all()
    by_id = {record.id: record for record in records}
    missing = [value for value in ids if value not in by_id]
    if missing:
        noun = "ID" if len(missing) == 1 else "IDs"
        raise PlanReactionSourceSelectionError(
            f"Unknown {label[:-1]} {noun}: {', '.join(map(str, missing))}", field=field
        )
    return tuple(by_id[value] for value in ids)


def load_selected_plan_reaction_sources(session, *, activity_ids, type_ids):
    activity_ids = _coerce_ids(activity_ids, label="Activity IDs", field="activities")
    type_ids = _coerce_ids(type_ids, label="Workout Type IDs", field="types")
    return SelectedPlanReactionSources(
        practice_types=_load_exact(
            session, PracticeType, type_ids, label="Workout Types", field="types"
        ),
        activities=_load_exact(
            session, PracticeActivity, activity_ids, label="Activities", field="activities"
        ),
    )


def load_all_plan_reaction_sources(session):
    return SelectedPlanReactionSources(
        practice_types=tuple(session.query(PracticeType).order_by(PracticeType.name).all()),
        activities=tuple(session.query(PracticeActivity).order_by(PracticeActivity.name).all()),
    )
```

- [ ] **Step 5: Update superseded one-Activity resolver expectations and run focused tests**

Change existing resolver cases that need Activity rows to provide two distinct Activities; retain explicit cases proving one Activity is ignored. Then run:

```bash
env/bin/pytest tests/practices/test_plan_reactions.py tests/practices/test_plan_reaction_queries.py -q
```

Expected: all focused tests pass.

- [ ] **Step 6: Run adjacent contracts and commit**

Run:

```bash
env/bin/pytest \
  tests/practices/test_plan_reaction_contracts.py \
  tests/practices/test_plan_reaction_migration.py \
  tests/practices/test_plan_reactions.py \
  tests/practices/test_plan_reaction_queries.py -q
```

Expected: all tests pass and the migration/schema contracts remain unchanged.

```bash
git add app/practices/plan_reactions.py app/practices/plan_reaction_queries.py \
  tests/practices/test_plan_reactions.py tests/practices/test_plan_reaction_queries.py
git commit -m "feat(practices): resolve multisport reaction defaults"
```

### Task 2: Build the Ephemeral Reaction Working-State Machine

**Files:**

- Create: `app/practices/plan_reaction_editor.py`
- Create: `tests/practices/test_plan_reaction_editor.py`

**Interfaces:**

- Consumes Task 1's `PlanReactionResolution`, `PlanReactionCatalogOption`, `resolve_plan_reaction_defaults()`, and normalizer.
- Produces `PlanReactionEditorState` plus `build_plan_reaction_editor_state()`, `reconcile_plan_reaction_editor_state()`, `restore_plan_reaction_defaults()`, `add_catalog_plan_reaction()`, `remove_plan_reaction()`, `undo_plan_reaction()`, `active_plan_reaction_snapshot()`, `serialize_plan_reaction_editor_state()`, and `deserialize_plan_reaction_editor_state()` for Slack and behavioral parity with Admin JavaScript.

- [ ] **Step 1: Write failing reconstruction, reconciliation, and origin tests**

Create fixtures for an interval Type, Run, configured Rollerski, unconfigured Strength, and conflicting/overflow sources. Add these tests:

```python
def test_create_starts_from_current_effective_defaults(sources):
    result = build_plan_reaction_editor_state(
        practice_types=[sources.intervals],
        activities=[sources.run, sources.rollerski],
        saved_snapshot=None,
    )
    assert result.blocking_error is None
    assert active_plan_reaction_snapshot(result.state) == FOUR_APPROVED_ROWS
    assert all(row.inherited_source_keys for row in result.state.rows)


def test_existing_empty_snapshot_suppresses_current_defaults(sources):
    result = build_plan_reaction_editor_state(
        practice_types=[sources.intervals],
        activities=[sources.run, sources.rollerski],
        saved_snapshot=[],
    )
    assert result.state.rows == []
    assert {item.emoji for item in result.state.suppressed} == {
        "evergreen_tree", "athletic_shoe", "hatching_chick",
        "older_adult::skin-tone-4",
    }


def test_edit_reconstructs_inherited_custom_label_and_protected_snapshot(sources):
    saved = [
        {"emoji": "athletic_shoe", "label": "trail runner"},
        {"emoji": "wheel", "label": "classic rollerski"},
    ]
    result = build_plan_reaction_editor_state(
        practice_types=[], activities=[sources.run, sources.rollerski],
        saved_snapshot=saved,
    )
    shoe, wheel = result.state.rows
    assert shoe.label == "trail runner"
    assert shoe.inherited_source_keys == (f"activity:{sources.run.id}",)
    assert shoe.protected_order is None
    assert wheel.protected_order == 1


def test_one_two_three_one_transition_preserves_only_surviving_origins(sources):
    initial = build_plan_reaction_editor_state(
        practice_types=[sources.intervals], activities=[sources.run],
        saved_snapshot=None,
    ).state
    two = reconcile_plan_reaction_editor_state(
        initial, practice_types=[sources.intervals],
        activities=[sources.run, sources.rollerski],
    ).state
    shoe = next(row for row in two.rows if row.emoji == "athletic_shoe")
    shoe.label = "Run or walk"
    three = reconcile_plan_reaction_editor_state(
        two, practice_types=[sources.intervals],
        activities=[sources.run, sources.rollerski, sources.strength],
    ).state
    one = reconcile_plan_reaction_editor_state(
        three, practice_types=[sources.intervals], activities=[sources.run],
    ).state
    assert active_plan_reaction_snapshot(one) == [EVERGREEN_PLAN_REACTION]
    assert one.unconfigured_activity_names == ()


def test_catalog_and_protected_origins_survive_inherited_source_disappearance(sources):
    state = build_plan_reaction_editor_state(
        practice_types=[], activities=[sources.run],
        saved_snapshot=[{"emoji": "athletic_shoe", "label": "saved runner"}],
    ).state
    option = PlanReactionCatalogOption(
        option_id="shoe", emoji="athletic_shoe", label="runner",
        source_keys=(f"activity:{sources.run.id}",),
    )
    state = add_catalog_plan_reaction(state, option)
    inherited = reconcile_plan_reaction_editor_state(
        state, practice_types=[], activities=[sources.run, sources.rollerski]
    ).state
    returned = reconcile_plan_reaction_editor_state(
        inherited, practice_types=[], activities=[sources.run]
    ).state
    assert len(returned.rows) == 1
    assert returned.rows[0].label == "saved runner"
    assert returned.rows[0].protected_order == 0
    assert returned.rows[0].catalog_order == 0
    assert returned.rows[0].inherited_source_keys == ()


def test_suppression_clears_only_after_all_original_sources_disappear(sources):
    state = build_plan_reaction_editor_state(
        practice_types=[], activities=[sources.run, sources.rollerski],
        saved_snapshot=[],
    ).state
    still_suppressed = reconcile_plan_reaction_editor_state(
        state, practice_types=[], activities=[sources.run, sources.strength]
    ).state
    assert "athletic_shoe" in {item.emoji for item in still_suppressed.suppressed}
    absent = reconcile_plan_reaction_editor_state(
        still_suppressed, practice_types=[], activities=[sources.rollerski]
    ).state
    assert "athletic_shoe" not in {item.emoji for item in absent.suppressed}
    returned = reconcile_plan_reaction_editor_state(
        absent, practice_types=[], activities=[sources.run, sources.strength]
    ).state
    assert "athletic_shoe" in {row.emoji for row in returned.rows}
```

- [ ] **Step 2: Write failing Remove/Undo/Add/Restore, invalid-transition, and serialization tests**

```python
def test_remove_and_undo_preserve_description_emoji_row_id_and_slot(sources):
    state = build_plan_reaction_editor_state(
        practice_types=[], activities=[sources.run, sources.rollerski],
        saved_snapshot=None,
    ).state
    row = state.rows[0]
    row.label = "edited description"
    removed = remove_plan_reaction(state, row.row_id)
    assert removed.rows[0].removed is True
    assert removed.rows[0].label == "edited description"
    assert reserved_plan_reaction_slots(removed) == len(removed.rows)
    restored = undo_plan_reaction(removed, row.row_id)
    assert restored.rows[0].removed is False
    assert restored.rows[0].row_id == row.row_id


def test_removed_inherited_only_row_disappears_with_source_and_returns_fresh(sources):
    state = build_plan_reaction_editor_state(
        practice_types=[], activities=[sources.run, sources.rollerski],
        saved_snapshot=None,
    ).state
    shoe = next(row for row in state.rows if row.emoji == "athletic_shoe")
    shoe.label = "stale edit"
    state = remove_plan_reaction(state, shoe.row_id)
    state = reconcile_plan_reaction_editor_state(
        state, practice_types=[], activities=[sources.rollerski]
    ).state
    assert "athletic_shoe" not in {row.emoji for row in state.rows}
    state = reconcile_plan_reaction_editor_state(
        state, practice_types=[], activities=[sources.run, sources.strength]
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
        add_catalog_plan_reaction(state, PlanReactionCatalogOption(
            option_id="fifth", emoji="bike", label="bike", source_keys=("activity:9",)
        ))


def test_invalid_reconciliation_preserves_last_valid_rows_and_blocks_state(sources):
    state = build_plan_reaction_editor_state(
        practice_types=[], activities=[sources.run, sources.rollerski],
        saved_snapshot=None,
    ).state
    before = serialize_plan_reaction_editor_state(state)
    result = reconcile_plan_reaction_editor_state(
        state, practice_types=[sources.conflicting_type],
        activities=[sources.run, sources.rollerski],
    )
    assert result.blocking_error and "conflicting labels" in result.blocking_error
    assert serialize_plan_reaction_editor_state(result.state)["rows"] == before["rows"]
    assert result.state.blocking_error == result.blocking_error


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


def test_restore_is_atomic_and_clears_all_practice_specific_working_state(sources):
    original = build_plan_reaction_editor_state(
        practice_types=[], activities=[sources.run, sources.rollerski],
        saved_snapshot=[{"emoji": "wheel", "label": "protected"}],
    ).state
    original = remove_plan_reaction(original, original.rows[0].row_id)
    restored = restore_plan_reaction_defaults(
        original, practice_types=[sources.intervals],
        activities=[sources.run, sources.rollerski],
    )
    assert restored.blocking_error is None
    assert active_plan_reaction_snapshot(restored.state) == FOUR_APPROVED_ROWS
    assert not restored.state.suppressed
    assert all(row.protected_order is None for row in restored.state.rows)
    assert all(row.catalog_order is None for row in restored.state.rows)


def test_metadata_round_trip_preserves_removed_labels_and_rejects_hostile_payload(sources):
    state = build_plan_reaction_editor_state(
        practice_types=[sources.intervals], activities=[sources.run],
        saved_snapshot=None,
    ).state
    state.rows[0].label = ""
    state = remove_plan_reaction(state, state.rows[0].row_id)
    payload = serialize_plan_reaction_editor_state(state, omit_active_labels=True)
    assert deserialize_plan_reaction_editor_state(payload) == state
    with pytest.raises(PlanReactionValidationError, match="editor metadata"):
        deserialize_plan_reaction_editor_state({"version": 99, "rows": []})
```

- [ ] **Step 3: Run the state tests and verify missing-symbol failures**

Run:

```bash
env/bin/pytest tests/practices/test_plan_reaction_editor.py -q
```

Expected: collection fails only because `app.practices.plan_reaction_editor` and its symbols do not exist.

- [ ] **Step 4: Implement explicit editor dataclasses and safe cloning**

Create the module with these public types and constants:

```python
PLAN_REACTION_EDITOR_VERSION = 1


@dataclass
class PlanReactionEditorRow:
    row_id: str
    emoji: str
    label: str
    removed: bool = False
    inherited_source_keys: tuple[str, ...] = ()
    inherited_order: int | None = None
    protected_order: int | None = None
    catalog_order: int | None = None


@dataclass(frozen=True)
class SuppressedPlanReaction:
    emoji: str
    source_keys: tuple[str, ...]


@dataclass
class PlanReactionEditorState:
    version: int = PLAN_REACTION_EDITOR_VERSION
    rows: list[PlanReactionEditorRow] = field(default_factory=list)
    suppressed: list[SuppressedPlanReaction] = field(default_factory=list)
    last_valid_type_ids: tuple[int, ...] = ()
    last_valid_activity_ids: tuple[int, ...] = ()
    next_row_number: int = 0
    blocking_error: str | None = None
    unconfigured_activity_names: tuple[str, ...] = ()
    effective_inherited_count: int = 0
    add_open: bool = False


@dataclass(frozen=True)
class PlanReactionEditorResult:
    state: PlanReactionEditorState
    resolution: PlanReactionResolution | None
    blocking_error: str | None = None


def _clone(state: PlanReactionEditorState) -> PlanReactionEditorState:
    return copy.deepcopy(state)


def _source_ids(items) -> tuple[int, ...]:
    return tuple(dict.fromkeys(item.id for item in items or ()))


def _new_row(state, *, emoji, label, inherited=(), inherited_order=None,
             protected_order=None, catalog_order=None):
    row = PlanReactionEditorRow(
        row_id=f"r{state.next_row_number}", emoji=emoji, label=label,
        inherited_source_keys=tuple(inherited), inherited_order=inherited_order,
        protected_order=protected_order, catalog_order=catalog_order,
    )
    state.next_row_number += 1
    return row


def _row_sort_key(row):
    if row.inherited_order is not None:
        return (0, row.inherited_order)
    if row.protected_order is not None:
        return (1, row.protected_order)
    return (2, row.catalog_order if row.catalog_order is not None else 10_000)
```

- [ ] **Step 5: Implement Create/Edit reconstruction and reconciliation**

Use the following exact state transitions:

```python
def build_plan_reaction_editor_state(*, practice_types, activities, saved_snapshot=None):
    try:
        resolution = resolve_plan_reaction_defaults(practice_types, activities)
    except PlanReactionValidationError as exc:
        state = PlanReactionEditorState(
            last_valid_type_ids=_source_ids(practice_types),
            last_valid_activity_ids=_source_ids(activities),
            blocking_error=str(exc),
        )
        if saved_snapshot is not None:
            for saved_order, pair in enumerate(normalize_plan_reactions(
                saved_snapshot, source="Saved Plan reactions"
            )):
                state.rows.append(_new_row(
                    state, emoji=pair["emoji"], label=pair["label"],
                    protected_order=saved_order,
                ))
        return PlanReactionEditorResult(state, None, str(exc))
    state = PlanReactionEditorState(
        last_valid_type_ids=_source_ids(practice_types),
        last_valid_activity_ids=_source_ids(activities),
        unconfigured_activity_names=resolution.unconfigured_activity_names,
        effective_inherited_count=len(resolution.rows),
    )
    current = {row.emoji: (index, row) for index, row in enumerate(resolution.rows)}
    if saved_snapshot is None:
        for index, row in enumerate(resolution.rows):
            state.rows.append(_new_row(
                state, emoji=row.emoji, label=row.label,
                inherited=row.source_keys, inherited_order=index,
            ))
    else:
        saved = normalize_plan_reactions(saved_snapshot, source="Saved Plan reactions")
        for saved_order, pair in enumerate(saved):
            match = current.get(pair["emoji"])
            state.rows.append(_new_row(
                state, emoji=pair["emoji"], label=pair["label"],
                inherited=match[1].source_keys if match else (),
                inherited_order=match[0] if match else None,
                protected_order=None if match else saved_order,
            ))
        saved_keys = {pair["emoji"] for pair in saved}
        state.suppressed = [
            SuppressedPlanReaction(row.emoji, row.source_keys)
            for row in resolution.rows if row.emoji not in saved_keys
        ]
    state.rows.sort(key=_row_sort_key)
    return PlanReactionEditorResult(state, resolution)


def reconcile_plan_reaction_editor_state(state, *, practice_types, activities):
    original = _clone(state)
    try:
        resolution = resolve_plan_reaction_defaults(practice_types, activities)
    except PlanReactionValidationError as exc:
        original.blocking_error = str(exc)
        original.add_open = False
        return PlanReactionEditorResult(original, None, str(exc))
    working = _clone(state)
    desired = {row.emoji: (index, row) for index, row in enumerate(resolution.rows)}
    source_keys_now = {key for row in resolution.rows for key in row.source_keys}
    kept_suppression = [
        item for item in working.suppressed
        if any(key in source_keys_now for key in item.source_keys)
    ]
    suppressed_keys = {item.emoji for item in kept_suppression}
    by_emoji = {row.emoji: row for row in working.rows}
    kept_rows = []
    for row in working.rows:
        match = desired.get(row.emoji)
        if match:
            row.inherited_order = match[0]
            row.inherited_source_keys = match[1].source_keys
        else:
            row.inherited_order = None
            row.inherited_source_keys = ()
        if match or row.protected_order is not None or row.catalog_order is not None:
            kept_rows.append(row)
    working.rows = kept_rows
    by_emoji = {row.emoji: row for row in working.rows}
    for index, resolved in enumerate(resolution.rows):
        if resolved.emoji not in by_emoji and resolved.emoji not in suppressed_keys:
            row = _new_row(
                working, emoji=resolved.emoji, label=resolved.label,
                inherited=resolved.source_keys, inherited_order=index,
            )
            working.rows.append(row)
            by_emoji[row.emoji] = row
    working.suppressed = kept_suppression
    if len({row.emoji for row in working.rows}) > MAX_PLAN_REACTIONS:
        original.blocking_error = (
            f"Selected Activities and Workout Types reserve more than {MAX_PLAN_REACTIONS} reactions"
        )
        original.add_open = False
        return PlanReactionEditorResult(original, None, original.blocking_error)
    working.rows.sort(key=_row_sort_key)
    working.last_valid_type_ids = _source_ids(practice_types)
    working.last_valid_activity_ids = _source_ids(activities)
    working.unconfigured_activity_names = resolution.unconfigured_activity_names
    working.effective_inherited_count = len(resolution.rows)
    working.blocking_error = None
    return PlanReactionEditorResult(working, resolution)
```

- [ ] **Step 6: Implement row actions, Restore, active snapshot, and metadata validation**

```python
def reserved_plan_reaction_slots(state):
    return len({row.emoji for row in state.rows})


def remove_plan_reaction(state, row_id):
    working = _clone(state)
    row = next((item for item in working.rows if item.row_id == row_id), None)
    if row is None:
        raise PlanReactionValidationError("Unknown reaction row")
    row.removed = True
    return working


def undo_plan_reaction(state, row_id):
    working = _clone(state)
    row = next((item for item in working.rows if item.row_id == row_id), None)
    if row is None or not row.removed:
        raise PlanReactionValidationError("Unknown removed reaction row")
    row.removed = False
    return working


def add_catalog_plan_reaction(state, option):
    working = _clone(state)
    working.suppressed = [
        item for item in working.suppressed if item.emoji != option.emoji
    ]
    existing = next((row for row in working.rows if row.emoji == option.emoji), None)
    if existing:
        if existing.catalog_order is None:
            existing.catalog_order = max(
                (row.catalog_order for row in working.rows if row.catalog_order is not None),
                default=-1,
            ) + 1
        return working
    if reserved_plan_reaction_slots(working) >= MAX_PLAN_REACTIONS:
        raise PlanReactionValidationError("Plan reactions: use at most 4 reactions")
    order = max(
        (row.catalog_order for row in working.rows if row.catalog_order is not None),
        default=-1,
    ) + 1
    working.rows.append(_new_row(
        working, emoji=option.emoji, label=option.label,
        catalog_order=order,
    ))
    working.rows.sort(key=_row_sort_key)
    working.add_open = False
    return working


def restore_plan_reaction_defaults(state, *, practice_types, activities):
    try:
        restored = build_plan_reaction_editor_state(
            practice_types=practice_types, activities=activities,
            saved_snapshot=None,
        )
    except PlanReactionValidationError as exc:
        working = _clone(state)
        working.blocking_error = str(exc)
        working.add_open = False
        return PlanReactionEditorResult(working, None, str(exc))
    if restored.blocking_error:
        working = _clone(state)
        working.blocking_error = restored.blocking_error
        working.add_open = False
        return PlanReactionEditorResult(working, None, restored.blocking_error)
    restored.state.next_row_number = max(state.next_row_number, restored.state.next_row_number)
    return restored


def active_plan_reaction_snapshot(state):
    return normalize_plan_reactions(
        [{"emoji": row.emoji, "label": row.label} for row in state.rows if not row.removed]
    )
```

Serialize every dataclass field with JSON primitives, use keys `version`, `rows`, `suppressed`, `last_valid_type_ids`, `last_valid_activity_ids`, `next_row_number`, `blocking_error`, `unconfigured_activity_names`, `effective_inherited_count`, and `add_open`, and validate through the public constructors on decode. When `omit_active_labels=True`, encode active labels as `null` but always retain removed labels. Reject unknown versions, duplicate row IDs/emoji, invalid origin orders, malformed source keys, a negative inherited count, more than four distinct rows, and a removed row without a label value with `PlanReactionValidationError("Invalid reaction editor metadata")`.

- [ ] **Step 7: Run focused and domain regression tests**

Run:

```bash
env/bin/pytest \
  tests/practices/test_plan_reactions.py \
  tests/practices/test_plan_reaction_queries.py \
  tests/practices/test_plan_reaction_editor.py -q
```

Expected: all tests pass, including temporary blank labels surviving editor actions while `active_plan_reaction_snapshot()` rejects incomplete active rows at submission.

- [ ] **Step 8: Commit the state machine**

```bash
git add app/practices/plan_reaction_editor.py tests/practices/test_plan_reaction_editor.py
git commit -m "feat(practices): add reaction editor state machine"
```

### Task 3: Enforce Selection and Key Authorization in Admin Routes

**Files:**

- Modify: `app/routes/admin_practices.py`
- Modify: `tests/routes/test_admin_practice_plan_reactions.py`

**Interfaces:**

- Consumes Task 1's strict source loader, resolver, catalog builder, and authorization validator.
- Preserves existing Admin JSON response shapes while using `field: "activity_ids"`, `field: "type_ids"`, or `field: "plan_reactions"` for the corresponding authoritative failure.
- Leaves existing missing-key versus explicit-empty semantics intact: Create without `plan_reactions` saves current defaults; Edit without the key preserves the snapshot; explicit `[]` clears it.

- [ ] **Step 1: Add failing route tests for distinct IDs and unknown IDs**

Add a second Activity wherever an existing test expects Activity inheritance. Then add:

```python
def test_create_duplicate_activity_ids_count_once_not_as_multisport(
    admin_client, db_session, activity_with_plan_reactions, location
):
    response = admin_client.post("/admin/practices/create", json={
        "date": "2026-07-14T18:15", "location_id": location.id,
        "activity_ids": [activity_with_plan_reactions.id] * 3,
        "type_ids": [],
    })
    assert response.status_code == 200
    practice = db.session.get(Practice, response.get_json()["practice_id"])
    assert practice.plan_reactions == []
    assert [item.id for item in practice.activities] == [activity_with_plan_reactions.id]


@pytest.mark.parametrize(
    ("field", "payload"),
    [
        ("activity_ids", {"activity_ids": [999999], "type_ids": []}),
        ("type_ids", {"activity_ids": [], "type_ids": [999999]}),
    ],
)
def test_create_rejects_unknown_selector_ids(
    admin_client, location, field, payload
):
    response = admin_client.post("/admin/practices/create", json={
        "date": "2026-07-14T18:15", "location_id": location.id, **payload,
    })
    assert response.status_code == 400
    assert response.get_json()["field"] == field


def test_edit_rejects_unknown_selector_id_without_mutating_snapshot(
    admin_client, db_session, practice_with_plan_reactions
):
    before = list(practice_with_plan_reactions.plan_reactions)
    response = admin_client.post(
        f"/admin/practices/{practice_with_plan_reactions.id}/edit",
        json={"activity_ids": [999999]},
    )
    assert response.status_code == 400
    db.session.refresh(practice_with_plan_reactions)
    assert practice_with_plan_reactions.plan_reactions == before
```

- [ ] **Step 2: Add failing tests for authoritative resolver and catalog authorization**

```python
def test_explicit_snapshot_cannot_bypass_selected_source_conflict(
    admin_client, activity_with_plan_reactions, second_activity,
    conflicting_type, location
):
    response = admin_client.post("/admin/practices/create", json={
        "date": "2026-07-14T18:15", "location_id": location.id,
        "activity_ids": [activity_with_plan_reactions.id, second_activity.id],
        "type_ids": [conflicting_type.id],
        "plan_reactions": [],
    })
    assert response.status_code == 400
    assert response.get_json()["field"] == "plan_reactions"
    assert "conflicting labels" in response.get_json()["error"]


def test_create_rejects_tampered_emoji_absent_from_settings(
    admin_client, location
):
    response = admin_client.post("/admin/practices/create", json={
        "date": "2026-07-14T18:15", "location_id": location.id,
        "activity_ids": [], "type_ids": [],
        "plan_reactions": [{"emoji": "made_up", "label": "tampered"}],
    })
    assert response.status_code == 400
    assert response.get_json()["field"] == "plan_reactions"
    assert "not configured in Settings" in response.get_json()["error"]


def test_edit_allows_saved_key_after_settings_key_was_removed(
    admin_client, db_session, practice_with_plan_reactions
):
    practice_with_plan_reactions.plan_reactions = [
        {"emoji": "legacy_saved", "label": "legacy description"}
    ]
    db.session.commit()
    response = admin_client.post(
        f"/admin/practices/{practice_with_plan_reactions.id}/edit",
        json={"plan_reactions": [
            {"emoji": "legacy_saved", "label": "custom legacy description"}
        ]},
    )
    assert response.status_code == 200
    db.session.refresh(practice_with_plan_reactions)
    assert practice_with_plan_reactions.plan_reactions[0]["label"] == (
        "custom legacy description"
    )


def test_edit_allows_current_catalog_key_with_custom_description(
    admin_client, db_session, practice_with_plan_reactions,
    activity_with_plan_reactions
):
    response = admin_client.post(
        f"/admin/practices/{practice_with_plan_reactions.id}/edit",
        json={"plan_reactions": [
            {"emoji": "hatching_chick", "label": "First time on rollerskis"}
        ]},
    )
    assert response.status_code == 200
    db.session.refresh(practice_with_plan_reactions)
    assert practice_with_plan_reactions.plan_reactions == [{
        "emoji": "hatching_chick", "label": "First time on rollerskis"
    }]


def test_deleted_catalog_key_blocks_new_open_edit_row_but_preserves_saved_key(
    admin_client, db_session, practice_with_plan_reactions,
    activity_with_plan_reactions
):
    activity_with_plan_reactions.default_plan_reactions = []
    db.session.commit()
    response = admin_client.post(
        f"/admin/practices/{practice_with_plan_reactions.id}/edit",
        json={"plan_reactions": [
            {"emoji": "hatching_chick", "label": "unsaved open-modal text"}
        ]},
    )
    assert response.status_code == 400
    assert "not configured in Settings" in response.get_json()["error"]
```

- [ ] **Step 3: Run route tests and verify the intended failures**

Run:

```bash
env/bin/pytest tests/routes/test_admin_practice_plan_reactions.py -q
```

Expected: new unknown/tampered-key tests fail, duplicate Activity IDs incorrectly enable the old Activity default, and the updated two-Activity default tests fail until route loading changes.

- [ ] **Step 4: Add one route-private authoritative preparation helper**

Import the Task 1 functions and add:

```python
def _prepare_plan_reaction_submission(
    data, *, existing_practice=None
):
    activity_ids = (
        data.get("activity_ids") or []
        if "activity_ids" in data
        else [item.id for item in existing_practice.activities]
    )
    type_ids = (
        data.get("type_ids") or []
        if "type_ids" in data
        else [item.id for item in existing_practice.practice_types]
    )
    selected = load_selected_plan_reaction_sources(
        db.session, activity_ids=activity_ids, type_ids=type_ids
    )
    resolution = resolve_plan_reaction_defaults(
        selected.practice_types, selected.activities
    )
    all_sources = load_all_plan_reaction_sources(db.session)
    catalog = build_plan_reaction_catalog(
        all_sources.practice_types, all_sources.activities
    )
    protected = (
        existing_practice.plan_reactions or [] if existing_practice else []
    )
    if data.get("restore_plan_reaction_defaults") is True:
        plan_reactions = resolution.snapshot
    elif "plan_reactions" in data:
        plan_reactions = validate_authorized_plan_reactions(
            data["plan_reactions"], catalog=catalog,
            protected_snapshot=protected,
        )
    elif existing_practice is None:
        plan_reactions = resolution.snapshot
    else:
        plan_reactions = None
    return selected, plan_reactions
```

The conditional expressions must be parenthesized exactly as above so a missing key on Edit uses existing relations while an explicit empty list clears the selection.

- [ ] **Step 5: Wire Create and Edit through the helper without changing unrelated behavior**

In Create, call `_prepare_plan_reaction_submission(data)` before constructing the model, map `PlanReactionSourceSelectionError.field` to `activity_ids`/`type_ids`, map other reaction errors to `plan_reactions`, assign the returned exact records to both relationships, and save the returned snapshot.

In Edit, call `_prepare_plan_reaction_submission(data, existing_practice=practice)` before mutating any field. Only assign `practice.plan_reactions` when the returned value is not `None`; assign selected relationships only when their request key is present. Catch errors before the outer mutation block and return:

```python
except PlanReactionSourceSelectionError as exc:
    field = {"activities": "activity_ids", "types": "type_ids"}[exc.field]
    return jsonify({"error": str(exc), "field": field}), 400
except PlanReactionValidationError as exc:
    field = {
        "activities": "activity_ids", "types": "type_ids"
    }.get(exc.field, "plan_reactions")
    return jsonify({"error": str(exc), "field": field}), 400
```

- [ ] **Step 6: Run route and resolver regressions**

Run:

```bash
env/bin/pytest \
  tests/routes/test_admin_practice_plan_reactions.py \
  tests/practices/test_plan_reactions.py \
  tests/practices/test_plan_reaction_queries.py -q
```

Expected: all focused tests pass; existing announcement-refresh assertions remain unchanged.

- [ ] **Step 7: Commit authoritative Admin validation**

```bash
git add app/routes/admin_practices.py tests/routes/test_admin_practice_plan_reactions.py
git commit -m "fix(admin): validate practice reaction sources"
```

### Task 4: Replace the Admin Practice Editor with Fixed-Emoji Rows

**Files:**

- Create: `app/static/practice_plan_reactions.js`
- Create: `app/static/practice_plan_reaction_editor.js`
- Modify: `app/templates/admin/practices/detail.html`
- Modify: `app/templates/admin/practices/_detail_script.js`
- Modify: `app/templates/admin/practices/config.html`
- Modify: `package.json`
- Modify: `package-lock.json`
- Create: `tests/js/practice_plan_reactions.test.js`
- Create: `tests/js/practice_plan_reaction_editor.test.js`
- Create: `tests/practices/test_practice_plan_reaction_js.py`
- Modify: `tests/practices/test_plan_reaction_ui_source.py`
- Modify: `tests/routes/test_admin_practice_plan_reactions.py`

**Interfaces:**

- `window.PracticePlanReactions` is the pure state API; it accepts the existing `/activities/data` and `/types/data` JSON records and mirrors Task 2's state transitions.
- `window.PracticePlanReactionEditor.mount(options) -> controller` owns only `#plan-reaction-editor`; `controller.setSelection(typeIds, activityIds)`, `controller.restore()`, and `controller.snapshot()` are the integration seams.
- Keep `window.PlanReactionEditor` and `app/static/plan_reactions.js` exclusively for Settings, including editable emoji, Up/Down, destructive Remove, and autosave.

- [ ] **Step 1: Add exact Node/jsdom test dependencies and a pytest bridge**

Run:

```bash
npm install --save-dev --save-exact jsdom@29.1.1
```

Add this script without changing the Tailwind scripts:

```json
"test:practice-reactions": "node --test tests/js/practice_plan_reactions.test.js tests/js/practice_plan_reaction_editor.test.js"
```

Create the pytest bridge so the complete Python suite exercises the browser-state tests:

```python
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]


def test_admin_practice_reaction_javascript_suite():
    result = subprocess.run(
        ["npm", "run", "test:practice-reactions"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
```

- [ ] **Step 2: Write failing pure-state JavaScript tests**

Use `node:test`, `node:assert/strict`, and `require('../../app/static/practice_plan_reactions.js')`. Define records that match the Admin JSON shape and add:

```javascript
test('one activity is ordinary and two activities derive multisport defaults', () => {
  const one = Model.create({types: [intervals], activities: [run], savedSnapshot: null});
  assert.deepEqual(Model.activeRows(one).map(row => row.emoji), ['evergreen_tree']);
  const two = Model.reconcile(one, {types: [intervals], activities: [run, rollerski]});
  assert.deepEqual(Model.activeRows(two).map(row => row.emoji), [
    'evergreen_tree', 'athletic_shoe', 'hatching_chick',
    'older_adult::skin-tone-4',
  ]);
});


test('1 to 2 to 3 to 1 preserves edits only on rows whose origin survives', () => {
  let state = Model.create({types: [intervals], activities: [run], savedSnapshot: null});
  state = Model.reconcile(state, {types: [intervals], activities: [run, rollerski]});
  Model.updateLabel(state, Model.rowByEmoji(state, 'evergreen_tree').rowId, 'Easy endurance');
  state = Model.reconcile(state, {types: [intervals], activities: [run, rollerski, strength]});
  assert.deepEqual(state.unconfiguredActivityNames, ['Strength']);
  state = Model.reconcile(state, {types: [intervals], activities: [run]});
  assert.deepEqual(Model.activeRows(state).map(row => [row.emoji, row.label]), [
    ['evergreen_tree', 'Easy endurance'],
  ]);
});


test('remove and undo preserve the fixed key, edited description, and slot', () => {
  let state = Model.create({types: [intervals], activities: [run], savedSnapshot: null});
  const row = state.rows[0];
  Model.updateLabel(state, row.rowId, 'Edited');
  state = Model.remove(state, row.rowId);
  assert.equal(state.rows[0].removed, true);
  assert.equal(Model.reservedSlots(state), 1);
  state = Model.undo(state, row.rowId);
  assert.deepEqual(
    [state.rows[0].rowId, state.rows[0].emoji, state.rows[0].label],
    [row.rowId, 'evergreen_tree', 'Edited'],
  );
});


test('add uses only an unused Settings pair and removed keys remain reserved', () => {
  let state = Model.create({types: [], activities: [], savedSnapshot: null});
  const catalog = Model.buildCatalog([intervals], [run, rollerski]);
  state = Model.add(state, catalog.find(option => option.emoji === 'athletic_shoe'));
  state = Model.remove(state, state.rows[0].rowId);
  assert.equal(Model.availableCatalog(state, catalog).some(
    option => option.emoji === 'athletic_shoe'
  ), false);
});


test('conflict and overflow retain last-valid rows and block add and snapshot', () => {
  const state = Model.create({types: [], activities: [run, rollerski], savedSnapshot: null});
  const invalid = Model.reconcile(state, {
    types: [conflictingType], activities: [run, rollerski],
  });
  assert.deepEqual(invalid.rows, state.rows);
  assert.match(invalid.blockingError, /conflict/);
  assert.equal(Model.canAdd(invalid, Model.resolve([], [])), false);
  assert.throws(() => Model.snapshot(invalid), /conflict/);
});


test('existing snapshot reconstruction preserves protected rows and suppression', () => {
  const state = Model.create({
    types: [intervals], activities: [run, rollerski],
    savedSnapshot: [
      {emoji: 'athletic_shoe', label: 'custom runner'},
      {emoji: 'wheel', label: 'protected rollerski'},
    ],
  });
  assert.equal(Model.rowByEmoji(state, 'athletic_shoe').label, 'custom runner');
  assert.equal(Model.rowByEmoji(state, 'wheel').protectedOrder, 1);
  assert.deepEqual(state.suppressed.map(item => item.emoji), [
    'evergreen_tree', 'hatching_chick', 'older_adult::skin-tone-4',
  ]);
});


test('initially invalid Edit keeps its saved snapshot while blocking submission', () => {
  const state = Model.create({
    types: [conflictingType], activities: [run, rollerski],
    savedSnapshot: [{emoji: 'wheel', label: 'saved protected row'}],
  });
  assert.match(state.blockingError, /conflict/);
  assert.deepEqual(state.rows.map(row => [row.emoji, row.label]), [
    ['wheel', 'saved protected row'],
  ]);
  assert.throws(() => Model.snapshot(state), /conflict/);
});
```

- [ ] **Step 3: Run Node tests and verify the missing-module RED state**

Run:

```bash
npm run test:practice-reactions
```

Expected: tests fail because the two new modules do not exist.

- [ ] **Step 4: Implement the pure Admin state module**

Export the same object through CommonJS and `window`:

```javascript
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.PracticePlanReactions = api;
})(typeof window !== 'undefined' ? window : globalThis, function () {
  const MAX = 4;

  function distinct(items) {
    const seen = new Set();
    return (items || []).filter(item => {
      const key = Number(item.id);
      if (!Number.isInteger(key) || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  function resolve(types, activities) {
    const typeSources = distinct(types).sort((a, b) => a.name.localeCompare(b.name));
    const activitySources = distinct(activities).sort((a, b) => a.name.localeCompare(b.name));
    const sources = typeSources.map(item => ({kind: 'type', item}));
    if (activitySources.length >= 2) {
      sources.push(...activitySources.map(item => ({kind: 'activity', item})));
    }
    const rows = [];
    const seen = new Map();
    for (const source of sources) {
      const sourceKey = `${source.kind}:${source.item.id}`;
      const sourceName = `${source.kind === 'type' ? 'Workout Type' : 'Activity'} ${source.item.name}`;
      for (const pair of source.item.default_plan_reactions || []) {
        const prior = seen.get(pair.emoji);
        if (prior && prior.label !== pair.label) {
          return {rows: [], unconfiguredActivityNames: [], error:
            `:${pair.emoji}: conflicts between ${prior.sourceName} and ${sourceName}`};
        }
        if (prior) {
          prior.sourceKeys.push(sourceKey);
        } else {
          const row = {emoji: pair.emoji, label: pair.label,
            sourceKeys: [sourceKey], sourceName};
          seen.set(pair.emoji, row);
          rows.push(row);
        }
      }
    }
    if (rows.length > MAX) return {rows: [], unconfiguredActivityNames: [],
      error: 'Selected Activities and Workout Types produce more than 4 reactions'};
    return {
      rows,
      unconfiguredActivityNames: activitySources.length >= 2
        ? activitySources.filter(item => !(item.default_plan_reactions || []).length)
          .map(item => item.name)
        : [],
      error: null,
    };
  }
```

Port Task 2's reconstruction/reconciliation algorithm directly with camelCase field names, including the initially-invalid Edit rule that retains saved rows as protected last-valid state while Create starts empty. Every mutator must deep-clone its input via `structuredClone`, merge origins by emoji, keep temporary blank labels, drop inherited-only rows when their source disappears, reserve active/removed keys, and sort inherited → protected → catalog. Export exactly:

```javascript
return {
  MAX, resolve, create, reconcile, restore, remove, undo, add,
  updateLabel, activeRows, snapshot, reservedSlots, rowByEmoji,
  buildCatalog, availableCatalog, canAdd,
};
```

`snapshot(state)` trims and validates active descriptions, throws a row-aware error object `{message, rowId}` for a blank/over-80-character description, and throws `state.blockingError` before returning active `{emoji, label}` pairs. Store `effectiveInheritedCount` on every Create/reconcile/Restore result. `canAdd` returns true only when there is no blocking error, fewer than four slots are reserved, and `effectiveInheritedCount === 0` or `unconfiguredActivityNames` is nonempty.

- [ ] **Step 5: Write failing jsdom tests for fixed rows, focus, Add, and Restore**

Create a `JSDOM` fixture with only the approved editor markup and add:

```javascript
test('practice row renders fixed shortcode, one description input, and no move controls', () => {
  const {controller, document} = mountEditor();
  const row = document.querySelector('[data-reaction-row]');
  assert.equal(row.querySelector('.practice-reaction-key').textContent, ':evergreen_tree:');
  assert.equal(row.querySelectorAll('input').length, 1);
  assert.equal(row.querySelector('input').maxLength, 80);
  assert.match(row.querySelector('input').getAttribute('aria-label'), /evergreen_tree/);
  assert.equal(row.textContent.includes('Up'), false);
  assert.equal(row.textContent.includes('Down'), false);
  assert.deepEqual(controller.snapshot(), [
    {emoji: 'evergreen_tree', label: 'Endurance instead of intervals'},
  ]);
});


test('remove dims with visible Removed and focuses Undo; Undo focuses description', () => {
  const {document} = mountEditor();
  document.querySelector('[data-action="remove"]').click();
  const removed = document.querySelector('[data-reaction-row]');
  assert.equal(removed.classList.contains('is-removed'), true);
  assert.match(removed.textContent, /Removed/);
  assert.equal(document.activeElement.dataset.action, 'undo');
  document.activeElement.click();
  assert.equal(document.activeElement.classList.contains('practice-reaction-label'), true);
});


test('add picker excludes active and removed keys and uses fixed selected emoji', () => {
  const {document} = mountEditor({types: [], activities: [], savedSnapshot: null});
  document.getElementById('add-plan-reaction').click();
  const select = document.getElementById('plan-reaction-catalog');
  assert.equal(select.hidden, false);
  select.value = Array.from(select.options).find(option =>
    option.textContent.includes('athletic_shoe')
  ).value;
  select.dispatchEvent(new document.defaultView.Event('change', {bubbles: true}));
  assert.equal(document.querySelector('.practice-reaction-key').textContent, ':athletic_shoe:');
});


test('selector reconciliation replaces only reaction children', () => {
  const {controller, document} = mountEditor();
  const unrelated = document.createElement('input');
  unrelated.id = 'workout_description';
  unrelated.value = 'Keep this workout';
  document.body.append(unrelated);
  controller.setSelection([], [run.id, rollerski.id]);
  assert.equal(unrelated.value, 'Keep this workout');
  assert.strictEqual(document.getElementById('workout_description'), unrelated);
});


test('restore changes only reaction state and keeps unrelated form values', () => {
  const {controller, document} = mountEditor({savedSnapshot: [
    {emoji: 'wheel', label: 'protected'}
  ]});
  document.getElementById('workout_description').value = 'Keep me';
  controller.restore();
  assert.equal(document.getElementById('workout_description').value, 'Keep me');
  assert.equal(controller.snapshot()[0].emoji, 'evergreen_tree');
});


test('empty state is explicit and keeps Add available when catalog exists', () => {
  const {document} = mountEditor({types: [], activities: [], savedSnapshot: null});
  assert.match(document.getElementById('plan-reaction-empty').textContent, /No Plan reactions/);
  assert.equal(document.getElementById('add-plan-reaction').hidden, false);
});
```

- [ ] **Step 6: Implement the practice-only DOM controller**

`mount()` must take this exact object:

```javascript
const controller = PracticePlanReactionEditor.mount({
  root: document.getElementById('plan-reaction-editor'),
  types: typesData,
  activities: activitiesData,
  selectedTypeIds: selectedTagIds('types-pills'),
  selectedActivityIds: selectedTagIds('activities-pills'),
  savedSnapshot: practiceId ? savedPlanReactions : null,
});
```

Render shortcode text with `textContent`, never `innerHTML`; render the label input with `maxlength="80"`, `aria-label="Description for :<emoji>:"`, and an error node referenced by `aria-describedby`. Active rows place Remove beside the description. Removed rows retain shortcode and last label as static text, include visible `Removed`, and expose Undo. Set `aria-invalid="true"` only on submission errors.

The controller must read all current label inputs into state before every `setSelection`, Remove, Add, and Restore transition. `setSelection()` calls the pure resolver/reconciler and rerenders only `root`. `snapshot()` catches `{rowId}` validation errors, marks/focuses that row's description, announces the error, and rethrows. Remove rerenders and focuses Undo; Undo rerenders and focuses the restored input. Status announcements include `Removed :emoji:.`, `Restored :emoji:.`, `Reaction defaults restored.`, unconfigured Activity names, and blocking errors.

- [ ] **Step 7: Replace only the Admin practice reaction integration**

In `detail.html`, load the two new scripts after `practice_editor.js`, wrap the existing reaction controls in `id="plan-reaction-editor"`, add `#plan-reaction-empty` with neutral empty copy, a hidden labelled catalog `<select id="plan-reaction-catalog">`, an unconfigured notice, and keep the live status. Give the Activities/Practice Types labels stable IDs and their pill containers `role="group"`, matching `aria-labelledby`, and `aria-describedby="plan-reaction-status"` so blocking reconciliation errors are programmatically associated with the changed selectors. Update the existing inline CSS so:

```css
.practice-reaction-row { display:grid; grid-template-columns:minmax(9rem,auto) minmax(0,1fr) auto; gap:.625rem; align-items:center; }
.practice-reaction-key { overflow-wrap:anywhere; font-weight:600; }
.practice-reaction-row.is-removed { opacity:.62; }
.practice-reaction-removed-label { opacity:1; font-weight:600; }
@media (max-width:767px) {
  .practice-reaction-row { grid-template-columns:1fr; }
  .practice-reaction-label, .practice-reaction-action,
  #restore-plan-reactions, #add-plan-reaction,
  #plan-reaction-catalog { min-height:44px; width:100%; }
}
```

Replace `_detail_script.js`'s `planReactionMode`, duplicated resolver, arbitrary blank-row Add, and editable emoji extraction. Keep all unrelated form code. Store one `planReactionController`; Activity/Type pill callbacks call `setSelection()` after it exists. The form submission always executes:

```javascript
try {
  payload.plan_reactions = planReactionController.snapshot();
} catch (error) {
  showToast(error.message || 'Check Plan reactions.', 'error');
  return;
}
```

Do not send `restore_plan_reaction_defaults`; Restore already replaced only the local working set and the final explicit snapshot is authoritative.

- [ ] **Step 8: Preserve Settings and add the exact Activity helper copy**

In `cfgBuildPlanReactionDefaults(record, entityKey, responseKey)`, insert a neutral helper before the Settings rows:

```javascript
const helperText = entityKey === 'activities'
  ? 'Used when this Activity is selected with another Activity.'
  : 'Applied when this Workout Type is selected.';
const helper = AdminUI.el('p', {class: 'cfg-helper-text'}, [helperText]);
```

Return the helper with the existing editable `PlanReactionEditor` rows. Do not change `savePlanReactions()`, its neutral incomplete branch, focus, classes, requests, or action buttons.

- [ ] **Step 9: Add/update source contracts and run Node plus Admin tests**

Assert the practice template loads `practice_plan_reactions.js` and `practice_plan_reaction_editor.js`, contains no editable `.plan-reaction-emoji` use in `_detail_script.js`, gives both selector groups programmatic labels plus the blocking-status description, and contains the exact Activity copy. Retain assertions proving Settings still uses `.plan-reaction-emoji`, Up/Down, and exact incomplete copy.

Run:

```bash
npm run test:practice-reactions
env/bin/pytest \
  tests/practices/test_practice_plan_reaction_js.py \
  tests/practices/test_plan_reaction_ui_source.py \
  tests/routes/test_admin_practice_plan_reactions.py -q
```

Expected: all tests pass, including focus and unrelated-node identity in jsdom.

- [ ] **Step 10: Commit the Admin structured editor**

```bash
git add package.json package-lock.json \
  app/static/practice_plan_reactions.js \
  app/static/practice_plan_reaction_editor.js \
  app/templates/admin/practices/detail.html \
  app/templates/admin/practices/_detail_script.js \
  app/templates/admin/practices/config.html \
  tests/js tests/practices/test_practice_plan_reaction_js.py \
  tests/practices/test_plan_reaction_ui_source.py \
  tests/routes/test_admin_practice_plan_reactions.py
git commit -m "feat(admin): add structured practice reactions"
```

### Task 5: Render and Serialize the Structured Slack Editor

**Files:**

- Create: `app/slack/practice_reaction_editor.py`
- Modify: `app/slack/modals.py`
- Modify: `app/slack/bolt_app.py` (modal-opening call sites only)
- Create: `tests/slack/test_practice_reaction_editor.py`
- Modify: `tests/slack/test_practice_create_modal.py`
- Modify: `tests/slack/test_practice_edit_full.py`
- Modify: `tests/slack/test_practice_preview.py`

**Interfaces:**

- Consumes Task 2's editor state and Task 1's catalog options.
- Produces `build_practice_reaction_blocks()`, `encode_practice_reaction_metadata()`, `decode_practice_reaction_metadata()`, `merge_practice_reaction_inputs()`, `apply_current_view_values()`, `build_retryable_practice_reaction_error_view()`, and `parse_practice_reaction_submission()`.
- Modal builders receive prepared state/catalog and may receive complete current `view.state.values`; they do not query the database.

- [ ] **Step 1: Write failing Block Kit row and catalog tests**

Create `tests/slack/test_practice_reaction_editor.py` and add:

```python
def _blocks_by_id(blocks):
    return {block["block_id"]: block for block in blocks if "block_id" in block}


def test_active_row_has_fixed_key_single_line_description_and_remove(editor_state):
    blocks = _blocks_by_id(build_practice_reaction_blocks(
        editor_state, CATALOG, allow_restore=True
    ))
    assert blocks["practice_reaction_key_r0"]["text"]["text"] == "*:evergreen_tree:*"
    field = blocks["practice_reaction_row_r0"]
    assert field["optional"] is True
    assert field["label"]["text"] == "Description for :evergreen_tree:"
    assert field["element"] == {
        "type": "plain_text_input",
        "action_id": "practice_reaction_description",
        "max_length": 80,
        "initial_value": "Endurance instead of intervals",
    }
    assert blocks["practice_reaction_controls_r0"]["elements"][0] == {
        "type": "button", "action_id": "practice_reaction_remove",
        "value": "r0", "text": {"type": "plain_text", "text": "Remove"},
        "accessibility_label": "Remove reaction :evergreen_tree:",
    }


def test_removed_row_is_static_labelled_and_undoable(editor_state):
    removed = remove_plan_reaction(editor_state, "r0")
    blocks = _blocks_by_id(build_practice_reaction_blocks(
        removed, CATALOG, allow_restore=True
    ))
    block = blocks["practice_reaction_removed_r0"]
    assert "Removed" in block["text"]["text"]
    assert "Endurance instead of intervals" in block["text"]["text"]
    assert block["accessory"]["action_id"] == "practice_reaction_undo"
    assert block["accessory"]["value"] == "r0"
    assert "practice_reaction_row_r0" not in blocks


def test_add_is_conditional_filters_reserved_emoji_and_restore_is_full_edit_only(empty_state):
    empty_state.add_open = True
    blocks = _blocks_by_id(build_practice_reaction_blocks(
        empty_state, CATALOG, allow_restore=False
    ))
    picker = blocks["practice_reaction_catalog_block"]["elements"][0]
    assert picker["action_id"] == "practice_reaction_catalog_select"
    assert all(len(option["text"]["text"]) <= 75 for option in picker["options"])
    assert not any(
        element.get("action_id") == "practice_reaction_restore"
        for block in blocks.values() for element in block.get("elements", [])
    )


def test_catalog_over_100_is_explicit_configuration_error(empty_state):
    empty_state.add_open = True
    catalog = tuple(
        PlanReactionCatalogOption(str(i), f"choice_{i}", f"Choice {i}", (f"type:{i}",))
        for i in range(101)
    )
    blocks = _blocks_by_id(build_practice_reaction_blocks(
        empty_state, catalog, allow_restore=False
    ))
    assert "more than 100" in blocks["practice_reaction_catalog_error"]["text"]["text"]
    assert "practice_reaction_catalog_block" not in blocks


def test_no_rows_has_explicit_empty_state_and_bounded_action_labels(empty_state):
    blocks = _blocks_by_id(build_practice_reaction_blocks(
        empty_state, CATALOG, allow_restore=False
    ))
    assert "No Plan reactions" in blocks["practice_reaction_empty"]["text"]["text"]
    long_key_state = copy.deepcopy(empty_state)
    long_key_state.rows = [PlanReactionEditorRow(
        row_id="r0", emoji="x" * 80, label="choice", catalog_order=0
    )]
    rendered = _blocks_by_id(build_practice_reaction_blocks(
        long_key_state, CATALOG, allow_restore=False
    ))
    button = rendered["practice_reaction_controls_r0"]["elements"][0]
    assert len(button["accessibility_label"]) <= 75


def test_picker_ellipsizes_display_only_and_full_label_survives_selection(empty_state):
    label = "L" * 80
    option = PlanReactionCatalogOption("opaque", "long", label, ("type:1",))
    empty_state.add_open = True
    block = _blocks_by_id(build_practice_reaction_blocks(
        empty_state, (option,), allow_restore=False
    ))["practice_reaction_catalog_block"]
    rendered = block["elements"][0]["options"][0]
    assert len(rendered["text"]["text"]) == 75
    assert rendered["text"]["text"].endswith("…")
    assert rendered["value"] == "opaque"
    assert add_catalog_plan_reaction(empty_state, option).rows[0].label == label
```

- [ ] **Step 2: Write failing metadata, input-merge, and value-preservation tests**

```python
def test_metadata_round_trip_is_versioned_bounded_and_preview_has_no_target(editor_state):
    encoded = encode_practice_reaction_metadata(
        mode="preview", context={"preview": True}, state=editor_state,
        preview_config=PREVIEW_CONFIG,
    )
    assert len(encoded) <= 3000
    mode, context, decoded, preview = decode_practice_reaction_metadata(encoded)
    assert mode == "preview"
    assert context == {"preview": True}
    assert decoded.rows[0].emoji == "evergreen_tree"
    assert preview == PREVIEW_CONFIG
    assert "practice_id" not in encoded


def test_metadata_rejects_unknown_version_and_oversize(editor_state):
    with pytest.raises(PlanReactionValidationError, match="metadata version"):
        decode_practice_reaction_metadata('{"v":99,"m":"preview","c":{},"s":{}}')
    with pytest.raises(PlanReactionValidationError, match="3,000"):
        encode_practice_reaction_metadata(
            mode="preview", context={"preview": True}, state=editor_state,
            preview_config={"padding": "x" * 3000},
        )


def test_merge_keeps_temporary_blank_and_removed_description_from_metadata(editor_state):
    values = {
        "practice_reaction_row_r0": {
            "practice_reaction_description": {"type": "plain_text_input", "value": ""}
        }
    }
    merged = merge_practice_reaction_inputs(editor_state, values)
    assert merged.rows[0].label == ""
    removed = remove_plan_reaction(merged, "r0")
    encoded = encode_practice_reaction_metadata(
        mode="create", context={"date": "2026-07-14"}, state=removed
    )
    assert decode_practice_reaction_metadata(encoded)[2].rows[0].label == ""


def test_current_values_replace_builder_defaults_without_trusting_option_text(create_blocks):
    values = {
        "workout_block": {"workout_description": {"value": "Edited workout"}},
        "activities_block": {"activity_ids": {"selected_options": [
            {"value": "2", "text": {"text": "UNTRUSTED"}}
        ]}},
        "flags_block": {"practice_flags": {"selected_options": []}},
    }
    apply_current_view_values(create_blocks, values)
    blocks = _blocks_by_id(create_blocks)
    assert blocks["workout_block"]["element"]["initial_value"] == "Edited workout"
    assert blocks["activities_block"]["element"]["initial_options"] == [
        blocks["activities_block"]["element"]["options"][1]
    ]
    assert "initial_options" not in blocks["flags_block"]["element"]


def test_submission_errors_attach_to_exact_description_block(editor_state):
    values = {"practice_reaction_row_r0": {
        "practice_reaction_description": {"value": ""}
    }}
    rows, errors = parse_practice_reaction_submission(editor_state, values)
    assert rows is None
    assert errors == {
        "practice_reaction_row_r0": "Enter a description for :evergreen_tree:."
    }


def test_retryable_lookup_error_view_keeps_current_values(create_view):
    values = create_view["state"]["values"]
    values["workout_block"]["workout_description"]["value"] = "Unsaved workout"
    rebuilt = build_retryable_practice_reaction_error_view(
        create_view, values, "Could not load reaction Settings. Try again."
    )
    blocks = _blocks_by_id(rebuilt["blocks"])
    assert blocks["workout_block"]["element"]["initial_value"] == "Unsaved workout"
    assert "Try again" in blocks["practice_reaction_lookup_error"]["text"]["text"]
    assert "state" not in rebuilt and "id" not in rebuilt and "hash" not in rebuilt
```

- [ ] **Step 3: Update modal tests to require structured rows and resolver-derived Preview**

Replace assertions for `plan_reactions_block` with:

```python
def test_create_uses_structured_reactions_and_dispatching_selectors(create_modal):
    blocks = _blocks_by_id(create_modal["blocks"])
    assert "plan_reactions_block" not in blocks
    assert blocks["activities_block"]["dispatch_action"] is True
    assert blocks["types_block"]["dispatch_action"] is True
    assert "practice_reaction_row_r0" in blocks
    assert decode_practice_reaction_metadata(
        create_modal["private_metadata"]
    )[0] == "create"


def test_full_edit_has_restore_and_protected_saved_rows(edit_modal):
    blocks = _blocks_by_id(edit_modal["blocks"])
    action_ids = [
        element["action_id"] for block in blocks.values()
        for element in block.get("elements", [])
    ]
    assert "practice_reaction_restore" in action_ids
    assert "plan_reactions_block" not in blocks


def test_preview_derives_four_rows_from_interval_run_and_rollerski_sources():
    modal = build_practice_preview_modal(PREVIEW_DATE)
    blocks = _blocks_by_id(modal["blocks"])
    assert [
        blocks[f"practice_reaction_key_r{i}"]["text"]["text"]
        for i in range(4)
    ] == [
        "*:evergreen_tree:*", "*:athletic_shoe:*", "*:hatching_chick:*",
        "*:older_adult::skin-tone-4:*",
    ]
    assert [option["value"] for option in
            blocks["activities_block"]["element"]["initial_options"]] == ["1", "2"]
    mode, context, _state, preview = decode_practice_reaction_metadata(
        modal["private_metadata"]
    )
    assert mode == "preview" and context == {"preview": True}
    assert preview["activities"][2]["name"] == "Strength"
```

- [ ] **Step 4: Run the focused Slack tests and verify freeform-contract failures**

Run:

```bash
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= \
env/bin/pytest \
  tests/slack/test_practice_reaction_editor.py \
  tests/slack/test_practice_create_modal.py \
  tests/slack/test_practice_edit_full.py \
  tests/slack/test_practice_preview.py -q
```

Expected: new module imports fail and existing multiline/empty-preview-metadata expectations fail until replaced.

- [ ] **Step 5: Implement the Block Kit renderer and bounded catalog**

Create these constants and IDs in `practice_reaction_editor.py`:

```python
PRACTICE_REACTION_METADATA_VERSION = 1
SLACK_PRIVATE_METADATA_MAX_CHARS = 3000
SLACK_REACTION_CATALOG_MAX_OPTIONS = 100
SLACK_OPTION_TEXT_MAX_CHARS = 75

DESCRIPTION_ACTION_ID = "practice_reaction_description"
REMOVE_ACTION_ID = "practice_reaction_remove"
UNDO_ACTION_ID = "practice_reaction_undo"
ADD_ACTION_ID = "practice_reaction_add"
CATALOG_ACTION_ID = "practice_reaction_catalog_select"
RESTORE_ACTION_ID = "practice_reaction_restore"
```

For each active row emit exactly three blocks: `practice_reaction_key_<row_id>` Section with full fixed shortcode, `practice_reaction_row_<row_id>` optional Input with one plain-text input and 80-character limit, and `practice_reaction_controls_<row_id>` Actions with Remove. For each removed row emit one `practice_reaction_removed_<row_id>` Section containing the shortcode, escaped last description, visible `_Removed_`, and an Undo button accessory. Button values are row IDs. Bound every Slack button `accessibility_label` to 75 characters with a final ellipsis when necessary; the adjacent key block always retains the full shortcode. When no rows exist, emit `practice_reaction_empty` with neutral `No Plan reactions are set for this practice.` before the conditional Add control.

Append a neutral Context block naming `state.unconfigured_activity_names`. Append a blocking-error Section when present. Show Add only when `state.effective_inherited_count == 0 or state.unconfigured_activity_names`, no blocking error exists, and fewer than four slots are reserved. `state.add_open=False` renders an Add button; true renders a static select filtered by every active/removed emoji. If the complete catalog is empty, render `Configure reaction pairs in Practices Settings first.` If it has more than 100 distinct pairs, render an error containing `more than 100`. Ellipsize `:<emoji>: <label>` to 75 characters with a final `…` while retaining `option_id` as the value. Include Restore in the footer only when `allow_restore=True`.

- [ ] **Step 6: Implement compact metadata and safe input rebuilding**

Encode:

```python
envelope = {
    "v": PRACTICE_REACTION_METADATA_VERSION,
    "m": mode,
    "c": context,
    "s": serialize_plan_reaction_editor_state(
        state, omit_active_labels=True
    ),
}
if preview_config is not None:
    envelope["p"] = preview_config
raw = json.dumps(envelope, separators=(",", ":"), ensure_ascii=True)
if len(raw) > SLACK_PRIVATE_METADATA_MAX_CHARS:
    raise PlanReactionValidationError(
        "Practice reaction metadata exceeds Slack's 3,000-character limit"
    )
```

Allow only modes `create`, `edit`, and `preview`; require Preview context to be exactly `{"preview": True}` and forbid a `practice_id` or other database-target field in Preview context/config. Synthetic selector source IDs are required and allowed. Decode through Task 2's hostile-payload validator.

`merge_practice_reaction_inputs()` clones state and replaces each active row label only when its exact block/action exists; removed labels remain from metadata. `parse_practice_reaction_submission()` merges then validates each active row, returning `(None, {block_id: message})` for blank/too-long labels and `(snapshot, {})` otherwise.

`apply_current_view_values()` walks rebuilt blocks by block/action ID. For plain text and timepicker values, replace/remove `initial_value`/`initial_time`; for select/checkbox values, map submitted values back to the builder's canonical `options` and replace/remove initial selections. Never copy submitted option text.

`build_retryable_practice_reaction_error_view()` copies only Slack-writable view keys (`type`, `callback_id`, `private_metadata`, `title`, `submit`, `close`, `notify_on_close`, and deep-copied `blocks`), inserts a `practice_reaction_lookup_error` Section with the supplied retryable message, and applies all current values. It must never return Slack read-only `id`, `hash`, `state`, `team_id`, or timestamps.

- [ ] **Step 7: Refactor modal builders to accept prepared state/catalog**

Change the production builder tails to keyword-only inputs:

```python
def build_practice_create_modal(
    practice_date, default_time, locations=None, channel_id=None,
    message_ts=None, all_activities=None, all_types=None,
    slot_defaults=None, silent_defaults=None, eligible_coaches=None,
    eligible_leads=None, *, reaction_editor, reaction_catalog,
    current_values=None, view_mode="create", preview_config=None,
) -> dict:
```

```python
def build_practice_edit_full_modal(
    practice, locations=None, eligible_coaches=None, eligible_leads=None,
    all_activities=None, all_types=None, *, reaction_editor,
    reaction_catalog, current_values=None,
) -> dict:
```

Set selector Input-block `dispatch_action` to true, remove the multiline block, append structured blocks in its place, and encode original context under mode `create`/`edit`. Apply `current_values` after the complete modal is built.

Rebuild Preview from synthetic `SimpleNamespace` Settings sources:

```python
intervals = SimpleNamespace(
    id=1, name="Intervals", default_plan_reactions=[EVERGREEN_PLAN_REACTION]
)
run = SimpleNamespace(
    id=1, name="Run",
    default_plan_reactions=[{"emoji": "athletic_shoe", "label": "runner"}],
)
rollerski = SimpleNamespace(
    id=2, name="Skate/Classic Rollerski", default_plan_reactions=[
        {"emoji": "hatching_chick", "label": "new rollerskier"},
        {"emoji": "older_adult::skin-tone-4", "label": "experienced rollerskier"},
    ],
)
strength = SimpleNamespace(id=3, name="Strength", default_plan_reactions=[])
```

Select Run + Rollerski, derive state through `build_plan_reaction_editor_state`, build the catalog through the production catalog builder, include all three Activities in the selector/config, and call the production Create builder with `view_mode="preview"`. Keep the existing Preview title/submit/callback. Preview metadata is now intentionally nonempty and versioned.

Update every existing production modal-opening call site in `bolt_app.py` in the same commit so no caller can invoke the new required builder arguments. Create-summary opening strictly loads its configured selected sources, builds current defaults with `saved_snapshot=None`, and passes the global catalog. Full Edit opening builds from the Practice's current relations and `saved_snapshot=practice.plan_reactions or []`, then passes the global catalog. Preserve all existing authorization checks; action/submission listeners remain unchanged until Task 6.

- [ ] **Step 8: Run focused Slack rendering tests**

Run the Step 4 command again.

Expected: all renderer, modal, metadata, option-bound, current-value, and Preview structure tests pass. Submission/action behavior remains for Task 6.

- [ ] **Step 9: Commit the Slack renderer and modal migration**

```bash
git add app/slack/practice_reaction_editor.py app/slack/modals.py app/slack/bolt_app.py \
  tests/slack/test_practice_reaction_editor.py \
  tests/slack/test_practice_create_modal.py \
  tests/slack/test_practice_edit_full.py \
  tests/slack/test_practice_preview.py
git commit -m "feat(slack): render structured practice reactions"
```

### Task 6: Wire Slack Actions and Authoritative Submissions

**Files:**

- Modify: `app/slack/bolt_app.py`
- Modify: `tests/slack/test_practice_reaction_editor.py`
- Modify: `tests/slack/test_practice_create_modal.py`
- Modify: `tests/slack/test_practice_edit_full.py`
- Modify: `tests/slack/test_practice_preview.py`

**Interfaces:**

- Produces always-importable `_handle_practice_reaction_action(ack, body, action, client, logger) -> None` and `_handle_practice_create_submission(ack, body, view, client, logger) -> dict | None` alongside the existing Full Edit helper.
- All seven action IDs (`activity_ids`, `type_ids`, Remove, Undo, Add, catalog select, Restore) delegate to the one handler.
- Production actions reload authoritative Settings/source records. Preview actions reconstruct only committed synthetic config and never enter application context.

- [ ] **Step 1: Write failing action-order, view-hash, and zero-persistence Preview tests**

Add event-recording test doubles and these tests:

```python
def test_reaction_action_acks_before_rebuild_and_updates_with_view_hash(preview_action_body):
    events = []
    client = MagicMock()
    client.views_update.side_effect = lambda **kwargs: events.append(("update", kwargs))
    _handle_practice_reaction_action(
        ack=lambda: events.append(("ack", None)), body=preview_action_body,
        action={"action_id": "practice_reaction_remove", "value": "r0"},
        client=client, logger=MagicMock(),
    )
    assert events[0][0] == "ack"
    assert events[1][1]["view_id"] == "V_PREVIEW"
    assert events[1][1]["hash"] == "HASH_PREVIEW"
    removed = _blocks_by_id(events[1][1]["view"]["blocks"])
    assert "practice_reaction_removed_r0" in removed


def test_preview_action_never_opens_application_context(preview_action_body, monkeypatch):
    monkeypatch.setattr(
        bolt_module, "get_app_context",
        lambda: (_ for _ in ()).throw(AssertionError("Preview touched app context")),
    )
    _handle_practice_reaction_action(
        ack=lambda: None, body=preview_action_body,
        action={"action_id": "activity_ids"},
        client=MagicMock(), logger=MagicMock(),
    )


def test_remove_accepts_temporarily_blank_description(preview_action_body):
    preview_action_body["view"]["state"]["values"][
        "practice_reaction_row_r0"
    ]["practice_reaction_description"]["value"] = ""
    client = MagicMock()
    _handle_practice_reaction_action(
        ack=lambda: None, body=preview_action_body,
        action={"action_id": "practice_reaction_remove", "value": "r0"},
        client=client, logger=MagicMock(),
    )
    metadata = client.views_update.call_args.kwargs["view"]["private_metadata"]
    assert decode_practice_reaction_metadata(metadata)[2].rows[0].label == ""


def test_views_update_failure_is_logged_and_does_not_persist(preview_action_body):
    logger = MagicMock()
    client = MagicMock()
    client.views_update.side_effect = RuntimeError("Slack unavailable")
    _handle_practice_reaction_action(
        ack=lambda: None, body=preview_action_body,
        action={"action_id": "practice_reaction_remove", "value": "r0"},
        client=client, logger=logger,
    )
    logger.exception.assert_called_once()


def test_settings_lookup_failure_preserves_modal_and_surfaces_retry(production_action_body, monkeypatch):
    monkeypatch.setattr(
        bolt_module, "load_all_plan_reaction_sources",
        lambda _session: (_ for _ in ()).throw(RuntimeError("database unavailable")),
    )
    client = MagicMock()
    _handle_practice_reaction_action(
        ack=lambda: None, body=production_action_body,
        action={"action_id": "practice_reaction_add"},
        client=client, logger=MagicMock(),
    )
    updated = _blocks_by_id(client.views_update.call_args.kwargs["view"]["blocks"])
    assert "Try again" in updated["practice_reaction_lookup_error"]["text"]["text"]
    assert updated["workout_block"]["element"]["initial_value"] == "Unsaved workout"


def test_preview_submission_remains_ack_only_after_interactivity(monkeypatch):
    ack = MagicMock()
    monkeypatch.setattr(
        bolt_module, "get_app_context",
        lambda: (_ for _ in ()).throw(AssertionError("submission touched database")),
    )
    _handle_practice_preview_submission(ack)
    ack.assert_called_once_with()
```

- [ ] **Step 2: Write failing transition, Add, Restore, and unrelated-value tests**

```python
def test_preview_selector_transition_one_two_three_one_reconciles_only_rows(
    preview_action_body
):
    client = MagicMock()
    values = preview_action_body["view"]["state"]["values"]
    values["workout_block"]["workout_description"]["value"] = "Do not lose me"
    values["activities_block"]["activity_ids"]["selected_options"] = [
        {"value": "1"}
    ]
    _handle_practice_reaction_action(
        lambda: None, preview_action_body, {"action_id": "activity_ids"},
        client, MagicMock(),
    )
    one = client.views_update.call_args.kwargs["view"]
    blocks = _blocks_by_id(one["blocks"])
    assert blocks["workout_block"]["element"]["initial_value"] == "Do not lose me"
    assert [key for key in blocks if key.startswith("practice_reaction_row_")] == [
        "practice_reaction_row_r0"
    ]


def test_add_then_catalog_select_appends_configured_fixed_key(preview_action_body):
    client = MagicMock()
    _handle_practice_reaction_action(
        lambda: None, preview_action_body,
        {"action_id": "practice_reaction_add"}, client, MagicMock(),
    )
    opened = client.views_update.call_args.kwargs["view"]
    option = _blocks_by_id(opened["blocks"])[
        "practice_reaction_catalog_block"
    ]["elements"][0]["options"][0]
    next_body = _action_body_from_view(opened)
    _handle_practice_reaction_action(
        lambda: None, next_body,
        {"action_id": "practice_reaction_catalog_select",
         "selected_option": {"value": option["value"]}},
        client, MagicMock(),
    )
    final = client.views_update.call_args.kwargs["view"]
    assert any(
        option["value"] in block.get("text", {}).get("text", "")
        for block in final["blocks"]
    ) is False  # opaque option IDs never become visible text


def test_full_edit_restore_preserves_every_nonreaction_value(full_edit_action_body):
    client = MagicMock()
    before = full_edit_action_body["view"]["state"]["values"]
    before["notes_block"]["logistics_notes"]["value"] = "Keep these notes"
    _handle_practice_reaction_action(
        lambda: None, full_edit_action_body,
        {"action_id": "practice_reaction_restore"}, client, MagicMock(),
    )
    updated = _blocks_by_id(client.views_update.call_args.kwargs["view"]["blocks"])
    assert updated["notes_block"]["element"]["initial_value"] == "Keep these notes"


def test_restore_conflict_keeps_reaction_state_unchanged(full_edit_action_body, conflicting_settings):
    before = decode_practice_reaction_metadata(
        full_edit_action_body["view"]["private_metadata"]
    )[2]
    client = MagicMock()
    _handle_practice_reaction_action(
        lambda: None, full_edit_action_body,
        {"action_id": "practice_reaction_restore"}, client, MagicMock(),
    )
    after = decode_practice_reaction_metadata(
        client.views_update.call_args.kwargs["view"]["private_metadata"]
    )[2]
    assert [(row.emoji, row.label, row.removed) for row in after.rows] == [
        (row.emoji, row.label, row.removed) for row in before.rows
    ]
    assert after.blocking_error
```

- [ ] **Step 3: Write failing Create and Full Edit server-validation tests**

Update multiline parsing tests to structured metadata/state. Add:

```python
def test_create_submission_rejects_unknown_activity_before_persistence(
    app, create_view, monkeypatch
):
    _select_values(create_view)["activities_block"]["activity_ids"][
        "selected_options"
    ] = [{"value": "999999"}]
    ack = MagicMock()
    _handle_practice_create_submission(
        ack, CREATE_BODY, create_view, MagicMock(), MagicMock()
    )
    assert ack.call_args.kwargs["response_action"] == "errors"
    assert "activities_block" in ack.call_args.kwargs["errors"]


def test_create_submission_rejects_metadata_tampered_emoji(
    app, create_view
):
    mode, context, state, _ = decode_practice_reaction_metadata(
        create_view["private_metadata"]
    )
    state.rows[0].emoji = "tampered"
    create_view["private_metadata"] = encode_practice_reaction_metadata(
        mode=mode, context=context, state=state
    )
    ack = MagicMock()
    _handle_practice_create_submission(
        ack, CREATE_BODY, create_view, MagicMock(), MagicMock()
    )
    assert ack.call_args.kwargs["response_action"] == "errors"
    assert "not configured in Settings" in next(iter(
        ack.call_args.kwargs["errors"].values()
    ))


def test_full_edit_accepts_saved_key_missing_from_settings(
    app, saved_unconfigured_practice, full_edit_view
):
    ack = MagicMock()
    result = _handle_practice_edit_full_submission(
        ack=ack, body=EDIT_BODY, view=full_edit_view,
        client=MagicMock(), logger=MagicMock(),
    )
    ack.assert_called_once_with()
    assert result["practice_updated"] is True


def test_catalog_key_deleted_while_modal_open_preserves_text_but_blocks_save(
    app, db_session, configured_activity, full_edit_view
):
    configured_activity.default_plan_reactions = []
    db_session.commit()
    ack = MagicMock()
    _handle_practice_edit_full_submission(
        ack=ack, body=EDIT_BODY, view=full_edit_view,
        client=MagicMock(), logger=MagicMock(),
    )
    assert ack.call_args.kwargs["response_action"] == "errors"
    errors = ack.call_args.kwargs["errors"]
    assert any("not configured in Settings" in message for message in errors.values())
```

- [ ] **Step 4: Run focused tests and verify missing action/submission behavior**

Run:

```bash
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= \
env/bin/pytest \
  tests/slack/test_practice_reaction_editor.py \
  tests/slack/test_practice_create_modal.py \
  tests/slack/test_practice_edit_full.py \
  tests/slack/test_practice_preview.py -q
```

Expected: action helper imports/listeners fail, Create still parses the removed multiline field, and Full Edit accepts tampered keys.

- [ ] **Step 5: Register thin listeners and implement one action controller**

Register:

```python
for action_id in (
    "activity_ids", "type_ids", REMOVE_ACTION_ID, UNDO_ACTION_ID,
    ADD_ACTION_ID, CATALOG_ACTION_ID, RESTORE_ACTION_ID,
):
    bolt_app.action(action_id)(
        lambda ack, body, action, client, logger:
            _handle_practice_reaction_action(ack, body, action, client, logger)
    )
```

Avoid late-bound loop capture by not referencing `action_id` inside the lambda. The controller must:

1. call `ack()` as its first effect;
2. decode metadata and merge exact current reaction descriptions;
3. read distinct selected Activity/Type option values from the complete current view state;
4. for Preview, rebuild synthetic sources/catalog solely from decoded `preview_config`;
5. for Create/Edit, enter `get_app_context()`, use Task 1's strict loaders, load the global catalog, and load modal reference records/people/practice;
6. reconcile for selector actions, mark `add_open` for Add, resolve opaque catalog option and add it, Remove/Undo by opaque row ID, or resolve-first Restore for Full Edit;
7. rebuild the same modal mode with `current_values=values`; and
8. call `client.views_update(view_id=view["id"], hash=view["hash"], view=modal)`.

On invalid selectors/conflict/overflow, preserve rows, set `blocking_error`, close Add, and rebuild with the selected values still visible. On Settings lookup failure, log with `logger.exception` and call `views_update` with `build_retryable_practice_reaction_error_view()` so current rows/inputs remain and `Could not load reaction Settings. Try again.` is visible. If that update or an ordinary `views_update` fails, log it; do not mutate data, and leave the current modal open/usable.

- [ ] **Step 6: Extract and authorize Create submission**

Move the nested Create callback body into always-defined `_handle_practice_create_submission()`. Decode mode `create`, parse non-reaction authoring fields, strictly load selected sources, resolve current defaults to catch conflicts/overflow, load the global catalog, parse row-specific descriptions, and call:

```python
plan_reactions = validate_authorized_plan_reactions(
    submitted_rows, catalog=catalog, protected_snapshot=(),
)
```

Map malformed/unknown Activity and Type errors to `activities_block`/`types_block`; map resolver errors via `exc.field`; map incomplete rows to their exact `practice_reaction_row_<row_id>`; and map unauthorized emoji to its current row block. Only after all validation succeeds construct the Practice with `plan_reactions=plan_reactions`, assign the exact loaded relationships, commit, `ack()`, and start the existing best-effort post-update thread. No error path may add/flush/commit a Practice.

Change `_parse_practice_authoring_values()` to parse only workout and optional Notes; remove `include_plan_reactions` and every `parse_plan_reaction_lines()` call.

- [ ] **Step 7: Revalidate Full Edit before acknowledgment or mutation**

Decode mode `edit` and its practice ID, load the Practice, strict selected sources, resolver, global catalog, and structured descriptions. Authorize with:

```python
plan_reactions = validate_authorized_plan_reactions(
    submitted_rows,
    catalog=catalog,
    protected_snapshot=practice.plan_reactions or [],
)
```

Return `ack(response_action="errors", errors=...)` before mutation on any failure. On success, call `ack()`, retain the previous snapshot for reaction cleanup/refresh, assign the validated rows and exact source relations, and leave existing notification, refresh, saved-but-unsynced, and DM behavior unchanged.

- [ ] **Step 8: Run focused Slack and adjacent announcement regressions**

Run:

```bash
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= \
env/bin/pytest \
  tests/slack/test_practice_reaction_editor.py \
  tests/slack/test_practice_create_modal.py \
  tests/slack/test_practice_edit_full.py \
  tests/slack/test_practice_preview.py \
  tests/slack/test_practice_posting.py \
  tests/practices/test_plan_reactions.py -q
```

Expected: all tests pass; Preview command guard/open-failure/ordinary-routing tests remain green and submission remains zero-persistence.

- [ ] **Step 9: Commit Slack interactivity and validation**

```bash
git add app/slack/bolt_app.py \
  tests/slack/test_practice_reaction_editor.py \
  tests/slack/test_practice_create_modal.py \
  tests/slack/test_practice_edit_full.py \
  tests/slack/test_practice_preview.py
git commit -m "feat(slack): make practice reactions interactive"
```

### Task 7: Commit Historical Evidence and a Digest-Approved Seed Operation

**Files:**

- Create: `scripts/data/2026-07-15-practice-plan-reaction-history.json`
- Create: `scripts/seed_practice_plan_reaction_defaults.py`
- Create: `tests/scripts/test_seed_practice_plan_reaction_defaults.py`

**Interfaces:**

- The manifest separates observations from approved targets; the command consumes only `approved_targets`.
- The command requires `--environment {local,production}` plus exactly one of `--dry-run` or `--commit`; commit also requires `--approve <dry-run-digest>`.
- The operation uses a plain SQLAlchemy engine/session and imports neither Slack clients nor `create_app()`.

- [ ] **Step 1: Commit the reviewed extraction manifest exactly**

Create the JSON with this extraction envelope and evidence. Keep excerpts deliberately minimal; the message hashes bind them to the reviewed Slack records without committing full private posts.

```json
{
  "schema_version": 1,
  "extraction": {
    "channel_id": "C042G463AQ1",
    "channel_name": "announcements-practices",
    "extracted_at_utc": "2026-07-15T17:05:15Z",
    "history_pages": 6,
    "returned_messages": 1097,
    "raw_extract_sha256": "cec3462bc1a7cb4aa2e09b66a26b0c6ec5aaa5448f5f3498a1f42ee22d19674e"
  },
  "review": {
    "state": "approved",
    "reviewed_on": "2026-07-15",
    "reviewer": "announcement-format design review",
    "note": "Approved normalization follows the current 2026 reaction grammar; observations are never promoted at runtime."
  },
  "evidence": [
    {
      "id": "weekly-multisport-2024-07-02",
      "message_ts": "1719804485.929409",
      "posted_at_central": "2024-06-30T22:28:05.929409-05:00",
      "practice_date": "2024-07-02",
      "message_sha256": "fbdb2025a273cbe3094c07789ab060415380c2365e1446ef0eeed0cb74ab564d",
      "excerpt": "Multisport used runner, bike, and snowflake choices.",
      "observed_activities": ["Run", "Bike", "Rollerski"],
      "normalized_pairs": [],
      "confidence": "supporting",
      "review_state": "approved_evidence"
    },
    {
      "id": "trail-multisport-2024-08-27",
      "message_ts": "1724770515.276249",
      "posted_at_central": "2024-08-27T09:55:15.276249-05:00",
      "practice_date": "2024-08-27",
      "message_sha256": "43cca321704aea8233f52a7b92b27f5a4c13abb17b68c36c70230b9a0f045b91",
      "excerpt": "Trail run, skate rollerski, or mountain bike used activity reactions.",
      "observed_activities": ["Run", "Skate Rollerski", "Mountain Bike"],
      "normalized_pairs": [
        {"emoji": "mountain_bicyclist", "label": "mountain biker"}
      ],
      "confidence": "direct",
      "review_state": "approved_evidence"
    },
    {
      "id": "summer-multisport-2025-07-13",
      "message_ts": "1752029138.964859",
      "posted_at_central": "2025-07-08T21:45:38.964859-05:00",
      "practice_date": "2025-07-13",
      "message_sha256": "01588553f8181603c6f3c9faf1002c38fc7ee22e22c19baff6c914deb89b67e3",
      "excerpt": "Run, rollerski, and bike choices recurred on a multisport practice.",
      "observed_activities": ["Run", "Rollerski", "Bike"],
      "normalized_pairs": [],
      "confidence": "supporting",
      "review_state": "approved_evidence"
    },
    {
      "id": "interval-practice-2026-02-03",
      "message_ts": "1770084008.307079",
      "posted_at_central": "2026-02-02T20:00:08.307079-06:00",
      "practice_date": "2026-02-03",
      "message_sha256": "16d9ac0b60b5899eebe2356d37e6644d7d21f5cd5d5ed7112d2d44fa57db11ae",
      "excerpt": "Interval practice root carried the endurance reaction option.",
      "observed_workout_types": ["has_intervals"],
      "normalized_pairs": [
        {"emoji": "evergreen_tree", "label": "Endurance instead of intervals"}
      ],
      "confidence": "direct",
      "review_state": "approved_evidence"
    },
    {
      "id": "interval-policy-2026-02-03",
      "message_ts": "1770089703.614499",
      "posted_at_central": "2026-02-02T21:35:03.614499-06:00",
      "practice_date": "2026-02-03",
      "message_sha256": "bac4188034ee0bce192ef2ad2b540a83cefc7f1e35fa3e1e0c124c403cc60d59",
      "excerpt": "The channel states the endurance option appears on practices tagged with intervals.",
      "observed_workout_types": ["has_intervals"],
      "normalized_pairs": [
        {"emoji": "evergreen_tree", "label": "Endurance instead of intervals"}
      ],
      "confidence": "policy",
      "review_state": "approved_evidence"
    },
    {
      "id": "rollerski-run-2026-06-02",
      "message_ts": "1780405202.087649",
      "posted_at_central": "2026-06-02T08:00:02.087649-05:00",
      "practice_date": "2026-06-02",
      "message_sha256": "df829b451087835235022187ba851a4979440d8172abc6508100a292930243f1",
      "excerpt": "Rollerski plus Run used new rollerskier, experienced rollerskier, and runner choices.",
      "observed_activities": ["Skate/Classic Rollerski", "Run"],
      "normalized_pairs": [
        {"emoji": "hatching_chick", "label": "new rollerskier"},
        {"emoji": "older_adult::skin-tone-4", "label": "experienced rollerskier"},
        {"emoji": "athletic_shoe", "label": "runner"}
      ],
      "confidence": "direct",
      "review_state": "approved_evidence"
    },
    {
      "id": "run-bike-rollerski-2026-06-16",
      "message_ts": "1781614801.941199",
      "posted_at_central": "2026-06-16T08:00:01.941199-05:00",
      "practice_date": "2026-06-16",
      "message_sha256": "d07c2e272e61a17ced5a60d92d2f69b20fd547fe7aa1bd5a0ec23c608332c83c",
      "excerpt": "Run, Bike, and Skate/Classic Rollerski used a bike activity choice.",
      "observed_activities": ["Run", "Bike", "Skate/Classic Rollerski"],
      "normalized_pairs": [
        {"emoji": "bike", "label": "bike"}
      ],
      "confidence": "direct",
      "review_state": "approved_evidence"
    },
    {
      "id": "rollerski-run-2026-07-07",
      "message_ts": "1783429201.952879",
      "posted_at_central": "2026-07-07T08:00:01.952879-05:00",
      "practice_date": "2026-07-07",
      "message_sha256": "8d36368cbbc1856c4f6c86ad71b46f80385f41c335a615da5b8c5a73b0b15ca7",
      "excerpt": "Skate/Classic Rollerski plus Run repeated the approved three-choice grammar.",
      "observed_activities": ["Skate/Classic Rollerski", "Run"],
      "normalized_pairs": [
        {"emoji": "hatching_chick", "label": "new rollerskier"},
        {"emoji": "older_adult::skin-tone-4", "label": "experienced rollerskier"},
        {"emoji": "athletic_shoe", "label": "runner"}
      ],
      "confidence": "direct",
      "review_state": "approved_evidence"
    }
  ],
  "approved_targets": [
    {
      "kind": "workout_type_selector",
      "selector": {"has_intervals": true},
      "defaults": [
        {"emoji": "evergreen_tree", "label": "Endurance instead of intervals"}
      ],
      "evidence_ids": ["interval-practice-2026-02-03", "interval-policy-2026-02-03"]
    },
    {
      "kind": "activity",
      "name": "Run",
      "defaults": [{"emoji": "athletic_shoe", "label": "runner"}],
      "evidence_ids": ["rollerski-run-2026-06-02", "rollerski-run-2026-07-07"]
    },
    {
      "kind": "activity",
      "name": "Bike",
      "defaults": [{"emoji": "bike", "label": "bike"}],
      "evidence_ids": ["run-bike-rollerski-2026-06-16"]
    },
    {
      "kind": "activity",
      "name": "Mountain Bike",
      "defaults": [{"emoji": "mountain_bicyclist", "label": "mountain biker"}],
      "evidence_ids": ["trail-multisport-2024-08-27"]
    },
    {
      "kind": "activity",
      "name": "Classic Rollerski",
      "defaults": [
        {"emoji": "hatching_chick", "label": "new rollerskier"},
        {"emoji": "older_adult::skin-tone-4", "label": "experienced rollerskier"}
      ],
      "normalization_note": "Approved current Rollerski grammar applies to each exact Rollerski Activity.",
      "evidence_ids": ["rollerski-run-2026-06-02", "rollerski-run-2026-07-07"]
    },
    {
      "kind": "activity",
      "name": "Skate Rollerski",
      "defaults": [
        {"emoji": "hatching_chick", "label": "new rollerskier"},
        {"emoji": "older_adult::skin-tone-4", "label": "experienced rollerskier"}
      ],
      "normalization_note": "Approved current Rollerski grammar applies to each exact Rollerski Activity.",
      "evidence_ids": ["rollerski-run-2026-06-02", "rollerski-run-2026-07-07"]
    },
    {
      "kind": "activity",
      "name": "Skate/Classic Rollerski",
      "defaults": [
        {"emoji": "hatching_chick", "label": "new rollerskier"},
        {"emoji": "older_adult::skin-tone-4", "label": "experienced rollerskier"}
      ],
      "evidence_ids": ["rollerski-run-2026-06-02", "rollerski-run-2026-07-07"]
    }
  ]
}
```

- [ ] **Step 2: Write failing manifest and dry-run safety tests**

Use real SQLAlchemy model rows in the test database; mock no ORM behavior. Add:

```python
def test_manifest_records_complete_reviewed_scope():
    manifest = load_manifest(MANIFEST_PATH)
    assert manifest["extraction"] == {
        "channel_id": "C042G463AQ1",
        "channel_name": "announcements-practices",
        "extracted_at_utc": "2026-07-15T17:05:15Z",
        "history_pages": 6,
        "returned_messages": 1097,
        "raw_extract_sha256": "cec3462bc1a7cb4aa2e09b66a26b0c6ec5aaa5448f5f3498a1f42ee22d19674e",
    }
    assert manifest["review"]["state"] == "approved"
    assert len(manifest["approved_targets"]) == 7


def test_only_approved_targets_are_consumed(seed_session, complete_targets):
    manifest = load_manifest(MANIFEST_PATH)
    manifest["evidence"].append({
        "id": "unapproved", "normalized_pairs": [{"emoji": "fire", "label": "fast"}],
        "review_state": "observation",
    })
    plan = build_seed_plan(seed_session, manifest, lock=False)
    assert "fire" not in json.dumps(plan.to_dict())


def test_dry_run_classifies_empty_exact_and_conflict_without_mutation(
    seed_session, complete_targets
):
    run = complete_targets["Run"]
    bike = complete_targets["Bike"]
    bike.default_plan_reactions = [{"emoji": "bike", "label": "bike"}]
    run.default_plan_reactions = [{"emoji": "shoe", "label": "custom admin value"}]
    seed_session.commit()
    before = copy.deepcopy(run.default_plan_reactions)
    plan = build_seed_plan(seed_session, load_manifest(MANIFEST_PATH), lock=False)
    assert plan.has_conflicts is True
    assert plan.change_for("Run").status == "conflict"
    assert plan.change_for("Bike").status == "exact"
    assert plan.change_for("Mountain Bike").status == "fill"
    assert run.default_plan_reactions == before


def test_target_name_or_count_drift_aborts(seed_session, complete_targets):
    seed_session.delete(complete_targets["Classic Rollerski"])
    seed_session.commit()
    with pytest.raises(SeedPlanError, match="expected 6 exact Activity targets"):
        build_seed_plan(seed_session, load_manifest(MANIFEST_PATH), lock=False)


def test_interval_types_are_selected_by_boolean_not_name(seed_session, complete_targets):
    unusual = PracticeType(name="Not Named Intervals", has_intervals=True)
    misleading = PracticeType(name="Intervals by name only", has_intervals=False)
    seed_session.add_all([unusual, misleading])
    seed_session.commit()
    plan = build_seed_plan(seed_session, load_manifest(MANIFEST_PATH), lock=False)
    assert list(plan.change_for("Not Named Intervals").desired) == [EVERGREEN_PLAN_REACTION]
    assert plan.change_for("Intervals by name only") is None
```

- [ ] **Step 3: Write failing commit/digest/concurrency/read-back/snapshot tests**

```python
def test_commit_requires_exact_fresh_dry_run_digest(seed_engine, complete_targets):
    manifest = load_manifest(MANIFEST_PATH)
    with Session(seed_engine) as session:
        digest = render_seed_plan(build_seed_plan(session, manifest, lock=False)).digest
    with pytest.raises(SeedPlanError, match="approval digest"):
        commit_seed_plan(seed_engine, manifest, approved_digest="wrong")
    assert commit_seed_plan(seed_engine, manifest, approved_digest=digest).verified


def test_nonempty_conflict_aborts_every_fill(seed_engine, complete_targets):
    with Session(seed_engine) as session:
        complete_targets["Run"].default_plan_reactions = [
            {"emoji": "shoe", "label": "custom"}
        ]
        session.merge(complete_targets["Run"])
        session.commit()
        plan = build_seed_plan(session, load_manifest(MANIFEST_PATH), lock=False)
        digest = render_seed_plan(plan).digest
    with pytest.raises(SeedPlanError, match="different non-empty"):
        commit_seed_plan(seed_engine, load_manifest(MANIFEST_PATH), digest)
    with Session(seed_engine) as session:
        mountain = session.scalar(select(PracticeActivity).where(
            PracticeActivity.name == "Mountain Bike"
        ))
        assert mountain.default_plan_reactions == []


def test_value_drift_after_dry_run_is_caught_by_locked_recheck(
    seed_engine, complete_targets
):
    manifest = load_manifest(MANIFEST_PATH)
    with Session(seed_engine) as session:
        digest = render_seed_plan(build_seed_plan(session, manifest, lock=False)).digest
    with Session(seed_engine) as concurrent:
        run = concurrent.scalar(select(PracticeActivity).where(
            PracticeActivity.name == "Run"
        ))
        run.default_plan_reactions = [{"emoji": "shoe", "label": "concurrent custom"}]
        concurrent.commit()
    with pytest.raises(SeedPlanError, match="approval digest"):
        commit_seed_plan(seed_engine, manifest, digest)


def test_repeat_is_idempotent_and_saved_practice_snapshots_never_change(
    seed_engine, complete_targets, upcoming_multisport_practice
):
    manifest = load_manifest(MANIFEST_PATH)
    original_snapshot = copy.deepcopy(upcoming_multisport_practice.plan_reactions)
    with Session(seed_engine) as session:
        digest = render_seed_plan(build_seed_plan(session, manifest, lock=False)).digest
    commit_seed_plan(seed_engine, manifest, digest)
    with Session(seed_engine) as session:
        repeat = build_seed_plan(session, manifest, lock=False)
        assert all(change.status == "exact" for change in repeat.changes)
        saved = session.get(Practice, upcoming_multisport_practice.id)
        assert saved.plan_reactions == original_snapshot
        assert repeat.upcoming_snapshot_mismatches
```

- [ ] **Step 4: Run seed tests and verify missing operation failures**

Run:

```bash
env/bin/pytest tests/scripts/test_seed_practice_plan_reaction_defaults.py -q
```

Expected: collection fails because the seed module and manifest do not yet exist.

- [ ] **Step 5: Implement manifest validation and canonical seed planning**

The module must expose:

```python
from dataclasses import asdict, dataclass


MANIFEST_PATH = Path(__file__).parent / "data/2026-07-15-practice-plan-reaction-history.json"
APPROVED_ACTIVITY_NAMES = (
    "Run", "Bike", "Mountain Bike", "Classic Rollerski",
    "Skate Rollerski", "Skate/Classic Rollerski",
)


@dataclass(frozen=True)
class SeedChange:
    kind: str
    record_id: int
    name: str
    current: tuple[dict[str, str], ...]
    desired: tuple[dict[str, str], ...]
    status: str  # exact, fill, or conflict


@dataclass(frozen=True)
class SeedPlan:
    changes: tuple[SeedChange, ...]
    upcoming_snapshot_mismatches: tuple[dict, ...]

    @property
    def has_conflicts(self):
        return any(item.status == "conflict" for item in self.changes)

    def change_for(self, name):
        return next((item for item in self.changes if item.name == name), None)

    def to_dict(self):
        return {
            "changes": [asdict(item) for item in self.changes],
            "upcoming_snapshot_mismatches": list(self.upcoming_snapshot_mismatches),
        }


@dataclass(frozen=True)
class RenderedSeedPlan:
    canonical_json: str
    digest: str


@dataclass(frozen=True)
class SeedCommitResult:
    verified: bool
    plan: SeedPlan


class SeedPlanError(RuntimeError):
    pass
```

`load_manifest()` must validate schema version, exact extraction scope, approved review state, unique evidence IDs, every approved target evidence reference, one boolean interval selector, and exactly the six approved Activity names. Pass every desired list through `normalize_plan_reactions()`.

`build_seed_plan(session, manifest, lock=False)` must query all `PracticeType.has_intervals.is_(True)` and exact Activity names; when `lock=True`, both selects use `.with_for_update()`. Require exactly six unique Activity records and at least one interval Type. Classify normalized current equals desired as `exact`, empty as `fill`, and different nonempty as `conflict`. Build upcoming mismatches for noncancelled practices dated today or later with at least two distinct Activities by resolving proxies containing the desired value for planned targets; include only practice ID/date/current/resolved snapshots. Never assign any ORM field.

`render_seed_plan()` must serialize a sorted object containing extraction hash, every change, conflicts, and upcoming mismatches via `json.dumps(..., sort_keys=True, separators=(",", ":"))`; its digest is `sha256(canonical_json.encode()).hexdigest()`.

- [ ] **Step 6: Implement atomic lock/recheck/commit and read-back**

```python
def _load_locked_models_by_change(session, changes):
    type_ids = [item.record_id for item in changes if item.kind == "workout_type"]
    activity_ids = [item.record_id for item in changes if item.kind == "activity"]
    records = {}
    if type_ids:
        for item in session.scalars(
            select(PracticeType).where(PracticeType.id.in_(type_ids)).with_for_update()
        ):
            records[("workout_type", item.id)] = item
    if activity_ids:
        for item in session.scalars(
            select(PracticeActivity).where(
                PracticeActivity.id.in_(activity_ids)
            ).with_for_update()
        ):
            records[("activity", item.id)] = item
    if len(records) != len(changes):
        raise SeedPlanError("A locked target disappeared; nothing was changed")
    return records


def commit_seed_plan(engine, manifest, approved_digest):
    if not approved_digest:
        raise SeedPlanError("--commit requires an approval digest")
    with Session(engine) as session, session.begin():
        locked = build_seed_plan(session, manifest, lock=True)
        rendered = render_seed_plan(locked)
        if rendered.digest != approved_digest:
            raise SeedPlanError(
                "The locked plan no longer matches the approval digest; run a new dry run"
            )
        if locked.has_conflicts:
            raise SeedPlanError("A target has a different non-empty value; nothing was changed")
        model_by_change = _load_locked_models_by_change(session, locked.changes)
        for change in locked.changes:
            if change.status == "fill":
                model_by_change[(change.kind, change.record_id)].default_plan_reactions = [
                    dict(item) for item in change.desired
                ]
        session.flush()
    with Session(engine) as verification:
        verified = build_seed_plan(verification, manifest, lock=False)
        if any(item.status != "exact" for item in verified.changes):
            raise SeedPlanError("Committed values failed read-back verification")
    return SeedCommitResult(verified=True, plan=verified)
```

Do not catch and continue from any transaction error. The context manager rolls back the whole transaction.

- [ ] **Step 7: Implement explicit CLI/environment safety**

Use `argparse` mutually exclusive mode options and select the URL without `create_app()`:

```python
load_dotenv(".env")
parser.add_argument("--environment", choices=("local", "production"), required=True)
mode = parser.add_mutually_exclusive_group(required=True)
mode.add_argument("--dry-run", action="store_true")
mode.add_argument("--commit", action="store_true")
parser.add_argument("--approve")

url_name = "PROD_DATABASE_URL" if args.environment == "production" else "DATABASE_URL"
database_url = os.environ.get(url_name)
if not database_url:
    raise SystemExit(f"{url_name} is required")
engine = create_engine(database_url)
```

Dry run prints the pretty diff/upcoming report and final `Approval digest: <sha256>`, performs no assignments, and exits nonzero without a digest on conflict or target drift. Commit rejects missing/mismatched digest, prints each fill/exact result, performs read-back, and prints `Verified <n> targets.` No code path imports Slack or writes `Practice.plan_reactions`.

- [ ] **Step 8: Run focused tests and source-safety checks**

Run:

```bash
env/bin/pytest tests/scripts/test_seed_practice_plan_reaction_defaults.py -q
rg -n "create_app|slack_sdk|WebClient|conversations_history|plan_reactions =" \
  scripts/seed_practice_plan_reaction_defaults.py
```

Expected: all tests pass; `rg` returns no app-factory/Slack-history imports and only assignments to `default_plan_reactions`, never `Practice.plan_reactions`.

- [ ] **Step 9: Exercise a local dry run twice and commit only local disposable data**

Run:

```bash
env/bin/python scripts/seed_practice_plan_reaction_defaults.py \
  --environment local --dry-run
```

Expected: a deterministic diff plus upcoming snapshot mismatches and one approval digest; database rows remain unchanged. Repeat the exact command and confirm the digest is unchanged while the database is unchanged. Do not run local `--commit` unless the local exact targets are disposable and the diff is reviewed.

- [ ] **Step 10: Commit manifest and operation**

```bash
git add scripts/data/2026-07-15-practice-plan-reaction-history.json \
  scripts/seed_practice_plan_reaction_defaults.py \
  tests/scripts/test_seed_practice_plan_reaction_defaults.py
git commit -m "feat(practices): seed historical reaction defaults safely"
```

### Task 8: Run Cross-Surface and Operational Gates

**Files:**

- Modify only if a gate exposes a defect; every fix receives its own focused RED/GREEN cycle and commit.

**Interfaces:**

- Consumes all prior tasks.
- Produces automated evidence, one native Slack Preview review in `C07G9RTMRT3`, one local Admin desktop/mobile review, and a production seed dry-run digest for explicit human approval. It does not commit the production seed.

- [ ] **Step 1: Run every focused reaction suite together**

```bash
npm run test:practice-reactions
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= \
env/bin/pytest \
  tests/practices/test_plan_reactions.py \
  tests/practices/test_plan_reaction_queries.py \
  tests/practices/test_plan_reaction_editor.py \
  tests/practices/test_practice_plan_reaction_js.py \
  tests/practices/test_plan_reaction_ui_source.py \
  tests/routes/test_admin_practice_plan_reactions.py \
  tests/slack/test_practice_reaction_editor.py \
  tests/slack/test_practice_create_modal.py \
  tests/slack/test_practice_edit_full.py \
  tests/slack/test_practice_preview.py \
  tests/scripts/test_seed_practice_plan_reaction_defaults.py -q
```

Expected: all focused tests pass with no skipped new behavior.

- [ ] **Step 2: Run the complete automated suite from a clean process**

```bash
env/bin/pytest -q
```

Expected: the complete suite passes. Existing SQLAlchemy deprecation warnings may remain; no new warning class or unhandled background-thread error is acceptable.

- [ ] **Step 3: Run repository hygiene and limit checks**

```bash
git diff --check $(git merge-base main HEAD)..HEAD
rg -n "one-off reaction|plan_reactions_block|action_id.*plan_reactions|multiline.*reaction" \
  app/slack app/templates/admin/practices app/static
git status --short
```

Expected: `git diff --check` is silent; the phrase `one-off reaction` and removed multiline authoring IDs are absent from production authoring surfaces; only the intentionally untracked `env` symlink may remain outside committed changes.

- [ ] **Step 4: Verify native Slack Preview without persistence**

Before opening Preview, record counts and newest timestamps for Practice rows, practice Slack message references, and weekly summary references in a read-only query. Point/restart the local companion on this worktree, then run exactly `/tcsc practice-preview` in `C07G9RTMRT3`.

On desktop and mobile, verify:

1. the default view has one interval Type, Run + Skate/Classic Rollerski, and four fixed-key rows;
2. description is the only editable value in each row;
3. transition Activities `1 → 2 → 3 → 1` and confirm only reaction rows reconcile;
4. customize a surviving description and confirm it survives;
5. Remove, inspect the dimmed `Removed` state, Undo, and confirm the same text returns;
6. clear the Type and leave one Activity so Add appears, then add a catalog option;
7. confirm no arbitrary shortcode control exists; and
8. submit `Close Preview`.

Re-run the exact read-only counts/timestamps. Expected: no Practice, message, thread, reaction, summary, or harness state changed. Do not post to `#announcements-practices`.

- [ ] **Step 5: Verify Admin Create/Edit on desktop and mobile with disposable local data**

Start the local app from this worktree. In Practices Settings, confirm Activity helper copy and that emoji keys remain editable/reorderable. In Admin Create/Edit, verify fixed keys, inline Remove, visible Removed + Undo, Add picker filtering, Restore, selector transition `1 → 2 → 3 → 1`, description preservation, neutral unconfigured-Activity copy, row errors, 44px mobile controls, fixed-key wrapping, and no horizontal overflow. Save one disposable local practice, reload it, and confirm its active snapshot/order round-trips. Delete the disposable row afterward; make no production Admin mutation.

- [ ] **Step 6: Generate but do not commit the production seed plan**

```bash
env/bin/python scripts/seed_practice_plan_reaction_defaults.py \
  --environment production --dry-run
```

Expected: exact targets are classified as `exact`, `fill`, or an all-or-nothing blocking conflict; upcoming Multisport snapshot differences are informational; no row changes. Capture the canonical diff and `Approval digest`. Stop before production `--commit` and present that exact diff/digest for human review.

- [ ] **Step 7: After explicit approval only, commit and verify the production seed**

This step requires a new explicit user approval of the Step 6 diff. Only then run:

```bash
env/bin/python scripts/seed_practice_plan_reaction_defaults.py \
  --environment production --commit --approve "$APPROVED_DIGEST"
```

Here `APPROVED_DIGEST` must be set to the exact Step 6 digest the user just approved, not recomputed or copied from another environment. Expected: the command locks/rechecks, fills only empty targets, commits atomically, and prints read-back verification. Immediately run the production dry run again; every target must be `exact` and existing Practice snapshots must remain unchanged. If the digest changed or any conflict appears, do not commit.

- [ ] **Step 8: Run final verification after any gate fixes**

If Tasks 4–7 exposed and fixed a defect, repeat Steps 1–3 and the affected native gate. Record the final commit range and test counts for branch review. Do not claim completion while Step 7 is awaiting approval; report it as the single intentional operational gate.
