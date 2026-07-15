# Structured Practice Reaction Editor and Multisport Defaults Design

**Date:** 2026-07-15<br>
**Status:** Draft for written review<br>
**Primary surfaces:** Slack practice Create, Preview, and Full Edit; Admin
practice Create/Edit; Practices Settings<br>
**Live validation channel:** `C07G9RTMRT3`<br>
**Builds on:**

- `docs/superpowers/specs/2026-07-12-practice-announcement-finalization-design.md`
- `docs/superpowers/specs/2026-07-14-practice-preview-design.md`

## 1. Purpose and precedence

Replace the typo-prone multiline Plan reactions field with a structured editor,
make practice-level emoji keys immutable, derive Activity defaults only for
multi-activity practices, and seed the defaults supported by historical
`#announcements-practices` usage.

This amendment supersedes the earlier designs only for:

- Plan-reaction default resolution;
- per-practice reaction authoring in Slack and Admin;
- reaction reconciliation after Activity or Workout Type changes;
- the interactive behavior of `/tcsc practice-preview`; and
- the operational insertion of historically established defaults.

The existing announcement grammar, accessibility fallback copy, reaction
seeding, RSVP semantics, saved `Practice.plan_reactions` snapshots, Settings
ownership, and preview zero-persistence guarantee otherwise remain unchanged.

## 2. Goals

- Use one safe structured interaction across Slack Create, Preview, Full Edit,
  and Admin practice editing.
- Let Settings remain the only place where an emoji key can be created or
  changed.
- Let a coach edit a reaction's description or remove it for one practice
  without retyping Slack shortcodes.
- Treat two or more selected Activities as multisport and inherit only those
  Activities' configured reaction pairs.
- Keep Workout Type defaults independent, including interval endurance.
- Reconcile inherited rows after selector changes without erasing unrelated
  form fields or surviving customizations.
- Add reactions safely from the existing Settings catalog when no inherited
  default exists or a selected Multisport Activity is unconfigured.
- Preserve the four-reaction limit and existing validation semantics.
- Record the historical extraction and insert approved defaults safely and
  idempotently.
- Exercise the native Slack experience only in `C07G9RTMRT3` before release.

## 3. Non-goals

- No new Multisport Workout Type, `is_multisport` flag, or name-based
  Multisport heuristic.
- No new Plan-reaction database table or member-choice persistence.
- No live Slack emoji picker or arbitrary shortcode entry in a practice
  editor.
- No runtime Slack-history scraping.
- No automatic rewrite of already-saved practice snapshots when Settings
  defaults change.
- No change to attendance/session reactions or their authorization rules.
- No broad rewrite outside the Plan-reaction editor and its selector actions;
  the existing modal/form shells and announcement system remain intact.
- No production announcement post during development or verification.

## 4. Domain model and terminology

The existing JSON schema remains unchanged:

```json
[
  {"emoji": "evergreen_tree", "label": "Endurance instead of intervals"}
]
```

The existing fields remain authoritative:

- `PracticeType.default_plan_reactions` stores ordered type defaults.
- `PracticeActivity.default_plan_reactions` stores ordered Activity defaults.
- `Practice.plan_reactions` stores the final practice-specific snapshot.

No schema migration is required for the editor or the Multisport rule.

This document uses:

- **Settings default** for a pair owned by a Workout Type or Activity.
- **Inherited row** for a Settings default currently applicable to a practice.
- **Catalog row** for a pair selected from configured Settings pairs for one
  practice.
- **Removed row** for a row hidden from the submitted value but retained in the
  open editor so it can be undone.
- **Multisport practice** for any practice with two or more selected Activities.

## 5. Default resolution

### 5.1 Multisport criterion

The number of selected Activities is the complete Multisport criterion after
the server resolves submitted IDs to distinct, valid Activity records. Unknown
IDs are rejected and duplicate IDs count once:

- zero or one selected Activity: do not inherit Activity defaults;
- two or more selected Activities: inherit defaults from every selected
  Activity.

The existing multi-selects in Slack and Admin already support this authoring
model. No additional Multisport control is introduced.

An Activity may define zero, one, or several ordered reaction pairs. Activity
defaults being ignored for a single-Activity practice prevents choices such as
`:athletic_shoe: runner` from appearing on routine Run-only practices.

### 5.2 Merge order

Effective defaults are resolved in this order:

1. selected Workout Types, sorted by name;
2. when at least two Activities are selected, selected Activities sorted by
   name;
