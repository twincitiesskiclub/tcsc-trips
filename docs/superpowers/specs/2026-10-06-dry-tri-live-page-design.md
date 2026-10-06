# Dry Tri live page

Date: 2026-10-06. Status: approved in conversation, spec pending review.

## Goal

twincitiesskiclub.org/dry-tri still says "Planning for 2026 is underway" and
has no registration link. The 2026 race (Sat Oct 24, Carver Park Reserve) has
been taking registrations on tcsc.ski since July 25. The marketing page should
show the current race and keep up with admin edits to the event without a
deploy.

Two pieces of work, shipped as two PRs in this order:

1. **Event times fix** (tcsc.ski). Event datetimes are stored inconsistently,
   so the public event page shows a 4:00 AM start. Fix first, because the new
   API would otherwise publish the wrong time.
2. **Live Dry Tri page.** A public event API on tcsc.ski and a marketing page
   that reads it.

Decisions Rob made on 2026-10-06:

- The page shows live facts plus a Register button. No entry chooser.
- The race schedule comes from the event description, rendered as written.
- Member prices are not mentioned anywhere on the marketing site.
- The time bug is fixed in its own PR, ahead of the page.

## PR 1: event times are UTC

### The bug

`admin_events.py` saves `event_date`, `signup_start` and `signup_end` exactly
as typed in the `datetime-local` inputs, which admins fill in Central time.
Everything that reads them assumes UTC:

- `events/registration.html` runs `event_date` through `central_time`, which
  converts UTC to Central. A 9:00 AM race shows as 4:00 AM CT.
- `routes/events.py` and `events/service.py` compare the signup window to
  `datetime.utcnow()`. Registration that should close at 11:59 PM Central on
  Oct 22 closes at 6:59 PM Central.

Seasons already do this correctly (`admin.py` `_parse_central_to_utc`). Events
should match.

### Changes

- Move `_parse_central_to_utc` out of `admin.py` into `app/utils.py` as
  `central_naive_to_utc_naive(dt)` (the inverse of the existing
  `utc_naive_to_central_naive`). Seasons and events both call it.
- `admin_events.py`: convert the three parsed values to UTC before saving.
  Signup ordering validation is unchanged (conversion preserves order).
- `admin/event_form.html`: prefill the three inputs with
  `|central_time('%Y-%m-%dT%H:%M')`, as `season_form.html` does.
- `admin_events.py` list JSON: emit `event_date` with a `Z` suffix so
  `admin_events.js` (`new Date(value)`) reads it as UTC and shows the admin's
  local time. Today it has no suffix and is read as local, which only looks
  right because the stored value is Central.
- `index.html` event cards: use `central_time` instead of raw `strftime`.
- `events/seeds.py` stays in Central. The seed migration `d4e7f9a1b2c3` calls
  `build_dry_tri_2026()` and runs before the conversion migration, which then
  converts the seeded row like any other. Changing the seed to UTC would shift
  a fresh database twice.
- Alembic data migration: for every `events` row, convert the three columns
  from Central to UTC with
  `(col AT TIME ZONE 'America/Chicago') AT TIME ZONE 'UTC'`, which handles DST
  per value. Downgrade reverses it. Bump `HEAD_REVISION` in
  `tests/practices/test_practice_migration_release.py`.

Prod rows affected: `dry-tri-2026` (all CDT, +5h) and the `pickleball` draft
(January, CST, +6h).

### Tests

- Admin create and edit store UTC for a Central input, in both CDT and CST.
- The edit form prefills the Central value it was given.
- The registration page shows "9:00 AM CT" for a 14:00 UTC event in October.
- Signup closes at the Central minute the admin typed.
- The migration round-trips (upgrade then downgrade restores the values).

### Out of scope

Trips save `signup_start`/`signup_end` the same unconverted way
(`admin.py` around line 148). Whether that is visible depends on how trip
pages read them, which this work does not check. Note it, don't fix it here.

## PR 2: live Dry Tri page

### API: `GET /api/events/dry-tri`

New blueprint `app/routes/event_api.py`, beside `season_api.py`.

Selection, in `app/events/selection.py` (pure, testable without a DB):

- Candidates: `template_key == 'dry_tri'`, `status != 'draft'` (a `closed`
  event is still the race; it just stopped taking signups), `audience !=
  'internal'`.
- Pick the soonest event whose `event_date` is now or later. If none, the most
  recent past one. If no candidates, return `{"event": null}` with status 200.

Body:

```json
{
  "generated_at": "2026-10-06T15:00:00Z",
  "event": {
    "slug": "dry-tri-2026",
    "name": "TCSC Roll, Ride, and Run Dry Tri 2026",
    "location": "Carver Park Reserve, Parley Lake, Victoria",
    "description": "TCSC's fall race ...\n\nSchedule of events\n\n- 7:30 AM: Packet pickup opens\n...",
    "event_date": "2026-10-24T14:00:00Z",
    "signup_start": "2026-07-25T05:00:00Z",
    "signup_end": "2026-10-23T04:59:00Z",
    "registration_path": "/events/dry-tri-2026",
    "details_url": "https://docs.google.com/document/d/...",
    "entries": [
      {"name": "Individual Triathlon", "description": "Complete all three legs yourself", "price_cents": 5500}
    ]
  }
}
```

