# TCSC Marketing Copy Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the approved weak marketing copy with plain, specific TCSC language while preserving the club details and surfaces the user chose to keep.

**Architecture:** This is a source-copy change across Astro content entries and a small set of hardcoded Astro and TypeScript strings. Each task updates one reviewable content domain, verifies exact approved phrases with shell assertions, runs Astro's type/content check, and commits only its scoped files. No schema, component API, route, or layout changes are required.

**Tech Stack:** Astro 7, Markdoc content collections, YAML content entries, TypeScript, Tailwind CSS, Node.js 22+, npm.

## Global Constraints

- Prefer concrete activities and named details over claims about values.
- Prefer direct verbs over nonprofit abstractions such as "fostering," "promoting," and "providing."
- Use at most one playful ski reference on a surface. Club-specific language such as Techno Corner and Birkie Fever stays.
- Remove slogan structures, inflated claims, filler adjectives, and repeated points.
- Keep eligibility, fees, registration dates, and optional racing language explicit.
- Do not invent facts to improve a sentence. Leave uncertain copy unchanged until the club confirms it.
- This is a copy-only pass. Do not change content schemas, routes, layouts, styling, image assets, or application behavior.
- Do not edit `site/src/content/pages/home.yaml`, `site/src/content/pages/racing.mdoc`, the home registration-strip subheads, the Dry Tri, Wax Room, trips, photo records, alt text, Michael's bio, or the two `everyone is welcome` workout statements.
- Keep `Come ski with us.`, Techno Corner, Birkie Fever, the Symanski Glute Buster, Night of 1000 Salads, Everything is a Vegetable, Literary Loppet, Tour de Ice Cream, the TCSC Classic, and the apres-ski line.
- Use the user-edited design source at `docs/superpowers/specs/2026-07-18-marketing-copy-refresh-design.md`.
- Run every command from `/Users/rob/env/tcsc-trips` unless a step says otherwise.

## File Map

- `site/src/content/pages/about.mdoc`: About masthead and body copy.
- `site/src/content/pages/community.mdoc`: Community masthead, member description, and member-led activity details.
- `site/src/pages/community.astro`: Community fallback headline and section labels.
- `site/src/content/coaches/rebecca.mdoc`: Rebecca's public biography.
- `site/src/content/coaches/greg.mdoc`: Greg's public biography.
- `site/src/pages/coaches.astro`: Coaches-page metadata description.
- `site/src/content/practice_seasons/fall-winter.yaml`: Fall/Winter registration and trip labels.
- `site/src/content/practice_seasons/spring-summer.yaml`: Spring/Summer registration label.
- `site/src/components/SeasonsGrid.astro`: Shared practice and dues sentence.
- `site/src/layouts/BaseLayout.astro`: Default metadata description.
- `site/src/pages/index.astro`: Home photo-mosaic heading and link label only.
- `site/src/pages/404.astro`: 404 subhead and recovery copy.
- `site/src/components/LiveConditions.astro`: Compact Birkie Fever label.
- `site/src/components/LiveConditions.client.ts`: Screen-reader wax-change announcement.

---

### Task 1: Rewrite the About page

**Files:**
- Modify: `site/src/content/pages/about.mdoc:1-19`

**Interfaces:**
- Consumes: the existing `about` singleton schema fields `headline` and `intro`, plus its Markdoc body.
- Produces: the same schema and links, with approved public copy consumed by `site/src/pages/about.astro`.

- [ ] **Step 1: Run the exact-copy assertion and confirm the new copy is absent**

```bash
rg -Fq 'TCSC brings young adult skiers together for year-round training, optional racing, and an active community beyond practice.' site/src/content/pages/about.mdoc &&
rg -Fq 'New registration is currently limited to skiers ages 21-35.' site/src/content/pages/about.mdoc &&
! rg -Fq 'We put skiers on snow' site/src/content/pages/about.mdoc
```

Expected: exit 1 because the approved intro and registration sentence are not present and the rejected intro is still present.

- [ ] **Step 2: Replace the About source with the approved copy**

