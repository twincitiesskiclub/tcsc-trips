# Tabulator Migration — Review Feedback (2026-06-07)

Captured during live walkthrough of `feat/tabulator-migration` on local dev. Input for an
upcoming `/brainstorming` pass. **No code changed yet.** Object-editing menus/pages are being
left as-is for now (see Deferred), to be cleaned up in a once-off pass later.

---

## Per-surface feedback

### Members (`users.html` / `admin_users.js`)
- Two status indicators (overall **Member status** vs per-**Season status**) sit in separate
  row columns, unlabeled — not obvious what each means.
  - **Decision:** grouped status cell — Member status as the primary badge, Season status as a
    muted sub-line prefixed with the season name (e.g. `2025-26 · Lottery`, or `Not registered`).
- Export CSV placement is awkward.
  - **Decision:** keep it at the bottom but restyle as a quiet utility action.
- Overall: looks good.

### Payments (`payments.html` / `admin_payments.js`)
- "Capturable only" filter control is much smaller than the other filters — size mismatch.
- Export CSV placed oddly — **unify CSV placement across the whole admin UI.**
- Clicking a transaction opens a slide-out for metadata that is **completely unstyled** — looks
  out of place; should match how we render detail drawers elsewhere.

### Roles (`roles.html`)
- Overall layout feels cluttered; structure could be organized more logically.

### Seasons (`seasons.html` / `admin_seasons.js`)
- Season-info slide-out drawer is **unformatted**.
- Edit dialog still leads to the **old editing menu** (deferred — OK for now).

### Trips (`trips.html` / `admin_trips.js`)
- Slide-out drawer **unformatted** again.
- Edit page not updated to the new structure; doesn't look great (deferred — OK for now).

### Social Events (`social_events.html` / `admin_social_events.js`)
- Same as Trips: unformatted drawer + old edit page (deferred).

### Slack Sync (`slack_sync.html` / `admin_slack.js`)
- Formatting badly off: spacing around the buttons is wrong.
- The white container box is way too cramped.
- User rows are too big — hard to scan everyone at once.

### Practices config (`practices/config.html`)
- _Not yet reviewed._

### Skipper (`skipper.html`)
- _Not yet reviewed._

---

## Cross-cutting themes (likely shared root causes — key for brainstorming)

1. **Unformatted preview/slide-out drawers** recur on Payments, Seasons, Trips, Social Events.
   Strong signal of a single shared cause (drawer body content rendered without surface CSS, or a
   missing shared drawer-content convention in the frozen `AdminUI` foundation). Fix the pattern
   once, apply everywhere — don't patch four times.
2. **Export CSV placement is inconsistent** (Users bottom-footer; Payments odd). Want **one unified
   placement/treatment** for CSV export across all surfaces.
3. **Filter-control sizing is inconsistent** (Payments "capturable only" smaller than siblings;
   Members status pills felt off). Filters within a toolbar should share one size/shape.
4. **Density / container sizing** (Slack Sync rows too big, container too cramped). Check row
   density and container padding conventions are consistent across surfaces.

---

## Deferred (explicit — leave for a later once-off pass)
- All object **edit menus / edit pages** stay as the existing old forms for now: Seasons edit
  dialog, Trips edit page, Social Events edit page. Clean these up together later.
