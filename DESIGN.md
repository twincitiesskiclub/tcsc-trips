# Design

Visual system for the TCSC marketing site (Astro + Tailwind, under `/site` in this repo). Brand identity is fixed (navy + mint + coral pink); this document codifies how that identity expresses on the web.

This is the third pass of `DESIGN.md` (v2 of the contract). v1 described a site that was partly never built and partly superseded by the June and July 2026 feedback rounds. v2 describes the site we want, which is mostly the site that shipped plus the discipline it lacks: one type scale, one gutter, one ledger, one seam, one button, and a motion clause that lists every arrival. The identity items are unchanged: the nine tokens, the two families, real consented photographs only, and the Live Conditions strip as the signature device.

## Theme

Two physical scenes the site has to read for:

- A Twin Cities resident considering joining, opening the site on a Tuesday evening in October: laptop on a kitchen table, warm lamp light, half-attending while making dinner.
- A sponsor opening it the next morning on a 27-inch monitor in a downtown Minneapolis office, daylight, in a tab next to three other club sites.

The site reads warmly to scene one and crisp to scene two through *commitment to navy*, not through paper alternation. Drenched navy on the home page mirrors the actual experience of Minnesota Nordic skiing: dark months, bright snow, photographs as the moments of light. Inner pages (about, racing, sponsors, the wax room) shift to paper-default for long-form reading.

No theme toggle. Not "dark mode." Not "light mode with hero strips." One site, two registers chosen by surface.

The voice of the visual layer is the quiet ledger: hairline rules, small-caps seams, sentence-case everything else, near-zero motion. When a reviewer proposes something louder, the ledger wins.

## Color

**Strategy: Drenched on the home page; Committed on inner pages.**

- **Home page** is drenched navy from nav to footer. Home is drenched navy with two paper moments: the mission panel and the closing chapter (wax room feed plus sponsors). Every other band on home is navy. Paper bands are never adjacent. Photographs and sponsor logos are the only other paper appearances; paper exists *inside* frames, as the bright spots in a dark vessel. Coral is the live/energy punctuation.
- **Inner pages** (`/about`, `/community`, `/racing`, `/dry-tri`, `/extra-training-fun`, `/coaches`, `/sponsors`, `/trips`, `/wax-room`, `/404`) default to paper. Navy bands appear deliberately for section punctuation (the sponsors impact band, the extra-training standing invitations), not as alternating rhythm. The wax room in particular leans editorial-on-paper because long-form reading is the point.

Colors expressed in OKLCH, tinted faintly toward the brand hue to avoid pure-white/pure-black flatness. Tailwind tokens defined in `tailwind.config.ts`. The hex column is the resolved sRGB value of each token (v1 listed estimates that did not match). The Flask app's brand navy is `#202A44`; the site's navy resolves to `#10213E`. That difference is accepted, not accidental.

| Token | OKLCH | Hex (resolved) | Use |
|---|---|---|---|
| `navy` | `oklch(0.25 0.06 260)` | `#10213E` | The home page surface (drenched). Nav, footer, and navy bands on inner pages. Headings on paper. |
| `navy-deep` | `oklch(0.18 0.05 260)` | `#051127` | Slightly darker navy for navy-on-navy elevation: the conditions strip (both variants) and the lightbox surface. Subtle. |
| `mint` | `oklch(0.91 0.12 155)` | `#9EF9BE` | On navy: the home hero h1, the CTAStrip h2, live data (temperatures, fever), `.label-caps` labels, links, primary CTA fills, and the ski-track marks in the logo. On paper: not used directly (too pale); use `mint-deep`. |
| `mint-deep` | `oklch(0.52 0.13 155)` | `#007E46` | The accessible mint for text on paper: links, `.label-caps` labels, and `.link-ledger` hover. Measured 4.95:1 on paper, 4.74:1 on paper-card. |
| `coral` | `oklch(0.74 0.16 15)` | `#FF7C8A` | Energy accent that carries state: the live stamp dot, the open-registration dot, the CTAStrip top rule, the playing fever note. ≤4 uses per page. Never text on paper (2.4:1). |
| `paper` | `oklch(0.985 0.003 90)` | `#FBFAF8` | Inner-page surface, and the frame color inside navy. Tinted faintly warm because pure white on a sport-club site reads clinical. |
| `paper-card` | `oklch(0.97 0.004 90)` | `#F6F5F2` | The barely-visible tint on paper: the mosaic tile placeholder before a photo paints. Not a card fill. |
| `ink` | `oklch(0.18 0.04 260)` | `#071123` | Body text on paper. |
| `slate` | `oklch(0.50 0.02 260)` | `#5D646F` | Secondary body on paper. Captions, dates, meta, ledger detail columns. |

### Register rules

- On paper, headings and display text are `navy`, body is `ink`, secondary body and meta are `slate`. Opacity modifiers are not a substitute for a token: secondary text on paper is `slate`, never `ink` at reduced opacity, and no text on paper uses an alpha below `/90`.
- Text on navy uses three tones: `mint`, `paper`, and `paper/75`. No other alpha on text over navy. (Known exception, recorded not endorsed: the groomed line the sacred conditions client injects at `paper/50`; it is fixed in a later Flask-side pass.)
- On navy, the home hero h1 and the CTAStrip h2 are mint; every other h2 and h3 on navy is paper. Mint otherwise carries live data, `.label-caps` labels, links, and CTA fills.
- Coral is a state, not a style. The live stamp is coral only when the fetch succeeded; the open-registration note carries a coral dot only while registration is open; loading, unavailable, and off-season stamps are `paper/75`. The compact conditions strip carries the same coral live dot as the prominent strip, before the first venue.
- Accent budget per surface: on navy, mint + coral + paper-inside-frames is the limit; on paper, mint-deep + coral + navy is the limit. The sponsors impact band is the reference example of the navy budget holding.

### Links

Links have three roles, each one class in `global.css`, color decided by the nearest surface:

- `.link-inline`: inline and standalone text links. On paper `mint-deep` with a `mint-deep/40` underline, offset 4, full-strength underline on hover; on navy `mint` with a `mint/40` underline. Matches prose links.
- `.link-ledger`: a ledger row title that happens to link. `navy` with an `ink/30` underline, turns `mint-deep` on hover; on navy `paper` with `mint/40`, turns `mint` on hover.
- `.link-nav`: nav and footer links. No underline, color to mint on hover.

No other link recipe. Underline decoration alphas are `ink/30` on paper and `mint/40` on navy, nothing else.

### Hairlines

Two hairline weights per surface, and no other rule alpha:

- Structural (`.hairline`): `ink/15` on paper, `mint/20` on navy. Seams, photo-grid gaps, section borders, the masthead rule.
- Row (`.hairline-soft`): `ink/10` on paper, `mint/15` on navy. Ledger dividers, the nav bottom edge, the footer top edge, the conditions-strip edges, and the vertical rule between conditions cells.

