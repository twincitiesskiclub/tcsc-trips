# Design

Visual system for the TCSC marketing site (Astro + Tailwind, under `/site` in this repo). Brand identity is fixed (navy + mint + coral pink); this document codifies how that identity expresses on the web.

This is the second pass of `DESIGN.md`. The first pass landed in the editorial-heritage-outdoor reflex lane (Fraunces + Inter + uppercase tracked eyebrows + paper-tinted-warm + alternating-band rhythm). The impeccable critique flagged it. This rewrite commits in the opposite direction: drenched navy on the home page, no serif anywhere, one sans family used with conviction, and one genuinely TCSC-specific live device (current ski conditions + wax recommendation) replacing what was an abstract decorative ski-track scroll motif.

## Theme

Two physical scenes the site has to read for:

- A Twin Cities resident considering joining, opening the site on a Tuesday evening in October — laptop on a kitchen table, warm lamp light, half-attending while making dinner.
- A sponsor opening it the next morning on a 27-inch monitor in a downtown Minneapolis office, daylight, in a tab next to three other club sites.

The site reads warmly to scene one and crisp to scene two through *commitment to navy*, not through paper alternation. Drenched navy on the home page mirrors the actual experience of Minnesota Nordic skiing — dark months, bright snow, photographs as the moments of light. Inner pages (about, racing, sponsors, the wax room) shift to paper-default for long-form reading.

No theme toggle. Not "dark mode." Not "light mode with hero strips." One site, two registers chosen by surface.

## Color

**Strategy: Drenched on the home page; Committed on inner pages.**

- **Home page** is drenched navy from nav to footer. Photographs (in `<PhotoMosaic>`, `<Hero>`, the wax room feed) are the only paper appearances — paper exists *inside* photo frames, as the bright spots in a dark vessel. Mint becomes the structural reading color on navy, not an accent. Coral is the live/energy punctuation.
- **Inner pages** (`/about`, `/racing`, `/coaches`, `/sponsors`, `/contact`, `/wax-room`, trip detail pages) default to paper. Navy bands appear deliberately for hero strips and section punctuation, not as alternating rhythm. The wax room in particular leans editorial-on-paper because long-form reading is the point.

Colors expressed in OKLCH, tinted faintly toward the brand hue to avoid pure-white/pure-black flatness. Tailwind tokens defined in `tailwind.config.ts`.

| Token | OKLCH | Hex (reference) | Use |
|---|---|---|---|
| `navy` | `oklch(0.25 0.06 260)` | `#202A44` | The home page surface (drenched). Hero strips, footer, and navy bands on inner pages. |
| `navy-deep` | `oklch(0.18 0.05 260)` | derived | Slightly darker navy — used for navy-on-navy elevation in the live conditions strip and nav. Subtle. |
| `mint` | `oklch(0.91 0.12 155)` | `#AAF0C1` | On navy: primary reading color for headings, key body text, primary CTA fills, the brand-mark ski tracks in the logo. On paper: not used directly (too pale); use `mint-deep` for legibility. |
| `mint-deep` | `oklch(0.55 0.13 155)` | derived | The accessible mint for text/links on paper. Pairs with paper at ≥4.5:1. |
| `coral` | `oklch(0.74 0.16 15)` | `#FF8FA3` | Energy accent. Live indicators (the green dot is mint; the pink dot is coral and means "now / current / open"). Section punctuation. CTA close strip top border. ≤4 uses per page. |
| `paper` | `oklch(0.985 0.003 90)` | near-white, faintly warm | Inner-page surface. Tinted faintly warm (sand direction) — but not "tinted toward sand because heritage." Tinted because pure white on a sport-club site reads clinical. |
| `paper-card` | `oklch(0.97 0.004 90)` | slightly darker paper | Embedded content on paper sections (a wax room entry preview, a coach card if needed). Difference is barely visible. |
| `ink` | `oklch(0.18 0.04 260)` | near-black, navy-tinted | Body text on paper. |
| `slate` | `oklch(0.50 0.02 260)` | mid-gray, navy-tinted | Secondary body on paper. Captions, dates, meta. |

**Banned in this design:**

- `#000` / `#fff`. Use `ink` / `paper`.
- Gradients for decoration. There is no SVG ski-track scroll motif in this version, so the previous exception is gone.
- Gradient text. Period.
- More than three accent colors per surface. On navy: mint + coral + paper-inside-frames is the limit. On paper: mint-deep + coral + navy is the limit.
- Soft-tinted gray cards on paper. If a card needs definition, give it a 1px ink-15% rule or a clear background, not a gray drop-shadowed slab.

