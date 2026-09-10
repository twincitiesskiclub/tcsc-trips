# lens: components + slop

1. the biggest problem is the ledger row: the site's signature device (label column, detail column, hairline between rows) is hand-built ten times across eight files with seven different column specs and three different row paddings, and the seam above it is hand-built three more times. nothing owns the grammar, so every page drifts a little.
2. second, the small-caps label has nine different specs (10px, 11px, 13px, text-xs, text-sm; tracking 0.08em, 0.14em, 0.18em, wider, widest, wide) and the hairline has seven tints (ink 10, 15, 25, 30; mint 10, 15, 20). the one voice the design depends on is defined nowhere.
3. third, the contract's component table describes a site that no longer exists (full-bleed coach entries, a wax room card on navy, conditions in the footer, Lucide, a TripEntry that was never built, mint headings on navy) while the shipped devices that replaced them (the seam, the stat stack, the photo band under mastheads) are in the banned list or absent from the contract. every reviewer after this one will re-litigate the same accepted decisions until DESIGN.md v2 records them.
4. the biggest opportunity is to give the site five real primitives (Seam, Ledger, FactStack, Button, PhotoStrip) plus three utilities (.label-caps, .hairline, .link-inline) and a three-step band rhythm. that is roughly 400 lines of markup removed, and it is what makes the next round of pages come out on-brand by default instead of by care.
5. overall read: the visual layer is already quiet and mostly slop-free (no shadows, no hover lift, no gradients except the two functional scrims, no card grid on home, no pills); the slop lives in the code, where every good decision was made by hand and never promoted to a component or a token.

## findings

### CS-1
- surface: community, racing, dry-tri, extra-training-fun, sponsors, 404, trips, wax-room, home (wax feed) / all / all
- kind: slop
- severity: P2
- contract: proposed: "the ledger (label column, detail column, hairline rows) is a component with fixed column presets; pages never hand-build rows."
- evidence: site/src/pages/community.astro:109-123, site/src/pages/racing.astro:52-71, site/src/pages/dry-tri.astro:61-69, site/src/pages/extra-training-fun.astro:36-46 and 77-84, site/src/pages/sponsors.astro:49-56 and 96-103, site/src/pages/404.astro:56-70, site/src/components/TripsTable.astro:13-50, site/src/components/WaxRoomFeed.astro:34-59; community-default-desktop.png, extra-training-fun-default-desktop.png, racing-default-desktop.png
- observation: the same row grammar is built ten times with seven column specs (`[minmax(14rem,18rem)_1fr]`, `[10rem_1fr_1fr]`, `[10rem_1fr_8rem]`, `[16rem_1fr]` twice, `[minmax(12rem,16rem)_1fr]`, `[8rem_1fr_minmax(8rem,auto)]`, `[8.5rem_1fr_auto]`), three paddings (py-4, py-5, py-6), two gaps (gap-x-6, gap-x-8), and four rule tints. visual-redesign names this ("no whitespace system: random mt-4, mt-6, mt-3 with no pattern") and awwwards-sections ("sections are not islands").
- proposal: one `<Ledger>` component in site/src/components with `cols: 'two' | 'three' | 'stacked'` (two = `md:grid-cols-[14rem_1fr]`, three = `md:grid-cols-[8rem_1fr_minmax(8rem,auto)]`, stacked = no grid), `rule: 'top' | 'y' | 'none'`, `surface: 'paper' | 'navy'`, and a `<LedgerRow>` slot with `label`, `detail`, optional `href`, optional `meta`. row padding fixed at py-5, gap-x-6, hover is text-to-mint-deep only. TripsTable, WaxRoomFeed, the races list, the course list, both etf lists, both sponsor lists, the community takeaways and the 404 destinations all become Ledger call sites.
- workstream: motion-components

### CS-2
- surface: home, community, dry-tri, extra-training-fun, sponsors / all / all
- kind: slop
- severity: P2
- contract: proposed: "the seam (small-caps label plus hairline to the right edge) is the section opener site-wide, built by one component."
- evidence: site/src/components/SectionBand.astro:27-34, site/src/components/PhotoMosaic.astro:125-131, site/src/components/WaxRoomFeed.astro:26-28, site/src/components/LiveConditions.astro:36
- observation: the seam markup (`flex items-center gap-4`, `text-[11px] tracking-[0.18em] uppercase font-semibold`, `h-px flex-1 bg-mint/20|bg-ink/15`) is copied in three components, and the trail report label repeats the type spec a fourth time without the rule. PhotoMosaic re-implements SectionBand's container (`safe-inline-6-10 max-w-7xl mx-auto px-6 md:px-10 pt-12 md:pt-16`) to do it.
- proposal: extract `<Seam label? surface>` (label optional so the mosaic and wax feed keep their rule-only form) and mount it from SectionBand, PhotoMosaic and WaxRoomFeed. the label uses `.label-caps-wide` (CS-5). the trail report label reuses the same utility.
- workstream: motion-components

### CS-3
- surface: home (mission panel), about, community, racing, dry-tri, extra-training-fun, coaches / all / all
- kind: slop
- severity: P2
- contract: proposed: "org facts render through one FactStack (value over small-caps label behind a left hairline); max three per surface; no boxes."
- evidence: site/src/components/MissionPanel.astro:19-28, site/src/components/HeroInner.astro:34-41; home-open-desktop.png, about-open-desktop.png
- observation: the same stat stack is built twice with different values: `space-y-5 md:pl-7 self-center mt-1.5 text-2xl md:text-3xl` on home versus `space-y-3 md:pl-6 self-end mt-0.5 text-base md:text-lg` on inner mastheads. same device, two rhythms, one of them vertically centered and the other bottom-aligned.
- proposal: `<FactStack facts size="lg|md" align="center|end">` owning the hairline (`md:border-l hairline`), the gap (`space-y-4`), the label (`.label-caps mt-1`), and the two value sizes. MissionPanel passes `size="lg"`, HeroInner `size="md"`. the `big` flag on MissionPanel goes away; the year and the count read at the same size as the cities line.
- workstream: motion-components

