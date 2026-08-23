'use strict';

// Season registration "Get Involved" section: committee reveal + the
// pick-at-least-one gate that must block payment submission.

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require('jsdom');

const ROOT = path.resolve(__dirname, '../..');
const SOURCE = fs.readFileSync(path.join(ROOT, 'app/static/script.js'), 'utf8');

// Mirrors season_register.html: the wizard form with the Get Involved
// section, minimal required fields, and the Stripe card mount point.
const HTML = `<!DOCTYPE html><html><body>
<form id="registration-form" data-season-id="7" data-price-cents="15000">
  <input type="hidden" name="csrf_token" value="t">
  <input type="hidden" name="continue_unverified" id="continue-unverified" value="0">
  <input type="email" id="email" name="email" value="vol@test.com" required>
  <input type="text" id="firstName" name="firstName" value="Vol" required>

  <div id="section-volunteer" class="form-section">
    <div class="pill-group" id="volunteer-interests">
      <label class="pill"><input type="checkbox" name="volunteerInterests" value="practice_lead"> Lead a group at practice</label>
      <label class="pill"><input type="checkbox" name="volunteerInterests" value="event_volunteer"> Volunteer at an event</label>
      <label class="pill"><input type="checkbox" name="volunteerInterests" value="committee" id="volunteer-committee-toggle"> Join a committee</label>
    </div>
    <div class="form-field" id="committee-picker" hidden>
      <div class="pill-group" id="volunteer-committees">
        <label class="pill"><input type="checkbox" name="volunteerCommittees" value="adventures"> Adventures</label>
        <label class="pill"><input type="checkbox" name="volunteerCommittees" value="social"> Social</label>
      </div>
    </div>
    <p class="card-error" id="volunteer-error" role="alert" hidden></p>
  </div>

  <input type="text" id="name" name="name" value="Vol Unteer" required>
  <div id="card-element"></div>
  <div class="card-error" id="card-errors" role="alert"></div>
  <input type="checkbox" id="agreement" name="agreement" checked required>
  <button type="submit" id="register-btn">
    <span id="button-text">Register</span>
    <span id="button-spinner" style="display:none"></span>
  </button>
</form>
</body></html>`;

function boot() {
  const dom = new JSDOM(HTML, {
    url: 'https://tcsc.test/seasons/7/register',
    runScripts: 'outside-only',
  });
  const {window} = dom;
  // jsdom has no scrollIntoView; every real browser does.
  window.HTMLElement.prototype.scrollIntoView = () => {};
  const fetchCalls = [];
  window.fetch = (url, opts) => {
    fetchCalls.push(String(url));
    if (String(url).includes('get-stripe-key')) {
      return Promise.resolve({json: () => Promise.resolve({publicKey: 'pk_test'})});
    }
    // Payment intent and everything else: report a server error so the
    // submit path stops after validation has passed.
    return Promise.resolve({
      ok: false,
      status: 500,
      json: () => Promise.resolve({error: 'stubbed'}),
    });
  };
  window.Stripe = () => ({
    elements: () => ({create: () => ({mount: () => {}, on: () => {}})}),
    confirmCardPayment: () => Promise.resolve({error: {message: 'stub'}}),
  });
  window.eval(SOURCE);
  window.document.dispatchEvent(
    new window.Event('DOMContentLoaded', {bubbles: true}));
  return {window, fetchCalls};
}

const tick = () => new Promise(resolve => setTimeout(resolve, 0));

test('committee picker stays hidden until Join a committee is checked', () => {
  const {window} = boot();
  const doc = window.document;
  const picker = doc.getElementById('committee-picker');
  assert.equal(picker.hidden, true);

  const toggle = doc.getElementById('volunteer-committee-toggle');
  toggle.checked = true;
  toggle.dispatchEvent(new window.Event('change', {bubbles: true}));
  assert.equal(picker.hidden, false);

  toggle.checked = false;
  toggle.dispatchEvent(new window.Event('change', {bubbles: true}));
  assert.equal(picker.hidden, true);
});

test('submit with no volunteer pick is blocked before payment', async () => {
  const {window, fetchCalls} = boot();
  const doc = window.document;
  doc.getElementById('registration-form').dispatchEvent(
    new window.Event('submit', {bubbles: true, cancelable: true}));
  await tick();

  const err = doc.getElementById('volunteer-error');
  assert.equal(err.hidden, false);
  assert.match(err.textContent, /at least one/i);
  assert.ok(!fetchCalls.some(u => u.includes('create-season-payment-intent')),
      'payment intent must not be created when the volunteer gate fails');
});

test('committee checked without a committee pick is blocked', async () => {
  const {window, fetchCalls} = boot();
  const doc = window.document;
  const toggle = doc.getElementById('volunteer-committee-toggle');
  toggle.checked = true;
  toggle.dispatchEvent(new window.Event('change', {bubbles: true}));

  doc.getElementById('registration-form').dispatchEvent(
    new window.Event('submit', {bubbles: true, cancelable: true}));
  await tick();

  const err = doc.getElementById('volunteer-error');
  assert.equal(err.hidden, false);
  assert.match(err.textContent, /which one/i);
  assert.ok(!fetchCalls.some(u => u.includes('create-season-payment-intent')));
});

test('a valid pick clears the gate and submit reaches payment', async () => {
  const {window, fetchCalls} = boot();
  const doc = window.document;
  const lead = doc.querySelector('input[value="practice_lead"]');
  lead.checked = true;
  lead.dispatchEvent(new window.Event('change', {bubbles: true}));

  doc.getElementById('registration-form').dispatchEvent(
    new window.Event('submit', {bubbles: true, cancelable: true}));
  await tick();
  await tick();

  assert.equal(doc.getElementById('volunteer-error').hidden, true);
  assert.ok(fetchCalls.some(u => u.includes('create-season-payment-intent')),
      'payment intent should be attempted once the gate passes');
});
