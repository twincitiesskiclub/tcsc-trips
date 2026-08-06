'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require('jsdom');

const ROOT = path.resolve(__dirname, '../..');
const SOURCE = fs.readFileSync(
  path.join(ROOT, 'app/static/event_registration.js'), 'utf8');

const OPTIONS = [
  {
    id: 1,
    name: 'Individual Triathlon',
    description: 'Solo',
    priceCents: 0,
    memberPriceCents: null,
    participantRoles: ['Participant']
  },
  {
    id: 2,
    name: 'Relay Triathlon',
    description: 'Team of three',
    priceCents: 0,
    memberPriceCents: null,
    participantRoles: ['Rollerskier', 'Mountain Biker', 'Trail Runner']
  },
  {
    id: 3,
    name: 'Run-only 6K',
    description: 'Just the run',
    priceCents: 0,
    memberPriceCents: null,
    participantRoles: ['Participant']
  }
];

// Mirrors the markup events/registration.html emits, including the
// index-based ids that let one key repeat across scopes.
function questionMarkup(questions) {
  return questions.map((question, index) => `
    <div class="form-field" data-question-field="${index}"
         data-question-scope='${JSON.stringify(question.scope)}'>
      <label class="form-field__label" for="question-${index}">
        ${question.label}
      </label>
      <select id="question-${index}" class="form-input"
              data-question-key="${question.key}"
              ${question.required ? 'required' : ''}>
        <option value="">Select an option</option>
        ${(question.options || []).map(
          choice => `<option value="${choice}">${choice}</option>`
        ).join('')}
      </select>
    </div>`).join('');
}

function load(questions, priceOptions = OPTIONS) {
  const data = {slug: 'dry-tri-2026', priceOptions, customQuestions: []};
  const dom = new JSDOM(`<!doctype html><body>
    <script id="event-registration-data" type="application/json">
      ${JSON.stringify(data)}
    </script>
    <form id="event-registration-form" novalidate>
      <div id="price-options">
        ${priceOptions.map((option, index) => `
          <label class="price-option-container">
            <input type="radio" name="price_option_id" value="${option.id}"
                   ${index === 0 ? 'checked' : ''} required>
          </label>`).join('')}
      </div>
      <p id="option-description"></p>
      <div class="form-field hidden" id="team-name-field">
        <input type="text" id="team-name" class="form-input">
      </div>
      <div id="participants-container"></div>
      <section class="form-section" id="event-questions">
        <h2 id="event-questions-title">Event questions</h2>
        ${questionMarkup(questions)}
      </section>
      <input type="text" id="discount-code">
      <button type="button" id="discount-apply">Apply</button>
      <span id="discount-message"></span>
      <div id="card-field"><div id="card-element"></div></div>
      <div class="card-error" id="form-errors" role="alert"></div>
      <button id="submit" type="submit">
        <span class="spinner hidden" id="spinner"></span>
        <span id="button-text">Continue</span>
      </button>
    </form>
  </body>`);

  new Function('window', 'document', SOURCE)(dom.window, dom.window.document);
  return dom;
}

function select(dom, optionId) {
  const radio = dom.window.document.querySelector(
    `input[name="price_option_id"][value="${optionId}"]`
  );
  radio.checked = true;
  radio.dispatchEvent(new dom.window.Event('change', {bubbles: true}));
}

function stateOf(dom, index) {
  const document = dom.window.document;
  const field = document.querySelector(`[data-question-field="${index}"]`);
  const input = document.getElementById(`question-${index}`);
  return {hidden: field.classList.contains('hidden'), disabled: input.disabled};
}

const DRY_TRI_QUESTIONS = [
  {
    key: 'competition_gender',
    label: 'Competition gender',
    options: ['Men', 'Women', 'Non-binary'],
    required: true,
    scope: ['Individual Triathlon', 'Run-only 6K']
  },
  {
    key: 'competition_gender',
    label: 'Competition gender',
    options: ['Men', 'Women', 'Mixed'],
    required: true,
    scope: ['Relay Triathlon']
  },
  {
    key: 'course',
    label: 'Course',
    options: ['Long', 'Short'],
    required: true,
    scope: ['Individual Triathlon', 'Relay Triathlon']
  },
  {key: 'club', label: 'Club', options: ['TCSC'], required: false, scope: []}
];

test('individual entry gets the non-binary gender question only', () => {
  const dom = load(DRY_TRI_QUESTIONS);

  assert.deepEqual(stateOf(dom, 0), {hidden: false, disabled: false});
  assert.deepEqual(stateOf(dom, 1), {hidden: true, disabled: true});
});

