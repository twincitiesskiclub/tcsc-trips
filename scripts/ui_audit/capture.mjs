// scripts/ui_audit/capture.mjs
// Usage: NODE_PATH=$(npm root -g) node scripts/ui_audit/capture.mjs <label> <serverJson>
//
// <label> names the output directory (e.g. "before", "after-members").
// <serverJson> is the JSON line printed by scripts/ui_audit/serve.py.
//
// Environment:
//   TCSC_UI_AUDIT_ONLY  comma-separated list of surface names and/or group
//                       names. When set, only matching surfaces are captured
//                       and only their PNGs are replaced; every other entry in
//                       an existing index.json is carried forward untouched.
//                       Tasks 9-13 each re-shoot one group after their CSS
//                       fixes, and a full run is ~11 minutes.
//
// Prefer driving this through scripts/ui_audit/run.sh, which also builds
// Tailwind, stages the browser's shared libraries, and starts/stops the server.

import { createRequire } from 'node:module';
import { mkdir, writeFile, readFile, readdir, rm } from 'node:fs/promises';
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

// ---------------------------------------------------------------------------
// Framing rules
// ---------------------------------------------------------------------------

// Three surfaces are uniform lists at production volume -- users-list is 55,862
// CSS px tall on mobile -- and everything past the cap on them really is the
// same row repeating. Those three carry `longList: true` in surfaces.mjs and
// are the ONLY surfaces allowed to lose content to a cap.
const LONG_LIST_CAP_CSS_PX = 6000;

// Every other surface is captured whole. This is a runaway guard, not a framing
// rule: the tallest non-long-list surface measured is practices-detail at 6,976
// CSS px on mobile, so nothing reaches it today. If a surface ever does, the run
// says so loudly and exits non-zero rather than quietly shipping a clipped base
// shot -- which is exactly how practices-detail lost its Status & Skipper, RSVPs
// and Lead Confirmations cards under the previous flat 6000px cap.
const SAFETY_CAP_CSS_PX = 12000;

// State shots are viewport-sized and anchored on the control that was clicked.
// Full-page framing actively loses the thing a state exists to show: drawers and
// modals are position:fixed, so in a full-page shot they render wherever the page
// happened to be scrolled -- the payments drawer landed 21,000px down a 36,000px
// image. Anchoring on the opener keeps both the control and the UI it revealed
// in frame, for fixed overlays and for in-flow reveals deep in a long page alike.
const STATE_ANCHOR_OFFSET_CSS_PX = 120;

// A one-viewport frame is not enough for the densest overlays: the users-list
// member drawer scrolls internally and ended at "No roles assigned", losing the
// roles block and the Assign-roles button entirely. Continuation shots page
// through the rest. Five covers every panel in this app and stops a
// pathological reveal from producing dozens of files.
//
// It doubles as the decision rule for in-flow reveals: chase one only if it can
// be finished inside this budget. Half of a 55,000px list re-render is not more
// reviewable than the top of it, just more files -- but a tab panel four
// screens tall is worth five frames, and a flagged-but-missing panel cannot be
// audited at all.
const MAX_CONTINUATION_SHOTS = 5;

// A reveal has to be a real chunk of UI, not a tooltip, before it is worth
// chasing across continuation shots.
const REVEAL_MIN_AREA_RATIO = 0.12;
const REVEAL_MIN_WIDTH_CSS_PX = 200;
const REVEAL_MIN_HEIGHT_CSS_PX = 160;

// ---------------------------------------------------------------------------
// Surface subsetting
// ---------------------------------------------------------------------------

const only = (process.env.TCSC_UI_AUDIT_ONLY || '')
  .split(',')
  .map((s) => s.trim())
  .filter(Boolean);

const selected = only.length
  ? SURFACES.filter((s) => only.includes(s.name) || only.includes(s.group))
  : SURFACES;

if (only.length) {
  const unmatched = only.filter(
    (token) => !SURFACES.some((s) => s.name === token || s.group === token),
  );
  if (unmatched.length) {
    throw new Error(
      `TCSC_UI_AUDIT_ONLY matches no surface or group: ${unmatched.join(', ')}`,
    );
  }
  console.log(
    `TCSC_UI_AUDIT_ONLY=${only.join(',')} -> ${selected.length}/${SURFACES.length} surfaces`,
  );
}

