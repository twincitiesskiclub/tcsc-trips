import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { JSDOM } from 'jsdom';

// Builds the whole site against a dead endpoint. Slow by nature: this is the
// only way to prove the accepted tradeoff (a deploy is never blocked) does not
// silently ship a page that claims registration is open.
test('a build against a dead API still succeeds and announces itself', () => {
  const root = new URL('..', import.meta.url).pathname;

  execFileSync('npm', ['run', 'build'], {
    cwd: root,
    env: { ...process.env, PUBLIC_SEASON_API_URL: 'http://127.0.0.1:1/api/season' },
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

  // And the destination is the app, which reads the database live.
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
