# Collapsed Slack Practice Reactions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show a compact reaction summary at the bottom of every Slack practice modal and reveal the existing fixed-emoji editor in place only after the user selects Edit reactions.

**Architecture:** Add one versioned `editor_expanded` boolean to the shared ephemeral editor state. The Slack adapter renders either a compact summary or the existing full rows from that state, while the existing `views.update` rebuild path preserves unrelated inputs. Collapsed metadata carries validated active labels because no hidden Slack input state exists; expanded metadata keeps the current label-omission optimization.

**Tech Stack:** Python 3.13, Flask, SQLAlchemy, Slack Bolt, Slack Block Kit, pytest.

## Global Constraints

- Apply the behavior consistently to Slack Create, Preview, and Full Edit; Preview continues to reuse Create.
- The reaction region is after every other practice field. In Full Edit it follows Notification.
- The initial state is collapsed. Edit reactions performs a one-way in-place reveal for that modal lifetime.
- Do not add a nested modal, Done button, Hide button, or collapse transition.
- Preserve exact Add, Remove, Undo, Restore, source reconciliation, fixed-emoji, and submission semantics.
- Preserve every unrelated unsaved Slack field during a view rebuild.
- A collapsed view must submit the exact summarized active reaction snapshot.
- Keep Slack private metadata at or below 3,000 characters and fail closed on malformed or noncanonical state.
- Preview remains isolated and discard-only. Do not post to `#announcements-practices`.
- Native Slack testing is allowed only in `C07G9RTMRT3` with `/tcsc practice-preview`.
- Do not run the production seed commit without a fresh explicit approval of its exact production dry-run diff and digest.
- Production is currently at Alembic revision `e36bbec59bde`; the seed dry run remains blocked until deployment applies `c4f1a8e2d9b7`.

## File Structure

- `app/practices/plan_reaction_editor.py`: owns versioned editor state, serialization, reconciliation, and Restore state continuity.
- `app/slack/practice_reaction_editor.py`: owns collapsed and expanded Block Kit rendering plus bounded private metadata.
- `app/slack/modals.py`: owns the final placement of the reaction region in Create, Preview, and Full Edit.
- `app/slack/bolt_app.py`: owns registered reaction actions and in-place expansion.
- `tests/practices/test_plan_reaction_editor.py`: verifies the state schema and transition continuity.
- `tests/slack/test_practice_reaction_editor.py`: verifies compact rendering, metadata, escaping, and bounds.
- `tests/slack/test_practice_create_modal.py`: verifies Create placement, no-edit submission, and Edit preservation.
- `tests/slack/test_practice_edit_full.py`: verifies Full Edit placement, saved snapshots, and expanded Restore.
- `tests/slack/test_practice_preview.py`: verifies the discard-only compact-to-expanded interaction.
- `tests/slack/test_practice_reaction_transport.py`: verifies ACK and lazy-worker registration for the new action.

---

### Task 1: Version the Shared Expansion State

**Files:**
- Modify: `app/practices/plan_reaction_editor.py:15-80, 410-450, 468-790`
- Test: `tests/practices/test_plan_reaction_editor.py`

**Interfaces:**
- Consumes: existing `PlanReactionEditorState`, `serialize_plan_reaction_editor_state()`, `deserialize_plan_reaction_editor_state()`, and `restore_plan_reaction_defaults()`.
- Produces: `PlanReactionEditorState.editor_expanded: bool`, serialized key `editor_expanded`, and schema version `2` for Tasks 2 and 3.

- [ ] **Step 1: Write failing schema and Restore tests**

Add these focused contracts to `tests/practices/test_plan_reaction_editor.py`:

