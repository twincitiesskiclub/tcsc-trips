## cross-page verdict

reviewed all 25 matrix rows at both viewports, before and after, plus live walks on the merged populated build (port 4407): entrance frames, hovers, focus, lightbox, fold geometry, type metrics, tap targets, and a left-edge census on about, sponsors, and community.

### 1. one brand?

- home: yes. drenched navy with exactly two paper moments (mission, wax room plus sponsors chapter). one label voice at 12px. coral only on live and open.
- about: yes. every heading and paragraph on one spine at 120; seasons opens with the seam; ends with the cta strip.
- community: yes. the wall is now a named chapter with the seam and mobile rhythm. the thread no longer breaks at the bottom.
- racing: yes. dates are sentence-case slate; the filler fact is gone; the strip breaks to band width.
- dry-tri: yes. the triptych is flush with hairline gaps and captions, no border box.
- extra-training-fun: yes. still the inner template at full strength; the pair is now 7/5 with slate captions.
- coaches: yes. real facts (4 coaches, tue · thu), smaller top-aligned slots, sharp portrait first.
- sponsors: yes. one h2 scale, one grid, ruled tier row, no ellipsis heading.
- trips: yes. ledger on the grid, header row at every viewport, contract empty copy.
- wax-room: yes. empty state is a ruled row in the club voice; index shares the feed's row grammar.
- wax-entry: yes. the gray slab is now a ruled dl with label-caps; title balances.
- 404: yes. one display heading, the label-caps kicker, three destinations that always have content.
- og image: yes. the sunset photo now carries the navy scrim and the lockup bottom-left, 148kb.

what still breaks the thread, small and shared: the injected groomed line at 11px paper/50 (recorded in the contract as a later flask pass), the fever cell's invisible hover, and the venue link's 42x14 tap target (below).

### 2. better?

- home: better. the fold is rebuilt, the mission is calmed to the archivo statement, dryland collapses to one dateline, closed state stops printing past dates.
- about: better. one spine, state-aware season notes, and the page finally ends with a hand extended.
- community: better. the wall has a name and rhythm, though the page grew to 19.5k css px on mobile.
- racing: better. seven fewer tracked-caps registers and a photo strip with no empty cell.
- dry-tri: better. the only bordered box on the site is gone and the legs read like the mosaic.
- extra-training-fun: better. the masthead gap closed and the photo pair joined the one grammar.
- coaches: better. the soft portrait stopped being the headline and the scaffolding facts are gone.
- sponsors: better. the loudest page became the calmest pitch: honest copy, one scale, logos in a ruled row.
- trips: better. the ledger sits on the grid and the empty state keeps the page's shape.
- wax-room: better. four floating words became a ruled placeholder with voice and a pointer home.
- wax-entry: better. the one banned slab on the site is now ledger furniture.
- 404: better. three shouts became one, and the destinations are the three pages that always have content.
- og image: better. the unfurl now says tcsc instead of showing an anonymous sunset.

counts: 13 better, 0 same, 0 worse.

### 3. the home fold

improved, at all three widths.

- 390: h1 renders at 48px (was 36) and the name no longer reads timid beside the 24px temperature. faces stay clear. the coming-soon dates line is legible paper, not 12px at 60%.
- 768: the text block moved to the right column. the member at the left edge, who sat behind "twin cities" before, is fully clear.
- 1440: all four faces are clear of the text block. the fold ends on the hero's bottom edge (hero bottom measured 901px in a 900px viewport; before, the hero got 651px and was cut mid-frame). the cta rises with the headline (0.25s at 200ms after the h1's 120ms), so the entrance is one gesture; at frame zero the button is no longer alone on empty navy.
- one departure to record: the hero h1 at lg is a scoped clamp(4rem, 6.25vw, 5.25rem) with nowrap (84px at 1440), not the contract's 6rem type-display. it is deliberate (the name holds one line) but it is a font-size at a call site.

### 4. most improved and still rough

most improved: sponsors (the page a sponsor judges the club by went from three shouting h2s, four widths, and an ellipsis heading to one calm ledger page), coaches (the blurry-headshot-first problem is gone and the masthead tells the truth), the wax room pair (both the index and the entry moved from bare line and gray slab to the ledger grammar).

still rough: community (17k desktop, 19.5k mobile css px; ledger groups still run seven rows and the etf group repeats a page that exists; the hub cap in the contract is not applied), the conditions strip's fine print (the 42x14 venue link, the 11px groomed line, the fever cell that gives no hover response beyond the ♪ brightening), sponsors' right column (detail columns sit at three x positions, 368, 643, 663, across the three bands, and the "what comes next" seam repeats its own h2 word for word).

### 5. louder, busier, more generic?

nothing got louder. no new colors, no new decoration, no gradients, no motion added beyond the cta joining the existing hero gesture. the mission dropped from eleven display lines to four archivo lines. sponsors dropped a full display size. the one thing that grew is the community mobile scroll (the 3:2 rhythm tiles add height); rhythm was the right trade but the page still needs the row cap. de-slop held: the nonprofit boilerplate ("fostering a supportive community") is gone from the mission, the ellipsis heading is gone, the filler masthead facts are gone, empty states speak in the club voice. the last template smells are the duplicated seam/h2 on sponsors' closing band and the etf group on community repeating its own page.

## rework (gestalt)

