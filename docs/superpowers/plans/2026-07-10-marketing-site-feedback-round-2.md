# Marketing Site July 2026 Feedback Round 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved design spec at `docs/superpowers/specs/2026-07-10-marketing-site-feedback-round-2-design.md` (committed on this branch): trail-report provenance (API fields + strip links/groomed line), mobile strip shows Theo Wirth instead of Birkie fever, hero focal fix, `How to register` closed CTA, seasons contrast bump, home mosaic photo swap, bottom-scrim hover captions, community subhead trim + ETF ledger group, crop audit, verified race dates, footer link order.

**Architecture:** All work on branch `feat/site-feedback-july-2026` in the git worktree `/Users/rob/env/tcsc-trips-site`. Two surfaces: the Astro static site (`site/`) and the Flask conditions API (`app/conditions/`, `app/routes/conditions.py`, tests in `tests/conditions/`). The API fields ship in the same PR; they deploy with the web service on merge, and the static strip degrades gracefully (fields absent -> nothing renders), so deploy order does not matter. No new photo ports: every image change reuses already-consented collection assets, so `migration/` files do not change.

**Tech stack:** Astro 5 + content collections, Tailwind tokens (navy/mint/mint-deep/paper/ink/slate), Flask + pytest.

**Working directories:**
- Repo root (worktree): `/Users/rob/env/tcsc-trips-site` - git, python, pytest (activate venv: `source env/bin/activate`)
- Site: `/Users/rob/env/tcsc-trips-site/site` - npm / astro commands

**Verification commands used throughout:**
- `cd /Users/rob/env/tcsc-trips-site/site && npx astro check` - 0 errors expected
- `cd /Users/rob/env/tcsc-trips-site/site && NODE_ENV=production npx astro build` - must end "10 page(s) built"
- `cd /Users/rob/env/tcsc-trips-site && source env/bin/activate && pytest tests/conditions tests/wix_scrape -q`
- NEVER run bare `pytest` (binds prod DB); use explicit paths only.
- Image-judgment steps: use the Read tool on the image file (it renders visually); judge crops with a dev-server screenshot when noted.

---

### Task 1: Baseline

**Files:** none (verification only)

- [ ] **Step 1: Confirm branch and clean state**

```bash
cd /Users/rob/env/tcsc-trips-site
git status --porcelain   # expect only untracked migration/dns-rollback-2026-06-11.json; stop if site/ files show
git log --oneline -2     # expect the spec commit on feat/site-feedback-july-2026
```

- [ ] **Step 2: Baseline build**

```bash
cd site && npx astro check && NODE_ENV=production npx astro build
cd .. && source env/bin/activate && pytest tests/conditions tests/wix_scrape -q
```

Expected: 0 errors, 10 pages, all tests pass.

---

### Task 2: Conditions API provenance fields

**Files:**
- Modify: `app/conditions/service.py` (location payload builder, ~lines 42-77)
- Modify: `tests/conditions/` (payload-shape tests)

- [ ] **Step 1: Read the current shape.** Read `app/conditions/service.py` in full, plus the `TrailCondition` dataclass it consumes (defined in `app/interfaces` or `app/integrations/trail_conditions.py` - find it) to confirm the exact attribute names: `report_url`, `report_date` (datetime or None), `groomed` (bool), `groomed_for` (str or None).

- [ ] **Step 2: Write failing tests first** (superpowers:test-driven-development). In the existing conditions test file that covers the location payload, add cases:
  - With a matched trail report carrying `report_url='https://www.skinnyski.com/trails/...'`, `report_date=datetime(2026, 2, 8)`, `groomed=True`, `groomed_for='skate'`: payload location includes `source_url` (same URL), `report_date == '2026-02-08'`, `groomed_for == 'skate'`.
  - With no matched report (dryland): all three keys present and `None`.
  Follow the existing tests' fixture/mocking style exactly. Run `pytest tests/conditions -q` - the new tests must FAIL before the implementation.