// A subset run must not leave last run's PNGs for the surfaces it is redoing --
// a manifest edit renames states, and triage works by browsing this directory.
// run.sh clears the whole label directory for a full run; here we clear only
// what this run will rewrite, and carry the rest of index.json forward.
const selectedNames = new Set(selected.map((s) => s.name));
let carried = [];
if (only.length) {
  const existing = await readdir(OUT).catch(() => []);
  for (const file of existing) {
    if (!file.endsWith('.png')) continue;
    if (selectedNames.has(file.split('--')[0])) {
      await rm(`${OUT}/${file}`, { force: true });
    }
  }
  const prior = await readFile(`${OUT}/index.json`, 'utf8')
    .then(JSON.parse)
    .catch(() => null);
  if (prior && Array.isArray(prior.captured)) {
    carried = prior.captured.filter((c) => !selectedNames.has(c.surface));
    console.log(`carrying ${carried.length} prior captures forward in index.json`);
  }
}

// ---------------------------------------------------------------------------
// In-page measurement helpers (stringified into the browser)
// ---------------------------------------------------------------------------

// Marks what is on screen *before* an opener is clicked, so the element the
// click revealed can be identified afterwards by elimination. Two passes: read
// every visibility first, then write, so the attribute writes cannot interleave
// with layout reads.
const TAG_PRE_STATE = () => {
  const els = Array.from(document.querySelectorAll('body *'));
  const visible = els.map((el) => {
    const cs = getComputedStyle(el);
    return (
      cs.display !== 'none' &&
      cs.visibility !== 'hidden' &&
      Number(cs.opacity) !== 0 &&
      el.getClientRects().length > 0
    );
  });
  els.forEach((el, i) => el.setAttribute('data-uia-pre', visible[i] ? '1' : '0'));
};

// Finds the largest thing the click revealed and reports whether the current
// frame actually contains it. Tags the winner (and its internal scroller, if
// any) so the driver can scroll them without re-running the search.
const MEASURE_REVEAL = (limits) => {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const minArea = vw * vh * limits.areaRatio;

  let best = null;
  for (const el of document.querySelectorAll('body *')) {
    if (el.getAttribute('data-uia-pre') === '1') continue; // already on screen
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    if (Number(cs.opacity) === 0) continue;
    if (!el.getClientRects().length) continue;
    const r = el.getBoundingClientRect();
    if (r.width < limits.minWidth || r.height < limits.minHeight) continue;
    const area = r.width * r.height;
    if (area < minArea) continue;
    const positioned =
      cs.position === 'fixed' || cs.position === 'absolute' || cs.position === 'sticky';
    const z = Number.parseInt(cs.zIndex, 10) || 0;
    // Prefer a positioned overlay over in-flow content, a higher stacking
    // context over a lower one, and the bigger box over the smaller one. That
    // picks the drawer root rather than its inner body or a nested list.
    const score = (positioned ? 1e12 : 0) + z * 1e6 + area;
    if (!best || score > best.score) best = { el, score, cs, r };
  }

  document
    .querySelectorAll('[data-uia-reveal], [data-uia-scroller]')
    .forEach((el) => {
      el.removeAttribute('data-uia-reveal');
      el.removeAttribute('data-uia-scroller');
    });

  const doc = {
    scrollWidth: document.documentElement.scrollWidth,
    scrollHeight: document.documentElement.scrollHeight,
    scrollY: window.scrollY,
    innerHeight: vh,
    innerWidth: vw,
  };
  if (!best) return { found: false, doc };

  const root = best.el;
  root.setAttribute('data-uia-reveal', '1');

  // An overlay that scrolls internally cannot be reached by scrolling the page;
  // the tallest such box inside the reveal is the one holding its content.
  let scroller = null;
  for (const el of [root, ...root.querySelectorAll('*')]) {
    const cs = getComputedStyle(el);
    if (!['auto', 'scroll', 'overlay'].includes(cs.overflowY)) continue;
    if (el.scrollHeight - el.clientHeight <= 2) continue;
    if (!scroller || el.clientHeight > scroller.clientHeight) scroller = el;
  }
  if (scroller) scroller.setAttribute('data-uia-scroller', '1');

  // A reveal inside a fixed ancestor does not move when the window scrolls, so
  // window scrolling can never bring more of it into frame.
  let inFixed = false;
  for (let el = root; el; el = el.parentElement) {
    if (getComputedStyle(el).position === 'fixed') {
      inFixed = true;
      break;
    }
  }

  const r = root.getBoundingClientRect();
  return {
    found: true,
    doc,
    inFixed,
    describe: `${root.tagName.toLowerCase()}${root.id ? '#' + root.id : ''}${
      root.className && typeof root.className === 'string'
        ? '.' + root.className.trim().split(/\s+/).slice(0, 2).join('.')
        : ''
    }`,
    rect: { top: r.top, bottom: r.bottom, height: r.height, width: r.width },
    pageTop: r.top + window.scrollY,
    scroller: scroller
      ? {
          scrollHeight: scroller.scrollHeight,
          clientHeight: scroller.clientHeight,
        }
      : null,
  };
};

// ---------------------------------------------------------------------------