```mdoc
---
headline: About Twin Cities Ski Club
intro: >-
  TCSC brings young adult skiers together for year-round training, optional
  racing, and an active community beyond practice.
---
TCSC started in 2020 to help young adult cross-country skiers in the Twin Cities find one another. Members now train, race, volunteer, and spend time together year-round.

## Who joins TCSC

New registration is currently limited to skiers ages 21-35.

New members should already have intermediate cross-country ski skills. Speed and racing experience do not matter. We cannot offer beginner lessons yet, but [Three Rivers](https://www.threeriversparks.org/activity/cross-country-skiing#lessons) and the [Loppet Foundation](https://loppet.org/Experiences/learn-to-ski/) do.

For many members, TCSC is where they train, volunteer, and make friends outside work and home. See what that looks like on our [Community page](/community).

## Coaching

TCSC's four [coaches](/coaches) plan and lead practices throughout the dryland and snow seasons.
```

- [ ] **Step 3: Re-run the exact-copy assertion**

Run the Step 1 command again.

Expected: exit 0. The approved intro and registration sentence are present, and the rejected slogan is absent.

- [ ] **Step 4: Validate the content entry**

Run: `npm --prefix site run check`

Expected: exit 0 with no Astro errors.

- [ ] **Step 5: Commit the About rewrite**

```bash
git add site/src/content/pages/about.mdoc
git commit -m "content(site): rewrite about copy"
```

### Task 2: Rewrite the Community page

**Files:**
- Modify: `site/src/content/pages/community.mdoc:1-95`
- Modify: `site/src/pages/community.astro:55-91`

**Interfaces:**
- Consumes: the existing `community` singleton fields and `takeaways` structure.
- Produces: unchanged content shapes for `community.astro`, with new headline, intro, body, labels, and section copy.

- [ ] **Step 1: Run the Community copy assertion and confirm it fails**

```bash
rg -Fq 'headline: What members do beyond practice' site/src/content/pages/community.mdoc &&
rg -Fq 'Members run the club' site/src/content/pages/community.mdoc &&
rg -Fq 'heading="How members pitch in"' site/src/pages/community.astro &&
! rg -Fq 'A welcoming community' site/src/content/pages/community.mdoc site/src/pages/community.astro &&
! rg -Fq 'National-level trip staff' site/src/content/pages/community.mdoc
```

Expected: exit 1 because the approved copy is absent and the rejected copy is present.

- [ ] **Step 2: Apply the Community content replacements**

```diff
--- a/site/src/content/pages/community.mdoc
+++ b/site/src/content/pages/community.mdoc
@@
-headline: A welcoming community
-intro: Volunteer nights, socials, member coaching, and extra training beyond practice.
+headline: What members do beyond practice
+intro: Volunteer nights, socials, member coaching, and extra workouts organized by TCSC members.
@@
-      - line: The club is 100% volunteer run
+      - line: Members run the club
         detail: >-
-          An unpaid board, monthly meetings open to any member, and committees
-          for practices, socials, trips, marketing, apparel, and the Dry Tri.
+          A volunteer board holds monthly meetings open to every member, with
+          committees for practices, socials, trips, marketing, apparel, and
+          the Dry Tri.
@@
-      - line: National-level trip staff
+      - line: Coaching and waxing at national races
         detail: >-
-          Members have worked CXC Midwest Team trips to US Junior Nationals and
-          Canadian Nationals as coaches and wax techs.
+          Members have joined CXC Midwest Team trips to U.S. Junior Nationals
+          and Canadian Nationals as coaches and wax techs.
@@
       - line: Thursday Track Club and The Sunday Roll
-        detail: Standing invitations, all season.
+        detail: Both run throughout dryland season.
       - line: The TCSC Classic and the Tour de Ice Cream
-        detail: Member-invented annuals.
+        detail: Members started both events, and each returns once a year.
@@
-Twin Cities Ski Club is an inclusive community for any cross-country skier ages 21-35 who lives in the greater Minneapolis · St. Paul area, regardless of race, gender, sexual orientation, or religion. Our members are a mix of Twin Cities transplants looking to establish roots with skiers their own age, retired high school or collegiate racers in search of a new team, and apres-ski lovers who put up with intervals in exchange for post-practice brews.
+TCSC welcomes intermediate cross-country skiers ages 21-35 who live in the greater Minneapolis and St. Paul area. Skiers of every race, gender, sexual orientation, and religion are welcome. Our members include Twin Cities transplants meeting skiers their age, former high school and college racers looking for a new team, and apres-ski lovers who put up with intervals for post-practice brews.
```

