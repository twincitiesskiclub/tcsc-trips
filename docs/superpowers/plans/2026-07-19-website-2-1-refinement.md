# Website 2.1 Refinement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to execute this plan task by task in the current session.

**Goal:** Refine the current TCSC marketing site without changing its established visual system: publish one useful Wax Room contingency article, make the conditions strip season-aware, remove the tablet-width navigation overflow, and correct a small set of misleading or overly corporate public copy.

**Architecture:** Keep the existing Astro content collections, page compositions, and navy/paper visual rhythm. Add one small pure TypeScript decision helper for the live-conditions client so season logic is testable without a browser. Make the remaining changes through existing content fields, breakpoints, and `InnerPageLayout` facts rather than introducing new UI patterns.

**Tech Stack:** Astro 7, TypeScript, Tailwind CSS 4, Markdoc, Node's built-in test runner, pytest/Playwright for final browser verification.

## Global Constraints

- This is a tick release, not a redesign. Preserve the current typography, color palette, photography, page compositions, and interaction style.
- Work only in `/Users/rob/env/tcsc-trips/.worktrees/site-2-1-refinement` on branch `feat/site-2-1-refinement`.
- Follow red-green-refactor for each task: add the smallest failing automated test, observe the expected failure, implement, then rerun the focused test.
- Do not change the server wax-temperature thresholds. Red wax can be valid above freezing when snow exists; the defect is that a successful July weather response bypasses the client's dryland presentation.
- April through October inclusive must render the dryland treatment even when the API succeeds. November through March must retain the current live conditions behavior.
- Do not attribute the Wax Room article to an individual without explicit publication approval. Omit `author_name`, photo, and conditions snapshot.
- Do not publish expired prices, discounts, participant names, speed promises, or current shop availability in the Wax Room article.
- Do not invent facts. Copy changes below use existing public content and the club's private-Slack coordination model.
- Keep all links truthful and useful. The global coming-soon registration CTA must point to confirmed dates on the home page, and the Dry Tri page must not send visitors to stale 2025 registration.
- Leave the coach-photo/profile follow-up and trip collection untouched; both require new assets or facts.
- Use `apply_patch` for hand-authored file changes. Preserve unrelated work.

## Task 1: Make live conditions season-aware on successful API responses

**Files:**

- Create: `site/src/lib/conditionsDisplayMode.ts`
- Create: `site/tests/conditionsDisplayMode.test.mjs`
- Modify: `site/src/components/LiveConditions.client.ts`

### Test first

- [ ] Create `site/tests/conditionsDisplayMode.test.mjs` using `node:test` and `node:assert/strict`.
- [ ] Import the pure helper from `../src/lib/conditionsDisplayMode.ts`.
- [ ] Cover these exact cases:
  - a healthy, non-empty payload at `2026-07-19T12:00:00-05:00` resolves to `off-season`;
  - an error/empty payload in July also resolves to `off-season`;
  - a healthy, non-empty payload at `2027-01-15T12:00:00-06:00` resolves to `live`;
  - an error/empty payload in January resolves to `unavailable`.
- [ ] Run `cd site && node --test tests/conditionsDisplayMode.test.mjs` and confirm it fails because the helper does not exist.

### Implement

- [ ] Add a pure exported `conditionsDisplayMode(payload, at = new Date())` helper returning the literal union `off-season | live | unavailable`.
- [ ] Define dryland season as local calendar months April through October inclusive.
- [ ] In `LiveConditions.client.ts`, use the helper before restoring or filling venue cells. A healthy July response must enter the same dryland presentation as a July fetch failure.
- [ ] Keep one shared rendering path for the dryland/unavailable quiet state; do not duplicate the DOM mutation block.
- [ ] Preserve the current presentation contract:
  - venue temperatures, wax labels/chips, report links, and grooming lines are hidden in dryland season;
  - compact/mobile output contains one `Dryland season` label;
  - prominent desktop retains the `98.6°` Birkie reading;
  - the prominent stamp says `● Trail reports come back with the snow`;
  - winter live payloads still render venue names, temperatures, wax, report links, grooming, and update time.