```python
def test_editor_expansion_defaults_false_and_round_trips(sources):
    state = build_plan_reaction_editor_state(
        practice_types=[sources.intervals],
        activities=[],
        saved_snapshot=None,
    ).state
    assert state.editor_expanded is False

    state.editor_expanded = True
    payload = serialize_plan_reaction_editor_state(state)
    assert payload["version"] == 2
    assert payload["editor_expanded"] is True
    assert deserialize_plan_reaction_editor_state(deepcopy(payload)) == state


@pytest.mark.parametrize("invalid", [None, 0, 1, "true", [], {}])
def test_metadata_rejects_nonboolean_editor_expanded(sources, invalid):
    state = build_plan_reaction_editor_state(
        practice_types=[sources.intervals],
        activities=[],
        saved_snapshot=None,
    ).state
    payload = serialize_plan_reaction_editor_state(state)
    payload["editor_expanded"] = invalid

    with pytest.raises(
        PlanReactionValidationError,
        match="^Invalid reaction editor metadata$",
    ):
        deserialize_plan_reaction_editor_state(payload)


def test_restore_defaults_keeps_expanded_editor_open(sources):
    state = build_plan_reaction_editor_state(
        practice_types=[sources.intervals],
        activities=[],
        saved_snapshot=[EVERGREEN_PLAN_REACTION],
    ).state
    state.editor_expanded = True

    restored = restore_plan_reaction_defaults(
        state,
        practice_types=[sources.intervals],
        activities=[],
    ).state

    assert restored.editor_expanded is True
```

- [ ] **Step 2: Run the new tests and verify RED**

Run:

```bash
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= \
env/bin/pytest \
  tests/practices/test_plan_reaction_editor.py::test_editor_expansion_defaults_false_and_round_trips \
  tests/practices/test_plan_reaction_editor.py::test_metadata_rejects_nonboolean_editor_expanded \
  tests/practices/test_plan_reaction_editor.py::test_restore_defaults_keeps_expanded_editor_open -q
```

Expected: FAIL because `editor_expanded` and version `2` do not exist.

- [ ] **Step 3: Implement the minimal versioned state change**

Make these exact structural changes in `app/practices/plan_reaction_editor.py`:

```python
PLAN_REACTION_EDITOR_VERSION = 2

_EDITOR_KEYS = {
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
    "editor_expanded",
}


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
    editor_expanded: bool = False
```

Add the key to `serialize_plan_reaction_editor_state()`:

```python
"editor_expanded": state.editor_expanded,
```

Validate and return it from `_deserialize_plan_reaction_editor_state()`:

```python
editor_expanded = payload["editor_expanded"]
if not isinstance(editor_expanded, bool):
    raise _metadata_error()

# In the final PlanReactionEditorState(...) constructor:
editor_expanded=editor_expanded,
```

Preserve it on successful Restore before returning:

```python
restored.state.next_row_number = next_row_number
restored.state.editor_expanded = state.editor_expanded
return restored
```

The existing error branches clone `state`, so they already preserve the boolean.

- [ ] **Step 4: Run the state tests and verify GREEN**

Run:

```bash
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= \
env/bin/pytest tests/practices/test_plan_reaction_editor.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit the state contract**

```bash
git add app/practices/plan_reaction_editor.py \
  tests/practices/test_plan_reaction_editor.py
git commit -m "feat(practices): track reaction editor expansion"
```

---

### Task 2: Render a Safe Collapsed Summary

**Files:**
- Modify: `app/slack/practice_reaction_editor.py:20-55, 140-380, 650-760`
- Test: `tests/slack/test_practice_reaction_editor.py`

**Interfaces:**
- Consumes: Task 1's `PlanReactionEditorState.editor_expanded` and state schema version `2`.
- Produces: `EDIT_ACTION_ID`, state-driven collapsed/expanded rendering, and conditional active-label metadata for Task 3.

- [ ] **Step 1: Make existing full-editor fixtures explicit**

Keep existing full-row tests focused on their original behavior by expanding their fixtures in `tests/slack/test_practice_reaction_editor.py`:

```python
@pytest.fixture
def editor_state():
    intervals = SimpleNamespace(
        id=1,
        name="Intervals",
        default_plan_reactions=[EVERGREEN_PLAN_REACTION],
    )
    state = build_plan_reaction_editor_state(
        practice_types=[intervals],
        activities=[],
        saved_snapshot=None,
    ).state
    state.editor_expanded = True
    return state


@pytest.fixture
def empty_state():
    return PlanReactionEditorState(editor_expanded=True)
