'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require('jsdom');

const ROOT = path.resolve(__dirname, '../..');
const SOURCE = fs.readFileSync(
  path.join(ROOT, 'app/static/admin_events.js'), 'utf8');

const TEMPLATES = {
  blank: {price_options: [], custom_questions: []},
  dry_tri: {
    price_options: [
      {name: 'Individual Triathlon', description: '', price_cents: 5500,
       member_price_cents: 3500, participant_roles: ['Participant'],
       active: true}
    ],
    custom_questions: [
      {key: 'course', label: 'Course', type: 'choice', options: ['Long'],
       required: true, price_options: ['Individual Triathlon']}
    ]
  }
};

// Mirrors admin/event_form.html: the editor is driven entirely by the two
// hidden JSON textareas.
function load(priceRows, questionRows, templateKey = 'blank') {
  const dom = new JSDOM(`<!doctype html><body>
    <section id="admin-event-form" data-page="form">
      <form id="event-editor-form">
        <select id="template_key">
          <option value="blank">Blank</option>
          <option value="dry_tri">Dry Tri</option>
        </select>
        <button type="button" id="add-price-option">Add price option</button>
        <div id="price-option-rows"></div>
        <textarea name="price_options_json" id="price_options_json"
          hidden>${JSON.stringify(priceRows)}</textarea>
        <button type="button" id="add-question">Add question</button>
        <div id="custom-question-rows"></div>
        <textarea name="custom_questions_json" id="custom_questions_json"
          hidden>${JSON.stringify(questionRows)}</textarea>
      </form>
    </section>
    <script type="application/json" id="event-template-data">
      ${JSON.stringify(TEMPLATES)}
    </script>
  </body>`);
  dom.window.document.getElementById('template_key').value = templateKey;

  new Function('window', 'document', SOURCE)(dom.window, dom.window.document);
  return dom;
}

function savedQuestions(dom) {
  return JSON.parse(
    dom.window.document.getElementById('custom_questions_json').value
  );
}

function scopeBoxes(dom, questionIndex) {
  const rows = dom.window.document.querySelectorAll(
    '#custom-question-rows .aef-editor-row'
  );
  return Array.from(
    rows[questionIndex].querySelectorAll('[data-field="scope"]')
  );
}

function priceNameInput(dom, index) {
  const rows = dom.window.document.querySelectorAll(
    '#price-option-rows .aef-editor-row'
  );
  return rows[index].querySelector('[data-field="name"]');
}

const TWO_OPTIONS = [
  {id: 1, name: 'Individual Triathlon', description: '', price_cents: 5500,
   member_price_cents: 3500, participant_roles: ['Participant'], active: true},
  {id: 2, name: 'Relay Triathlon', description: '', price_cents: 10500,
   member_price_cents: 7500,
   participant_roles: ['Rollerskier', 'Mountain Biker', 'Trail Runner'],
   active: true}
];

const GENDER_QUESTIONS = [
  {key: 'competition_gender', label: 'Competition gender', type: 'choice',
   options: ['Men', 'Women', 'Non-binary'], required: true, help_text: '',
   price_options: ['Individual Triathlon']},
  {key: 'competition_gender', label: 'Competition gender', type: 'choice',
   options: ['Men', 'Women', 'Mixed'], required: true, help_text: '',
   price_options: ['Relay Triathlon']}
];

test('each question offers a checkbox per price option', () => {
  const dom = load(TWO_OPTIONS, GENDER_QUESTIONS);

  const boxes = scopeBoxes(dom, 0);
  assert.deepEqual(boxes.map(box => box.value),
    ['Individual Triathlon', 'Relay Triathlon']);
  assert.deepEqual(boxes.map(box => box.checked), [true, false]);
  assert.deepEqual(scopeBoxes(dom, 1).map(box => box.checked), [false, true]);
});

test('checking a box records that option in the saved scope', () => {
  const dom = load(TWO_OPTIONS, GENDER_QUESTIONS);
  const box = scopeBoxes(dom, 0)[1];

  box.checked = true;
  box.dispatchEvent(new dom.window.Event('change', {bubbles: true}));

  assert.deepEqual(savedQuestions(dom)[0].price_options,
    ['Individual Triathlon', 'Relay Triathlon']);
});