3. each source's configured row order.

Workout Type defaults always apply. Therefore an interval Multisport practice
may inherit the evergreen Type row and the selected Activities' rows.

The existing domain rules continue to apply:

- identical emoji/label pairs from multiple sources deduplicate;
- the same emoji with different labels is an error naming both sources;
- reserved attendance/session emojis are rejected;
- invalid or blank rows are rejected; and
- the resolved practice may contain no more than four rows.

Nothing is silently truncated or chosen by precedence when validation fails.

### 5.3 Unconfigured Activities

An Activity with no defaults contributes no row. In a Multisport editor, each
such Activity is named in a neutral inline notice so the omission is visible.
The notice is non-blocking because an empty mapping may be intentional. The
safe **Add reaction** catalog control remains available in this state.

## 6. Approved historical defaults

The implementation records the reviewed extraction from all 1,097 messages
returned by the `#announcements-practices` channel history.

The stable findings are:

- Interval endurance was introduced on February 3, 2026 and then appeared on
  12 of the next 13 interval announcement roots. The channel explicitly said
  it applied to practices tagged with intervals.
- Run, rollerski, and bike choices recur across Multisport announcements from
  2024 through 2026, although their shortcode presentation drifted.
- The new/experienced rollerskier and runner trio appears on the June 2 and
  July 7, 2026 Rollerski + Run practices and is the approved current grammar.
- Historical strength-session reactions, attendance checkmarks, isolated
  social reactions, and older skate/classic experiments are not Plan defaults.

The approved insertion is:

| Settings source | Ordered defaults |
|---|---|
| Every existing `has_intervals = true` Workout Type | `:evergreen_tree:` — `Endurance instead of intervals` |
| `Run` Activity | `:athletic_shoe:` — `runner` |
| `Bike` Activity | `:bike:` — `bike` |
| `Mountain Bike` Activity | `:mountain_bicyclist:` — `mountain biker` |
| `Classic Rollerski` Activity | `:hatching_chick:` — `new rollerskier`; `:older_adult::skin-tone-4:` — `experienced rollerskier` |
| `Skate Rollerski` Activity | the same two Rollerski rows |
| `Skate/Classic Rollerski` Activity | the same two Rollerski rows |

The existing Plan-reaction migration already supplies the interval row. The
new insertion verifies that state but does not duplicate it.

Other Activities remain unconfigured until a stable need is established.

## 7. Settings ownership

The existing Activities and Workout Types Settings editors remain the source
of truth. They continue to allow an admin to:

- enter or change the emoji shortcode;
- enter or change its default description;
- add, remove, and reorder defaults; and
- save no more than four valid rows per Settings source.

Settings copy should make the Multisport rule clear on Activity cards:

```text
Used when this Activity is selected with another Activity.
```

Workout Type helper copy continues to state that its defaults are applied when
the type is selected.

Practice-level fixed-emoji behavior does not apply to Settings, because
Settings is where the key/value pair is intentionally defined.

Settings retains its existing neutral incomplete-row contract. If either half
of a newly added pair is blank, saving leaves Settings unchanged and shows:

```text
Complete both fields to save.
```

The incomplete row is not converted to an error state, focus is not moved, and
no partial mutation occurs.

## 8. Structured practice editor

### 8.1 Active row

Every applicable or catalog-selected pair renders as one structured row:

- fixed emoji/shortcode display;
- editable single-line description, limited to 80 characters; and
- **Remove** action close to the description.

The emoji has no input control in a practice editor. A coach cannot introduce
a typo or change the meaning of a Settings key while editing one practice.

The submitted row order is:

1. any row with an inherited origin, in Settings resolver order;
2. remaining protected snapshot rows, in their saved order; and
3. remaining catalog-only rows, in selection order.

There is no practice-level reorder control.

### 8.2 Slack Block Kit layout

Block Kit does not permit a plain-text input and button in the same block row:
an input element must be the sole element of an Input block, while buttons live
in Actions blocks or supported accessories. Therefore each active Slack row
uses:

1. a compact fixed-emoji label;
2. a description Input block; and
3. a **Remove** action directly beneath it.

This is the closest native structure to an inline delete button and was chosen
over returning to freeform text. The Admin web editor may place **Remove** on
the same visual row because it does not share Block Kit's constraint.

Relevant Slack references:

- <https://docs.slack.dev/reference/block-kit/blocks/input-block/>
- <https://docs.slack.dev/reference/block-kit/blocks/actions-block/>
- <https://docs.slack.dev/reference/block-kit/block-elements/plain-text-input-element/>
- <https://docs.slack.dev/reference/block-kit/block-elements/select-menu-element/>
- <https://docs.slack.dev/reference/block-kit/composition-objects/option-object/>

### 8.3 Remove and Undo

Removing a row does not immediately destroy it. Until the modal/form is
submitted, it becomes a dimmed static row that preserves:

- its fixed emoji;
- its most recently edited description; and
- an **Undo** action.

The submitted `Practice.plan_reactions` value contains active rows only.
Removed rows reserve their emoji and one of the four editor slots until submit,
which guarantees that **Undo** never becomes impossible because another row
was added. The four-slot count is the deduplicated union of active and removed
rows across inherited, protected snapshot, and catalog origins.

Closing the editor discards the working Remove/Undo state. Slack Full Edit and
Admin Create/Edit expose **Restore defaults**. Admin retains its existing
control; Slack Full Edit gains the equivalent structured action.
Restore defaults replaces only the reaction working set with the current
effective defaults, clearing practice-specific descriptions, catalog rows, and
removed state. It does not affect another field or persist until the complete
practice edit is submitted. The editor resolves and validates the current
selectors before replacing anything; a conflict or overflow preserves the
working set and shows the same blocking selector notice as reconciliation.

### 8.4 Add reaction

Coach-facing copy is always **Add reaction**. The phrase `one-off reaction` is
not shown.

Add does not accept arbitrary shortcode text. It exposes only the union of
valid pairs already configured on Activities and Workout Types in Settings.
Exact duplicate pairs appear once. Distinct configured labels for the same
emoji may appear as distinct choices, but a practice can still contain that
emoji only once.

Choosing a catalog option immediately appends a row with:

- the selected fixed emoji;
- its configured description prefilled; and
- the description editable for this practice.

The Add control is shown when:

- the effective inherited list is empty; or
- a selected Multisport Activity has no configured defaults.

It is hidden when four active/removed slots are reserved. Options whose emoji
is already active or removed are unavailable. If the global Settings catalog
is empty, the editor explains that reactions must first be configured in
Settings rather than presenting an empty picker.

Slack's picker is preflighted against its platform bounds. At most 100 distinct
pair options are rendered. If Settings ever produces more, Add shows a clear
configuration error instead of silently dropping choices. Picker text may use
a 75-character, ellipsized presentation label, while its opaque option value
resolves to the complete validated pair; the stored description is never
truncated.

### 8.5 Fixed-emoji scope

The same practice-level rules apply to:

- Slack Create;
- `/tcsc practice-preview`;
- Slack Full Edit;
- Admin practice Create; and
- Admin practice Edit.

This replaces the Slack multiline field and makes the existing Admin editor's
emoji field read-only. Settings remains editable as described in section 7.

## 9. Reconciliation after selector changes

Activity and Workout Type selectors become interactive inputs for reaction
derivation. This supersedes the earlier snapshot-only, no-`views.update`
behavior.

When either selection changes, the editor recomputes effective inherited
defaults and reconciles only reaction rows:

- an inherited emoji that remains applicable preserves its current description
  and Remove/Undo state;
- a newly applicable inherited emoji is added with its Settings label;
- an inherited-only emoji that is no longer applicable is dropped, including
  any removed tombstone, and frees its reserved slot;
- a protected snapshot row survives selector changes until the coach removes
  it or uses **Restore defaults**;
- a catalog row remains untouched;
- duplicate provenance does not create duplicate rows; and
- every non-reaction field remains exactly as entered.

A row may be both catalog-selected and inherited. If a newly selected source
inherits an emoji that already exists as a catalog row, the editor keeps one
row and records both origins. Removing that inherited source later does not
remove the row because its catalog origin still applies.

The same origin merge applies when a newly selected source matches a protected
snapshot row. Removing the inherited source later leaves the protected row in
place.

The transition from one Activity to two enables Activity inheritance. The
transition from two Activities to one removes Activity-inherited-only rows but
keeps Workout Type, protected snapshot, and catalog rows.

After every valid reconciliation, rows return to the order defined in section
8.1. Existing descriptions and removed state move with their row; Undo returns
a row to that position. If a removed inherited-only source becomes
inapplicable and is later selected again, it returns as a fresh active default
rather than restoring stale working state.