- [ ] **Step 3: Apply the Community page-label replacements**

```diff
--- a/site/src/pages/community.astro
+++ b/site/src/pages/community.astro
@@
-  headline={community.data.headline ?? 'A welcoming community'}
+  headline={community.data.headline ?? 'What members do beyond practice'}
@@
-      seam="Club record"
-      heading="What we've done"
-      subhead="A few seasons of volunteering, coaching, socials, and member-led training."
+      seam="Member-led"
+      heading="How members pitch in"
```

- [ ] **Step 4: Re-run the Community copy assertion**

Run the Step 1 command again.

Expected: exit 0. All approved labels are present, and both generic labels are absent.

- [ ] **Step 5: Validate the Community content and template**

Run: `npm --prefix site run check`

Expected: exit 0 with no Astro errors.

- [ ] **Step 6: Commit the Community rewrite**

```bash
git add site/src/content/pages/community.mdoc site/src/pages/community.astro
git commit -m "content(site): rewrite community copy"
```

### Task 3: Rewrite the coach summaries

**Files:**
- Modify: `site/src/pages/coaches.astro:18-25`
- Modify: `site/src/content/coaches/rebecca.mdoc:14`
- Modify: `site/src/content/coaches/greg.mdoc:13`

**Interfaces:**
- Consumes: the existing coach collection schema and rendered Markdoc bodies.
- Produces: unchanged coach entries and page props with factual metadata and biographies.

- [ ] **Step 1: Run the coach-copy assertion and confirm it fails**

```bash
rg -Fq "KJ, Greg, Rebecca, and Michael lead TCSC's ski technique, endurance, and strength sessions." site/src/pages/coaches.astro &&
rg -Fq 'Rebecca started skiing in middle school and later joined the University of Minnesota ski team.' site/src/content/coaches/rebecca.mdoc &&
rg -Fq 'Greg is a sports scientist with a PhD in Kinesiology and Exercise Science from the University of Minnesota.' site/src/content/coaches/greg.mdoc &&
! rg -Fq 'bring joy, excitement, and knowledge' site/src/pages/coaches.astro &&
! rg -Fq 'skiing journey' site/src/content/coaches/rebecca.mdoc
```

Expected: exit 1 because none of the approved summaries are present.

- [ ] **Step 2: Replace the coach-page description**

```diff
--- a/site/src/pages/coaches.astro
+++ b/site/src/pages/coaches.astro
@@
-  description="KJ, Greg, Rebecca, and Michael bring joy, excitement, and knowledge to every practice."
+  description="KJ, Greg, Rebecca, and Michael lead TCSC's ski technique, endurance, and strength sessions."
```

- [ ] **Step 3: Replace Rebecca's and Greg's biographies**

`site/src/content/coaches/rebecca.mdoc` body:

```md
Rebecca started skiing in middle school and later joined the University of Minnesota ski team. She has coached high school skiers and now coaches Finn Sisu's Vakava team.
```

`site/src/content/coaches/greg.mdoc` body:

```md
Greg is a sports scientist with a PhD in Kinesiology and Exercise Science from the University of Minnesota. He has also supported athletes at the MTB World Cup in Snowshoe, West Virginia.
```

- [ ] **Step 4: Re-run the coach-copy assertion**

Run the Step 1 command again.

Expected: exit 0. The factual summaries are present, and the generic phrases are absent.

- [ ] **Step 5: Validate the coach collection and page**

Run: `npm --prefix site run check`

