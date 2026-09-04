'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const {JSDOM} = require('jsdom');

const ROOT = path.resolve(__dirname, '../..');
const SOURCE = fs.readFileSync(path.join(ROOT, 'app/static/admin_trip_questions.js'), 'utf8');
const VENV = path.join(ROOT, '.venv-linux/bin/python');
const PYTHON = process.env.PYTHON || (fs.existsSync(VENV) ? VENV : 'python3');
// Read the actual YAML, including its shared anchors, and the server's key list.
// run_path avoids initializing the Flask app or connecting to a database.
const FIXTURES = JSON.parse(execFileSync(PYTHON, ['-c', `
import json, runpy
schema = runpy.run_path('app/trips/questions.py')
print(json.dumps({'templates': schema['load_trip_templates'](),
                  'reserved': sorted(schema['RESERVED_QUESTION_KEYS'])}))
`], {cwd: ROOT, encoding: 'utf8'}));
const NORTH_SHORE = FIXTURES.templates.north_shore.custom_questions;
const PARENT = {key: 'sharing', label: 'Will you share a bed?', type: 'yes_no', required: true};
const FOLLOW_UP = {key: 'share_with', label: 'Who with?', type: 'text', required: false,
  visible_if: {question: 'sharing', equals: 'yes'}};
const TEXT = {key: 'notes', label: 'Anything else?', type: 'text', required: false};

function load(questions = [], extraTemplates = {}) {
  const dom = new JSDOM(`<!doctype html><body><form id="trip-editor-form">
    <select id="template_key"><option value="">Choose a template</option></select>
    <input type="hidden" name="template_key" id="applied-trip-template" value="blank">
    <div id="trip-template-preview" hidden></div>
    <div id="trip-question-rows"></div>
    <button type="button" id="add-trip-question">Add question</button>
    <p id="trip-question-status" role="status"></p>
    <textarea name="custom_questions_json" id="custom_questions_json" hidden></textarea>
    <div id="trip-question-errors" role="alert" hidden></div>
    <button type="submit">Save trip</button>
    <script type="application/json" id="trip-template-data"></script>
  </form></body>`);
  const document = dom.window.document;
  document.getElementById('custom_questions_json').value = JSON.stringify(questions);
  const templates = {...FIXTURES.templates, ...extraTemplates};
  document.getElementById('trip-template-data').textContent = JSON.stringify(templates);
  for (const [key, template] of Object.entries(templates)) {
    const option = document.createElement('option');
    option.value = key;
    option.textContent = template.name;
    document.getElementById('template_key').appendChild(option);
  }
  new Function('document', SOURCE)(document);
  return dom;
}

function saved(dom) {
  return JSON.parse(dom.window.document.getElementById('custom_questions_json').value);
}

function card(dom, index) {
  return dom.window.document.querySelectorAll('.tq-card')[index];
}

function field(dom, index, name) {
  return card(dom, index).querySelector(`[data-field="${name}"]`);
}

function edit(dom, index, name, value) {
  const control = field(dom, index, name);
  if (control.type === 'checkbox') control.checked = value;
  else control.value = value;
  control.dispatchEvent(new dom.window.Event('input', {bubbles: true}));
  return control;
}

function submit(dom) {
  const event = new dom.window.Event('submit', {bubbles: true, cancelable: true});
  dom.window.document.getElementById('trip-editor-form').dispatchEvent(event);
  return !event.defaultPrevented;
}

function add(dom, label) {
  dom.window.document.getElementById('add-trip-question').click();
  const index = saved(dom).length - 1;
  if (label !== undefined) edit(dom, index, 'label', label);
  return index;
}

function chooseTemplate(dom, key) {
  const select = dom.window.document.getElementById('template_key');
  select.value = key;
  select.dispatchEvent(new dom.window.Event('change', {bubbles: true}));
  return dom.window.document.getElementById('trip-template-preview');
}

function templateAction(dom, label) {
  const buttons = dom.window.document.querySelectorAll('#trip-template-preview button');
  const target = Array.from(buttons).find(button => button.textContent === label);
  assert.ok(target, `Missing template action: ${label}`);
  target.click();
}