The classes switch by surface the way the focus ring does (an inherited custom property set by `.bg-navy` / `.bg-paper`).

### Buttons

One button primitive (`<Button>` / `.btn`) with one recipe per surface: on navy `bg-mint text-navy hover:bg-mint/90 active:bg-mint/80`; on paper `bg-navy text-mint hover:bg-navy-deep`. `rounded-md`, `px-5 py-3`, content-width at every viewport (`self-start`). Paper is never a button fill on navy. Every button and CTA on the site, including the nav CTA, the hero CTA, the CTAStrip, and the 404 button, renders through it.

### Data colors

The four wax-band chip colors (`wax-green`, `wax-blue`, `wax-purple`, `wax-red`, L 0.62) are data colors defined in `tailwind.config.ts`: the color *is* the recommendation. They appear only on the wax chip, never as text or decoration.

### Literals

`navy` and `ink` are referenced through `theme()` (and the `theme-color` meta reads the resolved navy `#10213E`), never as literals. The nav logo's `fill` attributes are the one literal exception, by the June 2026 decision that the mark must not break outside CSS scope; they are the resolved token hex (`#9EF9BE` tracks, `#FBFAF8` letters).

### Contrast (measured)

Any new text pairing is measured, not estimated, before it ships. Every text pair on every page passes WCAG AA. Measured from the OKLCH tokens (oklab to linear sRGB, WCAG relative luminance):

| Pairing | Ratio | Use |
|---|---|---|
| mint / navy | 12.8:1 | headings, data, links on navy |
| paper / navy | 15.4:1 | body on navy |
| paper/75 / navy | 11.8:1 | meta on navy |
| coral / navy | 6.5:1 | live dot, CTA rule |
| coral / navy-deep | 7.6:1 | live dot on the strip |
| navy / mint | 12.8:1 | button label |
| ink / paper | 18.0:1 | body on paper |
| navy / paper | 15.4:1 | headings on paper |
| slate / paper | 5.7:1 | secondary on paper |
| slate / paper-card | 5.5:1 | secondary on the tile placeholder |
| mint-deep / paper | 4.95:1 | links and labels on paper |
| mint-deep / paper-card | 4.74:1 | same, on paper-card |
| ink/80 / paper | 4.1:1 | **fails**; banned |
| coral / paper | 2.4:1 | non-text glyph only |
| mint/15 / navy | 2.8:1 | row hairline, perceptible |
| mint/10 / navy | 2.2:1 | **too faint**; banned |

**Banned in this design:**

- `#000` / `#fff`. Use `ink` / `paper`.
- Gradients for decoration. The only gradients are the two functional scrims (hero bottom vignette, mosaic hover caption scrim) that exist to make text legible.
- Gradient text. Period.
- More than three accent colors per surface.
- Soft-tinted gray cards on paper. If a card needs definition, give it a 1px ink-15% rule or a clear background, not a gray drop-shadowed slab. The `paper-card` token is a placeholder tint, not a box fill.
- Any color outside the tokens above, plus the four wax data colors. Arbitrary color values (`bg-ink/[0.03]`) are banned; a barely-visible tint on paper is `paper-card`.
- A third dark. Surfaces are navy, navy-deep, paper, paper-card.

## Typography

**One sans family, one weird display cut. No serif anywhere. No mono.**

The brief is warm/sporty/inclusive with Tracksmith × Patagonia DNA. Both prove that "outdoor heritage warmth" lives in *photography, voice, and color choices*, not in the type. So there is no serif, no editorial-magazine reflex, and one well-chosen sans family carries weight contrast and personality.

### What ships

- **Body, UI, labels, captions, statements, stat values, row titles, buttons: Archivo Variable** (`ArchivoVariable`, weights 100 to 900, width axis unused). Self-hosted from `/fonts/archivo/`.
- **Display moments: PolySans BulkyWide** (`PolySansBulkyWide`, licensed for production, a single 700 cut, subset A-Z a-z 0-9; Archivo supplies punctuation and any glyph outside the subset). Self-hosted from `/fonts/polysans/`. Because the cut is single-weight, `font-semibold` at a call site is a no-op; `.font-display` carries the weight fallback and `letter-spacing: -0.02em` itself. Because the subset lacks punctuation, the display cut never sets a paragraph.
- **No second family. No serif. No mono.** A label that needs to feel "live data" uses `.label-caps`, not a mono font.

### The display cut

The display cut is used on h1, h2, and the prominent conditions temperatures only; never on h3 or below, paragraphs, stat values, list rows, buttons, or labels. On home that is the hero h1, the season h2s, the mosaic h2, the CTAStrip h2, and the five temperatures. It reads as a signature because it is rare.

### Scale (fluid via `clamp()`, defined once)

Type roles are defined once in `global.css` as `clamp()` utilities; no `text-*`, `leading-*`, or `text-[Npx]` utility appears on a type role at a call site. No type on the site is smaller than 0.75rem. Weight for display rows is 700 (the single cut).

| Role | Utility | Mobile | Desktop | Line height | Weight | Family |
|---|---|---|---|---|---|---|
| Display h1 (home hero) | `.type-display` | 3.0rem | 6.0rem | 0.95 | 700 | Display |
| Display h1 (inner mastheads, wax entry) | `.type-display-inner` | 2.5rem | 4.0rem | 1.0 | 700 | Display |
| h2 (section) | `.type-h2` | 2.0rem | 3.0rem | 1.05 | 700 | Display |
| h2, long-form (markdoc h2, list titles, tier heads, season names on home) | `.type-h2-longform` | 1.75rem | 2.25rem | 1.1 | 700 | Display |
| h3 | `.type-h3` | 1.375rem | 1.625rem | 1.2 | 600 | Archivo |
| h4 | `.type-h4` | 1.125rem | 1.125rem | 1.3 | 600 | Archivo |
| Statement (mission paragraph, about lede) | `.type-statement` | 1.375rem | 1.875rem | 1.3 | 500 | Archivo |
| Lede (masthead subhead, hero subline, wax lede) | `.type-lede` | 1.125rem | 1.25rem | 1.55 | 400 | Archivo |
| Body | `.type-body` | 1.0rem | 1.0625rem | `--body-lh` | 400 | Archivo |
| Long-form body (markdoc via `prose`) | typography theme | 1.125rem | 1.125rem | 1.7 | 400 | Archivo |
| Caption / meta (dates, times, bylines, credits, feels-like) | `.type-caption` | 0.875rem | 0.875rem | 1.45 | 400 | Archivo |
| Stat value | `.type-stat` | 1.5rem | 1.5rem | 1.0 | 700, tabular-nums | Archivo |
| Label caps (dt labels, table heads, stat labels, venue names, kickers) | `.label-caps` | 0.75rem | 0.75rem | 1.0 | 600, tracking 0.12em, uppercase | Archivo |
| Seam (section chapter name) | `.seam` | 0.75rem | 0.75rem | 1.0 | 600, tracking 0.18em, uppercase | Archivo |
| Button label | `.btn` | 1.0rem | 1.0rem | 1.0 | 600 | Archivo |