- [ ] **Step 3: Implement.** In `service.py`, extend the per-location dict:

```python
'source_url': report.report_url if report else None,
'report_date': report.report_date.date().isoformat() if report and report.report_date else None,
'groomed_for': (report.groomed_for or ('both' if report.groomed else None)) if report else None,
```

Adapt to the real local variable names; if the builder only keeps `ski_quality` today, thread the whole `TrailCondition` through instead. `groomed_for` semantics: the report's value when set; `'both'` when groomed with no discipline parsed; `None` when not groomed or no report.

- [ ] **Step 4: Green + commit**

```bash
pytest tests/conditions -q   # all pass
git add app/conditions/service.py tests/conditions/
git commit -m "feat(conditions): expose per-venue source_url, report_date, groomed_for"
```

---

### Task 3: Strip provenance rendering

**Files:**
- Modify: `site/src/components/LiveConditions.client.ts` (VenueData type + fill logic)
- Modify: `site/src/components/LiveConditions.astro` (venue cell markup hooks)

- [ ] **Step 1: Read both files in full** to map how venue cells are server-rendered and client-filled (name, temp, feels-like, wax label, the info-toggle detail line, and the compact variant lines).

- [ ] **Step 2: Extend the client type**: add `source_url: string | null`, `report_date: string | null`, `groomed_for: string | null` to the venue interface.

- [ ] **Step 3: Venue-name link (both variants).** The venue name is server-rendered; give it a client hook (e.g. wrap the name text in an `<a>` that starts `hidden`/inert or a `data-source-link` span). On fill: when `source_url` is present, the name becomes a link to it (`target="_blank" rel="noopener"`), styled in the ledger link treatment already used sitewide: `underline underline-offset-4 decoration-mint/40 hover:decoration-mint` (on navy). When absent, plain text exactly as today. No icon, no tooltip.

- [ ] **Step 4: Groomed line (prominent variant only).** When `groomed_for` is present, append to the cell's detail line: `Groomed skate · Feb 8` / `Groomed classic · Feb 8` / `Groomed · Feb 8` (when `'both'`); date from `report_date` formatted short-month + day, no year; omit the date part if `report_date` is null. Muted color and the small type scale the detail line already uses. When `groomed_for` is null, render nothing (dryland = today's exact output).

- [ ] **Step 5: Check, build, visual.** `npx astro check && NODE_ENV=production npx astro build`. Dev server: in July the strip must look IDENTICAL to production today (fields are null). Then verify the winter path by temporarily stubbing the fetch response in the browser console or a scratch HTML harness - confirm link + groomed line render, then remove any stub.

- [ ] **Step 6: Commit**

```bash
git add site/src/components/LiveConditions.client.ts site/src/components/LiveConditions.astro
git commit -m "feat(site): trail report source links and groomed-as-of line"
```

---

### Task 4: Mobile strip shows Theo Wirth, not Birkie fever

**Files:**
- Modify: `site/src/components/LiveConditions.astro` (responsive classes, both variants)
- Modify: `site/src/components/LiveConditions.client.ts` (dryland label visibility)

- [ ] **Step 1: Prominent variant.** Venue cells currently all carry `max-md:hidden` (LiveConditions.astro:45); the Birkie cell is `col-span-2 md:col-span-1` (:73). Remove `max-md:hidden` from the `wirth` cell only and give it `col-span-2 md:col-span-1`; add `max-md:hidden` to the Birkie fever cell. Desktop layout unchanged (5 cells).

- [ ] **Step 2: Compact variant.** Venue lines carry `max-md:hidden` (:91). Same swap: `wirth` line visible on mobile, Birkie line `max-md:hidden`.

- [ ] **Step 3: Dryland mobile.** In `.client.ts` (~117-127) the off-season path injects a "Dryland season" label with `max-md:hidden` and hides venue cells. Make the dryland statement visible at all widths (drop `max-md:hidden` from the injected label) and ensure the wirth cell is hidden with the rest when collapsed, so mobile shows exactly `Trail report - Dryland season`.

