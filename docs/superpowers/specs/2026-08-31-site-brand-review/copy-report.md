# copy report

## rows

L-003: fixed (site/src/content/pages/home.yaml:8, 8c377e5)
L-004: fixed (site/src/content/pages/home.yaml:12, 8534546)
L-005: fixed (site/src/content/pages/sponsors_page.yaml:3, 2989c4b)
L-006: fixed (site/src/lib/registrationCopy.ts:67, e37a4ac)
L-007: fixed (site/src/content/photos/loppet-skijor.yaml:12, 0f325e9)
L-025: fixed (site/src/lib/registrationCopy.ts:35, dbd6565)
L-026: fixed (site/src/lib/registrationCopy.ts:60, 040ad17)
L-027: fixed (site/src/components/HeroHome.astro:34, 348b67e)
L-028: fixed (site/src/pages/about.astro:46, bb6ba03)
L-029: fixed (site/src/content/pages/racing.mdoc:37, 89997de)
L-030: fixed (site/src/content/coaches/rebecca.mdoc:8, d8b2601)
L-031: fixed (site/src/content/coaches/kj.mdoc:8, eeba84b)
L-032: fixed (site/src/content/pages/racing.mdoc:33, eef6360)
L-033: fixed (site/src/pages/sponsors.astro:24, 9a9e522)
L-034: fixed (site/src/pages/404.astro:10, 4e47dfa)
L-035: fixed (site/src/components/TripsTable.astro:23, 4c8ec03)
L-036: fixed (site/src/pages/wax-room/index.astro:20, 68ad66c)
L-037: fixed (site/src/components/Footer.astro:22, 4a86815)
L-038: fixed (site/src/pages/coaches.astro:23, 26e9c6b)
L-039: fixed (site/src/content/coaches/greg.mdoc:10, ddc97fb)
L-084: fixed (site/src/content/pages/racing.mdoc:25, f7cad88)
L-085: fixed (site/src/pages/404.astro:30, ff00ce0)
L-086: fixed (site/src/content/pages/community.mdoc:75, 81aaf31)
L-087: fixed (site/src/content/practice_seasons/fall-winter.yaml:9, 509a377)
L-088: fixed (site/src/content/practice_seasons/fall-winter.yaml:2, be0e50b)
L-089: fixed (site/src/content/site_meta.yaml:4, 5a879bd)
L-090: fixed (site/src/pages/index.astro:94, c831c74)
L-091: skipped (contract-only Flask follow-up outside the permitted site scope)
L-092: fixed (site/src/content/pages/community.mdoc:4, d32fc66)
L-093: fixed (site/src/content/pages/community.mdoc:71, e52e1bf)
L-094: fixed (site/src/content/pages/dry_tri.mdoc:26, 22db87e)
L-095: fixed (site/src/content/coaches/kj.mdoc:13, fd0e511)
L-096: fixed (site/src/content/pages/community.mdoc:69, d263cc5)
L-097: fixed (site/src/lib/sponsorTiers.js:7, eca9836)
L-098: fixed (site/src/pages/index.astro:121, 5ace8e9)
L-099: skipped (contract-only Keystatic field-description follow-up with no current content change)
L-100: fixed (site/src/pages/wax-room/index.astro:14, 48a954a)
L-101: fixed (site/src/assets/images/uploads/home-hero.jpg:1, b331193)
L-102: fixed (site/src/pages/about.astro:18, d351fd8)
L-103: fixed (site/src/layouts/BaseLayout.astro:12, 79ada90)
L-104: fixed (site/src/content/pages/community.mdoc:72, fe7aa32)
L-105: skipped (requires sections-owned PhotoMosaic markup under L-064)

## screens

- 404-default-desktop.png
- 404-default-mobile.png
- about-closed-desktop.png
- about-closed-mobile.png
- about-open-desktop.png
- about-open-mobile.png
- coaches-default-desktop.png
- coaches-default-mobile.png
- community-default-desktop.png
- community-default-mobile.png
- dry-tri-default-desktop.png
- dry-tri-default-mobile.png
- extra-training-fun-default-desktop.png
- extra-training-fun-default-mobile.png
- home-closed-desktop.png
- home-closed-mobile.png
- home-hero-desktop.png
- home-hero-mobile.png
- home-hero-tablet.png
- home-open-desktop.png
- home-open-mobile.png
- home-soon-desktop.png
- home-soon-mobile.png
- racing-default-desktop.png
- racing-default-mobile.png
- sponsors-default-desktop.png
- sponsors-default-mobile.png
- trips-empty-desktop.png
- trips-empty-mobile.png
- wax-room-empty-desktop.png
- wax-room-empty-mobile.png
- wax-room-populated-desktop.png
- wax-room-populated-mobile.png

## proposed

- L-007, sections and schema: add a render-eligibility field or filter so `loppet-skijor` stays off the community wall until third-party photo rights are recorded. The home wall already uses `vasaloppet-duo` instead.
- L-031, owner follow-up: confirm whether KJ's removed brand list represented sponsorship or shop affiliations, and ask KJ for two factual bio sentences.
- L-034, sections L-126: remove `Choose another page.` and its paragraph. Change `Try one of these` to the single h3 above the destination ledger.
- L-036, sections L-061: add the inline home link after the empty Wax Room sentence inside the ruled placeholder row.
- L-039, owner follow-up: obtain a sharper consented portrait of KJ. Greg now leads as the approved fallback.
- L-091, Flask follow-up: change `Theo` to `Theodore Wirth` in `app/conditions/locations.py`. That file is outside this workstream's permitted site scope.
- L-099, later schema round: add the date and place house formats to the Keystatic field descriptions.
- L-105, sections L-064: add the `Photo wall` seam and `Photos by club members` heading above the community mosaic.

No unledgered copy changes were made.

## test/build

- `npm run check`: `- 5 hints`
- `npm run build`: `15:24:50 [build] Complete!`
- `npm run test:refinement`: `ℹ duration_ms 687.627434`
- `npm run test:sponsors`: `ℹ duration_ms 51.184348`
- `npm run test:fallback`: `ℹ duration_ms 3448.561539`
