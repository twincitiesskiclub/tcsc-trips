'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require('jsdom');

const Model = require('../../app/static/practice_plan_reactions.js');

const ROOT = path.resolve(__dirname, '../..');
const TOAST_SOURCE = fs.readFileSync(
  path.join(ROOT, 'app/static/js/toast.js'),
  'utf8',
);

test('reaction conflict errors render as inert toast text', () => {
  const hostileName = '<img src=x onerror="window.__toastXss = true">';
  const resolution = Model.resolve([], [
    {
      id: 1,
      name: hostileName,
      default_plan_reactions: [{emoji: 'bike', label: 'bike'}],
    },
    {
      id: 2,
      name: 'Mountain Bike',
      default_plan_reactions: [{emoji: 'bike', label: 'mountain biker'}],
    },
  ]);
  assert.match(resolution.error, /<img/);

  const dom = new JSDOM('<!doctype html><body></body>', {
    runScripts: 'dangerously',
    pretendToBeVisual: true,
  });
  const {window} = dom;
  window.requestAnimationFrame = callback => callback();
  window.eval(TOAST_SOURCE);

  window.showToast(resolution.error, 'error');

  const toast = window.document.querySelector('#toast-container > div');
  assert.ok(toast);
  assert.equal(toast.querySelector('.flex-1').textContent, resolution.error);
  assert.equal(toast.querySelectorAll('img').length, 0);
  assert.equal(window.__toastXss, undefined);

  const dismiss = toast.querySelector('button');
  assert.equal(dismiss.getAttribute('onclick'), null);
  dismiss.click();
  assert.equal(window.document.querySelector('#toast-container > div'), null);
  dom.window.close();
});
