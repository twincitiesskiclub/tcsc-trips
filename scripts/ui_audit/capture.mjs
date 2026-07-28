// scripts/ui_audit/capture.mjs
// Usage: NODE_PATH=$(npm root -g) node scripts/ui_audit/capture.mjs <label> <serverJson>
//
// <label> names the output directory (e.g. "before", "after-members").
// <serverJson> is the JSON line printed by scripts/ui_audit/serve.py.
//
// Prefer driving this through scripts/ui_audit/run.sh, which also builds
// Tailwind, stages the browser's shared libraries, and starts/stops the server.

import { createRequire } from 'node:module';
import { mkdir, writeFile } from 'node:fs/promises';
import { SURFACES, VIEWPORTS } from './surfaces.mjs';

// Playwright is a global npm install, not a dependency of this repo. ESM's
// bare-specifier resolution ignores NODE_PATH, so `import ... from 'playwright'`
// fails even with NODE_PATH set; CommonJS resolution still honours it. This is
// the one line that lets the global install work from inside an .mjs file.
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const label = process.argv[2];
if (!label) throw new Error('usage: capture.mjs <label> <serverJson>');
const server = JSON.parse(process.argv[3]);

const BASE = `http://127.0.0.1:${server.port}`;
const OUT = `.ui-audit/${label}`;
await mkdir(OUT, { recursive: true });

// Base shots are full-page but capped. Uncapped, the seeded lists produce
// screenshots up to 130,000px tall and 10MB each -- 475MB of images that no
// reviewer, human or model, can actually read. Everything past this cap on
// those pages is the same list row repeating, so the cap costs no information.
// It is applied identically to every capture run, so before/after stays
// comparable.
const BASE_SHOT_MAX_CSS_PX = 6000;

// State shots are viewport-sized and anchored on the control that was clicked.
// Full-page framing actively loses the thing a state exists to show: drawers and
// modals are position:fixed, so in a full-page shot they render wherever the page
// happened to be scrolled -- the payments drawer landed 21,000px down a 36,000px
// image. Anchoring on the opener keeps both the control and the UI it revealed
// in frame, for fixed overlays and for in-flow reveals deep in a long page alike.
const STATE_ANCHOR_OFFSET_CSS_PX = 120;

const browser = await chromium.launch();
const captured = [];

// Every problem worth reporting to the caller, so a run that "worked" but
// silently captured nothing useful cannot be mistaken for a clean one.
const problems = { blocked: [], skipped: [], failed: [] };

