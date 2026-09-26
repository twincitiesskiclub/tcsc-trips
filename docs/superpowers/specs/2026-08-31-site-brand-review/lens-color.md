# lens: color

- biggest problem 1: secondary body copy on paper is set with opacity instead of the slate token. `text-ink/80` measures 4.09:1 and `text-ink/75` measures 3.43:1 on paper, both under wcag aa for body text, on six inner pages (CO-1).
- biggest problem 2: keyboard focus on every photo mosaic tile is invisible. the tile carries `bg-paper-card`, which flips the inherited focus ring to navy, and the ring is drawn on the navy grid gap around it (CO-2).
- biggest problem 3: the home page is not drenched. it reads navy / paper / navy / navy / paper / paper / navy, and the contract's own contrast table and hex references are wrong, so the site is being checked against numbers that do not exist (CO-4, CO-10).
- biggest opportunity: coral carries meaning on this site (the live dot, the open strip) but only the home page ever shows it. the compact conditions strip on every inner page has no live indicator at all. one coral dot there gives every route its third identity color for free, and the "unavailable" state stops wearing the "live" color (CO-5, CO-6).
- overall read: the palette is disciplined and the tokens are good. what has drifted is the grammar around them: opacity modifiers standing in for tokens, two link recipes on paper, three button recipes, three hairline levels on navy, and one register rule on home that the page no longer follows. all fixable without touching a token.

method note: ratios below are computed from the oklch values in `site/tailwind.config.ts` (oklab to linear srgb, wcag relative luminance), with alpha modifiers composited over the named surface. the calculator reproduces the contract's own mint-deep figures (4.95 on paper, 4.74 on paper-card) exactly, so the rest of its numbers can be trusted. resolved token hex: navy `#10213E`, navy-deep `#051127`, mint `#9EF9BE`, mint-deep `#007E46`, coral `#FF7C8A`, paper `#FBFAF8`, paper-card `#F6F5F2`, ink `#071123`, slate `#5D646F`.

## findings

### CO-1
- surface: community, racing, dry-tri, extra-training-fun, sponsors / default / all
- kind: drift
- severity: P1
- contract: "Contrast verified for the actual pairings used" and "`slate` ... Secondary body on paper. Captions, dates, meta."
- evidence: site/src/pages/community.astro:122, site/src/pages/racing.astro:69, site/src/pages/dry-tri.astro:65, site/src/pages/extra-training-fun.astro:81, site/src/pages/extra-training-fun.astro:85, site/src/pages/sponsors.astro:81, site/src/pages/sponsors.astro:92, site/src/pages/sponsors.astro:100; community-default-mobile.png, sponsors-default-desktop.png
- observation: secondary body text on paper is set as `text-ink/80` (4.09:1) and `text-ink/75` (3.43:1). both fail aa for normal text. `sponsors.astro:81` is `text-xl` (20px regular), which is still not "large text" under wcag, so it fails too. the contract already has a token for this role (`slate`, 5.74:1) and the july round fixed the same class of bug on navy (`text-paper/60` to `/75`); the paper side was never swept.
- proposal: replace every `text-ink/80` and `text-ink/75` with `text-slate`. where the copy is primary (the sponsors recognition body at `text-xl`), use `text-ink`. add a foundations lint: no opacity modifier on a text color on paper below `/90`, because ink drops under 4.5:1 at `/80`. `text-ink/90` (6.67:1, wax lede and wax index) passes but should also become `text-ink` or `text-slate` so the site has one way to say "secondary".
- workstream: foundations

### CO-2
- surface: home, community / default, lightbox / all
- kind: drift
- severity: P1
- contract: "Focus rings: 2px mint on navy, 2px navy on paper. Always visible on keyboard navigation."
- evidence: site/src/components/PhotoMosaic.astro:153 (`bg-paper-card` on the tile `<button>`), site/src/styles/global.css:78-84 (`.bg-paper-card { --focus-ring-color: navy }`), home-open-desktop.png (mosaic on navy)
- observation: every mosaic tile button carries `bg-paper-card` as a lazy-load placeholder color. the global focus map reads that class and sets the ring to navy. the ring is drawn 2px outside the tile, over the 1px navy gap and the navy section padding, so a keyboard user tabbing through 9 (home) or 22 (community) tiles sees no focus at all on the section's edges and a navy line over neighboring photos elsewhere. navy on navy is 1:1 against the 3:1 non-text minimum.
- proposal: move the placeholder color off the button (put `bg-paper-card` on an inner wrapper or drop it; the photos are lazy but the grid gap already shows navy) and give the tile an inset mint ring: `focus-visible:outline-offset-[-3px]` with `[--focus-ring-color:theme(colors.mint)]` on `[data-photo-mosaic]`, the same override lightbox.astro:13 already uses. an inset ring works over any photo. also add `[data-photo-mosaic]` to the global focus map in global.css so the section, not the tile, decides the ring color.
- workstream: foundations

