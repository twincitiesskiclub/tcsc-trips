'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require('jsdom');

const source = fs.readFileSync(path.join(__dirname, '../../app/static/trip_survey.js'), 'utf8');
const surveyModule = import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));

async function load(questions = '') {
  const dom = new JSDOM(`<form>
    <div id="dietary-options"></div>
    <label><input type="radio" name="profile-can-drive" value="yes">Yes</label>
    <label><input type="radio" name="profile-can-drive" value="no">No</label>
    <div id="driver-details"><input id="profile-seats" type="number"></div>
    ${questions}
  </form>`);
  const form = dom.window.document.querySelector('form');
  const errors = [];
  const {initTripSurvey} = await surveyModule;
  initTripSurvey(form, message => errors.push(message));
  return {dom, form, errors};
}

test('dietary options have tappable labels and expose checked values to registration', async () => {
  const {form} = await load();
  const inputs = [...form.querySelectorAll('[data-dietary]')];
  assert.equal(inputs.length, 10);
  for (const input of inputs) {
    const label = input.closest('label');
    assert.ok(label.textContent.includes(input.value));
    assert.ok(label.querySelector('[data-choice-mark]'), 'Each option has a visible check mark');
  }
  inputs.find(input => input.value === 'Vegan').closest('label').click();
  inputs.find(input => input.value === 'Nut allergy').closest('label').click();
  assert.deepEqual([...form.querySelectorAll('[data-dietary]:checked')].map(i => i.value),
    ['Vegan', 'Nut allergy']);
  inputs.find(input => input.value === 'Vegan').closest('label').click();
  assert.deepEqual([...form.querySelectorAll('[data-dietary]:checked')].map(i => i.value), ['Nut allergy']);
});

test('selection counts initialize, update, and reject only the excess choice', async () => {
  const {form, errors} = await load(`<div data-question-field="0">
    <div data-question-key="departures" data-question-type="multi_choice" data-max-selections="2">
      <label><input type="checkbox" value="Friday" checked>Friday</label>
      <label><input type="checkbox" value="Saturday">Saturday</label>
      <label><input type="checkbox" value="Sunday">Sunday</label>
      <p data-selection-counter aria-live="polite"></p>
    </div>
  </div>`);
  const counter = form.querySelector('[data-selection-counter]');
  const inputs = form.querySelectorAll('input[type="checkbox"][value]');
  const friday = [...inputs].find(i => i.value === 'Friday');
  const saturday = [...inputs].find(i => i.value === 'Saturday');
  const sunday = [...inputs].find(i => i.value === 'Sunday');
  assert.equal(counter.textContent, '1 of 2 selected');
  saturday.click();
  assert.equal(counter.textContent, '2 of 2 selected');
  sunday.click();
  assert.equal(sunday.checked, false);
  assert.equal(friday.checked, true);
  assert.equal(saturday.checked, true);
  assert.equal(counter.textContent, '2 of 2 selected');
  assert.match(errors.at(-1), /at most 2/);
  friday.click();
  assert.equal(counter.textContent, '1 of 2 selected');
  sunday.click();
  assert.equal(sunday.checked, true);
  assert.equal(counter.textContent, '2 of 2 selected');
});

for (const type of ['yes_no', 'choice', 'select']) {
  test(`conditional fields hide and disable when the ${type} parent changes`, async () => {
    const parent = type === 'select'
      ? '<select data-question-key="sharing" data-question-type="choice"><option value="">Choose</option><option value="yes">Yes</option><option value="no">No</option></select>'
      : `<div role="radiogroup" data-question-key="sharing" data-question-type="${type}"><input type="radio" name="sharing" value="yes"><input type="radio" name="sharing" value="no"></div>`;
    const {dom, form} = await load(`${parent}
      <div data-question-field="1" data-visible-if='{"question":"sharing","equals":"yes"}'>
        <input id="dependent" data-question-key="share_with" data-question-type="text" required value="Sam">
        <select><option>One</option></select>
      </div>`);
    const dependent = form.querySelector('#dependent');
    const wrapper = dependent.closest('[data-question-field]');
    const controls = [...wrapper.querySelectorAll('input, select')];
    assert.equal(wrapper.classList.contains('hidden'), true);
    assert.ok(controls.every(i => i.disabled));
    function choose(value) {
      if (type === 'select') {
        const select = form.querySelector('[data-question-key="sharing"]');
        select.value = value;
        select.dispatchEvent(new dom.window.Event('change', {bubbles: true}));
      } else form.querySelector(`input[name="sharing"][value="${value}"]`).click();
    }
    choose('yes');
    assert.equal(wrapper.classList.contains('hidden'), false);
    assert.ok(controls.every(i => !i.disabled));
    choose('no');
    assert.equal(wrapper.classList.contains('hidden'), true);
    assert.ok(controls.every(i => i.disabled));
    assert.equal(dependent.value, 'Sam', 'Hiding preserves the answer for a later reveal');
  });
}

test('driver details reveal for drivers and disable when switching to a passenger', async () => {
  const {form} = await load();
  const details = form.querySelector('#driver-details');
  const seats = form.querySelector('#profile-seats');
  assert.equal(details.classList.contains('hidden'), true);
  assert.equal(seats.disabled, true);
  form.querySelector('[name="profile-can-drive"][value="yes"]').click();
  assert.equal(details.classList.contains('hidden'), false);
  assert.equal(seats.disabled, false);
  seats.value = '3';
  form.querySelector('[name="profile-can-drive"][value="no"]').click();
  assert.equal(details.classList.contains('hidden'), true);
  assert.equal(seats.disabled, true);
});
