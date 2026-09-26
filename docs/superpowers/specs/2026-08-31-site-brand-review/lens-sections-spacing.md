# lens: sections + spacing

1. biggest problem: the home hero at 1440 and 768 sets "twin cities ski club", the subline, and the register button directly across the foreground skier's face. the july focal-only fix cleared 390 and nothing else, because the 4:3 source is width-bound at desktop and no object-position can move her.
2. second: the page column has five widths (1280, 1152, 1024, 896, 720) and two gutter systems (24px and 40px), so the left edge jitters by 16 to 144px between adjacent bands on every page. the contract's 1080px inner width exists nowhere in the code.
3. third: vertical rhythm is one value repeated (every band ends in pb-28) plus ad hoc page paddings (py-12, py-16, py-20, py-24). where two same-surface sections meet, the paddings stack into 160 to 212px holes (home seasons to mosaic, dry tri course to prose).
4. biggest opportunity: one spacing scale and one ledger component. eight hand-rolled ruled-row grids with seven column specs and four row paddings, plus nine hand-rolled prose wrappers, are where the site stops being one system. collapse them and the pages read as one ledger, which is the voice the june and july rounds chose.
5. overall: the section grammar (seam, hairline, ledger, asymmetric split) is right and mostly already here; what is missing is the discipline of one axis, one scale, one component per pattern, and one honest hero crop.

## findings

### SP-1
- surface: home / hero / desktop, tablet
- kind: drift
- severity: P1
- contract: "Headline set in mint over a navy-gradient bottom-vignette for legibility" plus the july round rule: "no face sits under the bottom text block at ~390px, ~768px, ~1440px"
- evidence: site/src/components/HeroHome.astro:51, :60-73; home-hero-desktop.png, home-hero-tablet.png, home-hero-mobile.png
- observation: at 1440x900 the foreground skier's face spans roughly x 180-480, y 560-900 of the viewport; "twin cities" crosses her forehead, the subline crosses her eyes, and the register button sits on her mouth. at 768 the same face sits under "twin cities". at 390 `max-md:object-[60%_15%]` crops her out and the fold is clean. the source is 2560x1920 (4:3), so at 1440 wide the picture is width-bound and object-position x has no effect; only the text block can move.
- proposal: keep the photo, scrim, and type. on lg+ put the content block on the 12-col grid and start it at column 5 (`lg:grid lg:grid-cols-12` on the frame, content `lg:col-start-5 lg:col-span-8`), which places the headline at x=~500 where the trail is empty and every other face is above y=530. at 72px the headline still fits one line (~740px in 856px). on md (768-1023) set `md:object-[100%_15%]` so the height-bound crop drops her off the left edge while the right-hand skier stays in frame above the text. keep the mobile value. verify at 390, 768, 1440 before and after.
- workstream: sections

### SP-2
- surface: all / all / all
- kind: drift
- severity: P2
- contract: "Vertical rhythm: sections breathe variably (96–144px y-padding on home, 64–104px on inner). Same-spacing-everywhere is monotony."
- evidence: site/src/components/SectionBand.astro:20-22 (pb-28 on every band, home and inner); MissionPanel.astro:15,17 (py-20 = 80 on home); PhotoMosaic.astro:123 (pb-20 = 80 on home); CTAStrip.astro:59 (py-20 = 80 on home); pages/about.astro:38, racing.astro:44,50, community.astro:68, extra-training-fun.astro:29, dry-tri.astro:73, trips/index.astro:12 (py-12 = 48 on inner); wax-room/index.astro:18 and WaxEntry.astro:53 (py-16 = 64); sponsors.astro:26 (py-20); 404.astro:38 (py-24 = 96)
- observation: desktop y-padding in use is 48, 56, 64, 80, 96, 112. home bands land at 80 (below the 96 floor) and 112; inner bands land at 48 (below the 64 floor) and 112 (above the 104 ceiling). the one value the contract wants varied, the band bottom, is the one value that never varies: every SectionBand ends in pb-28 regardless of page or what follows. the values are set per page, not from a scale.
- proposal: define the scale once in global.css as three utilities, `.band-y-s` (py 48 mobile / 64 desktop), `.band-y-m` (64 / 96), `.band-y-l` (80 / 128), and give SectionBand, MissionPanel, PhotoMosaic, WaxRoomFeed, CTAStrip a `rhythm: 's' | 'm' | 'l'` prop that maps to them. home uses m and l only; inner uses s and m only. delete the per-page py-12 / py-16 / py-20 / py-24 literals. the numbers 64/96/128 sit inside both contract ranges and are visibly different from each other.
- workstream: foundations

