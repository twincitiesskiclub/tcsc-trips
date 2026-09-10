# Marketing Site Brand Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Audit every page of twincitiesskiclub.org for brand drift, elevation, and vibe-coded slop; rewrite `DESIGN.md` as the v2 contract; implement the ledger with Codex agents per workstream on an integration branch; verify the result is one brand on every page and better than v1; put it on a Render preview before anything reaches `main`.

**Architecture:** Three phases separated by human gates. Phase 1: a screenshot harness (four static builds of the site, one per registration state plus one with fixture content, served locally and captured through the sibling Playwright container) plus nine read-only Fable agents (six lens, two gestalt, one synthesis) produce a ledger and `DESIGN.md` v2. Phase 2: four Codex `gpt-5.6-sol` agents at reasoning `max`, one per workstream, each in a worktree branched from `site/brand-review`, implement their ledger rows using the VibeCurb skill pipeline. Phase 3: three Fable agents adversarially verify against fresh screenshots. All branches hang off `site/brand-review`; `main` is touched once, by the one-line PR that enables Render pull-request previews.

**Tech Stack:** Astro 7 static build (`site/`), Tailwind 4, Node 24 here (Render builds on 22.22.0), `playwright-core` 1.61.1 (harness-local; matches the `intimate-brand-browser` container's `playwright run-server`), Codex CLI 0.151 (`codex exec`), Claude Code `Agent` tool with `model: "fable"`.

**Spec:** `docs/superpowers/specs/2026-08-31-site-brand-review-design.md`

## Global Constraints

- Every commit in this plan lands on `site/brand-review` or a `brand/<ws>` branch off it. The only commit to `main` is Task 2's `render.yaml` change, via PR. Every commit on `main` is a Render deploy.
- Presentation only in phase 2: no JS behavior, no new runtime dependencies (`site/package.json` `dependencies` unchanged), no content-schema (`site/src/content.config.ts`), Keystatic, API-contract, or `render.yaml` header changes.
- Sacred files (may be restyled at call sites, never edited): `site/src/lib/registrationState.ts`, `registrationFlip.ts`, `seasonData.ts`, `seasonSlug.ts`, `pageScrollLock.ts`, `samePageAnchor.ts`, `conditionsDisplayMode.ts`, `site/src/components/registrationCta.ts`, `LiveConditions.client.ts`, `PhotoMosaic.client.ts`.
- Fixed identity: the nine color tokens in `site/tailwind.config.ts`; Archivo Variable (body) and PolySans BulkyWide (display); no serif, no mono; real consented photos only, no stock, no generated production imagery; the Live Conditions strip stays.
- Every phase 2 change cites a ledger id (`L-nnn`). Uncited changes are reported, not made.
- From `site/`: `npm run check`, `npm run build`, `npm run test:refinement`, `npm run test:sponsors`, `npm run test:fallback` pass at the end of every workstream and after every merge.
- Copy rules: plain register, no em dashes, no exclamation points, no invented facts (the July 18 copy refresh spec).
- Viewports: mobile 390x844, desktop 1440x900, tablet 768x1024 (home hero only). Screenshot filename: `<surface>-<state>-<viewport>.png`.
- Nothing fake is ever committed under `site/src/content/`. Fixture content lives in `scripts/brand-review/fixtures/content/` and is copied in and out by the build script.
- Fixed ports: fixture API 4499; main dist server 4400; Codex workstreams 4401 (foundations), 4402 (copy), 4403 (motion-components), 4404 (sections); verifiers 4405; phase 1 lens and gestalt agents 4411-4418 (one each, so their live-browsing servers never collide).
- Hand Rob `https://preview.eaer.app/` or a Render preview URL, never a `localhost` link.

## File map

```
.agents/skills/<name>/SKILL.md                      five VibeCurb skills, unmodified (Task 1)
.agents/skills/README.md                            role of each skill here (Task 1)
.claude/skills/<name> -> ../../.agents/skills/<name> relative symlinks (Task 1)
render.yaml                                         + previews.generation on tcsc-team-site (Task 2, to main)
scripts/brand-review/
  package.json, package-lock.json, .gitignore       playwright-core only (Task 3)
  browser.mjs                                       connect to the sibling browser (Task 3)
  smoke.mjs                                         one screenshot to prove the chain (Task 3)
  fixture-api.mjs                                   season + conditions fixture server, port 4499 (Task 4)
  fixtures.test.mjs                                 payloads derive the intended states (Task 4)
  fixtures/content/trips/sisu-ski-fest.mdoc         fixture trip (Task 4)
  fixtures/content/wax_entries/first-snow-wax.mdoc  fixture wax entry (Task 4)
  build-state.mjs                                   one static build per state into builds/<name>/ (Task 4)
  serve-dist.mjs                                    Render-like static server; --preview mode for preview.eaer.app (Task 5)
  states.mjs                                        the state matrix as data (Task 5)
  screenshot.mjs                                    capture every state at every viewport (Task 5)
  ledger-rows.sh                                    print one workstream's open ledger rows (Task 10)
  run-codex.sh, resume-codex.sh                     Codex launcher / resumer (Task 10)
docs/superpowers/specs/2026-08-31-site-brand-review/
  state-matrix.md                                   (Task 5)
  screens/before/*.png                              (Task 6)
  prompts/*.md                                      (Tasks 7, 10, 12)
  lens-*.md, gestalt-*.md, ledger.md, contract-changes.md   (Task 8, by agents)
  <ws>-report.md, screens/after/*.png               (Task 11, by Codex)
  verification.md, screens/verify/*.png             (Task 12, by agents)
DESIGN.md                                           v2 (Task 8, by synthesis)
```

---

### Task 1: Vendor the VibeCurb skills

**Files:**
- Create: `.agents/skills/{awwwards-hero,awwwards-motion,awwwards-sections,imagegen-frontend,visual-redesign}/SKILL.md`
- Create: `.agents/skills/README.md`
- Create: `.claude/skills/<name>` symlinks (five)

**Interfaces:**
- Produces: skill files at a stable repo path that every prompt cites (`/workspace/tcsc-trips/.agents/skills/<name>/SKILL.md`). `~/.codex/skills/<name>` already points at the coffee copies, which are byte-identical, so Codex needs no relink.

- [ ] **Step 1: Copy the files from the coffee checkout**

```bash
cd /workspace/tcsc-trips
mkdir -p .agents/skills .claude/skills
for s in awwwards-hero awwwards-motion awwwards-sections imagegen-frontend visual-redesign; do
  mkdir -p .agents/skills/$s
  cp /workspace/intimate-coffee/.agents/skills/$s/SKILL.md .agents/skills/$s/SKILL.md
  ln -sfn ../../.agents/skills/$s .claude/skills/$s
done
wc -l .agents/skills/*/SKILL.md
for s in .claude/skills/*; do test -f "$s/SKILL.md" && echo "ok $s" || echo "BROKEN $s"; done
cmp .agents/skills/visual-redesign/SKILL.md ~/.codex/skills/visual-redesign/SKILL.md && echo "codex copy identical"
```

Expected: five line counts (587 / 764 / 772 / 714 / 1102 as of 2026-08-31), seven `ok` lines (the two existing project skills plus five links), `codex copy identical`.

- [ ] **Step 2: Write `.agents/skills/README.md`**

```markdown
# vibecurb skills

Pulled 2026-08-31 from https://github.com/Yu-369/VibeCurb (`skills/<name>/SKILL.md`, branch `main`), unmodified. Copied from the intimate-coffee checkout, which pulled them the same day.

Canonical copy lives here. Discovery paths are symlinks to it:
- `.claude/skills/<name>` (Claude Code, project scope; committed)
- `~/.codex/skills/<name>` (Codex CLI, user scope; points at the coffee copies, byte-identical)

Used by the marketing site brand review: `docs/superpowers/specs/2026-08-31-site-brand-review-design.md`.
The brief is `DESIGN.md`. These files are method and quality gate, not the brief.
Any instruction in a skill to add a dependency is overridden by the review's no-new-dependency rule.

| folder | frontmatter name | role in this repo |
|---|---|---|
| visual-redesign | visual-redesign | workhorse. 7-layer audit, sacred/slop classification, CSS-only surgery. written for React; applies unchanged to Astro components and Tailwind classes |
| awwwards-sections | awwwards-sections | SectionBand, CTAStrip, Footer, SeasonsGrid, PhotoMosaic, CoachEntry, SponsorWall, TripsTable. hierarchy, spacing, and anti-slop gates only; no pricing, bento, or social-proof patterns |
| awwwards-hero | awwwards-hero-section | HeroHome and HeroInner only, starting from the current fold, not a blank brief |
| awwwards-motion | awwwards-motion-design | audit and CSS-only tuning of existing motion. its Framer Motion / GSAP / Lenis guidance is ignored; its `linear()` easings, timing sheets, and reduced-motion rules are used. any new micro-interaction is a gate 1 contract change because DESIGN.md v1 says "Section transitions: none" |
| imagegen-frontend | imagegen-frontend-web | photo-treatment and composition rubric for the motion+imagery lens. no production assets. a reference board for the OG image only if the ledger asks |

Prompts reference the files by path.
```

- [ ] **Step 3: Commit**

```bash
git add .agents .claude/skills
git commit -m "chore(brand-review): vendor vibecurb skills, link into claude discovery"
```

---

### Task 2: Enable Render pull-request previews on the static site

**Files:**
- Modify: `render.yaml` (the `tcsc-team-site` service block, after `staticPublishPath: site/dist`)

**Interfaces:**
- Produces: any PR against `main` builds a preview of `tcsc-team-site` with production env vars and headers. Task 11 opens that PR from `site/brand-review`.

- [ ] **Step 1: Branch from main and add the field**

```bash
cd /workspace/tcsc-trips
git checkout -b chore/site-pr-previews main
```

In `render.yaml`, directly under the line `            staticPublishPath: site/dist` (12-space indent), add:

```yaml
            # Pull-request previews build this static site with the same
            # command, env vars, and headers as production, so a site change
            # can be walked at a Render URL before it merges (and deploys).
            previews:
              generation: automatic
```

Do not add a `branch:` field: Render docs say a set `branch` overrides the PR's branch in every preview.

- [ ] **Step 2: Validate the YAML and diff**

```bash
python3 -c "import yaml,sys; d=yaml.safe_load(open('render.yaml')); s=[x for e in d['projects'][0]['environments'] for x in e['services'] if x['name']=='tcsc-team-site'][0]; print(s['previews'])"
git diff --stat
```

Expected: `{'generation': 'automatic'}` and `render.yaml | 5 +`.

- [ ] **Step 3: Commit, push, open the PR, merge it**

```bash
git commit -am "chore(render): pull-request previews for the marketing site"
git push -u origin chore/site-pr-previews
gh pr create --base main --head chore/site-pr-previews --title "Enable Render PR previews for the marketing site" --body "$(cat <<'EOF'
One blueprint field. Any PR against main now builds a preview of tcsc-team-site with the production build command, env vars, and headers. No change to the live site.

Needed so the marketing site brand review (docs/superpowers/specs/2026-08-31-site-brand-review-design.md) can be walked at a Render URL before it merges.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01QVWHyaQMoWGXv3VTKdXX4u
EOF
)"
```

Rob merges (or says to merge). After merge:

```bash
git checkout site/brand-review && git merge --ff-only origin/main 2>/dev/null || (git fetch origin && git rebase origin/main)
```

Expected: `site/brand-review` now contains the preview field. Confirm on Render (`mcp__render__get_service` for `tcsc-team-site`, or the dashboard) that the service shows previews enabled after the blueprint sync.

---

### Task 3: Screenshot harness scaffold

**Files:**
- Create: `scripts/brand-review/package.json`, `scripts/brand-review/.gitignore`
- Create: `scripts/brand-review/browser.mjs`
- Create: `scripts/brand-review/smoke.mjs`

**Interfaces:**
- Produces: `getBrowser(): Promise<Browser>` (playwright-core `Browser` connected to `ws://127.0.0.1:3333/`), `BASE_URL` (default `http://127.0.0.1:4400`). Every later script imports these.

- [ ] **Step 1: Package and ignore files**

`scripts/brand-review/package.json`:

```json
{
  "name": "site-brand-review-harness",
  "private": true,
  "type": "module",
  "dependencies": {
    "playwright-core": "1.61.1"
  }
}
```

`scripts/brand-review/.gitignore`:

```
node_modules
builds
smoke.png
```

```bash
cd /workspace/tcsc-trips/scripts/brand-review && npm install --no-audit --no-fund
node -e "import('playwright-core').then(m=>console.log(Object.keys(m).includes('chromium')?'ok':'missing'))"
```

Expected: `ok`. The version pin must match the server container's `playwright@1.61.1`; a mismatch fails `connect` with a protocol error.

- [ ] **Step 2: Write `browser.mjs`**

```js
// Shared browser access for the site brand-review harness.
// This container has no chromium system libs and no root, so the browser runs in a
// sibling container (intimate-brand-browser, mcr.microsoft.com/playwright:v1.61.1-noble,
// `playwright run-server --port 3333 --host 127.0.0.1`) that shares this container's
// network namespace (--network container:<this id>). Both sides therefore use 127.0.0.1:
// the browser reaches our dist server and fixture api, and we reach the browser.
import { chromium } from "playwright-core";

export const BASE_URL = process.env.BASE_URL ?? "http://127.0.0.1:4400";
export const BROWSER_WS = process.env.BROWSER_WS ?? "ws://127.0.0.1:3333/";

export async function getBrowser() {
  try {
    return await chromium.connect(BROWSER_WS, { timeout: 15000 });
  } catch (e) {
    throw new Error(
      `cannot connect to ${BROWSER_WS}: ${e.message.split("\n")[0]}\n` +
        `start it with: docker start intimate-brand-browser`,
    );
  }
}
```

- [ ] **Step 3: Write `smoke.mjs` and prove the chain against the production site**

```js
// usage: node smoke.mjs [url]  -> smoke.png. Proves the browser container is reachable.
import { getBrowser } from "./browser.mjs";

const url = process.argv[2] ?? "https://twincitiesskiclub.org/";
const browser = await getBrowser();
const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
await page.goto(url, { waitUntil: "networkidle", timeout: 30000 });
console.log("season source:", await page.getAttribute("body", "data-season-source"));
await page.screenshot({ path: "smoke.png", fullPage: true });
await browser.close();
console.log("ok");
```

```bash
cd /workspace/tcsc-trips/scripts/brand-review && node smoke.mjs && ls -la smoke.png
```

Expected: `season source: api` (or `fallback` if tcsc.ski was down at the last deploy), `ok`, a png of a few hundred KB. If `connect` fails: `docker ps --filter name=intimate-brand-browser` then `docker start intimate-brand-browser`. If it prints `season source: null`, the page did not load; check the URL.

- [ ] **Step 4: Commit**

```bash
cd /workspace/tcsc-trips
git add scripts/brand-review/package.json scripts/brand-review/package-lock.json scripts/brand-review/.gitignore scripts/brand-review/browser.mjs scripts/brand-review/smoke.mjs
git commit -m "chore(brand-review): screenshot harness scaffold"
```

---

### Task 4: Fixture API, content fixtures, and per-state builds

**Files:**
- Create: `scripts/brand-review/fixture-api.mjs`
- Create: `scripts/brand-review/fixtures.test.mjs`
- Create: `scripts/brand-review/fixtures/content/trips/sisu-ski-fest.mdoc`
- Create: `scripts/brand-review/fixtures/content/wax_entries/first-snow-wax.mdoc`
- Create: `scripts/brand-review/build-state.mjs`

**Interfaces:**
- Produces from `fixture-api.mjs`: `seasonPayload(state: 'open'|'soon'|'closed')` → the JSON body `/api/season` returns; `conditionsPayload(mode: 'live'|'dryland')` → the JSON body `/api/conditions` returns; `startFixtureApi(port = 4499)` → `{ port, close() }`; `ensureFixtureApi()` → starts it only if nothing answers on 4499. Routes: `GET /season/<state>`, `GET /conditions/<mode>`.
- Produces from `build-state.mjs`: `node build-state.mjs <open|soon|closed|populated>` writes a complete static site to `scripts/brand-review/builds/<name>/` whose pages bake `PUBLIC_SEASON_API_URL=http://127.0.0.1:4499/season/<state>` and `PUBLIC_CONDITIONS_API_URL=http://127.0.0.1:4499/conditions/live`, and exits non-zero unless `index.html` carries `data-season-source="api"`. `populated` is the `open` state plus the fixture trip and wax entry.

- [ ] **Step 1: Write the failing test**

`scripts/brand-review/fixtures.test.mjs`:

```js
import assert from "node:assert/strict";
import test from "node:test";
import { deriveRegistrationState } from "../../site/src/lib/registrationState.ts";
import { conditionsDisplayMode } from "../../site/src/lib/conditionsDisplayMode.ts";
import { seasonPayload, conditionsPayload } from "./fixture-api.mjs";

const now = Date.now();

test("season fixtures derive the state they are named for, in the browser and at build", () => {
  for (const [state, expected] of [["open", "open"], ["soon", "coming_soon"], ["closed", "closed"]]) {
    const body = seasonPayload(state);
    assert.equal(deriveRegistrationState(body.primary, now), expected, state);
    assert.equal(deriveRegistrationState(body.by_type["fall/winter"], now), expected, state);
    assert.equal(typeof body.generated_at, "string");
  }
});

test("conditions fixtures drive the display modes", () => {
  const august = new Date("2026-08-31T12:00:00-05:00");
  assert.equal(conditionsDisplayMode(conditionsPayload("live"), august), "live");
  assert.equal(conditionsDisplayMode(conditionsPayload("dryland"), august), "off-season");
  assert.equal(conditionsPayload("live").locations.length, 4);
});
```

- [ ] **Step 2: Run it to confirm it fails**

```bash
cd /workspace/tcsc-trips/scripts/brand-review && node --test fixtures.test.mjs
```

Expected: FAIL with `Cannot find module .../fixture-api.mjs`. (Node 24 runs the `.ts` imports natively with type stripping; the site's own tests do the same.)

- [ ] **Step 3: Write `fixture-api.mjs`**

```js
// Fixture API for the site brand review. Serves the two endpoints the marketing site
// reads (season at build time, conditions in the browser) with deterministic payloads.
//   node fixture-api.mjs            keeps a server up on 4499 (ctrl-c to stop)
//   import { ... } from "./fixture-api.mjs"   for tests and build-state.mjs
// Windows are relative to NOW so registrationFlip.ts (which re-derives state in the
// browser) agrees with what the build baked. Shape mirrors app/seasons + site/scripts/test-build.mjs.
import { createServer } from "node:http";
import { connect } from "node:net";

export const FIXTURE_PORT = 4499;
const DAY = 24 * 60 * 60 * 1000;
const iso = (offsetDays) =>
  new Date(Date.now() + offsetDays * DAY).toISOString().replace(/\.\d{3}Z$/, "Z");

// returning window, then new-member window, as day offsets from now.
const WINDOWS = {
  open: [-1, 3, 5, 20],
  soon: [30, 40, 45, 60],
  closed: [-60, -50, -45, -30],
};

export function seasonPayload(state) {
  const w = WINDOWS[state];
  if (!w) throw new Error(`unknown season state ${state}`);
  const season = (season_type, name) => ({
    name,
    season_type,
    year: new Date().getFullYear(),
    price_cents: 20500,
    returning_start: iso(w[0]),
    returning_end: iso(w[1]),
    new_start: iso(w[2]),
    new_end: iso(w[3]),
  });
  const fw = season("fall/winter", "Fixture Fall/Winter");
  return {
    generated_at: iso(0),
    primary: fw,
    by_type: { "fall/winter": fw, "spring/summer": season("spring/summer", "Fixture Spring/Summer") },
  };
}

const VENUES = [
  ["wirth", "Theodore Wirth"],
  ["hyland", "Hyland"],
  ["french", "French Park"],
  ["battle-creek", "Battle Creek"],
];

export function conditionsPayload(mode) {
  const updated_at = new Date().toISOString();
  if (mode === "dryland") return { updated_at, error: "Conditions unavailable", locations: [] };
  if (mode !== "live") throw new Error(`unknown conditions mode ${mode}`);
  const temps = [12, 18, 27, 33];
  const bands = [
    ["green", "Green wax · cold snow"],
    ["blue", "Blue wax · firm snow"],
    ["purple", "Purple · transition snow"],
    ["red", "Red wax · klister conditions"],
  ];
  return {
    updated_at,
    locations: VENUES.map(([id, name], i) => ({
      id,
      name,
      temp_f: temps[i],
      wind_chill_f: temps[i] - (i === 1 ? 6 : 1),
      snow_conditions: "groomed",
      wax_band: bands[i][0],
      wax_label: bands[i][1],
      source_url: `https://www.skinnyski.com/trails/report.asp?id=${100 + i}`,
      report_date: new Date().toISOString().slice(0, 10),
      groomed_for: i % 2 ? "both" : "skate",
    })),
    birkie: { status: "rising", word: "101.2°", detail: "Fever climbing. Wave assignments posted." },
  };
}

