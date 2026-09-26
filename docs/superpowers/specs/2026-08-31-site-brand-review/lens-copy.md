# lens: copy

1. the home mission paragraph, the largest block of text on the site, uses "dedicated to fostering", "promoting a healthy lifestyle", and "educational programming", the exact nonprofit abstractions the july 18 voice rules banned; the copy refresh never touched it.
2. the sponsors page was never voice-passed: sixteen uses of "team" on a site that says "club" everywhere else, a deck-style heading that trails off in an ellipsis, and grant-report verbs ("strengthens the shared resources", "flexibility to invest where it can have the most impact") on the one page written for the sponsor scene.
3. the registration copy contradicts itself and the calendar: the coming-soon label is hardcoded to "fall" while the state is derived per season, the same opening dates render in three formats on one page, and the closed-state season card shows past opening dates as if they were a schedule.
4. biggest opportunity: make registrationCopy.ts state-aware (open, coming soon, closed each get one honest card note and strip subhead, and one date format), then rewrite the mission paragraph and the sponsors page in the racing and extra-training-fun register, which is already the best writing on the site.
5. overall: the pages the july refresh touched (about, community, coaches, extra training fun, dry tri, racing) read like a member talking; the pages it skipped (home mission, sponsors, 404, empty states, the registration helpers) still read like a template, and the seams between them show in spelling, separators, and fact formats.

swept with no copy finding: og image (1200x630, real club photo, no text; og:title and og:description inherit the page title and meta description, which are covered below), mobile nav panel labels ("Open menu", "Close menu", "Menu"), skip link, lightbox live region, live-conditions wax labels (api-authored), dry tri course ledger, extra training fun fixtures and annuals, coach photo alt text (all four are specific and accurate), community takeaways ledger.

## findings

### CP-1
- surface: home, about, every inner page / coming soon / all
- kind: drift
- severity: P1
- contract: DESIGN.md Components, Nav: "Primary CTA reads `registration_state`." proposed: "registration labels never name a season; the season is derived, so the label must be true for fall/winter and spring/summer alike."
- evidence: site/src/content/pages/home.yaml:8 (`cta_coming_soon_label: Fall registration dates`); site/src/components/registrationCta.ts:36-40 (primary season is whichever window is soonest ahead, either type); home-soon-desktop.png, home-soon-mobile.png
- observation: the coming-soon button reads "Fall registration dates" in the nav, mobile panel, and hero. the state comes from `season.primary`, which in march or april is spring/summer. a spring visitor will see a button promising fall dates for a summer season.
- proposal: `cta_coming_soon_label: Registration dates`. five characters shorter, true in both seasons, still a noun phrase that matches "How to register" and "Register for the season" in register. no url change.
- workstream: copy

### CP-2
- surface: home / all states / all
- kind: drift
- severity: P1
- contract: proposed: "site copy follows the 2026-07-18 voice rules: concrete activities over values, direct verbs, no nonprofit abstractions (fostering, promoting, providing), no slogan structures, no invented facts."
- evidence: site/src/content/pages/home.yaml:12-16; site/src/components/MissionPanel.astro:18 (rendered at display 2xl/3xl); home-open-desktop.png (the paper panel under the hero)
- observation: "Twin Cities Ski Club is a 501(c)(3) nonprofit dedicated to fostering a supportive community for young adults (ages 21-35) by promoting a healthy lifestyle through cross-country ski training sessions and educational programming." this is the biggest type on the page after the H1 and it contains both verbs the voice rules name as banned. the july refresh replaced the about page equivalents but left this one, probably because it reads as the filed mission statement.
- proposal: `mission_paragraph: Twin Cities Ski Club is a 501(c)(3) nonprofit. Cross-country skiers ages 21-35 train together year-round at coached practices twice a week, race when they want to, and stick around after.` every fact is already on the site (about, seasons, racing). if the current text is the legally filed mission and must stay verbatim, move it to the about page body as a quoted line and use the plain sentence on home. rob decides which.
- workstream: copy