test('unchecking every box means the question applies to all options', () => {
  const dom = load(TWO_OPTIONS, GENDER_QUESTIONS);
  const box = scopeBoxes(dom, 0)[0];

  box.checked = false;
  box.dispatchEvent(new dom.window.Event('change', {bubbles: true}));

  assert.deepEqual(savedQuestions(dom)[0].price_options, []);
});

test('renaming a price option carries its question scopes along', () => {
  const dom = load(TWO_OPTIONS, GENDER_QUESTIONS);
  const nameInput = priceNameInput(dom, 1);

  nameInput.value = 'Relay Team';
  nameInput.dispatchEvent(new dom.window.Event('change', {bubbles: true}));

  assert.deepEqual(savedQuestions(dom)[1].price_options, ['Relay Team']);
  assert.deepEqual(scopeBoxes(dom, 1).map(box => box.value),
    ['Individual Triathlon', 'Relay Team']);
  assert.deepEqual(scopeBoxes(dom, 1).map(box => box.checked), [false, true]);
});

test('removing a price option drops it from every question scope', () => {
  const dom = load(TWO_OPTIONS, GENDER_QUESTIONS);
  const rows = dom.window.document.querySelectorAll(
    '#price-option-rows .aef-editor-row'
  );

  rows[1].querySelector('.aef-remove').click();

  assert.deepEqual(savedQuestions(dom)[1].price_options, []);
  assert.deepEqual(scopeBoxes(dom, 0).map(box => box.value),
    ['Individual Triathlon']);
});

test('adding a price option offers it to existing questions', () => {
  const dom = load(TWO_OPTIONS, GENDER_QUESTIONS);

  dom.window.document.getElementById('add-price-option').click();

  // The new row has no name yet, so it is not offered until it is named.
  assert.deepEqual(scopeBoxes(dom, 0).map(box => box.value),
    ['Individual Triathlon', 'Relay Triathlon']);

  const nameInput = priceNameInput(dom, 2);
  nameInput.value = 'Run-only 6K';
  nameInput.dispatchEvent(new dom.window.Event('change', {bubbles: true}));

  assert.deepEqual(scopeBoxes(dom, 0).map(box => box.value),
    ['Individual Triathlon', 'Relay Triathlon', 'Run-only 6K']);
});

test('a question editor with no price options explains what to do', () => {
  const dom = load([], GENDER_QUESTIONS);
  const rows = dom.window.document.querySelectorAll(
    '#custom-question-rows .aef-editor-row'
  );

  assert.match(rows[0].textContent, /Add a price option first/);
  assert.equal(scopeBoxes(dom, 0).length, 0);
});

test('applying a template over existing data asks before replacing it', () => {
  const dom = load(TWO_OPTIONS, GENDER_QUESTIONS);
  const select = dom.window.document.getElementById('template_key');
  const asked = [];
  dom.window.confirm = message => {
    asked.push(message);
    return false;
  };

  select.value = 'dry_tri';
  select.dispatchEvent(new dom.window.Event('change', {bubbles: true}));

  assert.equal(asked.length, 1);
  assert.match(asked[0], /replaces all price options/);
  // Declining leaves the member prices and the selector untouched.
  assert.equal(select.value, 'blank');
  assert.deepEqual(
    JSON.parse(
      dom.window.document.getElementById('price_options_json').value
    ).map(option => option.member_price_cents),
    [3500, 7500]
  );
});

test('confirming the template swap replaces price options and questions', () => {
  const dom = load(TWO_OPTIONS, GENDER_QUESTIONS);
  const select = dom.window.document.getElementById('template_key');
  dom.window.confirm = () => true;

  select.value = 'dry_tri';
  select.dispatchEvent(new dom.window.Event('change', {bubbles: true}));

  assert.deepEqual(
    JSON.parse(
      dom.window.document.getElementById('price_options_json').value
    ).map(option => option.name),
    ['Individual Triathlon']
  );
  assert.deepEqual(savedQuestions(dom).map(question => question.key),
    ['course']);
  assert.equal(select.value, 'dry_tri');
});

test('an empty editor applies a template without prompting', () => {
  const dom = load([], []);
  const select = dom.window.document.getElementById('template_key');
  let asked = 0;
  dom.window.confirm = () => {
    asked += 1;
    return true;
  };

  select.value = 'dry_tri';
  select.dispatchEvent(new dom.window.Event('change', {bubbles: true}));

  assert.equal(asked, 0);
  assert.deepEqual(savedQuestions(dom).map(question => question.key),
    ['course']);
});