### SP-3
- surface: home / open / all; dry-tri / default / all; about / open / all
- kind: elevation
- severity: P2
- contract: "Vertical rhythm: sections breathe variably" and the sections skill: "Do NOT just stack sections with identical padding"
- evidence: home-open-desktop.png (dues line at y~748 of slice 2, next hairline at y~960: 212px of empty navy); SectionBand.astro:22 (pb-28) + PhotoMosaic.astro:125 (pt-16) + SeasonsGrid.astro:121 (py-6); dry-tri-default-desktop.png (course note to "2025" heading ~190px); dry-tri.astro:71,73; about.astro:47-51 (photo mt-10, wrapper py-12, band pt-28: 160px)
- observation: when a band is followed by a section on the same surface, the outgoing pb and the incoming pt both render, and the seam hairline arrives after a hole. on home the seasons band to the mosaic gap is 212px, larger than the hero's own text block. on dry tri the course ledger to the prose is 190px with nothing between.
- proposal: a same-surface adjacency rule: the incoming section owns the gap, the outgoing band drops its bottom padding. implement as a `flush: 'bottom'` prop on SectionBand (pb-0) used on home seasons and dry-tri course, and as a `pt` on the prose column that follows a band (band-y-s). target gap between a band's last row and the next seam hairline: 64px desktop on inner, 96px on home.
- workstream: sections

### SP-4
- surface: all / all / all
- kind: drift
- severity: P2
- contract: "Grid: 12-col with clamp(1rem, 4vw, 2rem) page gutter."
- evidence: site/src/styles/global.css:52-64 (`.safe-inline-6` 24px, `.safe-inline-6-10` 24/40px); HeroInner.astro:28 (px-6), SectionBand.astro:28,22 (px-10 at md), Nav.astro:11 (px-6), Footer.astro:27 (px-6), CTAStrip.astro:59 (px-6), MissionPanel.astro:17 (px-6), PhotoMosaic.astro:124 (px-10), WaxRoomFeed.astro:23 (px-10), sponsors.astro:107 (px-10 on the outer div, no padding on the p)
- observation: two gutter systems coexist. at 1440 the masthead, nav, footer, cta strip, and mission panel start at x=104; every SectionBand, the mosaic heading, the wax feed, and the sponsors strip start at x=120. the eye reads a 16px stagger between every adjacent pair down the page (about-open-desktop: "about twin cities ski club" at 104, "seasons" at 120, footer at 104). the contract's clamp gutter is not in the code at all.
- proposal: one gutter token in global.css, `--gutter: clamp(1.5rem, 4vw, 2.5rem)`, applied by a single `.gutter` utility that also folds in the safe-area max(). `.safe-inline-6` and `.safe-inline-6-10` become that one utility (keep the old names as aliases only until the pages are swept, then delete). every container uses `mx-auto max-w-site gutter`. verify by measuring the left edge of the h1, the first seam, and the footer wordmark on every page: one x value per viewport.
- workstream: foundations

### SP-5
- surface: all / all / desktop
- kind: drift
- severity: P2
- contract: "Max content width 1280px on home (the photo mosaic needs room); 1080px on inner pages (long-form prefers tighter measure)."
- evidence: grep counts: max-w-7xl x16, max-w-3xl x11, max-w-5xl x2 (sponsors.astro:26,108), max-w-4xl x1 (trips/index.astro:12), max-w-6xl x1 (CoachEntry.astro:56); coaches-default-desktop.png (masthead at x=104, coach entries at x=168); sponsors-default-desktop.png ("trailblazer partners" at x=248 under a masthead at 104); trips-populated-desktop.png (table at x=296)
- observation: five container widths, and inner pages use the home width (1280) for every band while the contract asks for 1080. the one-off widths are the ones that hurt: coaches is the only page whose main content starts at 168; the sponsor wall floats at 248 with its heading unanchored; the trips ledger sits at 296. none of these align with the masthead above them or the footer below.
- proposal: two widths, declared in tailwind.config.ts: `site` (1280) and `read` (720). the site column is the axis for mastheads, bands, seams, ledgers, footers. the read column is the centered long-form measure. then: CoachEntry moves to `max-w-site` with the split on the 12-col grid (see SP-16); the sponsor wall moves to `max-w-site` so "trailblazer partners" sits at x=104 under the h1; TripsTable moves to `max-w-site` as a ledger (it is a ledger, and the home wax feed, its sibling ledger, already runs at site width). update the contract: drop the 1080 figure, state the two widths.
- workstream: sections

