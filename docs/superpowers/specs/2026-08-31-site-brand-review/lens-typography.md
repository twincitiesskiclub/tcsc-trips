# lens: typography

1. the display cut is everywhere. DESIGN.md allows it in 2 to 3 places per page; the home page sets it on 14 elements (hero, a five-line mission paragraph, three stat values, two season names, two more h2s, five strip temperatures, the footer wordmark), and every heading on every route uses it.
2. there is no type scale in the code. the contract's fluid clamp() scale is implemented as stepped tailwind utilities copied per call site, so h2 renders at six sizes across the routes (14, 24, 27, 30, 36, 48px), h1 at three, lede at three, and heading line-height at five values.
3. uppercase tracked labels are the section grammar the contract bans: 18 on the home page in 8 different specs (10px, 11px, 12px, 13px, 14px; tracking 0.025em to 0.18em), including 10px venue links in the trail report.
4. biggest opportunity: define the roles once in global.css (display, display-inner, h2, h3, statement, lede, body, caption, label-caps, seam) as clamp() utilities with the reversed-type line-height bonus keyed to the surface, then delete every per-surface size string. one afternoon of foundations work removes most of the drift below at once and makes the display cut rare again, which is what makes it feel like a signature instead of a default.
5. overall read: the two families are right and the paper long-form pages already read like a good journal; the loudness is not the typeface, it is the type system's absence, so the site shouts in places (mission panel, stat stacks, every h2) where tracksmith would whisper in a grotesque.

## findings

### TY-1
- surface: home / all states / all
- kind: drift
- severity: P2
- contract: "The display cut is used at most 2–3 places per page; everything else is the body family."
- evidence: site/src/components/HeroHome.astro:61, MissionPanel.astro:18, MissionPanel.astro:22, SeasonsGrid.astro:91, PhotoMosaic.astro:132, LiveConditions.astro:52, LiveConditions.astro:83, CTAStrip.astro:61, Footer.astro:29, WaxRoomFeed.astro:31, WaxRoomFeed.astro:44; home-open-desktop.png
- observation: `font-display` appears on 14 elements of the home page (18 in the populated wax-feed state) and on 28 call sites across the site. the mission paragraph, the six stat values, the trips table rows, the wax feed rows, the footer wordmark and the compact strip temperatures all wear the display cut, so it stops reading as a moment.
- proposal: adopt the rule "display cut on h1, h2, and the conditions temperature; never on h3 or below, paragraphs, stat values, list rows, buttons or labels." remove `font-display` from MissionPanel:18 and :22, HeroInner:37, TripsTable:42, WaxRoomFeed:44, Footer:29, LiveConditions:96 and :102, community.astro:94. that leaves home at hero h1, two season h2s, mosaic h2, cta h2, and the five temperatures the contract itself specifies.
- workstream: foundations

### TY-2
- surface: shared components / all / all
- kind: slop
- severity: P2
- contract: "Scale (fluid via `clamp()`)"
- evidence: site/src/components/SectionBand.astro:38, site/src/pages/sponsors.astro:43, :78, :89 (identical string `font-display font-semibold text-4xl md:text-5xl leading-[1.05]`), PhotoMosaic.astro:132, CoachEntry.astro:79, HeroInner.astro:30, CTAStrip.astro:61, 404.astro:42; site/src/styles/global.css:99-105 (the only type rule defined once)
- observation: no clamp() exists anywhere. every heading is a hand-typed tailwind chain at its call site, and the same 48px h2 string is copied four times while five other h2s got a different chain. visual-redesign names this "no whitespace system / random values with no pattern" and "class string copied instead of a component prop."
- proposal: add role utilities to global.css under `@layer utilities` and use nothing else for type roles: `.type-display` (clamp(3rem, 1.6rem + 5.8vw, 6rem), lh 0.95), `.type-display-inner` (clamp(2.5rem, 1.9rem + 2.4vw, 4rem), lh 1.0), `.type-h2` (clamp(2rem, 1.5rem + 2vw, 3rem), lh 1.05), `.type-h2-longform` (clamp(1.75rem, 1.5rem + 1vw, 2.25rem), lh 1.1), `.type-h3` (clamp(1.375rem, 1.25rem + 0.5vw, 1.625rem), lh 1.2, 600), `.type-statement`, `.type-lede`, `.type-body`, `.type-caption`, `.label-caps`, `.seam`. all carry `text-wrap: balance` on the heading roles and `letter-spacing: -0.02em` on the display ones. replace the nine heading chains and the two seam chains with them.
- workstream: foundations

