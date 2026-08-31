you are implementing one workstream of a brand consistency, elevation, and de-slop pass on twincitiesskiclub.org, the Twin Cities Ski Club marketing site: Astro 7 static site + Tailwind 4 under site/ in this repo. you are working in a git worktree on branch brand/copy, branched from site/brand-review. commit on this branch; never merge, never push, never touch other branches, never touch main. do not stop or start docker containers.

## your workstream: copy
every string on every surface: site/src/content/** (pages, coaches, photos alt and captions, practice_seasons, sponsors, nav.yaml, site_meta.yaml), site/src/lib/registrationCopy.ts strings, site/src/lib/metaDescription.ts, site/src/components/heroFacts.ts, the 404 page copy. you change words, not markup; if a row needs markup, report it as proposed for sections.

## the contract (read in full, first)
DESIGN.md at the repo root is the v2 contract. its "Theme" section names the two scenes the site reads for. docs/superpowers/specs/2026-07-18-marketing-copy-refresh-design.md holds the voice rules. every change you make must move the site toward these.

## your ledger rows
these are the only changes you may make. each row cites the contract clause it implements.

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

## your method
no skill file. the rubric is docs/superpowers/specs/2026-07-18-marketing-copy-refresh-design.md "voice rules" and the copy section of DESIGN.md v2.
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
  PORT=4402 node screenshot.mjs after-copy <stateIds you touched>
state ids are in scripts/brand-review/states.mjs; the matrix is docs/superpowers/specs/2026-08-31-site-brand-review/state-matrix.md. your port is 4402; other workstreams use other ports, so never use 4400 to 4405 for anything else. the before screenshots are on this machine at /workspace/tcsc-trips/docs/superpowers/specs/2026-08-31-site-brand-review/screens/before/ (the main checkout; screens are not committed). compare each after image against the before image with the same filename. look at them. if a change reads louder, busier, or more generic than before, it fails the gate: revert and try a quieter version. leave no serve-dist.mjs process running when done (`pkill -f "serve-dist.mjs .* --port 4402"`).

## report
write docs/superpowers/specs/2026-08-31-site-brand-review/copy-report.md:
- `# copy report`
- `## rows`: one line per ledger id: `L-nnn: fixed (<file:line>, <commit sha>)` or `L-nnn: skipped (<reason>)`.
- `## screens`: list of after screenshots you produced (they live in screens/after-copy/ in your worktree; screens are gitignored, so do not try to commit them).
- `## proposed`: anything you noticed that has no ledger id.
- `## test/build`: paste the last line of each of the five commands.
commit the report on your branch as the last commit.

work through the rows in ledger order (P1 first). commit small and often: one commit per row or per tightly related group, message `brand(copy): <what> (L-nnn)`.
