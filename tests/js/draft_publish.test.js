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
  // The url gives the window a real origin — jsdom's default about:blank is
  // an opaque origin whose sessionStorage throws, and the availability-warning
  // handoff below needs a working one.
  const dom = new JSDOM('<!doctype html><div id="not-the-list"></div>',
    {url: 'http://localhost/'});
  global.window = dom.window;
  global.document = dom.window.document;
  const toasts = [];
  const module = {exports: {}};
  new Function('module', 'exports', 'window', 'document', 'showToast',
    SOURCE + '\nmodule.exports = {draftPublishHtml, rowHtml, pollCardHtml, '
    + '_setPractices: (d) => { practicesData = d; }};'
  )(module, module.exports, dom.window, dom.window.document,
    (msg, type) => toasts.push({msg, type}));
  return {dom, toasts, ...module.exports};
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

test('a hidden row is badged so it is not mistaken for a live practice', () => {
  const {rowHtml} = load();
  const html = rowHtml(BLOCKED, false);
  assert.match(html, /Hidden/);
  assert.match(html, /pl-row-draft/);
  assert.match(html, /needs location, type/);
});

test('a visible row carries no hidden badge', () => {
  const {rowHtml} = load();
  assert.doesNotMatch(rowHtml(PUBLISHED, false), /Hidden/);
});

test('the drawer explains what keeps a practice hidden, with no button', () => {
  const {draftPublishHtml} = load();
  const html = draftPublishHtml(BLOCKED);
  assert.match(html, /Hidden from members until it has a location and a type/);
  assert.doesNotMatch(html, /<button/);
});

test('a visible practice gets no hidden notice in the drawer', () => {
  const {draftPublishHtml} = load();
  assert.equal(draftPublishHtml(PUBLISHED), '');
});

test('no publish control exists anywhere on the page', () => {
  assert.doesNotMatch(SOURCE, /pl-publish/);
  assert.doesNotMatch(SOURCE, /\/publish'/);
  assert.doesNotMatch(SOURCE, /publishPollBlock|publishOnePractice/);
});

test('a poll card shows range, status and session count, and no publish button', () => {
  const {pollCardHtml} = load();
  const html = pollCardHtml({id: 7, starts_on: '2099-05-04', ends_on: '2099-05-17',
    status: 'closed', sessions: 6});
  assert.match(html, /6 sessions/);
  assert.match(html, /Closed/);
  assert.doesNotMatch(html, /Publish/);
});

test('an unopened block offers Open poll on its card', () => {
  const {pollCardHtml} = load();
  const html = pollCardHtml({id: 9, starts_on: '2099-05-04', ends_on: '2099-05-17',
    status: 'draft', sessions: 6, posted: false});
  assert.match(html, /pl-poll-open/);
  assert.match(html, /data-poll-id="9"/);
});

test('a block that never had a poll reads Assign only', () => {
  const {pollCardHtml} = load();
  const html = pollCardHtml({id: 9, starts_on: '2099-05-04', ends_on: '2099-05-17',
    status: 'closed', sessions: 6, posted: false});
  assert.match(html, /Assign only/);
});

test('the date-range poll toolbar is gone', () => {
  assert.doesNotMatch(SOURCE, /pl-poll-start|openAvailabilityPoll/);
});

test('the open-poll warning handoff is gone', () => {
  assert.doesNotMatch(SOURCE, /tcsc-availability-warning|flashPendingAvailabilityWarning/);
});