### CO-3
- surface: all / all / mobile
- kind: drift
- severity: P2
- contract: "Any color outside the tokens above" (banned) and "`navy` ... `#202A44`" (the reference hex column)
- evidence: site/src/layouts/BaseLayout.astro:32 (`const themeColor = '#202A44'`), site/tailwind.config.ts:9 (`oklch(0.25 0.06 260)` resolves to `#10213E`), site/public/favicon.svg:2 (`fill="#10213e"`, the true token)
- observation: the `theme-color` meta is `#202A44`, the hex the contract lists as a reference. the actual navy token resolves to `#10213E`, sixteen units lighter in red. on ios safari and android chrome the browser chrome paints `#202A44` directly against a `#10213E` nav, a visible two-tone seam at the top of every page on a phone. the favicon already uses the correct hex, so the site ships two navies in its own chrome. note for rob: the flask app's logo and brand navy are `#202a44` (june round, section 1), so tcsc.ski and twincitiesskiclub.org are also two navies. the tokens are fixed identity, so this lens does not propose changing them, only recording the fact.
- proposal: `themeColor = '#10213E'`. correct the reference hex column in design.md (see proposed contract changes). the nav logo fills (CO-12) are the same class of drift.
- workstream: foundations

### CO-4
- surface: home / open, soon, closed, wax-feed / all
- kind: drift
- severity: P2
- contract: "Home page is drenched navy from nav to footer. Photographs ... are the only paper appearances" and "The site reads warmly to scene one and crisp to scene two through commitment to navy, not through paper alternation." and "`<MissionPanel>` ... Single moment of paper before the page returns to navy."
- evidence: site/src/pages/index.astro:103-123 (MissionPanel, then `<SectionBand variant="paper" seam="Our sponsors">`), site/src/components/WaxRoomFeed.astro:22 (`bg-paper`), home-open-desktop.png, home-wax-feed-desktop.png
- observation: the home page has three paper bands: mission, wax room feed (when populated), and the sponsor strip. with the wax feed populated the bottom third of the page is a continuous paper run (feed, sponsors) before the navy cta. today, with no wax entries, the sponsor band sits alone as a second paper island. either way the page alternates, which is exactly the rhythm the theme section rejects. the sponsor logos are the honest constraint: `kwik-trip.jpg` is a jpeg and cannot sit on navy without a white box.
- proposal: put the sponsor strip on navy and set each logo inside a paper frame (`bg-paper px-5 py-3`), which is the contract's own "paper exists inside frames" grammar and reads as a logo plate rather than a band swap. keep mission and the wax feed as the two paper moments, and amend the contract to say two, not one (see proposed contract changes). if rob prefers the paper sponsor band, the alternative is to make the wax feed navy (`bg-navy`, `text-paper`, `divide-mint/15`) so the feed and sponsors do not stack as one paper block.
- workstream: sections

### CO-5
- surface: home / unavailable, dryland / all
- kind: drift
- severity: P2
- contract: "`coral` ... Live indicators (the green dot is mint; the pink dot is coral and means 'now / current / open')."
- evidence: site/src/components/LiveConditions.astro:37 (`text-coral` on `[data-updated]`), site/src/components/LiveConditions.client.ts:148-150 (sacred; sets "● Conditions unavailable" / "● Trail reports come back with the snow" into the same span), home-unavailable-desktop.png, home-dryland-mobile.png
- observation: the stamp is coral in every state. "● Live · updated 2:00 PM" is coral, "● Conditions unavailable" is coral, "● Trail reports come back with the snow" is coral, and "Loading conditions…" before the first fetch is coral. the contract gives coral one meaning, "now". an outage and an off-season message wearing the live color say the opposite of what the copy says.
- proposal: css only, no client change. the client sets `data-updated-at` on the root only in the live state (`LiveConditions.client.ts:89`) and deletes it in `renderQuiet` (`:146`). in the component `<style>`: `[data-live-conditions]:not([data-updated-at]) [data-updated] { color: theme(colors.paper / 0.6); }` so loading, unavailable, and dryland stamps are muted paper and only a live fetch turns the dot coral. the `●` glyph then means what the contract says it means.
- workstream: motion-components