### TY-3
- surface: home / hero, all states / all
- kind: drift
- severity: P2
- contract: "Display H1 (home hero) | 3.0rem | 6.0rem | 0.95 | 800"
- evidence: site/src/components/HeroHome.astro:61 (`text-4xl sm:text-5xl md:text-7xl leading-[1.02]`); home-hero-desktop.png, home-hero-mobile.png, home-hero-tablet.png
- observation: the hero h1 renders at 36px on a phone, 48px at 768 and 72px at 1440 against a contract of 48 and 96px, with line-height 1.02 instead of 0.95. at 1440 "Twin Cities Ski Club" spans 740 of 1232 available px; at 96px it would span about 990px and still clear the right gutter, and "Twin Cities" at 48px on a 390 phone is about 275px wide inside a 342px column.
- proposal: `.type-display` from TY-2 on the h1 (clamp(3rem, 1.6rem + 5.8vw, 6rem), lh 0.95). change the contract weight column for both display rows to 700, since PolySans BulkyWide ships as a single 700 cut (global.css:26) and the `font-semibold` at every call site is a no-op the file comment already admits.
- workstream: foundations

### TY-4
- surface: about, community, racing, dry-tri, extra-training-fun, coaches, sponsors, trips, wax-room, wax-entry, 404 / all / all
- kind: drift
- severity: P3
- contract: "Display H1 (inner pages) | 2.5rem | 4.5rem | 1.0 | 700"
- evidence: site/src/components/HeroInner.astro:30 (`text-4xl md:text-6xl leading-[1.05]`), site/src/components/WaxEntry.astro:55 (`text-3xl md:text-5xl leading-tight`); about-open-desktop.png, wax-entry-default-desktop.png
- observation: inner h1 renders 36/60px with lh 1.05, and the wax entry h1 renders 30/48px with lh 1.25, so the wax room article title is the size of every other page's h2. a 72px h1 inside HeroInner's 7-column cell would wrap "About Twin Cities Ski Club" to three lines, which is presumably why the value drifted.
- proposal: one `.type-display-inner` at clamp(2.5rem, 1.9rem + 2.4vw, 4rem), lh 1.0, on both HeroInner:30 and WaxEntry:55, and lower the contract's inner desktop value from 4.5rem to 4.0rem to fit the masthead grid.
- workstream: foundations

### TY-5
- surface: all routes / all / all
- kind: drift
- severity: P2
- contract: "H2 | 2.0rem | 3.0rem | 1.05 | 700"
- evidence: SectionBand.astro:38 and sponsors.astro:43,78,89 (36/48px), CoachEntry.astro:79 (30/48px), CTAStrip.astro:61 (30/36px), WaxRoomFeed.astro:31 (30/36px), racing.astro:51 (30px), wax-room/index.astro:28 (24/30px), SponsorWall.astro:65 (24/30px), SeasonsGrid.astro:91 as h2 on home (24/30px), 404.astro:42 (30/48px), 404.astro:55 (14px), markdoc h2 via prose-lg (27px, Archivo); sponsors-default-desktop.png, racing-default-desktop.png, 404-default-desktop.png
- observation: h2 renders at six sizes across the site and at three sizes on /sponsors alone (tier heading 30px, section headings 48px, cta 36px). on /404 an h2 at 48px sits beside an h2 at 14px. a designer reads this as no hierarchy.
- proposal: every section h2 takes `.type-h2`; list titles that are h2s (wax index, wax feed heading, "Races", SponsorWall tier heads, SeasonsGrid on home) take `.type-h2` at the low end via `.type-h2-longform`; the 404 "Helpful destinations" becomes `.type-h3`. no h2 anywhere carries a size utility.
- workstream: foundations

### TY-6
- surface: community, sponsors, about (seasons), 404 / all / all
- kind: drift
- severity: P3
- contract: "H3 | 1.375rem | 1.625rem | 1.2 | 600 | Body family"
- evidence: site/src/pages/community.astro:94 (`font-display font-semibold text-2xl`), sponsors.astro:52 (`font-semibold text-lg text-mint`), sponsors.astro:99 (`font-semibold text-xl text-navy`), SeasonsGrid.astro:91 rendered as h3 on /about at 24/30px display
- observation: h3 renders in the display cut at 24px on /community, in Archivo at 18px and 20px on /sponsors, and in the display cut at 30px on /about. the june round moved the community group heads to the display cut for presence; the presence can come from the 3/9 grid and the anchor photo rather than a third display size.
- proposal: `.type-h3` (Archivo 600, clamp(1.375rem, 1.625rem), lh 1.2, navy on paper, mint on navy) on all four. SeasonsGrid sizes the season name by `headingLevel`: `.type-h2-longform` when h2 (home), `.type-h3` when h3 (about).
- workstream: foundations

