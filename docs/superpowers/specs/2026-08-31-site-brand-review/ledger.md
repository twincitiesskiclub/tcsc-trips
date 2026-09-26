# ledger

merged findings from the eight phase 1 reviews (260 finding blocks across lens-typography, lens-color, lens-sections-spacing, lens-copy, lens-motion-imagery, lens-components-slop, gestalt-mobile, gestalt-desktop; the per-surface notes and proposed-contract-change bullets are folded into the same rows). one row per merged finding. every source id appears at least once; a source split across two rows appears in both with "(split)". every `contract:` line quotes a clause in DESIGN.md v2. rows are ordered P1, P2, P3, and within a severity by workstream: foundations, copy, motion-components, sections.

## summary

- rows: 142 (from 260 source findings). by severity: P1 9, P2 62, P3 71.
- by kind: drift 74, elevation 41, slop 27.
- by workstream: foundations 29, copy 42, motion-components 25, sections 46.
- contract-only rows (no code change, the v2 clause records the shipped decision): L-020, L-069, L-080, L-091, L-099, L-102, L-116, L-119, L-138, L-139, L-140.
- rejected: 3 (1 sacred, 2 partial rejections of split findings). recorded with no action: 1.
- the five to fix first if only five could be fixed:
  1. L-008: the hero text block moves off the skier's face at 768 and 1440 (the fold is the strongest screen and it is broken on two of three widths).
  2. L-001: secondary text on paper goes from ink opacity to slate (the only WCAG failure, on six pages).
  3. L-006: the closed season card stops printing past opening dates as a schedule (every winter visitor is misled today).
  4. L-010: type roles defined once as clamp() utilities (removes most of the typographic drift in one pass and makes the display cut rare again).
  5. L-005: the sponsors page copy (the one page written for the sponsor scene still reads like a grant report).

## P1

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

### L-003
- sources: [CP-1, GM-4, GD-11]
- surface: home, about, every inner page / coming soon / all
- kind: drift
- severity: P1
- contract: "Labels never name a season; the season is derived, so every label must be true for Fall/Winter and Spring/Summer alike." and "A CTA links out; a same-page anchor is not a CTA. The hero never points at content already visible beneath it."
- evidence: site/src/content/pages/home.yaml:8 (`cta_coming_soon_label: Fall registration dates`), home.yaml (`cta_coming_soon_url: https://twincitiesskiclub.org/#registration`); site/src/components/registrationCta.ts:36-40 (primary season is whichever window is soonest, either type); home-soon-desktop.png, home-soon-mobile.png
- observation: the coming-soon button says "fall" while the state is derived per season, so a march visitor sees a fall promise for a summer season. the button is also a same-page anchor that hard-jumps 4,000px to the cta strip, where the same dates print smaller, while the dates already sit 12px under the button. the copy lens proposed "Registration dates" with the anchor kept; both gestalts proposed the closed pair. decided by the theme: a visitor on either scene wants a route to registration, not a scroll; the label must also be season-neutral.
- proposal: home.yaml: `cta_coming_soon_label: How to register`, `cta_coming_soon_url: https://tcsc.ski`. the dates line under the hero button stays (restyled in L-071). content only; `registrationCta.ts` and `samePageAnchor.ts` untouched. grep check: the label appears in all four render sites in `dist/index.html`.
- workstream: copy
- status: open

### L-004
- sources: [CP-2]
- surface: home / all states / all
- kind: drift
- severity: P1
- contract: "Prefer direct verbs over nonprofit abstractions such as "fostering," "promoting," and "providing.""
- evidence: site/src/content/pages/home.yaml:12-16; site/src/components/MissionPanel.astro:18; home-open-desktop.png
- observation: the mission paragraph is the biggest type on the page after the h1 and contains "dedicated to fostering", "promoting a healthy lifestyle", and "educational programming", the exact abstractions the july 18 voice rules banned. the refresh replaced the about equivalents and left this one.
- proposal: `mission_paragraph: Twin Cities Ski Club is a 501(c)(3) nonprofit. Cross-country skiers ages 21-35 train together year-round at coached practices twice a week, race when they want to, and stick around after.` every fact is already on the site. if the current text is the legally filed mission and must survive verbatim, it moves to the about page body as a quoted line; rob decides.
- workstream: copy
- status: open

### L-005
- sources: [CP-3, CP-4, GM-25, GD-19 (split)]
- surface: sponsors / default / all
- kind: drift
- severity: P1
- contract: "the organization is "the club" and its people are "members"; "team" is reserved for race-day things (team wax, team tent, team jacket)." and "No em dashes, no exclamation points, no semicolons, no ellipsis headings, no question headlines."
- evidence: site/src/content/pages/sponsors_page.yaml:2-52 (16 uses of "team", 2 of "club"; "Sponsor support helped TCSC..."; "Interested in supporting TCSC?"); sponsors-default-desktop.png, sponsors-default-mobile.png
- observation: the one page written for the sponsor scene is the one page the copy refresh never reached: grant-report verbs ("strengthens the shared resources", "flexibility to invest where it can have the most impact"), a slide-deck ellipsis heading, a question headline, and an organization called a team sixteen times on a site that says club everywhere else. the good facts (two wax drills, rental vans, a tent and parking at the birkie, six jackets, pfas-free wax) are buried.
- proposal: adopt the CP-3 replacement set, facts unchanged, no new claims: intro `Our sponsors pay for the wax, vans, and race-day gear that every member shares, racer or not, and keep dues within reach.`; impact heading `What sponsor money paid for`, intro `Everything here is shared by racers and non-racers alike.`, items `Team wax sessions` / `Two wax drills and a shared wax supply, open to every member.`, `Vans to races` / `Rental vans carried food, gear, and supplies to the Prebirkie and the Great Bear Chase, so volunteer trip leaders had less to haul.`, `A base at the Birkie` / `A team tent and start-area parking: a place to wax, warm up, test skis, and cheer.`; recognition heading `Sponsor logos at the races`, body `Six club jackets carry sponsor logos at races and in podium photos.`; priorities heading `What comes next`, intro `Where the next sponsor dollars go.`, items `PFAS-free wax` / `Replace the club's shared wax with PFAS-free products.`, `More coaches, more gym space` / `Add coaches and book larger training spaces as the club grows.`, `Shared gear` / `Equipment that lowers the cost of a first season.`; contact heading `Sponsor TCSC`, body `Email club leadership about sponsorship and what the club needs this season.`; disclosure `Sponsor recognition is thanks, not an endorsement of a sponsor's products or services.` where "team" survives it names a race-day thing.
- workstream: copy
- status: open

### L-006
- sources: [CP-5, GM-15]
- surface: home, about / closed, open / all
- kind: drift
- severity: P1
- contract: "The season card note states the state in words (open, the upcoming dates, or closed); it never shows a past opening date as a schedule."
- evidence: site/src/lib/registrationCopy.ts:63-70 (`cardNote` has no state input); site/src/components/SeasonsGrid.astro:40-50; home-closed-desktop.png, about-closed-desktop.png, home-closed-mobile.png
- observation: once both windows pass, the card keeps printing the opening dates under a mint fee, so a winter visitor reads "2026 registration: returning members Aug 28 · new members Sep 3" and concludes registration is still to come. in the open state the same line renders bold mint while registration is already open. the mobile gestalt proposed falling back to the june yaml note when closed; the copy lens proposed a state-aware `cardNote`. the state-aware note wins because it also fixes the open state and keeps the yaml fallback for the no-api build.
- proposal: `cardNote(state, year, w)` in registrationCopy.ts: open `Registration open` (plus ` · new members from ${formatDay(new_start)}` while only the returning window is live), coming_soon unchanged, closed `${year} registration closed`. SeasonsGrid already derives the state per card at line 48; pass it through. yaml notes stay as the no-api fallback.
- workstream: copy
- status: open

