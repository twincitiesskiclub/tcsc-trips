'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require('jsdom');

const ROOT = path.resolve(__dirname, '../..');
const SOURCE = fs.readFileSync(
  path.join(ROOT, 'app/static/admin_practices.js'), 'utf8');

function load() {
  const dom = new JSDOM('<!doctype html><div id="lead-picker"></div>');
  global.window = dom.window;
  global.document = dom.window.document;
  const module = {exports: {}};
  new Function('module', 'exports', 'window', 'document',
    SOURCE + '\nmodule.exports = {leadCandidateLabel, renderLeadPicker};'
  )(module, module.exports, dom.window, dom.window.document);
  return {dom, ...module.exports};
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
