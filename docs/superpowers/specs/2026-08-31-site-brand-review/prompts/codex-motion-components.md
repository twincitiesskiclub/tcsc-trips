you are implementing one workstream of a brand consistency, elevation, and de-slop pass on twincitiesskiclub.org, the Twin Cities Ski Club marketing site: Astro 7 static site + Tailwind 4 under site/ in this repo. you are working in a git worktree on branch brand/motion-components, branched from site/brand-review. commit on this branch; never merge, never push, never touch other branches, never touch main. do not stop or start docker containers.

## your workstream: motion-components
timing, easing, reduced-motion, and the css-only micro-interactions the ledger approved; component consolidation (replace one-off markup with the existing component and, where a row asks, give the component the prop it needs); class dedup into props or global.css utilities; dead css and unused props removed. you own transitions and keyframes anywhere in site/src, and the internals of components when a row is about reuse.

## the contract (read in full, first)
DESIGN.md at the repo root is the v2 contract. its "Theme" section names the two scenes the site reads for. docs/superpowers/specs/2026-07-18-marketing-copy-refresh-design.md holds the voice rules. every change you make must move the site toward these.

## your ledger rows
these are the only changes you may make. each row cites the contract clause it implements.

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

## your method
follow /workspace/tcsc-trips/.agents/skills/awwwards-motion/SKILL.md (css `linear()` easings, timing sheets, reduced-motion; ignore every Framer Motion, GSAP, and Lenis instruction) and /workspace/tcsc-trips/.agents/skills/visual-redesign/SKILL.md (sacred/slop classification).
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
  PORT=4403 node screenshot.mjs after-motion-components <stateIds you touched>
state ids are in scripts/brand-review/states.mjs; the matrix is docs/superpowers/specs/2026-08-31-site-brand-review/state-matrix.md. your port is 4403; other workstreams use other ports, so never use 4400 to 4405 for anything else. the before screenshots are on this machine at /workspace/tcsc-trips/docs/superpowers/specs/2026-08-31-site-brand-review/screens/before/ (the main checkout; screens are not committed). compare each after image against the before image with the same filename. look at them. if a change reads louder, busier, or more generic than before, it fails the gate: revert and try a quieter version. leave no serve-dist.mjs process running when done (`pkill -f "serve-dist.mjs .* --port 4403"`).

## report
write docs/superpowers/specs/2026-08-31-site-brand-review/motion-components-report.md:
- `# motion-components report`
- `## rows`: one line per ledger id: `L-nnn: fixed (<file:line>, <commit sha>)` or `L-nnn: skipped (<reason>)`.
- `## screens`: list of after screenshots you produced (they live in screens/after-motion-components/ in your worktree; screens are gitignored, so do not try to commit them).
- `## proposed`: anything you noticed that has no ledger id.
- `## test/build`: paste the last line of each of the five commands.
commit the report on your branch as the last commit.

work through the rows in ledger order (P1 first). commit small and often: one commit per row or per tightly related group, message `brand(motion-components): <what> (L-nnn)`.