function move(dom, index, direction) {
  const buttons = card(dom, index).querySelectorAll('.tq-moves button');
  return buttons[direction === 'up' ? 0 : 1];
}

function assertServerAccepts(questions) {
  execFileSync(PYTHON, ['-c', `
import json, runpy, sys
runpy.run_path('app/trips/questions.py')['validate_questions'](json.load(sys.stdin))
`], {cwd: ROOT, input: JSON.stringify(questions), encoding: 'utf8'});
}

test('new labels generate normalized keys, numeric suffixes and an empty-label fallback', () => {
  const dom = load();
  add(dom, '  Éarly birds: departure windows?!  ');
  add(dom, 'Early birds departure windows');
  add(dom, 'Early birds departure windows');
  add(dom, '???');
  add(dom, 'Who’s driving?');
  assert.deepEqual(saved(dom).map(q => q.key), [
    'early_birds_departure_windows', 'early_birds_departure_windows_2',
    'early_birds_departure_windows_3', 'question', 'whos_driving'
  ]);
  edit(dom, 0, 'label', 'Leave on Friday');
  assert.equal(saved(dom)[0].key, 'leave_on_friday');
});

test('generated keys avoid every reserved server key and existing suffixes', () => {
  const dom = load([{...TEXT, key: 'email_2'}]);
  for (const key of FIXTURES.reserved) {
    const index = add(dom, key.replaceAll('_', ' '));
    assert.equal(saved(dom)[index].key, key === 'email' ? 'email_3' : `${key}_2`);
  }
  assertServerAccepts(saved(dom));
});

test('saved keys and manual overrides stay stable when labels change', () => {
  const dom = load([TEXT]);
  edit(dom, 0, 'label', 'Tell us more');
  assert.equal(saved(dom)[0].key, 'notes');
  const index = add(dom, 'Bed share');
  edit(dom, index, 'key', 'bedmates');
  edit(dom, index, 'label', 'Preferred bedmates');
  assert.equal(saved(dom)[index].key, 'bedmates');
  assert.equal(card(dom, index).querySelector('.tq-advanced').open, false);
});

test('new cards open and focus the question; existing cards start collapsed with summaries', () => {
  const dom = load(NORTH_SHORE);
  for (let index = 0; index < NORTH_SHORE.length; index++) {
    assert.equal(card(dom, index).querySelector('.tq-toggle').getAttribute('aria-expanded'), 'false');
    assert.equal(card(dom, index).querySelector('.tq-card-body').hidden, true);
  }
  assert.match(card(dom, 0).querySelector('.tq-summary').textContent, /Multiple choiceRequired8 options/);
  const index = add(dom);
  assert.equal(card(dom, index).querySelector('.tq-toggle').getAttribute('aria-expanded'), 'true');
  assert.equal(dom.window.document.activeElement, field(dom, index, 'label'));
  assert.equal(card(dom, index).querySelector('.tq-card-body').hidden, false);
});

test('only relevant fields show for each answer type and earlier yes or no questions', () => {
  const dom = load([TEXT, PARENT, FOLLOW_UP]);
  const hiddenField = (index, name) => field(dom, index, name).closest('.aef-field').hidden;
  assert.equal(hiddenField(0, 'options'), true);
  assert.equal(hiddenField(0, 'max-selections'), true);
  assert.equal(hiddenField(0, 'visible-if'), true);
  assert.equal(hiddenField(1, 'visible-if'), true);
  assert.equal(hiddenField(1, 'options'), true);
  assert.equal(hiddenField(2, 'visible-if'), false);
  assert.match(field(dom, 2, 'visible-if').textContent, /Will you share a bed\?: yes/);
  edit(dom, 0, 'type', 'choice');
  assert.equal(hiddenField(0, 'options'), false);
  assert.equal(hiddenField(0, 'max-selections'), true);
  edit(dom, 0, 'type', 'multi_choice');
  assert.equal(hiddenField(0, 'max-selections'), false);
  edit(dom, 0, 'type', 'yes_no');
  assert.equal(hiddenField(0, 'options'), true);
  assert.equal(hiddenField(0, 'max-selections'), true);
  assert.equal(hiddenField(1, 'visible-if'), false);
});

