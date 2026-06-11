# Marketing Site v2 · Polish Pass #4 Critique (2026-06-10, late night)

Subtraction-first multi-agent review of staging (all 12 pages, desktop + mobile).
Method: 19 independent reviewers (one design critic per page + 7 cross-cutting
lenses: typography, color/slop, voice, IA/nav, subtraction-only, family
consistency, mobile), 152 raw findings merged to 32 candidates, every candidate
re-verified by an adversarial agent against the screenshots and source. None
were refuted; 7 had their scope trimmed. Deterministic anti-pattern detector:
clean (12 false positives, the lightbox placeholder `<img>`).

Evidence: `migration/survey-2026-06-10/` (screenshots, slices, html,
detector.json, REVIEW-BRIEF.md). Raw verified output:
`/private/tmp/claude-501/-Users-rob-env-tcsc-trips/60b28b89-b574-4bcc-b91f-0fb3b3468f7f/tasks/wryz6ayrx.output`

Tally: 1 P0, 25 P1, 6 P2. By kind: 9 remove, 13 trim, 3 swap, 6 fix, 1 add
(the add is fact-gated). Net word count and element count go DOWN if all land.

## Bundle A · The arrow cleanup (P0)

- **F01 [P0/remove, 9 sources]** DESIGN.md reserves "→" for the home hero CTA
  only. It currently renders on the home CTA strip ("Register →",
  `index.astro:46`), trip detail ("Sign up →", `TripEntry.astro:97`), wax-room
  "Read →" links (redundant second link to the same URL), and TripsTable hover
  rows (with a reserved empty grid column). It is also baked into the shared
  open-state label (`home.yaml:7`, `registrationCta.ts:24`, plus the zod
  default at `content.config.ts:199`), so the top nav inherits it the moment
  registration opens. Meanwhile the hero, the one sanctioned spot, has no
  arrow. Fix: delete all of them; if the hero keeps an arrow, render the glyph
  inside HeroHome markup only. Lightbox prev/next stays.

## Bundle B · Say it once (redundancy cuts)

- **F02 [P1/remove, 6]** Home Practices band H2 ("Year-round cross-country ski
  training.") restates the hero subline verbatim one screen up. Delete the
  heading prop; seam + season cells carry it (matches dry-tri/ETF grammar).
  Note: bump SeasonsGrid h3s to h2 to keep the outline clean.
- **F04 [P1/remove, 5]** The 80+ Birkie stat appears three times on the
  one-screen racing page (masthead fact, body, table note). Delete the Birkie
  row note (`racing.mdoc:20`), trim the body paragraph to its net-new facts.
- **F06 [P1/trim, 4]** SeasonsGrid: dues sentence hardcoded inside the loop
  prints twice; two of three bullets identical across both seasons; renders
  verbatim again on /about. Hoist shared material out of the loop; each column
  keeps dates, price, summary, and its unique item.
- **F10 [P1/remove, 3]** Coaches roster stated three times before the first
  photo (generic subhead with banned flourish triple, "4 dedicated coaches"
  fact, anchor index). Delete subhead from render + the count fact; index is
  Rob's call (2 of 3 reviewers would cut it).
- **F12 [P1/trim, 3]** Community intro: paragraphs 1, 3, 4 pre-summarize the
  ledger and end in "And much, much more!". Keep only paragraph 2 as lede; fix
  the missing "or" and "21 - 35 years old" mechanics in the kept text.
- **F13 [P1/remove, 3, modified]** Trips masthead "Next up" facts always
  mirror the first table row beneath them. Delete the facts computation and
  prop entirely (verifier: also drop the masthead fallback; TripsTable's empty
  state already carries that signal).
- **F26 [P1/trim, 1, modified]** ETF: duplicate "so they finish together"
  sentence (prose + fixture), subhead enumerates the lists it precedes and
  miscategorizes time trials, "All levels are welcome." restates the intro.
  Three deletions in `extra_training.mdoc`.
- **F27 [P2/trim, 2]** About says its mission twice ("X. In short, X.") and
  its coaching sentence twice. Cut the abstract halves, keep the concrete
  close ("we put skiers on snow, and even on podiums...").
- **F30 [P2/trim, 3]** Age eligibility stated four times on home in three
  formats; the closed CTA strip ends the page on the orphan "and up." Cut the
  age clause from the strip subhead; normalize "21 - 35" to "21-35".
- **F31 [P2/trim, 5, modified]** Facts-rail rows that restate same-screen
  content: community "Ages 21-35", ETF "Member-organized"/"Year-round" (keep
  "Since 2022"), about "Founded 2020" (keep 501(c)(3) + cities). Delete the
  nav's low-contrast dateline span (`Nav.astro:45-47`), it duplicates the
  mission facts and computes ~4.2:1. Raise the conditions strip "feels N°"
  span to /60+.

## Bundle C · Tracked-caps de-escalation

- **F03 [P1/trim, 6]** The 11px tracked-caps voice appears 9-13 times per
  page: seam labels restating their own headings (three "community" within
  ~60px on home), community group h3s smaller than their body text,
  SeasonsGrid date kickers wrapping two lines of caps on mobile, wax-room
  dates. Keep the hairline seam rule everywhere; delete label text where the
  adjacent h2 names the section; sentence-case the group h3s and date metas.
  Tracked caps stay reserved for LiveConditions + at most one informative
  label per page.
- **F20 [P1/remove, 1]** Dry Tri ROLL/RIDE/RUN figcaptions: type flush against
  the hairline (zero horizontal padding) and the third statement of the trio
  in one viewport. Delete the figcaption row; the photos carry it.

## Bundle D · Copy register repairs

- **F14 [P1/fix, 2]** Greg's bio is grammatically broken (missing article,
  comma splice, "@" in prose, two exclamations). Rewrite with existing facts
  only. Owner question: is "the specialized athletes" the Specialized brand
  team? If unknown, drop the word.
