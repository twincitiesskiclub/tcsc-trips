'use strict';

// Season registration payment step: what the wizard does when
// /create-season-payment-intent refuses BEFORE placing a hold. These are
// the client halves of the server gates in
// tests/registration/test_payment_intent_gates.py.

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require('jsdom');

const ROOT = path.resolve(__dirname, '../..');
const SOURCE = fs.readFileSync(path.join(ROOT, 'app/static/script.js'), 'utf8');

// Step 0 panels (mirrors season_verify.test.js) plus the wizard fields the
// submit path validates and the Stripe card mount.
const HTML = `<!DOCTYPE html><html><body>
<nav class="progress-bar" hidden></nav>
<section id="section-verify" class="form-section">
  <div id="verify-expired-notice" hidden></div>
  <div id="verify-error" hidden></div>
  <div id="verify-phone-entry">
    <input type="tel" id="verify-phone">
    <button type="button" id="verify-send-btn">Text me a code</button>
    <a href="#" id="verify-cant-text-link">Can't receive texts?</a>
  </div>
  <div id="verify-code-entry" hidden>
    <span id="verify-phone-echo"></span><a href="#" id="verify-edit-phone">Edit</a>
    <input type="text" id="verify-code">
    <button type="button" id="verify-check-btn">Verify</button>
    <button type="button" id="verify-resend-btn" disabled>Resend (30)</button>
  </div>
  <div id="verify-email-entry" hidden>
    <p id="verify-email-msg"></p>
    <input type="email" id="verify-email">
    <button type="button" id="verify-email-send-btn">Email me a code</button>
    <div id="verify-email-code-row" hidden>
      <span id="verify-email-echo"></span>
      <input type="text" id="verify-email-code">
      <button type="button" id="verify-email-check-btn">Verify</button>
    </div>
    <a href="#" id="verify-email-dead-link">Can't reach that inbox?</a>
  </div>
  <div id="verify-already-registered" hidden>
    <h3 id="already-registered-title"></h3>
    <p id="already-registered-detail"></p>
    <a href="#" id="already-registered-not-me-link" hidden></a>
  </div>
  <div id="verify-window-wait" hidden>
    <h3 id="window-wait-title"></h3>
    <a href="#" id="window-wait-not-me-link" hidden></a>
  </div>
  <div id="verify-window-ended" hidden>
    <h3 id="window-ended-title"></h3>
    <a href="#" id="window-ended-not-me-link" hidden></a>
  </div>
</section>
<div id="verify-welcome" hidden>
  <span id="verify-welcome-text"></span>
  <a href="#" id="verify-not-me-link"></a>
</div>
<div id="unverified-notice" hidden></div>
<form id="registration-form" data-season-id="7" data-price-cents="20500" hidden>
  <input type="hidden" name="csrf_token" value="t">
  <input type="hidden" name="continue_unverified" id="continue-unverified" value="0">
  <input type="email" id="email" name="email" value="member@test.com" required>
  <div id="email-collision" hidden>
    <p id="email-collision-error" hidden></p>
    <button type="button" id="email-collision-send">Email me a code</button>
    <div id="email-collision-code-row" hidden>
      <input type="text" id="email-collision-code">
      <button type="button" id="email-collision-check">Verify</button>
    </div>
    <a href="#" id="email-collision-dead">Can't reach that inbox?</a>
  </div>
  <input type="text" id="firstName" name="firstName" value="Mem" required>
  <input type="text" id="name" name="name" value="Mem Ber" required>
  <div id="card-element"></div>
  <div class="card-error" id="card-errors" role="alert"></div>
  <input type="checkbox" id="agreement" name="agreement" checked required>
  <p id="payment-status-line" hidden></p>
  <button type="submit" id="register-btn">
    <span id="button-text">Register</span>
    <span id="button-spinner" style="display:none"></span>
  </button>
</form>
</body></html>`;

function wizardNew() {
  return {outcome: 'wizard_new', context: {member_type: 'new', first_name: null}, user: null};
}
function verifyPhone() {
  return {outcome: 'verify_phone', context: {}};
}

