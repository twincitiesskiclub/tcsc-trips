# Practice Announcement Copy and Visual Polish Addendum

**Date:** 2026-07-13<br>
**Status:** Approved<br>
**Primary surface:** `#announcements-practices`<br>
**Live validation channel:** `C07G9RTMRT3`<br>
**Builds on:** `docs/superpowers/specs/2026-07-12-practice-announcement-finalization-design.md`

## 1. Purpose and precedence

This addendum captures the product-owner review of the July 12 implementation.
It changes only the member-facing announcement grammar and the smallest shared
formatting support needed to keep that grammar consistent.

Where this document conflicts with the July 12 design, this addendum takes
precedence for:

- standalone RSVP and supplemental-reaction copy;
- combined-session hierarchy and RSVP mappings;
- the member-facing Notes icon;
- weekly-summary icons and footer copy;
- Slack skin-tone modifier validation; and
- the related accessibility and test contracts.

The correctness, lifecycle, persistence, authoring, cancellation, deletion,
and safety behavior already approved in the July 12 design remains unchanged.

## 2. Goals

- Restore the original friendly RSVP rationale, late-arrival instruction, and
  channel mention on every RSVP-bearing root announcement.
- Give supplemental reactions natural sentence grammar instead of a separate
  `Your Practice Plan` heading and key/value legend.
- Keep the attendance and supplemental instructions visually close without
  placing them in separate Block Kit context blocks.
- Remove repeated session-reaction cues from the upper half of combined posts.
- Keep the weekly summary restrained but not visually anonymous.
- Support a standard Slack skin-tone modifier without broadening shortcode
  parsing beyond Slack's documented form.
- Make the change with small shared formatters rather than a builder refactor.

## 3. Non-goals

- No database schema change or data migration.
- No change to Plan-reaction defaults, per-practice overrides, or authoring UI
  ownership.
- No emoji picker or Slack emoji-catalog lookup.
- No new combined-session scheduling workflow.
- No change to Details-thread content or urgent-exception promotion.
- No redesign of coach-review or other internal Slack surfaces.
- No broad announcement-component framework.

## 4. Shared RSVP context grammar

Standalone and combined roots use one shared formatter for their ending RSVP
context. The result is exactly one RSVP `context` block containing one
`mrkdwn` element. It has exactly one intentional newline:

```text
{attendance sentence} {supplemental sentence when configured}
Running late? Reply in the thread. <!channel>
```

Slack may wrap either line naturally for the member's viewport. The formatter
does not add another newline, blank line, heading, bullet, or separator.

When no supplemental reactions are configured, line one contains only the
attendance sentence. Line two is still present so late-arrival guidance and
the channel mention remain consistent.

Coach and lead attribution remains in its existing, separate context block.
The one-block rule applies only to the RSVP and supplemental instructions.

### 4.1 Standalone attendance

The standalone attendance sentence is exact:

```text
Bop :white_check_mark: so we'll know you'll be there.
```

This supersedes `Bop ✅ if you're coming.` from the July 12 design and restores
the rationale from the earlier approved message grammar.

### 4.2 Supplemental reactions

When at least one supplemental reaction exists, append this sentence to line
one, separated from the attendance sentence by one normal space:

```text
In addition to your attendance emoji, hit a :hatching_chick: for new rollerskier, a :older_adult::skin-tone-4: for experienced rollerskier, and a :athletic_shoe: for runner.
```

Generation rules:

- One choice: `a :emoji: for label`.
- Two choices: `a :one: for first and a :two: for second`.
- Three or four choices: comma-separated with an Oxford comma before `and`.
- Preserve saved reaction order.
- Preserve label capitalization as entered; do not guess whether a proper noun
  should be lowercased.
- Escape member-supplied Slack markup in labels.
- Use `a` before each emoji, matching the approved copy.
- Treat labels as sentence fragments when rendering: trim trailing whitespace
  and terminal `.`, `?`, or `!` characters from every displayed label without
  changing the stored value. Reject a label that has no content after this
  display normalization.
- Add exactly one final period to the assembled supplemental sentence.

The Slack root no longer displays `Your Practice Plan:`. Internal code and
authoring UI may continue using the established **Plan reactions** terminology.

### 4.3 Accessibility fallback

When an RSVP context is present, top-level fallback text ends with an exact
plain-language equivalent. It does not duplicate the raw `<!channel>` token;
the visible Block Kit context owns the broadcast mention once for the message.

Standalone tail without supplemental reactions:

```text
RSVP with the white check mark reaction so we'll know you'll be there. Running late? Reply in the thread.
```

Standalone tail with the three approved example reactions:

```text
RSVP with the white check mark reaction so we'll know you'll be there. Additional reactions: hatching chick for new rollerskier; older adult, skin tone 4 for experienced rollerskier; athletic shoe for runner. Running late? Reply in the thread.
```

Fallback reaction names are derived by replacing underscores with spaces and
rendering `::skin-tone-N` as `, skin tone N`. They never depend on raw Slack
shortcode delimiters. Supplemental labels use the same sentence-fragment
normalization as visible copy. One choice uses singular
`Additional reaction: {name} for {label}.`; two through four choices use plural
`Additional reactions:` and join complete `{name} for {label}` clauses with
semicolons, without an additional conjunction.

The fallback remains bounded by the existing 4,000-character guard and keeps
all previously required date, time, location, workout, Notes, Social, status,
and urgent-exception content.

## 5. Combined-session grammar

Combined sessions remain defensive compatibility rather than a primary
scheduling product.

### 5.1 Upper hierarchy

- Remove the `Choose a session:` section.
- Do not prefix upper session rows with attendance emojis.
- For sessions on different dates, each row keeps its full day, date, and time.
- When every session is on the same date, the header supplies the date and each
  session row uses only its time.
- If workout, Notes, or Social differs between sessions, identify the owning
  session with day/time text rather than its attendance emoji.

### 5.2 Bottom attendance mapping

Only the bottom RSVP context maps session reactions.

Different-day example:

```text
Bop :six: for Tue at 6:15 PM or :seven: for Wed at 7:15 PM so we'll know you'll be there. In addition to your attendance emoji, hit a :hatching_chick: for first strength practice support.
Running late? Reply in the thread. <!channel>
```

Same-day example:

```text
Bop :six: for 6:05 PM or :seven: for 7:20 PM so we'll know you'll be there. In addition to your attendance emoji, hit a :hatching_chick: for first strength practice support.
Running late? Reply in the thread. <!channel>
```

Mapping rules:

- One active session uses one reaction/time pair.
- Two active sessions join pairs with `or`.
- Three active sessions use commas and an Oxford `or` before the final pair.
- Different-day pairs use abbreviated weekday plus time.
- Same-day pairs use time only.
- Same-day versus different-day classification considers every session still
  displayed in the shared root, including a cancelled session. The mapping
  itself still contains active sessions only.
- Persisted session emoji remains the source of truth.
- Cancelled sessions stay visible with their reason but are omitted from the
  RSVP mapping.
- If every session is cancelled, omit the RSVP context entirely.
- A one-session survivor retains combined grammar and its persisted reaction.

Supplemental copy appears only when every session still represented in the
shared root, including a cancelled session, has the same ordered reaction
list. This preserves the July 12 compatibility rule without adding another
combined-session state model.

Combined fallback uses the same active-only mapping and same-day/cross-day
classification. Different-day example tail:

```text
RSVP with six for Tue at 6:15 PM or seven for Wed at 7:15 PM so we'll know you'll be there. Additional reactions: hatching chick for first strength practice support. Running late? Reply in the thread.
```

Same-day fallback removes the weekday names just as the visible mapping does.
When every displayed session is cancelled, visible and fallback output both
omit RSVP, supplemental-reaction, and late-arrival instructions.

## 6. Notes icon

Member-facing standalone and combined announcement Notes headings use this
exact bold `mrkdwn` payload:

```text
*📝 Notes*
```

This replaces `:pushpin:` so the Notes heading no longer competes with the red
location pin. Plain fallback text continues to say `Notes:` without an emoji.
Internal coach-review blocks are outside this change.

## 7. Weekly summary polish

The approved weekly hierarchy remains one section per represented calendar
date. Builder payloads use these exact Unicode characters, which Slack may
normalize to shortcodes in API readback. Its restrained visual vocabulary is:

- one `📅` emoji in the top-level header;
- no repeated calendar emoji on day rows;
- `🚫` only for a cancellation; and
- `📝` in the footer.

Example:

```text
📅 Practices this week · July 27–August 2

Monday, July 27 · 6:00 PM
Run intervals · Theodore Wirth
Forecast: 78°F, partly cloudy

Sunday, August 2 · 9:00 AM
🚫 CANCELLED · Heat warning
Run intervals · Theodore Wirth

📝 Full practice details will be posted before each practice. · <!channel>
```

The footer replaces `Daily details posted {days}.` It is emitted only when the
summary contains at least one active practice. This avoids claiming that the
publication day is the same as the practice day, which is not true for morning
practices posted the prior evening.

The weekly accessibility fallback remains emoji-independent and includes the
full week range and every active or cancelled practice. It does not repeat the
raw broadcast token.