test('sync writes only schema fields, trims blanks and preserves textarea input and caret', () => {
  const dom = load([PARENT, FOLLOW_UP]);
  const index = add(dom, ' Activities ');
  edit(dom, index, 'type', 'multi_choice');
  const raw = '  Hiking \n\n Biking  \n   \nSwimming\n';
  const options = edit(dom, index, 'options', raw);
  options.setSelectionRange(4, 4);
  options.dispatchEvent(new dom.window.Event('input', {bubbles: true}));
  assert.equal(field(dom, index, 'options'), options);
  assert.equal(options.value, raw);
  assert.equal(options.selectionStart, 4);
  assert.match(card(dom, index).textContent, /3 options/);
  edit(dom, index, 'max-selections', '2');
  edit(dom, index, 'help-text', ' Pick your favorites.  ');
  edit(dom, index, 'required', true);
  edit(dom, index, 'visible-if', JSON.stringify({question: 'sharing', equals: 'no'}));
  assert.deepEqual(saved(dom)[index], {
    key: 'activities', label: 'Activities', type: 'multi_choice', required: true,
    options: ['Hiking', 'Biking', 'Swimming'], max_selections: 2,
    help_text: 'Pick your favorites.', visible_if: {question: 'sharing', equals: 'no'}
  });
  assertServerAccepts(saved(dom));
  edit(dom, index, 'max-selections', '');
  edit(dom, index, 'help-text', '  ');
  edit(dom, index, 'visible-if', '');
  assert.deepEqual(saved(dom)[index], {
    key: 'activities', label: 'Activities', type: 'multi_choice', required: true,
    options: ['Hiking', 'Biking', 'Swimming']
  });
  edit(dom, index, 'type', 'text');
  assert.deepEqual(saved(dom)[index], {key: 'activities', label: 'Activities', type: 'text', required: true});
  edit(dom, index, 'type', 'choice');
  assert.deepEqual(saved(dom)[index].options, ['Hiking', 'Biking', 'Swimming']);
  assert.equal('max_selections' in saved(dom)[index], false);
  assert.equal(submit(dom), true);
});

test('North Shore YAML questions round trip losslessly through edit, reorder and submit', () => {
  const dom = load(NORTH_SHORE);
  assert.deepEqual(saved(dom), NORTH_SHORE);
  card(dom, 0).querySelector('.tq-toggle').click();
  edit(dom, 0, 'label', 'Departure windows');
  edit(dom, 0, 'label', NORTH_SHORE[0].label);
  move(dom, 0, 'down').click();
  move(dom, 1, 'up').click();
  assert.equal(submit(dom), true);
  assert.deepEqual(saved(dom), NORTH_SHORE);
  assertServerAccepts(saved(dom));
});

test('moves preserve conditions, block crossing a parent and retain focus and open state', () => {
  const dom = load([PARENT, TEXT, FOLLOW_UP]);
  card(dom, 2).querySelector('.tq-toggle').click();
  move(dom, 2, 'up').click();
  assert.deepEqual(saved(dom).map(q => q.key), ['sharing', 'share_with', 'notes']);
  assert.equal(card(dom, 1).querySelector('.tq-card-body').hidden, false);
  assert.equal(dom.window.document.activeElement, card(dom, 1).querySelector('.tq-toggle'));
  assert.equal(move(dom, 1, 'up').disabled, true);
  assert.equal(move(dom, 0, 'down').disabled, true);
  assert.equal(card(dom, 1).querySelector('.tq-order-hint').hidden, false);
  move(dom, 1, 'up').click();
  assert.deepEqual(saved(dom)[1].visible_if, FOLLOW_UP.visible_if);
  move(dom, 1, 'down').click();
  assert.equal(move(dom, 0, 'down').disabled, false);
  move(dom, 0, 'down').click();
  assert.deepEqual(saved(dom).map(q => q.key), ['notes', 'sharing', 'share_with']);
  assert.equal(submit(dom), true);
  assertServerAccepts(saved(dom));
});

