# Marketing Site Design Feedback Round, June 2026

Design spec for changes to the Astro marketing site (twincitiesskiclub.org) responding to feedback from a graphic designer friend of the club. Each item was assessed against the site's quiet, editorial "ledger" design language (hairline rules, small-caps seams, navy/mint/paper palette). Posture agreed with Rob: accept the underlying critiques, execute them in the site's own language, skip icons and chips.

Work happens on `main` in the site worktree (`/Users/rob/env/tcsc-trips-site`). All copy follows the club voice rules: plain register, no em dashes (use commas, middots, hyphens).

## Feedback disposition summary

Accepted (reinterpreted where noted):
- Logo "breaking" report: she misread the new abstract pill mark as a broken image. Fix is a brand decision, not a format swap: adopt the original club logo in the nav.
- "Register" button misleading while closed: relabel via the existing state machine.
- Practices section scannability, per-season registration statuses, named locations.
- Founded/located/size facts too quiet: stat-stack treatment.
- Inner page headers flat, pages feel blank: stat facts + photo bands.
- About founded paragraph emphasis, Community heading sizes, photos across About/Community/Racing.
- Sponsors as a home section: added as a strip, page kept.

Rejected:
- Replacing the logo SVG with a PNG (quality downgrade; root cause was brand recognition, not rendering).
- Chips and icons (off the site's design language).
- Deleting the sponsors page (it is a sponsorship pitch asset; URL is linked from nav and footer).
- Renaming the section to "Sessions" ("Seasons" chosen instead).

## 1. Logo

- Replace the inline pill-grid SVG and the separate "TCSC" wordmark span in `site/src/components/Nav.astro` (lines 13-25) with the original club logo, source: `app/static/images/tcsc-logo.svg` in the main repo (viewBox `0 0 358.78 54.47`).
- Recolor for the navy header: letter paths (`#202a44`) become paper (`oklch(0.985 0.003 90)` or `#fbfbfa` equivalent), ski polygons stay mint (`#aaf0c1`).
- Fills must be explicit attribute values on the SVG, not Tailwind utility classes, so the mark cannot break outside CSS scope.
- Render at the same header height as today (around 22px tall; the mark is roughly 6.6:1, so about 145px wide). Keep `aria-hidden="true"` on the SVG and keep the accessible label on the home link.
- Footer wordmark and favicon are unchanged. The pill favicon stays (a five-letter lettermark is unreadable at 16px).
- MobileNavPanel: confirm whether the mobile drawer shows a logo; if it reuses Nav's markup, nothing extra to do.

## 2. Registration closed-state copy

Content-only changes (Keystatic-editable, `site/src/content/pages/home.yaml`):
- `cta_closed_label`: `Register` becomes `Registration opens Aug/Sep`. This flows to the desktop nav, mobile nav panel, home hero, and bottom CTA strip through `getRegistrationCta()` and `CtaForState`.
- `cta_closed_url` stays `https://tcsc.ski`.

Code copy change in `site/src/pages/index.astro` (closed/coming_soon subhead, currently line 53):
- `Registration reopens in the fall. Intermediate ability and up, no racing required.` becomes `Registration reopens Aug/Sep. Intermediate ability and up, no racing required.`

Registration windows (facts from Rob, 2026-06-11): Fall/Winter opens Aug/Sep; Spring/Summer opens Apr/May. Each season has its own window.

## 3. Seasons section (home page and About reuse)

### Naming
- `SectionBand` seam on home (`site/src/pages/index.astro` line 78): `Practices` becomes `Seasons`.
- About page band heading (`site/src/pages/about.astro` line 26): `Practices` becomes `Seasons`.

### Layout (chosen mock: prose + labeled facts)
Rebuild `site/src/components/SeasonsGrid.astro` per season card:
1. Date range (small caps): `September - March` / `May - August`
2. Season name (display, mint on navy / navy on paper)
3. Fee and registration status on one baseline row: fee left, status right.
   - Fall/Winter status: `Registration opens Aug/Sep`, rendered in mint (open-ish, upcoming).
   - Spring/Summer status: `Closed for 2026 · reopens Apr/May`, rendered muted.
4. One character sentence (prose):
   - Fall/Winter: `Dryland until snow flies, then skate and classic workouts on snow, with weekly strength at Balance Fitness Studio.`
   - Spring/Summer: `Pole bounding, running intervals, rollerskiing, and biking, with weekly strength at Balance Fitness Studio.`
5. Three labeled fact lines, identical slots both cards. Labels are small-caps, mint on the navy home variant and mint-deep on the paper About variant:
   - When: `Tuesday + Thursday evenings` (both seasons)
   - Where: `Theodore Wirth · Hyland` / `Theodore Wirth · around the metro`
   - Trips: `Sisu, the Birkie, and more` / `Usually one summer trip`

Shared footer line under the grid is unchanged: `Organized evening practices twice per week, coached by KJ, Greg, Rebecca, and Michael. Dues cover coaching, workout space reservations, and the season's odds and ends.`

Venue facts verified against prod practice data 2026-06-11: Theodore Wirth (primary, Tuesdays), Hyland (secondary), Balance Fitness Studio (strength).

### Data model
Extend the `practice_seasons` collection (`site/src/content.config.ts`, `site/keystatic.config.ts`, and both yaml files in `site/src/content/practice_seasons/`):
- Add: `registration_note` (string), `registration_open` (boolean, drives mint vs muted styling), `when` (string), `where` (string), `trips` (string).
- Keep `summary` (now the one character sentence).
- Remove `what_included` (empty everywhere today; the new layout replaces it). Remove its rendering from SeasonsGrid.

Both SeasonsGrid variants (`navy` on home, `paper` on About) get the new layout.

## 4. Mission panel facts (home)

`site/src/components/MissionPanel.astro`: replace the small grey `facts` list with a stat stack beside the mission paragraph (chosen mock: vertical divider variant):
- Left: mission paragraph as today.
- Right column: vertical hairline on its left (`border-ink/15`), vertically centered stack of three stats, each value-over-label:
  - `2020` / small-caps `Founded`
  - `Minneapolis · St. Paul` / small-caps `Based in`
  - `80+` / small-caps `Skiers at the 2026 Birkie`
- Values in mint-deep (`oklch(0.52 0.13 155)`), bold, display scale (the year and `80+` larger than the cities line). Labels small-caps slate.
- Restructure the hardcoded `facts` array into `{value, label}` pairs in the component. CMS promotion is out of scope.
- No icons.

## 5. Inner page headers (About, Community, Racing)

`site/src/components/HeroInner.astro` and `site/src/layouts/InnerPageLayout.astro` (chosen mock: stat facts + photo band):
- `facts` prop changes from `string[]` to `{value, label}[]`, rendered as the same mint-deep stat treatment as the mission panel (smaller scale), bottom-aligned in the right column with a left hairline.
- New optional props on InnerPageLayout/HeroInner: `photo` (image import), `photoAlt` (string), optional focal position. When present, render a full-bleed photo band directly under the masthead grid, roughly 230-280px tall, `object-fit: cover`.
- Pages that pass no photo render exactly the masthead (Coaches, Wax Room, etc. unchanged).

Per-page facts (relabeled as value/label pairs):
- About: `501(c)(3) nonprofit` / `Status`, `Minneapolis · St. Paul` / `Based in`
- Community: `Founded 2020` becomes value `2020` / label `Founded`, `Photos by club members` / `Credits`
- Racing: `80+` / `Skiers at the 2026 Birkie`, `Always voluntary` / `Racing`

Header photo assignments (see section 6 for files): About gets the team banner photo, Community the canoe golden-hour, Racing the frosty-woods race crew.

## 6. Photos

Selected by Rob 2026-06-11 from 493 candidates (multi-agent curation over `migration/slack_photos/`, judge notes retained below). All photos are consent-cleared per Rob; the standing exclusion is professional race-gallery photography (rights, not consent).

Every new photo runs the standard port pipeline: exif_transpose, resize (max 2560px long edge, no upscaling), quality 90 progressive, `photo_alt` written, rows added to `migration/port-manifest.csv` and `migration/CONSENT.md`, `python -m scripts.wix_scrape.verify` exits 0. New `site/src/content/photos/*.yaml` entries get `show_on_home: false` and an appropriate `event_tag` unless noted.

Source files in `migration/slack_photos/`:

About:
- Header band: `2024-03-30_1711812078-797759_0.jpg` (about 50 members, TCSC banner). Crop: slight trim of dead space above heads; focal center 40%.
- Body, near "Who joins TCSC": `2024-08-13_1723597154-617769_0.jpg` (golden-hour rollerski group). Crop: trim parking-lot edges if needed.

Community:
- Header band: `2024-07-09_1720579793-084489_1.jpg` (canoe social, wide landscape, full-bleed friendly).
- Near "Our members" prose, a photo cluster (pair or two-up rows): `2024-05-16_1715917971-931869_0.jpg` (backyard party, crop modestly from top), `2026-04-23_1776954511-019769_2.jpg` (running-group selfie, slight bottom crop), `2023-01-08_1673242364-942339_1.jpg` (five members, portrait, good for side-by-side pairing), `2024-03-03_1709501583-457379_0.jpg` (lakeside picnic, crop to lift faces).
- "What we've done" groups: `2024-01-17_1705546321-840949_0.jpg` (Second Harvest volunteering, portrait; crop toward landscape) anchors Volunteering; `2026-04-12_1776027078-470899_0.jpg` (barn banquet, string lights) anchors Socials.
- The existing 22-photo mosaic at the bottom stays as is.

Racing:
- Header band: `2023-01-21_1674324661-077579_0.jpg` (six members in bibs, frosty woods, landscape).
- Photo strip near the Races list (5): `2023-01-28_1674942658-549799_0.jpg` (Ski de She trio), `2022-02-25_1645852380-232989_0.jpg` (Korte medals), `2024-02-23_1708738564-829599_1.jpg` (Birkie start pair), `2026-02-14_1771096714-097109_0.jpg` (Finlandia podium, trim right edge), `2024-02-07_1707360103-835559_0.jpg` (skijor with dog, crop left to remove kneeling photographer).
- OPEN CHECK before shipping: the skijor photo was posted by a now-deactivated member and has a slightly professional look. Confirm it is member-shot before publishing; drop it if unconfirmed (the strip works with 4).

Layout intent for body photos: quiet ruled placements consistent with the ledger language (single full-width images or simple two-up pairs inside the existing content column, hairline-separated), not new mosaic instances. Exact arrangement is an implementation detail; mixed orientations noted above should guide pairing.

## 7. About page founded paragraph

`site/src/content/pages/about.mdoc` first paragraph ("TCSC was founded in 2020...") gets a lede treatment: display font, larger size (around text-xl/2xl), navy. No background box. Implementation choice (first-paragraph CSS selector on the prose wrapper in `about.astro`, or moving the lede out of the mdoc body into frontmatter) is left to the implementation plan, with a preference for the CSS route so the mdoc stays one document.

## 8. Community group headings

`site/src/pages/community.astro` (line 39): the takeaway group h3s (Volunteering, Members who coach, Socials) move from `text-base font-semibold` to display-scale headings (around `font-display text-2xl font-semibold text-navy`), keeping the 3/9 ledger grid.

## 9. Sponsors strip on home

- New slim band on the home page between WaxRoomFeed and the bottom CTAStrip: `SectionBand` seam `Our sponsors`, the two sponsor logos (Twin Cities Orthopedics, Kwik Trip) at modest size, linking to their sites (rel=sponsored, matching SponsorWall behavior), plus a quiet text link to `/sponsors`.
- Implementation: either reuse `SponsorWall` with a compact variant prop or a small dedicated strip component; prefer the variant prop to keep one source of sponsor rendering.
- `/sponsors` page, nav, and footer are unchanged.

## Out of scope this round

- Favicon redesign, footer logo, OG image updates.
- CMS promotion of mission facts.
- Nav link slimming (Sponsors stays in the top nav).
- Trail report strip, WaxRoomFeed, trips pages: untouched.
- The home PhotoMosaic and its 9 `show_on_home` photos: untouched.

## Verification

- `npx astro check` and `NODE_ENV=production npx astro build` pass (10 pages).
- `python -m scripts.wix_scrape.verify` exits 0 with the new manifest rows.
- `pytest tests/conditions tests/wix_scrape` still green (71 tests).
- Visual pass on home, about, community, racing, sponsors at mobile and desktop widths; confirm the logo renders crisply at header size and the seasons cards stack on mobile.
- Confirm closed-state CTA copy appears in all four render sites.