Expected: exit 0 with no Astro errors.

- [ ] **Step 6: Commit the coach rewrite**

```bash
git add site/src/pages/coaches.astro site/src/content/coaches/rebecca.mdoc site/src/content/coaches/greg.mdoc
git commit -m "content(site): tighten coach biographies"
```

### Task 4: Clarify season and dues copy

**Files:**
- Modify: `site/src/content/practice_seasons/fall-winter.yaml:7-11`
- Modify: `site/src/content/practice_seasons/spring-summer.yaml:7`
- Modify: `site/src/components/SeasonsGrid.astro:81-87`

**Interfaces:**
- Consumes: the existing `practice_seasons` fields `registration_note` and `trips`.
- Produces: the same string fields consumed by `SeasonsGrid`, plus revised static dues copy.

- [ ] **Step 1: Run the season-copy assertion and confirm it fails**

```bash
rg -Fq '2026 registration: returning members Aug 28 · new members Sep 3' site/src/content/practice_seasons/fall-winter.yaml &&
rg -Fq 'Sisu Ski Fest and the American Birkebeiner' site/src/content/practice_seasons/fall-winter.yaml &&
rg -Fq '2026 registration closed · 2027 opens Apr/May' site/src/content/practice_seasons/spring-summer.yaml &&
rg -Fq 'Practices run twice a week with KJ, Greg, Rebecca, and Michael. Dues cover coaching and reserved workout space.' site/src/components/SeasonsGrid.astro &&
! rg -Fq "season's odds and ends" site/src/components/SeasonsGrid.astro
```

Expected: exit 1 because the approved registration, trips, and dues copy is absent.

- [ ] **Step 2: Update the season entries**

```diff
--- a/site/src/content/practice_seasons/fall-winter.yaml
+++ b/site/src/content/practice_seasons/fall-winter.yaml
@@
-registration_note: Returning Aug 28 · new members Sep 3
+registration_note: '2026 registration: returning members Aug 28 · new members Sep 3'
@@
-trips: Sisu, the Birkie, and more
+trips: Sisu Ski Fest and the American Birkebeiner
--- a/site/src/content/practice_seasons/spring-summer.yaml
+++ b/site/src/content/practice_seasons/spring-summer.yaml
@@
-registration_note: Closed for 2026 · reopens Apr/May
+registration_note: 2026 registration closed · 2027 opens Apr/May
```

The Fall/Winter value is quoted because its colon is part of the displayed YAML string.

- [ ] **Step 3: Replace the shared dues sentence and correct its source comment**

```diff
--- a/site/src/components/SeasonsGrid.astro
+++ b/site/src/components/SeasonsGrid.astro
@@
-    {/* Dues transparency and shared practice details, rendered once below
-        both season columns. Fee line is verbatim from the club's register
-        page. */}
+    {/* Dues transparency and shared practice details, rendered once below
+        both season columns. */}
@@
-        Organized evening practices twice per week, coached by KJ, Greg, Rebecca, and Michael. Dues cover coaching, workout space reservations, and the season's odds and ends.
+        Practices run twice a week with KJ, Greg, Rebecca, and Michael. Dues cover coaching and reserved workout space.
```

- [ ] **Step 4: Re-run the season-copy assertion**

Run the Step 1 command again.

Expected: exit 0. Every revised value is present and the vague dues phrase is absent.

- [ ] **Step 5: Validate the season entries and component**

Run: `npm --prefix site run check`

Expected: exit 0 with no Astro errors.

- [ ] **Step 6: Commit the season-copy changes**

```bash
git add site/src/content/practice_seasons/fall-winter.yaml site/src/content/practice_seasons/spring-summer.yaml site/src/components/SeasonsGrid.astro
git commit -m "content(site): clarify season details"
```

### Task 5: Tighten shared metadata, Home, and 404 copy

**Files:**
- Modify: `site/src/layouts/BaseLayout.astro:14-18`
- Modify: `site/src/pages/index.astro:82-88`
- Modify: `site/src/pages/404.astro:28-47`