### L-007
- sources: [MO-11]
- surface: home, community / mosaic / all
- kind: drift
- severity: P1
- contract: "No race-gallery or watermarked frames. A photo with a third-party mark needs a rights line in `CONSENT.md` before it renders, and the mark is cropped out."
- evidence: site/src/content/photos/loppet-skijor.yaml (`show_on_home: true`, order 60); site/src/assets/images/photos/loppet-skijor.jpg (watermarks "CITY OF LAKES loppet WINTER FESTIVAL" bottom-left and "mtec RESULTS" bottom-right); migration/CONSENT.md:37 (no rights line, unlike skijor-race at :92); home-open-desktop.png
- observation: the second photo a visitor sees on home is a race-gallery frame with two third-party logos burned in, the only image on the site that looks bought rather than shot. the mtec mark is a timing company's photo-sales mark.
- proposal: set `show_on_home: false` on loppet-skijor and `show_on_home: true` on vasaloppet-duo (order 90, 4:3, two skiers centered); keep exactly nine home photos. hold loppet-skijor out of the community wall (`photo_consent_recorded` stays true but add a `hidden` note for rob) until rob confirms rights as he did for skijor-race; if confirmed, trim the bottom 60px of the source before it returns.
- workstream: copy
- status: open

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

### L-025
- sources: [CP-6]
- surface: home / coming soon / all
- kind: drift
- severity: P2
- contract: "One format for a pair of opening dates everywhere: `Returning members Aug 28 · new members Sep 3` (middot, second clause lowercase, no semicolon)."
- evidence: site/src/lib/registrationCopy.ts:33-39 (`datesSentence`: semicolon, lowercase), :48-54 (`datesLine`: middot, capital N), :64-70 (`cardNote`: middot, lowercase); home-soon-desktop.png (all three on one page)
- observation: the same two dates render in three punctuation systems on one page, including the only semicolon on the site.
- proposal: `datesLine` and `datesSentence` both return `Returning members ${r} · new members ${f}`; `stripSubhead` reads `Returning members Sep 30 · new members Oct 15. Intermediate ability and up, no racing required.`; `cardNote` keeps its lowercase prefix form. delete the docblock em dashes at lines 32 and 42.
- workstream: copy
- status: open

### L-026
- sources: [CP-7]
- surface: home / closed / all
- kind: drift
- severity: P2
- contract: "The closed state names the reopen months."
- evidence: site/src/lib/registrationCopy.ts:56-61 (closed branch: "Registration is closed. Intermediate ability and up, no racing required."); home-closed-desktop.png; july round 2 spec section 3
- observation: the july decision to relabel the button "How to register" was accepted on the condition that the reopen months survive in the strip subhead; the api-driven rewrite dropped them.
- proposal: closed branch: `Registration is closed. Fall/Winter reopens Aug/Sep, Spring/Summer Apr/May. ${ABILITY}` with the two month pairs as named constants at the top of registrationCopy.ts, sourced from the june facts; rob confirms the months still hold before it ships.
- workstream: copy
- status: open

### L-027
- sources: [CP-8]
- surface: home / open / all
- kind: elevation
- severity: P2
- contract: "open | `Register for the season` | `https://tcsc.ski` | `New members Sep 3` while only the returning window is open, else hidden"
- evidence: site/src/components/HeroHome.astro:28-40 (`data-open-dates` baked empty); site/src/components/registrationFlip.ts:28 (reads `data-open-dates` and hides on empty; sacred, unchanged)
- observation: from aug 28 to sep 3 the site says "Register for the season" to everyone, and a new member who clicks lands on a form that refuses them until sep 3.
- proposal: `newMembersLine(w, now)` in registrationCopy.ts returning `New members ${formatDay(new_start)}` when `now < new_start`, else empty; HeroHome bakes it into `data-open-dates`. the flip script already reads that attribute, so no js change. the attribute wiring is one line in HeroHome and is the copy workstream's call site.
- workstream: copy
- status: open

### L-028
- sources: [CP-9]
- surface: about / all states / all
- kind: drift
- severity: P2
- contract: "Alt text describes what is in the frame; the same file carries the same alt on every page."
- evidence: site/src/pages/about.astro:44 ("A line of members rollerskiing together at golden hour, poles mid-swing"); site/src/pages/sponsors.astro:35 (same file, accurate alt); site/src/assets/images/photos/rollerski-golden-hour.jpg (a posed group of about twenty around a bench)
- observation: nobody in the photo is moving; a screen-reader user gets a different photo on each page.
- proposal: about.astro:44 becomes `About twenty members in matching club caps posed around a bench after a golden-hour rollerski, skis and helmets at their feet`. sponsors.astro unchanged.
- workstream: copy
- status: open

### L-029
- sources: [CP-10]
- surface: racing, sponsors, trips / default / all
- kind: drift
- severity: P2
- contract: "Race and event names are spelled the way the organizer spells them, once, everywhere: Sisu Ski Fest, Prebirkie, Kortelopet, American Birkebeiner, Great Bear Chase, Tour de Finn."
- evidence: site/src/content/pages/racing.mdoc:37 ("Korteloppet") vs racing.astro:25 ("Kortelopet"); sponsors_page.yaml:17 ("Pre-Birkie") vs racing.mdoc:11 and trips/index.astro:8,10 ("Prebirkie")
- observation: the same race is spelled two ways three hundred pixels apart.
- proposal: `Kortelopet` in racing.mdoc:37 and `Prebirkie` in sponsors_page.yaml:17 (birkie.com styling); the names list in v2 is the reference for future entries.
- workstream: copy
- status: open

### L-030
- sources: [CP-11]
- surface: coaches / default / all
- kind: drift
- severity: P2
- contract: "Remove slogan structures, inflated claims, filler adjectives, and repeated points."
- evidence: site/src/content/coaches/rebecca.mdoc:8-11 vs :14; greg.mdoc:9 vs :13; coaches-default-desktop.png
- observation: rebecca's three credentials restate her bio's three sentences as bullets directly beneath it; greg's first credential is his first sentence.
- proposal: rebecca: drop the credentials list. greg: keep only `Wilderness First Responder`. kj and michael unchanged. CoachEntry renders nothing for an empty list.
- workstream: copy
- status: open

### L-031
- sources: [CP-12]
- surface: coaches / default / all
- kind: drift
- severity: P2
- contract: "Do not invent facts to improve a sentence. Leave uncertain copy unchanged until the club confirms it."
- evidence: site/src/content/coaches/kj.mdoc:9 ("Salomon · Atomic · Bjorn Dahlie · Finn Sisu · Borah Teamwear"), :14 (one-sentence bio)
- observation: the head coach's first credential is five brand names with no label, one misspelled (Dæhlie), and his bio is one sentence while the other three get two to five.
- proposal: rob's call: (a) if these are sponsor or shop affiliations, `Sponsored by Salomon, Atomic, Dæhlie, Finn Sisu, and Borah Teamwear`; (b) if unconfirmed, cut the line. ask kj for two sentences in michael's register. no invented text.
- workstream: copy
- status: open

### L-032
- sources: [CP-13]
- surface: racing / default / all
- kind: drift
- severity: P2
- contract: "Use at most one playful ski reference on a surface." and "Remove slogan structures, inflated claims, filler adjectives, and repeated points."
- evidence: site/src/content/pages/racing.mdoc:33-35; racing.astro:37-38; racing-default-desktop.png
- observation: the voluntary point lands three times above the fold and "cheer" twice in two paragraphs; "take to the snow ... to put their training to the test" and "No matter which camp you're in" are the slogan cadence the refresh removed elsewhere.
- proposal: paragraphs 1 and 2 become `Racing is optional. Members race citizen events across the Midwest at every level, and members who skip the start line are just as much a part of race weekend: the Techno Corner cheering section shows up at most big races. Some skiers are there to finish and some are there to win. Either way, TCSC teammates line the trail.` paragraphs 3 and 4 stay. the masthead fact is L-038.
- workstream: copy
- status: open

