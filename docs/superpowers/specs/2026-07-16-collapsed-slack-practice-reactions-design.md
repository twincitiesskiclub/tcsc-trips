# Collapsed Slack Practice Reactions

**Date:** 2026-07-16  
**Status:** Approved interaction design

## Context

The structured Plan-reaction editor is intentionally detailed because emoji keys are fixed while descriptions, removal, undo, restore, and catalog additions remain editable. Showing every control by default makes the Slack practice modal unnecessarily long and interrupts the more common practice fields.

The reaction area should be the last content in every Slack practice surface: Create, Preview, and Full Edit. Preview continues to reuse the Create builder.

## Decision

Render a compact, read-only summary by default. An **Edit reactions** button expands the existing structured editor in place at the bottom of the same modal. The reveal is one-way for the lifetime of that modal view: once expanded, the editor remains expanded until the modal is submitted or closed.

This avoids a nested modal, keeps the default workflow compact, and does not introduce a second control for hiding incomplete edits.

## Collapsed State

The final section is titled **Plan reactions** and lists the current active pairs in their saved order, one pair per line:

```text
Plan reactions
:evergreen_tree: Endurance instead of intervals
:hatching_chick: New rollerskier
:athletic_shoe: Runner
                                      [Edit reactions]
```

Removed and suppressed rows are not shown. If the active set is empty, the section says **No Plan reactions** and the accessory button says **Add reactions**.

Blocking source errors and unconfigured-Activity guidance remain visible next to the compact summary. A lookup failure retains the current summary and existing retryable error treatment.

## Expanded State

Selecting **Edit reactions** updates the current Slack view in place and replaces the compact summary with the existing fixed-emoji editor blocks. The editor stays at the bottom of the modal.

The expanded state keeps all existing behavior:

- descriptions are editable;
- emoji keys are not editable;
- rows can be removed and undone;
- configured catalog pairs can be added when allowed;
- Full Edit can restore defaults; and
- row errors remain attached to the relevant description input.

There is no **Done**, **Hide**, or collapse action. This prevents partially edited or invalid rows from being hidden behind a summary.

## State and Data Flow

`PlanReactionEditorState` gains an `editor_expanded` boolean, defaulting to `False`. Its serialized schema version is incremented so stale or malformed metadata fails closed.

The existing action and rebuild path remains authoritative:

1. The modal starts collapsed.
2. Activity or Practice Type actions reconcile the working reaction state.
3. A collapsed modal rebuilds as a refreshed summary and stays collapsed.
4. **Edit reactions** sets the expansion boolean and rebuilds the same view through `views.update`.
5. Expanded selector changes, Add, Remove, Undo, and Restore rebuild the full editor and keep it expanded.
6. Matching Block Kit IDs preserve all unrelated unsaved practice fields during every rebuild.

Active descriptions are currently omitted from private metadata because rendered inputs return them in Slack view state. A collapsed view has no description inputs, so it must carry its validated active descriptions in private metadata. Expanded views continue recovering descriptions from their input blocks. Metadata JSON uses `ensure_ascii=False` so valid Unicode labels are not inflated into escape sequences. The existing explicit 3,000-character limit remains the final guard.

Submitting without expanding produces the exact summarized reaction snapshot. Submitting after expansion uses the current input values. Preview remains discard-only and performs no database or message mutation.

## Error Handling and Safety

- The Edit action is valid only for the three expected practice modal callbacks.
- Repeated or stale Edit actions are harmless; Slack view hashes continue protecting concurrent updates.
- Collapsed metadata cannot contain an active blank description because there is no visible row input to receive that validation error.
- Selector IDs, catalog options, metadata structure, block IDs, reaction limits, and description limits retain their existing server-side validation.
- Production Create and Full Edit continue loading reaction sources from authoritative Settings records. Preview continues using its isolated synthetic configuration.

## Verification

Automated coverage must prove:

- Create, Preview, and Full Edit start collapsed with the reaction summary region after every other practice field;
- empty, configured, unconfigured, and blocking states remain understandable;
- Edit expands the same view and preserves every unrelated unsaved field;
- submitting without Edit preserves the exact default or saved snapshot;
- selector changes refresh a collapsed summary;
- selector changes and Restore keep an expanded editor expanded;
- the existing Add, Remove, Undo, Restore, and validation flows still work;
- Unicode descriptions stay within private-metadata bounds;
- malformed or stale expansion actions fail closed; and
- Preview still closes without database, Slack message, thread, or reaction persistence.

Focused Slack reaction suites and the complete automated suite run after implementation. The native Preview check in `C07G9RTMRT3` is repeated before any production seed operation.

## Alternatives Rejected

### Toggleable in-place editor

A **Done** or **Hide** action would make the reveal reversible, but it adds validation and state transitions solely to save space after a user has chosen to edit. It could also hide incomplete edits. The one-way reveal is simpler and clearer.

### Nested child modal

A pushed child modal would require transferring unsaved parent values and reaction state across two views, complicate errors and Preview isolation, and depend on a short-lived trigger. The existing in-place update path already preserves inputs and view hashes.

### Always-expanded editor at the bottom

Moving the existing editor to the bottom improves ordering but does not address its bulk. The collapsed summary preserves the useful current set without forcing controls into the common path.
