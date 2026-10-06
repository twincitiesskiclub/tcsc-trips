'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require('jsdom');

const ROOT = path.resolve(__dirname, '../..');
const SOURCE = fs.readFileSync(
  path.join(ROOT, 'app/static/event_registration.js'), 'utf8');

// A free option keeps Stripe out of the submit path.
const OPTIONS = [
  {
    id: 1,
    name: 'Volunteer',
    description: 'Help on course',
    priceCents: 0,
    memberPriceCents: null,
    participantRoles: ['Volunteer']
  }
];

function load() {
  const data = {slug: 'dry-tri-2026', priceOptions: OPTIONS, customQuestions: []};
  const dom = new JSDOM(`<!doctype html><body>
    <script id="event-registration-data" type="application/json">
      ${JSON.stringify(data)}
    </script>
    <form id="event-registration-form" class="payment-view" novalidate>
      <div id="price-options">
        <label class="price-option-container">
          <input type="radio" name="price_option_id" value="1" checked required>
        </label>
      </div>
      <p id="option-description"></p>
      <div class="form-field hidden" id="team-name-field">
        <input type="text" id="team-name" class="form-input">
      </div>
      <div id="participants-container"></div>
      <input type="text" id="emergency-contact-name" required>
      <input type="tel" id="emergency-contact-phone" required>
      <div class="checkbox-group" id="waiver-field">
        <input type="checkbox" id="waiver-accepted" required>
        <label for="waiver-accepted">I agree</label>
      </div>
      <input type="text" id="discount-code">
      <button type="button" id="discount-apply">Apply</button>
      <div id="card-field"><div id="card-element"></div></div>
      <div class="card-error" id="form-errors" role="alert"></div>
      <button id="submit" type="submit">
        <span class="spinner hidden" id="spinner"></span>
        <span id="button-text">Continue</span>
      </button>
    </form>
    <div class="completed-view hidden"><h1>Done</h1>
      <p id="confirmation-message"></p></div>
  </body>`, {url: 'https://example.test/events/dry-tri-2026'});

  const {window} = dom;
  window.scrollTo = () => {};
  const calls = [];
  // The page calls bare fetch(), which under new Function resolves to
  // Node's global rather than window.fetch. Stub the global.
  globalThis.fetch = async (url, options) => {
    calls.push({url, body: JSON.parse(options.body)});
    return {
      ok: false,
      json: async () => ({
        error: {waiver_accepted: 'You must accept the waiver to register.'}
      })
    };
  };

  new Function('window', 'document', SOURCE)(window, window.document);
  return {dom, calls};
}

function fillRequiredText(document) {
  document.querySelectorAll('input[required]').forEach(input => {
    if (input.type === 'checkbox' || input.type === 'radio') return;
    input.value = input.type === 'date' ? '1990-01-01' : 'x@example.com';
  });
}

async function submit(dom) {
  const {window} = dom;
  const form = window.document.getElementById('event-registration-form');
  form.dispatchEvent(new window.Event('submit', {cancelable: true}));
  // Let the async submit handler run through fetch and json().
  await new Promise(resolve => setTimeout(resolve, 0));
  await new Promise(resolve => setTimeout(resolve, 0));
}

test('the payload carries the waiver checkbox and the server error lands on it', async () => {
  const {dom, calls} = load();
  const document = dom.window.document;
  fillRequiredText(document);
  document.getElementById('waiver-accepted').checked = true;

  await submit(dom);

  assert.equal(calls.length, 1);
  assert.equal(calls[0].body.waiver_accepted, true);
  assert.ok(
    document.getElementById('waiver-field').classList.contains('field-error')
  );
  assert.match(
    document.getElementById('form-errors').textContent,
    /accept the waiver/
  );
});

test('an unchecked waiver never reaches the server', async () => {
  const {dom, calls} = load();
  fillRequiredText(dom.window.document);

  await submit(dom);

  assert.equal(calls.length, 0);
});