### L-033
- sources: [CP-15]
- surface: sponsors, extra-training-fun / default / all
- kind: drift
- severity: P2
- contract: "every page authors its own meta description under 155 characters ending on a full stop; `metaDescription()` is the safety net, not the writer."
- evidence: site/src/pages/sponsors.astro:22 (`metaDescription(page.data.intro)`, 154 chars ending "…"); extra-training-fun.astro:24 (153 chars, at the limit)
- observation: the sponsors description is the intro cut mid-thought with an ellipsis, the failure the trimmer was written to avoid.
- proposal: sponsors: `TCSC's sponsors pay for shared wax, vans to races, and race-day gear. See what sponsor support has done and what comes next.` (129 chars). extra training fun: `Member-organized workouts between practices: Thursday Track Club, the Sunday Roll, open-water swims, and the club's annual traditions.` (134 chars). keep `metaDescription()` as the net.
- workstream: copy
- status: open

### L-034
- sources: [CP-17, GD-24 (split)]
- surface: 404 / default / all
- kind: slop
- severity: P2
- contract: "one Ledger of three destinations under an h3 `Try one of these` that always have content (About, Community, Registration). No second display heading, no "Choose another page." block. ... `noindex`; meta description `Page not found.`"
- evidence: site/src/pages/404.astro:9-25, :41-55; 404-default-desktop.png
- observation: after the masthead the body opens a second display headline that restates the subhead, then "Helpful destinations", a phrase from every error-page template, whose first row leads to a page that says "No trips posted". the desktop gestalt would fold "404" into the subhead and drop the kicker; the copy lens keeps the kicker because it carries information. kept (as `.label-caps`, L-126).
- proposal: strings: drop "Choose another page." and its paragraph; list heading `Try one of these`; replace the trips row with `Community` / `What members do beyond practice.`; keep About and Registration; meta description `Page not found.` structure is L-126.
- workstream: copy
- status: open

### L-035
- sources: [CP-18]
- surface: trips / empty / all
- kind: drift
- severity: P2
- contract: "Trips: `No trips posted yet. Trips go up here once dates are set. Questions in the meantime: contact@twincitiesskiclub.org.`"
- evidence: site/src/pages/trips/index.astro:8-10; site/src/components/TripsTable.astro:22-26 ("No trips posted. New trips are announced here each fall; get in touch ..."); trips-empty-desktop.png
- observation: the masthead promises four races and training weekends while the table says nothing is posted; the empty line claims trips are announced "here each fall", which the empty collection has never done, and carries a semicolon.
- proposal: subhead `Race weekends and training trips, with lodging and rides organized by the club.`; empty state per the contract with the address linked; meta `Club trips to regional race weekends and training camps, with lodging and rides organized by TCSC.`
- workstream: copy
- status: open

### L-036
- sources: [CP-19, GM-27 (split), GD-21 (split)]
- surface: wax-room / empty / all
- kind: elevation
- severity: P2
- contract: "Wax room: `No entries yet. The first reports arrive with the snow.` (the opening sentence is asserted by `tests/contentRollback.test.mjs` and stays)."
- evidence: site/src/pages/wax-room/index.astro:20 ("No entries yet."); tests/contentRollback.test.mjs:51; wax-room-empty-desktop.png, wax-room-empty-mobile.png
- observation: the most editorial surface on the site has a three-word production state. the two gestalts proposed longer lines pointing at the trail report; the copy lens's one-sentence addition keeps the page's single ski reference and the rollback assertion.
- proposal: `No entries yet. The first reports arrive with the snow.` inside the ruled placeholder row (L-061), followed by a `.link-inline` to `/`. confirm the rollback test asserts by substring or update its expectation in the same commit.
- workstream: copy
- status: open

### L-037
- sources: [CP-20]
- surface: all / all states / all
- kind: drift
- severity: P2
- contract: "One name per page, in sentence case: the nav label, the footer label, the page title, and the h1 match."
- evidence: site/src/components/Footer.astro:22 ("Extra Training & Fun"); extra-training-fun.astro:23 ("Extra Training Fun · ..."), :25 ("Extra training fun"); community.mdoc:86
- observation: the same page is named three ways.
- proposal: footer label `Extra training fun` (in the `FOOTER_EXTRAS` constant once L-111 lands); title `Extra training fun · Twin Cities Ski Club`. dry tri and wax room titles already match closely enough.
- workstream: copy
- status: open

### L-038
- sources: [GM-19, CP-37, CP-38, GD-32]
- surface: coaches, community, racing / default / all
- kind: slop
- severity: P2
- contract: "Masthead facts are true facts about the page and pair a short value (a number or a name) with a noun label; a page with none renders the single-column masthead."
- evidence: site/src/pages/community.astro:62 ("Photos by club members / Credits"), racing.astro:38 ("Always voluntary / Racing"), coaches.astro:22-25 ("Two seasons a year / Coaching", "Tuesday · Thursday / Practices"); Footer.astro:45 (the same photo credit)
- observation: the stat slot demanded content and labels were invented to fill it; the community credit duplicates the footer line. the copy lens would keep racing's "Always voluntary"; the mobile gestalt calls it scaffolding. decided by the value/label rule: a sentence is not a value, and L-032 makes "Racing is optional." the first sentence of the prose.
- proposal: coaches: `4 / Coaches`, `Tue · Thu / Practice nights`. community: `2020 / Founded`, `Member-run / Board and committees` (from community.mdoc:22-26). racing: keep `80+ / Skiers at the 2026 Birkie`, drop "Always voluntary". the footer keeps the photo credit.
- workstream: copy
- status: open

### L-039
- sources: [MO-18]
- surface: coaches / KJ entry / all
- kind: elevation
- severity: P2
- contract: "Every `object-cover` image has a deliberate focal point at both viewports" and "Real, consented club photography only."
- evidence: site/src/assets/images/coaches/coach-kj.jpg (2400x2400, a visible low-resolution upscale); CoachEntry.astro:7-11; coaches-default-desktop.png
- observation: the head coach's portrait is the softest image on the site and the coaches page's lcp. no css fixes upscaling; new photos are rob's call.
- proposal: flag for rob: a sharper consented photo of kj from the pool or a new one. if none by gate 2, set `order` so greg (crisp) leads and kj sits second. no blur, no grain. L-009 shrinks the slot in the meantime.
- workstream: copy
- status: open

### L-040
- sources: [CS-1, SP-13, GD-30, CS-21, CS-42, CO-15]
- surface: community, racing, dry-tri, extra-training-fun, sponsors, 404, trips, wax-room, home (wax feed) / all / all
- kind: slop
- severity: P2
- contract: "The ledger (label column, detail column, hairline rows) is a component with fixed column presets; pages never hand-build rows." and "Hover: title to `mint-deep` (paper) or `mint` (navy) only; no background wash, no negative margins. A seamed band never draws a second rule above its first row."
- evidence: community.astro:109-123, racing.astro:52-71, dry-tri.astro:61-69, extra-training-fun.astro:36-46,77-84, sponsors.astro:49-56,96-103, 404.astro:56-70, TripsTable.astro:13-50 (`hover:bg-ink/[0.03] md:-mx-3 md:px-3`), WaxRoomFeed.astro:34-59; seven column specs, three paddings, two gaps, four rule tints; extra-training-fun-default-desktop.png (a `border-t` 40px under the seam rule)
- observation: the site's signature below-the-fold form is built ten times by hand, so the label column jumps 160 to 256px between pages and every seamed list draws a second hairline under the seam. the trips row is the only row with a background wash, on an arbitrary color.
- proposal: `<Ledger cols rule surface>` and `<LedgerRow label title meta? note? href?>` per the primitives table (`two` 14rem, `three` 8rem_1fr_minmax, rows `py-5 gap-x-6`, row hairline dividers, `rule="between"` default, top rule only without a seam, hover title-only); rebuild the ten sites on it; drop the trips wash and negative margins.
- workstream: motion-components
- status: open