| id | surface | severity | instruction | workstream |
|---|---|---|---|---|
| GV-1 | conditions strip, all pages | P2 | the 44px venue-link rule shipped scoped: `[data-astro-cid-4frhl7yl][data-location] a[data-astro-cid-4frhl7yl][data-source-link]` never matches the anchor the sacred client injects (no astro-cid on it), so "theo" measures 42x14 at 390 on home and about. move the rule to global.css unscoped (`[data-location] a[data-source-link]{display:inline-flex;min-height:2.75rem;align-items:center;margin-block:-.5rem}`) and verify live, not in the source. | motion-components |
| GV-2 | sponsors | P3 | the closing band renders seam "what comes next" and h2 "what comes next", the same words twice, 20px apart. keep the h2, give the seam a chapter name (or pass no heading so the seam is the h2, as seasons does). | copy |
| GV-3 | sponsors | P3 | the three bands' detail columns sit at 368, 643, and 663. put the ledger detail column on one axis per page so the right edge reads as a spine too. | sections |
| GV-4 | home hero | P3 | record the lg hero-title override (clamp(4rem, 6.25vw, 5.25rem), nowrap, 84px at 1440) in DESIGN.md as the one sanctioned call-site size, or drop it and let type-display's 6rem wrap. today the site and the contract disagree silently. | foundations |
| GV-5 | community | P3 | apply the contract's hub rule: the extra training fun group shows one row plus the link; cap the other groups near four rows. the page is 19.5k css px on mobile, still the longest scroll on the site. | sections |
| GV-6 | conditions strip, home | P3 | the fever cell's hover changes nothing measurable but the ♪ alpha; the contract says the cell hovers to paper so it reads as a control. make the hover visible or note the ♪ as the whole affordance. | motion-components |

harness note, not rework: the home-wax-feed captures at both viewports crop above the wax band, so the populated chapter is not visible in the after screenshots; i verified it live (paper chapter, seam "wax room", one entry row, sponsors row, then navy). recapture with a taller scroll offset next round. the 11px groomed line stays a recorded flask-side follow-up, not a site rework row.

## recommendation

merge after rework: GV-1 only, then merge without re-review. it is a one-selector fix to a contract accessibility line ("all interactive elements >=44x44px, including the conditions venue link"), it fails live on every page today, and holding it out of the same pr just ships a known miss. everything else (GV-2 through GV-6) is fast-follow material and none of it argues against the branch: 13 surfaces read better, none read worse, the site now reads as one brand on every page, and the failure mode we guarded against, louder or more generic, did not happen.

## verifier A: foundations, copy

checked every fixed row in foundations-report.md and copy-report.md against the cited commits, the merged tree, and fresh screenshots (screens/verify/, 16 states rebuilt from the merged builds on port 4405). tests re-run: test:refinement 71 pass, test:sponsors pass, brandPrimitives 5 pass.