function handler(req, res) {
  const [, kind, arg] = new URL(req.url, "http://x").pathname.split("/");
  try {
    const body = kind === "season" ? seasonPayload(arg) : kind === "conditions" ? conditionsPayload(arg) : null;
    if (!body) throw new Error("not found");
    res.writeHead(200, {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
      "Access-Control-Allow-Origin": "*",
    });
    res.end(JSON.stringify(body));
  } catch (e) {
    res.writeHead(404, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: String(e.message) }));
  }
}

export function startFixtureApi(port = FIXTURE_PORT) {
  const server = createServer(handler);
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, "127.0.0.1", () => resolve({ port, close: () => server.close() }));
  });
}

function portOpen(port) {
  return new Promise((resolve) => {
    const s = connect({ port, host: "127.0.0.1" });
    s.once("connect", () => { s.end(); resolve(true); });
    s.once("error", () => resolve(false));
  });
}

/** Start the fixture api unless something already answers on the port. */
export async function ensureFixtureApi(port = FIXTURE_PORT) {
  if (await portOpen(port)) return { port, close: () => {}, external: true };
  return startFixtureApi(port);
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].split("/").pop())) {
  const { port } = await startFixtureApi();
  console.log(`fixture api on http://127.0.0.1:${port}  (/season/open|soon|closed, /conditions/live|dryland)`);
}
```

- [ ] **Step 4: Run the test to confirm it passes**

```bash
cd /workspace/tcsc-trips/scripts/brand-review && node --test fixtures.test.mjs
```

Expected: `# pass 2`. If `deriveRegistrationState` returns `closed` for `open`, the site's window logic has changed since 2026-08-31; read `site/src/lib/registrationState.ts:41` and adjust the day offsets.

- [ ] **Step 5: Write the content fixtures**

`scripts/brand-review/fixtures/content/trips/sisu-ski-fest.mdoc` (schema: `site/src/content.config.ts` `trips`; the hero image already exists at `site/src/assets/images/trips/sisu-ski-fest-hero.jpg`):

```markdown
---
slug: Sisu Ski Fest (fixture)
location: Ironwood, Michigan
dates: January 9-11, 2027
cost_summary: $180 covers two nights of lodging and a shared van
signup_deadline: December 12, 2026
capacity: 24 skiers
refund_policy: Full refund until the deadline, then only if your spot is filled
signup_url: https://tcsc.ski/
hero_photo: ../../assets/images/trips/sisu-ski-fest-hero.jpg
hero_photo_alt: Skiers in TCSC suits lined up at the Sisu Ski Fest start in falling snow
order: 10
---

Sisu is the club's first race weekend of the year. Most members ski the 21K skate or classic; a few take on the 42K. The Friday drive ends at a rented house in Ironwood with a wax room in the garage.

Saturday is the race. Sunday is a recovery ski on the ABR trails, then the drive home.

Trip details are a fixture for the brand review. Nothing here is a real offer.
```

`scripts/brand-review/fixtures/content/wax_entries/first-snow-wax.mdoc` (schema: `wax_entries`; the photo is already published on the site):

```markdown
---
slug: First snow, first wax of the year (fixture)
date: 2026-11-22
author_name: Coach Fixture
author_role: coach
lede: Fresh snow at Wirth and the first real blue-wax day of the season.
photo: ../../assets/images/photos/night-practice.jpg
photo_alt: Skiers under the lights at a night practice
conditions_snapshot:
  location: Theodore Wirth
  temp_f: 18
  wax_used: Swix V40 Blue Extra
---

Wirth groomed the 5K loop overnight and the snow held. At 18°F with no wind, blue kick wax was the whole answer: two thin layers, corked smooth, and it lasted the full practice.

If the temperature climbs past 28°F this week, move to purple. Below 14°F, go green.

This entry is a fixture for the brand review.
```

- [ ] **Step 6: Write `build-state.mjs`**

```js
// usage: node build-state.mjs <open|soon|closed|populated>
// Builds the marketing site once for one registration state into builds/<name>/.
// `populated` = open + the fixture trip and wax entry copied into site/src/content for the
// duration of the build only. The fixture api must be reachable on 4499 during the build
// (started here if needed) and again when the pages are opened, because the conditions
// url is baked into the html for the browser to fetch.
import { spawn } from "node:child_process";
import { cpSync, existsSync, mkdirSync, readFileSync, rmSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { ensureFixtureApi, FIXTURE_PORT } from "./fixture-api.mjs";

const name = process.argv[2];
const STATES = { open: "open", soon: "soon", closed: "closed", populated: "open" };
if (!STATES[name]) {
  console.error("usage: node build-state.mjs <open|soon|closed|populated>");
  process.exit(2);
}

const here = fileURLToPath(new URL(".", import.meta.url));
const site = fileURLToPath(new URL("../../site/", import.meta.url));
const outDir = `${here}builds/${name}`;
const fixtures = [
  ["fixtures/content/trips/sisu-ski-fest.mdoc", "src/content/trips/sisu-ski-fest.mdoc"],
  ["fixtures/content/wax_entries/first-snow-wax.mdoc", "src/content/wax_entries/first-snow-wax.mdoc"],
];

const api = await ensureFixtureApi();
const placed = [];
if (name === "populated") {
  for (const [from, to] of fixtures) {
    cpSync(here + from, site + to);
    placed.push(site + to);
  }
}

const cleanup = () => {
  for (const f of placed) rmSync(f, { force: true });
  if (!api.external) api.close();
};
process.on("SIGINT", () => { cleanup(); process.exit(130); });

rmSync(outDir, { recursive: true, force: true });
mkdirSync(outDir, { recursive: true });

const build = spawn("npx", ["astro", "build", "--force", "--outDir", outDir], {
  cwd: site,
  stdio: "inherit",
  env: {
    ...process.env,
    TCSC_EDGE_CONFIG: "true", // production config: flat files, no trailing slash
    PUBLIC_SEASON_API_URL: `http://127.0.0.1:${FIXTURE_PORT}/season/${STATES[name]}`,
    PUBLIC_CONDITIONS_API_URL: `http://127.0.0.1:${FIXTURE_PORT}/conditions/live`,
  },
});

