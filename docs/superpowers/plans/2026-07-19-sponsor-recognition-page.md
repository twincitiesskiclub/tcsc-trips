# Sponsor Recognition Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the sparse sponsors page with an accessible, recognition-first page that labels current Trailblazer Partners, documents verified collective impact, distinguishes future priorities, and gives prospective sponsors one clear contact action.

**Architecture:** Keep sponsor records and page copy in Astro content collections, move tier ordering/grouping into a small tested JavaScript module, and let `SponsorWall.astro` render the same grouped data in full-page and home-strip variants. Compose the page from the existing `InnerPageLayout`, `SectionBand`, `SponsorWall`, `Image`, and `CTAStrip` primitives, with direct imports of two consent-cleared club photos.

**Tech Stack:** Astro 7, TypeScript/JavaScript ES modules, Keystatic, Tailwind CSS 4, Astro content collections, Node's built-in test runner.

## Global Constraints

- Twin Cities Orthopedics and Kwik Trip are `Trailblazer Partners`; render that tier name without `highest level` language.
- Public sponsor tiers are exactly `trailblazer`, `community_partner`, and `supporter`, labeled `Trailblazer Partners`, `Community Partners`, and `Supporters` in that order.
- Do not publish tier prices, package benefits, tax-deduction claims, sponsor testimonials, or sponsor-specific purchase attribution.
- Completed-impact copy must use collective attribution and must cover shared waxing access for racers and non-racers, Pre-Birkie and Great Bear Chase van use, the team tent, and Birkie start parking.
- Treat the six sponsor-logo jackets as sponsor recognition, not shared member equipment.
- Frame coaching capacity, PFAS wax replacement, and shared equipment as future priorities, not completed or restricted spending.
- Keep `contact@twincitiesskiclub.org` as the only sponsorship contact and do not add a form.
- Keep the page within the existing paper/navy/mint/coral design system; use editorial rows and a logo wall, not cards or a generic three-column grid.
- Use `rollerski-golden-hour.jpg` for year-round training and `great-bear-chase.jpg` for jacket recognition with the exact alt text in the design spec.
- Sponsor links open in the same tab, use `rel="sponsored"`, and identify linked image destinations as `<Sponsor name> website`.
- Keep the compact home sponsor strip compatible and free of tier headings.
- Astro and Keystatic schemas must remain synchronized and strict.
- Follow red-green-refactor: each behavioral change starts with a test that fails for the expected missing behavior.
- Baseline local builds may emit the existing empty `trips` and `wax_entries` collection warnings; do not treat those warnings as sponsor-page regressions.

---

### Task 1: Sponsor Tier Contract and Grouping

**Files:**
- Create: `site/src/lib/sponsorTiers.js`
- Create: `site/tests/sponsorTiers.test.mjs`
- Modify: `site/src/content.config.ts`
- Modify: `site/keystatic.config.ts`
- Modify: `site/src/components/SponsorWall.astro`

**Interfaces:**
- Produces: `SPONSOR_TIERS`, an ordered read-only array of `{ tier, label }` records.
- Produces: `groupSponsorsByTier(sponsors)`, returning only populated groups in tier order, with items ordered by numeric `data.order` and then `id`.
- Preserves: `<SponsorWall variant="strip">` as a compact, unheaded row for the home page.

- [ ] **Step 1: Write the failing tier-grouping tests**

Create `site/tests/sponsorTiers.test.mjs`:

