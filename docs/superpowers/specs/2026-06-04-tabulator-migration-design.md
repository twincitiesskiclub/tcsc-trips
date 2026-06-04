# Tabulator Eradication — Admin Panel Migration Program

**Date:** 2026-06-04
**Status:** Design approved, pending spec review
**Goal:** Remove the Tabulator.js dependency entirely. Replace every admin grid with a
purpose-built, context-tailored UI — mirroring what the practices→calendar migration achieved —
with feature parity, lightweight obvious new features, and solid mobile behavior.

---

## 1. Context

The practices admin surface was recently migrated off a generic Tabulator table to a bespoke,
purpose-built UI (list + calendar + detail-page + preview-drawer). That migration is the
**reference implementation** for this program. We are applying its *philosophy* — not its
calendar solution — to the rest of the admin panel.

The end state, **per surface**, matches what practices achieved:
- Fully off Tabulator
- Drastically improved, context-tailored UX
- Lightweight obvious new features added (silly ones deliberately dropped)
- Works well on mobile

### 1.1 Reference material

The patterns below were extracted from the practices admin code. Each surface workflow should
read these as the canonical example:

- Routes / data flow: `app/routes/admin_practices.py`
- Bespoke views: `app/templates/admin/practices/{list,calendar,detail,config}.html`
- Editor JS / pill controls: `app/static/practice_editor.js`
- List + drawer JS: `app/static/admin_practices.js`
- Embedded form/context scripts: `app/templates/admin/practices/_detail_script.js`,
  `_detail_context.js`
- Shared infra already in place: `app/static/js/toast.js`, `app/templates/admin/admin_base.html`

---

## 2. Tabulator Inventory (grounding)

Tabulator is loaded globally in `app/templates/admin/admin_base.html` (CDN v5.5.2,
CSS line 8, JS line 99). It is instantiated across **13 grids on 9 pages**:

| # | Surface | Page / JS | Data endpoint | Notable features |
|---|---------|-----------|---------------|------------------|
| 1 | Members | `users.html` / `admin_users.js` | `/admin/users/data` | Frozen cols, role-emoji filter grid, CSV export, quick-edit modal, tag-assign modal, detail link |
| 2 | Payments | `payments.html` / `admin_payments.js` | `/admin/payments/data` | Row-select, bulk capture/refund, per-row accept/refund, CSV, money formatting |
| 3 | Trips | `trips.html` / `admin_trips.js` | `/admin/trips/data` | Status pills, edit→form page, delete |
| 4 | Social Events | `social_events.html` / `admin_social_events.js` | `/admin/social-events/data` | Mirror of Trips |
| 5 | Seasons | `seasons.html` / `admin_seasons.js` | `/admin/seasons/data` | Per-row activate / late-link / export / delete |
| 6 | Roles/Tags | `roles.html` (inline JS) | `/admin/tags/data` | Fully inline-edited cells, auto-save |
| 7 | Practices: locations | `practices/config.html` (inline JS) | `/admin/practices/locations/data` | Inline-edit CRUD |
| 8 | Practices: activities | `practices/config.html` (inline JS) | `/admin/practices/activities/data` | Inline-edit CRUD |
| 9 | Practices: types | `practices/config.html` (inline JS) | `/admin/practices/types/data` | Inline-edit CRUD |
| 10 | Practices: social-locations | `practices/config.html` (inline JS) | `/admin/practices/social-locations/data` | Inline-edit CRUD |
| 11 | Slack: DB users | `slack_sync.html` / `admin_slack.js` | `/admin/slack/users` | Matched/unmatched filter, link/unlink/delete |
| 12 | Slack: Slack-only | `slack_sync.html` / `admin_slack.js` | `/admin/slack/unmatched` | Import, link modal |
| 13 | Skipper | `skipper.html` (inline JS) | `/admin/skipper/data` | Read-only decisions log |

Every surface hand-rolls its own filter bar (search input + status/type `<select>` + `.admin-pill`
toggles). There is no shared filter partial. Editing is inconsistent: modals (Members, Slack),
dedicated form pages (Trips/Events/Seasons), inline cells (Roles, Practices config).

Full per-surface endpoint and mutation detail is preserved in the inventory section of each
workflow charter (Section 6).

---

## 3. The Migration Canon

Non-negotiable principles every surface workflow inherits (extracted from the practices reference):

1. **Server renders an empty shell; the client fetches read-only JSON and renders.** Reuse the
   existing `/<surface>/data` endpoints as-is. Mutations POST and return `{success, message, error}`.
   No server-embedded table data.