### CP-3
- surface: sponsors / default / all
- kind: drift
- severity: P1
- contract: proposed: voice rules clause (see CP-2). DESIGN.md Theme: "a sponsor opening it the next morning on a 27-inch monitor ... in a tab next to three other club sites."
- evidence: site/src/content/pages/sponsors_page.yaml:2-52; sponsors-default-desktop.png
- observation: the one page written for the sponsor scene is the one page the copy refresh did not reach. "Support from our sponsors strengthens the shared resources behind training, team waxing, travel, and race support while helping TCSC keep participation costs in reach." "Recent investments strengthened everyday team activities as well as travel." "As the team grows, sponsor support gives TCSC flexibility to invest where it can have the most impact." the heading "Sponsor support helped TCSC..." trails into an ellipsis so the three items complete the sentence, a slide-deck device. "Interested in supporting TCSC?" is a question headline. the concrete facts underneath (two wax drills, rental vans to the Prebirkie and Great Bear Chase, a tent and start-area parking at the Birkie, six jackets, PFAS-free wax) are good and are buried.
- proposal: replacement set, facts unchanged, no new claims:
  - intro: `Our sponsors pay for the wax, vans, and race-day gear that every member shares, racer or not, and keep dues within reach.`
  - impact_heading: `What sponsor money paid for`
  - impact_intro: `Everything here is shared by racers and non-racers alike.`
  - impact items: `Team wax sessions` / `Two wax drills and a shared wax supply, open to every member.`; `Vans to races` / `Rental vans carried food, gear, and supplies to the Prebirkie and the Great Bear Chase, so volunteer trip leaders had less to haul.`; `A base at the Birkie` / `A team tent and start-area parking: a place to wax, warm up, test skis, and cheer.`
  - recognition_heading: `Sponsor logos at the races`; recognition_body: `Six club jackets carry sponsor logos at races and in podium photos.`; caption unchanged.
  - priorities_heading: `What comes next`; priorities_intro: `Where the next sponsor dollars go.`
  - priority items: `PFAS-free wax` / `Replace the club's shared wax with PFAS-free products.`; `More coaches, more gym space` / `Add coaches and book larger training spaces as the club grows.`; `Shared gear` / `Equipment that lowers the cost of a first season.`
  - contact_heading: `Sponsor TCSC`; contact_body: `Email club leadership about sponsorship and what the club needs this season.`; cta label unchanged.
  - disclosure: `Sponsor recognition is thanks, not an endorsement of a sponsor's products or services.`
- workstream: copy

### CP-4
- surface: sponsors / default / all
- kind: drift
- severity: P2
- contract: proposed: "the organization is 'the club' and its people are 'members' in every string; 'team' is reserved for race-day contexts (team trip, team wax, team jacket)."
- evidence: site/src/content/pages/sponsors_page.yaml (16 occurrences of "team", 2 of "club"); compare site/src/content/pages/community.mdoc:22 ("Members run the club"), site/src/components/Footer.astro:31, site/src/components/TripsTable.astro:23
- observation: every other page calls TCSC a club. the sponsors page calls it a team sixteen times ("as the team grows", "everyday team activities", "a useful team base"). a sponsor reading two tabs side by side sees two organizations.
- proposal: covered by the CP-3 replacement set; where "team" survives it names a thing at a race (team wax sessions, team tent, team jackets), not the organization.
- workstream: copy

### CP-5
- surface: home / closed / all; about / closed / all
- kind: drift
- severity: P1
- contract: DESIGN.md, Components, SeasonsGrid: "On navy (home): mint headings, paper body." proposed: "the season card registration note states the current state in words: open, the upcoming dates, or closed. it never shows a past opening date without saying it has passed."
- evidence: site/src/lib/registrationCopy.ts:63-70 (`cardNote` has no state input); site/src/components/SeasonsGrid.astro:40-50; home-closed-desktop.png (cards read "2026 registration: returning members Jul 2 · new members Jul 17" with the windows already closed); about-closed-desktop.png
- observation: once both windows pass, the card keeps printing the opening dates as a schedule. in production this winter every visitor will read "2026 registration: returning members Aug 28 · new members Sep 3" under a mint "$205" and reasonably conclude registration is still to come. the open state has the mirror problem: the same line renders bold mint while registration is already open, so the dates read as future.
- proposal: give `cardNote` the state: `cardNote(state, year, w)`. open: `Registration open` (plus ` · new members from Sep 5` while only the returning window is live, both dates come from `w`). coming_soon: unchanged. closed: `${year} registration closed`. SeasonsGrid already derives the state per card at line 48; pass it through. the yaml fallback notes stay for the no-api case.
- workstream: copy

### CP-6
- surface: home / coming soon / all
- kind: drift
- severity: P2
- contract: proposed: "one format for a pair of opening dates everywhere: `Returning members Aug 28 · new members Sep 3`. middot separator, second clause lowercase, no semicolon."
- evidence: site/src/lib/registrationCopy.ts:33-39 (`datesSentence`: "Returning members Aug 30; new members Sep 5"), :48-54 (`datesLine`: "Returning members Aug 30 · New members Sep 5"), :64-70 (`cardNote`: "returning members Aug 30 · new members Sep 5"); home-soon-desktop.png shows all three on one page (under the hero button, in the CTA strip subhead, on both season cards)
- observation: the same two dates appear three times on the home page in three punctuation systems: middot with a capital N, semicolon with lowercase, middot with lowercase. the semicolon is the only one on the site outside code comments. the house separator is the middot.
- proposal: `datesLine` and `datesSentence` both return `Returning members ${r} · new members ${f}`; `stripSubhead` then reads `Returning members Sep 30 · new members Oct 15. Intermediate ability and up, no racing required.` `cardNote` keeps its lowercase prefix form. delete the docblock em dashes at lines 32 and 42 while there.
- workstream: copy

### CP-7
- surface: home / closed / all
- kind: drift
- severity: P2
- contract: july round 2 spec, section 3: "The months stay where they inform rather than exhort: CTA strip subhead ('Registration reopens Aug/Sep. ...') and both season cards' registration notes." proposed: "the closed state names when registration reopens."
- evidence: site/src/lib/registrationCopy.ts:56-61 (`stripSubhead` closed branch: "Registration is closed. Intermediate ability and up, no racing required."); home-closed-desktop.png
- observation: the july decision to relabel the button "How to register" was accepted on the condition that the reopen months survive in the strip subhead. the api-driven rewrite dropped them: closed now says only "Registration is closed." with a "How to register" button beside it. the honesty trade is gone.
- proposal: closed branch: `Registration is closed. Fall/Winter reopens Aug/Sep, Spring/Summer Apr/May. ${ABILITY}` with the two month pairs as named constants at the top of registrationCopy.ts, sourced from the june spec facts (rob, 2026-06-11). rob confirms the months still hold before this ships.
- workstream: copy

