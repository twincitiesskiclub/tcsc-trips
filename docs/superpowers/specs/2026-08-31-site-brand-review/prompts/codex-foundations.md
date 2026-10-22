you are implementing one workstream of a brand consistency, elevation, and de-slop pass on twincitiesskiclub.org, the Twin Cities Ski Club marketing site: Astro 7 static site + Tailwind 4 under site/ in this repo. you are working in a git worktree on branch brand/foundations, branched from site/brand-review. commit on this branch; never merge, never push, never touch other branches, never touch main. do not stop or start docker containers.

## your workstream: foundations
tokens, the type scale and its utilities, tracking, weights, line-height, spacing rhythm, dividers, and contrast fixes. you own site/src/styles/global.css and site/tailwind.config.ts, and per-surface class fixes that only change a token, scale step, or spacing value. if a row needs a new shared utility, add it to global.css under `@layer utilities` and use it at every call site the row lists.

## the contract (read in full, first)
DESIGN.md at the repo root is the v2 contract. its "Theme" section names the two scenes the site reads for. docs/superpowers/specs/2026-07-18-marketing-copy-refresh-design.md holds the voice rules. every change you make must move the site toward these.

## your ledger rows
these are the only changes you may make. each row cites the contract clause it implements.

### L-001
- sources: [CO-1, TY-30, CS-8 (split)]
- surface: community, racing, dry-tri, extra-training-fun, sponsors, wax-room, wax-entry / default / all
- kind: drift
- severity: P1
- contract: "secondary text on paper is `slate`, never `ink` at reduced opacity, and no text on paper uses an alpha below `/90`."
- evidence: site/src/pages/community.astro:122, racing.astro:69, dry-tri.astro:65, extra-training-fun.astro:81,85, sponsors.astro:81,92,100, wax-room/index.astro:38, WaxEntry.astro:99; community-default-mobile.png, sponsors-default-desktop.png
- observation: secondary body on paper is `text-ink/80` (4.09:1) and `text-ink/75` (3.43:1), both under aa for normal text; `text-ink/90` (6.67:1) passes but is a third way to say secondary. the contract already names slate (5.74:1) for this role. the july round fixed the same bug on navy and never swept paper.
- proposal: replace every `text-ink/80`, `/75`, and `/90` on text with `text-slate`; where the copy is primary (sponsors recognition body at `text-xl`) use `text-ink`. drop `opacity-90` from the SectionBand subhead. foundations adds the rule to global.css comments; the build guard (L-112) greps dist for `text-ink/`.
- workstream: foundations
- status: open


### L-002
- sources: [CO-2]
- surface: home, community / default, lightbox / all
- kind: drift
- severity: P1
- contract: "The ring color is decided by the nearest surface, not by a placeholder background on the focused element: `[data-photo-mosaic]` and the lightbox are in the surface map, and photo tiles use an inset mint ring (`outline-offset: -3px`) that reads over any photo."
- evidence: site/src/components/PhotoMosaic.astro:153 (`bg-paper-card` on the tile button), site/src/styles/global.css:78-84 (`.bg-paper-card` sets the ring to navy); home-open-desktop.png
- observation: every mosaic tile button carries `bg-paper-card` as a lazy-load placeholder, which flips the inherited ring to navy, drawn 2px outside the tile over navy gaps. a keyboard user tabbing 9 or 22 tiles sees no focus (1:1 against the 3:1 minimum).
- proposal: move `bg-paper-card` off the button onto an inner wrapper; add `[data-photo-mosaic]` to the focus surface map in global.css with `--focus-ring-color: mint`; give tiles `focus-visible:outline-offset-[-3px]`. remove the lightbox's inline `--focus-ring-color` override once `.bg-navy-deep` covers it (L-120).
- workstream: foundations
- status: open


### L-010
- sources: [TY-2, TY-17, GM-7 (split)]
- surface: shared components / all / all
- kind: slop
- severity: P2
- contract: "Type roles are defined once in `global.css` as `clamp()` utilities; no `text-*`, `leading-*`, or `text-[Npx]` utility appears on a type role at a call site."
- evidence: site/src/components/SectionBand.astro:38, pages/sponsors.astro:43,78,89 (the same `font-display font-semibold text-4xl md:text-5xl leading-[1.05]` string four times), PhotoMosaic.astro:132, CoachEntry.astro:79, HeroInner.astro:30, CTAStrip.astro:61, 404.astro:42; `leading-[1.05]` x7, `leading-tight` x5, `leading-[1.02]`, `leading-[1.0]`, `leading-[1.25]`, `leading-none`; global.css:99-105 (the only type rule defined once)
- observation: no clamp() exists anywhere. every heading is a hand-typed tailwind chain at its call site, heading line-height is set at eight values or not at all, and on a phone the section h2 renders at the same 36px as the page h1. visual-redesign names this "random values with no pattern" and "class string copied instead of a component prop".
- proposal: add the role utilities from the v2 scale table to global.css under `@layer utilities` (`.type-display`, `.type-display-inner`, `.type-h2`, `.type-h2-longform`, `.type-h3`, `.type-h4`, `.type-statement`, `.type-lede`, `.type-body`, `.type-caption`, `.type-stat`, `.label-caps`, `.seam`) with the clamp expressions, line heights, and weights the table gives; `text-wrap: balance` on the heading roles. replace every heading chain and delete every `leading-*` on a heading. L-011 through L-018 and L-072 through L-077 are the per-role sweeps.
- workstream: foundations
- status: open