2. **Tailored-first; table only when the data is truly tabular.** A surface may remain table-shaped,
   but must be a purpose-built view for *that* object — never a generic grid.
3. **Edit experience fits the object:** dedicated edit *page* with a context rail for anything
   non-trivial; modal only for genuinely small forms; inline-cell only for dense reference data.
   No one-size rule.
4. **List → focus-trapped preview drawer** for quick-look without navigation, where it earns its keep.
5. **Consistency primitives are shared; chrome is bespoke.** Status badge = color + dot + text;
   pill selectors read `.selected` at submit; sticky save bar; 767px breakpoint with drawer→sheet;
   `:focus-visible` rings on all interactive elements.
6. **Scoped `<style>` per view + Tailwind tokens** (`tcsc-navy`, `rounded-tcsc`, `tcsc-gray-*`).
   No global CSS leakage; prefix JS helpers per surface.
7. **Feature parity is a hard gate; new features are additive.** Each charter carries a parity
   checklist of existing behaviors that must survive. Obvious wins get added; anything silly gets
   dropped on purpose and noted.
8. **Mobile is a first-class target — verified, not assumed.**

---

## 4. Shared Foundation (WF-0, built and frozen first)

A deliberately **thin** set of primitives — consistency, not a framework. Built once, committed,
then treated as read-only by every surface workflow. Lives under `app/static/js/admin/` plus a
scoped CSS partial.

| Primitive | Replaces | Notes |
|-----------|----------|-------|
| **Filter bar** (`adminFilterBar`) | The 9 hand-rolled search+select+pill bars | Declarative config: search field, select filters, pill toggle-groups; emits a filter-state object. Biggest dedupe win. |
| **Status badge** (`statusBadge`) | Scattered badge markup | color + dot + text, a11y-correct; one source of state→style mapping |
| **Preview drawer** (`adminDrawer`) | (new capability) | Right-side, inert scrim, focus-trap, restore-focus, lazy content loader; →full-height sheet on mobile |
| **Pill / multi-select** (`adminPills`) | Members role-emoji grid, future M2M editors | `.selected`-at-submit pattern from practices |
| **Focus-trap + inert util** | Repeated modal code | Shared by drawer and modals |
| **Data layer** (`adminFetch` / `renderRows`) | Per-file fetch boilerplate | Tiny: GET JSON, POST mutation with toast + error handling. Not a grid engine. |
| **Sticky save bar** CSS | Per-template copies | From practices `detail.html` |

Reuse as-is: `js/toast.js`, `admin_base.html` shell, Tailwind tokens.

**Validation:** the foundation is exercised against the Members surface markup as its smoke test
during WF-0 (Members being the richest consumer), but Members' full migration is its own parallel
workflow — it does **not** gate the others. The foundation is considered done when its primitives
are committed and demonstrably render against real `/admin/users/data` and `/admin/payments/data`
shapes.

---

## 5. Workflow Map & Sequencing

13 grids collapse into **8 surface workflows**, plus the foundation and the endgame.

| Workflow | Grid(s) | Grouping rationale |
|----------|---------|--------------------|
| WF-0 Foundation | — | Phase 0 primitives; built + frozen first |
| WF-1 Members | Members | Richest surface; foundation's smoke-test consumer |
| WF-2 Payments | Payments | Money + bulk ops; high stakes |
| WF-3 Events | Trips + Social Events | Mirror surfaces; same components, two pages |
| WF-4 Seasons | Seasons | Lifecycle actions (activate, late-link) |
| WF-5 Roles | Roles/Tags | Inline-edit reference data |
| WF-6 Practices config | locations, activities, types, social-locations | 4 reference tables, one page, one cycle |
| WF-7 Slack Sync | DB-users + Slack-only | A matching workflow, not two tables |
| WF-8 Skipper | Decisions log | Read-only; trivial |
| WF-9 Endgame | — | Remove CDN, purge `.tabulator-*`, grep-verify, smoke-test |

### 5.1 Execution model — maximum parallelism

```
WF-0 Foundation (build + freeze + commit)
        │
        ▼  ── all 8 launch in parallel, each in its own git worktree ──
  WF-1 Members · WF-2 Payments · WF-3 Events · WF-4 Seasons
  WF-5 Roles · WF-6 Practices config · WF-7 Slack Sync · WF-8 Skipper
        │
        ▼  (hard-gated on all 8 complete)
  WF-9 Endgame
```

- **WF-0 is the only sequential prerequisite.** It is small and low-risk (the patterns are already
  validated in production by the practices UI), so it is built, committed, and frozen up front.
