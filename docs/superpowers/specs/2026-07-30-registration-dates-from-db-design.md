# Registration Dates From the Database — Design

**Date:** 2026-07-30
**Driver:** Two "Fall registration dates" buttons on the marketing site were dead clicks, and the
dates behind them are hand-typed in three places, already drifted out of sync with the
`registration_state` toggle that governs them.
**Scope:** Fix the dead CTAs; add a public Flask season API; consume it at build time and flip
state client-side. No schema migration — every field this needs already exists on `Season`.

## Background

The marketing site (`site/`, Astro, Render static) hardcodes fall registration dates in two
places and gates them behind a third hand-maintained field:

| Location | Field | Today |
|---|---|---|
| `site/src/pages/index.astro:60` | `ctaStripSubhead` | `'Returning members Aug 28; new members Sep 3.'` |
| `site/src/content/practice_seasons/fall-winter.yaml:7` | `registration_note` | `'2026 registration: returning members Aug 28 · new members Sep 3'` |
| `site/src/content/practice_seasons/*.yaml` | `registration_open` | manual boolean |
| `site/src/content/pages/home.yaml:6` | `registration_state` | manual `open`/`coming_soon`/`closed` |

All four are already implied by `Season.returning_start`, `returning_end`, `new_start`, and
`new_end` in the app database. Nothing derives them; a human retypes them each season and flips
the state by hand on the morning registration opens.

### The dead-CTA defect (included in this change)

Found the same day and shipping in this same branch, because it touches the same components
(`CtaForState.astro`, `index.astro`) and sequencing it separately would only create a conflict.

While `registration_state` is `coming_soon`, the CTA destination is a same-page anchor,
`https://twincitiesskiclub.org/#registration`. Three consumers use that correctly to scroll down
to the CTA strip. Two did not:

1. The **bottom CTA strip** *is* `<section id="registration">`, so its own button linked to the
   section it already occupies — a dead click. The existing guard in `index.astro` checked only
   for a missing or literal `'#'` url, not for a resolved same-page anchor.
2. The **mobile menu** is a `fixed inset-0` overlay over a scroll-locked body. A same-document
   fragment click never reloads, and nothing else closed the panel, so the overlay stayed up over
   a page that could not scroll. The tap read as completely dead.

Both are fixed by `site/src/lib/samePageAnchor.ts`, which resolves an href against the current
page — necessary because Keystatic authors urls as absolute, so a self-link never appears as a
bare `#registration`. The strip falls through to `tcsc.ski`; the mobile panel closes itself before
letting the browser scroll.

This matters to the design below beyond mere co-location: once state is derived from the database,
`coming_soon` will begin and end on its own schedule, so the CTA wiring for that state has to be
correct without anyone watching it.

### Deployment constraint

`tcsc-team-site` is a Render **static** service with `autoDeployTrigger: commit` (`render.yaml`).
It rebuilds only when something lands on `main`. "Read from the database" therefore has to cross
a build-time boundary — the site cannot query Postgres at request time because there are no
requests, only files.

### Existing precedent

`app/routes/conditions.py` already serves the marketing site a public JSON API with an origin
allowlist, `Vary: Origin`, and cache headers; `site/src/components/LiveConditions.astro` consumes
it client-side. The site's CSP (`render.yaml`) already permits `connect-src https://tcsc.ski`.
The new endpoint follows that blueprint's shape but omits its caching/background-rebuild
machinery, which exists only because conditions call slow external feeds.

## Decisions

Settled with the club before design:

1. **Both dates and state derive from the database.** The `registration_state` toggle is deleted,
   not kept as an override. State is a pure function of the windows and the current time.
2. **The season is chosen by soonest upcoming registration window**, not by `Season.is_current`.
   `is_current` is set by the "Activate Season" admin action, which is a bulk write across every
   user's status — nobody will run it to correct the website.
3. **Timestamps are baked into the HTML and the browser re-derives state from them.** No runtime
   API call. This is correct at the exact minute registration opens without a rebuild.
4. **A failed build-time fetch never blocks a deploy.** It falls back (see Failure Behavior).
5. **The two season cards are included**, matched to database rows by `season_type`.

## Non-goals

- Rebuilding the site on a schedule. Baked timestamps make the common case self-correcting;
  a rebuild is needed only when someone *edits* dates that are already published.
- Driving CTA labels or URLs from the database. Those stay editorial in Keystatic.
- Any change to how the Flask app itself renders registration (`app/templates/index.html`).
- Reconciling the legacy `season_type` values (`'legacy'`, `'winter'`) written by
  `app/slack/sync.py:335` and older tests. Unmatched types fall through to committed copy.

## Architecture

```
Postgres  ──►  Flask GET /api/season  ──►  astro build (one fetch)  ──►  baked HTML
                                                                             │
                                                       browser re-derives state from
                                                       baked timestamps, no network
```

### Flask: `GET /api/season`