### L-011
- sources: [TY-1, GD-26 (split)]
- surface: home, all inner pages / all / all
- kind: drift
- severity: P2
- contract: "The display cut is used on h1, h2, and the prominent conditions temperatures only; never on h3 or below, paragraphs, stat values, list rows, buttons, or labels."
- evidence: site/src/components/HeroHome.astro:61, MissionPanel.astro:18,22, SeasonsGrid.astro:91, PhotoMosaic.astro:132, LiveConditions.astro:52,83,96,102, CTAStrip.astro:61, Footer.astro:29, WaxRoomFeed.astro:31,44, TripsTable.astro:42, HeroInner.astro:37, community.astro:94; home-open-desktop.png; live census: about 12, community 14, coaches 13 display elements
- observation: `font-display` sits on 14 to 18 elements of the home page and 28 call sites site-wide: the mission paragraph, six stat values, trips rows, wax feed rows, the footer wordmark, and the compact strip temperatures all wear the display cut, so it stops reading as a moment. the desktop gestalt would keep it on stat values; the typography lens showed the wide cut at 16 to 24px just looks like bolder archivo. decided by the july posture (quiet ledger): stat values go to archivo.
- proposal: remove `font-display` from MissionPanel:18 and :22, HeroInner:37, TripsTable:42, WaxRoomFeed:44, Footer:29, LiveConditions:96 and :102, community.astro:94. home keeps the hero h1, the two season h2s, the mosaic h2, the cta h2, and the five prominent temperatures.
- workstream: foundations
- status: open


### L-012
- sources: [TY-3, GM-3]
- surface: home / hero, all states / all
- kind: drift
- severity: P2
- contract: "Display h1 (home hero) | `.type-display` | 3.0rem | 6.0rem | 0.95 | 700 | Display"
- evidence: site/src/components/HeroHome.astro:61 (`text-4xl sm:text-5xl md:text-7xl leading-[1.02]`); home-hero-desktop.png, home-hero-mobile.png, home-hero-tablet.png
- observation: the hero h1 renders 36px on a phone, 48 at 768, 72 at 1440 against 48 and 96, with lh 1.02 instead of 0.95. on a phone the club name is only 1.5x the 24px temperature above it and reads timid. at 96px "Twin Cities Ski Club" spans about 990px inside the 856px block L-008 gives it, so the headline wraps to two balanced lines at 1440; that is acceptable and `text-balance` handles it.
- proposal: `.type-display` on the h1 (`clamp(3rem, 1.6rem + 5.8vw, 6rem)`, lh 0.95, 700). the contract's display weight column reads 700 because PolySans BulkyWide ships as a single cut (global.css:26).
- workstream: foundations
- status: open


### L-013
- sources: [TY-5, GM-7 (split)]
- surface: all routes / all / all
- kind: drift
- severity: P2
- contract: "h2 (section) | `.type-h2` | 2.0rem | 3.0rem | 1.05 | 700 | Display" and "h2, long-form (markdoc h2, list titles, tier heads, season names on home) | `.type-h2-longform` | 1.75rem | 2.25rem | 1.1 | 700 | Display"
- evidence: SectionBand.astro:38 and sponsors.astro:43,78,89 (36/48px), CoachEntry.astro:79 (30/48), CTAStrip.astro:61 (30/36), WaxRoomFeed.astro:31 (30/36), racing.astro:51 (30), wax-room/index.astro:28 (24/30), SponsorWall.astro:65 (24/30), SeasonsGrid.astro:91 (24/30), 404.astro:42 (30/48), 404.astro:55 (14px h2); sponsors-default-desktop.png, racing-default-desktop.png, 404-default-desktop.png, about-open-mobile.png ("Seasons" as large as the h1)
- observation: h2 renders at six sizes across the site and at three sizes on /sponsors alone; on /404 a 48px h2 sits beside a 14px h2; on a phone the section h2 equals the h1. hierarchy is carried by position, not size.
- proposal: every section h2 (SectionBand, CTAStrip, CoachEntry name, mosaic) takes `.type-h2`; list and tier titles (wax index, wax feed heading, "Races", SponsorWall tier heads, SeasonsGrid on home) take `.type-h2-longform`; the 404 "Helpful destinations" becomes h3 (L-126). no h2 carries a size utility.
- workstream: foundations
- status: open