- **All 8 surface workflows then run in parallel**, each in its **own git worktree**, each running
  its **own full `/brainstorming` → spec → `/writing-plans` → implement cycle** in isolation.
- **Conflict-freedom:** surfaces share only (a) the frozen foundation — read-only to them — and
  (b) `admin_base.html`, which is touched **only** at the endgame. Each surface otherwise owns a
  disjoint set of files (its own template + JS). No two parallel workflows write the same file.
- **Foundation gaps** discovered mid-flight are **reported back, not patched in place**, so parallel
  workflows never race on shared code. If a gap is real, WF-0 is amended and the foundation re-frozen.
- **WF-9 Endgame** is hard-gated: it runs only after all 8 surfaces are migrated and verified.

---

## 6. Per-Surface Charters

Each charter is the seed for that surface's isolated `/brainstorming` cycle. Format:
**Parity (must-keep)** → **UX hypothesis (tailored shape)** → **Feature seeds (lightweight adds)** →
**Edit approach** → **Isolation**.

### WF-1 Members
- **Parity:** `/admin/users/data`; status + season-status + role-emoji filters; search; CSV export
  (`tcsc_members.csv`); quick-edit modal fields; category-grouped tag-assign modal
  (`POST /admin/users/{id}/tags`); link to `/admin/users/{id}`; frozen Name/Roles/Edit columns.
- **UX hypothesis:** roster view — name + roles + status forward; the other ~15 columns move into a
  preview drawer instead of frozen/horizontal-scroll.
- **Feature seeds:** saved filter chips ("Active members", "Unlinked Slack"); **bulk** tag-assign
  (extend the single-user modal to multi-select); copy-email.
- **Edit:** quick-edit stays a modal (small); full profile via drawer or detail page.
- **Isolation:** owns `users.html`, `admin_users.js`.

### WF-2 Payments
- **Parity:** `/admin/payments/data`; row-select; bulk capture/refund with confirm modal
  (`/admin/payments/bulk-capture`, `/bulk-refund`); per-row accept/refund
  (`/admin/payments/{id}/capture`, `/refund`); type + status filters; search; CSV export; money
  formatting.
- **UX hypothesis:** finance worktable grouped by status (Pending-auth / Captured / Refunded) with a
  persistent bulk-action bar.
- **Feature seeds:** **live $ sum of selected rows**; "capturable only" filter; per-trip/season rollup.
- **Edit:** no record edit; capture/refund are the mutations — keep the confirmation modal, show the
  `$` impact.
- **Isolation:** owns `payments.html`, `admin_payments.js`.

### WF-3 Events (Trips + Social Events)
- **Parity:** `/admin/trips/data` + `/admin/social-events/data`; status pills; edit→form page; delete
  confirm (`/admin/trips/{id}/delete`, `/admin/social-events/{id}/delete`); name link;
  price/capacity/dates.
- **UX hypothesis:** date-forward event cards grouped upcoming/past with a capacity-fill bar; two
  distinct pages sharing the same components.
- **Feature seeds:** capacity-fill indicator; registration count at a glance; duplicate-event action.
- **Edit:** keep existing dedicated form pages (`/edit`).
- **Isolation:** owns `trips.html`, `admin_trips.js`, `social_events.html`, `admin_social_events.js`.

### WF-4 Seasons
- **Parity:** `/admin/seasons/data`; current badge; activate (confirm, `/admin/seasons/{id}/activate`);
  late-link (`/admin/seasons/{id}/late-link`); export; delete (`/admin/seasons/{id}/delete-json`);
  reg windows / price / limit.
- **UX hypothesis:** vertical lifecycle timeline; current season highlighted; reg windows shown as
  date ranges.
- **Feature seeds:** replace the `window.prompt` late-link with a proper copy-link modal; reg-window
  open/closed/upcoming badges; member count per season.
- **Edit:** keep existing dedicated form page.
- **Isolation:** owns `seasons.html`, `admin_seasons.js`.

### WF-5 Roles
- **Parity:** `/admin/tags/data`; inline-edit emoji/name/display_name/gradient; user count;
  delete-if-zero-users; create (`/admin/tags/create`, `/admin/tags/{id}/edit`, `/admin/tags/{id}/delete`).
- **UX hypothesis:** roles editor with **live badge preview** (gradient + emoji rendered as it will
  appear in the UI).
- **Feature seeds:** gradient picker; "members with this role" drawer.
- **Edit:** inline fields or small per-role modal (not Tabulator cells).
- **Isolation:** owns `roles.html` (replace inline JS).