New blueprint at `app/routes/season_api.py`, registered alongside the conditions blueprint under
the `/api` prefix. Origin allowlist and `Vary: Origin` handling are shared with
`app/routes/conditions.py` — the allowlist constant moves to a small shared helper rather than
being duplicated.

```json
{
  "generated_at": "2026-07-30T16:00:00Z",
  "primary": { "...": "soonest upcoming across all types, or null" },
  "by_type": {
    "fall/winter":   { "...": "soonest upcoming of this type, or absent" },
    "spring/summer": { "...": "..." }
  }
}
```

Each season object:

```json
{
  "name": "2026 Fall/Winter",
  "season_type": "fall/winter",
  "year": 2026,
  "price_cents": 20500,
  "returning_start": "2026-08-28T17:00:00Z",
  "returning_end":   "2026-09-02T05:00:00Z",
  "new_start":       "2026-09-03T17:00:00Z",
  "new_end":         "2026-09-20T05:00:00Z"
}
```

Timestamps are stored naive UTC in the database (repo convention) and serialized with an explicit
`Z` so neither consumer has to guess. Null windows serialize as `null`.

Response is public and cacheable: `Cache-Control: public, max-age=300`. The endpoint exposes only
season names, types, prices, and registration windows — all of which are already public on both
sites. No member data.

### Selection rule

One function, `select_season(seasons, now)`, in a new `app/seasons/` package (following the
existing `app/conditions/`, `app/events/`, `app/practices/` layout). It is applied twice, never
reimplemented: once per distinct `season_type` present in the database to build `by_type`
(including legacy values like `'winter'` and `'legacy'`, which simply go unmatched by the site),
and once across all seasons to produce `primary`. Candidates are seasons with at least one
non-null start; a season with no windows at all is never selected.

Given `span_start = min(non-null starts)` and `span_end = max(non-null ends)`:

1. a season with `span_start <= now <= span_end` → that season
2. else the season with the smallest `span_start > now`
3. else the season with the largest `span_end` in the past
4. else `None`

### State rule

Deliberately three branches:

```
any window open now          -> open
else any window starts later -> coming_soon
else                         -> closed
```

The middle branch also covers the gap between `returning_end` and `new_start`: registration is
underway as a period, but nobody can actually submit, so the honest answer is `coming_soon` rather
than `open`. If the club's windows overlap in practice this branch simply never fires; it is
correct either way and costs one comparison.

**This rule exists once, in TypeScript** (`registrationState.ts`), and is called from two places
that share the module: the Astro build and the browser. The endpoint deliberately returns no
computed `state` field — a state computed on the server is wrong the moment a window boundary
passes, which is precisely the staleness this design removes. Flask needs no implementation of
its own; `Season.is_any_registration_open` already covers what the app itself renders.

### Site: bake all variants, flip in the browser

The browser performs no formatting and holds no copy. Every state's rendered strings are baked as
data attributes and the client script only chooses among them:

```html
<div data-registration
     data-returning-start="2026-08-28T17:00:00Z"
     data-returning-end="2026-09-02T05:00:00Z"
     data-new-start="2026-09-03T17:00:00Z"
     data-new-end="2026-09-20T05:00:00Z"
     data-open-label="Register for the season"  data-open-url="https://tcsc.ski/"
     data-soon-label="Fall registration dates"  data-soon-url="https://twincitiesskiclub.org/#registration"
     data-closed-label="How to register"        data-closed-url="https://tcsc.ski/">
```

New modules, each with one purpose and testable in isolation:

| Module | Purpose | Depends on |
|---|---|---|
| `site/src/lib/registrationState.ts` | pure `deriveRegistrationState(windows, now)` | nothing |
| `site/src/lib/seasonData.ts` | build-time fetch, memoized per build | `fetch`, env |
| `site/src/lib/registrationCopy.ts` | formats date lines in `America/Chicago` | `registrationState` |
| `site/src/components/registrationFlip.ts` | client script: re-derive, swap variant | `registrationState` |

`seasonData.ts` reads `import.meta.env.PUBLIC_SEASON_API_URL`, defaulting to
`https://tcsc.ski/api/season`, and the variable is added to the `tcsc-team-site` service in
`render.yaml` beside `PUBLIC_CONDITIONS_API_URL`. The fetch is memoized at module scope so a build
that renders the home page and both season cards issues one request, and uses
`AbortSignal.timeout(10_000)` so a hung API cannot stall a deploy.

Dates render in US Central via `Intl.DateTimeFormat` with `timeZone: 'America/Chicago'`, matching
the repo's UTC-stored / Central-displayed convention.

Consumers: `CtaForState.astro` (hero, nav, mobile menu) and `SeasonsGrid.astro` (both cards, matched
`'fall/winter'` → `fall-winter.yaml`, `'spring/summer'` → `spring-summer.yaml`). The bottom CTA
strip (`CTAStrip.astro`) is not a `CtaForState.astro` consumer — it renders its own `<a>` directly
— but bakes the identical `data-*` attribute vocabulary onto that `<a>`, plus a matching
`data-registration-subhead` marker with three baked subhead variants on its subhead `<p>`, so it
participates in the same flip as every other CTA.