### SP-6
- surface: sponsors / default / desktop
- kind: drift
- severity: P2
- contract: "Grid: 12-col with clamp(1rem, 4vw, 2rem) page gutter."
- evidence: site/src/pages/sponsors.astro:107-111; sponsors-default-desktop.png slice 3 (disclosure at x=80, every other line on the page at 104 or 120)
- observation: the disclosure paragraph's outer div carries `px-6 md:px-10` but the `mx-auto max-w-7xl` is on the inner p, so the p centers inside a 1360px box and lands 40px left of the band above it. a normal visitor sees a paragraph that does not line up with anything.
- proposal: move the disclosure inside the preceding paper SectionBand as its last child (`<p class="mt-10 text-base text-slate">`), or make the wrapper `safe-inline-6-10 mx-auto max-w-7xl px-6 md:px-10 pb-8` and the p unstyled for width. the band route also removes one more one-off wrapper.
- workstream: sections

### SP-7
- surface: home / wax-feed, open / all
- kind: drift
- severity: P2
- contract: "Home page is drenched navy from nav to footer. Photographs ... are the only paper appearances" and "MissionPanel ... Single moment of paper before the page returns to navy." and the theme: "through commitment to navy, not through paper alternation."
- evidence: pages/index.astro:103,114,115-123; WaxRoomFeed.astro:22 (bg-paper); home-wax-feed-desktop.png (wax feed paper, 144px of paper, then a second seam "our sponsors" on paper); home-open-desktop.png (mosaic navy, sponsors paper, cta navy)
- observation: the home page has three paper bands, not one: mission, wax feed (when populated), sponsors. with the wax feed live the sequence is navy, paper, navy, navy, paper, paper, navy, navy: two adjacent paper bands separated by a 144px gap and a fresh seam, which is exactly the alternation the theme section rejects. production today (no wax entries) is mission paper plus sponsors paper.
- proposal: two paper moments on home, by contract: the mission panel near the top and one closing paper band before the cta strip. merge WaxRoomFeed and the sponsors strip into that one band: the wax entries ledger, a hairline, then the sponsor logo row with "about our sponsors" on the same baseline (one seam, one pb). when there are no wax entries the band is just the sponsor row and keeps its place. delete the separate "our sponsors" SectionBand call in index.astro. update the contract clause on MissionPanel from "single moment" to "first of two".
- workstream: sections

### SP-8
- surface: home / open / all
- kind: elevation
- severity: P3
- contract: "MissionPanel ... A paper card embedded in the drenched-navy home page"
- evidence: site/src/components/MissionPanel.astro:15 (`bg-navy pt-14 md:pt-20`, no bottom padding); home-open-desktop.png (80px navy above the paper panel, 0px below)
- observation: the panel gets an 80px navy reveal above and none below, so it reads as attached to the seasons band rather than as a panel set into navy. the asymmetry is not doing anything.
- proposal: `py-14 md:py-20` on the navy wrapper (or `band-y-m` under SP-2), so the paper sits in navy on both sides. then SP-3 governs the seasons seam's own top gap.
- workstream: sections

### SP-9
- surface: home / open / all; about / open / all
- kind: elevation
- severity: P2
- contract: "SeasonsGrid ... No card decoration."
- evidence: site/src/components/SeasonsGrid.astro:89 (`p-8 md:p-10` on every cell), :121 (dues row `px-8 md:px-10`); home-open-desktop.png (seam at x=120, "fall / winter" at x=160); home-open-mobile.png (seam at 24, "fall / winter" at 56)
- observation: each season cell is padded 32px (mobile) or 40px (desktop) on all sides, so the copy is inset from the seam and every other left edge on the page. on mobile the inset costs 64px of a 342px measure. the inset is the ghost of a card: the cell has no background or border, so the padding only misaligns.
- proposal: cells carry vertical padding only (`py-8 md:py-10`); the second cell gets `md:pl-10` to clear the hairline and the first cell gets `md:pr-10`. on mobile both cells are px-0 and the hairline between them is the grid gap. the dues line drops its px too. the season name then sits on the seam's axis at 120 desktop and 24 mobile.
- workstream: sections