### CP-8
- surface: home / open / all
- kind: elevation
- severity: P2
- contract: proposed: "while only the returning window is open, the hero tells new members their date."
- evidence: site/src/components/HeroHome.astro:28-40 (`data-open-dates` baked empty; dates line shown only in coming_soon); site/src/lib/registrationState.ts:47 (open when either window is live)
- observation: from aug 28 to sep 3 the site says "Register for the season" to everyone, and a new member who clicks lands on a form that refuses them until sep 3. the dates line under the button is hidden in the open state by design.
- proposal: in HeroHome bake `data-open-dates` as `New members ${formatDay(new_start)}` when `now < new_start`, else empty; the flip script already reads that attribute and hides on empty, so no js change. registrationCopy.ts gets `newMembersLine(w, now)`. note that HeroHome markup belongs to sections; the string belongs here.
- workstream: copy

### CP-9
- surface: about / all states / all
- kind: drift
- severity: P2
- contract: DESIGN.md Imagery: "All photos schema-managed ... with required `alt`." proposed: "alt text describes what is in the frame; the same photo carries the same alt on every page."
- evidence: site/src/pages/about.astro:44 ("A line of members rollerskiing together at golden hour, poles mid-swing"); site/src/pages/sponsors.astro:35 ("A large group of TCSC members posing with roller skis and poles after a summer training session"); site/src/assets/images/photos/rollerski-golden-hour.jpg (viewed: a posed group of about twenty in matching caps, standing and seated around a bench, rollerskis on the ground)
- observation: the about page alt describes a rolling line with poles mid-swing. nobody in the photo is moving. the sponsors page alt for the same file is accurate. a screen-reader user gets a different photo on each page.
- proposal: about.astro:44 becomes `About twenty members in matching club caps posed around a bench after a golden-hour rollerski, skis and helmets at their feet`. leave sponsors.astro as is.
- workstream: copy

### CP-10
- surface: racing / default / all
- kind: drift
- severity: P2
- contract: voice rule 6: "Do not invent facts." proposed: "race and event names are spelled the way the organizer spells them, once, everywhere."
- evidence: site/src/content/pages/racing.mdoc:37 ("Korteloppet"); site/src/pages/racing.astro:25 ("Kortelopet medals"); site/src/content/pages/sponsors_page.yaml:17 ("Pre-Birkie"); site/src/content/pages/racing.mdoc:11 and site/src/pages/trips/index.astro:8,10 ("Prebirkie")
- observation: the same race is "Korteloppet" in the racing prose and "Kortelopet" in the alt text three hundred pixels below it. the same event is "Prebirkie" on racing and trips and "Pre-Birkie" on sponsors.
- proposal: verify against birkie.com and pick one spelling per event (birkie.com currently styles them "Kortelopet" and "Prebirkie"); apply to racing.mdoc:37 and sponsors_page.yaml:17. add the chosen spellings to a short names list in DESIGN.md so future entries match.
- workstream: copy

### CP-11
- surface: coaches / default / all
- kind: drift
- severity: P2
- contract: voice rule 4: "Remove ... repeated points."
- evidence: site/src/content/coaches/rebecca.mdoc:8-11 vs :14; site/src/content/coaches/greg.mdoc:9 vs :13; coaches-default-desktop.png
- observation: rebecca's three credentials ("Former high school ski coach", "Finn Sisu's Vakava team coach", "University of Minnesota ski team alumna") are her bio's three sentences restated as bullets directly beneath it. greg's first credential is his first sentence. the list reads as padding.
- proposal: rebecca: drop the credentials list entirely (the bio carries all three). greg: keep only `Wilderness First Responder`. kj and michael unchanged. CoachEntry already renders nothing for an empty list.
- workstream: copy

### CP-12
- surface: coaches / default / all
- kind: drift
- severity: P2
- contract: voice rule 1: "concrete activities and named details." voice rule 6: no invented facts.
- evidence: site/src/content/coaches/kj.mdoc:9 ("Salomon · Atomic · Bjorn Dahlie · Finn Sisu · Borah Teamwear"), :14 (one-sentence bio); coaches-default-desktop.png
- observation: kj's first credential is five brand names with no label. a visitor cannot tell whether he is sponsored by them, sells them, or likes them. "Bjorn Dahlie" is also not how the brand spells itself (Dæhlie). his bio is one sentence while the other three coaches get two to five; the head coach has the thinnest entry on the page.
- proposal: two paths, both need rob. (a) if the brands are his sponsor or shop affiliations, label the line: `Sponsored by Salomon, Atomic, Dæhlie, Finn Sisu, and Borah Teamwear` (or `Works with ...`). (b) if unconfirmed, cut the line. either way, ask kj for two sentences of bio in michael's register (where he skied, what he coaches on tuesdays). no invented text here; flagged as a content request.
- workstream: copy