### L-041
- sources: [CS-2, SP-24 (split)]
- surface: home, community, dry-tri, extra-training-fun, sponsors / all / all
- kind: slop
- severity: P2
- contract: "`<Seam label? surface>` | `.seam` label plus a structural hairline to the right edge. Rendered by SectionBand, PhotoMosaic, WaxRoomFeed, and the conditions strip label; the markup exists once."
- evidence: SectionBand.astro:27-34, PhotoMosaic.astro:125-131 (also re-implements the container), WaxRoomFeed.astro:26-28, LiveConditions.astro:36
- observation: the seam markup is copied in three components and the trail report label repeats the type spec a fourth time.
- proposal: extract `<Seam>` and mount it from the four sites; PhotoMosaic stops re-implementing SectionBand's container. labels for every seam are L-135.
- workstream: motion-components
- status: open

### L-042
- sources: [CS-3, TY-14, GM-9]
- surface: home (mission panel), about, community, racing, dry-tri, extra-training-fun, coaches / all / all
- kind: slop
- severity: P2
- contract: "Org facts render through one FactStack: value (`.type-stat`, navy on paper) over a `.label-caps` label, behind one left hairline, `space-y-4`; max three per surface; no boxes; mint numbers banned. ... Under `md` it renders as one ruled row (`border-t hairline pt-6 grid grid-cols-3`)."
- evidence: MissionPanel.astro:19-28 (`space-y-5 md:pl-7 self-center text-2xl md:text-3xl` display, `big` flag), HeroInner.astro:34-41 (`space-y-3 md:pl-6 self-end text-base md:text-lg` display); home-open-mobile.png (three orphan pairs, no rule under md)
- observation: the same device is built twice at two scales with the display cut at 16px on mastheads, and on a phone the hairline disappears and the facts float.
- proposal: `<FactStack facts size="lg|md" align="center|end">` owning the hairline, gap, label, and the two value sizes in Archivo 700 `tabular-nums`; MissionPanel drops `big`; the mobile ruled-row form is part of the primitive.
- workstream: motion-components
- status: open

### L-043
- sources: [CS-7, CO-17, GD-10, TY-20, CS-28]
- surface: nav, home hero, cta strip, mobile nav, 404, sponsors, about / all states / all
- kind: slop
- severity: P2
- contract: "One button primitive (`<Button>` / `.btn`) with one recipe per surface: on navy `bg-mint text-navy hover:bg-mint/90 active:bg-mint/80`; on paper `bg-navy text-mint hover:bg-navy-deep`. `rounded-md`, `px-5 py-3`, content-width at every viewport (`self-start`). Paper is never a button fill on navy."
- evidence: CtaForState.astro:28-30 (`hover:bg-paper`, `text-sm`), CTAStrip.astro:64-68 (`px-6`, no size, no hover, stretches full width on mobile), 404.astro:48-51 (hand-built on-paper), Lightbox.astro:30-33 (`rounded`, `border-paper/30`); home-open-mobile.png, home-hero-mobile.png, hover captures
- observation: four button definitions ship; the most-clicked button on the drenched home page turns white on hover, its twin in the strip has no hover, the same label renders at 14px and 16px on one page, and on a phone the strip button is full-width while the hero's is content-width.
- proposal: `<Button variant="on-navy|on-paper" href size?="sm|md">` owning the class string; CtaForState wraps it (`size="sm"` from Nav only); CTAStrip, 404, and the sponsors strip render it; `self-start` in the primitive; delete the unused `on-paper` branch from CtaForState. lightbox controls are L-120.
- workstream: motion-components
- status: open

### L-044
- sources: [CS-9 (split), SP-12]
- surface: about, community, racing, dry-tri, extra-training-fun, trips, wax-room, wax-entry / all / all
- kind: slop
- severity: P2
- contract: "Long-form content on inner pages mounts in one ProseColumn: the reading column on the grid (columns 1 to 8, `max-w-prose`), `prose` (not `prose-lg`), `band-sm` by default."
- evidence: about.astro:38, community.astro:68, racing.astro:44,50, extra-training-fun.astro:29, dry-tri.astro:73, trips/index.astro:12, wax-room/index.astro:18, WaxEntry.astro:53 (nine copies of `safe-inline-6 mx-auto max-w-3xl px-6 py-12` with four padding variants); SectionBand.astro:11 (`contentMax: 'narrow'` unused)
- observation: the reading column is the most repeated block on the site and is never a component; each copy picks its own padding and one swaps 3xl for 4xl.
- proposal: `<ProseColumn rhythm flush?>` with the grid placement from L-024, the prose classes fixed, and the first-h2 margin rule (L-142); every page uses it; delete the literals and the unused `contentMax`.
- workstream: motion-components
- status: open

### L-045
- sources: [CO-8, CO-14, CS-4, MO-7]
- surface: about, community, racing, dry-tri, extra-training-fun, home, 404, wax-room, trips, footer, mobile nav / all / all
- kind: slop
- severity: P2
- contract: "Links have three roles, each one class in `global.css`, color decided by the nearest surface" and "No other link recipe. Underline decoration alphas are `ink/30` on paper and `mint/40` on navy, nothing else."
- evidence: the 90-character string `text-navy underline decoration-ink/30 hover:text-mint-deep ...` in community.astro:116, racing.astro:62, dry-tri.astro:81,87, extra-training-fun.astro:89, index.astro:120, and a `decoration-ink/25` near-copy in 404.astro:63; `text-mint-deep hover:text-navy` WaxRoomFeed.astro:32; `text-mint-deep underline` TripsTable.astro:24; `text-mint/80 hover:text-mint` PhotoMosaic.astro:135; no transition on Footer.astro:36-44, MobileNavPanel.astro:31; prose links mint-deep at rest (tailwind.config.ts:47)
- observation: links on paper have four color recipes and four hover families, and the one string that is right exists seven times. the components lens would keep the navy recipe for inline links; the color lens matches inline links to the prose recipe (mint-deep) and keeps navy for ledger row titles, which gives the site one link color on paper and one row-title behavior. adopted.
- proposal: `.link-inline`, `.link-ledger`, `.link-nav` in `@layer components` per the contract; every site above becomes one class; the "See what members do", "All entries", and "About our sponsors" closers converge on `.link-inline`. the sacred client's `a.className` string on the venue link stays (it already matches the navy inline form).
- workstream: motion-components
- status: open

### L-046
- sources: [CS-16, GD-23, GM-32 (split), TY-25 (split)]
- surface: wax-room / populated / all; home / wax-feed / all
- kind: slop
- severity: P2
- contract: "One row grammar for wax entries on the home feed (`feed`) and the index (`index`): date · author, title (Archivo 600 1.125rem), lede as its own caption line, conditions meta right."
- evidence: wax-room/index.astro:22-41 (stacked article, long date, no rules), WaxRoomFeed.astro:34-59 (ledger row with the lede inlined inside the display-cut title); wax-room-populated-desktop.png, home-wax-feed-desktop.png, home-wax-feed-mobile.png
- observation: the same entry renders in two grammars with two date formats, and on a phone the feed's lede wraps under the title in a second face and size mid-line.
- proposal: `<WaxEntryRow entry density="feed|index">` inside a Ledger (L-040); title Archivo 600 1.125rem navy, lede `.type-caption` on its own line (md+ on the feed), the index keeps the long date and gains the conditions meta.
- workstream: motion-components
- status: open

