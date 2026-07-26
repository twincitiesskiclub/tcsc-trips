# `/api/site-content` implementation handoff

> **Status:** Ready for a new session to implement as one focused PR.
> **Prepared:** 2026-07-12.
> **Production services:** `tcsc-registration` (Flask) and `tcsc-team-site`
> (Astro static site) both deploy from this repository through `render.yaml`.

## Suggested next-session prompt

> Read `docs/superpowers/notes/2026-07-12-site-content-endpoint-handoff.md`
> completely, then implement the focused `/api/site-content` PR through tests,
> review, merge and production verification. Follow its runtime-fetch design
> and privacy boundary. Do not touch Dry Tri, do not publish trip signup
> timestamps, and preserve all unrelated/untracked workspace files.

## Goal

Make `tcsc.ski` the only source of operational membership facts used by the
marketing site:

- season fees;
- returning-member and new-member registration windows/state;
- the featured registration destination; and
- active current/upcoming trips.

The Astro site should fetch those facts at runtime from a new public,
read-only `GET /api/site-content` endpoint. A database change or a clock-based
registration transition must appear on the next page load without a Git edit,
Astro rebuild, or Render deploy hook.

This is not an attempt to put every piece of club copy in the registration
database. The ownership boundary should be:

| Content | Authority |
|---|---|
| Fees, season dates, registration windows/state | Flask/PostgreSQL |
| Active trip names, destinations, dates, prices and registration paths | Flask/PostgreSQL |
| Practice summaries, schedules, locations and general trip language | Astro/Keystatic |
| Race calendar and narrative | Astro/Keystatic, later protected by `review_by` checks |
| Dry Tri | Unchanged until the club supplies its upcoming update |

## Non-negotiable scope and safety

- **Do not change Dry Tri** content, templates, routes, images or registration
  links in this PR.
- Social events, sponsors and the editorial race calendar are not part of the
  v1 API.
- Do not expose users, emails, payments, registrations, counts, Slack fields,
  internal notes, capacities, `registration_limit`, or private identifiers.
- Keep the endpoint GET/HEAD-only. It does not need a CSRF exemption.
- Preserve the security baseline from PR #216.
- Do not turn Astro into SSR and do not make production builds depend on the
  Flask service being available.
- Do not add a Render deploy hook for v1. Runtime fetching is what lets a
  registration state change automatically at an exact time.
- Do not add a Flask in-process cache. These are cheap database reads, and
  separate Gunicorn workers would have separate caches.

## Repository/history warning

The public history was rewritten to remove two member-data CSV exports. The
current rewritten `origin/main` was `8f6fe68` when this handoff was written.
GitHub Support ticket **4557095** is open to purge immutable PR refs, caches and
fork-network objects.

Start the feature from a fresh fetch of `origin/main`; never merge an old local
branch or an old clone into this work. Before pushing, these commands must
return no CSV history:

```bash
git log --all -- export_dob_age.csv export_season_history.csv
git rev-list --objects --all | rg '(export_dob_age|export_season_history)\.csv'
```

The main worktree contains user-owned untracked files. Do not clean, delete or
stage them. Prefer a new worktree created from rewritten `origin/main`:

```bash
git fetch origin
git worktree add ../tcsc-site-content -b feat/site-content-api origin/main
```

Support ticket work is independent of this feature PR. Record any response,
but do not force-push history again as part of this implementation.

## Why runtime enhancement is the selected design

The production Astro site is fully static. `getEntry()` and `getCollection()`
run during `astro build`; `Cache-Control: max-age=0` only revalidates the same
built HTML and cannot regenerate it.

A build-time API fetch plus deploy hook would add a secret, publishing state,
retry logic, drift monitoring and clock-triggered rebuild scheduling. It would
also make the marketing build depend on the registration service. That is too
much infrastructure for this change.

Use the established Live Conditions pattern instead:

1. Render generic, truthful fallback HTML.
2. Fetch one small, versioned payload after page load.
3. Validate it before changing the DOM.
4. Update only volatile facts with `textContent` and validated paths.
5. On any failure, retain the generic fallback and working `tcsc.ski` link.

The fallback must not preserve old dates, prices or an asserted open/closed
state. A generic fallback such as “See current registration details” is less
specific but never lies when JavaScript or the API is unavailable.

## Current duplication to remove