```

- [ ] **Step 2: Write failing collapsed-rendering tests**

Import `EDIT_ACTION_ID` and add:

```python
def test_collapsed_summary_lists_only_active_rows_in_order(editor_state):
    editor_state.editor_expanded = False
    second = PlanReactionEditorRow(
        row_id="r1",
        emoji="athletic_shoe",
        label="runner",
        catalog_order=0,
    )
    removed = PlanReactionEditorRow(
        row_id="r2",
        emoji="hatching_chick",
        label="new rollerskier",
        removed=True,
        catalog_order=1,
    )
    editor_state.rows.extend([second, removed])
    editor_state.next_row_number = 3

    blocks = build_practice_reaction_blocks(
        editor_state,
        CATALOG,
        allow_restore=True,
    )
    summary = _blocks_by_id(blocks)["practice_reaction_summary"]

    assert summary["text"]["text"] == (
        "*Plan reactions*\n"
        ":evergreen_tree: Endurance instead of intervals\n"
        ":athletic_shoe: runner"
    )
    assert summary["accessory"]["action_id"] == EDIT_ACTION_ID
    assert summary["accessory"]["text"]["text"] == "Edit reactions"
    assert not any(
        block.get("block_id", "").startswith("practice_reaction_row_")
        for block in blocks
    )


def test_collapsed_empty_summary_uses_add_reactions(empty_state):
    empty_state.editor_expanded = False
    summary = _blocks_by_id(build_practice_reaction_blocks(
        empty_state,
        CATALOG,
        allow_restore=False,
    ))["practice_reaction_summary"]

    assert summary["text"]["text"] == "*Plan reactions*\nNo Plan reactions"
    assert summary["accessory"]["text"]["text"] == "Add reactions"


def test_collapsed_summary_escapes_labels_and_keeps_status_blocks(editor_state):
    editor_state.editor_expanded = False
    editor_state.rows[0].label = "Use <short> & steady"
    editor_state.unconfigured_activity_names = ("Skate <Rollerski>",)
    editor_state.blocking_error = "Resolve <conflict> & retry"

    blocks = _blocks_by_id(build_practice_reaction_blocks(
        editor_state,
        CATALOG,
        allow_restore=True,
    ))

    assert "Use &lt;short&gt; &amp; steady" in (
        blocks["practice_reaction_summary"]["text"]["text"]
    )
    assert "Skate &lt;Rollerski&gt;" in (
        blocks["practice_reaction_unconfigured"]["elements"][0]["text"]
    )
    assert blocks["practice_reaction_error"]["text"]["text"] == (
        "Resolve &lt;conflict&gt; &amp; retry"
    )
```

- [ ] **Step 3: Write failing conditional-metadata tests**

Add:

```python
def test_collapsed_metadata_retains_labels_while_expanded_omits_them():
    state = PlanReactionEditorState(
        rows=[PlanReactionEditorRow(
            row_id="r0",
            emoji="hatching_chick",
            label="Ny skiløper 🐣",
            catalog_order=0,
        )],
        next_row_number=1,
        editor_expanded=False,
    )
    context = {
        "date": "2026-07-14",
        "channel_id": None,
        "message_ts": None,
    }

    collapsed_raw = encode_practice_reaction_metadata(
        mode="create",
        context=context,
        state=state,
    )
    assert len(collapsed_raw) <= 3000
    assert decode_practice_reaction_metadata(collapsed_raw)[2].rows[0].label == (
        "Ny skiløper 🐣"
    )
    assert "\\u00f8" not in collapsed_raw

    state.editor_expanded = True
    expanded_raw = encode_practice_reaction_metadata(
        mode="create",
        context=context,
        state=state,
    )
    assert json.loads(expanded_raw)["s"]["rows"][0]["label"] is None


def test_collapsed_metadata_rejects_blank_active_label():
    state = PlanReactionEditorState(
        rows=[PlanReactionEditorRow(
            row_id="r0",
            emoji="athletic_shoe",
            label="",
            catalog_order=0,
        )],
        next_row_number=1,
        editor_expanded=False,
    )

    with pytest.raises(PlanReactionValidationError):
        encode_practice_reaction_metadata(
            mode="create",
            context={
                "date": "2026-07-14",
                "channel_id": None,
                "message_ts": None,
            },
            state=state,
        )
