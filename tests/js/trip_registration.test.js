'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const {JSDOM} = require('jsdom');

const ROOT = path.resolve(__dirname, '../..');
const VENV = path.join(ROOT, '.venv-linux/bin/python');
const PYTHON = process.env.PYTHON || (fs.existsSync(VENV) ? VENV : 'python3');
// Render the real template without connecting to a database or a provider.
const HTML = execFileSync(PYTHON, ['-c', `
from pathlib import Path
import runpy
from types import SimpleNamespace
from flask import Flask, render_template
app = Flask('trip_test', template_folder=str(Path('app/templates').resolve()))
app.jinja_env.filters['format_price'] = lambda cents: f'$'+format(cents / 100, '.2f')
app.jinja_env.globals['csrf_meta_tag'] = lambda: ''
schema = runpy.run_path('app/trips/questions.py')
questions = schema['default_builtin_questions']() + [
  {'key':'chore','label':'Which task?','type':'choice','options':['Cooking','Cleaning'],'required':True},
  {'key':'day','label':'Which day?','type':'choice','options':['Mon','Tue','Wed','Thu','Fri','Sat'],'required':False},
  {'key':'sharing','label':'Share a bed?','type':'yes_no','required':True},
  {'key':'share_with','label':'With whom?','type':'text','required':True,'visible_if':{'question':'sharing','equals':'yes'}},
  {'key':'departures','label':'Departure windows','type':'multi_choice','options':['Friday','Saturday','Sunday'],'max_selections':2,'required':True},
]
trip = SimpleNamespace(name='North Shore', destination='Lutsen, MN', formatted_date_range='Sep 18 to 20, 2026', price_low=21500, price_high=24500, custom_questions=questions)
with app.test_request_context():
  print(render_template('trips/register.html', trip=trip, series=SimpleNamespace(slug='north-shore'), registration_open=True, questions=questions, registration_data={'slug':'north-shore','priceLow':21500,'priceHigh':24500}))
`], {cwd: ROOT, encoding: 'utf8'});
const source = fs.readFileSync(path.join(ROOT, 'app/static/trip_registration.js'), 'utf8')
  .replace(/^import .*;\s*/, '');
const surveySource = fs.readFileSync(path.join(ROOT, 'app/static/trip_survey.js'), 'utf8');
const surveyModule = import('data:text/javascript;base64,' + Buffer.from(surveySource).toString('base64'));
const flush = () => new Promise(resolve => setImmediate(resolve));

