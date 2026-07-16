# Practice Authoring Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a zero-persistence `/tcsc practice-preview` command for native Slack modal review and make incomplete admin Plan-reaction rows wait neutrally for completion.

**Architecture:** A pure preview factory wraps the existing production create-modal builder with synthetic in-memory values and replaces only its safety-facing metadata. An always-defined Slack command helper branches on the exact diagnostic command before the existing `/tcsc` processor, enforces the test-channel boundary, and delegates preview submission to an ack-only callback; the admin correction remains a small inline change to the existing autosave function.

**Tech Stack:** Python 3.12.7, Flask, Slack Bolt/Block Kit, Jinja, vanilla JavaScript, pytest, `unittest.mock`, and Playwright for the final browser smoke test.

## Global Constraints

- The exact command is `/tcsc practice-preview`.
- Accept the preview only when Slack supplies channel ID `C07G9RTMRT3`.
- Do not add a role, tag, coach, or practice-lead authorization check; channel membership is the preview access boundary.
- Populate the preview exclusively with synthetic in-memory values; do not query or mutate production data.
- Reuse `build_practice_create_modal()` so the preview has the production field order, labels, hints, limits, selectors, and Plan-reaction formatting.
- Set the preview title to `Practice Preview`, submit label to `Close Preview`, callback ID to `practice_preview`, and private metadata to the empty string.
- Keep the Plan-reaction input as a multiline snapshot. Activity and Practice Type changes do not recalculate it.
- The preview submission listener must only call `ack()`; it must not parse fields, open an application context, persist records, post messages, add reactions, or refresh summaries.
- Do not add the diagnostic command to `/tcsc help`.
- Do not alter the real `practice_create` or `practice_edit_full` submission flows.
- Do not add a database migration, stored configuration, Slack shortcut, channel message, frontend framework, emoji picker, debounce queue, or autosave subsystem.
- For an incomplete admin Plan-reaction row, send no mutation, do not redirect focus, use neutral live-status styling, and show exactly `Complete both fields to save.`
- Preserve existing `Saving…`, `Saved.`, and red server-error behavior once a row is complete.
- Preserve the retained announcement validation-harness state; this feature creates no cleanup obligation.

---

## File Map

- Create `tests/slack/test_practice_preview.py`: dependency-free modal and Slack routing contracts for preview behavior.
- Modify `app/slack/modals.py`: add the pure synthetic preview-view factory next to the production create builder.
- Modify `app/slack/bolt_app.py`: add constants, an always-defined `/tcsc` routing helper, a preview-only ack helper, and thin decorated listeners.
- Create `tests/practices/test_plan_reaction_ui_source.py`: dependency-free source contract for the admin autosave interaction.
- Modify `app/templates/admin/practices/config.html`: make the incomplete-row branch neutral and non-focusing without changing complete-row autosave.

### Task 1: Build the Synthetic Preview with the Production Modal Factory

**Files:**

- Create: `tests/slack/test_practice_preview.py`
- Modify: `app/slack/modals.py` immediately after `build_practice_create_modal()`
- Test: `tests/slack/test_practice_create_modal.py`

**Interfaces:**

- Consumes: `build_practice_create_modal(practice_date, default_time, ..., initial_plan_reactions) -> dict` from `app.slack.modals`.
- Produces: `build_practice_preview_modal(practice_date: "datetime") -> dict` in `app.slack.modals` for Task 2.

- [ ] **Step 1: Write the failing preview-factory tests**

Create `tests/slack/test_practice_preview.py` with the following initial content:

```python
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
```

- [ ] **Step 2: Run the tests and confirm the missing factory is the only intended failure**

Run:

```bash
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= \
  env/bin/pytest tests/slack/test_practice_preview.py -q
```

Expected: collection fails with an `ImportError` for `build_practice_preview_modal`; do not proceed if an unrelated import or environment failure appears.

- [ ] **Step 3: Add the minimal pure preview factory**

Immediately after `build_practice_create_modal()` in `app/slack/modals.py`, add:

```python
def build_practice_preview_modal(practice_date: 'datetime') -> dict:
    """Build a discard-only preview of the production practice create modal."""
    modal = build_practice_create_modal(
        practice_date,
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
        initial_plan_reactions=[
            {
                "emoji": "evergreen_tree",
                "label": "Endurance instead of intervals",
            },
            {"emoji": "hatching_chick", "label": "new rollerskier"},
            {
                "emoji": "older_adult::skin-tone-4",
                "label": "experienced rollerskier",
            },
            {"emoji": "athletic_shoe", "label": "runner"},
        ],
    )
    modal.update({
        "title": {"type": "plain_text", "text": "Practice Preview"},
        "submit": {"type": "plain_text", "text": "Close Preview"},
        "callback_id": "practice_preview",
        "private_metadata": "",
    })
    return modal
```

This function intentionally does not accept IDs, defaults, channel metadata, or database objects. The fixed numeric IDs satisfy Slack static-select requirements without resembling a persistence target.

- [ ] **Step 4: Run the preview and adjacent modal tests**

Run:

```bash
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= \
  env/bin/pytest \
    tests/slack/test_practice_preview.py \
    tests/slack/test_practice_create_modal.py \
    tests/slack/test_modals_person_select.py \
    -q
```

Expected: all selected tests pass. The full-structure equality proves that the preview differs from the real create modal only in the four approved metadata fields.

- [ ] **Step 5: Commit the pure preview factory**

```bash
git add app/slack/modals.py tests/slack/test_practice_preview.py
git commit -m "feat(slack): build discard-only practice preview"
```

### Task 2: Route the Exact Test-Channel Command to an Ack-Only Preview Callback

**Files:**

- Modify: `tests/slack/test_practice_preview.py`
- Modify: `app/slack/bolt_app.py` near the module constants, `/tcsc` listener, view listeners, and always-defined helper section
- Test: `tests/slack/test_practice_create_modal.py`

**Interfaces:**

- Consumes: `build_practice_preview_modal(practice_date: "datetime") -> dict` from Task 1 and `now_central_naive() -> datetime` from `app.utils`.
- Produces: `_handle_tcsc_command(ack, command: dict, client, logger) -> None` and `_handle_practice_preview_submission(ack) -> None`, both always importable without Slack credentials.

- [ ] **Step 1: Add imports and test helpers for the Slack routing contract**

At the top of `tests/slack/test_practice_preview.py`, replace the imports with:

```python
"""Contracts for the discard-only Slack Practice Preview."""

from contextlib import nullcontext
from datetime import datetime
from unittest.mock import MagicMock, patch

import app.slack.bolt_app as bolt_module
from app.slack.modals import (
    build_practice_create_modal,
    build_practice_preview_modal,
)
```

After `_expected_create_modal()`, add:

```python
def _preview_command(**overrides):
    command = {
        "text": "practice-preview",
        "channel_id": "C07G9RTMRT3",
        "user_id": "U_PREVIEWER",
        "user_name": "previewer",
        "trigger_id": "TRIGGER_PREVIEW",
    }
    command.update(overrides)
    return command
```

- [ ] **Step 2: Write the failing channel, trigger, and open-order tests**

Append these tests to `tests/slack/test_practice_preview.py`:

```python
def test_preview_command_rejects_every_other_channel_before_opening_a_view():
    ack = MagicMock()
    client = MagicMock()

    bolt_module._handle_tcsc_command(
        ack=ack,
        command=_preview_command(channel_id="C_OTHER"),
        client=client,
        logger=MagicMock(),
    )

    ack.assert_called_once_with()
    client.views_open.assert_not_called()
    client.chat_postEphemeral.assert_called_once_with(
        channel="C_OTHER",
        user="U_PREVIEWER",
        text=":warning: Practice Preview is available only in the test channel.",
    )


def test_preview_command_reports_a_missing_trigger_without_building_or_opening():
    ack = MagicMock()
    client = MagicMock()
    logger = MagicMock()

    with patch("app.slack.modals.build_practice_preview_modal") as build_preview:
        bolt_module._handle_tcsc_command(
            ack=ack,
            command=_preview_command(trigger_id=""),
            client=client,
            logger=logger,
        )

    ack.assert_called_once_with()
    build_preview.assert_not_called()
    client.views_open.assert_not_called()
    logger.error.assert_called_once()
    client.chat_postEphemeral.assert_called_once_with(
        channel="C07G9RTMRT3",
        user="U_PREVIEWER",
        text=":warning: Could not open Practice Preview. Please try again.",
    )


def test_preview_command_acks_before_opening_the_synthetic_view():
    events = []
    client = MagicMock()
    modal = {"type": "modal", "callback_id": "practice_preview"}

    def record_ack():
        events.append("ack")

    def record_open(**kwargs):
        events.append("views_open")
        assert kwargs == {"trigger_id": "TRIGGER_PREVIEW", "view": modal}

    client.views_open.side_effect = record_open
    with patch(
        "app.utils.now_central_naive", return_value=PREVIEW_DATE
    ), patch(
        "app.slack.modals.build_practice_preview_modal", return_value=modal
    ) as build_preview:
        bolt_module._handle_tcsc_command(
            ack=record_ack,
            command=_preview_command(),
            client=client,
            logger=MagicMock(),
        )

    assert events == ["ack", "views_open"]
    build_preview.assert_called_once_with(PREVIEW_DATE)
    client.chat_postEphemeral.assert_not_called()
```

- [ ] **Step 3: Write the failing Slack-error, ordinary-command, exact-match, and submission tests**

Append:

```python
def test_preview_command_reports_views_open_failure_ephemerally():
    ack = MagicMock()
    client = MagicMock()
    client.views_open.side_effect = RuntimeError("Slack unavailable")
    logger = MagicMock()

    with patch(
        "app.slack.modals.build_practice_preview_modal",
        return_value={"type": "modal", "callback_id": "practice_preview"},
    ):
        bolt_module._handle_tcsc_command(
            ack=ack,
            command=_preview_command(),
            client=client,
            logger=logger,
        )

    ack.assert_called_once_with()
    logger.exception.assert_called_once()
    client.chat_postEphemeral.assert_called_once_with(
        channel="C07G9RTMRT3",
        user="U_PREVIEWER",
        text=":warning: Could not open Practice Preview. Please try again.",
    )


def test_ordinary_tcsc_command_keeps_the_existing_processor_path(monkeypatch):
    ack = MagicMock()
    client = MagicMock()
    response = {"text": "Existing help", "blocks": [{"type": "divider"}]}
    monkeypatch.setattr(bolt_module, "get_app_context", lambda: nullcontext())

    with patch(
        "app.slack.commands.handle_tcsc_command", return_value=response
    ) as process_command:
        bolt_module._handle_tcsc_command(
            ack=ack,
            command=_preview_command(text="help", channel_id="C_MEMBER"),
            client=client,
            logger=MagicMock(),
        )

    ack.assert_called_once_with()
    process_command.assert_called_once_with("help", "U_PREVIEWER", "previewer")
    client.views_open.assert_not_called()
    client.chat_postEphemeral.assert_called_once_with(
        channel="C_MEMBER",
        user="U_PREVIEWER",
        text="Existing help",
        blocks=[{"type": "divider"}],
    )


def test_preview_command_requires_an_exact_subcommand(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(bolt_module, "get_app_context", lambda: nullcontext())

    with patch(
        "app.slack.commands.handle_tcsc_command",
        return_value={"text": "Unknown command", "blocks": None},
    ) as process_command:
        bolt_module._handle_tcsc_command(
            ack=MagicMock(),
            command=_preview_command(text="practice-preview extra"),
            client=client,
            logger=MagicMock(),
        )

    process_command.assert_called_once_with(
        "practice-preview extra", "U_PREVIEWER", "previewer"
    )
    client.views_open.assert_not_called()


def test_preview_submission_only_acknowledges_and_closes():
    ack = MagicMock()

    with patch.object(
        bolt_module,
        "_parse_practice_authoring_values",
        side_effect=AssertionError("preview must not parse create fields"),
    ), patch.object(
        bolt_module,
        "get_app_context",
        side_effect=AssertionError("preview must not open an app context"),
    ):
        bolt_module._handle_practice_preview_submission(ack)

    ack.assert_called_once_with()
```