```

- [ ] **Step 4: Run the new adapter tests and verify RED**

Run:

```bash
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= \
env/bin/pytest \
  tests/slack/test_practice_reaction_editor.py::test_collapsed_summary_lists_only_active_rows_in_order \
  tests/slack/test_practice_reaction_editor.py::test_collapsed_empty_summary_uses_add_reactions \
  tests/slack/test_practice_reaction_editor.py::test_collapsed_summary_escapes_labels_and_keeps_status_blocks \
  tests/slack/test_practice_reaction_editor.py::test_collapsed_metadata_retains_labels_while_expanded_omits_them \
  tests/slack/test_practice_reaction_editor.py::test_collapsed_metadata_rejects_blank_active_label -q
```

Expected: FAIL because the compact renderer and conditional metadata do not exist.

- [ ] **Step 5: Implement the state-driven renderer**

In `app/slack/practice_reaction_editor.py`, import `active_plan_reaction_snapshot` and add:

```python
EDIT_ACTION_ID = "practice_reaction_edit"


def _practice_reaction_status_blocks(state: PlanReactionEditorState) -> list[dict]:
    blocks = []
    if state.unconfigured_activity_names:
        names = ", ".join(state.unconfigured_activity_names)
        message = _mrkdwn_escape(
            "No reaction pairs are configured for selected "
            f"Activities: {names}."
        )
        blocks.append({
            "type": "context",
            "block_id": "practice_reaction_unconfigured",
            "elements": [{
                "type": "mrkdwn",
                "text": _ellipsize(message, SLACK_TEXT_OBJECT_MAX_CHARS),
            }],
        })
    if state.blocking_error:
        blocks.append({
            "type": "section",
            "block_id": "practice_reaction_error",
            "text": {
                "type": "mrkdwn",
                "text": _ellipsize(
                    _mrkdwn_escape(state.blocking_error),
                    SLACK_TEXT_OBJECT_MAX_CHARS,
                ),
            },
        })
    return blocks


def _build_collapsed_practice_reaction_blocks(
    state: PlanReactionEditorState,
) -> list[dict]:
    active = [row for row in state.rows if not row.removed]
    lines = ["*Plan reactions*"]
    if active:
        lines.extend(
            f":{row.emoji}: {_mrkdwn_escape(row.label)}"
            for row in active
        )
        button_text = "Edit reactions"
    else:
        lines.append("No Plan reactions")
        button_text = "Add reactions"
    blocks = [{
        "type": "section",
        "block_id": "practice_reaction_summary",
        "text": {
            "type": "mrkdwn",
            "text": _ellipsize(
                "\n".join(lines),
                SLACK_TEXT_OBJECT_MAX_CHARS,
            ),
        },
        "accessory": _button(
            action_id=EDIT_ACTION_ID,
            text=button_text,
            accessibility_label=button_text,
        ),
    }]
    blocks.extend(_practice_reaction_status_blocks(state))
    return blocks
```

At the start of `build_practice_reaction_blocks()` after block-ID validation:

```python
if not state.editor_expanded:
    return _build_collapsed_practice_reaction_blocks(state)
```

Replace the duplicated expanded unconfigured/error construction with:

```python
blocks.extend(_practice_reaction_status_blocks(state))
```

Export `EDIT_ACTION_ID` through `__all__`.

- [ ] **Step 6: Implement bounded collapsed metadata**

Change `_validated_serialized_state()` and the JSON encoding path:

```python
def _validated_serialized_state(state: PlanReactionEditorState) -> dict:
    if not state.editor_expanded:
        raw_active = [
            {"emoji": row.emoji, "label": row.label}
            for row in state.rows
            if not row.removed
        ]
        if active_plan_reaction_snapshot(state) != raw_active:
            raise _metadata_error()
    payload = serialize_plan_reaction_editor_state(
        state,
        omit_active_labels=state.editor_expanded,
    )
    deserialize_plan_reaction_editor_state(payload)
    return payload

