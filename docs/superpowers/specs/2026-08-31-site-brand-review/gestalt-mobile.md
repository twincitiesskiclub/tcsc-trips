# gestalt: mobile

1. current feel: on a phone the site reads as a serious, quiet club with one genuinely great first screen and a lot of careful ledger work below it. it does not yet read as one voice: the label system is five registers deep, the type scale drifts page to page, and half the pages end without a hand extended.
2. furthest from the brand: coaches (a soft, upscaled first portrait under a masthead of filler stats), the community photo wall on mobile (22 identical squares with no heading, the longest uninterrupted scroll on the site), and the trips and wax room empty states (four words on a paper page, today's production).
3. best executed, protect these: the home fold (nav, trail report, photo, one CTA, all inside one phone screen), the extra training fun page (masthead, navy invitation band, captioned photos, ledger of annuals: the inner-page template at its best), and the 404 (voice, photo band, ruled destinations).
4. the one systemic change: collapse the label registers and pin the mobile type scale. today one home scroll carries fourteen tracked uppercase labels in four different roles at 10, 11 and 13px, and the inner-page H2 renders at the same 36px as the H1. one seam device, sentence-case captions everywhere else, nothing under 12px, H1 40 / H2 28 / H3 22 / body 17 / caption 14. everything else on this list gets easier once that lands.
5. home fold verdict: keep with changes. i agree with july, it is the strongest screen on the site at 390 wide; the 768 capture still puts "twin cities" across a member's face, the CTA pops in before the photo, and the coming-soon dates line is 12px at 60% on a photograph.

## per surface

### home fold, open (home-hero-mobile.png, home-open-mobile.png)
1. a real winter evening: two skiers grinning under snow-loaded trees, the club name in mint, one button, and the trail report above it like a weather station. it feels like a club, not a template.
2. n/a, first surface. it sets the thread: navy vessel, photo as the light, mint as the reading color, coral as the pulse.
3. finish the choreography. the photo and headline fade in but the button is already sitting alone in an empty navy box at frame zero; add the CTA to the same 250ms rise at a 200ms delay and the entrance is one gesture.
4. hero H1 is 36px against a contract of 48px, which is why the name reads slightly timid next to the 24px temperature above it. the strip's "THEO" label is 10px. faces are clear at 390 but not at 768 (see tablet).

### home fold, tablet (home-hero-tablet.png)
1. the same composition, but the woman at the left edge is now looking out from behind "twin cities".
2. same brand, broken promise: july's rule was faces clear at 390, 768 and 1440.
3. a tablet-only focal shift so she leaves the frame or the text block sits under the snow instead of under her.
4. the object position has a max-md value and a default; there is no md-to-lg value, so 768 gets the desktop crop in a portrait frame.

### home, coming soon (home-soon-mobile.png)
1. the same fold with a smaller, quieter button and a whisper of dates under it.
2. same brand. the button label "fall registration dates" is honest but the dates it promises are already printed 12px below it.
3. let the button do one job: either the label is "how to register" and points at tcsc.ski, or the dates line is dropped and the button scrolls to the strip. not both.
4. the dates line is 12px at 60% opacity on a photograph; it is the least legible text on the page in the state where it matters most.

### home, closed (home-closed-mobile.png)
1. honest and calm: "how to register" and a strip subhead that says registration is closed.
2. same brand.
3. the season cards. in closed state they say "2026 registration: returning members jul 2 · new members jul 17" in muted type, which reads as a schedule for a window that already shut.
4. nothing else; the closed state is the most consistent of the three.

### home, dryland (home-dryland-mobile.png)
1. "dryland season" with the coral line "trail reports come back with the snow": the site's best sentence of voice, and it is in the data strip.
2. same brand, better than most.
3. nothing. protect this copy.
4. the strip loses 100px of height in this state so the hero moves up; fine, nothing shifts after load.

### home, unavailable (home-unavailable-mobile.png)
1. a small grey "THEO / no report" under a coral "conditions unavailable". intentional, not broken, as the contract asks.
2. same brand.
3. drop the venue name when there is no report; "no report" under a grey "THEO" reads like a form with a blank field.
4. the grey label is the same 10px eyebrow at lower opacity, the smallest text on the site.

### home, mission panel (home-open-mobile.png, slice 01)
1. the page turns to paper and shouts the mission in eleven lines of the wide display face, then lists three facts as tiny green eyebrows under navy numbers.
2. the thread holds by color and breaks by voice. the about page sets its lede in archivo semibold at 20px; the home sets the same kind of paragraph in polysans bulkywide at 24px. two ledes, two voices.
3. set the mission in archivo semibold text-xl leading-snug, exactly like the about lede, and let the display cut stay with headings. the panel instantly calms and the numbers below it get their weight back.
4. on mobile the stat stack loses its hairline and floats as three orphaned pairs. "SKIERS AT THE 2026 BIRKIE" is an 11px label under a 24px number; a sponsor on a phone will squint.

### home, seasons (slices 01 to 03)
1. a well-built ledger: date range, name, fee in mint, one honest sentence, three labeled lines. it scans.
2. same brand, but the labels double the eyebrow count on the page: SEASONS, then WHEN WHERE TRIPS twice.
3. keep the seam, make the dl labels sentence-case slate at 14px. "When" in slate is calmer and reads faster than "WHEN" in mint tracking.
4. the season names are paper and 24px while "beyond practice" below is paper and 30px and "come ski with us." is mint and 30px: three H2 treatments in one scroll. after the dues line there is 150px of empty navy before the next seam.

### home, beyond practice mosaic and lightbox (slices 03, 04, home-lightbox-mobile.png)
1. the strongest stretch of the page after the fold: nine flush photos, a lead tile, faces everywhere. it is the community, not a picture of one.
2. same brand.
3. the lightbox. it dims the page to 95% so "beyond practice" ghosts through above the photo, and the arrows sit in two bordered pills. make the overlay opaque navy-deep, pin the caption under the image, and let the arrows be bare glyphs at 44px.
4. "see what members do" is a 20px-tall link. the lightbox close and arrows are the only place on the site the arrow glyph appears outside the hero CTA; fine as icons, but the pill borders read default.

### home, wax room feed (populated build; code, home-wax-feed-mobile.png)
1. from the code: a paper band with a bare hairline seam, "from the wax room", and dated log lines. in the populated capture the band is not visible; the screenshot shows only the CTA strip and footer.
2. by design it is the ledger voice again, on paper. it would be the second paper band in a row once the sponsors strip follows it.
3. give it the numbered seam ("wax room") instead of an unlabeled rule, and merge it with the sponsors band into one paper chapter so the page is navy, paper, navy, paper, navy.
4. the harness could not surface it (the section is absent from the mobile capture). the date and author sit in 12px slate; the lede rides inline after the title in a second font, a lot of registers for one line.

### home, sponsors strip (slice 04)
1. a slim paper band with two logos and an underlined link, wedged between the photo wall and a coral-topped navy strip.
2. this is where the thread thins. it is the only place on the home that feels added rather than composed: seam, logos of different visual weight, a link, then navy again.
3. make it a chapter, not a strip. one paper band that opens with the wax room seam and closes with "our sponsors", so the paper appearance earns its height; on mobile put the two logos on one row at max-h-10 and the link under them.
4. "about our sponsors" is 20px tall. the kwik trip block is the one saturated red on the page; it will always be there, so the band around it should be the quietest thing on the page.

### home, cta strip and footer (slice 05, 06)
1. "come ski with us." in mint, a full-width mint button, then a long navy footer that breathes. this is the right ending.
2. same brand.
3. tighten the footer's mobile stack: the wordmark is a 13px uppercase display label, the link rows are 44px tall each so the footer is 677px, mostly air.
4. the wordmark eyebrow is a sixth uppercase-tracked register. "all photos by club members." is the best line in the footer and it is at 50% opacity.

### mobile nav panel (home-mobile-nav-mobile.png)
1. a navy sheet with six 24px links centered and the CTA pinned at the bottom. it feels correct and slightly bare, like the panel shipped before the logo did.
2. same brand.
3. put the wordmark top-left, where the nav had it, and the one-line trail report above the CTA. the panel then carries the two things that make this site this site.
4. opening fades in 200ms with an 8px rise; closing is instant, which is a choice and feels fine. the panel has no logo, so for 400ms the visitor is on a page with no name.

### about (about-open-mobile.png, about-closed-mobile.png)
1. a proper inner page: paper, a display H1, a slate lede, two real facts, a full-bleed team photo, prose that reads like a person wrote it, then the seasons ledger on paper.
2. same brand, and the strongest inner masthead because the facts are true facts.
3. end with a hand: about is the page that explains who joins and it has no registration strip. add the CTAStrip after seasons in all three states.
4. "Seasons" renders at 36px, the same size as the H1. there is 120px of paper between the golden-hour photo and that heading. the compact strip's "THEO" link is 32 by 11px. the closed-state card note repeats past dates.

### community (community-default-mobile.png)
1. a warm page that runs too long: masthead, canoe photo, a 2x2 cluster, four ledger groups with anchor photos, then eleven rows of identical squares with no heading.
2. same brand for the first two thirds. the photo wall breaks the thread on mobile: on desktop it is an asymmetric mosaic, on a phone every span class is md: so it degrades to a camera roll.
3. give the mobile wall rhythm and a name: every fourth tile spans both columns at 3:2, and the section opens with the seam and a heading ("the whole album" or similar) so the wall is a chapter, not an overflow.
4. "photos by club members / CREDITS" is a masthead stat that is not a fact about the page. the fire-danger solo and the empty-trail landscape july cut from the home still sit in the wall between group shots.

### racing (racing-default-mobile.png)
1. prose, a clean race ledger with mint-deep date eyebrows, then five portrait photos in a 2-col grid with an empty grey sixth cell.
2. same brand until the strip; the empty cell reads as a photo that failed to load.
3. let the first strip photo span both columns at 3:2 on mobile so five photos fill 1+4 with no hole.
4. the dates are uppercase tracked in mint-deep (a seventh register). "always voluntary / RACING" is filler in the stat slot. the page has no closer.

### dry tri (dry-tri-default-mobile.png)
1. the club's own race presented like a program: format, venue, first held, a three-up triptych, the course ledger, the 2025 recap, the 2026 note, two underlined links.
2. same brand. the triptych is the odd note: three 110px-wide portraits inside a bordered box on a page that otherwise has no boxes.
3. run the three legs full-bleed edge to edge with hairline gaps on mobile, exactly like the mosaic, and drop the border.
4. the 9:00 AM and 9:30 AM start times are uppercase tracked mint-deep, the same treatment as the race dates on racing, applied to a time. it ends with "2025 results" as a lone underlined link where a closer belongs.

### extra training fun (extra-training-fun-default-mobile.png)
1. the best inner page on the phone: masthead with one true fact, prose, a navy band of standing invitations with the day in mint, two captioned photos on paper, then the annuals ledger and a line that hands you to the dry tri.
2. same brand, and it shows the inner template working at full strength.
3. close the 100px gap between the masthead rule and "how it works": the prose wrapper padding stacks on the prose h2 margin.
4. the captions "thursday track club, may." are the right voice; nothing else on the page needs fixing. protect it.

### coaches (coaches-default-mobile.png)
1. four tall portraits in a column with names under them. the first one, kj, is visibly soft and pixelated at 342px wide, and it is the first thing on the page.
2. the thread breaks here. a blurry headshot leading the coaching page reads as a broken image to a normal visitor, and the masthead facts ("two seasons a year / COACHING", "tuesday · thursday / PRACTICES") are scaffolding, not facts about coaches.
3. mount the portraits smaller on mobile (a 240px square, left aligned, with the name beside it) so soft sources sit at or above 1x, and drop the filler facts so the masthead collapses to the single-column form.
4. each 4:5 photo is 428px tall so the page is four screens of portrait before the fourth coach. michael's photo shows two other people on balance discs. credentials use a middot as a bullet, which is fine.

### sponsors (sponsors-default-mobile.png)
1. the pitch deck as a page: two large centered logos, a navy "sponsor impact" band with a photo and a mint ledger, a paper "partner recognition" band with the bear photo, "what continued support makes possible", a disclaimer, a coral-topped CTA.
2. same brand; the sponsor scene from the theme is served. two things drift: the logos are centered on a left-aligned page, and "sponsor support helped tcsc..." trails an ellipsis into a heading.
3. left-align the logo wall on mobile and cap kwik trip at max-h-16 so the red block does not outweigh the club's own headline.
4. the navy band uses mint for both the H2 and the ledger H3s, so the hierarchy inside it is carried by size alone. three seams on one page (sponsor impact, partner recognition, plus the footer wordmark).

### trips, empty and populated (trips-empty-mobile.png, trips-populated-mobile.png)
1. empty: a masthead, one sentence, a hairline, the footer. populated: a masthead, one ruled row, the footer. both feel like a page that is waiting for someone.
2. same brand in materials, thin in presence. the empty state is what production shows today.
3. give the empty state the ledger voice: three ruled rows for the usual calendar (sisu, january; birkie, february; great bear chase, march, all verified dates on the racing page) with "dates and signup posted each fall" as the note, so the page has a shape before it has trips.
4. the column header row is hidden on mobile so the populated row loses its "dates / trip / where" grammar. the empty copy ends in a semicolon clause and an underlined mailto.

### wax room, empty and populated (wax-room-empty-mobile.png, wax-room-populated-mobile.png)
1. "no entries yet." on a paper page. four words, then the footer.
2. same materials; the voice from the dryland strip is missing. a club that writes "trail reports come back with the snow" can write a better empty line.
3. "first field reports land with the first snow. until then the trail report above is the wax room." plus the dryland line's logic: the page should point at the strip.
4. populated: the entry list is fine but the date is "sunday, november 22, 2026" in full, then "by coach fixture · coach", two lines of meta for one title.

### wax entry (wax-entry-default-mobile.png)
1. a readable field report with a good headline, one photo, and a grey rounded box holding location, temp and wax used.
2. the box breaks the contract's "no soft-tinted gray cards on paper" rule, and it is the only rounded slab on the site.
3. set the snapshot as a ruled dl: border-y border-ink/15, three columns, sentence-case slate labels, ink values. same information, ledger voice.
4. the H1 is 30px here and 36px on every other inner page. the closing line "this entry is a fixture" is harness copy, not a finding.

### 404 (404-default-mobile.png)
1. "this trail ends here." over a groomed-trail photo, then "choose another page." with a navy button and three ruled destinations. it has more voice than most real pages.
2. same brand.
3. nothing structural. it is slightly over-built (two display headings and an eyebrow for a 404) but the excess is charm, not slop.
4. "helpful destinations" is a 14px semibold h2 that reads like a form label. the navy-on-paper button is the on-paper CTA variant and is consistent.

### og image (site/public/og/og-default.jpg)
1. a sunset group shot at 1200x630: twenty skiers, a magenta sky, arms out. it is exactly the photo tracksmith would run.
2. same brand in photograph; no brand in mark. shared into slack or imessage the card shows a photo and a domain, no wordmark.
3. add the paper wordmark small at bottom-left over the hero's functional bottom scrim (from-navy/95 to transparent at 35%). one image, one crop, still a photograph first.
4. the front row's faces sit in the bottom 25%, which square and 4:5 previews crop. the sky fights coral if coral ever lands on the card.

## findings

### GM-1
- surface: home / hero / tablet
- kind: drift
- severity: P1
- contract: "Real candid photo ... Headline set in mint over a navy-gradient bottom-vignette for legibility" plus the july rule "no face sits under the bottom text block at ~390px, ~768px, ~1440px"
- evidence: site/src/components/HeroHome.astro:47 (`object-[center_15%] max-md:object-[60%_15%]`), home-hero-tablet.png
- observation: at 768 the member at the left edge is directly under "twin cities". the crop has a max-md value and a desktop default and nothing between.
- proposal: add a tablet band, `md:max-lg:object-[72%_15%]`, and verify at 768 and 834; keep 390 and 1440 as they are.
- workstream: sections

### GM-2
- surface: home / hero / mobile
- kind: elevation
- severity: P3
- contract: "The headline appears at 200ms with a 4px upward translation. Single orchestrated entrance per session"
- evidence: site/src/components/HeroHome.astro:100-106, live frame hero-entrance-0 (button alone in empty navy)
- observation: the photo and headline animate; the CTA does not, so at frame zero the button sits alone in a blank navy box before the photograph arrives.
- proposal: give the CTA wrapper the `hero-headline` animation with a 200ms delay so the fold enters as one gesture; reduced-motion collapses it with the rest.
- workstream: motion-components

### GM-3
- surface: home / hero / mobile
- kind: drift
- severity: P2
- contract: "Display H1 (home hero) | 3.0rem mobile"
- evidence: live computed h1 36px; site/src/components/HeroHome.astro:60 (`text-4xl sm:text-5xl md:text-7xl`)
- observation: the club name renders at 36px, only 1.5x the 24px temperature in the strip above it. the fold's name is timid next to its own data.
- proposal: `text-[2.625rem]` (42px) at 390 with leading 0.98; "twin cities" still fits the 342px column in bulkywide.
- workstream: foundations

### GM-4
- surface: home / soon / mobile
- kind: elevation
- severity: P2
- contract: proposed: "the hero CTA never points at content already visible under it; in coming_soon the button reads as a route to registration, the dates line under it carries the dates"
- evidence: home-soon-mobile.png, site/src/components/HeroHome.astro:69-70, site/src/content/pages/home.yaml (cta_coming_soon_label)
- observation: the button says "fall registration dates" and anchors to the strip 4000px down, while the dates are printed 12px beneath it.
- proposal: coming_soon label "how to register" with url tcsc.ski (the closed pair), and the dates line stays; or keep the anchor and drop the dates line. one of the two, not both.
- workstream: copy

### GM-5
- surface: home / soon / mobile
- kind: elevation
- severity: P2
- contract: "Caption / meta | 0.875rem" and "Body text minimum 16px on mobile"
- evidence: site/src/components/HeroHome.astro:70 (`text-xs md:text-sm text-paper/60`)
- observation: the registration dates render at 12px and 60% opacity over a photograph, the least legible text on the site in the state where it matters most.
- proposal: `text-sm text-paper/85`, and sit it on the scrim's heavy zone (it already does).
- workstream: foundations

### GM-6
- surface: home / all / mobile
- kind: drift
- severity: P2
- contract: "Uppercase tracked eyebrow labels as repeating section grammar (banned). One use per page is allowed if it carries information." and "Caption / meta | 0.875rem"
- evidence: home-open-mobile.png (TRAIL REPORT, THEO, FOUNDED, BASED IN, SKIERS AT THE 2026 BIRKIE, SEASONS, WHEN, WHERE, TRIPS x2, OUR SPONSORS, TWIN CITIES SKI CLUB); site/src/components/LiveConditions.astro:38 (10px), MissionPanel.astro:25 (11px), SeasonsGrid.astro:109 (11px), SectionBand.astro:30 (11px), Footer.astro:29 (13px), racing.astro:57, dry-tri.astro:66
- observation: one home scroll carries fourteen tracked uppercase labels in five roles (strip eyebrow, venue name, stat label, dl label, section seam, footer wordmark) at 10 to 13px. the seam device is good; the rest dilute it.
- proposal: reserve tracked uppercase for exactly two devices, the section seam (SectionBand, mosaic, wax feed) and the trail report eyebrow. stat labels, dl labels, race dates, course times and column headers become sentence-case slate (mint-deep on paper only for links), `text-sm` (14px), no tracking. venue names in the strip become `text-xs` (12px) paper/70. footer wordmark becomes the logo svg at 22px.
- workstream: foundations

### GM-7
- surface: all / all / mobile
- kind: drift
- severity: P2
- contract: "Display H1 (inner pages) 2.5rem mobile; H2 2.0rem; H3 1.375rem"
- evidence: live computed: inner H1 36px (HeroInner.astro:30 `text-4xl`), SectionBand H2 36px (SectionBand.astro:38 `text-4xl`), mosaic H2 30px (PhotoMosaic.astro:132), CTAStrip H2 30px (CTAStrip.astro:61), SeasonsGrid H2 24px (SeasonsGrid.astro:91), WaxEntry H1 30px (WaxEntry.astro:55), CoachEntry H2 30px, racing "Races" 30px (racing.astro:51), about-open-mobile.png slice 02 ("Seasons" as large as the H1)
- observation: on a phone the section H2 renders at the same 36px as the page H1, and H2s elsewhere on the same page run 24, 30 or 36. the hierarchy is carried by position, not size.
- proposal: one mobile scale in global.css utilities and used everywhere: H1 `text-[2.5rem]/[1.02]`, H2 `text-[1.75rem]/[1.08]`, H3 `text-[1.375rem]/[1.2]`, body 17px, caption 14px, micro 12px (trail report only). `font-display` on H1 and H2 only; H3 and below in archivo semibold.
- workstream: foundations

### GM-8
- surface: home / mission / mobile
- kind: elevation
- severity: P2
- contract: "The display cut is used at most 2-3 places per page; everything else is the body family."
- evidence: site/src/components/MissionPanel.astro:18 (`font-display text-2xl`), home-open-mobile.png slice 01; site/src/pages/about.astro:39 sets the equivalent lede in `font-semibold text-xl` archivo
- observation: eleven lines of the wide display face on a phone read as shouting, and the about page sets the same kind of lede in archivo semibold. two ledes, two voices.
- proposal: mission paragraph in `font-semibold text-xl md:text-2xl leading-snug text-navy` (the about lede treatment); the display cut stays with headings and the stat values.
- workstream: sections

### GM-9
- surface: home / mission / mobile
- kind: elevation
- severity: P3
- contract: "Stat boxes with big mint numbers (banned)"; the june stat stack is navy numbers on paper, allowed, but loses its rule on mobile
- evidence: site/src/components/MissionPanel.astro:19 (`md:border-l md:border-ink/15 md:pl-7`)
- observation: under md the vertical hairline disappears and the three facts float as orphan pairs under the paragraph.
- proposal: on mobile render the facts as one ruled row: `border-t border-ink/15 pt-6 grid grid-cols-3 gap-4`, value 20px display, label 14px slate sentence case.
- workstream: sections

### GM-10
- surface: home / all / mobile
- kind: drift
- severity: P2
- contract: "On navy: primary reading color for headings ... mint"
- evidence: PhotoMosaic.astro:132 (`text-paper`), SeasonsGrid.astro:91 (inherits paper), CTAStrip.astro:61 (`text-mint`), sponsors.astro navy band H2 mint (sponsors-default-mobile.png slice 01)
- observation: on navy, "beyond practice" and the season names are paper, "come ski with us." and the sponsor band H2 are mint. two heading colors on one surface.
- proposal: H2 on navy is paper; mint display is reserved for the home H1 and the CTAStrip heading (two mint moments per page). the sponsors band H2 goes paper, its ledger H3s stay mint as the accent.
- workstream: foundations

### GM-11
- surface: home / seasons / mobile
- kind: elevation
- severity: P3
- contract: "sections breathe variably (96-144px y-padding on home)"
- evidence: home-open-mobile.png slice 03 (150 css px of empty navy between the dues line and the next seam); SectionBand.astro:22 (`pb-20 md:pb-28`) plus PhotoMosaic.astro:125 (`pt-12`)
- observation: the dues paragraph is followed by the largest empty gap on the page before the "beyond practice" seam; it reads as a missing section.
- proposal: `pb-12` on the seasons band on mobile (keep md:pb-28) so the seam arrives within one screen of the dues line.
- workstream: sections

### GM-12
- surface: home / lightbox / mobile
- kind: elevation
- severity: P3
- contract: "Lightbox open: 200ms scale-in with opacity. Lightbox navigation: hard-cut."
- evidence: site/src/components/Lightbox.astro:13 (`bg-ink/95`), :31-32 (bordered arrow pills), home-lightbox-mobile.png ("beyond practice" ghosting above the photo)
- observation: the 95% overlay lets the page heading ghost through above the image; the prev/next arrows sit in bordered pills that read default.
- proposal: `bg-navy-deep` opaque; caption directly under the image (`mt-3`); arrows as bare 28px glyphs in 44x44 hit areas with no border; keep hard-cut navigation.
- workstream: motion-components

### GM-13
- surface: home / mobile-nav / mobile
- kind: elevation
- severity: P2
- contract: "<MobileNavPanel> ... Navy panel, 24px links, Join CTA pinned bottom. Live conditions strip pinned to the top of the panel."
- evidence: site/src/components/MobileNavPanel.astro:14-33, home-mobile-nav-mobile.png
- observation: the panel has no wordmark and no trail report; for as long as it is open the visitor is on a page with no name.
- proposal: render the nav's logo svg top-left of the panel (same 145x22), and the compact trail report line (Theo only) above the CTA. no new js: the compact markup is server-rendered and the client already fills `[data-location]` by id, so mount the compact variant markup inside the panel only if the announcer's single-mount rule is relaxed; otherwise a static "trail report" link to the strip.
- workstream: sections

### GM-14
- surface: about / all / mobile
- kind: elevation
- severity: P2
- contract: "<CTAStrip> ... Used at the bottom of most pages."
- evidence: site/src/pages/about.astro:51-53 (page ends with the seasons band), about-open-mobile.png slice 03-04
- observation: the page that explains who joins ends without a registration strip in any of the three states.
- proposal: mount `CTAStrip` after the seasons band on /about with the same state props as the home strip.
- workstream: sections

### GM-15
- surface: home, about / closed / mobile
- kind: elevation
- severity: P2
- contract: proposed: "a closed season card says it is closed and when it reopens; it never lists a past window as a schedule"
- evidence: site/src/components/SeasonsGrid.astro:40-50 and site/src/lib/registrationCopy.ts:64-70, home-closed-mobile.png slice 02 ("2026 registration: returning members jul 2 · new members jul 17" muted)
- observation: in the closed state the card note prints the dates of the window that already shut, in the same sentence shape as the open note.
- proposal: when `deriveRegistrationState` is closed, fall back to `entry.data.registration_note` (the june copy, "closed for 2026 · reopens apr/may") instead of `cardNote`.
- workstream: copy

### GM-16
- surface: all / all / mobile
- kind: drift
- severity: P2
- contract: "All interactive elements >=44x44px on mobile."
- evidence: live measurement: compact strip "Theo" link 32x11 (LiveConditions.astro:88), "see what members do" 142x20 (PhotoMosaic.astro:135), "about our sponsors" 137x20 (index.astro:113)
- observation: three links on the home and every inner page are 11 to 20px tall.
- proposal: `inline-flex min-h-11 items-center -my-2` on the venue link (keeps the strip height), and `inline-flex min-h-11 items-center` on the two section links.
- workstream: motion-components

### GM-17
- surface: home / sponsors strip / mobile
- kind: elevation
- severity: P2
- contract: "Home page is drenched navy from nav to footer. Photographs ... are the only paper appearances" and "The home page has no card grid at all."
- evidence: site/src/pages/index.astro:107-117, site/src/components/WaxRoomFeed.astro:22, home-open-mobile.png slice 04 (197px paper strip between the photo wall and the coral-topped CTA)
- observation: the home now has up to three paper bands (mission, wax feed, sponsors). the sponsors strip is the thinnest and reads as an add-on; when the wax feed renders the two paper bands abut with two seams.
- proposal: one paper chapter after the mosaic: it opens with the "wax room" seam and log lines (when entries exist) and closes with the "our sponsors" seam, logos on one row at max-h-10 left-aligned, link under them. the home is then navy, paper, navy, paper, navy and the contract's paper rule is rewritten to name those two moments.
- workstream: sections

### GM-18
- surface: community / default / mobile
- kind: elevation
- severity: P2
- contract: "<PhotoMosaic> ... 4-col desktop / 2-col mobile. Mix of 1x1, 2x1, 2x2 tiles."
- evidence: site/src/components/PhotoMosaic.astro:63-72 (every span class is `md:`), community-default-mobile.png slices 06-09 (22 identical squares, no heading)
- observation: on a phone the wall has no rhythm and no name: 11 rows of uniform squares, about 2150px of scroll, starting from an unlabeled navy gap.
- proposal: mobile spans in the size cycle (`max-md:col-span-2 max-md:aspect-[3/2]` on indexes 1 and 6 of each eight), and pass `number="Community"` with a heading ("the whole album" or the copy lens's choice) from community.astro so the wall opens with the seam device.
- workstream: sections

### GM-19
- surface: about, community, racing, coaches, dry-tri / default / mobile
- kind: slop
- severity: P2
- contract: proposed: "masthead facts are true facts about the page; a page with none renders the single-column masthead"
- evidence: site/src/pages/community.astro:62 ("photos by club members / credits"), racing.astro:38 ("always voluntary / racing"), coaches.astro:23-24 ("two seasons a year / coaching", "tuesday · thursday / practices"); visual-redesign's "slop: filler that exists because the layout has a slot"
- observation: the stat slot demanded content, so labels were invented to fill it. about (501(c)(3), based in), racing (80+), dry tri (format, venue, first held) and etf (2022) are real; the rest are scaffolding.
- proposal: drop the four filler facts. coaches and community render the single-column masthead HeroInner already supports.
- workstream: copy

### GM-20
- surface: coaches / default / mobile
- kind: elevation
- severity: P1
- contract: "Astro image pipeline generates responsive srcset ... No stock photography." and CoachEntry.astro:7-11 ("KJ's is visibly soft at full size ... at ~460px CSS reads sharp")
- evidence: coaches-default-mobile.png slice 00 (first portrait pixelated at 342 css px, 684 device px), site/src/components/CoachEntry.astro:56-74
- observation: the first thing on the coaching page is a soft, upscaled headshot. a visitor reads it as a broken image, not a soft one.
- proposal: on mobile mount the portrait at `max-w-60 aspect-square` (240px, 480 device px) beside the name in a 2-col row (`grid-cols-[15rem_1fr]` collapsing to stacked under 360), so modest sources stay at or above 1x; the desktop mount is unchanged. if a sharper consented photo of kj exists in the pool, prefer it (rob's call, per july).
- workstream: sections

### GM-21
- surface: racing / default / mobile
- kind: elevation
- severity: P2
- contract: proposed: "photo strips never leave an empty cell; odd counts get a spanning lead tile"
- evidence: site/src/pages/racing.astro:73-85 (`grid-cols-2 md:grid-cols-5` with five photos), racing-default-mobile.png slice 03 (grey sixth cell)
- observation: five 3:4 photos in a 2-col grid leave an empty tinted cell that reads as a failed image.
- proposal: `max-md:[&>*:first-child]:col-span-2 max-md:[&>*:first-child]:aspect-[3/2]` so the strip fills 1+4.
- workstream: sections

### GM-22
- surface: dry-tri / default / mobile
- kind: elevation
- severity: P2
- contract: "No nested cards. Ever." and the mosaic's full-bleed grammar
- evidence: site/src/pages/dry-tri.astro:36 (`grid grid-cols-3 gap-px bg-ink/10 border border-ink/10` inside a padded container), dry-tri-default-mobile.png slice 00
- observation: three 110px-wide portraits in a bordered box; the only framed element on an otherwise unframed site.
- proposal: on mobile run the triptych full-bleed (drop the container padding and border, keep the hairline gaps) at `aspect-[4/5]`, or stack as 1+2 with the roll leg at `col-span-3 aspect-[3/2]`.
- workstream: sections

### GM-23
- surface: extra-training-fun / default / mobile
- kind: elevation
- severity: P3
- contract: "sections breathe variably (64-104px on inner)"
- evidence: extra-training-fun-default-mobile.png slice 00 (masthead rule, then ~100 css px of paper before "how it works"), InnerPageLayout content wrapper `py-12` plus prose h2 top margin
- observation: the first prose element is an h2, so wrapper padding and prose margin stack into the largest gap on the page.
- proposal: `[&>h2:first-child]:mt-0` on the prose wrapper (all inner pages), and `pt-8` on the wrapper when the masthead has no photo band.
- workstream: sections

### GM-24
- surface: sponsors / default / mobile
- kind: elevation
- severity: P2
- contract: "Sponsor display: Logo wall on /sponsors. Tiered headings; logos sized by tier. Not tiles."
- evidence: site/src/components/SponsorWall.astro:68-73 (`items-center ... justify-center` under sm), sponsors-default-mobile.png slice 00
- observation: the logos are centered on a page where every other element is left-aligned, and the kwik trip block at 96px tall is the heaviest object on the page.
- proposal: `items-start justify-start` at every width; trailblazer logos `max-h-16` on mobile; `max-h-24` from sm.
- workstream: sections

### GM-25
- surface: sponsors / default / mobile
- kind: elevation
- severity: P3
- contract: the july copy rules, plain register
- evidence: sponsors-default-mobile.png slice 01 ("sponsor support helped tcsc...")
- observation: a display heading trailing an ellipsis into its own list.
- proposal: "what sponsor support paid for" as the heading; the ledger below carries the list.
- workstream: copy

### GM-26
- surface: trips / empty / mobile
- kind: elevation
- severity: P2
- contract: proposed: "empty states on trips and the wax room carry the page's shape: a ruled ledger of what usually happens, in the club voice"
- evidence: site/src/components/TripsTable.astro:21-26, trips-empty-mobile.png (one sentence, one hairline, footer)
- observation: production today: a masthead, one sentence, a rule, the footer. the page has no shape until someone posts a trip.
- proposal: render three ruled rows from static data when the collection is empty: "january · sisu ski fest · ironwood, mi", "february · american birkebeiner · hayward, wi", "march · great bear chase · calumet, mi" (dates already verified on /racing), with the note "signup for each trip is posted here in the fall". the column header row also shows on mobile as a single ruled line.
- workstream: sections

### GM-27
- surface: wax-room / empty / mobile
- kind: elevation
- severity: P2
- contract: proposed (same clause as GM-26)
- evidence: site/src/pages/wax-room/index.astro:20 ("No entries yet."), wax-room-empty-mobile.png
- observation: four words on a paper page, then the footer. the dryland strip proves the site has a voice for waiting.
- proposal: "first field reports land with the first snow. until then, the trail report above is the wax room." set as the lede, plus a ruled row "what lands here: conditions, wax notes, race-day prep, technique."
- workstream: copy

### GM-28
- surface: wax-entry / default / mobile
- kind: drift
- severity: P2
- contract: "Soft-tinted gray cards on paper (banned). If a card needs definition, give it a 1px ink-15% rule"
- evidence: site/src/components/WaxEntry.astro:62 (`bg-paper-card p-4 rounded-md`), wax-entry-default-mobile.png slice 00
- observation: the conditions snapshot is the one rounded grey slab on the site.
- proposal: `<dl class="mt-6 border-y border-ink/15 py-4 grid grid-cols-3 gap-4 text-sm">`, labels sentence-case slate, values ink; no background, no radius.
- workstream: motion-components

### GM-29
- surface: home / open / mobile
- kind: elevation
- severity: P3
- contract: "<Footer> ... Three columns: contact, navigation, social. Live conditions strip at the top (compact form)."
- evidence: site/src/components/Footer.astro:26-49, home-open-mobile.png slice 05 (677 css px footer)
- observation: the footer's mobile stack is mostly air: 44px rows, a 13px uppercase wordmark, credits at 50% opacity. the compact strip the contract puts here lives under the nav instead, which is the better place.
- proposal: wordmark as the logo svg at 22px; link rows `min-h-10` with `gap-y-0`; "all photos by club members." at paper/70 since it is the line worth reading. contract updated to say the compact strip lives under the nav on inner pages, not in the footer.
- workstream: sections

### GM-30
- surface: OG image / default / all
- kind: elevation
- severity: P3
- contract: proposed: "the og image is a real club photograph with the paper wordmark small at bottom-left over a functional bottom scrim; faces stay inside the center 60% so square crops keep them"
- evidence: site/public/og/og-default.jpg
- observation: a strong sunset group photo with no mark; shared as a link card it shows a photo and a domain. the front row's faces sit in the bottom quarter.
- proposal: keep the photo; add a from-navy/90 bottom scrim to 30% and the paper logo svg at 220px wide, 48px from the left and bottom edges. one asset, generated once, no gemini needed.
- workstream: sections

### GM-31
- surface: home / open / mobile
- kind: drift
- severity: P2
- contract: "Caption / meta | 0.875rem" and "Body text minimum 16px on mobile"
- evidence: site/src/components/LiveConditions.astro:36 (`text-[11px]`), :38 (`text-[10px]`), :41 (`text-[11px]`), :47 (`text-xs`), MissionPanel.astro:25, HeroInner.astro:38, SectionBand.astro:30, Footer.astro:29
- observation: the strip runs 10, 11, 12 and 24px in four lines; 10px is the smallest text on the site and it labels the club's home venue.
- proposal: micro floor 12px (`text-xs`) for the strip's labels and meta; 14px (`text-sm`) for every caption and label outside the strip. no `text-[10px]` or `text-[11px]` anywhere.
- workstream: foundations

### GM-32
- surface: home / wax-feed / mobile
- kind: elevation
- severity: P3
- contract: "<WaxRoomFeed> ... three most recent wax room entries with date, title, one-line excerpt"
- evidence: site/src/components/WaxRoomFeed.astro:26-28 (unlabeled hairline seam), :41-48 (12px meta, inline lede in a second face)
- observation: the feed uses a bare rule where every other band uses a labeled seam, and packs date, author, title and lede into one line with three type registers.
- proposal: seam label "wax room"; entry as two lines, title (display 20px) then "nov 22 · coach fixture · 18°f at theodore wirth" in 14px slate; the lede only on md+. note for the harness: the populated mobile capture does not show this band; recapture after the fix.
- workstream: sections

## proposed contract changes

- label registers: tracked uppercase is reserved for the section seam and the trail report eyebrow; every other label is sentence-case caption text (GM-6, GM-31)
- mobile type scale pinned: H1 40 / H2 28 / H3 22 / body 17 / caption 14 / micro 12 (strip only); font-display on H1 and H2 only (GM-3, GM-7, GM-8)
- headings on navy are paper; mint display is reserved for the home H1 and the CTAStrip heading (GM-10)
- home paper moments named: the mission panel and one closing paper chapter (wax room feed plus sponsors); no other paper on the home (GM-17, GM-32)
- masthead facts must be true facts about the page; pages without them render the single-column masthead (GM-19)
- photo strips and walls never leave an empty cell; odd counts get a spanning lead tile; the mosaic keeps rhythm on mobile with 2x1 tiles (GM-18, GM-21, GM-22)
- empty states on trips and the wax room carry the page's shape as a ruled ledger in the club voice (GM-26, GM-27)
- a closed season card says it is closed and when it reopens; it never lists a past window as a schedule (GM-15)
- the hero CTA never points at content already visible beneath it; coming_soon label and dates line are one device, not two (GM-4, GM-5)
- the compact trail report lives under the nav on inner pages and inside the mobile nav panel; the footer carries no strip (GM-13, GM-29)
- the home entrance choreographs photo, headline and CTA as one gesture; the lightbox overlay is opaque navy-deep (GM-2, GM-12)
- og image clause added: real photograph, paper wordmark bottom-left over a functional scrim, faces inside the center 60% (GM-30)
- every page that explains joining ends with the CTAStrip (GM-14)
- mobile tap targets are 44px on every link, including inline section links and the strip's venue link (GM-16)