### CS-4
- surface: home, community, racing, dry-tri, extra-training-fun, 404 / all / all
- kind: slop
- severity: P2
- contract: proposed: "inline text links on paper: navy, underline offset 4, ink-30 decoration, mint-deep on hover; one utility."
- evidence: site/src/pages/index.astro:120, site/src/pages/community.astro:116, site/src/pages/racing.astro:62, site/src/pages/dry-tri.astro:81 and 87, site/src/pages/extra-training-fun.astro:89, site/src/pages/404.astro:63, site/src/components/TripsTable.astro:24, site/src/components/WaxRoomFeed.astro:32, site/src/components/PhotoMosaic.astro:135
- observation: `underline underline-offset-4 decoration-ink/30 hover:decoration-mint-deep hover:text-mint-deep transition-colors` is pasted seven times (404 varies it to decoration-ink/25 and group-hover), and three other link treatments coexist: `text-mint-deep underline` (trips empty state), `text-mint-deep hover:text-navy` (wax feed), `text-mint/80 hover:text-mint` (mosaic). visual-redesign: "className strings are slop; consolidate."
- proposal: `@layer components { .link-inline { ... } .link-inline-navy { ... } }` in global.css with the seven-class string as the paper form and `text-mint/85 hover:text-mint underline decoration-mint/40` as the navy form; every call site becomes one class. the "see what members do" and "all entries" links adopt the same treatment as "about our sponsors" so the three section-closer links read as one.
- workstream: foundations

### CS-5
- surface: all / all / all
- kind: slop
- severity: P2
- contract: proposed: "small-caps labels come in two sizes only: label-caps (0.6875rem, 0.14em, 600) and label-caps-wide (0.6875rem, 0.18em, 600, seams and the trail report only). no other uppercase spec."
- evidence: site/src/components/SectionBand.astro:30, site/src/components/LiveConditions.astro:36, 50, 78, 95, 101, site/src/components/HeroInner.astro:38, site/src/components/MissionPanel.astro:25, site/src/components/SeasonsGrid.astro:109, site/src/components/TripsTable.astro:16, site/src/components/WaxEntry.astro:65, 71, 77, site/src/components/Footer.astro:29, site/src/pages/racing.astro:57, site/src/pages/dry-tri.astro:66, site/src/pages/404.astro:41
- observation: nine distinct uppercase specs ship: `text-[11px] tracking-[0.18em] font-semibold`, `text-[11px] tracking-[0.14em]`, `text-[11px] tracking-[0.14em] font-semibold`, `text-[10px] tracking-widest`, `tracking-widest` at text-xs, `text-[11px] tracking-wider`, `text-sm tracking-wider`, `text-xs tracking-wide`, `text-[13px] tracking-[0.08em] font-bold`, plus a non-uppercase `text-sm tracking-[0.08em]` eyebrow on 404. thirteen `text-[Npx]` arbitrary sizes carry this. the spec's success criterion is "no ad-hoc font size outside the tokens".
- proposal: add to tailwind.config.ts `fontSize: { caps: ['0.6875rem', { lineHeight: '1', letterSpacing: '0.14em', fontWeight: '600' }] }` and in global.css `@layer components { .label-caps { @apply text-caps uppercase; } .label-caps-wide { @apply label-caps tracking-[0.18em]; } }`. race dates and course start times drop uppercase and render as `text-sm text-mint-deep tabular-nums` (data, not labels). the footer wordmark keeps display but uses `.label-caps` tracking. the 404 eyebrow becomes `.label-caps text-mint-deep`.
- workstream: foundations

### CS-6
- surface: all / all / all
- kind: slop
- severity: P2
- contract: proposed: "two hairlines only: hairline (ink 15% on paper, mint 15% on navy) for section and grid rules; hairline-soft (ink 10%, mint 10%) for row dividers and the nav/footer edge."
- evidence: site/src/components/HeroInner.astro:27, 34, site/src/components/CoachEntry.astro:53, site/src/components/SeasonsGrid.astro:75, site/src/components/SectionBand.astro:24, site/src/components/Nav.astro:10, site/src/components/Footer.astro:26, site/src/components/LiveConditions.astro:23, 27, 48, 76, site/src/components/Lightbox.astro:31-32, site/src/pages/sponsors.astro:49, 87, 96, site/src/pages/404.astro:56, 63, site/src/pages/dry-tri.astro:36, 61, site/src/pages/community.astro:72, 109
- observation: rules use `ink/10` (15 uses), `ink/15` (12), `ink/25` (1), `ink/30` (6, link decoration), `mint/10` (4), `mint/15` (4), `mint/20` (5), `paper/30` (2). the same physical hairline is a different gray on every page. visual-redesign: "border: 1px solid #dee2e6 ... commit to a border token."
- proposal: global.css `@layer utilities { .hairline { border-color: theme(colors.ink / 15%); } .hairline-soft { border-color: theme(colors.ink / 10%); } .bg-navy .hairline, .bg-navy-deep .hairline { border-color: theme(colors.mint / 15%); } .bg-navy .hairline-soft, .bg-navy-deep .hairline-soft { border-color: theme(colors.mint / 10%); } }` plus matching `.rule` (background) and `.divide-hairline` forms, following the focus-ring inheritance pattern already in global.css:71-85. link decoration uses ink/30 on paper and mint/40 on navy, defined once in CS-4. the lightbox buttons use paper/30 today and adopt `.hairline` on the ink surface.
- workstream: foundations

### CS-7
- surface: home (nav, hero, cta strip, mobile nav), about (cta), sponsors (cta strip), 404, lightbox / all / all
- kind: slop
- severity: P2
- contract: proposed: "one button: rounded-md, px-5 py-3, font-semibold text-sm, mint fill on navy (hover paper) or navy fill on paper (hover navy-deep); content-width at every viewport. no other button shapes."
- evidence: site/src/components/CtaForState.astro:28-30, site/src/components/CTAStrip.astro:64-68, site/src/pages/404.astro:48-51, site/src/components/Lightbox.astro:30-33; home-open-mobile.png (tile 4), home-hero-mobile.png, home-lightbox-desktop.png
- observation: four button definitions ship. CtaForState is the reference. CTAStrip's anchor is a second copy with `px-6` instead of `px-5`, no `text-sm`, and no hover state at all. the 404 "back to home" hand-builds CtaForState's `on-paper` variant (which is itself never passed by any caller) with `min-h-11` added. the lightbox prev/next use `rounded` (4px) with `border border-paper/30` and arrow glyphs, a third shape and a second radius. on mobile the strip button stretches full-width (flex-col child) while the hero button above it is content-width.
- proposal: `<Button variant="on-navy|on-paper" href>` (or a `.btn` component class) owning the CtaForState string; CTAStrip, 404 and the sponsors strip render it. the strip's anchor gets `self-start`. lightbox prev/next become icon buttons (CS-23) with `rounded-md`. delete the unused `on-paper` branch from CtaForState once Button exists, or make CtaForState wrap Button.
- workstream: motion-components

