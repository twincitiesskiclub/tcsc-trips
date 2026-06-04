# Practice List Redesign — Design

**Date:** 2026-06-04
**Status:** Approved (pending spec review) — revised after a 5-agent / 3-judge adversarial design review
**Visual references** (saved under `.superpowers/brainstorm/`, gitignored):
- `hero-preview.html` — approved list + open preview drawer
- `agenda-hybrid.html` — approved row layout (Option 1: date-block, day-grouped)
- **TODO before build:** an approved **375px (one-column) row frame** — the row's narrow-width reflow is the load-bearing responsive unknown and must be drawn, not asserted.

## Problem

The practice list page (`app/templates/admin/practices/list.html` + `app/static/admin_practices.js`) is still the original **Tabulator.js data grid**: ~12 columns wide, a frozen Actions column, inline Edit/Cancel/Delete buttons. It is desktop-only (horizontal scroll on a phone) and visually out of step with the newly refactored **full-page workout editor** (`detail.html`), which established a polished "Quiet Precision" design language (scoped tokens, cards, compact pills, status badges, focus rings, accessible toggles).

There is no way to preview a practice's details without navigating into the full editor.

## Goal

Replace the grid with an **on-brand, mobile-friendly list** plus a **click-to-preview slide-over drawer**, matching the editor's look and feel. Two user jobs drive the design:

1. **Daily driver** — see today's and upcoming practices front and center, with rich scannable metadata.
2. **Occasional lookup** — find what we did in the past.

Make job 1 effortless; keep job 2 one click (one scroll) away without cluttering the default view.

## Decisions

### Form factor — custom list + slide-over drawer (everywhere)
Drop Tabulator. Render a custom list. Clicking a row opens a **preview drawer that slides over from the right** on desktop and becomes a **full-height sheet** on mobile — one panel behavior to build and test for every screen size.

### List organization — single scroll, Past render-gated *(revised: was tabs)*
A single scrolling view, no tabs:
- **Today / This week / Later** sections at the top (the daily driver), ascending. Real `<h2>` section **headings with honest counts** (e.g. "This week · 3").
- A **collapsed "Past practices (N)" section** at the bottom, reverse-chronological, expanded on demand. The Past render is **gated** — paint only a recent window initially (e.g. current season / last ~20) with load-more — so expanding never dumps ~140 cards at once. (Chosen over tabs to drop tab/ARIA state and simplify mobile; ~140 rows does not justify a backend windowed endpoint — gating the render is enough.)

### Grouping boundaries — date-based, Chicago, rolling 7 days *(new)*
Bucket by **calendar date in America/Chicago**, not by datetime, so an evening practice today is still "Today." **This week** = the rolling next 7 days after today; **Later** = beyond that; **Past** = before today.

### Row layout — date-block, day-grouped (the "Option 1" hybrid)
- One **bold date block** (day-of-week / day-number / month) shown **once per day**; multiple same-day practices stack to its right.
- Each row shows: **location** (headline) · **time** · **activity & type pills** · **social / dark indicators (icon + text, not emoji alone)** · **staffing chip** · **status badge**.
- **Staffing chip** *(revised: was a labeled Coach + Leads name line)*: collapse coach/lead state to a single low-emphasis chip — `✓ 3/3` when staffed, an **amber "needs leads"** flag when empty. The actionable signal is *understaffed*; full names live in the drawer. (A fuller labeled coach/lead line may appear at the wide breakpoint only; it must not be the narrow-row default, where two name-lists wrap badly.)
- **Today** rows are tinted and carry a "Today" flag.
- **Assists are not on the row** — they live in the drawer.
- **The row is a single focusable `<button>`** (or `role="button"` with full keyboard handling), **not** a `div` + `onclick` — the click target must be keyboard-operable.

### Preview drawer — "preview + quick actions"
Read-only details with action buttons pinned at the bottom (no form editing — the full editor remains the single place to edit). The drawer is a **thin synchronous preview**, not a re-implementation of the editor's context rail; lift token values verbatim now and extract shared atoms as a fast-follow rather than reopening the just-stabilized editor.