### Verify

- [ ] Rerun `cd site && node --test tests/conditionsDisplayMode.test.mjs` and confirm all cases pass.
- [ ] Run `cd site && npx astro check`.
- [ ] With a local Astro server and an intercepted healthy July payload containing 87°F and `Red wax · klister conditions`, verify the rendered home page contains one dryland message and no visible red-wax or venue-temperature output.
- [ ] Repeat with a January payload and verify live venue/wax output remains visible.
- [ ] Commit only this task's implementation and test.

## Task 2: Keep the hamburger navigation through tablet widths

**Files:**

- Create: `site/tests/responsiveNav.test.mjs`
- Modify: `site/src/components/Nav.astro`

### Test first

- [ ] Create a source contract test that reads `Nav.astro` and asserts:
  - the primary nav uses `hidden lg:flex`;
  - the CTA wrapper uses `hidden lg:flex`;
  - the menu button uses `lg:hidden`;
  - the old `hidden md:flex` and `md:hidden` navigation-mode classes are absent.
- [ ] Run `cd site && node --test tests/responsiveNav.test.mjs` and confirm it fails on the current `md` breakpoint.

### Implement

- [ ] Change only the navigation-mode breakpoints from `md` to `lg`; preserve spacing, active-state treatment, button styling, markup, and link order.
- [ ] Do not tune fixed widths around the current CTA label.

### Verify

- [ ] Rerun the focused Node test.
- [ ] Build the site and, at viewport widths 768, 782, 783, and 1024, assert `document.documentElement.scrollWidth === document.documentElement.clientWidth` on every public route.
- [ ] At 768, 782, and 783 verify exactly the hamburger navigation is visible; at 1024 verify exactly the desktop navigation is visible.
- [ ] Open and close the mobile menu once at 783 to confirm focus, Escape, and scroll-lock behavior remain intact.
- [ ] Commit only this task's implementation and test.

## Task 3: Publish the contingency Wax Room article

**Files:**

- Create: `site/src/content/wax_entries/stone-grind-or-hotbox.mdoc`
- Create: `site/tests/waxRoomEntry.test.mjs`

### Test first

- [ ] Create a test that requires the entry file and, after an Astro build, verifies:
  - the home page, Wax Room index, and detail route all contain `Stone Grind or Hotbox? When Skis Need a Second Wind`;
  - the detail route is `/wax-room/stone-grind-or-hotbox/`;
  - the source has date `2026-07-19` and no `author_name`, `photo`, or `conditions_snapshot` field;
  - the source includes the headings `What a stone grind changes`, `What a hotbox changes`, `Five useful things to tell the shop`, and `The short version`;
  - the article contains no dollar price, discount claim, or em dash.
- [ ] Run the focused test and confirm it fails because the entry does not exist.

### Implement

- [ ] Add the following frontmatter exactly, with no byline or image metadata:

```yaml
---
slug: Stone Grind or Hotbox? When Skis Need a Second Wind
date: 2026-07-19
lede: >-
  Last winter, eleven TCSC pairs headed to the shop together. Here is how to
  think about structure, wax conditioning, or both.
---
```

- [ ] Write a concise field guide grounded in the December 2025 TCSC group service order:
  - open with the member question and the eleven-pair response;
  - explain that the batch used Finn Sisu's universal grind for a Midwest/manmade mix and offered hotboxing for skis without regular waxing;
  - distinguish permanent base structure from wax conditioning;
  - explain that fine/medium/coarse/universal are snow-use choices, not a slow-to-fast ranking;
  - give five concrete facts a skier should tell a shop;
  - close with the ski-specific rule: grind when structure needs renewal, ask about hotboxing when conditioning may help, and choose both only when both jobs make sense.
- [ ] Keep the voice member-like, compact, practical, and non-promotional. Use no em dashes or exclamation points.

### Verify

