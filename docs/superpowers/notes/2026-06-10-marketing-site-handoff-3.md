# Marketing Site v2 · Polish Session Handoff #3 (2026-06-10, night)

> **Status update (2026-07-10):** Club leadership confirmed full publication
> consent for the current site photos and a production PolySans web license.
> The related pre-cutover gates below are historical and closed;
> `migration/CONSENT.md` is the current photo-consent record.

Grounding doc for the NEXT polish round. Supersedes handoff #2 and its
bolted-on addendums (`2026-06-10-marketing-site-handoff-2.md`); the ORIGINAL
handoff's **§2 cutover runbook, §3 decision log, and §4 cross-session
gotchas remain authoritative** (`2026-06-10-marketing-site-handoff.md`) and
are not repeated here.

## Where things stand

| Item | Value |
|---|---|
| Branch | `feat/marketing-site-v2` @ `751114f` (pushed; this session = `8b5892e..751114f`, 6 commits) |
| Worktree | `/Users/rob/env/tcsc-trips-site` (venv `env/`, Python 3.13, Playwright + Pillow + full app deps) |
| Staging | https://tcsc-marketing.onrender.com (auto-deploys the branch; all deploys this session verified by strict marker) |
| Pages | 12 (was 10): added `/extra-training-fun` and `/dry-tri` |
| PR-1 | Still NOT opened; gated on Rob sign-off of staging |
| Verification | `astro check` 0 errors; build green (known empty `wax_entries` notices only); `python -m scripts.wix_scrape.verify` exit 0 (35 manifest rows) |
| Rob's review state | Reviewed the three new surfaces live; two correction rounds (voice sweep, display type) both landed and deployed |

## What landed this session (do not re-litigate)

1. **Content pass** (`8b5892e`): /community "What we've done" ledger
   (takeaways field: Volunteering / Members who coach / Socials, SectionBand
   seam "Club record"); new `/extra-training-fun` (standing fixtures navy
   band, annuals paper band, two pool photos); new `/dry-tri` (Roll/Ride/Run
   triptych, 2025 course ledger, year-one recap, 2026 status); racing rows
   gained optional `href` (Dry Tri row links). One new consented image
   (`dry-tri-roller.jpg`). All claims mined from Slack and audited; opus
   review pass applied before push.