- Timestamps use the same `_iso` shape as `/api/season` (naive UTC to a
  `Z`-suffixed string).
- `entries` are the active price options in `sort_order`. Public price only.
  The payload never carries `member_price_cents`, `discount_code`,
  `capacity`, or registration counts.
- `registration_path` is a path. The app has no ProxyFix, so
  `url_for(_external=True)` can produce `http://` behind Render. The site
  resolves the path against the API URL's origin.
- No open/closed state, for the reason documented in `season_api.py`.
- `apply_marketing_cors`, `Cache-Control: public, max-age=300`.

`/tri` and `/dryland-triathlon` in `routes/main.py` redirect to the selected
event's page. With no event they redirect to `/`.

### Marketing page

New `site/src/lib/eventData.ts`, modeled on `seasonData.ts`: one build-time
fetch of `PUBLIC_EVENT_API_URL` (default `https://tcsc.ski/api/events/dry-tri`),
10 s timeout, never fails the build, returns `{source: 'api' | 'fallback',
event}`.

New `site/src/lib/eventState.ts`: the single rule for the button.

| Now | State | Shows |
|---|---|---|
| before `signup_start` | `upcoming` | "Registration opens Saturday, July 25" |
| `signup_start` to `signup_end` | `open` | **Register** button, "Registration closes Thursday, October 22" |
| after `signup_end`, before race day ends | `closed` | "Registration is closed. See you at the start." |
| after race day | `past` | No button and no closing line. |

"Race day ends" is the end of `event_date`'s Central calendar day. Dates format
in America/Chicago.

`dry-tri.astro` renders, top to bottom:

1. Masthead. Facts strip: event date ("Sat, Oct 24"), "Carver Park Reserve",
   "Roll · Ride · Run". With no event the date fact is omitted.
2. Photo triptych, unchanged.
3. New band, seam label "2026 race" (the year comes from `event_date`): date and
   time, location, the description with line breaks kept and `- ` lines as a
   list, the entries as a ledger (name, description, price), the button area,
   and a "Full race details" link to `details_url` when present.
4. Course ledger, now three rows and no start column:
   Long course 18K roll · 17K ride · 11K run; Short course 9K roll · 9K ride ·
   6K run; Run only: 6K trail run. Footnote drops "The 2025 format."
5. Markdoc body: the 2025 recap. The "## 2026" section is deleted.
6. Links: "Latest results" to `results_url` (was labeled "2025 results"; the
   Keystatic field is already "Latest results URL"). Rob swaps in the 2026
   results URL after the race.

Browser refresh: an inline module script fetches the same URL on load. On
success it re-renders the band from the fresh JSON and recomputes the button
state. On failure it leaves the baked HTML alone. The band's DOM is produced by
one pure function in `eventRender.ts` that both the Astro build and the browser
call, so the two never drift. The site CSP already allows
`connect-src https://tcsc.ski`.

Fallback (no event at build time and no fresh fetch): the band reads
"Dates, entries and registration: tcsc.ski/tri", linked. `/tri` always lands on
the current event.

The band element gets `data-event-source="api|fallback"` (on the band, not
`<body>`, so BaseLayout needs no new prop).

Keystatic and `content.config.ts`: `courses[].start` becomes unused; remove it
from the schema and the `.mdoc`. `register_url` is removed; the API supplies it.

### Copy

Friendly, short, plain. No em dashes.

- Intro: "Our fall race at Carver Park Reserve: rollerski, mountain bike, trail
  run. Do all three yourself, split them with a team of three, or just run the
  6K. Open to everyone."
- Button states: as in the table.
- Fallback: as above.

The event's description and location come from the database and render as
written. Prod em dashes in both were replaced on 2026-10-06 (": " in the
schedule lines, ", " in the location). The prod description uses `\r\n` line
endings; the renderer must accept both.

### Tests

- pytest: selection (upcoming beats past, soonest upcoming wins, draft and
  internal excluded, none gives null), payload shape including the absence of
  member price and discount fields, CORS headers, `/tri` redirect with and
  without an event.
- node: `eventState` at each boundary, Central-day "past" edge, date
  formatting across DST.
- Site build test: extend `site/scripts/test-build.mjs` with a fixture
  `/api/events/dry-tri` response and assert the built page has
  `data-event-source="api"`, the Register button, and the entries.

### Conflicts

Draft PR #249 (`site/brand-review`, last touched 2026-09-01) restyles
`dry-tri.astro` and `dry_tri.mdoc`. This work lands first on main's current
components. #249 rebases onto it and moves the new band into its `Ledger` and
`ProseColumn` components.