test('renaming a parent updates follow-ups, including clearing and retyping a key', () => {
  const dom = load([PARENT, FOLLOW_UP]);
  edit(dom, 0, 'key', '');
  edit(dom, 0, 'key', 'bed_share');
  assert.deepEqual(saved(dom)[1].visible_if, {question: 'bed_share', equals: 'yes'});
  assert.equal(submit(dom), true);
  assert.equal(field(dom, 0, 'type').disabled, true);
  assert.equal(card(dom, 0).querySelector('.aef-remove').disabled, true);
  edit(dom, 1, 'visible-if', '');
  assert.equal(field(dom, 0, 'type').disabled, false);
  assert.equal(card(dom, 0).querySelector('.aef-remove').disabled, false);
  card(dom, 0).querySelector('.aef-remove').click();
  assert.equal(saved(dom).length, 1);
  assert.equal('visible_if' in saved(dom)[0], false);
});

test('fixing a duplicate parent key keeps the follow-up attached to the same question', () => {
  const dom = load([PARENT, TEXT, FOLLOW_UP]);
  edit(dom, 0, 'key', 'notes');
  assert.equal(submit(dom), false);
  edit(dom, 0, 'key', 'bed_share');
  assert.deepEqual(saved(dom)[2].visible_if, {question: 'bed_share', equals: 'yes'});
  assert.equal(submit(dom), true);
});

test('submit catches duplicate keys and empty options inline, opens Advanced and links errors', () => {
  const dom = load([TEXT, {...TEXT, label: 'Choose a chore', type: 'choice', options: []}]);
  assert.equal(submit(dom), false);
  assert.equal(field(dom, 0, 'key').getAttribute('aria-invalid'), 'true');
  assert.equal(field(dom, 1, 'key').getAttribute('aria-invalid'), 'true');
  assert.equal(field(dom, 1, 'options').getAttribute('aria-invalid'), 'true');
  assert.equal(card(dom, 0).querySelector('.tq-advanced').open, true);
  assert.equal(dom.window.document.activeElement, field(dom, 0, 'key'));
  const summary = dom.window.document.getElementById('trip-question-errors');
  assert.equal(summary.hidden, false);
  assert.match(summary.textContent, /Fix 3 issues/);
  assert.match(field(dom, 1, 'options').closest('.aef-field').textContent, /Add at least one option/);
  Array.from(summary.querySelectorAll('button')).at(-1).click();
  assert.equal(dom.window.document.activeElement, field(dom, 1, 'options'));
  edit(dom, 1, 'key', 'chores');
  edit(dom, 1, 'options', 'Cooking\nCleaning');
  assert.equal(summary.hidden, true);
  assert.equal(submit(dom), true);
});

test('live validation catches a manual duplicate and blank options before submitting', () => {
  const dom = load([TEXT]);
  const index = add(dom, 'Chores');
  edit(dom, index, 'key', 'notes');
  edit(dom, index, 'type', 'choice');
  edit(dom, index, 'options', ' \n\n ');
  assert.equal(field(dom, index, 'key').getAttribute('aria-invalid'), 'true');
  assert.equal(field(dom, index, 'options').getAttribute('aria-invalid'), 'true');
});

test('validation catches missing labels, invalid and reserved keys, answer types and invalid caps', () => {
  const dom = load([{key: 'bad-key', label: '', type: 'unknown', required: false}]);
  assert.equal(submit(dom), false);
  for (const name of ['label', 'key', 'type']) {
    assert.equal(field(dom, 0, name).getAttribute('aria-invalid'), 'true');
  }
  edit(dom, 0, 'label', 'Activities');
  edit(dom, 0, 'key', 'email');
  assert.match(field(dom, 0, 'key').closest('.aef-field').textContent, /used by the system/);
  edit(dom, 0, 'key', 'activities');
  edit(dom, 0, 'type', 'multi_choice');
  edit(dom, 0, 'options', 'Hiking');
  for (const cap of ['0', '-2', '1.5', 'nope', 'Infinity']) {
    edit(dom, 0, 'max-selections', cap);
    assert.equal(submit(dom), false, cap);
    assert.equal(field(dom, 0, 'max-selections').getAttribute('aria-invalid'), 'true');
    assert.notEqual(saved(dom)[0].max_selections, null);
  }
  edit(dom, 0, 'max-selections', '1');
  assert.equal(submit(dom), true);
});