```js
import assert from 'node:assert/strict';
import test from 'node:test';

import { SPONSOR_TIERS, groupSponsorsByTier } from '../src/lib/sponsorTiers.js';

const sponsor = (id, tier, order) => ({ id, data: { tier, order } });

test('defines the three public tiers in recognition order', () => {
  assert.deepEqual(SPONSOR_TIERS, [
    { tier: 'trailblazer', label: 'Trailblazer Partners' },
    { tier: 'community_partner', label: 'Community Partners' },
    { tier: 'supporter', label: 'Supporters' },
  ]);
  assert.equal(SPONSOR_TIERS.some(({ tier }) => tier === 'friend'), false);
});

test('omits empty tiers and sorts sponsors by order then id', () => {
  const groups = groupSponsorsByTier([
    sponsor('zeta', 'supporter', 4),
    sponsor('bravo', 'trailblazer', 2),
    sponsor('alpha', 'trailblazer', 2),
    sponsor('first', 'trailblazer', 1),
  ]);

  assert.deepEqual(
    groups.map(({ tier, label, items }) => ({
      tier,
      label,
      ids: items.map(({ id }) => id),
    })),
    [
      {
        tier: 'trailblazer',
        label: 'Trailblazer Partners',
        ids: ['first', 'alpha', 'bravo'],
      },
      { tier: 'supporter', label: 'Supporters', ids: ['zeta'] },
    ],
  );
});
```

- [ ] **Step 2: Run the test and verify the expected red state**

Run:

```bash
cd site
node --test tests/sponsorTiers.test.mjs
```

Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `src/lib/sponsorTiers.js`.

- [ ] **Step 3: Implement the tier module and make the unit tests green**

Create `site/src/lib/sponsorTiers.js`:

```js
// @ts-check

/** @typedef {'trailblazer' | 'community_partner' | 'supporter'} SponsorTier */

/** @type {ReadonlyArray<Readonly<{ tier: SponsorTier; label: string }>>} */
export const SPONSOR_TIERS = Object.freeze([
  Object.freeze({ tier: 'trailblazer', label: 'Trailblazer Partners' }),
  Object.freeze({ tier: 'community_partner', label: 'Community Partners' }),
  Object.freeze({ tier: 'supporter', label: 'Supporters' }),
]);

/**
 * @template {{ id: string; data: { tier: string; order: number } }} T
 * @param {readonly T[]} sponsors
 * @returns {Array<{ tier: SponsorTier; label: string; items: T[] }>}
 */
export function groupSponsorsByTier(sponsors) {
  return SPONSOR_TIERS.map(({ tier, label }) => ({
    tier,
    label,
    items: sponsors
      .filter((sponsor) => sponsor.data.tier === tier)
      .sort((a, b) => a.data.order - b.data.order || a.id.localeCompare(b.id)),
  })).filter(({ items }) => items.length > 0);
}
```

Run:

```bash
cd site
node --test tests/sponsorTiers.test.mjs
```

Expected: PASS, 2 tests and 0 failures.

- [ ] **Step 4: Synchronize the Astro and Keystatic tier contracts**

In `site/src/content.config.ts`, replace the sponsor `tier` field with:

```ts
tier: z
  .enum(['trailblazer', 'community_partner', 'supporter'])
  .default('supporter'),
```

In the sponsor collection in `site/keystatic.config.ts`, replace the tier options with:

```ts
options: [
  { label: 'Trailblazer', value: 'trailblazer' },
  { label: 'Community Partner', value: 'community_partner' },
  { label: 'Supporter', value: 'supporter' },
],
defaultValue: 'supporter',
```

- [ ] **Step 5: Make SponsorWall consume the tested grouping interface**

In `site/src/components/SponsorWall.astro`:

1. Import the helper:

```astro
import { groupSponsorsByTier } from '@/lib/sponsorTiers.js';
```

2. Replace the local `tiers` array and its mapping block with:

```ts
const tierGroups = groupSponsorsByTier(sponsors);
```

3. In the `strip` variant, retain one compact row and change linked image alt text to the destination-aware value:

```astro
alt={s.data.url ? `${s.data.slug} website` : s.data.slug}
```

4. Replace the `wall` branch with this grouped, always-labeled rendering:

