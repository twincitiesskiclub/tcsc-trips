# Practice List Redesign — Design

**Date:** 2026-06-04
**Status:** Approved (pending spec review)
**Visual references** (saved under `.superpowers/brainstorm/`, gitignored):
- `hero-preview.html` — approved list + open preview drawer
- `agenda-hybrid.html` — approved row layout (Option 1: date-block, day-grouped)

## Problem

The practice list page (`app/templates/admin/practices/list.html` + `app/static/admin_practices.js`) is still the original **Tabulator.js data grid**: ~12 columns wide, a frozen Actions column, inline Edit/Cancel/Delete buttons. It is desktop-only (horizontal scroll on a phone) and visually out of step with the newly refactored **full-page workout editor** (`detail.html`), which established a polished "Quiet Precision" design language (scoped tokens, cards, compact pills, status badges, focus rings, accessible toggles).

There is no way to preview a practice's details without navigating into the full editor.

## Goal

Replace the grid with an **on-brand, mobile-friendly list** plus a **click-to-preview slide-over drawer**, matching the editor's look and feel. Two user jobs drive the design:

1. **Daily driver** — see today's and upcoming practices front and center, with rich scannable metadata.
2. **Occasional lookup** — find what we did in the past.

Make job 1 effortless; keep job 2 one click away without cluttering the default view.

## Decisions

### Form factor — custom list + slide-over drawer (everywhere)
Drop Tabulator. Render a custom list. Clicking a row opens a **preview drawer that slides over from the right** on desktop and becomes a **full-height sheet** on mobile — one panel behavior to build and test for every screen size. (Chosen over keeping the grid, and over a persistent split-pane that would need a separate mobile behavior anyway.)

### List organization — Upcoming / Past tabs
- **Upcoming** (default tab): rows grouped under **Today / This week / Later**, ascending (soonest first). The default view never shows stale practices.
- **Past** tab: reverse-chronological, where search + filters do the lookup work.

### Row layout — date-block, day-grouped (the "Option 1" hybrid)
- One **bold date block** (day-of-week / day-number / month) shown **once per day**; multiple same-day practices stack to its right.
- Each row shows: **location** (headline) · **time** · **activity & type pills** · **social 🍺 / dark 🔦 icons** · **Coach + Leads** (small uppercase labels, ✓ = confirmed, "unassigned"/"none" when empty) · **status badge**.
- **Today** rows are tinted and carry a "Today" flag.
- **Assists are not shown on the row** — they live in the preview drawer to avoid crowding.

### Preview drawer — "preview + quick actions"
Read-only details with action buttons pinned at the bottom (no form editing — the full editor remains the single place to edit).

- **Header:** location, date/time, close ✕, and a badge row (status · Skipper GO/NO-GO · dark-practice).
- **Body (read-only, scrollable):**
  - **When & Where** — date/time, location (+ address hint), post-practice social
  - **Activity & Type** — pills
  - **Workout Plan** — warmup / main / cooldown (main is the visual anchor)
  - **Coaches · Leads · Assists** — per-person rows with confirmed/pending state
  - **RSVPs** — going / maybe / not-going count strip
- **Action bar (pinned bottom):** **Edit in full editor** (primary → `/admin/practices/<id>`) · **Cancel** · **Delete**.
- The drawer renders **instantly** from the already-loaded list payload, then **lazy-fetches** RSVP counts and Skipper evaluation on open (same pattern the editor uses).

### Visual direction — adopt the editor's "Quiet Precision" system
Reuse the exact tokens and component patterns established in `detail.html`: navy `#1c2c44`, page bg `#f8fafb`, card `#fff`, border `#e5e7eb`, text secondary `#475569` / muted `#64748b` / faint `#94a3b8`; radii card 12px, input 10px, pill 20px; status colors success `#dcfce7`/`#166534`, info `#dbeafe`/`#1e40af`, closed `#f1f5f9`/`#64748b`, danger `#fee2e2`/`#b91c1c`; GO badge `#166534` on `#dcfce7`. Scoped CSS in the template's `extra_css` block, mirroring the editor's approach.

