import assert from 'node:assert/strict';
import test from 'node:test';
import { JSDOM } from 'jsdom';

import { refreshEventBands } from '../src/lib/eventRefresh.ts';

const EVENT = {
  slug: 'dry-tri-2026', name: 'Dry Tri', location: 'Carver Park Reserve', description: '',
  event_date: '2026-10-24T14:00:00Z', signup_start: '2026-07-25T05:00:00Z', signup_end: '2026-10-23T04:59:00Z',
  registration_path: '/events/dry-tri-2026', details_url: null, entries: [],
};
const API = 'https://tcsc.ski/api/events/dry-tri';

function page(baked) {
  const { document } = new JSDOM(
    `<div data-event-band data-event-api="${API}" data-event-source="api" data-event='${JSON.stringify(baked)}'>BAKED</div>`,
  ).window;
  return { document, band: document.querySelector('[data-event-band]') };
}
const ok = (body) => async () => ({ ok: true, json: async () => body });

test('re-derives the state from baked data with the current time', async () => {
  const { document, band } = page(EVENT);
  await refreshEventBands(document, async () => { throw new Error('offline'); }, () => Date.parse('2026-10-23T12:00:00Z'));
  assert.equal(band.querySelector('[data-event-cta]').getAttribute('data-state'), 'closed');
  assert.equal(band.getAttribute('data-event-source'), 'api');
});

test('a fresh event replaces the band and marks it live', async () => {
  const { document, band } = page(EVENT);
  const fresh = { ...EVENT, location: 'New place' };
  await refreshEventBands(document, ok({ event: fresh }), () => Date.parse('2026-10-06T15:00:00Z'));
  assert.ok(band.textContent.includes('New place'));
  assert.equal(band.getAttribute('data-event-source'), 'live');
});

test('a null event from the API switches to the fallback line', async () => {
  const { document, band } = page(EVENT);
  await refreshEventBands(document, ok({ event: null }), () => Date.parse('2026-10-06T15:00:00Z'));
  assert.ok(band.textContent.includes('tcsc.ski/tri'));
});

test('a failed fetch with no baked event leaves the fallback markup alone', async () => {
  const { document, band } = page(null);
  await refreshEventBands(document, async () => ({ ok: false, status: 503 }), () => Date.now());
  assert.equal(band.textContent, 'BAKED');
});

test('a malformed body leaves the baked band alone', async () => {
  const { document, band } = page(null);
  await refreshEventBands(document, ok({ unexpected: true }), () => Date.now());
  assert.equal(band.textContent, 'BAKED');
});
