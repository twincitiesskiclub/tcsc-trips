'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require('jsdom');

const ROOT = path.resolve(__dirname, '../..');
const SOURCE = fs.readFileSync(
  path.join(ROOT, 'app/static/admin_practices.js'), 'utf8');
// Pure JS despite living under templates/ — it's {% include %}d verbatim
// into _detail_script.js, so it can be evaluated directly here.
const CONTEXT_SOURCE = fs.readFileSync(
  path.join(ROOT, 'app/templates/admin/practices/_detail_context.js'), 'utf8');

function load() {
  const dom = new JSDOM('<!doctype html><div id="lead-picker"></div>');
  global.window = dom.window;
  global.document = dom.window.document;
  const module = {exports: {}};
  new Function('module', 'exports', 'window', 'document',
    SOURCE + '\nmodule.exports = {leadCandidateLabel, renderLeadPicker, '
    + 'resolveLeadIds, markLeadPickerReady};'
  )(module, module.exports, dom.window, dom.window.document);
  return {dom, ...module.exports};
}

// Loads _detail_context.js with its collaborators stubbed, mirroring the
// scope it gets in the rendered page (practiceId, loadLeadCandidates and
// renderLeadPicker are all in scope there via _detail_script.js).
function loadContext({loadLeadCandidates, renderLeadPicker,
                      markLeadPickerReady} = {}) {
  const dom = new JSDOM(
    '<!doctype html><div id="lead-picker"><p class="pe-empty">Loading…</p></div>');
  const module = {exports: {}};
  const readyCalls = [];
  new Function('module', 'exports', 'window', 'document',
    'practiceId', 'loadLeadCandidates', 'renderLeadPicker',
    'markLeadPickerReady',
    CONTEXT_SOURCE + '\nmodule.exports = {loadLeadPicker};'
  )(module, module.exports, dom.window, dom.window.document,
    42, loadLeadCandidates, renderLeadPicker,
    markLeadPickerReady || ((v) => readyCalls.push(v)));
  return {dom, readyCalls, ...module.exports};
}

test('label shows availability and both load counts', () => {
  const {leadCandidateLabel} = load();
  const label = leadCandidateLabel({
    name: 'Ada L', available: true, responded: true, stale: false,
    led_in_block: 0, led_last_90d: 2,
  });
  assert.match(label, /available/);
  assert.match(label, /led 0 this block/);
  assert.match(label, /2 in 90d/);
});

test('no response reads differently from unavailable', () => {
  const {leadCandidateLabel} = load();
  const silent = leadCandidateLabel({
    name: 'Zoe', available: false, responded: false, stale: false,
    led_in_block: 0, led_last_90d: 0,
  });
  const declined = leadCandidateLabel({
    name: 'Kai', available: false, responded: true, stale: false,
    led_in_block: 0, led_last_90d: 0,
  });
  assert.match(silent, /no response/);
  assert.match(declined, /unavailable/);
});

test('stale responses are marked', () => {
  const {leadCandidateLabel} = load();
  const label = leadCandidateLabel({
    name: 'Ada L', available: true, responded: true, stale: true,
    led_in_block: 0, led_last_90d: 0,
  });
  assert.match(label, /⚠/);
});

test('capacity is rendered and unavailable candidates stay selectable', () => {
  const {renderLeadPicker, dom} = load();
  const container = dom.window.document.getElementById('lead-picker');
  renderLeadPicker(container, {
    leads_needed: 2,
    assigned: [1],
    candidates: [
      {user_id: 1, name: 'Ada L', available: true, responded: true,
       stale: false, led_in_block: 0, led_last_90d: 1},
      {user_id: 2, name: 'Zoe L', available: false, responded: false,
       stale: false, led_in_block: 3, led_last_90d: 5},
    ],
  });

  assert.match(container.textContent, /needs 2/);
  const boxes = container.querySelectorAll('input[type=checkbox]');
  assert.equal(boxes.length, 2);
  assert.equal(boxes[0].checked, true, 'already-assigned lead is checked');
  assert.equal(boxes[1].disabled, false,
    'unavailable leads must stay selectable — the picker informs the choice, it does not block it');
});

