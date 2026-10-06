'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {JSDOM} = require('jsdom');
const A = require('../../app/static/admin_analytics.js');

function dom(html) {
  const d = new JSDOM(`<!doctype html><body>${html}</body>`);
  return d.window.document;
}

test('embedAll passes parsed spec with measured width and svg renderer', async () => {
  const doc = dom('<div class="analytics-chart" data-spec-id="spec-1"></div>' +
    '<script type="application/json" id="spec-1">{"mark":"bar"}</script>');
  const el = doc.querySelector('.analytics-chart');
  Object.defineProperty(el, 'clientWidth', {value: 408});
  const calls = [];
  await A.embedAll(doc, (target, spec, opts) => { calls.push([target, spec, opts]); return Promise.resolve(); });
  assert.equal(calls.length, 1);
  assert.equal(calls[0][1].width, 400);
  assert.deepEqual(calls[0][2], {renderer: 'svg', actions: false, ast: true});
});

test('embed failure shows fallback text', async () => {
  const doc = dom('<div class="analytics-chart" data-spec-id="s"></div><script type="application/json" id="s">{}</script>');
  await A.embedAll(doc, () => Promise.reject(new Error('x')));
  assert.match(doc.querySelector('.analytics-chart').textContent, /could not be drawn/);
});

test('sortTable sorts numerically and toggles', () => {
  const doc = dom('<table><thead><tr><th>Week</th><th>RSVPs</th></tr></thead><tbody>' +
    '<tr><td>a</td><td>9</td></tr><tr><td>b</td><td>30</td></tr><tr><td>c</td><td>12</td></tr></tbody></table>');
  const table = doc.querySelector('table');
  A.sortTable(table, 1);
  assert.deepEqual([...table.querySelectorAll('tbody td:nth-child(2)')].map(td => td.textContent), ['9', '12', '30']);
  A.sortTable(table, 1);
  assert.deepEqual([...table.querySelectorAll('tbody td:nth-child(2)')].map(td => td.textContent), ['30', '12', '9']);
  assert.equal(table.querySelectorAll('th')[1].getAttribute('aria-sort'), 'descending');
});

test('malformed JSON shows the table fallback', async () => {
  const doc = dom('<div class="analytics-chart" data-spec-id="s"></div><script type="application/json" id="s">{oops</script>');
  await A.embedAll(doc, () => { throw new Error('Must not embed'); });
  assert.match(doc.querySelector('.analytics-chart').textContent, /table below/);
});

test('resize observes each chart, debounces and ignores changes of 8px or less', async () => {
  const doc = dom('<div class="analytics-chart" data-spec-id="s"></div><script type="application/json" id="s">{}</script>');
  const el = doc.querySelector('.analytics-chart');
  let width = 408;
  Object.defineProperty(el, 'clientWidth', {get: () => width});
  let callback;
  const observed = [];
  doc.defaultView.ResizeObserver = class {
    constructor(cb) { callback = cb; }
    observe(target) { observed.push(target); }
  };
  const calls = [];
  A.watchResize(doc, (target, spec) => { calls.push(spec.width); return Promise.resolve(); });
  assert.deepEqual(observed, [el]);
  width = 416;
  callback([{target: el}]);
  await new Promise(resolve => setTimeout(resolve, 180));
  assert.deepEqual(calls, []);
  width = 430;
  callback([{target: el}]);
  width = 450;
  callback([{target: el}]);
  await new Promise(resolve => setTimeout(resolve, 180));
  assert.deepEqual(calls, [442]);
});

test('browser auto-init attaches keyboard and click sorting', async () => {
  const fs = require('node:fs');
  const d = new JSDOM('<table class="analytics-table"><thead><tr><th>Name</th><th>Number</th></tr></thead>' +
    '<tbody><tr><td>b</td><td>12</td></tr><tr><td>a</td><td>9</td></tr></tbody></table>', {runScripts: 'outside-only'});
  d.window.vegaEmbed = () => Promise.resolve();
  d.window.eval(fs.readFileSync(require.resolve('../../app/static/admin_analytics.js'), 'utf8'));
  d.window.document.dispatchEvent(new d.window.Event('DOMContentLoaded'));
  const headers = d.window.document.querySelectorAll('th');
  assert.equal(headers[1].tabIndex, 0);
  headers[1].dispatchEvent(new d.window.KeyboardEvent('keydown', {key: 'Enter'}));
  assert.equal(headers[1].getAttribute('aria-sort'), 'ascending');
  headers[0].click();
  assert.equal(headers[0].getAttribute('aria-sort'), 'ascending');
  assert.equal(headers[1].getAttribute('aria-sort'), 'none');
  assert.equal(d.window.document.querySelector('tbody td').textContent, 'a');
  d.window.close();
});

test('re-embedding finalizes the old Vega view', async () => {
  const doc = dom('<div class="analytics-chart" data-spec-id="s"></div><script type="application/json" id="s">{}</script>');
  let finalized = 0;
  const embed = async () => ({finalize() { finalized++; }});
  await A.embedAll(doc, embed);
  await A.embedAll(doc, embed);
  assert.equal(finalized, 1);
});

test('sortTable handles negative and decimal numbers', () => {
  const doc = dom('<table><thead><tr><th>Value</th></tr></thead><tbody>' +
    ['1,000', '-10', '1.5', '1.05', '-2'].map(x => `<tr><td>${x}</td></tr>`).join('') + '</tbody></table>');
  A.sortTable(doc.querySelector('table'), 0);
  assert.deepEqual([...doc.querySelectorAll('td')].map(td => td.textContent), ['-10', '-2', '1.05', '1.5', '1,000']);
});