async function load({eligible = true, gateFails = false, serverError = null, stripeError = null,
  disabledBuiltins = [], optionalRegion = false, requiredDietary = false, noSurvey = false,
  completeCard = true, deferStripe = false} = {}) {
  const dom = new JSDOM(HTML, {url: 'http://localhost/north-shore/register', pretendToBeVisual: true});
  const {window} = dom;
  const {document} = window;
  disabledBuiltins.forEach(id => document.querySelector(`[data-builtin="${id}"]`).remove());
  if (optionalRegion) document.getElementById('profile-region').required = false;
  if (requiredDietary) document.getElementById('dietary-options').dataset.required = 'true';
  if (noSurvey) {
    document.getElementById('trip-questions').remove();
    document.querySelector('[href="#trip-questions"]').remove();
  }
  window.HTMLElement.prototype.scrollIntoView = function () {};
  window.matchMedia = () => ({matches: true});
  const posts = [];
  const confirmations = [];
  let stripeChange;
  let resolveStripeKey;
  const stripeKeyReady = deferStripe ? new Promise(resolve => { resolveStripeKey = resolve; }) : Promise.resolve();
  const card = {
    mount() {},
    focus() { this.focused = true; },
    on(name, callback) {
      if (name === 'change') {
        stripeChange = callback;
        callback({complete: completeCard});
      }
    },
  };
  window.Stripe = () => ({
    elements: () => ({create: () => card}),
    confirmCardPayment: async (...args) => {
      confirmations.push(args);
      return stripeError ? {error: {message: stripeError}} : {};
    },
  });
  const fetch = async (url, options) => {
    if (url === '/get-stripe-key') {
      await stripeKeyReady;
      return {ok: true, json: async () => ({publicKey: 'pk_test_stub'})};
    }
    if (url === '/api/trips/member-check') {
      if (gateFails) throw new Error('Network unavailable');
      return {ok: true, json: async () => ({eligible})};
    }
    assert.equal(url, '/north-shore/register');
    posts.push(JSON.parse(options.body));
    return {ok: !serverError, json: async () => serverError
      ? {error: serverError}
      : {clientSecret: 'cs_test', amountCents: 24500, registrationId: 1}};
  };
  const {initTripSurvey} = await surveyModule;
  new Function('document', 'window', 'fetch', 'initTripSurvey', source)(document, window, fetch, initTripSurvey);
  await flush();
  const form = document.getElementById('trip-registration-form');
  async function gate() {
    document.getElementById('member-email').value = 'member@example.com';
    document.getElementById('gate-check').click();
    await flush();
  }
  function click(selector) { form.querySelector(selector).closest('label').click(); }
  function fill() {
    if (document.getElementById('profile-can-drive-group')) click('[name="profile-can-drive"][value="no"]');
    if (document.getElementById('profile-region')) document.getElementById('profile-region').value = '4';
    click('[data-question-key="chore"] input[value="Cooking"]');
    document.querySelector('[data-question-key="day"]').value = 'Fri';
    click('[data-question-key="sharing"] input[value="no"]');
    click('[data-question-key="departures"] input[value="Friday"]');
    if (document.getElementById('dietary-options')) click('[data-dietary][value="Vegan"]');
  }
  async function submit() {
    form.dispatchEvent(new window.Event('submit', {bubbles: true, cancelable: true}));
    await flush();
  }
  return {window, document, form, posts, confirmations, gate, click, fill, submit, card,
    stripeChange(event) { stripeChange(event); },
    async finishStripeLoading() { resolveStripeKey(); await flush(); },
  };
}

function visible(node) { return !node.hidden; }

test('member check collapses to the confirmed email and unlocks the next step', async () => {
  const page = await load();
  await page.gate();
  assert.equal(visible(page.document.getElementById('gate-entry')), false);
  assert.equal(visible(page.document.getElementById('gate-confirmed')), true);
  assert.equal(page.document.getElementById('confirmed-email').textContent, 'member@example.com');
  assert.equal(visible(page.document.getElementById('form-body')), true);
  assert.equal(page.document.getElementById('member-email').readOnly, true);
  assert.equal(page.document.querySelector('[data-step-link][aria-current="step"]').getAttribute('href'), '#trip-questions');
});

test('ineligible members stay at the gate with an accessible inline error', async () => {
  const page = await load({eligible: false});
  await page.gate();
  assert.equal(visible(page.document.getElementById('form-body')), false);
  assert.equal(visible(page.document.getElementById('gate-message')), true);
  assert.equal(page.document.getElementById('member-email').getAttribute('aria-invalid'), 'true');
});

test('a failed member check can be retried without an unhandled rejection', async () => {
  const page = await load({gateFails: true});
  await page.gate();
  assert.equal(page.document.getElementById('gate-check').disabled, false);
  assert.equal(visible(page.document.getElementById('gate-message')), true);
  assert.match(page.document.getElementById('gate-message').textContent, /try again/i);
});

test('price selection updates the hold amount without losing the price-tier values', async () => {
  const page = await load();
  assert.equal(page.document.getElementById('button-text').textContent, 'Place hold for $215.00');
  page.click('[name="price-tier"][value="high"]');
  assert.equal(page.document.getElementById('button-text').textContent, 'Place hold for $245.00');
  page.click('[name="price-tier"][value="low"]');
  assert.equal(page.document.getElementById('button-text').textContent, 'Place hold for $215.00');
});

