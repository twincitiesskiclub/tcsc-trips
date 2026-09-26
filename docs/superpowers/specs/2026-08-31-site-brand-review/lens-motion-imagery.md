# lens: motion + imagery

1. the home headline still runs across the selfie-taker's face at 1440 and 768. the frame is wider than the photo, so only a vertical crop exists and no `object-position` can clear her. the july fix could never have worked at those widths; the text block has to move, not the focal point.
2. the mosaic crops photos blind. the size pattern is an index cycle, so a portrait source (dry-tri-rider) lands in a 2:1 slot with the face cropped out, five-wide selfies (night-practice) lose their outer faces in square slots, and the home tile `loppet-skijor` carries third-party "city of lakes loppet" and "mtec" watermarks with no rights check on record.
3. the motion clause and the code disagree in both directions: the lightbox opens with a hard cut (contract says 200ms scale-in), the conditions strip has a first-fill entrance the contract never mentions and no refresh flicker it demands, the hero entrance is 250ms/8px on every load (contract: 200ms/4px once per session with blurhash), and every tailwind `transition-*` utility runs on tailwind's default curve rather than the ease-out the contract names.
4. biggest opportunity: one easing token and one hover vocabulary. define `--ease-out: cubic-bezier(0.16,1,0.3,1)` once in global.css as tailwind's default timing function, give the lightbox a css-only `@starting-style` entrance, put `cursor-pointer` on the five button surfaces that lack it, and make the four link families share one 150ms rule. that is the whole motion system; it would read like one hand did it.
5. overall: the motion layer is admirably restrained and mostly transform/opacity, but the contract describes a site that was never built (blurhash, per-session entrance, expanding conditions cells, refresh flicker), and the imagery pipeline trusts geometry over faces. fix the crops and rewrite the motion clause to match the good decisions the code already made.

## findings

### MO-1
- surface: home / hero / desktop, tablet
- kind: drift
- severity: P1
- contract: "Headline set in mint over a navy-gradient bottom-vignette for legibility"; july round: "no face sits under the bottom text block at ~390px, ~768px, ~1440px widths"
- evidence: site/src/components/HeroHome.astro:51, :60-61; screens/before/home-hero-desktop.png, home-hero-tablet.png, home-hero-mobile.png; site/src/assets/images/uploads/home-hero-trail.jpg
- observation: at 1440x900 the hero frame is 1440x666 (2.16:1) and the photo is 4:3, so the image is width-fit and only cropped vertically. the selfie-taker's face spans y 35-65% of the source, which is inside every possible vertical window, and it sits at x 10-35%, exactly under the bottom-left headline block. "Twin Cities Ski Club" runs across her eyes and nose. at 768 (`max-md` does not apply at exactly 768) the same thing happens with "Twin Cities" over her forehead. only mobile is clean, and only because `60% 15%` pushes her off the left edge entirely, which also halves the fourth skier.
- proposal: no `object-position` clears desktop; move the text block instead. at md+ right-align the headline, subline, and CTA (`md:items-end md:text-right md:ml-auto` on the inner flex column, headline `max-w-5xl` kept) so the block sits over the blue-jacket skier's torso and the snow, which are face-free at 1440 and 768. keep the current left placement below md. keep the scrim but mirror it: `bg-gradient-to-t` stays, add nothing. if rob prefers left text, the alternative is a different hero photo whose bottom-left third is snow; no crop of this photo works.
- workstream: sections

### MO-2
- surface: home / lightbox / all
- kind: drift
- severity: P2
- contract: "Lightbox open: 200ms scale-in with opacity. Lightbox navigation: hard-cut."
- evidence: site/src/components/Lightbox.astro:11-18 (no transition rules); site/src/components/PhotoMosaic.client.ts:78-86 (toggles `hidden`/`flex`, comment "no transitions"); screens/before/home-lightbox-desktop.png
- observation: the lightbox pops from display none to a full-screen ink panel with no entrance. navigation is correctly hard-cut. the client script is sacred, so the fix has to be css that reacts to the class toggle.
- proposal: css-only entrance on `[data-lightbox]`: `transition: opacity 200ms var(--ease-out), display 200ms allow-discrete; @starting-style { opacity: 0 }` and on `[data-lightbox-img]` `transition: transform 200ms var(--ease-out); @starting-style { transform: scale(0.97) }`. `hidden` still governs display, so close stays instant. the global reduced-motion rule collapses both. browsers without `@starting-style` keep today's hard cut.
- workstream: motion-components