- **Header:** location, date/time, close ✕ (≥44px hit area), and a badge row (status · Skipper GO/NO-GO · dark-practice).
- **Body (read-only, scrollable):**
  - **When & Where** — date/time, location, post-practice social
  - **Activity & Type** — pills
  - **Workout Plan** — warmup / main / cooldown (main is the visual anchor)
  - **Coaches · Leads · Assists** — per-person rows with confirmed/pending state
  - **RSVPs** — going / maybe / not-going count strip
- **Action bar (pinned bottom):** **Edit in full editor** (primary → `/admin/practices/<id>`) · **Cancel** · **Delete**.
- **Data loading:** render the read-only sections **instantly** from the already-loaded list payload. **RSVP counts** auto-load on open via `GET /admin/practices/<id>/rsvps` (mirrors the editor). **Skipper GO/NO-GO does NOT auto-fetch** *(revised)* — it hits ~5 uncached external integrations, so it sits behind a **manual "Load evaluation" button gated to today/tomorrow**, exactly as the editor does. The earlier "lazy-fetch Skipper on open" claim was wrong and is removed.

### Visual direction — adopt the editor's *real* tokens (unify the fork) *(revised)*
The earlier draft claimed "reuse the exact tokens" but actually codified the mockup's **drifted** values. Use the editor's real values:
- Base: navy `#1c2c44`, page bg `#f8fafb`, card `#fff`, border `#e5e7eb`, text secondary `#475569` / muted `#64748b` / faint `#94a3b8`; radii card 12px, input 10px, pill 20px.
- **Status badge — all five states** *(the earlier mockup styled only 3; the Past section needs `completed`/`cancelled` or it cannot render its dominant rows)*:
  - `scheduled` → `#dbeafe` / `#1e40af`
  - `confirmed` → `#dcfce7` / `#166534`
  - `in_progress` → `#fefce8` / `#854d0e`
  - `completed` → `#f1f5f9` / `#64748b`
  - `cancelled` → `#fde8e8` / `#c53030`
- **Skipper** (match the editor exactly): GO `#acf3c4` / `#166534`; NO-GO `#fde8e8` / `#c53030`.
- **Functional text must not use the faint `#94a3b8`** — it fails contrast for real content (e.g. the "Tue" day label); use `#64748b` for functional labels and reserve `#94a3b8` for truly decorative text.
- Scoped CSS in the template's `extra_css` block, mirroring the editor's approach.

### Accessibility (required, not optional) *(expanded)*
- **Status never rides on color alone** — every status/Skipper badge pairs a color cue with a text label; decorative dots are `aria-hidden`.
- **Row** — a real focusable button with a 2px navy (`#1c2c44`) focus ring; activates on Enter/Space.
- **Drawer is a modal dialog** — `role="dialog"` + `aria-modal`, labelled by its heading; **focus trap** while open; **closes on Esc**; **restores focus to the triggering row** on close; on mobile, the underlying list is `inert`/hidden from AT so it doesn't bleed through the sheet.
- **Announce lazy content** — the RSVP/Skipper slots are `aria-live="polite"` so a verdict appearing after a fetch (especially the safety-relevant Skipper result) is announced rather than popping in silently.
- **Reduced motion** — a `prefers-reduced-motion` guard disables/space-collapses the slide animation.
- **Touch targets** — comfortable on mobile (~44px where practical), including the drawer ✕.
- **Labels** — every filter/control has an associated label.

### Search & filters *(carried over, one extension)*
Keep the search box plus status + location filters. **Search also matches coach/lead/assist names** (the payload already carries them; the old grid never searched people). Calendar View and + New Practice actions carry over.

## Data flow

The existing **`GET /admin/practices/data`** already returns, per practice: `id`, `date`, `day_of_week`, `location_name`, `location_id`, `social_location_id`, `social_location_name`, `activities[]`, `practice_types[]`, `status`, `has_social`, `is_dark_practice`, `leads[]` / `coaches[]` / `assists[]` (each with `name` + `confirmed`), `cancellation_reason`, and `warmup_description` / `workout_description` / `cooldown_description`.

