# Marketing Site Feedback Round 2, July 2026

Design spec for changes to the Astro marketing site (twincitiesskiclub.org) responding to feedback from a developer friend of the club. Posture matches the June 2026 round: accept the underlying critiques, execute them in the site's quiet ledger language (hairline rules, small-caps seams, navy/mint/paper palette, near-zero motion), reject off-language formats. Triage decisions were made against the June round's documented preferences (docs/superpowers/specs/2026-06-11-marketing-site-design-feedback-design.md, handoff notes, DESIGN.md) because Rob asked for this round to run without further input.

Work happens on `feat/site-feedback-july-2026` in the site worktree (`/Users/rob/env/tcsc-trips-site`). All copy follows the club voice rules: plain register, no em dashes (use commas, middots, hyphens), no exclamation points, no invented facts.

## Feedback disposition summary

Accepted (reinterpreted where noted):
- Trail report source links + "groomed as of": the scraper already parses per-venue `report_url`, `report_date`, `groomed`, `groomed_for`; expose them through `/api/conditions` and render quiet links + a groomed line in the strip. Tooltip/popover rejected as off-language ("no modal"); plain links instead.
- "Twin Cities" over a member's face in the home hero: focal-point fix only; the hero layout is the strongest screen on the site and stays.
- Closed CTA copy: relabel `Registration opens Aug/Sep` to `How to register`. The months survive in the CTA strip subhead and both season cards, so honesty is preserved while the button reads as a CTA.
- Seasons muted-text contrast on navy: bump `text-paper/60` to `text-paper/75`.
- "A welcoming community" mosaic: cut the no-people trail photo and the solo photo, swap in two group photos already in the consented collection. Keep the 9-photo flush grid.
- Mosaic hover: replace the full-tile navy wash with a bottom caption scrim that fades in; the photo itself stays visible.
- Community masthead intro too wordy: shorten the subhead; the full inclusivity sentence moves into the body prose. Other routes audited: About (reference wording), Racing, Dry Tri, ETF subheads are already one tight line each; no change.
- "Extra training fun" feels like a hidden link: promote it to a fourth group in the "What we've done" ledger with its own items and link; delete the trailing "own page" line.
- Volunteering photo cuts heads off: fix, plus a crop audit of every `object-cover` image on About/Community/Racing (implementer views each source image and sets `object-position`).
- Race dates: add officially announced 2026-27 dates only (verified against official race sites); unannounced races keep their current month-level labels.
- Header/footer link order: footer restructured so links read in nav order down each column (today the two-column grid interleaves them).
- Narrow-width "BIRKIE 98.6": mobile shows the Theodore Wirth cell instead of the Birkie fever cell (the fever gag reads as noise to a first-time phone visitor). Fever cell becomes md+ only. In the dryland season, mobile shows the single "Dryland season" statement.

Rejected:
- Exact Birkie count ("tell me exactly how many, cut the +"): no exact number exists anywhere in the repo or notes; the standing rule is never invent facts. Flagged for Rob: supply the count and it is a two-line change (racing masthead fact + mission panel).
- "Come ski with us." to "Come ski with us!": exclamation points were deliberately stripped sitewide in the copy-voice audit (Sisu lede had 3, racing prose 4, all flattened). The period is the voice.
- Carousel for the Community groups: off-language. DESIGN.md: "Section transitions: none. No fade-in-on-scroll. No staggered entrances." The underlying critique (table format is not scannable, each group deserves a header/photo/summary) is honored inside the existing ledger: anchor photos, display-scale group headings (both shipped in June), plus the new ETF group this round.
- New photo ports from the Slack archive: June's ports were individually consent-cleared by Rob; publishing new archive faces without him is out of bounds for an autonomous round. All photo swaps this round use already-consented, already-published collection images.

## 1. Trail report provenance (API + strip)

Backend (main Flask app; deploys with the web service on merge):
- `app/conditions/service.py` (`_build_location_payload`, lines ~60-77): each location dict gains
  - `source_url`: `TrailCondition.report_url` (SkinnySkI report page), null when no report matched.
  - `report_date`: ISO `YYYY-MM-DD` from `TrailCondition.report_date`, null when unknown.
  - `groomed_for`: `'skate' | 'classic' | 'both' | null` from the matched report.
- Null in the dryland season (no reports); the strip renders nothing extra then, so the July-live behavior is unchanged.
- `tests/conditions`: extend the payload-shape tests for the three new fields (present with report, null without).

Strip (`site/src/components/LiveConditions.astro` + `LiveConditions.client.ts`):
- Extend the `VenueData` type with the three fields.
- When `source_url` is present, the venue name renders as a quiet link to the SkinnySkI report (underline-offset ledger treatment, opens in a new tab, `rel="noopener"`). No icon.
- When `groomed_for`/`report_date` are present, the venue cell's detail line gains `Groomed skate · Feb 8` (or `Groomed · Feb 8` when `groomed_for` is null but the report is groomed; omit entirely when not groomed). Formatting: short month + day, no year. Same small type scale the cell already uses; muted color.
- No tooltips, no popovers, no new interaction patterns. Compact (inner-page) variant gets the name-link only, not the groomed line (one line per venue there).