### TY-7
- surface: home, all inner pages, shared components / all / all
- kind: drift
- severity: P2
- contract: "eyebrow labels appear at most twice per page, and only where they carry information" and "Uppercase tracked eyebrow labels as repeating section grammar" (banned)
- evidence: LiveConditions.astro:36 (`text-[11px] tracking-[0.18em]`), :50 and :78 (`text-[10px] tracking-widest`), :95 and :101 (`text-xs tracking-widest`), SectionBand.astro:30 and PhotoMosaic.astro:128 (`text-[11px] tracking-[0.18em]`), MissionPanel.astro:25 and HeroInner.astro:38 and SeasonsGrid.astro:109 (`text-[11px] tracking-[0.14em]`), Footer.astro:29 (`text-[13px] tracking-[0.08em] font-display`), TripsTable.astro:16 (`text-[11px] tracking-wider`), racing.astro:57 and dry-tri.astro:66 (`text-sm tracking-wider`), WaxEntry.astro:65,71,77 (`text-xs tracking-wide`), 404.astro:41 (`text-sm tracking-[0.08em]`, no uppercase); home-open-desktop.png
- observation: the home page carries 18 uppercase tracked labels (trail report, five venue names, three stat labels, the seasons seam, six when/where/trips labels, the sponsors seam, the footer wordmark). site-wide there are eight distinct specs for the same device, and the seam string is pasted into three components. the june and july rounds accepted "small-caps seams" as the ledger language, so the contract and the site disagree and the contract needs the finer rule, but eight specs is slop by visual-redesign's "no whitespace system" rule either way.
- proposal: two utilities in global.css and nothing else: `.seam` (0.6875rem, tracking 0.18em, uppercase, 600, lh 1; the section-name-plus-hairline device, at most one per band) and `.label-caps` (0.75rem, tracking 0.12em, uppercase, 600, lh 1; dt labels, table heads, stat labels, venue names). contract v2 separates seams and data labels from eyebrows: a seam is allowed once per band, data labels do not count, decorative eyebrows stay banned. replace all 17 sites; the 404 kicker becomes a `.label-caps`.
- workstream: foundations

### TY-8
- surface: home / open, soon, closed, unavailable / all
- kind: drift
- severity: P2
- contract: "Caption / meta | 0.875rem" (the smallest row in the scale) and "All interactive elements ≥44×44px on mobile."
- evidence: site/src/components/LiveConditions.astro:50 (`text-[10px] tracking-widest uppercase text-paper/55`), LiveConditions.client.ts:195-203 (the venue name becomes a link); home-open-mobile.png (the underlined "THEO" link at the top of the phone)
- observation: the venue names in the prominent strip are 10px, the smallest type on the site, and in winter they are also the SkinnySkI report links, so a phone visitor gets a 10px-tall tap target as the first interactive thing under the nav.
- proposal: `.label-caps` at 0.75rem for the venue name; give the injected link `inline-flex min-h-11 items-center` on mobile (the client sets className, so the change is a string in a sacred file's call site, or a `[data-source-link]` rule in LiveConditions.astro's style block). contract: no type below 0.75rem anywhere.
- workstream: foundations

### TY-9
- surface: shared components / all / all
- kind: slop
- severity: P2
- contract: "No raw color and no ad-hoc font size outside the tokens on any page. `global.css` and `tailwind.config.ts` are the only places a value is defined." (spec success criteria); scale table
- evidence: `text-[10px]` x2 (LiveConditions.astro:50,78), `text-[11px]` x9 (LiveConditions.astro:36,37,53, LiveConditions.client.ts:221, SectionBand:30, PhotoMosaic:128, MissionPanel:25, HeroInner:38, SeasonsGrid:109, TripsTable:16), `text-[13px]` x2 (SeasonsGrid:96, Footer:29), `text-xs` (12px) on the whole compact strip (LiveConditions:27) and on WaxRoomFeed:41,51, WaxEntry:65,71,77, HeroHome:73
- observation: fourteen arbitrary pixel sizes and a dozen 12px sites sit below the contract's 14px floor. visual-redesign: "random values with no pattern."
- proposal: two sub-body sizes only: `.type-caption` 0.875rem (dates, meta, credits, groomed line, feels-like) and `.label-caps` 0.75rem (TY-7). delete every `text-[Npx]`. the compact strip line reads at 0.875rem for temp and wax and 0.75rem for the venue label.
- workstream: foundations

### TY-10
- surface: home (seasons, cta), community (ledger), extra-training-fun, sponsors, dry-tri, 404, footer / all / desktop
- kind: drift
- severity: P2
- contract: "Body M | 1.0rem | 1.0625rem | 1.65" and "Body text minimum 16px on mobile, 17px on desktop."
- evidence: site/src/components/SeasonsGrid.astro:101 (`max-w-prose`, no size, 16px), community.astro:122, extra-training-fun.astro:43,81, sponsors.astro:53,100, dry-tri.astro:65, 404.astro:66; html has no desktop font-size step (global.css:37-43)
- observation: nothing on the site renders body at 17px on desktop. every non-markdoc paragraph is tailwind's 16px/1.5 default, so desktop body is one pixel under the accessibility clause and 0.15 short on line-height.
- proposal: `.type-body { font-size: clamp(1rem, 0.96rem + 0.2vw, 1.0625rem); line-height: var(--body-lh, 1.65); }` in global.css, applied to every non-prose paragraph listed above. see TY-11 for `--body-lh`.
- workstream: foundations

