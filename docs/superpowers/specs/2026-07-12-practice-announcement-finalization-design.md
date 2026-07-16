# Practice Announcement Finalization Design

**Date:** 2026-07-12<br>
**Status:** Approved<br>
**Primary surface:** `#announcements-practices`<br>
**Live validation channel:** `C07G9RTMRT3`<br>
**Builds on:** `docs/superpowers/specs/2026-06-04-practice-announcement-redesign-design.md`

## 1. Purpose

Finish the member-facing practice announcement system so posts are easy to scan, accurate, accessible, resilient to incomplete content, and consistent across creation, editing, cancellation, deletion, and weekly summaries.

The existing standalone announcement hierarchy remains the foundation. This work corrects known bugs, promotes only urgent exceptions, completes defensive handling for the uncommon combined-session case, simplifies the weekly summary, and replaces the hard-coded evergreen behavior with configurable plan reactions.

## 2. Goals

- Preserve the current standalone announcement grammar and visual hierarchy.
- Correct the summer sunset/headlamp calculation and warn when practice runs past sunset.
- Keep an active sibling visible when one practice in a shared Slack post is cancelled or deleted.
- Give every Slack post and update useful screen-reader and notification fallback text.
- Render incomplete or empty content intentionally, without adjacent dividers or empty Details replies.
- Prevent Slack content-limit failures with small, centralized guardrails.
- Promote urgent safety or change information without moving routine conditions into the hero.
- Present a calendar-week summary with one readable section per day and visible cancellations.
- Let Activities and Workout Types define reusable plan-reaction defaults.
- Let authorized leads, coaches, and admins change those defaults for an individual practice.
- Validate every visual state in `C07G9RTMRT3` before posting to the production announcements channel.

## 3. Non-goals

- No standalone announcement redesign from scratch.
- No new weather, air-quality, daylight, or trail integration.
- No emoji picker or live `emoji.list` lookup.
- No separate database table for members' supplemental plan-reaction selections.
- No per-day duplication of reaction defaults in `practice_days` settings.
- No automatic retroactive rewrite of existing practices when a Settings default changes.
- No new combined-session scheduling product. Combined posts remain a supported edge case.
- No broad refactor of unrelated Slack, practice, or admin code.

## 4. Standalone Announcement Grammar

### 4.1 Routine practice

The current hierarchy remains:

1. Header with day, activity, and time.
2. Location and address.
3. Workout, Notes, and Social when present.
4. RSVP and Practice Plan.
5. Coach and lead context.
6. Secondary parking, gear, weather, wind, trails, and routine air quality in the Details thread.

The normal RSVP ending is:

```text
Bop ✅ if you're coming.

Your Practice Plan:
🌲 Endurance instead of intervals · 👟 Run · 🐣 New to rollerskiing
```

`Your Practice Plan:` and its values are rendered only when at least one plan reaction is configured. The heading is bold in Block Kit. The literal label `Optional:` is not used.

The plan line is a generated key/value legend. Each emoji is the Slack reaction key; its label explains what that reaction communicates. Members may select none, one, or several. These reactions supplement the attendance RSVP and never replace ✅.

### 4.2 Incomplete workout

When `workout_description` is empty, the hero renders:

```text
Workout details coming soon.
```

Publication is not blocked. This is an intentional incomplete state, not an empty zone.

### 4.3 Urgent exception promotion

Only the following move into the hero:

- An active NWS weather alert.
- AQI of 101 or higher.
- A headlamp requirement.
- A location or time change to an already-announced practice.

Routine forecast, wind, parking, gear, trails, and AQI below 101 remain in Details.

There is no `No alerts` message. A failed alert lookup is treated as unknown and omitted, never presented as confirmed safe.

When an already-posted practice changes time or location, the edit path compares the saved old and new values. The immediate hero refresh receives a short one-time notice such as `📍 Location updated, check Where below`, and the thread receives an edit note. This does not require historical snapshot columns.

## 5. Daylight and Headlamp Correctness

The daylight integration must ask Astral for results in the practice location's timezone, then normalize the returned datetimes for the application's existing storage and comparison conventions. It must not calculate sunset from a UTC calendar date that can map to the previous Central Time evening.

The headlamp rule is true when either:

- `practice.is_dark_practice` is true; or
- expected practice end is at or after local sunset.

Expected end uses the configured practice duration, currently 90 minutes, added to `practice.date`. Comparing only the start time is incorrect.

If daylight lookup fails, `is_dark_practice` still produces the warning. Otherwise the daylight line is omitted rather than guessed.

Required regression cases:

- A July 7 practice at 6:15 PM Central does not use the previous evening's sunset and does not show a false headlamp warning when it ends before sunset.
- A winter practice that starts before sunset but ends after sunset shows the headlamp warning.
- An explicitly dark practice shows the warning even when daylight data is unavailable.