**Interfaces:**
- Consumes: existing `BaseLayout` description default, `PhotoMosaic` string props, and `InnerPageLayout` string props.
- Produces: unchanged component calls with clearer strings. The home mission and registration-strip subheads remain untouched.

- [ ] **Step 1: Run the shared-copy assertion and confirm it fails**

```bash
rg -Fq 'Year-round cross-country ski training and community for adults 21-35 in Minneapolis-St. Paul, with coached practices, racing, and trips.' site/src/layouts/BaseLayout.astro &&
rg -Fq 'heading="Beyond practice"' site/src/pages/index.astro &&
rg -Fq 'more_label="See what members do"' site/src/pages/index.astro &&
rg -Fq 'subhead="The page may have moved, or the link may point to our old site."' site/src/pages/404.astro &&
rg -Fq 'Choose another page.' site/src/pages/404.astro &&
! rg -Fq 'Head back to the clubhouse.' site/src/pages/404.astro
```

Expected: exit 1 because the new strings are absent and the stacked 404 metaphors remain.

- [ ] **Step 2: Replace the default metadata description**

```diff
--- a/site/src/layouts/BaseLayout.astro
+++ b/site/src/layouts/BaseLayout.astro
@@
-  description = 'Twin Cities Ski Club is a nonprofit dedicated to fostering a supportive community for young adults (21-35) by promoting a healthy lifestyle through cross-country ski training sessions and educational programming.',
+  description = 'Year-round cross-country ski training and community for adults 21-35 in Minneapolis-St. Paul, with coached practices, racing, and trips.',
```

- [ ] **Step 3: Replace only the approved Home mosaic strings**

```diff
--- a/site/src/pages/index.astro
+++ b/site/src/pages/index.astro
@@
-    heading="A welcoming community"
+    heading="Beyond practice"
@@
-    more_label="More from the community"
+    more_label="See what members do"
```

Do not change `ctaStripSubhead`, `HeroHome`'s subline, `Come ski with us.`, or `home.yaml`.

- [ ] **Step 4: Remove the extra 404 metaphors**

```diff
--- a/site/src/pages/404.astro
+++ b/site/src/pages/404.astro
@@
-  subhead="The page may have moved, or the link may be from our old site. We can get you back on a familiar track."
+  subhead="The page may have moved, or the link may point to our old site."
@@
-          Head back to the clubhouse.
+          Choose another page.
@@
-          Start from the home page, or use one of the well-groomed routes nearby.
+          Start at the home page or use one of the links below.
```

Keep the headline `This trail ends here.`, the trail photograph, destination list, and button unchanged.

- [ ] **Step 5: Re-run the shared-copy assertion**

Run the Step 1 command again.

Expected: exit 0. The approved Home, metadata, and 404 strings are present, and the clubhouse line is absent.

- [ ] **Step 6: Validate the shared templates**

Run: `npm --prefix site run check`

Expected: exit 0 with no Astro errors.

- [ ] **Step 7: Commit the shared-copy changes**

```bash
git add site/src/layouts/BaseLayout.astro site/src/pages/index.astro site/src/pages/404.astro
git commit -m "content(site): tighten shared page copy"
```

### Task 6: Clarify conditions labels for sighted and screen-reader users

**Files:**
- Modify: `site/src/components/LiveConditions.astro:90-103`
- Modify: `site/src/components/LiveConditions.client.ts:74-84`

**Interfaces:**
- Consumes: the existing compact conditions markup and `LocResp.wax_label`.
- Produces: the same DOM hooks and announcement flow, with `Birkie fever` as the visible label and a semantically accurate wax-recommendation message.

- [ ] **Step 1: Run the conditions-copy assertion and confirm it fails**

```bash
rg -Fq '<span class="tracking-widest uppercase text-mint">Birkie fever</span>' site/src/components/LiveConditions.astro &&
rg -Fq 'announcements.push(`${loc.name} wax recommendation changed: ${loc.wax_label}`);' site/src/components/LiveConditions.client.ts &&
! rg -Fq 'announcements.push(`${loc.name} wax changed to ${loc.wax_label}`);' site/src/components/LiveConditions.client.ts
```

