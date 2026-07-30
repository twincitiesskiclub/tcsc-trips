import assert from 'node:assert/strict';
import { mkdtempSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { JSDOM } from 'jsdom';

// Astro names the bundle after the .astro file that declares the <script>
// (BaseLayout), not after registrationFlip.ts -- so find it by content.
//
// Astro also inlines a script directly into every page's HTML, deleting the
// dist/_astro/*.js file entirely, whenever the compiled chunk shares no
// imports with any other client script AND is under Vite's default
// assetsInlineLimit (4096 bytes) -- see shouldInlineScriptChunk in
// astro/dist/core/build/plugins/plugin-scripts.js. registrationFlip.ts is
// small and its only dependency (registrationState.ts) isn't imported by any
// other client script, so it reliably qualifies: there is no external file to
// find. Look in both places so this test keeps working whichever way Astro's
// optimizer packages it, without hardcoding on either outcome.
const distDir = new URL('../dist/_astro/', import.meta.url);
const bundleName = readdirSync(distDir).find(
  (f) =>
    f.endsWith('.js') &&
    readFileSync(new URL(f, distDir), 'utf8').includes('data-registration'),
);

let bundlePath;
if (bundleName) {
  bundlePath = new URL(bundleName, distDir);
} else {
  const html = readFileSync(new URL('../dist/index.html', import.meta.url), 'utf8');
  const { document: builtDoc } = new JSDOM(html).window;
  const inlineScript = Array.from(
    builtDoc.querySelectorAll('script[type="module"]'),
  ).find((el) => el.textContent.includes('data-registration'));
  assert.ok(inlineScript, 'a bundle containing the flip script should be built (external or inlined)');

  const tmpDir = mkdtempSync(join(tmpdir(), 'registration-flip-'));
  const tmpFile = join(tmpDir, 'inline-flip.mjs');
  writeFileSync(tmpFile, inlineScript.textContent);
  bundlePath = new URL(`file://${tmpFile}`);
}

const PAGE = `<!doctype html><html><body>
  <a data-registration
     data-state="coming_soon"
     data-returning-start="2026-08-28T17:00:00Z"
     data-returning-end="2026-09-02T05:00:00Z"
     data-new-start="2026-09-03T17:00:00Z"
     data-new-end="2026-09-20T05:00:00Z"
     data-open-label="Register for the season" data-open-url="https://tcsc.ski/"
     data-soon-label="Fall registration dates" data-soon-url="https://twincitiesskiclub.org/#registration"
     data-closed-label="How to register" data-closed-url="https://tcsc.ski/"
     href="https://twincitiesskiclub.org/#registration">Fall registration dates</a>
</body></html>`;

const PAGE_WITH_EMPTY_CLOSED_URL = `<!doctype html><html><body>
  <a data-registration
     data-state="coming_soon"
     data-returning-start="2026-08-28T17:00:00Z"
     data-returning-end="2026-09-02T05:00:00Z"
     data-new-start="2026-09-03T17:00:00Z"
     data-new-end="2026-09-20T05:00:00Z"
     data-open-label="Register for the season" data-open-url="https://tcsc.ski/"
     data-soon-label="Fall registration dates" data-soon-url="https://twincitiesskiclub.org/#registration"
     data-closed-label="How to register" data-closed-url=""
     href="https://twincitiesskiclub.org/#registration">Fall registration dates</a>
</body></html>`;

async function runFlipAt(isoNow, page = PAGE) {
  const dom = new JSDOM(page, { url: 'https://twincitiesskiclub.org/' });
  globalThis.window = dom.window;
  globalThis.document = dom.window.document;
  globalThis.Element = dom.window.Element;

  const realNow = Date.now;
  Date.now = () => Date.parse(isoNow);
  try {
    // Cache-bust so each run re-executes the side-effecting module.
    await import(`${bundlePath.href}?t=${encodeURIComponent(isoNow)}`);
  } finally {
    Date.now = realNow;
  }
  return dom.window.document.querySelector('[data-registration]');
}

test('leaves the DOM alone while the baked state is still correct', async () => {
  const cta = await runFlipAt('2026-07-30T12:00:00Z');
  assert.equal(cta.textContent, 'Fall registration dates');
  assert.equal(cta.getAttribute('href'), 'https://twincitiesskiclub.org/#registration');
});

test('flips to the open variant once registration has opened', async () => {
  const cta = await runFlipAt('2026-08-29T12:00:00Z');
  assert.equal(cta.textContent, 'Register for the season');
  assert.equal(cta.getAttribute('href'), 'https://tcsc.ski/');
  assert.equal(cta.getAttribute('data-state'), 'open');
});

test('flips to the closed variant once every window has passed', async () => {
  const cta = await runFlipAt('2026-10-01T12:00:00Z');
  assert.equal(cta.textContent, 'How to register');
  assert.equal(cta.getAttribute('href'), 'https://tcsc.ski/');
});

test('removes href when flipping to a closed variant with empty url', async () => {
  const cta = await runFlipAt('2026-10-01T14:00:00Z', PAGE_WITH_EMPTY_CLOSED_URL);
  assert.equal(cta.textContent, 'How to register');
  assert.equal(cta.hasAttribute('href'), false, 'href should be removed when closing to an empty url');
});