For an existing practice, the saved snapshot is the initial active value.
Current defaults are used only when reconciling a selector change or when the
coordinator explicitly chooses **Restore defaults**. Saving still writes one
final snapshot; source/provenance state is not persisted to the database.

Full Edit/Admin reconstructs deterministic working state at open:

- a saved row whose emoji matches a current effective default is treated as
  inherited, while preserving its saved practice-specific description;
- another saved row is treated as a protected practice-specific snapshot row;
  and
- a current effective default missing from the saved snapshot is marked
  suppressed while its current source remains applicable.

Suppression prevents an unrelated selector change from silently restoring a
default that was deliberately removed in an earlier editing session. When all
sources for a suppressed default become inapplicable, its suppression is
dropped; selecting a source again later adds a fresh active default. Because
the database intentionally stores only final pairs, matching is by emoji and
this deterministic reconstruction replaces persisted provenance.

If a selector change would produce a conflict or make the deduplicated union of
active and removed rows across inherited, protected snapshot, and catalog
origins exceed four, the chosen selector value remains visible, the last valid
reaction working set remains unchanged, Add is unavailable, and a blocking
notice names the problem. Submission is rejected against the relevant selector
until a later selection resolves it. An initially invalid Create or Preview
uses an empty last-valid reaction set. Full Edit and Admin Edit instead retain
the saved snapshot as last-valid while blocking submission until the selectors
become valid.

## 10. Slack interaction mechanics

Slack block actions are registered for:

- Activity and Workout Type selection changes;
- Remove;
- Undo;
- Add reaction;
- catalog selection; and
- Restore defaults in Full Edit.

The Activity and Workout Type Input blocks enable Block Kit
`dispatch_action`, allowing their multi-select changes to reach these handlers.

Each handler:

1. acknowledges promptly;
2. captures the complete current `view.state.values` payload and validates the
   structural context needed to rebuild the view;
3. merges current text edits, including temporarily incomplete descriptions,
   with compact reaction working state;
4. performs the approved reconciliation; and
5. calls `views.update` with the current view hash.

Block actions do not run full submission validation. In particular, a coach
may remove a row whose description is currently blank. Complete row, conflict,
and limit validation runs when the modal is submitted.

Rebuilding a view must preserve time, location, workout, Notes, people,
options, notification state, and every other input. Reaction state uses stable
opaque row identifiers; raw emoji or labels are not trusted as action IDs.

Compact, versioned JSON in `private_metadata` carries only the context already
required by the view plus active/removed row origins, removed descriptions,
suppressed emoji/source state, and compact source IDs for the last-valid
working set. Create retains its date/channel context, Full Edit retains its
practice ID, and Preview carries a `preview` mode marker plus synthetic working
state but no database target. The builder measures the final serialized
envelope and fails safely rather than exceeding Slack's 3,000-character limit.
Every action rebuild replaces the metadata with the newly validated state.

For Preview, this deliberately supersedes the July 14 design's empty
`private_metadata` requirement. The bounded, transient envelope is necessary
for native Block Kit interaction, is discarded with the modal, identifies no
practice row, and does not weaken Preview's zero-persistence guarantee.

Production Create and Full Edit handlers load Settings mappings through the
existing application context. The Preview modal receives a small synthetic
catalog and source mapping so its actions use the same reconciliation code
without reading or writing production practice data.

Submission revalidates the active rows server-side. Row-specific description
errors attach to that row's Input block. Cross-source conflicts and limit
errors attach to the relevant Activity/Workout Type selector. Client-side or
modal metadata is never treated as authoritative configuration.

Create accepts only emoji keys supplied by the current effective defaults or
Settings catalog. Full Edit also accepts keys already present in the saved
practice snapshot so removing a default from Settings does not make an existing
practice impossible to save. Any newly catalog-added row remains authorized
only while its emoji key exists in at least one current Settings row; its
practice-specific description need not equal the Settings default. If an admin
removes that key from Settings while the practice modal is open, the modal
preserves the coach's description, marks that row with a specific error, and
requires the coach to remove it or select a valid replacement. Any other newly
introduced unknown key is rejected.

## 11. Admin interaction mechanics

The Admin practice form uses the same domain resolver and reconciliation rules
as Slack. Its client-side editor mirrors the approved states:

- fixed emoji;
- editable description;
- Remove;
- dimmed removed row with Undo;
- conditional Add reaction catalog; and
- Restore defaults in both Create and Edit.