# Inside encode_practice_reaction_metadata(...):
raw = json.dumps(envelope, separators=(",", ":"), ensure_ascii=False)
```

After deserializing in `decode_practice_reaction_metadata()`, enforce the same canonical collapsed invariant before returning:

```python
if not state.editor_expanded:
    raw_active = [
        {"emoji": row.emoji, "label": row.label}
        for row in state.rows
        if not row.removed
    ]
    if active_plan_reaction_snapshot(state) != raw_active:
        raise _metadata_error()
```

Keep the existing final `len(raw) > SLACK_PRIVATE_METADATA_MAX_CHARS` rejection unchanged.

- [ ] **Step 7: Run the full adapter suite and verify GREEN**

Run:

```bash
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= \
env/bin/pytest tests/slack/test_practice_reaction_editor.py -q
```

Expected: all tests pass.

- [ ] **Step 8: Commit the compact adapter**

```bash
git add app/slack/practice_reaction_editor.py \
  tests/slack/test_practice_reaction_editor.py
git commit -m "feat(slack): collapse practice reactions by default"
```

---

### Task 3: Wire In-Place Expansion Across Slack Surfaces

**Files:**
- Modify: `app/slack/modals.py:620-890`
- Modify: `app/slack/bolt_app.py:45-85, 1360-1620`
- Test: `tests/slack/test_practice_create_modal.py`
- Test: `tests/slack/test_practice_edit_full.py`
- Test: `tests/slack/test_practice_preview.py`
- Test: `tests/slack/test_practice_reaction_transport.py`

**Interfaces:**
- Consumes: Task 2's `EDIT_ACTION_ID` and state-driven `build_practice_reaction_blocks()`.
- Produces: an eighth shared Slack action, the one-way expansion transition, and bottom placement on Create, Preview, and Full Edit.

- [ ] **Step 1: Write failing modal placement tests**

Add one order helper per modal test module:

```python
def _block_index(modal, block_id):
    return next(
        index
        for index, block in enumerate(modal["blocks"])
        if block.get("block_id") == block_id
    )
```

Add these assertions to the focused builder tests:

```python
def test_create_reaction_summary_is_collapsed_and_last():
    modal = build_practice_create_modal(
        datetime(2026, 7, 14, 18, 15),
        "18:15",
        locations=[(10, "Theodore Wirth")],
        eligible_coaches=[(1, "Coach", "U1")],
        eligible_leads=[(2, "Lead", "U2")],
        **_reaction_inputs(),
    )
    blocks = _blocks_by_id(modal)
    assert "practice_reaction_summary" in blocks
    assert "practice_reaction_row_r0" not in blocks
    assert _block_index(modal, "practice_reaction_summary") > _block_index(
        modal, "flags_block"
    )


def test_full_edit_reaction_summary_follows_notification():
    practice = _practice_info()
    modal = build_practice_edit_full_modal(
        practice,
        **_edit_reaction_inputs(practice),
    )
    assert _block_index(modal, "practice_reaction_summary") > _block_index(
        modal, "notify_block"
    )


def test_preview_starts_with_collapsed_summary_as_final_region():
    modal = build_practice_preview_modal(PREVIEW_DATE)
    blocks = _blocks_by_id(modal)
    assert "practice_reaction_summary" in blocks
    assert "practice_reaction_row_r0" not in blocks
    assert _block_index(modal, "practice_reaction_summary") > _block_index(
        modal, "flags_block"
    )