### MO-3
- surface: home / hero / all
- kind: drift
- severity: P3
- contract: "the hero photo fades in over 400ms ease-out-quint with a synchronized blur-to-sharp via BlurHash. The headline appears at 200ms with a 4px upward translation. Single orchestrated entrance per session; cached after."
- evidence: site/src/components/HeroHome.astro:98-110; site/src/components/imageWidths.ts (no blurhash anywhere in site/)
- observation: the code runs the photo fade at 400ms (matches), the headline at 120ms delay, 250ms, 8px rise (contract: 200ms, 4px), on every load of `/` (contract: once per session), and there is no blurhash placeholder anywhere on the site. per-session gating needs sessionstorage js and blurhash needs a dependency; both are non-goals. the code's choices are fine; the contract is the thing that is wrong.
- proposal: keep the code. rewrite the clause: "hero photo fades in over 400ms `--ease-out`; the headline rises 8px over 250ms starting at 120ms. once per page load. no placeholder image; tiles and frames sit on `paper-card` until the photo paints." see contract changes.
- workstream: motion-components

### MO-4
- surface: home / conditions live, dryland, unavailable / all
- kind: drift
- severity: P3
- contract: "A subtle 200ms opacity-flicker when data updates (every 5 minutes via revalidation). No spinner, no skeleton card, no shimmer. Data simply replaces." and "Click a column → expands to show full conditions detail (wind, gusts, snow depth) inline."
- evidence: site/src/components/LiveConditions.astro:108-126 (first-fill entrance 250ms, 4px); site/src/components/LiveConditions.client.ts:289-301 (refreshes are silent); state-matrix.md "The strip never got that interaction"
- observation: the strip has a first-fill entrance (250ms opacity and 4px rise, keyed on `data-filled`) that the contract never mentions, and no flicker on the five-minute refresh that the contract demands. the expand-on-click cell was never built and the only interactive cell is the birkie fever button. the code's silent refresh is the better behaviour: a flicker every five minutes on the signature device is noise, and "data simply replaces" already says so.
- proposal: keep the code. contract: "first fill: cells rise 4px and fade in over 250ms `--ease-out` after the first fetch, backstopped at 1200ms; refreshes replace text silently." delete the expand-on-click sentence and the wind/gusts/snow-depth detail line. see contract changes.
- workstream: motion-components

### MO-5
- surface: shared / every `transition-*` utility / all
- kind: drift
- severity: P3
- contract: "Hover overlay 150ms ease-out." (mosaic) and the skill's three-curve maximum: "Grep the CSS - if you find a 4th curve, the palette leaked."
- evidence: builds/open/_astro/Footer.*.css: `--default-transition-timing-function:cubic-bezier(.4, 0, .2, 1)` plus four uses of `cubic-bezier(.16,1,.3,1)`; site/src/components/PhotoMosaic.astro:180 (`transition-opacity duration-150`, no ease class); Nav.astro:46, CtaForState.astro:29-30, TripsTable.astro:38,42, WaxRoomFeed.astro:44, LiveConditions.astro:80
- observation: the hand-written css (hero, conditions first-fill, mobile panel) uses the skill's `--ease-out` curve. every tailwind `transition-colors` and `transition-opacity` utility, including the mosaic hover scrim the contract calls "ease-out", runs on tailwind's material-style default `cubic-bezier(.4,0,.2,1)`. two easing families on one page, and the one the contract names is the minority.
- proposal: one token. in global.css `@theme { --ease-out: cubic-bezier(0.16, 1, 0.3, 1); --default-transition-timing-function: var(--ease-out); --default-transition-duration: 150ms; }` and replace the four literal `cubic-bezier(0.16, 1, 0.3, 1)` strings in HeroHome, LiveConditions, and MobileNavPanel with `var(--ease-out)`. no class changes needed; every utility inherits. the site then has exactly one curve.
- workstream: motion-components

### MO-6
- surface: home / hero / all (prefers-reduced-motion)
- kind: drift
- severity: P3
- contract: "`prefers-reduced-motion`: all entrance animations disabled. Hero photo loads without fade."
- evidence: site/src/styles/global.css:98-104; site/src/components/HeroHome.astro:109 (`animation: hero-headline-in 250ms ... 120ms both`)
- observation: the global rule collapses `animation-duration` and `transition-duration` but not `animation-delay`. with reduced motion the headline sits at opacity 0 (fill-mode `both`, backwards phase) for 120ms and then pops. everything else escapes cleanly: no `transition-all`, no layout-property animation, no `will-change`, no scroll-driven rules, mobile panel and conditions entrance both collapse, lightbox has no motion to collapse. this is the only leak.
- proposal: add `animation-delay: 0s !important;` to the reduced-motion block. optionally narrow the block from `*` to the elements that animate (`.hero-headline`, `section picture`, `[data-location]`, `[data-birkie]`, `[data-mobile-panel]`, `[data-lightbox]`) so 150ms hover colour changes survive, which the skill allows ("opacity-only fades at reduced duration are acceptable").
- workstream: motion-components