### CO-6
- surface: about, community, racing, dry-tri, extra-training-fun, coaches, sponsors, trips, wax-room, wax-entry, 404 / all / all
- kind: elevation
- severity: P2
- contract: "On paper inner pages: a compact horizontal version in the footer, single line per location." and "'Live · updated [n] min ago' indicator in coral, top-right." (the compact variant has no indicator clause)
- evidence: site/src/components/LiveConditions.astro:89-105 (compact variant: no `[data-updated]`, no coral anywhere), about-open-desktop.png, coaches-default-desktop.png
- observation: inner pages contain zero coral. about, community, racing, coaches, trips, wax room, wax entry, dry tri, extra training, and 404 are navy / paper / mint-deep only; sponsors gets one coral line from its cta strip. the compact strip, the signature device, has no live indicator at all, so a visitor on an inner page cannot tell a live report from a stale one. the identity is "navy + mint + coral pink"; ten of eleven routes show two of the three.
- proposal: give the compact strip a leading coral `●` (aria-hidden, `text-coral`, `text-[10px]`) before the first venue, keyed to the same `data-updated-at` rule as CO-5 so it is muted paper when the fetch fails and coral only when live. one coral per inner page, carrying information, inside the max-4 budget.
- workstream: sections

### CO-7
- surface: home, sponsors, extra-training-fun / all / all
- kind: drift
- severity: P2
- contract: "`mint` ... On navy: primary reading color for headings, key body text, primary CTA fills"
- evidence: site/src/components/PhotoMosaic.astro:132 (`h2 ... text-paper`), site/src/components/SeasonsGrid.astro:91 (season name h2 inherits `text-paper`), site/src/components/CTAStrip.astro:61 (`h2 ... text-mint`), site/src/pages/sponsors.astro:43 (`h2 ... text-mint`), site/src/pages/extra-training-fun.astro:40 (fixture names `text-paper`), home-open-desktop.png
- observation: headings on navy are mint in three places (hero h1, cta strip h2, sponsors impact h2) and paper in two (mosaic "Beyond practice" h2, the two season-name h2s on home). the contract says mint is the reading color for headings on navy. the seasons band is the one place on home where paper headings and mint labels invert the hierarchy: the small "when / where / trips" labels are mint and the big season names are paper.
- proposal: h1 and h2 on navy are mint; h3 and row titles (season fact rows, fixture names, sponsor impact item titles) are paper. concretely: `PhotoMosaic.astro:132` and `SeasonsGrid.astro:91` (navy variant) become `text-mint`. write this as a contract clause so the next component does not have to guess.
- workstream: sections

### CO-8
- surface: about, community, racing, dry-tri, extra-training-fun, home, 404, wax-room / all / all
- kind: slop
- severity: P2
- contract: "`mint-deep` ... The accessible mint for text/links on paper."
- evidence: site/tailwind.config.ts:47 (`--tw-prose-links: mint-deep`, renders about.astro and dry-tri prose links mint-deep at rest); site/src/pages/community.astro:116, racing.astro:62, dry-tri.astro:81, dry-tri.astro:87, extra-training-fun.astro:89, index.astro:120, 404.astro:63 (`text-navy underline decoration-ink/30 hover:text-mint-deep`, the same 90-character class string copied seven times); site/src/components/WaxRoomFeed.astro:32 (`text-mint-deep hover:text-navy`, the inverse); site/src/components/TripsTable.astro:24 (`text-mint-deep underline`, a fourth recipe); about-open-desktop.png (green prose links) vs community-default-mobile.png (navy ledger links)
- observation: links on paper have four color recipes: prose links mint-deep at rest; hand-coded links navy at rest with an ink/30 underline turning mint-deep on hover; the wax feed "All entries" mint-deep turning navy on hover; the trips empty-state link mint-deep with a full-strength underline. the visual-redesign skill names this directly ("No design system - spacing and colors are ad-hoc per component") and the review spec lists "duplicated class strings" as de-slop.
- proposal: two roles, written into the contract. inline and standalone links on paper: `text-mint-deep underline decoration-mint-deep/40 underline-offset-4 hover:decoration-mint-deep` (matches prose, so `dry-tri.astro:81,87`, `extra-training-fun.astro:89`, `index.astro:120`, `TripsTable.astro:24`, `WaxRoomFeed.astro:32` all converge). ledger row titles that happen to link (community items, race names, 404 destinations): stay navy with `decoration-ink/30`, hover mint-deep, because the row title is the content and the link is secondary. extract the row-title recipe into one class in global.css (`.link-ledger`) so the string exists once.
- workstream: motion-components

