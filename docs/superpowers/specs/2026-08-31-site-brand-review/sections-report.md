# sections report

## rows

L-008: fixed (site/src/components/HeroHome.astro:62, eede554)
L-009: fixed (site/src/components/CoachEntry.astro:73, 195fc6a)
L-050: fixed (site/src/components/WaxRoomFeed.astro:33, fbd1d5d)
L-051: fixed (site/src/components/LiveConditions.astro:99, b4f646b)
L-052: fixed (site/src/components/SectionBand.astro:35, 6d44e54)
L-053: fixed (site/src/pages/index.astro:103, e61ef6b)
L-054: fixed (site/src/styles/global.css:145, 4989a94d)
L-055: fixed (site/src/pages/sponsors.astro:34, 593cd3a)
L-056: fixed (site/src/components/SponsorWall.astro:52, 9692ab3)
L-057: fixed (site/src/components/SeasonsGrid.astro:92, c7537df)
L-058: fixed (site/src/components/WaxEntry.astro:64, b849497)
L-059: fixed (site/src/pages/racing.astro:75, afcd010)
L-060: fixed (site/src/pages/dry-tri.astro:38, ec20d9a)
L-061: fixed (site/src/pages/wax-room/index.astro:23, 1b7063f)
L-062: fixed (site/src/components/PhotoMosaic.astro:142, bb5681e)
L-063: fixed (site/src/components/PhotoMosaic.astro:224, fc5ee70)
L-064: fixed (site/src/components/PhotoMosaic.astro:229, e041147)
L-065: fixed (site/src/components/LiveConditions.astro:154, 54f1148)
L-066: fixed (site/src/styles/global.css:22, 7621d6b)
L-067: fixed (site/src/components/MobileNavPanel.astro:18, c970df9)
L-068: fixed (site/src/pages/about.astro:86, 6671dc1)
L-069: skipped (contract-only row already recorded in DESIGN.md v2; no code change)
L-070: fixed (site/src/layouts/BaseLayout.astro:71, ff46adc)
L-071: fixed (site/src/components/HeroHome.astro:65, 220baec)
L-121: fixed (site/src/pages/racing.astro:61, c9c0e19)
L-122: fixed (site/src/components/Footer.astro:25, a5c66f2)
L-123: fixed (site/src/components/LiveConditions.astro:96, 6f30a1c)
L-124: fixed (site/src/components/LiveConditions.astro:42, dd95949)
L-125: fixed (site/src/components/LiveConditions.astro:35, 1a9e985)
L-126: fixed (site/src/pages/404.astro:45, 298c57b)
L-127: fixed (site/src/components/Nav.astro:17, 44d85c0)
L-128: fixed (site/src/components/SeasonsGrid.astro:107, aafe6d4)
L-129: fixed (site/src/components/HeroInner.astro:51, 88d49d4)
L-130: fixed (site/src/pages/about.astro:66, 72363c1)
L-131: fixed (site/src/pages/404.astro:40, c741a59)
L-132: fixed (site/src/pages/community.astro:78, 2f0e846)
L-133: fixed (site/src/components/HeroInner.astro:32, b2efd46)
L-134: fixed (site/src/components/HeroInner.astro:40, 53f02d4)
L-135: fixed (site/src/components/WaxRoomFeed.astro:35, 25cd5e9)
L-136: fixed (site/src/pages/extra-training-fun.astro:47, d3987f5)
L-137: fixed (site/src/components/PhotoStrip.astro:110, 78efa1e)
L-138: skipped (contract-only music-glyph exception already recorded in DESIGN.md v2; no code change)
L-139: skipped (contract-only FactStack clarification already recorded in DESIGN.md v2; no code change)
L-140: skipped (contract-only TripEntry clarification already recorded in DESIGN.md v2; no code change)
L-141: fixed (site/src/components/LiveConditions.astro:200, 7621d6b)
L-142: fixed (site/src/styles/global.css:419, cc7e080f)

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

- Update the review harness's `home-wax-feed` action to target the closing chapter instead of the document bottom. The larger L-053 CTA now places the populated Wax Room row above that viewport crop.

## test/build

- `npm run check`: `- 5 hints`
- `npm run build`: `18:32:16 [build] Complete!`
- `npm run test:refinement`: `ℹ duration_ms 993.063346`
- `npm run test:sponsors`: `ℹ duration_ms 50.764182`
- `npm run test:fallback`: `ℹ duration_ms 3503.350268`
