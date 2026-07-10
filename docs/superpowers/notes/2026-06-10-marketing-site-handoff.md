# Marketing Site v2 · Session Handoff (2026-06-10)

> **Status update (2026-07-10):** Club leadership confirmed full publication
> consent for the current site photos and a production PolySans web license.
> The related pre-cutover gates below are historical and closed;
> `migration/CONSENT.md` is the current photo-consent record.

Grounding doc for the next session: polish pass, cutover to live, and the decision log from the subagent-driven execution of `docs/superpowers/plans/2026-05-16-marketing-site-transition.md`.

## Where things stand

| Item | Value |
|---|---|
| Branch | `feat/marketing-site-v2` (pushed; 54+ commits over `main` @ 9fd7501) |
| Worktree | `/Users/rob/env/tcsc-trips-site` (main checkout untouched) |
| Staging | https://tcsc-marketing.onrender.com (Render static `tcsc-marketing`, srv-d8kglm0jo6nc73fhpg20, auto-deploys the branch) |
| Old attempt | local branch `feat/marketing-site` (never pushed); kept as reference, do not resurrect its scrape code |
| PR-1 | NOT yet opened; gated on Rob sign-off of staging. Body drafted (see final review summary). |
| PR-2 (DNS cutover) | Not started, by design |
| QA baseline | `docs/superpowers/notes/2026-06-10-marketing-site-staging-qa.md` (route walk, 4-viewport image audit, Lighthouse, interactions; all follow-ups resolved in `49146d9`) |
| Verification | `astro check` 0 errors; production build green (10 pages); `pytest tests/conditions tests/wix_scrape` 64/64; migration verifier (`python -m scripts.wix_scrape.verify`) exit 0 |

The media failure from the first attempt is closed: scrape fetches true Wix originals (strip everything from `/v1/`), all content images run through astro:assets (srcset, AVIF/WebP, intrinsic dims, server-side crops), per-slot minimums enforced and audited in `migration/port-manifest.csv`, and the staging image audit found zero under-resolved images at 390@3x / 768@2x / 1440@2x / 2560@1x.

## 1 · Polish pass backlog

**Update (2026-06-10, /impeccable polish pass, later session):** the holistic pass landed. Done since this doc was written: Inter replaced with self-hosted Archivo Variable (width axis = display cut; Inter was the project's own anti-reference); copy ported to original-site voice via `migration/copy-voice-audit.md` (home hero/CTA strip now bookend the club's own "skiers on snow / without breaking the bank" sentence); all public Slack links removed (CTAs are state-aware and point at tcsc.ski/register, "Member area" label gone); nav lockup + location detail; conditions strip reworked (header row with live stamp, server-rendered venue names, wind chill when material, wax-band color chips, quieter failure state); mission card became a full-bleed paper band with org-facts column; coaches went from full-bleed 21:9 to alternating 4:5 editorial splits (masks the soft sources); new hero photo + 6 mosaic photos sourced from Slack #photos-videos (puller: `scripts/slack_photo_pull.py`, 1886 images + reaction-ranked manifest in gitignored `migration/slack_photos/`; contact sheets: `scripts/photo_contact_sheet.py`). **Consent attention:** the 7 Slack-sourced images were never on the public web; they're listed separately in `migration/CONSENT.md` and must be called out in the board re-confirmation (runbook step 4). Pro race-gallery photos in the channel were excluded on rights grounds. KJ's fresh-portrait content ask still stands.

**Update 2 (2026-06-10, pass 2, commit e33a101):** photo pool fully replaced with 23 recent (2025-26) member photos hand-sequenced as a season arc with flat field-note captions (Wix-era photos retired; verify.py classifies them 'superseded-2026-06'); coach Michael Symanski added (strength coach; bio sourced via Slack search, photo from his own post); conditions venues now Theo Wirth / Elm Creek / Hyland Nordic / Double OO plus a Birkie-likelihood fifth cell (`app/conditions/birkie.py`; Flask side ships with PR-1); CTAs read "Register" and point at https://tcsc.ski; nav corner reverted to "TCSC"; trips index reworked as a typeset row-link list; a fable-vs-opus debate workflow produced the soul update set, of which these shipped: Wax Room logbook grammar, dues transparency line under season fees, off-season member-voice in the conditions failure state, de-eyebrowed coach roles, honest closed-state registration subhead, footer photo credit. **Still needs Rob's input (debate items gated on real facts):** (1) mission-panel manifesto rewrite at display scale, (2) per-coach micro-records (go-to wax, home trail, coldest practice led), (3) member-name photo captions after board re-confirmation.

Everything below is non-blocking. Reviewed and consciously deferred, ordered roughly by value.