## 6. Practice Plan Reactions

### 6.1 Terminology

Member-facing and admin-facing copy uses **Plan reactions** or **Your Practice Plan**, not attendance options. Attendance is represented by ✅ for a standalone practice and by the session reaction for a combined post.

### 6.2 Storage

Add these ordered JSON fields:

- `PracticeType.default_plan_reactions`, default `[]`.
- `PracticeActivity.default_plan_reactions`, default `[]`.
- `Practice.plan_reactions`, default `[]`.

Each value has this schema:

```json
[
  {"emoji": "evergreen_tree", "label": "Endurance instead of intervals"},
  {"emoji": "athletic_shoe", "label": "Run"}
]
```

Although these are key/value pairs conceptually, an ordered list is used so the member-facing display order is stable.

### 6.3 Validation

A shared plan-reaction module owns normalization, merging, parsing, formatting, and validation for Settings, web practice editing, Slack modals, and announcement rendering.

Rules:

- Accept bare or colon-wrapped Slack names and store them without outer colons.
- Require a nonblank, single-line member-facing label.
- Limit labels to 80 characters.
- Limit each default set and each resolved practice to four plan reactions.
- Require unique emoji keys within a set.
- Reserve `white_check_mark` and every emoji used for combined-session attendance.
- Deduplicate the same emoji and label when inherited from multiple sources.
- Reject the same emoji with different labels in one resolved practice. The error identifies both Settings sources; no precedence rule silently chooses one.
- Validate shortcode syntax locally. Do not add a network call to Slack's emoji catalog.

### 6.4 Default resolution

On practice creation:

1. Read defaults from the selected Workout Types, ordered by type name.
2. Read defaults from the selected Activities, ordered by activity name.
3. Preserve the order within each source.
4. Deduplicate identical pairs and validate the effective list.
5. Copy the final list into `Practice.plan_reactions`.

The saved practice value is a snapshot. Later Settings changes affect newly created practices only. An existing practice changes only through an explicit per-practice edit or **Restore defaults** action.

The current `practice_days` settings already preselect Workout Type and Activity IDs. Therefore the normal weekly Slack creation flow receives plan-reaction defaults without adding another field to each day configuration.

### 6.5 Settings UI

The existing Activities and Types tabs on the Practices Configuration page each gain an inline **Plan reactions** editor. Each row contains:

- Slack emoji shortcode.
- Member-facing label.
- Remove action.

An **Add reaction** action appends a row. Helper copy reads:

```text
Added automatically when this activity or workout type is selected.
```

The editor uses the existing form-control and autosave vocabulary. It does not open a new modal and does not introduce a separate global reaction registry.

### 6.6 Web practice creation and admin editing

On a new practice, the web editor derives Plan reactions from the selected Activities and Workout Types. Until the coordinator edits the reaction list, changing those selections refreshes the derived preview.

Once a coordinator adds, changes, removes, or reorders a reaction, the visible list becomes the complete practice-specific value and stops auto-refreshing. A **Restore defaults** action recalculates it from the current Activity and Workout Type selections.

On an existing practice, the editor always shows the saved snapshot. Changing Activity or Workout Type does not silently overwrite it. The same **Restore defaults** action is available when the coordinator wants the current Settings values.

An explicitly empty list means the practice has no Plan reactions and the Slack section is omitted.

### 6.7 Slack practice creation modal

The existing practice creation modal available to authorized practice leads and coaches gains one multiline **Plan reactions** input. It is prefilled from the Activity and Workout Type defaults already selected when the modal opens. This is the existing coach-review creation path; the feature does not create a new public Slack entry point.

Format:

```text
:evergreen_tree: Endurance instead of intervals
:athletic_shoe: Run
```

Hint:

```text
Defaults loaded from Settings. Edit as needed for this practice, one reaction per line.
```

The visible submitted value is authoritative. A lead or coach may change, add, remove, reorder, or clear the defaults before creating the practice. If the Activity or Workout Type selectors are changed in the same modal, the Plan reactions field is not silently recalculated; the coordinator updates the visible list when needed. The modal does not use dynamic `views.update` behavior, which keeps it predictable and simple.

The server parses and validates the field before acknowledging submission so errors appear on the input. Existing role checks remain the authority for who can access and submit the modal.

### 6.8 Evergreen migration

For each existing `PracticeType` with `has_intervals = true`, seed:

```json
[{"emoji": "evergreen_tree", "label": "Endurance instead of intervals"}]
```

Backfill the same snapshot onto existing interval practices so current behavior does not disappear. Then remove both hard-coded `has_intervals` branches that currently render and seed evergreen. `has_intervals` remains useful workout metadata but is no longer the source of announcement copy.

### 6.9 Reaction and RSVP semantics