### TY-11
- surface: home (seasons, cta, footer), extra-training-fun (standing invitations), sponsors (impact) / all / all
- kind: drift
- severity: P3
- contract: "Light type on navy gets `+0.05` line-height bonus to body sizes"
- evidence: SeasonsGrid.astro:101 (lh 1.5), :122 (lh 1.5), extra-training-fun.astro:43 (lh 1.5), CTAStrip.astro:62 (lh 1.5), sponsors.astro:53 (lh 1.625), Footer.astro:30 (lh 1.625), HeroHome.astro:63 (lh 1.5)
- observation: no reversed body block reaches 1.70. the seasons summary on navy is the tightest body on the site at 1.5, the exact block the clause was written for.
- proposal: the same trick global.css already uses for focus rings: `.bg-navy, .bg-navy-deep { --body-lh: 1.7 } .bg-paper, .bg-paper-card { --body-lh: 1.65 }`, consumed by `.type-body` and `.type-lede` (lede on navy 1.6). no per-call-site leading utilities.
- workstream: foundations

### TY-12
- surface: home (seasons), extra-training-fun, sponsors, cta strip, footer / all / desktop
- kind: drift
- severity: P3
- contract: "Body line length capped at 62ch on paper, 56ch on navy"; tokens `max-w-prose` (62ch) and `max-w-prose-narrow` (56ch) in tailwind.config.ts:74
- evidence: SeasonsGrid.astro:101 (`max-w-prose` on navy), extra-training-fun.astro:43 (`max-w-prose` on navy), sponsors.astro:46 (`max-w-[56ch]`), :81 and :100 (`max-w-[62ch]`), :92 (`max-w-[52ch]`), CTAStrip.astro:62 (`max-w-xl`), Footer.astro:30 (`max-w-xs`), 404.astro:42 (`max-w-lg` on an h2)
- observation: the two measure tokens exist and are bypassed: navy bodies use the paper token, and /sponsors hand-types three ch values including one (52ch) that is not in the contract.
- proposal: `max-w-prose-narrow` on every navy body (SeasonsGrid:101, extra-training-fun:43, CTAStrip:62, Footer:30), `max-w-prose` on paper; delete the four arbitrary values. contract: arbitrary ch values are banned; the two tokens are the only measures.
- workstream: foundations

### TY-13
- surface: home / mission panel, all states / all
- kind: elevation
- severity: P2
- contract: "`<MissionPanel>` ... ink display H1, slate body"; proposed: "Statement | 1.375rem | 1.875rem | 1.3 | 500 | Body family: a single short paragraph set large, never the display cut"
- evidence: site/src/components/MissionPanel.astro:18 (`font-display text-2xl md:text-3xl leading-[1.25]`); home-open-desktop.png, home-open-mobile.png
- observation: the mission is a 40-word paragraph set in PolySans BulkyWide, five lines at 30px on desktop and nine lines at 24px on a phone. it is the heaviest block on the site and it is body copy. the display subset also lacks the hyphen, so "cross-country" breaks with an Archivo hyphen mid-word (about.astro:6-8 already notes this). tracksmith sets its statements in the grotesque at medium weight and lets the photograph carry the warmth.
- proposal: `.type-statement` (Archivo 500, clamp(1.375rem, 1.2rem + 0.9vw, 1.875rem), lh 1.3, navy, `max-w-[44ch]` via a `max-w-statement` token) on MissionPanel:18. copy lens owns the words; this row is the voice.
- workstream: foundations

### TY-14
- surface: home (mission), about, community, racing, dry-tri, extra-training-fun, coaches / all / all
- kind: slop
- severity: P3
- contract: june round "stat stack ... values ... bold, display scale"; proposed: "Stat | value Archivo 700 1.5rem tabular-nums, label `.label-caps`"
- evidence: MissionPanel.astro:22 (`text-2xl md:text-3xl` / `text-lg md:text-xl` display), HeroInner.astro:37 (`text-base md:text-lg` display); about-open-desktop.png, coaches-default-desktop.png
- observation: the same stat device is rendered by two components at two scales, and the masthead version sets the display cut at 16px, where a wide bulky cut has nothing to offer and just looks like a bolder Archivo. visual-redesign: duplicated markup where one component should exist.
- proposal: one `StatStack` partial used by both, values in Archivo 700 at 1.5rem with `tabular-nums`, labels `.label-caps`. the numbers stay navy on paper (not big mint, which the contract bans).
- workstream: motion-components