```

- [ ] **Step 2: Write failing action and preservation tests**

Add a Preview integration test that exercises the real shared handler:

```python
def test_preview_edit_reactions_expands_in_place_and_preserves_values(
    preview_action_body,
):
    values = preview_action_body["view"]["state"]["values"]
    values["workout_block"]["workout_description"]["value"] = (
        "Unsaved interval workout"
    )
    client = MagicMock()

    bolt_module._handle_practice_reaction_action(
        ack=lambda: None,
        body=preview_action_body,
        action={"action_id": "practice_reaction_edit"},
        client=client,
        logger=MagicMock(),
    )

    updated = client.views_update.call_args.kwargs["view"]
    blocks = _blocks_by_id(updated)
    assert blocks["workout_block"]["element"]["initial_value"] == (
        "Unsaved interval workout"
    )
    assert "practice_reaction_summary" not in blocks
    assert "practice_reaction_row_r0" in blocks
    assert decode_practice_reaction_metadata(
        updated["private_metadata"]
    )[2].editor_expanded is True
```

Add a Create submission test using the normal collapsed builder and no row inputs:

```python
def test_create_submission_without_expanding_preserves_summary_snapshot(
    db_session,
    create_sources,
    create_view,
    monkeypatch,
):
    _location, activity, practice_type = create_sources
    collapsed = copy.deepcopy(create_view)
    mode, context, state, preview = decode_practice_reaction_metadata(
        collapsed["private_metadata"]
    )
    state = merge_practice_reaction_inputs(
        state,
        collapsed["state"]["values"],
    )
    state.editor_expanded = False
    expected = active_plan_reaction_snapshot(state)
    collapsed["private_metadata"] = encode_practice_reaction_metadata(
        mode=mode,
        context=context,
        state=state,
        preview_config=preview,
    )
    collapsed["blocks"] = [
        block
        for block in collapsed["blocks"]
        if not block.get("block_id", "").startswith("practice_reaction_")
    ] + build_practice_reaction_blocks(
        state,
        build_plan_reaction_catalog([practice_type], [activity]),
        allow_restore=False,
    )
    collapsed["state"] = {"values": _view_values(collapsed)}
    monkeypatch.setattr(bolt_module.threading, "Thread", MagicMock())

    bolt_module._handle_practice_create_submission(
        MagicMock(),
        CREATE_BODY,
        collapsed,
        MagicMock(),
        MagicMock(),
    )

    practice = Practice.query.filter_by(
        slack_coach_summary_ts=CREATE_TEST_PREFIX
    ).one()
    assert practice.plan_reactions == expected
```

Import `active_plan_reaction_snapshot`, `build_practice_reaction_blocks`, `merge_practice_reaction_inputs`, `decode_practice_reaction_metadata`, and `encode_practice_reaction_metadata` in this test module. If the shared `create_view` fixture is kept expanded to protect existing edit-field tests, set `editor.editor_expanded = True` before building that fixture. The new builder test above remains the default-state contract.

- [ ] **Step 3: Update the transport contract from seven to eight actions**

In `tests/slack/test_practice_reaction_transport.py`, add `practice_reaction_edit` to `ACTION_IDS` and rename the test:

```python
ACTION_IDS = (
    "activity_ids",
    "type_ids",
    "practice_reaction_edit",
    "practice_reaction_remove",
    "practice_reaction_undo",
    "practice_reaction_add",
    "practice_reaction_catalog_select",
    "practice_reaction_restore",
)


def test_all_eight_reaction_actions_share_ack_and_lazy_worker_registration():
    app = _installed_bolt_app()
    observed = []
    lock = threading.Lock()
    all_finished = threading.Event()

    def worker(action):
        with lock:
            observed.append(action["action_id"])
            if len(observed) == len(ACTION_IDS):
                all_finished.set()

    bolt_module._register_practice_reaction_action_listeners(
        app,
        worker=worker,
    )
    responses = [
        app.dispatch(_request(action_id))
        for action_id in ACTION_IDS
    ]

    assert all(response.status == 200 for response in responses)
    assert all_finished.wait(1)
    assert set(observed) == set(ACTION_IDS)
    assert len(app._listeners) == len(ACTION_IDS)
```

- [ ] **Step 4: Run the new cross-surface tests and verify RED**

Run:

```bash
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= \
env/bin/pytest \
  tests/slack/test_practice_create_modal.py::test_create_reaction_summary_is_collapsed_and_last \
  tests/slack/test_practice_edit_full.py::test_full_edit_reaction_summary_follows_notification \
  tests/slack/test_practice_preview.py::test_preview_starts_with_collapsed_summary_as_final_region \
  tests/slack/test_practice_preview.py::test_preview_edit_reactions_expands_in_place_and_preserves_values \
  tests/slack/test_practice_reaction_transport.py::test_all_eight_reaction_actions_share_ack_and_lazy_worker_registration -q
