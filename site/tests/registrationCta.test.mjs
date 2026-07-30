import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { JSDOM } from 'jsdom';

import { isSamePageAnchor } from '../src/lib/samePageAnchor.ts';

const HOME = 'https://twincitiesskiclub.org/';

// Same bundle-locating strategy as registrationFlip.test.mjs: Astro names the
// chunk after the .astro file that declares the <script> (MobileNavPanel),
// and inlines it directly into the page HTML instead of emitting a
// dist/_astro/*.js file whenever the chunk shares no imports with any other
// client script and is small enough to qualify for Vite's
// assetsInlineLimit. Minification strips the `isSamePageAnchor` identifier
// (see the bundled output — it becomes a single-letter local), so this
// searches for a CSS-selector string literal that survives minification
// instead of the source-level regexes this test used to rely on.
const MOBILE_PANEL_MARKER = 'data-mobile-panel';
const distDir = new URL('../dist/_astro/', import.meta.url);
const mobilePanelBundleName = readdirSync(distDir).find(
  (f) =>
    f.endsWith('.js') &&
    readFileSync(new URL(f, distDir), 'utf8').includes(MOBILE_PANEL_MARKER),
);

let mobilePanelBundlePath;
if (mobilePanelBundleName) {
  mobilePanelBundlePath = new URL(mobilePanelBundleName, distDir);
} else {
  const html = readFileSync(new URL('../dist/index.html', import.meta.url), 'utf8');
  const { document: builtDoc } = new JSDOM(html).window;
  const inlineScript = Array.from(
    builtDoc.querySelectorAll('script[type="module"]'),
  ).find((el) => el.textContent.includes(MOBILE_PANEL_MARKER));
  assert.ok(
    inlineScript,
    'a bundle containing the mobile panel script should be built (external or inlined)',
  );

  const tmpDir = mkdtempSync(join(tmpdir(), 'mobile-panel-'));
  const tmpFile = join(tmpDir, 'inline-mobile-panel.mjs');
  writeFileSync(tmpFile, inlineScript.textContent);
  mobilePanelBundlePath = new URL(`file://${tmpFile}`);
}

test('recognises a same-page anchor written as an absolute url', () => {
  // The `coming_soon` CTA is authored in Keystatic, where the url field is a
  // full url — so the self-link never looks like a bare '#registration'.
  assert.equal(
    isSamePageAnchor('https://twincitiesskiclub.org/#registration', HOME),
    true,
  );
  assert.equal(isSamePageAnchor('#registration', HOME), true);
  assert.equal(isSamePageAnchor('/#registration', HOME), true);
});

test('does not treat off-page destinations as same-page anchors', () => {
  assert.equal(isSamePageAnchor('https://tcsc.ski/', HOME), false);
  assert.equal(isSamePageAnchor('https://tcsc.ski/#registration', HOME), false);
  assert.equal(isSamePageAnchor('/trips#registration', HOME), false);
  assert.equal(isSamePageAnchor('https://twincitiesskiclub.org/', HOME), false);
  assert.equal(isSamePageAnchor(undefined, HOME), false);
  assert.equal(isSamePageAnchor('', HOME), false);
  assert.equal(isSamePageAnchor('not a url', HOME), false);
});

test('ignores a trailing-slash mismatch between link and page', () => {
  assert.equal(
    isSamePageAnchor('https://twincitiesskiclub.org#registration', HOME),
    true,
  );
  assert.equal(
    isSamePageAnchor('/#registration', 'https://twincitiesskiclub.org'),
    true,
  );
});

test('the registration strip button does not link to the strip itself', () => {
  // The strip IS <section id="registration">, so a CTA pointing back at that
  // anchor is a dead click: the browser is already there and nothing moves.
  const html = readFileSync(new URL('../dist/index.html', import.meta.url), 'utf8');
  const { document } = new JSDOM(html).window;

  const strip = document.querySelector('#registration');
  assert.ok(strip, 'home page should still have the #registration strip');

  const button = strip.querySelector('a[href]');
  assert.ok(button, 'registration strip should still offer a link');

  assert.equal(
    isSamePageAnchor(button.getAttribute('href'), HOME),
    false,
    `strip button links to its own section: ${button.getAttribute('href')}`,
  );
});

test('the mobile menu closes itself and releases the scroll lock before a same-page anchor scrolls', async () => {
  // A same-document fragment click never reloads, so without this the panel
  // stays open over a scroll-locked body and the CTA looks broken. This
  // drives the REAL built script against a DOM shaped like the real markup,
  // rather than grepping the .astro source: a source-text match keeps passing
  // even if the `close()` call is deleted from the handler body, which makes
  // that kind of assertion a guard with no teeth.
  const dom = new JSDOM(
    `<!doctype html><html><body>
      <button data-mobile-toggle aria-expanded="false">Open</button>
      <div data-mobile-panel class="hidden" aria-hidden="true">
        <button data-mobile-close aria-label="Close menu">Close</button>
        <nav>
          <a href="/about">About</a>
          <a href="https://twincitiesskiclub.org/#registration">Fall registration dates</a>
        </nav>
      </div>
    </body></html>`,
    { url: HOME },
  );
  globalThis.window = dom.window;
  globalThis.document = dom.window.document;
  globalThis.Element = dom.window.Element;
  // jsdom implements neither: the open handler chains two rAFs purely to let
  // a display-change commit before the opening transition starts, and
  // scrollTo is jsdom's own no-op stub that only logs a warning. Neither
  // affects what this test asserts, so stub them rather than let their
  // absence throw or add stderr noise.
  globalThis.requestAnimationFrame = (cb) => setTimeout(cb, 0);
  dom.window.scrollTo = () => {};

  await import(`${mobilePanelBundlePath.href}?t=${encodeURIComponent(Math.random())}`);

  const { document } = dom.window;
  const toggle = document.querySelector('[data-mobile-toggle]');
  const panel = document.querySelector('[data-mobile-panel]');
  const anchorLink = document.querySelector('a[href="https://twincitiesskiclub.org/#registration"]');

  assert.notEqual(document.body.style.position, 'fixed', 'body should not start scroll-locked');

  toggle.dispatchEvent(new dom.window.Event('click', { bubbles: true }));
  assert.equal(panel.classList.contains('hidden'), false, 'opening the toggle should show the panel');
  assert.equal(document.body.style.position, 'fixed', 'opening the panel should lock the body scroll');

  anchorLink.dispatchEvent(new dom.window.Event('click', { bubbles: true }));

  assert.equal(
    panel.classList.contains('hidden'),
    true,
    'the panel should close itself on a same-page anchor click',
  );
  assert.notEqual(
    document.body.style.position,
    'fixed',
    'closing the panel should release the body scroll lock',
  );
});