Clamp expressions: `.type-display` `clamp(3rem, 1.6rem + 5.8vw, 6rem)`; `.type-display-inner` `clamp(2.5rem, 1.9rem + 2.4vw, 4rem)`; `.type-h2` `clamp(2rem, 1.5rem + 2vw, 3rem)`; `.type-h2-longform` `clamp(1.75rem, 1.5rem + 1vw, 2.25rem)`; `.type-h3` `clamp(1.375rem, 1.25rem + 0.5vw, 1.625rem)`; `.type-statement` `clamp(1.375rem, 1.2rem + 0.9vw, 1.875rem)`; `.type-body` `clamp(1rem, 0.96rem + 0.2vw, 1.0625rem)`.

- The inner display h1 desktop value is 4.0rem (v1: 4.5rem) so it fits the masthead's 8-column cell.
- The reversed-type bonus is mechanized: `--body-lh` is set by the surface (`.bg-navy` and `.bg-navy-deep` 1.7, `.bg-paper` and `.bg-paper-card` 1.65) and consumed by `.type-body` and `.type-lede` (lede on navy 1.6); call sites never set leading.
- Measures: `max-w-prose` (62ch) on paper and `max-w-prose-narrow` (56ch) on navy are the only body measures; `.type-statement` caps at 44ch via `max-w-statement`. Arbitrary `ch` values and `max-w-xs/lg/xl` on text are banned.
- h1 and h2 carry `text-wrap: balance`; the statement carries `text-wrap: pretty`.
- Dates, times, bylines, and credits are the caption role: slate on paper, paper/75 on navy, `tabular-nums`, sentence case, never uppercase or tracked.
- Button labels are Archivo 600 at 1rem; the nav bar CTA alone is 0.875rem (`size="sm"`).
- Markdoc headings are themed once in the typography theme (`h2` = display cut at `.type-h2-longform` values, `h3` = `.type-h3`, `h4` = `.type-h4`); pages use `prose`, never `prose-lg`, and never patch prose headings with arbitrary variants.
- Stat values are Archivo 700 at 1.5rem `tabular-nums` over a `.label-caps` label, in navy on paper and paper on navy; rendered by one `FactStack` partial in the mission panel and the inner masthead.

### Labels and seams

Two uppercase specs only: `.seam` (0.75rem, tracking 0.18em, 600) and `.label-caps` (0.75rem, tracking 0.12em, 600). A seam is the section chapter name plus a hairline to the right edge, at most one per band and at most three per page; every seam carries a label. Data labels (dt labels, table heads, stat labels, venue names, the 404 kicker) share `.label-caps` and do not count as eyebrows. Decorative eyebrows stay banned. Uppercase is banned on headings, buttons, dates, and times. `.label-caps` is `mint` on navy and `mint-deep` on paper; `.seam` is `mint` on navy and `mint-deep` on paper.

### Document outline

Every band has a heading element; SectionBand renders its seam as the h2 when no heading prop is passed and as a span when one is. One h1 per page, no skipped levels. The prominent conditions strip carries an sr-only h2 "Trail report".

## Layout

- **Gutter:** one gutter token, `--gutter: clamp(1.5rem, 4vw, 2.5rem)`, applied by one `.gutter` utility that folds in the safe-area `max()`. Call sites never add `px-*` beside it. Every container shares one left edge per viewport (120px at 1440).
- **Container:** one container, `max-w-site` (1280px), for every band, masthead, ledger, strip, and footer on every page. There is no separate inner-page width. The reading column sits left-aligned on the 12-col grid (columns 1 to 8) capped at `max-w-prose`; no centered `max-w-3xl/4xl/5xl/6xl` wrappers. Long-form prose mounts through `ProseColumn`.
- **Vertical rhythm:** three band rhythms, defined once in `global.css` as `band-sm` (48/64px), `band` (64/96px), and `band-lg` (80/128px), mobile/desktop. Home uses `band` and `band-lg`; inner pages use `band-sm` and `band`. A page uses at least two of the three. Same-surface neighbors share one gap owned by the incoming section; the outgoing band drops its bottom padding (`flush="bottom"`). Seam-to-content gap is one value (2rem). The mission panel sits in navy on both sides (`band` above and below). A prose column that opens with an h2 zeroes that h2's top margin.
- **Asymmetric defaults.** Two-up grids prefer 7/5 or 5/7 splits rather than 6/6, except the seasons grid, where parity is the point. Photo pairs are 7/5 with mixed aspects.
- **Photo groups:** one photo-group grammar: flush tiles, hairline gaps (`gap-px` on the structural hairline color), no perimeter border, optional caption line in slate below the group. A group never leaves an empty cell; odd counts get a spanning lead tile. Below `md`, a strip runs full-bleed or 1 + n; the mosaic keeps rhythm with 2x1 tiles. A portrait source never receives a wide slot.
- **No card-grid reflex.** Cards are used where they're truly the best affordance: sponsors as a logo wall in ruled rows (not tiles), trips as a ledger on the trips index (not a 3-up card grid), coaches as 4/7 editorial entries (not 3-up cards).
- **No nested cards. Ever.**
- **The home page has no card grid at all.** Every section is full-bleed-on-navy or a deliberate photographic puncture.

## Components

Built in `site/src/components/`. Each takes typed props; story-doc'd inline. The first table is the primitives every other component composes; a page never hand-builds one of these patterns.

### Primitives