`registrationFlip.ts` runs once per page load and, for each `[data-registration]` element, re-derives
state from the baked timestamps. When it differs from the baked state, it updates that element's
label and href, then climbs to the nearest `<section>` and updates a `[data-registration-subhead]`
found there (currently only the CTA strip carries one; the hero/nav/mobile CTAs have no paired
subhead and this is a no-op for them). When the derived state matches the baked state — the
overwhelmingly common case — it does nothing.

## Failure behavior

A failed or timed-out build-time fetch never fails the build. The fallback is deliberately
pessimistic: it declines to make a claim rather than making a stale one.

| | On API failure |
|---|---|
| State | `closed` |
| Label / URL | "How to register" → `https://tcsc.ski/` |
| Strip subhead | date sentence omitted entirely; ability line retained |
| Season cards | committed `registration_note` and `registration_open` from the YAML |
| Build output | loud `[season]` warning naming the URL and the error |

`closed` is the safe direction because its destination is the Flask app, which reads the database
live and shows the real opening date regardless of what the static site believes. Falling back to
`open` would send members to a registration form that may not accept them.

This fallback is silent by design (deploys are never blocked), so it is made **detectable**: every
build stamps the page with

```html
<body data-season-source="api|fallback" data-season-generated-at="2026-07-30T16:00:00Z">
```

A single `curl` against the live site reveals a fallback build. Without this the accepted tradeoff
— never blocking a deploy — would let stale dates ship invisibly, which is the failure mode this
whole design exists to remove.

## Keystatic and content changes

- **Deleted:** `registration_state` from `home.yaml`, `content.config.ts`, `keystatic.config.ts`.
- **Kept, unchanged in meaning:** `cta_*_label` and `cta_*_url` — copy and destinations are
  editorial, not derived.
- **Kept, redocumented:** `registration_note` and `registration_open` in `practice_seasons/*.yaml`
  are now fallback-only, used when the API is unreachable or no database season matches that
  `season_type`. Their schema comments say so.

## Testing

**Python (pytest, existing PostgreSQL fixtures)**
- `select_season` across each branch: open now, future only, all past, no candidates, ties.
- Endpoint: JSON shape, `Z`-suffixed timestamps, null windows, CORS allowlist hit and miss,
  `Vary: Origin`, and the zero-seasons case returning `primary: null` rather than erroring.

**TypeScript (`node --test`, existing site harness)**
- `deriveRegistrationState` boundaries: exactly at a start, exactly at an end, one second either
  side, inside the returning/new gap, no windows at all, all windows past.
- `registrationCopy` formats in Central across a DST boundary.

**Build**
- `dist/index.html` carries the `data-registration` attributes and a `data-season-source` stamp.
- A build with `PUBLIC_SEASON_API_URL` pointed at a closed port produces the closed-state
  fallback, `data-season-source="fallback"`, and still exits zero.

**Browser (jsdom, driving the real built bundle)**
- With timestamps baked before an opening moment and a clock set after it, the flip script swaps
  the CTA to the open variant; with a clock before it, the DOM is untouched (`registrationFlip.test.mjs`).
- The mobile menu closes and releases the body scroll lock when a same-page anchor inside it is
  clicked (`registrationCta.test.mjs`). Added in a later review pass to replace an earlier version
  of this test that only grepped the `.astro` source for `isSamePageAnchor` and
  `panel.addEventListener('click'` — assertions that keep passing even if the handler's `close()`
  call is deleted. The current version instead locates the built `MobileNavPanel` script (by
  content, external-or-inlined, the same way `registrationFlip.test.mjs` locates its bundle — Astro
  minifies away the `isSamePageAnchor` identifier, so the search key is a CSS-selector string
  literal that survives minification), runs it under jsdom against a DOM shaped like the real
  panel markup, opens the panel, clicks a same-page-anchor link inside it, and asserts the panel
  closed and `document.body.style.position` was released from `fixed`. Deliberately removing the
  `close()` call and rerunning was used to confirm the test fails without it.

## Risks

- **Date edits after a build still go stale.** Baked timestamps self-correct across a *transition*
  but not across an *edit*. Editing published dates requires a rebuild. Accepted: date edits are
  rare and deliberate, and `data-season-generated-at` makes the staleness visible.
- **`season_type` is a free-form string.** A typo in the admin form silently unmatches a card,
  which then shows committed copy. Acceptable — the failure is visible copy, not a wrong claim.
- **A clock-skewed visitor sees the wrong state.** The flip trusts the browser's clock. A device
  set days off could show `open` early. Untreatable without a network call, and the destination
  (`tcsc.ski`) rejects an out-of-window registration anyway.
