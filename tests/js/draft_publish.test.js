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
    SOURCE + '\nmodule.exports = {draftPublishHtml, rowHtml};'
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
  assert.match(rowHtml(BLOCKED, false), /needs location, type/);
});

test('the drawer offers a single-practice publish escape hatch', () => {
  // Blocks are normally published from their availability poll. This exists for
  // a draft whose block never got one, which would otherwise be unpublishable.
  const {draftPublishHtml} = load();
  const html = draftPublishHtml(READY);
  assert.match(html, /pl-publish-one/);
  assert.match(html, /availability block/);
});

test('a draft missing details is explained, not offered a publish button', () => {
  const {draftPublishHtml} = load();
  const html = draftPublishHtml(BLOCKED);
  assert.match(html, /needs location, type/);
  assert.doesNotMatch(html, /pl-publish-one/);
});

test('a published practice gets no draft notice in the drawer', () => {
  const {draftPublishHtml} = load();
  assert.equal(draftPublishHtml(PUBLISHED), '');
});

test('there is no week-level or list-level publish control', () => {
  // The Sunday evening flow already sends the coming week to members with no
  // human in the loop; a batch publish here would gate a working workflow.
  assert.doesNotMatch(SOURCE, /pl-publish-btn/);
  assert.doesNotMatch(SOURCE, /draftBannerHtml/);
});
