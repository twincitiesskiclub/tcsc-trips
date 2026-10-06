import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import test from 'node:test';
import { JSDOM } from 'jsdom';

// Builds the whole site against a dead endpoint. Slow by nature: this is the
// only way to prove the accepted tradeoff (a deploy is never blocked) does not
// silently ship a page that claims registration is open.
test('a build against a dead API still succeeds and announces itself', () => {
  const root = new URL('..', import.meta.url).pathname;

  execFileSync('npm', ['run', 'build'], {
    cwd: root,
    env: {
      ...process.env,
      PUBLIC_SEASON_API_URL: 'http://127.0.0.1:1/api/season',
      PUBLIC_EVENT_API_URL: 'http://127.0.0.1:1/api/events/dry-tri',
    },
    stdio: 'pipe',
  });

  const html = readFileSync(`${root}/dist/index.html`, 'utf8');
  const { document } = new JSDOM(html).window;

  assert.equal(document.body.getAttribute('data-season-source'), 'fallback');

  // Never claims open registration without data to back it.
  const ctas = document.querySelectorAll('[data-registration]');
  assert.ok(ctas.length > 0, 'expected at least one registration CTA');
  for (const cta of ctas) {
    assert.equal(cta.getAttribute('data-state'), 'closed');
  }

  // A fallback build does not know the state, so it must not route people to
  // the interest list: registration may be open. The app reads the database
  // live and shows either the Register button or its own interest form.
  const strip = document.querySelector('#registration a[href]');
  assert.equal(strip.getAttribute('href'), 'https://tcsc.ski/');
});

test.after(() => {
  // Leave dist/ the way the rest of the suite expects to find it.
  execFileSync('node', ['scripts/test-build.mjs'], {
    cwd: new URL('..', import.meta.url).pathname,
    stdio: 'pipe',
  });
});

test('the Dry Tri band announces its own fallback when the event API is dead', () => {
  // Runs after the build above, which pointed both APIs at a dead port.
  // Without TCSC_EDGE_CONFIG the build uses directory format.
  const file = ['../dist/dry-tri.html', '../dist/dry-tri/index.html']
    .map((p) => new URL(p, import.meta.url))
    .find((u) => existsSync(u));
  const html = readFileSync(file, 'utf8');
  const band = new JSDOM(html).window.document.querySelector('[data-event-band]');
  assert.equal(band.getAttribute('data-event-source'), 'fallback');
  assert.equal(band.querySelector('a').getAttribute('href'), 'https://tcsc.ski/tri');
});