### CO-9
- surface: og image / default / all
- kind: elevation
- severity: P2
- contract: proposed: "the og image is the home fold in miniature: a consented club photo with the navy bottom scrim and the mint wordmark lockup, 1200x630. no page ships a share card with no brand color on it."
- evidence: site/public/og/og-default.jpg (1200x630, sunset over a groomed field, twelve skiers, no wordmark, no navy, no mint); site/src/layouts/BaseLayout.astro:24 (every route uses it); site/src/content/site_meta.yaml:8
- observation: the only share card on the site is a bare photograph. its palette is sunset orange and pink over snow, which by luck rhymes with coral, and the green jackets nod at mint, but nothing on the card says tcsc. next to three other club sites in a slack unfurl it is an anonymous sunset. the contract is silent on the og image and the june and july rounds both scoped it out.
- proposal: keep the photo (it is a strong one and its warmth is on brand). add the home hero's own grammar: a bottom scrim `from-navy/95 via-navy/50 to-transparent` over the lower 45%, the mint ski-track wordmark from nav.astro at bottom-left at about 260px wide, and "Twin Cities Ski Club" in paper below it. no gradient decoration, the scrim is functional exactly as in the hero. confirm the photo is in the consent manifest before it ships (it lives in `public/`, outside the photos collection, so the harness cannot check it).
- workstream: sections

### CO-10
- surface: all / all / all
- kind: drift
- severity: P2
- contract: "Contrast verified for the actual pairings used: mint / navy: 8:1 ... paper / navy: 14:1 ... ink / paper: 17:1 ... slate / paper: 7.2:1 ... coral / navy: 5.6:1" and the hex reference column ("`#202A44`", "`#AAF0C1`", "`#FF8FA3`")
- evidence: site/tailwind.config.ts:8-20 (the oklch values), computed: mint/navy 12.83, paper/navy 15.38, ink/paper 18.04, slate/paper 5.74, coral/navy 6.48, mint-deep/paper 4.95, mint-deep/paper-card 4.74
- observation: five of the six figures in the contract's contrast table are wrong, and slate/paper is wrong in the dangerous direction (7.2 claimed, 5.74 real). the hex reference column does not match the tokens either: navy is `#10213E` not `#202A44`, mint is `#9EF9BE` not `#AAF0C1`, coral is `#FF7C8A` not `#FF8FA3`. the mint-deep figures are the only ones that were measured, and they are exact. everything else was estimated. a reviewer checking the site against this table will pass pairings that fail (CO-1 is the proof).
- proposal: replace the table with measured values and add the alpha pairings the site actually uses (see proposed contract changes). replace the hex column with the resolved hex of each token. add a one-line rule: "any new text pairing is measured, not estimated, before it ships."
- workstream: foundations

### CO-11
- surface: home / open, birkie-hover / all
- kind: drift
- severity: P3
- contract: "Any color outside the tokens above." (banned) and "Colors expressed in OKLCH ... Tailwind tokens defined in `tailwind.config.ts`."
- evidence: site/src/components/LiveConditions.astro:132-135 (`.wax-chip[data-band='green'] { background: oklch(0.62 0.13 150); }` and three more), home-open-desktop.png (four chips)
- observation: the four wax chip colors are the only raw oklch values outside the token files. the comment defends them well: the chip's color is the recommendation itself, a data encoding, muted to sit on navy-deep. they measure 4.8 to 5.5:1 on navy-deep, fine for a non-text mark. but they live in a component `<style>` block, so the contract's single-source rule is broken and the review spec's success criterion ("`global.css` and `tailwind.config.ts` are the only places a value is defined") fails on them.
- proposal: move the four values into the `palette` object in tailwind.config.ts as `wax-green`, `wax-blue`, `wax-purple`, `wax-red`, render the chips with `bg-wax-green` etc., and add a contract clause naming them as data colors that may appear only on the wax chip and never as text or decoration.
- workstream: foundations

### CO-12
- surface: all / all / all
- kind: drift
- severity: P3
- contract: "Any color outside the tokens above." (banned)
- evidence: site/src/components/Nav.astro:17 (`<g fill="#aaf0c1">`), site/src/components/Nav.astro:29 (`<g fill="#fbfbfa">`), site/public/favicon.svg:3 (`fill="#9ef9be"`, the true token)
- observation: the nav logo's ski tracks are `#aaf0c1`, the contract's stale reference hex, twelve units of red and nine of green away from the mint token `#9ef9be` that the headline beside it uses. the letterforms are `#fbfbfa` against paper `#fbfaf8`. the favicon was generated from the real tokens and does not match the nav mark. the june round asked for the fills to be hardcoded, which is right; it just hardcoded the wrong hex.
- proposal: `fill="#9EF9BE"` and `fill="#FBFAF8"`. keep them as attributes, not classes, per the june rationale.
- workstream: sections