test('invalid conditions remain visible for repair instead of being silently cleared', () => {
  const invalids = [
    {question: 'missing', equals: 'yes'}, {question: 'notes', equals: 'no'},
    {question: 'sharing', equals: 'maybe'}, {question: 'sharing', equals: 'yes', extra: true}
  ];
  for (const condition of invalids) {
    const dom = load([TEXT, PARENT, {...FOLLOW_UP, visible_if: condition}]);
    assert.equal(submit(dom), false);
    assert.deepEqual(saved(dom)[2].visible_if, condition);
    assert.equal(field(dom, 2, 'visible-if').getAttribute('aria-invalid'), 'true');
    edit(dom, 2, 'visible-if', '');
    assert.equal(submit(dom), true);
  }
  const dom = load([FOLLOW_UP, PARENT]);
  assert.equal(field(dom, 0, 'visible-if').closest('.aef-field').hidden, false);
  assert.equal(submit(dom), false);
  move(dom, 0, 'down').click();
  assert.equal(submit(dom), true);
});

test('selecting and cancelling a template only previews it; Replace uses the exact template', () => {
  const dom = load([TEXT]);
  const panel = chooseTemplate(dom, 'north_shore');
  assert.equal(panel.hidden, false);
  assert.deepEqual(Array.from(panel.querySelectorAll('li'), li => li.textContent), NORTH_SHORE.map(q => q.label));
  assert.deepEqual(saved(dom), [TEXT]);
  assert.equal(dom.window.document.getElementById('applied-trip-template').value, 'blank');
  templateAction(dom, 'Cancel');
  assert.equal(panel.hidden, true);
  assert.deepEqual(saved(dom), [TEXT]);
  chooseTemplate(dom, 'north_shore');
  templateAction(dom, 'Replace questions');
  assert.deepEqual(saved(dom), NORTH_SHORE);
  assert.equal(dom.window.document.getElementById('applied-trip-template').value, 'north_shore');
  assert.equal(submit(dom), true);
});

test('an empty editor previews the template before explicitly adding its questions', () => {
  const dom = load();
  chooseTemplate(dom, 'north_shore');
  assert.deepEqual(saved(dom), []);
  templateAction(dom, 'Add 5 questions');
  assert.deepEqual(saved(dom), NORTH_SHORE);
});

test('Append preserves existing questions and remaps template keys and conditions together', () => {
  const template = {name: 'Bed sharing', custom_questions: [PARENT, FOLLOW_UP,
    {...TEXT, key: 'sharing_2'}]};
  const existing = [PARENT, FOLLOW_UP, {...TEXT, key: 'sharing_2'}];
  const dom = load(existing, {sharing: template});
  chooseTemplate(dom, 'sharing');
  templateAction(dom, 'Append questions');
  const questions = saved(dom);
  assert.deepEqual(questions.slice(0, 3), existing);
  assert.deepEqual(questions.slice(3).map(q => q.key), ['sharing_3', 'share_with_2', 'sharing_2_2']);
  assert.deepEqual(questions[4].visible_if, {question: 'sharing_3', equals: 'yes'});
  assert.equal(dom.window.document.getElementById('applied-trip-template').value, 'blank');
  assert.equal(submit(dom), true);
  assertServerAccepts(questions);
});

test('registrant preview shows plain text, help, choices and limits without contributing form fields', () => {
  const dom = load(NORTH_SHORE);
  const preview = card(dom, 0).querySelector('.tq-preview');
  preview.open = true;
  preview.dispatchEvent(new dom.window.Event('toggle'));
  assert.match(preview.textContent, /Select every window that could work for you/);
  assert.match(preview.textContent, /Pick up to 8/);
  assert.equal(preview.querySelectorAll('input[type="checkbox"]').length, 8);
  edit(dom, 0, 'label', '<img src=x onerror=alert(1)>');
  assert.equal(preview.querySelector('img'), null);
  assert.match(preview.textContent, /<img src=x onerror=alert\(1\)>/);
  const data = new dom.window.FormData(dom.window.document.getElementById('trip-editor-form'));
  assert.deepEqual(Array.from(data.keys()), ['template_key', 'custom_questions_json']);
});