Expected: exit 1 because the compact label and announcement still use the old wording.

- [ ] **Step 2: Replace the compact label and announcement**

```diff
--- a/site/src/components/LiveConditions.astro
+++ b/site/src/components/LiveConditions.astro
@@
-        <span class="tracking-widest uppercase text-mint">Birkie</span>
+        <span class="tracking-widest uppercase text-mint">Birkie fever</span>
--- a/site/src/components/LiveConditions.client.ts
+++ b/site/src/components/LiveConditions.client.ts
@@
-      announcements.push(`${loc.name} wax changed to ${loc.wax_label}`);
+      announcements.push(`${loc.name} wax recommendation changed: ${loc.wax_label}`);
```

- [ ] **Step 3: Re-run the conditions-copy assertion**

Run the Step 1 command again.

Expected: exit 0. The compact label and accurate live-region message are present, and the old announcement is absent.

- [ ] **Step 4: Validate the Astro and TypeScript sources**

Run: `npm --prefix site run check`

Expected: exit 0 with no Astro or TypeScript errors.

- [ ] **Step 5: Commit the conditions-copy changes**

```bash
git add site/src/components/LiveConditions.astro site/src/components/LiveConditions.client.ts
git commit -m "fix(site): clarify conditions copy"
```

### Task 7: Run integrated copy, build, metadata, and visual verification

**Files:**
- Verify only: all files changed in Tasks 1-6.
- Create only outside the repository: screenshots under `/tmp/tcsc-copy-review/`.

**Interfaces:**
- Consumes: the six independently checked implementation commits.
- Produces: a passing static build, source-copy audit, metadata-length report, screenshots, and a reviewable six-commit diff.

- [ ] **Step 1: Run the full Astro check**

Run: `npm --prefix site run check`

Expected: exit 0 with no Astro or TypeScript errors.

- [ ] **Step 2: Build the production site**

Run: `npm --prefix site run build`

Expected: exit 0. Astro writes the static site to `site/dist` and generates About, Community, Coaches, Home, 404, and inner-page output.

- [ ] **Step 3: Confirm rejected phrases are gone from their approved target files**

```bash
if rg -n -F \
  -e 'We put skiers on snow' \
  -e 'A welcoming community' \
  -e 'The club is 100% volunteer run' \
  -e 'National-level trip staff' \
  -e 'Standing invitations, all season.' \
  -e 'Member-invented annuals.' \
  -e 'bring joy, excitement, and knowledge' \
  -e 'skiing journey' \
  -e 'bridges exercise science theory' \
  -e "description = 'Twin Cities Ski Club is a nonprofit dedicated" \
  -e 'heading="A welcoming community"' \
  -e 'more_label="More from the community"' \
  -e 'Returning Aug 28 · new members Sep 3' \
  -e 'Closed for 2026 · reopens Apr/May' \
  -e 'Sisu, the Birkie, and more' \
  -e "season's odds and ends" \
  -e 'familiar track' \
  -e 'Head back to the clubhouse.' \
  -e 'well-groomed routes nearby' \
  -e '<span class="tracking-widest uppercase text-mint">Birkie</span>' \
  -e 'wax changed to' \
  site/src/content/pages/about.mdoc \
  site/src/content/pages/community.mdoc \
  site/src/pages/community.astro \
  site/src/pages/coaches.astro \
  site/src/content/coaches/rebecca.mdoc \
  site/src/content/coaches/greg.mdoc \
  site/src/content/practice_seasons/fall-winter.yaml \
  site/src/content/practice_seasons/spring-summer.yaml \
  site/src/components/SeasonsGrid.astro \
  site/src/layouts/BaseLayout.astro \
  site/src/pages/index.astro \
  site/src/pages/404.astro \
  site/src/components/LiveConditions.astro \
  site/src/components/LiveConditions.client.ts; then
  exit 1
fi
```

Expected: exit 0 with no matching output.

