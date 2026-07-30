import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { JSDOM } from 'jsdom';

const html = readFileSync(new URL('../dist/index.html', import.meta.url), 'utf8');
const { document } = new JSDOM(html).window;

test('the page records where its season data came from', () => {
  const source = document.body.getAttribute('data-season-source');
  assert.ok(
    source === 'api' || source === 'fallback',
    `expected an api/fallback stamp, got ${source}`,
  );
});

test('every registration CTA carries all three baked variants', () => {
  const ctas = document.querySelectorAll('[data-registration]');
  assert.ok(ctas.length > 0, 'expected at least one registration CTA');

  for (const cta of ctas) {
    for (const attr of [
      'data-open-label', 'data-open-url',
      'data-soon-label', 'data-soon-url',
      'data-closed-label', 'data-closed-url',
    ]) {
      assert.ok(cta.getAttribute(attr), `missing ${attr}`);
    }
  }
});

test('a CTA renders the variant matching the baked state', () => {
  const cta = document.querySelector('[data-registration]');
  const state = cta.getAttribute('data-state');
  assert.ok(['open', 'coming_soon', 'closed'].includes(state), `bad state: ${state}`);

  const expected = {
    open: 'data-open-label',
    coming_soon: 'data-soon-label',
    closed: 'data-closed-label',
  }[state];
  assert.equal(cta.textContent.trim(), cta.getAttribute(expected));
});

test('the registration strip still never links to its own section', () => {
  // Guards the fix from earlier on this branch against the rewrite.
  const strip = document.querySelector('#registration');
  const button = strip.querySelector('a[href]');
  const href = new URL(button.getAttribute('href'), 'https://twincitiesskiclub.org/');
  assert.notEqual(href.hash, '#registration');
});

test('registration_state is gone from the content schema', () => {
  const home = readFileSync(
    new URL('../src/content/pages/home.yaml', import.meta.url),
    'utf8',
  );
  assert.doesNotMatch(home, /registration_state/);

  const config = readFileSync(
    new URL('../src/content.config.ts', import.meta.url),
    'utf8',
  );
  assert.doesNotMatch(config, /registration_state/);
});