## Typography

**One sans family, one weird display cut. No serif anywhere. No mono.**

The brief is warm/sporty/inclusive with Tracksmith × Patagonia DNA. Tracksmith isn't a serif brand at heart — their wordmark is custom and their workhorse is a grotesque. Patagonia's marketing uses Founders Grotesk. Both prove that "outdoor heritage warmth" lives in *photography, voice, and color choices*, not in the type. So we drop the serif, drop the editorial-magazine reflex with it, and let one well-chosen sans family carry weight contrast and personality.

### Choice

- **Body, UI, eyebrows, captions: a neo-grotesque with humanist warmth.** Production preference: **Söhne Buch** (Klim Type Foundry, commercial license). Free fallback for prototyping or for shipping without a license budget: **PolySans Median** (Pangram Pangram, free tier). Both have multiple optical cuts and weights and read well at small sizes. Neither is on impeccable's reflex-reject list.
- **Display moments only (wordmark area + H1 on home hero + the Wax Room masthead): a wider, more characterful cut from the same family.** With Söhne: **Söhne Breit** (the wider, more architectural cut — same foundry, same family). With PolySans: **PolySans Wide** in heavy weight, or substitute **Migra** (Pangram Pangram, paid but affordable) for a more distinctive display moment. The display cut is used at most 2–3 places per page; everything else is the body family.
- **No second family. No serif. No mono.** If a label needs to feel "tech / live data," use Söhne Buch in small caps with letter-spacing, not a mono font. Mono is reserved for genuine code or terminal contexts, neither of which appear on this site.
- **Eyebrow / kicker labels are NOT a default section grammar.** The previous spec used eyebrows on every section band; impeccable's brand register bans that pattern. In this revision, eyebrow labels appear **at most twice per page**, and only where they carry information (e.g., "01 — Mission" numbered sections, or "Live · Updated 3 min ago" on the conditions strip). They are not decoration.

### Scale (fluid via `clamp()`)

Modular ratio 1.333 for body to H3; jumps wider at display sizes for confidence.

| Role | Mobile | Desktop | Line height | Weight | Family |
|---|---|---|---|---|---|
| Display H1 (home hero) | 3.0rem | 6.0rem | 0.95 | 800 | Display cut |
| Display H1 (inner pages) | 2.5rem | 4.5rem | 1.0 | 700 | Display cut |
| H2 | 2.0rem | 3.0rem | 1.05 | 700 | Body family |
| H3 | 1.375rem | 1.625rem | 1.2 | 600 | Body family |
| H4 | 1.125rem | 1.125rem | 1.3 | 600 | Body family |
| Body L (lede) | 1.125rem | 1.25rem | 1.55 | 400 | Body family |
| Body M | 1.0rem | 1.0625rem | 1.65 | 400 | Body family |
| Caption / meta | 0.875rem | 0.875rem | 1.45 | 400, slate | Body family |
| Numbered section marker | 0.875rem | 1.0rem | 1.0 | 600, letter-spaced 0.04em | Body family |

- Body line length capped at **62ch on paper**, **56ch on navy** (light type on dark reads as lighter weight; tighter measure compensates).
- Light type on navy gets `+0.05` line-height bonus to body sizes (Inter/Söhne render denser when reversed).
- Numbered section markers ("01", "02") replace the previous uppercase-tracked-eyebrow pattern when navigation aid is needed.

## Layout

- **Grid:** 12-col with `clamp(1rem, 4vw, 2rem)` page gutter. Max content width 1280px on home (the photo mosaic needs room); 1080px on inner pages (long-form prefers tighter measure).
- **Vertical rhythm:** sections breathe variably (96–144px y-padding on home, 64–104px on inner). Same-spacing-everywhere is monotony.
- **Asymmetric defaults.** Two-up grids prefer 7/5 or 5/7 splits rather than 6/6. The photo mosaic itself is asymmetric (mixed 1×1, 2×1, 2×2 tiles).
- **No card-grid reflex.** Cards are used where they're truly the best affordance — sponsors as a logo wall (not tiles), trips as a typeset table on the trips index (not a 3-up card grid), coaches as full-bleed long-scroll editorial entries (not 3-up cards).
- **No nested cards. Ever.**
- **The home page has no card grid at all.** Every section is full-bleed-on-navy or a deliberate photographic puncture.

## Components

Built in `site/src/components/`. Each takes typed props; story-doc'd inline.

