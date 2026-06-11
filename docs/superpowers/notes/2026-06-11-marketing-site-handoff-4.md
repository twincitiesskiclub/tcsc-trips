# Marketing Site v2 · Polish Session Handoff #4 (2026-06-11, overnight)

Grounding doc for the NEXT session. Supersedes handoff #3
(`2026-06-10-marketing-site-handoff-3.md`); the ORIGINAL handoff's **§2
cutover runbook, §3 decision log, and §4 cross-session gotchas remain
authoritative** (`2026-06-10-marketing-site-handoff.md`).

## Where things stand

| Item | Value |
|---|---|
| Branch | `feat/marketing-site-v2` (pushed; this session = polish pass #4) |
| Worktree | `/Users/rob/env/tcsc-trips-site` (venv `env/`, Playwright + Pillow) |
| Staging | https://tcsc-marketing.onrender.com |
| Pages | **11** (was 12): `/contact` retired, redirect `/contact -> /` in render.yaml |
| PR-1 | Still NOT opened; gated on Rob sign-off of staging |
| Verification | `astro check` 0 errors; build green; `python -m scripts.wix_scrape.verify` exit 0 |

## What landed this session (do not re-litigate)

Polish pass #4: a 52-agent critique (19 reviewers, 152 raw findings, merged
to 32, every one adversarially verified) followed by full implementation.
Rob approved scope "everything" plus four decisions: delete /contact, add
the sponsor closing line, cut the coaches anchor index, normalize to "Sisu
Ski Fest". Full findings list with file:line:
`docs/superpowers/notes/2026-06-10-polish-pass-4-critique.md`.

The shape was subtraction-first: 22 of 32 items were remove/trim; net diff
across 52 files was negative.

1. **Arrows (F01).** "→" removed sitewide: home CTA strip, TripEntry "Sign
   up", wax-room "Read" links (deleted entirely), TripsTable hover arrow +
   its grid track, and the open-state CTA label in home.yaml /
   registrationCta.ts / both config defaults. The hero stays plain; the
   site now has ZERO decorative arrows (lightbox controls excepted). Do not
   reintroduce.
2. **Say-it-once cuts.** Home Practices band heading deleted (seam + season
   cells carry it; SeasonsGrid gained a headingLevel prop, h2 on home, h3
   on about). SeasonsGrid dues sentence + shared coaching/practices line
   hoisted to render once per band; season yamls keep only unique bullets.
   Racing's Birkie stat now appears twice not three times. Trips "Next up"
   masthead facts deleted. Coaches subhead (meta-only now), count fact, and
   anchor index deleted. Community intro cut to one paragraph. About mission
   de-duplicated; founding story moved from masthead to body lede. Age
   eligibility on home cut from 4 statements to 2.
3. **Tracked-caps de-escalation (F03).** Seam labels deleted where the
   adjacent h2 names the section (home Community + Wax Room). Community
   ledger group h3s are sentence-case navy semibold. SeasonsGrid date
   kickers and wax-room dates are sentence-case slate. Tracked caps remain:
   LiveConditions strip, seam labels that ARE the section name (Practices,
   Club record), eyebrow on trip detail.
4. **Voice repairs.** Greg's bio rewritten (was grammatically broken; the
   ambiguous word "specialized" was DROPPED, ask Rob if it meant the brand).
   Sisu lede rewritten plain (was 3 exclamation points). Racing prose
   flattened, spaced-hyphen dashes removed. Sponsors intro replaced.
   3 photo captions de-flourished. KJ/Rebecca bios trimmed to net-new story;
   Michael's credentials bullets deleted so the page ends on polka dancing.
5. **UX fixes.** MobileNavPanel now gets the Register CTA (both mounts:
   index.astro + InnerPageLayout). Footer nav decoupled from top nav: two
   columns covering all 9 destinations incl. Trips/ETF/Dry Tri. Sisu racing
   row now links to the trip page. BaseLayout sticky-footer fix
   (min-h-svh flex flex-col + flex-1 main). Sponsors page: content-scaled
   logo wall (<4 logos = larger flex row), lone tier heading suppressed,
   closing line "Interested in sponsoring TCSC? Email contact@...".