### Accessibility (required, not optional)
- **Status never rides on color alone** — every status badge pairs a color cue with a text label; decorative dots are `aria-hidden`.
- **Focus visibility** — a perceivable 2px navy (`#1c2c44`) focus ring on every interactive element (rows, tabs, drawer controls, buttons).
- **Keyboard** — rows are keyboard-activatable; the drawer traps focus while open, **closes on Esc**, and returns focus to the triggering row on close.
- **Touch targets** — comfortable on mobile (~44px where practical).
- **Labels** — every filter/control has an associated label.

## Data flow

The existing **`GET /admin/practices/data`** already returns, per practice: `id`, `date`, `day_of_week`, `location_name`, `location_id`, `social_location_id`, `social_location_name`, `activities[]`, `practice_types[]`, `status`, `has_social`, `is_dark_practice`, `leads[]` / `coaches[]` / `assists[]` (each with `name` + `confirmed`), `cancellation_reason`, and `warmup_description` / `workout_description` / `cooldown_description`.

This covers the entire list **and** most of the drawer. The drawer additionally lazy-fetches:
- **RSVP counts** via the existing `GET /admin/practices/<id>/rsvps`
- **Skipper GO/NO-GO** via the existing `GET /admin/practices/<id>/evaluation`

**No backend changes are required for the core.** Location street address for the drawer's "weather-check point" hint is a nice-to-have; include it only if it is already present on the payload or trivially added — otherwise omit the hint. No change to any POST endpoint or the data model.

## Affected files

| File | Change |
|------|--------|
| `app/templates/admin/practices/list.html` | Rebuilt: toolbar (search + status + location filters, Calendar + New Practice), Upcoming/Past tab bar, empty list container, and the preview-drawer markup (hidden until a row is clicked). Scoped "Quiet Precision" CSS in `extra_css`. Existing **cancel modal** markup stays. |
| `app/static/admin_practices.js` | Rewritten rendering: fetch `/admin/practices/data` once → split upcoming/past → group by day → render date-block rows. Handlers for tab switch, search/filters, row-click (open drawer, populate from cached row, lazy-fetch RSVP + evaluation), and drawer Edit/Cancel/Delete. **Keep** the cancel modal flow, `deletePractice`, and the data/location loaders. **Remove** all Tabulator init/column/grid code. |

No changes to `admin_practices.py` routes, the calendar, the editor (`detail.html`), or the sidebar.

## Scope boundaries (out of scope)

- Inline editing inside the drawer (the full editor stays the single edit surface).
- Bulk actions / multi-select.
- Any change to the workout editor page, the calendar, POST endpoints, or the data model.
- New workout features (copy-from-previous, live Slack preview, templates, rich text).

## Verification

Practices admin routes are not covered by automated tests. Verify by running the app:

- **Tabs & grouping** — Upcoming shows Today / This week / Later ascending; Past shows reverse-chronological; today is tinted/flagged; a multi-practice day groups under one date block.
- **Row content** — location, time, pills, social/dark icons, coach + leads (with ✓ and unassigned/none states), status badge all render correctly.
- **Filters** — search (location/activity/type), status filter, location filter narrow the visible rows.
- **Drawer** — row-click opens it; read-only sections populate instantly; RSVP counts and Skipper GO/NO-GO lazy-load; Edit navigates to `/admin/practices/<id>`; Cancel opens the existing cancel flow; Delete removes the practice.
- **Responsive** — exercise on a wide viewport and ~375px mobile; list is single-column and tappable; drawer is a full-height sheet on mobile.
- **Accessibility** — keyboard-only navigation with visible focus; drawer closes on Esc and restores focus; status badges pair color with a label; GO badge contrast holds.