| ledger id | claimed | verdict | evidence |
|---|---|---|---|
| L-001 | fixed | regressed | 8306467 swept ink alphas to slate, then sections 593cd3a (L-055) reintroduced `text-ink/75` on paper at site/src/pages/sponsors.astro:102 (3.43:1, under aa). tree grep shows it is the only ink alpha left. sponsors-default-desktop.png shows it rendering |
| L-002 | fixed | verified | `[data-photo-mosaic]` in the focus surface map (global.css) sets the mint ring; tile buttons carry `focus-visible:outline-offset-[-3px]` (PhotoMosaic.astro:222) and `bg-paper-card` moved to an inner span (:238). compiled css in builds/open confirms the mint ring vars |
| L-010 | fixed | verified | all thirteen role utilities live once in global.css with the contract clamps; no `text-[Npx]` or `tracking-[` in any built html; heading chains gone. the sponsors leftovers are logged under L-015 |
| L-011 | fixed | verified | raw `font-display` survives only on the five prominent temperatures and the fever word (LiveConditions.astro:56,89); mission, stats, trips rows, footer, compact temps all archivo |
| L-012 | fixed | verified | HeroHome.astro:63 `type-display`; home-hero-mobile.png shows the h1 at 48px, three times the temperature above it |
| L-013 | fixed | verified | every h2 renders `.type-h2` or `.type-h2-longform` via SectionBand headingRole; no h2 carries a size utility; 404 second heading is now an h3 |
| L-014 | fixed | verified | `.seam` and `.label-caps` at 0.75rem in global.css; zero `text-[Npx]` in src (one in the sacred client, recorded); dist grep clean |
| L-015 | fixed | regressed | 26adba1 applied `.type-body` at all cited sites; sections 593cd3a rewrote sponsors and dropped it: sponsors.astro:52 (`text-lg leading-relaxed`), :87 (`text-xl leading-relaxed`), :102. remaining sites hold |
| L-016 | fixed | verified | MissionPanel.astro:29 `type-statement` (archivo 500); home-open-desktop.png shows the mission in the sans, statement measure |
| L-017 | fixed | verified | h2/h3/h4 themed once in tailwind.config.ts typography; `[&_h2]` overrides gone from about.astro; about-closed-desktop.png shows "Who joins TCSC" in the display cut at longform scale |
| L-018 | fixed | verified | SeasonsGrid.astro:101-110 `type-caption font-semibold` note, coral dot while open, stacks under the fee below sm. home-open and home-closed screens confirm both states |
| L-019 | fixed | verified | site/src/lib/brand.ts `NAVY_HEX = '#10213E'`; BaseLayout themeColor reads it; global.css html uses `theme(colors.navy)` |
| L-021 | fixed | verified | `.hairline`/`.hairline-soft` (plus rule/divide forms) switch by surface; nav, footer, and both strip edges on the soft weight; no stray border alphas in src |
| L-022 | fixed | verified | band-y-sm/band-y/band-y-lg at 48/64, 64/96, 80/128 in global.css; components take rhythm props; no page-level py-N literals remain |
| L-023 | fixed | verified | one `--gutter` clamp and one `.gutter` utility; safe-inline aliases deleted; no px-6 beside it; left edges align on the about screens (h1, seam, footer at one x) |
| L-024 | fixed | verified | `max-w-site` 80rem token; the 3xl/4xl/5xl/6xl/7xl wrappers are gone (the hero h1 max-w-5xl and lightbox caption belong to sections/motion rows) |
| L-072 | fixed | verified | HeroInner.astro:33 and WaxEntry title on `.type-display-inner`; wax-entry-default-desktop.png shows the entry title at masthead scale |
| L-073 | fixed | verified | no h3 without `.type-h3` in src; SeasonsGrid sizes by headingLevel (`type-h2-longform` as h2, `type-h3` as h3) |
| L-074 | fixed | verified | arbitrary ch values and max-w-xs/lg/xl on text are gone; navy bodies use max-w-prose-narrow (CTAStrip, Footer, SeasonsGrid) |
| L-075 | fixed | not fixed | the about statement never applies: markdoc renders `<article>` inside the wrapper, so `.prose-statement > p:first-child` (global.css) matches nothing. builds/open/about.html shows `prose-statement"> <article><p>`; the founding paragraph renders as plain prose (about-closed-desktop.png). the four other lede sites are fixed |
| L-076 | fixed | verified | balance baked into the display and h2 roles; pretty on the statement; no orphaned single words on the sponsors or about screens |
| L-077 | fixed | verified | typography theme sets 1.125rem/1.7; plain `prose` at all seven call sites; no prose-lg in src |
| L-078 | fixed | verified | four wax tokens in tailwind.config.ts palette; LiveConditions component style block no longer carries raw oklch |
| L-079 | fixed | verified | quote borders `alpha('ink', 0.15)`; code theming gone; SectionBand dead variants deleted (28d1302, 901a072) |
| L-081 | fixed | verified | astro text on navy is mint, paper, or paper/75; mint/50 only on the fever off state (recorded); the sacred client's paper/70 and paper/50 lines remain and are the recorded exception |
| L-082 | fixed | verified | `.font-display { font-weight: 700; letter-spacing: -0.02em }`, no font-stretch; zero `font-display font-semibold` pairs in src |
| L-083 | fixed | regressed | logo-sm/md/lg tokens and underline-offset-8 landed (5bb9047), then sections 9692ab3 (L-056) added `max-w-[13.5rem]` at SponsorWall.astro:52, a sizing literal outside the token files |
| L-003 | fixed | verified | home.yaml `How to register` / `https://tcsc.ski`; all four render sites bake the label in builds/soon/index.html; home-soon-desktop.png shows nav, hero, and strip |
| L-004 | fixed | verified | home.yaml mission matches the ledger text; renders in home-open-desktop.png; no fostering/promoting/programming |
| L-005 | fixed | verified | sponsors_page.yaml matches the CP-3 set word for word; "team" survives only on wax sessions, tent, jacket; sponsors-default-desktop.png confirms the render |
| L-006 | fixed | verified | cardNote(state, year, w) in registrationCopy.ts; closed cards read "2026 registration closed" (home-closed, about-closed screens); open cards read "Registration open · new members from Sep 5" |
| L-007 | fixed | not fixed | home is fixed (loppet-skijor show_on_home false, vasaloppet-duo true, nine photos, home-open-desktop.png clean). but the community wall still renders the watermarked frame: PhotoMosaic.astro:48 filters only on consent, loppet-skijor.yaml keeps `photo_consent_recorded: true`, and CONSENT.md:37 has no rights line. the clause requires a rights line before it renders anywhere. the copy report itself defers this in its proposed section |
| L-025 | fixed | verified | datesSentence/datesLine share one middot format; no semicolon or em dash left in registrationCopy.ts; home-soon screens show one format in hero, strip, and cards |
| L-026 | fixed | verified | closed branch names both reopen pairs; home-closed-desktop.png shows the strip subhead |
| L-027 | fixed | verified | newMembersLine in registrationCopy.ts, HeroHome bakes data-open-dates; builds/open shows `data-open-dates="New members Sep 5"` and the line renders under the open hero button |
| L-028 | fixed | not fixed | the about alt is now accurate (about.astro:76), but sponsors.astro:44 carries a different alt for the same file, so "the same file carries the same alt on every page" still fails. the ledger proposal created this conflict by leaving sponsors unchanged |
| L-029 | fixed | verified | Kortelopet in racing.mdoc:37, Prebirkie in sponsors_page.yaml; no other spellings in src |
| L-030 | fixed | verified | rebecca has no credentials list; greg keeps only Wilderness First Responder; coaches-default-desktop.png confirms |
| L-031 | fixed | verified | the five-brand line is gone from kj.mdoc; remaining credentials are the two confirmed ones; no invented bio text |
| L-032 | fixed | verified | racing.mdoc paragraphs match the ledger text; racing-default-desktop.png shows the new open |
| L-033 | fixed | verified | sponsors and extra-training descriptions authored per the ledger, under 155 chars, full stop, no ellipsis |
| L-034 | fixed | verified | no "Choose another page."; h3 "Try one of these"; Community replaces the trips row; meta "Page not found."; 404-default-desktop.png |
| L-035 | fixed | verified | empty row matches the contract sentence with the address linked; subhead and meta per the ledger; trips-empty-desktop.png |
| L-036 | fixed | verified | "No entries yet. The first reports arrive with the snow." plus a link-inline home link in the ruled row; contentRollback assertion still passes; wax-room-empty-desktop.png |
| L-037 | fixed | verified | footer label "Extra training fun" via FOOTER_EXTRAS (navLinks.ts:22); title and h1 match |
| L-038 | fixed | verified | coaches "4 / Coaches", "Tue · Thu / Practice nights"; community "2020 / Founded", "Member-run / Board and committees"; racing keeps only "80+ / Skiers at the 2026 Birkie" |
| L-039 | fixed | verified | greg order 1, kj order 2; coaches-default-desktop.png shows greg leading with the crisp portrait |
| L-084 | fixed | verified | tour de finn date empty, note carries the series context; the row renders full width with no phantom date; racing-default-desktop.png |
| L-085 | fixed | verified | 404 title uses the middot |
| L-086 | fixed | verified | no semicolons left in visitor copy (registrationCopy, TripsTable, community.mdoc all swept) |
| L-087 | fixed | verified | both season yamls read "Tuesday and Thursday evenings"; the coaches fact stays middot |
| L-088 | fixed | verified | "September to March" and "May to August" |
| L-089 | fixed | verified | site_meta description and footer line match the ledger text; screens confirm the footer |
| L-090 | fixed | verified | subline "Coached cross-country ski training for adults ages 21-35, twice a week, year-round, in Minneapolis and St. Paul." renders on two lines at desktop |
| L-092 | fixed | verified | `team_bonding_activities: []` |
| L-093 | fixed | verified | Jessie Diggins line, "About 20 members", dry_tri "about 20 club volunteers" |
| L-094 | fixed | verified | dry_tri.mdoc:26 replaced with the non-duplicating sentence; community keeps the list |
| L-095 | fixed | verified | curly quotes in kj.mdoc and extra_training.mdoc |
| L-096 | fixed | verified | après-ski accented in both places |
| L-097 | fixed | verified | sponsorTiers.js labels sentence case (the seam renders them uppercase by design) |
| L-098 | fixed | verified | WaxRoomFeed closer reads "Sponsor the club"; home-open-desktop.png |
| L-100 | fixed | verified | description and subhead share the 99-char line |
| L-101 | fixed | verified | both orphans deleted (b331193); og/og-default.jpg remains the canonical copy; sisu fixture hero kept |
| L-102 | fixed | verified | every direct page import carries a `// CONSENT.md:<line>` comment (404, about x2, community x8, racing x6, sponsors x2); spot-checked rows 78, 79, 32, 104 match |
| L-103 | fixed | verified | BaseLayout reads getEntry('site_meta'); the literal is a one-word fallback |
| L-104 | fixed | verified | the etf group is one row with the link; community-default-desktop.png |

