# Tabulator Review-Polish - Final Implementation Spec

**Date:** 2026-06-07
**Status:** Approved for implementation
**Branch:** `feat/tabulator-migration`
**Approved design:** `docs/superpowers/specs/2026-06-07-tabulator-review-polish-design.md`
**Parent program:** `docs/superpowers/specs/2026-06-04-tabulator-migration-design.md`

## Goal

Resolve the polish issues surfaced during the live walkthrough of the completed Tabulator migration by fixing their shared root causes once in the frozen foundation and then retrofitting each surface to consume the result, so the admin panel reads as a single cohesive product in both look and behavior. The largest single root cause is that `AdminUI.drawer` mounts its panel on `document.body` (verified: `app/static/js/admin/drawer.js:37-38`), outside every surface root, so the four surfaces that scope all their CSS under a root id render an unstyled drawer body. This spec promotes a globally-scoped drawer-content convention, a globally-scoped CSV export convention, and a shared drawer-internal pill into `app/static/css/admin_ui.css`, then converts Payments, Seasons, Trips, Social Events, and Slack Sync onto them, declutters Members and Roles, and compacts Slack Sync rows.

**Guiding principle.** Extrapolate from existing patterns; invent nothing. Cross-surface concerns go into the frozen foundation as globally-scoped `.admin-ui-*` classes; bespoke information architecture stays scoped under the surface root (`#member-roster`, `#pay-root`, `#season-tl`, `#roles-studio`, `#slack-sync`). The Members roster is the canonical reference for every shared shape; when a value is in dispute it is resolved to the verified Members `.mr-*` declarations (`app/templates/admin/users.html:131-154`, `app/static/admin_users.js:537-551`), not re-derived. No new color systems, no frameworks, no em or en dashes in any copy (the house separator is the middot U+00B7, emitted as an `AdminUI.el` text-node child, never an HTML entity, never a dash).

---

## 1. Shared foundation changes

All foundation edits land in **one coordinated commit** authored by **one** engineer to `app/static/css/admin_ui.css`. No surface team edits this file. No surface redefines, re-scopes, or shadows any `.admin-ui-dw-*`, `.admin-ui-export-*`, or `.admin-ui-dw-pill` selector. After this single commit lands and all consuming surfaces are retrofit, run `git tag -f admin-ui-foundation-frozen` **exactly once**.

Every value below is copied byte-for-byte from the verified Members canon. The four engineer teams diverged on geometry (Seasons proposed 96px key / 10.5px title; Payments and Social proposed 10px-radius / 13.5px buttons citing a "UX freeze"). All such divergences are **overridden to Members canon**: key 90px, section-title 11px, footer buttons radius 9px / font 14px / height 40px. The "UX freeze" claim is rejected: the design directive is literally "modeled on `.mr-act-*`" and the 40px footer button is its own modeled-on-Members shape at 9px; cohesion with Members outranks per-surface zero-shift.

### 1.1 Drawer-content family

Append immediately **after** the `.admin-ui-drawer__body` rule (`admin_ui.css:57`), as globally-scoped (unprefixed) selectors so they reach the body-mounted panel:

```css
/* --- Drawer content (shared, body-mounted) --- */
.admin-ui-dw{display:flex;flex-direction:column;gap:0}
.admin-ui-dw-sep{border:none;border-top:1px solid #f1f5f9;margin:16px 0}
.admin-ui-dw-section{margin-bottom:4px}
.admin-ui-dw-section-title{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#64748b;margin-bottom:10px}
.admin-ui-dw-kv{display:flex;align-items:baseline;gap:8px;margin-bottom:6px}
.admin-ui-dw-key{width:90px;flex-shrink:0;color:#64748b;font-size:13.5px}
.admin-ui-dw-val{color:#1c2c44;font-weight:500;font-size:13.5px}
.admin-ui-dw-val--empty{color:#94a3b8;font-weight:400}
.admin-ui-dw-val--mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;word-break:break-all}
.admin-ui-dw-note,.admin-ui-dw-empty{color:#94a3b8;font-size:13.5px}
.admin-ui-dw-sub{font-size:13px;color:#475569;margin:0 0 12px}
.admin-ui-dw-desc{font-size:13px;color:#475569;line-height:1.55;white-space:pre-wrap;overflow-wrap:anywhere;background:#f8fafb;border:1px solid #eef1f5;border-left:3px solid #cbd5e1;border-radius:8px;padding:9px 11px}
.admin-ui-dw-pill{display:inline-flex;align-items:center;border:1.5px solid #e5e7eb;border-radius:20px;padding:1px 9px;font-size:11.5px;font-weight:500;color:#475569}
.admin-ui-dw-footer{position:sticky;bottom:0;background:#fff;border-top:1px solid #eef1f5;padding:13px 18px;display:flex;gap:9px;flex-wrap:wrap}
.admin-ui-dw-btn-primary{flex:1;height:40px;background:#1c2c44;color:#fff;border:none;border-radius:9px;font-size:14px;font-weight:600;cursor:pointer;font-family:inherit;text-decoration:none;display:inline-flex;align-items:center;justify-content:center;white-space:nowrap}
.admin-ui-dw-btn-primary:hover{background:#253c5e}
.admin-ui-dw-btn-primary:focus-visible{outline:2px solid #1c2c44;outline-offset:2px}
.admin-ui-dw-btn-ghost{flex:1;height:40px;background:#fff;color:#475569;border:1.5px solid #e5e7eb;border-radius:9px;font-size:14px;font-weight:600;cursor:pointer;font-family:inherit;text-decoration:none;display:inline-flex;align-items:center;justify-content:center;white-space:nowrap}
.admin-ui-dw-btn-ghost:hover{border-color:#1c2c44;color:#1c2c44}
.admin-ui-dw-btn-ghost:focus-visible{outline:2px solid #1c2c44;outline-offset:2px}
.admin-ui-dw-btn-success{height:40px;padding:0 16px;background:#fff;color:#166534;border:1.5px solid #bbf7d0;border-radius:9px;font-size:14px;font-weight:600;cursor:pointer;font-family:inherit;display:inline-flex;align-items:center;justify-content:center;white-space:nowrap}
.admin-ui-dw-btn-success:hover{border-color:#86efac}
.admin-ui-dw-btn-success:focus-visible{outline:2px solid #1c2c44;outline-offset:2px}
.admin-ui-dw-btn-danger{height:40px;padding:0 16px;background:#fff;color:#c53030;border:1.5px solid #f3c9c9;border-radius:9px;font-size:14px;font-weight:600;cursor:pointer;font-family:inherit;display:inline-flex;align-items:center;justify-content:center;white-space:nowrap}
.admin-ui-dw-btn-danger:hover{background:#fde8e8}
.admin-ui-dw-btn-danger:focus-visible{outline:2px solid #1c2c44;outline-offset:2px}
```