| Volatile fact | Current marketing-site copies |
|---|---|
| Registration state and state-specific CTA | `site/src/content/pages/home.yaml`, `site/src/content.config.ts`, `site/keystatic.config.ts`, `site/src/components/registrationCta.ts` |
| August 28 / September 3 | `home.yaml`, plus hardcoded CTA-strip copy in `site/src/pages/index.astro` |
| Season fee and registration status | `site/src/content/practice_seasons/*.yaml`, both schemas, `site/src/components/SeasonsGrid.astro` |
| Trip ledger | Empty `site/src/content/trips/` collection, both schemas, `site/src/components/TripsTable.astro` |

The operational Flask facts are in `Season` and `Trip` in `app/models.py`.
There are also three inconsistent concepts of “current season” today:

- `app/routes/main.py` chooses the latest season with registration dates;
- `app/routes/registration.py` orders similar candidates ascending; and
- `Season.get_current()` means the administratively activated membership
  season, which can differ from the next season accepting registrations.

Do not use any of those queries verbatim for the new endpoint. Create and test
one public featured-season selector. Do not change the meaning of
`Season.get_current()` because member-status and Slack code rely on it.

## Proposed v1 contract

Return RFC 3339 UTC timestamps with `Z`, date-only values as `YYYY-MM-DD`, and
money as integer cents. The browser must format registration dates in
`America/Chicago`, never in the visitor's local timezone.

Paths are intentionally relative. The client should resolve them against the
configured `https://tcsc.ski` API origin and reject any unexpected origin or
unsafe scheme.

```ts
type WindowState = 'upcoming' | 'open' | 'closed' | 'unscheduled';
type RegistrationState = 'open' | 'coming_soon' | 'closed';
type Audience = 'returning' | 'new';

interface RegistrationWindow {
  state: WindowState;
  opens_at: string | null;
  closes_at: string | null;
}

interface PublicSeason {
  id: number;
  name: string;
  // Stable normalized values such as `spring-summer` and `fall-winter`.
  season_type: string;
  year: number;
  starts_on: string;
  ends_on: string;
  fee: {
    amount_cents: number | null;
    currency: 'USD';
  };
  details_path: string;
  // Non-null only while at least one audience can actually register.
  register_path: string | null;
  registration: {
    state: RegistrationState;
    open_for: Audience[];
    next_transition_at: string | null;
    returning: RegistrationWindow;
    new: RegistrationWindow;
  };
  source_updated_at: string | null;
}

interface PublicTrip {
  slug: string;
  name: string;
  destination: string;
  starts_on: string;
  ends_on: string;
  price: {
    low_cents: number;
    high_cents: number;
    currency: 'USD';
  };
  details_path: string;
  source_updated_at: string | null;
}

interface SiteContentV1 {
  schema_version: 1;
  meta: {
    generated_at: string;
    time_zone: 'America/Chicago';
    source_updated_at: string | null;
    next_transition_at: string | null;
  };
  membership: {
    featured_season_id: number | null;
    // One relevant row per normalized season type, in deterministic order.
    seasons: PublicSeason[];
  };
  // Only status=active trips that have not ended, ordered by starts_on.
  trips: PublicTrip[];
}
```

Exact field names can change before implementation, but the privacy boundary,
`schema_version`, normalized season key, Central-time display rule, integer
cents and relative-path rule should not.

### Deliberately omitted from the v1 contract

- Season descriptions and capacity/registration counts.
- Trip descriptions, Slack channel, capacities and payment/registration data.
- Social events.
- Editorial race dates.
- Dry Tri.
- Trip signup opening/closing timestamps.

Trip signup timestamps are omitted for a concrete data-quality reason:
`parse_trip_form()` in `app/routes/admin.py` stores browser `datetime-local`
values as naive datetimes, while `app/routes/trips.py` compares them with UTC.
Season registration windows correctly convert Central input to UTC. Do not
label existing trip signup values as UTC in a public API. Fix and migrate that
timezone behavior in a separate PR before extending this contract.

## Backend implementation

Suggested structure:

- `app/site_content/service.py` — selection, state derivation and explicit
  serializers;
- `app/routes/site_content.py` — thin `GET /api/site-content` blueprint;
- `tests/site_content/test_service.py`;
- `tests/site_content/test_route.py`.

Register the blueprint beside the conditions blueprint in `app/__init__.py`.

### Featured-season selector

Implement a deterministic `select_featured_season(now_utc)` with this order:

1. A season with a returning or new window open now.
2. Otherwise, the season with the earliest future registration opening.
3. Otherwise, the administratively `is_current` season.
4. Otherwise, the most recently started season that has not ended.
5. Otherwise, `None`.