const browser = await chromium.launch();
const captured = [];

// Every problem worth reporting to the caller, so a run that "worked" but
// silently captured nothing useful cannot be mistaken for a clean one.
const problems = { blocked: [], skipped: [], failed: [], clipped: [] };

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

  for (const surface of selected) {
    // Writes one PNG and its index.json row. `extra` carries whatever the
    // caller already knows about this frame (part number, truncation, the
    // reveal it depicts).
    const write = async (stateName, options, meta) => {
      const file = `${surface.name}--${stateName}--${viewport.name}.png`;
      await page.screenshot({ ...options, path: `${OUT}/${file}` });
      captured.push({
        group: surface.group,
        surface: surface.name,
        state: stateName,
        viewport: viewport.name,
        file,
        ...meta,
      });
      const flags = [
        meta.truncated ? `TRUNCATED(${meta.truncatedReason})` : null,
        meta.overflowX ? `overflow-x ${meta.scrollWidth}px` : null,
      ].filter(Boolean);
      console.log(`  ${file}${flags.length ? '  [' + flags.join(', ') + ']' : ''}`);
      return file;
    };

    // Full page from the top. Capped only for the long lists; anything else
    // that hits a cap is a defect in this file's assumptions, not a framing
    // decision, and fails the run.
    const shootBase = async () => {
      await page.evaluate(() => window.scrollTo(0, 0));
      const doc = await page.evaluate(() => ({
        scrollHeight: document.documentElement.scrollHeight,
        // Horizontal overflow is a defect class this audit exists to find --
        // user-edit is 716 CSS px wide at a 390px viewport. Clipping to the
        // viewport width would crop the evidence out of the screenshot.
        scrollWidth: document.documentElement.scrollWidth,
      }));

      const cap = surface.longList ? LONG_LIST_CAP_CSS_PX : SAFETY_CAP_CSS_PX;
      const options = { fullPage: true };
      let truncated = false;
      let truncatedReason = null;
      if (doc.scrollHeight > cap) {
        truncated = true;
        truncatedReason = surface.longList ? 'long-list-cap' : 'safety-cap';
        options.clip = {
          x: 0,
          y: 0,
          width: Math.max(doc.scrollWidth, viewport.width),
          height: cap,
        };
      }

      if (truncated && !surface.longList) {
        const line =
          `${surface.name}--base--${viewport.name} hit the ${SAFETY_CAP_CSS_PX}px safety cap ` +
          `(document is ${doc.scrollHeight}px). This surface is not on the long-list ` +
          `allowlist, so the clipped region is NOT known to be repeating rows -- ` +
          `content below the cap is unreviewable. Either add longList: true to ` +
          `surfaces.mjs with a reason, or raise SAFETY_CAP_CSS_PX.`;
        console.warn(`  CLIPPED ${line}`);
        problems.clipped.push(line);
      }

      await write('base', options, {
        framing: 'full-page',
        truncated,
        truncatedReason,
        part: 1,
        parts: 1,
        docHeight: doc.scrollHeight,
        scrollWidth: doc.scrollWidth,
        viewportWidth: viewport.width,
        overflowX: doc.scrollWidth > viewport.width,
      });
    };

    // Viewport frame anchored on the opener, plus continuation shots when the
    // revealed overlay does not fit in one frame.
    const shootState = async (stateName, anchor) => {
      await anchor
        .evaluate((el, offset) => {
          const top = el.getBoundingClientRect().top + window.scrollY;
          window.scrollTo(0, Math.max(0, top - offset));
        }, STATE_ANCHOR_OFFSET_CSS_PX)
        .catch(() => {});
      await page.waitForTimeout(200);

      const reveal = await page.evaluate(MEASURE_REVEAL, {
        areaRatio: REVEAL_MIN_AREA_RATIO,
        minWidth: REVEAL_MIN_WIDTH_CSS_PX,
        minHeight: REVEAL_MIN_HEIGHT_CSS_PX,
      });
      const doc = reveal.doc;
      const common = {
        framing: 'viewport-anchored',
        docHeight: doc.scrollHeight,
        scrollWidth: doc.scrollWidth,
        viewportWidth: viewport.width,
        overflowX: doc.scrollWidth > viewport.width,
        reveal: reveal.found ? reveal.describe : null,
      };

      // How much of the reveal is missing from this frame, and can we get it?
      let mode = 'none';
      let remaining = 0;
      let step = doc.innerHeight;
      if (reveal.found && reveal.scroller) {
        mode = 'scroller';
        step = reveal.scroller.clientHeight;
        remaining = reveal.scroller.scrollHeight - reveal.scroller.clientHeight;
      } else if (reveal.found && reveal.rect.bottom > doc.innerHeight + 1) {
        remaining = reveal.rect.bottom - doc.innerHeight;
        if (reveal.inFixed) {
          // A fixed overlay taller than the viewport with no internal scroller
          // cannot be reached by scrolling anything. Nothing to do but say so.
          mode = 'unreachable';
        } else if (remaining > doc.innerHeight * MAX_CONTINUATION_SHOTS) {
          // A whole-list re-render (select mode redraws 266 rows, 54,000px of
          // them). Paging partway through it produces near-identical frames and
          // still does not finish, so record it as truncated and stop.
          mode = 'too-large';
        } else {
          mode = 'window';
        }
      }

      const wanted = step > 0 ? Math.ceil(remaining / step) : 0;
      const extras =
        mode === 'scroller' || mode === 'window'
          ? Math.min(wanted, MAX_CONTINUATION_SHOTS)
          : 0;
      const leftover = mode === 'none' ? 0 : remaining - extras * step;
      const parts = 1 + extras;

      const reasonFor = (isLast) => {
        if (!isLast || leftover <= 1) return null;
        if (mode === 'unreachable') return 'overlay-taller-than-viewport';
        if (mode === 'too-large') return 'reveal-spans-whole-page';
        return 'continuation-limit';
      };

      const baseTop = await page.evaluate(() => window.scrollY);
      for (let part = 1; part <= parts; part += 1) {
        if (part > 1) {
          if (mode === 'scroller') {
            await page.evaluate((offset) => {
              const s = document.querySelector('[data-uia-scroller]');
              if (s) s.scrollTop = offset;
            }, (part - 1) * step);
          } else {
            await page.evaluate((y) => window.scrollTo(0, y), baseTop + (part - 1) * step);
          }
          await page.waitForTimeout(250);
        }
        const isLast = part === parts;
        const reason = reasonFor(isLast);
        await write(
          part === 1 ? stateName : `${stateName}-part${part}`,
          {},
          {
            ...common,
            part,
            parts,
            continuation: mode,
            truncated: Boolean(reason),
            truncatedReason: reason,
          },
        );
      }

      if (leftover > 1) {
        console.warn(
          `  TRUNCATED ${surface.name}/${stateName}/${viewport.name}: ` +
            `${Math.round(leftover)}px of ${reveal.describe} still not captured (${mode})`,
        );
      }
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
      await shootBase();

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
          await page.evaluate(TAG_PRE_STATE);
          await target.click({ timeout: 5000 });
          await page.waitForTimeout(700);
          await shootState(state.name, target);
        } catch (err) {
          const line = `${surface.name}/${state.name} -> ${err.message}`;
          console.warn(`  SKIP ${line}`);
          problems.skipped.push(line);
        } finally {
          // Reload rather than press Escape. Escape closes a modal but leaves
          // tab selection, filter pills, expanded rows and appended editor rows
          // exactly as the previous state left them, so state N+1 would be shot
          // on top of state N. A reload is the only reset that holds for every
          // kind of opener in this manifest -- and it also clears the
          // data-uia-* bookkeeping attributes added above.
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

const all = [...carried, ...captured];
await writeFile(
  `${OUT}/index.json`,
  JSON.stringify(
    { label, only: only.length ? only : null, captured: all, problems },
    null,
    2,
  ),
);

console.log(`\n${captured.length} captures -> ${OUT}`);
if (carried.length) console.log(`${all.length} total rows in index.json (${carried.length} carried)`);
console.log(
  `BLOCKED ${problems.blocked.length}  SKIP ${problems.skipped.length}  ` +
    `FAIL ${problems.failed.length}  CLIPPED ${problems.clipped.length}`,
);
const stillTruncated = captured.filter((c) => c.truncated);
if (stillTruncated.length) {
  console.log(`\ntruncated captures (${stillTruncated.length}):`);
  for (const c of stillTruncated) console.log(`  ${c.file}  ${c.truncatedReason}`);
}
const overflowing = captured.filter((c) => c.overflowX);
if (overflowing.length) {
  console.log(`\nhorizontal overflow (${overflowing.length} captures):`);
  const seen = new Set();
  for (const c of overflowing) {
    const key = `${c.surface}--${c.viewport}`;
    if (seen.has(key)) continue;
    seen.add(key);
    console.log(`  ${key}: ${c.scrollWidth}px wide at a ${c.viewportWidth}px viewport`);
  }
}

// A clean run must produce no blocked mutation, no unmatched selector, no
// unreachable surface, and no base shot clipped outside the long-list
// allowlist. Exiting non-zero keeps run.sh from reporting success on a capture
// set that is quietly missing states or missing the bottom of a page.
if (
  problems.blocked.length ||
  problems.skipped.length ||
  problems.failed.length ||
  problems.clipped.length
) {
  process.exitCode = 1;
}
