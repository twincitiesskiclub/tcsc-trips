'use strict';

// Season registration step 0: the server's verdict is rendered by
// applyVerdict and the resume IIFE. These tests drive script.js through
// a stubbed /api/verify/resolve and check what the member would see.

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require('jsdom');

const ROOT = path.resolve(__dirname, '../..');
const SOURCE = fs.readFileSync(path.join(ROOT, 'app/static/script.js'), 'utf8');

// Mirrors season_register.html: every element step 0 binds to, the
// verdict panels, and a wizard with the payment status line and button.
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
  <input type="email" id="email" name="email" required>
  <div id="email-collision" hidden>
    <p id="email-collision-error" hidden></p>
    <button type="button" id="email-collision-send">Email me a code</button>
    <div id="email-collision-code-row" hidden>
      <input type="text" id="email-collision-code">
      <button type="button" id="email-collision-check">Verify</button>
    </div>
    <a href="#" id="email-collision-dead">Can't reach that inbox?</a>
  </div>
  <input type="text" id="firstName" name="firstName" required>
  <p id="payment-status-line" hidden></p>
  <button type="submit" id="register-btn">
    <span id="button-text">Register</span>
    <span id="button-spinner" style="display:none"></span>
  </button>
</form>
</body></html>`;

const ENTERED_KEY = 'tcsc-registration-7-entered';

function boot(opts) {
  const dom = new JSDOM(HTML, {
    url: 'https://tcsc.test/seasons/7/register',
    runScripts: 'outside-only',
  });
  const {window} = dom;
  window.HTMLElement.prototype.scrollIntoView = () => {};
  window.scrollTo = () => {};
  if (opts.entered !== undefined) {
    window.sessionStorage.setItem(ENTERED_KEY, opts.entered);
  }
  const calls = [];
  window.fetch = (url, init) => {
    const u = String(url);
    calls.push({url: u, method: (init && init.method) || 'GET'});
    let body;
    if (u.includes('/api/verify/resolve')) body = opts.resolve;
    else if (u.includes('/api/verify/disclaim')) body = opts.disclaim || {ok: true};
    else body = {ok: false, error: 'stubbed'};
    return Promise.resolve({ok: true, status: 200, json: () => Promise.resolve(body)});
  };
  window.eval(SOURCE);
  window.document.dispatchEvent(
    new window.Event('DOMContentLoaded', {bubbles: true}));
  return {window, calls};
}

const tick = () => new Promise(resolve => setTimeout(resolve, 0));
async function settle() {
  for (let i = 0; i < 6; i++) await tick();
}

function wizardVerdict(memberType, firstName) {
  const user = firstName
    ? {firstName, lastName: 'Member', email: 'm@test.com'}
    : null;
  return {
    outcome: memberType === 'returning' ? 'wizard_returning' : 'wizard_new',
    context: {member_type: memberType, first_name: firstName || null},
    user,
  };
}

// --- Submit button label follows the capture method ---

test('returning member sees Register & Pay with the amount', async () => {
  const {window} = boot({resolve: wizardVerdict('returning', 'Rita')});
  await settle();
  const doc = window.document;
  assert.equal(doc.getElementById('registration-form').hidden, false);
  assert.equal(doc.getElementById('button-text').textContent, 'Register & Pay $205.00');
});

test('new member sees Register & Hold, matching the hold copy above it', async () => {
  const {window} = boot({resolve: wizardVerdict('new', null)});
  await settle();
  const doc = window.document;
  assert.equal(doc.getElementById('button-text').textContent, 'Register & Hold $205.00');
  assert.match(doc.getElementById('payment-status-line').textContent, /hold/i);
});

test('unknown member type falls back to a neutral Register', async () => {
  const {window} = boot({
    resolve: {outcome: 'wizard_new', context: {member_type: null, first_name: null}, user: null},
  });
  await settle();
  assert.equal(window.document.getElementById('button-text').textContent, 'Register');
});

test('spinner span survives the label change', async () => {
  const {window} = boot({resolve: wizardVerdict('returning', 'Rita')});
  await settle();
  assert.ok(window.document.getElementById('button-spinner'));
});
