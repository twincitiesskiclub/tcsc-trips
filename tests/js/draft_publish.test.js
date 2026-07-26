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
  // Deliberately WITHOUT #pl-list: the source's DOMContentLoaded handler
  // returns early when that element is absent, so loading the file here can't
  // kick off the page's fetch()es. Same trick as lead_picker.test.js.
  const dom = new JSDOM('<!doctype html><div id="not-the-list"></div>');
  global.window = dom.window;
  global.document = dom.window.document;
  const module = {exports: {}};
  new Function('module', 'exports', 'window', 'document',
    SOURCE + '\nmodule.exports = {draftBannerHtml, readyDrafts, rowHtml};'
  )(module, module.exports, dom.window, dom.window.document);
  return {dom, ...module.exports};
}

const READY = {
  id: 1, date: '2099-05-04T18:15:00', location_name: 'TEST Wirth',
  status: 'scheduled', is_draft: true, missing_details: [],
  activities: [], practice_types: [], leads: [], coaches: [],
};
const BLOCKED = {
  id: 2, date: '2099-05-05T18:15:00', location_name: 'No Location',
  status: 'scheduled', is_draft: true, missing_details: ['location', 'type'],
  activities: [], practice_types: [], leads: [], coaches: [],
};
const PUBLISHED = {
  id: 3, date: '2099-05-06T18:15:00', location_name: 'TEST Elm',
  status: 'scheduled', is_draft: false, missing_details: [],
  activities: [], practice_types: [], leads: [], coaches: [],
};

test('a draft row is badged so it is not mistaken for a live practice', () => {
  const {rowHtml} = load();
  const html = rowHtml(READY, false);
  assert.match(html, /Draft/);
  assert.match(html, /pl-row-draft/);
});

test('a published row carries no draft badge', () => {
  const {rowHtml} = load();
  assert.doesNotMatch(rowHtml(PUBLISHED, false), /Draft/);
});

test('a draft missing details says what it needs, on the row', () => {
  const {rowHtml} = load();
  const html = rowHtml(BLOCKED, false);
  assert.match(html, /needs location, type/);
});

test('readyDrafts counts only drafts with every required detail', () => {
  const {readyDrafts} = load();
  const ready = readyDrafts([READY, BLOCKED, PUBLISHED]);
  assert.deepEqual(ready.map(p => p.id), [1]);
});

test('the banner offers to publish exactly the ready drafts', () => {
  const {draftBannerHtml} = load();
  const html = draftBannerHtml([READY, BLOCKED, PUBLISHED]);
  assert.match(html, /2 drafts/);
  assert.match(html, /Publish 1 ready/);
  assert.doesNotMatch(html, /disabled/);
});

test('the banner names the drafts that are holding things up', () => {
  const {draftBannerHtml} = load();
  const html = draftBannerHtml([READY, BLOCKED]);
  assert.match(html, /needs location, type/);
});

test('nothing ready means the publish button is disabled, not hidden', () => {
  // Hiding it would read as "there is nothing to publish", when the truth is
  // "someone has to fill in the missing details first".
  const {draftBannerHtml} = load();
  const html = draftBannerHtml([BLOCKED]);
  assert.match(html, /disabled/);
  assert.match(html, /Publish 0 ready/);
});

test('no drafts means no banner at all', () => {
  const {draftBannerHtml} = load();
  assert.equal(draftBannerHtml([PUBLISHED]), '');
});

test('draft counts ignore practices that already went out', () => {
  const {draftBannerHtml} = load();
  const html = draftBannerHtml([READY, PUBLISHED]);
  assert.match(html, /1 draft is not visible/);
});