### CP-13
- surface: racing / default / all
- kind: drift
- severity: P2
- contract: voice rule 4 (repetition); voice rule 3 (one playful ski reference per surface).
- evidence: site/src/content/pages/racing.mdoc:33-35; site/src/pages/racing.astro:37-38 (masthead fact "Always voluntary / Racing"); racing-default-desktop.png
- observation: the voluntary point lands three times above the fold: the masthead fact, "Racing with TCSC is voluntary", and "members who choose not to race are just as much a part of race weekend". "cheer" appears twice in two paragraphs. "take to the snow at citizen ski races to put their training to the test" and "No matter which camp you're in" are the slogan cadence the refresh removed elsewhere; the july spec flattened the exclamation points here but never rewrote the sentences.
- proposal: paragraphs 1 and 2 become: `Racing is optional. Members race citizen events across the Midwest at every level, and members who skip the start line are just as much a part of race weekend: the Techno Corner cheering section shows up at most big races. Some skiers are there to finish and some are there to win. Either way, TCSC teammates line the trail.` paragraphs 3 and 4 stay. the masthead fact stays (it is the scannable version).
- workstream: copy

### CP-14
- surface: racing / default / all
- kind: drift
- severity: P3
- contract: DESIGN.md Components, TripsTable: "A typeset table ... date, name, location." proposed: "a date column holds dates or date windows; anything else goes in notes."
- evidence: site/src/content/pages/racing.mdoc:25 (`date: Local series`); site/src/pages/racing.astro:57 (rendered uppercase, tracked, mint: "LOCAL SERIES"); racing-default-desktop.png
- observation: the date column reads JAN 9, 2027 / LATE JANUARY / FEB 27, 2027 / MAR 13, 2027 / LOCAL SERIES / LATE OCTOBER. "Local series" is a kind of event, not a date, and in the mint date slot it scans as a place. the july round kept the value; the new argument is that the column's styling now makes the category read as data.
- proposal: `date: ''` for Tour de Finn (racing.astro:55 already keeps the empty cell so columns do not shift) and `notes: 'A season-long local series. Two TCSC teams participated in 2026.'`
- workstream: copy