```

Expected: FAIL because placement and Edit-action wiring are not implemented.

- [ ] **Step 5: Move the reaction region to the bottom**

In `build_practice_create_modal()`, remove the existing `build_practice_reaction_blocks()` call after Practice Types. Append the same call only after `flags_block`:

```python
blocks.append({
    "type": "input",
    "block_id": "flags_block",
    "optional": True,
    "label": {"type": "plain_text", "text": "Options"},
    "element": _build_practice_flags_element(is_dark_practice=default_is_dark),
})
blocks.extend(build_practice_reaction_blocks(
    reaction_editor,
    reaction_catalog,
    allow_restore=False,
))
```

In `build_practice_edit_full_modal()`, remove the existing call after Notes. Keep the current Options and Notification dictionaries together, then append the reaction blocks after them:

```python
blocks.extend([
    {
        "type": "input",
        "block_id": "flags_block",
        "optional": True,
        "label": {"type": "plain_text", "text": "Options"},
        "element": _build_practice_flags_element(practice),
    },
    {
        "type": "input",
        "block_id": "notify_block",
        "optional": True,
        "label": {"type": "plain_text", "text": "Notification"},
        "element": {
            "type": "checkboxes",
            "action_id": "notify_update",
            "options": [{
                "text": {
                    "type": "mrkdwn",
                    "text": "*Post update notification*",
                },
                "description": {
                    "type": "plain_text",
                    "text": "Notify the thread about this change",
                },
                "value": "notify",
            }],
            "initial_options": [{
                "text": {
                    "type": "mrkdwn",
                    "text": "*Post update notification*",
                },
                "description": {
                    "type": "plain_text",
                    "text": "Notify the thread about this change",
                },
                "value": "notify",
            }],
        },
    },
])
blocks.extend(build_practice_reaction_blocks(
    reaction_editor,
    reaction_catalog,
    allow_restore=True,
))
```

- [ ] **Step 6: Register and apply the one-way Edit action**

Add the new action ID to `_PRACTICE_REACTION_ACTION_ID_ORDER` in `app/slack/bolt_app.py`:

```python
_PRACTICE_REACTION_ACTION_ID_ORDER = (
    "activity_ids",
    "type_ids",
    "practice_reaction_edit",
    "practice_reaction_remove",
    "practice_reaction_undo",
    "practice_reaction_add",
    "practice_reaction_catalog_select",
    "practice_reaction_restore",
)
```

In `_apply_practice_reaction_action()`, keep selector reconciliation first. After the existing last-valid selector check and before Remove, add:

```python
if action_id == "practice_reaction_edit":
    working = copy.deepcopy(state)
    working.editor_expanded = True
    working.add_open = False
    return working
```

Because assigning `True` repeatedly is idempotent and `views.update` uses the current view hash, repeated or stale clicks remain harmless.

- [ ] **Step 7: Adapt expanded-flow fixtures without weakening default contracts**

For existing tests that directly select Remove, Add, Undo, Restore, or edit a reaction description, explicitly build or transition to `editor_expanded=True`. For Preview, add a helper that uses the real Edit action once and returns an action body from the rebuilt view:

```python
def _expanded_preview_action_body(preview_action_body):
    client = MagicMock()
    bolt_module._handle_practice_reaction_action(
        lambda: None,
        preview_action_body,
        {"action_id": "practice_reaction_edit"},
        client,
        MagicMock(),
    )
    return _action_body_from_view(
        client.views_update.call_args.kwargs["view"],
        view_hash="HASH_EXPANDED",
    )