| Primitive | Fixed values |
|---|---|
| `<Seam label? surface>` | `.seam` label plus a structural hairline to the right edge. Rendered by SectionBand, PhotoMosaic, WaxRoomFeed, and the conditions strip label; the markup exists once. |
| `<Ledger cols rule surface>` + `<LedgerRow label title meta? note? href?>` | The ledger (label column, detail column, hairline rows) is a component with fixed column presets; pages never hand-build rows. `cols`: `two` (`md:grid-cols-[14rem_1fr]`), `three` (`md:grid-cols-[8rem_1fr_minmax(8rem,auto)]`), `stacked`. Rows `py-5 gap-x-6`. Divider is the row hairline. Rule: `between` by default; a top rule only when mounted without a seam. Hover: title to `mint-deep` (paper) or `mint` (navy) only; no background wash, no negative margins. A seamed band never draws a second rule above its first row. |
| `<FactStack facts size align>` | Org facts render through one FactStack: value (`.type-stat`, navy on paper) over a `.label-caps` label, behind one left hairline, `space-y-4`; max three per surface; no boxes; mint numbers banned. `size="lg"` on the mission panel, `"md"` on mastheads. Under `md` it renders as one ruled row (`border-t hairline pt-6 grid grid-cols-3`). |
| `<Button variant href size?>` | The one button (see Color, Buttons). |
| `<PhotoStrip photos cols aspect captions?>` | The photo-group grammar (see Layout). Used by the community cluster, the racing strip, the dry-tri legs, the extra-training pair. |
| `<SectionHeader heading more_href? more_label?>` | Heading plus optional closer link; `flex-col items-start gap-2 md:flex-row md:items-end md:justify-between`; the closer link is `.link-inline` with a 44px hit area. |
| `<ProseColumn rhythm flush?>` | Long-form content on inner pages mounts in one ProseColumn: the reading column on the grid (columns 1 to 8, `max-w-prose`), `prose` (not `prose-lg`), `band-sm` by default. |
| `<WaxEntryRow entry density>` | One row grammar for wax entries on the home feed (`feed`) and the index (`index`): date · author, title (Archivo 600 1.125rem), lede as its own caption line, conditions meta right. |

### Site components

