# Year-Round Wax Recommendations Design

**Date:** 2026-07-19
**Status:** Approved direction, awaiting written-spec review

## Context

TCSC's Live Conditions strip receives current temperatures and mechanically derives the winter wax recommendation for each venue. The API already produces those values year round. In summer, that can yield an entirely correct result such as an 88°F reading paired with `Red wax · klister conditions`.

Website 2.1 added a client-side calendar gate that suppresses every healthy April-through-October payload. The strip instead collapses to `Dryland season`, removes the venue readings, and says trail reports will return with the snow. That behavior hides useful live data and removes the dry, ski-nerdy humor that comes from presenting the recommendation literally.

## Decision

Use the same live conditions instrument in every month when the API returns a healthy payload. Present the real current temperature and the existing winter wax recommendation without explaining, decorating, or amplifying the joke.

The calendar remains relevant only when live data is unavailable:

- April through October failure: show the existing `Dryland season` fallback.
- November through March failure: show the existing `Conditions unavailable` fallback.

## Goals

- Restore actual venue temperatures and wax recommendations year round.
- Keep the feature visually serious, technically credible, and unmistakably part of the existing TCSC brand.
- Let the literal recommendation carry the humor by itself.
- Preserve the existing winter experience, responsive behavior, Birkie Fever interaction, accessibility, refresh policy, and failure handling.
- Make healthy-data precedence explicit and regression-tested.

## Non-Goals

- No new summer-specific copy, badges, colors, illustrations, icons, or animation.
- No explanation that the wax recommendation is theoretical.
- No separate summer component or expanded summer layout.
- No backend or API schema changes.
- No new weather fields, future forecast data, or snow-depth simulation.
- No changes to wax temperature thresholds or labels.
- No changes to Birkie Fever values, copy, audio, or interaction.

## Experience Contract

### Healthy payload, any month

The prominent home-page strip keeps its current presentation:

- `Trail report` label
- factual `Live · updated [time]` stamp
- Theo, Elm, Hyland, and Telemark venue cells on desktop
- Theo on mobile
- real temperature and materially different feels-like temperature
- the existing wax-color chip and exact API wax label
- trail report links and grooming details when the API supplies them
- Birkie Fever on desktop, including the user-triggered song

The compact inner-page strip likewise keeps its current presentation:

- all four venue lines and Birkie Fever on desktop
- Theo on mobile
- current temperature and exact wax recommendation

Summer does not receive a different visual treatment. The professional ledger and live timestamp make the output feel intentional. The unexpected recommendation supplies the personality.

### Loading and no JavaScript

Keep the current server-rendered venue names, placeholders, loading stamp, first-fill transition, and 1.2-second visibility backstop. This change does not introduce a new loading state.

### Unavailable payload

Keep the two existing quiet fallbacks:

- April through October: collapse to the existing `Dryland season` presentation and 98.6° Birkie Fever reading.
- November through March: keep venue rows visible with `No report`, show `Conditions unavailable`, and clear stale links, grooming details, and wax chips.

An API failure must never manufacture or preserve a recommendation as if it were current.

## State Selection

`conditionsDisplayMode(payload, at)` remains the single state-selection boundary. It evaluates payload health before applying a seasonal fallback.

| Payload | Month | Mode |
|---|---|---|
| No top-level error and a non-empty `locations` array | Any month | `live` |
| Error, missing payload, or empty `locations` | April through October | `off-season` |
| Error, missing payload, or empty `locations` | November through March | `unavailable` |

This ordering is the core behavior change. A healthy July response is `live`; July itself is not an error state.

## Data Flow and Component Boundaries

No server changes are required.

1. `LiveConditions.client.ts` fetches `GET /api/conditions` immediately and every five minutes while the page is visible.
2. `conditionsDisplayMode.ts` classifies the response using the truth table above.
3. A `live` classification uses the existing renderer and exposes the API's temperature, wax band, wax label, provenance, grooming, timestamp, and Birkie status.
4. A quiet classification uses the existing seasonal failure renderer.

Responsibilities remain separated:

- `site/src/lib/conditionsDisplayMode.ts`: payload and calendar state selection only.
- `site/src/components/LiveConditions.client.ts`: DOM rendering, refresh, stale-state cleanup, and Birkie audio behavior.
- `site/src/components/LiveConditions.astro`: markup, responsive layout, visual tokens, and reduced-motion styling. No visual change is expected.
- `app/conditions/*` and `app/routes/conditions.py`: unchanged data production and caching.

## Accessibility and Brand Constraints

- Preserve `aria-label="Current ski conditions"` and the polite live announcer.
- Continue announcing only a material change in a previously rendered wax band.
- Preserve current keyboard, focus, 44px mobile-target, and reduced-motion behavior.
- Keep the navy-deep, mint, paper, and coral token system unchanged.
- Keep the current typographic hierarchy and responsive density unchanged.
- Add no decorative motion or interaction. The data remains the signature device.

## Test Strategy

Implementation follows test-driven development.

1. Change the current healthy-July unit expectation from `off-season` to `live` and observe it fail against the existing selector.
2. Preserve and run the error-July test, which must remain `off-season`.
3. Preserve the healthy-January and error-January expectations.
4. Add a rendered-DOM regression with a July clock and healthy venue payload. Assert that venue cells remain visible and render a summer temperature, the exact `Red wax · klister conditions` label, the red wax chip, the live timestamp, and the API Birkie value.
5. Keep the existing October-failure to November-failure transition regression. It protects restoration of venue rows when the calendar changes.
6. Run the complete refinement, sponsor, backend conditions, and Astro diagnostic suites.
7. Inspect the prominent and compact variants at 390px and 1440px using a mocked healthy summer payload. Require no overflow, no layout shift, and no new seasonal ornament.

## Acceptance Criteria

- A healthy API payload renders as live in January, July, and every other month.
- A summer visitor sees real venue temperatures and the same wax recommendations a winter visitor would see at those temperatures.
- The recommendation labels and wax-color encoding remain unchanged.
- The prominent and compact layouts remain visually identical across seasons for healthy data.
- Summer and winter failures retain their current distinct fallbacks.
- The Birkie Fever cell and audio remain unchanged.
- No backend, content schema, API, or global design-token changes are introduced.
- Automated and browser verification cover both viewport classes and both seasonal failure branches.