```

Use this helper as the starting body for existing expanded Preview action tests. Do not make the production Preview builder start expanded just to satisfy tests.

- [ ] **Step 8: Run all affected Slack suites and verify GREEN**

Run serially because several suites use the persistent test database:

```bash
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= \
env/bin/pytest \
  tests/practices/test_plan_reaction_editor.py \
  tests/slack/test_practice_reaction_editor.py \
  tests/slack/test_practice_reaction_transport.py \
  tests/slack/test_practice_create_modal.py \
  tests/slack/test_practice_edit_full.py \
  tests/slack/test_practice_preview.py -q
```

Expected: all tests pass with no skipped new behavior.

- [ ] **Step 9: Commit the cross-surface wiring**

```bash
git add app/slack/modals.py app/slack/bolt_app.py \
  tests/slack/test_practice_create_modal.py \
  tests/slack/test_practice_edit_full.py \
  tests/slack/test_practice_preview.py \
  tests/slack/test_practice_reaction_transport.py
git commit -m "feat(slack): expand practice reactions in place"
```

---

### Task 4: Run Regression and Operational Gates

**Files:**
- Modify only if a gate exposes a defect. Every defect gets a focused RED/GREEN test and its own commit.

**Interfaces:**
- Consumes: Tasks 1 through 3.
- Produces: automated, native Preview, and production-readiness evidence. It does not authorize a production seed write.

- [ ] **Step 1: Run every reaction suite**

```bash
npm run test:practice-reactions
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= \
env/bin/pytest \
  tests/practices/test_plan_reactions.py \
  tests/practices/test_plan_reaction_contracts.py \
  tests/practices/test_plan_reaction_editor.py \
  tests/practices/test_practice_plan_reaction_js.py \
  tests/practices/test_plan_reaction_ui_source.py \
  tests/routes/test_admin_practice_plan_reactions.py \
  tests/slack/test_practice_reaction_editor.py \
  tests/slack/test_practice_reaction_transport.py \
  tests/slack/test_practice_create_modal.py \
  tests/slack/test_practice_edit_full.py \
  tests/slack/test_practice_preview.py \
  tests/scripts/test_seed_practice_plan_reaction_defaults.py -q
```

Expected: all Node and Python reaction tests pass.

- [ ] **Step 2: Run the complete Python suite**

```bash
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest -q
```

Expected: all tests pass. Known dependency deprecation warnings may remain unchanged.

- [ ] **Step 3: Run branch hygiene checks**

```bash
git diff --check "$(git merge-base main HEAD)..HEAD"
rg -n "one-off reaction|plan_reactions_block|action_id.*plan_reactions|multiline.*reaction" \
  app/slack app/templates/admin/practices app/static
git status --short
```

Expected: diff check is silent; removed freeform authoring IDs remain absent; only the pre-existing untracked `env` symlink may remain.

- [ ] **Step 4: Repeat the isolated native Slack Preview gate**

Before Preview, record the same read-only local database snapshot and Slack metadata snapshot for `C07G9RTMRT3` used by the original operational gate. Restart the local companion from this exact worktree and run exactly `/tcsc practice-preview` in `C07G9RTMRT3`.

Verify:

1. Create/Preview opens with the compact Plan-reaction summary after Options.
2. The summary lists the four current pairs in order.
3. Edit reactions expands the fixed-key rows in the same modal.
4. Workout, selectors, coaches, leads, and Options retain unsaved values across expansion.
5. Selector changes update the state and keep the editor expanded.
6. Add, Remove, and Undo remain usable.
7. Close Preview dismisses the modal.
8. The before/after Slack metadata hash and local database snapshot are identical.

Do not post to `#announcements-practices`.

- [ ] **Step 5: Resume the production dry run only after schema deployment**

First run the read-only schema check. Require Alembic revision `c4f1a8e2d9b7` and the three reaction columns before continuing. Then run:

```bash
env/bin/python scripts/seed_practice_plan_reaction_defaults.py \
  --environment production --dry-run
```

Expected: deterministic `exact`, `fill`, or blocking `conflict` classifications plus one approval digest and no writes. Capture the complete canonical diff and digest, then stop for fresh explicit user approval.

Do not run `--commit` while production remains at `e36bbec59bde`, if the dry-run digest changes, if any conflict appears, or before the user approves that exact diff and digest.
