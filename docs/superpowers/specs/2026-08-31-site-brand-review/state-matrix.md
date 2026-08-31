# state matrix

Every row is a screenshot target. Viewports: mobile 390x844, desktop 1440x900, both unless noted; the home hero adds tablet 768x1024. Filenames: `screens/<phase>/<surface>-<state>-<viewport>.png`. Captures are full-page unless the row says viewport only.

## how states are produced

- Registration state is baked at build time from `PUBLIC_SEASON_API_URL`. `scripts/brand-review/build-state.mjs <open|soon|closed|populated>` builds the site once per state against the fixture api (`fixture-api.mjs`, port 4499, windows relative to now so `registrationFlip.ts` agrees in the browser). Every capture asserts `data-season-source="api"`; a `fallback` capture is a harness failure, not a finding.
- Conditions are fetched by the browser. `screenshot.mjs` answers the fetch per state: `live` (four venues with temps and wax bands, Birkie fever), `dryland` (error payload; in August the strip reads "Dryland season"), `unavailable` (fetch aborted with the browser clock frozen at 2027-01-15, so the strip reads "No report"; the registration CTA in that capture is whatever the frozen clock derives, which is closed, and is not a finding).
- `populated` is the open build plus `fixtures/content/trips/sisu-ski-fest.mdoc` and `fixtures/content/wax_entries/first-snow-wax.mdoc`, copied into `site/src/content/` for the build only. Production currently has no trips and no wax entries, so the `empty` states are what visitors see today.
- Serve a build locally: `node serve-dist.mjs <build> --port 4400`. Take one state: `node screenshot.mjs <phase> <id>`.
- The contract describes a conditions cell that expands on click ("Click a column → expands"). The strip never got that interaction; the only interactive element is the Birkie fever button, which plays a song. That gap is a finding for the lens agents, so the matrix captures the hover state of that button instead.

## rows

| id | surface | state | build | url | conditions | viewports | how |
|---|---|---|---|---|---|---|---|
| home-open | home | open | open | / | live | m, d | registration open: CTA in nav, hero, strip |
| home-soon | home | soon | soon | / | live | m, d | coming soon: dates line under the hero CTA |
| home-closed | home | closed | closed | / | live | m, d | closed: "How to register" |
| home-dryland | home | dryland | open | / | dryland | m, d | conditions strip off-season |
| home-unavailable | home | unavailable | open | / | aborted, clock 2027-01-15 | m, d | conditions strip "No report" |
| home-birkie-hover | home | birkie-hover | open | / | live | d | viewport only; hover on the Birkie fever button |
| home-wax-feed | home | wax-feed | populated | / | live | m, d | scrolled to the bottom; wax teaser visible |
| home-hero | home | hero | open | / | live | m, t, d | viewport only; hero at three widths (faces clear of text) |
| home-mobile-nav | home | mobile-nav | open | / | live | m | viewport only; menu open |
| home-lightbox | home | lightbox | open | / | live | m, d | viewport only; first mosaic photo opened |
| home-mosaic-hover | home | mosaic-hover | open | / | live | d | viewport only; caption scrim on hover |
| about | about | open | open | /about | live | m, d | |
| about-closed | about | closed | closed | /about | live | m, d | seasons grid closed note |
| community | community | default | open | /community | live | m, d | |
| racing | racing | default | open | /racing | live | m, d | |
| dry-tri | dry-tri | default | open | /dry-tri | live | m, d | |
| extra-training | extra-training-fun | default | open | /extra-training-fun | live | m, d | |
| coaches | coaches | default | open | /coaches | live | m, d | |
| sponsors | sponsors | default | open | /sponsors | live | m, d | |
| trips-empty | trips | empty | open | /trips | live | m, d | production today |
| trips-populated | trips | populated | populated | /trips | live | m, d | one fixture trip |
| wax-room-empty | wax-room | empty | open | /wax-room | live | m, d | production today |
| wax-room-populated | wax-room | populated | populated | /wax-room | live | m, d | one fixture entry |
| wax-entry | wax-entry | default | populated | /wax-room/first-snow-wax | live | m, d | |
| not-found | 404 | default | open | /this-does-not-exist | live | m, d | |

## non-page surfaces

- OG image: `site/public/og/og-default.jpg` (the only one; every page uses it). Review the file directly.
- Shared components (read the code; they appear in the rows above): `Nav`, `MobileNavPanel`, `LiveConditions` (full on home, compact in the header of inner pages), `SectionBand` (navy / paper / paper-on-navy), `MissionPanel`, `SeasonsGrid` (navy on home, paper on about), `CTAStrip`, `Footer`, `HeroHome`, `HeroInner`, `PhotoMosaic`, `Lightbox`, `CoachEntry`, `SponsorWall`, `TripsTable`, `WaxRoomFeed`, `WaxEntry`.