2. **Voice sweep** (`7ce304e`): Rob flagged "cringe" constructions; full
   sweep applied. The pattern (also in memory `feedback_site_copy_voice.md`):
   no punchline fragments ("That is the whole system."), no quote-setup
   devices ("put it plainly"), no flourishes bolted onto facts ("top to
   bottom"), no dramatized details ("within the hour"), no paired open/close
   cleverness, no anthropomorphizing ("Late October delivered"), no "X means
   Y" constructions. Plain club register, the original Wix site is the
   reference. Em dashes never (standing rule). **Pickleball Sundays was
   removed: it looked evidenced in Slack but is not a real fixture. Verify
   standing-fixture claims with Rob.**
3. **Display type fix** (`0e5fe06`): the 125% expanded Archivo display cut
   is RETIRED (Rob: "squished and too big at the same time"). Display voice
   is now weight-led: `.font-display` = normal width + -0.02em tracking,
   every display heading carries `font-semibold`, home hero stepped bold →
   semibold. Decided against on-page specimens of Hanken Grotesk / Space
   Grotesk / Bricolage Grotesque; Rob chose keeping Archivo. **Do not
   reintroduce `font-stretch` on `.font-display`.** PolySans remains the
   commercial upgrade path at the documented swap points. Deliberately left
   at 400: the MissionPanel manifesto paragraph (prose-scale, not a
   heading). Dry Tri page says 2026 registration opens this summer (Rob
   confirmed).

## Open items for this round

1. **KJ headshot swap (still open; Rob was sourcing).** The committed
   `coach-kj.jpg` is unchanged since the original port and is soft /
   AI-upscaled at source. When the new photo arrives:
   ImageOps.exif_transpose → resize 2560px longest edge → save
   `site/src/assets/images/coaches/coach-kj.jpg` (quality=90, progressive)
   → update `photo_alt` in `src/content/coaches/kj.mdoc` → port-manifest.csv
   row (slot `coach_photo`, min 1200) + CONSENT.md line, or verify.py fails.
2. **Nav decision (Rob's call).** Top nav holds the spec'd 6 links; 8
   overflow at md. `/extra-training-fun` and `/dry-tri` are cross-linked
   only (community ledger, racing row, mutual links). Decide whether either
   earns a slot; same question still open for Trips and Contact.
3. **Fact-gated debate items (need Rob's words, never invent):**
   mission-panel manifesto rewrite at display scale; per-coach
   micro-records (go-to wax / home trail / coldest practice led); member
   names in photo captions (board-gated, post re-confirmation).
4. **Dry Tri registration flip (this summer).** When 2026 reg opens:
   update the dry_tri singleton (`register_url`, the "## 2026" body
   paragraph), and note tcsc.ski/tri (Flask, main repo
   `app/templates/dryland-triathlon.html`) still shows the 2025 event and
   needs its own update. Results URL is the 2025 race; swap after the 2026
   edition runs.
5. **Original backlog still open:** mosaic `event_tag` filter UI on
   /community (data-tag hooks exist); Lighthouse perf 92-93 vs 95 target
   (hero LCP; re-measure after the type change, semibold may shift it
   slightly); seed one real wax-room entry pre-launch; BlurHash (revisit
   only if scroll-in feels flat).
6. **Consent gate (HARD, pre-cutover):** all images Slack-sourced, never
   public-web. `migration/CONSENT.md` is the system of record and now
   carries a **public-event caveat for the three Dry Tri photos**
   (participants may be non-members). Board re-confirmation must cover
   this explicitly. Pro race-gallery photos stay excluded.
7. **Future-dated copy to refresh next season:** "Wooden Hill in 2026"
   (community socials row), "Third annual in 2025" (TCSC Classic row),
   "Since 2022" hero fact on /extra-training-fun, the dry_tri 2026
   paragraph and URLs.
8. **Conditions/Flask:** unchanged from handoff #1/#2; venue + Birkie fever
   changes reach production only with PR-1; staging shows the client
   fallback (Dryland season / 98.6°) until then.

## Operational gotchas (new since the original handoff's §4)

- **Evidence base for all new copy:** `migration/slack_facts/` (gitignored,
  member names inside). Raw channel extracts + five audited fact-sheet
  JSONs; each sheet's `cautions` array lists what must NOT be claimed (no
  rain on race day, no sold-out language, no attendance from reaction
  counts, no member discount codes, Track Club is not club-official).
  Re-extraction pattern: `scripts/extract_channel_history.py` (main repo).
- **announcements-general migration artifact:** lines stamped
  [2026-05-11 17:4x] with [bot:NAME] authors are re-posted history; real
  dates are inside the message text. Anything "current" sourced from that
  channel needs a native (non-bot) timestamp.
- **Render deploy verification (re-confirmed):** poll a strict marker only
  the new build can serve. This session: a new route returning 200 with its
  headline, then a copy string, then `font-stretch:100%` inside the hashed
  CSS bundle. Deploys take ~2-5 min; a 404/old-string loop with sleep 20 is
  fine.
- **Playwright full-page screenshots miss lazy images:** scroll through the
  page (stepwise scrollTo) before capturing, or below-the-fold `<Image
  loading="lazy">` renders as blank space with floating captions.
- **Tabulator-style two-file mirror discipline applies to content models:**
  every schema change lands twice, `site/src/content.config.ts` (zod,
  `.strict()`) AND `site/keystatic.config.ts`, with identical field names.
  New singletons this session: `extra_training`, `dry_tri`; community
  gained `takeaways`; racing races gained `href`.
- **Page photos come from the consent-cleared pool** (`src/assets/images/
  photos/`), referenced by relative path from the singleton frontmatter;
  the Keystatic image fields for the new singletons point at the pool
  directory on purpose. Reuse beats re-importing: rider/runner/track/
  rollerski shots were already consented, only the roll leg was new.

## Verification commands

```bash
cd /Users/rob/env/tcsc-trips-site/site
npx astro check                      # 0 errors expected
NODE_ENV=production npx astro build  # 12 pages; wax_entries notices are known
cd /Users/rob/env/tcsc-trips-site
source env/bin/activate
python -m scripts.wix_scrape.verify  # exit 0, 35 manifest rows
```