build.on("exit", (code) => {
  cleanup();
  if (code !== 0) process.exit(code ?? 1);
  const html = readFileSync(`${outDir}/index.html`, "utf8");
  const m = html.match(/data-season-source="(\w+)"/);
  if (!m || m[1] !== "api") {
    console.error(`build ${name}: data-season-source is ${m?.[1] ?? "missing"}, expected api`);
    process.exit(1);
  }
  const expectPages = name === "populated" ? ["trips.html", "wax-room/first-snow-wax.html"] : ["trips.html"];
  for (const p of expectPages) if (!existsSync(`${outDir}/${p}`)) { console.error(`missing ${p}`); process.exit(1); }
  console.log(`build ${name}: ok -> ${outDir}`);
});
build.on("error", (e) => { cleanup(); console.error(e); process.exit(1); });
```

- [ ] **Step 7: Build all four states**

```bash
cd /workspace/tcsc-trips/scripts/brand-review
for s in open soon closed populated; do node build-state.mjs $s || break; done
ls builds/*/index.html builds/populated/wax-room/ && git -C /workspace/tcsc-trips status --short site/src/content
```

Expected: four `build <name>: ok` lines, `builds/populated/wax-room/first-snow-wax.html` present, and `git status` prints nothing under `site/src/content` (the fixtures were removed). If `astro build` fails on the fixture frontmatter, the schema in `content.config.ts` has moved; fix the fixture, never the schema. If it fails with an image error, `hero_photo`/`photo` paths must be relative to `src/content/<collection>/`.

- [ ] **Step 8: Commit**

```bash
cd /workspace/tcsc-trips
git add scripts/brand-review/fixture-api.mjs scripts/brand-review/fixtures.test.mjs scripts/brand-review/fixtures scripts/brand-review/build-state.mjs
git commit -m "chore(brand-review): fixture api, content fixtures, per-state builds"
```

---

### Task 5: Dist server, state matrix, and screenshot script

**Files:**
- Create: `scripts/brand-review/serve-dist.mjs`
- Create: `scripts/brand-review/states.mjs`
- Create: `scripts/brand-review/screenshot.mjs`
- Create: `docs/superpowers/specs/2026-08-31-site-brand-review/state-matrix.md`

**Interfaces:**
- Consumes: `builds/<name>/` from Task 4; `getBrowser`, `BASE_URL` from Task 3; `conditionsPayload` from Task 4.
- Produces: `node serve-dist.mjs <build> [--port N] [--preview]` serves a build the way Render serves `format: 'file'` output. `STATES` array (`{ id, surface, state, build, url, conditions?, viewports?, clock?, actions? }`). `node screenshot.mjs <phase> [id...]` writes `docs/superpowers/specs/2026-08-31-site-brand-review/screens/<phase>/<surface>-<state>-<viewport>.png` and exits non-zero if any capture failed or any page reported `data-season-source` other than `api`.

- [ ] **Step 1: Write `serve-dist.mjs`**

```js
// usage: node serve-dist.mjs <build-name> [--port 4400] [--preview]
// Serves builds/<name>/ like Render serves a static site built with format 'file' and
// trailingSlash 'never': /about -> about.html, /wax-room/x -> wax-room/x.html, unknown -> 404.html (404).
// --preview: also satisfy ~/preview/proxy.cjs's liveness probe so preview.eaer.app can front it.
// The proxy pins to a project dir and reads <dir>/.superpowers/brainstorm/.last-port and .last-token,
// then probes GET /?key=<token> expecting 200 + Set-Cookie brainstorm-key-<port>=... . We play along.
import { createServer } from "node:http";
import { existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { randomBytes } from "node:crypto";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

const args = process.argv.slice(2);
const name = args[0];
const port = Number(args[args.indexOf("--port") + 1] || 0) || Number(process.env.PORT) || 4400;
const preview = args.includes("--preview");
const here = fileURLToPath(new URL(".", import.meta.url));
const root = join(here, "builds", name ?? "");
if (!name || !existsSync(join(root, "index.html"))) {
  console.error(`no build at ${root}; run: node build-state.mjs ${name ?? "<name>"}`);
  process.exit(2);
}

const MIME = {
  ".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "text/javascript", ".mjs": "text/javascript",
  ".json": "application/json", ".xml": "application/xml", ".txt": "text/plain", ".svg": "image/svg+xml",
  ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".avif": "image/avif",
  ".ico": "image/x-icon", ".woff2": "font/woff2", ".woff": "font/woff", ".mp3": "audio/mpeg",
};

const token = randomBytes(32).toString("hex");

function resolve(pathname) {
  let p = normalize(decodeURIComponent(pathname)).replace(/^(\.\.[/\\])+/, "");
  if (p.endsWith("/")) p = p.slice(0, -1);
  const candidates = p === "" || p === "/" ? ["index.html"] : [p, `${p}.html`, `${p}/index.html`];
  for (const c of candidates) {
    const f = join(root, c);
    if (existsSync(f) && statSync(f).isFile()) return { file: f, status: 200 };
  }
  return { file: join(root, "404.html"), status: 404 };
}

createServer((req, res) => {
  const { file, status } = resolve(new URL(req.url, "http://x").pathname);
  const headers = { "Content-Type": MIME[extname(file)] ?? "application/octet-stream", "Cache-Control": "no-store" };
  if (preview) headers["Set-Cookie"] = `brainstorm-key-${port}=${token}; Path=/; SameSite=Lax`;
  res.writeHead(status, headers);
  res.end(readFileSync(file));
}).listen(port, "127.0.0.1", () => {
  console.log(`serving builds/${name} on http://127.0.0.1:${port}`);
  if (preview) {
    const repo = fileURLToPath(new URL("../../", import.meta.url));
    const bs = join(repo, ".superpowers", "brainstorm");
    mkdirSync(bs, { recursive: true });
    writeFileSync(join(bs, ".last-port"), String(port));
    writeFileSync(join(bs, ".last-token"), token);
    console.log(`preview mode: pin the proxy with  echo ${repo.replace(/\/$/, "")} > ~/preview/target  then open https://preview.eaer.app/`);
  }
});
```

- [ ] **Step 2: Write `states.mjs`**

```js
// The state matrix as data. One entry per screenshot target.
//   build:      which builds/<name>/ to serve (open | soon | closed | populated)
//   conditions: how the browser's /conditions fetch is answered: live | dryland | unavailable (aborted)
//   clock:      ISO time to freeze the browser clock at (only for the winter "unavailable" strip)
//   viewports:  subset of mobile | desktop | tablet (default mobile + desktop)
//   actions:    { click: sel } | { waitFor: sel } | { scroll: y } | { wait: ms } | { hover: sel } | { press: key }
const OPEN = "open";

export const STATES = [
  // home, registration states (the CTA renders in nav, mobile panel, hero, and CTA strip)
  { id: "home-open", surface: "home", state: "open", build: "open", url: "/", conditions: "live" },
  { id: "home-soon", surface: "home", state: "soon", build: "soon", url: "/", conditions: "live" },
  { id: "home-closed", surface: "home", state: "closed", build: "closed", url: "/", conditions: "live" },
  // home, conditions strip states (registration open throughout)
  { id: "home-dryland", surface: "home", state: "dryland", build: OPEN, url: "/", conditions: "dryland" },
  { id: "home-unavailable", surface: "home", state: "unavailable", build: OPEN, url: "/", conditions: "unavailable",
    clock: "2027-01-15T18:00:00Z" }, // winter: an error payload renders "No report" instead of "Dryland season"
  { id: "home-conditions-expanded", surface: "home", state: "conditions-expanded", build: OPEN, url: "/", conditions: "live",
    actions: [{ click: "[data-location='wirth']" }, { wait: 400 }] },
  // home, content states
  { id: "home-wax-feed", surface: "home", state: "wax-feed", build: "populated", url: "/", conditions: "live",
    actions: [{ scroll: 99999 }, { wait: 300 }] },
  { id: "home-hero", surface: "home", state: "hero", build: OPEN, url: "/", conditions: "live",
    viewports: ["mobile", "tablet", "desktop"], actions: [{ wait: 600 }], viewportOnly: true },
  { id: "home-mobile-nav", surface: "home", state: "mobile-nav", build: OPEN, url: "/", conditions: "live",
    viewports: ["mobile"], actions: [{ click: "button[aria-label='Open menu']" }, { wait: 400 }], viewportOnly: true },
  { id: "home-lightbox", surface: "home", state: "lightbox", build: OPEN, url: "/", conditions: "live",
    actions: [{ click: "[data-photo-mosaic] button" }, { waitFor: "[data-lightbox]:not([hidden])" }, { wait: 400 }], viewportOnly: true },
  { id: "home-mosaic-hover", surface: "home", state: "mosaic-hover", build: OPEN, url: "/", conditions: "live",
    viewports: ["desktop"], actions: [{ hover: "[data-photo-mosaic] button" }, { wait: 300 }], viewportOnly: true },
  // inner pages
  { id: "about", surface: "about", state: "open", build: OPEN, url: "/about", conditions: "live" },
  { id: "about-closed", surface: "about", state: "closed", build: "closed", url: "/about", conditions: "live" },
  { id: "community", surface: "community", state: "default", build: OPEN, url: "/community", conditions: "live" },
  { id: "racing", surface: "racing", state: "default", build: OPEN, url: "/racing", conditions: "live" },
  { id: "dry-tri", surface: "dry-tri", state: "default", build: OPEN, url: "/dry-tri", conditions: "live" },
  { id: "extra-training", surface: "extra-training-fun", state: "default", build: OPEN, url: "/extra-training-fun", conditions: "live" },
  { id: "coaches", surface: "coaches", state: "default", build: OPEN, url: "/coaches", conditions: "live" },
  { id: "sponsors", surface: "sponsors", state: "default", build: OPEN, url: "/sponsors", conditions: "live" },
  { id: "trips-empty", surface: "trips", state: "empty", build: OPEN, url: "/trips", conditions: "live" },
  { id: "trips-populated", surface: "trips", state: "populated", build: "populated", url: "/trips", conditions: "live" },
  { id: "wax-room-empty", surface: "wax-room", state: "empty", build: OPEN, url: "/wax-room", conditions: "live" },
  { id: "wax-room-populated", surface: "wax-room", state: "populated", build: "populated", url: "/wax-room", conditions: "live" },
  { id: "wax-entry", surface: "wax-entry", state: "default", build: "populated", url: "/wax-room/first-snow-wax", conditions: "live" },
  { id: "not-found", surface: "404", state: "default", build: OPEN, url: "/this-does-not-exist", conditions: "live" },
];
```

Before relying on the selectors, confirm them: `grep -n 'data-location=' site/src/components/LiveConditions.astro`, `grep -n '<button' site/src/components/PhotoMosaic.astro`, `grep -n 'hidden' site/src/components/Lightbox.astro`. If the lightbox is shown by a class rather than the `hidden` attribute, change the `waitFor` to that class.

- [ ] **Step 3: Write `screenshot.mjs`**

```js
// usage: node screenshot.mjs <phase> [stateId...]
//   -> docs/superpowers/specs/2026-08-31-site-brand-review/screens/<phase>/<surface>-<state>-<viewport>.png
// Groups states by build, serves each build on PORT (default 4400) for the duration, answers the
// conditions fetch per state, asserts data-season-source="api", and writes one png per viewport.
import { spawn } from "node:child_process";
import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { STATES } from "./states.mjs";
import { getBrowser } from "./browser.mjs";
import { conditionsPayload, ensureFixtureApi } from "./fixture-api.mjs";

const VIEWPORTS = {
  mobile: { width: 390, height: 844 },
  tablet: { width: 768, height: 1024 },
  desktop: { width: 1440, height: 900 },
};
const [phase = "before", ...only] = process.argv.slice(2);
const port = Number(process.env.PORT) || 4400;
const base = `http://127.0.0.1:${port}`;
const here = fileURLToPath(new URL(".", import.meta.url));
const outDir = fileURLToPath(new URL(`../../docs/superpowers/specs/2026-08-31-site-brand-review/screens/${phase}/`, import.meta.url));
mkdirSync(outDir, { recursive: true });

const wanted = STATES.filter((s) => !only.length || only.includes(s.id));
const byBuild = Map.groupBy(wanted, (s) => s.build);
const api = await ensureFixtureApi();
const browser = await getBrowser();
const failures = [];

function serve(build) {
  const child = spawn("node", [`${here}serve-dist.mjs`, build, "--port", String(port)], { stdio: ["ignore", "pipe", "inherit"] });
  return new Promise((resolve, reject) => {
    child.stdout.on("data", (d) => { if (String(d).includes("serving")) resolve(child); });
    child.on("exit", (code) => reject(new Error(`serve-dist exited ${code} for ${build}; run build-state.mjs ${build}`)));
  });
}

for (const [build, states] of byBuild) {
  const server = await serve(build);
  try {
    for (const s of states) {
      for (const vp of s.viewports ?? ["mobile", "desktop"]) {
        const ctx = await browser.newContext({ viewport: VIEWPORTS[vp], deviceScaleFactor: 2, reducedMotion: "no-preference" });
        if (s.clock) { await ctx.clock.install({ time: new Date(s.clock) }); }
        await ctx.route("**/conditions/**", (route) =>
          s.conditions === "unavailable"
            ? route.abort()
            : route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(conditionsPayload(s.conditions ?? "live")) }),
        );
        const page = await ctx.newPage();
        const file = `${outDir}${s.surface}-${s.state}-${vp}.png`;
        try {
          await page.goto(base + s.url, { waitUntil: "networkidle", timeout: 30000 });
          const source = await page.getAttribute("body", "data-season-source");
          if (source !== "api") throw new Error(`data-season-source=${source}`);
          for (const a of s.actions ?? []) {
            if (a.click) await page.click(a.click);
            else if (a.hover) await page.hover(a.hover);
            else if (a.press) await page.keyboard.press(a.press);
            else if (a.waitFor) await page.waitForSelector(a.waitFor, { timeout: 15000 });
            else if (a.scroll !== undefined) await page.evaluate((y) => window.scrollTo(0, y), a.scroll);
            else if (a.wait) await page.waitForTimeout(a.wait);
          }
          await page.waitForTimeout(400); // let the 150ms hover and 200ms lightbox transitions settle
          await page.screenshot({ path: file, fullPage: !s.viewportOnly && !s.actions?.some((a) => a.scroll !== undefined) });
          console.log("ok", file.split("/").pop());
        } catch (e) {
          failures.push(`${s.id}/${vp}: ${e.message.split("\n")[0]}`);
          console.log("FAIL", s.id, vp, e.message.split("\n")[0]);
        } finally {
          await ctx.close();
        }
      }
    }
  } finally {
    server.kill();
  }
}

await browser.close();
if (!api.external) api.close();
if (failures.length) { console.error(`\n${failures.length} failures:\n${failures.join("\n")}`); process.exit(1); }
console.log(`\nall captures written to ${outDir}`);
```

Note on `ctx.clock.install`: Playwright's clock API exists since 1.45; it freezes `Date` for the page so `conditionsDisplayMode` sees January. `registrationFlip.ts` also reads the clock, so the `home-unavailable` capture may show a different registration state than the build baked; that is expected and documented in the matrix.

- [ ] **Step 4: Smoke the matrix on two states**

```bash
cd /workspace/tcsc-trips/scripts/brand-review
node screenshot.mjs smoke home-open wax-entry && ls ../../docs/superpowers/specs/2026-08-31-site-brand-review/screens/smoke/
```

Expected: four `ok` lines (two states x two viewports), files `home-open-mobile.png`, `home-open-desktop.png`, `wax-entry-default-mobile.png`, `wax-entry-default-desktop.png`. Open one with the Read tool and confirm the conditions strip shows temperatures (live fixture) and the hero CTA reads as the open-state label. Then `rm -r ../../docs/superpowers/specs/2026-08-31-site-brand-review/screens/smoke`.

- [ ] **Step 5: Write `state-matrix.md`**

```markdown
# state matrix

Every row is a screenshot target. Viewports: mobile 390x844, desktop 1440x900, both unless noted; the home hero adds tablet 768x1024. Filenames: `screens/<phase>/<surface>-<state>-<viewport>.png`.

## how states are produced

- Registration state is baked at build time from `PUBLIC_SEASON_API_URL`. `scripts/brand-review/build-state.mjs <open|soon|closed|populated>` builds the site once per state against the fixture api (`fixture-api.mjs`, port 4499, windows relative to now so `registrationFlip.ts` agrees in the browser). Every capture asserts `data-season-source="api"`; a `fallback` capture is a harness failure, not a finding.
- Conditions are fetched by the browser. `screenshot.mjs` answers the fetch per state: `live` (four venues with temps and wax bands, Birkie fever), `dryland` (error payload; in August the strip reads "Dryland season"), `unavailable` (fetch aborted with the browser clock frozen at 2027-01-15, so the strip reads "No report"; the registration CTA in that capture is whatever the frozen clock derives and is not a finding).
- `populated` is the open build plus `fixtures/content/trips/sisu-ski-fest.mdoc` and `fixtures/content/wax_entries/first-snow-wax.mdoc`, copied into `site/src/content/` for the build only. Production currently has no trips and no wax entries, so the `empty` states are what visitors see today.
- Serve a build locally: `node serve-dist.mjs <build> --port 4400`. Take one state: `node screenshot.mjs <phase> <id>`.

## rows

| id | surface | state | build | url | conditions | viewports | how |
|---|---|---|---|---|---|---|---|
| home-open | home | open | open | / | live | m, d | registration open: CTA in nav, hero, strip |
| home-soon | home | soon | soon | / | live | m, d | coming soon: dates line under the hero CTA |
| home-closed | home | closed | closed | / | live | m, d | closed: "How to register" |
| home-dryland | home | dryland | open | / | dryland | m, d | conditions strip off-season |
| home-unavailable | home | unavailable | open | / | aborted, clock 2027-01-15 | m, d | conditions strip "No report" |
| home-conditions-expanded | home | conditions-expanded | open | / | live | m, d | click the Wirth cell |
| home-wax-feed | home | wax-feed | populated | / | live | m, d | scrolled to the bottom; wax teaser visible |
| home-hero | home | hero | open | / | live | m, t, d | viewport only; hero at three widths (faces clear of text) |
| home-mobile-nav | home | mobile-nav | open | / | live | m | menu open |
| home-lightbox | home | lightbox | open | / | live | m, d | first mosaic photo opened |
| home-mosaic-hover | home | mosaic-hover | open | / | live | d | caption scrim on hover |
| about | about | open | open | /about | live | m, d | |
| about-closed | about | closed | closed | /about | live | m, d | seasons grid closed note |
| community | community | default | open | /community | live | m, d | |
| racing | racing | default | open | /racing | live | m, d | |
| dry-tri | dry-tri | default | open | /dry-tri | live | m, d | |
| extra-training | extra-training-fun | default | open | /extra-training-fun | live | m, d | |
| coaches | coaches | default | open | /coaches | live | m, d | |
| sponsors | sponsors | default | open | /sponsors | live | m, d | |
| trips-empty | trips | empty | open | /trips | live | m, d | production today |
| trips-populated | trips | populated | populated | /trips | live | m, d | one fixture trip |
| wax-room-empty | wax-room | empty | open | /wax-room | live | m, d | production today |
| wax-room-populated | wax-room | populated | populated | /wax-room | live | m, d | one fixture entry |
| wax-entry | wax-entry | default | populated | /wax-room/first-snow-wax | live | m, d | |
| not-found | 404 | default | open | /this-does-not-exist | live | m, d | |

## non-page surfaces

- OG image: `site/public/og/og-default.jpg` (the only one; every page uses it). Review the file directly.
- Shared components (read the code; they appear in the rows above): `Nav`, `MobileNavPanel`, `LiveConditions` (full on home, compact in the footer), `SectionBand` (navy / paper / paper-on-navy), `MissionPanel`, `SeasonsGrid` (navy on home, paper on about), `CTAStrip`, `Footer`, `HeroHome`, `HeroInner`, `PhotoMosaic`, `Lightbox`, `CoachEntry`, `SponsorWall`, `TripsTable`, `WaxRoomFeed`, `WaxEntry`.
```

- [ ] **Step 6: Commit**

```bash
cd /workspace/tcsc-trips
git add scripts/brand-review/serve-dist.mjs scripts/brand-review/states.mjs scripts/brand-review/screenshot.mjs docs/superpowers/specs/2026-08-31-site-brand-review/state-matrix.md
git commit -m "chore(brand-review): dist server, state matrix, screenshot script"
```

---

### Task 6: Before screenshots

**Files:**
- Create: `docs/superpowers/specs/2026-08-31-site-brand-review/screens/before/*.png`

- [ ] **Step 1: Capture everything**

```bash
cd /workspace/tcsc-trips/scripts/brand-review
node screenshot.mjs before 2>&1 | tail -15
ls ../../docs/superpowers/specs/2026-08-31-site-brand-review/screens/before | wc -l
```

Expected: `all captures written`, and a file count equal to the matrix's capture count, which is printed by `node -e "import('./states.mjs').then(m=>console.log(m.STATES.reduce((n,s)=>n+(s.viewports??['m','d']).length,0)))"` (47 for the matrix as written: 22 rows at two viewports, the hero at three, mobile-nav and mosaic-hover at one each). Any `FAIL` line: fix the selector or state and rerun just that id with `node screenshot.mjs before <id>`.

- [ ] **Step 2: Look at four of them**

Open with the Read tool: `home-open-desktop.png`, `home-hero-tablet.png`, `coaches-default-mobile.png`, `wax-entry-default-desktop.png`. Confirm: conditions strip shows four temperatures; the hero headline is legible; no "Dryland season" text in the live states; nothing cut off at the bottom of full-page captures.

- [ ] **Step 3: Commit**

```bash
cd /workspace/tcsc-trips
git add docs/superpowers/specs/2026-08-31-site-brand-review/screens/before
git commit -m "docs(brand-review): before screens"
```

---

### Task 7: Phase 1 prompts

**Files:**
- Create: `docs/superpowers/specs/2026-08-31-site-brand-review/prompts/lens-template.md`
- Create: `docs/superpowers/specs/2026-08-31-site-brand-review/prompts/lens-{typography,color,sections-spacing,copy,motion-imagery,components-slop}.md`
- Create: `docs/superpowers/specs/2026-08-31-site-brand-review/prompts/gestalt-{mobile,desktop}.md`
- Create: `docs/superpowers/specs/2026-08-31-site-brand-review/prompts/synthesis.md`

**Interfaces:**
- Produces: prompt files Task 8 passes verbatim to `Agent` calls. Lens prompts write `lens-<slug>.md`; gestalt writes `gestalt-<viewport>.md`; synthesis writes `ledger.md`, `contract-changes.md`, and `DESIGN.md`.

- [ ] **Step 1: Write `lens-template.md`**

```markdown
you are one of six lens reviewers in a brand consistency, elevation, and de-slop audit of twincitiesskiclub.org, the Twin Cities Ski Club marketing site (Astro + Tailwind, under /workspace/tcsc-trips/site). you are read-only: do not edit any file except your output file. do not run git commands that change state. do not start or stop docker containers.

## your lens
{{LENS_NAME}}: {{LENS_DESCRIPTION}}

## the brand (read all of these first, in this order)
- /workspace/tcsc-trips/DESIGN.md  (v1 contract; you may propose changes to it. its "Theme" section names the two scenes the site reads for; its "Banned" list is the de-slop baseline)
- /workspace/tcsc-trips/docs/superpowers/specs/2026-08-31-site-brand-review-design.md (the spec: "goal", "contract posture", "non-goals", "finding schema")
- /workspace/tcsc-trips/docs/superpowers/specs/2026-06-11-marketing-site-design-feedback-design.md and 2026-07-10-marketing-site-feedback-round-2-design.md (what was accepted and rejected in the last two rounds, and why; do not re-propose a rejected item without a new argument)
- /workspace/tcsc-trips/docs/superpowers/specs/2026-07-18-marketing-copy-refresh-design.md (the voice rules)

fixed identity (never propose changing these): the nine color tokens in site/tailwind.config.ts; Archivo Variable for body and PolySans BulkyWide for display; no serif, no mono; real consented club photos only; the Live Conditions strip.

## your rubric
{{RUBRIC_SKILLS}}
treat the skill as a method and a quality gate, not the brief. where it says to add a library, ignore that. where it says "louder", "massive", "cinematic", or "viewport-scale", translate to this brand: navy, mint, paper; quiet ledger language; hairline rules; near-zero motion. the reference set is Tracksmith and Patagonia (photography, voice, and color carry the warmth; the type stays a grotesque). not awwwards showcase sites.

## what to sweep
every row in /workspace/tcsc-trips/docs/superpowers/specs/2026-08-31-site-brand-review/state-matrix.md. screenshots are in /workspace/tcsc-trips/docs/superpowers/specs/2026-08-31-site-brand-review/screens/before/ (view them with the Read tool; both viewports, three for the hero). for each state, read the code that renders it too:
- pages: site/src/pages/*.astro, site/src/pages/trips/index.astro, site/src/pages/wax-room/*.astro
- layouts: site/src/layouts/BaseLayout.astro, InnerPageLayout.astro
- components: site/src/components/*.astro (all of them), and the two client scripts LiveConditions.client.ts, PhotoMosaic.client.ts (read-only context; they are sacred)
- tokens and global css: site/tailwind.config.ts, site/src/styles/global.css
- content and copy: site/src/content/** (pages/*.mdoc and *.yaml, coaches, photos, practice_seasons, sponsors, nav.yaml, site_meta.yaml), site/src/lib/registrationCopy.ts, site/src/lib/metaDescription.ts, site/src/components/heroFacts.ts
- og image: site/public/og/og-default.jpg

if you need to see a state live (hover, focus, motion), serve a build and drive the remote browser: from /workspace/tcsc-trips/scripts/brand-review run `node serve-dist.mjs open --port {{PORT}}` in the background (builds: open, soon, closed, populated), then write a small node script in a scratch directory that imports { getBrowser } from /workspace/tcsc-trips/scripts/brand-review/browser.mjs (run it with `node` from that directory so playwright-core resolves) and opens http://127.0.0.1:{{PORT}}/. the conditions fetch goes to http://127.0.0.1:4499/conditions/live (fixture api; start it with `node fixture-api.mjs` if it is not up). kill your server when done.

## three mandates, equal weight
1. consistency: where does this surface disagree with DESIGN.md, or with another surface? (kind: drift)
2. elevation: where would raising the standard make this something we'd put next to Tracksmith without flinching? (kind: elevation). be concrete. "more whitespace" is not a finding; "increase SectionBand's navy y-padding from py-20 to py-28 on desktop so the mission panel breathes (DESIGN.md: 96-144px on home)" is.
3. de-slop: where does this read as a template or AI default, or where does the code duplicate instead of reuse? (kind: slop). cite the skill rule that names the pattern. examples: identical padding on every band, `→` outside the home hero CTA, a three-up grid, hover-lift on a non-interactive element, a class string copied across pages instead of a component prop, dead rules in global.css.

## output
write /workspace/tcsc-trips/docs/superpowers/specs/2026-08-31-site-brand-review/lens-{{LENS_SLUG}}.md:

1. `# lens: {{LENS_NAME}}` and a five-line summary: the three biggest problems, the one biggest opportunity, and your overall read of this lens in one sentence.
2. `## findings`, one block per finding, using exactly this schema:

### {{LENS_PREFIX}}-<n>
- surface: <surface> / <state> / <mobile|tablet|desktop|all>
- kind: drift | elevation | slop
- severity: P1 | P2 | P3
- contract: <DESIGN.md clause, quoted, or "proposed: <new clause>">
- evidence: <file:line> and/or <screenshot filename>
- observation: <what is, one or two sentences>
- proposal: <what should be, concrete: token, value, copy, layout>
- workstream: foundations | copy | motion-components | sections

severity: P1 = a normal visitor sees it as broken or inconsistent, or it fails WCAG AA. P2 = a designer notices. P3 = polish.
workstreams: foundations owns global.css, tailwind.config.ts, type scale, spacing rhythm, dividers, contrast. copy owns strings in site/src/content and the copy helpers. motion-components owns transitions, keyframes, reduced-motion, component consolidation, class dedup, dead css. sections owns the structure of HeroHome, HeroInner, SectionBand, MissionPanel, SeasonsGrid, CTAStrip, Footer, PhotoMosaic, CoachEntry, SponsorWall, TripsTable, WaxRoomFeed, WaxEntry, LiveConditions.astro markup, and the pages.

3. `## proposed contract changes`: each DESIGN.md change you want, one per line, with the finding ids that need it. only the synthesis agent edits DESIGN.md; you propose.

aim for completeness over brevity: sweep every state, every viewport, and the og image. dedupe within your own file. write in lowercase, short sentences, no em dashes. when you finish, reply with only the five-line summary.
```

- [ ] **Step 2: Write the six lens prompts by filling the template**

Replace `{{LENS_NAME}}`, `{{LENS_SLUG}}`, `{{LENS_PREFIX}}`, `{{LENS_DESCRIPTION}}`, `{{RUBRIC_SKILLS}}`, `{{PORT}}`:

| slug | prefix | port | description | rubric |
|---|---|---|---|---|
| typography | TY | 4411 | every type role against the DESIGN.md scale table (display H1 home and inner, H2, H3, H4, lede, body, caption, numbered marker); display-cut (`font-display`) count per page, max 2-3; measure caps (62ch on paper, 56ch on navy, the `max-w-prose` tokens); the +0.05 line-height bonus for light type on navy; eyebrow / uppercase-tracked label count per page (max 2, only when informative); heading hierarchy per route (one H1, no skipped levels); font-size values set outside the scale | /workspace/tcsc-trips/.agents/skills/visual-redesign/SKILL.md (its typography layer and slop classification) |
| color | CO | 4412 | token use vs raw values (grep site/src for `#[0-9a-fA-F]{3,8}\b`, `rgb(`, `oklch(` outside tailwind.config.ts and global.css); WCAG AA on every real text/background pairing (compute ratios from the OKLCH values in tailwind.config.ts; `text-paper/75` on navy, `text-slate` on paper-card, `mint-deep` links, coral indicators); coral count per page (max 4); mint used directly on paper (banned); navy/paper register discipline per route (home drenched, inner paper); focus-ring color per surface (`--focus-ring-color`); the og image's palette | /workspace/tcsc-trips/.agents/skills/visual-redesign/SKILL.md (its color layer) |
| sections-spacing | SP | 4413 | vertical rhythm variance (DESIGN.md requires 96-144px on home and 64-104px on inner, varied, not one value); the safe-inline gutters; asymmetric two-up splits (7/5 or 5/7, not 6/6); band sequencing per page and how bands meet (hairline rules, coral top border on CTAStrip); card-shape audit (none on home, no nested cards anywhere, no soft-gray card slabs on paper); hero composition for HeroHome at 390, 768, and 1440 (faces clear of the text block; scrim functional not decorative) and HeroInner on every inner page; footer column order vs nav order | /workspace/tcsc-trips/.agents/skills/awwwards-sections/SKILL.md (sequencing, spacing gates, anti-slop audit; ignore its pricing, bento, social-proof, and stats patterns), /workspace/tcsc-trips/.agents/skills/awwwards-hero/SKILL.md (HeroHome and HeroInner only; start from the current fold, which the july round judged the strongest screen on the site) |
| copy | CP | 4414 | voice per the july 18 copy refresh spec: plain register, concrete activities over values, direct verbs, at most one playful ski reference per surface, no slogan structures, no invented facts; no em dashes anywhere (commas, periods, middots instead); no exclamation points; sentence case (this brand is not lowercase); CTA labels in all three registration states across all four render sites (nav, mobile panel, hero, CTA strip) and the dates line; season card notes; meta descriptions (site/src/lib/metaDescription.ts, under 155 characters, no mid-thought truncation); alt text and captions in site/src/content/photos and coaches; 404 copy; footer and nav labels; the racing table's date labels; anything that repeats itself across pages | none. the rubric is /workspace/tcsc-trips/docs/superpowers/specs/2026-07-18-marketing-copy-refresh-design.md "voice rules" plus the accepted/rejected copy decisions in the two feedback specs |
| motion-imagery | MO | 4415 | every transition, keyframe, and hover in site/src (grep `transition`, `animate`, `duration-`, `@keyframes`, `group-hover`) against the DESIGN.md motion clause (hero entrance once per session; mosaic hover 150ms; lightbox 200ms scale-in; conditions 200ms flicker; no scroll reveals; transform and opacity only); prefers-reduced-motion behavior of each (global.css collapses everything; check nothing escapes); state changes that are abrupt today and would be better with a css-only transition (each of these is a contract-change proposal, because v1 forbids new motion); imagery: crop and `object-position` of every `object-cover` image at both viewports (open the source jpgs with the Read tool and compare with the screenshots; no cropped heads), image sizing and srcset via imageWidths.ts, the mosaic's size pattern, photo consent flags all true, the og image's composition and whether one default og image is enough | /workspace/tcsc-trips/.agents/skills/awwwards-motion/SKILL.md (audit method, css `linear()` easings, timing sheets, reduced-motion rules; ignore every Framer Motion, GSAP, and Lenis instruction), /workspace/tcsc-trips/.agents/skills/imagegen-frontend/SKILL.md (as a photo-treatment and composition rubric only; do not generate images) |
| components-slop | CS | 4416 | the sacred/slop classification from visual-redesign applied to every component and page: one-off markup where a component already exists (a hand-built band instead of SectionBand, a hand-built CTA instead of CTAStrip, a hand-built rule instead of the shared hairline); class strings duplicated across pages that should be a component prop or a global.css utility; per-page spacing utilities that differ for no reason; dead rules in global.css and unused props; `→` outside the home hero CTA; icons in CTAs or headings; any three-up equal grid; stat boxes; pill badges; drop shadows; border-radius that varies; hover-lift on non-interactive elements; anything on the DESIGN.md banned list; also the harness's tests under site/tests as evidence of what is contract-tested and what is not | /workspace/tcsc-trips/.agents/skills/visual-redesign/SKILL.md (sacred/slop classification, the 7-layer audit), /workspace/tcsc-trips/.agents/skills/awwwards-sections/SKILL.md (its anti-slop audit list) |

Save each as `prompts/lens-<slug>.md`.

- [ ] **Step 3: Write the two gestalt prompts**

```markdown
you are a gestalt reviewer for the {{VIEWPORT}} viewport in a brand consistency, elevation, and de-slop audit of twincitiesskiclub.org, the Twin Cities Ski Club marketing site. you judge feel, not tokens. you are read-only: do not edit any file except your output file. do not run git commands that change state. do not start or stop docker containers.

read first: /workspace/tcsc-trips/DESIGN.md (especially "Theme": the two scenes, a prospective member on a tuesday evening at a kitchen table and a sponsor on a 27-inch monitor the next morning; and "Banned"), the spec /workspace/tcsc-trips/docs/superpowers/specs/2026-08-31-site-brand-review-design.md, and the two feedback specs /workspace/tcsc-trips/docs/superpowers/specs/2026-06-11-marketing-site-design-feedback-design.md and 2026-07-10-marketing-site-feedback-round-2-design.md (they record what a developer friend of the club said, what was accepted, and what was rejected as off-language).

walk every state in /workspace/tcsc-trips/docs/superpowers/specs/2026-08-31-site-brand-review/state-matrix.md using the {{VIEWPORT}} screenshots in /workspace/tcsc-trips/docs/superpowers/specs/2026-08-31-site-brand-review/screens/before/ (Read tool, files ending -{{VIEWPORT}}.png; the hero also has -tablet.png). look at the og image site/public/og/og-default.jpg. to feel motion, hover, and scroll, open states live: from /workspace/tcsc-trips/scripts/brand-review run `node serve-dist.mjs open --port {{PORT}}` in the background (builds: open, soon, closed, populated), then write a small node script in a scratch directory that imports { getBrowser } from /workspace/tcsc-trips/scripts/brand-review/browser.mjs, run it with `node` from that directory, viewport {{VIEWPORT_SIZE}}. the conditions fetch goes to http://127.0.0.1:4499/conditions/live (start `node fixture-api.mjs` if it is not up). kill your server when done.

for each surface answer, in order:
1. what does this state feel like in one sentence, honestly?
2. does it feel like the same brand as the previous surface you looked at? if not, what specifically breaks the thread?
3. what is the single change that would make this one we'd put next to Tracksmith or Patagonia without flinching?
4. where are the rough edges: anything that looks unfinished, default, template-like, or accidental.

state a verdict on the home fold explicitly: keep as is, keep with these changes, or rework. the july round judged it the strongest screen on the site; say whether you agree.

then write /workspace/tcsc-trips/docs/superpowers/specs/2026-08-31-site-brand-review/gestalt-{{VIEWPORT}}.md:
- `# gestalt: {{VIEWPORT}}`, a ten-line summary: the site's current feel in two sentences; the three surfaces furthest from the brand; the three best-executed surfaces (we protect these); the one systemic change that would lift everything; the home fold verdict.
- `## per surface`: your four answers per surface.
- `## findings`: one block per finding, using exactly this schema:

### G{{VIEWPORT_LETTER}}-<n>
- surface: <surface> / <state> / <mobile|tablet|desktop|all>
- kind: drift | elevation | slop
- severity: P1 | P2 | P3
- contract: <DESIGN.md clause, quoted, or "proposed: <new clause>">
- evidence: <file:line> and/or <screenshot filename>
- observation: <what is, one or two sentences>
- proposal: <what should be, concrete: token, value, copy, layout>
- workstream: foundations | copy | motion-components | sections

most of yours will be kind: elevation. be concrete in proposals; name tokens, values, copy. severity: P1 = a normal visitor sees it as broken or inconsistent; P2 = a designer notices; P3 = polish. workstreams: foundations (tokens, type scale, spacing, contrast), copy (strings), motion-components (transitions, component consolidation, dead css), sections (structure of components and pages).
- `## proposed contract changes`: one per line, with finding ids.

lowercase, short sentences, no em dashes. when you finish, reply with only the ten-line summary.
```

Save as `prompts/gestalt-mobile.md` (`{{VIEWPORT}}` = `mobile`, `{{VIEWPORT_SIZE}}` = `390x844`, `{{VIEWPORT_LETTER}}` = `M`, `{{PORT}}` = `4417`) and `prompts/gestalt-desktop.md` (`desktop`, `1440x900`, `D`, `4418`).

- [ ] **Step 4: Write `synthesis.md`**

```markdown
you are the synthesis agent for a brand consistency, elevation, and de-slop audit of twincitiesskiclub.org. eight reviewers have written findings. you merge them, write the ledger, and rewrite DESIGN.md as the v2 contract. you may write only these three files:
- /workspace/tcsc-trips/docs/superpowers/specs/2026-08-31-site-brand-review/ledger.md
- /workspace/tcsc-trips/docs/superpowers/specs/2026-08-31-site-brand-review/contract-changes.md
- /workspace/tcsc-trips/DESIGN.md
do not run git commands that change state. do not start or stop servers or containers.

read, in order: /workspace/tcsc-trips/DESIGN.md (v1), the spec /workspace/tcsc-trips/docs/superpowers/specs/2026-08-31-site-brand-review-design.md (especially "contract posture": what is fixed and what is open), the two feedback specs (2026-06-11 and 2026-07-10 under docs/superpowers/specs/) and the copy refresh spec (2026-07-18), then all eight inputs in /workspace/tcsc-trips/docs/superpowers/specs/2026-08-31-site-brand-review/: lens-typography.md, lens-color.md, lens-sections-spacing.md, lens-copy.md, lens-motion-imagery.md, lens-components-slop.md, gestalt-mobile.md, gestalt-desktop.md. look at screens/before/ (Read tool) when a finding is ambiguous.

## ledger.md
- one block per merged finding. merge when surface + observation are the same thing; keep every source id in `sources`.
- schema: the finding schema from the spec plus `id: L-<nnn>` (zero-padded, sequential), `sources: [<ids>]`, `status: open`. block shape:

### L-<nnn>
- sources: [TY-3, GD-7]
- surface: <surface> / <state> / <mobile|tablet|desktop|all>
- kind: drift | elevation | slop
- severity: P1 | P2 | P3
- contract: <DESIGN.md v2 clause, quoted>
- evidence: <file:line> and/or <screenshot filename>
- observation: <what is>
- proposal: <what should be, concrete>
- workstream: foundations | copy | motion-components | sections
- status: open

- exactly one workstream per row. if a finding needs two, split it into two rows and cross-reference. ownership: foundations owns site/src/styles/global.css, site/tailwind.config.ts, type scale, spacing rhythm, dividers, contrast. copy owns strings under site/src/content and in registrationCopy.ts, metaDescription.ts, heroFacts.ts. motion-components owns transitions, keyframes, reduced-motion, component consolidation, class dedup, dead css. sections owns the structure of HeroHome, HeroInner, SectionBand, MissionPanel, SeasonsGrid, CTAStrip, Footer, PhotoMosaic, CoachEntry, SponsorWall, TripsTable, WaxRoomFeed, WaxEntry, LiveConditions.astro markup, and site/src/pages.
- order: P1 first, then P2, then P3; within a severity, group by workstream.
- when two reviewers disagree, decide using DESIGN.md's "Theme" (the two scenes) and the july round's stated posture (quiet ledger language, hairline rules, near-zero motion) and say which decided it in the observation.
- a row that touches a sacred file (registrationState.ts, registrationFlip.ts, seasonData.ts, seasonSlug.ts, pageScrollLock.ts, samePageAnchor.ts, conditionsDisplayMode.ts, registrationCta.ts, LiveConditions.client.ts, PhotoMosaic.client.ts) or content.config.ts goes under `## rejected` with reason `sacred`, unless the proposal can be met at the call site; then rewrite the proposal that way.
- a row that proposes changing a fixed identity item (the nine tokens, the two fonts, real photos only, the conditions strip) goes under `## rejected` with reason `fixed identity`.
- drop nothing silently. any other rejection goes under `## rejected` with the reason.
- start the file with `## summary`: count by severity, by kind, and by workstream, and the five rows you'd fix first if only five could be fixed.

## DESIGN.md (v2)
rewrite the whole file as the contract for the site we want. keep its section structure (Theme, Color, Typography, Layout, Components, the signature device, Motion, Iconography, Imagery, Banned, Accessibility) so readers of v1 find their way. rules:
- fixed identity items stay verbatim: the token table values, the two font families and the no-serif/no-mono rule, real consented photos only, the Live Conditions section.
- every other token, type role, spacing value, component spec, motion rule: state what it should be. where v1 is right, keep it. where the site is already better than v1, adopt the site. where a reviewer proposed a change and it serves the two scenes, adopt it and cite the finding id in the changelog.
- v1's Typography section still names Söhne and PolySans Median as choices; the site ships Archivo Variable and PolySans BulkyWide (tailwind.config.ts, global.css). describe what ships.
- the motion clause is open. if you admit any new motion, write the exact rule (what, duration, easing, reduced-motion behavior) and keep "no scroll reveals" unless a finding makes the case; the july round rejected a carousel on that clause.
- add clauses v1 lacks and the ledger needs: the og image, the 404 page, empty-state rules for trips and the wax room, the registration CTA copy per state and per render site, meta description length, a contrast floor (WCAG AA on every text pair), the de-slop rules the components-slop lens established (one component per pattern, no duplicated class strings, no dead css).
- every ledger row's `contract:` line must quote a clause that exists in your v2. if a row needs a clause, write the clause.
- end with `## changelog from v1`: one line per change, `- <what changed>: <why> (<finding ids>)`.

## contract-changes.md
the changelog as a checklist for rob: `- [ ] <change>: <why> (unlocks L-nnn, L-nnn)`. one line each. add a two-line note at the top explaining that striking a line rejects that change and its ledger rows move to `## rejected`.

lowercase, short sentences, no em dashes. when you finish, reply with only the `## summary` block of the ledger.
```

- [ ] **Step 5: Commit**

```bash
cd /workspace/tcsc-trips
git add docs/superpowers/specs/2026-08-31-site-brand-review/prompts
git commit -m "docs(brand-review): phase 1 agent prompts"
```

---

### Task 8: Run phase 1

**Files:**
- Create (by agents): `lens-*.md` x6, `gestalt-*.md` x2, `ledger.md`, `contract-changes.md`, `DESIGN.md` v2

- [ ] **Step 1: Confirm the inputs**

```bash
cd /workspace/tcsc-trips
ls scripts/brand-review/builds/ && ls docs/superpowers/specs/2026-08-31-site-brand-review/screens/before | wc -l
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:4499/season/open || (cd scripts/brand-review && nohup node fixture-api.mjs > /tmp/claude-1000/-workspace-tcsc-trips/01b754ce-3776-4a27-884c-aa04e26de682/scratchpad/fixture-api.log 2>&1 &)
docker ps --filter name=intimate-brand-browser --format '{{.Status}}'
```

Expected: four build dirs, the screenshot count from Task 6, `200` (or the fixture api starting), `Up ...`.

- [ ] **Step 2: Launch the eight review agents in one message**

Eight `Agent` calls in a single response, `subagent_type: "general-purpose"`, `model: "fable"`, `description` `lens: <slug>` / `gestalt: <viewport>`, `prompt` = the full contents of the matching prompt file. They run in the background; wait for all eight completion notifications. Do not read their reports; the files are the output.

- [ ] **Step 3: Check the outputs**

```bash
cd /workspace/tcsc-trips/docs/superpowers/specs/2026-08-31-site-brand-review
for f in lens-typography lens-color lens-sections-spacing lens-copy lens-motion-imagery lens-components-slop gestalt-mobile gestalt-desktop; do
  printf "%-24s %4s lines %3s findings\n" $f "$(wc -l < $f.md)" "$(grep -c '^### ' $f.md)"
done
git -C /workspace/tcsc-trips status --short | grep -v "2026-08-31-site-brand-review/"
pgrep -af serve-dist.mjs
```

Expected: eight files with findings; the `git status` line prints nothing (no agent edited outside the review dir); no stray `serve-dist` processes (kill any). If a file is missing or an agent edited elsewhere, `git checkout -- <file>` the stray edit and relaunch that one agent.

- [ ] **Step 4: Launch synthesis**

One `Agent` call, `model: "fable"`, prompt = `prompts/synthesis.md`. Wait for completion.

- [ ] **Step 5: Verify synthesis output**

```bash
cd /workspace/tcsc-trips
grep -c "^### L-" docs/superpowers/specs/2026-08-31-site-brand-review/ledger.md
grep -c "^- \[ \]" docs/superpowers/specs/2026-08-31-site-brand-review/contract-changes.md
grep -n "^## changelog from v1" DESIGN.md && grep -c "oklch(0.25 0.06 260)" DESIGN.md
grep -n "PolySansBulkyWide\|PolySans BulkyWide" DESIGN.md | head -2
git diff --stat
```

Expected: a ledger count; a checklist count; the changelog heading; the navy token still present (fixed identity kept); the display face named; `git diff --stat` shows only `DESIGN.md` modified plus new review files.

- [ ] **Step 6: Commit phase 1**

```bash
git add DESIGN.md docs/superpowers/specs/2026-08-31-site-brand-review
git commit -m "docs(brand-review): phase 1 audit, ledger, DESIGN.md v2 proposal"
```

---

### Task 9: Gate 1 (Rob)

- [ ] **Step 1: Present**

Tell Rob: the ledger counts by severity, kind, and workstream; the five "fix first" rows; the home fold verdicts from both gestalt agents; and the path to `contract-changes.md`. Ask him to strike any checklist line or ledger row he rejects, and to say "approved" when done.

- [ ] **Step 2: Apply strikes**

For each struck contract line: revert that clause in `DESIGN.md` to v1, delete it from the changelog, and move the ledger rows it unlocked to `## rejected` with reason `rob: struck at gate 1`. For each struck ledger row: same move. Commit as `docs(brand-review): apply gate 1 decisions`.

Nothing in Task 10 onward starts until Rob says approved.

---

### Task 10: Phase 2 prompts and launcher

**Files:**
- Create: `docs/superpowers/specs/2026-08-31-site-brand-review/prompts/codex-template.md`
- Create: `docs/superpowers/specs/2026-08-31-site-brand-review/prompts/codex-{foundations,copy,motion-components,sections}.md`
- Create: `scripts/brand-review/ledger-rows.sh`, `scripts/brand-review/run-codex.sh`, `scripts/brand-review/resume-codex.sh`

**Interfaces:**
- Consumes: `ledger.md`, `DESIGN.md` v2, `.agents/skills/*`, `screens/before/`.
- Produces: `bash scripts/brand-review/run-codex.sh <ws>` creates `.worktrees/brand-<ws>` on branch `brand/<ws>` from `site/brand-review`, launches Codex there in the background, logs to the scratchpad, records the session id. Each Codex run writes `docs/superpowers/specs/2026-08-31-site-brand-review/<ws>-report.md` and commits on its branch.

- [ ] **Step 1: Write `ledger-rows.sh`**

```bash
#!/bin/bash
# usage: bash scripts/brand-review/ledger-rows.sh <workstream>  -> prints the open ledger blocks for that workstream
ws=$1
awk -v ws="$ws" '
  /^## rejected/ {exit}
  /^### L-/ {if (blk && keep) printf "%s\n", blk; blk=$0 "\n"; keep=0; next}
  blk {blk=blk $0 "\n"; if ($0 ~ "^- workstream: " ws "$") keep=1}
  END {if (blk && keep) printf "%s\n", blk}
' "$(dirname "$0")/../../docs/superpowers/specs/2026-08-31-site-brand-review/ledger.md"
```

```bash
chmod +x scripts/brand-review/ledger-rows.sh
for ws in foundations copy motion-components sections; do printf "%-18s %s rows\n" $ws "$(bash scripts/brand-review/ledger-rows.sh $ws | grep -c '^### L-')"; done
```

Expected: four counts that sum to the number of non-rejected ledger rows.

- [ ] **Step 2: Write `codex-template.md`**

```markdown
you are implementing one workstream of a brand consistency, elevation, and de-slop pass on twincitiesskiclub.org, the Twin Cities Ski Club marketing site: Astro 7 static site + Tailwind 4 under site/ in this repo. you are working in a git worktree on branch brand/{{WORKSTREAM}}, branched from site/brand-review. commit on this branch; never merge, never push, never touch other branches, never touch main. do not stop or start docker containers.

## your workstream: {{WORKSTREAM}}
{{WORKSTREAM_DESCRIPTION}}

## the contract (read in full, first)
DESIGN.md at the repo root is the v2 contract. its "Theme" section names the two scenes the site reads for. docs/superpowers/specs/2026-07-18-marketing-copy-refresh-design.md holds the voice rules. every change you make must move the site toward these.

## your ledger rows
these are the only changes you may make. each row cites the contract clause it implements.

{{LEDGER_ROWS}}

## your method
{{SKILLS}}
read the whole skill file. run its pipeline: extract the target from the contract; gate (does the proposal serve the two scenes and the quiet register?); build; verify by screenshot; reject drift (anything in your diff that isn't a ledger row gets reverted). where the skill says to add a library, ignore it. where it says "louder", "massive", "cinematic", or "viewport-scale", translate to this brand: navy, mint, paper; hairline rules; near-zero motion.

## hard rules
- presentation only: astro component markup and classes, css in site/src/styles/global.css, tokens in site/tailwind.config.ts, copy strings under site/src/content and in the copy helpers. no js behavior changes. these files are sacred and must not be edited: site/src/lib/registrationState.ts, registrationFlip.ts, seasonData.ts, seasonSlug.ts, pageScrollLock.ts, samePageAnchor.ts, conditionsDisplayMode.ts, site/src/components/registrationCta.ts, LiveConditions.client.ts, PhotoMosaic.client.ts. also untouchable: site/src/content.config.ts, site/keystatic.config.ts, site/astro.config.mjs, render.yaml, anything outside site/ except your report and screenshots.
- no new dependencies. site/package.json and site/package-lock.json must be unchanged.
- every change cites a ledger id in its commit message. if you find something worth fixing that has no ledger id, do not fix it; add it to `## proposed` in your report.
- keep prefers-reduced-motion behavior: global.css collapses every animation and transition under the media query; do not add anything that escapes it.
- copy: no em dashes (use commas, periods, or middots), no exclamation points, sentence case, no invented facts. if a row's proposal contains an em dash, fix the proposal's punctuation, not the rule.
- no photo may be added, replaced, or generated. crop and object-position changes to existing photos are fine when a row asks.
- fixed identity: do not change the nine color token values, the two font families, or the Live Conditions strip's data or behavior.
- tests and build must pass from site/ before you report done: `npm run check`, `npm run build`, `npm run test:refinement`, `npm run test:sponsors`, `npm run test:fallback`. if a test asserts old copy or an old class that a ledger row changes, update the test and cite the row.
- do not edit anything under docs/superpowers/specs/2026-08-31-site-brand-review/ except your report and your after-screenshots.
- nothing fake under site/src/content: the harness copies fixtures in and out for you; if a build fails and leaves sisu-ski-fest.mdoc or first-snow-wax.mdoc behind, delete them before committing.

## verify by screenshot
the harness lives in scripts/brand-review (node_modules is linked into your worktree). the fixture api is shared on port 4499 (`curl -s http://127.0.0.1:4499/season/open | head -c 80`; if it is down, `nohup node fixture-api.mjs &` from that directory). to see your branch:
  cd scripts/brand-review
  node build-state.mjs open          # also: soon, closed, populated. rebuild after every change you want to see
  PORT={{PORT}} node screenshot.mjs after-{{WORKSTREAM}} <stateIds you touched>
state ids are in scripts/brand-review/states.mjs; the matrix is docs/superpowers/specs/2026-08-31-site-brand-review/state-matrix.md. your port is {{PORT}}; other workstreams use other ports, so never use 4400 to 4405 for anything else. compare each after image against screens/before/ with the same filename. look at them. if a change reads louder, busier, or more generic than before, it fails the gate: revert and try a quieter version. leave no serve-dist.mjs process running when done (`pkill -f "serve-dist.mjs .* --port {{PORT}}"`).

## report
write docs/superpowers/specs/2026-08-31-site-brand-review/{{WORKSTREAM}}-report.md:
- `# {{WORKSTREAM}} report`
- `## rows`: one line per ledger id: `L-nnn: fixed (<file:line>, <commit sha>)` or `L-nnn: skipped (<reason>)`.
- `## screens`: list of after screenshots you produced (they live in screens/after-{{WORKSTREAM}}/).
- `## proposed`: anything you noticed that has no ledger id.
- `## test/build`: paste the last line of each of the five commands.
commit the report on your branch as the last commit.

work through the rows in ledger order (P1 first). commit small and often: one commit per row or per tightly related group, message `brand({{WORKSTREAM}}): <what> (L-nnn)`.
```

- [ ] **Step 3: Write the four workstream prompts by filling the template**

| ws | port | description | skills |
|---|---|---|---|
| foundations | 4401 | tokens, the type scale and its utilities, tracking, weights, line-height, spacing rhythm, dividers, and contrast fixes. you own site/src/styles/global.css and site/tailwind.config.ts, and per-surface class fixes that only change a token, scale step, or spacing value. if a row needs a new shared utility, add it to global.css under `@layer utilities` and use it at every call site the row lists | /workspace/tcsc-trips/.agents/skills/visual-redesign/SKILL.md |
| copy | 4402 | every string on every surface: site/src/content/** (pages, coaches, photos alt and captions, practice_seasons, sponsors, nav.yaml, site_meta.yaml), site/src/lib/registrationCopy.ts strings, site/src/lib/metaDescription.ts, site/src/components/heroFacts.ts, the 404 page copy. you change words, not markup; if a row needs markup, report it as proposed for sections | none. the rubric is docs/superpowers/specs/2026-07-18-marketing-copy-refresh-design.md "voice rules" |
| motion-components | 4403 | timing, easing, reduced-motion, and the css-only micro-interactions the ledger approved; component consolidation (replace one-off markup with the existing component and, where a row asks, give the component the prop it needs); class dedup into props or global.css utilities; dead css and unused props removed. you own transitions and keyframes anywhere in site/src, and the internals of components when a row is about reuse | /workspace/tcsc-trips/.agents/skills/awwwards-motion/SKILL.md (css `linear()` easings, timing sheets, reduced-motion; ignore every Framer Motion, GSAP, and Lenis instruction), /workspace/tcsc-trips/.agents/skills/visual-redesign/SKILL.md (sacred/slop classification) |
| sections | 4404 | page and component structure: HeroHome, HeroInner, SectionBand, MissionPanel, SeasonsGrid, CTAStrip, Footer, PhotoMosaic, CoachEntry, SponsorWall, TripsTable, WaxRoomFeed, WaxEntry, LiveConditions.astro markup (not its client script), and site/src/pages/*.astro. the home fold was judged the strongest screen on the site; start from the current fold and change only what the ledger rows say. you start in parallel with the other workstreams but will be asked to rebase onto their merged result and retake screenshots before your final pass | /workspace/tcsc-trips/.agents/skills/awwwards-hero/SKILL.md (HeroHome, HeroInner), /workspace/tcsc-trips/.agents/skills/awwwards-sections/SKILL.md (everything below the hero; ignore pricing, bento, social-proof, stats patterns), /workspace/tcsc-trips/.agents/skills/visual-redesign/SKILL.md |

For each, fill `{{LEDGER_ROWS}}` with `bash scripts/brand-review/ledger-rows.sh <ws>` output. Save as `prompts/codex-<ws>.md`. If a prompt exceeds roughly 60k words, split its ledger rows into two prompts run sequentially in the same worktree (`resume-codex.sh` after the first finishes).

- [ ] **Step 4: Write `run-codex.sh` and `resume-codex.sh`**

`scripts/brand-review/run-codex.sh`:

```bash
#!/bin/bash
# usage: bash scripts/brand-review/run-codex.sh <workstream>
# creates .worktrees/brand-<ws> on branch brand/<ws> from site/brand-review and launches codex
# (gpt-5.6-sol, reasoning max) there in the background. prompt goes on stdin; a file argument does not work.
set -euo pipefail
ws=$1
root=$(cd "$(dirname "$0")/../.." && pwd)
wt=$root/.worktrees/brand-$ws
prompt=$root/docs/superpowers/specs/2026-08-31-site-brand-review/prompts/codex-$ws.md
logdir=${CODEX_LOG_DIR:-/tmp/claude-1000/-workspace-tcsc-trips/01b754ce-3776-4a27-884c-aa04e26de682/scratchpad}
log=$logdir/codex-$ws.log

[ -f "$prompt" ] || { echo "no prompt: $prompt"; exit 1; }
mkdir -p "$logdir"
cd "$root"
if [ ! -d "$wt" ]; then
  git worktree add -b "brand/$ws" "$wt" site/brand-review
fi
[ -e "$wt/site/node_modules" ] || ln -s "$root/site/node_modules" "$wt/site/node_modules"
[ -e "$wt/scripts/brand-review/node_modules" ] || ln -s "$root/scripts/brand-review/node_modules" "$wt/scripts/brand-review/node_modules"

echo "launching codex for $ws in $wt, log: $log"
nohup codex exec -C "$wt" -c model_reasoning_effort="max" - < "$prompt" > "$log" 2>&1 &
echo $! > "$log.pid"
echo "pid $(cat "$log.pid")"
# record the session id once codex prints it, for resume-codex.sh
( for i in $(seq 1 60); do sid=$(grep -m1 -oE 'session id: [0-9a-f-]+' "$log" | awk '{print $3}'); [ -n "$sid" ] && { echo "$ws $sid" >> "$logdir/codex-sessions.txt"; exit 0; }; sleep 5; done ) &
```

`scripts/brand-review/resume-codex.sh`:

```bash
#!/bin/bash
# usage: bash scripts/brand-review/resume-codex.sh <workstream> ["extra instruction"]
# resumes the codex session recorded in $logdir/codex-sessions.txt for that workstream, in its worktree.
set -euo pipefail
ws=$1
extra=${2:-}
root=$(cd "$(dirname "$0")/../.." && pwd)
wt=$root/.worktrees/brand-$ws
logdir=${CODEX_LOG_DIR:-/tmp/claude-1000/-workspace-tcsc-trips/01b754ce-3776-4a27-884c-aa04e26de682/scratchpad}
sid=$(awk -v ws="$ws" '$1==ws {print $2}' "$logdir/codex-sessions.txt" | tail -1)
[ -n "$sid" ] || { echo "no session id for $ws"; exit 1; }
log=$logdir/codex-$ws.log
msg="your session was interrupted and has been resumed. continue exactly where you left off. first run \`git status --short\` and \`git log --oneline site/brand-review..HEAD\` in your worktree to see what you already committed and what is still uncommitted; commit any clean uncommitted work with the ledger id it belongs to before continuing. then work through your remaining ledger rows, run the five test/build commands, take your after screenshots, write your report, and commit it. do not redo rows you already committed. $extra"
echo "resuming $ws session $sid in $wt, log: $log"
# -c must precede the resume subcommand; resume takes no -C, so cd into the worktree
(cd "$wt" && nohup codex exec -c model_reasoning_effort="max" resume "$sid" "$msg" >> "$log" 2>&1 &
echo $! > "$log.pid")
sleep 1
echo "pid $(cat "$log.pid")"
```

```bash
chmod +x scripts/brand-review/run-codex.sh scripts/brand-review/resume-codex.sh
bash -n scripts/brand-review/run-codex.sh && bash -n scripts/brand-review/resume-codex.sh && echo "syntax ok"
```

Expected: `syntax ok`. Codex 0.151 prints a header before the prompt echo that includes the line `session id: 01a057b2-287c-7e91-a706-0d019bf95bc4` (verified in the coffee logs on 2026-08-31); the `grep -oE 'session id: [0-9a-f-]+'` in `run-codex.sh` matches that line.

- [ ] **Step 5: Commit**

```bash
cd /workspace/tcsc-trips
git add scripts/brand-review/ledger-rows.sh scripts/brand-review/run-codex.sh scripts/brand-review/resume-codex.sh docs/superpowers/specs/2026-08-31-site-brand-review/prompts/codex-*.md
git commit -m "chore(brand-review): codex prompts, ledger extractor, launcher"
```

---

### Task 11: Run phase 2, merge, and stand up the previews

- [ ] **Step 1: Launch all four workstreams**

```bash
cd /workspace/tcsc-trips
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:4499/season/open || (cd scripts/brand-review && nohup node fixture-api.mjs > /tmp/claude-1000/-workspace-tcsc-trips/01b754ce-3776-4a27-884c-aa04e26de682/scratchpad/fixture-api.log 2>&1 &)
for ws in foundations copy motion-components sections; do bash scripts/brand-review/run-codex.sh $ws; done
```

Then set a `Monitor` on the four log files for `report.md` or process exit, with a `ScheduleWakeup` fallback of 1200s. Codex at max reasoning on a workstream can take an hour or more; do not poll faster than every 10 minutes.

- [ ] **Step 2: When a workstream exits, check it**

```bash
ws=foundations
cd /workspace/tcsc-trips/.worktrees/brand-$ws
git log --oneline site/brand-review..HEAD | head -30
git diff site/brand-review --stat | tail -3
git diff site/brand-review -- site/package.json site/package-lock.json | wc -l    # must be 0
git diff site/brand-review --name-only | grep -E "site/src/lib/(registrationState|registrationFlip|seasonData|seasonSlug|pageScrollLock|samePageAnchor|conditionsDisplayMode)\.ts|components/(registrationCta|LiveConditions\.client|PhotoMosaic\.client)\.ts|content\.config\.ts|keystatic\.config\.ts|astro\.config\.mjs|^render\.yaml|^app/" # must be empty
git diff site/brand-review --name-only | grep -E "site/src/content/(trips|wax_entries)/"   # must be empty (no fixtures committed)
git log --format=%s site/brand-review..HEAD | grep -v "L-[0-9]\{3\}" | grep -v "report"   # uncited commits, must be empty
test -f docs/superpowers/specs/2026-08-31-site-brand-review/$ws-report.md && sed -n 1,40p docs/superpowers/specs/2026-08-31-site-brand-review/$ws-report.md
```

If any forbidden grep prints, or package files changed: do not merge; `bash scripts/brand-review/resume-codex.sh $ws "revert the changes to <files>; they violate the presentation-only rule. then rerun the five test/build commands and update the report."`.

- [ ] **Step 3: Merge in order foundations → copy → motion-components**

```bash
cd /workspace/tcsc-trips && git checkout site/brand-review
for ws in foundations copy motion-components; do
  git merge --no-ff brand/$ws -m "merge brand/$ws"
  (cd site && npm run check 2>&1 | tail -2 && npm run build 2>&1 | tail -2 && npm run test:refinement 2>&1 | tail -3 && npm run test:sponsors 2>&1 | tail -3 && npm run test:fallback 2>&1 | tail -3)
done
```

Resolve `global.css` and `tailwind.config.ts` conflicts by hand: keep both sides' intent, prefer token and scale definitions from foundations and utilities/transitions from motion-components. All five commands must pass after each merge before the next.

- [ ] **Step 4: Rebase sections, final pass, merge**

```bash
cd /workspace/tcsc-trips/.worktrees/brand-sections && git rebase site/brand-review
```

Then `bash scripts/brand-review/resume-codex.sh sections "site/brand-review has merged the foundations, copy, and motion-components workstreams and your branch is rebased on it. re-check every row in your report against the new tokens and utilities, rebuild and retake your after screenshots, fix anything that regressed, rerun the five test/build commands, update the report, commit."`. When it exits, repeat Step 2's checks, then merge `brand/sections` into `site/brand-review` with the same test/build gate.

- [ ] **Step 5: Full after screenshots on the merged branch**

```bash
cd /workspace/tcsc-trips/scripts/brand-review
for s in open soon closed populated; do node build-state.mjs $s || break; done
node screenshot.mjs after 2>&1 | tail -5
cd /workspace/tcsc-trips
git add docs/superpowers/specs/2026-08-31-site-brand-review/screens/after docs/superpowers/specs/2026-08-31-site-brand-review/*-report.md
git commit -m "docs(brand-review): after screens and workstream reports"
```

- [ ] **Step 6: Push and open the draft PR for the Render preview**

```bash
git push -u origin site/brand-review
gh pr create --draft --base main --head site/brand-review --title "Marketing site brand review" --body "$(cat <<'EOF'
Brand consistency, elevation, and de-slop pass over twincitiesskiclub.org. Spec: docs/superpowers/specs/2026-08-31-site-brand-review-design.md. Ledger, DESIGN.md v2, before/after screens, and verification live under docs/superpowers/specs/2026-08-31-site-brand-review/.

Draft until gate 2. Merging deploys.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01QVWHyaQMoWGXv3VTKdXX4u
EOF
)"
sleep 120 && gh pr view --comments | grep -io "https://[a-z0-9.-]*onrender.com[^ )]*" | head -1
```

Expected: a Render preview URL in the PR comments within a few minutes (Render comments on the PR when the preview is live). If no comment appears after 10 minutes, check `mcp__render__list_deploys` for the service or the Render dashboard's Previews tab; if previews are not being generated, fall back to a second static service pinned to `site/brand-review` (`mcp__render__create_static_site` with `buildCommand: cd site && npm ci && npm run build`, `publishPath: site/dist`, `branch: site/brand-review`, the three env vars from `render.yaml`) and delete it after gate 2. Verify the preview reports `data-season-source="api"`: `curl -s <preview-url> | grep -o 'data-season-source="[a-z]*"'`.

- [ ] **Step 7: Container preview for fast iteration**

```bash
cd /workspace/tcsc-trips/scripts/brand-review
node build-state.mjs open
nohup node serve-dist.mjs open --port 4400 --preview > /tmp/claude-1000/-workspace-tcsc-trips/01b754ce-3776-4a27-884c-aa04e26de682/scratchpad/preview.log 2>&1 &
echo /workspace/tcsc-trips > ~/preview/target
~/preview/preview-up.sh
sleep 3 && curl -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:8790/about"
```

Expected: `200`. Hand Rob `https://preview.eaer.app/`. Note in the message that this build uses fixture registration data (the fixture api), while the Render preview uses live `tcsc.ski` data. When done: `rm ~/preview/target`, `pkill -f "serve-dist.mjs open --port 4400"`.

---

### Task 12: Phase 3 verification

**Files:**
- Create: `docs/superpowers/specs/2026-08-31-site-brand-review/prompts/verify-{a,b,gestalt}.md`
- Create (by agents): `verification.md`, `screens/verify/*.png`

- [ ] **Step 1: Write the adversarial verifier prompt (two copies)**

```markdown
you are an adversarial verifier. four implementation agents claim to have fixed brand findings on twincitiesskiclub.org, the Twin Cities Ski Club marketing site (Astro + Tailwind under /workspace/tcsc-trips/site). assume every claim is wrong until you prove it right. you are read-only except for your output file and your screenshots. do not run git commands that change state. do not stop or start docker containers.

read: /workspace/tcsc-trips/DESIGN.md (the v2 contract), the spec /workspace/tcsc-trips/docs/superpowers/specs/2026-08-31-site-brand-review-design.md, and /workspace/tcsc-trips/docs/superpowers/specs/2026-08-31-site-brand-review/ledger.md.

your workstreams: {{WORKSTREAMS}}. their reports: {{REPORT_FILES}} under /workspace/tcsc-trips/docs/superpowers/specs/2026-08-31-site-brand-review/.

for every row marked fixed in those reports:
1. read the diff for the cited commit (`git show <sha>`) and the current code at the cited file:line on site/brand-review (the checkout at /workspace/tcsc-trips is on that branch).
2. does the change satisfy the contract clause the ledger row cites? quote the clause.
3. take a fresh screenshot yourself, not the implementer's: from /workspace/tcsc-trips/scripts/brand-review, `node build-state.mjs <build>` once per build you need (open, soon, closed, populated; the merged branch is what builds), then `PORT=4405 node screenshot.mjs verify <stateId>` (state ids in states.mjs). compare screens/verify/<file> against screens/before/<file> and screens/after/<file> with the Read tool. is the visible result what the row proposed?
4. verdict: verified | not fixed | regressed (say what regressed: the fix broke something else, or made a surface louder, busier, or more generic).

also scan the full diff of your workstreams (`git log --oneline main..site/brand-review --grep "brand({{WS_GREP}})"` then `git show <sha> --stat` and the diffs) for rule violations: edits to the sacred files (site/src/lib/registrationState.ts, registrationFlip.ts, seasonData.ts, seasonSlug.ts, pageScrollLock.ts, samePageAnchor.ts, conditionsDisplayMode.ts, site/src/components/registrationCta.ts, LiveConditions.client.ts, PhotoMosaic.client.ts), content.config.ts, keystatic.config.ts, astro.config.mjs, render.yaml, anything under app/; site/package.json or package-lock.json changes; fixture files under site/src/content/trips or wax_entries; a raw color or font-size value outside tailwind.config.ts and global.css; an em dash or exclamation point in copy; a new photo; commits with no ledger id in the message. list every violation.

write your section into /workspace/tcsc-trips/docs/superpowers/specs/2026-08-31-site-brand-review/verification.md under `## verifier {{LETTER}}: {{WORKSTREAMS}}` (create the file if missing; append if it exists; never delete another verifier's section): a table `ledger id | claimed | verdict | evidence`, then `## violations ({{LETTER}})`, then `## rework ({{LETTER}})`: the exact rows and what the implementer must do, phrased as instructions the implementer can follow verbatim, each tagged with the owning workstream.

leave no serve-dist.mjs process running. lowercase, short sentences, no em dashes. when you finish, reply with only the counts: verified / not fixed / regressed / violations.
```

Copy A: `{{WORKSTREAMS}}` = `foundations, copy`, `{{REPORT_FILES}}` = `foundations-report.md, copy-report.md`, `{{WS_GREP}}` = `foundations\|copy`, letter `A`. Copy B: `motion-components, sections`, `motion-components-report.md, sections-report.md`, `motion-components\|sections`, letter `B`.

- [ ] **Step 2: Write the cross-page gestalt verifier prompt**

```markdown
you are the final cross-page reviewer for a brand consistency, elevation, and de-slop pass on twincitiesskiclub.org. one question: is it now one brand on every page, and is it better than before? you are read-only except for your output file. do not run git commands that change state. do not stop or start docker containers.

read /workspace/tcsc-trips/DESIGN.md (v2 contract; "Theme" names the two scenes), /workspace/tcsc-trips/docs/superpowers/specs/2026-08-31-site-brand-review/gestalt-mobile.md and gestalt-desktop.md (the before-verdicts). walk every state in /workspace/tcsc-trips/docs/superpowers/specs/2026-08-31-site-brand-review/state-matrix.md at both viewports using screens/before/ and screens/after/ side by side (Read tool). to feel motion, hover, and scroll, open states live: from /workspace/tcsc-trips/scripts/brand-review, `node serve-dist.mjs open --port 4405` in the background (the builds under builds/ are from the merged branch), and write a small node script in a scratch directory that imports { getBrowser } from /workspace/tcsc-trips/scripts/brand-review/browser.mjs, run with `node` from that directory. kill your server when done.

write `## cross-page verdict` into /workspace/tcsc-trips/docs/superpowers/specs/2026-08-31-site-brand-review/verification.md (append; never delete the verifiers' sections):
1. one brand? per surface, yes/no, and what still breaks the thread.
2. better? per surface, better / same / worse, one sentence why.
3. the home fold: keep / improved / regressed, with the specific evidence at 390, 768, and 1440.
4. the three surfaces that improved most, and the three that still have rough edges.
5. anything that got louder, busier, or more generic than before (this is the failure mode we're guarding against), and anything that still reads as template or AI default (the de-slop mandate).
6. `## rework (gestalt)`: rows and instructions, same format as the verifiers, each tagged with the owning workstream.
7. `## recommendation`: merge as is / merge after rework / do not merge, with reasons.

lowercase, short sentences, no em dashes. when you finish, reply with only the recommendation line and the counts of better / same / worse.
```

- [ ] **Step 3: Launch the three verifiers in one message**

Three `Agent` calls, `subagent_type: "general-purpose"`, `model: "fable"`, prompts from the files. Wait for all three.

- [ ] **Step 4: Rework loop (at most two rounds)**

For each `## rework` item, resume the owning Codex session: `bash scripts/brand-review/resume-codex.sh <ws> "<rework instructions verbatim>. rerun the five test/build commands, update your report, commit."`. Merge the branch again into `site/brand-review` (`git merge brand/<ws>`; sections rebases first), rebuild, retake `after` screenshots for the touched states (`node screenshot.mjs after <ids>`), push, and relaunch only the verifier that owns those rows with the same prompt plus "re-verify only: <ids>". Stop after two rounds; anything still open is listed in `verification.md` under `## deferred` with the reason.

- [ ] **Step 5: Final checks and commit**

```bash
cd /workspace/tcsc-trips && git checkout site/brand-review
(cd site && npm run check 2>&1 | tail -1 && npm run build 2>&1 | tail -1 && npm run test:refinement 2>&1 | tail -2 && npm run test:sponsors 2>&1 | tail -2 && npm run test:fallback 2>&1 | tail -2)
git diff main -- site/package.json site/package-lock.json | wc -l                       # 0
git diff main --name-only | grep -E "^app/|^render\.yaml|content\.config|keystatic\.config|astro\.config" # empty
ls site/src/content/trips site/src/content/wax_entries                                     # only .gitkeep
# success criterion: no raw colors or ad-hoc sizes outside the token files
grep -rnE "#[0-9a-fA-F]{3,8}\b|rgb\(|oklch\(" site/src --include='*.astro' --include='*.ts' | grep -v "site/src/styles/global.css" || echo "no raw colors in components"
grep -rnE "text-\[[0-9.]+(px|rem)\]|\[font-size:" site/src --include='*.astro' || echo "no ad-hoc font sizes"
grep -rn "—" site/src/content site/src/lib/registrationCopy.ts site/src/lib/metaDescription.ts site/src/components/heroFacts.ts || echo "no em dashes"
git add docs/superpowers/specs/2026-08-31-site-brand-review
git commit -m "docs(brand-review): verification" && git push
```

Expected: all five commands pass; `0`; empty; `.gitkeep` only; the three `no ...` lines (anything else is a ledger row for the next round or a deferred item with a reason).

---

### Task 13: Gate 2 (Rob) and cleanup

- [ ] **Step 1: Present**

Give Rob: the `## recommendation`, the per-surface better/same/worse table, the home fold verdict, the count of verified vs deferred rows, the Render preview URL from the PR, and the paths to `screens/before/` and `screens/after/`. Offer a side-by-side artifact page of before/after pairs if he wants to review visually rather than by file (load the `artifact-design` skill first if he says yes). Mark the PR ready for review only when he says so; merging it is the deploy and is his call.

- [ ] **Step 2: On approval, tidy**

```bash
cd /workspace/tcsc-trips
for ws in foundations copy motion-components sections; do git worktree remove --force .worktrees/brand-$ws; done
git branch -d brand/foundations brand/copy brand/motion-components brand/sections
pkill -f "serve-dist.mjs" ; pkill -f "fixture-api.mjs"
rm -f ~/preview/target
rm -rf scripts/brand-review/builds
```

If the branch-pinned fallback static service was created in Task 11, delete it on Render after the merge. Deploy is Rob's merge of the PR and is not part of this plan.
