# Tabulator Migration — Review Polish

**Date:** 2026-06-07
**Status:** Design approved
**Branch:** `feat/tabulator-migration`
**Companion feedback notes:** `docs/superpowers/notes/2026-06-07-tabulator-review-feedback.md`
**Parent program:** `docs/superpowers/specs/2026-06-04-tabulator-migration-design.md`

**Goal:** Resolve the UX/polish issues found during the live walkthrough of the completed
Tabulator migration, fixing shared root causes once rather than patching each surface, so the
admin panel reads as cohesive in both look and behavior.

---

## 0. Guiding principle (applies to every task)

**Extrapolate from existing patterns; do not invent new ones.** The migration already established
the vocabulary — shared `AdminUI` foundation primitives (consistency) + scoped per-surface chrome
(bespoke). Every change here reuses that vocabulary:

- Shared, cross-surface concerns go into the frozen foundation (`app/static/js/admin/*`,
  `app/static/css/admin_ui.css`) so all surfaces inherit them identically.
- Per-surface chrome stays scoped under the surface root (`#pay-root`, `#season-tl`, `#slack-sync`,
  `#roles-studio`, `#member-roster`).
- The **practices reference** and the **Members roster** remain the canonical examples of a
  well-formed list, row, drawer, and filter bar. When in doubt, match Members.
- Geometry tokens already in use are the source of truth: 38px controls, radius 10px inputs /
  11px cards / 9999px pills, row padding `12px 15px`, 40px avatar/initials chip, navy `#1c2c44`.

No new frameworks, no new color systems, no unrelated refactors.

---

## 1. Context

The Tabulator eradication program (parent spec) is functionally complete on
`feat/tabulator-migration`: all 8 surfaces migrated, WF-9 endgame done (CDN removed, `.tabulator-*`
purged), foundation frozen at tag `admin-ui-foundation-frozen`. A live review surfaced polish
issues, several of which share a single root cause. This spec covers those fixes. It does **not**
re-open the migration architecture.

---

## 2. Cross-cutting fixes (highest leverage — implement first)

### 2.1 Shared drawer-content convention  *(fixes Payments, Seasons, Trips, Social Events)*

**Root cause.** `AdminUI.drawer` appends its panel to `document.body`, outside any surface's root
container. Members defines its drawer-content CSS as **unscoped** top-level selectors
(`.mr-dw-content`, `.mr-kv`, ...), so those rules reach the body-mounted panel and the drawer looks
formatted. Payments, Seasons, Trips, and Social Events scope **all** their CSS under a root id
(`#pay-root .pw-*`, `#season-tl .stl-*`, ...). Their drawer-content builders emit those class names,
but the rules cannot match outside the root, so the drawer body renders completely unstyled.

This is a genuine gap in the frozen foundation: the drawer primitive provides the shell
(header, close, scrim, focus-trap, `.admin-ui-drawer__body` padding) but **no shared content
convention**, forcing each surface to bring its own — and four of them brought theirs in a form
that cannot reach the mount point.