6. **LiveConditions off-season treatment (F05).** renderFailure clears
   [data-temp] (no dangling middots), collapses the four venue cells to one
   statement when off-season (prominent: the stamp carries it; compact: one
   injected "Dryland season" label, desktop-only), restores the grid on the
   next successful render. **Gotcha found live: the compact cells carry a
   `flex` class, so `el.hidden` does nothing; hide/show uses inline
   `style.display`.** The injected label is `max-md:hidden` so mobile keeps
   the single Birkie line.
7. **Photos (F17).** show_on_home trimmed 15 -> 9 (flush grid at both
   breakpoints). `recess-ski.yaml` deleted from the community wall (22
   render, even rows); the image asset and its CONSENT.md line remain.
8. **/contact retired (F07, Rob's call).** Page + singleton deleted from
   content.config.ts AND keystatic.config.ts (mirror discipline). Footer/
   BaseLayout hardcode email + Instagram as canonical. render.yaml
   redirects /contact -> /. verify.py: contact moved to REDIRECT_SLUGS.
   TripsTable empty state links mailto: now.
9. **Punctuation normalized (F32).** "Minneapolis · St. Paul" everywhere,
   "21-35" unspaced everywhere, date ranges "September-March" / "May-August",
   "Tuesday · Thursday", sign-up (noun) / sign up (verb), "Sisu Ski Fest"
   casing everywhere.

## Open items for the next round

1. **KJ headshot swap (still open; Rob sourcing).** Unchanged procedure from
   handoff #3 item 1.
2. **Nav decision (Rob's call, still open).** Top nav holds 6; the footer
   now covers all 9 destinations, which lowers the pressure, but whether
   Trips/ETF/Dry Tri earn top-nav slots is still Rob's.
3. **Fact-gated items (need Rob's words):** mission-panel manifesto rewrite
   at display scale; per-coach micro-records; member names in captions
   (board-gated). Plus: was Greg's "specialized athletes" the Specialized
   brand team? (word currently dropped).
4. **Dry Tri registration flip (this summer).** Unchanged from handoff #3
   item 4.
5. **Backlog still open:** mosaic event_tag filter UI; Lighthouse 92-93 vs
   95 (re-measure after this pass; hero unchanged); seed one real wax-room
   entry pre-launch; BlurHash (only if scroll-in feels flat).
6. **Consent gate (HARD, pre-cutover):** unchanged from handoff #3 item 6.
   Note recess-ski was removed from the site but stays consented/on-disk.
7. **Future-dated copy:** unchanged list from handoff #3 item 7.
8. **about prose-h2 scale:** F29 was resolved with weight/voice only
   ([&_h2] semibold tracking-tight on the prose wrapper). If the two-grammar
   tension still bothers at review, the next step would be sizing prose h2s
   up one step, not moving the band.

## Operational gotchas (new this session)

- **`el.hidden` vs Tailwind display classes:** any element carrying `flex`/
  `grid` classes ignores the hidden attribute (author styles beat the UA
  [hidden] rule). Use inline `style.display`. Bit us on LiveConditions
  compact cells; screenshots looked right on prominent and wrong on compact.
- **Critique artifacts:** survey screenshots + slices + detector output under
  `migration/survey-2026-06-10/` (gitignored), before/after sets. Impeccable
  critique snapshot in `.impeccable/critique/` (gitignored). Screenshot
  capture script: `scripts/survey_screenshots_v2.py` (handles lazy-image
  scroll; slices to 2000px segments for review).
- **wix_scrape verify accounting:** a deleted page must move its slug in
  `scripts/wix_scrape/verify.py` (CONTENT_MAP -> REDIRECT_SLUGS with a
  render.yaml route, or WAIVED with a reason) or verify fails.
- **SeasonsGrid hoisted copy:** the dues sentence and the shared
  practices/coaches line are component-hardcoded (rendered once per band).
  If season content changes in Keystatic, check those lines still read true.

## Verification commands

```bash
cd /Users/rob/env/tcsc-trips-site/site
npx astro check                      # 0 errors expected
NODE_ENV=production npx astro build  # 11 pages; wax_entries notices are known
cd /Users/rob/env/tcsc-trips-site
source env/bin/activate
python -m scripts.wix_scrape.verify  # exit 0, 34 manifest rows
```