### SP-10
- surface: wax-entry / default / all
- kind: drift
- severity: P2
- contract: "Soft-tinted gray cards on paper. If a card needs definition, give it a 1px ink-15% rule or a clear background, not a gray drop-shadowed slab."
- evidence: site/src/components/WaxEntry.astro:62 (`bg-paper-card p-4 rounded-md`); wax-entry-default-desktop.png, wax-entry-default-mobile.png
- observation: the conditions snapshot is a rounded gray slab between the byline and the photo. it is the only rounded box on the site that is not a button, and on mobile it stacks into a 3-row slab.
- proposal: render it as a ruled row in the ledger grammar: `<dl class="mt-6 border-y border-ink/15 py-3 grid grid-cols-3 gap-6 text-sm">` with the small tracked label over the value in each cell, no background, no radius. it then matches the season fact lines and the trail report.
- workstream: sections

### SP-11
- surface: shared components / SectionBand paper-on-navy / all
- kind: slop
- severity: P3
- contract: "Card-shaped components anywhere on the home page." (banned) and the spec's de-slop list: dead CSS
- evidence: site/src/components/SectionBand.astro:3,15-22 (`rounded-xl px-8 py-12 md:px-16 md:py-20` paper card in navy); grep: no page passes `variant="paper-on-navy"` and no page passes `contentMax`
- observation: the paper-on-navy variant is a rounded paper card inside a navy band, which the banned list forbids on the only page it was meant for, and nothing uses it. `contentMax="narrow"` is also unused while nine pages hand-roll the same narrow column (SP-12).
- proposal: delete the paper-on-navy branch (variant type becomes `'navy' | 'paper'`) and the isCard padding string. keep contentMax and make the pages use it (SP-12). update the contract's SectionBand row to two variants.
- workstream: motion-components

### SP-12
- surface: about, community, racing, dry-tri, extra-training-fun, trips, wax-room / all / all
- kind: slop
- severity: P2
- contract: spec de-slop list: "one-off markup where a component exists, duplicated class strings, spacing values that differ by page for no reason"
- evidence: pages/about.astro:38, community.astro:68, racing.astro:44,50, extra-training-fun.astro:29, dry-tri.astro:73, trips/index.astro:12, wax-room/index.astro:18, components/WaxEntry.astro:53 (nine copies of `safe-inline-6 mx-auto max-w-3xl px-6 py-12` with four different padding variants); SectionBand.astro:11 (`contentMax: 'narrow'` unused)
- observation: the reading column is the most repeated block on the site and is never a component. each copy chooses its own py (48, 48 bottom only, 64) and one page swaps 3xl for 4xl. the prose class string `prose prose-lg max-w-prose text-ink` rides along in each copy.
- proposal: one `ProseColumn.astro` (or `SectionBand variant="paper" contentMax="narrow" rhythm="s"` with the prose wrapper inside) used by every page; the racing races section and the dry-tri prose use the same component with `flush` where SP-3 applies. delete the literals.
- workstream: motion-components

### SP-13
- surface: racing, dry-tri, extra-training-fun, community, sponsors, trips, home wax feed / all / all
- kind: slop
- severity: P2
- contract: spec de-slop list: "duplicated class strings"; sections skill: "Feature cards are NOT all the same height with the same padding and the same structure" inverted: the same structure should be the same component
- evidence: pages/racing.astro:54 (`py-4 ... sm:grid-cols-[10rem_1fr_1fr]`), dry-tri.astro:63 (`py-5 ... sm:grid-cols-[10rem_1fr_8rem]`), extra-training-fun.astro:38,79 (`py-6 ... md:grid-cols-[16rem_1fr]`), community.astro:111 (`py-5 ... sm:grid-cols-[minmax(14rem,18rem)_1fr]`), sponsors.astro:51 (`py-6 ... sm:grid-cols-[minmax(12rem,16rem)_1fr]`), components/TripsTable.astro:13 (`md:grid-cols-[8rem_1fr_minmax(8rem,auto)]`), WaxRoomFeed.astro:39 (`py-4 md:grid-cols-[8.5rem_1fr_auto]`), 404.astro:56-70 (a ninth, in a ul)
- observation: the ruled ledger row is the site's signature below-the-fold form, and it exists as eight hand-rolled grids with seven label-column widths (8, 8.5, 10, 12-16, 14-18, 16rem) and four row paddings (16, 20, 24, 40px), three divider tokens (ink/10, ink/15, mint/15), and two breakpoints (sm, md). a designer scrolling from racing to extra-training sees the label column jump from 160 to 256px and the rows tighten and loosen for no reason.
- proposal: one `Ledger.astro` + `LedgerRow.astro` pair: `Ledger` sets the divider (ink/10 on paper, mint/15 on navy), the row padding (py-5), and a `label` width prop with two values, `short` (8rem, for dates) and `long` (14rem, for names); `LedgerRow` takes `label`, `title`, `meta`, optional `note` and `href`. rebuild the eight sites on it. trips and the wax feed then look like the racing list, which is the point.
- workstream: motion-components