## 8. Slack skin-tone modifier support

Following Slack's documented
[`reactions.add` modifier syntax](https://docs.slack.dev/reference/methods/reactions.add/),
the normalized reaction name may be either:

```text
base_emoji
base_emoji::skin-tone-N
```

where `N` is 2 through 6. For example, both of these authoring forms normalize
to `older_adult::skin-tone-4`:

```text
older_adult::skin-tone-4
:older_adult::skin-tone-4:
```

Rendering wraps the stored name once, producing
`:older_adult::skin-tone-4:`. Reaction seeding and event matching use the full
normalized Slack name unchanged.

Malformed modifiers, multiple modifiers, missing base names, and modifier
numbers outside 2 through 6 produce the existing field-specific validation
error. A normalized reaction name is limited to 80 characters. Validation
splits any modifier from its base and checks the base against reserved
attendance names, so adding a modifier cannot bypass the reservation.

## 9. Component boundaries

Keep the implementation small:

- `app/practices/plan_reactions.py` owns natural-language supplemental lists,
  label escaping, and modifier-aware name validation.
- `app/slack/blocks/announcements.py` owns attendance sentences, the shared
  two-line context composition, same-day/cross-day combined labels, Notes icon,
  and accessible fallback composition.
- `app/slack/blocks/summary.py` owns the weekly header icon, cancellation icon,
  and non-day-specific footer.

No builder performs database writes or Slack API calls. Existing orchestration,
persistence compensation, reaction reconciliation, and refresh paths continue
to consume these builders.

## 10. Error handling and limits

- Context output remains subject to Slack's existing 2,000-character guard.
  The formatter builds the complete second line first and reserves its length,
  then reserves the attendance sentence on line one. Only the supplemental
  sentence may be truncated with an ellipsis in the remaining budget. The
  final generic block guard is defense in depth, not the mechanism that
  preserves required copy.
- Each stored label remains capped at 80 characters, each normalized reaction
  name at 80 characters, and the resolved list at four choices.
- Standalone and combined fallback builders similarly reserve their complete
  RSVP/supplemental/late-arrival tail before budgeting earlier content. A final
  4,000-character guard must not right-truncate that required tail.
- Invalid skin-tone syntax is rejected before a practice or default is saved.
- A cancelled combined slot cannot remain in the active RSVP sentence.
- The live harness continues recursively stripping broadcast mentions before
  posting to `C07G9RTMRT3`.

## 11. Verification

Implementation follows test-driven development. Exact-copy and structural
tests cover:

- standalone RSVP with zero, one, two, three, and four supplemental choices;
- one RSVP context block, one `mrkdwn` element, and exactly one intentional
  newline while preserving the separate coach/lead context;
- natural `and`/Oxford-comma grammar and escaped labels;
- per-label terminal-punctuation normalization for visible and fallback copy;
- valid bare and wrapped skin-tone names plus malformed variants;
- full-name reaction seeding and reaction-event matching;
- combined posts with one, two, and three active sessions;
- same-day time-only mappings and cross-day abbreviated-weekday mappings;
- mixed cancellation excluding the cancelled reaction from RSVP copy;
- all-cancelled combined output with no RSVP context;
- same-day/cross-day classification using every displayed sibling while RSVP
  mappings include active siblings only;
- no `Choose a session:` label or upper attendance emoji;
- exact plain-language standalone and combined fallback tails, including
  active-only and all-cancelled cases;
- fallback reservation preserving the complete required tail at 4,000 chars;
- `*📝 Notes*` headings in standalone and combined roots;
- weekly `📅` header, `🚫` cancellation cue, and `📝` exact footer;
- complete bounded standalone, combined, and weekly fallbacks; and
- initial post and refresh paths using the same copy.

The guarded live harness adds or updates scenarios for:

1. A standalone rollerski/run practice with three supplemental reactions,
   including `older_adult::skin-tone-4`.
2. A combined practice across different dates.
3. A combined practice with two sessions on the same date.
4. The approved weekly cross-month cancellation layout.

After automated verification, replace the current review messages in
`C07G9RTMRT3`, read every revised message back through Slack, and obtain final
product-owner sign-off before teardown and branch integration.

## 12. Delivery shape

The implementation plan should remain a small revision of the existing feature
branch:

1. Add failing contracts for shared grammar and modifier validation.
2. Implement the shared RSVP/supplemental formatters and combined labels.
3. Apply Notes and weekly-summary polish.
4. Update fallbacks, harness scenarios, and exact-copy tests.
5. Run focused and full verification, independent review, then guarded live
   validation.