### CS-8
- surface: all / all / all
- kind: slop
- severity: P3
- contract: "slate ... Secondary body on paper. Captions, dates, meta."
- evidence: site/src/pages/community.astro:122, site/src/pages/racing.astro:69, site/src/pages/dry-tri.astro:65, site/src/pages/extra-training-fun.astro:43, 81, 85, site/src/pages/sponsors.astro:46, 53, 81, 92, 100, site/src/components/WaxEntry.astro:99, site/src/pages/wax-room/index.astro:38, site/src/components/SectionBand.astro:41
- observation: secondary text on paper is written five ways: `text-ink/80` (6), `text-ink/75` (2), `text-ink/90` (2), `text-slate` and `opacity-90`. on navy it is `text-paper/85`, `/80`, `/75`, `/70`, `/60`, `/55`, `/50`. thirteen tints do the job of three tokens. the contract already names slate for this.
- proposal: on paper, secondary body is `text-slate` and nothing else (drop every `text-ink/N`; the SectionBand subhead drops `opacity-90`). on navy, define two utilities in global.css, `.text-navy-body` = paper/85 and `.text-navy-meta` = paper/65, and replace the seven paper tints with them. the seasons registration note keeps the body tint, since the July round set its /75 floor for contrast at 13px. color lens verifies contrast; this lens asks for the count to drop from thirteen to three.
- workstream: foundations

### CS-9
- surface: about, community, racing, dry-tri, extra-training-fun, trips, wax-room / all / all
- kind: slop
- severity: P2
- contract: proposed: "long-form content on inner pages mounts in one ProseColumn (max-w-3xl, band-y-sm)."
- evidence: site/src/pages/about.astro:38-41, site/src/pages/community.astro:68-71, site/src/pages/racing.astro:44-48, site/src/pages/dry-tri.astro:73-76, site/src/pages/extra-training-fun.astro:29-33, site/src/pages/trips/index.astro:12-14, site/src/pages/wax-room/index.astro:18
- observation: `safe-inline-6 mx-auto max-w-3xl px-6 py-12` wraps `prose prose-lg max-w-prose text-ink` on five pages, with `pb-12` on dry-tri, `py-12 md:py-16` on the wax room, `max-w-4xl` on trips, and about alone carrying `[&_h2]:font-semibold [&_h2]:tracking-tight` overrides. dry-tri's `## 2025` and `## 2026` headings therefore render with the typography plugin's default weight while about's `## Who joins TCSC` renders semibold tight (dry-tri-default-desktop.png versus about-open-desktop.png).
- proposal: `<ProseColumn>` in components with the wrapper and the prose classes fixed; move the h2 override into the typography theme in tailwind.config.ts (`h2: { fontWeight: '600', letterSpacing: '-0.01em', color: palette.navy }`) so every markdoc body agrees. trips adopts max-w-3xl.
- workstream: motion-components

### CS-10
- surface: all / all / all
- kind: slop
- severity: P3
- contract: proposed: "safe-inline-* utilities own the horizontal gutter; call sites do not add px-*."
- evidence: site/src/styles/global.css:54-65; 27 of 28 `safe-inline` call sites also carry `px-6` or `px-6 md:px-10` (grep `safe-inline-6[^"']*px-6`); built css scripts/brand-review/builds/open/_astro/Footer.*.css (safe-inline rules are unlayered, `.px-6` sits inside `@layer utilities`)
- observation: `.safe-inline-6` sets padding-left and padding-right outside any cascade layer, so it beats the layered `px-6` utility on every element. the `px-6 md:px-10` beside it is dead weight on 27 lines and misleads readers into thinking the gutter is 24px (it is `max(1.5rem, safe-area + .75rem)`, which is the same number, by coincidence, until a cutout appears).
- proposal: delete `px-6` and `px-6 md:px-10` wherever a `safe-inline-*` class is present. rename the utilities `.gutter` and `.gutter-wide` so the intent reads. one place, one number.
- workstream: motion-components

### CS-11
- surface: shared components / all / all
- kind: slop
- severity: P3
- contract: "No card-shaped components anywhere on the home page."
- evidence: site/src/components/SectionBand.astro:3, 11, 15-22, 40-42 (`paper-on-navy`, `contentMax`, `subhead`: no call site passes any of them, grep `<SectionBand` in pages), site/src/components/CtaForState.astro:10, 30 (`on-paper` never passed), site/src/components/PhotoMosaic.astro:24, 42 (`limit` never passed)
- observation: five props and one variant are dead. the dead `paper-on-navy` variant is also the only `rounded-xl` on the site and describes exactly the floating card the contract bans on home; it still emits css because tailwind scans the source.
- proposal: remove `paper-on-navy`, `contentMax` and `subhead` from SectionBand (MissionPanel is the paper moment and owns its own markup), remove `on-paper` from CtaForState once CS-7 lands, remove `limit` from PhotoMosaic or use it. dead props are dead css.
- workstream: motion-components

### CS-12
- surface: all / all / all
- kind: slop
- severity: P3
- contract: proposed: "global.css and tailwind.config.ts ship only rules the site uses."
- evidence: site/tailwind.config.ts:2, 75; built css contains 12 `[type=checkbox]`, 8 `[type=radio]`, 4 `select:where`, 3 `::-webkit-date-and-time-value` rules; `grep -rn '<form\|<input\|<select\|<textarea' site/src` returns 0
- observation: `@tailwindcss/forms` is loaded and its full form reset ships in the 63KB stylesheet, and the site has no form, input, select or textarea anywhere.
- proposal: drop the `forms` import and plugin entry. the devDependency can stay in package.json (removing it is a package change the rules do not need); the config change is enough to stop shipping the css.
- workstream: motion-components

### CS-13
- surface: all / all / all
- kind: slop
- severity: P3
- contract: "Any color outside the tokens above." (banned)
- evidence: site/src/styles/global.css:41-42 (`background: oklch(0.25 0.06 260); color: oklch(0.18 0.04 260)`), site/src/layouts/BaseLayout.astro:32 (`themeColor = '#202A44'`), site/src/components/Nav.astro:17, 30 (`#aaf0c1`, `#fbfbfa`, deliberate per the June spec)
- observation: navy and ink are written as raw literals in global.css and BaseLayout rather than through the theme. the config comment says the tokens are the single source, and they are not.
- proposal: `html { background: theme(colors.navy); color: theme(colors.ink); }` and export a `NAVY_HEX` constant from a small `site/src/lib/brand.ts` (or read `palette.navy` from the config) for the theme-color meta. the logo fills stay literal by the June decision; note that exception in the contract.
- workstream: foundations

### CS-14
- surface: all / all / all
- kind: slop
- severity: P3
- contract: "Display moments only ... The display cut is used at most 2-3 places per page"
- evidence: site/src/styles/global.css:87-96 (comment: "font-semibold at call sites still applies but is redundant"), 17 `font-display font-semibold` pairs across components and pages
- observation: every display heading carries `font-semibold` that the utility comment admits is redundant, and `.font-display` sets `font-stretch: 100%` for a face with no width axis. the fallback weight belongs in the utility, not in seventeen call sites.
- proposal: `.font-display { font-weight: 600; letter-spacing: -0.02em; }` (drop font-stretch), then delete `font-semibold` from every `font-display` element. the fallback face still renders semibold.
- workstream: foundations

