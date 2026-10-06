import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { JSDOM } from 'jsdom';

// TCSC_EDGE_CONFIG builds format 'file', so the page is dist/dry-tri.html.
const html = readFileSync(new URL('../dist/dry-tri.html', import.meta.url), 'utf8');
const { document } = new JSDOM(html).window;
const band = document.querySelector('[data-event-band]');

test('the band was baked from the fixture API, not the fallback', () => {
  assert.equal(band?.getAttribute('data-event-source'), 'api');
});

test('the fixture build is open with a Register button to tcsc', () => {
  const cta = band.querySelector('[data-event-cta]');
  assert.equal(cta.getAttribute('data-state'), 'open');
  assert.match(cta.querySelector('a').getAttribute('href'), /\/events\/dry-tri-fixture$/);
});

test('entries and schedule render', () => {
  assert.deepEqual([...band.querySelectorAll('[data-entry-price]')].map((p) => p.textContent), ['$55', '$30']);
  assert.equal(band.querySelector('li').textContent, '7:30 AM: Packet pickup opens');
});

test('baked JSON round-trips for the browser refresh', () => {
  assert.equal(JSON.parse(band.getAttribute('data-event')).slug, 'dry-tri-fixture');
});

test('the old 2026 placeholder and 2025-only labels are gone', () => {
  const text = document.body.textContent;
  assert.ok(!text.includes('Planning for 2026 is underway'));
  assert.ok(!text.includes('The 2025 format'));
  assert.ok(text.includes('Latest results'));
});

test('no em or en dashes in the page body', () => {
  assert.ok(!/[–—]/.test(document.querySelector('main').textContent));
});