### L-047
- sources: [MO-2, GD-9 (split)]
- surface: home, community / lightbox / all
- kind: drift
- severity: P2
- contract: "Opens with a 200ms opacity fade and a scale from 0.97 to 1 on the image, CSS-only via `@starting-style` and `transition-behavior: allow-discrete` reacting to the client's class toggle; browsers without `@starting-style` keep a hard cut. Close is instant. Navigation between photos is a hard cut."
- evidence: Lightbox.astro:11-18 (no transition), PhotoMosaic.client.ts:81-91 (toggles `hidden`/`flex`; sacred); home-lightbox-desktop.png
- observation: the lightbox pops from display none with no entrance. the desktop gestalt proposed rewriting the contract to a hard cut on the belief that a display toggle cannot transition without js; `@starting-style` with `allow-discrete` transitions a none-to-flex change in css alone. v1's 200ms clause is kept and met at the call site.
- proposal: in Lightbox.astro's style block: `[data-lightbox] { transition: opacity 200ms var(--ease-out), display 200ms allow-discrete; @starting-style { opacity: 0 } }` and `[data-lightbox-img] { transition: transform 200ms var(--ease-out); @starting-style { transform: scale(0.97) } }`. close stays instant; the reduced-motion rule collapses both.
- workstream: motion-components
- status: open

### L-048
- sources: [CO-5]
- surface: home / unavailable, dryland, loading / all
- kind: drift
- severity: P2
- contract: "The live stamp is coral only when the fetch succeeded; ... loading, unavailable, and off-season stamps are `paper/75`."
- evidence: LiveConditions.astro:37 (`text-coral` on `[data-updated]`), LiveConditions.client.ts (sets `data-updated-at` on the root only in the live render and deletes it in `renderQuiet`; sacred); home-unavailable-desktop.png, home-dryland-mobile.png
- observation: "● Conditions unavailable" and "● Trail reports come back with the snow" wear the live color, so the dot says the opposite of the copy.
- proposal: css only in LiveConditions.astro: `[data-live-conditions]:not([data-updated-at]) [data-updated] { color: theme(colors.paper / 0.75); }`. no client change.
- workstream: motion-components
- status: open

### L-049
- sources: [MO-8, GM-16, TY-8 (split)]
- surface: home, community, every inner page / all / mobile, desktop
- kind: drift
- severity: P2
- contract: "All interactive elements ≥44×44px on mobile, including inline section links, the conditions venue link (`[data-location] a[data-source-link]` gets `inline-flex min-h-11 items-center`), the fever cell, and the lightbox controls." and "Every button shows the pointer cursor."
- evidence: no `cursor:pointer` in the built css (tailwind 4 preflight dropped it), `grep cursor-pointer site/src` empty; PhotoMosaic.astro:150, LiveConditions.astro:70, Lightbox.astro:19,31,32, Nav.astro:58; live measurement: compact strip venue link 32x11, "See what members do" 142x20, "About our sponsors" 137x20; home-birkie-hover-desktop.png (no visible change)
- observation: every button on the site shows the arrow cursor, so nothing says a photo opens; three links on every page are 11 to 20px tall; the fever cell's only hover signal is a 10px ♪ brightening. the venue link's class string is set by the sacred client, so the fix is a selector rule at the call site.
- proposal: `button:not(:disabled) { cursor: pointer }` in global.css base; in LiveConditions.astro's style block `[data-location] a[data-source-link] { display: inline-flex; min-height: 2.75rem; align-items: center; margin-block: -0.5rem; }`; `inline-flex min-h-11 items-center` on the two section closer links (via SectionHeader, L-107); the fever cell hovers the whole cell to `paper` (`group-hover`), still 150ms, no lift.
- workstream: motion-components
- status: open

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

### L-084
- sources: [CP-14]
- surface: racing / default / all
- kind: drift
- severity: P3
- contract: "A date column holds dates or date windows; anything else goes in notes."
- evidence: racing.mdoc:25 (`date: Local series`); racing.astro:57; racing-default-desktop.png
- observation: "Local series" is a kind of event, not a date, and in the date slot it scans as a place.
- proposal: `date: ''` for Tour de Finn (racing.astro:55 keeps the empty cell) and `notes: 'A season-long local series. Two TCSC teams participated in 2026.'`
- workstream: copy
- status: open

### L-085
- sources: [CP-16, CS-36]
- surface: 404 / default / all
- kind: drift
- severity: P3
- contract: "Page titles are `<Page> · Twin Cities Ski Club`; the home page is the bare name."
- evidence: 404.astro:29 ("Page not found | Twin Cities Ski Club")
- observation: the only pipe separator on the site.
- proposal: `Page not found · Twin Cities Ski Club`.
- workstream: copy
- status: open

### L-086
- sources: [CP-21]
- surface: all / all states / all
- kind: drift
- severity: P3
- contract: "No em dashes, no exclamation points, no semicolons"
- evidence: registrationCopy.ts:38, TripsTable.astro:23, community.mdoc:89 ("No signup; all members welcome.")
- observation: three semicolons survive in visitor copy on a site whose separator grammar is the middot.
- proposal: registrationCopy per L-025, TripsTable per L-035, community.mdoc:89 `No signup, all members welcome.`
- workstream: copy
- status: open

### L-087
- sources: [CP-22]
- surface: home, about / all states / all
- kind: drift
- severity: P3
- contract: "Days join with "and" in prose and a middot in fact slots, never a plus sign."
- evidence: practice_seasons/fall-winter.yaml:9 and spring-summer.yaml:9 ("Tuesday + Thursday evenings"); coaches.astro:24 ("Tuesday · Thursday"); extra_training.mdoc:4
- observation: the plus sign is a code-comment habit and the only one on the site.
- proposal: both yaml files: `when: Tuesday and Thursday evenings`. the coaches fact stays middot.
- workstream: copy
- status: open

### L-088
- sources: [CP-23]
- surface: home, about / all states / all
- kind: drift
- severity: P3
- contract: "Ranges are "September to March" in prose and unspaced hyphens in compact form"
- evidence: fall-winter.yaml:2 ("September - March"), spring-summer.yaml:2 ("May - August")
- observation: a spaced hyphen is the typewriter stand-in for an en dash; the site writes ranges unspaced elsewhere.
- proposal: `date_range: September to March` and `May to August`.
- workstream: copy
- status: open

### L-089
- sources: [CP-24]
- surface: all / all states / all
- kind: drift
- severity: P3
- contract: "The metro is "Minneapolis and St. Paul" in prose and "Minneapolis · St. Paul" in fact slots and the footer. The age band is "ages 21-35", never parenthetical."
- evidence: site_meta.yaml:6 and BaseLayout.astro:22 ("Minneapolis-St. Paul"); Footer.astro:31 ("young adults (21-35)"); home.yaml:14; index.astro:94 ("adults 21-35"); community.mdoc:96
- observation: the two facts every page repeats are written five ways.
- proposal: meta `Year-round cross-country ski training and community for adults ages 21-35 in Minneapolis and St. Paul, with coached practices, racing, and trips.` (144 chars); footer `A 501(c)(3) nonprofit for cross-country skiers ages 21-35 in Minneapolis · St. Paul. Coached practices twice a week, two seasons a year.`; hero subline per L-090; mission per L-004.
- workstream: copy
- status: open