## 2. Home hero focal point

`site/src/components/HeroHome.astro` (line ~28): the photo is `object-[center_38%]` and the headline block is bottom-anchored, which puts "Twin Cities" across a member's face at common widths. Fix is focal only:
- Implementer opens `site/src/assets/images/uploads/home-hero-trail.jpg` (Read tool renders it), locates the faces, and adjusts `object-position` so no face sits under the bottom text block at ~390px, ~768px, ~1440px widths. Screenshot verification at all three.
- Do not restructure the hero, scrim, or type. If no focal value clears all three widths, pick the best compromise favoring desktop and note it in the PR body.

## 3. Closed-state CTA copy

- `site/src/content/pages/home.yaml`: `cta_closed_label: Registration opens Aug/Sep` becomes `cta_closed_label: How to register`. `cta_closed_url` stays `https://tcsc.ski`.
- Flows to all four render sites (desktop nav, mobile panel, hero, CTA strip) through `getRegistrationCta()`; grep-count check as in June (4 occurrences in `dist/index.html`, 2 in `dist/about/index.html`).
- The months stay where they inform rather than exhort: CTA strip subhead ("Registration reopens Aug/Sep. ...") and both season cards' registration notes. No other copy changes.

## 4. Seasons muted-text contrast

`site/src/components/SeasonsGrid.astro` (line ~40): navy variant `muted = 'text-paper/60'` becomes `'text-paper/75'`. Affects the date-range line, the closed registration note, and the shared dues paragraph on the home (navy) variant. Paper variant (`text-slate`) already passes and is unchanged.

## 5. Home mosaic photo swap

`site/src/content/photos/`: the "A welcoming community" section pulls the 9 `show_on_home: true` entries.
- Cut from home (set `show_on_home: false`, keep in the community wall): `oo-corridor` (trail corridor, no people), `fire-danger-maria` (one member).
- Add (set `show_on_home: true`): `rollerski-treats` (group around post-practice treats), plus ONE of `finlandia-axes` / `great-bear-chase` / `borah-epic`. Implementer Reads all three images at the grid's rendered size and picks the strongest group-fun photo, then sets `order` values so the two newcomers sit well in the mosaic's size pattern (the cut photos held orders 10 and 100; the lead slot renders large, so the replacement there must survive a big crop).
- Invariants: exactly 9 `show_on_home` entries (flush grid at both breakpoints), `photo_consent_recorded: true` on every entry (all candidates already are), event-tag variety preserved.

## 6. Mosaic hover caption

`site/src/components/PhotoMosaic.astro` (lines ~178-185): replace the full-tile overlay (`absolute inset-0 ... bg-navy/70`) with a bottom scrim:
- `absolute inset-x-0 bottom-0` gradient `from-navy/85 via-navy/50 to-transparent`, tall enough to seat one or two caption lines (roughly `pt-10 pb-4 px-4`), caption text unchanged.
- Same `opacity-0 group-hover:opacity-100` fade, 150ms ease-out, desktop only (`hidden md:flex` stays). The photo above the scrim is never dimmed.
- This matches the functional-gradient rule the hero already follows (gradients earn their place by making text legible, not by decorating).

## 7. Community masthead subhead

- `site/src/content/pages/community.mdoc` intro (the masthead subhead) currently runs 33 words. Replace with: `Volunteer nights, socials, member coaching, and extra training beyond practice.`
- The full inclusivity sentence moves into the body prose: merge "Twin Cities Ski Club is an inclusive community for any cross-country skier ages 21-35 who lives in the greater Minneapolis · St. Paul area, regardless of race, gender, sexual orientation, or religion." with the existing single body paragraph, editing so nothing is stated twice. The sentence itself is club-approved wording; keep it intact apart from joining punctuation.
- Other routes audited for the same wordiness: About subhead is the club's reference sentence (keep), Racing / Dry Tri / ETF subheads are one line each (keep), Coaches has none. No further changes.

## 8. Extra training fun in the Community ledger

`site/src/content/pages/community.mdoc` takeaways + `site/src/pages/community.astro`:
- Add a fourth group `Extra training fun` after Socials. Items (facts sourced from the ETF page itself):
  1. line `Member-organized workouts, most days of the week`, detail `Track mornings, long rollerskis, open-water swims. No signup, everyone welcome.`, href `/extra-training-fun`
  2. line `Thursday Track Club and The Sunday Roll`, detail `Standing invitations, all season.`
  3. line `The TCSC Classic and the Tour de Ice Cream`, detail `Member-invented annuals.`
