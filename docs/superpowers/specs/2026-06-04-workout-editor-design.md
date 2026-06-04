# Unified Workout Editor — Design

**Date:** 2026-06-04
**Status:** Approved (pending spec review)
**Visual reference:** [`2026-06-04-workout-editor-mockup.html`](./2026-06-04-workout-editor-mockup.html) — open in a browser; this is the approved target look & feel.

## Problem

There are **two separate, inconsistent editors** for the same task — editing a practice/workout:

- **Editor A — full page** (`app/templates/admin/practices/detail.html`, route `practice_detail` at `/admin/practices/<id>`). Plain checkbox controls. The *only* place with Skipper evaluation, RSVPs, and lead-confirmation toggles. Reached from the calendar and by direct URL.
- **Editor B — modal** (inside `app/templates/admin/practices/list.html`, driven by `app/static/admin_practices.js`). Nicer controls (pill selectors, name search, collapsible assists, dark-practice toggle) but cramped in an 800px modal, poor on mobile, and missing all the read-only context. Reached from the grid's Edit / "Create New Practice" buttons.

Both editors POST to the **same two endpoints** (`create_practice`, `edit_practice`), so the backend is already unified — only the front end is duplicated. The duplication causes drift, doubles maintenance, and gives admins an inconsistent experience.

## Goal

One great, consistent, **full-page** workout editor that works well on **mobile and desktop**, combining the best of both editors, with **extreme visual/UX polish** on the existing fields. **No new workout features** (explicitly out of scope: copy-from-previous-practice, live Slack preview, type-based templates, rich-text). Polish and consolidate only.

## Decisions

### Form factor — full page
A single dedicated editor page is the canonical editor. The grid's Edit button, the calendar, and direct URLs all land here. Chosen over a modal/drawer because the editor carries a lot (four form sections **plus** Skipper / RSVP / lead-confirmation context) and a full page is the only form factor that holds all of it comfortably while behaving well on a phone (single scrolling column, native inputs, real headroom). The calendar already links here, minimizing navigation churn.

### Layout
- **Desktop:** two columns. Left = the edit form. Right = read-only context rail (~320px).
- **Mobile:** single stacked column, with a **sticky Save / Cancel bar** pinned to the bottom so the primary action is always reachable.
- **Section order (left form):**
  1. **When & Where** — date & time, location, post-practice social, dark-practice toggle
  2. **Activity & Type** — multi-select pills (activities, practice types)
  3. **Coaches · Leads · Assists** — person selectors with name-search filter; selected people shown as removable chips; **Assists** collapsible
  4. **Workout Plan** — warmup / main workout / cooldown. **The visual anchor** — most polish concentrates here.
- **Context rail (right, edit mode only):**
  - **A. Status & Skipper** — status control + GO/NO-GO badge, confidence, weather summary
  - **B. RSVPs** — going / maybe / not-going counts (segmented strip) + short list
  - **C. Lead Confirmations** — per-person confirmed/pending toggle
- **New Practice** shows only the left form (sections 1–4); **Edit** adds the context rail.

### Controls ported from the modal
Pill selectors (activities/types), name-search filter for people, collapsible assists, and the dark-practice toggle move from the modal into the full page. The interaction logic for these already exists in `admin_practices.js` (modal) and is adapted/relocated for the page rather than rewritten.

### Visual direction — "Quiet Precision," merged
Base is the **Quiet Precision** treatment (strict 8px spacing grid, near-monochrome navy/neutral palette, confident typographic hierarchy, hairline borders, color used only for meaning), with grafts resolved during the design debate:
- From **Trailhead** (warm): per-field **helper microcopy** under load-bearing fields (e.g. Location → "weather check location for Skipper"), the **segmented RSVP count strip**, a real **keyboarded toggle** for dark practice (`<button role="switch" aria-checked>`), and the **labeled, keyboarded collapsible** for assists.
- From **Grid-Lock** (dense): the **restrained context rail** (slim `rail-card` headers, inline GO badge, weather chips, compact 3-column RSVP strip, dense lead rows with role sub-labels), and **focus rings on every interactive element**.

Stakeholder refinements after review:
- **Compact choice pills** — `min-height ~28px`, `padding 4px 10px`, font ~12.5px, 20px radius, 6px gaps. Selected = 2px navy border + subtle navy tint (not a heavy filled block).
- **Restrained sidebar** adopted from Grid-Lock, narrowed to ~320px.