```astro
tierGroups.map(({ tier, label, items }) => {
  const logoClass =
    tier === 'trailblazer'
      ? 'max-h-24 max-w-[280px]'
      : tier === 'community_partner'
        ? 'max-h-20 max-w-[240px]'
        : 'max-h-16 max-w-[200px]';
  const footprintClass =
    tier === 'trailblazer'
      ? 'h-28 sm:w-[320px]'
      : tier === 'community_partner'
        ? 'h-24 sm:w-[280px]'
        : 'h-20 sm:w-[240px]';

  return (
    <section class="mt-14 first:mt-0">
      <Heading class="font-display font-semibold text-2xl md:text-3xl text-navy">
        {label}
      </Heading>
      <div class="mt-7 flex flex-col sm:flex-row sm:flex-wrap items-center sm:items-start gap-x-12 gap-y-8">
        {items.map((s) => {
          const Wrapper = s.data.url ? 'a' : 'div';
          return (
            <Wrapper
              class={`w-full ${footprintClass} inline-flex items-center justify-center sm:justify-start`}
              {...(s.data.url ? { href: s.data.url, rel: 'sponsored' } : {})}
            >
              <Image
                src={s.data.logo}
                alt={s.data.url ? `${s.data.slug} website` : s.data.slug}
                widths={THUMB}
                width={Math.min(600, s.data.logo.width)}
                sizes={
                  tier === 'trailblazer'
                    ? '(min-width: 640px) 280px, 80vw'
                    : tier === 'community_partner'
                      ? '(min-width: 640px) 240px, 75vw'
                      : '(min-width: 640px) 200px, 70vw'
                }
                class={`${logoClass} h-auto w-auto`}
                loading="lazy"
              />
            </Wrapper>
          );
        })}
      </div>
    </section>
  );
})
```

Delete the obsolete comments about suppressing a lone tier heading and count-based logo sizing. Keep the existing comments about empty tiers, URL wrappers, heading levels, and variants accurate.

- [ ] **Step 6: Verify the tier change**

Run:

```bash
cd site
node --test tests/sponsorTiers.test.mjs
npm run check
npm run build
```

Expected: 2 tests pass, Astro reports 0 errors, and the build exits 0. Only the known empty-collection warnings may appear.

- [ ] **Step 7: Commit Task 1**

```bash
git add site/src/lib/sponsorTiers.js site/tests/sponsorTiers.test.mjs site/src/content.config.ts site/keystatic.config.ts site/src/components/SponsorWall.astro
git commit -m "feat: add sponsor recognition tiers"
```

---

### Task 2: Sponsor Impact Page and Editable Copy

**Files:**
- Create: `site/tests/sponsors-page.test.mjs`
- Modify: `site/package.json`
- Modify: `site/src/content.config.ts`
- Modify: `site/keystatic.config.ts`
- Modify: `site/src/content/pages/sponsors_page.yaml`
- Modify: `site/src/pages/sponsors.astro`

**Interfaces:**
- Consumes: `SponsorWall` and `groupSponsorsByTier` from Task 1.
- Consumes: `sponsors_page` singleton fields defined in this task.
- Produces: a statically rendered `/sponsors` page and a repeatable `npm run test:sponsors` regression command.

- [ ] **Step 1: Write the failing built-page regression test**

Create `site/tests/sponsors-page.test.mjs`:

```js
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const sponsorsHtml = readFileSync(new URL('../dist/sponsors/index.html', import.meta.url), 'utf8');
const homeHtml = readFileSync(new URL('../dist/index.html', import.meta.url), 'utf8');

const toText = (html) =>
  html
    .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replaceAll('&#39;', "'")
    .replaceAll('&#x27;', "'")
    .replaceAll('&apos;', "'")
    .replaceAll('&quot;', '"')
    .replaceAll('&amp;', '&')
    .replace(/\s+/g, ' ')
    .trim();

const sponsorText = toText(sponsorsHtml);
const homeText = toText(homeHtml);
const anchorTags = sponsorsHtml.match(/<a\b[^>]*>/gi) ?? [];
const anchorFor = (href) => anchorTags.find((tag) => tag.includes(`href="${href}"`));

test('renders the approved recognition and impact copy', () => {
  for (const phrase of [
    'Our sponsors',
    'Trailblazer Partners',
    'Sponsor support helped TCSC...',
    'Host team waxing sessions',
    'Pre-Birkie and Great Bear Chase',
    'Build a useful team base',
    'Visible support at team events',
    'six team jackets featuring sponsor logos',
    'What continued support makes possible',
    'products containing PFAS',
    'Coaching and training capacity',
    'Shared team equipment',
    'Interested in supporting TCSC?',
    'Sponsor recognition acknowledges support and does not constitute endorsement',
  ]) {
    assert.ok(sponsorText.includes(phrase), `missing page copy: ${phrase}`);
  }
});

test('keeps current sponsor links accessible and qualified', () => {
  for (const [href, name] of [
    ['https://tcomn.com/', 'Twin Cities Orthopedics'],
    ['https://www.kwiktrip.com/', 'Kwik Trip'],
  ]) {
    const anchor = anchorFor(href);
    assert.ok(anchor, `missing sponsor link: ${href}`);
    assert.match(anchor, /\brel="sponsored"/);
    assert.ok(sponsorsHtml.includes(`alt="${name} website"`));
  }

  assert.ok(sponsorsHtml.includes('href="mailto:contact@twincitiesskiclub.org"'));
  assert.ok(
    sponsorsHtml.includes(
      'alt="A large group of TCSC members posing with roller skis and poles after a summer training session"',
    ),
  );
  assert.ok(
    sponsorsHtml.includes(
      'alt="A TCSC member wearing a black team jacket with Kwik Trip and Twin Cities Orthopedics logos beside another member and the Great Bear Chase mascot"',
    ),
  );
});

test('keeps prices and highest-level claims off the public page', () => {
  assert.doesNotMatch(sponsorText, /highest level/i);
  assert.doesNotMatch(sponsorText, /\$(?:2|4|6)(?:,?000|k)\b/i);
});

test('keeps the home sponsor strip compact and unheaded', () => {
  assert.equal(homeText.includes('Trailblazer Partners'), false);
  assert.ok(homeHtml.includes('alt="Twin Cities Orthopedics website"'));
  assert.ok(homeHtml.includes('alt="Kwik Trip website"'));
});
```

Add this script to `site/package.json`:

```json
"test:sponsors": "npm run build && node --test tests/sponsorTiers.test.mjs tests/sponsors-page.test.mjs"
```

- [ ] **Step 2: Run the page test and verify the expected red state**

Run:

```bash
cd site
npm run test:sponsors
```

Expected: the build succeeds, the tier unit tests pass, and the page test fails because the approved impact and recognition copy is not rendered yet.

- [ ] **Step 3: Extend and synchronize the sponsors-page content schema**

In `site/src/content.config.ts`, replace the `sponsors_page` schema with:

```ts
const sponsorPageItem = z
  .object({
    title: z.string().min(1),
    detail: z.string().min(1),
  })
  .strict();

const sponsors_page = defineCollection({
  loader: singletonLoader('sponsors_page.yaml'),
  schema: z
    .object({
      headline: z.string().min(1),
      intro: z.string().min(1),
      impact_heading: z.string().min(1),
      impact_intro: z.string().min(1),
      impact_items: z.array(sponsorPageItem).min(1),
      recognition_heading: z.string().min(1),
      recognition_body: z.string().min(1),
      recognition_caption: z.string().min(1),
      priorities_heading: z.string().min(1),
      priorities_intro: z.string().min(1),
      priority_items: z.array(sponsorPageItem).min(1),
      contact_heading: z.string().min(1),
      contact_body: z.string().min(1),
      contact_email: z.email(),
      contact_cta_label: z.string().min(1),
      disclosure: z.string().min(1),
    })
    .strict(),
});
```

In the `sponsors_page` singleton in `site/keystatic.config.ts`, use this schema:

```ts
schema: {
  headline: fields.text({ label: 'Headline', validation: { isRequired: true } }),
  intro: fields.text({ label: 'Intro', multiline: true, validation: { isRequired: true } }),
  impact_heading: fields.text({ label: 'Impact heading', validation: { isRequired: true } }),
  impact_intro: fields.text({ label: 'Impact intro', multiline: true, validation: { isRequired: true } }),
  impact_items: fields.array(
    fields.object({
      title: fields.text({ label: 'Title', validation: { isRequired: true } }),
      detail: fields.text({ label: 'Detail', multiline: true, validation: { isRequired: true } }),
    }),
    { label: 'Completed impact', itemLabel: (p) => p.fields.title.value || 'Impact item' },
  ),
  recognition_heading: fields.text({ label: 'Recognition heading', validation: { isRequired: true } }),
  recognition_body: fields.text({ label: 'Recognition body', multiline: true, validation: { isRequired: true } }),
  recognition_caption: fields.text({ label: 'Recognition photo caption', validation: { isRequired: true } }),
  priorities_heading: fields.text({ label: 'Priorities heading', validation: { isRequired: true } }),
  priorities_intro: fields.text({ label: 'Priorities intro', multiline: true, validation: { isRequired: true } }),
  priority_items: fields.array(
    fields.object({
      title: fields.text({ label: 'Title', validation: { isRequired: true } }),
      detail: fields.text({ label: 'Detail', multiline: true, validation: { isRequired: true } }),
    }),
    { label: 'Future priorities', itemLabel: (p) => p.fields.title.value || 'Priority' },
  ),
  contact_heading: fields.text({ label: 'Contact heading', validation: { isRequired: true } }),
  contact_body: fields.text({ label: 'Contact body', multiline: true, validation: { isRequired: true } }),
  contact_email: fields.text({ label: 'Contact email', validation: { isRequired: true } }),
  contact_cta_label: fields.text({ label: 'Contact CTA label', validation: { isRequired: true } }),
  disclosure: fields.text({ label: 'Sponsor disclosure', multiline: true, validation: { isRequired: true } }),
},
```

- [ ] **Step 4: Populate the approved content**

Replace `site/src/content/pages/sponsors_page.yaml` with:

```yaml
headline: Our sponsors
intro: >-
  Support from our sponsors strengthens the shared resources behind training,
  team waxing, travel, and race support while helping TCSC keep participation
  costs in reach.
impact_heading: Sponsor support helped TCSC...
impact_intro: >-
  Recent investments strengthened everyday team activities as well as travel,
  with shared resources available to racers and non-racers.
impact_items:
  - title: Host team waxing sessions
    detail: >-
      Two team drills support organized waxing sessions, and shared waxing
      supplies remain available to members whether or not they race.
  - title: Make team travel easier
    detail: >-
      Rental vans carried food, equipment, and team supplies to the Pre-Birkie
      and Great Bear Chase, reducing the logistics handled by volunteer trip
      leaders.
  - title: Build a useful team base
    detail: >-
      A team tent and Birkie start parking created space for waxing, warming up,
      testing skis, cheering, and moving people and gear.
recognition_heading: Visible support at team events
recognition_body: >-
  TCSC purchased six team jackets featuring sponsor logos for use at races and
  podium photos.
recognition_caption: A sponsor-logo team jacket at the Great Bear Chase.
priorities_heading: What continued support makes possible
priorities_intro: >-
  As the team grows, sponsor support gives TCSC flexibility to invest where it
  can have the most impact.
priority_items:
  - title: Shared wax resources
    detail: >-
      Move the team's shared wax collection away from products containing PFAS,
      often called forever chemicals.
  - title: Coaching and training capacity
    detail: Add coaches and secure larger training spaces as the team grows.
  - title: Shared team equipment
    detail: >-
      Invest in equipment that lowers the upfront cost of participating and
      helps new members get up to speed.
contact_heading: Interested in supporting TCSC?
contact_body: >-
  Contact club leadership to discuss sponsorship opportunities and current team
  needs.
contact_email: contact@twincitiesskiclub.org
contact_cta_label: Email club leadership
disclosure: >-
  Sponsor recognition acknowledges support and does not constitute endorsement
  of a sponsor's products or services.
```

- [ ] **Step 5: Compose the new sponsors page**