### MO-7
- surface: shared / link and button hover / all
- kind: slop
- severity: P3
- contract: skill "Intensity consistency: ... Hover lifts all use the SAME offset"; "Every link has a hover underline animation or color shift"; spec de-slop: "duplicated class strings"
- evidence: transition 150ms: Nav.astro:46, CtaForState.astro:29, TripsTable.astro:38, WaxRoomFeed.astro:44, LiveConditions.astro:80. instant (no transition): Footer.astro:36,39,43,44, MobileNavPanel.astro:31, PhotoMosaic.astro:134, WaxRoomFeed.astro:32, LiveConditions.client.ts:199. the underline-link string `underline underline-offset-4 decoration-ink/30 hover:decoration-mint-deep hover:text-mint-deep transition-colors` copied verbatim in index.astro:120, community.astro:116, racing.astro:62, dry-tri.astro:81 and :87, extra-training-fun.astro:89, and a near-copy in 404.astro:63
- observation: four hover families exist. nav and cta links ease over 150ms, footer and mobile-panel links snap, the paper-page underline link is a seven-utility string pasted at six call sites, and the "See what members do" and "All entries" section links have no transition at all. none of it is wrong on its own; together it reads as several authors.
- proposal: one rule, one class. in global.css `@layer components { .link-quiet { @apply underline underline-offset-4 decoration-ink/30 transition-colors hover:text-mint-deep hover:decoration-mint-deep; } .link-nav { @apply transition-colors hover:text-mint; } }` and use them at every site above (footer, mobile panel, section "more" links, conditions source link via `a.className` string is sacred, so leave that one). with MO-5 landed, every hover is 150ms `--ease-out`. press feedback stays colour-only (`active:bg-mint/90`), which fits near-zero motion; do not add scale.
- workstream: motion-components

### MO-8
- surface: home, community / mosaic tiles, birkie fever button, lightbox controls, hamburger / desktop
- kind: drift
- severity: P2
- contract: "All interactive elements ≥44×44px on mobile" and the skill's "Every button has hover ... + focus-visible states"; a visitor must be able to tell a photo opens
- evidence: builds/open/_astro/Footer.*.css contains no `cursor:pointer` rule; tailwind 4.3.2 preflight no longer sets it on `button`; `grep -rn cursor-pointer site/src` returns nothing; PhotoMosaic.astro:150, LiveConditions.astro:70, Lightbox.astro:19,31,32, Nav.astro:58
- observation: every `<button>` on the site shows the arrow cursor. hovering a mosaic photo gives the caption scrim but no pointer, so nothing says "this opens". the birkie fever cell's only hover signal is a 10px `♪` going from `mint/50` to `mint`, which the before-capture shows as imperceptible (home-birkie-hover-desktop.png is pixel-identical to home-hero-desktop.png at a glance).
- proposal: add `cursor-pointer` to the mosaic tile button, the fever button, the hamburger, and the three lightbox buttons (or one base rule `button:not(:disabled) { cursor: pointer }` in global.css). for the fever cell, hover the whole cell: `group-hover:text-paper/85` on the "Birkie fever" label alongside the note, still 150ms. no lift, no scale.
- workstream: motion-components

### MO-9
- surface: home / lightbox / all
- kind: slop
- severity: P3
- contract: "Iconography: Lucide ... lightbox close"; banned: "→ on every link. Reserved for the home hero CTA."
- evidence: site/src/components/Lightbox.astro:31-32 (`←` and `→` as button text); Lightbox.astro:20-22 (close is an inline svg)
- observation: the close button is an inline svg in the lucide idiom, but previous and next are typed arrow glyphs in a bordered box. the arrow ban targets links, and these are buttons, but the mixed idiom inside one dialog reads as unfinished. the buttons also show the arrow cursor (MO-8).
- proposal: replace the glyphs with inline `chevron-left` and `chevron-right` paths (`M15 18l-6-6 6-6` / `M9 18l6-6-6-6`) at 24px, same `min-h-11 min-w-11 border border-paper/30 rounded` frame, keep the aria labels. no dependency.
- workstream: motion-components