Selection changes update only reaction rows. The live status region announces
missing Activity mappings, validation errors, removals, and restores without
moving focus unexpectedly. The server revalidates the submitted snapshot;
JavaScript is an interaction aid, not the authority.

## 12. Preview contract

`/tcsc practice-preview` remains available only in `C07G9RTMRT3` and keeps its
preview-specific callback. Its fixture selects two Activities so the modal
demonstrates the Multisport rule and includes the approved four-row scenario:

- `:evergreen_tree:` Endurance instead of intervals;
- `:hatching_chick:` new rollerskier;
- `:older_adult::skin-tone-4:` experienced rollerskier; and
- `:athletic_shoe:` runner.

These rows are not injected as a finished practice snapshot. The fixture
defines one interval Workout Type plus `Run` and a Rollerski Activity with
their source defaults, selects both Activities, and obtains all four rows from
the production resolver.

The preview supports selector changes, description edits, Remove/Undo, and the
catalog interaction. Closing or submitting only acknowledges and dismisses the
modal. It creates or changes no database row, Slack message, thread, reaction,
summary, or harness state.

## 13. Historical insertion operation

Implementation includes a dry-run-first, idempotent operational command. It
does not query Slack at runtime. The reviewed source dates and approved mapping
are committed with the operation so its provenance remains auditable.

A committed, read-only extraction manifest is the bridge between the completed
channel review and the insertion command. Its extraction metadata records
channel `C042G463AQ1`, all 1,097 messages returned across six history pages,
and the extraction time. An evidence entry records the message timestamp/date,
selected Activities or Workout Types when known, normalized emoji/label pair,
a minimal evidence excerpt or content hash, confidence/reviewer state, and its
approved Settings target. The command consumes approved targets only; it never
scrapes Slack or promotes an unreviewed observation at runtime.

The operation:

1. selects interval types by `has_intervals`, never by name;
2. resolves Activity targets by exact reviewed names and verifies the expected
   target count before mutation;
3. passes every desired list through shared domain validation;
4. treats an exact current value as a no-op;
5. fills an empty current value;
6. aborts the transaction on a different non-empty value rather than
   overwriting admin customization;
7. locks the resolved target rows and rechecks their values inside the write
   transaction so a concurrent Settings edit cannot be overwritten;
8. supports explicit local/production and dry-run/commit modes; and
9. performs a read-back verification after commit.

For this reviewed one-time seed, an empty value on an exact approved target is
explicitly eligible for insertion even though an empty Activity mapping can be
intentional in ordinary Settings use. The production dry-run diff therefore
requires human approval immediately before commit. A different non-empty value
always remains protected.

The dry run also lists upcoming practices with at least two Activities whose
saved snapshots differ from the newly resolved defaults. It does not rewrite
those snapshots. A coordinator may explicitly use Full Edit/Admin **Restore
defaults** when an upcoming practice should adopt the new mapping.

## 14. Error and empty states

- No active or removed rows: show the empty state and **Add reaction** when its
  visibility rule applies.
- Selected Multisport Activity without defaults: name it neutrally and keep
  Add available.
- No Settings catalog: explain that an admin must configure a pair in Settings.
- Conflicting source labels: name both sources; do not choose one silently.
- More than four reserved rows across all origins: identify the limit and
  require a Settings or selector change; do not truncate.
- Incomplete description: keep the row and attach the error to its field.
- Slack `views.update` failure: log it and leave the current modal usable; do
  not persist partial reaction state.
- Settings lookup failure: preserve the current rows and surface a retryable
  error; never replace them with an empty list.

## 15. Accessibility and content limits

- Every description field has a specific label that includes the fixed emoji's
  accessible name or shortcode.
- Remove and Undo controls name the affected reaction.
- Admin status updates use the existing live region.
- Dimmed state is communicated with text and control state, not color alone.
- Existing 80-character description validation remains authoritative.
- Four rows keep both Slack's modal block count and submitted content well
  within existing limits.
- Member-facing announcement fallback generation remains unchanged and uses
  only the final active snapshot.

## 16. Verification design

### 16.1 Domain tests

Cover:

- zero, one, two, and three selected Activities;
- duplicate Activity IDs counting once and unknown IDs being rejected;
- Type defaults applying with every Activity count;
- Activity defaults beginning at exactly two Activities;
- duplicate Rollerski mappings deduplicating;
- same-emoji label conflicts naming both sources;
- interval plus Multisport merging;
- the four-row boundary and overflow rejection;
- unconfigured Activities; and
- deterministic source and row ordering.

