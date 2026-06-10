# Marketing site staging QA audit — 2026-06-10

Target: https://tcsc-marketing.onrender.com (Render Static, branch `feat/marketing-site-v2`)
Tooling: headless Playwright chromium (repo venv) + Lighthouse 12 (CHROME_PATH = Playwright chromium 1148), mobile defaults.
Companion: `scripts/wix_scrape/verify.py` (Task 36 migration verifier) exits 0 — all 15 Wix slugs accounted, text coverage 83-134%, 35 manifest rows clean, 22 unported images classified.

Verdict: **go for PR-1.** No blockers found. Four small follow-ups (favicon, /coaches LCP eager-load, compact conditions-strip contrast, /api/conditions CORS) listed at the bottom.

## 1. Route walk — PASS (10/10)

All 10 routes return 200 with expected key content, zero unexpected console errors, zero 404 subresources, zero failed requests.

| Route | Status | Key content | Console errors* | 404 subresources |
|-------|--------|-------------|-----------------|------------------|
| / | 200 | hero headline | 0 | 0 |
| /about | 200 | "About Twin Cities Ski Club" | 0 | 0 |
| /community | 200 | "A welcoming community" | 0 | 0 |
| /racing | 200 | "Twin Cities Ski Club racers" | 0 | 0 |
| /coaches | 200 | KJ bio | 0 | 0 |
| /sponsors | 200 | "Meet our sponsors" | 0 | 0 |
| /contact | 200 | club email | 0 | 0 |
| /trips | 200 | "Sisu Ski Fest" | 0 | 0 |
| /trips/sisu-ski-fest | 200 | "Ironwood" | 0 | 0 |
| /wax-room | 200 | "The Wax Room" | 0 | 0 |

\* Excludes the expected `https://tcsc.ski/api/conditions` failure (3 events/page: CORS block + `net::ERR_FAILED` + requestfailed). LiveConditions correctly degrades to "Conditions unavailable".

Two findings the route walk could not see but Lighthouse did:

- **favicon 404 on every page.** No favicon file in `site/public/` and no `<link rel="icon">` in `BaseLayout.astro`; browsers request `/favicon.ico` → 404 console error (headless Playwright never fetches favicons, so the route walk showed 0). Costs Best Practices points.
- **The conditions failure is a CORS block, not a 404.** `tcsc.ski/api/conditions` (when deployed) must send `Access-Control-Allow-Origin` for the marketing origin — the marketing site stays a different origin even after cutover (twincitiesskiclub.org vs tcsc.ski). Without it, LiveConditions will *never* populate.

## 2. Image audit — PASS (project-critical check)

For every rendered content `<img>` at each page x viewport: rendered CSS width, the srcset candidate actually chosen (resolved by matching `currentSrc` against the `w` descriptors — `naturalWidth` is density-corrected for w-srcsets and unusable), and ratio = chosenW / (cssW x DPR). Flag threshold 0.95.

| Page | Viewport | Imgs | Worst ratio | Under-resolved | At-source-max | No-srcset |
|------|----------|------|-------------|----------------|---------------|-----------|
| / | 390x844@3x | 16 | 1.09 | 0 | 0 | 0 |
| /coaches | 390x844@3x | 3 | 1.09 | 0 | 0 | 0 |
| /community | 390x844@3x | 27 | 1.60 | 0 | 0 | 0 |
| /trips/sisu-ski-fest | 390x844@3x | 1 | 1.09 | 0 | 0 | 0 |
| / | 768x1024@2x | 16 | 0.83 | 1 | 0 | 0 |
| /coaches | 768x1024@2x | 3 | 0.83 | 3 | 0 | 0 |
| /community | 768x1024@2x | 27 | 1.13 | 0 | 0 | 0 |
| /trips/sisu-ski-fest | 768x1024@2x | 1 | 0.83 | 1 | 0 | 0 |
| / | 1440x900@2x | 16 | 0.89 | 0 | 1 | 0 |
| /coaches | 1440x900@2x | 3 | 0.71 | 0 | 3 | 0 |
| /community | 1440x900@2x | 27 | 0.98 | 0 | 0 | 0 |
| /trips/sisu-ski-fest | 1440x900@2x | 1 | 0.89 | 0 | 1 | 0 |
| / | 2560x1440@1x | 16 | 1.00 | 0 | 0 | 0 |
| /coaches | 2560x1440@1x | 3 | 0.80 | 0 | 2 | 0 |
| /community | 2560x1440@1x | 27 | 1.31 | 0 | 0 | 0 |
| /trips/sisu-ski-fest | 2560x1440@1x | 1 | 1.00 | 0 | 0 | 0 |