### CO-13
- surface: all / all / all
- kind: slop
- severity: P3
- contract: proposed: "hairlines have two weights per surface. structural (seams, grid gaps, section borders): `mint/20` on navy, `ink/15` on paper. row dividers inside a ledger: `mint/15` on navy, `ink/10` on paper. no other rule alpha."
- evidence: navy `/10`: site/src/components/Nav.astro:10, Footer.astro:26, LiveConditions.astro:23, LiveConditions.astro:27; navy `/15`: LiveConditions.astro:48, LiveConditions.astro:76, pages/extra-training-fun.astro:36; navy `/20`: SectionBand.astro:24, SeasonsGrid.astro:75, PhotoMosaic.astro:129, pages/sponsors.astro:49; paper `/10` and `/15` across community.astro:72,109, racing.astro:52,73, dry-tri.astro:36,61, 404.astro:56, TripsTable.astro:16,22,28
- observation: navy has three hairline weights (10, 15, 20) and paper has two (10, 15). the `/10` mint rules on nav, footer, and both edges of the conditions strip measure 2.18:1 against navy, close to invisible, so the nav-to-strip-to-hero stack reads as one undifferentiated block on desktop. the visual-redesign skill lists "Inconsistent spacing / no whitespace system" as a crime; the same holds for rule weights. paper is already a clean two-level system.
- proposal: adopt the two-level rule above. nav, footer, and the conditions strip borders move from `mint/10` to `mint/15` so the chrome seams are perceptible (2.77:1). keep `/20` for seams and grids. dry-tri's leg triptych uses `ink/10` for both its gap and its border (dry-tri.astro:36) where every other photo grid uses `ink/15`; align it.
- workstream: foundations

### CO-14
- surface: 404, home, all / all / all
- kind: slop
- severity: P3
- contract: proposed (folds into CO-8's link rule): "underline decoration on a navy row-title link is `ink/30`; on a navy surface a text link's underline is `mint/40`."
- evidence: `decoration-ink/30` in community.astro:116, racing.astro:62, dry-tri.astro:81,87, extra-training-fun.astro:89, index.astro:120; `decoration-ink/25` in 404.astro:63; `decoration-mint/40` in LiveConditions.client.ts:199 (sacred, leave); `decoration-mint/50` in Nav.astro:47 (active-page rule, a different device)
- observation: the 404 page is the one place the ledger-link underline is `/25` instead of `/30`. nobody will see the difference, which is the point: it is a value that differs by page for no reason, the pattern the review spec names.
- proposal: `404.astro:63` to `decoration-ink/30`, or better, consume the `.link-ledger` class from CO-8 so the value exists once.
- workstream: motion-components

### CO-15
- surface: trips / populated / desktop
- kind: slop
- severity: P3
- contract: "`paper-card` ... Embedded content on paper sections ... Difference is barely visible." and "Any color outside the tokens above."
- evidence: site/src/components/TripsTable.astro:38 (`hover:bg-ink/[0.03]`)
- observation: the trip row hover tint is an arbitrary-value class, `ink` at 3% over paper. the contract has a token for a barely-visible tint on paper: `paper-card`. this is the only arbitrary color value in the site.
- proposal: `hover:bg-paper-card`. same effect, one fewer non-token value, and the tint now matches the wax entry aside and every other embedded-on-paper surface.
- workstream: foundations

### CO-16
- surface: wax-entry / default / all
- kind: drift
- severity: P3
- contract: "Soft-tinted gray cards on paper. If a card needs definition, give it a 1px ink-15% rule or a clear background, not a gray drop-shadowed slab." (banned)
- evidence: site/src/components/WaxEntry.astro:62 (`<aside class="mt-6 bg-paper-card p-4 rounded-md ...">`), wax-entry-default-desktop.png
- observation: the conditions snapshot aside is a rounded, tinted slab on paper. no shadow, so it is not the worst form of the banned pattern, but it is the only rounded tinted box on any inner page and it sits directly above a hairline-ruled editorial layout that never uses a box anywhere else. the same three facts (location, temp, wax used) are exactly the ledger grammar the trail report and the seasons grid use.
- proposal: drop the tint and the radius. render it as a ruled row: `border-y border-ink/15 py-4 flex gap-8`, labels `text-[11px] tracking-[0.14em] uppercase text-mint-deep` and values `text-ink`, the same label voice as the hero facts and the seasons dl. it then reads as the wax room's own conditions strip in miniature, which is the point of the device.
- workstream: sections

### CO-17
- surface: home, about, 404, sponsors / all / all
- kind: slop
- severity: P3
- contract: "`<CTAStrip>` ... single mint-filled CTA." and "`mint` ... primary CTA fills"
- evidence: site/src/components/CtaForState.astro:29 (`bg-mint text-navy ... hover:bg-paper active:bg-mint/90`), site/src/components/CTAStrip.astro:66 (`bg-mint text-navy font-semibold rounded-md`, no hover or active state at all), site/src/pages/404.astro:50 (`bg-navy text-mint hover:bg-navy-deep`)
- observation: the primary button has three color recipes. the nav, mobile panel, and hero button turns paper on hover, so the drenched home page grows a white block at its most-clicked spot. the cta strip button, same label, same destination, has no hover state. the 404 button is a third recipe and duplicates the unused `on-paper` variant in CtaForState (CO-18). the visual-redesign checklist asks for hover feedback on every button and the same recipe across the same component type.
- proposal: one primary recipe on navy: `bg-mint text-navy hover:bg-mint/90 active:bg-mint/80` (10.2:1 and 8.9:1 for the navy label). paper is not a button fill on the home page. one primary recipe on paper: `bg-navy text-mint hover:bg-navy-deep`. CTAStrip renders its link through the same class as CtaForState, so the hero and the strip cannot disagree again.
- workstream: motion-components

### CO-18
- surface: shared components / all / all
- kind: slop
- severity: P3
- contract: "`<SectionBand>` ... Variants: `navy`, `paper`, `paper-on-navy`" vs "`<MissionPanel>` ... a full-bleed band, not a floating card" (MissionPanel.astro:2)
- evidence: site/src/components/SectionBand.astro:15-22 (`paper-on-navy` branch: `rounded-xl px-8 py-12`, a floating card), grep: no caller passes `paper-on-navy`; site/src/components/CtaForState.astro:30 (`on-paper` variant), grep: no caller passes `on-paper`; site/src/pages/404.astro:50 (re-implements the on-paper button by hand)
- observation: two color variants are dead. the `paper-on-navy` card was superseded when MissionPanel became a full-bleed band, and its `rounded-xl` card on navy is exactly the shape the contract now bans on home ("Card-shaped components anywhere on the home page"). the `on-paper` cta variant is never used, while the 404 page hand-writes the same colors. dead branches keep a banned shape one prop away.
- proposal: delete the `paper-on-navy` variant from SectionBand and the `paper-on-navy` row from the contract's component table. either use `CtaForState variant="on-paper"` on the 404 page (it has no registration state, so a plain `<Button variant="on-paper">` extracted from CtaForState's class strings is the honest shape) or delete the variant.
- workstream: motion-components