- [ ] **Step 4: Run the routing tests and verify the helpers are missing**

Run:

```bash
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= \
  env/bin/pytest tests/slack/test_practice_preview.py -q
```

Expected: the two modal-factory tests pass; routing tests fail with `AttributeError` because `_handle_tcsc_command` and `_handle_practice_preview_submission` do not exist yet.

- [ ] **Step 5: Add the preview channel and error-copy constants**

In `app/slack/bolt_app.py`, immediately after `_FULL_EDIT_UNSYNCED_ERROR`, add:

```python
_PRACTICE_PREVIEW_CHANNEL_ID = "C07G9RTMRT3"
_PRACTICE_PREVIEW_CHANNEL_ONLY_TEXT = (
    ":warning: Practice Preview is available only in the test channel."
)
_PRACTICE_PREVIEW_RETRY_TEXT = (
    ":warning: Could not open Practice Preview. Please try again."
)
```

- [ ] **Step 6: Make the decorated `/tcsc` listener a thin delegate**

Replace the current decorated `/tcsc` listener body in `app/slack/bolt_app.py` with:

```python
    @bolt_app.command("/tcsc")
    def handle_tcsc_command(ack, command, client, logger):
        """Handle /tcsc slash commands, including the test-only preview."""
        _handle_tcsc_command(ack, command, client, logger)
```

Do not change `app/slack/commands.py`: ordinary commands continue through it from the always-defined helper in the next step.

- [ ] **Step 7: Register the preview-specific view listener**

Immediately before the existing `@bolt_app.view("practice_create")` listener, add:

```python
    @bolt_app.view("practice_preview")
    def handle_practice_preview_submission(ack):
        """Close Practice Preview without parsing or persisting its fields."""
        _handle_practice_preview_submission(ack)
```

This listener deliberately accepts only `ack`; Slack Bolt therefore has no path from this callback to create-state parsing, a client call, or application data.

- [ ] **Step 8: Add the always-defined command and submission helpers**

At the beginning of the always-defined helper section in `app/slack/bolt_app.py`, before `_safe_get`, add:

```python
def _handle_tcsc_command(ack, command: dict, client, logger) -> None:
    """Route /tcsc while keeping Practice Preview isolated from persistence."""
    ack()

    command_text = command.get("text", "")
    user_id = command.get("user_id", "")
    user_name = command.get("user_name", "")
    channel_id = command.get("channel_id", "")

    if command_text.strip().lower() == "practice-preview":
        if channel_id != _PRACTICE_PREVIEW_CHANNEL_ID:
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=_PRACTICE_PREVIEW_CHANNEL_ONLY_TEXT,
            )
            return

        trigger_id = command.get("trigger_id")
        if not trigger_id:
            logger.error("No trigger_id in /tcsc practice-preview command")
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=_PRACTICE_PREVIEW_RETRY_TEXT,
            )
            return

        from app.slack.modals import build_practice_preview_modal
        from app.utils import now_central_naive

        practice_date = now_central_naive().replace(
            hour=18, minute=15, second=0, microsecond=0
        )
        modal = build_practice_preview_modal(practice_date)
        try:
            client.views_open(trigger_id=trigger_id, view=modal)
        except Exception:
            logger.exception("Could not open Practice Preview")
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=_PRACTICE_PREVIEW_RETRY_TEXT,
            )
        return

    from app.slack.commands import handle_tcsc_command as process_command

    with get_app_context():
        response = process_command(command_text, user_id, user_name)

    client.chat_postEphemeral(
        channel=channel_id,
        user=user_id,
        text=response.get("text", ""),
        blocks=response.get("blocks"),
    )


def _handle_practice_preview_submission(ack) -> None:
    """Dismiss the synthetic preview without reading or saving its state."""
    ack()
```