This covers the entire list **and** the drawer's read-only body. On drawer open the page additionally:
- auto-loads **RSVP counts** via the existing `GET /admin/practices/<id>/rsvps`, and
- loads **Skipper GO/NO-GO** via the existing `GET /admin/practices/<id>/evaluation` **only when the user presses the gated button** (today/tomorrow).

**No backend changes are required.** No change to any POST endpoint or the data model. (A street address for a drawer location hint is **not** in the payload — show a short existing descriptor or omit the hint line; do not add a backend field for it.)

## Affected files

| File | Change |
|------|--------|
| `app/templates/admin/practices/list.html` | Rebuilt: toolbar (people-aware search + status + location filters, Calendar + New Practice), single-scroll sections with real headings + counts, a render-gated Past section, an empty list container, and the preview-drawer markup as a `role="dialog"` (hidden until a row is clicked). Scoped "Quiet Precision" CSS in `extra_css` using the unified tokens + all five status states. Existing **cancel modal** markup stays. |
| `app/static/admin_practices.js` | Rewritten rendering: fetch `/admin/practices/data` once → bucket by Chicago date (Today / This week / Later / Past) → group by day → render date-block rows as buttons with the staffing chip. Handlers for search/filters, Past expand + render-gate, row activation (open dialog, populate from cached row, auto-load RSVP, **gated** Skipper button), focus trap / Esc / focus restore, and drawer Edit/Cancel/Delete. **Keep** the cancel modal flow, `deletePractice`, and the data/location loaders. **Remove** all Tabulator init/column/grid code. |

No changes to `admin_practices.py` routes, the calendar, the editor (`detail.html`), or the sidebar. *(Optional fast-follow, not a shipping precondition: extract the shared badge / GO chip / RSVP strip / person-row atoms into a layer reused by both the editor and this page.)*

## Scope boundaries (out of scope)

- Inline editing inside the drawer (the full editor stays the single edit surface).
- Bulk actions / multi-select.
- Any change to the workout editor page, the calendar, POST endpoints, or the data model.
- New workout features (copy-from-previous, live Slack preview, templates, rich text).
- **Rejected by the review panel:** a Past-tab "reporting console" / extra filter state; J/K keyboard power-nav + roving tabindex; a date-windowed Past backend endpoint (gate the render instead).

## Optional (not required to ship)

- Replace the drawer's location address hint with a short descriptor, or delete the line.
- Separate the **Delete** button's red from the **NO-GO** red so the same red isn't doing triple duty.
- Sequence as two PRs (list first, accessible drawer second); a single disciplined PR is also acceptable.

## Verification

Practices admin routes are not covered by automated tests. Verify by running the app:

- **Sections & grouping** — Today / This week / Later show ascending with correct counts; date-based Chicago bucketing keeps evening "today" practices in Today; a multi-practice day groups under one date block; the Past section is collapsed by default and render-gated when expanded.
- **Row content** — location, time, pills, social/dark (icon + text), staffing chip (`3/3` vs amber "needs leads"), and the correct status badge for **all five** statuses render correctly.
- **Filters** — search (location/activity/type **and people names**), status filter, and location filter narrow the visible rows.
- **Drawer** — row-click opens the dialog; read-only sections populate instantly; RSVP counts auto-load; the Skipper button appears only for today/tomorrow and loads on press (never auto); Edit navigates to `/admin/practices/<id>`; Cancel opens the existing cancel flow; Delete removes the practice.
- **Responsive** — exercise on a wide viewport and ~375px mobile against the approved row frame; list is single-column and tappable; drawer is a full-height sheet on mobile.
- **Accessibility** — keyboard-only: rows are buttons, focus is visible, the drawer traps focus, closes on Esc, and restores focus to the triggering row; lazy RSVP/Skipper results are announced via `aria-live`; reduced-motion disables the slide; status badges pair color with a label; badge/pill contrast and the unified Skipper colors hold.