### L-014
- sources: [TY-7, TY-9, CS-5, GM-6, GM-31, GD-27, TY-8 (split)]
- surface: home, all inner pages, shared components / all / all
- kind: drift
- severity: P2
- contract: "Two uppercase specs only: `.seam` (0.75rem, tracking 0.18em, 600) and `.label-caps` (0.75rem, tracking 0.12em, 600). ... Data labels (dt labels, table heads, stat labels, venue names, the 404 kicker) share `.label-caps` and do not count as eyebrows. Decorative eyebrows stay banned. Uppercase is banned on headings, buttons, dates, and times." and "No type on the site is smaller than 0.75rem."
- evidence: LiveConditions.astro:36,50,78,95,101 (10px and 11px, tracking 0.18em and widest), SectionBand.astro:30, PhotoMosaic.astro:128, MissionPanel.astro:25, HeroInner.astro:38, SeasonsGrid.astro:109, Footer.astro:29 (13px, 0.08em, display), TripsTable.astro:16, racing.astro:57, dry-tri.astro:66, WaxEntry.astro:65,71,77, 404.astro:41; `text-[10px]` x2, `text-[11px]` x9, `text-[13px]` x2; home-open-desktop.png (18 tracked labels), home-open-mobile.png (14)
- observation: nine uppercase specs and fourteen arbitrary pixel sizes carry one device; the venue names in the trail report are 10px, the smallest type on the site, labeling the club's home venue. the mobile gestalt would drop caps from stat and dl labels entirely; the june round accepted small-caps labels on the season fact lines and stat stacks and the july round named "small-caps seams" as the ledger language, so the label form stays and the spec count drops to two. dates and times leave the caps register on every lens's reading.
- proposal: define `.seam` and `.label-caps` in global.css at 0.75rem per the contract; replace all seventeen sites; delete every `text-[Npx]`; the footer wordmark is handled by L-122, the 404 kicker by L-126, race dates and course times by L-121. contract floor: nothing below 0.75rem.
- workstream: foundations
- status: open


### L-015
- sources: [TY-10, TY-11]
- surface: home (seasons, cta, footer), community (ledger), extra-training-fun, sponsors, dry-tri, 404 / all / all
- kind: drift
- severity: P2
- contract: "Body | `.type-body` | 1.0rem | 1.0625rem | `--body-lh` | 400 | Archivo" and "`--body-lh` is set by the surface (`.bg-navy` and `.bg-navy-deep` 1.7, `.bg-paper` and `.bg-paper-card` 1.65) and consumed by `.type-body` and `.type-lede` (lede on navy 1.6); call sites never set leading."
- evidence: SeasonsGrid.astro:101,122, community.astro:122, extra-training-fun.astro:43,81, sponsors.astro:53,100, dry-tri.astro:65, 404.astro:66, CTAStrip.astro:62, Footer.astro:30, HeroHome.astro:63 (all tailwind 16px/1.5 or 1.625 defaults); global.css:37-43 (no desktop step)
- observation: nothing renders body at 17px on desktop, so desktop body is one pixel under the accessibility clause and 0.15 short on line-height, and no reversed body block reaches the +0.05 bonus; the seasons summary on navy, the block the clause was written for, is the tightest body on the site at 1.5.
- proposal: `.type-body { font-size: clamp(1rem, 0.96rem + 0.2vw, 1.0625rem); line-height: var(--body-lh, 1.65); }` and `.bg-navy, .bg-navy-deep { --body-lh: 1.7 } .bg-paper, .bg-paper-card { --body-lh: 1.65 }` in global.css, the same inheritance trick the focus ring uses; apply `.type-body` to every non-prose paragraph listed and delete per-call-site `leading-*`.
- workstream: foundations
- status: open


### L-016
- sources: [TY-13, GM-8, GD-4]
- surface: home / mission panel, all states / all
- kind: elevation
- severity: P2
- contract: "Statement (mission paragraph, about lede) | `.type-statement` | 1.375rem | 1.875rem | 1.3 | 500 | Archivo" and "the mission set as `.type-statement` in navy (Archivo, never the display cut)"
- evidence: site/src/components/MissionPanel.astro:18 (`font-display text-2xl md:text-3xl leading-[1.25]`); home-open-desktop.png (five lines of the wide cut at 30px with parentheses, hyphens, and periods falling back to archivo mid-line), home-open-mobile.png (nine to eleven lines at 24px); about.astro:39 sets the equivalent lede in archivo semibold
- observation: a 40-word paragraph in PolySans BulkyWide is the heaviest block on the site and it is body copy, mixing two faces because the display subset has no punctuation. the about page sets the same kind of lede in archivo, so the site has two lede voices. tracksmith sets its statements in the grotesque at medium weight and lets the photograph carry the warmth.
- proposal: `.type-statement` (Archivo 500, `clamp(1.375rem, 1.2rem + 0.9vw, 1.875rem)`, lh 1.3, navy, `max-w-statement` 44ch, `text-wrap: pretty`) on MissionPanel:18; the about founding paragraph takes the same role (L-075). the words are L-004.
- workstream: foundations
- status: open