### WF-6 Practices config
- **Parity:** inline-edit + add/delete across all 4 tables; per-table fields (location spot/coaches,
  social map_link); endpoints `/admin/practices/{locations,activities,types,social-locations}/...`.
- **UX hypothesis:** tabbed config panel; each entity a simple bespoke editable list; deliberately
  kept lightweight (this surface does not need to be fancy).
- **Feature seeds:** location mini-map (lat/lon already stored); activity `gear_required` editor.
- **Edit:** inline / small modal.
- **Isolation:** owns `practices/config.html` (replace inline JS). Must **not** touch other practices
  views (list/calendar/detail are already migrated).

### WF-7 Slack Sync
- **Parity:** `/admin/slack/users` + `/admin/slack/unmatched`; matched/unmatched filters;
  link/unlink/delete (`/admin/slack/link`, `/unlink`, `/delete-user`); import (`/admin/slack/import`);
  sync + sync-profiles triggers; link modal.
- **UX hypothesis:** reconciliation workspace — DB users ↔ Slack users with suggested matches, link
  inline; design around the matching job, not two grids.
- **Feature seeds:** surface email-based suggested matches; bulk-import unmatched; sync-status banner.
- **Edit:** replace the link modal with an inline link picker.
- **Isolation:** owns `slack_sync.html`, `admin_slack.js`.

### WF-8 Skipper
- **Parity:** `/admin/skipper/data` read-only decisions log with status badges. (Pending-proposal
  approve/reject cards already live outside the table — leave them.)
- **UX hypothesis:** chronological decision feed / timeline.
- **Feature seeds:** filter by status/date; link to the practice; surface the weather snapshot from
  `evaluation_data`.
- **Edit:** none (read-only).
- **Isolation:** owns `skipper.html` (replace inline JS).

---

## 7. WF-9 Endgame (hard-gated on all 8 surfaces)

1. Confirm zero `new Tabulator(` references remain (grep across `app/static` and `app/templates`).
2. Remove the Tabulator CDN includes from `admin_base.html` (CSS line 8, JS line 99).
3. Purge `.tabulator-*` CSS classes and any `tabulator-data` / `tabulator-config` container classes.
4. Grep-verify no remaining `tabulator` references anywhere.
5. Smoke-test every admin page (desktop + mobile viewport).

---

## 8. Dynamic Workflow Launch — Charter Template

Each surface launches in its own isolated session/worktree, seeded with this template:

```
You are migrating the <SURFACE> admin surface off Tabulator in the tcsc-trips Flask app,
working in an isolated git worktree.

Reference (read first):
- Migration canon: docs/superpowers/specs/2026-06-04-tabulator-migration-design.md (Section 3)
- Practices reference implementation: app/templates/admin/practices/*, app/static/practice_editor.js,
  app/static/admin_practices.js
- Shared foundation (frozen, read-only to you): app/static/js/admin/*

Your charter (from Section 6 of the design doc):
  Parity (must-keep): <...>
  UX hypothesis: <...>
  Feature seeds: <...>
  Edit approach: <...>
  Files you own (touch only these): <...>

Run your own full cycle: /brainstorming -> spec -> /writing-plans -> implement -> verify.

Rules:
- Honor the migration canon (Section 3). Reuse the shared foundation; do NOT modify it — if you
  find a gap, report it back rather than patching shared code.
- Do NOT touch any other surface's files or admin_base.html.
- Not done until: parity verified against the checklist, lightweight feature seeds landed
  (drop any that prove silly, and say so), mobile checked at the 767px breakpoint.
```

---

## 9. Risks & Mitigations

- **Foundation gaps surface during parallel work.** Mitigation: report-back protocol (Section 5.1);
  WF-0 amended and re-frozen rather than patched ad hoc by a surface workflow.
- **Parallel worktrees diverge from `main`.** Mitigation: disjoint file ownership keeps merges
  clean; only `admin_base.html` is shared and it is touched solely at the endgame.
- **Parity regressions.** Mitigation: per-surface parity checklist is a hard completion gate;
  verify against the live `/data` endpoints.
- **Inconsistent UX despite bespoke goal.** Mitigation: shared consistency primitives (badges,
  filter bar, drawer) keep the panel coherent even as each surface is tailored.

---

## 10. Out of Scope

- Backend `/data` endpoint changes beyond what a surface genuinely needs (reuse existing shapes).
- The practices list/calendar/detail views (already migrated).
- Non-Tabulator admin pages.
- Newsletter/dispatch admin surfaces (no Tabulator grids found there).