- Seed ✅ and every configured Plan reaction on standalone posts.
- Only ✅ creates or updates a standalone `PracticeRSVP`.
- Removing ✅ removes the matching going RSVP and refreshes the displayed count.
- Plan-reaction additions and removals do not mutate `PracticeRSVP`.
- The Slack app subscribes to both `reaction_added` and `reaction_removed`.
- When an edit adds a Plan reaction, seed the new reaction best-effort.
- When an edit removes one, remove the bot's own seed best-effort. Member reactions are not deleted.
- Updated legend copy is authoritative when historical member reactions remain on the message.

Slack reaction state is sufficient for the supplemental choices in this version. There is no reporting or persistence table for which member selected which plan reaction.

## 7. Empty Content and Details Lifecycle

Block builders assemble populated content groups first, then insert dividers between groups. They never emit adjacent dividers.

The Details builder returns no blocks when parking, gear, conditions, alerts, wind, daylight, air quality, and trail information are all absent.

On initial announcement creation, no Details reply is posted when its block list is empty.

On refresh:

- If Details now contain content and no reply exists, create it.
- If Details contain content and a reply exists, update it.
- If Details become empty and a reply exists, delete it and clear `slack_details_ts`.

This prevents both header-only replies and stale logistics or conditions.

Conditions are gathered once per announcement render and reused by hero, Details, and fallback-text builders. A refresh must not make separate weather or alert calls that can disagree inside the same post.

## 8. Accessibility and Notification Fallback

Every `chat.postMessage` and `chat.update` call for these surfaces receives complete top-level plain text:

- Standalone announcement and refresh.
- Details reply and refresh.
- Cancellation notice.
- Combined announcement.
- Weekly summary.

Standalone fallback includes date, time, location, workout or incomplete state, urgent exceptions, RSVP instruction, and Plan-reaction meanings. Example:

```text
Tuesday, July 14 at 6:15 PM at Theodore Wirth. Workout: 5 x 4 minutes at threshold. Headlamp required. RSVP with ✅. Your Practice Plan: 🌲 Endurance instead of intervals.
```

RSVP-count refresh code must rebuild or preserve this complete fallback. It must not replace it with a generic string such as `Practice on Tuesday`.

## 9. Content-Limit Guardrails

Use one small Slack-text helper for:

- Header text, maximum 150 characters.
- Section text, maximum 3,000 characters.
- Context text, maximum 2,000 characters.
- Top-level fallback text, target maximum 4,000 characters.

New edits to `workout_description` and `logistics_notes` are limited to 2,500 characters in the web and Slack authoring surfaces, leaving room for their Block Kit labels. Plan-reaction labels are limited to 80 characters as defined above. Existing Activity, Workout Type, and Location database limits remain unchanged. The renderer remains the final defense: it truncates safely with an ellipsis and logs the field and practice ID instead of allowing a Slack post or update to fail.

No database length constraints or generalized rich-text framework are introduced.

## 10. Combined-Session Defensive Compatibility

Combined sessions are expected to be uncommon. The standalone message remains the primary design and test priority. Combined support exists so a rare shared Strength post cannot lose an active practice.

A combined post uses the same hierarchy as standalone, with a **Choose a session** section and one stable reaction per session. Plan reactions are shared at the announcement level and appear under `Your Practice Plan:` only when every session has the same saved list.

Only combine sessions whose location, shared workout content, notes, and Plan reactions are compatible and whose attendance reactions are unique and stable. Otherwise post standalone announcements.

Cancellation behavior:

- Cancelling one session keeps the shared root.
- The cancelled session stays visible as `CANCELLED`, with its reason.
- Active siblings remain visible and usable.
- New RSVPs for the cancelled slot are ignored.
- A cancellation thread note identifies the affected session.

Deletion behavior:

- Query siblings by both Slack channel ID and message timestamp.
- If siblings remain, rebuild the root without the deleted practice.
- Rebuild or remove the shared Details reply from the remaining sessions using the normal empty-Details rules.
- Never call `chat.delete` while another practice references the shared root.
- If one session remains, retain the combined grammar for that post's remaining lifecycle so its reaction mapping stays stable.
- Delete the Slack root only when the final sibling is deleted.
- If rebuilding fails, leave the existing shared message intact and report the error. A temporarily stale slot is safer than hiding an active practice.

## 11. Weekly Summary

The weekly builder receives an explicit Monday and covers Monday through Sunday.

Heading example:

```text
Practices this week · July 13-19
```

Content example:

```text
Tuesday, July 14 · 6:15 PM
Run intervals · Theodore Wirth
Forecast: 78°F, partly cloudy

Thursday, July 16
6:05 PM · Strength · Balance Fitness
7:20 PM · Strength · Balance Fitness
```

Rules:

- One section per calendar day.
- Correct cross-month and cross-year formatting.
- The Sunday job targets the coming Monday.
- Multiple sessions on a day are grouped under that day.
- Cancelled practices remain visible as `CANCELLED`, including the reason.
- The `Daily details posted ...` footer is generated from actual non-cancelled practice days.
- Weekly top-level fallback includes the week range and each practice or cancellation.

## 12. Data and Component Boundaries

Keep responsibilities narrow:

- `app/practices/plan_reactions.py`: normalization, validation, default resolution, Slack-line parsing, and formatting.
- Practice models: store default lists and the per-practice snapshot.
- Settings routes and UI: edit defaults on Activities and Workout Types.
- Practice create/edit routes and UI: derive, customize, restore, and persist the snapshot.
- Slack modal handlers: prefill, parse, validate, and persist the visible per-practice list.
- Announcement block builders: render already-resolved Practice data without querying Settings.
- Announcement orchestration: gather conditions once, build blocks and fallback, and post/update hero and Details.
- RSVP event handling: distinguish attendance reactions from supplemental Plan reactions.
- Weekly-summary builder: format the explicit calendar week without announcement-side effects.

No block builder performs database writes or Slack API calls.

## 13. Error Handling

- Invalid Plan reaction input returns a field-specific admin or Slack modal error.
- Conflicting inherited emoji labels name the conflicting Activity or Workout Type sources.
- More than four effective Plan reactions blocks creation until Settings or the individual practice is corrected.
- Weather, alert, daylight, air-quality, and trail failures omit only unavailable content and log the integration failure.
- Slack reaction seeding failures are logged and do not roll back a successfully posted announcement.
- Details creation/update/deletion failure does not delete the hero.
- Shared-post rebuild failure never falls back to deleting the shared root.
- Content truncation logs enough context to identify the source field without logging tokens or credentials.

## 14. Automated Verification

Tests cover:

### Plan reactions

- Bare and colon-wrapped shortcode parsing.
- Stable order and formatting.
- Duplicate collapse.
- Conflicting-label rejection.
- Reserved emoji rejection.
- Empty, one, and four-value cases.
- Effective-list overflow.
- Activity and Workout Type merge order.
- Interval default migration and practice backfill.
- Web create, edit, clear, and Restore defaults.
- Slack modal prefill, edit, clear, validation error, and persistence.
- Plan reactions never creating or deleting `PracticeRSVP`.
- ✅ add and remove behavior.

### Standalone and Details

- Correct summer local sunset date.
- End-time headlamp comparison.
- Explicit dark-practice fallback.
- Active alert and AQI promotion.
- Failed alert lookup with no `No alerts` claim.
- Missing workout placeholder.
- No adjacent dividers.
- Empty Details omission and stale Details deletion.
- Complete fallback text on post and every update path.
- Header, section, context, and fallback length boundaries.

### Combined defensive behavior

- Compatible grouping and standalone fallback for incompatible sessions.
- Mixed active/cancelled rendering.
- One-session cancellation preserving siblings.
- One-session deletion preserving the shared root.
- Final-sibling deletion removing the root.
- Rebuild failure preserving the existing root.
- Stable RSVP mapping and cancelled-slot rejection.

### Weekly summary

- Monday-to-Sunday range.
- Cross-month and cross-year heading.
- One and multiple practices per day.
- Visible cancellation and reason.
- Dynamic footer days.
- Complete weekly fallback.

## 15. Live Validation and Release Gate

Use `scripts/validate_announcement.py`; do not use the older root manual script that can touch production data.

Harness guardrails:

- Hard-code and assert `C07G9RTMRT3` as the only allowed destination.
- Strip `<!channel>` from test content.
- Use synthetic practices rather than production practice rows.
- Give every run a unique visible label.
- Record each posted timestamp immediately.
- Seed configured reactions.
- Delete all test messages during teardown.

Live scenarios:

1. Routine standalone practice.
2. July evening with no false headlamp warning.
3. Legitimate end-after-sunset warning.
4. Active weather alert.
5. AQI at the promotion threshold.
6. Missing workout.
7. No Details content.
8. Intervals with evergreen default.
9. Multiple Plan reactions.
10. Per-practice override and explicitly empty Plan reactions.
11. Long content at safe boundaries.
12. Weekly summary crossing a month boundary with a cancellation.
13. Combined Strength and mixed cancellation as defensive regression cases.

The product owner reviews the test messages on mobile and desktop. Nothing posts to `#announcements-practices` until explicit sign-off.

## 16. Delivery Shape

The later implementation plan should divide this design into independently reviewable workstreams while preserving one final live-validation gate:

1. Shared Plan-reaction model, resolver, migration, and authoring UI.
2. Standalone correctness, urgent promotion, empty states, accessibility, and limits.
3. Combined-session cancellation/deletion safety and defensive rendering.
4. Weekly-summary simplification.
5. Automated regression matrix and test-channel validation.

No implementation begins until this written specification is reviewed and approved.