### TY-15
- surface: about, dry-tri, extra-training-fun, coaches, wax-entry / all / all
- kind: drift
- severity: P2
- contract: "One sans family, one weird display cut"; H2 row of the scale
- evidence: site/tailwind.config.ts:43-63 (typography theme sets colors only), site/src/pages/about.astro:39 (`[&_h2]:font-semibold [&_h2]:tracking-tight`), about-open-desktop.png (compare "Who joins TCSC" at 27px Archivo with "Seasons" at 48px display on the same page), dry-tri-default-desktop.png ("2025")
- observation: markdoc headings inherit the typography plugin's defaults: Archivo 700 at 1.5em and 1.25em, no tracking. component h2s are in the display cut. /about shows both h2 voices 600px apart, and about.astro patches one of them with a one-off arbitrary variant.
- proposal: theme the prose headings once in tailwind.config.ts `typography.DEFAULT.css`: `h2` = font-family display, `.type-h2-longform` values, `letter-spacing: -0.02em`; `h3` = `.type-h3` values; `h4` = 1.125rem 600. delete the `[&_h2]` overrides on about.astro:39.
- workstream: foundations

### TY-16
- surface: home (hero subline), about (founding lede), all inner mastheads, wax-entry / all / all
- kind: drift
- severity: P3
- contract: "Body L (lede) | 1.125rem | 1.25rem | 1.55 | 400"
- evidence: HeroInner.astro:31 (`text-lg md:text-xl text-slate`, lh 1.5), about.astro:39 (`[&>p:first-child]:font-semibold text-xl md:text-2xl leading-snug text-navy`), WaxEntry.astro:99 (`text-lg leading-relaxed text-ink/90`), HeroHome.astro:63 (`text-base md:text-lg text-paper/85`), SectionBand.astro:41 (`text-lg leading-relaxed opacity-90`)
- observation: five lede treatments: slate 18/20 at 1.5, navy semibold 20/24 at 1.375, ink-90 18 at 1.625, paper-85 16/18 at 1.5, and inherited-color 18 at 90% opacity. the about lede also depends on the mdoc's first paragraph staying first (about.astro:9-10).
- proposal: one `.type-lede` (clamp(1.125rem, 1.25rem), lh 1.55, 400, slate on paper, paper/85 on navy) for all five. if the about founding paragraph must read larger than the masthead subhead, it takes `.type-statement` (TY-13) as frontmatter `lede`, not a first-child selector.
- workstream: foundations

### TY-17
- surface: shared components / all / all
- kind: drift
- severity: P3
- contract: line-height column of the scale (h1 0.95 and 1.0, h2 1.05, h3 1.2, h4 1.3)
- evidence: `leading-[1.05]` x7, `leading-tight` (1.25) on CTAStrip.astro:61, WaxEntry.astro:55, wax-room/index.astro:28, 404.astro:42, WaxRoomFeed.astro:44; `leading-[1.02]` HeroHome:61; `leading-[1.0]` CoachEntry:79; `leading-[1.25]` MissionPanel:18; `leading-none` MissionPanel:22; no leading on community.astro:94 (1.33), SponsorWall:65 (1.2), sponsors.astro:52 (`leading-snug`)
- observation: heading line-height is set at eight values or not at all. the cta strip h2 at 1.25 is visibly airier than the mosaic h2 at 1.05 two bands above it. visual-redesign: "line-height 1.2 on headings: too loose for display."
- proposal: line-height lives in the role utilities (TY-2) and nowhere else; every `leading-*` on a heading is deleted.
- workstream: foundations

### TY-18
- surface: about, sponsors, community, wax-entry / all / desktop
- kind: elevation
- severity: P3
- contract: proposed: "h1 and h2 carry `text-wrap: balance`"
- evidence: HeroHome.astro:61 (the only `text-balance`); about-open-desktop.png ("About Twin Cities Ski / Club"), sponsors-default-desktop.png ("Sponsor support helped / TCSC...", "Visible support at team / events", "What continued / support makes / possible"), wax-entry-default-desktop.png
- observation: only the home h1 is balanced. inner h1s and section h2s leave one-word orphan lines. visual-redesign lists "no text-wrap: balance on headings" as a slop marker.
- proposal: `text-wrap: balance` inside `.type-display-inner`, `.type-h2`, `.type-h2-longform`; `.type-statement` gets `text-wrap: pretty`.
- workstream: foundations

