# Marketing Site v2 · Polish Session Handoff #2 (2026-06-10, end of day)

Grounding doc for the NEXT polish session. Supersedes the polish-backlog
section of `2026-06-10-marketing-site-handoff.md`; that doc's **§2 cutover
runbook, §3 decision log, and §4 cross-session gotchas remain authoritative**
and are not repeated here.

## Where things stand

| Item | Value |
|---|---|
| Branch | `feat/marketing-site-v2` @ `360d11f` (pushed; today's polish = `00541ac..360d11f`, 16 commits) |
| Worktree | `/Users/rob/env/tcsc-trips-site` (venv `env/`, Python 3.13, Playwright + Pillow + full app deps) |
| Staging | https://tcsc-marketing.onrender.com (auto-deploys the branch) |
| PR-1 | Still NOT opened; gated on Rob sign-off of staging |
| Verification | `astro check` 0 errors; build green (only the known empty `wax_entries` notices); `pytest tests/conditions tests/wix_scrape` 71/71; `python -m scripts.wix_scrape.verify` exit 0 |
| Rob's standing verdict | Three passes in, the generic/soulless complaints are addressed structurally; remaining items below are his explicit asks + fact-gated leftovers |

## What landed today (so you don't re-litigate it)

Three structured passes plus live iteration with Rob:

1. **Impeccable pass** (`00541ac..475089f`): no public Slack links (CTAs →
   tcsc.ski), original-Wix voice ported per `migration/copy-voice-audit.md`,
   Inter → self-hosted **Archivo Variable** (width axis = display cut; the
   swap point comments moved accordingly), nav lockup, conditions strip
   craft (wax-band color chips = literal wax color), mission panel as
   full-bleed paper band, coaches at constrained 4:5 (masks soft sources),
   new hero photo + photos sourced from Slack.
2. **Pass 2** (`e33a101`): mosaic pool replaced with **23 recent (2025-26)
   member photos** in a season arc with flat field-note captions (Wix-era 27
   retired; verify.py classifies them `superseded-2026-06`); **coach Michael
   Symanski** added (bio via Slack search, photo self-posted); trips as
   typeset list; soul-debate workflow outputs (wax logbook grammar, dues
   line, honest closed-state subhead, footer photo credit).
3. **UI/UX structural pass** (`b40ac96`, from the second fable-vs-opus
   debate; diagnosis: color did all the sectioning, one hero shape on five
   pages, thin pages exposed the skeleton, conditions buried, zero response
   to the reader): conditions strip under the nav everywhere + dateline
   stamp; HeroInner = ruled two-cell ledger masthead with per-page static
   `facts`; Wax Room feed = paper band (renders its empty state, giving home
   the navy/paper rhythm); trips ledger with column headers; **seam device**
   (section name in Trail Report label voice + hairline to the right edge,
   reworked once in `28160ad` after Rob flagged the original swatch-on-line
   as a square jut); coaches all-left + ruled roster index; full-bleed
   mosaic; mobile nav ease-in; single page-load entrance (group fade,
   `data-filled` flag, reduced-motion safe).
4. **Rob's live edits** (`410d6b1..360d11f`): nav corner = "TCSC"; CTAs =
   "Register" → https://tcsc.ski (root, not /register); venues = **Theo /
   Elm / Hyland / Telemark**; **Birkie fever thermometer** (98.6° no fever →
   104° full-blown; statuses in `app/conditions/birkie.py`, slugs stable)
   with the **Birkie Fever song easter egg** (cell is a button, ♪ turns
   coral while playing, `site/public/audio/birkie-fever.mp3`, lazy Audio);
   hero = "Twin Cities Ski Club" at display scale + factual subline (the
   podiums/bank bookend was cringe, retired); CTA strip = "Come ski with
   us."; off-season cells say "Dryland season"; **mobile strips collapse to
   the Birkie fever cell only** (venue cells are md+); 2025 → 2026 Birkie
   stats sitewide; "four dedicated coaches"; winter season notes its
   Christmas break; Wax Room empty state is just "No entries yet."

## Open items for the next session

1. **KJ headshot swap (imminent: Rob is sourcing the photo now).** When it
   arrives: ImageOps.exif_transpose → resize to 2560px longest edge → save
   `site/src/assets/images/coaches/coach-kj.jpg` (quality=90, progressive)
   → update `photo_alt` in `src/content/coaches/kj.mdoc` → add a
   port-manifest.csv row (slot `coach`, min 1200) and a CONSENT.md line, or
   verify.py fails. The 4:5 attention-crop slot is forgiving.
2. **Fact-gated debate items (need Rob's words, never invent):**
   mission-panel manifesto rewrite at display scale; per-coach micro-records
   (go-to wax / home trail / coldest practice led); member names in photo
   captions (board-gated, post re-confirmation).
3. **Original backlog still open:** mosaic `event_tag` filter UI on
   /community (data-tag hooks exist); Lighthouse perf 92-93 vs 95 target
   (hero LCP); seed one real wax-room entry pre-launch; Trips/Contact nav
   discoverability; BlurHash (skipped, revisit only if scroll-in feels flat).
4. **Conditions/Flask:** the venue + fever changes ride this branch's Flask
   side and reach production only with PR-1. Until then staging shows the
   client fallback (now a feature: Dryland season / 98.6°). The
   klister-at-80°F seasonal gate on live data is still deferred; an
   AppConfig editorial override for the fever status is sketched in
   `app/conditions/birkie.py`'s docstring.
5. **Consent gate (HARD, pre-cutover):** every image on the site is now
   Slack-sourced and was never on the public web; `migration/CONSENT.md` is
   the system of record and the board re-confirmation must call this out.
   Pro race-gallery photos (brockit / official Birkie) must stay excluded.

## New operational gotchas (beyond the prior handoff's §4)

- **Photo pipeline:** `scripts/slack_photo_pull.py` (1886 images +
  reaction-ranked manifest in gitignored `migration/slack_photos/`),
  `scripts/photo_contact_sheet.py` for triage sheets,
  `scripts/survey_{screenshots,sections}.py` for viewport surveys. Every
  committed image needs a port-manifest.csv row (slot + min width) or
  `python -m scripts.wix_scrape.verify` fails; retired images need a
  classification entry in `scripts/wix_scrape/verify.py`.
- **Slack:** `SLACK_USER_TOKEN` can call `search.messages` (how Michael's
  bio was found); the bot token cannot search and is only in ~30 channels.
  Don't join channels with the bot (visible in the live workspace).
- **Render deploy verification:** poll for a marker string that only the
  NEW build contains (or the old build's removal), never a loose pattern; a
  sloppy poll once reported a deploy live while staging still served the
  old build, and Rob caught it.
- **Audio:** MP3 over AAC on purpose (Playwright's Chromium lacks AAC; MP3
  decodes everywhere). The fever cell creates its Audio element on first
  click only.
- **Seam device:** label + hairline on one baseline, same voice as the
  TRAIL REPORT header. Do not reintroduce the translate-y swatch that cuts
  the rule; Rob explicitly rejected it.
- **Voice tripwires from today:** Rob reads "AI-ish" fast: no invented
  warmth ("winter people"), no completed-sentence cleverness held across
  sections (the bookend died), no over-explained datelines ("usually around
  Thanksgiving" got cut). Plain, factual, club-register lines win. Em
  dashes never.
