import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import test from 'node:test';

import { fetchSeasonData } from '../src/lib/seasonData.ts';

const BODY = {
  generated_at: '2026-07-30T12:00:00Z',
  primary: {
    name: '2026 Fall/Winter',
    season_type: 'fall/winter',
    year: 2026,
    price_cents: 20500,
    returning_start: '2026-08-28T17:00:00Z',
    returning_end: '2026-09-02T05:00:00Z',
    new_start: '2026-09-03T17:00:00Z',
    new_end: '2026-09-20T05:00:00Z',
  },
  by_type: { 'fall/winter': { season_type: 'fall/winter', year: 2026 } },
};

async function withServer(handler, run) {
  const server = createServer(handler);
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const url = `http://127.0.0.1:${server.address().port}/api/season`;
  try {
    return await run(url);
  } finally {
    server.close();
  }
}

test('returns api data when the endpoint responds', async () => {
  await withServer(
    (req, res) => {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(BODY));
    },
    async (url) => {
      const data = await fetchSeasonData(url);
      assert.equal(data.source, 'api');
      assert.equal(data.primary.season_type, 'fall/winter');
      assert.equal(data.generated_at, '2026-07-30T12:00:00Z');
      assert.equal(data.by_type['fall/winter'].year, 2026);
    },
  );
});

test('issues one request per build no matter how many callers ask', async () => {
  let hits = 0;
  await withServer(
    (req, res) => {
      hits += 1;
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(BODY));
    },
    async (url) => {
      await Promise.all([fetchSeasonData(url), fetchSeasonData(url), fetchSeasonData(url)]);
      assert.equal(hits, 1);
    },
  );
});

test('falls back instead of throwing when the endpoint is unreachable', async () => {
  // Port 1 is reserved and nothing listens on it.
  const data = await fetchSeasonData('http://127.0.0.1:1/api/season');
  assert.equal(data.source, 'fallback');
  assert.equal(data.primary, null);
  assert.deepEqual(data.by_type, {});
  assert.equal(data.generated_at, null);
});

test('falls back on a non-200 response', async () => {
  await withServer(
    (req, res) => {
      res.writeHead(503);
      res.end('down');
    },
    async (url) => {
      const data = await fetchSeasonData(url);
      assert.equal(data.source, 'fallback');
      assert.equal(data.primary, null);
    },
  );
});

test('falls back on a malformed body', async () => {
  await withServer(
    (req, res) => {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end('{ not json');
    },
    async (url) => {
      const data = await fetchSeasonData(url);
      assert.equal(data.source, 'fallback');
    },
  );
});