### CS-15
- surface: all / all / all
- kind: slop
- severity: P3
- contract: "No animations on layout properties. Transform and opacity only."
- evidence: site/src/components/Nav.astro:47, site/src/components/CtaForState.astro:29-30, site/src/components/TripsTable.astro:38, 42, site/src/components/WaxRoomFeed.astro:44, site/src/pages/community.astro:116, site/src/pages/404.astro:50, 63, site/src/pages/wax-room/index.astro:29, site/src/pages/index.astro:120
- observation: hover transitions are written three ways: `transition-colors duration-150` (7), `transition-colors` (9), and bare `transition` (7, which animates every animatable property including layout). tailwind's default duration is already 150ms.
- proposal: one form, `transition-colors`, everywhere; delete every `duration-150` and every bare `transition`. this is class dedup, and it also closes the layout-property loophole the contract names.
- workstream: motion-components

### CS-16
- surface: wax-room / populated / all; home / wax-feed / all
- kind: slop
- severity: P2
- contract: "`<WaxRoomFeed>` ... three most recent wax room entries with date, title, one-line excerpt."
- evidence: site/src/pages/wax-room/index.astro:22-41, site/src/components/WaxRoomFeed.astro:34-59; wax-room-populated-desktop.png, home-wax-feed-desktop.png
- observation: the same entry renders in two grammars: a one-line ledger row on home (date · author / title + lede / temp · venue) and a stacked article on the index (long date / h2 / by line / lede). the index has no hairline rows, no temperature, and a different date format ("Sunday, November 22, 2026" versus "Nov 22").
- proposal: `<WaxEntryRow entry density="feed|index">` used by both. the index keeps the long date and adds the conditions meta on the right; the feed keeps its density. the list container is CS-1's Ledger with `rule="y"`.
- workstream: motion-components