### SP-14
- surface: racing / default / desktop
- kind: elevation
- severity: P2
- contract: "No card-grid reflex." and "The photo mosaic itself is asymmetric"; sections skill: "One visual break section per page ... breaks the grid pattern"
- evidence: site/src/pages/racing.astro:73-85 (`grid-cols-2 md:grid-cols-5 gap-px` inside the 720px column, `aspect-[3/4]`); racing-default-desktop.png slice 1 (five 144x192px tiles)
- observation: the race photo strip is five thumbnail-sized portraits locked inside the reading column. it is the only photography on the page below the masthead and it reads as an afterthought row, not a break. on desktop the tiles are smaller than the trail report cells.
- proposal: let the strip break the column the way the mosaic and the dry-tri triptych do: move it out of the 3xl wrapper into a `max-w-site` (or full-bleed `gap-px`) row, five across at ~250px each with `aspect-[3/4]`, or 2 + 3 with the first two at `aspect-[4/5]`. keep gap-px and the hairline tint. on mobile keep grid-cols-2 with the fifth tile spanning both columns at `aspect-video` so the row does not end on an orphan.
- workstream: sections

### SP-15
- surface: dry-tri / default / all
- kind: elevation
- severity: P2
- contract: "Identical three-column card grids." (banned) and the sections skill mobile diff: "All multi-column layouts collapse to single column below 768px"
- evidence: site/src/pages/dry-tri.astro:35-57 (`grid grid-cols-3 gap-px bg-ink/10 border border-ink/10`, `aspect-[4/5]`); dry-tri-default-mobile.png (three 114px tiles inside a hairline box at 390); dry-tri-default-desktop.png (three 400px tiles inside a hairline box)
- observation: the roll/ride/run triptych is content-justified three-up, but the outer `border` turns it into a framed three-card block, and on mobile it stays three across at 114px each, too small to read the legs. it is also the only photo group on the site with a perimeter border.
- proposal: drop the outer border (hairline gaps only, like the mosaic). desktop stays three across at site width. below md run the three tiles as a full-bleed horizontal strip (`max-md:-mx-6` or the full-bleed section pattern from PhotoMosaic) at `aspect-[3/4]` so each leg is ~130px wide edge to edge, or stack them as a single column at `aspect-[4/3]`. the strip is the better answer because the three legs read as one event.
- workstream: sections