skipped rows check out: L-020 and L-080 are contract-only and done in v2; L-091 is a flask change outside scope; L-099 is a later schema round; L-105's dependency landed via sections (the community wall now opens with the "Photo wall" seam and "Photos by club members" h2).

## violations (A)

- none of the hard rules are broken by the 72 foundations and copy commits: no sacred files, no content.config.ts / keystatic.config.ts / astro.config.mjs / render.yaml / app/ edits, no package.json or lockfile changes, no fixture edits under trips or wax_entries, no em dashes or exclamation points in added copy, no new photos (two deletions only), and every brand(...) commit names a ledger id.
- 0cdf847 `fix(brand-review): per-worktree node_modules` sits in the foundations branch with no ledger id. it touches only scripts/brand-review/run-codex.sh (harness, not site code). recording it for completeness.
- transient arbitrary values (footer `text-[13px] tracking-[0.08em]`, mission `text-2xl leading-[1.25]`, sponsors `max-w-[52ch]`) appear in mid-sequence foundations diffs and are all removed by later foundations commits; the end state is clean.
- contract gap found while verifying, owned by no fixed row: the open-state strip subhead returns only the ability sentence (registrationCopy.ts:58), but the v2 registration table reads "Registration is open. Intermediate ability and up, no racing required." filed under rework.

## rework (A)

1. [sections; regresses foundations L-001, L-015] site/src/pages/sponsors.astro: line 102 replace `text-ink/75` with `text-slate`; line 52 replace `text-lg leading-relaxed` with `type-lede` (keep max-w-prose-narrow and text-paper); line 87 replace `text-xl leading-relaxed` with `type-lede` (keep text-ink); line 82 replace `text-sm leading-relaxed` with `type-caption`. rebuild and confirm no `text-ink/` and no `leading-relaxed` remain in src/pages/sponsors.astro.
2. [sections; regresses foundations L-083] site/src/components/SponsorWall.astro:52: replace `max-w-[13.5rem]` with a named token: add `'logo-mobile': '13.5rem'` to the spacing map in site/tailwind.config.ts and use `max-w-logo-mobile`. confirm no `max-w-[` remains in src outside the sacred files.
3. [foundations L-075] site/src/styles/global.css: the selector `.prose-statement > p:first-child` never matches because markdoc wraps content in an article. change both statement rules to also match `.prose-statement > article > p:first-child` (size rule and navy color rule). verify in builds: the about founding paragraph must render at the statement clamp, navy, 44ch.
4. [copy L-007] keep the watermarked frame off the community wall until rights are recorded: remove site/src/content/photos/loppet-skijor.yaml and site/src/assets/images/photos/loppet-skijor.jpg (both restorable from git; note the removal beside CONSENT.md:37 for rob). when rob records a rights line as he did for skijor-race, crop the two marks out of the source and restore both files. do not touch content.config.ts.
5. [copy L-028] one alt per file: put the about wording on sponsors.astro:44 as well, so rollerski-golden-hour carries "About twenty members in matching club caps posed around a bench after a golden-hour rollerski, skis and helmets at their feet" on both pages. optionally write "About 20" in that alt to match the L-093 numeral style, in both places at once.
6. [copy; registration table] site/src/lib/registrationCopy.ts:58: the open branch of stripSubhead must return `Registration is open. ${ABILITY}` per the v2 table. update tests/registrationCopy.test.mjs in the same commit.

## verifier B: motion-components, sections

method: read every cited commit diff and the current code on site/brand-review, then took a fresh screenshot set (`PORT=4405 node screenshot.mjs verify`, all 24 states, 48 captures, all passed `data-season-source=api`) and compared against screens/before and screens/after. verdicts below are mine, not the implementers'.