test('relay entry gets the mixed gender question only', () => {
  const dom = load(DRY_TRI_QUESTIONS);
  select(dom, 2);

  assert.deepEqual(stateOf(dom, 0), {hidden: true, disabled: true});
  assert.deepEqual(stateOf(dom, 1), {hidden: false, disabled: false});
});

test('run-only entry is asked neither course nor a mixed gender', () => {
  const dom = load(DRY_TRI_QUESTIONS);
  select(dom, 3);

  assert.deepEqual(stateOf(dom, 0), {hidden: false, disabled: false});
  assert.deepEqual(stateOf(dom, 1), {hidden: true, disabled: true});
  assert.deepEqual(stateOf(dom, 2), {hidden: true, disabled: true});
});

test('an unscoped question applies to every entry option', () => {
  const dom = load(DRY_TRI_QUESTIONS);

  for (const optionId of [1, 2, 3]) {
    select(dom, optionId);
    assert.deepEqual(stateOf(dom, 3), {hidden: false, disabled: false});
  }
});

test('a scope naming no surviving option falls open to applying', () => {
  const dom = load([
    {key: 'club', label: 'Club', options: ['TCSC'], required: false,
     scope: ['Renamed Away']}
  ]);

  assert.deepEqual(stateOf(dom, 0), {hidden: false, disabled: false});
});

test('a scope is honoured while any named option still exists', () => {
  const dom = load([
    {key: 'club', label: 'Club', options: ['TCSC'], required: false,
     scope: ['Relay Triathlon', 'Renamed Away']}
  ]);

  assert.deepEqual(stateOf(dom, 0), {hidden: true, disabled: true});
  select(dom, 2);
  assert.deepEqual(stateOf(dom, 0), {hidden: false, disabled: false});
});

test('malformed scope data applies the question rather than dropping it', () => {
  const dom = load([
    {key: 'club', label: 'Club', options: ['TCSC'], required: false, scope: []}
  ]);
  const field = dom.window.document.querySelector('[data-question-field="0"]');
  field.dataset.questionScope = 'not json';
  select(dom, 2);

  assert.deepEqual(stateOf(dom, 0), {hidden: false, disabled: false});
});

test('an out-of-scope answer already typed is kept but not submitted', () => {
  const dom = load(DRY_TRI_QUESTIONS);
  const document = dom.window.document;

  document.getElementById('question-2').value = 'Long';
  select(dom, 3);

  // Preserved in the DOM for a switch back, but excluded from the payload.
  assert.equal(document.getElementById('question-2').value, 'Long');
  const submitted = Array.from(
    document.querySelectorAll('[data-question-key]:not([disabled])')
  ).map(input => input.dataset.questionKey);
  assert.deepEqual(submitted, ['competition_gender', 'club']);

  select(dom, 1);
  assert.equal(document.getElementById('question-2').value, 'Long');
  assert.equal(document.getElementById('question-2').disabled, false);
});

test('team name is required and enabled only for a multi-role option', () => {
  const dom = load(DRY_TRI_QUESTIONS);
  const document = dom.window.document;
  const field = document.getElementById('team-name-field');
  const input = document.getElementById('team-name');

  assert.equal(field.classList.contains('hidden'), true);
  assert.equal(input.required, false);
  assert.equal(input.disabled, true);

  select(dom, 2);
  assert.equal(field.classList.contains('hidden'), false);
  assert.equal(input.required, true);
  assert.equal(input.disabled, false);
});

test('the questions section hides when nothing is in scope', () => {
  const dom = load([
    {key: 'course', label: 'Course', options: ['Long'], required: true,
     scope: ['Relay Triathlon']}
  ]);
  const section = dom.window.document.getElementById('event-questions');

  assert.equal(section.classList.contains('hidden'), true);

  select(dom, 2);
  assert.equal(section.classList.contains('hidden'), false);
});

test('every participant card collects its own emergency contact', () => {
  const dom = load([]);
  select(dom, 2);  // Relay Triathlon renders three cards

  const groups = dom.window.document.querySelectorAll('[data-participant]');
  assert.equal(groups.length, 3);
  groups.forEach(group => {
    assert.ok(group.querySelector(
      '[data-participant-field="emergency_contact_name"]'));
    assert.ok(group.querySelector(
      '[data-participant-field="emergency_contact_phone"]'));
  });
});

test('emergency contact values survive switching options', () => {
  const dom = load([]);
  const document = dom.window.document;
  document.querySelector(
    '[data-participant="0"] [data-participant-field="emergency_contact_name"]'
  ).value = 'Pat Contact';

  select(dom, 2);
  select(dom, 1);

  assert.equal(
    document.querySelector(
      '[data-participant="0"] ' +
      '[data-participant-field="emergency_contact_name"]'
    ).value,
    'Pat Contact');
});
