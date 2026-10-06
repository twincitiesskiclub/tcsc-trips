import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import test from 'node:test';

import { fetchEventData, registrationUrl, FALLBACK_URL } from '../src/lib/eventData.ts';

async function withServer(handler, run) {
  const server = createServer(handler);
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const url = `http://127.0.0.1:${server.address().port}/api/events/dry-tri`;
  try {
    return await run(url);
  } finally {
    server.close();
  }
}

test('a healthy response is source api', async () => {
  const body = { generated_at: '2026-10-06T15:00:00Z', event: { slug: 'dry-tri-2026', entries: [] } };
  await withServer((_, res) => res.end(JSON.stringify(body)), async (url) => {
    const data = await fetchEventData(url);
    assert.equal(data.source, 'api');
    assert.equal(data.event.slug, 'dry-tri-2026');
  });
});

test('a null event from a healthy API is still source api', async () => {
  await withServer((_, res) => res.end('{"event": null}'), async (url) => {
    const data = await fetchEventData(url);
    assert.deepEqual(data, { source: 'api', event: null });
  });
});

test('a 500 falls back instead of throwing', async () => {
  await withServer((_, res) => { res.statusCode = 500; res.end(); }, async (url) => {
    assert.deepEqual(await fetchEventData(url), { source: 'fallback', event: null });
  });
});

test('registration path resolves against the API origin', () => {
  const event = { registration_path: '/events/dry-tri-2026' };
  assert.equal(
    registrationUrl(event, 'https://tcsc.ski/api/events/dry-tri'),
    'https://tcsc.ski/events/dry-tri-2026',
  );
});

test('a missing path falls back to tcsc.ski/tri', () => {
  assert.equal(registrationUrl({ registration_path: '' }, 'https://tcsc.ski/api/events/dry-tri'), FALLBACK_URL);
});