Keep both helpers outside the `_bot_token` conditional. This is required for blank-credential tests and makes the discard behavior reviewable without initializing a Bolt app.

- [ ] **Step 9: Run the routing and adjacent `/tcsc` tests**

Run:

```bash
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= \
  env/bin/pytest \
    tests/slack/test_practice_preview.py \
    tests/slack/test_practice_create_modal.py \
    tests/slack/test_practice_edit_full.py \
    -q
```

Expected: all selected tests pass. In particular, accepted preview commands call `ack` before `views_open`, rejected commands never open a view, exact-match failures use the existing processor, and preview submission only acknowledges.

- [ ] **Step 10: Commit the Slack routing seam**

```bash
git add app/slack/bolt_app.py tests/slack/test_practice_preview.py
git commit -m "feat(slack): add test-channel practice preview command"
```

### Task 3: Keep Incomplete Admin Reaction Rows Neutral Until Both Fields Exist

**Files:**

- Create: `tests/practices/test_plan_reaction_ui_source.py`
- Modify: `app/templates/admin/practices/config.html` inside `savePlanReactions()`
- Test: `tests/routes/test_admin_practice_plan_reactions.py`

**Interfaces:**

- Consumes: existing `firstIncompleteRow()`, `setStatus(message, isError)`, `PlanReactionEditor.get(rows)`, and `AdminUI.mutate(...)` JavaScript functions.
- Produces: the unchanged `savePlanReactions() -> void` browser function with a neutral, non-mutating early return for any partial or blank row.

- [ ] **Step 1: Write a dependency-free failing source-contract test**

Create `tests/practices/test_plan_reaction_ui_source.py` with:

```python
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
```

The test intentionally reads only the template source. It runs without Flask, PostgreSQL, or a browser, and it locks the exact microcopy and branch semantics that were approved.

- [ ] **Step 2: Run the source test and confirm it catches the current premature error**

Run:

```bash
env/bin/pytest tests/practices/test_plan_reaction_ui_source.py -q
```

Expected: the first test fails because the current branch uses `Complete both fields or remove the unfinished reaction.`, passes `true`, and calls `.focus()`; the complete-row preservation test passes.

- [ ] **Step 3: Replace only the incomplete-row branch**

In `app/templates/admin/practices/config.html`, replace:

```javascript
        const incomplete = firstIncompleteRow();
        if (incomplete) {
            setStatus('Complete both fields or remove the unfinished reaction.', true);
            const emoji = incomplete.querySelector('.plan-reaction-emoji');
            const label = incomplete.querySelector('.plan-reaction-label');
            (!emoji.value.trim() ? emoji : label).focus();
            return;
        }
```

with:

```javascript
        const incomplete = firstIncompleteRow();
        if (incomplete) {
            setStatus('Complete both fields to save.', false);
            return;
        }
```

Do not change `firstIncompleteRow()`: a fully blank added row and a row with only one populated field must both wait neutrally. Do not change the complete-row promise chain or its error styling.

- [ ] **Step 4: Run the source contract and existing server validation tests**

Run:

```bash
env/bin/pytest \
  tests/practices/test_plan_reaction_ui_source.py \
  tests/routes/test_admin_practice_plan_reactions.py \
  -q
```

Expected: all selected tests pass. The source contract covers the client-side early return; the route suite continues to cover valid saves plus malformed, reserved, duplicate, and conflicting reaction errors.

- [ ] **Step 5: Smoke-test the interaction in a browser against disposable local data**

Start the existing local app with its development database, sign in as an admin, and open `/admin/practices/config`. Repeat the following once for an Activity and once for a Workout Type:

1. Open a saved record and add a Plan-reaction row.
2. Enter an emoji shortcode, then press Tab into its label.
3. Confirm the label receives normal browser focus, the live status says `Complete both fields to save.` in neutral styling, and the browser Network panel shows no edit request.
4. Enter the label and leave the field; confirm exactly one edit request completes and the live status progresses through `Saving…` to `Saved.`.
5. Enter a complete reserved or malformed emoji; confirm the server response is rendered as a red error without redirecting focus.
6. At desktop width and at a viewport no wider than 767px, confirm the editor does not overflow and the console remains free of errors.

Use records created for local testing or restore their original values after the smoke. Do not perform this interaction against production settings.

- [ ] **Step 6: Commit the admin interaction correction**

```bash
git add \
  app/templates/admin/practices/config.html \
  tests/practices/test_plan_reaction_ui_source.py
git commit -m "fix(admin): keep incomplete reaction defaults neutral"
```

### Task 4: Verify the Integrated Change and Run the Native Slack Release Gate

**Files:**

- Verify: `app/slack/modals.py`
- Verify: `app/slack/bolt_app.py`
- Verify: `app/templates/admin/practices/config.html`
- Verify: `tests/slack/test_practice_preview.py`
- Verify: `tests/practices/test_plan_reaction_ui_source.py`

**Interfaces:**

- Consumes: all deliverables from Tasks 1–3.
- Produces: a test-verified branch plus a post-deployment native Slack acceptance result; it produces no database or Slack cleanup artifact.

- [ ] **Step 1: Run the focused regression set with Slack initialization disabled**

Run:

```bash
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= \
  env/bin/pytest \
    tests/slack/test_practice_preview.py \
    tests/slack/test_practice_create_modal.py \
    tests/slack/test_practice_edit_full.py \
    tests/slack/test_modals_person_select.py \
    tests/practices/test_plan_reaction_ui_source.py \
    tests/routes/test_admin_practice_plan_reactions.py \
    -q
```

Expected: all selected tests pass with no Slack token, proving that preview construction, routing, and submission do not depend on a live workspace.

- [ ] **Step 2: Run the full automated suite**

Run:

```bash
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest -q
```

Expected: the suite exits zero with no failures or errors. If an unrelated environment-dependent test cannot run, record its exact command and output rather than treating it as a feature success.

- [ ] **Step 3: Audit the final diff for scope and hygiene**

Run:

```bash
git diff --check
git status --short
git log --oneline -4
git diff HEAD~3 -- \
  app/slack/modals.py \
  app/slack/bolt_app.py \
  app/templates/admin/practices/config.html \
  tests/slack/test_practice_preview.py \
  tests/practices/test_plan_reaction_ui_source.py
```

Expected:

- `git diff --check` prints nothing.
- `git status --short` contains only the pre-existing untracked `env` symlink.
- The three implementation commits are present.
- The diff contains no model, migration, `app/slack/commands.py`, help-copy, role-check, create/edit submission, announcement, RSVP, or harness-state changes.

- [ ] **Step 4: Perform the post-deployment native Slack smoke test**

After deploying the verified branch:

1. In channel `C07G9RTMRT3`, invoke `/tcsc practice-preview`.
2. Confirm the modal title is `Practice Preview`, its primary action is `Close Preview`, the date is the current Central calendar date, and time is 6:15 PM.
3. Inspect desktop and mobile Slack layouts. Confirm Theodore Wirth - Trailhead, both Activity options, both Workout Type options, Preview Coach, Preview Lead, and all four reaction lines render correctly.
4. Change selectors and confirm the multiline reaction snapshot does not recalculate.
5. Edit, reorder, and clear reaction text locally, then select `Close Preview`; confirm the modal dismisses without a creation confirmation.
6. Confirm no practice, Slack message, thread, reaction, timestamp, weekly summary, coach summary, or validation-harness record was created or changed.
7. Invoke `/tcsc practice-preview` outside `C07G9RTMRT3`; confirm the ephemeral test-channel message appears and no modal opens.

No teardown follows this smoke test. Slack owns and dismisses the modal, and both invocation and submission are zero-persistence by design.