| Component | Purpose | Notes |
|---|---|---|
| `<Nav>` | Top navigation | Navy bar, row hairline below. The club logo (mint ski tracks, paper letters, fills as literal hex) at 22px tall; six section links inline desktop, `.link-nav`; hamburger mobile (inline svg). Primary CTA reads `registration_state` through `CtaForState`, `size="sm"`. The conditions strip sits directly under the nav on every page. |
| `<LiveConditions>` | **The signature device.** | See the section below. `prominent` on home; `compact` under the nav on inner pages. |
| `<MobileNavPanel>` | Full-screen mobile nav | Navy panel. The logo lockup top-left (same 145x22 mark as the nav), six 24px links, the CTA pinned bottom. No conditions strip (the strip is one mount per page and already sits under the nav). |
| `<HeroHome>` | Home hero | **Full-bleed photograph** behind the headline. Real candid photo. Headline in mint over the functional bottom scrim (`from-navy/95 via-navy/50 via-45% to-transparent`). Subline `.type-lede` in `paper`; dates line (coming soon only) `.type-caption` in `paper/75`. Single primary CTA. The text block sits in a face-free zone at 390, 768, and 1440; the zone may change side or column by breakpoint; when no crop clears a face, the text block moves, not the photo. At `lg` the hero fills the first viewport below the nav and strip (`calc(100svh - nav - strip)`, minimum 540px); the fold ends on the hero's bottom edge. Sparse-photo fallback: solid navy with the display h1 huge in mint. |
| `<HeroInner>` | Inner-page masthead | Paper. `.type-display-inner` h1 in navy on columns 1 to 8 (`text-balance`), `.type-lede` subhead in slate, optional FactStack on columns 10 to 12 behind a hairline (bottom-aligned with two or more facts, top-aligned with one), a structural hairline below. Optional full-bleed photo band directly under the masthead: `aspect-[16/5]`, min 230px, max 420px, `object-cover` with a deliberate `object-position` per photo. Pages with no true facts render the single-column masthead. |
| `<SectionBand>` | Wraps a content block | Variants: `navy`, `paper` (the `paper-on-navy` card is deleted). Props: `seam` (rendered through Seam; becomes the h2 when no heading is passed), optional `heading`, `rhythm` (`sm` / `md` / `lg`), `flush`. No numbered marker. |
| `<MissionPanel>` | Mission statement on home | A full-bleed paper band (not a card): the mission set as `.type-statement` in navy (Archivo, never the display cut) on an 8/3 split beside a FactStack (`size="lg"`). The first of home's two paper moments; navy `band` padding above and below. |
| `<SeasonsGrid>` | Two-up seasons detail | Hairline cells with vertical padding only (text sits on the seam's axis); on navy (home) season names `.type-h2-longform` in paper, fee 1.125rem mint, registration note `.type-caption` 600 (coral dot while open) stacked under the fee below `sm`; three `.label-caps` fact rows. On paper (about) the same with navy names and mint-deep labels, `headingLevel="h3"`, opened by the same `seam="Seasons"` as home. Dues line `.type-body`. No card decoration, no cell inset. |
| `<PhotoMosaic>` | Asymmetric photo wall | Hairline grid (`gap-px` on the structural hairline), composed layout (lead 2x2 plus sides) under 12 photos, dense 8-cycle above. Orientation-aware spans (a portrait source never gets `col-span-2`), face-aware square crops (sharp `position: attention`), `object-[center_25%]` for portrait sources in landscape slots, the lead tile's crop set deliberately. Mobile keeps rhythm with 2x1 tiles every fourth position; composed side tiles are `4/3` on mobile, never forced square. Always opens with a Seam and an h2 (on community too). Hover: bottom caption scrim, 150ms, photo never dimmed. Tap opens the lightbox. Enforces `photo_consent_recorded`. |
| `<Lightbox>` | Fullscreen photo viewer | `navy-deep/95` surface (in the focus map, no override). Close, previous, next as inline chevron/close strokes in 44px hit areas, no bordered pills. Caption directly under the image. Entrance per Motion; navigation hard-cut. |
| `<CoachEntry>` | Coach editorial entry | Site-width 12-col grid: photo `md:col-span-4 aspect-square` (the native shape, attention-cropped), text `md:col-span-7 md:col-start-6`, top-aligned so the slot never towers over the bio. Name as h2 in the display cut, role in mint-deep, bio in `prose`, credentials as a plain list only when they add to the bio. Under `md`: a 240px square portrait beside the name, then the bio. **Not a card.** Stacks vertically on `/coaches`. |
| `<TripsTable>` | Trips index | A Ledger (`cols="three"`: dates, trip, where) at site width; the header row shows at every viewport as a ruled line. No photography until trip detail pages exist (`hero_photo` stays in the schema, documented as unused). Empty state per Empty states. |
| `<SponsorWall>` | Sponsor display | A ruled row per tier at site width: tier label in the seam voice at left, logos left-aligned in the row, sized by tier (`logo-lg` 17.5rem, `logo-md` 15rem, `logo-sm` 12.5rem widths; `max-h-16` under `sm`). Two sponsors fill one row with dignity. Not tiles, not centered. |
| `<WaxRoomFeed>` | Wax Room teaser | Opens home's closing paper chapter: `seam="Wax room"`, up to three WaxEntryRows in a Ledger, then a hairline, then `seam="Our sponsors"` with the two logos on one row (`max-h-10` on mobile) and one `.link-inline` closer. With no entries the chapter is the sponsor row alone and keeps its place. |
| `<WaxEntry>` | A single wax room post | Editorial layout on paper in ProseColumn: date and byline `.type-caption`, `.type-display-inner` title (`text-balance`), lede `.type-lede`, one photo, body `prose`. The conditions snapshot is a ruled `dl` (structural hairline top and bottom, three cells, `.label-caps` labels in mint-deep, values in ink); no fill, no radius. |
| `<CTAStrip>` | Section closer | Navy with mint `.type-h2` heading, `.type-lede` subhead at `max-w-prose-narrow`, one Button. Coral 3px top rule (the page's coral punctuation). `rhythm="lg"` on home, `"md"` elsewhere. Mounted at the bottom of home, about, and sponsors; every page that explains joining ends with it. Its section class literal is guarded by `tests/contentRefinements.test.mjs` and is updated in the same commit as any change. |
| `<Footer>` | Site footer | Navy, row hairline above. Three columns: the logo lockup (the nav svg at 120px) plus a one-line description at `max-w-prose-narrow`; two-column nav read from `getNavLinks()` plus a `FOOTER_EXTRAS` constant, in header order; contact and credits in `paper/75`. Link rows `min-h-10`. No conditions strip. |

### Components removed

- `<TripEntry>`: never built; `/trips` is a ledger with no photography until detail pages exist.
- `SectionBand variant="paper-on-navy"`, `contentMax`, `subhead`, `CtaForState variant="on-paper"` (superseded by Button), `PhotoMosaic limit`: dead props are dead CSS and are deleted.
- `<SkiTracks>`, `<CoachCard>`, `<TripCard>`, `<SponsorTile>`: removed in v1 and still gone.

## The signature device: Live Conditions

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

**Why this matters.** It's the only element on the site that:
1. Is genuinely useful to the audience (Nordic skiers actually want this data).
2. Demonstrates expertise (only a real ski club builds in wax recommendations).
3. Cannot be replicated in a weekend: it requires real API integration, the wax knowledge, and the specific local location curation.
4. Replaces decorative motion with functional motion. The "signature" is the data, not a vector flourish.

### As built (corrections to v1's description)

- The visible name of the device is **Trail report**. The four venues come from the API (`app/conditions/locations.py`): Theodore Wirth, Elm Creek, Hyland, and Telemark (Cable, WI), not French Park and Battle Creek. The server-rendered venue label "Theo" is a Flask string and is flagged for a later Flask change to "Theodore Wirth".
- The fifth cell on `md+` is **Birkie fever**, the race-likelihood reading on a thermometer scale; it is also a button that plays the club's Birkie Fever song. It carries a ♪ as its play affordance (aria-hidden, `md+` only); the whole cell hovers to `paper` so it reads as a control. There is no click-to-expand cell and no wind/gusts/snow-depth detail; v1's expand clause is withdrawn.
- Prominent variant (home): the strip label is a Seam voice (`.seam`), the stamp reads `● Live · updated 7:02 AM` (a clock time, not "n min ago"), cells are venue name `.label-caps`, temperature in the display cut at 2rem in mint, feels-like `.type-caption` on its own line under the temperature, wax line `.type-body` with the data-color chip, groomed line below. Cells separate with the row hairline drawn on each venue cell's right edge (so hidden cells take their rule with them). Grid: `grid-cols-2 md:grid-cols-3 lg:grid-cols-5` (Theo, Hyland, fever at `md`; all five at `lg`); mobile shows the Theodore Wirth cell only.
- Compact variant (every inner page, directly under the nav): one line per venue: coral live dot, venue name `.label-caps` as the report link when a source exists, temperature Archivo 700 0.875rem `tabular-nums`, wax text `.type-caption`; no display cut. Mobile shows the Theodore Wirth line only; line height clears a 44px tap target for the link.
- Dryland season (API error in April to October): the venue cells hide and the strip collapses to a single dateline, `Trail report · Dryland season · Birkie fever 98.6°`, with the stamp `● Trail reports come back with the snow` in `paper/75`; mobile shows "Dryland season" alone. No orphan rule.
- Unavailable (fetch failed in season): the stamp reads `● Conditions unavailable` in `paper/75` and the cells show venue names only; the per-cell "No report" line is hidden by CSS so the message is said once. Never broken; always intentional.
- Coral means live: the dot is coral only while `data-updated-at` is present.

## Motion

Near zero, and every arrival is listed here. If it is not in this list, it does not move.

- **One easing curve site-wide.** `--ease-out: cubic-bezier(0.16, 1, 0.3, 1)`, set as Tailwind's default transition timing function; default transition duration 150ms. No second curve anywhere.
- **Hero entrance (home).** The photo fades in over 400ms `--ease-out`; the headline, subline, and CTA rise 8px over 250ms starting at 120ms (the CTA at 200ms), so the fold enters as one gesture. Once per page load. No placeholder image and no BlurHash; frames sit on `paper-card` until the photo paints.
- **Conditions first fill.** Cells rise 4px and fade in over 250ms `--ease-out` after the first fetch, backstopped at 1200ms. Refreshes every five minutes replace text silently. No flicker, no spinner, no skeleton, no shimmer.
- **Mobile nav panel.** Opens with a 200ms opacity fade and an 8px rise on the link list; closes instantly.
- **Lightbox.** Opens with a 200ms opacity fade and a scale from 0.97 to 1 on the image, CSS-only via `@starting-style` and `transition-behavior: allow-discrete` reacting to the client's class toggle; browsers without `@starting-style` keep a hard cut. Close is instant. Navigation between photos is a hard cut.
- **Mosaic hover.** Bottom caption scrim fades in over 150ms; the photo is never dimmed. Desktop only.
- **Hover and press feedback** is a 150ms color change (color, background-color, text-decoration-color), never a lift, scale, shadow, or background wash. Written as `transition-colors` only; bare `transition` and `duration-150` are banned. Focus rings never transition.
- **Section transitions: none.** No fade-in-on-scroll. No staggered entrances. No scroll reveals. No parallax. The four arrivals above are the only animated arrivals in the site.
- **`prefers-reduced-motion`:** animation and transition durations *and delays* are zeroed; the hero photo loads without fade; Live Conditions still refreshes (it's information, not motion).
- **No animations on layout properties.** Transform, opacity, and color only.
- Every `<button>` shows the pointer cursor (`button:not(:disabled) { cursor: pointer }`; Tailwind 4 preflight does not set it).

## Iconography

Inline 24px stroke-2 SVG paths, no icon library. Three icons exist: menu (hamburger), close, and chevron (lightbox previous and next). Used sparingly. **No icons in CTAs.** No decorative icons in headings or bullets. No arrow glyphs (`→`, `←`) in link or button text anywhere; navigation controls are the chevron strokes. One exception, recorded: the ♪ on the Birkie fever cell is its play affordance, aria-hidden, `md+` only.

## Imagery

- Real, consented club photography only. No stock. No generated production imagery. No decorative SVG, abstract shapes, gradient orbs, or vector backgrounds.
- Every photo the site renders has a row in `migration/CONSENT.md`; collection photos (`site/src/content/photos/*.yaml`) additionally carry `photo_consent_recorded: true`, which PhotoMosaic enforces. Direct page imports are allowed only for placements the mosaic cannot express (mastheads, anchors, strips) and cite the CONSENT row in a comment.
- No race-gallery or watermarked frames. A photo with a third-party mark needs a rights line in `CONSENT.md` before it renders, and the mark is cropped out.
- Every `object-cover` image has a deliberate focal point at both viewports: `object-position` for hand-placed photos, sharp `position: attention` for square and fixed-ratio renditions. No face touches an edge. The mosaic never gives a portrait source a wide slot.
- Masthead photo bands: `aspect-[16/5]`, min 230px, max 420px, with a per-page `object-position` set by reading the source (about `center 58%`, community `center 46%`, 404 `center 60%`).
- **The home hero requires a photo.** Sparse-photo fallback is well-designed (typography hero on solid navy) but the default is photographic.
- Astro image pipeline generates responsive `srcset`; the mosaic lead tile's width list reaches 1920 so a 2x display is never upscaled. Formats: webp everywhere; avif on the home hero only. No BlurHash.
- If a section needs a photo and there isn't a real one, the section adapts (e.g., the wax room leads with its ruled empty state, not a placeholder image).
- Unreferenced image assets are deleted or added to a collection; the repo does not carry orphan photos.

## OG image

One default share card for the site, `site/public/og/og-default.jpg`, 1200x630 JPEG under 200KB: a consented club photograph (the sunset skate practice) with the hero's functional bottom scrim (`from-navy/95 via-navy/50 to-transparent` over the lower 45%) and the logo lockup (mint tracks, paper letters, the nav svg) bottom-left at about 240px wide, 48px from the left and bottom edges. No headline type in the image; the title comes from `og:title`. Faces stay inside the center 60% vertically so square and 4:5 previews keep them. Wax entries derive their card from the entry photo (existing behavior). `BaseLayout` always sets `og:image:width`, `og:image:height`, `og:image:alt`, and `twitter:image`. Per-page cards derived from masthead photos are a later round.

## 404

The 404 page has one display heading: the masthead h1 `This trail ends here.` with the subhead `The page may have moved, or the link may point to our old site.`, the trail photo band, then a `.label-caps` kicker `404 · Page not found`, one Button (`Back to home`, on-paper recipe), and one Ledger of three destinations under an h3 `Try one of these` that always have content (About, Community, Registration). No second display heading, no "Choose another page." block. Title `Page not found · Twin Cities Ski Club`; `noindex`; meta description `Page not found.`

## Empty states

An empty collection renders one ruled placeholder row in the same Ledger the populated state uses, with one or two plain sentences in the club voice and one `.link-inline`; never a bare paragraph, never a promised cadence the site has not kept, never an invented schedule. Trips: `No trips posted yet. Trips go up here once dates are set. Questions in the meantime: contact@twincitiesskiclub.org.` Wax room: `No entries yet. The first reports arrive with the snow.` (the opening sentence is asserted by `tests/contentRollback.test.mjs` and stays).

## Copy

The 2026-07-18 voice rules, verbatim:

1. Prefer concrete activities and named details over claims about values.
2. Prefer direct verbs over nonprofit abstractions such as "fostering," "promoting," and "providing."
3. Use at most one playful ski reference on a surface. Club-specific language such as Techno Corner and Birkie Fever stays.
4. Remove slogan structures, inflated claims, filler adjectives, and repeated points.
5. Keep eligibility, fees, registration dates, and optional racing language explicit.
6. Do not invent facts to improve a sentence. Leave uncertain copy unchanged until the club confirms it.

Plus the house rules:

- Punctuation: sentence punctuation is the period, the comma, the colon, and the middot. No em dashes, no exclamation points, no semicolons, no ellipsis headings, no question headlines. Typographic (curly) quotes in prose. Sentence case everywhere, including tier headings; title case only in proper names.
- Names and facts: the organization is "the club" and its people are "members"; "team" is reserved for race-day things (team wax, team tent, team jacket). The metro is "Minneapolis and St. Paul" in prose and "Minneapolis · St. Paul" in fact slots and the footer. The age band is "ages 21-35", never parenthetical. Days join with "and" in prose and a middot in fact slots, never a plus sign. Ranges are "September to March" in prose and unspaced hyphens in compact form (`Jan 9-11`, `ages 21-35`). Numbers under ten are words, ten and above numerals. Race and event names are spelled the way the organizer spells them, once, everywhere: Sisu Ski Fest, Prebirkie, Kortelopet, American Birkebeiner, Great Bear Chase, Tour de Finn. "après-ski" carries its accent. Registration months (Rob, 2026-06-11): Fall/Winter opens Aug/Sep, Spring/Summer opens Apr/May.
- House formats: dates `Jan 9, 2027` and `Jan 9-11, 2027` (short month, no leading zeros, unspaced hyphen range); places `Ironwood, MI` (two-letter state). Trips, races, wax entries, and captions all use them. A date column holds dates or date windows; anything else goes in notes.
- Masthead facts are true facts about the page and pair a short value (a number or a name) with a noun label; a page with none renders the single-column masthead. A hub-page ledger group whose content lives on its own page shows one row plus the link.
- One name per page, in sentence case: the nav label, the footer label, the page title, and the h1 match. Page titles are `<Page> · Twin Cities Ski Club`; the home page is the bare name.
- Meta: every page authors its own meta description under 155 characters ending on a full stop; `metaDescription()` is the safety net, not the writer. `site_meta.yaml` is the only source for the default description.
- Alt text describes what is in the frame; the same file carries the same alt on every page.
- One source per string: no literal repeated across files (nav labels, the site description, the mission).

### Registration copy (per state, per render site)

The CTA renders in four places (desktop nav, mobile panel, home hero, CTAStrip) through `getRegistrationCta()`, and the season cards and strip subhead read the same windows. Labels never name a season; the season is derived, so every label must be true for Fall/Winter and Spring/Summer alike.

| State | CTA label | CTA url | Hero dates line | Strip subhead | Season card note |
|---|---|---|---|---|---|
| open | `Register for the season` | `https://tcsc.ski` | `New members Sep 3` while only the returning window is open, else hidden | `Registration is open. Intermediate ability and up, no racing required.` | `Registration open` (plus ` · new members from Sep 3` while only returning is live), coral dot |
| coming soon | `How to register` | `https://tcsc.ski` | `Returning members Aug 28 · new members Sep 3` | `Returning members Aug 28 · new members Sep 3. Intermediate ability and up, no racing required.` | `2026 registration: returning members Aug 28 · new members Sep 3` |
| closed | `How to register` | `https://tcsc.ski` | hidden | `Registration is closed. Fall/Winter reopens Aug/Sep, Spring/Summer Apr/May. Intermediate ability and up, no racing required.` | `2026 registration closed` |

- One format for a pair of opening dates everywhere: `Returning members Aug 28 · new members Sep 3` (middot, second clause lowercase, no semicolon).
- The season card note states the state in words (open, the upcoming dates, or closed); it never shows a past opening date as a schedule.
- The closed state names the reopen months.
- A CTA links out; a same-page anchor is not a CTA. The hero never points at content already visible beneath it.
- The yaml fallback labels for the no-API build stay in `home.yaml`; the schema and `registrationCta.ts` defaults are a later change.

## Banned (project-specific, on top of the shared bans)

- Stat boxes (tinted or bordered slabs) and mint-colored numbers. The FactStack is the sanctioned form.
- Pill emoji badges (✦, ★, etc.).
- Arrow glyphs in link or button text. (v1 reserved `→` for the home hero CTA; the CTA never used one and does not need it.)
- Identical three-column card grids.
- Card-shaped components anywhere on the home page.
- A perimeter border around a photo group; photo groups separate with hairline gaps only.
- Decorative parallax. Scroll reveals. Staggered entrances.
- Loading spinners, skeletons, shimmer.
- Hover lift, hover scale, hover shadow, hover background wash on rows.
- A second display typeface beyond the one display cut.
- Any serif typeface.
- Any mono typeface for non-code content.
- The display cut on paragraphs, h3s, stat values, list rows, buttons, or labels.
- Uppercase tracked labels as decoration; uppercase on headings, buttons, dates, or times; any uppercase spec other than `.seam` and `.label-caps`.
- `text-[Npx]`, `tracking-[...]`, arbitrary `ch` measures, arbitrary color values, and `leading-*` on type roles at call sites.
- Opacity modifiers standing in for tokens (`text-ink/80`, `text-paper/60`).
- Hand-built ledger rows, seams, stat stacks, buttons, prose wrappers, or photo grids where the primitive exists.
- Dead variants, dead props, dead plugins: `global.css` and `tailwind.config.ts` ship only rules the site uses (no forms plugin, no prose code theming, no mint blockquote rule).
- Any color outside the tokens above.

## Accessibility (visual layer)

- Body text minimum 16px on mobile, 17px on desktop (`.type-body` delivers both). No type below 0.75rem.
- Every text/background pairing on every page passes WCAG AA; the contrast table above is measured and is the reference. Every new pairing is measured before it ships.
- Focus rings: 2px mint on navy and navy-deep, 2px navy on paper. Always visible on keyboard navigation, never transitioned. The ring color is decided by the nearest surface, not by a placeholder background on the focused element: `[data-photo-mosaic]` and the lightbox are in the surface map, and photo tiles use an inset mint ring (`outline-offset: -3px`) that reads over any photo.
- All interactive elements ≥44×44px on mobile, including inline section links, the conditions venue link (`[data-location] a[data-source-link]` gets `inline-flex min-h-11 items-center`), the fever cell, and the lightbox controls.
- Every button shows the pointer cursor.
- Reduced motion: durations and delays zeroed; hero photo no fade; live conditions still refreshes silently.
- Live Conditions: ARIA live region announces material wax-recommendation changes (e.g., temperature crosses a wax band) for screen readers, as `${name} wax recommendation changed: ${wax_label}`.
- The document outline is one h1 and no skipped levels on every page.

## Build guards

The brand primitives are guarded by a small dist-grep build test (`tests/brandPrimitives.test.mjs`): no `text-[Npx]` and no `tracking-[` in dist HTML; at most one `.seam` per band; `border-t-[3px] border-coral` exactly once per page that mounts CTAStrip; footer links in nav order; no raw `oklch(` outside `global.css` and `tailwind.config.ts`. `global.css` and `tailwind.config.ts` are the only places a size, color, or spacing value is defined.

## changelog from v1

- Theme: added the "quiet ledger wins" sentence: the June and July rounds chose that posture and reviewers kept re-litigating it (GD-27, CS-37)
- Color, tokens: hex column replaced with the resolved values; Flask navy difference recorded as accepted: v1's hex estimates were wrong and shipped into `theme-color` and the logo fills (CO-3, CO-10, CO-12)
- Color, token uses: mint's use rewritten (hero h1, CTAStrip h2, data, labels, links) and paper-card demoted to a placeholder tint: the site's calmer reading of mint serves the ledger posture (CO-7, CS-32, GM-10, CO-15)
- Color, register: "single moment of paper" became two named paper moments (mission panel, closing wax-room-plus-sponsors chapter), never adjacent: the sponsor logos need paper honestly and the strip read as an add-on (CO-4, SP-7, GM-17, GD-6)
- Color, register rules: added slate-not-opacity on paper, three tones on navy, headings-on-navy rule, coral-as-state, compact-strip live dot, accent budget: the site had thirteen text tints doing the work of three tokens and coral on outage states (CO-1, TY-30, CS-8, CO-24, CO-5, CO-6, CO-21, CO-25)
- Color, links: three link roles as classes: four recipes and a seven-utility string pasted seven times (CO-8, CO-14, CS-4, MO-7)
- Color, hairlines: two weights per surface as classes; chrome edges move from mint/10 to mint/15: seven rule tints, the chrome seams near invisible (CO-13, CS-6)
- Color, buttons: one primitive, one recipe per surface, no paper hover on navy, content-width everywhere: four button definitions shipped (CO-17, CS-7, GD-10, TY-20, CS-28)
- Color, data colors: the four wax chip colors named as tokens with a chip-only rule: the only raw values outside the token files (CO-11, CS-41)
- Color, literals: theme() rule with the logo-fill exception (CS-13, CO-3, CO-12)
- Color, contrast table: replaced with measured values and the alpha pairings in use; added the measure-before-ship rule and the AA floor: five of six v1 figures were wrong, slate/paper in the dangerous direction (CO-10, CO-1)
- Color, banned: gradient exception rewritten for the two functional scrims; added the third-dark ban; arbitrary color values named: the lightbox was ink, a third dark (CO-20, GM-12, CO-15)
- Typography, families: Söhne and PolySans Median replaced by what ships, Archivo Variable and PolySans BulkyWide, with the single-weight and subset facts: v1 named fonts the site never used (TY-3, CS-14, GD-4)
- Typography, display cut: "2-3 places" became a role rule (h1, h2, prominent temperatures only): 14 to 18 display elements per page (TY-1, TY-13, TY-14, TY-21, TY-22, TY-25, GD-26, GM-7)
- Typography, scale: every role is a named clamp() utility defined once; added h2-longform, statement, long-form body, stat, label-caps, seam, button rows; display weight 700; inner h1 desktop 4.0rem: no clamp existed and h2 rendered at six sizes (TY-2, TY-4, TY-5, TY-6, TY-9, TY-10, TY-13, TY-15, TY-16, TY-17, TY-29, GM-7, GM-3)
- Typography, mechanics: `--body-lh` by surface, two measures plus 44ch statement, balance on h1/h2, captions never uppercase, button label sizes, prose theme, FactStack stat spec: each was set per call site or not at all (TY-11, TY-12, CS-43, TY-18, GD-14, TY-19, TY-20, TY-15, CS-9, TY-14, CS-3)
- Typography, labels and seams: the eyebrow clause rewritten as two utilities, seams once per band and at most three per page, data labels do not count, uppercase banned on headings/buttons/dates/times, floor 0.75rem: the June and July rounds accepted small-caps seams and the site shipped nine specs (TY-7, TY-8, TY-9, CS-5, GM-6, GM-31, GD-27, SP-24, TY-28, TY-32)
- Typography, outline: every band has a heading; seam becomes the h2 when no heading is passed (TY-26)
- Layout, gutter: one clamp token and one utility, no px-* beside it: two gutter systems staggered every page by 16px (SP-4, CS-10)
- Layout, container: one 1280 container and a left-aligned reading column on the grid; the 1080 inner width dropped: the site had five widths and the reading column was centered like a blog (SP-5, CS-31, GD-13)
- Layout, rhythm: three named band rhythms, adjacency rule, seam gap, mission panel padding, prose first-h2 rule: twenty-one paddings and 210px holes between same-surface bands (SP-2, SP-3, SP-8, SP-28, CS-30, GD-5, GM-11, GM-23)
- Layout, photo groups: one grammar (flush, hairline gaps, no border, no empty cell, portrait never wide, mobile rhythm): four hand-built grammars (SP-14, SP-15, SP-27, SP-29, CS-34, GD-29, GM-21, GM-22, GM-18, MO-12, MO-13)
- Components, primitives: added Seam, Ledger, FactStack, Button, PhotoStrip, SectionHeader, ProseColumn, WaxEntryRow with fixed values: every good decision was made by hand ten times (CS-1, CS-2, CS-3, CS-7, CS-9, CS-16, CS-29, CS-34, SP-12, SP-13, GD-23, GD-30, GM-32)
- Components, table rewritten to the shipped site: HeroInner (ruled masthead, FactStack, photo band), MissionPanel (full-bleed band, statement), SeasonsGrid (hairline cells, fact rows, seam on about), PhotoMosaic (hairline grid, scrim, crops, seam everywhere), Lightbox (navy-deep, chevrons), CoachEntry (4/7, square), TripsTable (ledger), SponsorWall (ruled rows), WaxRoomFeed (closing chapter), WaxEntry (ruled snapshot), CTAStrip (rhythm, mounts), Footer (logo, nav order, no strip), MobileNavPanel (logo, no strip), Nav: eleven rows described reversed decisions (CS-37, SP-19, SP-20, SP-21, SP-22, SP-23, SP-9, GD-28, CS-33, SP-10, CS-26, GD-22, GM-28, TY-24, CO-16, SP-16, GD-15, GM-20, GD-20, GM-24, GM-13, GM-14, GM-29, TY-21, CS-17, SP-6, CS-20, SP-17, GD-19)
- Components, removed: TripEntry deleted; dead variants and props listed for deletion (MO-21, CO-18, SP-11, CS-11)
- Signature device: v1 body kept verbatim (fixed identity); "As built" addendum records the real venues, the Trail report name, the clock-time stamp, the fever cell and its ♪, no expand-on-click, the compact placement under the nav, the dryland dateline, the unavailable single line, and the cell-rule direction (CP-26, CP-27, MO-4, CS-24, CS-27, GD-7, GD-8, TY-22, TY-23, SP-25, SP-19, GM-13)
- Motion: rewritten as an explicit arrivals list with one easing token; hero timing corrected to what ships (400/250/120, 8px, once per load, CTA joins the gesture); conditions first fill replaces the refresh flicker; mobile panel codified; lightbox entrance kept at 200ms as CSS-only; hover is color only; focus rings never transition; delays zeroed under reduced motion; pointer cursor: the clause described a site that was never built and the code used two curves (MO-2, MO-3, MO-4, MO-5, MO-6, MO-7, MO-8, MO-10, MO-25, CS-15, GD-3, GM-2, GD-9, GD-12)
- Iconography: Lucide replaced by the three inline strokes that ship; arrow glyphs banned in controls; ♪ exception recorded (CS-23, MO-9, CP-28, CS-24)
- Imagery: consent rule rewritten around CONSENT.md; watermark ban; crop rule with `position: attention`; masthead band geometry and per-page positions; formats honest (webp, avif hero only); no BlurHash; orphan assets rule; srcset ceiling (MO-11, MO-24, MO-12, MO-13, MO-14, MO-15, MO-16, MO-17, GD-33, GD-31, MO-23, MO-3, MO-20, MO-22, SP-21)
- OG image: new section: the share card was an anonymous sunset next to three other clubs (TY-31, CO-9, SP-26, MO-19, CS-38, GM-30, GD-25)
- 404: new section: three headlines for one message (TY-32, CP-17, GD-24, CP-16, CS-36)
- Empty states: new section: production shows both empty states today (SP-18, CS-35, GD-21, GM-26, GM-27, CP-18, CP-19)
- Copy: new section with the July 18 voice rules verbatim, punctuation, names and facts, house formats, masthead-fact rule, one-name rule, titles and meta, alt text, single source: the pages the refresh skipped still read like a template (CP-2, CP-3, CP-4, CP-9, CP-10, CP-11, CP-12, CP-13, CP-14, CP-15, CP-16, CP-20, CP-21, CP-22, CP-23, CP-24, CP-25, CP-29, CP-30, CP-31, CP-32, CP-33, CP-34, CP-35, CP-36, CP-37, CP-38, CP-39, CP-41, CS-18, GM-19, GD-32, GD-16)
- Registration copy: new table per state and per render site; labels never name a season; coming-soon CTA links out; card note is state-aware; closed names the reopen months; one date-pair format; new-member date while only returning is open (CP-1, CP-5, CP-6, CP-7, CP-8, GM-4, GM-5, GM-15, GD-11, TY-28, CO-23)
- Banned: stat-box line rewritten around FactStack; arrow reservation dropped; perimeter borders, hover lifts, row washes, uppercase misuse, arbitrary utilities, opacity-for-tokens, hand-built patterns, dead CSS added (CS-25, CS-23, SP-15, CS-42, CO-24, CS-11, CS-12, CO-19)
- Accessibility: contrast floor, focus-by-surface with inset tile ring, 44px on inline links and the venue link, pointer cursor, announcement template, outline (CO-2, GM-16, TY-8, MO-8, GD-12, TY-26)
- Build guards: new section: nothing this contract names was tested, which is why it drifted (CS-39)