test('pill, select and checkbox answers reach the payload while hidden dependents are omitted', async () => {
  const page = await load();
  await page.gate();
  page.fill();
  page.click('[name="price-tier"][value="high"]');
  await page.submit();
  assert.deepEqual(page.posts[0].answers, {chore: 'Cooking', day: 'Fri', sharing: 'no', departures: ['Friday']});
  assert.equal(page.posts[0].price_tier, 'high');
  assert.deepEqual(page.posts[0].profile.dietary_restrictions, ['Vegan']);
  assert.equal(page.posts[0].profile.seat_capacity, '');
  assert.equal(page.confirmations.length, 1);
  assert.equal(visible(page.form), false);
  assert.equal(visible(page.document.querySelector('.completed-view')), true);
  assert.match(page.document.getElementById('confirmation-message').textContent, /\$245.00/);
  assert.equal(page.document.activeElement.id, 'confirmation-title');
});

test('field errors show at both a control and a group, link to the controls and keep the summary', async () => {
  const page = await load({serverError: {'profile.region_code': 'Choose a region.', 'answers.chore': 'Choose a task.'}});
  await page.gate();
  page.fill();
  await page.submit();
  const region = page.document.getElementById('profile-region');
  assert.equal(region.getAttribute('aria-invalid'), 'true');
  assert.equal(page.document.getElementById('profile-region-error').textContent, 'Choose a region.');
  assert.equal(page.document.getElementById('question-4-error').textContent, 'Choose a task.');
  assert.ok(region.getAttribute('aria-describedby').includes('profile-region-error'));
  assert.match(page.document.getElementById('form-errors').textContent, /Choose a region.*Choose a task/);
  assert.equal(page.confirmations.length, 0);
});

test('empty required fields, including checkbox groups, stop before a registration request', async () => {
  const page = await load();
  await page.gate();
  await page.submit();
  assert.equal(page.posts.length, 0);
  assert.ok(page.document.getElementById('profile-can-drive-group-error').textContent);
  page.fill();
  page.click('[data-question-key="departures"] input[value="Friday"]');
  await page.submit();
  assert.equal(page.posts.length, 0);
  assert.ok(page.document.getElementById('question-8-error').textContent);
});

test('an incomplete card blocks native form submission until Stripe reports it complete', async () => {
  const page = await load({completeCard: false});
  await page.gate();
  page.fill();
  await page.submit();
  assert.equal(page.posts.length, 0);
  assert.equal(page.confirmations.length, 0);
  assert.equal(page.document.getElementById('card-element-error').textContent, 'Enter your card details.');
  assert.equal(page.document.getElementById('card-element').getAttribute('aria-invalid'), 'true');
  assert.equal(page.card.focused, true);

  page.stripeChange({complete: true});
  assert.equal(page.document.getElementById('card-element-error').hidden, true);
  await page.submit();
  assert.equal(page.posts.length, 1);
  assert.equal(page.confirmations.length, 1);
});

test('submission waits for Stripe to load and for the card to become complete', async () => {
  const page = await load({completeCard: false, deferStripe: true});
  await page.gate();
  page.fill();
  await page.submit();
  assert.equal(page.posts.length, 0);
  assert.equal(page.document.getElementById('card-element-error').textContent, 'Enter your card details.');
  await page.finishStripeLoading();
  await page.submit();
  assert.equal(page.posts.length, 0);
  page.stripeChange({complete: true});
  page.stripeChange({complete: false});
  await page.submit();
  assert.equal(page.posts.length, 0);
  page.stripeChange({complete: true});
  await page.submit();
  assert.equal(page.posts.length, 1);
});