### CS-17
- surface: footer / all / all
- kind: slop
- severity: P3
- contract: "`<Footer>` ... Three columns: contact, navigation, social."
- evidence: site/src/components/Footer.astro:12-24, site/src/content/nav.yaml, site/src/components/navLinks.ts:10-17
- observation: the six top-nav labels exist in three places (nav.yaml, the navLinks fallback, and Footer's colA/colB). the July round asked the footer to follow nav order; it does so by copy, so a nav.yaml edit silently desyncs it.
- proposal: Footer calls `getNavLinks()` for column A and appends the three extras (Trips, Extra Training & Fun, Dry Tri) from one `FOOTER_EXTRAS` constant in navLinks.ts.
- workstream: motion-components

### CS-18
- surface: all / all / all
- kind: slop
- severity: P3
- contract: proposed: "site_meta.yaml is the only source for the default description."
- evidence: site/src/layouts/BaseLayout.astro:22, site/src/content/site_meta.yaml:4-6
- observation: the default meta description is the same sentence typed twice, once in yaml and once as a literal default in BaseLayout.
- proposal: BaseLayout reads `getEntry('site_meta','site_meta')` for its default (it already fetches season data at that level), keeping a one-word literal fallback only for a missing singleton.
- workstream: copy

### CS-19
- surface: dry-tri / default / all
- kind: slop
- severity: P3
- contract: "No decorative icons in headings or bullets." (and the leg names are information)
- evidence: site/src/pages/dry-tri.astro:17-21 (`label: 'Roll' | 'Ride' | 'Run'`), 36-56 (label never rendered); dry-tri-default-desktop.png
- observation: the triptych computes a label per leg and throws it away; the three photos sit in a bordered box (`border border-ink/10` around a `gap-px` grid) with no caption, so a visitor cannot tell which leg is which, and the outer border is the only framed photo group on the site.
- proposal: drop the outer border, keep `gap-px` on the hairline background, and render each label as a `<figcaption class="label-caps text-mint-deep mt-2">` under its photo. this uses data that is already there and turns the only card-like frame on the site into a captioned strip.
- workstream: sections

### CS-20
- surface: sponsors / default / all
- kind: slop
- severity: P2
- contract: "Body line length capped at 62ch on paper, 56ch on navy" and SectionBand "Takes optional numbered marker, heading, optional subhead, children."
- evidence: site/src/pages/sponsors.astro:43, 46, 78, 81, 87-104, 89, 92, 100, 107-111; sponsors-default-desktop.png
- observation: sponsors is the one page that ignores its own components. it hand-builds three h2s with SectionBand's heading class string (`font-display font-semibold text-4xl md:text-5xl leading-[1.05]`), writes the measure cap as arbitrary values (`max-w-[56ch]`, `max-w-[62ch]` twice, `max-w-[52ch]`) when `max-w-prose` and `max-w-prose-narrow` are the tokens for exactly those numbers, nests a second section ("What continued support makes possible") inside the "Partner recognition" band with a hand-rolled `mt-20 md:mt-28 pt-12 md:pt-16 border-t` seam, and floats the disclosure paragraph in a bare `pb-8` div at `max-w-7xl` between the band and the CTA strip so it lands at a different left edge than everything above it.
- proposal: three SectionBands (`seam="Sponsor impact"`, `seam="Partner recognition"`, `seam="What continued support makes possible"`) each using the `heading` prop; measures become `max-w-prose` (paper) and `max-w-prose-narrow` (navy); the two item lists become Ledger rows (CS-1); the disclosure becomes a `text-sm text-slate` line inside the last band's column. the sponsors-page tests check copy order and mobile text size (tests/sponsors-page.test.mjs:135, 189), not markup, so the restructure is free.
- workstream: sections

### CS-21
- surface: dry-tri, extra-training-fun, community, sponsors / default / all
- kind: slop
- severity: P2
- contract: proposed: "a seamed band does not draw a second rule above its first row."
- evidence: site/src/pages/extra-training-fun.astro:36 and 77 (`border-t` under a seam), site/src/pages/dry-tri.astro:61, site/src/pages/community.astro:109, site/src/pages/sponsors.astro:49 (`border-y`); extra-training-fun-default-desktop.png (tile 1, "standing invitations"), dry-tri-default-desktop.png ("the course")
- observation: under every seam on these pages the list draws its own `border-t`, so two hairlines run 40px apart with nothing between them. the seam rule is the top rule; the second one is the ledger being built by hand without knowing it sits under a seam.
- proposal: Ledger (CS-1) defaults to `rule="between"` and only draws a top rule when mounted without a seam (racing's "Races" h2, the wax room index). visually the seam, the first row and the rest of the list read as one ruled column.
- workstream: sections

### CS-22
- surface: community / default / all
- kind: drift
- severity: P2
- contract: "Vertical rhythm: sections breathe variably ... Same-spacing-everywhere is monotony." and PhotoMosaic "The photo wall is paper-on-navy on the home page (photos sit inside ... frames against the navy surface)."
- evidence: site/src/components/PhotoMosaic.astro:123 (`!heading && 'pt-20'`); community-default-desktop.png (tile 3: an 80px bare navy stripe above the grid)
- observation: on community the mosaic mounts without a heading, so `pt-20` produces an empty navy band between the paper ledger and the first photo row. it reads as a rendering gap, not a pause.
- proposal: when `heading` is absent the section starts flush (`pt-0`) or mounts the rule-only Seam (CS-2) at `pt-12`; the navy surface then means something (a seam) rather than nothing. on home the heading path is unchanged.
- workstream: sections

### CS-23
- surface: lightbox / open / all; home / hero / all
- kind: drift
- severity: P3
- contract: "'→' on every link. Reserved for the home hero CTA." (banned list) and "Lucide ... Used sparingly: hamburger, lightbox close ... No icons in CTAs."
- evidence: site/src/components/Lightbox.astro:30-33 (`←` `→` as button text), site/src/components/HeroHome.astro:65-74 (no arrow on the hero CTA), site/src/components/Nav.astro:66-67 and Lightbox.astro:20-22 (hand-drawn inline svg strokes, not Lucide)
- observation: the only arrows on the site are the lightbox prev/next glyphs, and the one place the contract reserves the arrow for (the hero CTA) does not use it. the close button beside them is an svg stroke, so the three lightbox controls mix a glyph style and an icon style. no Lucide is imported anywhere; the hamburger and close are inline paths.
- proposal: lightbox prev/next become the same 24px stroke-2 inline chevron paths as the close button, `rounded-md`, `.hairline` border. contract change: drop the hero-arrow reservation (the site has proven it does not need it) and replace "Lucide" with "inline 24px stroke-2 svg paths; three icons exist (menu, close, chevron); no icon library".
- workstream: motion-components

### CS-24
- surface: home / live conditions / desktop
- kind: drift
- severity: P3
- contract: "No decorative icons in headings or bullets."
- evidence: site/src/components/LiveConditions.astro:80 (`♪` inside the Birkie fever label), LiveConditions.client.ts:248-263
- observation: the ♪ is the play affordance for the fever song, sitting inside a small-caps label. it is the one glyph-as-icon in a label on the site. it carries information (the cell is a button), so it is defensible, but the contract does not know about it.
- proposal: keep it, record it: contract exception "the Birkie fever cell carries a ♪ as its play affordance, aria-hidden, md+ only." if the synthesis agent would rather not carve an exception, the alternative is the word "play" in `.label-caps text-mint/50` after the label, which says the same thing in the site's own voice.
- workstream: sections

### CS-25
- surface: home (mission panel), about, community, racing, dry-tri, extra-training-fun, coaches / all / all
- kind: drift
- severity: P3
- contract: "Stat boxes with big mint numbers." (banned) versus the June round (accepted: "stat-stack treatment ... vertical hairline variant")
- evidence: site/src/components/MissionPanel.astro:9-13, 19-28, site/src/components/HeroInner.astro:34-41, docs/superpowers/specs/2026-06-11-marketing-site-design-feedback-design.md sections 4 and 5
- observation: the shipped stat stacks are not boxes and the numbers are navy, not mint, so they pass the letter of the ban, but the contract still reads as if they are forbidden. the next reviewer will propose removing them again.
- proposal: contract change: replace the banned line with "stat boxes (tinted or bordered slabs) and mint-colored numbers are banned; the FactStack (value in navy over a small-caps label, behind one hairline, max three) is the sanctioned form." no code change.
- workstream: sections

### CS-26
- surface: wax-entry / default / all
- kind: drift
- severity: P2
- contract: "Soft-tinted gray cards on paper. If a card needs definition, give it a 1px ink-15% rule or a clear background, not a gray drop-shadowed slab." (banned)
- evidence: site/src/components/WaxEntry.astro:62-82 (`bg-paper-card p-4 rounded-md`); wax-entry-default-desktop.png, wax-entry-default-mobile.png
- observation: the conditions snapshot is the one gray-tinted rounded slab on the site. it is exactly the pattern the contract bans, and it is the only `rounded-md` on a non-button.
- proposal: render the snapshot as a ruled row: `<dl class="mt-6 border-y hairline py-3 flex flex-wrap gap-x-8 gap-y-2 text-sm">` with each `<dt>` in `.label-caps text-slate` and the `<dd>` in ink. same three fields, ledger grammar, no fill, no radius. drop `paper-card` from this component; the token keeps its use as the mosaic tile placeholder.
- workstream: sections

### CS-27
- surface: home / dryland / desktop
- kind: drift
- severity: P2
- contract: "Sparse data fallback ... Never broken; always intentional."
- evidence: site/src/components/LiveConditions.astro:76 (`md:border-l md:border-mint/15 md:pl-4` on the fever button), LiveConditions.client.ts:119-122 (venue cells hidden off-season); home-dryland-desktop.png (a lone vertical rule at the strip's left edge)
- observation: off-season the four venue cells are hidden and the Birkie fever cell becomes the first visible child, but it keeps its left border and left padding, so a stray hairline hangs at the far left of the strip with nothing to its left. the desktop dryland state, which is what production shows for six months, opens with a broken-looking rule.
- proposal: css-only, no client change: move the rule to the venue cells' right edge (`md:border-r md:border-mint/15 md:pr-5` on `[data-location]` cells, and drop `md:border-l md:pl-4` from the fever button). hidden venues take their rules with them; the fever cell never carries one.
- workstream: sections

### CS-28
- surface: home / open, soon, closed / mobile
- kind: drift
- severity: P3
- contract: "`<CTAStrip>` ... single mint-filled CTA" (and CS-7)
- evidence: site/src/components/CTAStrip.astro:59 (`flex flex-col md:flex-row`), 64-68; home-open-mobile.png (tile 4), home-hero-mobile.png
- observation: on a phone the strip's button stretches to the full column while the hero's identical button 3000px above is content-width. the same label, two widths, one page.
- proposal: `self-start` on the strip anchor (or the Button primitive sets `self-start` by default). one width rule for buttons at every viewport.
- workstream: sections

### CS-29
- surface: home / open / mobile
- kind: elevation
- severity: P3
- contract: proposed: "section header rows (heading plus closer link) stack left-aligned under 768px."
- evidence: site/src/components/PhotoMosaic.astro:132-137 (`flex flex-wrap items-end justify-between`, link `ml-auto`), site/src/components/WaxRoomFeed.astro:30-33 (`flex items-end justify-between`, no wrap); home-open-mobile.png (tile 3: "See what members do" right-aligned on its own row under "Beyond practice")
- observation: the mosaic header wraps on mobile and the link jumps to the right edge on a second row; the wax feed header does not wrap at all, so a long entry title would collide with "All entries". two hand-built header rows, two behaviours.
- proposal: one `<SectionHeader heading more_href more_label>` used by both (and by the sponsors strip), `flex flex-col items-start gap-2 md:flex-row md:items-end md:justify-between`. the closer link uses `.link-inline` (CS-4).
- workstream: motion-components

### CS-30
- surface: all / all / all
- kind: slop
- severity: P2
- contract: "Vertical rhythm: sections breathe variably (96-144px y-padding on home, 64-104px on inner). Same-spacing-everywhere is monotony."
- evidence: SectionBand.astro:20-22 (`pb-20 md:pb-28`, `pt-8 md:pt-10`, `pt-20 md:pt-28`, `pt-12 md:pt-16`), PhotoMosaic.astro:123-125 (`pb-20`, `pt-20`, `pt-12 md:pt-16`), WaxRoomFeed.astro:26-29 (`pt-12 md:pt-16`, `pt-8`, `pb-16 md:pb-20`), MissionPanel.astro:15-17 (`pt-14 md:pt-20`, `py-14 md:py-20`), CTAStrip.astro:59 (`py-16 md:py-20`), HeroInner.astro:28 (`py-10 md:py-14`), CoachEntry.astro:56 (`py-12 md:py-16`), Footer.astro:27 (`pt-14 pb-14`), pages: `py-12`, `pb-12`, `py-12 md:py-16`, `py-14 md:py-20`, `pt-14 md:pt-20`, `py-16 md:py-20`, `py-16 md:py-24`
- observation: twenty-one distinct band paddings, none of them a scale. variety without a system is the same crime as monotony (visual-redesign: "no whitespace system"). the visible symptom is home: dues line to "Beyond practice" seam is `pb-28 + pt-16 + mt-8` (~200px) while mission panel to seasons seam is `pt-14 + pt-16` (~120px); on inner pages a prose column ends in `py-12` (48px) and the next band opens with `pt-12 md:pt-16`, so paper-to-paper joins are tighter than the contract's 64px floor.
- proposal: three band tokens in global.css, `--band-sm: clamp(3rem, 6vw, 4rem)`, `--band: clamp(4rem, 8vw, 6.5rem)`, `--band-lg: clamp(6rem, 10vw, 9rem)`, exposed as `.band-y-sm`, `.band-y`, `.band-y-lg` (and `-t`/`-b` halves). SectionBand takes `rhythm: 'sm' | 'md' | 'lg'` (default md on inner, lg on home). seam-to-content gap is one value (`pt-8`). every page-level `py-N` becomes one of the three. the sections lens will choose which band gets which size; this lens asks that there be three sizes to choose from.
- workstream: foundations

### CS-31
- surface: inner pages / all / desktop
- kind: drift
- severity: P2
- contract: "Max content width 1280px on home (the photo mosaic needs room); 1080px on inner pages (long-form prefers tighter measure)."
- evidence: HeroInner.astro:28, SectionBand.astro:19, CTAStrip.astro:59, Footer.astro:27, LiveConditions.astro:35, 90, PhotoMosaic.astro:125 (`max-w-7xl` = 1280 everywhere), pages/trips/index.astro:12 (`max-w-4xl`), pages/sponsors.astro:26 (`max-w-5xl`), CoachEntry.astro:56 (`max-w-6xl`), prose columns `max-w-3xl`
- observation: no inner surface uses the contract's 1080. bands use 1280, and the pages then pick 768, 896, 1024 and 1152 for their own columns, so inner pages have five widths and none of them is the one the contract names.
- proposal: add `maxWidth: { inner: '67.5rem' }` (1080) to tailwind.config.ts; HeroInner, SectionBand (inner), CTAStrip (inner), Footer, the compact conditions strip, the sponsor wall, CoachEntry and the trips table use `max-w-inner`; long-form prose keeps `max-w-3xl`; home keeps `max-w-7xl`. two widths per register, from the contract.
- workstream: foundations

### CS-32
- surface: home, sponsors, extra-training-fun / all / all
- kind: drift
- severity: P2
- contract: "`<SeasonsGrid>` On navy (home): mint headings" and "mint ... primary reading color for headings, key body text" versus the site
- evidence: SeasonsGrid.astro:91 (season names inherit paper), PhotoMosaic.astro:133 (`text-paper`), SectionBand.astro:38 (heading inherits paper on navy), pages/sponsors.astro:43 (`text-mint`), CTAStrip.astro:61 (`text-mint`), pages/extra-training-fun.astro:40 (`text-paper`)
- observation: display headings on navy are paper in three components and mint in two. the contract says mint. the site, mostly, says paper, and the paper headings read calmer next to the mint data in the conditions strip.
- proposal: pick paper. contract change: "on navy, display headings are paper; mint is reserved for the CTA strip heading, live data (temperatures, fever), fact labels and links." sponsors' impact h2 becomes paper. one rule, and mint stops competing with itself.
- workstream: sections

### CS-33
- surface: about / open, closed / all; home / open / all
- kind: drift
- severity: P2
- contract: "`<SectionBand>` ... Takes optional numbered marker ... heading" and CS-2
- evidence: pages/index.astro:104 (`seam="Seasons"`, no heading), pages/about.astro:51 (`heading="Seasons"`, no seam); home-open-desktop.png (tile 1), about-open-desktop.png (tile 2)
- observation: the same section opens with an 11px small-caps seam on home and a 48px display h2 on about. same component, same content, opposite grammar; on about the band also switches to `pt-20 md:pt-28` because no seam means no seam padding.
- proposal: about uses `seam="Seasons"` like home (the season names are the h2s in both places; pass `headingLevel="h2"` there too). the `heading` prop stays for bands that need a sentence heading under a seam (community, sponsors) but never replaces the seam.
- workstream: sections

### CS-34
- surface: extra-training-fun / default / all
- kind: slop
- severity: P3
- contract: "The photo mosaic itself is asymmetric ... hairline gaps" (the site's photo grammar: PhotoMosaic, community cluster, racing strip, dry-tri legs all use `gap-px`)
- evidence: pages/extra-training-fun.astro:51 (`grid gap-6 md:grid-cols-2`), pages/community.astro:72 (`gap-px bg-ink/15`), pages/racing.astro:73 (`gap-px bg-ink/15`), pages/dry-tri.astro:36 (`gap-px bg-ink/10`), PhotoMosaic.astro:143-148 (`gap-px`)
- observation: four photo groups use hairline gaps; the etf pair uses 24px gutters with captions. it is the one photo group that looks like a different site, and the four hairline groups are four hand-built grids with three different rule tints and three different aspect rules.
- proposal: `<PhotoStrip photos cols="2|3|5" aspect="4/3|3/4|4/5" captions?>` with `gap-px` on `.rule` background; etf, community's cluster, racing's strip and dry-tri's legs become call sites. captions render as a `.label-caps`/`text-sm text-slate` row under the strip so etf keeps its captions inside the shared grammar.
- workstream: motion-components

### CS-35
- surface: trips / empty / all; wax-room / empty / all
- kind: drift
- severity: P2
- contract: proposed: "an empty collection renders one ruled placeholder row in the ledger grammar, with a sentence and one link. never a bare paragraph."
- evidence: components/TripsTable.astro:21-26 (ruled row, sentence, mailto link), pages/wax-room/index.astro:20 (`<p class="text-slate">No entries yet.</p>`), tests/contentRollback.test.mjs:51 (the exact string is asserted); trips-empty-desktop.png, wax-room-empty-desktop.png
- observation: production today shows both empty states. trips is composed (column header, ruled placeholder row, a link). the wax room is four words floating in 200px of paper. the spec asks synthesis for an empty-state clause; this is the evidence.
- proposal: the wax room index mounts Ledger with one placeholder row containing exactly "No entries yet." (keeps the rollback test green) followed by the closer link `.link-inline` to `/` or the conditions strip anchor. the trips placeholder becomes the same Ledger row so the two match. contract clause as above.
- workstream: sections

### CS-36
- surface: 404 / default / all
- kind: drift
- severity: P3
- contract: proposed: "page titles are `<Page> · Twin Cities Ski Club`."
- evidence: pages/404.astro:29 (`Page not found | Twin Cities Ski Club`), every other page `· Twin Cities Ski Club`
- observation: the 404 is the only title with a pipe. the site's separator is the middot, in titles, in the seasons notes, in the conditions strip and in the footer.
- proposal: `Page not found · Twin Cities Ski Club`.
- workstream: copy

### CS-37
- surface: shared components / all / all
- kind: drift
- severity: P2
- contract: the "Components" table and "Iconography" section of DESIGN.md v1
- evidence: HeroInner.astro:27, 44-55 (border-y, optional photo band; contract: "slim navy ruled line below. No image"), MissionPanel.astro:15-16 (full-bleed band; contract: "paper card"), SeasonsGrid.astro:102-115 (labeled fact rows; contract: none), PhotoMosaic.astro:143-148 (`gap-px`; contract: "generous mint or paper frames"), CoachEntry.astro:2-11, 56 (constrained 5/7 split; contract: "full-bleed photo ... name typeset at display scale below"), WaxRoomFeed.astro:22 (paper band; contract: "paper-card-on-navy"), Footer.astro (no conditions strip; contract: "Live conditions strip at the top"), InnerPageLayout.astro:51-53 (compact strip under the nav; contract: footer), MobileNavPanel.astro (no strip; contract: "Live conditions strip pinned to the top of the panel"), LiveConditions.astro:14-19 (Theo, Elm, Hyland, Telemark; contract: Theodore Wirth, Hyland, French Park, Battle Creek), 70-86 (Birkie fever cell; contract: none), state-matrix.md (no click-to-expand; contract: "Click a column → expands"), no `<TripEntry>` exists, no trip detail pages exist, no Lucide import exists
- observation: eleven rows of the component table and the iconography clause describe decisions that were reversed on purpose (most with a comment saying why), and none of the shipped replacements are in the contract. a reviewer holding v1 will mark every one of these as drift and propose undoing accepted work.
- proposal: synthesis rewrites the table to the shipped site: HeroInner (ruled masthead, FactStack, optional full-bleed photo band 230/280px), MissionPanel (full-bleed paper band, 8/3 split, FactStack), SeasonsGrid (hairline cells, fee + note row, three fact rows), PhotoMosaic (hairline grid, composed fallback under 12, bottom caption scrim on hover), CoachEntry (5/7 split, 4:5 attention-cropped portrait, credentials list), WaxRoomFeed (paper band, ledger rows), CTAStrip (as is), Footer (brand / nav in nav order / contact; no strip), LiveConditions (four venues from the api, Birkie fever fifth cell md+, compact form under the nav on inner pages, mobile shows Theo only, no expand), MobileNavPanel (no strip), Seam and Ledger and FactStack and Button and PhotoStrip as new rows. delete TripEntry. iconography: inline svg strokes, three icons.
- workstream: sections

### CS-38
- surface: og image / default / all
- kind: elevation
- severity: P2
- contract: proposed: "the og image is a consented club photo with the club logo mark in a navy band along the bottom; 1200x630 jpeg under 200KB; one image for the site plus per-entry photos for wax room posts."
- evidence: site/public/og/og-default.jpg (1200x630, 166KB, photo only, no mark, no navy), pages/wax-room/[slug].astro:23-27 (per-entry og from the entry photo, also unmarked), BaseLayout.astro:24, 63
- observation: the share card is a sunset ski photo with no club identification. it is a good photo, and it could be any club's. the site's two fixed identity elements (navy and the logo) are absent from the one surface that appears next to three other clubs in a Slack or Messages preview, which is the second scene the theme section names.
- proposal: keep the photo. export a new og-default.jpg once: same crop in the top 78%, a navy band across the bottom 22% (138px) carrying the Nav logo mark (mint tracks, paper letters, ~300px wide) at the left gutter. no headline text (titles come from og:title). wax entry og images inherit the same band via a small sharp step in [slug].astro's `getImage` call, or stay as plain photos if the build cost is not wanted; note which in the contract.
- workstream: sections

### CS-39
- surface: shared components / all / all
- kind: elevation
- severity: P3
- contract: proposed: "the site's build tests guard the seam, the hairline utilities and the button primitive so consolidation cannot silently regress them."
- evidence: tests/contentRefinements.test.mjs:130 (asserts the literal `class="bg-navy border-t-[3px] border-coral text-paper"` on CTAStrip's section), tests/responsiveNav.test.mjs:13-23 (nav breakpoint classes), tests/contentRollback.test.mjs:51 ("No entries yet."), tests/sponsors-page.test.mjs:189, 251 (mobile text size, home strip unheaded), tests/seasonBuild.test.mjs (baked CTA variants); no test touches SectionBand, the seam, HeroInner, Footer order (the July spec asked for it), TripsTable's empty state, 404, the lightbox, or any hairline or button class
- observation: what is contract-tested is the registration machinery, the sponsors page copy, and three literal class strings. everything this lens proposes to consolidate is untested, which is why it drifted, and the one guarded string (CTAStrip's section class) will break the moment CS-6 or CS-7 touches it.
- proposal: phase 2 keeps the CTAStrip section class literal byte-for-byte or updates contentRefinements.test.mjs:130 in the same commit. add one small build test (`tests/brandPrimitives.test.mjs`, dist grep) asserting: every page has at most one `label-caps-wide` per seam and no raw `tracking-[0.18em]`; no `text-[Npx]` in dist html; `border-t-[3px] border-coral` appears exactly once per page that mounts CTAStrip; footer links appear in nav order. cheap, and it makes the primitives the contract instead of the class strings.
- workstream: motion-components

### CS-40
- surface: sponsors, home / default / all
- kind: slop
- severity: P3
- contract: "No raw color and no ad-hoc font size outside the tokens" (spec success criteria) and CS-5
- evidence: components/SponsorWall.astro:41 (`max-h-12 max-w-[200px]`), 50-61 (`max-h-24 max-w-[280px]`, `h-28 sm:w-[320px]`, `h-24 sm:w-[280px]`, `h-20 sm:w-[240px]`), HeroInner.astro:50 (`h-[230px] md:h-[280px]`), Nav.astro:47 (`underline-offset-[10px]`)
- observation: eight arbitrary pixel widths and heights define the sponsor tiers and the masthead band. they are the right numbers; they are just written where nobody can find them.
- proposal: tailwind.config.ts `extend.spacing: { 'logo-sm': '12.5rem', 'logo-md': '15rem', 'logo-lg': '17.5rem', 'band-photo': '14.375rem', 'band-photo-md': '17.5rem' }` (or a `sponsorTiers.js` sizing map next to the tier labels, which already exist there) and `underline-offset-8` for the nav. arbitrary values then read as decisions.
- workstream: foundations

### CS-41
- surface: home / live conditions / all
- kind: drift
- severity: P3
- contract: "Any color outside the tokens above." (banned) versus LiveConditions.astro:128-131 ("Deliberate non-token colors: this is data encoding")
- evidence: components/LiveConditions.astro:132-135 (four oklch wax-chip colors)
- observation: the wax chips are the only non-token colors on the site and the comment explains why. the contract does not.
- proposal: contract exception, one line: "wax chips use four fixed data colors (green, blue, purple, red at L 0.62) because the color is the recommendation; they are not palette." no code change. the color lens owns the values.
- workstream: foundations

### CS-42
- surface: trips / populated / desktop; home / wax-feed / desktop
- kind: slop
- severity: P3
- contract: proposed: "ledger row hover is a color change on the title only; no background wash."
- evidence: components/TripsTable.astro:38 (`hover:bg-ink/[0.03]` plus title to mint-deep), components/WaxRoomFeed.astro:44 (title to mint-deep only), pages/404.astro:63 (title to mint-deep only)
- observation: the trips row is the one row on the site with a background wash on hover (an arbitrary `ink/[0.03]`), and it also has negative margins (`md:-mx-3 md:px-3`) to make the wash bleed past the column. the other two clickable ledgers change only the title color. visual-redesign's table cure ("subtle hover row highlight") is the generic default; the site's own quieter answer is already in two of three places.
- proposal: Ledger (CS-1) rows: title `group-hover:text-mint-deep`, nothing else. drop the wash and the negative margins.
- workstream: motion-components

### CS-43
- surface: home / hero, wax-feed / all
- kind: slop
- severity: P3
- contract: "Body line length capped at 62ch on paper, 56ch on navy"
- evidence: components/CTAStrip.astro:62 (`max-w-xl` for the subhead on navy), components/HeroHome.astro:63 (`max-w-prose-narrow`), components/Footer.astro:30 (`max-w-xs`), pages/404.astro:42 (`max-w-lg` on a heading), 45 (`max-w-prose`)
- observation: measure caps are written as `max-w-xl`, `max-w-xs`, `max-w-lg` and `max-w-prose(-narrow)` for the same purpose. the two ch tokens exist and are used in two of five places.
- proposal: body measures use only `max-w-prose` (paper) and `max-w-prose-narrow` (navy); the footer blurb becomes `max-w-prose-narrow`, the CTA subhead `max-w-prose-narrow`, the 404 h2 drops its cap (`text-balance` does the job).
- workstream: foundations

## proposed contract changes

- add a "primitives" row set to the components table: Seam, Ledger, FactStack, Button, PhotoStrip, SectionHeader, ProseColumn, WaxEntryRow, each with its fixed values (CS-1, CS-2, CS-3, CS-7, CS-9, CS-16, CS-29, CS-34)
- add a "utilities" clause: `.label-caps` / `.label-caps-wide` are the only small-caps specs; `.hairline` / `.hairline-soft` are the only rules; `.link-inline` (paper) / `.link-inline-navy` are the only inline links; no `text-[Npx]`, no `tracking-[…]`, no `/N` opacity on rules outside these (CS-4, CS-5, CS-6, CS-8)
- replace the "Vertical rhythm" sentence with the three-step band scale (`band-sm`, `band`, `band-lg`) and the rule that a page uses at least two of the three (CS-30)
- add `max-w-inner` (1080) as the inner-page band width and name the two-widths-per-register rule (CS-31)
- add "on navy, display headings are paper; mint is reserved for the CTA strip heading, live data, fact labels and links" and remove "mint headings" from the SeasonsGrid row (CS-32)
- add "a seamed band never draws a second rule above its first row" and "a section that opens without a heading starts flush or with a rule-only seam" (CS-21, CS-22)
- replace the banned line "Stat boxes with big mint numbers" with the FactStack definition (navy value, small-caps label, one hairline, max three, no box) (CS-25)
- rewrite the component table rows for HeroInner, MissionPanel, SeasonsGrid, PhotoMosaic, CoachEntry, WaxRoomFeed, Footer, LiveConditions, MobileNavPanel to the shipped site; delete TripEntry; fix the venue list to the api's four (CS-37)
- replace the iconography clause: inline 24px stroke-2 svg paths (menu, close, chevron); no icon library; and drop the hero-arrow reservation from the banned list (CS-23)
- record two exceptions: the ♪ play affordance on the Birkie fever cell, and the four wax-chip data colors (CS-24, CS-41)
- add an empty-state clause: one ruled placeholder row in the ledger grammar with a sentence and one link (CS-35)
- add an og image clause: consented photo, navy band with the logo mark along the bottom, 1200x630 (CS-38)
- add "page titles are `<Page> · Twin Cities Ski Club`" (CS-36)
- add "global.css and tailwind.config.ts ship only what the site uses; no forms plugin; navy and ink referenced through theme(), never as literals; the nav logo fills are the one literal exception" (CS-12, CS-13)
- add "safe-inline-* (renamed gutter-*) owns the horizontal gutter; call sites do not add px-*" (CS-10)
- add a testing note: the brand primitives are guarded by a dist-grep build test; the CTAStrip section class literal in contentRefinements.test.mjs is updated with any change to it (CS-39)
