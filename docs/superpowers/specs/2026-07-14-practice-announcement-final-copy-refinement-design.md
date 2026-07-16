# Practice Announcement Final Copy Refinement Design

**Date:** 2026-07-14
**Status:** Approved
**Scope:** RSVP line wrapping and the standalone location heading

## 1. Context

Standalone and combined practice roots already share one RSVP formatter. It
produces one Block Kit `context` block with one `mrkdwn` element, but it always
puts the late-arrival instruction on a second visual line. That separation is
useful when supplemental reaction guidance makes the first line long. It adds
unnecessary height when the post contains only its attendance reaction.

The standalone location section also renders `Where:` even though the other
member-facing headings use a centered dot or no punctuation. The colon makes
that one heading feel visually unrelated to the rest of the post.

## 2. Considered approaches

### 2.1 Conditional line break in the shared formatter — selected

Use one line when no supplemental reactions exist and two lines when they do.
Because standalone and combined announcements already use the same formatter,
this creates one rule for both surfaces without duplicating logic.

### 2.2 Put every RSVP on one line

This is simpler mechanically, but complex rollerski and strength instructions
would become crowded and harder to scan. It does not preserve the approved
grouping for supplemental choices.

### 2.3 Compact only standalone check-mark posts

This matches the most common case but gives combined posts different wrapping
for the same information structure. It would also require surface-specific
behavior in a formatter that is currently shared.

## 3. Approved RSVP grammar

The RSVP remains exactly one `context` block containing exactly one `mrkdwn`
element. Only the separator before the late-arrival instruction changes.

When no supplemental reaction is configured, use one visual line:

```text
Bop :white_check_mark: so we'll know you'll be there. Running late? Reply in the thread. <!channel>
```

The same rule applies to combined attendance reactions:

```text
Bop :six: for Tue at 6:15 PM or :seven: for Wed at 7:15 PM so we'll know you'll be there. Running late? Reply in the thread. <!channel>
```

When one or more supplemental reactions are configured, retain the approved
two-line layout:

```text
{attendance sentence} {supplemental reaction sentence}
Running late? Reply in the thread. <!channel>
```

Slack may still wrap a long line naturally for the member's viewport. The
builder adds no manual newline in the no-supplemental case and exactly one
manual newline in the supplemental case. Coach and lead attribution stays in
its separate context block.

Accessibility fallbacks already express the attendance and late-arrival copy
as continuous prose. Their wording and ordering do not change.

## 4. Approved location grammar

The first location line becomes one bold, dot-separated heading:

```text
*Where · Theodore Wirth - Trailhead*
📍 <address link>
```

The existing location and spot values remain unchanged. When no spot exists,
the line is `*Where · Theodore Wirth*`; when no location exists, it is
`*Where · TBD*`. The existing ASCII hyphen between location and spot remains.
The map-pin address stays on the following line and is omitted under the same
conditions as today.

This change is visual Block Kit copy only. Accessibility fallbacks already use
the prose form `at {location}` and remain unchanged.

## 5. Boundaries and non-goals

- No database, model, migration, settings, default, or authoring-UI change.
- No change to attendance or supplemental reaction seeding and removal.
- No change to combined-session mappings, cancellation behavior, or Details
  replies.
- No change to weekly summaries, urgent notices, coach attribution, or
  accessibility fallback wording.
- No new Block Kit blocks, helper abstraction, or broad builder refactor.
- No production Slack post during development or verification.

## 6. Verification design

Tests will exercise real public builders and prove:

- standalone without supplemental reactions has one RSVP visual line;
- standalone with supplemental reactions has exactly two RSVP visual lines;
- combined without shared supplemental reactions has one RSVP visual line;
- combined with shared supplemental reactions has exactly two RSVP visual
  lines;
- both layouts keep one context block and one element, preserve the complete
  late-arrival/channel tail, and stay within Slack's context limit;
- the location section renders `*Where · location - spot*`, with its address
  behavior unchanged and no `*Where:*` residue;
- accessibility fallbacks remain unchanged;
- the guarded Slack harness validates the conditional line-count rule rather
  than requiring two lines for every RSVP.

After focused and full automated verification, the harness-owned messages in
`C07G9RTMRT3` will be safely replaced. Slack API readback must match the final
local blocks and fallbacks before the refreshed posts are retained for visual
review.