### MO-10
- surface: home / mobile-nav / mobile
- kind: elevation
- severity: P3
- contract: proposed: "mobile nav panel: opens with a 200ms opacity fade and an 8px rise on the link list; closes instantly."
- evidence: site/src/components/MobileNavPanel.astro:43-70, :88-108; screens/before/home-mobile-nav-mobile.png
- observation: the panel has a deliberate, well-built asymmetric entrance (fade plus rise, instant close) that the motion clause never lists. the contract says "the single hero entrance is the only animated arrival in the site", which is now false three times over (panel, conditions first-fill, and the proposed lightbox). the panel itself is good and should stay.
- proposal: codify it. the motion clause lists every arrival: hero, conditions first-fill, mobile panel, lightbox. nothing else moves. see contract changes.
- workstream: motion-components

### MO-11
- surface: home / mosaic (composed layout) / desktop, mobile
- kind: drift
- severity: P1
- contract: "No stock photography."; "real, consented club photography only"; june round: "the standing exclusion is professional race-gallery photography (rights, not consent)"
- evidence: site/src/content/photos/loppet-skijor.yaml (`show_on_home: true`, order 60); site/src/assets/images/photos/loppet-skijor.jpg (watermarks bottom-left "CITY OF LAKES loppet WINTER FESTIVAL" and bottom-right "mtec RESULTS"); screens/before/home-open-desktop.png (side tile, both logos visible); migration/CONSENT.md:37 (member-posted-club-slack, no rights line, unlike skijor-race at :92)
- observation: the second photo a visitor sees on the home page is a race-gallery frame with two third-party logos burned in. it is the only image on the site that looks bought rather than shot, and the mtec watermark is the timing company's photo-sales mark. on the community wall it appears again in a 1x1 slot with the mtec mark half visible.
- proposal: flip `show_on_home` off for loppet-skijor and on for vasaloppet-duo (order 90, 4:3, two skiers centred, survives every mosaic slot). keep the home count at exactly nine. hold loppet-skijor out of the community wall too until rob confirms rights as he did for skijor-race; if confirmed, crop the watermarks out of the source (`fit: cover` to 3:2 from the top-left, or a 60px trim of the bottom edge) before it returns. photo yaml flags are content, so this is the copy workstream's file; the mosaic invariant (nine on home) is the check.
- workstream: copy