- [ ] **Step 4: Verify at 390px.** Dev server, narrow viewport, home + one inner page: today (July) the strip shows the eyebrow + single Dryland statement, no Birkie cell, no empty grid track. Desktop unchanged, fever audio still works md+. Screenshot both.

- [ ] **Step 5: Commit**

```bash
git add site/src/components/LiveConditions.astro site/src/components/LiveConditions.client.ts
git commit -m "feat(site): mobile trail strip leads with Theo Wirth, fever cell md+"
```

---

### Task 5: Hero focal fix

**Files:**
- Modify: `site/src/components/HeroHome.astro` (~line 28, `object-[center_38%]`)

- [ ] **Step 1: Read the image** `site/src/assets/images/uploads/home-hero-trail.jpg` and locate every face relative to frame height.

- [ ] **Step 2: Adjust `object-position`** so no face sits under the bottom-anchored text block (headline + subline + CTA, bottom ~35% of the 74vh frame). Screenshot the dev server at ~390px, ~768px, ~1440px and iterate until clear at all three; if impossible, favor desktop and record the compromise for the PR body.

- [ ] **Step 3: Commit**

```bash
git add site/src/components/HeroHome.astro
git commit -m "fix(site): hero focal point keeps faces clear of the headline"
```

---

### Task 6: Closed CTA relabel

**Files:**
- Modify: `site/src/content/pages/home.yaml` (cta_closed_label)

- [ ] **Step 1:** `cta_closed_label: Registration opens Aug/Sep` becomes `cta_closed_label: How to register`. Nothing else changes (URL stays `https://tcsc.ski`; subheads and season cards keep the months).

- [ ] **Step 2: Build + grep-count all render sites**

```bash
cd site && NODE_ENV=production npx astro build
grep -c "How to register" dist/index.html          # expect 4 (nav, mobile panel, hero, strip)
grep -c "How to register" dist/about/index.html    # expect 2 (nav, mobile panel)
grep -c "Registration reopens Aug/Sep" dist/index.html   # expect 1 (strip subhead keeps the months)
```

- [ ] **Step 3: Commit**

```bash
git add site/src/content/pages/home.yaml
git commit -m "feat(site): closed CTA reads How to register"
```

---

### Task 7: Seasons contrast

**Files:**
- Modify: `site/src/components/SeasonsGrid.astro` (~line 40)

- [ ] **Step 1:** Navy variant `muted = 'text-paper/60'` becomes `'text-paper/75'`. Paper variant untouched.
- [ ] **Step 2:** `npx astro check`; dev-server glance at the home Seasons band (date ranges, closed note, dues paragraph all read comfortably).
- [ ] **Step 3: Commit** - `git add site/src/components/SeasonsGrid.astro && git commit -m "fix(site): seasons muted text contrast on navy"`

---

### Task 8: Home mosaic photo swap

**Files:**
- Modify: `site/src/content/photos/oo-corridor.yaml`, `fire-danger-maria.yaml` (show_on_home -> false)
- Modify: `site/src/content/photos/rollerski-treats.yaml` + ONE of `finlandia-axes.yaml` / `great-bear-chase.yaml` / `borah-epic.yaml` (show_on_home -> true, order values)

- [ ] **Step 1: Read the mosaic slotting.** Read `site/src/components/PhotoMosaic.astro` to learn how `order` maps to tile size (1x1 / 2x1 / 2x2 pattern) and which order slots the two cut photos (orders 10 and 100) occupied.