| ledger id | claimed | verdict | evidence |
|---|---|---|---|
| L-040 | fixed (Ledger.astro, 096c074) | verified | Ledger/LedgerRow primitives with the contract presets (`14rem_1fr`, `8rem_1fr_minmax(8rem,auto)`, rows py-5 gap-x-6, row-hairline dividers, top rule only when unseamed, hover recolors the title only); all ten hand-built sites now mount it; the trips wash and negative margins are gone. trips-populated-desktop.png: header and rows align on one grid. |
| L-041 | fixed (Seam.astro, 2426c2b, fd879e3) | verified | one Seam component; SectionBand, PhotoMosaic, WaxRoomFeed, and LiveConditions:39 all mount it. |
| L-042 | fixed (FactStack.astro, f545d1c, 472c068) | verified | FactStack owns hairline, gap, `.type-stat` over `.label-caps`, max three (throws over), `align`, and the mobile ruled 3-col row. home-open-mobile.png shows the ruled row; mission panel and mastheads both use it. |
| L-043 | fixed (Button.astro, 2fe5446) | verified | one Button with exactly the two contract recipes, `rounded-md px-5 py-3 self-start min-h-11`; nav (sm), hero, CTAStrip, mobile panel (via slot), 404 all render through it; no paper fill on navy anywhere. |
| L-044 | fixed (ProseColumn.astro, e93046e) | verified | ProseColumn = gutter + max-w-site + 12-col grid, reading column span 8 capped at max-w-prose, plain `prose`, band-sm default; 8 pages mount it; no `prose-lg` left in src. |
| L-045 | fixed (global.css:169, ee845d8) | verified | `.link-inline`, `.link-ledger`, `.link-nav` in global.css, colors switched by the surface custom properties; decoration alphas are ink/30 and mint/40 only; the seven-copy 90-char string is gone; sacred client untouched. |
| L-046 | fixed (WaxEntryRow.astro, 16bd5ad) | verified | one row grammar (date · author caption label, Archivo 600 1.125rem title, lede on its own caption line, conditions meta right) at both densities; populated home feed markup confirms. |
| L-047 | fixed (Lightbox.astro:76, cf8494a) | verified | `[data-lightbox][aria-hidden='false']` transitions opacity 200ms var(--ease-out) with `display ... allow-discrete`; image scales 0.97→1 under `@starting-style`; close and photo navigation stay hard cuts. CSS-only as specified. |
| L-048 | fixed (496083d, 27b7161) | verified | `[data-live-conditions]:not([data-updated-at]) [data-updated] { color: var(--color-paper-muted) }`, token compiled in :root. home-unavailable-desktop.png: "● Conditions unavailable" renders muted, not coral; live state stays coral. |
| L-049 | fixed (global.css:114, da8fd62) | not fixed | three of four parts hold: `button:not(:disabled){cursor:pointer}` in base, SectionHeader closers min-h-11, and the fever cell does hover whole-cell to paper (pixel-sampled home-birkie-hover-desktop.png: mint 158,249,190 → paper 251,250,248, contra GV-6). but the venue-link rule sits in LiveConditions.astro's scoped style block and compiles to `[data-location] a[data-astro-cid-4frhl7yl][data-source-link]`; the sacred client injects that anchor without the cid attribute, so the rule never matches and the link stays ~14px tall (matches GV-1's live measurement). the contract clause names this selector explicitly. |
| L-106 | fixed (PhotoStrip.astro, d7cb3cf) | verified | one PhotoStrip (gap-px on the structural rule color, caption row, seven-five and lead-three layouts, mobileLead); community, racing, dry-tri, extra-training-fun are call sites. |
| L-107 | fixed (SectionHeader.astro, 5399304) | verified | one header row (flex-col → md:row items-end justify-between), closer is `.link-inline` with min-h-11; mosaic, wax feed, sponsor strip use it. |
| L-108 | fixed (SectionBand.astro, aaeff75) | verified | `paper-on-navy`, `contentMax`, `subhead`, CtaForState `variant`, PhotoMosaic `limit` all gone; SectionBand type is `'navy' | 'paper'`; no rounded-xl remains. |
| L-109 | fixed (tailwind.config.ts, 647894c) | verified | forms plugin import/entry removed (devDependency kept, per the row); built css has zero `[type=checkbox]` rules. |
| L-110 | fixed (Nav.astro:46, 8678c93) | verified | no bare `transition` utility and no `duration-150` anywhere in src; hover feedback is transition-colors; the one `transition-opacity` is the sanctioned mosaic scrim arrival. |
| L-111 | fixed (navLinks.ts:20, 480d540) | verified | Footer renders `[...getNavLinks(), ...FOOTER_EXTRAS]`; a nav.yaml edit now reorders the footer; brandPrimitives test asserts the order. |
| L-112 | fixed (brandPrimitives.test.mjs, 8fe895a) | verified | the dist-grep test exists and passes (5/5 locally): text-[Npx]/tracking-[ ban, one seam per band, coral rule singular, footer order, oklch containment. caveat: no npm script runs it, see rework. |
| L-113 | fixed (global.css:4, 720b1f4) | verified | `@theme` sets --ease-out as the default timing function and 150ms default duration; built css contains exactly one cubic-bezier, `(.16,1,.3,1)`. |
| L-114 | fixed (global.css:523, fb5c1de) | verified | reduced-motion block zeroes animation-delay and transition-delay alongside durations. |
| L-115 | fixed (imageWidths.ts:12, 9bff566) | verified | MOSAIC = [400,800,1200,1600,1920], lead clamp raised to 1920, comment corrected; dist home srcset carries 1920w. |
| L-116 | skipped (contract-only) | verified | listed in the ledger's contract-only set; no code change expected or made. |
| L-117 | fixed (global.css:108, 056aa4e) | verified | `:focus-visible { transition: none }` in base beside the ring rules. |
| L-118 | fixed (HeroHome.astro:65, 2fa9b13) | verified | the CTA wrapper carries `hero-headline hero-cta` with animation-delay 200ms; the fold enters as one gesture. |
| L-119 | skipped (contract-only) | verified | listed in the ledger's contract-only set. |
| L-120 | fixed (Lightbox.astro:10, a9b609b) | verified | `bg-navy-deep/95` (in the focus map via `[data-lightbox]`, no inline override), inline chevron strokes (`M15 18l-6-6 6-6` / `M9 18l6-6-6-6`) in min-h-11 min-w-11 hit areas, no borders, paper/75→mint, caption mt-3 under the image. home-lightbox-desktop.png confirms. |
| L-008 | fixed (HeroHome.astro:62, eede554, a34315c) | verified | content block moves to `lg:col-start-5 lg:col-span-8`; md crop `object-[100%_15%]`; mobile kept. fresh home-hero-{mobile,tablet,desktop}.png: text sits over trail and torsos, all faces clear at 390, 768, 1440. but eede554 got there partly by capping the h1 off-contract; see violations. |
| L-009 | fixed (CoachEntry.astro:73, 1a90aab, 195fc6a) | verified | max-w-site 12-col grid, photo col-span-4 aspect-square attention-cropped, text col-start-6 span-7 self-start; under md a 240px portrait beside the name, stacking under 360px; greg leads. coaches-default-{desktop,mobile}.png: no towering slot, kj's softness below notice. mobile name clamp is a violation, see below. |
| L-050 | fixed (WaxRoomFeed.astro:33, fbd1d5d) | verified | WaxRoomFeed is the closing paper chapter (seam Wax room → ≤3 rows → hairline → seam Our sponsors → logo row + closer); the separate sponsors band is deleted; empty state keeps the chapter as the sponsor row alone. home runs navy, paper, navy, navy, paper, navy. |
| L-051 | fixed (LiveConditions.astro:99, b4f646b) | verified | compact strip opens with an aria-hidden ● keyed `group-data-[updated-at]/conditions:text-coral`, muted otherwise; visible on every inner-page capture. |
| L-052 | fixed (SectionBand.astro:35, 6d44e54) | verified | SectionBand's navy variant forces `[&_h2]:text-paper [&_h3]:text-paper`; sponsors impact h2 is paper; hero h1 and CTAStrip h2 stay mint; mosaic/seasons h2 paper. |
| L-053 | fixed (index.astro:103, e61ef6b) | verified | three band utilities at 48/64, 64/96, 80/128; home seasons `rhythm="lg" flush="both"`, mosaic and chapter md, CTAStrip lg on home and md elsewhere, dry-tri course `flush="bottom"`; the 210px holes are gone in home-open-desktop.png. |
| L-054 | fixed (global.css:145, 4989a94d) | not fixed | the reading column, one left edge, and the wrapper deletions hold (about/community/sponsors captures show one spine; CoachEntry and SponsorWall sit on max-w-site). but the row names "TripsTable ... move to max-w-site" and the component table says the trips ledger renders at site width; trips/index.astro mounts TripsTable inside ProseColumn, so the table caps at the 62ch reading column (trips-populated-desktop.png). |
| L-055 | fixed (sponsors.astro:34, 593cd3a) | regressed | the structure is right: three SectionBands with the contract seams and heading props, impact `.type-h2` vs longform elsewhere, both lists as Ledgers, disclosure in the column. but 593cd3a replaced `text-slate` with `text-ink/75` on the priorities intro (sponsors.astro:102), re-breaking the L-001 P1 clause ("no text on paper uses an alpha below /90"; ink/75 ≈ 3.4:1, AA fail) on the page foundations had just fixed, and set the intro/body paragraphs as `text-lg`/`text-xl` + `leading-relaxed` call-site chains instead of type roles. |
| L-056 | fixed (SponsorWall.astro:52, 9692ab3) | verified | ruled row per tier (border-y hairline), tier label in the seam voice at left, logos left-aligned at every width, max-h-16 under sm, logo-lg/md/sm tokens in tailwind.config.ts. sponsors-default-{desktop,mobile}.png: two logos on one dignified row, nothing centered. (one arbitrary `max-w-[13.5rem]`, see violations.) |
| L-057 | fixed (SeasonsGrid.astro:92, c7537df) | verified | cells `py-8 md:py-10 md:odd:pr-10 md:even:pl-10`, px-0 mobile, dues row py-6; about opens the band with `seam="Seasons"` + `headingLevel="h3"`. copy sits on the seam axis in home-open and about captures. |
| L-058 | fixed (WaxEntry.astro:64, b849497) | verified | ruled dl (border-y hairline, 3 cells, `.label-caps text-mint-deep` labels, `.type-body text-ink` values), no fill, no radius. wax-entry-default-desktop.png confirms. |
| L-059 | fixed (racing.astro:75, afcd010) | verified | strip breaks to max-w-site through PhotoStrip cols=5; mobileLead gives 1+4 with no orphan cell (racing-default-mobile.png); skijor keeps 82% center, others center 30%. |
| L-060 | fixed (dry-tri.astro:38, ec20d9a) | verified | perimeter border gone, gap-px on the structural rule, Roll/Ride/Run rendered as `.label-caps text-mint-deep` figcaptions, mobile full-bleed via `-mx-[var(--gutter)]` (dry-tri-default-mobile.png). |
| L-061 | fixed (wax-room/index.astro:23, 1b7063f) | verified | wax room empty state is one ruled Ledger row with the contract copy and a `.link-inline`; trips placeholder is the same grammar and its header row shows on mobile as a ruled line (trips-empty-mobile.png, wax-room-empty-desktop.png). |
| L-062 | fixed (PhotoMosaic.astro:142, ef8ddbc, bb5681e) | verified | build-time swap keeps portraits out of wide slots (grid-flow-row-dense closes gaps), squares crop with `position: attention` (dry-tri-runner focal fallback kept), portraits in landscape slots get `object-[center_25%]`. community wall at 390 and 1440 shows no cut faces. |
| L-063 | fixed (PhotoMosaic.astro:224, fc5ee70) | verified | composed side tiles `max-md:aspect-[4/3]`, lead tile `object-[center_65%]`; home-open-desktop.png lead shows the table and faces, not the parking lot. |
| L-064 | fixed (PhotoMosaic.astro:229, e041147, 3aa8909) | verified | mobile 2x1 tiles in the size cycle plus an even-tail fill; community passes `number="Photo wall"` + heading so the wall is named; no empty pt-20 stripe. community-default-mobile.png shows the rhythm. |
| L-065 | fixed (LiveConditions.astro:154, 54f1148) | verified | rules moved to venue cells' right edges, fever button dropped its left rule; `:has([data-dryland-label])` recomposes the strip into a one-line dateline (home-dryland-desktop.png: Trail report · Dryland season · Birkie fever 98.6°, no orphan rule). |
| L-066 | fixed (global.css:22, 7621d6b, 0540e4d) | verified | `--chrome-h` = nav + prominent strip; hero-frame `calc(100svh - var(--chrome-h))` at lg, min 540px; home-hero-desktop.png: the fold lands on the hero's bottom edge in a 900px viewport. |
| L-067 | fixed (MobileNavPanel.astro:18, c970df9) | verified | the nav's 145x22 lockup renders top-left of the panel (correct token fills after L-127); no strip in the panel. home-mobile-nav-mobile.png confirms. |
| L-068 | fixed (about.astro:86, 6671dc1) | verified | CTAStrip mounted after the seasons band on /about, `rhythm="md"`, state props wired; about-open-desktop.png ends with the strip. |
| L-069 | skipped (contract-only) | verified | listed in the ledger's contract-only set. |
| L-070 | fixed (BaseLayout.astro:71, ff46adc) | verified | og-default.jpg regenerated (1200x630, 148KB): sunset skate practice, hero scrim over the lower 45%, mint-tracks/paper-letters lockup ~240px at 48px from left and bottom, no headline type, faces inside the center band; BaseLayout emits og:image:width/height/alt and twitter:image. |
| L-071 | fixed (HeroHome.astro:65, 220baec) | verified | subline `.type-lede text-paper max-w-prose-narrow`; dates line `.type-caption text-paper/75` (dist markup of the soon build confirms). |
| L-121 | fixed (racing.astro:61, c9c0e19) | verified | dates, times, bylines are the caption role via `labelRole="caption"` (0.875rem, 400, tabular-nums, sentence case, slate); racing and dry-tri lost uppercase/tracking/mint-deep. racing-default-desktop.png: dates read as dates, not eyebrows. |
| L-122 | fixed (Footer.astro:25, a5c66f2) | verified | nav svg at 120px replaces the text wordmark (fills corrected by 44d85c0), description `.type-body max-w-prose-narrow`, link rows min-h-10 through `.link-nav`, credits paper/75; mobile footer is compact (home-open-mobile.png). |
| L-123 | fixed (LiveConditions.astro:96, 9ec96f7, 6f30a1c) | verified | compact line: venue `.label-caps`, temp Archivo 700 `.type-caption tabular-nums`, wax `.type-caption`, no display cut, min-h-11 lines. |
| L-124 | fixed (LiveConditions.astro:42, dd95949) | verified | `grid-cols-2 md:grid-cols-3 lg:grid-cols-5` with elm/telemark `max-lg:hidden`; feels-like on its own `whitespace-nowrap` caption line. home-hero-tablet.png: three cells, nothing wraps. |
| L-125 | fixed (LiveConditions.astro:35, 8df380c, 1a9e985) | verified | SectionBand renders the seam as h2 when no heading is passed; prominent strip carries the sr-only h2 Trail report; dist outlines: one h1 per page, no skipped levels (404's h1→h3 is the contract's own prescription). |
| L-126 | fixed (404.astro:45, 298c57b) | verified | one display heading; `.label-caps text-mint-deep` kicker `404 · Page not found`; Button on-paper under the kicker; destinations as a Ledger under `h3.type-h3` Try one of these. 404-default-desktop.png confirms. |
| L-127 | fixed (Nav.astro:17, 44d85c0) | verified | all six logo fills (nav, footer, mobile panel) are the resolved token hexes `#9EF9BE` / `#FBFAF8`, still as attributes. |
| L-128 | fixed (SeasonsGrid.astro:107, aafe6d4) | verified | open note prefixed with an aria-hidden coral ● at `.label-caps` size; closed/soon notes stay muted. home-open captures show the dot. |
| L-129 | fixed (HeroInner.astro:51, 88d49d4) | verified | photo band `aspect-[16/5] min-h-band-photo-min max-h-band-photo-max` with the tokens in tailwind.config.ts; fixed heights gone. |
| L-130 | fixed (about.astro:66, 72363c1) | verified | `photoPosition="center 58%"`; about-open-desktop.png shows the TCSC banner with headroom above every back-row head. |
| L-131 | fixed (404.astro:40, c741a59) | verified | `center 60%`; the 404 band shows the tree line meeting the trail corridor, not flat snow. |
| L-132 | fixed (community.astro:78, 2f0e846) | verified | `center 46%`; back-row heads clear the top edge at 1440. |
| L-133 | fixed (HeroInner.astro:32, b2efd46) | verified | headline `md:col-span-8` with `text-balance`, facts `md:col-start-10 md:col-span-3`; about h1 breaks "About Twin / Cities Ski Club", no orphan. |
| L-134 | fixed (HeroInner.astro:40, 53f02d4) | verified | FactStack `align={facts.length > 1 ? 'end' : 'start'}` with pt-3 in the start case; the single ETF fact tops-aligns beside the h1 (extra-training-fun-default-desktop.png). |
| L-135 | fixed (WaxRoomFeed.astro:35, 25cd5e9) | verified | every home seam carries a label: Seasons, Community, Wax room, Our sponsors, Trail report; no bare-hairline seam device remains. |
| L-136 | fixed (extra-training-fun.astro:47, d3987f5) | verified | pool pair through PhotoStrip `layout="seven-five"`, 4/3 + 4/5, gap-px hairline, captions in the strip's caption row. |
| L-137 | fixed (PhotoStrip.astro:110, dc61c76, 78efa1e) | verified | community cluster through PhotoStrip `layout="lead-three"`: lead aspect-video row over three squares on desktop, plain 2x2 on mobile. |
| L-138 | skipped (contract-only) | verified | listed in the ledger's contract-only set. |
| L-139 | skipped (contract-only) | verified | listed in the ledger's contract-only set. |
| L-140 | skipped (contract-only) | verified | listed in the ledger's contract-only set. |
| L-141 | fixed (LiveConditions.astro:200, 44fec5f, 7621d6b) | verified | `[data-filled='true']:not([data-updated-at]):not(:has([data-dryland-label])) [data-wax] { display:none }` (plus birkie detail); home-unavailable-desktop.png: venue names only, the stamp says it once. |
| L-142 | fixed (global.css:419, cc7e080f) | verified | `.prose-column-body > h2:first-child { margin-top: 0 }` (and first-wrapper variant) inside ProseColumn; the ETF masthead-to-"How it works" gap is band-sm, not a stack. |

counts: 62 verified, 2 not fixed, 1 regressed, of 65 claimed rows (6 of the 71 assigned rows were skipped as contract-only; all 6 match the ledger's contract-only list and 5 are counted in the 63 as verified-skip, L-069 the sixth).

## violations (B)

1. eede554 (sections, L-008): `site/src/components/HeroHome.astro` style block sets `.hero-title { font-size: clamp(4rem, 6.25vw, 5.25rem); white-space: nowrap; }` at lg. a raw font-size outside tailwind.config.ts/global.css, and it overrides `.type-display` (6rem desktop), partially undoing foundations' L-012 and suppressing the two-line balanced wrap the ledger explicitly accepted.
2. 195fc6a (sections, L-009): `site/src/components/CoachEntry.astro` style block sets `.coach-name { font-size: clamp(1.375rem, 5.5vw, 1.625rem); line-height: 1.05; }` under md. a raw font-size and line-height outside the token files, overriding `.type-h2` at a call site.
3. 593cd3a (sections, L-055): `site/src/pages/sponsors.astro:102` replaces `text-slate` with `text-ink/75` on body text on paper (3.4:1, AA fail), re-breaking the L-001 P1 clause foundations had already fixed on this page.
4. 9692ab3 (sections, L-056): `site/src/components/SponsorWall.astro:52` adds the arbitrary width `max-w-[13.5rem]` outside the token files (the tier tokens logo-sm/md/lg exist beside it).

noted, not counted: a5c66f2 (L-122) and c970df9 (L-067) introduced the stale v1 logo hexes `#aaf0c1`/`#fbfbfa`; 44d85c0 (L-127) corrected all six fills later on the same branch, so the merged branch is clean. the two merge commits (904ce12, 20c9b46) carry no ledger id, as merges. no sacred file, package.json, fixture, config, or app/ edit appears in either workstream's diffs; no em dash, exclamation point, or new photo was added.

## rework (B)

1. [sections, L-055] site/src/pages/sponsors.astro:102: change `text-ink/75` to `text-slate`. in the same pass, replace the call-site type chains the L-055 rewrite added: impact intro (line ~52) `text-lg leading-relaxed text-paper` becomes `type-lede text-paper`; recognition body (line ~88) `text-xl leading-relaxed text-ink` becomes `type-lede text-ink` (or `type-body text-ink` if the lede reads too large); priorities intro `text-lg leading-relaxed` becomes `type-lede`; disclosure drops `text-base` so `.type-caption` sizes it. run test:sponsors after.
2. [sections, L-054] site/src/pages/trips/index.astro: TripsTable must render at site width per the component table. replace the `<ProseColumn><TripsTable /></ProseColumn>` mount with `<section class="gutter mx-auto max-w-site band-y-sm"><TripsTable /></section>`. verify trips-populated-desktop: the three-column ledger spans the 1280 container and the left edge stays at the gutter.
3. [sections, L-008] site/src/components/HeroHome.astro: delete the `.hero-title` font-size/white-space override. if the two-line wrap at 1440 must be avoided, change `.type-display`'s clamp in global.css (one definition for the role) and record it in DESIGN.md; otherwise accept the balanced wrap the ledger already approved. re-shoot home-hero-desktop and confirm the text block still clears all faces from col-start-5.
4. [sections, L-009] site/src/components/CoachEntry.astro: remove the `.coach-name` mobile font-size override. either accept `.type-h2`'s mobile clamp (2rem) with the existing min-w-0 wrap, or add the size decision to a role in global.css. no font-size in component style blocks.
5. [sections, L-056] site/src/components/SponsorWall.astro:52: replace `max-w-[13.5rem]` with a named token (add e.g. `'logo-mobile': '13.5rem'` to the tailwind.config.ts spacing/maxWidth map). coordinate with rework (A) item 2, which flags the same literal.
6. [motion-components, L-049] move the venue-link rule out of LiveConditions.astro's scoped style block into global.css, unscoped: `[data-location] a[data-source-link] { display: inline-flex; min-height: 2.75rem; align-items: center; margin-block: -0.5rem; }` (same fix GV-1 names). verify live in a browser, not in the source: the compact strip's Theo link must measure at least 44px tall at 390.
7. [motion-components, L-112] site/package.json: append tests/brandPrimitives.test.mjs to the test:refinement file list (it needs the dist build the script already produces) so the guard actually runs in the suite. it currently passes but nothing invokes it.
8. [motion-components, L-120, minor] site/src/components/Lightbox.astro:32: the caption wrapper uses `max-w-3xl`; swap for `max-w-prose` to keep the banned-width sweep clean.
