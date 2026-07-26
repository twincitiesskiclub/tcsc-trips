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
  // esc() lives in admin_practices.js, which the detail page loads first;
  // _detail_context.js escapes every innerHTML hole through it.
  const esc = (v) => String(v == null ? '' : v)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  new Function('module', 'exports', 'window', 'document',
    'practiceId', 'loadLeadCandidates', 'renderLeadPicker',
    'markLeadPickerReady', 'esc',
    CONTEXT_SOURCE + '\nmodule.exports = {loadLeadPicker, loadRSVPs, '
    + 'loadLeadConfirmations};'
  )(module, module.exports, dom.window, dom.window.document,
    42, loadLeadCandidates, renderLeadPicker,
    markLeadPickerReady || ((v) => readyCalls.push(v)), esc);
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

/* --------------------------------------------------------------------------
   Stored XSS in the detail rails. Member names reach these rails straight from
   the public season-registration form, and the admin CSP allows 'unsafe-inline'
   for script-src, so an <img onerror> in a last name executed in the admin's
   session the moment they opened the practice page.
   -------------------------------------------------------------------------- */

function loadRails(fetchImpl) {
  const dom = new JSDOM(
    '<!doctype html><div id="rsvp-summary"></div><div id="rsvp-list"></div>'
    + '<div id="lead-confirmations-container"></div>');
  const esc = (v) => String(v == null ? '' : v)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  const module = {exports: {}};
  new Function('module', 'exports', 'window', 'document', 'practiceId',
    'loadLeadCandidates', 'renderLeadPicker', 'markLeadPickerReady', 'esc',
    'fetch',
    CONTEXT_SOURCE + '\nmodule.exports = {loadRSVPs, loadLeadConfirmations};'
  )(module, module.exports, dom.window, dom.window.document, 42,
    async () => null, () => {}, () => {}, esc, fetchImpl);
  return {dom, ...module.exports};
}

const XSS = '<img src=x onerror="window.pwned=1">';

test('a hostile member name cannot inject markup into the RSVP rail', async () => {
  const {dom, loadRSVPs} = loadRails(async () => ({
    json: async () => ({
      summary: {going: 1, maybe: 0, not_going: 0},
      rsvps: [{id: 1, user_id: 2, user_name: `Ada ${XSS}`, status: 'going'}],
    }),
  }));

  await loadRSVPs();
  const list = dom.window.document.getElementById('rsvp-list');
  assert.equal(list.querySelectorAll('img').length, 0,
    'the name must not become a real element');
  assert.match(list.textContent, /Ada/, 'but the name itself still renders');
  assert.match(list.innerHTML, /&lt;img/, 'escaped, not stripped');
});

test('a hostile lead name cannot inject markup into the confirmations rail', async () => {
  const {dom, loadLeadConfirmations} = loadRails(async () => ({
    json: async () => ({
      leads: [{id: 5, name: `Zoe ${XSS}`, role: 'lead', confirmed: false}],
    }),
  }));

  await loadLeadConfirmations();
  const c = dom.window.document.getElementById('lead-confirmations-container');
  assert.equal(c.querySelectorAll('img').length, 0);
  assert.match(c.textContent, /Zoe/);
  // The name is also interpolated into an aria-label attribute, so a quote
  // must not be able to break out of it and add a handler.
  const label = c.querySelector('input[type=checkbox]').getAttribute('aria-label');
  assert.match(label, /Confirm Zoe/);
  assert.equal(c.querySelector('input[type=checkbox]').getAttribute('onerror'), null);
});

test('candidates outside the lead pool are labelled and classed', () => {
  const {leadCandidateLabel, renderLeadPicker, dom} = load();

  const outsider = leadCandidateLabel({
    name: 'Jane L', available: true, responded: true, stale: false,
    led_in_block: 0, led_last_90d: 0, in_pool: false,
  });
  assert.match(outsider, /not in the lead pool/,
    'picking someone outside the pool is a different decision — say so');

  const regular = leadCandidateLabel({
    name: 'Ada L', available: true, responded: true, stale: false,
    led_in_block: 0, led_last_90d: 0, in_pool: true,
  });
  assert.doesNotMatch(regular, /not in the lead pool/,
    'positive control: a normal candidate must not be flagged');

  // A payload with no in_pool key (an older cached response) must read as a
  // normal candidate, not flag every single person.
  const legacy = leadCandidateLabel({
    name: 'Kai L', available: true, responded: true, stale: false,
    led_in_block: 0, led_last_90d: 0,
  });
  assert.doesNotMatch(legacy, /not in the lead pool/);

  const container = dom.window.document.getElementById('lead-picker');
  renderLeadPicker(container, {
    leads_needed: 2,
    assigned: [1],
    candidates: [
      {user_id: 1, name: 'Jane L', available: false, responded: false,
       stale: false, led_in_block: 0, led_last_90d: 0, in_pool: false},
      {user_id: 2, name: 'Ada L', available: true, responded: true,
       stale: false, led_in_block: 0, led_last_90d: 0, in_pool: true},
    ],
  });
  const rows = container.querySelectorAll('.lead-option');
  assert.ok(rows[0].classList.contains('outside-pool'));
  assert.ok(!rows[1].classList.contains('outside-pool'));
  assert.equal(rows[0].querySelector('input').checked, true,
    'an assigned out-of-pool lead stays checked, so saving keeps them');
});
