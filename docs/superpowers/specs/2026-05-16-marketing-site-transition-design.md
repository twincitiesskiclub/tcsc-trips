# TCSC Marketing Site — Wix → Astro Transition

**Status:** Design (awaiting review)
**Date:** 2026-05-16
**Owner:** Rob
**Companion docs:** [`PRODUCT.md`](../../../PRODUCT.md) (strategy, users, anti-references, design principles) · [`DESIGN.md`](../../../DESIGN.md) (color tokens, typography, components, motion). This spec covers _what we're building_; those two cover _why_ and _how it looks_.

## Summary

Migrate `twincitiesskiclub.org` off Wix into a new Astro static site living at `/site` in the `tcsc-trips` repo. Use Keystatic as a typed content layer, edited primarily through a Slack agent (separate project) and secondarily through Keystatic local mode. Deploy to Render Static as a separate service so the existing Flask app at `tcsc.ski` is unaffected. Design: drenched navy on the home page (with photographs as the bright spots), paper-default on inner pages, single sans family + one display cut. The signature device is **Live Conditions** — current temperature + wax recommendation at four Twin Cities ski areas, sourced from the existing Flask Skipper integrations. The home page links into **The Wax Room**, a dated editorial publication section run by coaches and members.

## Goals

- Take full ownership of the marketing site (off vendor lock-in).
- Make non-developer content edits easy: board members message a Slack agent; agent commits typed, schema-validated changes to GitHub; Render auto-deploys.
- Make the site visibly better than the Wix incumbent — brand-committed, editorial, photography-first, with one signature interaction. Avoid the generic "AI-templated" look.
- Strong service isolation from the Flask app: separate `npm` project, separate Render service, separate domain.
- Preserve all existing content, voice, and images from the Wix site.

## Non-goals

- Replacing or modifying the Flask registration / practices / admin app at `tcsc.ski`.
- Building the Slack content-editing agent (separate project; this spec only guarantees the content model is agent-friendly).
- Member portal, login, paid features, e-commerce. Marketing only.
- Reworking the IA / sitemap from scratch — this is a lift-and-shift-and-elevate.

## Stack

| Layer | Choice | Why |
|---|---|---|
| Framework | **Astro 5** | Best-in-class static marketing-site SSG. Ships zero JS by default. Tailwind v3/v4 first-class. Content Collections give typed Markdown/MDX. |
| Styling | **Tailwind CSS + Tailwind UI / Plus** (paid library Rob has access to) | Component scaffolding speed, design tokens, painless theming. |
| CMS | **Keystatic** (local mode for Rob; schema is the contract for the Slack agent) | Typed schema in `keystatic.config.ts`. Content stays as Markdown/YAML in the repo — no vendor dependency. Keystatic's hosted GitHub mode is not used; the Slack agent handles board-member edits directly via GitHub API. |
| Live data | **Fetch from Flask app endpoints** | Live Conditions strip pulls from a new `/api/conditions` JSON endpoint on the Flask app (reusing existing Skipper NWS + SkinnySkI integrations). Static site fetches client-side; cached 5 minutes. No GSAP, no scroll-driven animation in this version. |
| Hosting | **Render Static Site** | Already on Render for the Flask app; same dashboard / billing. Auto-deploys on git push. Free for static. |
| Domain | `twincitiesskiclub.org` (and `www.` redirect) | DNS cutover from Wix to Render. |
| Fonts | Self-hosted **Fraunces** (display, variable, Google Fonts) + **Inter** (body & UI, variable). No second display family, no mono font. | One paired type system, used confidently. Detail in `DESIGN.md`. If TCSC ever licenses GT Sectra, that's an in-place swap. |

## Repo & service architecture

```
tcsc-trips/
├── app/                  # existing Flask app (UNTOUCHED)
├── site/                 # NEW: Astro marketing site
│   ├── astro.config.mjs
│   ├── keystatic.config.ts
│   ├── package.json      # separate npm project from root package.json
│   ├── tailwind.config.ts
│   ├── content/          # Markdown/YAML content (Keystatic-managed)
│   │   ├── pages/        # home.yaml, about.md, community.md, racing.md, sponsors.md, contact.yaml
│   │   ├── coaches/      # kj.md, greg.md, rebecca.md
│   │   ├── photos/       # photo wall entries with captions + tags
│   │   ├── trips/        # sisu-ski-fest.md, ...
│   │   └── sponsors/
│   ├── public/           # images, fonts, favicons
│   └── src/
│       ├── components/   # TCSC-themed: Nav, Hero, SectionBand, CoachCard, PhotoMosaic, SkiTracks, CTAStrip, Footer
│       ├── layouts/
│       ├── pages/        # one .astro file per route
│       └── styles/
├── migration/            # NEW: one-time scrape output, kept in repo as audit trail
│   ├── pages/
│   ├── images/
│   └── inventory.md
├── scripts/
│   └── scrape_wix.py     # NEW: Playwright-based Wix scraper (Phase 0)
└── docs/superpowers/specs/2026-05-16-marketing-site-transition-design.md
```