### CP-15
- surface: home / all states / all; sponsors / default / all
- kind: drift
- severity: P2
- contract: proposed: "one meta description per page, authored, under 155 characters, ending on a full stop. the trimmer is a safety net, not a writer."
- evidence: site/src/pages/sponsors.astro:22 (`metaDescription(page.data.intro)`); builds/*/sponsors.html meta description is 154 chars ending "...helping TCSC keep participation…"; site/src/pages/extra-training-fun.astro:24 (153 chars, at the limit)
- observation: the sponsors description is the intro paragraph cut mid-thought with an ellipsis, which is the failure metaDescription.ts was written to avoid. it fails because the intro's only sentence end is past the window. five pages derive their description from an intro that was never written as a search snippet.
- proposal: sponsors: pass an authored string, `TCSC's sponsors pay for shared wax, vans to races, and race-day gear. See what sponsor support has done and what comes next.` (129 chars). keep `metaDescription()` on the others but shorten the ETF intro or author its description: `Member-organized workouts between practices: Thursday Track Club, the Sunday Roll, open-water swims, and the club's annual traditions.` (134 chars).
- workstream: copy

### CP-16
- surface: 404 / default / all
- kind: drift
- severity: P3
- contract: proposed: "page titles are `<Page> · Twin Cities Ski Club`; the home page is the bare name."
- evidence: site/src/pages/404.astro:29 ("Page not found | Twin Cities Ski Club"); every other page uses " · " (about.astro:26, coaches.astro:19, trips/index.astro:7, wax-room/[slug].astro:30)
- observation: the 404 is the only title on the site with a pipe separator.
- proposal: `title="Page not found · Twin Cities Ski Club"`.
- workstream: copy

### CP-17
- surface: 404 / default / all
- kind: slop
- severity: P2
- contract: july 18 spec, 404: "one ski reference rather than four." awwwards-sections anti-slop audit: no icon+heading+paragraph repeats, no generic template phrasing.
- evidence: site/src/pages/404.astro:9-25, :41-55; 404-default-desktop.png
- observation: after the masthead ("This trail ends here." / "The page may have moved...") the body opens a second display-scale headline ("Choose another page.") that restates the subhead, then a "Helpful destinations" list, a phrase from every error-page template. the first destination is "Club trips / See where the club is headed next.", which today leads to a page that says "No trips posted". the eyebrow "404 · Page not found" is the page's only eyebrow and carries information, fine.
- proposal: drop the "Choose another page." h2 and its paragraph; keep the eyebrow and the "Back to home" button. rename the list heading `Try one of these` and replace the trips row with `Community / What members do beyond practice.` (a page that always has content). keep About and Registration rows. the meta description is dead weight under `noindex`; shorten to `Page not found.` or drop it.
- workstream: copy

### CP-18
- surface: trips / empty / all
- kind: drift
- severity: P2
- contract: voice rule 6 (no invented facts); proposed: "empty states tell the truth about today, in the ledger voice, in one or two sentences."
- evidence: site/src/pages/trips/index.astro:8-10 (subhead lists four races; description says "Lodging and meals organized."); site/src/components/TripsTable.astro:22-26 ("No trips posted. New trips are announced here each fall; get in touch with questions in the meantime."); trips-empty-desktop.png
- observation: the masthead promises "Sisu Ski Fest, the Birkie, the Prebirkie, the Great Bear Chase. Plus training trips and team weekends." and the table underneath says nothing is posted. the empty line claims trips are announced "here each fall"; the collection has been empty since launch, so that is a hope, not a record. it also carries a semicolon (see CP-21).
- proposal: subhead: `Race weekends and training trips, with lodging and rides organized by the club.` empty state: `No trips posted yet. Trips go up here once dates are set. Questions in the meantime: contact@twincitiesskiclub.org.` (link on the address). meta description: `Club trips to regional race weekends and training camps, with lodging and rides organized by TCSC.`
- workstream: copy

### CP-19
- surface: wax-room / empty / all
- kind: elevation
- severity: P3
- contract: proposed empty-state clause (CP-18).
- evidence: site/src/pages/wax-room/index.astro:20 ("No entries yet."); wax-room-empty-desktop.png (three words centered in an otherwise blank paper band)
- observation: the wax room is the most editorial surface on the site and its production state is three words. the conditions strip already has a voice for this ("Trail reports come back with the snow").
- proposal: `No entries yet. The first reports arrive with the snow.` that is the page's one ski reference. keep it `text-slate`, left-aligned in the prose column.
- workstream: copy

### CP-20
- surface: all / all states / all
- kind: drift
- severity: P2
- contract: proposed: "one name per page, in sentence case: the name in the nav, the footer, the page title, and the H1 match."
- evidence: site/src/components/Footer.astro:22 ("Extra Training & Fun"); site/src/pages/extra-training-fun.astro:23 (title "Extra Training Fun · ..."), :25 (H1 "Extra training fun"); site/src/content/pages/community.mdoc:86 ("Extra training fun")
- observation: the same page is named three ways: with an ampersand and title case in the footer, title case in the browser tab, sentence case on the page and in the community ledger. the footer form does not exist anywhere else.
- proposal: footer label `Extra training fun`; title `Extra training fun · Twin Cities Ski Club`. audit the other titles: `Dry Tri · Twin Cities Ski Club` matches its H1 "The Dry Tri" closely enough; `The Wax Room · ...` matches.
- workstream: copy

### CP-21
- surface: all / all states / all
- kind: drift
- severity: P3
- contract: june spec: "no em dashes (use commas, middots, hyphens)". proposed: "sentence punctuation is the period, the comma, the colon, and the middot. no semicolons in visitor-facing copy."
- evidence: site/src/lib/registrationCopy.ts:38; site/src/components/TripsTable.astro:23; site/src/content/pages/community.mdoc:89 ("No signup; all members welcome.")
- observation: three semicolons survive in visitor copy. the site's own separator grammar (middots on every fact line and the conditions strip) makes them stand out.
- proposal: registrationCopy per CP-6; TripsTable per CP-18; community.mdoc:89 `No signup, all members welcome.`
- workstream: copy

### CP-22
- surface: home, about / all states / all
- kind: drift
- severity: P3
- contract: proposed: "days of the week are joined with 'and' in prose and with a middot in fact slots. never a plus sign."
- evidence: site/src/content/practice_seasons/fall-winter.yaml:9 and spring-summer.yaml:9 ("Tuesday + Thursday evenings"); site/src/pages/coaches.astro:24 ("Tuesday · Thursday"); site/src/content/pages/extra_training.mdoc:4 ("Tuesday and Thursday")
- observation: the same fact renders with a plus sign on the season cards, a middot on the coaches masthead, and "and" in the ETF intro. the plus sign is a code-comment habit, not a typographic choice, and it is the only one on the site.
- proposal: both season yaml files: `when: Tuesday and Thursday evenings`. coaches fact stays middot (fact slot).
- workstream: copy

### CP-23
- surface: home, about / all states / all
- kind: drift
- severity: P3
- contract: june spec: "no em dashes (use commas, middots, hyphens)". proposed: "date ranges in prose use 'to'; compact ranges use an unspaced hyphen (Jan 9-11, ages 21-35)."
- evidence: site/src/content/practice_seasons/fall-winter.yaml:2 ("September - March"), spring-summer.yaml:2 ("May - August")
- observation: a spaced hyphen is the typewriter stand-in for an en dash. the site elsewhere writes ranges unspaced ("21-35", "Jan 9-11").
- proposal: `date_range: September to March` and `May to August`.
- workstream: copy

### CP-24
- surface: all / all states / all
- kind: drift
- severity: P3
- contract: proposed: "the metro is 'Minneapolis and St. Paul' in prose and 'Minneapolis · St. Paul' in fact slots and the footer. the age band is 'ages 21-35', never parenthetical."
- evidence: site/src/content/site_meta.yaml:6 and site/src/layouts/BaseLayout.astro:22 ("Minneapolis-St. Paul"); site/src/components/Footer.astro:31 ("young adults (21-35) in Minneapolis · St. Paul"); site/src/content/pages/home.yaml:14 ("young adults (ages 21-35)"); site/src/pages/index.astro:94 ("adults 21-35"); site/src/content/pages/community.mdoc:96 ("skiers ages 21-35 ... Minneapolis and St. Paul")
- observation: the two facts every page repeats are written five ways. "young adults (21-35)" says the age twice.
- proposal: meta description: `Year-round cross-country ski training and community for adults ages 21-35 in Minneapolis and St. Paul, with coached practices, racing, and trips.` (144 chars). footer: `A 501(c)(3) nonprofit for cross-country skiers ages 21-35 in Minneapolis · St. Paul. Coached practices twice a week, two seasons a year.` hero subline per CP-25. home mission per CP-2.
- workstream: copy

### CP-25
- surface: home / all states / all
- kind: elevation
- severity: P3
- contract: DESIGN.md Theme (the sponsor scene wants place and scale in the first screen). july round 2: hero layout "stays".
- evidence: site/src/pages/index.astro:94 (subline hardcoded: "Year-round cross-country ski training for adults 21-35."); home-hero-desktop.png
- observation: the H1 repeats the wordmark that sits 300px above it in the nav, which the july round accepted, so the subline is the only line in the fold that can say anything. it says what the club does but not where or how often, and the sponsor scene is a reader who wants both in five seconds.
- proposal: subline: `Coached cross-country ski training for adults ages 21-35, twice a week, year-round, in Minneapolis and St. Paul.` fits `max-w-prose-narrow` on two lines at desktop. H1 unchanged.
- workstream: copy

### CP-26
- surface: home / all states / all
- kind: slop
- severity: P3
- contract: DESIGN.md, LiveConditions: "current temp + recommended wax range at four Twin Cities ski areas (Theodore Wirth, Hyland, French Park, Battle Creek)."
- evidence: site/src/components/LiveConditions.astro:14-19 (Theo, Elm, Hyland, Telemark); scripts/brand-review/fixture-api.mjs VENUES (mirrors app/conditions/locations.py); home-open-desktop.png
- observation: the contract names two venues the strip has never shown, and one of the four it does show (Telemark, in Cable, WI) is not a Twin Cities ski area. the venue label "Theo" is the only place on the site the home trail is not called "Theodore Wirth" (season cards, ETF, community, wax fixture all spell it out). the api overwrites the server-rendered name on every fetch, so the placeholder alone cannot fix it; this is a flask string, out of scope this round.
- proposal: contract change only (see below): list the real four and call the device by its visible name. leave the code. flag "Theo" to rob as a one-line change in app/conditions/locations.py for a later flask pr.
- workstream: copy

### CP-27
- surface: home / unavailable / all
- kind: slop
- severity: P3
- contract: DESIGN.md, LiveConditions: "Sparse data fallback (API failure): the strip shows location names + a quiet 'Conditions unavailable' line."
- evidence: site/src/components/LiveConditions.client.ts:104, :144 ("No report" written into every cell); home-unavailable-desktop.png (the stamp says "Conditions unavailable" and five cells each say "No report")
- observation: the client's own comment says cells "go quiet ... instead of repeating the error four times", and then it repeats "No report" five times under a stamp that already says the same thing. the contract asks for names plus one line.
- proposal: cells render an empty wax line (or a lone middot) when the stamp carries the message. this is a string change in a sacred file; propose it for rob's yes/no rather than fixing it in this round.
- workstream: copy

### CP-28
- surface: home / lightbox / all
- kind: slop
- severity: P3
- contract: DESIGN.md Banned: "'→' on every link. Reserved for the home hero CTA." Iconography: "Lucide ... lightbox close."
- evidence: site/src/components/Lightbox.astro:31-32 (visible button text "←" and "→"); home-lightbox-desktop.png
- observation: the only arrows on the site are the lightbox prev/next buttons, rendered as text glyphs in Archivo, not Lucide strokes like the close button beside them. the home hero CTA that the ban reserves the arrow for does not use one.
- proposal: the aria-labels are already "Previous photo" / "Next photo"; swap the glyphs for the Lucide chevrons the close button's style already establishes (markup belongs to motion-components; noting here because the contract clause is a copy rule and needs rewording, see below).
- workstream: motion-components

### CP-29
- surface: home / all states / all
- kind: slop
- severity: P3
- contract: visual-redesign: one source per string; no duplicated literals.
- evidence: site/src/layouts/BaseLayout.astro:22 (default description literal); site/src/content/site_meta.yaml:4-6 (same sentence)
- observation: the site description lives in two files word for word. the july spec asked for the BaseLayout fallback to be "the existing plain site description", which produced the duplicate.
- proposal: BaseLayout reads `site_meta` for its fallback (a `getEntry('site_meta', 'site_meta')` in the layout frontmatter), and the literal goes away. CP-24 then edits one place.
- workstream: copy

### CP-30
- surface: community / default / all
- kind: slop
- severity: P3
- contract: visual-redesign: dead content and dead fields are slop.
- evidence: site/src/content/pages/community.mdoc:4-18 (`team_bonding_activities`, 14 items); no reference in any .astro file (grep)
- observation: fourteen lines of content that nothing renders, including "Meet & greet with 3-time Olympic medalist Jessie Diggins", which also appears as a Socials item at line 85. the schema field is a non-goal to remove, but the content is not.
- proposal: empty the list in community.mdoc (`team_bonding_activities: []`). the schema keeps its default.
- workstream: copy

### CP-31
- surface: community / default / all
- kind: drift
- severity: P3
- contract: proposed: "numbers under ten are words; ten and above are numerals; ampersands only in proper names."
- evidence: site/src/content/pages/community.mdoc:85 ("Meet & greet with 3-time Olympic medalist"); site/src/content/pages/dry_tri.mdoc:24-26 ("About 25 racers" then "about twenty club volunteers")
- observation: "3-time" and "Meet & greet" in a list where every other line is prose; "25" and "twenty" in consecutive sentences.
- proposal: community.mdoc:85 `A meet and greet with three-time Olympic medalist Jessie Diggins`; dry_tri.mdoc:26 `about 20 club volunteers`. community.mdoc:35 "About twenty members" becomes `About 20 members`.
- workstream: copy

### CP-32
- surface: dry-tri, community / default / all
- kind: drift
- severity: P3
- contract: voice rule 4 (repeated points), across pages.
- evidence: site/src/content/pages/dry_tri.mdoc:26 vs site/src/content/pages/community.mdoc:35-38 (the volunteer-roles list "parking, course marshaling, chip timing, the finish line, photography, and cleanup" appears verbatim on both pages)
- observation: one sentence copied between two pages.
- proposal: community keeps the list (it is the ledger's point). dry_tri.mdoc:26 becomes `About 20 club volunteers ran the day, from parking to chip timing to cleanup. Planning for the next edition started soon after the finish.`
- workstream: copy

### CP-33
- surface: coaches, extra-training-fun / default / all
- kind: drift
- severity: P3
- contract: proposed: "typographic quotes in prose."
- evidence: site/src/content/coaches/kj.mdoc:14 (`Kevin "KJ" Johnson`); site/src/content/pages/extra_training.mdoc:58 (a quoted member line in straight quotes)
- observation: the only two quotations on the site use straight typewriter quotes. Archivo has the curly glyphs.
- proposal: `Kevin “KJ” Johnson`; `“wanting to do the speed workouts I would be doing anyways with other people.”`
- workstream: copy

### CP-34
- surface: community / default / all
- kind: drift
- severity: P3
- contract: proposed spelling list (CP-10).
- evidence: site/src/content/pages/community.mdoc:83 ("The apres-ski book club"), :96 ("apres-ski lovers")
- observation: "apres-ski" without the accent twice. the july spec protected the sentence, not the spelling. Archivo carries the glyph; the display subset does not, but neither line is set in the display cut.
- proposal: `après-ski` in both places.
- workstream: copy

### CP-35
- surface: sponsors / default / all
- kind: drift
- severity: P3
- contract: proposed sentence-case clause (CP-20).
- evidence: site/src/lib/sponsorTiers.js:7-9 ("Trailblazer Partners", "Community Partners", "Supporters"); sponsors-default-desktop.png
- observation: the tier headings are the only title-case headings on the site. "Trailblazer" is a tier name and can keep its capital; "Partners" is a common noun.
- proposal: `Trailblazer partners`, `Community partners`, `Supporters`. (a js lib string, no logic; the file is not on the sacred list.)
- workstream: copy

### CP-36
- surface: home / all states / all
- kind: drift
- severity: P3
- contract: voice rule 4.
- evidence: site/src/pages/index.astro:115 (seam "Our sponsors"), :121 (link "About our sponsors"); site/src/content/pages/sponsors_page.yaml:1 (headline "Our sponsors")
- observation: "sponsors" three times in one slim band, and the link leads to a page whose H1 is the seam label again.
- proposal: link label `Sponsor the club` if the page's purpose is the pitch (CP-3), else `More about our sponsors`. seam stays.
- workstream: copy

### CP-37
- surface: community / default / all
- kind: drift
- severity: P3
- contract: voice rule 4, across surfaces.
- evidence: site/src/pages/community.astro:62 (masthead fact "Photos by club members / Credits"); site/src/components/Footer.astro:45 ("All photos by club members.")
- observation: the same credit line sits in the community masthead and in the footer of the same page, and "Credits" as a label reads like a film title card next to "Founded".
- proposal: replace the community fact with something the masthead does not already say and the page proves: `4 / Standing groups` is invented framing; safer is `2020 / Founded` plus `Member-run / Board and committees` (from community.mdoc:22-26). the footer keeps the photo credit.
- workstream: copy

### CP-38
- surface: coaches / default / all
- kind: drift
- severity: P3
- contract: june spec, section 5: facts render as `value / label` pairs where the label names the value.
- evidence: site/src/pages/coaches.astro:22-25 ("Two seasons a year / Coaching", "Tuesday · Thursday / Practices")
- observation: "Coaching: two seasons a year" is a label and value that do not quite belong to each other; the other mastheads pair a noun label with a value of that noun (Founded / 2020, Venue / Carver Park Reserve).
- proposal: `Fall/Winter · Spring/Summer / Seasons` and `Tuesday · Thursday / Practice nights`.
- workstream: copy

### CP-39
- surface: trips / populated / all; racing / default / all
- kind: elevation
- severity: P3
- contract: proposed: "house formats for dates and places: `Jan 9-11, 2027` (short month, no leading zeros, unspaced hyphen range); `Ironwood, MI` (two-letter state). trips, races, wax entries, and captions all use them."
- evidence: scripts/brand-review/fixtures/content/trips/sisu-ski-fest.mdoc:3-4 ("Ironwood, Michigan", "January 9-11, 2027") vs site/src/content/pages/racing.mdoc:8-9 ("Ironwood, MI", "Jan 9, 2027"); trips-populated-desktop.png
- observation: the trip schema takes free text for dates and location, so the first real trip will be typed by whoever posts it. the fixture already shows the drift: long month and full state on trips, short month and abbreviation on racing, for the same event in the same town.
- proposal: contract clause above, plus the format written into the keystatic field descriptions later (schema is a non-goal this round). no content change now.
- workstream: copy

### CP-40
- surface: home / all states / all
- kind: slop
- severity: P3
- contract: visual-redesign: one source of truth per string.
- evidence: site/keystatic.config.ts:73 (closed default "Member area"); site/src/content.config.ts:212 (closed default "Register"); site/src/components/registrationCta.ts:51 (closed fallback "Register"); all three: coming-soon default "Get on the list"
- observation: three fallback vocabularies for the same two labels. "Get on the list" promises a mailing list the site does not have; "Register" as a closed-state label is the june round's rejected wording. none of them render while home.yaml is filled in, so this is latent.
- proposal: nothing in this round: registrationCta.ts is sacred and the schema files are non-goals. record in the ledger as deferred, with the fix being `Registration dates` / `How to register` in all three files in a later pr.
- workstream: copy

### CP-41
- surface: wax-room / populated / all
- kind: drift
- severity: P3
- contract: proposed one-name clause (CP-20).
- evidence: site/src/pages/wax-room/index.astro:14 (description "Conditions reports, wax notes, race prep, and technique") vs :16 (subhead "Conditions, wax notes, race-day prep, technique. Field reports ...")
- observation: the subhead and the meta description say the same thing in two wordings ("race prep" / "race-day prep", "Conditions reports" / "Conditions").
- proposal: both: `Conditions, wax notes, race-day prep, and technique. Field reports from TCSC coaches and members.` (99 chars).
- workstream: copy

## proposed contract changes

- add a "Copy" section to DESIGN.md that carries the 2026-07-18 voice rules verbatim (plain register, concrete over values, direct verbs, one playful ski reference per surface, no slogan structures, no invented facts) plus: no em dashes, no exclamation points, no semicolons, sentence case everywhere, curly quotes in prose. needed by CP-2, CP-3, CP-13, CP-21, CP-33, CP-35.
- add a "Registration copy" clause: labels never name a season; the card note states the state in words (open / dates / closed) and never shows a past opening date as a schedule; the closed state names the reopen months; one date-pair format (`Returning members Aug 28 · new members Sep 3`); while only the returning window is open the hero names the new-member date. needed by CP-1, CP-5, CP-6, CP-7, CP-8.
- add an "Empty states" clause: one or two sentences in the ledger voice, true today, no promised cadence the site has not kept. needed by CP-18, CP-19.
- add a "Names and facts" list: the club is "the club" and its people "members"; the metro is "Minneapolis and St. Paul" in prose and "Minneapolis · St. Paul" in fact slots; the age band is "ages 21-35"; days join with "and" in prose and a middot in fact slots; ranges are "September to March" in prose and unspaced hyphens in compact form; race names spelled per the organizer (Kortelopet, Prebirkie, Sisu Ski Fest, American Birkebeiner, Great Bear Chase). needed by CP-4, CP-10, CP-22, CP-23, CP-24, CP-39.
- add a "Titles and meta" clause: `<Page> · Twin Cities Ski Club`, home is the bare name; every page authors its own meta description under 155 characters ending on a full stop; `metaDescription()` is the safety net. needed by CP-15, CP-16, CP-20, CP-29.
- add a "404" clause: masthead line plus one list of three live destinations; no second headline; noindex. needed by CP-17.
- add an "Alt text" clause: describes what is in the frame; the same file carries the same alt on every page. needed by CP-9.
- correct the LiveConditions section: the four venues are Theodore Wirth, Elm Creek, Hyland, and Telemark (Cable, WI), not French Park and Battle Creek; the device's visible name is "Trail report" and its stamp reads "Live · updated 7:02 AM" (a clock time, not "n min ago"); the unavailable state is the stamp line plus quiet cells. needed by CP-26, CP-27.
- reword the arrow ban: "no arrow glyphs in link or button text anywhere; navigation controls use Lucide strokes." the current exception for the home hero CTA describes a button that has never had one. needed by CP-28.
- add the 2026-06-11 registration-month facts (Fall/Winter opens Aug/Sep, Spring/Summer opens Apr/May) to the contract's facts list with their source and date, so the closed-state copy has a citable origin. needed by CP-7.
