# motion-components report

## rows

L-040: fixed (site/src/components/Ledger.astro:24, 096c074)
L-041: fixed (site/src/components/Seam.astro:21, 2426c2b; site/src/components/LiveConditions.astro:37, fd879e3)
L-042: fixed (site/src/components/FactStack.astro:24, f545d1c; site/src/styles/global.css:307, 472c068)
L-043: fixed (site/src/components/Button.astro:19, 2fe5446)
L-044: fixed (site/src/components/ProseColumn.astro:17, e93046e)
L-045: fixed (site/src/styles/global.css:169, ee845d8)
L-046: fixed (site/src/components/WaxEntryRow.astro:25, 16bd5ad)
L-047: fixed (site/src/components/Lightbox.astro:76, cf8494a)
L-048: fixed (site/src/components/LiveConditions.astro:132, 496083d; site/src/styles/global.css:12, 27b7161)
L-049: fixed (site/src/styles/global.css:114, da8fd62)
L-106: fixed (site/src/components/PhotoStrip.astro:53, d7cb3cf)
L-107: fixed (site/src/components/SectionHeader.astro:19, 5399304)
L-108: fixed (site/src/components/SectionBand.astro:5, aaeff75)
L-109: fixed (site/tailwind.config.ts:1, 647894c)
L-110: fixed (site/src/components/Nav.astro:46, 8678c93)
L-111: fixed (site/src/components/navLinks.ts:20, 480d540)
L-112: fixed (site/tests/brandPrimitives.test.mjs:19, 8fe895a)
L-113: fixed (site/src/styles/global.css:4, 720b1f4)
L-114: fixed (site/src/styles/global.css:523, fb5c1de)
L-115: fixed (site/src/components/imageWidths.ts:12, 9bff566)
L-116: skipped (contract-only row; v2 already specifies WebP everywhere and AVIF on the home hero only)
L-117: fixed (site/src/styles/global.css:108, 056aa4e)
L-118: fixed (site/src/components/HeroHome.astro:65, 2fa9b13)
L-119: skipped (contract-only row; v2 already specifies the current hero, conditions, and mobile navigation motion)
L-120: fixed (site/src/components/Lightbox.astro:10, a9b609b)

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
- home-birkie-hover-desktop.png
- home-closed-desktop.png
- home-closed-mobile.png
- home-dryland-desktop.png
- home-dryland-mobile.png
- home-hero-desktop.png
- home-hero-mobile.png
- home-hero-tablet.png
- home-lightbox-desktop.png
- home-lightbox-mobile.png
- home-mobile-nav-mobile.png
- home-mosaic-hover-desktop.png
- home-open-desktop.png
- home-open-mobile.png
- home-soon-desktop.png
- home-soon-mobile.png
- home-unavailable-desktop.png
- home-unavailable-mobile.png
- home-wax-feed-desktop.png
- home-wax-feed-mobile.png
- racing-default-desktop.png
- racing-default-mobile.png
- sponsors-default-desktop.png
- sponsors-default-mobile.png
- trips-empty-desktop.png
- trips-empty-mobile.png
- trips-populated-desktop.png
- trips-populated-mobile.png
- wax-entry-default-desktop.png
- wax-entry-default-mobile.png
- wax-room-empty-desktop.png
- wax-room-empty-mobile.png
- wax-room-populated-desktop.png
- wax-room-populated-mobile.png

## proposed

None.

## test/build

- `npm run check`: `- 5 hints`
- `npm run build`: `16:04:39 [build] Complete!`
- `npm run test:refinement`: `ℹ duration_ms 832.799729`
- `npm run test:sponsors`: `ℹ duration_ms 46.154537`
- `npm run test:fallback`: `ℹ duration_ms 3317.298695`