- [ ] Run `cd site && npm run build` and confirm the Wax Room collection warning is gone and the new detail page is generated.
- [ ] Run `cd site && node --test tests/waxRoomEntry.test.mjs`.
- [ ] Inspect the home feed, index, and detail page at 390px and 1440px. Confirm title wrapping, heading rhythm, readable measure, and adjacent section seams fit the current design.
- [ ] Commit only this task's entry and test.

## Task 4: Correct registration, event, membership, mission, race, and sponsor copy

**Files:**

- Create: `site/tests/contentRefinements.test.mjs`
- Modify: `site/src/content/pages/home.yaml`
- Modify: `site/src/pages/index.astro`
- Modify: `site/src/components/CTAStrip.astro`
- Modify: `site/src/content/pages/dry_tri.mdoc`
- Modify: `site/src/content/pages/extra_training.mdoc`
- Modify: `site/src/content/pages/community.mdoc`
- Modify: `site/src/content/pages/racing.mdoc`
- Modify: `site/src/pages/sponsors.astro`

### Test first

- [ ] Add a source-and-built-output contract test for every exact change below, and first run it against current sources to observe failures.

### Implement exact copy and wiring

- [ ] In `home.yaml`, set:
  - `cta_coming_soon_label: Fall registration dates`
  - `cta_coming_soon_url: https://twincitiesskiclub.org/#registration`
  - mission paragraph: `TCSC is a 501(c)(3) nonprofit where young adult skiers train together twice a week, race if they want to, travel to Midwest ski weekends, volunteer, and organize workouts and socials beyond practice.`
- [ ] Add an optional `id` prop to `CTAStrip.astro`, forward it to the component's `<section>`, and pass `id="registration"` to the home-page CTA strip. Preserve every existing style class.
- [ ] Keep the existing home CTA subhead with the confirmed distinction: `Returning members Aug 28; new members Sep 3.`
- [ ] In `dry_tri.mdoc`, remove `register_url` and replace the 2026 paragraph with: `Planning for 2026 is underway. The date and registration details will be posted here when confirmed.` Preserve the 2025 recap and results link.
- [ ] In the Extra Training intro, replace `Everyone is welcome` with `Every member is welcome`.
- [ ] In Community's Extra Training detail, replace `No signup, everyone welcome.` with `No signup; all members welcome.`
- [ ] In Racing, replace `Two TCSC teams participated this year.` with `Two TCSC teams participated in 2026.`
- [ ] On Sponsors, pass `facts={[{ value: '501(c)(3) nonprofit', label: 'Status' }]}` to `InnerPageLayout` so nonprofit status appears in the masthead.

### Verify

- [ ] Run the focused contract test and confirm it passes.
- [ ] Run a production build and assert:
  - the coming-soon CTA label links to `https://twincitiesskiclub.org/#registration` and the target exists;
  - both Aug 28 and Sep 3 are visible in the registration section;
  - the Dry Tri page contains no 2026 registration-open promise and no stale `/tri` registration link;
  - the sponsor masthead includes `501(c)(3) nonprofit`;
  - rejected phrases `dedicated to fostering`, `promoting a healthy lifestyle`, `this year`, and bare `everyone welcome` are absent from public content.
- [ ] Inspect home, Dry Tri, Extra Training, Racing, Community, and Sponsors at 390px and 1440px for clean wraps and unchanged hierarchy.
- [ ] Commit only this task's implementation and test.

## Final Integration and Review

- [ ] Run all new Node tests together after a fresh production build.
- [ ] Run `cd site && npx astro check` and require zero errors, warnings, and hints.
- [ ] Run the existing sponsor suite.
- [ ] Run `/Users/rob/env/tcsc-trips/env/bin/pytest tests/conditions tests/wix_scrape -q` and preserve the 74-test green baseline.
- [ ] Crawl every built public route at 320, 390, 768, 782, 783, 1024, and 1440 widths for horizontal overflow, one H1, duplicate IDs, missing image alt text, and broken internal links.
- [ ] Review the entire branch against `main`, resolve all Critical/Important findings, and rerun affected tests.
- [ ] Record the remaining evidence-gated follow-ups: a better KJ portrait/profile source and explicit public-guest policy if club leadership wants nonmembers at informal workouts.