Notes on the additions beyond the design §2.1 table, all resolved in favor of promotion because each has two or more consumers and introduces zero new color or geometry token:

- `.admin-ui-dw-sub` (Trips, Social Events sub-line; distinct from `-note`: 13px/#475569 vs 13.5px/#94a3b8).
- `.admin-ui-dw-desc` (Seasons description panel; a bordered pre-wrap box, distinct from the muted single-line `-note`; verbatim from the existing `.stl-desc-box`).
- `.admin-ui-dw-pill` (Payments drawer Type value, Seasons drawer meta pill; verbatim geometry from `.pw-type-pill`). Inline-styling per surface is rejected as the exact drift the foundation exists to prevent.
- `.admin-ui-dw-val--mono` (Payments Intent ID).
- `.admin-ui-dw-btn-success` (Seasons Activate only; not a general primitive, but authored here so it is body-reachable).
- `.admin-ui-dw-footer` carries **no** `margin-top:auto` (Members omits it; the Social proposal incorrectly added it - do not add it).

### 1.2 Drawer mobile block

Append to the **existing** `@media (max-width: 767px)` block (`admin_ui.css:67-70`). These live only on the global classes because the body-mounted panel cannot inherit any `#surface-root`-scoped rule - that inheritance gap is the entire root cause being fixed:

```css
  .admin-ui-dw-key{width:80px}
  .admin-ui-dw-footer{padding-bottom:calc(13px + env(safe-area-inset-bottom,0px))}
  .admin-ui-dw-btn-primary,.admin-ui-dw-btn-ghost,.admin-ui-dw-btn-success,.admin-ui-dw-btn-danger{min-height:44px}
```

### 1.3 CSV export family

Append **after** the `.admin-ui-sticky-bar` block (`admin_ui.css:65`), globally scoped. Height resolved to the 38px geometry token (32px rejected as off-token); hairline resolved to the foundation's own `#e4e4e7` (the `#e5e7eb` several proposals copied is rejected so the bar matches `.admin-ui-drawer__header` and `.admin-ui-sticky-bar` byte-for-byte). Styled quiet (white bg, muted text) so it reads as a utility, not a CTA:

```css
/* --- CSV export (shared) --- */
.admin-ui-export-bar{display:flex;justify-content:flex-end;margin-top:16px;padding-top:14px;border-top:1px solid #e4e4e7}
.admin-ui-export-btn{display:inline-flex;align-items:center;gap:6px;height:38px;padding:0 14px;border:1.5px solid #e4e4e7;border-radius:10px;background:#fff;color:#64748b;font-size:13px;font-weight:600;cursor:pointer;font-family:inherit;transition:border-color .12s,color .12s}
.admin-ui-export-btn:hover{border-color:#1c2c44;color:#1c2c44}
.admin-ui-export-btn:focus-visible{outline:2px solid #1c2c44;outline-offset:2px}
```

### 1.4 Filter sizing (cross-surface note)

There is **no** foundation edit for filter sizing. The global `.admin-ui-pill` is **not** modified (its default 6px/12px pill is correct elsewhere). The single §2.3 fix is scoped to Payments (see section 3). The other surfaces' filter rows were audited; only the Payments "capturable only" control is undersized.

### 1.5 Canonical conventions every retrofit surface obeys

- **Footer mount (mandatory, identical everywhere).** Build the footer, append it **inside** the content node (`content.appendChild(footer)`), then pass that node to `AdminUI.drawer({content})`. This is the only arrangement where `.admin-ui-dw-footer{position:sticky;bottom:0}` pins as the last child of the scrollable `.admin-ui-drawer__body`. Reference: `app/static/admin_users.js:549`. Every `drawer.body.parentElement.appendChild` / `drawer.body.appendChild(footer)` sibling mount is deleted. The primary (safe/navigational) button is the first footer child for tab order.
- **Flex sizing.** Only `-btn-primary` and `-btn-ghost` carry `flex:1`; `-success` and `-danger` are content-width. Footers with more than two buttons rely on `flex-wrap:wrap`, never on N equal slivers.
- **Empty values.** Any placeholder drawer value (`-`, `Not set`, `No limit`, missing) gets class string `admin-ui-dw-val admin-ui-dw-val--empty`.
- **Sub-line.** Trips and Social Events use `.admin-ui-dw-sub`. Do not fold into `-note`.
- **Footer button roles are fixed vocabulary.** primary = safe/navigational (Edit, Link), navy filled; ghost = secondary neutral (Export, Late Link); danger = destructive (Delete); success = Seasons Activate only. A surface never restyles a role or swaps its color.
- **Dead-CSS removal is tightly scoped.** Delete only the drawer-content rules the JS no longer emits; classes shared with on-page cards stay. Use only `/* */` comments - never introduce a Jinja `{# #}` sequence into a `<style>` block (the commit `4506ebb` regression). Re-verify each surface's scoped CSS still matches in the rendered browser, console clean, after deletion.

---

## 2. Sequencing

1. **Step 0 - foundation gate (one author, one commit):** land 1.1-1.3 in `admin_ui.css`. Additive only; no existing `.admin-ui-*` selector modified, so Members and every currently-correct drawer are unaffected. Then `git tag -f admin-ui-foundation-frozen` once.
2. **Step 1 - no-dependency surfaces (may start immediately, even before Step 0, disjoint files):** Members grouped-status-cell (`.mr-*` scoped); Roles rail declutter + savebar overlap; Slack Sync **row compaction** (workstream A, pure `#slack-sync` chrome).
3. **Step 2 - foundation consumers (gated on Step 0 re-freeze):** Members CSV swap; Payments (drawer + pill + CSV); Seasons drawer; Trips drawer; Social Events drawer; Slack Sync **drawer retrofit** (workstream B). Any of these landing before Step 0 renders its button/drawer unstyled - hard gate.
4. **Step 3 - joint gate:** Trips and Social Events drawer retrofits land together (one PR or back-to-back); a side-by-side DOM diff of `tripsOpenDrawer` vs `sevOpenDrawer` (same class strings, same node order, footer inside content) is the acceptance check.
5. **Step 4 - verify per surface:** desktop + ≤767px, console clean, drawer renders styled with footer sticky-pinned, export reads as a quiet utility, no em/en dashes in rendered copy, all mutation parity intact, all six drawers read as the same component side by side.

---

## 3. Per-surface sections

### 3.1 Members

**Files:** `app/templates/admin/users.html`, `app/static/admin_users.js`. Consumer of the foundation export classes; author of the bespoke `.mr-status-cell` IA (stays scoped under `#member-roster`). No drawer edits this pass; `.mr-dw-*` remains the reference shape, untouched.

**Grouped status cell (Step 1, no foundation dependency).**
- Keep the row grid `40px 1fr auto auto` unchanged.
- `users.html`: replace the `.mr-badges` rule (line 110) with `.mr-status-cell{display:flex;flex-direction:column;align-items:flex-end;gap:5px;flex-shrink:0}` (identical geometry, semantic rename), and add `.mr-status-sub{font-size:12px;color:#64748b;font-weight:500;text-align:right;white-space:nowrap}`. In the mobile block (line 206) change the selector `.mr-badges,.mr-actions` to `.mr-status-cell,.mr-actions`.
- `admin_users.js`: add module state `var mr_effectiveSeasonName = null;` alongside the existing season/view state (~line 15). Add a Members-scoped helper near `mr_seasonText` (~line 86): `function mr_seasonTextShort(ss){var map={ACTIVE:'Active',PENDING_LOTTERY:'Lottery',DROPPED_LOTTERY:'Dropped',DROPPED_VOLUNTARY:'Dropped',DROPPED_CAUSE:'Dropped'};return map[ss]||'';}`. **Do not** touch `mr_seasonText` - the drawer Membership block and the season-status select still need its verbose forms.
- In `mr_applyGlobalView`, after `effId` is resolved, stash the name from that same context (no independent helper - it drifts from the toolbar): `var _es = (effId !== null) ? allSeasons.find(function(s){return s.id === effId;}) : null; mr_effectiveSeasonName = _es ? _es.name : null;`.
- In `mr_buildRow` (lines 276-305): drop the `ssBadge`/`badgesEl` block. Build the member-status badge as today via `AdminUI.statusBadge(mr_statusText(user.status), mr_statusVariant(user.status))` and set its `aria-label` to `'Member status: ' + mr_statusText(user.status)`. Build `var subText = user.season_status ? ((mr_effectiveSeasonName ? mr_effectiveSeasonName + ' · ' : '') + mr_seasonTextShort(user.season_status)) : 'Not registered';`. Build `var seasonSubEl = el('span', { class: 'mr-status-sub', 'aria-label': user.season_status ? ('Season: ' + (mr_effectiveSeasonName ? mr_effectiveSeasonName + ', ' : '') + mr_seasonTextShort(user.season_status)) : 'Not registered in current season' }, [subText]);`. Assemble `var statusCellEl = el('div', { class: 'mr-status-cell' }, [statusBadge, seasonSubEl]);`. Remove `statusBadge` from `actionsEl` so it is `el('div', { class: 'mr-actions' }, [selectCb, editBtn])`. Change the row child array (line 328) from `[avatarEl, primaryEl, badgesEl, actionsEl]` to `[avatarEl, primaryEl, statusCellEl, actionsEl]`.
- The middot `·` is U+00B7 emitted as the text node inside `subText`. Empty state is the literal sentence-case `Not registered` (no prefix, no badge). Null name with a set status renders the bare short status, never a leading `· ` and never `undefined`.

**CSV swap (Step 2, gated on foundation).**
- `users.html`: remove the dead `.mr-footer-row` rule (line 194). Replace the export markup (lines 315-317) with:
  ```html
  <div class="admin-ui-export-bar"><button id="mr-export-csv" class="admin-ui-export-btn"><svg width="13" height="13" viewBox="0 0 16 16" fill="none" aria-hidden="true" style="flex-shrink:0"><path d="M8 11L3 6h3V1h4v5h3L8 11Z" fill="currentColor"/><rect x="2" y="13" width="12" height="2" rx="1" fill="currentColor"/></svg>Export CSV</button></div>
  ```
- Keep `id="mr-export-csv"` and its JS wiring (`admin_users.js:1256-1257`) verbatim - zero JS diff for export. This SVG + `Export CSV` copy is the canonical export markup Payments copies byte-for-byte.

**Open question resolved at spec time:** prefixing the current-season name in All / Alumni / Waitlist views is **intended** (it mirrors the existing `season_status` recompute via the `effId` fallback to `currentSeason.id`). No suppression guard.

**Parity checklist (must survive):**
- Desktop: member badge on top, right-aligned, muted season sub-line directly below, matching the prior right-edge rhythm.
- Switching the season select re-prefixes every visible row's sub-line and flips the short status.
- All / Alumni / Waitlist views show the current-season name as prefix.
- Unregistered member shows `Not registered`, no prefix, no badge.
- No-current-season edge: bare short status, no leading middot, never `undefined`.
- Mobile ≤767px: `.mr-status-cell` spans full row width, badge + sub-line inline; Edit button not pushed off-screen; touch targets ≥44px.
- Export downloads `tcsc_members.csv` unchanged; 19-column schema and raw `season_status` code untouched (presentation-only).
- Edit + checkbox remain in the actions column.
- Console clean on load, filter changes, drawer open/close, export.

### 3.2 Payments

**Files:** `app/static/css/admin_ui.css` (consume only), `app/templates/admin/payments.html`, `app/static/admin_payments.js`. Three disjoint fixes; zero foundation authorship.

**Drawer retrofit (Step 2).** Root cause: `pay_openDrawer`/`pay_kvRow` emit `#pay-root`-scoped `pw-kv*`/`pw-dw-*` that never match the body-mounted panel. In `admin_payments.js`:
- `pay_kvRow` (926-931): `pw-kv-row`/`key`/`val` → `admin-ui-dw-kv`/`-key`/`-val`.
- `pay_openDrawer` (874-924): `kvList` (892) `pw-kv-list` → `admin-ui-dw`; Type value (883) `pw-type-pill` → `admin-ui-dw-pill`; Intent ID (889) `pw-kv-mono` → `admin-ui-dw-val--mono`; `actRow` (907) `pw-dw-actions` → `admin-ui-dw-footer`; accept btn (897) → `admin-ui-dw-btn-primary`; refund btn (903) → `admin-ui-dw-btn-danger`.
- **Footer mount:** build the footer/actRow and `content.appendChild(actRow)` (or assemble actRow as the last child of the `admin-ui-dw` node) before passing to `AdminUI.drawer`. Preserve the existing `setAttribute('disabled', ...)` calls (899/905) so refunded/closed payments show greyed, non-actionable buttons out of tab order.
- `payments.html`: delete the dead drawer KV + action rules (289-361) and their mobile overrides (617-619). **Keep `.pw-type-pill`** (220-229) - it still styles the on-ledger row pill; only the drawer Type value moves to `.admin-ui-dw-pill`.

**Capturable-only pill height (scoped, Step 1-eligible).** Add scoped `#pay-root .admin-ui-pill{height:38px}` (radius stays 9999px) so the control matches sibling selects. Do **not** touch the global `.admin-ui-pill`; do **not** add it to the search/select override list (it would not match).

**Export (Step 2).** In `pay_buildShell` (88-96): drop `exportBtn` from `pw-head` (head becomes `div.pw-head [h1]`); after the spacer append `div.admin-ui-export-bar` holding `button.admin-ui-export-btn id="pw-export-csv" onclick=pay_exportCsv` with the identical aria-hidden SVG glyph + `Export CSV` text from Members. `pay_exportCsv` (943-975, exports `state.currentFiltered`) is untouched. Delete the dead `#pay-root .pw-btn-ghost` rules (31-47). Verify the export bar stays reachable above the fixed mobile bulk bar (599-610).

**Geometry overrides applied here:** footer buttons use 9px/14px (not the proposal's 10px/13.5px); export button uses 38px/radius-10px/#e4e4e7 (not 32px/#e5e7eb).

**Parity checklist (must survive):** KV order; Type renders as a styled pill (not bare text); Intent ID monospace + break-all, no overflow at 420px; Esc/scrim/X close clears `state.openDrawer`; disabled accept/refund on closed/refunded payments; bulk capture/refund; `pay_exportCsv` exports `currentFiltered` (not `all`); all colors and backend and data shape unchanged; console clean desktop + ≤767px.

### 3.3 Roles

**Files:** `app/templates/admin/roles.html` only. No foundation authorship; no drawer retrofit. All edits inside the `<style>` block and inline `<script>`. Step 1 (no foundation dependency).

**Rail declutter.** In `rsRenderList()` (247-252) replace the button children array
```
rsLiveBadge(role, false),
el('div',{'class':'rs-row-names'},[el('div',{'class':'rs-row-display'},[role.display_name||'']), el('div',{'class':'rs-row-system'},[role.name||''])]),
rsUserChip(role.user_count, role.id)
```
with
```
rsLiveBadge(role, false),
el('div',{'class':'rs-row-system'},[role.name||'']),
rsUserChip(role.user_count, role.id)
```
CSS:
- Delete `.rs-row-names` (line 40) and `.rs-row-display` (line 41).
- Update `.rs-row-system` (line 42) to **prepend** `flex:1;min-width:0` (load-bearing - without it the system name will not grow and the chip will not right-align): `#roles-studio .rs-row-system{flex:1;min-width:0;font-size:11px;font-family:monospace;color:#64748b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}`.
- Add a rail-scoped badge cap `#roles-studio .rs-row .rs-badge{max-width:60%;overflow:hidden;text-overflow:ellipsis}` so a long display_name cannot crowd out the system name and chip. **Do not** cap the shared `.rs-badge` base (line 48) - the editor preview badge `.rs-preview-badge` reuses it uncapped.
- Keep the mobile `#roles-studio .rs-row-system{display:none}` (line 117) - badge + chip only on mobile is a valid tighter declutter.

**Savebar overlap.** Change `#rs-editor` (line 59) padding `20px 24px` → `20px 24px 72px` (reserve = 1px border + 12px + 12px padding + 38px button ≈ 63px, rounded to 72px), so the gradient swatch grid and description scroll fully above the sticky bar.

**Foundation reuse (subtractive).** Delete the scoped `#roles-studio .rs-savebar` rule (line 103) - it is byte-for-byte identical to the foundation `.admin-ui-sticky-bar` the element already carries (roles.html:505), and the foundation additionally supplies the mobile safe-area padding the duplicate lacks. Keep the inert `rs-savebar` class on the element as a future override hook.

**Mandatory mobile-drawer verification.** The desktop `#rs-editor` padding-bottom does **not** carry into the `AdminUI.drawer` mount (`rsOpenEditorMobile`, ~573); `.admin-ui-drawer__body` is a separate scroll container. On a ≤767px viewport, verify the last swatch row (5-wide, 44px min-height) and the description textarea clear the sticky savebar inside the drawer. **Only if occluded**, set `content.style.paddingBottom='72px'` on the detached content node built in `rsOpenEditorMobile` (~585). Never edit the foundation `.admin-ui-drawer__body`.

**Parity checklist (must survive):** long display_name truncates at 60% and does not push the system name/chip off-row; 0-user vs many-user chip variant and right-alignment correct; gradient swatches + description fully reachable above the savebar (desktop and mobile); row button `aria-label` (line 245, `<display_name> role, N users`) unchanged; swatch `:focus-visible` double ring and pluralized chip aria-label intact; reduced-motion block respected; console clean, no layout shift on preview update or role switch.

### 3.4 Seasons

**Files:** `app/static/admin_seasons.js`, `app/templates/admin/seasons.html`. Consumer of the shared drawer family plus the Seasons-only `-btn-success` / `-desc` / `-pill` (all authored in the single foundation commit, not by Seasons). Step 2.

**Builder renames** in `stlBuildDrawerContent` (494-595): every `stl-blk` → `admin-ui-dw-section`; `stl-blk-h` → `admin-ui-dw-section-title`; `stl-kv` → `admin-ui-dw-kv`; `{class:'k'}` → `admin-ui-dw-key`; `{class:'v'}` → `admin-ui-dw-val`; placeholder values (`-`, `Not set`, `No limit`) get `admin-ui-dw-val admin-ui-dw-val--empty`; `stl-desc-box` (590) → `admin-ui-dw-desc`; outer wrapper (594) gains `class:'admin-ui-dw'`. Drawer meta (502) `stl-dw-meta` → `admin-ui-dw-meta` is **not** introduced; instead the meta pill (500) routes through the shared `.admin-ui-dw-pill` and the year span (501) uses a plain muted `admin-ui-dw-val` (no second pill class). **Keep the `.stl-pill` / `.stl-year` rules** in `seasons.html` - the on-page hero/node cards (`admin_seasons.js:697-698,768`) still use them.

**Footer + mount correction** in `stlOpenPreview` (597-671): wrapper `stl-dw-footer` → `admin-ui-dw-footer`; Edit `stl-act-primary` → `admin-ui-dw-btn-primary`; Export CSV and Late Link `stl-act-ghost` → `admin-ui-dw-btn-ghost`; Activate `stl-act-success` → `admin-ui-dw-btn-success`; Delete `stl-act-danger` → `admin-ui-dw-btn-danger`. Restructure: `var content = stlBuildDrawerContent(season);` … build footer … `content.appendChild(footer);` … `var drawer = AdminUI.drawer({title:season.name, content:content});`. **Delete** the sibling mount (637-639: `var panel = drawer.body.parentElement; if(panel) panel.appendChild(footer);`). **Five-button rule:** only `-btn-primary` carries `flex:1`; ghost/success/danger are content-width; `flex-wrap:wrap` lets the four secondaries wrap. Migrate the active-card cleanup observer to `drawer.body.closest('.admin-ui-drawer')`; keep the `drawer.close` override (641-647) for synchronous programmatic activate/delete cleanup; keep `stlMarkActiveCard`.

**Template cleanup** in `seasons.html`: delete the drawer-actions block (26-34: `.stl-act` and `-primary`/`-ghost`/`-success`/`-danger` + hovers), the drawer-detail block (81-89: `.stl-dw-meta`, `.stl-blk`(+`:last-child`), `.stl-blk-h`, `.stl-kv`(+`:last-child`), `.stl-kv .k`, `.stl-kv .v`, `.stl-desc-box`), and the drawer-footer block (91-92: `.stl-dw-footer`). Edit line 23 to drop the trailing `, #season-tl a.stl-act:focus-visible` fragment. In the mobile block, drop `,#season-tl a.stl-act` from line 127 and delete line 128 (`.stl-dw-footer` padding-bottom - the foundation footer carries its own safe-area padding). **Keep untouched:** `.stl-pill`, `.stl-year`, all hero/node/card/head/count/btn/win/stat rules, the deferred edit-form inputs, the confirm + late-link modals, copy-row, aria-live, reduced-motion. Verify (grep) `stl-blk|stl-kv|stl-desc-box|stl-dw-footer|stl-act` is emitted nowhere; `stl-pill`/`stl-year` remain only on the card builders.

**Geometry overrides applied here:** key 90px (not 96px); section-title 11px (not 10.5px).

**Parity checklist (must survive):** active-card highlight clears on every close path (X, Esc, scrim, programmatic activate/delete); Edit stays a plain navigation anchor to the deferred edit page (only re-classed); tab order puts Edit first, then Activate/Delete; section titles remain real text labels; window-state badge keeps its `AdminUI.statusBadge` text label and rides as a third kv child; long window-range values wrap (no horizontal scroll); footer sticky-pinned, no double border; five buttons wrap sanely at 420px / 100vw with 44px touch targets; confirm/late-link modals layer above the drawer; card-click vs button-click propagation guard intact; the absent `member_count` Registration row stays absent.

### 3.5 Trips

**Files:** `app/static/admin_trips.js`, `app/templates/admin/trips.html`. Consumer only; emits the subset `{dw, dw-sub, dw-kv, dw-key, dw-val, dw-footer, dw-btn-primary, dw-btn-danger}`; does **not** wrap its flat KV list in `-section` blocks. Step 2; lands with Social Events (Step 3 joint gate).

**Builder** in `tripsOpenDrawer` (316-462): `tl-dw-sub` (336) → `admin-ui-dw-sub`; `contentDiv` (376) gains `class:'admin-ui-dw'`; `tl-kv`/`k`/`v` (378-385) and the badge row (388-396) → `admin-ui-dw-kv`/`-key`/`-val`; Edit `tl-dw-edit` (404) → `admin-ui-dw-btn-primary`; Delete `tl-dw-delete` (409) → `admin-ui-dw-btn-danger`; footer `tl-dwfooter` (412) → `admin-ui-dw-footer`. **Footer mount:** change `drawer.body.appendChild(footer)` (413) to `contentDiv.appendChild(footer)` **before** the `AdminUI.drawer({content: contentDiv})` call (399). Keep `tripsCurrentDrawer` assigned (400) before the footer build so `tripsDelete`'s id-guard (470) holds. **Do not** touch the MutationObserver (438-461), the wrapped `origClose` (416-430), inert toggles, is-active management, or the Edit href `/admin/trips/<id>/edit`.

**House style:** fix the price-range en dash to `' - '` (hyphen) at the drawer (~366) and the card (`tripsRenderCard`, ~131); fix any past-count em dash to `'· '` (middot).

**Template cleanup** in `trips.html`: delete the dead drawer rules (95-108: `.tl-dwfooter`, `.tl-dw-edit`/`.tl-dw-delete` + hovers + focus-visible, `.tl-kv`, `.tl-kv .k`, `.tl-kv .v`, `.tl-dw-sub`) and their mobile variants (116-117). Keep all `#trips-list` card/toolbar/header/date-block/aside/past-toggle/empty rules and the other mobile rules.

**Geometry override applied here:** the proposal's 9px/14px ruling is correct and is the ruling for all four surfaces.

**Parity checklist (must survive):** drawer opens from card click and keyboard and renders styled (sub-line, 90px muted keys + navy values, Status badge row, sticky footer Edit + Delete); footer spans edge-to-edge (no 20px inset gap); Esc/scrim/X/delete-from-drawer all restore card `.is-active` removed, rows/toolbar un-inerted, focus returned; `tripsDelete` id-guard fires; Edit navigates to the deferred page and does not keep the drawer; name link + Edit/Delete `stopPropagation`; mobile full-width drawer, footer clears the iOS home indicator, buttons ≥44px; Status row announced to a screen reader; Delete `:focus-visible` ring; `#trips-rows` aria-live still announces the count; no en/em dashes in copy; console clean; Members/Payments/Seasons visually unchanged.

### 3.6 Social Events

**Files:** `app/static/admin_social_events.js`, `app/templates/admin/social_events.html`. **Lockstep mirror of Trips** - identical class set, identical node order, identical footer mount, so a follow-on pass can collapse both into one builder. Step 2 / Step 3 joint gate.

**Builder** in `sevOpenDrawer`: `sl-dw-sub` (342) → `admin-ui-dw-sub`; `contentDiv` (375) gains `class:'admin-ui-dw'`; `sl-kv`/`k`/`v` (379-394) and badge row (386-388) → `admin-ui-dw-kv`/`-key`/`-val`; Edit `sl-dw-edit` (401) → `admin-ui-dw-btn-primary`; Delete `sl-dw-delete` (406) → `admin-ui-dw-btn-danger`; footer `sl-dwfooter` (409) → `admin-ui-dw-footer`. **Footer mount:** change `drawer.body.appendChild(footer)` (410) to `contentDiv.appendChild(footer)` before `AdminUI.drawer({content: contentDiv})` (mirror of Trips). **Do not** touch the MutationObserver, wrapped close, inert, `sevCurrentDrawer` assignment, or the Edit href `/admin/social-events/<id>/edit`.

**House style:** fix the past-count em dash `'- ' + past.length` (~289) to `'· ' + past.length`. Social has a single price (`sevFormatPrice` → `Free`/`$N.NN`) - there is **no** range dash here, and the Trips price-range dash must not migrate in.

**Template cleanup** in `social_events.html`: delete the dead drawer rules (96-108: `.sl-dwfooter`, `.sl-dw-edit`/`.sl-dw-delete` + variants, `.sl-kv`, `.sl-kv .k`, `.sl-kv .v`, `.sl-dw-sub`) and their mobile variants (116-117). Keep all `#sev-list` card chrome.

**Geometry overrides applied here:** footer buttons 9px/14px (not the proposal's 10px/13.5px "UX freeze"); kv geometry 90px/13.5px/baseline (drop the legacy `sl-*` 12px/10px). `.admin-ui-dw-footer` carries no `margin-top:auto` (the proposal incorrectly added it - omit). Sub-line uses the distinct `.admin-ui-dw-sub`, not `-note`.

**Parity checklist (must survive):** drawer renders styled, identical in structure/spacing to Trips (diff the two builders); Status badge row; sticky footer Edit (primary) + Delete (danger); mobile buttons ≥44px with safe-area footer padding; Esc/scrim close restores focus, clears card is-active, releases inert; delete confirms/toasts/closes/removes card; Edit navigates to the deferred edit page; no orphaned `#sev-list .sl-kv`/`.sl-dwfooter`/`.sl-dw-*` rules; no em/en dash in the rendered past-events label; console clean.

### 3.7 Slack Sync

**Files:** `app/static/admin_slack.js`, `app/templates/admin/slack_sync.html`. Two disjoint workstreams. Slack Sync is a previously-unlisted §2.1 drawer victim: its `.ss-dw-*` are scoped under `#slack-sync` while `AdminUI.drawer` mounts to `document.body`, so the reconciliation drawer renders unstyled today; the row-compaction work assumes that drawer works, so workstream B is mandatory.

**Workstream A - row compaction (Step 1, no foundation dependency, pure `#slack-sync` chrome).** Rewrite `ssyncBuildRowActions` (~541-689) so every kind renders exactly one compact trailing primary control plus, for DB kinds, one `.ss-overflow-btn`; no `.ss-picker` mounts at rest. Generalize the existing all-db-unlinked on-demand swap (563-577) to all kinds. Per-kind trailing primary (verb-consistent): all-db-linked → `.ss-act-ghost` "Unlink" (no overflow); all-db-unlinked → `.ss-act-primary` "Link" + overflow `{Delete user}`; attention-db confident → `.ss-act-primary` "Link" (one-click `ssyncLink(record.id, match.candidate.id)`, fast path preserved) + overflow `{Link via picker, Open details, Delete user}`; attention-db weak/none → `.ss-act-primary` "Link" (opens picker) + overflow `{Delete user}`; slack → `.ss-act-primary` "Import" (existing `ssyncShowImportConfirm` verbatim) + overflow `{Link to DB user}` (no Delete - there is no `/admin/slack/delete-slack-user` endpoint).
- **Shorten the confident-match label** from `'Link to @X (email match)'` (601) to `'Link'`; the @name + reason move to the trigger `title`/`aria-describedby` (the existing `warnSpan` 607-612) and the in-picker `.ss-picker-suggestion-badge`. House style: no em/en dashes in the new copy.
- **Expand the picker inside `.ss-row-actions`** (the existing `stopPropagation` sink, line 505), **never** as a descendant of the `.ss-row` `<button>` (invalid interactive nesting that breaks AT). Reuse the all-db-unlinked `pickerWrap` pattern: a `position:relative` div holds the trigger; on click remove the trigger, inject `ssyncLinkPicker(...)` in its place, focus `.ss-picker-input`.
- **Singleton + precedence:** add a module-level `ssyncOpenPicker` (mirror `ssyncOpenPopover`, line 20). Opening a picker closes any other picker and any open popover, and vice versa. Esc and outside-click collapse the picker and return focus to the trigger.
- Generalize `ssyncTogglePopover` (953-1014) to take an `items[]` array (`[{label, danger, action}]`); keep its open/close/Esc/outside-click logic. Remove the three inline `.ss-act-danger` Delete buttons from the trailing column (579-588, 631-640, 656-665); Delete lives only in the overflow.
- Reuse `ssyncLinkPicker`, `ssyncSuggestMatch`, `ssyncSuggestMatchSlack`, `ssyncShowImportConfirm` and the mutation wrappers (`ssyncLink`/`Unlink`/`Delete`/`Import`) byte-for-byte. Fix the picker option-id a11y bug: assign each option an id (e.g. `listId + '-opt-' + idx`) so `updateHighlight`'s `aria-activedescendant` read of `o.id` resolves.
- `slack_sync.html`: add a desktop picker width cap `#slack-sync .ss-row-actions .ss-picker{width:220px}` inside `@media (min-width:768px)` (mobile keeps the fixed bottom-sheet dropdown). Add a coarse-pointer bump `@media (pointer:coarse){#slack-sync .ss-overflow-btn{width:44px;height:44px}#slack-sync .ss-act-primary,#slack-sync .ss-act-ghost{min-height:44px}}`. No new color or geometry tokens. No `{# #}` Jinja sequence in the `<style>` block.

**Workstream B - drawer retrofit (Step 2, gated on foundation).** In `ssyncOpenDrawer` (1018-1252): `.ss-dw-section` → `admin-ui-dw-section`, `.ss-dw-section-title` → `admin-ui-dw-section-title`, `.ss-dw-kv` → `admin-ui-dw-kv`, `.ss-dw-key` → `admin-ui-dw-key`, `.ss-dw-val` → `admin-ui-dw-val`, `.ss-dw-actions` → `admin-ui-dw-footer`, `.ss-dw-btn-primary`/`-ghost`/`-danger` → `admin-ui-dw-btn-*`. For the bespoke confirm-zone (`.ss-dw-confirm-zone`/`-msg`/`-actions`) and email-warn (`.ss-dw-email-warn`) that have no shared analog, **un-scope** them in `slack_sync.html` (drop the `#slack-sync` prefix, keep the names) so they reach the body-mounted panel, mirroring how Members keeps `.mr-dw-*` unscoped. Delete the now-dead scoped `.ss-dw-section`/`-kv`/`-btn` rules (152-159, 164-172). Apply the footer-mount-inside-content correction here too if the confirm footer is appended as a body sibling.

**Parity checklist (must survive):** ~12 rows visible at rest desktop in all three views; rows ~64px until a Link picker expands; Link DB→Slack, Link Slack→DB, confident one-click Link, Unlink, Delete (via overflow), Import (and bulk import) all route through the unchanged mutation wrappers and reload; reconciliation drawer renders styled (DB / Slack / match-analysis sections + unlink/delete/import confirm flows); clicking a primary/overflow control does not also open the drawer (`.ss-row-actions` stops propagation); the row body still opens the drawer on click; grep returns no `{# #}` and no residual drawer `ss-dw-*`/`ss-kv` in row-action code (card-level controls remain); ≤767px rows stay compact, picker/popover render as fixed bottom sheets, controls ≥44px; after a mutation focus moves to a stable anchor (active tab or search box); console clean.

---

## 4. Deferred / out of scope (explicit)

- **All object edit menus and pages:** Seasons edit dialog, Trips edit page, Social Events edit page - cleaned up together in a later once-off pass. This spec only re-classes their Edit footer anchors (href untouched).
- **Members `.mr-dw-*` → shared-class migration:** cosmetic only; Members supplies the reference shape and stays on `.mr-dw-*` this pass.
- **Backend `/data` endpoint changes:** none; reuse existing shapes.
- **Practices config and Skipper surfaces:** untouched (not flagged in the review).
- **`MONEY_HIDDEN` em-dash placeholder** (`admin_payments.js:11`): flagged as an in-code placeholder, not user-facing copy this pass.
- **Follow-on (enabled, not done):** collapse the byte-identical Trips and Social drawer builders into one `AdminUI.drawerContent(...)` helper, and promote the duplicated inert + MutationObserver + restore-focus lifecycle into the drawer primitive.

---

## 5. Risks and mitigations

- **Editing the frozen foundation could ripple to correct drawers.** All additions are new class names; no existing `.admin-ui-*` selector is modified; Members is untouched. One author, one commit, one re-freeze. Verify each drawer after.
- **Five proposals independently transcribed the foundation block with conflicting geometry** (10px vs 9px buttons; 96px vs 90px key; 10.5px vs 11px title). Mitigation: the single foundation commit fixes every value to the verified Members canon up front, before any surface merges; surfaces consume, never redefine.
- **Footer mounted outside the scroll container** silently no-ops `position:sticky` and breaks the edge-to-edge hairline on Seasons/Trips/Social/Slack. Mitigation: footer-mount-inside-content (`content.appendChild(footer)` then `AdminUI.drawer({content})`) is a mandatory acceptance criterion for every retrofit surface, with `admin_users.js:549` as the reference.
- **Mobile drawer occlusion** is a silent gap: a desktop scroll-container padding reserve does not carry into the `AdminUI.drawer` body. Mitigation: each surface with a sticky footer/savebar inside a drawer verifies on a real ≤767px viewport that tail content clears the bar; any fix is scoped to the surface's mobile content node, never the foundation `.admin-ui-drawer__body`.
- **Slack Sync interactive nesting:** mounting the picker inside the `.ss-row` `<button>` is invalid and breaks AT. Mitigation: expand inside `.ss-row-actions`.
- **Slack Sync drawer is unstyled today** and the row work assumes it works. Mitigation: workstream B is mandatory and sequenced after the foundation re-freeze.
- **Roles `flex:1` move is load-bearing:** forgetting to move `flex:1;min-width:0` onto `.rs-row-system` breaks chip right-alignment. Called out explicitly; one-line CSS prepend.
- **Jinja `{# #}` regression** (commit `4506ebb`) silently swallows CSS rules. Mitigation: dead-CSS deletions use only `/* */` comments; re-verify each surface's scoped CSS still matches in the rendered browser, console clean.
- **Sequencing.** Any surface emitting `.admin-ui-*` classes before Step 0 lands renders unstyled (the broken state being fixed). Hard gate: foundation first, re-freeze, then consumers.

**Reference files (absolute paths):** `/Users/rob/env/tcsc-trips/app/static/css/admin_ui.css`, `/Users/rob/env/tcsc-trips/app/templates/admin/users.html`, `/Users/rob/env/tcsc-trips/app/static/admin_users.js`, `/Users/rob/env/tcsc-trips/app/static/js/admin/drawer.js`, `/Users/rob/env/tcsc-trips/app/templates/admin/payments.html`, `/Users/rob/env/tcsc-trips/app/static/admin_payments.js`, `/Users/rob/env/tcsc-trips/app/templates/admin/roles.html`, `/Users/rob/env/tcsc-trips/app/templates/admin/seasons.html`, `/Users/rob/env/tcsc-trips/app/static/admin_seasons.js`, `/Users/rob/env/tcsc-trips/app/templates/admin/trips.html`, `/Users/rob/env/tcsc-trips/app/static/admin_trips.js`, `/Users/rob/env/tcsc-trips/app/templates/admin/social_events.html`, `/Users/rob/env/tcsc-trips/app/static/admin_social_events.js`, `/Users/rob/env/tcsc-trips/app/templates/admin/slack_sync.html`, `/Users/rob/env/tcsc-trips/app/static/admin_slack.js`.