- No anchor photo for this group this round (every candidate image already renders elsewhere on the same page, and new ports are out of bounds; "Members who coach" also has no photo, so the rhythm holds). Follow-up flagged for Rob: pick an ETF anchor from the archive if wanted.
- Delete the trailing "Member-organized workouts are on their own page: Extra training fun." paragraph (community.astro lines ~126-132); the group replaces it.
- Section subhead updates from `A few seasons of volunteering, coaching, and socials.` to `A few seasons of volunteering, coaching, socials, and member-led training.`

## 9. Crop audit (heads cut off)

Implementer Reads each source image and screenshot-verifies each rendered crop at mobile and desktop, setting `object-position` where heads or key subjects are clipped:
- `second-harvest` Volunteering anchor (currently `center 65%`, the reported head-cutter) - community.astro:43.
- Community member cluster, all 4 (`backyard-social`, `run-club-selfie`, `winter-five`, `lakeside-picnic`): `h-48 md:h-64 object-cover` with no object-position today.
- `barn-banquet` Socials anchor: no object-position today.
- Racing strip (`ski-de-she-trio`, `korte-medals`, `birkie-start`, `finlandia-podium`): tall `aspect-[3/4] object-cover` with no object-position (skijor-race already has one).
- `rollerski-golden-hour` on About; masthead bands (`team-banner` 40%, `canoe-social` 52%, `race-crew-frosty` 30%) verified but expected fine.
- Only `object-position` values change; no size, aspect, or layout changes.

## 10. Race dates

`site/src/content/pages/racing.mdoc` races list: replace month-level date labels with officially announced 2026-27 dates, verified against the official race sites (research agent output reviewed before use; a date ships only with a confirmed-official source). Expected shape, subject to what is actually announced:
- Sisu Ski Fest, Prebirkie & North End Classic, American Birkebeiner, Great Bear Chase: `Jan 9, 2027`-style values where confirmed; otherwise the current label stays.
- Tour de Finn stays `Local series`; TCSC Dry Tri stays `Late October` (no public 2026 date; prior note confirms).
- Date format: `Feb 27, 2027` (short month, no leading zeros, hyphen ranges when needed), consistent column width in the existing `sm:grid-cols-[10rem_1fr_1fr]` grid.

Verified 2026-27 race dates (web research, 2026-07-10; official race sites):
- Sisu Ski Fest: `Jan 9, 2027` (sisuskifest.com homepage) - confirmed, use it.
- American Birkebeiner: `Feb 27, 2027` (birkie.com event page; Birkie Week Feb 23-28) - confirmed, use it.
- Great Bear Chase: `Mar 13, 2027` (greatbearchase.com homepage) - confirmed, use it.
- Prebirkie & North End Classic: no official 2027 dates published (only a third-party tentative listing) - keep the current `Late January` label.
- Tour de Finn: season-long points series, no 2027 list posted - keep `Local series`.
- TCSC Dry Tri: no public 2026 date - keep `Late October`.

## 11. Footer link order

`site/src/components/Footer.astro` (lines ~11-23): restructure the two-column block so each column is its own list and the visual reading order matches the header nav: column A `About, Community, Racing, Coaches, Wax Room`, column B `Sponsors, Trips, Extra Training & Fun, Dry Tri`. No links added or removed; only the interleaving goes away.

## 12. Trail strip at narrow widths

`site/src/components/LiveConditions.astro` + `.client.ts`:
- Prominent (home) variant: the Theodore Wirth cell loses `max-md:hidden`; the Birkie fever cell gains it (desktop unchanged: 4 venues + fever). Mobile now shows the strip eyebrow + the Theo Wirth report.
- Compact (inner) variant: same swap on the line items.
- Dryland season: the client's injected "Dryland season" statement loses `max-md:hidden` so a July phone visitor sees `Trail report - Dryland season` instead of a bare fever reading or an empty strip. When live venue data returns in winter, mobile shows the Theo cell.
- The fever cell's audio easter egg is untouched on md+.

## Out of scope this round

- Exact Birkie participant count (waiting on a number from Rob).
- New photo ports from `migration/slack_photos/` (consent gate; includes an ETF anchor photo).
- Favicon, OG images, nav link slimming, event_tag filter UI, klister seasonal gate.
- Home PhotoMosaic layout mechanics beyond the photo swap and hover treatment.

## Verification

- `npx astro check` 0 errors; `NODE_ENV=production npx astro build` ends "10 page(s) built".
- `python -m scripts.wix_scrape.verify` exit 0 (no manifest changes expected this round).
- `pytest tests/conditions tests/wix_scrape` green, including the new payload-field tests.
- Grep checks: `How to register` count 4 in `dist/index.html`, 2 in `dist/about/index.html`; `Come ski with us.` still present, no `!` added.
- Visual sweep at ~390px and desktop: home (hero face clear of text, mosaic 9 photos all people-groups, hover scrim bottom-only, seasons contrast, sponsor strip untouched), community (short subhead, ETF group, no hidden-link line, crops), racing (dates, strip crops), footer order, trail strip mobile = Theo cell (or Dryland statement).
- API: `curl /api/conditions` locally shows the three new per-venue fields (null off-season is correct).