// opts.intent: the /create-season-payment-intent reply {status, body}.
// opts.resolve: the /api/verify/resolve reply; opts.afterRefusal replaces
// it once the intent request has been refused.
function boot(opts) {
  const dom = new JSDOM(HTML, {
    url: 'https://tcsc.test/seasons/7/register',
    runScripts: 'outside-only',
  });
  const {window} = dom;
  window.HTMLElement.prototype.scrollIntoView = () => {};
  window.scrollTo = () => {};
  const calls = [];
  let refused = false;
  window.fetch = (url, init) => {
    const u = String(url);
    calls.push({url: u, init: init || {}});
    if (u.includes('get-stripe-key')) {
      return Promise.resolve({ok: true, status: 200, json: () => Promise.resolve({publicKey: 'pk_test'})});
    }
    if (u.includes('/api/verify/resolve')) {
      // Before the refusal the server says "wizard"; after it, whatever
      // the test says the identity now resolves to.
      const body = refused && opts.afterRefusal ? opts.afterRefusal : opts.resolve;
      return Promise.resolve({ok: true, status: 200, json: () => Promise.resolve(body)});
    }
    if (u.includes('create-season-payment-intent')) {
      const {status, body} = opts.intent;
      if (status >= 400) refused = true;
      return Promise.resolve({ok: status < 400, status, json: () => Promise.resolve(body)});
    }
    return Promise.resolve({ok: false, status: 500, json: () => Promise.resolve({error: 'stubbed'})});
  };
  window.Stripe = () => ({
    elements: () => ({create: () => ({mount: () => {}, on: () => {}})}),
    confirmCardPayment: () => Promise.resolve({error: {message: 'stub'}}),
  });
  window.eval(SOURCE);
  window.document.dispatchEvent(
    new window.Event('DOMContentLoaded', {bubbles: true}));
  return {window, calls};
}

const tick = () => new Promise(resolve => setTimeout(resolve, 0));
async function settle() {
  for (let i = 0; i < 8; i++) await tick();
}

function submit(window) {
  window.document.getElementById('registration-form').dispatchEvent(
    new window.Event('submit', {bubbles: true, cancelable: true}));
}

test('payment intent request carries the continue_unverified flag', async () => {
  const {window, calls} = boot({
    resolve: wizardNew(),
    intent: {status: 500, body: {error: 'stubbed'}},
  });
  await settle();
  const doc = window.document;
  assert.equal(doc.getElementById('registration-form').hidden, false);
  // Dead-inbox hatch flips the hidden field to 1.
  doc.getElementById('email-collision-dead').dispatchEvent(
    new window.Event('click', {bubbles: true, cancelable: true}));
  assert.equal(doc.getElementById('continue-unverified').value, '1');

  submit(window);
  await settle();

  const intent = calls.find(c => c.url.includes('create-season-payment-intent'));
  assert.ok(intent, 'payment intent was requested');
  const body = JSON.parse(intent.init.body);
  assert.equal(body.continue_unverified, true);
});

test('verification_expired sends the member back to phone entry', async () => {
  const {window, calls} = boot({
    resolve: wizardNew(),
    afterRefusal: verifyPhone(),
    intent: {status: 400, body: {
      error: 'Your verification expired. Please verify your number again.',
      code: 'verification_expired'}},
  });
  await settle();
  const resolvesBefore = calls.filter(c => c.url.includes('/api/verify/resolve')).length;
  submit(window);
  await settle();

  const doc = window.document;
  const resolvesAfter = calls.filter(c => c.url.includes('/api/verify/resolve')).length;
  assert.ok(resolvesAfter > resolvesBefore, 'client re-asked the server after the refusal');
  assert.equal(doc.getElementById('verify-phone-entry').hidden, false);
  assert.equal(doc.getElementById('registration-form').hidden, true);
  assert.match(doc.getElementById('verify-error').textContent, /expired/i);
  assert.equal(doc.getElementById('verify-error').hidden, false);
});

test('email_unverified reopens the collision box instead of paying', async () => {
  const {window} = boot({
    resolve: wizardNew(),
    intent: {status: 400, body: {
      error: 'That email already has a member account.',
      code: 'email_unverified'}},
  });
  await settle();
  submit(window);
  await settle();

  const doc = window.document;
  assert.equal(doc.getElementById('registration-form').hidden, false);
  assert.equal(doc.getElementById('email-collision').hidden, false);
  assert.equal(doc.getElementById('email-collision-send').hidden, false);
  assert.match(doc.getElementById('card-errors').textContent, /member account/i);
});