- **F15 [P1/trim, 2]** Sisu lede: three exclamation points, restates the H1,
  "SISU" vs "Sisu" casing drift across three files (owner confirms official
  spelling), "kick-off" as verb, lowercase "slack".
- **F16 [P1/trim, 2]** Racing prose: filler opener, four exclamations, two
  spaced hyphens functioning as em dashes (banned), flourish tails. All
  existing facts retained, register flattened.
- **F21 [P1/trim, 1]** Sponsors intro is leftover Wix caption copy: "highest
  level contributions" goes false when lower tiers populate; "incredibly" is
  a banned intensifier. Trim to one plain sentence.
- **F25 [P1/trim, 1]** Three photo captions violate the cringe list ("Mud
  season delivers.", "Small but mighty.", "Repping across America."). Delete
  the flourish sentence in each, keep the factual half.
- **F32 [P2/fix, 5]** One fact set, three punctuation systems: the city lockup
  renders "Minneapolis · St. Paul" / "Minneapolis / St. Paul" /
  "Minneapolis - St.Paul, Minnesota" (nav vs footer vs contact, first two
  visible simultaneously on every page). Normalize to the middot form,
  unspaced "21-35", "cross-country" throughout.

## Bundle E · Real UX gaps

- **F18 [P1/fix, 2]** MobileNavPanel's spec'd Join CTA slot is never filled:
  on mobile, Register exists only on the home page. Render the existing
  CtaForState into the panel's cta slot at both mount sites. No new copy.
- **F08 [P1/swap, 4]** Footer nav is a verbatim copy of the top nav; zero
  internal links reach /trips, and the Sisu racing row has no href while the
  Dry Tri row does. Decouple the footer list, add Trips (+ ETF/Dry Tri/Contact
  can ride along), add `href` to the Sisu row in racing.mdoc.
- **F05 [P1/fix, 4, modified]** Off-season LiveConditions: dangling "·"
  placeholders at display scale in all four venue cells (renderFailure never
  clears [data-temp]), "Dryland season" repeated four times, doubled empty
  message on mobile. Clear the temp slots; when every venue reports the same
  off-season status collapse to one statement + the Birkie cell, restore the
  grid when data returns. Verifier: do NOT statically hide the prominent
  header on mobile (it would also vanish in season); gate on the off-season
  state instead. This is the signature device in the state it will launch in.
- **F19 [P1/fix, 1, modified]** Navy footer floats above ~135px of raw paper
  on short pages (wax-room, contact, trips, sponsors at 1440x900). One layout
  fix in BaseLayout: `min-h-svh flex flex-col` + grow main. Skip the
  empty-state realignment (standard column; entry seeding makes it moot).

## Bundle F · Page endings (peak-end)

- **F11 [P1/remove, 3]** Community ends on a 14-pill chip cloud where the
  Jessie Diggins meet-and-greet renders at the same weight as "Pickleball".
  Delete the section; move Diggins (and optionally costume relays) into the
  Socials ledger as rows. Mosaic flows into footer; page ends on its proof.
- **F09 [P1/trim, 4, modified]** Coach credential bullets restate the bios
  nearly verbatim for all four coaches. KJ/Greg/Rebecca: keep bullets, cut
  duplicated clauses + filler wind-ups from bios. Michael: inverse, delete his
  bullets so the page ends on "...water skiing, and polka dancing."
- **F17 [P1/trim, 4, modified]** Home mosaic runs 15 of 23 community photos
  (teaser duplicates its destination) and both walls end on ragged half-empty
  rows. Trim show_on_home to the 9 strongest (9 ends flush at BOTH
  breakpoints per the component's sparse layout); drop the single weakest
  community photo so 22 render (9 clean rows of 4). Verify in browser.
- **F24 [P1/add, 2, FACT-GATED]** Sponsors page is a dead end for the sponsor
  audience: no path to act. Owner question: add one plain closing line under
  the wall, "Interested in sponsoring TCSC? Email
  contact@twincitiesskiclub.org."? (mailto, plain body type, no CTA band).
- **F07 [P1/remove, 4]** /contact is unreachable (no nav/footer/content link;
  only the trips empty state points at it, which doesn't render while a trip
  exists) and its entire payload repeats in the footer directly beneath it,
  including the site's only typo'd city lockup. Cleanest cut: delete the page
  and retarget the empty-state link to mailto. If kept: fix lockup, lead with
  the mailto, build meta description from the singleton. OWNER CALL.

## Bundle G · Structure and scale fixes

- **F22 [P1/swap, 2]** Two-sponsor wall stranded in the left half of a 4-col
  grid; square Kwik Trip mark optically dominates the wide TCO lockup. Scale
  the wall to its content (larger logos in a flex row under ~4 items), skip
  the lone tier heading when only one tier renders.
- **F23 [P1/swap, 1]** Sisu facts grid buries $220 at the head of a six-line
  semibold brick. Split cost_summary at the first sentence: three short bold
  facts up top, lodging/meals sentences drop to a full-width regular row.
- **F28 [P2/fix, 2]** Coaches H1 and the four coach-name H2s render at
  identical scale (five same-size display shouts). Drop CoachEntry h2 one
  step to text-3xl md:text-5xl.
- **F29 [P2/fix, 2, modified]** About runs two competing section grammars
  (prose h2 at ~27px vs SectionBand h2 at ~48px, two alignment axes).
  Subtraction first: delete the three one-paragraph h3 subheads in the about
  body; then unify the two h2 grammars (verifier scoped to /about only).

## Confirmed working (do not break)

58 items recorded; highlights: the home hero screen (strongest on the site);
the drenched-navy spine with exactly two paper punctures; the HeroInner
ledger masthead grammar sitewide; the ruled-ledger family (trips table,
What we've done, ETF fixtures, dry-tri course); the off-season Trail Report
voice and Birkie fever cell; Michael's bio as the voice target; the photo
mosaic's content selection; coral scarcity (2 uses on home, 0 inner); the
single-source registration CTA plumbing; mobile nav mechanics (44px targets,
focus trap, reduced motion); the lean pages (sponsors, dry-tri, trip detail)
reading as confident rather than thin; contact's no-form brevity instinct;
the about/racing outbound honesty links.

## Owner decisions needed

1. /contact: delete (footer carries it) or keep + fix? (F07)
2. Sponsor closing line: yes/no on the one fact-gated addition (F24)
3. Coaches anchor index: keep or cut? (F10, reviewers split 2-1 for cut)
4. "Sisu" vs "SISU" official casing (F15); Greg's "specialized" =
   Specialized the brand? (F14)
