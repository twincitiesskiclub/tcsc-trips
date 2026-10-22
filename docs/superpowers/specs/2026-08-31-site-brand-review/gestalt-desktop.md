# gestalt: desktop

the home page reads as one committed navy object with real people in it: the trail report, the hero, and the photo wall already feel like a club and not a template. the inner pages read as a well-mannered documentation site: a strong left-aligned masthead, then a centered blog column, then ledgers, with the brand living mostly in the nav, the compact strip, and the footer.
furthest from the brand: /sponsors (three shouting display h2s, four content widths, an ellipsis heading), /wax-room (a single slate line as the empty state, a gray slab on the entry page), /coaches (the head coach is the blurriest thing on the site, beside 400px of nothing).
best executed, protect these: the home fold (nav, trail report, hero), the "beyond practice" mosaic with its hover scrim and lightbox, and the inner masthead with its photo band (about, community, racing).
the one systemic change: one page grid. every inner band uses the same container (max-w-7xl, px-10, left edge at 120px on 1440) and the reading column is left-aligned on that grid instead of centered in max-w-3xl. today about has six left edges, community seven, sponsors eight; the eye never finds a spine.
home fold verdict: keep with these changes. i agree with july that it is the strongest screen. fix the fourth member's face under the headline (still there at 768 and 1440), let the hero own the first viewport (it gets 651 of 900px and is cut at the bottom edge), and let the cta rise with the headline instead of sitting alone on navy for the first 100ms.

## per surface

### home / open (home-open-desktop.png)
1. feel: a real club on a real winter evening; navy and mint carry it, and the trail report says "we know snow" before a word of marketing.
2. thread: this is the reference; everything else is judged against it.
3. the single change: give the hero the full first viewport (the fold ends 15px inside the hero, the strip and nav take 249px) and clear the fourth face.
4. rough edges: ~210px of empty navy between the seasons dues line and the "beyond practice" seam (scroll-1700 live capture); the mission paragraph mixes two typefaces because parentheses, hyphens, and periods fall back to archivo inside polysans; the sponsor band goes paper on a page the contract says is drenched navy, and the "about our sponsors" link floats 700px away from the logos; at t=0 of the page load the cta button is the only thing on an empty navy hero.

### home / soon (home-soon-desktop.png)
1. feel: same page, honest state: "fall registration dates" plus "returning members sep 30 · new members oct 15" under the button.
2. thread: yes.
3. the single change: the button is a same-page anchor that hard-jumps 4,000px to the cta strip, where the same dates appear smaller. the dates line under the button already answers the question; the button should go to tcsc.ski or not be a button.
4. rough edges: dates line at text-sm paper/60 is the quietest line in the fold and is the one piece of information a coming-soon visitor came for.