Use explicit secondary ordering (`start_date`, then `id`) and log a warning if
multiple rows are marked `is_current`. For the `membership.seasons` array,
choose the most relevant current/upcoming row for each normalized
`season_type`; use a deterministic recent fallback when that type has no
current/future row.

After its tests pass, reuse the selector in `app/routes/main.py` and the
`/seasons` listing so `tcsc.ski` itself cannot disagree with the API. Keep this
refactor narrow; registration authorization continues to use the existing
model window helpers.

### Registration state

- A window is `unscheduled` unless it has a complete, valid start/end pair.
- Start is inclusive and end follows the existing model's inclusive behavior.
- Aggregate state is `open` when either audience is open.
- It is `coming_soon` when neither is open and a valid opening is in the
  future.
- Otherwise it is `closed`.
- `open_for` must distinguish returning-only, both-open and new-only periods.
- `next_transition_at` is the earliest future opening or closing boundary.
- Incomplete/reversed windows fail closed and are logged; never guess.

### Public trip selection

Publish only trips where `status == 'active'` and the trip has not ended. Sort
by start date and then slug. Date-only trip fields, prices and the existing
detail route are safe for v1; signup-window timestamps are not.

Use an explicit serializer. Never serialize SQLAlchemy models generically.

### HTTP, caching and CORS

- GET/HEAD only; no authentication and no credentials.
- Reuse the exact-origin allowlist behavior from `app/routes/conditions.py`:
  production apex, `www`, staging, and debug-only localhost.
- Always send `Vary: Origin`.
- Never send wildcard CORS or `Access-Control-Allow-Credentials`.
- Add `Cache-Control: public, max-age=N, s-maxage=N, must-revalidate`, where
  `N` is at most 60 seconds and is shortened to the seconds remaining before
  `next_transition_at`.
- A legitimate empty database result is a 200 response with no featured
  season and an empty trips array.
- A database/serialization failure is a sanitized 503 with
  `Cache-Control: no-store`.
- The global CSP, HSTS, frame, referrer and nosniff headers should apply
  automatically; add a regression assertion rather than a route exemption.

There is no need for preflight support: the marketing request is a simple
credential-free GET.

## Marketing-site implementation

Add `PUBLIC_SITE_CONTENT_API_URL=https://tcsc.ski/api/site-content` beside
`PUBLIC_CONDITIONS_API_URL` for `tcsc-team-site` in `render.yaml`. The existing
static-site CSP already permits `connect-src https://tcsc.ski`.

Suggested files:

- `site/src/lib/siteContent.ts` — strict contract parser, state/date/price
  formatters and safe path resolution;
- `site/src/components/SiteContent.client.ts` — one fetch and DOM updates;
- `site/src/layouts/BaseLayout.astro` — load the client once per document;
- existing CTA, season and trip components — add stable `data-*` hooks.

Client requirements:

- Fetch once per document with `credentials: 'omit'` and a short timeout.
- Require `schema_version === 1` and validate every field used by the DOM.
- Resolve only relative API paths against the configured `tcsc.ski` origin.
- Use `textContent`, `replaceChildren` and property assignment; never inject
  API strings with `innerHTML`.
- Format registration timestamps with `Intl.DateTimeFormat` and
  `timeZone: 'America/Chicago'`.
- Refresh on a future transition timer (a small delay after the boundary) and
  when a hidden page becomes visible again. Do not poll continuously.
- Leave generic fallback markup untouched on timeout, non-200, malformed
  JSON, unknown schema version or CORS failure.
- A valid `trips: []` is different from a failed request and should render the
  intentional “No trips posted” state.
- Reserve enough space for dynamic notes so enhancement does not create a
  noticeable layout shift.

### Remove manual operational facts

The PR is not complete if the old facts merely remain as a second source.

1. Home content/schema:
   - remove manual `registration_state` from `home.yaml`, Astro schema and
     Keystatic schema;
   - keep state-specific labels only if they remain date-free editorial copy;
   - make every no-JS CTA a generic link to current details at `tcsc.ski`.
2. `site/src/pages/index.astro`:
   - remove hardcoded August 28 / September 3 copy;
   - provide data hooks for the live audience-specific line.
3. Practice-season content/schema:
   - add an explicit normalized `season_type` matching key;
   - remove `fee_cents`, `registration_note` and `registration_open` from the
     YAML, Astro schema and Keystatic schema;
   - keep `date_range`, summary, when, where and general trips language as
     editorial content.