### MO-12
- surface: community / mosaic (dense layout) / desktop
- kind: drift
- severity: P2
- contract: success criterion "Every `object-cover` image has a deliberate `object-position` at both viewports; no cropped faces."
- evidence: site/src/components/PhotoMosaic.astro:63-72 (index-cycled `sizeClasses`), :168-177 (`object-cover`, no `object-position`); screens/before/community-default-desktop.png (dry-tri-rider in the 2:1 slot shows handlebars and torso, no face; night-practice in the 2x2 square loses the leftmost face and clips the rightmost; rollerski-treats in a 2:1 slot clips the top of the curly-haired man's head; half-dome-tee in a square loses half dome; techno-corner in a square is 60% sky)
- observation: the size pattern is assigned by `i % 8` with no knowledge of the source. dry-tri-rider (2:3 portrait, order 190, index 17) lands on `md:col-span-2 md:aspect-auto`, a 2:1 window that shows 33% of the image's height, centred, so the rider's face at y 22-30% is gone. five-wide selfies (night-practice, 4:3) cannot survive a square window that keeps 75% of the width. these are the exact "cropped heads" the july round closed on the community page, moved down into the wall.
- proposal: two rules in PhotoMosaic.astro, no schema change. (1) orientation-aware spans: a portrait source (`image.height > image.width`) never receives `col-span-2`; the pattern advances to the next landscape source for wide slots, and `grid-flow-row-dense` keeps the wall flush. (2) face-aware square crops: for tiles that are square at every width (dense 1x1, composed remainder), pass `width`, `height=width`, `fit="cover"`, `position="attention"` to `<Image>` exactly as CoachEntry.astro:59-73 and dry-tri.astro:40-52 already do, so sharp chases faces at build time. for the remaining wide slots, a portrait or square source gets `object-[center_25%]` (heads live in the top third of every portrait in this pool). acceptance: read every tile at 390 and 1440; no face touches an edge.
- workstream: sections

### MO-13
- surface: home / mosaic (composed layout) / mobile
- kind: drift
- severity: P2
- contract: "no cropped faces"; "Hover overlay desktop; lightbox tap mobile"
- evidence: site/src/components/PhotoMosaic.astro:154-158 (`composed && i < 3 ? 'aspect-auto max-md:aspect-square'`); screens/before/home-open-mobile.png (night-practice tile: leftmost face cut at the edge, rightmost person clipped); site/src/assets/images/photos/night-practice.jpg
- observation: on mobile the two composed side tiles are forced square. night-practice is a five-wide 4:3 selfie with faces from x 5% to 85%; a square keeps 75% of the width, so someone is always cut. the desktop `aspect-auto` version of the same tile is fine.
- proposal: `max-md:aspect-[4/3]` instead of `max-md:aspect-square` for the two composed side tiles (every source in the home nine is 4:3 or 3:2, so no crop at all), or apply the MO-12 attention crop to them. with MO-11 the side tiles become night-practice and techno-corner; techno-corner is 3:4 portrait and needs the `object-[center_25%]` rule from MO-12 in any landscape slot. `sizes` for these tiles stays `50vw` below md.
- workstream: sections

### MO-14
- surface: racing / race strip / mobile
- kind: drift
- severity: P2
- contract: "Soft-tinted gray cards on paper" banned; "No card-grid reflex"
- evidence: site/src/pages/racing.astro:73-84 (`grid grid-cols-2 md:grid-cols-5 gap-px bg-ink/15`, five photos); screens/before/racing-default-mobile.png (bottom-right cell is a flat `ink/15` gray slab the full size of a photo)
- observation: five portrait photos in two columns leave an orphan sixth cell, and because the hairline colour is painted on the wrapper, that empty cell renders as a gray tile. a normal visitor reads it as a broken image. on desktop the same strip renders at 144px per photo, postage stamps under a 720px prose column.
- proposal: mobile: reuse the SeasonsGrid trick, `max-md:[&>:last-child:nth-child(odd)]:col-span-2` with `max-md:[&>:last-child:nth-child(odd)]:aspect-[3/2]` on the fifth image, or hold the strip to four photos below md (`max-md:[&>:nth-child(5)]:hidden`). desktop: widen the strip to the page column (`max-w-5xl`, `md:grid-cols-5`) so each tile is around 190px, or run 3 + 2 rows at `aspect-[3/4]`. skijor-race keeps its `82% center`; the other four need `object-[center_30%]` (heads sit in the top third of every portrait here) rather than the current centre default.
- workstream: sections

### MO-15
- surface: about / masthead band / desktop
- kind: elevation
- severity: P3
- contract: "Optional `photo` ... full-bleed photo band directly under the masthead grid, roughly 230-280px tall"
- evidence: site/src/pages/about.astro:36 (`center 40%`); site/src/components/HeroInner.astro:50 (`h-[230px] md:h-[280px]`); screens/before/about-open-desktop.png vs about-open-mobile.png; site/src/assets/images/photos/team-banner.jpg
- observation: at 1440 the band shows y 26-61% of the source: every head, and none of the "TCSC" banner the members are holding, which is the thing that makes the photo the club's. mobile shows the whole frame and reads far better.
- proposal: `photoPosition="center 58%"` (window 38-73%: heads plus the banner, back-row heads keep 4% margin) and for this page `md:h-[320px]`. HeroInner could take an optional `photoHeight` prop so about can ask for the taller band without changing the other mastheads. verify at 1440 that no back-row head touches the top edge.
- workstream: sections

### MO-16
- surface: 404 / masthead band / desktop
- kind: elevation
- severity: P3
- contract: "No decorative SVG / abstract shapes / gradient orbs / vector backgrounds"; imagery skill: one focal point per section
- evidence: site/src/pages/404.astro:36 (`center 72%`); screens/before/404-default-desktop.png vs 404-default-mobile.png; site/src/assets/images/photos/oo-corridor.jpg
- observation: at 1440 the 280px band shows y 62-77% of a portrait photo: flat snow with faint corduroy and no trees. it reads as a texture strip, the kind of abstract background the contract bans, and a visitor cannot tell it is a trail. mobile shows the corridor and the snow-loaded trees and is the best version of this photo on the site.
- proposal: `photoPosition="center 60%"`, which at desktop shows y 51-66% (tree line meeting the trail) and at mobile y 34-78% (still corridor and trees). if that still reads flat at 1440, use `md:h-[360px]` on this page via the same optional height prop as MO-15.
- workstream: sections

### MO-17
- surface: community / masthead band / desktop
- kind: elevation
- severity: P3
- contract: "no cropped faces"
- evidence: site/src/pages/community.astro:66 (`center 52%`); screens/before/community-default-desktop.png; site/src/assets/images/photos/canoe-social.jpg
- observation: the crop works, but the back-row heads (white cap at left, white shirt at right) sit within a few pixels of the top edge at 1440. it is the tightest masthead on the site.
- proposal: `center 46%` (window 24-59%: 3% of headroom above the back row, the front bald man still fully in frame at the bottom). mobile is unaffected (the window there is 47% of the height).
- workstream: sections

### MO-18
- surface: coaches / KJ entry / all
- kind: elevation
- severity: P2
- contract: "real, consented club photography only" (met); imagery skill: "No illegible ... everything is readable at the generated resolution"
- evidence: site/src/assets/images/coaches/coach-kj.jpg (2400x2400 but visibly a low-resolution upscale: blocky edges around the cap and jaw, smeared foliage); site/src/components/CoachEntry.astro:7-11 (comment already notes "KJ's is visibly soft at full size"); screens/before/coaches-default-desktop.png (first entry, above the fold, the page's LCP image)
- observation: the head coach's portrait is the first photo on the coaches page and the softest image on the site. at 460px css it shows compression blocks and a halo around the head. the other three coach photos are crisp. the contract forbids new photos in this round, so this is a rob decision, not a codex fix.
- proposal: flag for rob: a replacement photo of KJ from the consented pool or a new one. interim, no css trick fixes upscaling; do not add blur or grain. if no replacement exists by gate 2, reorder so greg (order 2, crisp) leads the page and KJ sits second; the `order` field is content.
- workstream: copy

### MO-19
- surface: OG image / all pages / all
- kind: elevation
- severity: P2
- contract: proposed: "one OG image per route family: the home share card is a 1200x630 crop of the current hero photo; inner pages with a masthead photo derive their card from it; the wax room derives per entry (already does)."
- evidence: site/public/og/og-default.jpg (1200x630, sunset skate practice, about fourteen skiers, faces under 40px at card size, no wordmark); site/src/layouts/BaseLayout.astro:24, :61-66 (single default, no `og:image:width`, `og:image:height`, `og:image:alt`, `twitter:image`); site/src/pages/wax-room/[slug].astro:25-27 (per-entry og via getImage, the pattern to reuse); migration/port-manifest.csv:2-3 (og-default and the unused home-hero.jpg are the same wix-era source)
- observation: every page except wax entries shares one card, and that card is a photo the site never shows anywhere else: a pink sunset with tiny figures. at slack or imessage preview size (about 300px wide) it is a sunset, not a ski club. it does not match the fold a visitor lands on (the snow-loaded trail selfie), and about, community, racing, and dry-tri each have a masthead photo that would make a truer card. one default is enough only if it is the site's own image.
- proposal: (1) regenerate `og-default.jpg` as a 1200x630 crop of `home-hero-trail.jpg` centred on the three standing skiers (x 40-100%, y 15-80% of the source), no text overlay, so the share card is the fold. (2) in InnerPageLayout, when `photo` is passed and `ogImage` is not, derive `ogImage` with `getImage({ src: photo, width: 1200, height: 630, fit: 'cover', position: 'attention', format: 'jpeg' })`, the wax-entry pattern; about, community, racing, and 404 get their own cards with zero new assets. (3) in BaseLayout add `og:image:width` 1200, `og:image:height` 630, `og:image:alt` (pass the masthead alt through), and `twitter:image`. the og photo's consent is already recorded (same source as home-hero.jpg).
- workstream: sections

### MO-20
- surface: shared / image assets / n/a
- kind: slop
- severity: P3
- contract: spec de-slop: "dead CSS" and its image equivalent
- evidence: `grep -rl` over site/src finds no reference to site/src/assets/images/uploads/home-hero.jpg (784KB), site/src/assets/images/photos/recess-ski.jpg (790KB, has a CONSENT.md row at :33 and a manifest row but no photos yaml, so it is in no collection), and site/src/assets/images/trips/sisu-ski-fest-hero.jpg (used only by the brand-review fixture)
- observation: two consented photos sit in the repo doing nothing, one of them the superseded hero. astro only processes referenced images, so there is no build cost, but they are invisible to keystatic and to anyone auditing what the site can show.
- proposal: delete `uploads/home-hero.jpg` (its og twin is the canonical copy). for `recess-ski.jpg`: it is a no-people trail shot (skis and a glove), the kind the july round cut from the home mosaic; delete it or add a yaml with `show_on_home: false` if rob wants it on the community wall. leave the sisu hero where it is; the fixture path depends on it and production trips will need a hero in that folder.
- workstream: copy

### MO-21
- surface: trips / populated / all
- kind: drift
- severity: P3
- contract: components table: "`<TripEntry>` Trip marketing ... Editorial layout: photo, dates, location, lede paragraph"; imagery: "Astro image pipeline generates responsive `srcset`"
- evidence: site/src/components/TripsTable.astro (no image anywhere); site/src/content.config.ts:152-153 (`hero_photo` field); scripts/brand-review/fixtures/content/trips/sisu-ski-fest.mdoc (`hero_photo` set); screens/before/trips-populated-desktop.png (ledger row, no photo)
- observation: the trips collection carries a hero photo that nothing renders. `TripEntry` does not exist; there are no trip detail pages (TripsTable.astro:5-6 says so). the contract describes a component and an image the site does not have.
- proposal: contract change: remove `<TripEntry>` from the components table and state that `/trips` is a ledger with no photography; the `hero_photo` field stays in the schema (schema is a non-goal) but is documented as unused until detail pages exist. no code change.
- workstream: sections

### MO-22
- surface: home / mosaic (composed lead tile) / desktop
- kind: elevation
- severity: P3
- contract: "Astro image pipeline generates responsive `srcset`"; imageWidths.ts: "never pre-filter ... Astro ... appends the intrinsic width itself"
- evidence: site/src/components/imageWidths.ts:12 (MOSAIC max 1600, comment assumes spans reach ~700px css); site/src/components/PhotoMosaic.astro:171 (`width={Math.min(1600, ...)}`); builds/open/index.html: lead tile `srcset` is exactly 400, 800, 1200, 1600w with `sizes="(min-width: 768px) 66vw, 100vw"`
- observation: the composed lead tile is 66vw, about 950px css at 1440, so a 2x display asks for 1900px and gets 1600, a 19% upscale on the largest photo on the home page. the intrinsic 2560 candidate is not appended because the explicit `width` clamps the request; the imageWidths comment describes behaviour the component then defeats.
- proposal: add 1920 to `MOSAIC` (`[400, 800, 1200, 1600, 1920]`) and raise the lead tile's `width` clamp to 1920, or pass `FULL_BLEED` for the composed lead only. correct the comment in imageWidths.ts to say the intrinsic candidate is appended only when `width` is not passed.
- workstream: motion-components

### MO-23
- surface: shared / every non-home image / all
- kind: drift
- severity: P3
- contract: "AVIF + WebP fallbacks."
- evidence: site/src/components/HeroHome.astro:45-56 (`<Picture formats={['avif','webp']}>`); every other image site uses `<Image>` (HeroInner.astro:45, PhotoMosaic.astro:168, CoachEntry.astro:59, WaxEntry.astro:85, about/community/racing/sponsors/dry-tri/extra-training-fun pages), which emits webp only
- observation: only the home hero ships avif. the masthead bands (2560-wide renditions for a 280px band, `sizes="100vw"`) and the whole mosaic are webp only. not visible to a visitor, but the contract says otherwise and the mastheads are the heaviest images after the hero.
- proposal: either switch the three masthead bands and the mosaic lead tile to `<Picture formats={['avif','webp']}>` (they are the only images large enough to matter), or change the contract to "webp; avif on the home hero only" and stop promising it. the second is honest and cheaper; recommend it.
- workstream: motion-components

### MO-24
- surface: shared / photo consent / n/a
- kind: elevation
- severity: P3
- contract: "All photos schema-managed in Keystatic with required `alt`, `caption`, `event_tag`, `photo_consent_recorded`."
- evidence: all 22 files in site/src/content/photos/*.yaml carry `photo_consent_recorded: true` (verified); 21 photos are imported directly by pages (about.astro:18-19, community.astro:17-24, racing.astro:11-16, sponsors.astro:12-13, dry-tri via dry_tri.mdoc, extra-training-fun via extra_training.mdoc, 404.astro:7), bypassing the collection and its consent gate; every one of them has a CONSENT.md row (checked :60-95)
- observation: the flag is true everywhere it exists, and the direct imports are all accounted for in CONSENT.md, so nothing is wrong today. but the contract's sentence describes a gate that half the site's photos never pass through, and PhotoMosaic.astro:39 is the only place the flag is enforced. the next direct import has no guard.
- proposal: contract change: "every photo the site renders has a row in `migration/CONSENT.md`; collection photos additionally carry `photo_consent_recorded: true`, which PhotoMosaic enforces. direct page imports are allowed only for placements the mosaic cannot express (mastheads, anchors, strips) and must cite the CONSENT row in a comment." no code change beyond the comments.
- workstream: copy

### MO-25
- surface: home, community / mosaic hover / desktop
- kind: drift
- severity: P3
- contract: "Photo mosaic interactions. Hover overlay 150ms ease-out."
- evidence: site/src/components/PhotoMosaic.astro:180 (`transition-opacity duration-150`, tailwind default ease); screens/before/home-mosaic-hover-desktop.png (bottom scrim with caption, photo undimmed, correct per the july round)
- observation: the treatment is right (bottom scrim, caption, photo never dimmed, `group-focus-visible` for keyboard). only the curve is off, and only because of MO-5. no separate fix once MO-5 lands; recorded so the ledger can mark the clause verified after.
- proposal: none beyond MO-5. after MO-5, re-read the hover capture and close.
- workstream: motion-components

## proposed contract changes

- motion clause, hero: replace "fades in over 400ms ease-out-quint with a synchronized blur-to-sharp via BlurHash. The headline appears at 200ms with a 4px upward translation. Single orchestrated entrance per session; cached after." with "photo fades in over 400ms `--ease-out`; the headline rises 8px over 250ms starting at 120ms; once per page load; no placeholder image." (MO-3)
- motion clause, conditions: replace the 200ms refresh flicker with "first fill: cells rise 4px and fade over 250ms `--ease-out`; refreshes replace text silently." (MO-4)
- signature device section: delete "Click a column → expands to show full conditions detail (wind, gusts, snow depth) inline. No modal." and the wind/gusts/snow-depth promise; the only interactive cell is the birkie fever button. (MO-4)
- motion clause, arrivals: replace "The single hero entrance is the only animated arrival in the site" with an explicit list: hero entrance, conditions first fill, mobile nav panel open (200ms fade, 8px rise, instant close), lightbox open (200ms opacity and scale from 0.97). nothing else moves. (MO-2, MO-10)
- motion clause, properties: "Transform and opacity only" becomes "transform, opacity, and colour only; one easing curve site-wide, `--ease-out: cubic-bezier(0.16, 1, 0.3, 1)`, set as tailwind's default timing function; hover and press feedback is a 150ms colour change, never a lift or scale." (MO-5, MO-7)
- reduced motion: add "animation delays are zeroed as well as durations." (MO-6)
- hero component row: replace the focal-point sentence with "the text block sits in a face-free zone at 390, 768, and 1440; the zone may change side by breakpoint; when no crop clears all three, move the block, not the photo." (MO-1)
- imagery, blurhash: delete "BlurHash placeholders" from both the imagery and mosaic rows; tiles sit on `paper-card` until they paint. (MO-3)
- imagery, formats: "AVIF + WebP fallbacks" becomes "webp everywhere; avif on the home hero only" unless synthesis prefers MO-23's first option. (MO-23)
- imagery, crops: new clause "every `object-cover` image has a deliberate focal point at both viewports: `object-position` for hand-placed photos, sharp `position: attention` for square and fixed-ratio renditions; the mosaic never gives a portrait source a wide slot; no face touches an edge." (MO-12, MO-13, MO-14)
- imagery, consent: replace the keystatic-only sentence with the CONSENT.md rule in MO-24. (MO-24)
- imagery, rights: add "no race-gallery or watermarked frames; a photo with a third-party mark needs a rights line in CONSENT.md before it renders." (MO-11)
- new OG clause: "one share card per route family: home uses a 1200x630 crop of the current hero photo; inner pages with a masthead photo derive their card from it; wax entries derive from the entry photo; `og:image:width`, `og:image:height`, `og:image:alt`, and `twitter:image` are always set." (MO-19)
- components table: remove `<TripEntry>`; `/trips` is a ledger with no photography until detail pages exist. (MO-21)
- iconography: add "lightbox previous and next are lucide chevrons, inline svg; no arrow glyphs as controls." (MO-9)
- accessibility: add "every button shows the pointer cursor; tailwind 4 preflight does not set it." (MO-8)
- masthead band: "roughly 230-280px tall" becomes "230px on mobile, 280px default on desktop, up to 360px where the photo's subject needs it (about's banner, the 404 corridor)". (MO-15, MO-16)