test('hiding driver details and conditional answers clears their obsolete errors', async () => {
  const page = await load();
  await page.gate();
  page.fill();
  page.click('[name="profile-can-drive"][value="yes"]');
  page.document.getElementById('profile-seats').value = '100';
  page.click('[data-question-key="sharing"] input[value="yes"]');
  await page.submit();
  assert.ok(page.document.getElementById('profile-seats-error').textContent);
  assert.ok(page.document.getElementById('question-7-error').textContent);
  page.click('[name="profile-can-drive"][value="no"]');
  assert.equal(page.document.getElementById('profile-seats-error').textContent, '');
  assert.equal(page.document.getElementById('profile-seats').hasAttribute('aria-invalid'), false);
  page.click('[data-question-key="sharing"] input[value="no"]');
  assert.equal(page.document.getElementById('question-7-error').textContent, '');
  assert.equal(page.document.getElementById('form-errors').textContent, '');
});

test('Stripe changes and selection caps preserve other unresolved field errors', async () => {
  const page = await load({serverError: {'profile.region_code': 'Choose a region.'}});
  await page.gate();
  page.fill();
  await page.submit();
  page.stripeChange({error: {message: 'Check your card number.'}});
  assert.match(page.document.getElementById('form-errors').textContent, /Choose a region/);
  assert.match(page.document.getElementById('form-errors').textContent, /Check your card number/);
  page.stripeChange({});
  assert.equal(page.document.getElementById('form-errors').textContent, 'Choose a region.');
  page.click('[data-question-key="departures"] input[value="Saturday"]');
  page.click('[data-question-key="departures"] input[value="Sunday"]');
  assert.match(page.document.getElementById('form-errors').textContent, /Choose a region/);
  assert.match(page.document.getElementById('form-errors').textContent, /at most 2/);
});

const PROFILE_FIELDS = {
  carpool: ['can_drive', 'seat_capacity', 'bike_capacity', 'hitch_size'],
  region_code: ['region_code'], dietary: ['dietary_restrictions', 'dietary_other'], tent: ['has_tent'],
};
for (const disabled of Object.keys(PROFILE_FIELDS)) {
  test(`registration tolerates missing ${disabled} controls and omits only their payload fields`, async () => {
    const page = await load({disabledBuiltins: [disabled]});
    await page.gate();
    page.fill();
    await page.submit();
    assert.equal(page.posts.length, 1);
    assert.deepEqual(Object.keys(page.posts[0].profile).sort(), Object.entries(PROFILE_FIELDS)
      .filter(([id]) => id !== disabled).flatMap(([, fields]) => fields).sort());
  });
}

test('disabled carpool with optional empty region advances to the next visible question', async () => {
  const page = await load({disabledBuiltins: ['carpool'], optionalRegion: true});
  await page.gate();
  assert.equal(page.document.activeElement.id, 'profile-region');
  page.fill();
  page.document.getElementById('profile-region').value = '';
  await page.submit();
  assert.equal(page.posts[0].profile.region_code, '');
  assert.equal('can_drive' in page.posts[0].profile, false);
});

test('required dietary uses the same group validation and payload as custom multi-choice', async () => {
  const page = await load({requiredDietary: true});
  await page.gate();
  page.fill();
  page.click('[data-dietary][value="Vegan"]');
  await page.submit();
  assert.equal(page.posts.length, 0);
  assert.ok(page.document.getElementById('dietary-options-error').textContent);
  page.click('[data-dietary][value="Other (specify below)"]');
  page.document.getElementById('profile-dietary-other').value = 'Sesame allergy';
  await page.submit();
  assert.deepEqual(page.posts[0].profile.dietary_restrictions, ['Other (specify below)']);
  assert.equal(page.posts[0].profile.dietary_other, 'Sesame allergy');
});

test('a trip with no survey advances to payment and submits an empty profile', async () => {
  const page = await load({noSurvey: true});
  await page.gate();
  assert.equal(page.document.querySelector('[data-step-link][aria-current="step"]').hash, '#payment-section');
  await page.submit();
  assert.deepEqual(page.posts[0].profile, {});
  assert.deepEqual(page.posts[0].answers, {});
});