### home / closed (home-closed-desktop.png)
1. feel: calm; "how to register" reads as a cta and not a dead end (july's fix holds).
2. thread: yes.
3. the single change: none beyond the open-state fixes.
4. rough edges: the hero cta and nav cta shrink to a shorter label; the nav still balances.

### home / dryland (home-dryland-desktop.png)
1. feel: thin. four venues vanish and one "birkie fever 98.6°" cell sits in an 80 percent empty band with a lone left hairline, like a table that lost its columns.
2. thread: the fold above and below still reads as the brand, but the strip reads as broken for a second.
3. the single change: in dryland the strip should collapse to a single dateline (compact grammar: "trail report · dryland season · birkie fever 98.6°") rather than an empty grid.
4. rough edges: "trail reports come back with the snow" in coral is the best line on the page and it is 11px, right-aligned, easy to miss.

### home / unavailable (home-unavailable-desktop.png)
1. feel: five "no report" cells with hairlines; intentional but reads like a table with no data, not the "quiet line" the contract describes.
2. thread: yes, barely.
3. the single change: one quiet line under the venue names instead of five repeats.
4. rough edges: the coral stamp says "conditions unavailable" and each cell says "no report": two phrasings for one state.

### home / birkie-hover (home-birkie-hover-desktop.png)
1. feel: nothing visibly happens; the ♪ brightens from mint/50 to mint. a visitor would not know the cell is a button.
2. thread: yes.
3. the single change: fine as an easter egg; if it stays, the note should read as a control (mint at rest, 44px hit area) or the whole cell should not be a button.
4. rough edges: the contract still describes "click a column → expands inline"; the strip never got it and the fever cell took its place.

### home / hero (home-hero-desktop.png, home-hero-tablet.png)
1. feel: the strongest frame on the site: fresh snow, four faces, mint headline. at 1440 the fourth member's forehead is under "twin" and the eyes are under the subline; at 768 the whole face is under the headline.
2. thread: yes.
3. the single change: clear that face. at 1440 the image is width-fitted so horizontal object-position does nothing; only the vertical value or a source crop can move it.
4. rough edges: the scrim is heavy across the bottom 45 percent, which is right for legibility but turns the left member into a navy silhouette; h1 at 72px/1.02 is below the contract's 6rem/0.95 desktop display size.

### home / wax-feed (home-wax-feed-desktop.png, waxfeed-hover-row live capture)
1. feel: a good logbook line, and the only place on the home page where the club writes in its own voice.
2. thread: the feed is paper, then the sponsors band is paper, so 584px of paper with two hairline seams stack before the coral rule. the "drenched navy" promise is broken at the bottom of the page.
3. the single change: keep the feed as the second paper moment and move the sponsor logos onto navy inside paper frames, so the page returns to navy before the close.
4. rough edges: the row hover goes mint-deep on the title only; fine. the feed's headline "from the wax room" is 36px display with no seam label, while every other band has one.

### home / lightbox (home-lightbox-desktop.png, lightbox-040 and lightbox-340 live captures)
1. feel: functional and quiet; the photo is the only bright thing.
2. thread: yes, apart from the arrows.
3. the single change: replace the "←" "→" text glyphs in bordered boxes with lucide chevrons and no border; the close x already uses a proper icon.
4. rough edges: opening is a hard cut, the contract says 200ms scale-in; bg-ink/95 lets the page ghost through, which is fine; caption "· photo 5 of 9" is good.

### home / mosaic-hover (home-mosaic-hover-desktop.png)
1. feel: right. the bottom scrim carries the caption and the photo stays a photo.
2. thread: yes.
3. the single change: none. protect.
4. rough edges: the 2x2 lead tile shows a parking lot for its top 40 percent; a crop with object-position center 65% would fill the tile with the table and faces.

### about / open and closed (about-open-desktop.png, about-closed-desktop.png)
1. feel: a good masthead and photo band, then the page turns into a centered blog: the h1 sits at x=104, the prose at x=360, the seasons heading at 360, the seasons cells at 160.
2. thread: the top 700px is the brand; below it the page could be any astro starter with a nice palette.
3. the single change: left-align the reading column to the masthead grid (or a fixed 3/9 split with the h2s in the left column like the community ledger).
4. rough edges: "about twin cities ski club" orphans "club" on its own line; the team photo band trims the top row of heads at center 40%; the "seasons" band is the only band with an h2 and no seam; the closed state's muted note is right.

### community (community-default-desktop.png)
1. feel: generous and true, and 8,179px long. the ledger is on-language but "how members pitch in" is twenty rows and the eye stops reading at row eight.
2. thread: the masthead, canoe band, and 2x2 cluster are the brand; the photo wall at the bottom starts as an unlabeled navy block with no seam or heading, which reads as a different page.
3. the single change: cap each ledger group at three or four rows with a link out, and give the wall the same seam + heading grammar the home mosaic has.
4. rough edges: canoe band crops the tallest head at the top edge; the 2x2 cluster is 720px wide inside a 1440 page while the group anchors are 890px, a third width; "extra training fun" repeats the etf page's content.

### racing (racing-default-desktop.png)
1. feel: the best inner page. masthead, frosty race crew, a ledger of races with real dates.
2. thread: yes.
3. the single change: the five-up photo strip at 144px tiles turns faces into thumbnails; let it break to the band width.
4. rough edges: the ledger's uppercase mint dates ("jan 9, 2027") make six more tracked caps on a page that already has two stat labels; "late january" and "local series" in caps read as categories, not dates.

### dry-tri (dry-tri-default-desktop.png)
1. feel: an event page with real energy; the triptych is the right idea.
2. thread: mostly. the triptych sits inside a 1px border box, the only bordered photo group on the site.
3. the single change: one photo-group grammar (flush, gap-px, no border) shared with the community cluster and the racing strip.
4. rough edges: widths jump 120 → 360 → 120 → 360 down the page; the "2025" and "2026" prose h2s are archivo while every other h2 is display; the rollerski leg crops the helmet.

### extra-training-fun (extra-training-fun-default-desktop.png)
1. feel: the most "member" page: a navy band of standing invitations, two captioned photos, and the annuals. it feels written, not templated.
2. thread: yes.
3. the single change: align the prose column to the grid; the "how it works" block floats at 360 between two 120-aligned bands.
4. rough edges: the invitations ledger content ends at ~1000px in a 1200px band; the two-up photos use gap-6 while every other group uses gap-px; the closing "the club also puts on its own fall race" line is a good hand-off and should be the pattern for the community page's etf group.

### coaches (coaches-default-desktop.png)
1. feel: kj's portrait is visibly soft at 427px wide and it is the first thing on the page; beside it one sentence and three bullets leave 400px of paper.
2. thread: the names at display scale and the mint-deep roles are right; the composition is not.
3. the single change: fix the first entry. a sharper consented photo of kj, or a smaller slot (col-span-4, square) so the softness stops being the headline; and let each entry's slot height follow its text.
4. rough edges: the masthead facts ("two seasons a year / coaching") pair a sentence with a category; the credential bullets use a leading middot as a fake bullet.

### sponsors (sponsors-default-desktop.png)
1. feel: the page a sponsor on a 27-inch monitor will judge the club by, and it is the most template-like: three 48px display h2s in three bands, each with a photo and a ledger, plus a wall that sits in its own 5xl width.
2. thread: the navy "sponsor impact" band is on-language; the page as a whole is louder than any other.
3. the single change: one h2 scale per page (text-4xl), one grid, and one heading that does not end in an ellipsis ("sponsor support helped tcsc..." renders the dots in the fallback face).
4. rough edges: disclosure line at x=80, a ninth left edge; "?" in "interested in supporting tcsc?" renders in archivo; the wall's "trailblazer partners" heading is the only h2 indented to 248px; two logos in 1440px of paper look like a wall with two bricks.

### trips / empty and populated (trips-empty-desktop.png, trips-populated-desktop.png, trips-hover-row live capture)
1. feel: restrained and right. a ledger with a header row and a ruled placeholder gives one trip (or none) dignity.
2. thread: yes, apart from the width: the ledger sits at 296px, a fourth content width.
3. the single change: put it on the grid.
4. rough edges: the row hover tints the row bg-ink/3 and turns the title mint-deep, the site's only row-tint hover; the populated page is 900px tall with 300px of paper under one row, which is fine.

### wax-room / empty and populated (wax-room-empty-desktop.png, wax-room-populated-desktop.png)
1. feel: empty state is one slate line, "no entries yet.", floating in 550px of paper. the populated index is a plain list.
2. thread: the trips page solved the same problem in the ledger grammar; the wax room did not get the treatment.
3. the single change: an empty state in the ledger grammar with one honest line ("no entries yet. the first field report lands with the first snow.").
4. rough edges: index entry title, byline, and lede are three type sizes with no rule between entries and the date above the title; the home feed and the index use different row grammars for the same content.

### wax-entry (wax-entry-default-desktop.png)
1. feel: an editorial entry with the right bones: date, display title, byline, photo, lede, body.
2. thread: the conditions snapshot is a rounded gray slab, which the contract bans on paper.
3. the single change: a ruled dl (border-y ink/15) with location, temp, wax used, in the seasons dl grammar.
4. rough edges: the 16:9 photo crops the group photo to a strip of faces; the h1 wraps "year (fixture)" because the display face is wide at 48px in a 720px column.

### 404 (404-default-desktop.png)
1. feel: three shouts on one page: "this trail ends here." at 60px, a full-bleed trail band, then "choose another page." at 48px with a "404 · page not found" eyebrow.
2. thread: yes, the pieces are all on-language; there are just too many.
3. the single change: one display heading. move "404" into the masthead subhead, drop the second display h2 to archivo 600 text-2xl or delete it.
4. rough edges: "back to home" is a navy button with mint text, a third button recipe; the destinations list is good.

### og image (site/public/og/og-default.jpg)
1. feel: a beautiful sunset skate photo with no mark on it. in a slack unfurl it is an anonymous photo.
2. thread: no. nothing says tcsc, navy, or mint.
3. the single change: the same photo with a navy bottom scrim and the mint logo lockup bottom-left, nothing else.
4. rough edges: this photo is not used anywhere on the site, so the unfurl and the landing do not match.

### shared components
- nav: right. logo, six links, mint cta. hover mint, focus ring mint (after a 150ms fade, see gd-12). the cta hover flips mint to paper, a white flash on a navy bar.
- live conditions, prominent: the signature device works. the compact variant on inner pages is a good dateline; venue names carry an underline and read as links, which they are.
- section band: the seam device (11px tracked caps + hairline) is the site's section grammar and it works; it just contradicts the contract's eyebrow count. the contract should change, not the site.
- mission panel: right placement, wrong weight: a 30px display paragraph with fallback glyphs.
- seasons grid: the best ledger on the site; on navy the mint labels and paper/75 muted text are balanced.
- cta strip: fine; the coral rule is the one coral punctuation per page and it earns it. the button has no hover state.
- footer: fine. the wordmark is the display cut at 13px uppercase, a fourth wordmark treatment (nav svg, footer caps, og nothing, favicon pill).
- hero inner: the strongest inner component; the facts column and photo band answer "the pages feel blank" without a new hero shape.
- photo mosaic and lightbox: protect. one grammar for photo groups should extend from here to the cluster, strip, triptych, and pair.
- coach entry: not a card, correctly; the slot height and photo quality are the problem, not the shape.
- sponsor wall: two logos need a wall grammar that does not look empty at 1440.
- trips table: the ledger to copy for every list on the site.
- wax room feed and wax entry: right bones, one banned slab.

## findings

### GD-1
- surface: home / hero / desktop, tablet
- kind: drift
- severity: P1
- contract: proposed: "no face sits under the hero text block at 390, 768, or 1440"
- evidence: site/src/components/HeroHome.astro:155, home-hero-desktop.png, home-hero-tablet.png
- observation: the fourth member's face is under the headline and subline at 1440 and fully under the headline at 768. the image is width-fitted at 1440, so the horizontal object-position value has no effect there.
- proposal: change `object-[center_15%] max-md:object-[60%_15%]` to `object-[center_0%] max-md:object-[60%_10%]` and verify at three widths; if the face is still under the block, crop the source jpg to drop the bottom 12 percent (crop fixes are in scope) and keep the text block where it is.
- workstream: sections

### GD-2
- surface: home / all / desktop
- kind: elevation
- severity: P2
- contract: proposed: "at lg the hero fills the first viewport below the nav and strip; the fold ends on the hero's bottom edge"
- evidence: site/src/components/HeroHome.astro:187-196, live measurement: hero 249 to 915 in a 900px viewport, strip 172px
- observation: nav plus strip take 249px, the hero gets 651px, and the fold cuts the hero 15px above its bottom edge.
- proposal: `.hero-frame { height: calc(100svh - 249px) }` at lg with the 540px minimum kept, and trim the strip from 172 to about 150px (`pb-3` on the grid, `min-h-8` to `min-h-4`), so the first screen is nav, strip, hero, exactly.
- workstream: sections

### GD-3
- surface: home / open / desktop
- kind: elevation
- severity: P3
- contract: "The headline appears at 200ms with a 4px upward translation. Single orchestrated entrance per session"
- evidence: site/src/components/HeroHome.astro:169-178, live capture home-entrance-0000.png
- observation: the cta button is static, so for the first 100ms of a load it is the only element on an empty navy hero.
- proposal: add the `hero-headline` class to the `div.mt-8` cta wrapper so it rises with the headline at the same 250ms/120ms timing; nothing else animates.
- workstream: motion-components

### GD-4
- surface: home / all / all
- kind: elevation
- severity: P2
- contract: "The display cut is used at most 2–3 places per page"
- evidence: site/src/components/MissionPanel.astro:205, home-open-desktop.png, live check: glyphs `()-.` fall back to archivo
- observation: the mission paragraph is five lines of polysans bulkywide at 30px; parentheses, hyphens, and periods render in archivo inside it, so the paragraph mixes two faces and is the heaviest type on the page after the h1.
- proposal: set the mission in archivo, `font-semibold text-2xl md:text-3xl leading-[1.3] text-navy`; reserve the display cut on home for the h1, the four section h2s, and the stat values.
- workstream: foundations

### GD-5
- surface: home / all / desktop
- kind: elevation
- severity: P2
- contract: "sections breathe variably (96–144px y-padding on home)"
- evidence: site/src/components/SectionBand.astro:163 (`pb-20 md:pb-28`), site/src/components/PhotoMosaic.astro:124 (`pt-12 md:pt-16`), live capture scroll-1700.png
- observation: between the seasons dues line and the "beyond practice" seam there is about 210px of empty navy (112 band bottom + 64 seam top + the dues line's own padding); it reads as a missing section.
- proposal: seam-led bands own their top space only; set SectionBand `pb-16 md:pb-20` when the next band is the same surface, and define the two home gaps once as tokens (`--band-gap-sm: 96px`, `--band-gap-lg: 128px`) used by SectionBand, PhotoMosaic, WaxRoomFeed, and MissionPanel.
- workstream: sections

### GD-6
- surface: home / open, wax-feed / all
- kind: drift
- severity: P2
- contract: "Home page is drenched navy from nav to footer. Photographs ... are the only paper appearances" and "paper exists inside photo frames"
- evidence: site/src/pages/index.astro:115-123, site/src/components/WaxRoomFeed.astro:321, home-wax-feed-desktop.png, live measurement: paper bands at 3755+303 and 4058+281
- observation: the sponsor band is paper; with wax entries published the feed is also paper, so 584px of paper with two hairline seams stack before the coral rule. the "about our sponsors" link sits 700px from the logos.
- proposal: sponsors band goes `variant="navy"` with each logo inside a paper frame (`bg-paper p-5`, flush, `gap-px`, the same frame grammar as the mosaic tiles) and the link directly after the frames; the wax feed stays the second paper moment (contract change, see gd-27b). home then runs navy, paper (mission), navy, navy, paper (wax), navy, navy.
- workstream: sections

### GD-7
- surface: home / dryland / desktop
- kind: elevation
- severity: P2
- contract: "Sparse data fallback ... Never broken; always intentional."
- evidence: home-dryland-desktop.png, site/src/components/LiveConditions.astro:253-300
- observation: in dryland the four venue cells disappear and the birkie fever cell sits alone with a left hairline in an 80 percent empty band.
- proposal: when the client marks the strip dryland (whatever attribute it sets; the client is sacred), css switches the prominent grid to a single dateline: `trail report · dryland season · birkie fever 98.6°` in the compact grammar, 40px tall; the venue names stay server-rendered for no-js visitors.
- workstream: sections

### GD-8
- surface: home / unavailable / desktop
- kind: elevation
- severity: P3
- contract: "the strip shows location names + a quiet 'Conditions unavailable' line"
- evidence: home-unavailable-desktop.png
- observation: five cells each say "no report" under hairlines, and the stamp says "conditions unavailable"; two phrasings and a table with no data.
- proposal: cells show only the venue name; one line under the row, `no report · conditions unavailable`, in paper/55; the coral stamp stays.
- workstream: copy

### GD-9
- surface: home / lightbox / desktop
- kind: elevation
- severity: P3
- contract: "Lightbox open: 200ms scale-in with opacity. Lightbox navigation: hard-cut." and "Iconography: Lucide ... lightbox close"
- evidence: site/src/components/Lightbox.astro:274-275, site/src/components/PhotoMosaic.client.ts:46, home-lightbox-desktop.png
- observation: prev and next are the text glyphs "←" "→" inside bordered rounded boxes, the only place the site uses arrow glyphs; opening is a hard cut, which the client comments call "per spec" while the contract says 200ms.
- proposal: lucide `chevron-left` and `chevron-right` at 24px, no border, 44px hit area, paper/70 at rest and mint on hover; change the contract to hard-cut open (the hidden/flex toggle cannot transition without js, and js is sacred).
- workstream: motion-components

### GD-10
- surface: shared / all / all
- kind: slop
- severity: P3
- contract: proposed: "one primary button recipe, one secondary; no third"
- evidence: site/src/components/CtaForState.astro:173-175, site/src/components/CTAStrip.astro:411, site/src/pages/404.astro:249, live captures hover-nav-cta.png and hover-cta-strip.png
- observation: three button class strings: the nav and hero cta hover mint to paper (a white flash on navy), the cta strip button has no hover at all, the 404 button is navy with mint text. `visual-redesign` names duplicated class strings as slop.
- proposal: `.btn-primary` in global.css: `bg-mint text-navy font-semibold rounded-md px-5 py-3 hover:bg-mint/85 transition-colors duration-150`; `.btn-on-paper`: `bg-navy text-mint hover:bg-navy-deep`; all four call sites use them.
- workstream: motion-components

### GD-11
- surface: home / open / desktop
- kind: elevation
- severity: P2
- contract: proposed: "the coming-soon cta links out; same-page anchors are not ctas"
- evidence: site/src/content/pages/home.yaml (`cta_coming_soon_url: https://twincitiesskiclub.org/#registration`), site/src/pages/index.astro:36-53, home-soon-desktop.png
- observation: "fall registration dates" hard-jumps 4,000px to the cta strip, where the same dates print smaller; the dates line already sits under the button.
- proposal: `cta_coming_soon_url` becomes `https://tcsc.ski/` and `cta_coming_soon_label` becomes `How to register` (the closed label), keeping the dates line under the hero button at `text-sm text-paper/85` so it reads as information, not a footnote.
- workstream: copy

### GD-12
- surface: shared / all / desktop
- kind: elevation
- severity: P3
- contract: "Focus rings: 2px mint on navy, 2px navy on paper. Always visible on keyboard navigation."
- evidence: live measurement: nav link outline-color paper/85 at t0, mint at t250; site/src/components/Nav.astro:401, site/src/components/CtaForState.astro:174
- observation: `transition-colors` includes outline-color, so the focus ring fades in over 150ms on every link and button that has a color transition.
- proposal: in global.css `:focus-visible { transition: none; }` inside the base layer, or scope link transitions to `transition-[color,background-color,text-decoration-color]`.
- workstream: motion-components

### GD-13
- surface: about, community, racing, dry-tri, extra-training-fun, coaches, sponsors, trips, wax-room / all / desktop
- kind: elevation
- severity: P2
- contract: "Grid: 12-col ... Max content width ... 1080px on inner pages" (the contract names one width; the site uses seven)
- evidence: live census of left edges at 1440: about [120,160,258,360,761,858], community [0,120,360,430,721,742,1081], sponsors [80,104,120,248,408,643,663,853]; site/src/components/HeroInner.astro:28 (px-6, 104), site/src/components/SectionBand.astro:169 (px-10, 120), site/src/pages/about.astro:141 (max-w-3xl, 360), site/src/pages/trips/index.astro:12 (max-w-4xl, 296), site/src/pages/sponsors.astro:223 (max-w-5xl, 248), site/src/pages/sponsors.astro:304 (px-6, 80), site/src/components/CoachEntry.astro:56 (max-w-6xl, 168)
- observation: the masthead is left-aligned at 104, bands at 120, prose centered at 360, and every page adds a width of its own. the eye never finds a spine; this is what makes the inner pages read as a template.
- proposal: one container for every band and the masthead (`max-w-7xl px-6 md:px-10`, left edge 120 at 1440); the reading column is `md:col-start-1 md:col-span-8 max-w-prose` on that grid, left-aligned, or the 3/9 split with the h2 in the left column (the community ledger already does this); delete the `max-w-3xl/4xl/5xl/6xl mx-auto` wrappers.
- workstream: foundations

### GD-14
- surface: about, wax-entry / all / desktop
- kind: elevation
- severity: P3
- contract: proposed: "display headings are balanced; no single-word last lines"
- evidence: about-open-desktop.png ("club" alone), wax-entry-default-desktop.png ("year (fixture)"), site/src/components/HeroInner.astro:30
- observation: the about h1 orphans "club"; the wax entry h1 wraps at the wide display face in a 720px column.
- proposal: `text-balance` on HeroInner h1 and WaxEntry h1; wax entry h1 at `md:text-4xl` (the column is narrow).
- workstream: foundations

### GD-15
- surface: coaches / default / desktop
- kind: elevation
- severity: P1
- contract: "photographs as the moments of light" and CoachEntry's own note that kj's source is soft
- evidence: site/src/components/CoachEntry.astro:7-11, :56-75, coaches-default-desktop.png
- observation: the head coach's portrait is visibly soft at 427x534 css px and is the first image on the page; beside it one sentence and three bullets leave about 400px of empty paper.
- proposal: first, ask rob for a sharper consented photo of kj (the only real fix); until then render kj's slot `md:col-span-4 aspect-square` (fewer device pixels, the softness drops below notice) and top-align the entry so the slot never towers over one sentence; give each coach's entry a pull quote or a "coaches: tuesday · thursday" fact line so the column is not empty.
- workstream: sections

### GD-16
- surface: community / default / desktop
- kind: elevation
- severity: P2
- contract: proposed: "a ledger group shows at most four rows on a hub page; the rest live on the destination page"
- evidence: community-default-desktop.png (8,179px), site/src/pages/community.astro:91-129, site/src/content/pages/community.mdoc takeaways
- observation: "how members pitch in" runs about twenty rows across four groups; the extra training fun group repeats the etf page. the page is three times the length of any other inner page.
- proposal: cap each group at four rows; the etf group keeps one row plus the link (the etf page already holds the rest); `py-5` to `py-4` on ledger rows.
- workstream: sections

### GD-17
- surface: community / default / desktop
- kind: elevation
- severity: P2
- contract: "SectionBand ... Takes optional numbered marker ... heading" (one section grammar)
- evidence: site/src/pages/community.astro:132, site/src/components/PhotoMosaic.astro:122 (`pt-20` with no heading), community-default-desktop.png tile 06
- observation: the community photo wall begins as an unlabeled 80px navy block after the paper ledger, then photos. on home the same component has a seam and an h2.
- proposal: pass `number="Photo wall"` and `heading="From the archive"` (or the photo count, "52 photos by members") so the wall uses the seam + h2 grammar everywhere it appears.
- workstream: sections

### GD-18
- surface: racing / default / desktop
- kind: elevation
- severity: P2
- contract: "Asymmetric defaults ... The photo mosaic itself is asymmetric"
- evidence: site/src/pages/racing.astro:206-218, racing-default-desktop.png tile 02
- observation: five 3:4 tiles at 144px wide inside the 720px prose column; faces become thumbnails and the medals photo is a sliver.
- proposal: the strip breaks out to the band container (1200px at 1440): five tiles at 232px, or 3 + 2 with the birkie start at 2x width; `object-position` per tile as the july audit set.
- workstream: sections

### GD-19
- surface: sponsors / default / desktop
- kind: elevation
- severity: P2
- contract: "H2 ... 3.0rem desktop" and "The display cut is used at most 2–3 places per page"
- evidence: site/src/pages/sponsors.astro:240, :275, :286 (three `text-5xl` display h2s), :223 (`max-w-5xl`), :304 (`px-6` disclosure), sponsors-default-desktop.png
- observation: three 48px display h2s in three bands each with a photo and a ledger; the wall sits in its own width; the disclosure sits at x=80; "sponsor support helped tcsc..." ends in an ellipsis rendered in the fallback face, and "?" in the cta heading does the same.
- proposal: h2s at `text-4xl`; the wall on the grid; disclosure moves into the cta strip subhead ("recognition is not endorsement." as the last sentence) or the footer; impact heading becomes "What sponsor support has done" and the cta heading "Interested in supporting TCSC" without the question mark, or the subset gains `?` and `.`.
- workstream: sections

### GD-20
- surface: sponsors / default / desktop
- kind: elevation
- severity: P3
- contract: "SponsorWall: Logo wall ... logos sized by tier. Not tiles."
- evidence: site/src/components/SponsorWall.astro:246-292, sponsors-default-desktop.png tile 00
- observation: two logos in 1440px of paper under "trailblazer partners" read as a wall with two bricks.
- proposal: the wall is a ruled row per tier (border-y ink/15), tier label in the seam voice at left, logos right-aligned in the row; two sponsors fill one row with dignity, ten fill three.
- workstream: sections

### GD-21
- surface: wax-room / empty / desktop
- kind: elevation
- severity: P2
- contract: proposed: "empty states use the ledger grammar: a ruled placeholder row with one plain sentence; never a bare line"
- evidence: site/src/pages/wax-room/index.astro:83, wax-room-empty-desktop.png, site/src/components/TripsTable.astro:115 (the good example)
- observation: "no entries yet." is one slate line in 550px of paper; production shows this today.
- proposal: `<p class="py-6 border-y border-ink/10 text-slate">No entries yet. The first field report lands with the first snow.</p>` on the grid; the same rule covers trips (already done) and any future empty list.
- workstream: copy

### GD-22
- surface: wax-entry / default / all
- kind: drift
- severity: P2
- contract: "Soft-tinted gray cards on paper. If a card needs definition, give it a 1px ink-15% rule or a clear background, not a gray drop-shadowed slab."
- evidence: site/src/components/WaxEntry.astro:62, wax-entry-default-desktop.png
- observation: the conditions snapshot is `bg-paper-card p-4 rounded-md`, a tinted rounded slab.
- proposal: a ruled `<dl>` with `border-y border-ink/15 py-4 flex gap-10`, labels in the seasons dt voice (`text-[11px] tracking-[0.14em] uppercase text-mint-deep`), values in ink.
- workstream: sections

### GD-23
- surface: wax-room / populated / desktop
- kind: elevation
- severity: P3
- contract: proposed: "one row grammar for wax entries: date · author, title, lede, on the home feed and the index"
- evidence: site/src/pages/wax-room/index.astro:85-103, site/src/components/WaxRoomFeed.astro:333-358, wax-room-populated-desktop.png, home-wax-feed-desktop.png
- observation: the home feed is a three-column ruled row; the index is a stacked date / title / byline / lede with no rule above the first entry. same content, two grammars.
- proposal: the index reuses the feed's row (`md:grid-cols-[8.5rem_1fr_auto]`, `border-y divide-y`) with the lede on a second line; the feed component takes a `limit` prop and both call it.
- workstream: motion-components

### GD-24
- surface: 404 / default / all
- kind: elevation
- severity: P3
- contract: "The display cut is used at most 2–3 places per page"
- evidence: site/src/pages/404.astro:231, :240-243, 404-default-desktop.png
- observation: a 60px display h1, a full-bleed trail band, then a 48px display h2 and an eyebrow "404 · page not found": three headlines for one message.
- proposal: masthead subhead becomes "404. The page may have moved, or the link may point to our old site."; delete the eyebrow; "choose another page." becomes archivo `font-semibold text-2xl` or is removed and the button moves up under the subhead.
- workstream: copy

### GD-25
- surface: og image / default / all
- kind: elevation
- severity: P2
- contract: proposed: "the og image is a consented club photo with a navy bottom scrim and the mint logo lockup bottom-left; no other text"
- evidence: site/public/og/og-default.jpg (1200x630), site/src/layouts/BaseLayout.astro:149
- observation: a sunset skate photo with no mark; a slack or imessage unfurl shows an anonymous photo, and the photo does not appear on the site the link opens.
- proposal: keep the photo, add the same functional scrim the hero uses (`from-navy/95 via-navy/50 via-45%`) and the nav svg lockup in mint at about 240px wide, 48px from the left and bottom edges; export at 1200x630 jpeg quality 85.
- workstream: sections

### GD-26
- surface: shared / all / all
- kind: drift
- severity: P2
- contract: "The display cut is used at most 2–3 places per page; everything else is the body family"
- evidence: live census: display leaf elements per page: about 12, community 14, coaches 13, sponsors 12, racing 10, trips 7; site/src/components/TripsTable.astro:135, site/src/components/WaxRoomFeed.astro:343, site/src/components/HeroInner.astro:37, site/src/components/MissionPanel.astro:209, site/src/components/Footer.astro:444
- observation: every h2, h3, stat value, season name, trip name, and the 13px uppercase footer wordmark use polysans. the site has settled on a wider role for the display cut than the contract allows, and mostly it works; the footer wordmark and the ledger row titles are where it stops working.
- proposal: change the contract (see proposed changes) to: display cut for h1, h2, stat values, coach names; archivo 600 for h3, dl values, table and feed row titles; the footer wordmark becomes the nav svg lockup at 120px wide (one mark, everywhere).
- workstream: foundations

### GD-27
- surface: shared / all / all
- kind: drift
- severity: P3
- contract: "eyebrow labels appear at most twice per page, and only where they carry information"
- evidence: live census: home has 11 uppercase tracked labels (trail report, four venue names, two seams, six dl labels, footer wordmark); site/src/components/SectionBand.astro:171, site/src/components/SeasonsGrid.astro:327
- observation: the june and july rounds adopted "small-caps seams" as the ledger language; the contract still bans them as repeating grammar. the site is right and the contract is stale.
- proposal: contract change: the seam (11px, 0.18em, mint/90 on navy, mint-deep on paper, hairline to the right edge) is the section device, one per band; dl labels inside a ledger may use the same voice; uppercase is banned on headings, buttons, and dates (racing's "jan 9, 2027" in caps becomes sentence case, `text-mint-deep text-sm tabular-nums`).
- workstream: foundations

### GD-28
- surface: about / open / desktop
- kind: elevation
- severity: P3
- contract: "SeasonsGrid ... On paper (about): ink headings, slate body, hairline navy divider between the two seasons"
- evidence: site/src/pages/about.astro:154, site/src/components/SeasonsGrid.astro:307 (`p-8 md:p-10`), about-open-desktop.png tile 02
- observation: the seasons band on about is the only band with an h2 and no seam, and the cells' inner padding puts their text at 160, a third left edge on the page.
- proposal: `<SectionBand variant="paper" seam="Seasons">` with no h2 (as on home); cells `py-8 md:py-10 md:pr-10 md:pl-0` for the first and `md:pl-10 md:pr-0` for the second, so text aligns to 120.
- workstream: sections

### GD-29
- surface: dry-tri, extra-training-fun, community, racing / default / desktop
- kind: slop
- severity: P3
- contract: proposed: "one photo-group grammar: flush tiles, gap-px, no border; optional caption in slate below the group"
- evidence: site/src/pages/dry-tri.astro:257 (`gap-px border border-ink/10`), site/src/pages/extra-training-fun.astro:364 (`gap-6` with figcaptions), site/src/pages/community.astro:72 (`gap-px bg-ink/15`), site/src/pages/racing.astro:206 (`gap-px bg-ink/15`)
- observation: four photo-group grammars on four pages, differing by border, gap, and caption. `awwwards-sections` calls this the icon-heading-paragraph pattern's cousin: same component, four hand-rolled versions.
- proposal: a `<PhotoGroup>` (or PhotoMosaic with `variant="row"`) used by all four; the dry tri box loses its border; the etf pair keeps its captions as a group caption line.
- workstream: motion-components

### GD-30
- surface: community, dry-tri, extra-training-fun, racing, sponsors / default / all
- kind: slop
- severity: P3
- contract: proposed: "one ledger component: label column 16rem, body 1fr, optional trailing column; py-5 rows; divide-y ink/10"
- evidence: site/src/pages/community.astro:111 (`minmax(14rem,18rem)_1fr`), site/src/pages/dry-tri.astro:284 (`10rem_1fr_8rem`), site/src/pages/extra-training-fun.astro:351 (`16rem_1fr`), site/src/pages/racing.astro:187 (`10rem_1fr_1fr`), site/src/pages/sponsors.astro:248 (`minmax(12rem,16rem)_1fr`)
- observation: five ledgers, five column specs, five copies of the same underline-link class string.
- proposal: `<Ledger rows={[{label, body, trail, href}]}>` in components, with `variant="navy" | "paper"`; the racing races and dry tri course tables are the same component with a trailing column.
- workstream: motion-components

### GD-31
- surface: home / mosaic-hover / desktop
- kind: elevation
- severity: P3
- contract: "Every object-cover image has a deliberate object-position at both viewports"
- evidence: home-open-desktop.png tile 02, site/src/components/PhotoMosaic.astro:168-177 (no object-position on tiles)
- observation: the 2x2 lead tile shows a parking lot for its top 40 percent; the table and faces are in the bottom half.
- proposal: a per-photo `focal` field is out of scope (no schema changes), so set `object-position: center 65%` on the lead tile via the existing `order`-based lead slot, or choose a lead photo whose subject is centered.
- workstream: sections

### GD-32
- surface: coaches / default / all
- kind: elevation
- severity: P3
- contract: proposed: "masthead facts pair a short value with a noun label"
- evidence: site/src/pages/coaches.astro:179-182, coaches-default-desktop.png
- observation: "two seasons a year / coaching" and "tuesday · thursday / practices" pair a sentence with a category; the stat stack reads best when the value is a number or a name.
- proposal: `{ value: '4', label: 'Coaches' }`, `{ value: 'Tue · Thu', label: 'Practice nights' }`.
- workstream: copy

### GD-33
- surface: about / open / desktop
- kind: elevation
- severity: P3
- contract: "Every object-cover image has a deliberate object-position ... no cropped faces"
- evidence: site/src/pages/about.astro:139 (`center 40%`), about-open-desktop.png tile 00
- observation: the team banner band trims the top row of heads at 280px tall.
- proposal: `photoPosition="center 30%"` or band height `md:h-[320px]` for this photo; verify at 1440.
- workstream: sections

## proposed contract changes

- the seam (11px tracked caps + hairline) is the section device, one per band; dl labels inside ledgers may share the voice; uppercase is banned on headings, buttons, and dates (GD-27)
- display cut for h1, h2, stat values, and coach names; archivo 600 for h3, dl values, table and feed row titles; one wordmark treatment (the nav svg) in nav, footer, and og (GD-26)
- home is drenched navy with two paper moments, the mission panel and the wax room feed; every other band on home is navy; logos and photos on navy sit in paper frames (GD-6)
- one inner-page grid: every band and the masthead share max-w-7xl px-10; the reading column is left-aligned on that grid (cols 1-8, 62ch cap) or a 3/9 split; no centered max-w-3xl/4xl/5xl/6xl wrappers (GD-13)
- no face under the hero text block at 390, 768, and 1440; at lg the hero fills the first viewport below nav and strip (GD-1, GD-2)
- the hero entrance moves photo, headline, subline, and cta together; nothing else on the site animates in (GD-3)
- lightbox open is a hard cut (matching the shipped client); lucide chevrons for prev and next, no bordered glyph buttons (GD-9)
- one primary button recipe (mint on navy, hover mint/85) and one on-paper recipe (navy with mint text); no third; focus rings never transition (GD-10, GD-12)
- empty states use the ledger grammar: a ruled placeholder row with one plain sentence; a bare line is banned (GD-21)
- one ledger component and one photo-group grammar (flush, gap-px, no border, slate caption below) across every inner page (GD-29, GD-30)
- a ledger group on a hub page shows at most four rows and links to the destination page for the rest (GD-16)
- coming-soon ctas link out (tcsc.ski); same-page anchors are not ctas; the dates line under the hero button is the information (GD-11)
- the conditions strip in dryland collapses to one dateline; in the unavailable state cells show names only with one quiet line (GD-7, GD-8)
- the og image is a consented club photo with the hero's navy scrim and the mint logo lockup bottom-left, 1200x630, no other text (GD-25)
- the 404 page has one display heading (GD-24)
- masthead facts pair a short value (number or name) with a noun label (GD-32)