Replace `site/src/pages/sponsors.astro` with:

```astro
---
// /sponsors: recognition-first partner wall, verified collective impact,
// future priorities, and a direct sponsorship contact.
import { getEntry } from 'astro:content';
import { Image } from 'astro:assets';
import CTAStrip from '@/components/CTAStrip.astro';
import InnerPageLayout from '@/layouts/InnerPageLayout.astro';
import SectionBand from '@/components/SectionBand.astro';
import SponsorWall from '@/components/SponsorWall.astro';
import { CARD } from '@/components/imageWidths';
import { metaDescription } from '@/lib/metaDescription';
import greatBearChase from '@/assets/images/photos/great-bear-chase.jpg';
import rollerskiGoldenHour from '@/assets/images/photos/rollerski-golden-hour.jpg';

const page = await getEntry('sponsors_page', 'sponsors_page');
if (!page) throw new Error('sponsors_page singleton missing (src/content/pages/sponsors_page.yaml)');

const mailtoHref = `mailto:${page.data.contact_email}`;
---
<InnerPageLayout
  title="Sponsors · Twin Cities Ski Club"
  description={metaDescription(page.data.intro)}
  headline={page.data.headline}
  subhead={page.data.intro}
>
  <div class="mx-auto max-w-5xl px-6 md:px-10 py-16 md:py-20">
    <SponsorWall headingLevel="h2" />
  </div>

  <SectionBand variant="navy" seam="Sponsor impact">
    <div class="grid gap-10 md:grid-cols-12 md:gap-14 items-start">
      <div class="md:col-span-7">
        <h2 class="font-display font-semibold text-4xl md:text-5xl leading-[1.05] text-mint">
          {page.data.impact_heading}
        </h2>
        <p class="mt-5 max-w-[56ch] text-lg leading-relaxed text-paper/85">
          {page.data.impact_intro}
        </p>
        <div class="mt-10 border-y border-mint/20 divide-y divide-mint/20">
          {page.data.impact_items.map((item) => (
            <article class="py-6 grid gap-2 sm:grid-cols-[minmax(12rem,16rem)_1fr] sm:gap-8">
              <h3 class="font-semibold text-lg leading-snug text-mint">{item.title}</h3>
              <p class="leading-relaxed text-paper/80">{item.detail}</p>
            </article>
          ))}
        </div>
      </div>
      <figure class="md:col-span-5">
        <Image
          src={rollerskiGoldenHour}
          alt="A large group of TCSC members posing with roller skis and poles after a summer training session"
          widths={CARD}
          sizes="(min-width: 768px) 38vw, 100vw"
          class="w-full aspect-[4/3] md:aspect-[4/5] object-cover"
          loading="lazy"
        />
      </figure>
    </div>
  </SectionBand>

  <SectionBand variant="paper" seam="Partner recognition">
    <div class="grid gap-10 md:grid-cols-12 md:gap-16 items-center">
      <figure class="md:col-span-5">
        <Image
          src={greatBearChase}
          alt="A TCSC member wearing a black team jacket with Kwik Trip and Twin Cities Orthopedics logos beside another member and the Great Bear Chase mascot"
          widths={CARD}
          sizes="(min-width: 768px) 38vw, 100vw"
          class="w-full aspect-[4/5] object-cover"
          style="object-position: 68% center"
          loading="lazy"
        />
        <figcaption class="mt-3 text-sm leading-relaxed text-slate">
          {page.data.recognition_caption}
        </figcaption>
      </figure>
      <div class="md:col-span-7 md:pl-4">
        <h2 class="font-display font-semibold text-4xl md:text-5xl leading-[1.05] text-navy">
          {page.data.recognition_heading}
        </h2>
        <p class="mt-6 max-w-[62ch] text-xl leading-relaxed text-ink/80">
          {page.data.recognition_body}
        </p>
      </div>
    </div>

    <div class="mt-20 md:mt-28 pt-12 md:pt-16 border-t border-ink/15 grid gap-10 md:grid-cols-12 md:gap-14">
      <div class="md:col-span-5">
        <h2 class="font-display font-semibold text-4xl md:text-5xl leading-[1.05] text-navy">
          {page.data.priorities_heading}
        </h2>
        <p class="mt-5 max-w-[52ch] text-lg leading-relaxed text-ink/75">
          {page.data.priorities_intro}
        </p>
      </div>
      <div class="md:col-span-7 border-y border-ink/15 divide-y divide-ink/15">
        {page.data.priority_items.map((item) => (
          <article class="py-6">
            <h3 class="font-semibold text-xl text-navy">{item.title}</h3>
            <p class="mt-2 max-w-[62ch] leading-relaxed text-ink/75">{item.detail}</p>
          </article>
        ))}
      </div>
    </div>
  </SectionBand>

  <div class="bg-paper px-6 md:px-10 pb-8">
    <p class="mx-auto max-w-7xl text-xs leading-relaxed text-slate">
      {page.data.disclosure}
    </p>
  </div>

  <CTAStrip
    heading={page.data.contact_heading}
    subhead={page.data.contact_body}
    cta_label={page.data.contact_cta_label}
    cta_url={mailtoHref}
  />
</InnerPageLayout>
```