### 16.2 Slack tests

Cover Create, Preview, and Full Edit for:

- fixed emoji and editable description blocks;
- no multiline reaction input;
- Remove, dimmed state, Undo, and conditional Add;
- catalog options coming only from Settings/preview fixtures;
- selector changes reconciling only inherited rows;
- customized descriptions and catalog rows surviving reconciliation;
- protected snapshot rows surviving selection changes, remaining removable,
  keeping saved order, and reserving one of the four slots;
- source disappearance freeing a removed slot and later reselection restoring
  a fresh default;
- saved-snapshot suppression surviving unrelated selector changes, clearing
  when its source disappears, and returning fresh after reselection;
- invalid selector transitions preserving the selected value and last-valid
  reaction rows while blocking Add and submission;
- four-slot validation counting inherited, protected, catalog, and removed
  origins after deduplication;
- every unrelated field surviving `views.update`;
- selector Input blocks enabling `dispatch_action`;
- versioned Preview/Create/Edit metadata remaining below 3,000 characters and
  containing no Preview database target, while suppression and last-valid
  provenance survive a metadata round trip;
- catalog preflight at 100 distinct pairs and 75-character display labels;
- a catalog description remaining editable without losing key authorization,
  while deletion of that emoji key from Settings mid-session preserves entered
  text but blocks submission until removal or replacement;
- view-hash use and retryable update failures;
- Restore defaults replacing only reaction state after successful resolution
  and preserving all state after a conflict or overflow;
- row and cross-source submission errors;
- Preview submission performing zero persistence;
- and Preview's test-channel guard, absence of role lookup, missing-trigger
  error, `views.open` failure, and unchanged routing for ordinary `/tcsc`
  commands.

### 16.3 Admin tests

Cover:

- Settings retaining editable emoji keys;
- Settings incomplete pairs showing `Complete both fields to save.` without
  mutation, error styling, focus movement, or loss of draft text;
- practice Create/Edit rendering fixed emoji keys;
- selector-driven reconciliation;
- source disappearance, reselection, saved-snapshot suppression, and invalid
  selector transitions matching Slack;
- protected snapshot survival, removal, ordering, and slot accounting;
- Remove/Undo, Add, Restore defaults, and accessible status copy;
- catalog-key deletion during an open edit preserving text but blocking invalid
  submission;
- server rejection of tampered emoji data; and
- desktop and mobile browser interaction.

### 16.4 Insertion tests

Cover:

- manifest metadata recording the channel and complete 1,097-message scope;
- only reviewed, approved manifest targets being eligible for insertion;
- dry run making no mutation;
- exact matches being no-ops;
- empty targets being filled;
- conflicting non-empty targets aborting the whole transaction;
- target-count/name drift aborting;
- concurrent value drift being caught by the in-transaction lock and recheck;
- repeat execution being idempotent;
- interval targeting by boolean metadata; and
- existing practice snapshots remaining unchanged after verified read-back.

### 16.5 Live gate

After focused tests and the complete automated suite pass:

1. run `/tcsc practice-preview` in `C07G9RTMRT3`;
2. inspect default rows on desktop and mobile;
3. exercise Activity transitions `1 → 2 → 3 → 1`;
4. edit a surviving description and confirm it remains intact;
5. exercise Remove/Undo;
6. clear the fixture's Type selection and leave one Activity selected so the
   empty-default state exposes **Add reaction**, then exercise the catalog;
7. submit/close and prove no database or Slack-message mutation occurred;
8. exercise Admin Create/Edit on desktop and mobile with disposable local data;
9. run the production insertion dry run and review its exact diff;
10. commit the insertion explicitly and verify read-back; and
11. post nothing to `#announcements-practices` until the complete release is
    approved.

## 17. Completion criteria

The feature is complete when:

- all five practice-authoring surfaces use the approved fixed-emoji editor;
- Activity defaults apply only to practices with at least two Activities;
- selector changes reconcile safely without losing other input;
- the historical mappings are inserted and verified without overwriting any
  different non-empty customization, after explicit approval of empty-target
  changes;
- Preview remains discard-only;
- focused, full-suite, native Slack, and Admin browser checks pass; and
- no test artifact remains in production data or Slack.