for (const viewport of VIEWPORTS) {
  const context = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height },
    deviceScaleFactor: 2,
  });

  // Backstop: a misfired click cannot produce a request that mutates anything.
  // The admin UI has controls that DM hundreds of real members and capture real
  // payments; the manifest is supposed to contain openers only, and this is what
  // makes a manifest mistake harmless as well as visible.
  await context.route('**/*', (route) => {
    const method = route.request().method();
    if (method === 'GET' || method === 'HEAD') return route.continue();
    const line = `${method} ${route.request().url()}`;
    console.warn(`  BLOCKED ${line}`);
    problems.blocked.push(line);
    return route.abort();
  });

  await context.addCookies([
    {
      name: server.cookie_name,
      value: server.cookie_value,
      domain: '127.0.0.1',
      path: '/',
    },
  ]);

  const page = await context.newPage();

  for (const surface of SURFACES) {
    // anchor === null  -> base shot: full page from the top, capped.
    // anchor === locator -> state shot: viewport framed on that control.
    const shoot = async (stateName, anchor = null) => {
      const file = `${surface.name}--${stateName}--${viewport.name}.png`;
      const options = { path: `${OUT}/${file}` };
      let truncated = false;

      if (anchor) {
        await anchor
          .evaluate((el, offset) => {
            const top = el.getBoundingClientRect().top + window.scrollY;
            window.scrollTo(0, Math.max(0, top - offset));
          }, STATE_ANCHOR_OFFSET_CSS_PX)
          .catch(() => {});
        await page.waitForTimeout(200);
      } else {
        await page.evaluate(() => window.scrollTo(0, 0));
        const height = await page.evaluate(
          () => document.documentElement.scrollHeight,
        );
        options.fullPage = true;
        if (height > BASE_SHOT_MAX_CSS_PX) {
          truncated = true;
          options.clip = {
            x: 0,
            y: 0,
            width: viewport.width,
            height: BASE_SHOT_MAX_CSS_PX,
          };
        }
      }

      await page.screenshot(options);
      captured.push({
        group: surface.group,
        surface: surface.name,
        state: stateName,
        viewport: viewport.name,
        file,
        framing: anchor ? 'viewport-anchored' : 'full-page',
        truncated,
      });
      console.log(`  ${file}${truncated ? ' (capped)' : ''}`);
    };

    try {
      const response = await page.goto(BASE + surface.path, {
        waitUntil: 'networkidle',
        timeout: 30000,
      });
      if (response && response.status() >= 400) {
        const line = `${surface.path} -> HTTP ${response.status()}`;
        console.warn(`  FAIL ${line}`);
        problems.failed.push(line);
        continue;
      }
      if (page.url().includes('/login')) {
        throw new Error(`session cookie rejected at ${surface.path}`);
      }
      await page.waitForTimeout(600);
      await shoot('base');

      for (const state of surface.states) {
        // Some UI only exists at some widths -- the mobile nav trigger sits
        // inside an `lg:hidden` header, so it is display:none at 1024px and up.
        // Without this gate every such state logs a no-match SKIP at the two
        // wider viewports, and real unmatched selectors would hide in the noise.
        if (state.viewports && !state.viewports.includes(viewport.name)) continue;

        try {
          // Some states need a prior click to reach (a tab, then a row inside
          // it). `click` is the opener; `pre` is any click needed to get there.
          for (const pre of state.pre || []) {
            const stepper = page.locator(pre).first();
            if ((await stepper.count()) === 0) {
              throw new Error(`no match for pre-step ${pre}`);
            }
            await stepper.click({ timeout: 5000 });
            await page.waitForTimeout(400);
          }

          const target = page.locator(state.click).first();
          if ((await target.count()) === 0) {
            const line = `${surface.name}/${state.name} -> no match for ${state.click}`;
            console.warn(`  SKIP ${line}`);
            problems.skipped.push(line);
            continue;
          }
          await target.click({ timeout: 5000 });
          await page.waitForTimeout(700);
          await shoot(state.name, target);
        } catch (err) {
          const line = `${surface.name}/${state.name} -> ${err.message}`;
          console.warn(`  SKIP ${line}`);
          problems.skipped.push(line);
        } finally {
          // Reload rather than press Escape. Escape closes a modal but leaves
          // tab selection, filter pills, expanded rows and appended editor rows
          // exactly as the previous state left them, so state N+1 would be shot
          // on top of state N. A reload is the only reset that holds for every
          // kind of opener in this manifest.
          try {
            await page.goto(BASE + surface.path, {
              waitUntil: 'networkidle',
              timeout: 30000,
            });
            await page.waitForTimeout(400);
          } catch {
            /* the next state's own goto will surface a genuine problem */
          }
        }
      }
    } catch (err) {
      const line = `${surface.path} -> ${err.message}`;
      console.warn(`  FAIL ${line}`);
      problems.failed.push(line);
    }
  }

  await context.close();
}

await browser.close();
await writeFile(
  `${OUT}/index.json`,
  JSON.stringify({ label, captured, problems }, null, 2),
);

console.log(`\n${captured.length} captures -> ${OUT}`);
console.log(
  `BLOCKED ${problems.blocked.length}  SKIP ${problems.skipped.length}  FAIL ${problems.failed.length}`,
);

// A clean run must produce no blocked mutation, no unmatched selector, and no
// unreachable surface. Exiting non-zero keeps run.sh from reporting success on
// a capture set that is quietly missing states.
if (problems.blocked.length || problems.skipped.length || problems.failed.length) {
  process.exitCode = 1;
}
