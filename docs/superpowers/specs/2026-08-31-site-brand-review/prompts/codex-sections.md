you are implementing one workstream of a brand consistency, elevation, and de-slop pass on twincitiesskiclub.org, the Twin Cities Ski Club marketing site: Astro 7 static site + Tailwind 4 under site/ in this repo. you are working in a git worktree on branch brand/sections, branched from site/brand-review. commit on this branch; never merge, never push, never touch other branches, never touch main. do not stop or start docker containers.

## your workstream: sections
page and component structure: HeroHome, HeroInner, SectionBand, MissionPanel, SeasonsGrid, CTAStrip, Footer, PhotoMosaic, CoachEntry, SponsorWall, TripsTable, WaxRoomFeed, WaxEntry, LiveConditions.astro markup (not its client script), and site/src/pages/*.astro. the home fold was judged the strongest screen on the site; start from the current fold and change only what the ledger rows say. you start in parallel with the other workstreams but will be asked to rebase onto their merged result and retake screenshots before your final pass.

## the contract (read in full, first)
DESIGN.md at the repo root is the v2 contract. its "Theme" section names the two scenes the site reads for. docs/superpowers/specs/2026-07-18-marketing-copy-refresh-design.md holds the voice rules. every change you make must move the site toward these.

## your ledger rows
these are the only changes you may make. each row cites the contract clause it implements.

### L-008
- sources: [SP-1, MO-1, GD-1, GM-1]
- surface: home / hero, all states / desktop, tablet
- kind: drift
- severity: P1
- contract: "The text block sits in a face-free zone at 390, 768, and 1440; the zone may change side or column by breakpoint; when no crop clears a face, the text block moves, not the photo."
- evidence: site/src/components/HeroHome.astro:51 (`object-[center_15%] max-md:object-[60%_15%]`), :60-73 (bottom-left text block); home-hero-desktop.png (headline across the left skier's forehead, subline across her eyes, button on her mouth), home-hero-tablet.png (her face under "Twin Cities"), home-hero-mobile.png (clean)
- observation: at 1440 the 4:3 source is width-bound, so horizontal `object-position` does nothing and her face (y 35-65% of the source) sits inside every vertical window; the july focal fix could only ever clear 390. at 768 the frame is height-bound so a horizontal shift works. the desktop gestalt proposed a vertical shift or a source crop; neither clears a face that spans the middle third of the image. sections and motion lenses both concluded the text block must move; the sections lens's grid placement keeps the left-to-right reading and the page gutter, so it is adopted over right-alignment.
- proposal: keep the photo, scrim, and type. at `lg+` put the content block on the 12-col grid starting at column 5 (`lg:grid lg:grid-cols-12` on the frame's inner container, content `lg:col-start-5 lg:col-span-8`), which lands the headline at x≈500 over empty trail with the other three faces above y=530; at 72 to 96px the headline still fits one line. at `md` only, `md:max-lg:object-[100%_15%]` so the height-bound crop drops her off the left edge while the right-hand skier stays in frame above the text; fall back toward `72% 15%` if his shoulder crops. keep the mobile value. verify at 390, 768, 834, and 1440 before and after.
- workstream: sections
- status: open


### L-009
- sources: [GD-15, GM-20, SP-16]
- surface: coaches / default / all
- kind: elevation
- severity: P1
- contract: "Site-width 12-col grid: photo `md:col-span-4 aspect-square` (the native shape, attention-cropped), text `md:col-span-7 md:col-start-6`, top-aligned so the slot never towers over the bio. ... Under `md`: a 240px square portrait beside the name, then the bio."
- evidence: site/src/components/CoachEntry.astro:7-11 (comment: kj's source is soft), :56-76 (`max-w-6xl`, `md:col-span-5 aspect-[4/5]`); coaches-default-desktop.png (first portrait soft at 427x534, 400px of empty paper beside it), coaches-default-mobile.png (pixelated at 342 css px)
- observation: the head coach's upscaled portrait is the first image on the coaching page, rendered at the largest size on the site, and reads as a broken image to a normal visitor. the 4:5 crop is manufactured from a square source and leaves each entry 60 percent empty on the right. the entries also sit on their own 1152px axis at x=168.
- proposal: CoachEntry moves to `max-w-site` on the 12-col grid: photo `md:col-span-4 aspect-square` with `fit="cover" position="attention"`, text `md:col-span-7 md:col-start-6 self-start`. under `md`: `grid-cols-[15rem_1fr]` with a `max-w-60 aspect-square` portrait beside the name, stacking under 360px. the smaller slot puts kj's source at or above 1x and the softness drops below notice. the replacement photo and the entry order are rob's (L-039). no pull quotes: none exist and none may be invented.
- workstream: sections
- status: open

## P2


### L-050
- sources: [CO-4, SP-7, GM-17, GD-6]
- surface: home / open, wax-feed / all
- kind: drift
- severity: P2
- contract: "Home is drenched navy with two paper moments: the mission panel and the closing chapter (wax room feed plus sponsors). Every other band on home is navy. Paper bands are never adjacent."
- evidence: index.astro:103-123 (MissionPanel, then `<SectionBand variant="paper" seam="Our sponsors">`), WaxRoomFeed.astro:22 (`bg-paper`); home-open-desktop.png, home-wax-feed-desktop.png (584px of paper with two seams before the coral rule), home-open-mobile.png (a 197px paper strip wedged between the wall and the cta)
- observation: home has up to three paper bands and, with entries, two adjacent ones, which is the alternation the theme rejects; the sponsor strip is the one place on home that feels added rather than composed. the color lens and desktop gestalt proposed sponsors on navy inside paper logo plates; the sections lens and mobile gestalt proposed one closing paper chapter. decided by the theme: paper is a deliberate moment, and the kwik trip jpeg needs paper honestly; a logo-plates-on-navy row reads as ad slots. one chapter.
- proposal: WaxRoomFeed becomes the closing chapter: `seam="Wax room"`, up to three WaxEntryRows, a hairline, then `seam="Our sponsors"`, the two logos on one row (`max-h-10` on mobile, left-aligned) and one `.link-inline` closer; delete the separate sponsors SectionBand call in index.astro. with no entries the chapter is the sponsor row alone. home then runs navy, paper, navy, navy, paper, navy.
- workstream: sections
- status: open


### L-051
- sources: [CO-6]
- surface: about, community, racing, dry-tri, extra-training-fun, coaches, sponsors, trips, wax-room, wax-entry, 404 / all / all
- kind: elevation
- severity: P2
- contract: "The compact conditions strip carries the same coral live dot as the prominent strip, before the first venue."
- evidence: LiveConditions.astro:89-105 (compact variant: no `[data-updated]`, no coral anywhere); about-open-desktop.png, coaches-default-desktop.png
- observation: ten of eleven routes show two of the three identity colors, and the signature device on inner pages has no live indicator, so a visitor cannot tell a live report from a stale one.
- proposal: a leading `●` (aria-hidden, `text-coral`, `.label-caps` size) before the first venue in the compact markup, keyed to the same `:not([data-updated-at])` rule as L-048 so it is `paper/75` unless live. one coral per inner page, inside the budget.
- workstream: sections
- status: open


### L-052
- sources: [CO-7, CS-32, GM-10]
- surface: home, sponsors, extra-training-fun / all / all
- kind: drift
- severity: P2
- contract: "On navy, the home hero h1 and the CTAStrip h2 are mint; every other h2 and h3 on navy is paper. Mint otherwise carries live data, `.label-caps` labels, links, and CTA fills."
- evidence: PhotoMosaic.astro:132 (`text-paper`), SeasonsGrid.astro:91 (inherits paper), CTAStrip.astro:61 (`text-mint`), sponsors.astro:43 (`text-mint` h2) and :52 (`text-mint` h3s), extra-training-fun.astro:40 (`text-paper`); home-open-desktop.png, sponsors-default-mobile.png
- observation: headings on navy are mint in three places and paper in two. the color lens read v1 literally (mint for headings); both gestalts and the components lens read the site (paper headings are calmer beside the mint data of the strip). decided by the july posture and the theme's "photographs as the moments of light": mint stays punctuation, two mint moments per page.
- proposal: sponsors impact h2 becomes `text-paper`; its item h3s stay mint as the band's accent is wrong too, so they become paper with mint `.label-caps` if a label is needed; mosaic and season h2s stay paper; hero h1 and CTAStrip h2 stay mint. write the rule into SectionBand's navy variant so the next band does not guess.
- workstream: sections
- status: open


### L-053
- sources: [SP-3, GD-5 (split), GM-11, SP-28, SP-8]
- surface: home / open / all; dry-tri, about / default / all
- kind: elevation
- severity: P2
- contract: "Same-surface neighbors share one gap owned by the incoming section; the outgoing band drops its bottom padding (`flush="bottom"`). Seam-to-content gap is one value (2rem). The mission panel sits in navy on both sides (`band` above and below)."
- evidence: home-open-desktop.png (dues line to the "Beyond practice" seam about 210px: `pb-28` + `pt-16` + `py-6`), home-open-mobile.png (150px), dry-tri-default-desktop.png (course ledger to prose 190px), about.astro:47-51 (photo `mt-10` + wrapper `py-12` + band `pt-28`: 160px), MissionPanel.astro:15 (80px navy above the panel, 0 below), CTAStrip.astro:58-59 (80px, the thinnest band on home closing the page)
- observation: where two same-surface sections meet, both paddings render and the seam arrives after a hole larger than the hero's text block. the mission panel reads attached to the seasons band; the cta strip is thinner than the sponsors band above it.
- proposal: using L-022's scale: home bands `band-lg` with seasons `flush="bottom"`; mosaic and the closing chapter `band`; MissionPanel `band` on both sides; CTAStrip `rhythm="lg"` on home and `"md"` elsewhere; inner bands `band` with prose columns `band-sm`; dry-tri course `flush="bottom"`; about's photo band drops `mt-10`. target gap from a band's last row to the next seam: 96px on home, 64px on inner, at desktop.
- workstream: sections
- status: open


### L-054
- sources: [SP-5 (split), GD-13 (split), CS-31 (split)]
- surface: about, community, racing, dry-tri, extra-training-fun, coaches, sponsors, trips, wax-room / all / desktop
- kind: elevation
- severity: P2
- contract: "The reading column sits left-aligned on the 12-col grid (columns 1 to 8) capped at `max-w-prose`; no centered `max-w-3xl/4xl/5xl/6xl` wrappers."
- evidence: about-open-desktop.png (h1 at 104, prose at 360, seasons h2 at 360, cells at 160), coaches-default-desktop.png (entries at 168), sponsors-default-desktop.png (wall at 248, disclosure at 80), trips-populated-desktop.png (table at 296); live census of left edges: about six, community seven, sponsors eight
- observation: the masthead is left-aligned, the prose is centered like a blog, and every page adds a width of its own; below the masthead the inner pages could be any astro starter with a nice palette.
- proposal: every page mounts prose through ProseColumn (L-044) on columns 1 to 8; CoachEntry, SponsorWall, TripsTable, and the sponsors wrappers move to `max-w-site`; delete every `max-w-3xl/4xl/5xl/6xl mx-auto`. verify: one left edge per page at 1440 for the h1, the first seam, the prose, and the footer.
- workstream: sections
- status: open


### L-055
- sources: [SP-6, CS-20, SP-17, GD-19 (split)]
- surface: sponsors / default / all
- kind: slop
- severity: P2
- contract: "`<SectionBand>` ... Props: `seam` (rendered through Seam; becomes the h2 when no heading is passed), optional `heading`, `rhythm` (`sm` / `md` / `lg`), `flush`." and "h2, long-form ... | `.type-h2-longform`"
- evidence: sponsors.astro:43,46,78,81,87-104,89,92,100,107-111 (three hand-built h2s with SectionBand's class string, `max-w-[56ch]`, `max-w-[62ch]` x2, `max-w-[52ch]`, a nested section with a hand-rolled `mt-20 md:mt-28 pt-12 border-t` seam, the disclosure in a bare `pb-8` div whose `max-w-7xl` sits on the inner p so it lands at x=80); sponsors-default-desktop.png
- observation: the page a sponsor judges the club by is the one page that ignores its own components: three 48px display h2s at one volume, four content widths, and a paragraph that lines up with nothing.
- proposal: three SectionBands (`seam="Sponsor impact"` navy, `seam="Partner recognition"` paper, `seam="What comes next"` paper) each with the `heading` prop; impact h2 `.type-h2`, recognition and priorities `.type-h2-longform` so the page has a loud, a medium, and a quiet band; measures `max-w-prose` / `max-w-prose-narrow`; both item lists as Ledgers (L-040); the disclosure as a `.type-caption text-slate` line inside the last band's column. the sponsors tests check copy order and mobile text size, not markup.
- workstream: sections
- status: open


### L-056
- sources: [GD-20, GM-24]
- surface: sponsors / default / all
- kind: elevation
- severity: P2
- contract: "A ruled row per tier at site width: tier label in the seam voice at left, logos left-aligned in the row, sized by tier ... Two sponsors fill one row with dignity. Not tiles, not centered."
- evidence: SponsorWall.astro:41-73 (`items-center justify-center` under sm, `max-w-5xl`); sponsors-default-desktop.png (two logos in 1440px of paper under an indented heading), sponsors-default-mobile.png (centered logos on a left-aligned page, kwik trip at 96px the heaviest object on the page)
- observation: two logos read as a wall with two bricks, centered on a page where everything else is left-aligned, and the red kwik trip block outweighs the club's own headline.
- proposal: SponsorWall renders a ruled row per tier (`border-y hairline`), tier label `.seam` at left, logos `items-start justify-start` at every width, `max-h-16` under `sm` and `max-h-24` from `sm`, on `max-w-site`.
- workstream: sections
- status: open


### L-057
- sources: [SP-9, GD-28, CS-33]
- surface: home, about / seasons grid, all states / all
- kind: elevation
- severity: P2
- contract: "Hairline cells with vertical padding only (text sits on the seam's axis); ... On paper (about) the same with navy names and mint-deep labels, `headingLevel="h3"`, opened by the same `seam="Seasons"` as home."
- evidence: SeasonsGrid.astro:89 (`p-8 md:p-10` on every cell), :121 (dues row `px-8 md:px-10`); about.astro:51 (`heading="Seasons"`, no seam) vs index.astro:104 (`seam="Seasons"`); home-open-desktop.png (seam at 120, "Fall / Winter" at 160), home-open-mobile.png (64px of a 342px measure lost to inset), about-open-desktop.png (a 48px h2 and no seam on the only band that does that)
- observation: each cell is inset on all sides like the ghost of a card, so the copy misaligns with every other left edge; the same section opens with an 11px seam on home and a 48px h2 on about.
- proposal: cells `py-8 md:py-10`, second cell `md:pl-10`, first `md:pr-10`, px-0 on mobile with the grid gap as the hairline; dues line drops its px; about mounts `<SectionBand variant="paper" seam="Seasons">` with `headingLevel="h3"` and no h2.
- workstream: sections
- status: open


### L-058
- sources: [SP-10, TY-24, CO-16, CS-26, GM-28, GD-22]
- surface: wax-entry / default / all
- kind: drift
- severity: P2
- contract: "The conditions snapshot is a ruled `dl` (structural hairline top and bottom, three cells, `.label-caps` labels in mint-deep, values in ink); no fill, no radius."
- evidence: WaxEntry.astro:62-82 (`bg-paper-card p-4 rounded-md` with three `text-xs uppercase tracking-wide` labels); wax-entry-default-desktop.png, wax-entry-default-mobile.png
- observation: the one rounded tinted slab on the site sits on the most editorial page, directly above a hairline-ruled layout that never uses a box anywhere else. six reviewers flagged it; the mobile gestalt would set the labels sentence-case slate, the others keep the seasons-dl label voice. the `.label-caps` voice wins for consistency with the season fact rows and the trail report.
- proposal: `<dl class="mt-6 border-y hairline py-4 grid sm:grid-cols-3 gap-6">`, `dt` in `.label-caps text-mint-deep`, `dd` in `.type-body text-ink`; drop `bg-paper-card` and `rounded-md`.
- workstream: sections
- status: open


### L-059
- sources: [SP-14, GD-18, MO-14, GM-21]
- surface: racing / default / all
- kind: elevation
- severity: P2
- contract: "A group never leaves an empty cell; odd counts get a spanning lead tile. Below `md`, a strip runs full-bleed or 1 + n" and "Every `object-cover` image has a deliberate focal point at both viewports"
- evidence: racing.astro:73-85 (`grid-cols-2 md:grid-cols-5 gap-px` inside the 720px column, `aspect-[3/4]`, no `object-position` on four of five); racing-default-desktop.png (five 144px tiles), racing-default-mobile.png (an empty gray sixth cell that reads as a failed image)
- observation: the only photography below the masthead is a row of thumbnails locked inside the reading column, and on a phone the wrapper's hairline color paints an orphan cell.
- proposal: through PhotoStrip (L-106): the strip breaks to `max-w-site` (five across at about 232px at 1440, or 3 + 2 with the birkie start at 2x); below `md` the first photo spans both columns at `aspect-[3/2]` so five fill 1 + 4; skijor-race keeps `82% center`, the other four get `object-[center_30%]`.
- workstream: sections
- status: open


### L-060
- sources: [SP-15, GM-22, CS-19]
- surface: dry-tri / default / all
- kind: elevation
- severity: P2
- contract: "A perimeter border around a photo group; photo groups separate with hairline gaps only." and "optional caption line in slate below the group"
- evidence: dry-tri.astro:17-21 (`label: 'Roll' | 'Ride' | 'Run'` computed and never rendered), :35-57 (`grid-cols-3 gap-px bg-ink/10 border border-ink/10`, `aspect-[4/5]`); dry-tri-default-mobile.png (three 110px tiles in a box), dry-tri-default-desktop.png
- observation: the roll/ride/run triptych is the only framed photo group on the site, stays three-across at 110px on a phone, and throws away the leg names it already computes.
- proposal: through PhotoStrip: drop the outer border, keep `gap-px` on the structural hairline, render each label as a `figcaption` in `.label-caps text-mint-deep` under its photo; below `md` run the three legs full-bleed (`-mx-[var(--gutter)]`) at `aspect-[3/4]` so each is about 130px edge to edge.
- workstream: sections
- status: open


### L-061
- sources: [SP-18, CS-35, GD-21 (split), GM-26 (split), GM-27 (split)]
- surface: trips, wax-room / empty / all
- kind: elevation
- severity: P2
- contract: "An empty collection renders one ruled placeholder row in the same Ledger the populated state uses, with one or two plain sentences in the club voice and one `.link-inline`; never a bare paragraph, never a promised cadence the site has not kept, never an invented schedule."
- evidence: wax-room/index.astro:19-20 (`<p class="text-slate">No entries yet.</p>`), TripsTable.astro:21-26 (the ruled placeholder, the good example); wax-room-empty-desktop.png (one line in 550px of paper), trips-empty-mobile.png (the column header hidden on mobile)
- observation: both empty states are production today. the trips page has a shape; the wax room has three words. the mobile gestalt proposed three static rows of the usual race calendar for trips; that presents a hope as a schedule and is rejected under voice rule 6 (see `## rejected`).
- proposal: the wax room index mounts a Ledger with one placeholder row (copy L-036) and a `.link-inline`; TripsTable's placeholder becomes the same Ledger row (copy L-035) and its header row shows on mobile as a single ruled line.
- workstream: sections
- status: open


### L-062
- sources: [MO-12]
- surface: community / mosaic (dense layout) / desktop, mobile
- kind: drift
- severity: P2
- contract: "Orientation-aware spans (a portrait source never gets `col-span-2`), face-aware square crops (sharp `position: attention`), `object-[center_25%]` for portrait sources in landscape slots"
- evidence: PhotoMosaic.astro:63-72 (index-cycled `sizeClasses`), :168-177 (`object-cover`, no `object-position`); community-default-desktop.png (dry-tri-rider in a 2:1 slot shows handlebars and no face; night-practice loses its outer faces in a square; rollerski-treats clips a head; techno-corner is 60% sky)
- observation: the size pattern is `i % 8` with no knowledge of the source, so portrait photos land in wide slots with the face cropped out and five-wide selfies lose people in squares. these are the cropped heads the july round closed on the community page, moved down into the wall.
- proposal: in PhotoMosaic.astro (build-time, not the client): skip wide slots for sources with `height > width` and advance to the next landscape source (`grid-flow-row-dense` keeps the wall flush); square tiles pass `width`, `height=width`, `fit="cover"`, `position="attention"` as CoachEntry and dry-tri already do; portrait sources in remaining landscape slots get `object-[center_25%]`. acceptance: read every tile at 390 and 1440; no face touches an edge.
- workstream: sections
- status: open


### L-063
- sources: [MO-13, GD-31]
- surface: home / mosaic (composed layout) / all
- kind: drift
- severity: P2
- contract: "composed side tiles are `4/3` on mobile, never forced square" and "the lead tile's crop set deliberately"
- evidence: PhotoMosaic.astro:154-158 (`max-md:aspect-square` on the two side tiles), :168-177; home-open-mobile.png (night-practice: a face cut at the edge), home-open-desktop.png (the 2x2 lead tile is 40% parking lot)
- observation: on a phone the composed side tiles are forced square, so someone in the five-wide selfie is always cut; on desktop the lead tile's top 40 percent is a parking lot while the table and faces sit in the bottom half.
- proposal: `max-md:aspect-[4/3]` on the composed side tiles (every home source is 4:3 or 3:2); with L-007 the side tiles include techno-corner (3:4), which takes the portrait rule from L-062; the lead slot gets `object-[center_65%]` via the existing order-based lead selection (a per-photo focal field is a schema change and out of scope).
- workstream: sections
- status: open


### L-064
- sources: [GM-18, GD-17, CS-22]
- surface: community / default / all
- kind: elevation
- severity: P2
- contract: "Mobile keeps rhythm with 2x1 tiles every fourth position ... Always opens with a Seam and an h2 (on community too)."
- evidence: PhotoMosaic.astro:63-72 (every span class is `md:`), :123 (`!heading && 'pt-20'`); community-default-mobile.png (22 identical squares, 2150px of scroll, no heading), community-default-desktop.png (an 80px bare navy stripe above the grid)
- observation: on a phone the wall degrades to a camera roll with no name, and on desktop it starts as an unlabeled navy block that reads as a rendering gap.
- proposal: mobile spans in the size cycle (`max-md:col-span-2 max-md:aspect-[3/2]` on indexes 1 and 6 of each eight); community.astro passes a seam and heading (strings in L-105); when no heading is passed the section starts flush or with the rule-only Seam, never an empty `pt-20`.
- workstream: sections
- status: open


### L-065
- sources: [CS-27, GD-7]
- surface: home / dryland / desktop
- kind: drift
- severity: P2
- contract: "the venue cells hide and the strip collapses to a single dateline, `Trail report · Dryland season · Birkie fever 98.6°`" and "No orphan rule." and "Cells separate with the row hairline drawn on each venue cell's right edge (so hidden cells take their rule with them)."
- evidence: LiveConditions.astro:76 (`md:border-l md:border-mint/15 md:pl-4` on the fever button), LiveConditions.client.ts `renderQuiet` (hides venue cells, inserts `[data-dryland-label]`; sacred); home-dryland-desktop.png (a lone vertical rule at the strip's left edge in an 80 percent empty band)
- observation: production shows this state for six months a year and it opens with a broken-looking rule beside one cell in an empty grid.
- proposal: css only: rules move to the venue cells' right edge (`md:border-r hairline-soft md:pr-5` on `[data-location]`), the fever button drops its left rule and padding; `[data-live-conditions]:has([data-dryland-label])` switches the prominent grid to a single-line flex dateline (label, "Dryland season", fever reading) about 40px tall. server-rendered names stay for no-js visitors.
- workstream: sections
- status: open


### L-066
- sources: [GD-2]
- surface: home / all / desktop
- kind: elevation
- severity: P2
- contract: "At `lg` the hero fills the first viewport below the nav and strip (`calc(100svh - nav - strip)`, minimum 540px); the fold ends on the hero's bottom edge."
- evidence: HeroHome.astro:87-96 (`height: 74svh`), live measurement: hero 249 to 915 in a 900px viewport, strip 172px
- observation: nav plus strip take 249px, the hero gets 651, and the fold cuts the hero 15px above its bottom edge.
- proposal: `.hero-frame { height: calc(100svh - var(--chrome-h)) }` at `lg` with the 540px minimum kept, where `--chrome-h` is set from the nav and strip heights; trim the strip from 172 to about 150px (`pb-3` on the grid, `min-h-8` to `min-h-4` on the wax line once L-124 moves feels-like to its own line).
- workstream: sections
- status: open


### L-067
- sources: [GM-13, SP-20]
- surface: home / mobile-nav / mobile
- kind: elevation
- severity: P2
- contract: "The logo lockup top-left (same 145x22 mark as the nav), six 24px links, the CTA pinned bottom. No conditions strip (the strip is one mount per page and already sits under the nav)."
- evidence: MobileNavPanel.astro:7-40; home-mobile-nav-mobile.png (close button, six centered links, cta pinned bottom, nothing at the top)
- observation: for as long as the panel is open the visitor is on a page with no name. the mobile gestalt also wanted the compact trail line inside the panel; the client assumes one mount per page (InnerPageLayout comment), so a second strip would break the announcer. v1's pinned-strip clause is struck.
- proposal: render the nav's logo svg top-left of the panel at the nav's size; no strip.
- workstream: sections
- status: open


### L-068
- sources: [GM-14]
- surface: about / all states / all
- kind: elevation
- severity: P2
- contract: "Mounted at the bottom of home, about, and sponsors; every page that explains joining ends with it."
- evidence: about.astro:51-53 (the page ends with the seasons band); about-open-mobile.png
- observation: the page that explains who joins ends without a registration strip in any of the three states.
- proposal: mount `CTAStrip` after the seasons band on /about with the same state props as home (`rhythm="md"`).
- workstream: sections
- status: open


### L-069
- sources: [CS-37, SP-19, GM-29 (split)]
- surface: shared components / all / all
- kind: drift
- severity: P2
- contract: "Components ... The first table is the primitives every other component composes; a page never hand-builds one of these patterns." (and the rewritten site components table)
- evidence: HeroInner.astro:27,44-55, MissionPanel.astro:15-16, SeasonsGrid.astro:102-115, PhotoMosaic.astro:143-148, CoachEntry.astro:2-11, WaxRoomFeed.astro:22, Footer.astro, InnerPageLayout.astro:51-53, MobileNavPanel.astro, LiveConditions.astro:14-19,70-86; no `<TripEntry>`, no lucide import
- observation: eleven rows of v1's component table described decisions that were reversed on purpose (most with a comment saying why), and none of the shipped replacements were in the contract, so every reviewer re-litigated accepted work. the built footer (brand, nav in header order, contact) and the compact strip under the nav are better than v1's footer strip.
- proposal: contract only, done in v2: the component table rewritten to the shipped site plus the primitives; TripEntry deleted. no code change.
- workstream: sections
- status: open


### L-070
- sources: [TY-31, CO-9, SP-26, MO-19, CS-38, GM-30, GD-25]
- surface: og image / default / all
- kind: elevation
- severity: P2
- contract: "One default share card for the site ... a consented club photograph (the sunset skate practice) with the hero's functional bottom scrim ... and the logo lockup ... bottom-left at about 240px wide, 48px from the left and bottom edges. No headline type in the image ... `BaseLayout` always sets `og:image:width`, `og:image:height`, `og:image:alt`, and `twitter:image`."
- evidence: site/public/og/og-default.jpg (1200x630, sunset skate practice, no mark, no navy, no mint); BaseLayout.astro:24,57-66 (single default, no width/height/alt, no twitter:image); wax-room/[slug].astro:23-27 (per-entry card, the pattern)
- observation: seven reviewers: the share card is an anonymous sunset in a slack unfurl next to three other clubs. five proposed the lockup over a scrim, two a navy band, one a hero-photo recrop with per-page derivation. decided by the theme's sponsor scene: the mark is what matters, the scrim is the hero's own grammar, and the sunset photo is the club's warmest image (kept; the motion lens's point that it appears nowhere on the site is noted for rob). per-page derivation from masthead photos is deferred to a later round.
- proposal: regenerate og-default.jpg once (sharp or a one-off script, no gemini): same crop, the hero scrim over the lower 45%, the nav logo svg in mint tracks and paper letters at 240px, 48px from the left and bottom; jpeg quality 85, under 200KB; confirm the front row's faces sit inside the center 60% vertically. BaseLayout adds `og:image:width` 1200, `og:image:height` 630, `og:image:alt` (the masthead alt or the site description), and `twitter:image`. confirm the source has a CONSENT.md row (it shares a source with the retired home-hero.jpg).
- workstream: sections
- status: open


### L-071
- sources: [GM-5, TY-28, CO-23]
- surface: home / hero, soon / all
- kind: drift
- severity: P2
- contract: "Subline `.type-lede` in `paper`; dates line (coming soon only) `.type-caption` in `paper/75`."
- evidence: HeroHome.astro:63 (`text-base md:text-lg text-paper/85`), :73 (`text-xs md:text-sm text-paper/60`); home-soon-mobile.png, home-soon-desktop.png, home-hero-tablet.png
- observation: the registration dates render at 12px and 60% over a photograph in the state where they matter most, and the subline is the lowest-alpha text on the page over the one background that is not a token.
- proposal: subline `.type-lede text-paper max-w-prose-narrow`; dates line `.type-caption text-paper/75`, seated in the scrim's dense zone.
- workstream: sections
- status: open

## P3


### L-121
- sources: [TY-19]
- surface: racing, dry-tri, trips, wax-room, home (wax feed, seasons) / all / all
- kind: drift
- severity: P3
- contract: "Dates, times, bylines, and credits are the caption role: slate on paper, paper/75 on navy, `tabular-nums`, sentence case, never uppercase or tracked."
- evidence: racing.astro:57 (`text-mint-deep text-sm tracking-wider uppercase`), dry-tri.astro:66 (same, on start times), TripsTable.astro:41, WaxRoomFeed.astro:41, wax-room/index.astro:25, SeasonsGrid.astro:90; racing-default-desktop.png (six dates reading as six eyebrows)
- observation: the same datum, a date, is an uppercase tracked mint-deep label on two pages and a sentence-case slate caption on three others.
- proposal: `.type-caption` on every date, time, and byline; racing.astro:57 and dry-tri.astro:66 lose uppercase, tracking, and mint-deep. the Ledger (L-040) carries this by default.
- workstream: sections
- status: open


### L-122
- sources: [TY-21, GM-29 (split), GD-26 (split)]
- surface: footer / all / all
- kind: slop
- severity: P3
- contract: "Three columns: the logo lockup (the nav svg at 120px) plus a one-line description at `max-w-prose-narrow`; ... contact and credits in `paper/75`. Link rows `min-h-10`."
- evidence: Footer.astro:29 (`font-display font-bold uppercase text-[13px] tracking-[0.08em] text-mint`), :30 (`max-w-xs`), :36-46 (44px link rows, credits at `paper/50`); home-open-mobile.png (a 677px footer, mostly air)
- observation: the footer wordmark is the display cut, uppercase, 13px, tracked, bold: four decisions the cut was not designed for and a fourth wordmark treatment across the site; on a phone the footer is mostly air and its best line ("All photos by club members.") is at 50%.
- proposal: the nav logo svg at 120px wide in place of the text wordmark (one mark everywhere); description `.type-body max-w-prose-narrow`; link rows `min-h-10 gap-y-0` through `.link-nav`; credits `paper/75`.
- workstream: sections
- status: open


### L-123
- sources: [TY-22]
- surface: all inner pages / compact conditions strip / all
- kind: elevation
- severity: P3
- contract: "Compact variant (every inner page, directly under the nav): one line per venue: coral live dot, venue name `.label-caps` as the report link when a source exists, temperature Archivo 700 0.875rem `tabular-nums`, wax text `.type-caption`; no display cut."
- evidence: LiveConditions.astro:27 (`text-xs` on the whole strip), :95 (`tracking-widest uppercase text-mint`), :96 (`font-display` at 12px); about-open-desktop.png, about-open-mobile.png
- observation: the compact strip mixes three voices in one 12px line and the bulky display cut at 12px just reads bolder; on a phone this is the first line of every inner page.
- proposal: venue `.label-caps`, temperature Archivo 700 `.type-caption tabular-nums`, wax `.type-caption`; mobile line height so the single venue line clears 44px (L-049 handles the link itself).
- workstream: sections
- status: open


### L-124
- sources: [TY-23, SP-25]
- surface: home / hero, live conditions / tablet
- kind: drift
- severity: P3
- contract: "feels-like `.type-caption` on its own line under the temperature ... Grid: `grid-cols-2 md:grid-cols-3 lg:grid-cols-5` (Theo, Hyland, fever at `md`; all five at `lg`)"
- evidence: LiveConditions.astro:39 (`grid-cols-2 md:grid-cols-5`), :51-54 (feels-like beside the temperature in a flex row); home-hero-tablet.png (feels-like wraps, wax labels wrap in four of five cells, the strip is the tallest element above the hero)
- observation: at 768 five cells share 720px and every detail line wraps, exactly at the width the july round added as a check.
- proposal: feels-like moves to its own `.type-caption` line (`whitespace-nowrap`); `md:grid-cols-3 lg:grid-cols-5` with elm and telemark `max-lg:hidden`; the mobile rule (Theo only) unchanged.
- workstream: sections
- status: open


### L-125
- sources: [TY-26]
- surface: home, extra-training-fun, dry-tri, 404 / all / all
- kind: drift
- severity: P3
- contract: "Every band has a heading element; SectionBand renders its seam as the h2 when no heading prop is passed and as a span when one is. One h1 per page, no skipped levels. The prominent conditions strip carries an sr-only h2 "Trail report"."
- evidence: SectionBand.astro:27-34 (seam is a span), index.astro:104,115 (no heading on the seasons and sponsors bands), extra-training-fun.astro:35,76, dry-tri.astro:60, 404.astro:55 (a 14px h2)
- observation: the home outline is h1 then the season h2s; "Trail report" and "Our sponsors" have no heading; on /404 an h2 is 14px.
- proposal: SectionBand renders `<h2 class="seam">` when no heading is passed; LiveConditions gets an sr-only h2; 404 per L-126.
- workstream: sections
- status: open


### L-126
- sources: [TY-32, GD-24 (split), CP-17 (split)]
- surface: 404 / default / all
- kind: drift
- severity: P3
- contract: "The 404 page has one display heading: the masthead h1 ... then a `.label-caps` kicker `404 · Page not found`, one Button (`Back to home`, on-paper recipe), and one Ledger of three destinations under an h3 `Try one of these`"
- evidence: 404.astro:41 (a sixth kicker style, tracked but not uppercase), :42 (a 48px display h2), :55 (a 14px h2); 404-default-desktop.png (three shouts for one message)
- observation: three headlines for one message and a 48px h2 beside a 14px h2. the desktop gestalt would fold the kicker into the subhead; the kicker carries the only "404" on the page and stays as a data label.
- proposal: kicker `.label-caps text-mint-deep`; delete the h2 and its paragraph; the button (L-043) moves up under the kicker; destinations as a Ledger under `h3.type-h3`. strings are L-034.
- workstream: sections
- status: open


### L-127
- sources: [CO-12]
- surface: all / all / all
- kind: drift
- severity: P3
- contract: "The nav logo's `fill` attributes are the one literal exception ... they are the resolved token hex (`#9EF9BE` tracks, `#FBFAF8` letters)."
- evidence: Nav.astro:17 (`fill="#aaf0c1"`), :29 (`fill="#fbfbfa"`), favicon.svg:3 (`#9ef9be`, the true token)
- observation: the logo's tracks are v1's stale reference hex, twelve units of red and nine of green from the mint the headline beside it uses; the favicon was generated from the real tokens and does not match the nav mark.
- proposal: `fill="#9EF9BE"` and `fill="#FBFAF8"`, still as attributes per the june rationale.
- workstream: sections
- status: open


### L-128
- sources: [CO-21]
- surface: home, about / open / all
- kind: elevation
- severity: P3
- contract: "the open-registration note carries a coral dot only while registration is open"
- evidence: SeasonsGrid.astro:96 (open note `font-semibold text-mint`, indistinguishable from the fee and labels around it); home-open-mobile.png
- observation: on the seasons card mint means "label", so an open season does not read as open; the trail report trains the visitor to read a coral dot on the same page.
- proposal: when open, prefix the note with an aria-hidden coral `●` at `.label-caps` size; the text stays. coral on home: live stamp, one or two season dots, cta rule, at most four. on paper (about) the dot is a non-text glyph and passes.
- workstream: sections
- status: open


### L-129
- sources: [SP-21, CS-40 (split)]
- surface: about, community, racing, 404 / masthead band / all
- kind: drift
- severity: P3
- contract: "Optional full-bleed photo band directly under the masthead: `aspect-[16/5]`, min 230px, max 420px, `object-cover` with a deliberate `object-position` per photo." and "a structural hairline below"
- evidence: HeroInner.astro:27 (`border-y border-ink/15`), :44-56 (`h-[230px] md:h-[280px]`); about-open-desktop.png (a 5:1 letterbox at 1440)
- observation: the june round accepted photo bands under the masthead and an ink hairline rather than v1's navy rule; both are right and v1 was stale. the band is a fixed 280px at every desktop width, so the team photo has no room at 1440.
- proposal: `aspect-[16/5] min-h-[14.375rem] max-h-[26.25rem]` (tokens `band-photo-min` / `band-photo-max` in tailwind.config.ts) instead of fixed heights; contract row updated in v2.
- workstream: sections
- status: open


### L-130
- sources: [MO-15, GD-33]
- surface: about / masthead band / desktop
- kind: elevation
- severity: P3
- contract: "Masthead photo bands: `aspect-[16/5]`, min 230px, max 420px, with a per-page `object-position` set by reading the source (about `center 58%`, community `center 46%`, 404 `center 60%`)."
- evidence: about.astro:36 (`center 40%`); about-open-desktop.png vs about-open-mobile.png; site/src/assets/images/photos/team-banner.jpg
- observation: at 1440 the band shows the heads and none of the "TCSC" banner the members are holding, the thing that makes the photo the club's. the desktop gestalt read the top row as trimmed and proposed 30%; the motion lens measured the source (window 38-73% at 58% keeps every back-row head with 4% margin and shows the banner). the measured value is adopted, with the taller band from L-129 giving it room.
- proposal: `photoPosition="center 58%"`; verify at 1440 that no back-row head touches the top edge, and step toward 46% if one does.
- workstream: sections
- status: open


### L-131
- sources: [MO-16]
- surface: 404 / masthead band / desktop
- kind: elevation
- severity: P3
- contract: "Masthead photo bands: `aspect-[16/5]`, min 230px, max 420px, with a per-page `object-position` set by reading the source (about `center 58%`, community `center 46%`, 404 `center 60%`)."
- evidence: 404.astro:36 (`center 72%`); 404-default-desktop.png (flat snow, a texture strip) vs 404-default-mobile.png (the corridor and trees)
- observation: at 1440 the band shows y 62-77% of a portrait photo: flat snow with faint corduroy, which reads as the abstract background the contract bans.
- proposal: `photoPosition="center 60%"` (tree line meeting the trail at desktop, still corridor at mobile).
- workstream: sections
- status: open


### L-132
- sources: [MO-17]
- surface: community / masthead band / desktop
- kind: elevation
- severity: P3
- contract: "Masthead photo bands: `aspect-[16/5]`, min 230px, max 420px, with a per-page `object-position` set by reading the source (about `center 58%`, community `center 46%`, 404 `center 60%`)."
- evidence: community.astro:66 (`center 52%`); community-default-desktop.png; canoe-social.jpg
- observation: the back-row heads sit within a few pixels of the top edge at 1440, the tightest masthead on the site.
- proposal: `center 46%` (3% headroom above the back row, the front row fully in frame). mobile unaffected.
- workstream: sections
- status: open


### L-133
- sources: [SP-22]
- surface: about / open / desktop
- kind: elevation
- severity: P3
- contract: "`.type-display-inner` h1 in navy on columns 1 to 8 (`text-balance`), `.type-lede` subhead in slate, optional FactStack on columns 10 to 12 behind a hairline"
- evidence: HeroInner.astro:29-30 (`md:col-span-7`, no `text-balance`); about-open-desktop.png ("About Twin Cities Ski / Club")
- observation: the headline column is 7 of 12 with columns 8 and 9 empty, so the longest inner h1 breaks on its last word.
- proposal: headline `md:col-span-8`, facts `md:col-start-10 md:col-span-3`, `text-balance` on the h1 (L-076).
- workstream: sections
- status: open


### L-134
- sources: [SP-23]
- surface: extra-training-fun / default / desktop
- kind: elevation
- severity: P3
- contract: "optional FactStack on columns 10 to 12 behind a hairline (bottom-aligned with two or more facts, top-aligned with one)"
- evidence: HeroInner.astro:34 (`self-end`); extra-training-fun-default-desktop.png (one fact floating mid-air beside the last line of a three-line subhead)
- observation: bottom alignment works with two or three facts; with one fact and a long subhead the stat floats far from the h1 it annotates.
- proposal: `class:list={[facts.length > 1 ? 'self-end' : 'self-start md:pt-3', ...]}` (inside FactStack's `align` prop once L-042 lands).
- workstream: sections
- status: open


### L-135
- sources: [SP-24 (split), GM-32 (split)]
- surface: home, community / mosaic, wax feed / all
- kind: drift
- severity: P3
- contract: "A seam is the section chapter name plus a hairline to the right edge, at most one per band and at most three per page; every seam carries a label."
- evidence: PhotoMosaic.astro:125-131 and WaxRoomFeed.astro:24-28 (seam without a label); seams per page: home 2 labeled + 2 unlabeled
- observation: the seam is used two ways, with a chapter label and as a bare hairline over an h2, which reads as two devices. numbered markers never shipped and are withdrawn from the contract.
- proposal: the mosaic on home passes `seam="Community"`, the wax feed `seam="Wax room"` (its chapter form is L-050), both through Seam (L-041).
- workstream: sections
- status: open


### L-136
- sources: [SP-27]
- surface: extra-training-fun / default / desktop
- kind: elevation
- severity: P3
- contract: "Photo pairs are 7/5 with mixed aspects." and "one photo-group grammar: flush tiles, hairline gaps (`gap-px` on the structural hairline color), no perimeter border"
- evidence: extra-training-fun.astro:51 (`grid gap-6 md:grid-cols-2`, both `aspect-[4/3]`); extra-training-fun-default-desktop.png
- observation: the two pool photos are the only 6/6 photo split on the site outside the seasons grid and the only photo group with 24px gutters.
- proposal: through PhotoStrip: `md:grid-cols-12`, first figure `md:col-span-7 aspect-[4/3]`, second `md:col-span-5 aspect-[4/5]` (the treat-crew photo is the portrait-friendly one), `gap-px` on the structural hairline, captions in the strip's caption row.
- workstream: sections
- status: open


### L-137
- sources: [SP-29]
- surface: community / default / desktop
- kind: elevation
- severity: P3
- contract: "Two-up grids prefer 7/5 or 5/7 splits rather than 6/6, except the seasons grid, where parity is the point." and "one photo-group grammar: flush tiles, hairline gaps (`gap-px` on the structural hairline color), no perimeter border"
- evidence: community.astro:72-83 (a 2x2 of equal `h-48 md:h-64` tiles inside the 720px column); community-default-desktop.png
- observation: a uniform grid on a page whose closing mosaic is the asymmetric version of the same idea.
- proposal: through PhotoStrip: first tile `col-span-2 aspect-video`, the remaining three at `aspect-square` in a three-column row, same `gap-px` grid, at the reading column's width on the grid.
- workstream: sections
- status: open


### L-138
- sources: [CS-24]
- surface: home / live conditions / desktop
- kind: drift
- severity: P3
- contract: "It carries a ♪ as its play affordance (aria-hidden, `md+` only)"
- evidence: LiveConditions.astro:80 (`♪` inside the fever label), LiveConditions.client.ts:248-263
- observation: the one glyph-as-icon in a label on the site; it carries information (the cell is a button) and v1 did not know about it.
- proposal: contract only, done in v2 as a recorded exception. no code change (the hover is L-049).
- workstream: sections
- status: open


### L-139
- sources: [CS-25]
- surface: home (mission panel), about, community, racing, dry-tri, extra-training-fun, coaches / all / all
- kind: drift
- severity: P3
- contract: "Stat boxes (tinted or bordered slabs) and mint-colored numbers. The FactStack is the sanctioned form." (banned list)
- evidence: MissionPanel.astro:9-13,19-28, HeroInner.astro:34-41, the june spec sections 4 and 5
- observation: the shipped stat stacks are not boxes and the numbers are navy, so they pass the letter of v1's ban, but v1 read as if they were forbidden and the next reviewer would propose removing them again.
- proposal: contract only, done in v2. no code change.
- workstream: sections
- status: open


### L-140
- sources: [MO-21]
- surface: trips / populated / all
- kind: drift
- severity: P3
- contract: "`<TripEntry>`: never built; `/trips` is a ledger with no photography until detail pages exist."
- evidence: TripsTable.astro (no image), content.config.ts:152-153 (`hero_photo` field), the fixture sets it; trips-populated-desktop.png
- observation: v1 described a component and an image the site does not have; the schema field is documented as unused (schema is a non-goal).
- proposal: contract only, done in v2. no code change.
- workstream: sections
- status: open


### L-141
- sources: [CP-27, GD-8]
- surface: home / unavailable / all
- kind: slop
- severity: P3
- contract: "Unavailable (fetch failed in season): the stamp reads `● Conditions unavailable` in `paper/75` and the cells show venue names only; the per-cell "No report" line is hidden by CSS so the message is said once."
- evidence: LiveConditions.client.ts `renderQuiet` (writes "No report" into every `[data-wax]`; sacred), home-unavailable-desktop.png (five "No report" cells under a stamp saying the same thing)
- observation: the client's own comment says cells go quiet instead of repeating the error, then repeats "No report" five times. the copy lens proposed a string change in the sacred file; the same result is a css rule at the call site, since the unavailable state is the only quiet state without `[data-dryland-label]`.
- proposal: in LiveConditions.astro's style block: `[data-live-conditions][data-filled='true']:not([data-updated-at]):not(:has([data-dryland-label])) [data-wax] { display: none; }` so cells show the venue name only; the stamp carries the message. no client change.
- workstream: sections
- status: open


### L-142
- sources: [GM-23]
- surface: extra-training-fun, all inner pages / default / all
- kind: elevation
- severity: P3
- contract: "A prose column that opens with an h2 zeroes that h2's top margin."
- evidence: extra-training-fun-default-mobile.png (about 100 css px between the masthead rule and "How it works"); InnerPageLayout content wrapper `py-12` plus the prose h2 top margin
- observation: the first prose element is an h2, so wrapper padding and prose margin stack into the largest gap on the page.
- proposal: `[&>h2:first-child]:mt-0` on the prose wrapper (inside ProseColumn, L-044); `band-sm` top when the masthead has no photo band.
- workstream: sections
- status: open

## recorded, no action

### CO-25
- surface: sponsors / default / all
- observation: the navy sponsor impact band holds to the accent budget (mint, paper, one photo) and the paper section below it passes too. recorded as the reference example in v2's accent-budget clause. no change.

## your method
follow /workspace/tcsc-trips/.agents/skills/awwwards-hero/SKILL.md (HeroHome, HeroInner), /workspace/tcsc-trips/.agents/skills/awwwards-sections/SKILL.md (everything below the hero; ignore pricing, bento, social-proof, stats patterns), and /workspace/tcsc-trips/.agents/skills/visual-redesign/SKILL.md.
read the whole skill file. run its pipeline: extract the target from the contract; gate (does the proposal serve the two scenes and the quiet register?); build; verify by screenshot; reject drift (anything in your diff that isn't a ledger row gets reverted). where the skill says to add a library, ignore it. where it says "louder", "massive", "cinematic", or "viewport-scale", translate to this brand: navy, mint, paper; hairline rules; near-zero motion.

## hard rules
- presentation only: astro component markup and classes, css in site/src/styles/global.css, tokens in site/tailwind.config.ts, copy strings under site/src/content and in the copy helpers. no js behavior changes. these files are sacred and must not be edited: site/src/lib/registrationState.ts, registrationFlip.ts, seasonData.ts, seasonSlug.ts, pageScrollLock.ts, samePageAnchor.ts, conditionsDisplayMode.ts, site/src/components/registrationCta.ts, LiveConditions.client.ts, PhotoMosaic.client.ts. also untouchable: site/src/content.config.ts, site/keystatic.config.ts, site/astro.config.mjs, render.yaml, anything outside site/ except your report and screenshots.
- no new dependencies. site/package.json and site/package-lock.json must be unchanged.
- every change cites a ledger id in its commit message. if you find something worth fixing that has no ledger id, do not fix it; add it to `## proposed` in your report.
- keep prefers-reduced-motion behavior: global.css collapses every animation and transition under the media query; do not add anything that escapes it.
- copy: no em dashes (use commas, periods, or middots), no exclamation points, sentence case, no invented facts. if a row's proposal contains an em dash, fix the proposal's punctuation, not the rule.
- no photo may be added, replaced, or generated. crop and object-position changes to existing photos are fine when a row asks.
- fixed identity: do not change the nine color token values, the two font families, or the Live Conditions strip's data or behavior.
- tests and build must pass from site/ before you report done: `npm run check`, `npm run build`, `npm run test:refinement`, `npm run test:sponsors`, `npm run test:fallback`. if a test asserts old copy or an old class that a ledger row changes, update the test and cite the row.
- do not edit anything under docs/superpowers/specs/2026-08-31-site-brand-review/ except your report and your after-screenshots.
- nothing fake under site/src/content: the harness copies fixtures in and out for you; if a build fails and leaves sisu-ski-fest.mdoc or first-snow-wax.mdoc behind, delete them before committing.

## verify by screenshot
the harness lives in scripts/brand-review (node_modules is linked into your worktree). the fixture api is shared on port 4499 (`curl -s http://127.0.0.1:4499/season/open | head -c 80`; if it is down, `nohup node fixture-api.mjs &` from that directory). to see your branch:
  cd scripts/brand-review
  node build-state.mjs open          # also: soon, closed, populated. rebuild after every change you want to see
  PORT=4404 node screenshot.mjs after-sections <stateIds you touched>
state ids are in scripts/brand-review/states.mjs; the matrix is docs/superpowers/specs/2026-08-31-site-brand-review/state-matrix.md. your port is 4404; other workstreams use other ports, so never use 4400 to 4405 for anything else. the before screenshots are on this machine at /workspace/tcsc-trips/docs/superpowers/specs/2026-08-31-site-brand-review/screens/before/ (the main checkout; screens are not committed). compare each after image against the before image with the same filename. look at them. if a change reads louder, busier, or more generic than before, it fails the gate: revert and try a quieter version. leave no serve-dist.mjs process running when done (`pkill -f "serve-dist.mjs .* --port 4404"`).

## report
write docs/superpowers/specs/2026-08-31-site-brand-review/sections-report.md:
- `# sections report`
- `## rows`: one line per ledger id: `L-nnn: fixed (<file:line>, <commit sha>)` or `L-nnn: skipped (<reason>)`.
- `## screens`: list of after screenshots you produced (they live in screens/after-sections/ in your worktree; screens are gitignored, so do not try to commit them).
- `## proposed`: anything you noticed that has no ledger id.
- `## test/build`: paste the last line of each of the five commands.
commit the report on your branch as the last commit.

work through the rows in ledger order (P1 first). commit small and often: one commit per row or per tightly related group, message `brand(sections): <what> (L-nnn)`.