### L-090
- sources: [CP-25]
- surface: home / all states / all
- kind: elevation
- severity: P3
- contract: (the theme's sponsor scene wants place and scale in the first screen) "A sponsor opening it the next morning on a 27-inch monitor"
- evidence: index.astro:94 ("Year-round cross-country ski training for adults 21-35."); home-hero-desktop.png
- observation: the h1 repeats the wordmark in the nav, so the subline is the only line in the fold that can say anything, and it says what but not where or how often.
- proposal: subline `Coached cross-country ski training for adults ages 21-35, twice a week, year-round, in Minneapolis and St. Paul.` (two lines at desktop inside `max-w-prose-narrow`). h1 unchanged.
- workstream: copy
- status: open

### L-091
- sources: [CP-26]
- surface: home / all states / all
- kind: slop
- severity: P3
- contract: "The four venues come from the API (`app/conditions/locations.py`): Theodore Wirth, Elm Creek, Hyland, and Telemark (Cable, WI), not French Park and Battle Creek. The server-rendered venue label "Theo" is a Flask string and is flagged for a later Flask change to "Theodore Wirth"."
- evidence: LiveConditions.astro:14-19; scripts/brand-review/fixture-api.mjs VENUES; home-open-desktop.png
- observation: v1 named two venues the strip has never shown, and "Theo" is the only place the home trail is not called Theodore Wirth. the api overwrites the server-rendered name on every fetch, so only a flask change fixes the label.
- proposal: contract only, done in v2. flag for rob: a one-line change in app/conditions/locations.py in a later flask pr. no site code change.
- workstream: copy
- status: open

### L-092
- sources: [CP-30]
- surface: community / default / all
- kind: slop
- severity: P3
- contract: "One source per string: no literal repeated across files"
- evidence: community.mdoc:4-18 (`team_bonding_activities`, 14 items, rendered nowhere; one duplicates the Socials item at :85)
- observation: fourteen lines of dead content.
- proposal: `team_bonding_activities: []` in community.mdoc; the schema keeps its default.
- workstream: copy
- status: open

### L-093
- sources: [CP-31]
- surface: community, dry-tri / default / all
- kind: drift
- severity: P3
- contract: "Numbers under ten are words, ten and above numerals."
- evidence: community.mdoc:85 ("Meet & greet with 3-time Olympic medalist"), :35 ("About twenty members"); dry_tri.mdoc:24-26 ("About 25 racers" then "about twenty club volunteers")
- observation: numerals and words in consecutive sentences, and an ampersand outside a proper name.
- proposal: community.mdoc:85 `A meet and greet with three-time Olympic medalist Jessie Diggins`; :35 `About 20 members`; dry_tri.mdoc:26 `about 20 club volunteers`.
- workstream: copy
- status: open

### L-094
- sources: [CP-32]
- surface: dry-tri, community / default / all
- kind: drift
- severity: P3
- contract: "Remove slogan structures, inflated claims, filler adjectives, and repeated points."
- evidence: dry_tri.mdoc:26 vs community.mdoc:35-38 (the volunteer-roles list verbatim on both pages)
- observation: one sentence copied between two pages.
- proposal: community keeps the list; dry_tri.mdoc:26 becomes `About 20 club volunteers ran the day, from parking to chip timing to cleanup. Planning for the next edition started soon after the finish.`
- workstream: copy
- status: open

### L-095
- sources: [CP-33]
- surface: coaches, extra-training-fun / default / all
- kind: drift
- severity: P3
- contract: "Typographic (curly) quotes in prose."
- evidence: kj.mdoc:14 (`Kevin "KJ" Johnson`); extra_training.mdoc:58 (a quoted member line in straight quotes)
- observation: the only two quotations on the site use typewriter quotes; archivo has the glyphs.
- proposal: `Kevin “KJ” Johnson`; `“wanting to do the speed workouts I would be doing anyways with other people.”`
- workstream: copy
- status: open

### L-096
- sources: [CP-34]
- surface: community / default / all
- kind: drift
- severity: P3
- contract: ""après-ski" carries its accent."
- evidence: community.mdoc:83, :96
- observation: the july spec protected the sentence, not the spelling; neither line is set in the display subset.
- proposal: `après-ski` in both places.
- workstream: copy
- status: open

### L-097
- sources: [CP-35]
- surface: sponsors / default / all
- kind: drift
- severity: P3
- contract: "Sentence case everywhere, including tier headings; title case only in proper names."
- evidence: site/src/lib/sponsorTiers.js:7-9 ("Trailblazer Partners", "Community Partners", "Supporters")
- observation: the only title-case headings on the site.
- proposal: `Trailblazer partners`, `Community partners`, `Supporters` (a js lib string, not on the sacred list).
- workstream: copy
- status: open

### L-098
- sources: [CP-36]
- surface: home / all states / all
- kind: drift
- severity: P3
- contract: "Remove slogan structures, inflated claims, filler adjectives, and repeated points."
- evidence: index.astro:115 (seam "Our sponsors"), :121 ("About our sponsors"); sponsors_page.yaml:1 ("Our sponsors")
- observation: "sponsors" three times in one slim band, and the link leads to a page whose h1 is the seam label again.
- proposal: closer link `Sponsor the club` (the page's purpose after L-005). seam stays.
- workstream: copy
- status: open

### L-099
- sources: [CP-39]
- surface: trips, racing, wax-room / populated / all
- kind: elevation
- severity: P3
- contract: "House formats: dates `Jan 9, 2027` and `Jan 9-11, 2027` (short month, no leading zeros, unspaced hyphen range); places `Ironwood, MI` (two-letter state)."
- evidence: scripts/brand-review/fixtures/content/trips/sisu-ski-fest.mdoc:3-4 ("Ironwood, Michigan", "January 9-11, 2027") vs racing.mdoc:8-9 ("Ironwood, MI", "Jan 9, 2027")
- observation: the trip schema takes free text, so the first real trip will be typed by whoever posts it; the fixture already drifts from the racing page for the same event.
- proposal: contract only, done in v2. the keystatic field descriptions carry the format in a later schema round. no content change now.
- workstream: copy
- status: open

### L-100
- sources: [CP-41]
- surface: wax-room / populated / all
- kind: drift
- severity: P3
- contract: "every page authors its own meta description under 155 characters ending on a full stop"
- evidence: wax-room/index.astro:14 vs :16 (the description and subhead say the same thing in two wordings)
- observation: "race prep" / "race-day prep", "Conditions reports" / "Conditions".
- proposal: both: `Conditions, wax notes, race-day prep, and technique. Field reports from TCSC coaches and members.` (99 chars).
- workstream: copy
- status: open

### L-101
- sources: [MO-20]
- surface: shared / image assets / n/a
- kind: slop
- severity: P3
- contract: "Unreferenced image assets are deleted or added to a collection; the repo does not carry orphan photos."
- evidence: site/src/assets/images/uploads/home-hero.jpg (784KB, unreferenced), photos/recess-ski.jpg (790KB, CONSENT row, no yaml), trips/sisu-ski-fest-hero.jpg (fixture only)
- observation: two consented photos sit in the repo doing nothing, invisible to keystatic and to anyone auditing what the site can show.
- proposal: delete `uploads/home-hero.jpg` (its og twin is the canonical copy); delete `recess-ski.jpg` (a no-people trail shot, the kind the july round cut) or add a yaml with `show_on_home: false` if rob wants it on the wall; leave the sisu hero (the fixture depends on it).
- workstream: copy
- status: open

### L-102
- sources: [MO-24]
- surface: shared / photo consent / n/a
- kind: elevation
- severity: P3
- contract: "Every photo the site renders has a row in `migration/CONSENT.md`; collection photos ... additionally carry `photo_consent_recorded: true`, which PhotoMosaic enforces. Direct page imports are allowed only for placements the mosaic cannot express ... and cite the CONSENT row in a comment."
- evidence: all 22 photos yaml carry the flag; 21 photos are imported directly by pages, bypassing the collection; every one has a CONSENT.md row
- observation: nothing is wrong today, but v1 described a gate half the site's photos never pass through, and the next direct import has no guard.
- proposal: contract only, done in v2; the copy workstream adds the `// CONSENT.md:<line>` comment beside each direct import.
- workstream: copy
- status: open

### L-103
- sources: [CS-18, CP-29]
- surface: home, all / all states / all
- kind: slop
- severity: P3
- contract: "`site_meta.yaml` is the only source for the default description."
- evidence: BaseLayout.astro:22 (default description literal), site_meta.yaml:4-6 (the same sentence)
- observation: the site description lives in two files word for word.
- proposal: BaseLayout reads `getEntry('site_meta', 'site_meta')` for its fallback (it already fetches season data at that level) with a one-word literal only for a missing singleton; L-089 then edits one place.
- workstream: copy
- status: open

### L-104
- sources: [GD-16 (split)]
- surface: community / default / all
- kind: elevation
- severity: P3
- contract: "A hub-page ledger group whose content lives on its own page shows one row plus the link."
- evidence: community.astro:91-129, community.mdoc takeaways (the extra training fun group repeats the etf page); community-default-desktop.png (8,179px)
- observation: the etf group restates a page that already holds the rest. the desktop gestalt also proposed capping every group at four rows; that part is rejected (see `## rejected`).
- proposal: the extra training fun group keeps its first row (`Member-organized workouts, most days of the week` with the link) and drops the other two; the closing hand-off sentence pattern from the etf page is reused.
- workstream: copy
- status: open

### L-105
- sources: [GD-17 (split), GM-18 (split)]
- surface: community / default / all
- kind: elevation
- severity: P3
- contract: "Always opens with a Seam and an h2 (on community too)."
- evidence: community.astro:132 (PhotoMosaic mounted with no seam or heading)
- observation: the wall needs a chapter name; the gestalts proposed "the whole album" and "From the archive" or a photo count. both invent framing; the footer's credit line is the true statement.
- proposal: seam `Photo wall`, h2 `Photos by club members`. structure is L-064.
- workstream: copy
- status: open

### L-106
- sources: [CS-34, GD-29]
- surface: dry-tri, extra-training-fun, community, racing / default / all
- kind: slop
- severity: P3
- contract: "`<PhotoStrip photos cols aspect captions?>` | The photo-group grammar (see Layout). Used by the community cluster, the racing strip, the dry-tri legs, the extra-training pair."
- evidence: extra-training-fun.astro:51 (`gap-6 md:grid-cols-2` with figcaptions), community.astro:72 (`gap-px bg-ink/15`), racing.astro:73 (`gap-px bg-ink/15`), dry-tri.astro:36 (`gap-px bg-ink/10 border`)
- observation: four hand-built photo grids with three rule tints and three aspect rules; the etf pair is the one that looks like a different site.
- proposal: `<PhotoStrip>` with `gap-px` on the structural hairline, optional `.type-caption text-slate` caption row; the four sites become call sites (L-059, L-060, L-136, L-137 pick their shapes).
- workstream: motion-components
- status: open

### L-107
- sources: [CS-29]
- surface: home / open / mobile
- kind: elevation
- severity: P3
- contract: "`<SectionHeader heading more_href? more_label?>` | Heading plus optional closer link; `flex-col items-start gap-2 md:flex-row md:items-end md:justify-between`; the closer link is `.link-inline` with a 44px hit area."
- evidence: PhotoMosaic.astro:132-137 (wraps, link jumps right on mobile), WaxRoomFeed.astro:30-33 (does not wrap); home-open-mobile.png
- observation: two hand-built header rows with two behaviors.
- proposal: one `<SectionHeader>` used by the mosaic, the wax feed, and the sponsors closer.
- workstream: motion-components
- status: open

### L-108
- sources: [CS-11, CO-18, SP-11]
- surface: shared components / all / all
- kind: slop
- severity: P3
- contract: "`SectionBand variant="paper-on-navy"`, `contentMax`, `subhead`, `CtaForState variant="on-paper"` (superseded by Button), `PhotoMosaic limit`: dead props are dead CSS and are deleted."
- evidence: SectionBand.astro:3,11,15-22,40-42 (no caller passes `paper-on-navy`, `contentMax`, or `subhead`; the variant is the only `rounded-xl` on the site and the card shape the contract bans on home), CtaForState.astro:10,30, PhotoMosaic.astro:24,42
- observation: five props and one variant are dead and one of them keeps a banned shape one prop away.
- proposal: delete them (the `on-paper` branch after L-043 lands); update the SectionBand type to `'navy' | 'paper'`.
- workstream: motion-components
- status: open

### L-109
- sources: [CS-12]
- surface: all / all / all
- kind: slop
- severity: P3
- contract: "no forms plugin"
- evidence: tailwind.config.ts:2,75; built css contains 12 `[type=checkbox]`, 8 `[type=radio]`, 4 `select:where` rules; no form, input, select, or textarea anywhere in site/src
- observation: the full forms reset ships in a 63KB stylesheet for a site with no form.
- proposal: drop the `forms` import and plugin entry; the devDependency may stay in package.json.
- workstream: motion-components
- status: open

### L-110
- sources: [CS-15]
- surface: all / all / all
- kind: slop
- severity: P3
- contract: "Written as `transition-colors` only; bare `transition` and `duration-150` are banned."
- evidence: Nav.astro:47, CtaForState.astro:29-30, TripsTable.astro:38,42, WaxRoomFeed.astro:44, community.astro:116, 404.astro:50,63, wax-room/index.astro:29, index.astro:120 (`transition-colors duration-150` x7, `transition-colors` x9, bare `transition` x7)
- observation: bare `transition` animates every animatable property including layout, the loophole the contract names; the default duration is already 150ms.
- proposal: `transition-colors` everywhere; delete every `duration-150` and every bare `transition`. most sites are absorbed by L-045.
- workstream: motion-components
- status: open

### L-111
- sources: [CS-17]
- surface: footer / all / all
- kind: slop
- severity: P3
- contract: "two-column nav read from `getNavLinks()` plus a `FOOTER_EXTRAS` constant, in header order"
- evidence: Footer.astro:12-24, nav.yaml, navLinks.ts:10-17 (the six labels in three places)
- observation: the july round asked the footer to follow nav order; it does so by copy, so a nav.yaml edit silently desyncs it.
- proposal: Footer calls `getNavLinks()` for column A and appends `FOOTER_EXTRAS` (Trips, Extra training fun, Dry Tri) from navLinks.ts.
- workstream: motion-components
- status: open

### L-112
- sources: [CS-39]
- surface: shared components / all / all
- kind: elevation
- severity: P3
- contract: "The brand primitives are guarded by a small dist-grep build test (`tests/brandPrimitives.test.mjs`): no `text-[Npx]` and no `tracking-[` in dist HTML; at most one `.seam` per band; `border-t-[3px] border-coral` exactly once per page that mounts CTAStrip; footer links in nav order; no raw `oklch(` outside `global.css` and `tailwind.config.ts`."
- evidence: tests/contentRefinements.test.mjs:130 (asserts the literal CTAStrip section class), responsiveNav.test.mjs:13-23, contentRollback.test.mjs:51, sponsors-page.test.mjs:189,251, seasonBuild.test.mjs; nothing tests the seam, hairlines, buttons, footer order, empty states, 404, or the lightbox
- observation: what drifted is what was untested, and the one guarded literal will break the moment L-021 or L-043 touches it.
- proposal: add `tests/brandPrimitives.test.mjs` per the contract; update contentRefinements.test.mjs:130 in the same commit as any CTAStrip class change.
- workstream: motion-components
- status: open

### L-113
- sources: [MO-5, MO-25]
- surface: shared / every `transition-*` utility / all
- kind: drift
- severity: P3
- contract: "`--ease-out: cubic-bezier(0.16, 1, 0.3, 1)`, set as Tailwind's default transition timing function; default transition duration 150ms. No second curve anywhere."
- evidence: built css: `--default-transition-timing-function: cubic-bezier(.4, 0, .2, 1)` plus four literal `cubic-bezier(.16,1,.3,1)` in HeroHome, LiveConditions, MobileNavPanel; PhotoMosaic.astro:180 (`transition-opacity duration-150`, tailwind's default curve on the hover scrim the contract calls "ease-out")
- observation: two easing families on one page and the one the contract names is the minority. the mosaic hover treatment itself is right (bottom scrim, photo undimmed) and needs nothing beyond the curve.
- proposal: `@theme { --ease-out: cubic-bezier(0.16, 1, 0.3, 1); --default-transition-timing-function: var(--ease-out); --default-transition-duration: 150ms; }` in global.css; replace the four literals with `var(--ease-out)`. re-read the hover capture after and close MO-25.
- workstream: motion-components
- status: open

### L-114
- sources: [MO-6]
- surface: home / hero / all (prefers-reduced-motion)
- kind: drift
- severity: P3
- contract: "animation and transition durations *and delays* are zeroed; the hero photo loads without fade"
- evidence: global.css:98-104 (collapses durations, not `animation-delay`), HeroHome.astro:109 (`120ms both`)
- observation: with reduced motion the headline sits at opacity 0 for 120ms and then pops; everything else collapses cleanly.
- proposal: add `animation-delay: 0s !important;` to the reduced-motion block; optionally narrow the block from `*` to the animating elements so 150ms hover color changes survive.
- workstream: motion-components
- status: open

### L-115
- sources: [MO-22]
- surface: home / mosaic (composed lead tile) / desktop
- kind: elevation
- severity: P3
- contract: "the mosaic lead tile's width list reaches 1920 so a 2x display is never upscaled."
- evidence: imageWidths.ts:12 (MOSAIC max 1600), PhotoMosaic.astro:171 (`width={Math.min(1600, ...)}`); built html: lead tile srcset ends at 1600w with `sizes="(min-width: 768px) 66vw, 100vw"`
- observation: the lead tile is about 950px css at 1440, so a 2x display asks for 1900 and gets 1600, a 19% upscale on the largest photo on home; the explicit `width` clamp defeats the intrinsic-candidate behavior the comment describes.
- proposal: `MOSAIC = [400, 800, 1200, 1600, 1920]` and raise the lead tile's clamp to 1920; correct the imageWidths.ts comment.
- workstream: motion-components
- status: open

### L-116
- sources: [MO-23]
- surface: shared / every non-home image / all
- kind: drift
- severity: P3
- contract: "Formats: webp everywhere; avif on the home hero only. No BlurHash."
- evidence: HeroHome.astro:45-56 (`<Picture formats={['avif','webp']}>`); every other image uses `<Image>` (webp only)
- observation: v1 promised avif and webp everywhere; only the hero ships avif. the honest, cheaper contract is adopted.
- proposal: contract only, done in v2. no code change.
- workstream: motion-components
- status: open

### L-117
- sources: [GD-12]
- surface: shared / all / desktop
- kind: elevation
- severity: P3
- contract: "Focus rings ... Always visible on keyboard navigation, never transitioned."
- evidence: live measurement: nav link outline-color paper/85 at t0, mint at t250; Nav.astro:46, CtaForState.astro:29
- observation: `transition-colors` includes outline-color, so the focus ring fades in over 150ms on every link and button with a color transition.
- proposal: `:focus-visible { transition: none; }` in the base layer of global.css.
- workstream: motion-components
- status: open

### L-118
- sources: [GM-2, GD-3]
- surface: home / hero / all
- kind: elevation
- severity: P3
- contract: "the headline, subline, and CTA rise 8px over 250ms starting at 120ms (the CTA at 200ms), so the fold enters as one gesture."
- evidence: HeroHome.astro:60-75 (the `mt-8` cta wrapper has no `hero-headline` class); live capture home-entrance-0000.png (the button alone on empty navy)
- observation: the photo and headline animate; the cta does not, so at frame zero the button sits alone in a blank navy box.
- proposal: add the `hero-headline` class to the cta wrapper with `animation-delay: 200ms`; reduced motion collapses it with the rest.
- workstream: motion-components
- status: open

### L-119
- sources: [MO-3, MO-4, MO-10]
- surface: home / hero, conditions, mobile-nav / all
- kind: drift
- severity: P3
- contract: "The photo fades in over 400ms `--ease-out`; the headline, subline, and CTA rise 8px over 250ms starting at 120ms" and "Cells rise 4px and fade in over 250ms `--ease-out` after the first fetch, backstopped at 1200ms. Refreshes every five minutes replace text silently." and "Opens with a 200ms opacity fade and an 8px rise on the link list; closes instantly."
- evidence: HeroHome.astro:98-110 (400ms photo, 250ms/8px/120ms headline, every load, no blurhash), LiveConditions.astro:108-126 (first-fill entrance), LiveConditions.client.ts (silent refreshes), MobileNavPanel.astro:43-70,88-108 (fade plus rise, instant close); v1 promised blurhash, per-session gating, a refresh flicker, and an expand-on-click cell
- observation: the code's choices are the better ones (a flicker every five minutes on the signature device is noise; per-session gating and blurhash need js or a dependency, both non-goals); v1 was wrong.
- proposal: contract only, done in v2. no code change.
- workstream: motion-components
- status: open

### L-120
- sources: [MO-9, CS-23, CP-28, GD-9 (split), GM-12, CO-20]
- surface: home, community / lightbox / all
- kind: slop
- severity: P3
- contract: "`navy-deep/95` surface (in the focus map, no override). Close, previous, next as inline chevron/close strokes in 44px hit areas, no bordered pills. Caption directly under the image."
- evidence: Lightbox.astro:13 (`bg-ink/95` with an inline focus override), :31-32 (`←` `→` as button text in bordered rounded boxes), :20-22 (close is an inline svg); home-lightbox-desktop.png, home-lightbox-mobile.png
- observation: the lightbox is the site's one surface that is neither navy nor paper, its three controls mix a glyph idiom and a stroke idiom, and the only arrow glyphs on the site are here while the hero cta the ban reserved them for never used one. the mobile gestalt would make the overlay opaque; `navy-deep/95` keeps the two-register system and the global focus map handles it.
- proposal: `bg-navy-deep/95` (add `.bg-navy-deep\/95` to the focus map if the base selector does not match) and remove the inline override; prev and next become inline `chevron-left` / `chevron-right` paths (`M15 18l-6-6 6-6` / `M9 18l6-6-6-6`) at 24px in `min-h-11 min-w-11` hit areas, no border, `paper/75` at rest and mint on hover; caption `mt-3` under the image; aria labels unchanged.
- workstream: motion-components
- status: open

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

## rejected

### CP-40
- sources: [CP-40]
- reason: sacred. the three fallback vocabularies ("Member area", "Register", "Get on the list") live in `registrationCta.ts` (sacred) and the schema files (`content.config.ts`, `keystatic.config.ts`, non-goals). none render while home.yaml is filled in. deferred: `Registration dates` / `How to register` in all three files in a later pr. no call-site rewrite exists because the strings are defaults, not call sites.

### GD-16 (cap every ledger group at four rows)
- sources: [GD-16 (split; the etf part is accepted as L-104)]
- reason: the 2026-07-18 copy spec protects "the member-written details that make TCSC recognizable", and the "How members pitch in" ledger is the page's content, not filler. cutting rows from the volunteering, coaching, and socials groups would delete member facts to shorten a page. if rob wants the page shorter, he picks the rows.

### GM-26 (three static rows of the usual race calendar as the trips empty state)
- sources: [GM-26 (split; the ledger-shape part is accepted as L-061)]
- reason: voice rule 6, no invented facts. the racing page's dates are race dates, not trip commitments; rendering them as trip rows promises trips the club has not posted, which is the same "announced here each fall" hope the copy lens struck in L-035.