### SP-16
- surface: coaches / default / desktop
- kind: elevation
- severity: P3
- contract: "Asymmetric defaults. Two-up grids prefer 7/5 or 5/7 splits" and "CoachEntry ... Not a card."
- evidence: site/src/components/CoachEntry.astro:56-57,76 (max-w-6xl, `md:col-span-5` photo at `aspect-[4/5]`, `md:col-span-7` text); coaches-default-desktop.png (photo 460x575, text block ~250px tall, ~300px of empty paper under every bio)
- observation: the 5/7 split is right but the 4:5 portrait is much taller than the three-line bios, so each entry is 60 percent empty on the right. the code comment says the sources are square-ish, so the 4:5 crop is manufactured. combined with SP-5 the entries also sit on their own axis at x=168.
- proposal: site-width container on the 12-col grid: photo `md:col-span-4` at `aspect-square` (the native shape, which also kills the extra saliency crop), text `md:col-span-7 md:col-start-6`. the entry height then tracks the photo at ~410px and the bio, role, and credentials fill it. keep the steady left column (the code's argument against alternation holds).
- workstream: sections

### SP-17
- surface: sponsors / default / all
- kind: elevation
- severity: P3
- contract: sections skill: "Typography scale shifts ... Monotone scale = monotone page" and "Section headings vary in scale"
- evidence: site/src/pages/sponsors.astro:43,78,89 (three h2 at `text-4xl md:text-5xl`), :27 SponsorWall h2 at `text-2xl md:text-3xl`; sponsors-default-desktop.png
- observation: three consecutive bands each open with a 48px display h2, so the page has one register below the masthead: impact, recognition, priorities all shout at the same volume.
- proposal: impact stays at text-5xl (it is the pitch). recognition drops to text-3xl display with the photo carrying the band. priorities becomes a ledger heading at text-2xl semibold body family, since its content is a three-row ledger. the page then has a loud, a medium, and a quiet band.
- workstream: sections

### SP-18
- surface: wax-room / empty / all
- kind: elevation
- severity: P2
- contract: proposed: "empty states use the same grammar as the populated state: a ruled placeholder row, never a bare sentence" (the contract is silent; TripsTable already does this)
- evidence: site/src/pages/wax-room/index.astro:19-20 (`<p class="text-slate">No entries yet.</p>`); wax-room-empty-desktop.png (one gray line in a 720px column, then 200px of paper, then the footer); components/TripsTable.astro:21-26 (the ruled placeholder row)
- observation: this is the production state of the page today. a first-time visitor gets a masthead, one gray sentence, and a footer. the trips page in the same state ships a column-header row and a ruled placeholder with a contact link, which reads as a schedule waiting for entries.
- proposal: mirror TripsTable: a ruled row (`border-y border-ink/10 py-6 text-slate`) reading "no entries yet. the first field reports land with the first snow." plus the contact link, inside the same ledger the populated state uses. the contract already suggests the wax room "can lead with a pull-quote from a coach instead of a hero image"; if a real quote exists it goes above the row.
- workstream: sections

### SP-19
- surface: shared components / Footer / all
- kind: drift
- severity: P3
- contract: "Footer: Navy. Three columns: contact, navigation, social. Live conditions strip at the top (compact form)." and "LiveConditions ... secondary placement in the footer on inner pages."
- evidence: site/src/components/Footer.astro:26-48 (brand, nav, contact+social; no strip); layouts/InnerPageLayout.astro:51-53 (compact strip under the nav on every inner page); all footer screenshots
- observation: the built footer is brand / nav / contact, and the compact conditions strip lives under the nav, not in the footer. the built order is better (the wordmark leads, links read in nav order per the july fix, contact closes), and the strip under the nav is the right call ("a snow club leads with the snow"). the contract describes a footer that never shipped.
- proposal: no code change. contract rows for Footer and LiveConditions change to describe the built footer (three columns: wordmark + one-line description, two-column nav in header order, contact + credits) and the compact strip's placement under the nav on inner pages.
- workstream: sections

### SP-20
- surface: home / mobile-nav / mobile
- kind: drift
- severity: P3
- contract: "MobileNavPanel ... Live conditions strip pinned to the top of the panel."
- evidence: site/src/components/MobileNavPanel.astro:7-40; home-mobile-nav-mobile.png (close button, six links centered, cta pinned bottom, nothing at the top)
- observation: the panel has no conditions strip. it does not need one: the strip is already the first thing under the nav on every page, and a second mount would break the one-mount rule the client script assumes (InnerPageLayout comment). the empty upper half of the panel is the only cost.
- proposal: strike the pinned-strip clause from the contract. optionally use the empty top of the panel for the wordmark lockup at 24px so the panel reads as the brand's, not a bare list.
- workstream: sections

### SP-21
- surface: shared components / HeroInner / all
- kind: drift
- severity: P3
- contract: "<Hero> (inner): Paper background, ink display H1, slim navy ruled line below. No image (the page below has plenty)."
- evidence: site/src/components/HeroInner.astro:27 (`border-y border-ink/15`, not navy), :44-56 (optional photo band `h-[230px] md:h-[280px]`); about-open-desktop.png, community-default-desktop.png, racing-default-desktop.png, 404-default-desktop.png
- observation: the june round accepted photo bands under the masthead, and the rule is an ink/15 hairline, not navy. both are right and the contract is stale. separately, the band is a fixed 280px at every desktop width, so at 1440 it is a 5:1 letterbox; at 1920 it would be 7:1.
- proposal: contract row becomes: paper, ink display h1, optional stat stack behind a hairline, ink/15 hairline below, optional full-bleed photo band. code: the band uses `aspect-[16/5] max-h-[420px] min-h-[230px]` instead of fixed heights so it scales with the viewport and gives the team photo room at 1440 (~450px capped to 420).
- workstream: sections

### SP-22
- surface: about / open / desktop
- kind: elevation
- severity: P3
- contract: "Display H1 (inner pages) ... 4.5rem" and the hero skill gate: "Heading wraps to max 2-3 lines on desktop"
- evidence: site/src/components/HeroInner.astro:29-30 (`md:col-span-7`, no text-balance); about-open-desktop.png ("about twin cities ski / club")
- observation: the headline column is 7 of 12 with columns 8 and 9 empty, so the longest inner h1 breaks on its last word.
- proposal: headline column `md:col-span-8` (the facts keep `md:col-start-10 md:col-span-3`, leaving column 9 as the gutter) and `text-balance` on the h1 so any two-line wrap balances ("about twin cities / ski club").
- workstream: sections

### SP-23
- surface: extra-training-fun / default / desktop
- kind: elevation
- severity: P3
- contract: june round: facts "bottom-aligned in the right column with a left hairline"
- evidence: site/src/components/HeroInner.astro:34 (`self-end`); extra-training-fun-default-desktop.png (one fact at y~300 beside a headline at y~170 and a three-line subhead)
- observation: bottom alignment works with two or three facts and a one-line subhead. with one fact and a three-line subhead the single stat floats mid-air next to the last line of body copy, far from the h1 it annotates. new argument since june: the single-fact case did not exist then.
- proposal: keep `self-end` for two or more facts; for exactly one fact align to the h1 (`self-start md:pt-3`). implement as `class:list={[facts.length > 1 ? 'self-end' : 'self-start md:pt-3', ...]}`.
- workstream: sections

### SP-24
- surface: all / all / all
- kind: drift
- severity: P3
- contract: "SectionBand ... Takes optional numbered marker ("01 / Mission")" and "Numbered section markers ("01", "02") replace the previous uppercase-tracked-eyebrow pattern"
- evidence: site/src/components/SectionBand.astro:4-7,27-33 (the seam: tracked caps + hairline); PhotoMosaic.astro:125-131 and WaxRoomFeed.astro:24-28 (seam without label); seams per page: home 2 labeled + 2 unlabeled, sponsors 2, extra-training 2, community 1, dry-tri 1, about 0, racing 0
- observation: numbered markers never shipped; the seam did, and it is the site's section device. but it is used two ways: with a chapter label (seasons, our sponsors, the course) and as a bare hairline over an h2 (beyond practice, from the wax room). the mix reads as two devices.
- proposal: contract: replace the numbered-marker clause with the seam, defined as "small tracked caps naming the chapter plus a hairline to the right edge; the only allowed eyebrow form; at most three per page". code: every seam carries its label (mosaic on home passes `number="Community"` again, wax feed gets `seam="Wax room"`), and PhotoMosaic and WaxRoomFeed render the seam through SectionBand's seam markup instead of their own copies of it.
- workstream: sections

### SP-25
- surface: home / open / tablet
- kind: elevation
- severity: P3
- contract: "Four columns, equal width, separated by 1px mint-20% rules." (LiveConditions)
- evidence: site/src/components/LiveConditions.astro:39 (`grid-cols-2 md:grid-cols-5`); home-hero-tablet.png (140px cells, "feels 12°" and every wax label wrapping to two or three lines)
- observation: at 768 the prominent strip runs five cells across 720px. every detail line wraps and the fever cell's sentence breaks three times; the strip is the tallest element above the hero at tablet.
- proposal: `md:grid-cols-3 lg:grid-cols-5`, with elm and telemark `max-lg:hidden` (theo, hyland, fever at md; all five at lg). the mobile rule (theo only) is unchanged.
- workstream: sections

### SP-26
- surface: og image / default / all
- kind: elevation
- severity: P3
- contract: proposed: "the og image is a consented club photo with the wordmark in mint on a navy band along the bottom edge; faces stay inside the center 80 percent"
- evidence: site/public/og/og-default.jpg (1200x630, sunset ski group, no wordmark, no navy); BaseLayout.astro:24,63
- observation: the share card is a good photo with no brand on it. a sponsor pasting the link into slack sees a sunset and a url; nothing says tcsc. the contract has no og clause.
- proposal: add a 90px navy band along the bottom with the heritage wordmark in mint at left (the same svg the nav uses) and nothing else; recrop the photo above it so the front row of faces sits in the safe zone. keep it the only og image; the wax entry route already overrides per entry.
- workstream: sections

### SP-27
- surface: extra-training-fun / default / desktop
- kind: elevation
- severity: P3
- contract: "Asymmetric defaults. Two-up grids prefer 7/5 or 5/7 splits rather than 6/6."
- evidence: site/src/pages/extra-training-fun.astro:51 (`grid gap-6 md:grid-cols-2`, both `aspect-[4/3]`); extra-training-fun-default-desktop.png
- observation: the two pool photos are a 6/6 pair with identical aspect, the only 6/6 photo split on the site outside the seasons grid (where parity is the point).
- proposal: `md:grid-cols-12`, first figure `md:col-span-7 aspect-[4/3]`, second `md:col-span-5 aspect-[4/5]`, `gap-px bg-ink/15` instead of gap-6 so the pair matches the mosaic grammar. the treat-crew photo is the portrait-friendly one.
- workstream: sections

### SP-28
- surface: home / open / desktop
- kind: slop
- severity: P3
- contract: sections skill: "Do NOT just stack sections with identical padding"; DESIGN.md "CTAStrip ... Coral 3px top border"
- evidence: site/src/components/CTAStrip.astro:58-59 (`py-16 md:py-20`), Footer.astro:26 (`border-t border-mint/10`); home-open-desktop.png slice 3
- observation: the coral rule on the cta strip is right and present on both call sites. but the strip's 80px is below the home floor and the strip is visibly thinner than the sponsors band above it, so the page closes on its smallest band. (sponsors page, where 80 is inside the inner range, is fine.)
- proposal: folded into SP-2: CTAStrip takes `rhythm="l"` on home (128) and `rhythm="m"` on sponsors (96).
- workstream: sections

### SP-29
- surface: community / default / desktop
- kind: elevation
- severity: P3
- contract: "No card-grid reflex."
- evidence: site/src/pages/community.astro:72-83 (`grid grid-cols-2 gap-px bg-ink/15`, four `h-48 md:h-64` tiles inside the 720px column); community-default-desktop.png
- observation: the member cluster is a 2x2 of equal 360x256 tiles inside the reading column, the same shape at every breakpoint. it works, but it is a uniform grid in a page whose closing mosaic is the asymmetric version of the same idea.
- proposal: let the cluster use the mosaic's tile logic at small scale: first tile `col-span-2 aspect-video`, the remaining three at `aspect-square` in a three-column row (2 + 3 in the same gap-px grid). the cluster then rhymes with the mosaic below instead of competing with it.
- workstream: sections

## proposed contract changes

- layout: replace "Max content width 1280px on home; 1080px on inner pages" with "two container widths: `site` 1280px and `read` 720px; bands, mastheads, ledgers, and footers sit on `site`; long-form prose sits centered on `read`" (SP-5)
- layout: replace the gutter clause with "one gutter token, `clamp(1.5rem, 4vw, 2.5rem)`, applied by one utility; every container shares one left edge per viewport" (SP-4)
- layout: replace the vertical rhythm clause with a named scale, "three band rhythms, s 48/64, m 64/96, l 80/128 (mobile/desktop); home uses m and l, inner uses s and m; same-surface neighbors share one gap owned by the incoming section" (SP-2, SP-3, SP-28)
- color: change "Single moment of paper" (MissionPanel) to "two paper moments on home: the mission panel and one closing paper band (wax feed + sponsors) before the cta strip" (SP-7)
- components: SectionBand row: variants `navy | paper` only; drop paper-on-navy and the numbered marker; add the seam definition "small tracked caps naming the chapter plus a hairline to the right edge; the only eyebrow form; at most three per page; every seam carries a label" (SP-11, SP-24)
- components: Hero (inner) row: "paper, ink display h1 (col 1-8), optional stat stack behind an ink/15 hairline (col 10-12), ink/15 hairline below, optional full-bleed photo band at aspect 16/5 capped at 420px" (SP-21, SP-22)
- components: Hero (home) row: add "the text block never covers a face at 390, 768, or 1440; when the crop cannot clear a face, the text block moves, not the photo" (SP-1)
- components: Footer row: "navy; wordmark + one-line description, two-column nav in header order, contact + credits; no conditions strip" and LiveConditions row: "compact strip sits under the nav on inner pages" (SP-19)
- components: MobileNavPanel row: strike "Live conditions strip pinned to the top of the panel" (SP-20)
- components: add a Ledger row: "ruled rows, py-5, divider ink/10 on paper and mint/15 on navy, label column short (8rem) or long (14rem); every list of dated or named items on the site is a Ledger" (SP-13)
- new clause, empty states: "an empty collection renders a ruled placeholder row in the same ledger as the populated state, never a bare sentence" (SP-18)
- new clause, og image: "one consented club photo with the wordmark in mint on a navy band along the bottom edge; faces inside the center 80 percent" (SP-26)
- banned list: add "a perimeter border around a photo group; photo groups separate with hairline gaps only" (SP-15)