### CO-19
- surface: about, coaches, racing, dry-tri, extra-training-fun, wax-entry / all / all
- kind: drift
- severity: P3
- contract: "`mint` ... On paper: not used directly (too pale); use `mint-deep` for legibility." and "No mono typeface for non-code content."
- evidence: site/tailwind.config.ts:53 (`'--tw-prose-quote-borders': palette.mint`), site/tailwind.config.ts:55-57 (`--tw-prose-code`, `--tw-prose-pre-code`, `--tw-prose-pre-bg`), grep of site/src/content: no blockquote, no code fence in any mdoc
- observation: the prose theme puts raw mint on paper as the blockquote rule (1.20:1, invisible) and themes code blocks that the contract says will never exist. neither is reachable from current content, so this is dead config carrying a banned pairing.
- proposal: `--tw-prose-quote-borders: alpha('ink', 0.15)` (a hairline, matching every other rule on paper) or `palette['mint-deep']` if a quote deserves accent. remove the three code entries; if a wax entry ever needs code the plugin default is fine and the contract says it will not.
- workstream: foundations

### CO-20
- surface: home, community / lightbox / all
- kind: drift
- severity: P3
- contract: "One site, two registers chosen by surface." and "`navy-deep` ... used for navy-on-navy elevation"
- evidence: site/src/components/Lightbox.astro:13 (`bg-ink/95 ... [--focus-ring-color:theme(colors.mint)]`), site/src/components/Lightbox.astro:7-9 (comment explaining the override exists because `bg-ink` is not in the focus map), home-lightbox-desktop.png
- observation: the lightbox is the site's one surface that is neither navy nor paper: ink at 95% over the page. it is a third dark, and it needs a manual focus-ring override because the global map does not know it. the screenshot shows it reading as near-black, colder than the navy it covers.
- proposal: `bg-navy-deep/95`. the surface stays in the two-register system, the global focus map already handles `.bg-navy-deep`, and the explicit `--focus-ring-color` override can be removed. (tailwind emits `bg-navy-deep/95` as a class, so the base-layer `.bg-navy-deep` selector still needs its own utility present; if it does not match, add `.bg-navy-deep\/95` to the map rather than keep the inline override.)
- workstream: motion-components