### TY-19
- surface: racing, dry-tri, trips, wax-room, home (wax feed, seasons) / all / all
- kind: drift
- severity: P3
- contract: "Caption / meta | 0.875rem | 0.875rem | 1.45 | 400, slate"
- evidence: racing.astro:57 (`text-mint-deep text-sm tracking-wider uppercase`), dry-tri.astro:66 (same, right-aligned times), TripsTable.astro:41 (`text-sm text-slate tabular-nums`), WaxRoomFeed.astro:41 (`text-xs text-slate tabular-nums`), wax-room/index.astro:25 (`text-sm text-slate`), SeasonsGrid.astro:90 (`text-sm` muted); racing-default-desktop.png, trips-populated-desktop.png
- observation: the same datum, a date, is an uppercase tracked mint-deep label on /racing and /dry-tri and a sentence-case slate caption on /trips and in the wax feed. the race dates read as six eyebrows in a column.
- proposal: dates and meta are `.type-caption` everywhere: 0.875rem, slate on paper (paper/75 on navy), `tabular-nums`, sentence case, no tracking. mint-deep stays for links and `.label-caps` only. racing.astro:57 and dry-tri.astro:66 lose uppercase and tracking.
- workstream: sections

### TY-20
- surface: nav, home hero, cta strip, 404, mobile nav / all states / all
- kind: drift
- severity: P3
- contract: proposed: "button labels: 1rem 600 Archivo; the nav bar cta only at 0.875rem"
- evidence: CtaForState.astro:29-30 (`text-sm`, used by nav, mobile panel and hero), CTAStrip.astro:66 (no size, 16px), 404.astro:50 (16px), TripsTable.astro:24 (inline link)
- observation: the hero cta and the strip cta are the same button in the same state at two sizes (14px and 16px), because the hero reuses the nav's component. on the mobile nav panel the 14px label sits under 24px links.
- proposal: `size?: 'sm' | 'md'` on CtaForState, default md (1rem); Nav passes sm. CTAStrip and 404 use the same class string through a shared `btn` utility so there is one button voice.
- workstream: motion-components

### TY-21
- surface: footer / all / all
- kind: slop
- severity: P3
- contract: "display moments only (wordmark area + H1 on home hero + the Wax Room masthead)"; TY-1 rule
- evidence: site/src/components/Footer.astro:29 (`font-display font-bold uppercase text-[13px] tracking-[0.08em] text-mint`); home-open-desktop.png
- observation: the footer wordmark is the display cut, uppercase, 13px, tracked, bold: four decisions the cut was not designed for, and the ninth caps-label spec. the nav already carries the real logo.
- proposal: Archivo 600 at 0.875rem, sentence case "Twin Cities Ski Club", mint; or the same logo svg at 110px wide, which is what the contract's "wordmark area" means. either way no display cut here.
- workstream: sections

### TY-22
- surface: all inner pages / compact conditions strip / all
- kind: elevation
- severity: P3
- contract: "On paper inner pages: a compact horizontal version in the footer, single line per location."
- evidence: LiveConditions.astro:27 (`text-xs` on the whole strip), :95 (`tracking-widest uppercase text-mint` venue link), :96 (`font-display text-paper` temp at 12px); about-open-desktop.png, about-open-mobile.png
- observation: the compact strip mixes three voices in one 12px line: uppercase tracked mint links, display-cut temperatures, and Archivo wax text. at 12px the bulky display cut loses its shape and just reads bolder. on a phone this is the first line of every inner page.
- proposal: venue name `.label-caps` (0.75rem), temperature Archivo 700 0.875rem `tabular-nums`, wax text `.type-caption`; no display cut in the compact variant. mobile line height 1.4 so the single venue line clears 44px inside its py.
- workstream: sections

### TY-23
- surface: home / hero, live conditions / tablet
- kind: drift
- severity: P3
- contract: "Each column: location name in body-M weight 600, temp huge (display cut at 2rem) in mint, wax recommendation in body-M"
- evidence: LiveConditions.astro:51-54 (`flex items-baseline gap-2` with the 11px feels-like beside a 30px temp); home-hero-tablet.png (Elm cell: "feels / 12°" wraps to two lines beside the temperature; wax labels wrap in every cell)
- observation: at 768 the feels-like wraps inside the flex row and the wax label runs to two lines in four of five cells, so the strip's baseline rhythm breaks exactly at the width the july round added as a check.
- proposal: feels-like moves to its own `.type-caption` line under the temperature (`whitespace-nowrap`), and the cell grid gains `md:grid-cols-3 lg:grid-cols-5` so cells at 768 are wide enough for a one-line wax label.
- workstream: sections

### TY-24
- surface: wax-entry / default / all
- kind: slop
- severity: P3
- contract: "Soft-tinted gray cards on paper. If a card needs definition, give it a 1px ink-15% rule"; TY-7 rule
- evidence: site/src/components/WaxEntry.astro:62-81 (`bg-paper-card p-4 rounded-md` with three `text-xs text-slate uppercase tracking-wide` labels); wax-entry-default-desktop.png
- observation: the conditions snapshot is a rounded paper-card box holding three more caps labels in yet another spec (12px, 0.025em). it is the one card on a long-form page.
- proposal: a ruled row: `border-y border-ink/15 py-4 grid sm:grid-cols-3`, labels `.label-caps`, values `.type-body`. no background, no radius.
- workstream: sections