### Accessibility (required, not optional)
The debate's critic flagged accessibility as the main risk; these are firm requirements:
- **Status never rides on color alone** — every status pairs a color cue **with a text label** (WCAG 1.4.1); decorative dots are `aria-hidden`.
- **GO badge** uses AA-contrast colors (`#166534` on `#dcfce7` / `#acf3c4`).
- **Focus visibility** — a perceivable **2px navy (`#1c2c44`) focus ring** on every interactive element (not a faint mint ring).
- **Label association** — every input/control has an associated `<label>`.
- **Touch targets** — comfortable on mobile; inline filter pills may be ~28–30px but tap-friendly.

### Design tokens (existing TCSC system — use exactly)
Navy `#1c2c44`; mint `#acf3c4`; page bg `#f8fafb`; card `#fff`; border `#e5e7eb`; text primary `#1c2c44` / secondary `#475569` / muted `#64748b` / faint `#94a3b8`; radii card 12px, input 10px, pill 20px; status success `#dcfce7`/`#166534`, info `#dbeafe`/`#1e40af`, closed `#f1f5f9`/`#64748b`; warn `#fefce8`/`#fde68a`/`#854d0e`. Implementation uses the app's Tailwind classes / component classes (`btn-primary`, `card`, etc.) where they map cleanly; the mockup's inline CSS is a visual reference, not the implementation method.

## Consolidation & cleanup

- **Grid "Edit"** → navigates to `/admin/practices/<id>` (the full page).
- **Grid "Create New Practice"** → navigates to a new **`GET /admin/practices/new`** route that renders the editor page with `practice=None` (this route does not exist yet and must be added; today "new" only existed as the modal).
- **Calendar** click → already navigates to `/admin/practices/<id>`; unchanged.
- **Delete** the edit/create **modal markup** from `list.html` and the modal-specific JS in `admin_practices.js` (open/populate/save), keeping grid rendering, data loading, the **cancel** modal, delete, and lead toggle-confirm. (Decide during planning whether the cancel modal stays in `list.html` or is unaffected — it is unrelated to the edit modal and can stay.)
- **Sidebar** active-state already checks `admin_practices.practice_detail`; verify it still highlights correctly for the new `/new` route.
- **POST endpoints** `create_practice` / `edit_practice` are unchanged — the page already submits to them.

## Affected files

| File | Change |
|------|--------|
| `app/templates/admin/practices/detail.html` | Rebuilt as the canonical polished editor: two-column layout, pills, person search + collapsible assists, polished Workout Plan, restrained context rail, sticky save bar, accessible toggles. |
| `app/static/admin_practices.js` | Remove edit/create modal logic; repoint grid Edit/Create to navigate to the page; keep grid, data load, cancel, delete, toggle-confirm. Relocate reusable pill/person-search/assists logic to the page (or a shared module). |
| `app/templates/admin/practices/list.html` | Remove edit/create modal markup. Grid Edit/Create become navigations. |
| `app/routes/admin_practices.py` | Add `GET /admin/practices/new` rendering `detail.html` with `practice=None`. Confirm `practice_detail` passes everything the polished template needs (social_locations etc.). |
| `app/templates/admin/practices/calendar.html` | No change expected (already links to the page); verify. |
| `app/templates/admin/partials/sidebar.html` | Verify active-state highlighting for the editor routes. |

## Scope boundaries (out of scope)
Copy-from-previous-practice, live Slack-announcement preview, practice-type templates/prefill, rich-text editing, and any change to the underlying data model or POST payload. Workout fields remain free-text — just polished.

## Verification
Practices admin routes are not currently covered by automated tests. Plan to verify by:
- Running the app and exercising **Create** (`/admin/practices/new`) and **Edit** (`/admin/practices/<id>`) on both a wide viewport and a ~375px mobile viewport.
- Confirming pills, person search, collapsible assists, dark toggle, status, save, and cancel all work; context rail (Skipper / RSVP / lead-confirm) loads and toggles in edit mode.
- A quick accessibility pass: keyboard-only navigation with visible focus, status color+label, contrast of the GO badge and pills.
- A light backend test for the new `GET /admin/practices/new` route (renders 200 with `practice=None`) is reasonable to add given a new route is introduced.