| Component | Purpose | Notes |
|---|---|---|
| `<Nav>` | Top navigation | Navy bar. Logo (mint ski-tracks + "TCSC" lockup). Section links inline desktop; hamburger mobile. Primary CTA reads `registration_state`. Live conditions strip sits directly under the nav. |
| `<LiveConditions>` | **The signature device.** A slim horizontal strip showing current temp + recommended wax range at four Twin Cities ski areas (Theodore Wirth, Hyland, French Park, Battle Creek). Built on the existing Flask Skipper NWS integration. Wax recommendation logic keyed to temperature bands (cold / cool / warm / klister). Updates on page load; small "Live · updated 3 min ago" indicator. Displayed prominently on the home page, secondary placement in the footer on inner pages. **This is what a competitor couldn't copy in a weekend.** |
| `<MobileNavPanel>` | Full-screen mobile nav | Navy panel, 24px links, Join CTA pinned bottom. Live conditions strip pinned to the top of the panel. |
| `<Hero>` (home) | Home hero | **Full-bleed photograph** behind the headline. Real candid photo — Birkie wave start, post-practice gathering, breath-fog moment. Headline set in mint over a navy-gradient bottom-vignette for legibility (gradient is functional, not decorative). Single primary CTA. Sparse-photo fallback: solid navy with the display H1 set huge in mint. |
| `<Hero>` (inner) | Inner-page hero | Paper background, ink display H1, slim navy ruled line below. No image (the page below has plenty). |
| `<SectionBand>` | Wraps a content block | Variants: `navy`, `paper`, `paper-on-navy` (paper card embedded in a navy page — used sparingly on home for the mission paragraph). Takes optional numbered marker ("01 / Mission"), heading, optional subhead, children. **Eyebrow labels are not the default.** |
| `<MissionPanel>` | Mission paragraph on home | A paper card embedded in the drenched-navy home page: ink display H1, slate body, ink-color link out. Single moment of paper before the page returns to navy. |
| `<SeasonsGrid>` | Two-up seasons detail | On navy (home): mint headings, paper body inside a thin paper rule. On paper (about): ink headings, slate body, hairline navy divider between the two seasons. No card decoration. |
| `<PhotoMosaic>` | Asymmetric photo wall | 4-col desktop / 2-col mobile. Mix of 1×1, 2×1, 2×2 tiles. The photo wall is paper-on-navy on the home page (photos sit inside generous mint or paper frames against the navy surface). Hover overlay desktop; lightbox tap mobile. BlurHash placeholders. Sparse-content fallback (uniform 3-col under 12 photos). |
| `<CoachEntry>` | Full-bleed coach editorial | Each coach gets a full-bleed photo with their name typeset at display scale below the image. Bio set in body-L with a single pull quote. **Not a card.** Stacks vertically on `/coaches`. |
| `<TripEntry>` | Trip marketing | Used on home (single feature trip) and trip detail pages. Editorial layout: photo, dates, location, lede paragraph, structured details (cost, deadline, capacity). No card frame. |
| `<TripsTable>` | Trips index | A typeset table on `/trips`: date, name, location, sign-up status. Restraint as voice. |
| `<SponsorWall>` | Sponsor display | Logo wall on `/sponsors`. Tiered headings; logos sized by tier. Not tiles. |
| `<WaxRoomFeed>` | Wax Room teaser | On the home page (paper-card-on-navy): three most recent wax room entries with date, title, one-line excerpt. Links to `/wax-room`. |
| `<WaxEntry>` | A single wax room post | Editorial layout on paper. Date, author (coach or member), title, body markdoc. Embedded photos and conditions snapshots. |
| `<CTAStrip>` | Section closer | Navy with mint heading + single mint-filled CTA. Coral 3px top border. Used at the bottom of most pages. |
| `<Footer>` | Site footer | Navy. Three columns: contact, navigation, social. Live conditions strip at the top (compact form). |

### Components removed from the previous version

- `<SkiTracks>` — the abstract scroll-driven SVG signature. Replaced by `<LiveConditions>`, which is genuinely specific to TCSC and useful to visitors. The mint ski-track marks remain in the logo only.
- `<CoachCard>` — coaches are no longer card-shaped. Full-bleed editorial entries instead.
- `<TripCard>`, `<SponsorTile>` — replaced with `<TripEntry>`, `<SponsorWall>`. Card-shapes removed where they were defaulting in.

## The signature device — Live Conditions

This deserves its own section. It's the single most distinctive choice in the site.

Each of four Twin Cities Nordic locations gets:

- Current temperature (NWS API; cached 5 min)
- Wind chill
- Snow depth / surface conditions (from SkinnySkI scraper; both are already integrated in the existing Flask app)
- A recommended wax range, computed from temperature:

| Temp band | Glide wax color | Klister? | Display |
|---|---|---|---|
| Below 14°F (-10°C) | Green / Cold | No | "Green wax · cold snow" |
| 14–28°F | Blue | No | "Blue wax · firm snow" |
| 28–32°F | Purple | Optional | "Purple · transition snow" |
| 32°F+ | Red / Yellow | Yes | "Red wax · klister conditions" |

Visual treatment on navy:
- Four columns, equal width, separated by 1px mint-20% rules.
- Each column: location name in body-M weight 600, temp huge (display cut at 2rem) in mint, wax recommendation in body-M slate-on-mint-tint.
- "Live · updated [n] min ago" indicator in coral, top-right.
- Click a column → expands to show full conditions detail (wind, gusts, snow depth) inline. No modal.

On paper inner pages: a compact horizontal version in the footer, single line per location.

**Why this matters.** It's the only element on the site that:
1. Is genuinely useful to the audience (Nordic skiers actually want this data).
2. Demonstrates expertise (only a real ski club builds in wax recommendations).
3. Cannot be replicated in a weekend — it requires real API integration, the wax knowledge, and the specific local location curation.
4. Replaces decorative motion with functional motion. The "signature" is the data, not a vector flourish.

Sparse data fallback (API failure): the strip shows location names + a quiet "Conditions unavailable" line. Never broken; always intentional.

## Motion

- **Live Conditions refresh.** A subtle 200ms opacity-flicker when data updates (every 5 minutes via revalidation). No spinner, no skeleton card, no shimmer. Data simply replaces.
- **Hero photograph load.** On the home page, the hero photo fades in over 400ms ease-out-quint with a synchronized blur-to-sharp via BlurHash. The headline appears at 200ms with a 4px upward translation. Single orchestrated entrance per session; cached after.
- **Photo mosaic interactions.** Hover overlay 150ms ease-out. Lightbox open: 200ms scale-in with opacity. Lightbox navigation: hard-cut.
- **Section transitions: none.** No fade-in-on-scroll. No staggered entrances. The single hero entrance is the only animated arrival in the site.
- **`prefers-reduced-motion`:** all entrance animations disabled. Live Conditions still refreshes (it's information, not motion). Hero photo loads without fade.
- **No animations on layout properties.** Transform and opacity only.

## Iconography

Lucide (open source, consistent line weight). Used sparingly: hamburger, lightbox close, social icons in footer, live-conditions "info" toggle. **No icons in CTAs.** No decorative icons in headings or bullets.

## Imagery

- All photos schema-managed in Keystatic with required `alt`, `caption`, `event_tag`, `photo_consent_recorded`.
- **The home hero requires a photo.** Sparse-photo fallback is well-designed (typography hero on solid navy) but the default is photographic.
- Astro image pipeline generates responsive `srcset`. AVIF + WebP fallbacks. BlurHash placeholders.
- No stock photography. If a section needs a photo and there isn't a real one, the section adapts (e.g., the wax room can lead with a pull-quote from a coach instead of a hero image).
- No decorative SVG / abstract shapes / gradient orbs / vector backgrounds.

## Banned (project-specific, on top of the shared impeccable bans)

- Stat boxes with big mint numbers.
- Pill emoji badges (✦, ★, etc.).
- "→" on every link. Reserved for the home hero CTA.
- Identical three-column card grids.
- Card-shaped components anywhere on the home page.
- Decorative parallax.
- Loading spinners.
- A second display typeface beyond the one display cut.
- Any serif typeface.
- Any mono typeface for non-code content.
- Uppercase tracked eyebrow labels as repeating section grammar. (One use per page is allowed if it carries information.)
- Any color outside the tokens above.

## Accessibility (visual layer)

- Body text minimum 16px on mobile, 17px on desktop.
- Focus rings: 2px mint on navy, 2px navy on paper. Always visible on keyboard navigation.
- Contrast verified for the actual pairings used:
  - mint / navy: 8:1 (large text and UI elements)
  - mint-deep / paper: 5.2:1 (body text on paper)
  - paper / navy: 14:1 (paper card on home)
  - ink / paper: 17:1 (inner-page body)
  - slate / paper: 7.2:1 (secondary body)
  - coral / navy: 5.6:1 (live indicators)
- Reduced motion: hero photo no fade; live conditions still refreshes silently.
- All interactive elements ≥44×44px on mobile.
- Live Conditions: ARIA live region announces material wax-recommendation changes (e.g., temperature crosses a wax band) for screen readers.