- [ ] **Step 6: Run the targeted tests and verify green**

Run:

```bash
cd site
npm run test:sponsors
```

Expected: the production build exits 0 and all sponsor tier/page tests pass.

- [ ] **Step 7: Run static diagnostics**

Run:

```bash
cd site
npm run check
```

Expected: `Result (46 files): 0 errors, 0 warnings, 0 hints` or the updated file count with the same zero diagnostics.

- [ ] **Step 8: Commit Task 2**

```bash
git add site/tests/sponsors-page.test.mjs site/package.json site/src/content.config.ts site/keystatic.config.ts site/src/content/pages/sponsors_page.yaml site/src/pages/sponsors.astro
git commit -m "feat: redesign sponsor recognition page"
```

---

## Final Review and Release Gate

After both tasks pass their task-level specification and quality reviews:

1. Run `npm run test:sponsors` and `npm run check` from `site/` on the complete feature branch.
2. Start the built site with `npm run preview -- --host 127.0.0.1`. In another shell, capture both viewports with the installed Chrome:

   ```bash
   sponsor_chrome_profile="$(mktemp -d)"
   sponsor_capture_dir="$(mktemp -d)"
   '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
     --headless=new \
     --hide-scrollbars \
     --user-data-dir="$sponsor_chrome_profile" \
     --window-size=1440,1800 \
     --screenshot="$sponsor_capture_dir/sponsors-desktop.png" \
     http://127.0.0.1:4321/sponsors
   '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
     --headless=new \
     --hide-scrollbars \
     --user-data-dir="$sponsor_chrome_profile" \
     --window-size=390,844 \
     --screenshot="$sponsor_capture_dir/sponsors-mobile.png" \
     http://127.0.0.1:4321/sponsors
   ```
3. Inspect both captures for hierarchy, sponsor-logo balance, logo overflow, copy measure, image crop, heading order, and contact prominence. Inspect `/` to confirm the home sponsor strip remains compact and unheaded.
4. Run an independent whole-branch adversarial review against `docs/superpowers/specs/2026-07-19-sponsor-recognition-page-design.md`. The review must challenge unsupported attribution, distinction between completed and future spending, content-schema parity, accessibility, responsive behavior, outbound-link treatment, and home-strip regressions.
5. Fix all Critical and Important findings in one fix pass, rerun the covering tests, and re-review until no blocking findings remain.
6. Run `git diff --check`, `npm run test:sponsors`, and `npm run check` immediately before integration.
7. Merge the reviewed branch into `main`, rerun the same commands on merged `main`, push `main`, and monitor the configured deployment.
8. Confirm the production `/sponsors` page returns HTTP 200 and contains `Trailblazer Partners`, `Sponsor support helped TCSC...`, and `contact@twincitiesskiclub.org` before reporting completion.