### Visual / UX
- **Design polish pass with `/impeccable`** on the staging URL. Nothing has had a holistic visual pass yet; per-phase reviews were correctness-focused. Candidates: hero scrim tuning with the real photo at 1440px+, mosaic rhythm, inner-page typographic detail.
- **Live Conditions strip, richer display**: wind_chill_f and snow_conditions are already in the API payload but not rendered. Adding them (esp. in winter) strengthens the signature device. Also consider a seasonal gate (the strip faithfully recommends klister at 80°F in June).
- **Community mosaic tag filter**: spec calls for filtering by event_tag on /community; `data-tag` hooks are already on every tile, no filter UI yet.
- **CTAStrip label is hardcoded** "Become a member →" regardless of registration_state; make label + URL state-aware together (URL already is).
- **"Our two coaches" heading variant**: only the 1-coach singular is special-cased; 2 coaches reads "Our coaches".
- **Trips + Contact discoverability**: both pages exist but are not in the top nav (spec'd 6 links). Decide whether Trips earns a nav slot or a home-page section link.
- **Lighthouse perf 92-93 (target 95)**: remaining gap is hero LCP 3.2-3.3s on staging. Options: preload the hero image, lighter AVIF quality, or accept (Render CDN + real-world caching may already clear it).
- **Seed one real wax-room entry** before launch so the feed, detail page, and og:image path are exercised in production (collection is empty; everything renders empty states correctly).
- **BlurHash placeholders** (spec wishlist) were skipped in favor of plain lazy loading; revisit only if scroll-in feels flat.

### Content asks
- **KJ's photo**: source (2400x2400) is visibly soft/AI-upscaled. Request a fresh portrait; Greg/Rebecca are crisp.
- **site_meta description** keeps the live site's "programing" spelling verbatim; fix if desired (one Keystatic edit).
- **registration_state** is `closed`; flip in Keystatic when season registration opens (drives hero CTA, nav CTA, CTA strip in lockstep).
- Sponsors page has exactly 2 sponsors (TCO, Kwik Trip), matching the live Wix site; add others when logos exist.

### Code hygiene (rule-of-three watch)
- `Prose.astro` extraction (the prose wrapper is duplicated 4x across inner pages).
- Shared `trapFocus()` once a third overlay appears (MobileNavPanel + Lightbox currently mirror each other deliberately).
- If a page ever mounts BOTH LiveConditions variants, dedupe the sr announcer (one per page assumption documented in the component).
- `/api/conditions` cold-start: concurrent first requests each build the body (rare, once per worker); fold into the scheduler+AppConfig snapshot architecture if it ever matters.

## 2 · Cutover to live (runbook)

Order matters. The plan's Task 39 / PR-2 covers steps 4-9.

1. **Rob signs off on staging** → open PR-1 (`feat/marketing-site-v2` → main; body already drafted in the final review).
2. **Merge PR-1.** This deploys the Flask side (`/api/conditions` + CORS allowlist incl. the staging origin) with the normal app deploy. Verify: `curl https://tcsc.ski/api/conditions` returns JSON; the staging site's conditions strip populates.
3. **Switch the Render static service branch** `feat/marketing-site-v2` → `main` (render.yaml comment marks this), confirm a clean deploy, then let staging soak ≥24h.
4. **Board photo-consent re-confirmation** per `migration/CONSENT.md` (27 photos, republished-from-public-Wix basis). Hard gate; remediation path is flipping `photo_consent_recorded: false` on any photo, which removes it from every mosaic.
5. **Render dashboard actions** (cannot be set via API; checklist also at the bottom of `render.yaml`):
   - Add the 8 redirect rules (Dashboard → Redirects/Rewrites). Render Static does NOT read `_redirects` files. Rules: /register, /copy-of-register → tcsc.ski/register; /sisu-signup → tcsc.ski/trips/sisu-ski-fest; /trip-sign-up → tcsc.ski/trips; /sisu-information → /trips/sisu-ski-fest; /trip-information → /trips; /trip-confirmation, /confirmation → /.
   - Remove the X-Robots-Tag noindex header if one was added.
6. **Cutover PR (PR-2)**: restore `site/public/robots.txt` to Allow + Sitemap (the current file's comment header preserves the exact lines); note Render's CDN caches robots.txt ~5 min.
7. **Custom domains**: Render → tcsc-marketing → add `twincitiesskiclub.org` + `www.twincitiesskiclub.org`; update DNS at the registrar per Render's records. Cloudflare gray-cloud (DNS only) until the Render cert is confirmed. Low-traffic hours.
8. **Verify**: site loads with valid cert; all 8 redirects fire; `x-robots-tag` noindex appears on the onrender.com alias once the custom domain verifies; submit sitemap in Search Console (optional).
9. **Keep Wix active 7 days** for instant rollback; monitor Render traffic logs; cancel Wix only after a clean week. Document the cancel-after date in PR-2.

Post-cutover: `PUBLIC_CONDITIONS_API_URL` stays default (https://tcsc.ski/api/conditions); never set NODE_ENV on the static service (devDependencies needed at build).

## 3 · Decision log

Decisions made during this session, with rationale. Revisit deliberately or not at all.

| Decision | Rationale |
|---|---|
| Fresh re-execution from current main (v2 branch) instead of fixing the old `feat/marketing-site` | Old branch built from stale main and carried the low-res media systemically (scrape + content + components); root-causing showed the fix had to start at the scraper |
| Scrape fix: `original_wix_url()` strips everything from `/v1/` | The old `re.sub(r'/v1/fill/w_\d+', ...)` left `,h_NN` constraints so the CDN kept serving thumbnails; bare media URL returns the original (200x200 → 2048x2048 proven) |
| All content images through astro:assets (`src/assets` + `image()` schema), not `public/` strings | public/ bypasses sharp entirely (no srcset/AVIF/dims); spec's perf budget requires responsive images; existence checks + dimensions for free. og image is the one public/ exception (stable URL) |
| Committed asset cap 2560px longest edge; per-slot minimums (hero ≥1920, coach ≥1200, trip ≥1600, mosaic ≥800); no upscaling ever | Max rendition is 2048w; Astro copies originals into dist; keeps git/dist lean at zero quality cost. Audited in port-manifest.csv, enforced by verify.py |
| Photo consent: 27 photos marked consented on republished-from-public-Wix basis | They were already publicly displayed on the club site. Board re-confirmation gated before cutover; system of record is `migration/CONSENT.md` because Keystatic deletes YAML comments on save |
| Inter Variable self-hosted; PolySans deferred | PolySans free trial is a manual browser download; plan sanctioned the fallback. Swap point documented in tailwind.config.ts + global.css |
| `/api/conditions` rebuilt as stale-serve + daemon-thread refresh (not the plan's in-request locked rebuild) | A hanging NWS/SkinnySkI upstream could otherwise block gunicorn workers that serve registration/payments for minutes |
| Canonical SkinnySkI venue names ('Hyland Lake Park Reserve' etc.), not slugs | Fuzzy matcher scored de-slugged 'hyland park' higher against St. Paul's 'Highland Park' (0.83) than the correct venue (0.63); canonical names kill the trap (0.54, below threshold) |
| Tailwind tokens gained `/ <alpha-value>` | Without it, Tailwind 3.4 silently dropped every opacity-modifier class (lightbox backdrop, hover overlays, hairlines) since Phase A |
| mint-deep darkened to oklch(0.52 0.13 155); DESIGN.md contrast table corrected | Measured 4.37:1 on paper (DESIGN.md falsely claimed 5.2:1); 0.52 gives 4.95:1 paper / 4.74:1 paper-card |
| Dates pinned to UTC via `src/lib/formatDate.ts` | YAML dates parse as UTC midnight; US Central local formatting shifted them a day |
| `order` int fields on trips/practice_seasons/sponsors; photos use gapped ordering (10, 20, 30) | Display order must not be hostage to filename alphabetics; gaps make future inserts cheap. Photo orders are tile-aware (panoramas on wide tiles, the one portrait on a square) |
| Redirects live in `render.yaml` routes; `site/public/_redirects` deleted | Render Static does not read `_redirects` (plan assumption was wrong); the file would have shipped as misleading junk. Render redirects are dashboard-applied for API-created services |
| Staging robots.txt = Disallow all | The API-created service couldn't get the noindex header; bare onrender.com sites are otherwise indexable duplicate content. Cutover PR restores Allow |
| Staging origin added to Flask CORS allowlist | So the conditions strip works on staging once PR-1 deploys; production origins (apex + www) were already allowed; Vary: Origin unconditional (cache-poison fix) |
| Verbatim voice with three disclosed trims | Live-site wording preferred over plan drafts everywhere; only mechanical typo fixes (ACTIVITES, a trailing '..'), straight-quote normalization, and removal of body headings duplicated by structured frontmatter sections |
| Keystatic admin + react dev-gated (NODE_ENV) | Astro 5 removed 'hybrid'; production dist stays purely static, zero JS shipped except the three small inline scripts (~2.1KB gzip on home vs 35KB budget) |
| Consciously out of scope | Slack editing agent, PostHog analytics, BlurHash, scroll animation/GSAP, wind-chill display, mosaic tag filter UI, DNS cutover |

## 4 · Cross-session gotchas (operational)

- Always work in the worktree `/Users/rob/env/tcsc-trips-site`; its venv is `env/` (Python 3.13, has Playwright + chromium + Pillow + full app deps).
- pytest: explicit paths only (`pytest tests/conditions tests/wix_scrape`), never bare `pytest` (prod-DB import footgun in scripts/).
- Deleting content entries locally needs an Astro content-cache clear (`rm -rf site/node_modules/.astro`) or builds reference ghosts.
- `migration/images/` (160MB originals) is gitignored but on disk in the worktree; `images.csv` + `port-manifest.csv` are the committed audit trail and allow re-download.
- The contract docs are the headers of `site/src/content.config.ts` and `site/keystatic.config.ts` (entry.id vs data.slug, image path shapes, strict mirrors) and `site/src/components/imageWidths.ts` (never pre-filter widths; Astro clamps and appends intrinsic; always pass explicit clamped `width`).