### TY-25
- surface: trips (populated), home (wax feed) / populated / all
- kind: drift
- severity: P3
- contract: TY-1 rule; "Body M" row
- evidence: TripsTable.astro:42 (`font-display text-lg md:text-xl`), WaxRoomFeed.astro:44-49 (title span in display cut with the lede as an inline `span` inside it); trips-populated-mobile.png, home-wax-feed-desktop.png
- observation: list rows set their titles in the display cut at 18 and 20px, and the wax feed inlines the lede inside the title element so on a phone the sentence wraps under the title in a second face and size mid-line.
- proposal: row titles Archivo 600 at 1.125rem navy; the wax feed lede becomes its own `p.type-caption` under the title. the display cut stays out of lists.
- workstream: sections

### TY-26
- surface: home, extra-training-fun, dry-tri, 404 / all / all
- kind: drift
- severity: P3
- contract: lens brief "one H1, no skipped levels"; proposed: "every band has a heading element; a seam without a heading prop is rendered as the band's h2"
- evidence: SectionBand.astro:27-34 (seam is a `span`), index.astro:104 and :115 (seasons and sponsors bands have no heading), extra-training-fun.astro:35 and :76, dry-tri.astro:60, 404.astro:55 (h2 at `text-sm`)
- observation: the home outline is h1 then the two season h2s; "Trail report" and "Our sponsors" have no heading. on /extra-training-fun the outline skips from "How it works" to nothing for the two ledgers. on /404 an h2 is 14px.
- proposal: SectionBand renders the seam as `<h2 class="seam">` when no `heading` is passed and as a `span` when one is; LiveConditions gets an sr-only h2 "Trail report" (its label is already the seam text); 404 "Helpful destinations" becomes h3 with `.type-h3`.
- workstream: sections

### TY-27
- surface: home, about / seasons grid, all states / all
- kind: elevation
- severity: P2
- contract: proposed: caption floor 0.875rem (TY-9)
- evidence: SeasonsGrid.astro:96 (`text-[13px]` registration note, `font-semibold mint` when open, muted when closed); home-open-mobile.png, about-closed-desktop.png
- observation: the registration dates, the one line a returning member is looking for in august, are the smallest type in the card at 13px, wrapping to two lines on a phone under a 24px fee. on the closed state it drops to paper/75 at 13px on navy.
- proposal: `.type-caption` at 0.875rem 600 for the note, and on mobile stack it under the fee on its own line rather than in the baseline row (`flex-col` under `sm:`). the fee stays 1.125rem.
- workstream: foundations

### TY-28
- surface: home / soon / all
- kind: drift
- severity: P3
- contract: "Caption / meta | 0.875rem"
- evidence: HeroHome.astro:73 (`text-xs md:text-sm text-paper/60`); home-soon-desktop.png ("Returning members Sep 30 · New members Oct 15")
- observation: the dates line under the coming-soon cta is 12px on a phone and 14px at 60% paper on desktop, on the fold, carrying the registration dates.
- proposal: `.type-caption` at 0.875rem both widths, paper/75 (the july contrast value the seasons grid already moved to).
- workstream: foundations

### TY-29
- surface: about, community, racing, dry-tri, extra-training-fun, coaches, wax-entry / all / all
- kind: elevation
- severity: P3
- contract: proposed: "Long-form body (markdoc) | 1.125rem | 1.125rem | 1.7 | 400" as a scale row
- evidence: `prose prose-lg` on about.astro:39, community.astro:69, racing.astro:45, dry-tri.astro:74, extra-training-fun.astro:30, CoachEntry.astro:81, WaxEntry.astro:100; community-default-desktop.png (18px prose above a 16px ledger)
- observation: markdoc bodies are prose-lg (18px, lh 1.78) and every other body is 16px at 1.5, so /community shows two body registers 200px apart. the 18px is right for reading and should be the contract, not the plugin default; the 1.78 is looser than anything else on the site.
- proposal: add the row to the scale; set `--tw-prose-body` size and line-height in the typography theme (1.125rem / 1.7) and use plain `prose` instead of `prose-lg` at all seven call sites; ledger bodies use `.type-body` (TY-10) so the two registers are 18/1.7 and 17/1.65 by design.
- workstream: foundations

### TY-30
- surface: community, racing, dry-tri, extra-training-fun, sponsors, wax-room, wax-entry / all / all
- kind: drift
- severity: P3
- contract: "`slate` ... Secondary body on paper. Captions, dates, meta."
- evidence: community.astro:122, racing.astro:69, dry-tri.astro:65, extra-training-fun.astro:81,85, sponsors.astro:81,92,100, wax-room/index.astro:38, WaxEntry.astro:99 (`text-ink/80`, `/75`, `/90`)
- observation: secondary body on paper is ink at three opacities in ten places instead of the slate role. overlaps the color lens; listed here because it is the secondary-text role of the scale and it makes the ledgers' two columns read as the same weight.
- proposal: `text-slate` on every detail column; ink opacity modifiers on text are removed.
- workstream: foundations