**Decision — Approach A: promote a drawer-content convention into the foundation.** (Considered and
rejected: per-surface un-scoping, and `.admin-ui-drawer`-bridged selectors — both produce four
near-identical copies that drift, and neither matches the program's "consistency primitives are
shared" canon.)

Add a small set of **globally-scoped** `.admin-ui-dw-*` classes to `app/static/css/admin_ui.css`
(loaded globally via `admin_base.html`, so they reach the body-mounted drawer). These mirror the
proven Members `.mr-dw-*` shapes:

| Class | Purpose | Modeled on |
|-------|---------|-----------|
| `.admin-ui-dw` | drawer content wrapper (column flex) | `.mr-dw-content` |
| `.admin-ui-dw-section` | a grouped block | `.mr-dw-blk` |
| `.admin-ui-dw-section-title` | 11px/700 uppercase label | `.mr-dw-blk-h` |
| `.admin-ui-dw-kv` | key/value row | `.mr-kv` |
| `.admin-ui-dw-key` | fixed-width muted key | `.mr-k` |
| `.admin-ui-dw-val` | value | `.mr-v` |
| `.admin-ui-dw-sep` | hairline separator | `.mr-dw-sep` |
| `.admin-ui-dw-note` / `.admin-ui-dw-empty` | muted descriptive text box | `.mr-no-roles-note` |
| `.admin-ui-dw-footer` | sticky footer action zone | `.mr-dw-footer` |
| `.admin-ui-dw-btn-primary` / `-ghost` / `-danger` | 40px footer buttons | `.mr-act-*` |

**Retrofit** Payments / Seasons / Trips / Social Events drawer-content builders to emit these shared
classes instead of their root-scoped ones, and remove the now-dead `#root .x-dw-*` rules they were
relying on. Their drawers already pass the same data shape (title + content node); only the content
markup's class names change.

**Members:** already correct via `.mr-dw-*`. Leave as-is for this pass (no behavior change, no risk);
the shared classes are visually equivalent, so the panel reads cohesively across surfaces. (Optional
future cleanup: migrate `.mr-dw-*` onto the shared classes — out of scope here.)

**Foundation amendment + re-freeze.** This edits the frozen foundation, which the canon permits via
report-back → amend → re-freeze. After the new classes land and the four surfaces are retrofit,
re-tag: `git tag -f admin-ui-foundation-frozen`.

### 2.2 Unify CSV export

CSV export is placed inconsistently (Members: bottom footer; Payments: awkward). Define **one**
treatment and apply it everywhere a full-list export exists (Members, Payments):

- A quiet utility action, bottom-right of the list, lighter than a primary button (reads as a
  secondary/utility control, not a CTA).
- Promote to the foundation as `.admin-ui-export-bar` (right-aligned footer row, hairline top
  border) + `.admin-ui-export-btn` (quiet button, small download glyph, `:focus-visible` ring),
  in `admin_ui.css`.
- Both surfaces use these classes; the existing `mr-export-csv` / payments export button keep their
  ids and JS wiring, only class + placement change.

### 2.3 Consistent filter-control sizing

Filter controls within a toolbar must share one geometry (38px height, radius 10px), matching
`.admin-ui-filterbar` / `.mr-select`. Fix the undersized Payments "capturable only" control so it
matches its sibling selects. Audit the other surfaces' filter rows for stray sizing while here.

---

## 3. Per-surface fixes

### 3.1 Members (`users.html` / `admin_users.js`)
- **Grouped status cell.** Replace the two unlabeled badges split across columns 3 and 4 with one
  status column: **Member status** as the primary badge (top); **Season status** as a muted
  sub-line below, prefixed with the season name (`2025-26 · Lottery`), or `Not registered` when the
  member has no status in the effective season. The effective-season label comes from the existing
  `mr_applyGlobalView` season context. Edit/checkbox stay in the actions column.
- **CSV** via the unified treatment (§2.2).
- Use `·` (middot) as the season separator — no em/en dashes (house style).

### 3.2 Payments (`payments.html` / `admin_payments.js`)
- Metadata drawer fixed by §2.1.
- "Capturable only" filter sizing fixed by §2.3.
- CSV placement fixed by §2.2.
- No bespoke work beyond adopting the three cross-cutting fixes.

### 3.3 Roles (`roles.html`)
- **Declutter the left rail.** Today each row shows the colored badge (which already contains the
  display name) *and* a duplicate, truncated copy of the display name, *plus* the mono system name,
  *plus* the count chip. Remove the redundancy: lead with the badge (carrying the display name), keep
  the system name as muted mono secondary text and the count chip; drop the separate truncated
  display-name text. Result: badge + system-name + count, no repetition.
- **Fix the gradient-picker / save-bar overlap.** The sticky `.rs-savebar` currently overlaps the
  second row of preset swatches (swatches bleed behind it / are cut off). Ensure the editor content
  scrolls fully above the sticky bar (padding-bottom equal to the bar height, or restructure so the
  picker is never occluded) so all presets are visible and reachable.
- Stay within the established Roles Studio pattern (rail + editor); this is decluttering, not a
  re-architecture.

### 3.4 Seasons / Trips / Social Events
- Drawers fixed by §2.1 (`seasons.html`/`admin_seasons.js`, `trips.html`/`admin_trips.js`,
  `social_events.html`/`admin_social_events.js`).
- Edit pages/dialogs **deferred** (see §5).

### 3.5 Slack Sync (`slack_sync.html` / `admin_slack.js`)
**Problem (confirmed from live render):** every row renders an always-open "Search Slack user…"
picker input plus a stacked "Delete" link in the trailing column. This balloons rows to ~140px
(only ~6 people visible), creates awkward right-side button spacing, and makes the white
rows-on-white-container read as a cramped mass. The recent refactor matched the row *shell* to
siblings but left the always-open picker inside it.

**Fix — compact, single-action rows matching the sibling pattern:**
- Row collapses to single geometry (~64px, like `.mr-row` / `.ss-row` shell) showing initials chip
  + name + email/meta + status, with **one** compact trailing primary action: **Link** (for users
  needing a Slack match). Delete moves into the existing overflow menu (`.ss-overflow-btn` /
  `.ss-popover`, already present).
- The link picker (`.ss-picker`) opens **on demand by inline-expanding the row** when **Link** is
  clicked — instead of rendering on every row at rest. (Chosen over putting it in the drawer so the
  match action stays where the eye already is; the row still opens the reconciliation drawer on
  click for full detail.) Reuse the existing picker markup/logic and suggested-match behavior
  verbatim; only its trigger changes from always-rendered to on-demand.
- Verify the scoped CSS actually applies (the surface had a prior Jinja `{#` comment-parsing
  regression, commit `4506ebb`); confirm no remaining `{#` / `#}` sequences silently swallow rules.
- Outcome: ~12 people visible at once, consistent row rhythm, tidy trailing actions.

---

## 4. Sequencing

1. **Foundation amendments first** (§2.1 drawer classes, §2.2 export classes) — committed and the
   foundation re-frozen — because the per-surface work consumes them.
2. **Per-surface adoption**: Members (§3.1), Payments (§3.2), Roles (§3.3), Seasons/Trips/Social
   drawer retrofit (§3.4), Slack Sync (§3.5). These are independent and touch disjoint files (same
   isolation property as the parent program), so they can proceed in any order / parallel.
3. **Verify**: each surface re-checked in the browser, desktop + ≤767px, console clean.

---

## 5. Out of scope / deferred (explicit)

- **All object edit menus & pages** stay as the existing forms for now — Seasons edit dialog, Trips
  edit page, Social Events edit page — to be cleaned up together in a later once-off pass.
- Members `.mr-dw-*` → shared-class migration (cosmetic-only; defer).
- Backend `/data` endpoint changes (reuse existing shapes).
- Practices config and Skipper surfaces (not flagged in review).

---

## 6. Files touched

**Foundation (amend + re-freeze):**
- `app/static/css/admin_ui.css` — add `.admin-ui-dw-*` + `.admin-ui-export-*`.

**Per-surface (disjoint ownership):**
- `app/templates/admin/users.html`, `app/static/admin_users.js`
- `app/templates/admin/payments.html`, `app/static/admin_payments.js`
- `app/templates/admin/roles.html`
- `app/templates/admin/seasons.html`, `app/static/admin_seasons.js`
- `app/templates/admin/trips.html`, `app/static/admin_trips.js`
- `app/templates/admin/social_events.html`, `app/static/admin_social_events.js`
- `app/templates/admin/slack_sync.html`, `app/static/admin_slack.js`

---

## 7. Risks & mitigations

- **Editing the frozen foundation** could ripple to surfaces that already render drawers. Mitigation:
  the new classes are additive (new names), Members is untouched, and only the four broken surfaces
  switch to them; verify each drawer after.
- **Slack Sync row redesign** is the largest behavioral change. Mitigation: reuse the existing picker
  logic and suggested-match code verbatim; only the trigger (always-on → on-demand) and row geometry
  change. Verify link/unlink/delete/import parity against the live `/admin/slack/*` endpoints.
- **Visual drift between surfaces.** Mitigation: shared foundation classes + matching Members as the
  reference keep the panel cohesive.