### CO-21
- surface: home, about / open / all
- kind: elevation
- severity: P3
- contract: "`coral` ... the pink dot is coral and means 'now / current / open'." and "Coral ... ≤4 uses per page."
- evidence: site/src/components/SeasonsGrid.astro:96 (open note: `font-semibold text-mint`; closed note: muted), home-open-mobile.png (both season notes mint, indistinguishable from the fee and labels)
- observation: when a season is open for registration, the card says so in mint semibold, the same color as the fee and the three fact labels around it. mint on this card means "label". the contract already assigns the meaning "open" to a coral dot, and the trail report trains the visitor to read that dot on the same page.
- proposal: when `open` is true, prefix the note with an aria-hidden coral `●` (`text-coral text-[10px] mr-1.5`) and leave the note text mint. coral count on home becomes: live stamp, one or two season dots, cta strip border, at most four, with the fever note's transient coral not counted as a static use. on the paper variant (about) the dot is coral too; coral on paper is 2.37:1, which is fine for a non-text glyph next to mint-deep text but must never be text there (see proposed contract changes).
- workstream: sections

### CO-22
- surface: about, community, racing, dry-tri, extra-training-fun, coaches, sponsors, trips, wax-room, home / all / all
- kind: drift
- severity: P3
- contract: "`<Hero>` (inner) ... ink display H1" and "`<MissionPanel>` ... ink display H1, slate body, ink-color link out." vs "`ink` ... Body text on paper."
- evidence: site/src/components/HeroInner.astro:30 (`text-navy`), site/src/components/MissionPanel.astro:18 (`text-navy`), site/tailwind.config.ts:45 (`--tw-prose-headings: navy`), every hand-coded h2 and h3 on paper (`text-navy`, 32 occurrences)
- observation: the contract says ink for display headings on paper in two places; the site uses navy for every heading on paper without exception and ink for body. the site is right: navy (L 0.25) over ink (L 0.18) gives headings a faint hue lift that ties them to the nav and footer, and navy/paper is 15.4:1. this is the contract lagging the build, and the mission panel's "slate body" clause is also stale (the body is the display-scale paragraph, in navy).
- proposal: no code change. amend the contract: on paper, headings and display text are `navy`, body is `ink`, secondary body and meta are `slate`. update the HeroInner and MissionPanel rows to match.
- workstream: foundations

### CO-23
- surface: home / hero / all
- kind: drift
- severity: P3
- contract: "Headline set in mint over a navy-gradient bottom-vignette for legibility (gradient is functional, not decorative)."
- evidence: site/src/components/HeroHome.astro:59 (`from-navy/95 via-navy/50 via-45% to-transparent`), site/src/components/HeroHome.astro:63 (`text-paper/85` subline), site/src/components/HeroHome.astro:73 (`text-paper/60` dates line), home-hero-mobile.png, home-soon-mobile.png
- observation: the scrim is correct and functional. the subline and the coming-soon dates line are set at paper/85 and paper/60 over the scrim, which is 95% navy at the very bottom but thinning to 50% by 45% of the frame's height. on the 390px capture the subline sits where the scrim is still dense, so it passes; on the tablet capture the subline's top edge sits nearer the thinning zone over the green jacket. contrast over a photograph is not measurable in general, but the composition puts the two lowest-alpha text runs on the page over the one background that is not a token.
- proposal: keep the scrim. set the subline to `text-paper` (full) and the dates line to `text-paper/75`, the same floor the july round set for muted text on navy. two fewer alpha steps on the page, no visual cost where the scrim is dense, and a real margin where it is not.
- workstream: sections

### CO-24
- surface: home / open / desktop
- kind: slop
- severity: P3
- contract: proposed: "text on navy uses at most three tones: `mint`, `paper`, `paper/75`. hairline-weight labels may use `paper/55`. nothing else."
- evidence: site/src/components/LiveConditions.astro:36 (`text-mint/90`), :37 (`text-coral`), :50 (`text-paper/55`), :53 (`text-paper/60`), :58 (`text-paper/70`), :80 (`text-mint/50`), :85 (`text-paper/70`); site/src/components/LiveConditions.client.ts:221 (`text-paper/50`, sacred); SectionBand.astro:23 (`text-mint/90`); PhotoMosaic.astro:134 (`text-mint/80`); Footer.astro:30 (`text-paper/70`), :45-46 (`text-paper/50`); Nav.astro:38 (`text-paper/85`); SeasonsGrid.astro:78 (`text-paper/75`); sponsors.astro:46 (`text-paper/85`), :53 (`text-paper/80`); extra-training-fun.astro:43 (`text-paper/80`)
- observation: text on navy uses eleven distinct tones: mint, mint/90, mint/80, mint/50, paper, paper/85, paper/80, paper/75, paper/70, paper/60, paper/55, paper/50. all pass aa (the lowest, paper/50 on navy, is 8.2:1), so this is not a contrast finding. it is a system finding: the july round chose paper/75 as the muted tone for the seasons band, and since then five other muted tones have been added around it. the visual-redesign skill's audit calls this "No visual hierarchy: everything the same size, weight, and color" in reverse: so many tones that none of them means anything.
- proposal: collapse to the three-tone rule above (plus `paper/55` for the 10px tracked venue labels, which need to recede). map: `/85` and `/80` become `paper`; `/70`, `/60` become `paper/75`; `/50` in the footer becomes `paper/75`; `mint/90` and `mint/80` become `mint`; `mint/50` on the fever note stays (it is an off state that turns coral on play, a real state change). the sacred `text-paper/50` in the client's groomed line is left alone and noted for a later pass.
- workstream: foundations