### TY-31
- surface: og image / default / all
- kind: elevation
- severity: P3
- contract: proposed: "the og image carries the photograph and the logo mark only; no headline type, the card title comes from og:title"
- evidence: site/public/og/og-default.jpg (1200x630, a sunset group photo, no type); BaseLayout.astro:57-59
- observation: the share card is a bare photograph. in a slack or imessage preview the title comes from og:title, so nothing is broken, but a sponsor sharing the link sees no club mark on it, and the contract has no clause for it.
- proposal: add the clause above; the imagery workstream places the nav logo lockup (mint tracks, paper letters) bottom-left over the same functional scrim the hero uses, about 220px wide, and nothing else. no headline in the image, so it never conflicts with the page title.
- workstream: sections

### TY-32
- surface: 404 / default / all
- kind: drift
- severity: P3
- contract: TY-7 rule; H2 row
- evidence: 404.astro:41 (`text-sm font-semibold tracking-[0.08em] text-mint-deep`, mixed case), :42 (`text-3xl md:text-5xl leading-tight`), :55 (h2 `text-sm font-semibold`); 404-default-desktop.png
- observation: the 404 body introduces a sixth kicker style (tracked but not uppercase) and puts a 48px h2 and a 14px h2 side by side.
- proposal: kicker becomes `.label-caps`; "Choose another page." takes `.type-h2`; "Helpful destinations" becomes `h3.type-h3`.
- workstream: sections

## proposed contract changes

- display cut rule: "the display cut is used on h1, h2, and the live conditions temperature only; never on h3 or below, paragraphs, stat values, list rows, buttons or labels." replaces "at most 2–3 places per page." (TY-1, TY-13, TY-14, TY-21, TY-22, TY-25)
- scale is fluid and defined once: every row in the scale table is a clamp() expressed as a role utility in global.css (`.type-display`, `.type-display-inner`, `.type-h2`, `.type-h2-longform`, `.type-h3`, `.type-statement`, `.type-lede`, `.type-body`, `.type-caption`, `.label-caps`, `.seam`); tailwind `text-*` and `leading-*` utilities are not used on type roles. (TY-2, TY-5, TY-6, TY-17)
- scale table edits: H2 family becomes the display cut (the site already does this and it is right); add "H2, long-form (markdoc and list titles) | 1.75rem | 2.25rem | 1.1 | display cut"; add "Statement | 1.375rem | 1.875rem | 1.3 | 500 | body family"; add "Long-form body (markdoc) | 1.125rem | 1.125rem | 1.7 | 400"; replace "Numbered section marker" with "Label caps | 0.75rem | 0.75rem | 1.0 | 600, tracking 0.12em, uppercase"; display rows weight column reads 700 (single-weight cut). (TY-3, TY-5, TY-7, TY-13, TY-15, TY-29)
- inner display h1 desktop value 4.5rem becomes 4.0rem so it fits the 7-column masthead cell. (TY-4)
- eyebrow clause rewrite: "a seam (section name in `.seam` plus a hairline) is allowed once per band; data labels (dt, table heads, stat labels, venue names) share `.label-caps` and do not count as eyebrows; eyebrows as decoration stay banned; no type on the site is smaller than 0.75rem, and only `.label-caps` is that small." (TY-7, TY-8, TY-9, TY-28, TY-32)
- measure clause: "`max-w-prose` (62ch) on paper and `max-w-prose-narrow` (56ch) on navy are the only measures; arbitrary ch values are banned; a statement paragraph caps at 44ch." (TY-12, TY-13)
- reversed-type bonus is mechanized: "`--body-lh` is set by the surface utilities (`.bg-navy` 1.7, `.bg-paper` 1.65) and consumed by the body and lede roles; call sites do not set leading." (TY-10, TY-11)
- dates and meta: "dates, times, bylines and credits are the caption role: slate on paper, paper/75 on navy, tabular-nums, sentence case, never uppercase or tracked." (TY-19)
- buttons: "button labels are Archivo 600 at 1rem; the nav bar cta alone is 0.875rem; one `btn` utility." (TY-20)
- headings carry `text-wrap: balance` (h1, h2) or `pretty` (statement). (TY-18)
- document outline: "every band has a heading element; SectionBand renders its seam as the h2 when no heading prop is given." (TY-26)
- og image clause: "photograph plus the logo lockup bottom-left; no headline type in the image." (TY-31)
- stat device: "stat values are Archivo 700 at 1.5rem tabular-nums over a `.label-caps` label, rendered by one partial in both the mission panel and the inner masthead." (TY-14)
- secondary text on paper is the slate token, never ink at reduced opacity. (TY-30)