### L-017
- sources: [TY-15, CS-9 (split)]
- surface: about, dry-tri, extra-training-fun, coaches, wax-entry, community, racing / all / all
- kind: drift
- severity: P2
- contract: "Markdoc headings are themed once in the typography theme (`h2` = display cut at `.type-h2-longform` values, `h3` = `.type-h3`, `h4` = `.type-h4`); pages use `prose`, never `prose-lg`, and never patch prose headings with arbitrary variants."
- evidence: site/tailwind.config.ts:43-63 (typography theme sets colors only), site/src/pages/about.astro:39 (`[&_h2]:font-semibold [&_h2]:tracking-tight`); about-open-desktop.png ("Who joins TCSC" at 27px archivo 600px from "Seasons" at 48px display), dry-tri-default-desktop.png ("2025" in the plugin's default weight)
- observation: markdoc headings inherit the plugin's archivo 700 at 1.5em and 1.25em while component h2s are in the display cut; about patches one of them with an arbitrary variant and dry-tri does not, so the same h2 renders two ways.
- proposal: theme `h2`, `h3`, `h4` once in `typography.DEFAULT.css` in tailwind.config.ts (font-family display, the long-form h2 clamp, `letter-spacing: -0.02em`, navy); delete the `[&_h2]` overrides on about.astro:39.
- workstream: foundations
- status: open


### L-018
- sources: [TY-27]
- surface: home, about / seasons grid, all states / all
- kind: elevation
- severity: P2
- contract: "registration note `.type-caption` 600 (coral dot while open) stacked under the fee below `sm`"
- evidence: SeasonsGrid.astro:96 (`text-[13px]` note, semibold mint when open, muted when closed); home-open-mobile.png, about-closed-desktop.png
- observation: the registration dates, the one line a returning member is looking for in august, are the smallest type in the card at 13px, wrapping to two lines on a phone under a 24px fee.
- proposal: `.type-caption` at 0.875rem 600 for the note; on mobile stack it under the fee on its own line (`flex-col sm:flex-row`). the fee stays 1.125rem.
- workstream: foundations
- status: open


### L-019
- sources: [CO-3, CS-13]
- surface: all / all / mobile (theme-color), all (literals)
- kind: drift
- severity: P2
- contract: "`navy` and `ink` are referenced through `theme()` (and the `theme-color` meta reads the resolved navy `#10213E`), never as literals."
- evidence: site/src/layouts/BaseLayout.astro:32 (`const themeColor = '#202A44'`), site/tailwind.config.ts:9 (navy resolves to `#10213E`), site/public/favicon.svg:2 (`#10213e`), site/src/styles/global.css:41-42 (raw oklch for navy and ink)
- observation: the `theme-color` meta is the contract's stale reference hex, sixteen units lighter than the real navy, so ios and android paint a visible two-tone seam at the top of every page against the `#10213E` nav; the favicon already uses the right value. global.css also writes navy and ink as literals under a comment that says the tokens are the single source.
- proposal: `themeColor` reads a `NAVY_HEX = '#10213E'` constant from a small `site/src/lib/brand.ts` (or the resolved palette); `html { background: theme(colors.navy); color: theme(colors.ink); }` in global.css.
- workstream: foundations
- status: open


### L-020
- sources: [CO-10]
- surface: all / all / all
- kind: drift
- severity: P2
- contract: "Any new text pairing is measured, not estimated, before it ships. Every text pair on every page passes WCAG AA."
- evidence: DESIGN.md v1 contrast table vs computed: mint/navy 12.83 (claimed 8), paper/navy 15.38 (14), ink/paper 18.04 (17), slate/paper 5.74 (7.2), coral/navy 6.48 (5.6); hex column `#202A44`, `#AAF0C1`, `#FF8FA3` vs resolved `#10213E`, `#9EF9BE`, `#FF7C8A`
- observation: five of six v1 figures were estimates and slate/paper was wrong in the dangerous direction; L-001 is the proof that a reviewer checking against the table passes pairings that fail.
- proposal: contract only, done in v2: the measured table with the alpha pairings in use, the resolved hex column, and the measure-before-ship rule. no code change; phase 3 verifies every pairing against the v2 table.
- workstream: foundations
- status: open


### L-021
- sources: [CO-13, CS-6]
- surface: all / all / all
- kind: slop
- severity: P2
- contract: "Structural (`.hairline`): `ink/15` on paper, `mint/20` on navy." and "Row (`.hairline-soft`): `ink/10` on paper, `mint/15` on navy." and "Two hairline weights per surface, and no other rule alpha"
- evidence: navy `/10`: Nav.astro:10, Footer.astro:26, LiveConditions.astro:23,27; navy `/15`: LiveConditions.astro:48,76, extra-training-fun.astro:36; navy `/20`: SectionBand.astro:24, SeasonsGrid.astro:75, PhotoMosaic.astro:129, sponsors.astro:49; paper `/10` and `/15` across community.astro:72,109, racing.astro:52,73, dry-tri.astro:36,61, 404.astro:56, TripsTable.astro:16,22,28; `ink/25` on 404.astro:63; `paper/30` on Lightbox.astro:31-32
- observation: rules use eight alphas; the `mint/10` chrome seams on nav, footer, and both strip edges measure 2.18:1 and the nav-to-strip-to-hero stack reads as one block on desktop. paper is already close to a two-level system.
- proposal: `.hairline` and `.hairline-soft` (border), `.rule` and `.rule-soft` (background), `.divide-hairline` in global.css switching by surface through an inherited custom property; nav, footer, and the strip move to the row weight (`mint/15`, 2.77:1); dry-tri's triptych aligns to `ink/15`; the lightbox controls adopt `.hairline` on navy-deep. link decoration alphas live in L-045.
- workstream: foundations
- status: open


### L-022
- sources: [SP-2, CS-30, GD-5 (split)]
- surface: all / all / all
- kind: drift
- severity: P2
- contract: "three band rhythms, defined once in `global.css` as `band-sm` (48/64px), `band` (64/96px), and `band-lg` (80/128px), mobile/desktop. Home uses `band` and `band-lg`; inner pages use `band-sm` and `band`. A page uses at least two of the three."
- evidence: SectionBand.astro:20-22 (`pb-28` on every band), MissionPanel.astro:15,17 (py-20), PhotoMosaic.astro:123-125, WaxRoomFeed.astro:26-29, CTAStrip.astro:59 (py-20), HeroInner.astro:28, CoachEntry.astro:56, Footer.astro:27, pages: py-12, pb-12, py-16, py-20, py-24; twenty-one distinct band paddings
- observation: desktop y-padding in use is 48, 56, 64, 80, 96, 112; home bands land below the 96 floor and inner bands land at 48 and 112, outside both ranges; the one value the contract wants varied, the band bottom, never varies. variety without a system is the same crime as monotony.
- proposal: three utilities in global.css, `.band-y-sm`, `.band-y`, `.band-y-lg` (with `-t` and `-b` halves) at 48/64, 64/96, 80/128; SectionBand, MissionPanel, PhotoMosaic, WaxRoomFeed, CTAStrip, HeroInner, CoachEntry, and Footer take a `rhythm` prop mapping to them; every page-level `py-N` literal becomes one of the three. which band gets which size is L-053.
- workstream: foundations
- status: open


### L-023
- sources: [SP-4, CS-10]
- surface: all / all / all
- kind: drift
- severity: P2
- contract: "one gutter token, `--gutter: clamp(1.5rem, 4vw, 2.5rem)`, applied by one `.gutter` utility that folds in the safe-area `max()`. Call sites never add `px-*` beside it. Every container shares one left edge per viewport (120px at 1440)."
- evidence: site/src/styles/global.css:52-64 (`.safe-inline-6` 24px, `.safe-inline-6-10` 24/40px, unlayered), 27 of 28 call sites also carry `px-6` or `px-6 md:px-10`; HeroInner.astro:28, Nav.astro:11, Footer.astro:27, CTAStrip.astro:59, MissionPanel.astro:17 (x=104 at 1440) vs SectionBand.astro:28, PhotoMosaic.astro:124, WaxRoomFeed.astro:23 (x=120); about-open-desktop.png
- observation: two gutter systems coexist, so the left edge staggers 16px between adjacent bands on every page, and the `px-*` beside every safe-inline class is dead (the unlayered rule beats it) and misleading.
- proposal: one `--gutter` token and one `.gutter` utility in global.css replacing `.safe-inline-6` and `.safe-inline-6-10` (keep the old names as aliases until swept, then delete); delete every `px-6` and `px-6 md:px-10` beside them; every container is `mx-auto max-w-site gutter`. verify by measuring the h1, first seam, and footer wordmark left edges on every page: one x per viewport.
- workstream: foundations
- status: open


### L-024
- sources: [CS-31, SP-5 (split), GD-13 (split)]
- surface: all / all / desktop
- kind: drift
- severity: P2
- contract: "one container, `max-w-site` (1280px), for every band, masthead, ledger, strip, and footer on every page. There is no separate inner-page width."
- evidence: grep: `max-w-7xl` x16, `max-w-3xl` x11, `max-w-5xl` x2 (sponsors.astro:26,108), `max-w-4xl` (trips/index.astro:12), `max-w-6xl` (CoachEntry.astro:56); live census of left edges at 1440: about six, community seven, sponsors eight
- observation: v1 named 1080 for inner pages; the code never used it and instead grew five widths. the components lens proposed adding a 1080 token; the sections lens proposed 1280 plus a centered 720 reading column; the desktop gestalt proposed one 1280 container with the reading column left-aligned on the grid. decided by the theme (one committed object, the eye finds a spine) and the ledger posture (the community 3/9 grid already does this): one width, no 1080, no centered reading column.
- proposal: `maxWidth: { site: '80rem', statement: '44ch' }` in tailwind.config.ts alongside the two prose measures; `.reading-column` (or ProseColumn, L-044) as `md:col-span-8 max-w-prose` on the 12-col grid; delete the `max-w-3xl/4xl/5xl/6xl mx-auto` wrappers. the per-page sweep is L-054.
- workstream: foundations
- status: open


### L-072
- sources: [TY-4, GD-14 (split)]
- surface: about, community, racing, dry-tri, extra-training-fun, coaches, sponsors, trips, wax-room, wax-entry, 404 / all / all
- kind: drift
- severity: P3
- contract: "Display h1 (inner mastheads, wax entry) | `.type-display-inner` | 2.5rem | 4.0rem | 1.0 | 700 | Display"
- evidence: HeroInner.astro:30 (`text-4xl md:text-6xl leading-[1.05]`), WaxEntry.astro:55 (`text-3xl md:text-5xl leading-tight`); about-open-desktop.png, wax-entry-default-desktop.png ("year (fixture)" wrapping)
- observation: inner h1 renders 36/60 at lh 1.05 and the wax entry h1 30/48 at 1.25, so the article title is the size of every other page's h2. a 72px h1 in the masthead cell would wrap three lines, which is why it drifted; the contract's desktop value drops to 4.0rem.
- proposal: `.type-display-inner` on HeroInner:30 and WaxEntry:55 with `text-balance`.
- workstream: foundations
- status: open


### L-073
- sources: [TY-6]
- surface: community, sponsors, about (seasons), 404 / all / all
- kind: drift
- severity: P3
- contract: "h3 | `.type-h3` | 1.375rem | 1.625rem | 1.2 | 600 | Archivo"
- evidence: community.astro:94 (`font-display font-semibold text-2xl`), sponsors.astro:52 (`text-lg text-mint`), :99 (`text-xl text-navy`), SeasonsGrid.astro:91 as h3 on /about (24/30 display)
- observation: h3 renders in the display cut at two sizes and in archivo at two others. the june round moved the community group heads to the display cut for presence; the 3/9 grid and the anchor photo carry the presence.
- proposal: `.type-h3` on all four; SeasonsGrid sizes the season name by `headingLevel` (`.type-h2-longform` when h2, `.type-h3` when h3).
- workstream: foundations
- status: open


### L-074
- sources: [TY-12, CS-43]
- surface: home (seasons, hero, cta, footer, wax feed), extra-training-fun, sponsors, 404 / all / desktop
- kind: drift
- severity: P3
- contract: "`max-w-prose` (62ch) on paper and `max-w-prose-narrow` (56ch) on navy are the only body measures; `.type-statement` caps at 44ch via `max-w-statement`. Arbitrary `ch` values and `max-w-xs/lg/xl` on text are banned."
- evidence: SeasonsGrid.astro:101 and extra-training-fun.astro:43 (`max-w-prose` on navy), sponsors.astro:46,81,92,100 (`max-w-[56ch]`, `[62ch]` x2, `[52ch]`), CTAStrip.astro:62 (`max-w-xl`), Footer.astro:30 (`max-w-xs`), 404.astro:42 (`max-w-lg` on an h2)
- observation: the two measure tokens exist and are bypassed by four arbitrary ch values and three tailwind sizes; navy bodies use the paper measure.
- proposal: `max-w-prose-narrow` on every navy body, `max-w-prose` on paper, `max-w-statement` on the mission; delete the arbitrary values; the 404 h2 drops its cap (`text-balance` does the job).
- workstream: foundations
- status: open


### L-075
- sources: [TY-16]
- surface: home (hero subline), about (founding lede), all inner mastheads, wax-entry / all / all
- kind: drift
- severity: P3
- contract: "Lede (masthead subhead, hero subline, wax lede) | `.type-lede` | 1.125rem | 1.25rem | 1.55 | 400 | Archivo"
- evidence: HeroInner.astro:31, about.astro:39 (`[&>p:first-child]:font-semibold text-xl md:text-2xl`), WaxEntry.astro:99, HeroHome.astro:63, SectionBand.astro:41
- observation: five lede treatments in five colors and line heights; the about lede also depends on the mdoc's first paragraph staying first.
- proposal: `.type-lede` on all five (slate on paper, paper on navy); the about founding paragraph takes `.type-statement` through a frontmatter `lede` field only if the schema allows it, else the first-child selector applies `.type-statement` instead of its own chain.
- workstream: foundations
- status: open


### L-076
- sources: [TY-18, GD-14 (split)]
- surface: about, sponsors, community, wax-entry / all / desktop
- kind: elevation
- severity: P3
- contract: "h1 and h2 carry `text-wrap: balance`; the statement carries `text-wrap: pretty`."
- evidence: HeroHome.astro:61 (the only `text-balance`); about-open-desktop.png ("About Twin Cities Ski / Club"), sponsors-default-desktop.png (three orphaned last lines), wax-entry-default-desktop.png
- observation: only the home h1 is balanced; inner h1s and section h2s leave one-word orphans.
- proposal: `text-wrap: balance` inside `.type-display-inner`, `.type-h2`, `.type-h2-longform`; `text-wrap: pretty` in `.type-statement`.
- workstream: foundations
- status: open


### L-077
- sources: [TY-29]
- surface: about, community, racing, dry-tri, extra-training-fun, coaches, wax-entry / all / all
- kind: elevation
- severity: P3
- contract: "Long-form body (markdoc via `prose`) | typography theme | 1.125rem | 1.125rem | 1.7 | 400 | Archivo"
- evidence: `prose prose-lg` on about.astro:39, community.astro:69, racing.astro:45, dry-tri.astro:74, extra-training-fun.astro:30, CoachEntry.astro:81, WaxEntry.astro:100; community-default-desktop.png (18px prose above a 16px ledger)
- observation: markdoc bodies are 18px at 1.78 and every other body is 16px at 1.5, so /community shows two body registers 200px apart; the 18px is right and should be the contract, the 1.78 is looser than anything else on the site.
- proposal: set the body size and line-height (1.125rem / 1.7) in the typography theme; plain `prose` at all seven call sites; ledger bodies take `.type-body` (L-015) so the two registers are by design.
- workstream: foundations
- status: open


### L-078
- sources: [CO-11, CS-41]
- surface: home / open, birkie-hover / all
- kind: drift
- severity: P3
- contract: "The four wax-band chip colors (`wax-green`, `wax-blue`, `wax-purple`, `wax-red`, L 0.62) are data colors defined in `tailwind.config.ts`: the color *is* the recommendation. They appear only on the wax chip, never as text or decoration."
- evidence: LiveConditions.astro:132-135 (four raw oklch values in a component style block, with a comment defending them)
- observation: the only raw color values outside the token files; the reasoning is right and the location breaks the single-source rule.
- proposal: move the four values into the `palette` object in tailwind.config.ts as `wax-green` etc.; render the chips with `bg-wax-green` and friends.
- workstream: foundations
- status: open


### L-079
- sources: [CO-19]
- surface: about, coaches, racing, dry-tri, extra-training-fun, wax-entry / all / all
- kind: drift
- severity: P3
- contract: "Dead variants, dead props, dead plugins: `global.css` and `tailwind.config.ts` ship only rules the site uses (no forms plugin, no prose code theming, no mint blockquote rule)."
- evidence: tailwind.config.ts:53 (`--tw-prose-quote-borders: palette.mint`, 1.2:1 on paper), :55-57 (code, pre-code, pre-bg themed); no blockquote or code fence in any mdoc
- observation: the prose theme puts raw mint on paper as a blockquote rule and themes code blocks the contract says will never exist.
- proposal: `--tw-prose-quote-borders: alpha('ink', 0.15)`; remove the three code entries.
- workstream: foundations
- status: open


### L-080
- sources: [CO-22]
- surface: all inner pages, home / all / all
- kind: drift
- severity: P3
- contract: "On paper, headings and display text are `navy`, body is `ink`, secondary body and meta are `slate`."
- evidence: HeroInner.astro:30 (`text-navy`), MissionPanel.astro:18 (`text-navy`), tailwind.config.ts:45 (`--tw-prose-headings: navy`), 32 hand-coded `text-navy` headings on paper; v1 said "ink display H1" and "slate body" for these
- observation: the site uses navy for every heading on paper and it is right (a faint hue lift that ties headings to the nav and footer, 15.4:1); v1 lagged the build.
- proposal: contract only, done in v2. no code change.
- workstream: foundations
- status: open


### L-081
- sources: [CO-24, CS-8 (split)]
- surface: home / open / all
- kind: slop
- severity: P3
- contract: "Text on navy uses three tones: `mint`, `paper`, and `paper/75`. No other alpha on text over navy."
- evidence: LiveConditions.astro:36 (`mint/90`), :50 (`paper/55`), :53 (`paper/60`), :58,85 (`paper/70`), :80 (`mint/50`), SectionBand.astro:23 (`mint/90`), PhotoMosaic.astro:134 (`mint/80`), Footer.astro:30,45-46 (`paper/70`, `paper/50`), Nav.astro:38 (`paper/85`), sponsors.astro:46,53 (`paper/85`, `/80`), extra-training-fun.astro:43 (`paper/80`); LiveConditions.client.ts:221 (`paper/50` groomed line; sacred)
- observation: eleven distinct tones on navy, all passing aa, none meaning anything. the july round chose paper/75 for the seasons band and five muted tones grew around it.
- proposal: map `/85` and `/80` to `paper`; `/70`, `/60`, `/55`, `/50` to `paper/75`; `mint/90` and `mint/80` to `mint`; `mint/50` on the fever note stays (an off state that turns coral on play). the client's groomed line is left and recorded in the contract as a known exception.
- workstream: foundations
- status: open


### L-082
- sources: [CS-14]
- surface: all / all / all
- kind: slop
- severity: P3
- contract: "Because the cut is single-weight, `font-semibold` at a call site is a no-op; `.font-display` carries the weight fallback and `letter-spacing: -0.02em` itself."
- evidence: global.css:87-96 (comment admits the redundancy; `font-stretch: 100%` for a face with no width axis), 17 `font-display font-semibold` pairs
- observation: every display heading carries a redundant weight utility and the utility sets a stretch that does nothing.
- proposal: `.font-display { font-weight: 700; letter-spacing: -0.02em; }` (drop font-stretch); delete `font-semibold` from every `font-display` element; the role utilities (L-010) absorb this.
- workstream: foundations
- status: open


### L-083
- sources: [CS-40 (split)]
- surface: sponsors, home / default / all
- kind: slop
- severity: P3
- contract: "`global.css` and `tailwind.config.ts` are the only places a size, color, or spacing value is defined."
- evidence: SponsorWall.astro:41-61 (`max-w-[200px]`, `[280px]`, `sm:w-[320px]`, `[280px]`, `[240px]`), HeroInner.astro:50 (`h-[230px] md:h-[280px]`), Nav.astro:47 (`underline-offset-[10px]`)
- observation: eight arbitrary pixel values define the sponsor tiers and the masthead band; they are the right numbers written where nobody can find them.
- proposal: `extend.spacing: { 'logo-sm': '12.5rem', 'logo-md': '15rem', 'logo-lg': '17.5rem' }` in tailwind.config.ts (or a sizing map in sponsorTiers.js beside the tier labels), `underline-offset-8` for the nav; the masthead band moves to the aspect rule in L-129.
- workstream: foundations
- status: open

## your method
follow /workspace/tcsc-trips/.agents/skills/visual-redesign/SKILL.md.
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
  PORT=4401 node screenshot.mjs after-foundations <stateIds you touched>
state ids are in scripts/brand-review/states.mjs; the matrix is docs/superpowers/specs/2026-08-31-site-brand-review/state-matrix.md. your port is 4401; other workstreams use other ports, so never use 4400 to 4405 for anything else. the before screenshots are on this machine at /workspace/tcsc-trips/docs/superpowers/specs/2026-08-31-site-brand-review/screens/before/ (the main checkout; screens are not committed). compare each after image against the before image with the same filename. look at them. if a change reads louder, busier, or more generic than before, it fails the gate: revert and try a quieter version. leave no serve-dist.mjs process running when done (`pkill -f "serve-dist.mjs .* --port 4401"`).

## report
write docs/superpowers/specs/2026-08-31-site-brand-review/foundations-report.md:
- `# foundations report`
- `## rows`: one line per ledger id: `L-nnn: fixed (<file:line>, <commit sha>)` or `L-nnn: skipped (<reason>)`.
- `## screens`: list of after screenshots you produced (they live in screens/after-foundations/ in your worktree; screens are gitignored, so do not try to commit them).
- `## proposed`: anything you noticed that has no ledger id.
- `## test/build`: paste the last line of each of the five commands.
commit the report on your branch as the last commit.

work through the rows in ledger order (P1 first). commit small and often: one commit per row or per tightly related group, message `brand(foundations): <what> (L-nnn)`.
