import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { JSDOM } from 'jsdom';

import { isSamePageAnchor } from '../src/lib/samePageAnchor.ts';

const HOME = 'https://twincitiesskiclub.org/';

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

test('the mobile menu closes itself before a same-page anchor scrolls', () => {
  // A same-document fragment click never reloads, so without this the panel
  // stays open over a scroll-locked body and the CTA looks broken.
  const panelSource = readFileSync(
    new URL('../src/components/MobileNavPanel.astro', import.meta.url),
    'utf8',
  );

  assert.match(
    panelSource,
    /isSamePageAnchor/,
    'panel should detect same-page anchor clicks',
  );
  assert.match(
    panelSource,
    /panel\.addEventListener\('click'/,
    'panel should handle clicks on its own links',
  );
});