**Isolation guarantees:**

- Different language / runtime (Node vs. Python). No shared dependencies.
- Different build (`cd site && npm run build` vs. Flask app's Procfile).
- Different Render service, different domain.
- A breaking change in `/site` cannot break `tcsc.ski`, and vice versa.

## Visual system

The complete visual system — color tokens (OKLCH), typography scale, component library, motion rules, banned patterns — lives in [`DESIGN.md`](../../DESIGN.md). Strategic context (users, voice, anti-references, design principles) lives in [`PRODUCT.md`](../../PRODUCT.md). This spec doesn't duplicate them.

For engineering reference, the component inventory we'll build in `site/src/components/`:

| Component | Purpose |
|---|---|
| `<Nav>` | Navy top bar; logo; section links desktop / hamburger mobile; primary CTA reads `registration_state` |
| `<LiveConditions>` | **The signature device.** Four-column strip showing current temp + recommended wax range at Theodore Wirth, Hyland, French Park, Battle Creek. Fetched from Flask `/api/conditions`. Prominent on home; compact form in footer on inner pages. (See Signature device section below.) |
| `<MobileNavPanel>` | Full-screen navy panel; 24px links; Live Conditions strip pinned top; Join CTA pinned bottom |
| `<Hero>` (home) | Full-bleed photograph behind headline; sparse-photo fallback to typography-on-navy |
| `<Hero>` (inner) | Paper hero with ink display H1 and a navy ruled line below |
| `<SectionBand>` | Navy / paper / paper-on-navy variants; takes optional numbered marker, heading, slot. Eyebrow labels NOT default. |
| `<MissionPanel>` | Paper card embedded in the drenched-navy home page; the single paper moment before the page returns to navy |
| `<SeasonsGrid>` | Two-up seasons detail; not card-shaped; navy variant uses mint headings, paper variant uses ink |
| `<PhotoMosaic>` | Asymmetric tile grid; hover/lightbox; sparse-content fallback. On home, photos sit as paper-on-navy moments |
| `<CoachEntry>` | Full-bleed photo + display-size name typeset below; pull quote in body. **Not a card.** Stacks on `/coaches` |
| `<TripEntry>` | Editorial trip layout: photo, dates, location, lede, structured details. No card frame. |
| `<TripsTable>` | Typeset table on `/trips` (date, name, location, sign-up status) |
| `<SponsorWall>` | Logo wall on `/sponsors`; tiered, not tiled |
| `<WaxRoomFeed>` | Home-page teaser: three most recent wax room entries with date, title, one-line excerpt |
| `<WaxEntry>` | A single wax room post: editorial layout on paper |
| `<CTAStrip>` | Navy; coral 3px top border; one mint heading + one mint CTA |
| `<Footer>` | Three columns; compact Live Conditions at top |

### Signature device — Live Conditions

Replaces the abstract scroll-driven ski-track motif from the previous spec revision. **The site's "signature" is data + a brand point of view, not a vector flourish.**

- Four locations: Theodore Wirth, Hyland, French Park, Battle Creek.
- For each: current temp, wind chill, snow conditions (from SkinnySkI), recommended glide-wax color band:

| Temp band | Recommendation |
|---|---|
| < 14°F | Green wax · cold snow |
| 14–28°F | Blue wax · firm snow |
| 28–32°F | Purple · transition snow |
| 32°F + | Red wax · klister conditions |

- **Source:** new endpoint `GET /api/conditions` on the existing Flask app, reusing the integrations in `app/integrations/weather.py` and `app/integrations/trail_conditions.py` (both already exist for Skipper). Returns a JSON array of four location objects. Cached 5 minutes server-side. CORS-enabled for the marketing site origin only.
- **Client:** the Astro static site fetches client-side on page load (no SSR coupling); revalidates every 5 minutes if the page is open. Sparse data / API failure → "Conditions unavailable" message; never broken.
- **Accessibility:** ARIA live region announces material wax-band transitions (e.g., temperature crosses 32°F).

This is the single most TCSC-specific element on the site. It's the answer to "what could a competitor not copy in a weekend."

### Photo mosaic specifics

- 4-col desktop / 2-col mobile. Tile sizes 1×1, 2×1, 2×2; ~70/25/5 mix.
- **Home placement:** 15-photo asymmetric band (not a teaser). `show_on_home` boolean on each photo determines membership.
- **/community placement:** full archive. Filterable by `event_tag`.
- Hover overlay (desktop): navy at 70% opacity, caption + tag pill, 150ms fade.
- Lightbox: keyboard ←/→/Esc, mobile swipe; hard-cut transitions, no slide.
- Lazy-loaded; BlurHash placeholders; Astro-generated `srcset` (AVIF+WebP).
- **Sparse content:** under 12 photos, mosaic collapses to a uniform 3-col grid (no asymmetry). 0 photos → section omitted entirely.
- **Photo consent:** required schema field `photo_consent_recorded: boolean`. Editors confirm consent at upload time. No image renders without it (CI fails).

## Content model (Keystatic schema)

**Singletons** (one document each):

| Slug | Path | Notable fields |
|---|---|---|
| `home` | `site/content/pages/home.yaml` | Hero eyebrow, headline, subhead, primary/secondary CTAs, season-status banner text, photo-mosaic teaser count |
| `about` | `site/content/pages/about.md` | Founding story (markdoc), who-joins cards (array of 3), practices summary |
| `community` | `site/content/pages/community.md` | Inclusivity statement, team-bonding activities (array of strings), CTA |
| `racing` | `site/content/pages/racing.md` | Intro, races list (array of name + date + role), Birkie callout, Techno Corner mention |
| `sponsors_page` | `site/content/pages/sponsors.md` | Tier intros |
| `contact` | `site/content/pages/contact.yaml` | Email, mailing address, socials |

**Collections** (repeating items):

| Slug | Path | Fields |
|---|---|---|
| `coaches` | `site/content/coaches/*.md` | `name`, `role`, `photo` (image w/ required alt), `bio` (markdoc), `credentials` (array) |
| `practice_seasons` | `site/content/practice_seasons/*.yaml` | `name`, `date_range`, `fee_cents`, `summary`, `what_included` (array) |
| `trips` | `site/content/trips/*.md` | `name`, `location`, `dates`, `cost_summary`, `signup_deadline`, `capacity`, `what_to_expect` (markdoc), `refund_policy`, `signup_url` (external link → Flask app) |
| `photos` | `site/content/photos/*.yaml` | `image` (with required `alt`), `caption`, `event_tag`, `member_names` (array, optional), `order`, `show_on_home` (bool), `photo_consent_recorded` (bool, required true to render) |
| `sponsors` | `site/content/sponsors/*.yaml` | `name`, `logo`, `tier` ("trailblazer" / other), `url` |
| `wax_entries` | `site/content/wax_entries/*.md` | `date` (required), `title`, `author_name`, `author_role` (coach / member / board), `lede`, `body` (markdoc), optional `photo`, optional `conditions_snapshot` (location + temp + wax used). Powers `/wax-room`. |

**Global / settings:**

- `nav` — top nav links + footer link groups.
- `site_meta` — site title, default SEO, social handles, contact email, OG image.
- `registration_state` — one of `open` / `coming_soon` / `closed`. Drives the hero CTA, top-nav CTA, and CTA strip in lockstep. Editors flip this in Keystatic at season transitions; everything else stays in source control.

**Schema-as-contract for the Slack agent:** the agent reads `keystatic.config.ts`, sees that `practice_seasons` has a `fee_cents` integer field, and can update only that field. It cannot invent new fields or break validation. PRs that fail schema validation fail CI and never merge.

## Editing workflow

1. **Slack agent (primary, board members).** Board member DMs the agent: _"change Fall/Winter fee to $215"_ or _"add Maya as a member voice"_. Agent reads schema, edits the relevant file, opens a PR, replies in Slack with the diff + PR link. Merge → Render auto-deploys in ~60s.
   - Image uploads attached to Slack → agent uploads to `site/public/photos/` and adds a `photos/` entry.
2. **Keystatic local (developer mode).** `cd site && npm run dev`, visit `/keystatic`, web UI for any edit. Saves to files; you commit/push. Used for bigger edits, image management, anything that benefits from preview.
3. **Direct git.** Code and component changes only.

The Slack agent itself is **out of scope** for this spec. This design guarantees the content model is agent-friendly:

- Small, scoped files (one entity per file).
- Typed schema (Keystatic ensures field validation).
- All edits are git commits with full attribution.
- Broken edits fail CI and never reach production.

## Pages & sitemap

All copy lifted from the current Wix site verbatim. Voice stays; design elevates.

| Route | Source page (Wix) | Notable design |
|---|---|---|
| `/` | `/` (home) | **Drenched navy throughout.** In order: (1) Nav + Live Conditions strip pinned below it; (2) **Hero with full-bleed photograph** (real Birkie / practice / community moment), headline in mint, single primary CTA reading `registration_state`; (3) Mission paragraph as a paper card embedded in the navy page (the single paper puncture before the photo mosaic); (4) Two seasons practices grid (`<SeasonsGrid>` navy variant, mint headings); (5) **Real 15-photo asymmetric mosaic** — photos sit as paper-on-navy framings; (6) **Wax Room teaser feed** (`<WaxRoomFeed>`) — three most-recent entries; (7) Sponsor + get-involved band → coral-bordered CTA close. Coaches do NOT appear on the home. |
| `/about` | `/about` | Editorial paper section intro; "Who joins TCSC" 3-up; practices detail (2 cards w/ fee badges); coaches teaser |
| `/community` | `/community` | Inclusivity statement; **full photo mosaic** is the centerpiece; team-bonding activities as a tag/chip list; Slack link |
| `/racing` | `/racing` | Navy hero; race list (Sisu, Prebirkie, Birkie, Great Bear Chase, Tour de Finn); Birkie 2025 callout ("80+ skiers, every wave"); Techno Corner section |
| `/coaches` | `/coaches` | Three coach cards (KJ, Greg, Rebecca) with real photos and expandable bios |
| `/sponsors` | `/sponsors` | Tiered sponsor grid; "Trailblazer level" hero treatment |
| `/contact` | `/contact` | Email, social, mailing address. Optional simple mailto form (no backend) |
| `/trips/sisu-ski-fest` | `/sisu-information` | Editorial trip layout — drives all future trip marketing pages. CTA → registration app on `tcsc.ski` |
| `/wax-room` (NEW) | (none — net-new section) | Editorial publication: dated entries from coaches + members. Wax recommendations, condition reports, race-day prep, technique notes. List view (newest first) + detail pages. Edited via Keystatic + Slack agent. The "this is a serious club run by serious people" proof for sponsors. |

**Top nav:** About · Community · Racing · Coaches · Wax Room · Sponsors · **Join the club** (CTA → registration in Flask app).

**Out of scope** (these were Wix forms, now in the Flask app): `/register`, `/copy-of-register`, `/sisu-signup`, `/trip-sign-up`, `/trip-confirmation`, `/confirmation`, `/trip-information`.

**Redirects (configured on Render):**

| From | To |
|---|---|
| `/register` | `https://tcsc.ski/register/...` |
| `/sisu-signup` | `https://tcsc.ski/trips/sisu-ski-fest` (or the live registration URL) |
| `/trip-sign-up` | `https://tcsc.ski/trips` |
| `/trip-information`, `/trip-confirmation`, `/confirmation`, `/copy-of-register` | `/` with a query param the homepage can detect to display a small "this form is now at tcsc.ski" notice |

## Flask app dependency: `/api/conditions`

The Live Conditions signature device requires one (small) addition to the existing Flask app: a public JSON endpoint that exposes current weather + trail conditions for the four locations.

- **Route:** `GET /api/conditions`
- **Implementation:** new blueprint or addition to `app/routes/main.py`; reuses `app/integrations/weather.py` (NWS) and `app/integrations/trail_conditions.py` (SkinnySkI). Both are already used by Skipper.
- **Response shape:**
  ```json
  {
    "updated_at": "2026-05-16T15:32:00-05:00",
    "locations": [
      {
        "id": "wirth",
        "name": "Theodore Wirth",
        "temp_f": 28,
        "wind_chill_f": 22,
        "snow_conditions": "firm",
        "wax_band": "purple",
        "wax_label": "Purple · transition snow"
      },
      // ...3 more
    ]
  }
  ```
- **Caching:** 5-minute server-side cache (in-process or Redis). NWS rate limits are forgiving but we batch.
- **CORS:** Allow `https://twincitiesskiclub.org` only.
- **Failure mode:** if upstream APIs fail, return 200 with `"temp_f": null` per location and a top-level `"error": "upstream unavailable"`. Front-end renders "Conditions unavailable" gracefully.

This is the only Flask-side change required by the marketing site. It's strictly additive and doesn't modify any existing route.

## UX edges (codified before implementation, not after)

These are the year-round-correctness commitments. The site must render correctly under all of them.

### Mobile navigation

- Top bar: logo on left; "Join the club" CTA in the middle position (always visible); hamburger on right.
- Tap hamburger → full-screen navy panel slides in (200ms ease-out-quint).
- Panel: 24px link list, mint ski-track motif faintly in the background, "Join the club" CTA pinned to the bottom of the panel as the primary action.
- Closes on link tap, Esc key, or tap outside the link list.
- No bottom nav bar. No floating-action button. Just hamburger.

### Seasonal CTA state (driven by `registration_state` in Keystatic)

| State | Hero CTA | Top-nav CTA | CTA strip close |
|---|---|---|---|
| `open` | "Register for [season] →" → `tcsc.ski/register/...` | "Join the club" | "Ready to find your winter people?" + Register button |
| `coming_soon` | "[Season] registration opens [date]" (display-only) | "Coming soon" (disabled visual) | "Get on the list" → Slack invite or mailing list |
| `closed` | "Members only — already in?" → member resources/Slack | "Member area" | (Optional) hidden or replaced with a sponsor invitation |

Editors flip the state field in Keystatic; all three locations update on next deploy.

### Empty / sparse states

- **Coaches page:** renders 1–N coaches in a responsive grid (not hard-coded 3). Heading adapts: "Our coach" / "Our two coaches" / "Our coaches".
- **Trips page:** zero upcoming trips → "No trips currently scheduled — sign up for the Slack to hear about new trips first" with a single link, not a blank grid.
- **Photo mosaic:** see spec above; < 12 photos → uniform 3-col grid; 0 photos → section omitted.
- **Sponsors page:** tiers with no sponsors do not render empty headings.

### SEO / metadata

- Per-page `<title>`, `<meta description>`, `og:image`, `og:title`, `og:description` — all Keystatic-managed (singleton + collection-level fields).
- Values seeded from the Wix scrape in Phase 1.
- Astro auto-generates `sitemap.xml` at build.
- Single JSON-LD `SportsOrganization` block in the site head: name, logo, address, contact email, founder, `sameAs` (socials). Improves Google's understanding of what the site is for sponsor / donor search.

### Analytics — deferred

PostHog wiring is intentionally NOT in this spec. Will be added in a later pass. Until then, the site ships clean (no third-party scripts, GDPR-trivial).

### Performance budget

- First Contentful Paint < 1.5s on 4G.
- Total JS on home < 35KB gzipped (Astro default ≈ 0 + GSAP ScrollTrigger only on home/about ≈ 18KB + a small lightbox script).
- All images responsive (`srcset`) with AVIF + WebP fallbacks, BlurHash placeholders for mosaic.
- Fonts self-hosted with `font-display: swap`; preload Fraunces 700 + Inter 400 on every page.

## Migration plan

### Phase 0 — Full Wix scrape (before any Astro code)

Script: `scripts/scrape_wix.py` (Python + Playwright; Wix renders client-side, plain `curl` is insufficient).

Outputs to `migration/`:

```
migration/
├── pages/
│   ├── home.html          # fully rendered HTML for reference
│   ├── home.txt           # extracted visible text
│   ├── home.json          # structured: { title, sections[], links[], image_refs[] }
│   └── ...                # one set per sitemap URL
├── images/                # every image downloaded, renamed by page + sequence
│   ├── logo-main.png
│   ├── logo-mark.png
│   ├── home-hero-1.jpg
│   ├── coaches-kj.jpg
│   └── ...
├── images.csv             # image_url → local_filename → page → alt_text (from <img alt>)
├── links.csv              # outbound links found
└── inventory.md           # human-readable: per page, every heading, every image count, every CTA
```

Scrape steps:

1. Read `https://www.twincitiesskiclub.org/pages-sitemap.xml`; gather all page URLs.
2. For each URL: launch Playwright, wait for network idle, expand any accordions / tabs by clicking common Wix expander selectors, then capture rendered DOM.
3. Extract:
   - Visible text, preserving heading structure (H1/H2/H3) and section boundaries.
   - All `<img src>` and CSS `background-image` URLs; prefer the largest available variant on the Wix CDN.
   - All outbound links.
   - Any embedded `<iframe>` / `<video>` / social embeds.
   - Per-page `<title>`, `<meta name="description">`, OG image.
4. Download every unique image to `migration/images/`. Rename meaningfully (`<page>-<sequence>.<ext>`).
5. Write `inventory.md` — the **completeness checklist**.

`migration/` is checked into the repo as an audit trail (gitignored only if it's too large; otherwise kept).

### Phase 1 — Port content into Keystatic

For each Wix page, a developer (or eventually the Slack agent) reads the migration JSON and creates the corresponding Keystatic content file in `site/content/`. Images copied into `site/public/photos/` (community) or `site/public/images/` (page-specific). Each port = a git commit referencing the inventory line item.

### Phase 2 — Build the Astro site

With content in place, build components and pages. The design system (above) drives all page work. Each page is an `.astro` file in `site/src/pages/`. Layouts, components, and content collections wired together.

### Phase 3 — Verification before cutover

A second pass through `inventory.md` confirming nothing was dropped:

- Every image in `migration/images.csv` has a counterpart in `site/public/` (verification script).
- Every section heading from the original Wix page exists in the new content, or has a documented reason for merger / removal.
- Text-length sanity: if a new page has < 70% of the original's word count, flag for review.
- Manual click-through pass on staging URL by Rob + at least one board member.

### Phase 4 — Domain cutover

1. New Render Static service deployed at `tcsc-marketing.onrender.com` (or chosen staging URL) with all content + redirects in place.
2. QA pass on staging.
3. Update DNS: switch `twincitiesskiclub.org` apex from Wix to Render (A/AAAA or CNAME flattening); set `www.twincitiesskiclub.org` to redirect to apex.
4. Verify HTTPS cert issuance on Render.
5. Confirm redirects from old form URLs → Flask app at `tcsc.ski` are working.
6. Monitor traffic logs for 7 days.
7. Cancel Wix subscription only after a clean 7-day window.

### Things the scrape may miss — manual checks

- PDF documents linked from any page (race calendars, waivers).
- Wix Forms submission destinations (moot since forms are removed, but worth confirming).
- Anything behind member-only / password-protected pages (sitemap shows none).
- Favicon and `apple-touch-icon` variants — captured separately from `<link rel="icon">` tags.
- Social embeds (Instagram, etc.) — preserve via OEmbed or replace with curated photos in the mosaic.

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Wix scrape misses dynamic content (accordions, tabs) | Use Playwright (not curl); script clicks common Wix expander selectors before capture; manual review of `inventory.md` against live Wix site before scrape is considered complete |
| DNS cutover causes downtime | Stage on `tcsc-marketing.onrender.com` first; cutover during low-traffic hours; keep Wix subscription active for 7 days after cutover for instant rollback |
| Slack agent makes a bad edit | Schema validation enforced; failed validation fails CI; all changes are git commits and revertable; PRs (rather than direct commits) gate the most sensitive collections (e.g., `practice_seasons`, `sponsors`) |
| Board members don't adopt the Slack-agent workflow | Keystatic local mode is still available; Rob can edit on their behalf; UI is good enough that direct GitHub edit via web UI also works in a pinch |
| Photo mosaic feels empty at launch | Seed with ~30 photos from existing club archive during Phase 1; mosaic gracefully handles 8–80 photos via grid auto-flow |
| Design feels "AI-templated" anyway | Design rules section codifies anti-generic moves; design pass with external tool planned before implementation |

## Open questions

- _None._ Strategy, visual system, IA, content model, migration, and UX edge cases all resolved in the brainstorming and `impeccable` passes. The remaining external visual-design pass (user-driven) will refine surface details but should not invalidate decisions captured in `DESIGN.md`.

## Next steps

1. User reviews this spec, `PRODUCT.md`, and `DESIGN.md`.
2. (Optional) external design-tool pass on visual details.
3. Implementation plan written via `writing-plans` skill — sequenced as Phase 0 (scrape) → Phase 1 (content port) → Phase 2 (build) → Phase 3 (verify) → Phase 4 (cutover).