- [ ] **Step 4: Confirm the approved copy reached generated HTML**

```bash
rg -Fq 'TCSC brings young adult skiers together for year-round training, optional racing, and an active community beyond practice.' site/dist/about/index.html &&
rg -Fq 'What members do beyond practice' site/dist/community/index.html &&
rg -Fq 'How members pitch in' site/dist/community/index.html &&
rg -Fq 'Rebecca started skiing in middle school and later joined the University of Minnesota ski team.' site/dist/coaches/index.html &&
rg -Fq 'Beyond practice' site/dist/index.html &&
rg -Fq '2026 registration: returning members Aug 28 · new members Sep 3' site/dist/index.html &&
rg -Fq 'Choose another page.' site/dist/404.html
```

Expected: exit 0. Every changed public page contains its approved copy.

- [ ] **Step 5: Verify generated metadata lengths**

```bash
node --input-type=module <<'NODE'
import { readFileSync } from 'node:fs';

const pages = [
  'site/dist/index.html',
  'site/dist/about/index.html',
  'site/dist/community/index.html',
  'site/dist/coaches/index.html',
  'site/dist/404.html',
];

for (const page of pages) {
  const html = readFileSync(page, 'utf8');
  const description = html.match(/<meta name="description" content="([^"]*)"/)?.[1];
  if (!description) throw new Error(`${page}: missing meta description`);
  if (description.length > 160) {
    throw new Error(`${page}: description is ${description.length} characters`);
  }
  console.log(`${page}: ${description.length}`);
}
NODE
```

Expected: exit 0. Each page prints a description length of 160 characters or fewer.

- [ ] **Step 6: Start the production preview for visual checks**

Run: `npm --prefix site run preview -- --host 127.0.0.1`

Expected: the preview server stays running at `http://127.0.0.1:4321`.

- [ ] **Step 7: Capture desktop and mobile review screenshots**

```bash
mkdir -p /tmp/tcsc-copy-review
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 --window-size=1440,4000 --screenshot=/tmp/tcsc-copy-review/home-desktop.png http://127.0.0.1:4321/
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 --window-size=1440,2800 --screenshot=/tmp/tcsc-copy-review/about-desktop.png http://127.0.0.1:4321/about
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 --window-size=390,4200 --screenshot=/tmp/tcsc-copy-review/about-mobile.png http://127.0.0.1:4321/about
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 --window-size=1440,5600 --screenshot=/tmp/tcsc-copy-review/community-desktop.png http://127.0.0.1:4321/community
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 --window-size=390,7600 --screenshot=/tmp/tcsc-copy-review/community-mobile.png http://127.0.0.1:4321/community
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 --window-size=1440,5200 --screenshot=/tmp/tcsc-copy-review/coaches-desktop.png http://127.0.0.1:4321/coaches
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 --window-size=1440,1500 --screenshot=/tmp/tcsc-copy-review/404-desktop.png http://127.0.0.1:4321/404.html
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 --window-size=1440,1600 --screenshot=/tmp/tcsc-copy-review/racing-conditions-desktop.png http://127.0.0.1:4321/racing
```

Expected: eight PNG files exist under `/tmp/tcsc-copy-review/`. Chrome may print benign sandbox or metrics warnings, but every command exits 0.

- [ ] **Step 8: Inspect every screenshot**

Use `view_image` on each PNG from Step 7.

Expected: no clipped text, overflow, accidental duplicate paragraphs, broken content bands, or awkward heading wraps. The compact inner-page strip reads `Birkie fever`. If a screenshot exposes a copy-wrap problem, adjust only the affected approved string, rerun that task's assertion and `npm --prefix site run check`, and document the deviation for the user.

- [ ] **Step 9: Present the implementation diff for the user's general review**

```bash
git diff --stat HEAD~6..HEAD -- site/src
git diff HEAD~6..HEAD -- site/src
```

Expected: the diff contains only the 14 source files listed in the File Map, with no edits to `home.yaml`, `racing.mdoc`, schemas, styles, routes, or assets.