- **No image lacks a srcset; no image renders from a candidate smaller than another available candidate would warrant by mistake.** The old failure mode (tiny intrinsic source stretched into a big slot) is gone.
- **"Under-resolved" at 768@2x (ratio 0.83) is Chrome's geometric-mean srcset selection**, not a build bug: for a 768px slot at DPR 2 (needs 1536), Chrome picks the 1280w candidate over the available 1920w because sqrt(1.67 x 2.5) > 2 — a deliberate bandwidth heuristic. Safari/Firefox pick 1920w. Candidates exist; nothing to fix.
- **"At-source-max" (ratios 0.71-0.89) = the largest candidate was already chosen** and is capped by the 2560px commit policy or the original photo (coach-greg original is 2048px, coach-kj 2400px). Only fixable with bigger source photos; port-manifest `min_required_w` is satisfied everywhere.
- **Lightbox: PASS.** Clicking a community tile opens the viewer with the 2048w full-resolution candidate (srcset 1024w/1600w/2048w, sizes=100vw) — >= 1600w requirement met; not the grid variant.

## 3. Interaction checks — PASS (all)

Mobile nav at 390px:

| Check | Result |
|-------|--------|
| Skip link present ("Skip to content") | PASS |
| Hamburger opens panel (aria-hidden=false, aria-expanded=true) | PASS |
| Focus lands on close button | PASS |
| Body scroll locked while open (`overflow: hidden`) | PASS |
| Escape closes + focus restored to toggle + scroll restored | PASS |

Lightbox keyboard nav (1440px, /community): ArrowRight advances, ArrowLeft returns, focus opens on Close, Escape closes, focus restored to the invoking tile, scroll restored — all PASS.

aria-current: `/about` marks `a[href="/about"]` with `aria-current="page"` in both the desktop nav and the mobile panel — PASS.

## 4. Reduced motion — PASS

With `prefers-reduced-motion: reduce` emulated on `/`: media query matches, and a sweep of **every element's** computed `transition-duration` and `animation-duration` found **0 elements above 0.01ms** (the global.css kill switch applies universally, hero and overlay included).

## 5. Lighthouse (mobile defaults, Lighthouse 12)

| Category | / | /coaches | Target |
|----------|----|----------|--------|
| Performance | 92 | 93 | >= 95 (missed) |
| Accessibility | 100 | 95 | >= 95 (met) |
| Best Practices | 96 | 96 | >= 95 (met) |
| SEO | 69 | 69 | staging-intentional (see below) |

Metrics: FCP 0.8-0.9s, SI 0.8-0.9s, TBT 0ms, CLS 0, LCP 3.2-3.3s. LCP is the entire performance gap.

Top opportunities/diagnostics:

- **/coaches: the LCP element (first coach portrait) is `loading="lazy"`** (`lcp-lazy-loaded` fails). Eager-loading + `fetchpriority="high"` on the first portrait is the one real perf fix available.
- **/: LCP is the eager hero AVIF at 3.3s** under Lighthouse's throttled-mobile profile; render-blocking CSS costs ~140ms (`/_astro/about.jzLwLkpD.css`). Marginal.
- **/coaches a11y 95: compact LiveConditions strip fails contrast** — `<span data-wax>` is `text-paper/70` (#dfe0e2) on `bg-navy/40` over paper (#9da3ae) = 1.91:1 at 12px (needs 4.5:1). Affects all inner pages (home uses the prominent variant on solid `bg-navy-deep`, which passes — hence 100 on /).
- **Best Practices 96 on both = `errors-in-console`** only: the favicon 404 + the expected conditions CORS error. Both go away with the favicon fix + Flask conditions deploy with CORS.
- **SEO 69 on both = solely `is-crawlable`** (weight ~4): staging intentionally serves `X-Robots-Tag: noindex` (render.yaml) and `robots.txt` Disallow: /. Every other SEO audit passes; at cutover (Task 39 removes both) SEO should score ~100.

## Open items

None blocking PR-1. Follow-ups, roughly in order of value:

1. **Add a favicon** (`site/public/favicon.svg` + `<link rel="icon">` in BaseLayout) — kills a console error on every page, restores Best Practices to 100.
2. **Eager-load the first coach portrait** (`loading="eager"` + `fetchpriority="high"` in coaches.astro / CoachEntry) — fixes `lcp-lazy-loaded`, likely lifts /coaches perf to ~95+.
3. **Fix compact LiveConditions contrast** — darken the strip (e.g. solid `bg-navy-deep` like the prominent variant) or use full-opacity text; restores inner-page a11y to 100.
4. **Flask `/api/conditions` must ship CORS headers** (`Access-Control-Allow-Origin` for the marketing origin) or LiveConditions will stay "Conditions unavailable" forever — the origins differ even after DNS cutover.
5. (Informational) Chrome under-selects srcset candidates at exactly 2x via its geometric-mean heuristic; no action.

## Reproduction

QA scripts (not committed; throwaway, in /tmp/qa during the audit): route walk + console/network capture, srcset-candidate image audit, interaction/reduced-motion checks via Playwright sync API; Lighthouse via `CHROME_PATH=<playwright chromium> npx lighthouse@12 <url> --chrome-flags="--headless=new"`.
Migration verifier: `env/bin/python scripts/wix_scrape/verify.py` (exit 0), tests: `env/bin/pytest tests/wix_scrape -v` (39 passed).
