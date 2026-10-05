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
  assert.equal(form.querySelector('button[type="submit"]').textContent.trim(), 'Sign up');
});

test('join page reads in the club voice', () => {
  const { document } = new JSDOM(page('join')).window;
  assert.equal(document.querySelector('h1').textContent.trim(), 'Registration Contact List Sign-up');
  // Eligibility stays explicit so prospects can self-select before signing up.
  assert.ok(document.body.textContent.includes('For skiers ages 21-35 with intermediate skills. No racing required.'));
  assert.doesNotMatch(document.body.textContent, /\u2014/, 'no em dashes in copy');
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

test('join page flips to a Register button when registration opens', () => {
  // registrationFlip.ts swaps a [data-registration] CTA and, in the same
  // <section>, its [data-registration-subhead]. Assert the baked contract it
  // needs; the flip mechanism itself is covered by registrationFlip.test.mjs.
  const { document } = new JSDOM(page('join')).window;
  const subhead = document.querySelector('main [data-registration-subhead]');
  assert.ok(subhead, 'join page needs a flip-aware subhead');
  const cta = subhead.closest('section').querySelector('[data-registration]');
  assert.ok(cta, 'subhead must share a <section> with a [data-registration] CTA');

  assert.equal(cta.getAttribute('data-open-url'), 'https://tcsc.ski/');
  assert.equal(subhead.getAttribute('data-open-subhead'), 'Registration is open now. Skip the list and register.');
  assert.equal(cta.getAttribute('data-soon-url'), '#join-form');
  // One primary action per screen: the top CTA shows only when registration
  // is open. Outside that, the form right below is the action. CSS keys off
  // data-state, which registrationFlip.ts updates, so this needs no JS.
  assert.match(cta.parentElement.className, /\[&>\[data-registration\]:not\(\[data-state=open\]\)\]:hidden/);
  assert.ok(document.getElementById('join-form'), 'the scroll target must exist');

  // The fixture build is coming_soon: dates show, no "open" copy.
  assert.equal(cta.getAttribute('data-state'), 'coming_soon');
  assert.match(subhead.textContent, /Registration opens: Returning members \w{3} \d{1,2}/);
});
