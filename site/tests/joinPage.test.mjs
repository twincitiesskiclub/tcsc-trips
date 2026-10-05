import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { JSDOM } from 'jsdom';

function page(slug) {
  const base = new URL('../dist/', import.meta.url);
  for (const candidate of [`${slug}/index.html`, `${slug}.html`]) {
    try {
      return readFileSync(new URL(candidate, base), 'utf8');
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
    }
  }
  throw new Error(`no built page for ${slug}`);
}

test('join page posts a plain form to tcsc.ski', () => {
  const { document } = new JSDOM(page('join')).window;
  const form = document.querySelector('form[action="https://tcsc.ski/interest"]');
  assert.ok(form, 'join page must post to https://tcsc.ski/interest');
  assert.equal(form.getAttribute('method'), 'post');
  assert.ok(form.querySelector('input[name="email"][type="email"][required]'));
  assert.ok(form.querySelector('input[name="name"][required]'));
  assert.ok(!form.querySelector('input[name="phone"][required]'), 'phone stays optional');
  assert.ok(form.textContent.includes("We'll text you when registration opens. Reply STOP to opt out."));
});

test('join page shows the opening dates when the season has them', () => {
  // scripts/test-build.mjs serves a fixture whose windows are in the future.
  const { document } = new JSDOM(page('join')).window;
  assert.match(document.body.textContent, /Returning members \w{3} \d{1,2}/);
});

test('join page links members on to tcsc.ski', () => {
  const { document } = new JSDOM(page('join')).window;
  assert.ok(document.querySelector('main a[href="https://tcsc.ski/"]'));
});

test('static site CSP lets the join form post to tcsc.ski', () => {
  const blueprint = readFileSync(new URL('../../render.yaml', import.meta.url), 'utf8');
  assert.match(blueprint, /form-action 'self' https:\/\/tcsc\.ski;/);
});