test('failed candidate load replaces Loading… with a visible error', async () => {
  const {loadLeadPicker, dom} = loadContext({
    // loadLeadCandidates resolves null after showing its toast (non-ok response)
    loadLeadCandidates: async () => null,
  });
  await loadLeadPicker();
  const container = dom.window.document.getElementById('lead-picker');
  assert.doesNotMatch(container.textContent, /Loading…/,
    'a failed load must not leave the loading state on screen');
  assert.ok(container.querySelector('.rail-error'),
    'renders an in-place error like the sibling loaders');
});

test('a rejected candidate fetch also lands as an in-place error', async () => {
  const {loadLeadPicker, dom} = loadContext({
    loadLeadCandidates: async () => { throw new Error('network down'); },
  });
  await loadLeadPicker();
  const container = dom.window.document.getElementById('lead-picker');
  assert.doesNotMatch(container.textContent, /Loading…/);
  assert.ok(container.querySelector('.rail-error'));
});

test('a successful candidate load still renders the picker', async () => {
  const payload = {leads_needed: 2, assigned: [], candidates: []};
  const calls = [];
  const {loadLeadPicker} = loadContext({
    loadLeadCandidates: async (id) => { calls.push(id); return payload; },
    renderLeadPicker: (container, p) => { calls.push(p); },
  });
  await loadLeadPicker();
  assert.deepEqual(calls, [42, payload]);
});

/* --------------------------------------------------------------------------
   The save-wipe guard. The picker is the only lead-assignment control on the
   practice form, and the form always submits lead_ids, so an empty checkbox
   set is a destructive instruction: edit_practice deletes every coach/lead
   row and re-adds only what the payload names. Before this guard, a picker
   that failed to load (or hadn't finished) meant clicking Save deleted every
   assigned lead and rewrote the member-facing announcement without them.
   -------------------------------------------------------------------------- */

test('an unrendered picker preserves the server-side assignment', () => {
  const {resolveLeadIds, dom} = load();
  const container = dom.window.document.getElementById('lead-picker');
  // Exactly what a failed load leaves behind: the error node, no checkboxes.
  container.innerHTML = '<p class="rail-error">Could not load lead availability.</p>';

  const {ids, preserved} = resolveLeadIds(container, [7, 9]);
  assert.deepEqual(ids, [7, 9],
    'must resubmit the already-assigned leads, not an empty set');
  assert.equal(preserved, true, 'caller needs to know the edit did not take');
});

test('a still-loading picker preserves the server-side assignment', () => {
  const {resolveLeadIds, dom} = load();
  const container = dom.window.document.getElementById('lead-picker');
  container.innerHTML = '<p class="pe-empty">Loading…</p>';

  const {ids, preserved} = resolveLeadIds(container, [3]);
  assert.deepEqual(ids, [3]);
  assert.equal(preserved, true);
});

test('a rendered picker is authoritative, including deselect-to-none', () => {
  const {renderLeadPicker, resolveLeadIds, dom} = load();
  const container = dom.window.document.getElementById('lead-picker');
  renderLeadPicker(container, {
    leads_needed: 2,
    assigned: [1],
    candidates: [
      {user_id: 1, name: 'Ada L', available: true, responded: true,
       stale: false, led_in_block: 0, led_last_90d: 1},
      {user_id: 2, name: 'Zoe L', available: true, responded: true,
       stale: false, led_in_block: 0, led_last_90d: 0},
    ],
  });

  // Reflects the checkboxes, not the server's list.
  assert.deepEqual(resolveLeadIds(container, [1]).ids, [1]);

  container.querySelectorAll('input[type=checkbox]')[1].checked = true;
  assert.deepEqual(resolveLeadIds(container, [1]).ids, [1, 2],
    'a newly ticked candidate must reach the payload');

  // Deliberately clearing every lead must still be possible — the guard is
  // about an *unknown* state, not about refusing to unassign.
  container.querySelectorAll('input[type=checkbox]').forEach((b) => {
    b.checked = false;
  });
  const cleared = resolveLeadIds(container, [1]);
  assert.deepEqual(cleared.ids, [],
    'unassigning every lead on a rendered picker must still be honoured');
  assert.equal(cleared.preserved, false);
});

test('reloading the picker withdraws trust until it re-renders', async () => {
  const {loadLeadPicker, readyCalls} = loadContext({
    loadLeadCandidates: async () => null,  // fails
  });
  await loadLeadPicker();
  assert.deepEqual(readyCalls, [false],
    'a failed reload must clear the flag, not leave a stale true standing');
});