4. Trips:
   - change `TripsTable.astro` from an empty build-time collection to a generic
     runtime-enhanced shell;
   - remove or clearly retire the currently empty trip collection in both
     schemas so editors cannot create a second operational ledger.

CTA consumers to verify include desktop navigation on every page, mobile
navigation, the homepage hero, and the homepage closing CTA. Season cards are
rendered on both `/` and `/about`.

## Tests

### Flask tests

- Exact contract and `schema_version: 1`.
- Frozen-time cases immediately before, at and after every returning/new
  opening and closing boundary.
- Returning-only, both-open, new-only, coming-soon, closed and no-season.
- Open season wins; otherwise earliest upcoming; current/ongoing fallbacks.
- Deterministic duplicate/current handling and season-type normalization,
  including legacy values.
- August 28 and September 3 Central values serialize to correct UTC and the
  contract declares `America/Chicago`.
- Incomplete/reversed windows fail closed.
- Only active non-ended trips are returned, in chronological order.
- Trip signup timestamps are absent from v1.
- Exact payload assertions prove private model fields cannot leak.
- Allowed, denied, staging and debug-localhost CORS behavior.
- `Vary: Origin`, content type, transition-aware cache TTL and 503/no-store.
- Existing conditions CORS/cache behavior remains unchanged if its helper is
  refactored.

### Astro/client verification

There is currently no first-party browser test runner under `site/`; do not
pretend `astro check` tests runtime behavior. At minimum, keep parsing and
formatting functions pure enough for lightweight tests and perform documented
browser smoke checks.

- Exactly one initial request per document regardless of CTA count.
- Every CTA instance resolves to the same state, label and safe destination.
- `/` and `/about` map season rows by stable season type, never array index or
  human-readable display name.
- Correct Central date formatting across CST and CDT.
- Valid populated and valid-empty trip responses.
- Timeout, 503, malformed JSON, partial payload and unknown version retain the
  generic fallback.
- Unsafe absolute URLs and schemes are rejected.
- No `innerHTML`, console errors, blank content or noticeable layout shift.
- The site builds successfully while `/api/site-content` is unavailable.
- Desktop/mobile smoke checks on `/`, `/about`, `/trips`, and one inner page.

Run the full verification suite:

```bash
# From repository root, with the normal safe test database environment
pytest

cd site
npm ci
npm run check
NODE_ENV=production npm run build
```

## Rollout and rollback

Both Render services deploy the same merged commit and may finish in either
order. One additive PR is still safe:

- If the static site deploys first, its generic fallback remains functional
  until the endpoint is live.
- If Flask deploys first, the unused public endpoint is harmless.
- No build-time fetch means neither deployment blocks the other.

After merge, verify:

1. `/api/site-content` is 200 JSON with the expected cache/security headers.
2. Allowed-origin CORS is present and an arbitrary origin receives none.
3. The payload contains no user/payment/Slack or hidden-capacity fields.
4. Homepage, `/about`, `/trips`, desktop nav and mobile nav agree.
5. Changing a test season value in a non-production environment updates the
   site on the next load without rebuilding Astro.
6. API failure leaves truthful generic links rather than stale facts.

Rollback is a normal revert. Because the fallback is generic and the endpoint
is additive, there is no data migration or deploy-hook secret to unwind.

## Definition of done

- `tcsc.ski` is the only manual source for season fees, registration windows
  and operational trip rows.
- No hardcoded registration dates, fees or open/closed state remain in Astro
  content or page code.
- A registration boundary updates the site without a Git change or rebuild.
- All live CTAs agree and distinguish returning/new-member availability.
- API failures retain working, truthful generic registration/trip content.
- No private/internal data appears in the contract.
- Full Flask tests, Astro check/build and browser smoke tests pass.
- Dry Tri remains byte-for-byte unchanged.

## Follow-up after this PR (not part of v1)

Operational records do not need arbitrary `review_by` dates: their effective
state is derived directly from database values and time. Editorial facts do.
A separate follow-up should add required `review_by` metadata and automated
build/CI expiry checks to `racing.mdoc` and other date-sensitive narrative.
Dry Tri should join that mechanism only when its promised update arrives.

Another separate prerequisite is normalizing and migrating trip signup
timestamps from naive local values to UTC. Only then should v2 expose trip
signup deadlines or live trip-registration state.