### CO-25
- surface: sponsors / default / all
- kind: drift
- severity: P3
- contract: "More than three accent colors per surface ... On navy: mint + coral + paper-inside-frames is the limit."
- evidence: site/src/pages/sponsors.astro:30-59 (navy band: mint h2, mint h3 item titles, paper/85 intro, paper/80 detail, mint/20 rules, a photo), sponsors-default-desktop.png
- observation: the navy band on sponsors is the one navy band on an inner page with a full editorial layout, and it holds to the limit: mint, paper, one photo. this is a pass, recorded so the ledger shows the accent budget was checked on the one surface likely to break it. the paper section below it also passes (navy, mint-deep, slate; the coral cta border belongs to the strip).
- proposal: none. keep as the reference example when the contract clause on accent budget is rewritten.
- workstream: sections

## proposed contract changes

- replace the "Contrast verified" table with measured values and add the alpha pairings in use: mint/navy 12.8, paper/navy 15.4, paper/75 on navy 11.8, mint-deep/paper 4.95, mint-deep/paper-card 4.74, slate/paper 5.7, slate/paper-card 5.5, ink/paper 18.0, coral/navy 6.5, coral/navy-deep 7.6, navy/mint 12.8 (button label). state that coral on paper is 2.4:1 and is never text on paper. (CO-1, CO-10, CO-21)
- replace the hex reference column with the resolved hex of each token: navy `#10213E`, navy-deep `#051127`, mint `#9EF9BE`, mint-deep `#007E46`, coral `#FF7C8A`, paper `#FBFAF8`, paper-card `#F6F5F2`, ink `#071123`, slate `#5D646F`. note that the flask app's brand navy is `#202A44` and that this difference is accepted, not accidental. (CO-3, CO-10, CO-12)
- add: "secondary text on paper is `slate`. opacity modifiers are not a substitute for a token; no text color on paper may use an alpha below /90." (CO-1)
- add: "text on navy uses `mint`, `paper`, and `paper/75`; 10px tracked labels may use `paper/55`. no other alpha on text over navy." (CO-23, CO-24)
- change "Single moment of paper" to "at most two paper moments on home: the mission panel and the wax room feed. the sponsor strip sits on navy with each logo in a paper frame. paper bands are never adjacent." (CO-4)
- add to the coral row: "coral is a state, not a style: the live stamp is coral only when the fetch succeeded; the open-registration note carries a coral dot only while open. unavailable, loading, and off-season states are muted paper." (CO-5, CO-21)
- add to the LiveConditions section: "the compact variant carries the same coral live dot as the prominent variant, before the first venue." (CO-6)
- add to the mint row: "on navy, h1 and h2 are mint; h3, row titles, and item names are paper." (CO-7)
- add under Color: "links on paper have two roles. inline and standalone links are `mint-deep` with a `mint-deep/40` underline. ledger row titles that link are `navy` with an `ink/30` underline and turn `mint-deep` on hover. one class each, defined in global.css." (CO-8, CO-14)
- add a new section "OG image": the home fold in miniature; consented photo, navy bottom scrim, mint wordmark, paper title; 1200x630; one default for the site, per-entry photos for wax entries. (CO-9)
- add to the banned list an exception: "the four wax-band chip colors (`wax-green`, `wax-blue`, `wax-purple`, `wax-red`) are data colors defined in tailwind.config.ts; they appear only on the wax chip and never as text or decoration." (CO-11)
- add under Color: "hairlines have two weights per surface: structural `mint/20` / `ink/15`, row divider `mint/15` / `ink/10`. nav, footer, and conditions-strip borders are structural weight." (CO-13)
- add under Components: "one primary button recipe per surface. on navy: `bg-mint text-navy hover:bg-mint/90`. on paper: `bg-navy text-mint hover:bg-navy-deep`. paper is never a button fill on the home page." (CO-17)
- remove the `paper-on-navy` variant from the SectionBand row. (CO-18)
- change the HeroInner and MissionPanel rows: headings and display text on paper are `navy`, body `ink`, secondary `slate`; remove "ink display H1" and "slate body". (CO-22)
- change the lightbox surface (not currently in the contract) to `navy-deep/95`, and add it to the focus-ring surface list. (CO-2, CO-20)
- add to Accessibility: "focus rings are decided by the nearest surface, not by a placeholder background on the focused element. photo tiles use an inset mint ring." (CO-2)
