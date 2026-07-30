import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { JSDOM } from 'jsdom';

const html = readFileSync(new URL('../dist/index.html', import.meta.url), 'utf8');
const { document } = new JSDOM(html).window;

test('the page records where its season data came from', () => {
  // The test-build fixture (scripts/test-build.mjs) always serves a healthy
  // payload, so a real build against it must land on "api", not merely one of
  // the two valid stamps -- accepting "fallback" here would also pass if the
  // fixture harness died and every build silently fell back.
  const source = document.body.getAttribute('data-season-source');
  assert.equal(source, 'api', `expected the fixture build to report "api", got ${source}`);
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

test('the hero shows the coming_soon dates line under the CTA, with all baked variants', () => {
  // The fixture build (scripts/test-build.mjs) always lands on coming_soon
  // with real windows, so the hero's dates line should be visible and read
  // the same dates the CTA itself was baked with.
  const dates = document.querySelector('[data-registration-dates]');
  assert.ok(dates, 'expected a dates element in the hero section');
  assert.equal(dates.hasAttribute('hidden'), false, 'dates line should be visible under coming_soon');
  assert.match(dates.textContent, /Returning members .+ · New members .+/);

  // Baked so registrationFlip.ts can hide it (open/closed) or restore it
  // (coming_soon) without a rebuild, exactly like the CTA's own variants.
  assert.equal(dates.getAttribute('data-open-dates'), '');
  assert.equal(dates.getAttribute('data-closed-dates'), '');
  assert.equal(dates.getAttribute('data-soon-dates'), dates.textContent);

  const hero = dates.closest('section');
  const cta = hero.querySelector('[data-registration]');
  assert.equal(cta.getAttribute('data-state'), 'coming_soon');
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