- [ ] **Step 2: View candidates.** Read the image files behind `rollerski-treats`, `finlandia-axes`, `great-bear-chase`, `borah-epic` (paths in their yamls). Pick rollerski-treats + the strongest second (group of 2+, mid-action or celebrating, survives its slot's crop - the order-10 slot renders large).

- [ ] **Step 3: Flip flags + orders.** Exactly 9 entries end with `show_on_home: true`. Assign the newcomers order values that keep event-tag variety spread through the grid (avoid two `race` tags adjacent if slotting allows).

- [ ] **Step 4: Visual check.** Dev server home: 9 photos, flush grid at ~390px and desktop, every tile 2+ people (loppet-skijor's skier + dog stays per spec), no crop disasters on the two newcomers - fix with the same order-shuffle if needed.

- [ ] **Step 5: Commit** - `git add site/src/content/photos/ && git commit -m "feat(site): home mosaic swaps in group photos"`

---

### Task 9: Mosaic hover scrim

**Files:**
- Modify: `site/src/components/PhotoMosaic.astro` (~lines 178-185)

- [ ] **Step 1:** Replace the caption overlay's `absolute inset-0 ... bg-navy/70` with a bottom scrim: `absolute inset-x-0 bottom-0 bg-gradient-to-t from-navy/85 via-navy/50 to-transparent pt-10 px-4 pb-4`. Keep `hidden md:flex items-end`, the caption text markup, `opacity-0 group-hover:opacity-100`, and the 150ms transition exactly as they are.
- [ ] **Step 2:** Dev server: hover a captioned tile - photo stays fully visible, caption fades in over the bottom scrim only; uncaptioned tiles unchanged; lightbox click still works. Check a long caption doesn't overflow the scrim (deepen `pt-` if needed).
- [ ] **Step 3: Commit** - `git add site/src/components/PhotoMosaic.astro && git commit -m "feat(site): mosaic hover caption rides a bottom scrim"`

---

### Task 10: Community subhead + ETF ledger group

**Files:**
- Modify: `site/src/content/pages/community.mdoc` (intro, body paragraph, takeaways, +ETF group)
- Modify: `site/src/pages/community.astro` (remove trailing ETF link paragraph, section subhead)

- [ ] **Step 1: intro.** Replace the 33-word intro with: `Volunteer nights, socials, member coaching, and extra training beyond practice.`

- [ ] **Step 2: body merge.** Prepend/merge the full inclusivity sentence (`Twin Cities Ski Club is an inclusive community for any cross-country skier ages 21-35 who lives in the greater Minneapolis · St. Paul area, regardless of race, gender, sexual orientation, or religion.`) into the existing single body paragraph, editing the join so nothing repeats. Keep the sentence's wording intact apart from joining punctuation. No em dashes, no exclamation points.

- [ ] **Step 3: ETF takeaways group.** Append after Socials (exact schema of existing groups):

```yaml
- group: Extra training fun
  items:
    - line: Member-organized workouts, most days of the week
      detail: Track mornings, long rollerskis, open-water swims. No signup, everyone welcome.
      href: /extra-training-fun
    - line: Thursday Track Club and The Sunday Roll
      detail: Standing invitations, all season.
    - line: The TCSC Classic and the Tour de Ice Cream
      detail: Member-invented annuals.
```

(Adapt key names to the real takeaways schema in `site/src/content.config.ts` - read it first. No anchor photo for this group.)

- [ ] **Step 4: community.astro.** Delete the trailing `Member-organized workouts are on their own page: ...` paragraph (~lines 126-132). Update the SectionBand subhead to `A few seasons of volunteering, coaching, socials, and member-led training.`

- [ ] **Step 5: Check, build, visual.** `npx astro check && NODE_ENV=production npx astro build`. Dev server /community: short subhead; body carries the inclusivity sentence once; four groups render (ETF last, no photo, link on its first line); no stray ETF paragraph below the ledger.

- [ ] **Step 6: Commit** - `git add site/src/content/pages/community.mdoc site/src/pages/community.astro && git commit -m "feat(site): tighter community masthead, extra training joins the club record"`

---

### Task 11: Crop audit

**Files:**
- Modify: `site/src/pages/community.astro`, `site/src/pages/racing.astro`, possibly `site/src/pages/about.astro` (object-position values only)

- [ ] **Step 1: View every audited image at its rendered crop.** For each below: Read the source image, then screenshot the dev-server rendering at ~390px and desktop, and set/adjust `object-position` only where heads or key subjects are clipped:
  - `second-harvest` (community.astro:43, currently `center 65%` - the reported head-cutter; likely wants a lower percentage to lift the crop toward faces)
  - member cluster x4: `backyard-social`, `run-club-selfie`, `winter-five`, `lakeside-picnic` (h-48 md:h-64, none set)
  - `barn-banquet` (none set)
  - racing strip: `ski-de-she-trio`, `korte-medals`, `birkie-start`, `finlandia-podium` (aspect-[3/4], none set)
  - About `rollerski-golden-hour`; masthead bands `team-banner` (40%), `canoe-social` (52%), `race-crew-frosty` (30%) - verify, expected fine.
- [ ] **Step 2: No other changes** - sizes, aspects, layout untouched.
- [ ] **Step 3: Commit** - `git add site/src/pages/ && git commit -m "fix(site): crop audit keeps heads in frame across pages"`

---

### Task 12: Race dates

**Files:**
- Modify: `site/src/content/pages/racing.mdoc` (races list dates)

- [ ] **Step 1:** Apply ONLY the confirmed-official dates from the spec's "Verified 2026-27 race dates" addendum (do not re-research; do not guess). Races without a confirmed date keep their current labels. Format `Jan 9, 2027` / `Feb 25-27, 2027`.
- [ ] **Step 2:** Build + dev-server glance at /racing: date column widths hold in the `sm:grid-cols-[10rem_1fr_1fr]` grid at both breakpoints.
- [ ] **Step 3: Commit** - `git add site/src/content/pages/racing.mdoc && git commit -m "feat(site): official 2026-27 race dates"`

---

### Task 13: Footer link order

**Files:**
- Modify: `site/src/components/Footer.astro` (~lines 11-23)

- [ ] **Step 1:** Restructure the interleaving `grid-cols-2` flow into two explicit column lists reading top-to-bottom in nav order: column A `About, Community, Racing, Coaches, Wax Room`; column B `Sponsors, Trips, Extra Training & Fun, Dry Tri`. Same links, same styling, no additions/removals.
- [ ] **Step 2:** Dev server: footer columns read in nav order on desktop and stacked mobile.
- [ ] **Step 3: Commit** - `git add site/src/components/Footer.astro && git commit -m "fix(site): footer links read in nav order"`

---

### Task 14: Full verification pass

**Files:** none

- [ ] **Step 1: Full battery**

```bash
cd /Users/rob/env/tcsc-trips-site && source env/bin/activate
cd site && npx astro check && NODE_ENV=production npx astro build && cd ..
python -m scripts.wix_scrape.verify; echo "verify exit: $?"
pytest tests/conditions tests/wix_scrape -q
grep -c "How to register" site/dist/index.html            # 4
grep -c "Come ski with us." site/dist/index.html          # 1, no '!' variant anywhere
```

- [ ] **Step 2: Visual sweep** at ~390px and desktop: home (hero faces clear, mosaic 9 group photos + hover scrim, seasons contrast, mobile strip = Dryland statement), /community (subhead, ETF group, crops), /racing (dates, strip crops), /about, footer order everywhere.

- [ ] **Step 3: Code review** (superpowers:requesting-code-review) of the full branch diff against the spec, then push and open the PR (superpowers:finishing-a-development-branch). PR body: summary per spec section, the rejected-items rationale, the two flagged follow-ups for Rob (exact Birkie count, ETF anchor photo), and any hero-focal compromise note.

---

## Plan deviations from spec (flagged for review)

None at plan time. The spec's race-dates section depends on the research addendum; if no race has a confirmed-official 2027 date, Task 12 becomes a no-op and the PR body says so.
