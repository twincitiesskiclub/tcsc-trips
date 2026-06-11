# Marketing Site June 2026 Feedback Round Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved design spec at `/Users/rob/env/tcsc-trips/docs/superpowers/specs/2026-06-11-marketing-site-design-feedback-design.md` (note: the spec lives in the MAIN checkout, not the worktree this plan executes in): heritage logo in the nav, honest closed-registration copy, rebuilt Seasons section, mission stat stack, inner-page headers with stat facts + photo bands, 14 new member photos placed across About/Community/Racing, About lede, larger Community headings, and a sponsor strip on home.

**Architecture:** All work is in the Astro static site (`site/`) inside the git worktree `/Users/rob/env/tcsc-trips-site`, on a new branch off `main`. Content-collection schema changes (practice_seasons) land before the component that reads them. New photos are direct page imports (NOT `content/photos` entries; entries would also inject them into the Community bottom mosaic and duplicate them on that page - this is a deliberate, documented deviation from spec section 6's "content entries" line, allowed by its "arrangement is an implementation detail" clause). Every committed image gets a `migration/port-manifest.csv` row and a `migration/CONSENT.md` row so `scripts/wix_scrape/verify.py` stays green.

**Tech Stack:** Astro 5 + content collections (zod), Keystatic (local mode), Tailwind (tokens: navy/mint/mint-deep/paper/ink/slate), astro:assets `Image`, Pillow for photo processing, pytest for the wix_scrape/conditions suites.

**Working directories:**
- Repo root (worktree): `/Users/rob/env/tcsc-trips-site` - git, python, verify.py, pytest (activate venv: `source env/bin/activate`)
- Site: `/Users/rob/env/tcsc-trips-site/site` - npm / astro commands

**Verification commands used throughout:**
- `cd /Users/rob/env/tcsc-trips-site/site && npx astro check` - type/template check
- `cd /Users/rob/env/tcsc-trips-site/site && NODE_ENV=production npx astro build` - must end "10 pages" with no errors
- `cd /Users/rob/env/tcsc-trips-site && source env/bin/activate && python -m scripts.wix_scrape.verify` - must exit 0
- NEVER run bare `pytest` (binds prod DB); use `pytest tests/conditions tests/wix_scrape`

---

### Task 1: Branch setup

**Files:** none (git only)

- [ ] **Step 1: Create the feature branch off main in the worktree**

```bash
cd /Users/rob/env/tcsc-trips-site
git status --porcelain   # expect only the untracked dns-rollback json; stop and ask if site/ files show
# Note: `git stash list` shows ~5 pre-existing stashes from OTHER branches; they are unrelated, ignore them.
git checkout -b feat/site-design-feedback main
git log --oneline -1   # expect e3c5e68 docs(site): design spec... (or newer main)
```

Note: the worktree currently sits on `chore/dns-cutover-robots`; `main` lives in the other checkout but branching from the `main` ref works fine here (worktrees share refs). The untracked `migration/dns-rollback-2026-06-11.json` stays untracked; do not add it.

- [ ] **Step 2: Baseline build to prove a clean start**

```bash
cd site && npx astro check && NODE_ENV=production npx astro build
```

Expected: check passes (0 errors), build ends with `10 page(s) built`.

---

### Task 2: Heritage logo in the nav

**Files:**
- Modify: `site/src/components/Nav.astro:13-25`

The current mark is an abstract pill grid + a separate "TCSC" wordmark span. Replace BOTH with the original club logo (source: `app/static/images/tcsc-logo.svg` in the main repo), recolored for the navy bar: letters paper, skis the heritage mint `#aaf0c1`. Fills are explicit attributes (never Tailwind classes) so the mark cannot break outside CSS scope.

- [ ] **Step 1: Replace the logo markup**

In `site/src/components/Nav.astro`, replace lines 13-25 (the `<svg ...>...</svg>` block AND the `<span class="font-display ...">TCSC</span>` line) with:

```html
      <svg width="145" height="22" viewBox="0 0 358.78 54.47" aria-hidden="true">
        <!-- Heritage club logo (from app/static/images/tcsc-logo.svg), recolored
             for the navy bar. Fills are hardcoded on purpose: this mark must
             survive outside Tailwind scope (no class-based fills). -->
        <g fill="#aaf0c1">
          <polygon points="105.53 42.42 107.8 35.26 77.36 35.26 74.61 42.42 105.53 42.42"/>
          <path d="M22.82,35.26c-2.2,0-20.29,0-21.74,1s-1.44,4.3,0,5.26,19.54,1,21.74,1H45l2-7.16Z"/>
          <polygon points="173.35 35.26 163.99 35.26 161.65 42.42 173.35 42.42 180.19 42.47 182.49 35.2 173.35 35.26"/>
          <polygon points="237.75 35.02 235.25 42.65 255.83 42.74 258.31 34.93 237.75 35.02"/>
          <path d="M357.69,37.57c-4.46-3.44-24.53-2.9-26.73-2.9l-17,.08-2.67,8.17L331,43c2.2,0,22.27-.06,26.73-2.9C359.14,39.15,359.14,38.53,357.69,37.57Z"/>
          <polygon points="261 20.56 263.48 12.74 236.5 12.84 234.01 20.45 261 20.56"/>
          <path d="M331,20.82c2.2,0,22.27-.06,26.73-2.9,1.45-1,1.45-1.58,0-2.54-4.46-3.44-24.53-2.9-26.73-2.9l-13,.07-2.68,8.19Z"/>
          <polygon points="173.35 20.23 185.91 20.28 188.22 13.01 173.35 13.07 162.31 13.07 159.97 20.23 173.35 20.23"/>
          <path d="M22.82,13.07c-2.2,0-20.29,0-21.74.95s-1.44,4.3,0,5.26,19.54.95,21.74.95h9.1l2-7.16Z"/>
          <polygon points="88.23 13.07 85.54 20.23 110.43 20.23 112.7 13.07 88.23 13.07"/>
        </g>
        <g fill="#fbfbfa">
          <path d="M53.13,14.06H38.33V1.33H80.66V14.06H65.86V53.14H53.13Z"/>
          <path d="M130.39,32.56c0,5.7.37,9.18,5.84,9.18s6.07-2.89,6.37-8l12.28,2.73c0,4.89-1.11,18-18.65,18s-18.57-13.1-18.57-18V18c0-4.88,1-18,18.57-18s18.65,13.1,18.65,18L142.6,20.72c-.3-5.1-.89-8-6.37-8s-5.84,3.48-5.84,9.18Z"/>
          <path d="M217.26,18.65c-.59-4.52-3.18-5.77-6.81-5.77-2.88,0-4.66,1.7-4.36,3.4,1,5.77,24.79,5.63,24.79,22.65,0,2.22-2.52,15.32-20.06,15.32-15.83,0-19.31-10-19.31-16.51L204.09,35c.37,5.33,3.11,6.52,6.73,6.52s6.29-2.15,5.85-4.15c-1.41-6.29-24-4.88-24-21.9C192.54,13.25,193.88.15,210.45.15c15.54,0,19.32,9.25,19.32,15.76Z"/>
          <path d="M281.23,32.56c0,5.7.37,9.18,5.85,9.18s6.07-2.89,6.36-8l12.29,2.73c0,4.89-1.11,18-18.65,18s-18.58-13.1-18.58-18V18c0-4.88,1-18,18.58-18s18.65,13.1,18.65,18l-12.29,2.74c-.29-5.1-.89-8-6.36-8s-5.85,3.48-5.85,9.18Z"/>
        </g>
      </svg>
```

The `<a href="/" class="flex items-center gap-3.5" aria-label="Twin Cities Ski Club home">` wrapper stays exactly as is (the aria-label now carries all the accessible naming since the wordmark span is gone).

- [ ] **Step 2: Check and build**

```bash
cd /Users/rob/env/tcsc-trips-site/site && npx astro check && NODE_ENV=production npx astro build
```

Expected: 0 errors, 10 pages.

- [ ] **Step 3: Visual check**

```bash
cd /Users/rob/env/tcsc-trips-site/site && npx astro dev
```

Open http://localhost:4321 - the nav shows the TCSC lettermark with mint ski lines threading through it, white letters, roughly the same header height as before. Check one inner page (/about) too. Stop the dev server.

- [ ] **Step 4: Commit**

```bash
cd /Users/rob/env/tcsc-trips-site
git add site/src/components/Nav.astro
git commit -m "feat(site): heritage club logo in the nav, recolored for navy"
```

---

### Task 3: Closed-state registration copy

**Files:**
- Modify: `site/src/content/pages/home.yaml:11`
- Modify: `site/src/pages/index.astro:50-53`

- [ ] **Step 1: Relabel the closed CTA**

In `site/src/content/pages/home.yaml`, change:

```yaml
cta_closed_label: Register
```

to:

```yaml
cta_closed_label: Registration opens Aug/Sep
```

(`cta_closed_url` stays `https://tcsc.ski`.)

- [ ] **Step 2: Name the months in the CTA strip subhead**

In `site/src/pages/index.astro`, change the closed-state branch of `ctaStripSubhead` (line 53):

```ts
    : 'Registration reopens in the fall. Intermediate ability and up, no racing required.';
```

to:

```ts
    : 'Registration reopens Aug/Sep. Intermediate ability and up, no racing required.';
```

- [ ] **Step 3: Build and verify the copy reaches all four render sites**

```bash
cd /Users/rob/env/tcsc-trips-site/site && NODE_ENV=production npx astro build
grep -c "Registration opens Aug/Sep" dist/index.html
grep -c "Registration opens Aug/Sep" dist/about/index.html
```

Expected: build OK; `dist/index.html` count is exactly 4 (nav + mobile panel + hero + strip), `dist/about/index.html` exactly 2 (nav + mobile panel). A lower count means a render site silently dropped the label.

- [ ] **Step 4: Commit**

```bash
cd /Users/rob/env/tcsc-trips-site
git add site/src/content/pages/home.yaml site/src/pages/index.astro
git commit -m "feat(site): honest closed-state registration copy with real months"
```

---

### Task 4: practice_seasons schema + content

**Files:**
- Modify: `site/src/content.config.ts:114-126` (practice_seasons collection)
- Modify: `site/keystatic.config.ts` (practice_seasons collection fields)
- Modify: `site/src/content/practice_seasons/fall-winter.yaml`
- Modify: `site/src/content/practice_seasons/spring-summer.yaml`

The schema is `.strict()`, so config and yaml must change together in this task. SeasonsGrid still references `what_included` until Task 5, so this task removes that reference too in the same commit; the two tasks could be merged, but keeping the data change reviewable on its own is worth it - the build gate at the end of THIS task therefore happens after Task 5's component change. Follow the steps in order across Tasks 4 and 5 and commit once at the end of Task 5.

- [ ] **Step 1: Replace the practice_seasons schema in `site/src/content.config.ts`**

Replace the whole `const practice_seasons = defineCollection({...});` block with:

```ts
const practice_seasons = defineCollection({
  loader: dataLoader('practice_seasons'),
  schema: z
    .object({
      slug: z.string(), // display name ("Season name")
      date_range: z.string(),
      fee_cents: z.number().int(),
      summary: z.string(),
      // Per-season registration status line ("Registration opens Aug/Sep").
      // registration_open=true renders it in the accent color, false muted.
      registration_note: z.string(),
      registration_open: z.boolean().default(false),
      // Parallel scannable facts, identical slots on every season card.
      when: z.string(),
      where: z.string(),
      trips: z.string(),
      order: z.number().int().default(0),
    })
    .strict(),
});
```

- [ ] **Step 2: Update the Keystatic collection**

In `site/keystatic.config.ts`, inside the `practice_seasons: collection({...})` schema, replace the `what_included` line:

```ts
        what_included: fields.array(fields.text({ label: 'Item' }), { label: 'What is included' }),
```

with:

```ts
        registration_note: fields.text({ label: 'Registration status line', validation: { isRequired: true } }),
        registration_open: fields.checkbox({ label: 'Highlight registration line (accent color)', defaultValue: false }),
        when: fields.text({ label: 'When (fact line)', validation: { isRequired: true } }),
        where: fields.text({ label: 'Where (fact line)', validation: { isRequired: true } }),
        trips: fields.text({ label: 'Trips (fact line)', validation: { isRequired: true } }),
```

- [ ] **Step 3: Rewrite `site/src/content/practice_seasons/fall-winter.yaml`** (full file)

```yaml
slug: Fall / Winter
date_range: September - March
fee_cents: 20500
summary: >-
  Dryland until snow flies, then skate and classic workouts on snow, with
  weekly strength at Balance Fitness Studio.
registration_note: Registration opens Aug/Sep
registration_open: true
when: Tuesday + Thursday evenings
where: Theodore Wirth · Hyland
trips: Sisu, the Birkie, and more
order: 1
```

- [ ] **Step 4: Rewrite `site/src/content/practice_seasons/spring-summer.yaml`** (full file)

```yaml
slug: Spring / Summer
date_range: May - August
fee_cents: 10500
summary: >-
  Pole bounding, running intervals, rollerskiing, and biking, with weekly
  strength at Balance Fitness Studio.
registration_note: Closed for 2026 · reopens Apr/May
registration_open: false
when: Tuesday + Thursday evenings
where: Theodore Wirth · around the metro
trips: Usually one summer trip
order: 2
```

- [ ] **Step 5: Confirm the build now FAILS (red)**

```bash
cd /Users/rob/env/tcsc-trips-site/site && npx astro check 2>&1 | head -20
```

Expected: `astro check` reports a ts(2339) in `SeasonsGrid.astro`: `what_included` does not exist on the regenerated season data type. (Zod validation itself passes - the yamls were fully rewritten to match the new schema; the red comes from the stale component reference.) That is the signal to proceed to Task 5; do NOT commit yet.

---

### Task 5: SeasonsGrid rebuild + section rename

**Files:**
- Modify: `site/src/components/SeasonsGrid.astro` (full rewrite of the card body)
- Modify: `site/src/pages/index.astro:78` (seam)
- Modify: `site/src/pages/about.astro:26` (band heading)

- [ ] **Step 1: Rewrite `site/src/components/SeasonsGrid.astro`** (full file)

```astro
---
// SeasonsGrid: two-up grid of practice seasons. Per card: date range, name,
// fee + per-season registration status on one row, a one-sentence character
// summary, then three labeled fact lines (When / Where / Trips) that use
// identical slots on every card so the seasons scan in parallel.
// Renders nothing at all when no seasons exist.
// entry.id is the file-name slug; entry.data.slug is the DISPLAY NAME
// (see content.config.ts header).
import { getCollection } from 'astro:content';

interface Props {
  variant?: 'navy' | 'paper';
  /** Heading level for the season name. Home passes 'h2' after the band
      heading is removed; /about keeps the default 'h3'. */
  headingLevel?: 'h2' | 'h3';
}
const { variant = 'navy', headingLevel = 'h3' } = Astro.props;
const HeadingTag = headingLevel;

const seasons = await getCollection('practice_seasons');
seasons.sort((a, b) => a.data.order - b.data.order || a.id.localeCompare(b.id));

const dollar = (cents: number) => {
  // Whole-dollar fees stay clean ($205); fractional ones keep cents ($205.50).
  const digits = cents % 100 === 0 ? 0 : 2;
  return (cents / 100).toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
};

// Hairline divider: the wrapper carries the tinted divider color as its
// background and the opaque season cells sit on top, so the 1px grid gap
// reads as a single hairline between cells (no doubled per-cell borders,
// no extra perimeter). The last-child:nth-child(odd) rule stretches an odd
// trailing season across both columns so the empty grid cell never exposes
// a half-width tint panel.
const hairline = variant === 'navy' ? 'bg-mint/20' : 'bg-ink/15';
const surface = variant === 'navy' ? 'bg-navy text-paper' : 'bg-paper text-ink';
const accent = variant === 'navy' ? 'text-mint' : 'text-mint-deep';
const muted = variant === 'navy' ? 'text-paper/60' : 'text-slate';
---
{seasons.length > 0 && (
  <div>
    <div
      class:list={[
        'grid md:grid-cols-2 gap-px md:[&>:last-child:nth-child(odd)]:col-span-2',
        hairline,
      ]}
    >
      {seasons.map((s) => (
        <div class:list={['p-8 md:p-10', surface]}>
          <p class:list={['text-sm', muted]}>{s.data.date_range}</p>
          <HeadingTag class="mt-3 font-display font-semibold text-2xl md:text-3xl">{s.data.slug}</HeadingTag>
          <div class="mt-2 flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
            <p class:list={['text-lg font-semibold', accent]}>{dollar(s.data.fee_cents)}</p>
            <p class:list={['text-[13px]', s.data.registration_open ? `font-semibold ${accent}` : muted]}>
              {s.data.registration_note}
            </p>
          </div>
          <p class="mt-4 max-w-prose">{s.data.summary}</p>
          <dl class="mt-6 space-y-2.5 text-sm">
            {[
              ['When', s.data.when],
              ['Where', s.data.where],
              ['Trips', s.data.trips],
            ].map(([label, value]) => (
              <div class="flex gap-4">
                <dt class:list={['w-14 shrink-0 text-[11px] tracking-[0.14em] uppercase font-semibold pt-0.5', accent]}>
                  {label}
                </dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        </div>
      ))}
    </div>
    {/* Dues transparency and shared practice details, rendered once below
        both season columns. Fee line is verbatim from the club's register
        page. */}
    <div class:list={['px-8 md:px-10 py-6', surface]}>
      <p class:list={['text-sm', muted]}>
        Organized evening practices twice per week, coached by KJ, Greg, Rebecca, and Michael. Dues cover coaching, workout space reservations, and the season's odds and ends.
      </p>
    </div>
  </div>
)}
```

- [ ] **Step 2: Rename the section**

In `site/src/pages/index.astro` line 78: `<SectionBand variant="navy" seam="Practices">` becomes `<SectionBand variant="navy" seam="Seasons">`.

In `site/src/pages/about.astro` line 26: `<SectionBand variant="paper" heading="Practices">` becomes `<SectionBand variant="paper" heading="Seasons">`.

- [ ] **Step 3: Check and build (green)**

```bash
cd /Users/rob/env/tcsc-trips-site/site && npx astro check && NODE_ENV=production npx astro build
grep -o 'Registration opens Aug/Sep' dist/index.html | wc -l
grep -c 'Closed for 2026' dist/index.html
```

Expected: 0 errors, 10 pages; the Aug/Sep count on `dist/index.html` is now exactly 5 (the Fall/Winter season card adds one to Task 3's 4), `Closed for 2026` count is 1.

- [ ] **Step 4: Visual check**

`npx astro dev`, open home: the navy band now reads "Seasons", each card shows fee + status on one row and the When/Where/Trips trio aligned across both cards. Check /about (paper variant). Stop the server.

- [ ] **Step 5: Commit (Tasks 4+5 together - the schema and its consumer)**

```bash
cd /Users/rob/env/tcsc-trips-site
git add site/src/content.config.ts site/keystatic.config.ts site/src/content/practice_seasons/ site/src/components/SeasonsGrid.astro site/src/pages/index.astro site/src/pages/about.astro
git commit -m "feat(site): rebuild Seasons section with per-season status and parallel fact lines"
```

---

### Task 6: MissionPanel stat stack

**Files:**
- Modify: `site/src/components/MissionPanel.astro` (full rewrite)

- [ ] **Step 1: Rewrite `site/src/components/MissionPanel.astro`** (full file)

```astro
---
// The home page's single moment of paper (DESIGN.md): a full-bleed band, not
// a floating card. Asymmetric 8/3 split: the mission statement at display
// scale, plus a stat stack of org facts behind a vertical hairline for the
// sponsor doing 20-second due diligence. The facts deliberately avoid
// repeating the mission text's own "501(c)(3)" line.
interface Props { body: string; }
const { body } = Astro.props;
const facts: Array<{ value: string; label: string; big?: boolean }> = [
  { value: '2020', label: 'Founded', big: true },
  { value: 'Minneapolis · St. Paul', label: 'Based in' },
  { value: '80+', label: 'Skiers at the 2026 Birkie', big: true },
];
---
<section class="bg-navy pt-14 md:pt-20">
  <div class="bg-paper text-ink">
    <div class="mx-auto max-w-7xl px-6 py-14 md:py-20 grid gap-10 md:grid-cols-12">
      <p class="md:col-span-8 font-display text-2xl md:text-3xl leading-[1.25] text-navy">{body}</p>
      <ul class="md:col-span-3 md:col-start-10 self-center md:border-l md:border-ink/15 md:pl-7 space-y-5">
        {facts.map((f) => (
          <li>
            <div class:list={['font-display font-semibold text-mint-deep leading-none', f.big ? 'text-2xl md:text-3xl' : 'text-lg md:text-xl']}>
              {f.value}
            </div>
            <div class="text-[11px] tracking-[0.14em] uppercase text-slate mt-1.5">{f.label}</div>
          </li>
        ))}
      </ul>
    </div>
  </div>
</section>
```

- [ ] **Step 2: Check, build, visual**

```bash
cd /Users/rob/env/tcsc-trips-site/site && npx astro check && NODE_ENV=production npx astro build
```

Expected: 0 errors, 10 pages. Dev-server glance at home: facts now read as mint-deep stats with small-caps labels behind a vertical hairline, vertically centered next to the mission.

- [ ] **Step 3: Commit**

```bash
cd /Users/rob/env/tcsc-trips-site
git add site/src/components/MissionPanel.astro
git commit -m "feat(site): mission facts as a stat stack with hairline divider"
```

---

### Task 7: HeroInner stat facts + photo band, all pages migrated

**Files:**
- Create: `site/src/components/heroFacts.ts` (shared Fact type, same pattern as `imageWidths.ts`)
- Modify: `site/src/components/HeroInner.astro` (full rewrite)
- Modify: `site/src/layouts/InnerPageLayout.astro` (props passthrough)
- Modify: `site/src/pages/about.astro:19`, `site/src/pages/community.astro:22`, `site/src/pages/racing.astro:18`, `site/src/pages/coaches.astro:22`, `site/src/pages/extra-training-fun.astro:27`, `site/src/pages/dry-tri.astro:28` (facts prop shape)

The `facts` prop changes shape from `string[]` to `{value, label}[]`, so all six pages that pass it migrate in this task. The photo band props land here too, but no page passes a photo until Tasks 9-12 (the band code is exercised then).

- [ ] **Step 1: Create `site/src/components/heroFacts.ts`, then rewrite `site/src/components/HeroInner.astro`**

`site/src/components/heroFacts.ts` (new file, full contents):

```ts
// Shared masthead fact shape: HeroInner renders it, InnerPageLayout passes it
// through, page frontmatters construct it. Lives in a .ts module (like
// imageWidths.ts) rather than a .astro frontmatter export by convention.
export interface Fact {
  value: string;
  label: string;
}
```

`site/src/components/HeroInner.astro` (full file):

```astro
---
// Ruled two-cell ledger masthead: H1 in the wide column, page-specific
// STATIC org facts bottom-baselined in the narrow column as a stat stack
// (value over small-caps label, behind a vertical hairline; build-time
// strings only; live data belongs exclusively to the conditions strip).
// With no facts the band collapses to a single column, no hole.
// Optional `photo` renders a full-bleed photo band directly under the
// masthead grid (About: team photo, Community: canoe social, Racing: race
// crew) - the answer to "the pages feel blank" without inventing a new
// hero shape per page.
import { Image } from 'astro:assets';
import { FULL_BLEED } from '@/components/imageWidths';
import type { Fact } from '@/components/heroFacts';

interface Props {
  headline: string;
  subhead?: string;
  facts?: Fact[];
  photo?: ImageMetadata;
  photoAlt?: string;
  /** CSS object-position for the band crop, e.g. "center 40%". */
  photoPosition?: string;
}
const { headline, subhead, facts = [], photo, photoAlt = '', photoPosition } = Astro.props;
---
<section class="bg-paper text-ink border-y border-ink/15">
  <div class="mx-auto max-w-7xl px-6 py-10 md:py-14 grid gap-x-10 gap-y-6 md:grid-cols-12">
    <div class:list={[facts.length > 0 ? 'md:col-span-7' : 'md:col-span-9']}>
      <h1 class="font-display font-semibold text-4xl md:text-6xl leading-[1.05] text-navy">{headline}</h1>
      {subhead && <p class="mt-4 text-lg md:text-xl text-slate max-w-prose">{subhead}</p>}
    </div>
    {facts.length > 0 && (
      <ul class="md:col-span-3 md:col-start-10 self-end md:border-l md:border-ink/15 md:pl-6 space-y-3">
        {facts.map((f) => (
          <li>
            <div class="font-display font-semibold text-mint-deep text-base md:text-lg leading-tight">{f.value}</div>
            <div class="text-[11px] tracking-[0.14em] uppercase text-slate mt-0.5">{f.label}</div>
          </li>
        ))}
      </ul>
    )}
  </div>
  {photo && (
    <Image
      src={photo}
      alt={photoAlt}
      widths={FULL_BLEED}
      sizes="100vw"
      class="w-full h-[230px] md:h-[280px] object-cover"
      style={photoPosition ? `object-position: ${photoPosition}` : undefined}
      loading="eager"
    />
  )}
</section>
```

- [ ] **Step 2: Pass the new props through `site/src/layouts/InnerPageLayout.astro`**

Replace the `interface Props` block and the destructure (lines 28-37) with:

```ts
import type { Fact } from '@/components/heroFacts';

interface Props {
  title: string;
  description?: string;
  ogImage?: string;
  headline?: string;
  subhead?: string;
  /** Static org facts for the masthead's narrow column (HeroInner). */
  facts?: Fact[];
  /** Optional full-bleed photo band under the masthead (HeroInner). */
  photo?: ImageMetadata;
  photoAlt?: string;
  photoPosition?: string;
}
const { title, description, ogImage, headline, subhead, facts, photo, photoAlt, photoPosition } = Astro.props;
```

(the `import type` line goes with the other imports at the top of the frontmatter)

and replace line 48:

```astro
  {headline && <HeroInner headline={headline} subhead={subhead} facts={facts} />}
```

with:

```astro
  {headline && (
    <HeroInner
      headline={headline}
      subhead={subhead}
      facts={facts}
      photo={photo}
      photoAlt={photoAlt}
      photoPosition={photoPosition}
    />
  )}
```

- [ ] **Step 3: Migrate every facts caller**

`site/src/pages/about.astro` line 19:

```astro
  facts={[
    { value: '501(c)(3) nonprofit', label: 'Status' },
    { value: 'Minneapolis · St. Paul', label: 'Based in' },
  ]}
```

`site/src/pages/community.astro` line 22:

```astro
  facts={[
    { value: '2020', label: 'Founded' },
    { value: 'Photos by club members', label: 'Credits' },
  ]}
```

`site/src/pages/racing.astro` line 18:

```astro
  facts={[
    { value: '80+', label: 'Skiers at the 2026 Birkie' },
    { value: 'Always voluntary', label: 'Racing' },
  ]}
```

`site/src/pages/coaches.astro` line 22:

```astro
  facts={[
    { value: 'Two seasons a year', label: 'Coaching' },
    { value: 'Tuesday · Thursday', label: 'Practices' },
  ]}
```

`site/src/pages/extra-training-fun.astro` line 27:

```astro
  facts={[{ value: '2022', label: 'Member-led since' }]}
```

`site/src/pages/dry-tri.astro` line 28:

```astro
  facts={[
    { value: 'Roll · Ride · Run', label: 'Format' },
    { value: 'Carver Park Reserve', label: 'Venue' },
    { value: 'October 2025', label: 'First held' },
  ]}
```

- [ ] **Step 4: Check and build**

```bash
cd /Users/rob/env/tcsc-trips-site/site && npx astro check && NODE_ENV=production npx astro build
```

Expected: 0 errors, 10 pages. (Bare `ImageMetadata` needs no import - it is ambient in this project; HeroHome.astro:12 and CoachEntry.astro:25 already use it import-free.)

- [ ] **Step 5: Commit**

```bash
cd /Users/rob/env/tcsc-trips-site
git add site/src/components/heroFacts.ts site/src/components/HeroInner.astro site/src/layouts/InnerPageLayout.astro site/src/pages/about.astro site/src/pages/community.astro site/src/pages/racing.astro site/src/pages/coaches.astro site/src/pages/extra-training-fun.astro site/src/pages/dry-tri.astro
git commit -m "feat(site): masthead stat facts and optional photo band on inner pages"
```

---

### Task 8: Port the 13 confirmed photos

**Files:**
- Create: `scripts/port_feedback_photos.py` (one-off, committed for traceability)
- Create: 13 images under `site/src/assets/images/photos/`
- Modify: `migration/port-manifest.csv` (13 rows)
- Modify: `migration/CONSENT.md` (new section + 13 rows)

The 14th photo (skijor) is gated on a rights check - Task 12 Step 4. Mapping (source files in `migration/slack_photos/`):

| New asset (site/src/assets/images/photos/) | Source file | Slot | min_required_w |
|---|---|---|---|
| team-banner.jpg | 2024-03-30_1711812078-797759_0.jpg | page_header | 1920 |
| canoe-social.jpg | 2024-07-09_1720579793-084489_1.jpg | page_header | 1920 |
| race-crew-frosty.jpg | 2023-01-21_1674324661-077579_0.jpg | page_header | 1920 |
| rollerski-golden-hour.jpg | 2024-08-13_1723597154-617769_0.jpg | page_body | 800 |
| backyard-social.jpg | 2024-05-16_1715917971-931869_0.jpg | page_body | 800 |
| run-club-selfie.jpg | 2026-04-23_1776954511-019769_2.jpg | page_body | 800 |
| winter-five.jpg | 2023-01-08_1673242364-942339_1.jpg | page_body | 800 |
| lakeside-picnic.jpg | 2024-03-03_1709501583-457379_0.jpg | page_body | 800 |
| second-harvest.jpg | 2024-01-17_1705546321-840949_0.jpg | page_body | 800 |
| barn-banquet.jpg | 2026-04-12_1776027078-470899_0.jpg | page_body | 800 |
| ski-de-she-trio.jpg | 2023-01-28_1674942658-549799_0.jpg | page_body | 800 |
| korte-medals.jpg | 2022-02-25_1645852380-232989_0.jpg | page_body | 800 |
| birkie-start.jpg | 2024-02-23_1708738564-829599_1.jpg | page_body | 800 |
| finlandia-podium.jpg | 2026-02-14_1771096714-097109_0.jpg | page_body | 800 |

(13 rows above for this task; skijor-race.jpg joins via Task 12 Step 4 only if cleared.)

- [ ] **Step 1: Write `scripts/port_feedback_photos.py`**

```python
"""One-off: port the June 2026 design-feedback photos from the Slack archive.

Pipeline matches the site's photo convention: EXIF transpose, downscale to a
2560px long edge (never upscale), save progressive JPEG quality 90. Prints the
port-manifest.csv rows for the committed files.

Run from the repo root: python scripts/port_feedback_photos.py
"""
from pathlib import Path

from PIL import Image, ImageOps

SRC = Path('migration/slack_photos')
DEST = Path('site/src/assets/images/photos')
SOURCE_URL = 'slack://twincitiesskiclub/#photos-videos (see migration/slack_photos/manifest.csv)'
CONSENT = 'member-posted-club-slack; see migration/CONSENT.md'

# (dest_name, source_name, slot, min_required_w)
PHOTOS = [
    ('team-banner.jpg', '2024-03-30_1711812078-797759_0.jpg', 'page_header', 1920),
    ('canoe-social.jpg', '2024-07-09_1720579793-084489_1.jpg', 'page_header', 1920),
    ('race-crew-frosty.jpg', '2023-01-21_1674324661-077579_0.jpg', 'page_header', 1920),
    ('rollerski-golden-hour.jpg', '2024-08-13_1723597154-617769_0.jpg', 'page_body', 800),
    ('backyard-social.jpg', '2024-05-16_1715917971-931869_0.jpg', 'page_body', 800),
    ('run-club-selfie.jpg', '2026-04-23_1776954511-019769_2.jpg', 'page_body', 800),
    ('winter-five.jpg', '2023-01-08_1673242364-942339_1.jpg', 'page_body', 800),
    ('lakeside-picnic.jpg', '2024-03-03_1709501583-457379_0.jpg', 'page_body', 800),
    ('second-harvest.jpg', '2024-01-17_1705546321-840949_0.jpg', 'page_body', 800),
    ('barn-banquet.jpg', '2026-04-12_1776027078-470899_0.jpg', 'page_body', 800),
    ('ski-de-she-trio.jpg', '2023-01-28_1674942658-549799_0.jpg', 'page_body', 800),
    ('korte-medals.jpg', '2022-02-25_1645852380-232989_0.jpg', 'page_body', 800),
    ('birkie-start.jpg', '2024-02-23_1708738564-829599_1.jpg', 'page_body', 800),
    ('finlandia-podium.jpg', '2026-02-14_1771096714-097109_0.jpg', 'page_body', 800),
    # skijor-race.jpg deliberately ABSENT pending the rights check
    # (re-add '2024-02-07_1707360103-835559_0.jpg' here if cleared).
]


def main() -> None:
    rows = []
    for dest_name, source_name, slot, minw in PHOTOS:
        src_path = SRC / source_name
        dest_path = DEST / dest_name
        with Image.open(src_path) as img:
            img = ImageOps.exif_transpose(img)
            ow, oh = img.size
            img.thumbnail((2560, 2560), Image.Resampling.LANCZOS)  # downscale only
            cw, ch = img.size
            img.convert('RGB').save(dest_path, 'JPEG', quality=90, progressive=True, optimize=True)
        if cw < minw:
            print(f'!! {dest_name}: committed width {cw} < min_required_w {minw}')
        rows.append(
            f'site/src/assets/images/photos/{dest_name},migration/slack_photos/{source_name},'
            f'{SOURCE_URL},{ow},{oh},{cw},{ch},{slot},{minw},{CONSENT}'
        )
        print(f'ok {dest_name}: {ow}x{oh} -> {cw}x{ch}')
    print('\n--- append to migration/port-manifest.csv ---')
    for r in rows:
        print(r)


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Run it**

```bash
cd /Users/rob/env/tcsc-trips-site && source env/bin/activate
python scripts/port_feedback_photos.py
```

Expected: 13 `ok` lines (skijor is deliberately absent), zero `!!` warnings, then 13 manifest rows printed. If any `!!` appears (a header photo too small), stop and flag it to Rob instead of shipping a soft image.

- [ ] **Step 3: Append the printed rows to `migration/port-manifest.csv`**

Copy the 13 printed rows verbatim onto the end of the file (no header changes, no blank lines).

- [ ] **Step 4: Add a section to `migration/CONSENT.md`**

At the very END of the file (after the "Dry Tri photo caveat" section, which is the current last section), add:

```markdown
## June 2026 design-feedback round additions (page photos)

Direct page imports (About / Community / Racing placements), not mosaic
entries; same Slack consent basis as above. Selected 2026-06-11 by Rob from a
493-candidate curation pass. The skijor photo
(2024-02-07_1707360103-835559_0.jpg) is EXCLUDED pending a rights check
(poster account deactivated; slight professional look).

| Page placement | Image file | Slack source file |
|---|---|---|
| About header | site/src/assets/images/photos/team-banner.jpg | 2024-03-30_1711812078-797759_0.jpg |
| About body | site/src/assets/images/photos/rollerski-golden-hour.jpg | 2024-08-13_1723597154-617769_0.jpg |
| Community header | site/src/assets/images/photos/canoe-social.jpg | 2024-07-09_1720579793-084489_1.jpg |
| Community members | site/src/assets/images/photos/backyard-social.jpg | 2024-05-16_1715917971-931869_0.jpg |
| Community members | site/src/assets/images/photos/run-club-selfie.jpg | 2026-04-23_1776954511-019769_2.jpg |
| Community members | site/src/assets/images/photos/winter-five.jpg | 2023-01-08_1673242364-942339_1.jpg |
| Community members | site/src/assets/images/photos/lakeside-picnic.jpg | 2024-03-03_1709501583-457379_0.jpg |
| Community volunteering | site/src/assets/images/photos/second-harvest.jpg | 2024-01-17_1705546321-840949_0.jpg |
| Community socials | site/src/assets/images/photos/barn-banquet.jpg | 2026-04-12_1776027078-470899_0.jpg |
| Racing header | site/src/assets/images/photos/race-crew-frosty.jpg | 2023-01-21_1674324661-077579_0.jpg |
| Racing strip | site/src/assets/images/photos/ski-de-she-trio.jpg | 2023-01-28_1674942658-549799_0.jpg |
| Racing strip | site/src/assets/images/photos/korte-medals.jpg | 2022-02-25_1645852380-232989_0.jpg |
| Racing strip | site/src/assets/images/photos/birkie-start.jpg | 2024-02-23_1708738564-829599_1.jpg |
| Racing strip | site/src/assets/images/photos/finlandia-podium.jpg | 2026-02-14_1771096714-097109_0.jpg |
```

- [ ] **Step 5: Run verify**

```bash
cd /Users/rob/env/tcsc-trips-site && python -m scripts.wix_scrape.verify; echo "exit: $?"
```

Expected: `exit: 0`. The reverse check must report 0 unaudited committed images. If it fails on a dims mismatch, the manifest row numbers were not copied exactly - rerun the script and re-copy.

- [ ] **Step 6: Commit**

```bash
cd /Users/rob/env/tcsc-trips-site
git add scripts/port_feedback_photos.py site/src/assets/images/photos/ migration/port-manifest.csv migration/CONSENT.md
git commit -m "feat(site): port 13 member photos for the June 2026 feedback round"
```

---

### Task 9: About page (header photo, lede, body photo)

**Files:**
- Modify: `site/src/pages/about.astro`

- [ ] **Step 1: Rewrite `site/src/pages/about.astro`** (full file)

```astro
---
// /about: the founding story + who joins, from the `about` singleton, then
// the practice seasons band (paper variant on the paper page). Team photo
// rides the masthead band; the rollerski group closes the prose column.
// The first body paragraph (the founding story) renders as a display lede
// via the [&>p:first-child] overrides on the prose wrapper.
import { getEntry, render } from 'astro:content';
import { Image } from 'astro:assets';
import InnerPageLayout from '@/layouts/InnerPageLayout.astro';
import SectionBand from '@/components/SectionBand.astro';
import SeasonsGrid from '@/components/SeasonsGrid.astro';
import { metaDescription } from '@/lib/metaDescription';
import { CARD } from '@/components/imageWidths';
import teamBanner from '@/assets/images/photos/team-banner.jpg';
import rollerskiGoldenHour from '@/assets/images/photos/rollerski-golden-hour.jpg';

const about = await getEntry('about', 'about');
if (!about) throw new Error('about singleton missing (src/content/pages/about.mdoc)');
const { Content } = await render(about);
---
<InnerPageLayout
  title="About · Twin Cities Ski Club"
  description={about.data.intro && metaDescription(about.data.intro)}
  headline={about.data.headline ?? 'About Twin Cities Ski Club'}
  subhead={about.data.intro}
  facts={[
    { value: '501(c)(3) nonprofit', label: 'Status' },
    { value: 'Minneapolis · St. Paul', label: 'Based in' },
  ]}
  photo={teamBanner}
  photoAlt="Around fifty TCSC members posing together behind the club banner"
  photoPosition="center 40%"
>
  <div class="mx-auto max-w-3xl px-6 py-12">
    <div class="prose prose-lg max-w-prose text-ink [&_h2]:font-semibold [&_h2]:tracking-tight [&>p:first-child]:font-display [&>p:first-child]:text-xl md:[&>p:first-child]:text-2xl [&>p:first-child]:leading-snug [&>p:first-child]:text-navy">
      <Content />
    </div>
    <Image
      src={rollerskiGoldenHour}
      alt="A line of members rollerskiing together at golden hour, poles mid-swing"
      widths={CARD}
      sizes="(min-width: 768px) 720px, 100vw"
      class="mt-10 w-full h-64 md:h-80 object-cover"
      loading="lazy"
    />
  </div>
  <SectionBand variant="paper" heading="Seasons">
    <SeasonsGrid variant="paper" />
  </SectionBand>
</InnerPageLayout>
```

- [ ] **Step 2: Check, build, visual**

```bash
cd /Users/rob/env/tcsc-trips-site/site && npx astro check && NODE_ENV=production npx astro build
```

Expected: 0 errors, 10 pages. Dev-server check of /about: team photo band under the masthead, founded paragraph visibly larger in display navy, rollerski photo between prose and Seasons band. Check the lede at BOTH breakpoints (the `md:` variant cascades separately from the base). If the typography plugin wins the cascade on the lede, escalate size AND leading together with `!`: `[&>p:first-child]:!text-xl md:[&>p:first-child]:!text-2xl [&>p:first-child]:!leading-snug` (prose-lg pins p font-size and line-height; font-display/text-navy are safe, prose does not set those).

- [ ] **Step 3: Commit**

```bash
cd /Users/rob/env/tcsc-trips-site
git add site/src/pages/about.astro
git commit -m "feat(site): about page team photo, founding lede, rollerski body photo"
```

---

### Task 10: Community page (header photo, members cluster, group anchors, bigger headings)

**Files:**
- Modify: `site/src/pages/community.astro`

- [ ] **Step 1: Rewrite `site/src/pages/community.astro`** (full file)

```astro
---
// /community: community story from the `community` singleton, a photo
// cluster pairing with the "Our members" prose, the grouped "what we've
// done" takeaways ledger (volunteering / members who coach / socials, mined
// from club Slack; volunteering and socials carry an anchor photo), and the
// FULL consented photo mosaic (no homeOnly filter).
// The cluster/anchor photos are direct imports, NOT photos-collection
// entries: a collection entry would also land them in the mosaic below and
// double them up on this very page.
import { getEntry, render } from 'astro:content';
import { Image } from 'astro:assets';
import InnerPageLayout from '@/layouts/InnerPageLayout.astro';
import PhotoMosaic from '@/components/PhotoMosaic.astro';
import SectionBand from '@/components/SectionBand.astro';
import { metaDescription } from '@/lib/metaDescription';
import { CARD } from '@/components/imageWidths';
import canoeSocial from '@/assets/images/photos/canoe-social.jpg';
import backyardSocial from '@/assets/images/photos/backyard-social.jpg';
import runClubSelfie from '@/assets/images/photos/run-club-selfie.jpg';
import winterFive from '@/assets/images/photos/winter-five.jpg';
import lakesidePicnic from '@/assets/images/photos/lakeside-picnic.jpg';
import secondHarvest from '@/assets/images/photos/second-harvest.jpg';
import barnBanquet from '@/assets/images/photos/barn-banquet.jpg';

const community = await getEntry('community', 'community');
if (!community) throw new Error('community singleton missing (src/content/pages/community.mdoc)');
const { Content } = await render(community);
const takeaways = community.data.takeaways;

const memberCluster = [
  { src: backyardSocial, alt: 'A crowded backyard social at dusk, members chatting in small groups with name tags' },
  { src: runClubSelfie, alt: 'A grinning group selfie mid-run, thumbs up in golden evening light' },
  { src: winterFive, alt: 'Five members in club kits shoulder to shoulder on a snowy trail in low winter sun' },
  { src: lakesidePicnic, alt: 'A lakeside picnic crowd in novelty hats around a packed picnic table' },
];

// Anchor photo per takeaways group; groups without one render unchanged.
const groupPhotos: Record<string, { src: ImageMetadata; alt: string }> = {
  Volunteering: {
    src: secondHarvest,
    alt: 'Members in hairnets and aprons packing food at a Second Harvest volunteer night',
  },
  Socials: {
    src: barnBanquet,
    alt: 'The club banquet in a barn venue strung with lights, every table full',
  },
};
---
<InnerPageLayout
  title="Community · Twin Cities Ski Club"
  description={community.data.intro && metaDescription(community.data.intro)}
  headline={community.data.headline ?? 'A welcoming community'}
  subhead={community.data.intro}
  facts={[
    { value: '2020', label: 'Founded' },
    { value: 'Photos by club members', label: 'Credits' },
  ]}
  photo={canoeSocial}
  photoAlt="Members in canoes and kayaks rafted together on a city lake at golden hour"
>
  <div class="mx-auto max-w-3xl px-6 py-12">
    <div class="prose prose-lg max-w-prose text-ink">
      <Content />
    </div>
    <div class="mt-10 grid grid-cols-2 gap-px bg-ink/15">
      {memberCluster.map((p) => (
        <Image
          src={p.src}
          alt={p.alt}
          widths={CARD}
          sizes="(min-width: 768px) 360px, 50vw"
          class="w-full h-48 md:h-64 object-cover"
          loading="lazy"
        />
      ))}
    </div>
  </div>
  {takeaways.length > 0 && (
    <SectionBand
      variant="paper"
      seam="Club record"
      heading="What we've done"
      subhead="A few seasons of volunteering, coaching, and socials."
    >
      <div class="space-y-14">
        {takeaways.map((g) => (
          <div class="grid gap-4 md:gap-10 md:grid-cols-12">
            <h3 class="md:col-span-3 font-display font-semibold text-2xl text-navy pt-4">
              {g.group}
            </h3>
            <div class="md:col-span-9">
              {groupPhotos[g.group] && (
                <Image
                  src={groupPhotos[g.group].src}
                  alt={groupPhotos[g.group].alt}
                  widths={CARD}
                  sizes="(min-width: 768px) 720px, 100vw"
                  class="w-full h-56 md:h-72 object-cover mb-2"
                  loading="lazy"
                />
              )}
              <div class="divide-y divide-ink/10 border-t border-ink/10">
                {g.items.map((item) => (
                  <div class="py-5 grid gap-x-6 gap-y-1 sm:grid-cols-[minmax(14rem,18rem)_1fr]">
                    <div class="font-semibold text-navy">
                      {item.href ? (
                        <a
                          href={item.href}
                          class="underline underline-offset-4 decoration-ink/30 hover:decoration-mint-deep hover:text-mint-deep transition-colors"
                        >{item.line}</a>
                      ) : (
                        item.line
                      )}
                    </div>
                    {item.detail && <p class="text-ink/80">{item.detail}</p>}
                  </div>
                ))}
              </div>
            </div>
          </div>
        ))}
        {/* The training half of this culture has its own page. */}
        <p class="text-ink/80">
          Member-organized workouts are on their own page:{' '}
          <a
            href="/extra-training-fun"
            class="font-semibold text-navy underline underline-offset-4 decoration-ink/30 hover:decoration-mint-deep hover:text-mint-deep transition-colors"
          >Extra training fun</a>.
        </p>
      </div>
    </SectionBand>
  )}
  <PhotoMosaic />
</InnerPageLayout>
```

Note: bare `ImageMetadata` in the `groupPhotos` type needs no import - it is ambient in this project (HeroHome.astro:12 precedent).

- [ ] **Step 2: Check, build, visual**

```bash
cd /Users/rob/env/tcsc-trips-site/site && npx astro check && NODE_ENV=production npx astro build
```

Expected: 0 errors, 10 pages. Dev-server check of /community: canoe band under masthead, 2x2 photo cluster under the prose, Volunteering and Socials groups carry an anchor photo, "Members who coach" group renders exactly as before (no photo), group headings now display-scale.

- [ ] **Step 3: Commit**

```bash
cd /Users/rob/env/tcsc-trips-site
git add site/src/pages/community.astro
git commit -m "feat(site): community photos at the top, group anchors, display headings"
```

---

### Task 11: Racing page (header photo + race strip)

**Files:**
- Modify: `site/src/pages/racing.astro`

- [ ] **Step 1: Rewrite `site/src/pages/racing.astro`** (full file)

```astro
---
// /racing: racing story from the `racing` singleton plus the structured
// races list (date / name / location rows, optional full-width notes) and a
// member-shot race photo strip. Strip photos are direct imports, not
// photos-collection entries (entries would also join the community mosaic).
import { getEntry, render } from 'astro:content';
import { Image } from 'astro:assets';
import InnerPageLayout from '@/layouts/InnerPageLayout.astro';
import { metaDescription } from '@/lib/metaDescription';
import { CARD } from '@/components/imageWidths';
import raceCrewFrosty from '@/assets/images/photos/race-crew-frosty.jpg';
import skiDeSheTrio from '@/assets/images/photos/ski-de-she-trio.jpg';
import korteMedals from '@/assets/images/photos/korte-medals.jpg';
import birkieStart from '@/assets/images/photos/birkie-start.jpg';
import finlandiaPodium from '@/assets/images/photos/finlandia-podium.jpg';

const racing = await getEntry('racing', 'racing');
if (!racing) throw new Error('racing singleton missing (src/content/pages/racing.mdoc)');
const { Content } = await render(racing);
const races = racing.data.races;

const raceStrip = [
  { src: skiDeSheTrio, alt: 'Three members in TCSC jerseys and race bibs in front of the Ski de She backdrop' },
  { src: korteMedals, alt: 'Two finishers with Kortelopet medals and bibs grinning in golden sun' },
  { src: birkieStart, alt: 'Two members in matching TCSC kits with arms raised at the Birkie start banner' },
  { src: finlandiaPodium, alt: 'A member on the Finlandia podium holding the trophy axe in TCSC kit' },
];
---
<InnerPageLayout
  title="Racing · Twin Cities Ski Club"
  description={racing.data.intro && metaDescription(racing.data.intro)}
  headline={racing.data.headline ?? 'Twin Cities Ski Club racers'}
  subhead={racing.data.intro}
  facts={[
    { value: '80+', label: 'Skiers at the 2026 Birkie' },
    { value: 'Always voluntary', label: 'Racing' },
  ]}
  photo={raceCrewFrosty}
  photoAlt="Six members in race bibs, arms around each other, in frosty woods before a start"
>
  <div class="mx-auto max-w-3xl px-6 py-12">
    <div class="prose prose-lg max-w-prose text-ink">
      <Content />
    </div>
  </div>
  {races.length > 0 && (
    <section class="mx-auto max-w-3xl px-6 pb-12">
      <h2 class="font-display font-semibold text-3xl text-navy">Races</h2>
      <div class="mt-6 divide-y divide-ink/10">
        {races.map((r) => (
          <div class="py-4 grid gap-x-6 gap-y-1 sm:grid-cols-[10rem_1fr_1fr]">
            {/* date/name/location always render (possibly empty) so the
                three grid columns never shift when a field is omitted. */}
            <div class="text-mint-deep text-sm tracking-wider uppercase pt-0.5">{r.date}</div>
            <div class="font-semibold text-navy">
              {r.href ? (
                <a
                  href={r.href}
                  class="underline underline-offset-4 decoration-ink/30 hover:decoration-mint-deep hover:text-mint-deep transition-colors"
                >{r.name}</a>
              ) : (
                r.name
              )}
            </div>
            <div class="text-slate">{r.location}</div>
            {r.notes && <div class="sm:col-span-full text-sm text-ink/80">{r.notes}</div>}
          </div>
        ))}
      </div>
      <div class="mt-10 grid grid-cols-2 md:grid-cols-4 gap-px bg-ink/15">
        {raceStrip.map((p) => (
          <Image
            src={p.src}
            alt={p.alt}
            widths={CARD}
            sizes="(min-width: 768px) 180px, 50vw"
            class="w-full aspect-[3/4] object-cover"
            loading="lazy"
          />
        ))}
      </div>
    </section>
  )}
</InnerPageLayout>
```

- [ ] **Step 2: Check, build, visual**

```bash
cd /Users/rob/env/tcsc-trips-site/site && npx astro check && NODE_ENV=production npx astro build
```

Expected: 0 errors, 10 pages. Dev-server check of /racing: header band photo, races list unchanged, 4-up uniform photo strip below it (2-up on mobile).

- [ ] **Step 3: Commit**

```bash
cd /Users/rob/env/tcsc-trips-site
git add site/src/pages/racing.astro
git commit -m "feat(site): racing page header photo and member race strip"
```

---

### Task 12: Skijor photo (CONDITIONAL - only on Rob's rights confirmation)

**Files (only if cleared):**
- Modify: `scripts/port_feedback_photos.py`, `migration/port-manifest.csv`, `migration/CONSENT.md`, `site/src/pages/racing.astro`
- Create: `site/src/assets/images/photos/skijor-race.jpg`

- [ ] **Step 1: Ask Rob** whether `2024-02-07_1707360103-835559_0.jpg` (skijor with dog, bib 9527, posted by a deactivated account, slight professional look) is confirmed member-shot. If NOT confirmed or unknown: mark this task complete with the photo dropped, update the CONSENT.md note to say "excluded after rights review", and stop here. The 4-photo strip stands on its own.

- [ ] **Step 2 (if cleared): Port it**

In `scripts/port_feedback_photos.py`, add to `PHOTOS` (replacing the comment):

```python
    ('skijor-race.jpg', '2024-02-07_1707360103-835559_0.jpg', 'page_body', 800),
```

Re-run `python scripts/port_feedback_photos.py` (existing outputs regenerate identically; that is fine), append ONLY the new skijor row to `migration/port-manifest.csv`, and add to the CONSENT.md June 2026 table:

```markdown
| Racing strip | site/src/assets/images/photos/skijor-race.jpg | 2024-02-07_1707360103-835559_0.jpg (rights confirmed <date> by <who>) |
```

Also delete the "skijor ... EXCLUDED" sentence from the section intro.

- [ ] **Step 3 (if cleared): Add to the racing strip**

In `site/src/pages/racing.astro` add the import and a fifth entry:

```ts
import skijorRace from '@/assets/images/photos/skijor-race.jpg';
```

```ts
  { src: skijorRace, alt: 'A member skijoring with their dog mid-race, crop keeping skier and dog centered' },
```

With 5 photos the `md:grid-cols-4` grid wraps one onto a second row; change it to `md:grid-cols-5` in the same edit.

- [ ] **Step 4 (if cleared): Verify and commit**

```bash
cd /Users/rob/env/tcsc-trips-site && python -m scripts.wix_scrape.verify; echo "exit: $?"
cd site && NODE_ENV=production npx astro build
cd .. && git add scripts/port_feedback_photos.py site/src/assets/images/photos/skijor-race.jpg migration/port-manifest.csv migration/CONSENT.md site/src/pages/racing.astro
git commit -m "feat(site): add cleared skijor photo to the racing strip"
```

---

### Task 13: Sponsor strip on home

**Files:**
- Modify: `site/src/components/SponsorWall.astro` (add `variant` prop)
- Modify: `site/src/pages/index.astro` (mount between WaxRoomFeed and CTAStrip)

- [ ] **Step 1: Add the strip variant to `site/src/components/SponsorWall.astro`**

Change the Props interface and destructure:

```ts
interface Props {
  headingLevel?: 'h2' | 'h3';
  /** 'wall' (default): tiered groups for /sponsors. 'strip': one compact
      logo row for the home page band - no tier headings, smaller logos. */
  variant?: 'wall' | 'strip';
}
const { headingLevel: Heading = 'h3', variant = 'wall' } = Astro.props;
```

Then, after the `tierGroups` computation, add a strip branch ABOVE the existing template and wrap the existing template in the wall branch. The full template section becomes:

```astro
{variant === 'strip' ? (
  <div class="flex flex-wrap items-center gap-x-14 gap-y-8">
    {tierGroups.flatMap((g) => g.items).map((s) => {
      const Wrapper = s.data.url ? 'a' : 'div';
      return (
        <Wrapper {...(s.data.url ? { href: s.data.url, rel: 'sponsored' } : {})}>
          <Image
            src={s.data.logo}
            alt={s.data.slug}
            widths={THUMB}
            width={Math.min(400, s.data.logo.width)}
            sizes="200px"
            class="max-h-12 max-w-[200px] h-auto w-auto"
            loading="lazy"
          />
        </Wrapper>
      );
    })}
  </div>
) : (
  tierGroups.map(({ label, items }) => {
    // Scale the layout to the content: small groups (fewer than 4) render
    // larger logos in a flex row; 4+ items use the standard 4-col grid.
    // Tier headings are suppressed when only one tier group exists.
    const showHeading = tierGroups.length > 1;
    const isSmall = items.length < 4;
    return (
      <section class="mt-12 first:mt-0">
        {showHeading && (
          <Heading class="font-display font-semibold text-2xl text-navy">{label}</Heading>
        )}
        <div
          class={
            isSmall
              ? (showHeading ? 'mt-6' : '') + ' flex flex-wrap gap-12 items-center'
              : (showHeading ? 'mt-6' : '') + ' grid grid-cols-2 md:grid-cols-4 gap-8 items-center'
          }
        >
          {items.map((s) => {
            const Wrapper = s.data.url ? 'a' : 'div';
            // Small groups: taller max-h and a generous max-w so wide lockups
            // get proportional optical weight alongside square marks.
            const imgClass = isSmall
              ? 'max-h-20 max-w-[280px] h-auto w-auto'
              : 'max-h-16 max-w-full h-auto w-auto';
            return (
              <Wrapper {...(s.data.url ? { href: s.data.url, rel: 'sponsored' } : {})}>
                <Image
                  src={s.data.logo}
                  alt={s.data.slug}
                  widths={THUMB}
                  width={Math.min(600, s.data.logo.width)}
                  sizes={isSmall ? '280px' : '(min-width: 768px) 200px, 40vw'}
                  class={imgClass}
                  loading="lazy"
                />
              </Wrapper>
            );
          })}
        </div>
      </section>
    );
  })
)}
```

(That else branch is the current wall markup verbatim; only indentation shifts.)

- [ ] **Step 2: Mount the strip on home**

In `site/src/pages/index.astro`, add the import:

```ts
import SponsorWall from '@/components/SponsorWall.astro';
```

and between `<WaxRoomFeed />` and `<CTAStrip` insert:

```astro
  <SectionBand variant="paper" seam="Our sponsors">
    <div class="flex flex-wrap items-center justify-between gap-x-12 gap-y-8">
      <SponsorWall variant="strip" />
      <a
        href="/sponsors"
        class="text-sm font-semibold text-navy underline underline-offset-4 decoration-ink/30 hover:decoration-mint-deep hover:text-mint-deep transition-colors"
      >About our sponsors</a>
    </div>
  </SectionBand>
```

- [ ] **Step 3: Check, build, visual**

```bash
cd /Users/rob/env/tcsc-trips-site/site && npx astro check && NODE_ENV=production npx astro build
grep -c 'rel="sponsored"' dist/index.html
```

Expected: 0 errors, 10 pages, sponsored-link count 2. Dev-server: home shows a quiet "Our sponsors" band with two logos + the page link; /sponsors page unchanged.

- [ ] **Step 4: Commit**

```bash
cd /Users/rob/env/tcsc-trips-site
git add site/src/components/SponsorWall.astro site/src/pages/index.astro
git commit -m "feat(site): sponsor strip on the home page"
```

---

### Task 14: Full verification pass

**Files:** none

- [ ] **Step 1: Full battery**

```bash
cd /Users/rob/env/tcsc-trips-site && source env/bin/activate
cd site && npx astro check && NODE_ENV=production npx astro build && cd ..
python -m scripts.wix_scrape.verify; echo "verify exit: $?"
pytest tests/conditions tests/wix_scrape -q
```

Expected: check 0 errors; build 10 pages; verify exit 0; 71 tests pass.

- [ ] **Step 2: Visual sweep (dev server)**

At desktop AND a ~375px viewport: home (logo, closed CTA copy, Seasons cards stack on mobile, mission stats, sponsor strip), /about (band photo, lede, rollerski photo, Seasons heading), /community (band, cluster, anchors, heading sizes), /racing (band, strip), /sponsors (unchanged), /coaches and /dry-tri and /extra-training-fun (migrated facts render).

- [ ] **Step 3: Finish the branch**

Use the superpowers:finishing-a-development-branch skill (merge vs PR decision is Rob's; note that pushing to main deploys both the static site and the Flask service).

---

## Plan deviations from spec (flagged for review)

1. **No `content/photos` entries for the 14 new photos** (spec section 6 said entries with `show_on_home: false`). Reason: the Community page mounts the unfiltered consented mosaic; collection entries would render every new photo a second time on the same page. Direct imports + manifest/CONSENT rows preserve all consent traceability. Surface this to Rob at review.
2. **`registration_open: true` on Fall/Winter** while registration is not literally open: the field drives accent styling per spec section 3 ("drives mint vs muted styling"); the Keystatic label says "Highlight registration line" to keep editors unconfused.
3. **Date ranges lose their parentheticals**: the yamls previously read `September-March (with a Christmas break)` / `May-August (with a 2-week "4th of July Break")`; the new cards use the spec's clean `September - March` / `May - August` spans as approved in the mocks. The break details drop off the site (they survive in git history); flag to Rob if they should land somewhere else, e.g. the season summary.
