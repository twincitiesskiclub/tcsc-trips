# Tabulator Review-Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve the polish issues found in the live walkthrough of the completed Tabulator migration by fixing their shared root causes once in the frozen `AdminUI` foundation, then retrofitting each surface onto the result, so the admin panel reads as one cohesive product.

**Architecture:** Cross-surface concerns become globally-scoped `.admin-ui-*` classes in `app/static/css/admin_ui.css` (loaded globally, so they reach the `document.body`-mounted drawer panel); bespoke information architecture stays scoped under each surface root (`#member-roster`, `#pay-root`, `#season-tl`, `#roles-studio`, `#slack-sync`). The Members roster (`.mr-*`) is the canonical reference for every shared shape.

**Tech Stack:** Vanilla ES5-compatible JS (`window.AdminUI`, IIFE modules), scoped `<style>` blocks per template, Tailwind tokens already compiled. No build step for the admin JS/CSS.

**Authoritative source:** `docs/superpowers/specs/2026-06-07-tabulator-review-polish-implementation.md` (committed `ec816ac`). Each task below cites its section; that spec is the exact-edit reference (line numbers, full rename maps, parity checklists). This plan sequences it into commit-sized tasks and inlines the load-bearing/easy-to-miss code.

**Verification model:** This repo has **no JS test runner** (per the migration canon). "Verify" means: with the dev server running (`./scripts/dev.sh 5001`, already up at http://127.0.0.1:5001), load the named admin page, open the browser console, and confirm the named behaviors on desktop **and** at a ≤767px viewport, console clean. The full parity checklist for each surface lives in the spec section cited; the inline checks below are the must-pass subset.

**House style (applies to all copy):** never use em or en dashes. The season separator is the middot `·` (U+00B7), emitted as an `AdminUI.el` text-node child, never an HTML entity, never a dash.

---

## File Structure

**Foundation (authored once, Task 1 only):**
- Modify: `app/static/css/admin_ui.css` - add `.admin-ui-dw-*` drawer-content family, its mobile block, and `.admin-ui-export-*`.

**Per-surface (disjoint ownership):**
- `app/templates/admin/users.html`, `app/static/admin_users.js` - status cell (scoped) + CSV (consume foundation)
- `app/templates/admin/payments.html`, `app/static/admin_payments.js` - drawer + pill + CSV
- `app/templates/admin/roles.html` - rail declutter + savebar (scoped only)
- `app/templates/admin/seasons.html`, `app/static/admin_seasons.js` - drawer
- `app/templates/admin/trips.html`, `app/static/admin_trips.js` - drawer
- `app/templates/admin/social_events.html`, `app/static/admin_social_events.js` - drawer (lockstep mirror of Trips)
- `app/templates/admin/slack_sync.html`, `app/static/admin_slack.js` - row compaction (scoped) + drawer retrofit (consume foundation)

**Sequencing gate:** Task 1 (foundation) lands and is re-frozen before any task that emits `.admin-ui-*` classes (Tasks 3, 4, 6, 7, 8, 10). Tasks 2, 5, 9 are pure scoped chrome and have no foundation dependency. Tasks 7 and 8 land back-to-back (Trips/Social lockstep).

---

## Task 1: Shared foundation - drawer-content + CSV export conventions

Spec: §1.1, §1.2, §1.3, §1.5. One author, one commit, additive only (no existing `.admin-ui-*` selector is modified, so Members and every currently-correct drawer are unaffected).

**Files:**
- Modify: `app/static/css/admin_ui.css`

- [ ] **Step 1: Append the drawer-content family immediately after the `.admin-ui-drawer__body` rule** (currently `admin_ui.css:57`). Paste verbatim:

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

- [ ] **Step 2: Append the drawer mobile rules inside the existing `@media (max-width: 767px)` block** (currently `admin_ui.css:67-70`):

```css
  .admin-ui-dw-key{width:80px}
  .admin-ui-dw-footer{padding-bottom:calc(13px + env(safe-area-inset-bottom,0px))}
  .admin-ui-dw-btn-primary,.admin-ui-dw-btn-ghost,.admin-ui-dw-btn-success,.admin-ui-dw-btn-danger{min-height:44px}
```

- [ ] **Step 3: Append the CSV export family after the `.admin-ui-sticky-bar` block** (currently `admin_ui.css:65`). Note the hairline is the foundation's own `#e4e4e7` (not `#e5e7eb`) and the control is on the 38px geometry token:

```css
/* --- CSV export (shared) --- */
.admin-ui-export-bar{display:flex;justify-content:flex-end;margin-top:16px;padding-top:14px;border-top:1px solid #e4e4e7}
.admin-ui-export-btn{display:inline-flex;align-items:center;gap:6px;height:38px;padding:0 14px;border:1.5px solid #e4e4e7;border-radius:10px;background:#fff;color:#64748b;font-size:13px;font-weight:600;cursor:pointer;font-family:inherit;transition:border-color .12s,color .12s}
.admin-ui-export-btn:hover{border-color:#1c2c44;color:#1c2c44}
.admin-ui-export-btn:focus-visible{outline:2px solid #1c2c44;outline-offset:2px}
```

- [ ] **Step 4: Verify the foundation is additive and renders.** Load http://127.0.0.1:5001/admin/users (Members, which still uses `.mr-dw-*`). Open a member drawer; confirm it is unchanged. In the console run `getComputedStyle(document.querySelector('body')).length > 0` is not needed - instead create a probe: run in console
```javascript
var p=document.createElement('div');p.className='admin-ui-dw-key';document.body.appendChild(p);console.log(getComputedStyle(p).width);p.remove();
```
Expected: `90px` (the new class resolves globally). Console clean.

- [ ] **Step 5: Commit and re-freeze the foundation.** The tag marks the foundation read-only for all subsequent surface tasks.

```bash
git add app/static/css/admin_ui.css
git commit -m "feat(admin-ui): shared drawer-content + CSV export conventions"
git tag -f admin-ui-foundation-frozen
```

---

## Task 2: Members - grouped status cell  *(no foundation dependency)*

Spec: §3.1 "Grouped status cell" + parity checklist. Replaces the two unlabeled badges (split across row columns 3 and 4) with one status column: Member status badge on top, muted season sub-line below, prefixed with the effective season name.

**Files:**
- Modify: `app/templates/admin/users.html` (CSS at line 110; mobile at line 206)
- Modify: `app/static/admin_users.js` (state ~line 15; helper ~line 86; `mr_applyGlobalView`; `mr_buildRow` lines 276-328)

- [ ] **Step 1: Rename the badges CSS and add the sub-line style.** In `users.html`, replace the `.mr-badges` rule (line 110) with:

```css
.mr-status-cell{display:flex;flex-direction:column;align-items:flex-end;gap:5px;flex-shrink:0}
.mr-status-sub{font-size:12px;color:#64748b;font-weight:500;text-align:right;white-space:nowrap}
```

- [ ] **Step 2: Update the mobile selector.** In `users.html` mobile block (line 206), change `.mr-badges,.mr-actions` to `.mr-status-cell,.mr-actions`.

- [ ] **Step 3: Add module state and a short-status helper.** In `admin_users.js`, add near the season/view state (~line 15): `var mr_effectiveSeasonName = null;`. Add near `mr_seasonText` (~line 86) - do **not** modify `mr_seasonText` (the drawer still needs its verbose forms):

```javascript
function mr_seasonTextShort(ss){
  var map={ACTIVE:'Active',PENDING_LOTTERY:'Lottery',DROPPED_LOTTERY:'Dropped',DROPPED_VOLUNTARY:'Dropped',DROPPED_CAUSE:'Dropped'};
  return map[ss]||'';
}
```

- [ ] **Step 4: Stash the effective season name from the existing context.** In `mr_applyGlobalView`, immediately after `effId` is resolved, add (reuse `effId`/`allSeasons` already in scope - do not derive independently):

```javascript
var _es = (effId !== null) ? allSeasons.find(function(s){return s.id === effId;}) : null;
mr_effectiveSeasonName = _es ? _es.name : null;
```

- [ ] **Step 5: Rebuild the status column in `mr_buildRow`** (lines 276-305). Delete the `ssBadge`/`badgesEl` block. Build the member badge and season sub-line, and remove the status badge from the actions zone:

```javascript
var statusBadge = AdminUI.statusBadge(mr_statusText(user.status), mr_statusVariant(user.status));
statusBadge.setAttribute('aria-label', 'Member status: ' + mr_statusText(user.status));

var subText = user.season_status
  ? ((mr_effectiveSeasonName ? mr_effectiveSeasonName + ' · ' : '') + mr_seasonTextShort(user.season_status))
  : 'Not registered';
var seasonSubEl = el('span', {
  class: 'mr-status-sub',
  'aria-label': user.season_status
    ? ('Season: ' + (mr_effectiveSeasonName ? mr_effectiveSeasonName + ', ' : '') + mr_seasonTextShort(user.season_status))
    : 'Not registered in current season'
}, [subText]);

var statusCellEl = el('div', { class: 'mr-status-cell' }, [statusBadge, seasonSubEl]);
```

Change `actionsEl` to drop the status badge: `var actionsEl = el('div', { class: 'mr-actions' }, [selectCb, editBtn]);`. Change the row child array (line 328) from `[avatarEl, primaryEl, badgesEl, actionsEl]` to `[avatarEl, primaryEl, statusCellEl, actionsEl]`. The `·` in `subText` is U+00B7 (middot), a literal text-node character.

- [ ] **Step 6: Verify.** Load http://127.0.0.1:5001/admin/users. Confirm: member badge on top, muted season sub-line below right-aligned; switching the season select re-prefixes every row's sub-line and flips the short status; All/Alumni/Waitlist views show the current-season name as prefix; an unregistered member shows `Not registered` (no prefix, no badge); no `undefined` and no leading `· ` on any row. At ≤767px the cell spans full width with badge + sub-line inline and Edit not pushed off-screen. Console clean. (Full list: spec §3.1 parity checklist.)

- [ ] **Step 7: Commit.**

```bash
git add app/templates/admin/users.html app/static/admin_users.js
git commit -m "feat(members): grouped status cell (member badge + season sub-line)"
```

---

## Task 3: Members - CSV export swap  *(depends on Task 1)*

Spec: §3.1 "CSV swap". Zero JS diff for export; markup + dead-CSS only.

**Files:**
- Modify: `app/templates/admin/users.html` (dead rule line 194; export markup lines 315-317)

- [ ] **Step 1: Remove the dead footer rule.** In `users.html`, delete the `.mr-footer-row` rule (line 194).

- [ ] **Step 2: Replace the export markup** (lines 315-317) with the canonical export bar (this SVG + copy is what Payments will copy byte-for-byte):

```html
  <div class="admin-ui-export-bar"><button id="mr-export-csv" class="admin-ui-export-btn"><svg width="13" height="13" viewBox="0 0 16 16" fill="none" aria-hidden="true" style="flex-shrink:0"><path d="M8 11L3 6h3V1h4v5h3L8 11Z" fill="currentColor"/><rect x="2" y="13" width="12" height="2" rx="1" fill="currentColor"/></svg>Export CSV</button></div>
```

Keep `id="mr-export-csv"` and its existing JS wiring (`admin_users.js:1256-1257`) untouched.

- [ ] **Step 3: Verify.** Load http://127.0.0.1:5001/admin/users. The export control reads as a quiet bottom-right utility (white, muted, download glyph), not a CTA. Click it; `tcsc_members.csv` downloads unchanged. Console clean, desktop + ≤767px.

- [ ] **Step 4: Commit.**

```bash
git add app/templates/admin/users.html
git commit -m "feat(members): unified quiet CSV export treatment"
```

---

## Task 4: Payments - drawer retrofit + pill height + CSV  *(depends on Task 1)*

Spec: §3.2 + parity checklist. Three disjoint fixes; zero foundation authorship.

**Files:**
- Modify: `app/static/admin_payments.js` (`pay_kvRow` 926-931; `pay_openDrawer` 874-924; `pay_buildShell` 88-96)
- Modify: `app/templates/admin/payments.html` (dead drawer rules 289-361 + mobile 617-619; `.pw-btn-ghost` 31-47; keep `.pw-type-pill` 220-229)

- [ ] **Step 1: Retrofit the drawer builder class names.** In `admin_payments.js`, apply this exact rename map:

| Location | Old class | New class |
|---|---|---|
| `pay_kvRow` 926-931 | `pw-kv-row` / `pw-kv-key` / `pw-kv-val` | `admin-ui-dw-kv` / `admin-ui-dw-key` / `admin-ui-dw-val` |
| `pay_openDrawer` 892 (`kvList`) | `pw-kv-list` | `admin-ui-dw` |
| 883 (Type value) | `pw-type-pill` | `admin-ui-dw-pill` |
| 889 (Intent ID) | `pw-kv-mono` | `admin-ui-dw-val--mono` |
| 907 (`actRow`) | `pw-dw-actions` | `admin-ui-dw-footer` |
| 897 (accept btn) | (its class) | `admin-ui-dw-btn-primary` |
| 903 (refund btn) | (its class) | `admin-ui-dw-btn-danger` |

Preserve the existing `setAttribute('disabled', ...)` calls (899/905).

- [ ] **Step 2: Mount the footer inside the content node (mandatory convention).** In `pay_openDrawer`, ensure `actRow` is appended as the last child of the `admin-ui-dw` content node (`content.appendChild(actRow)`) **before** the node is passed to `AdminUI.drawer({content})`. A body-sibling mount silently breaks `position:sticky`. Reference: `admin_users.js:549`.

- [ ] **Step 3: Scope the capturable-only pill height.** In `payments.html`, add `#pay-root .admin-ui-pill{height:38px}` (radius stays 9999px). Do **not** touch the global `.admin-ui-pill`.

- [ ] **Step 4: Move export into the shared bar.** In `pay_buildShell` (88-96), remove `exportBtn` from `pw-head` and, after the spacer, append `<div class="admin-ui-export-bar">` holding `<button class="admin-ui-export-btn" id="pw-export-csv" onclick=pay_exportCsv>` with the identical aria-hidden SVG glyph + `Export CSV` text from Task 3. `pay_exportCsv` (943-975, exports `state.currentFiltered`) is untouched.

- [ ] **Step 5: Delete dead CSS.** In `payments.html`, delete the drawer KV + action rules (289-361) and their mobile overrides (617-619), and the now-dead `#pay-root .pw-btn-ghost` rules (31-47). **Keep `.pw-type-pill` (220-229)** - it still styles the on-ledger row pill. Use only `/* */` comments; introduce no `{# #}` sequence.

- [ ] **Step 6: Verify.** Load http://127.0.0.1:5001/admin/payments. Open a transaction: drawer renders styled (90px muted keys, navy values, Type as a styled pill, Intent ID monospace + break-all with no overflow at 420px, sticky footer accept/refund). Closed/refunded payments show disabled accept/refund. "Capturable only" filter now matches sibling select height. Export reads as a quiet utility and exports the filtered set. Bulk capture/refund still work. Console clean, desktop + ≤767px. (Full list: spec §3.2.)

- [ ] **Step 7: Commit.**

```bash
git add app/templates/admin/payments.html app/static/admin_payments.js
git commit -m "feat(payments): shared drawer convention, filter sizing, unified CSV"
```

---

## Task 5: Roles - rail declutter + savebar overlap  *(no foundation dependency)*

Spec: §3.3 + parity checklist. All edits inside `roles.html`'s `<style>` and inline `<script>`.

**Files:**
- Modify: `app/templates/admin/roles.html`

- [ ] **Step 1: Remove the duplicate display name from the rail row.** In `rsRenderList()` (247-252), replace the button children array

```javascript
rsLiveBadge(role, false),
el('div',{'class':'rs-row-names'},[el('div',{'class':'rs-row-display'},[role.display_name||'']), el('div',{'class':'rs-row-system'},[role.name||''])]),
rsUserChip(role.user_count, role.id)
```

with

```javascript
rsLiveBadge(role, false),
el('div',{'class':'rs-row-system'},[role.name||'']),
rsUserChip(role.user_count, role.id)
```

- [ ] **Step 2: Update rail CSS.** Delete `.rs-row-names` (line 40) and `.rs-row-display` (line 41). Update `.rs-row-system` (line 42) to **prepend** `flex:1;min-width:0` (load-bearing - without it the system name will not grow and the count chip will not right-align):

```css
#roles-studio .rs-row-system{flex:1;min-width:0;font-size:11px;font-family:monospace;color:#64748b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
```

Add a rail-scoped badge cap (do **not** cap the shared `.rs-badge` base on line 48 - the editor preview reuses it uncapped):

```css
#roles-studio .rs-row .rs-badge{max-width:60%;overflow:hidden;text-overflow:ellipsis}
```

Keep the mobile `#roles-studio .rs-row-system{display:none}` (line 117).

- [ ] **Step 3: Fix the savebar overlap.** Change `#rs-editor` (line 59) padding from `20px 24px` to `20px 24px 72px` so the gradient swatch grid and description scroll fully above the sticky bar.

- [ ] **Step 4: Drop the duplicate savebar rule.** Delete the scoped `#roles-studio .rs-savebar` rule (line 103) - it is identical to the foundation `.admin-ui-sticky-bar` the element already carries (roles.html:505), and the foundation also supplies the mobile safe-area padding. Keep the inert `rs-savebar` class on the element as a future override hook.

- [ ] **Step 5: Verify (including the mobile drawer).** Load http://127.0.0.1:5001/admin/roles. Rail rows show badge + muted system name + count chip, no duplicate name; a long display name truncates at 60% without pushing the system name/chip off-row; the 0-user vs many-user chip variant and right-alignment are correct. Select a role: all gradient swatches and the description are reachable above the Save/Delete bar. At ≤767px, open the editor drawer and confirm the last swatch row (5-wide) and the textarea clear the sticky savebar; **only if occluded**, set `content.style.paddingBottom='72px'` on the detached content node in `rsOpenEditorMobile` (~585) - never edit the foundation `.admin-ui-drawer__body`. Console clean. (Full list: spec §3.3.)

- [ ] **Step 6: Commit.**

```bash
git add app/templates/admin/roles.html
git commit -m "feat(roles): declutter rail, fix gradient/savebar overlap"
```

---

## Task 6: Seasons - drawer retrofit  *(depends on Task 1)*

Spec: §3.4 + parity checklist. Consumer of the shared drawer family plus `-btn-success` / `-desc` / `-pill`.

**Files:**
- Modify: `app/static/admin_seasons.js` (`stlBuildDrawerContent` 494-595; `stlOpenPreview` 597-671)
- Modify: `app/templates/admin/seasons.html` (delete drawer rules 26-34, 81-89, 91-92; edit lines 23, 127, 128; keep `.stl-pill`, `.stl-year`)

- [ ] **Step 1: Rename the content builder classes.** In `stlBuildDrawerContent` (494-595), apply:

| Old | New |
|---|---|
| `stl-blk` | `admin-ui-dw-section` |
| `stl-blk-h` | `admin-ui-dw-section-title` |
| `stl-kv` | `admin-ui-dw-kv` |
| `{class:'k'}` | `admin-ui-dw-key` |
| `{class:'v'}` | `admin-ui-dw-val` |
| placeholder values (`-`, `Not set`, `No limit`) | `admin-ui-dw-val admin-ui-dw-val--empty` |
| `stl-desc-box` (590) | `admin-ui-dw-desc` |
| outer wrapper (594) | add `class:'admin-ui-dw'` |

For the drawer meta (500-502): route the meta pill through `.admin-ui-dw-pill`; the year span uses a plain muted `admin-ui-dw-val` (no second pill class). Do **not** introduce `admin-ui-dw-meta`. **Keep** the `.stl-pill` / `.stl-year` rules in the template - the on-page hero/node cards still use them.

- [ ] **Step 2: Rename the footer buttons and correct the mount.** In `stlOpenPreview` (597-671): `stl-dw-footer` → `admin-ui-dw-footer`; Edit `stl-act-primary` → `admin-ui-dw-btn-primary`; Export CSV + Late Link `stl-act-ghost` → `admin-ui-dw-btn-ghost`; Activate `stl-act-success` → `admin-ui-dw-btn-success`; Delete `stl-act-danger` → `admin-ui-dw-btn-danger`. Restructure so the footer mounts inside content:

```javascript
var content = stlBuildDrawerContent(season);
// ... build footer ...
content.appendChild(footer);
var drawer = AdminUI.drawer({ title: season.name, content: content });
```

**Delete** the sibling mount (637-639: `var panel = drawer.body.parentElement; if(panel) panel.appendChild(footer);`). Only `-btn-primary` carries `flex:1`; ghost/success/danger are content-width and wrap. Migrate the active-card cleanup observer to `drawer.body.closest('.admin-ui-drawer')`; keep the `drawer.close` override (641-647) and `stlMarkActiveCard`.

- [ ] **Step 3: Delete dead template CSS.** In `seasons.html`, delete: the drawer-actions block (26-34), the drawer-detail block (81-89: `.stl-dw-meta`, `.stl-blk`(+`:last-child`), `.stl-blk-h`, `.stl-kv`(+`:last-child`), `.stl-kv .k`, `.stl-kv .v`, `.stl-desc-box`), the drawer-footer block (91-92). Edit line 23 to drop the trailing `, #season-tl a.stl-act:focus-visible` fragment. In the mobile block drop `,#season-tl a.stl-act` from line 127 and delete line 128 (`.stl-dw-footer` padding-bottom). **Keep** `.stl-pill`, `.stl-year`, all hero/node/card/head/count/btn/win/stat rules, the deferred edit-form inputs, the confirm + late-link modals, copy-row, aria-live, reduced-motion. Use only `/* */` comments.

- [ ] **Step 4: Verify no orphaned references.** Run:
```bash
grep -nE "stl-blk|stl-kv|stl-desc-box|stl-dw-footer|stl-act" app/static/admin_seasons.js
```
Expected: no matches in emitted markup. Run `grep -n "stl-pill\|stl-year" app/static/admin_seasons.js` - expected: only the card builders.

- [ ] **Step 5: Verify in browser.** Load http://127.0.0.1:5001/admin/seasons. Open a season: drawer renders styled (sections with real text titles, 90px muted keys, navy values, description in a bordered box, sticky footer with Edit/Activate/Late Link/Export/Delete wrapping sanely). The active-card highlight clears on every close path (X, Esc, scrim, programmatic activate/delete). Edit navigates to the deferred edit page. Tab order: Edit first. At ≤767px the five buttons wrap with ≥44px targets; confirm/late-link modals layer above the drawer. Console clean. (Full list: spec §3.4.)

- [ ] **Step 6: Commit.**

```bash
git add app/templates/admin/seasons.html app/static/admin_seasons.js
git commit -m "feat(seasons): adopt shared drawer-content convention"
```

---

## Task 7: Trips - drawer retrofit  *(depends on Task 1; lockstep with Task 8)*

Spec: §3.5 + parity checklist. Emits the subset `{dw, dw-sub, dw-kv, dw-key, dw-val, dw-footer, dw-btn-primary, dw-btn-danger}`; flat KV list (no `-section` blocks).

**Files:**
- Modify: `app/static/admin_trips.js` (`tripsOpenDrawer` 316-462; `tripsRenderCard` ~131)
- Modify: `app/templates/admin/trips.html` (delete drawer rules 95-108 + mobile 116-117)

- [ ] **Step 1: Rename the builder classes.** In `tripsOpenDrawer` (316-462):

| Location | Old | New |
|---|---|---|
| 336 | `tl-dw-sub` | `admin-ui-dw-sub` |
| 376 (`contentDiv`) | (none) | add `class:'admin-ui-dw'` |
| 378-385 + badge row 388-396 | `tl-kv` / `k` / `v` | `admin-ui-dw-kv` / `admin-ui-dw-key` / `admin-ui-dw-val` |
| 404 (Edit) | `tl-dw-edit` | `admin-ui-dw-btn-primary` |
| 409 (Delete) | `tl-dw-delete` | `admin-ui-dw-btn-danger` |
| 412 (footer) | `tl-dwfooter` | `admin-ui-dw-footer` |

- [ ] **Step 2: Correct the footer mount.** Change `drawer.body.appendChild(footer)` (413) to `contentDiv.appendChild(footer)` placed **before** the `AdminUI.drawer({content: contentDiv})` call (399). Keep `tripsCurrentDrawer` assigned (400) before the footer build so `tripsDelete`'s id-guard (470) holds. Do **not** touch the MutationObserver (438-461), the wrapped `origClose` (416-430), inert toggles, is-active management, or the Edit href.

- [ ] **Step 3: Fix house-style dashes.** Change the price-range en dash to `' - '` (hyphen) at the drawer (~366) and the card `tripsRenderCard` (~131); change any past-count em dash to `'· '` (middot).

- [ ] **Step 4: Delete dead template CSS.** In `trips.html`, delete the drawer rules (95-108: `.tl-dwfooter`, `.tl-dw-edit`/`.tl-dw-delete` + hovers + focus-visible, `.tl-kv`, `.tl-kv .k`, `.tl-kv .v`, `.tl-dw-sub`) and their mobile variants (116-117). Keep all `#trips-list` card/toolbar/header/date-block/aside/past-toggle/empty rules.

- [ ] **Step 5: Verify.** Load http://127.0.0.1:5001/admin/trips. Open a trip from card click and from keyboard: drawer renders styled (sub-line, 90px muted keys + navy values, Status badge row, sticky footer Edit + Delete spanning edge-to-edge). Esc/scrim/X/delete-from-drawer all restore card `.is-active` removed, rows un-inerted, focus returned. Edit navigates to the deferred page. No en/em dashes in rendered copy. At ≤767px the drawer is full-width, footer clears the home indicator, buttons ≥44px. Console clean. (Full list: spec §3.5.)

- [ ] **Step 6: Commit.**

```bash
git add app/templates/admin/trips.html app/static/admin_trips.js
git commit -m "feat(trips): adopt shared drawer-content convention"
```

---

## Task 8: Social Events - drawer retrofit (lockstep mirror of Trips)  *(depends on Task 1; lands with Task 7)*

Spec: §3.6 + parity checklist. Identical class set, node order, and footer mount as Trips so a follow-on can collapse both into one builder.

**Files:**
- Modify: `app/static/admin_social_events.js` (`sevOpenDrawer`)
- Modify: `app/templates/admin/social_events.html` (delete drawer rules 96-108 + mobile 116-117)

- [ ] **Step 1: Rename the builder classes** in `sevOpenDrawer`:

| Location | Old | New |
|---|---|---|
| 342 | `sl-dw-sub` | `admin-ui-dw-sub` |
| 375 (`contentDiv`) | (none) | add `class:'admin-ui-dw'` |
| 379-394 + badge row 386-388 | `sl-kv` / `k` / `v` | `admin-ui-dw-kv` / `admin-ui-dw-key` / `admin-ui-dw-val` |
| 401 (Edit) | `sl-dw-edit` | `admin-ui-dw-btn-primary` |
| 406 (Delete) | `sl-dw-delete` | `admin-ui-dw-btn-danger` |
| 409 (footer) | `sl-dwfooter` | `admin-ui-dw-footer` |

- [ ] **Step 2: Correct the footer mount.** Change `drawer.body.appendChild(footer)` (410) to `contentDiv.appendChild(footer)` before the `AdminUI.drawer({content: contentDiv})` call (mirror of Trips). Do **not** touch the MutationObserver, wrapped close, inert, `sevCurrentDrawer` assignment, or the Edit href.

- [ ] **Step 3: Fix the house-style dash.** Change the past-count em dash `'— ' + past.length` (~289) to `'· ' + past.length`. Social has a single price (`Free`/`$N.NN`) - there is **no** range dash; do not migrate the Trips price-range dash in.

- [ ] **Step 4: Delete dead template CSS.** In `social_events.html`, delete the drawer rules (96-108: `.sl-dwfooter`, `.sl-dw-edit`/`.sl-dw-delete` + variants, `.sl-kv`, `.sl-kv .k`, `.sl-kv .v`, `.sl-dw-sub`) and their mobile variants (116-117). Keep all `#sev-list` card chrome.

- [ ] **Step 5: Verify, including the builder diff (lockstep acceptance).** Load http://127.0.0.1:5001/admin/social-events. Open an event: drawer is styled and **structurally identical to Trips** (Status badge row, sticky footer Edit + Delete). Then diff the two builders to confirm identical class strings + node order:
```bash
grep -n "admin-ui-dw" app/static/admin_trips.js app/static/admin_social_events.js
```
Expected: the same class set in the same order in both. Esc/scrim close restores focus, clears card is-active, releases inert; delete confirms/toasts/closes/removes card; no orphaned `.sl-kv`/`.sl-dwfooter` rules; no em/en dash in the past-events label. Console clean, ≤767px buttons ≥44px. (Full list: spec §3.6.)

- [ ] **Step 6: Commit.**

```bash
git add app/templates/admin/social_events.html app/static/admin_social_events.js
git commit -m "feat(social-events): adopt shared drawer convention (lockstep with trips)"
```

---

## Task 9: Slack Sync - row compaction (workstream A)  *(no foundation dependency)*

Spec: §3.7 workstream A + parity checklist. Pure `#slack-sync` chrome. Rewrite `ssyncBuildRowActions` (~541-689) so every row renders exactly one compact trailing primary control (plus one overflow for DB kinds); no `.ss-picker` mounts at rest.

**Files:**
- Modify: `app/static/admin_slack.js` (`ssyncBuildRowActions` ~541-689; `ssyncTogglePopover` 953-1014; add module singleton near line 20)
- Modify: `app/templates/admin/slack_sync.html` (add two scoped media rules)

- [ ] **Step 1: Generalize the on-demand picker swap to every kind.** Generalize the existing all-db-unlinked pattern (563-577) so each kind's trailing column renders one primary control; the `.ss-picker` is injected only when the primary is clicked. Per-kind primary (verb-consistent), reusing the existing mutation wrappers verbatim:
  - all-db-linked → `.ss-act-ghost` "Unlink" (no overflow)
  - all-db-unlinked → `.ss-act-primary` "Link" + overflow `{Delete user}`
  - attention-db confident → `.ss-act-primary` "Link" (one-click `ssyncLink(record.id, match.candidate.id)`, fast path preserved) + overflow `{Link via picker, Open details, Delete user}`
  - attention-db weak/none → `.ss-act-primary` "Link" (opens picker) + overflow `{Delete user}`
  - slack → `.ss-act-primary` "Import" (existing `ssyncShowImportConfirm` verbatim) + overflow `{Link to DB user}` (no Delete - there is no delete-slack-user endpoint)

- [ ] **Step 2: Shorten the confident-match label.** Change `'Link to @X (email match)'` (601) to `'Link'`; move the @name + reason to the trigger `title`/`aria-describedby` (existing `warnSpan` 607-612) and the in-picker `.ss-picker-suggestion-badge`. No em/en dashes in the new copy.

- [ ] **Step 3: Expand the picker inside `.ss-row-actions`, never inside the row `<button>`.** Reuse the all-db-unlinked `pickerWrap` pattern: a `position:relative` div holds the trigger; on click, remove the trigger, inject `ssyncLinkPicker(...)` in its place, and focus `.ss-picker-input`. The `.ss-row-actions` is the existing `stopPropagation` sink (line 505); mounting the picker as a descendant of the `.ss-row` `<button>` is invalid interactive nesting and breaks AT - do not do it.

- [ ] **Step 4: Add a picker singleton + popover precedence.** Add a module-level `ssyncOpenPicker` (mirror `ssyncOpenPopover`, line 20). Opening a picker closes any other picker and any open popover, and vice versa; Esc and outside-click collapse the picker and return focus to the trigger.

- [ ] **Step 5: Generalize the overflow menu and remove inline Delete buttons.** Generalize `ssyncTogglePopover` (953-1014) to take an `items[]` array (`[{label, danger, action}]`), keeping its open/close/Esc/outside-click logic. Remove the three inline `.ss-act-danger` Delete buttons from the trailing column (579-588, 631-640, 656-665); Delete lives only in the overflow. Reuse `ssyncLinkPicker`, `ssyncSuggestMatch`, `ssyncSuggestMatchSlack`, `ssyncShowImportConfirm` and the mutation wrappers byte-for-byte.

- [ ] **Step 6: Fix the picker option-id a11y bug.** Assign each picker option an id (e.g. `listId + '-opt-' + idx`) so `updateHighlight`'s `aria-activedescendant` read of `o.id` resolves.

- [ ] **Step 7: Add scoped responsive rules.** In `slack_sync.html`, inside `@media (min-width:768px)` add `#slack-sync .ss-row-actions .ss-picker{width:220px}` (mobile keeps the fixed bottom-sheet dropdown). Add `@media (pointer:coarse){#slack-sync .ss-overflow-btn{width:44px;height:44px}#slack-sync .ss-act-primary,#slack-sync .ss-act-ghost{min-height:44px}}`. No new color/geometry tokens; no `{# #}` sequence in the `<style>` block.

- [ ] **Step 8: Verify.** Load http://127.0.0.1:5001/admin/slack. In all three views (~12 rows visible at rest desktop), rows are ~64px until a Link picker is expanded. Confirm: Link (DB→Slack), confident one-click Link, Unlink, Delete (via overflow), Import + bulk import all route through the unchanged wrappers and reload; clicking a primary/overflow control does not also open the reconciliation drawer; the row body still opens the drawer; only one picker/popover open at a time, Esc/outside-click collapse and restore focus. At ≤767px rows stay compact and the picker/popover render as fixed bottom sheets, controls ≥44px. Console clean (no `aria-activedescendant` warnings). (Full list: spec §3.7.)

- [ ] **Step 9: Commit.**

```bash
git add app/templates/admin/slack_sync.html app/static/admin_slack.js
git commit -m "feat(slack-sync): compact rows with on-demand link picker + overflow"
```

---

## Task 10: Slack Sync - drawer retrofit (workstream B)  *(depends on Task 1)*

Spec: §3.7 workstream B + parity checklist. The reconciliation drawer's `.ss-dw-*` are scoped under `#slack-sync` and never reach the body-mounted panel; this retrofits them onto the shared family and un-scopes the bespoke confirm-zone.

**Files:**
- Modify: `app/static/admin_slack.js` (`ssyncOpenDrawer` 1018-1252)
- Modify: `app/templates/admin/slack_sync.html` (un-scope confirm-zone/email-warn; delete dead scoped rules 152-159, 164-172)

- [ ] **Step 1: Rename the drawer builder classes** in `ssyncOpenDrawer` (1018-1252):

| Old | New |
|---|---|
| `ss-dw-section` | `admin-ui-dw-section` |
| `ss-dw-section-title` | `admin-ui-dw-section-title` |
| `ss-dw-kv` | `admin-ui-dw-kv` |
| `ss-dw-key` | `admin-ui-dw-key` |
| `ss-dw-val` | `admin-ui-dw-val` |
| `ss-dw-actions` | `admin-ui-dw-footer` |
| `ss-dw-btn-primary` / `-ghost` / `-danger` | `admin-ui-dw-btn-primary` / `-ghost` / `-danger` |

If the confirm footer is appended as a body sibling, apply the footer-mount-inside-content correction here too.

- [ ] **Step 2: Un-scope the bespoke confirm-zone + email-warn.** In `slack_sync.html`, for `.ss-dw-confirm-zone` / `-msg` / `-actions` and `.ss-dw-email-warn` (no shared analog), drop the `#slack-sync` prefix but keep the class names, so they reach the body-mounted panel (mirroring how Members keeps `.mr-dw-*` unscoped).

- [ ] **Step 3: Delete dead scoped CSS.** Delete the now-unused scoped `.ss-dw-section`/`-kv`/`-btn` rules (152-159, 164-172). Use only `/* */` comments; no `{# #}` sequence.

- [ ] **Step 4: Verify no orphans.** Run:
```bash
grep -nE "ss-dw-(section|kv|key|val|actions|btn)" app/static/admin_slack.js
```
Expected: no matches (all renamed). Card-level controls remain untouched.

- [ ] **Step 5: Verify in browser.** Load http://127.0.0.1:5001/admin/slack. Click a row body to open the reconciliation drawer: it renders styled (DB / Slack / match-analysis sections + the unlink/delete/import confirm flows). Confirm the unlink/delete/import confirm zones and email warnings are styled. Console clean, desktop + ≤767px. (Full list: spec §3.7 workstream B.)

- [ ] **Step 6: Commit.**

```bash
git add app/templates/admin/slack_sync.html app/static/admin_slack.js
git commit -m "feat(slack-sync): retrofit reconciliation drawer onto shared convention"
```

---

## Final verification (after all tasks)

- [ ] **Step 1: All six drawers read as one component.** Open the drawer on Members, Payments, Seasons, Trips, Social Events, and Slack Sync side by side; confirm identical key width, section-title style, footer geometry, and button shapes.

- [ ] **Step 2: No regressions, no stray dashes, no Jinja-comment breakage.** Run:
```bash
grep -rnE "—|–" app/templates/admin app/static/admin_*.js app/static/js/admin 2>/dev/null
grep -rn "{#" app/templates/admin/*.html | grep -i "style\|admin" || true
```
Expected: no em/en dashes in admin UI copy; no `{#` inside `<style>` blocks.

- [ ] **Step 3: Smoke-test every migrated admin page** (the parent program's outstanding WF-9 Step 5) on desktop + ≤767px, console clean: `/admin/users`, `/admin/payments`, `/admin/trips`, `/admin/social-events`, `/admin/seasons`, `/admin/roles`, `/admin/practices/config`, `/admin/slack`, `/admin/skipper`.

---

## Deferred (explicit, do not implement)

- All object **edit menus and pages**: Seasons edit dialog, Trips edit page, Social Events edit page. This plan only re-classes their Edit footer anchors (href untouched).
- Members `.mr-dw-*` → shared-class migration (cosmetic; Members stays the reference shape).
- Collapsing the byte-identical Trips/Social drawer builders into one `AdminUI.drawerContent(...)` helper, and promoting the inert + MutationObserver + restore-focus lifecycle into the drawer primitive (follow-on, enabled by this work).
- Backend `/data` changes; Practices config and Skipper surfaces.

---

## Self-Review Notes

- **Spec coverage:** foundation §1.1-1.3 → Task 1; §1.5 conventions embedded in Tasks 4/6/7/8/10 (footer-mount-inside-content) ; Members §3.1 → Tasks 2-3; Payments §3.2 → Task 4; Roles §3.3 → Task 5; Seasons §3.4 → Task 6; Trips §3.5 → Task 7; Social §3.6 → Task 8; Slack A/B §3.7 → Tasks 9-10; sequencing §2 → task ordering + the foundation re-freeze in Task 1 Step 5; deferred §4 and risks §5 reflected in the Deferred section and the per-task load-bearing callouts (footer mount, Roles `flex:1`, Jinja `{#`, mobile drawer occlusion).
- **Re-freeze timing:** resolved to right after the foundation commit (Task 1 Step 5) so every subsequent surface task consumes a frozen foundation, consistent with the parent program's freeze-then-consume model.
- **Type/name consistency:** the foundation class names authored in Task 1 are the exact strings consumed by Tasks 3, 4, 6, 7, 8, 10; helper names (`mr_seasonTextShort`, `mr_effectiveSeasonName`, `ssyncOpenPicker`) are defined in the task that first uses them.
