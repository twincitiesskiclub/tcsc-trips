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
    + 'publishResultMessage, flashPendingAvailabilityWarning, '
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

/* ---------- block-level publish: the poll cards ---------- */

function poll(overrides) {
  return {
    id: 7, starts_on: '2099-05-04', ends_on: '2099-05-17', status: 'closed',
    is_shadow: false, sessions: 12, unpublished: 0, publishable: 0,
    ...overrides,
  };
}

test('a poll with publishable drafts offers its publish button', () => {
  const {pollCardHtml} = load();
  const html = pollCardHtml(poll({unpublished: 3, publishable: 3}));
  assert.match(html, /pl-poll-publish/);
  assert.match(html, /data-poll-id="7"/);
  assert.match(html, /Publish 3 practices/);
  // date range, status and session count are all on the card
  assert.match(html, /12 sessions/);
  assert.match(html, /Closed/);
});

test('unpublished-but-unpublishable reads as "needs details", not "nothing to do"', () => {
  // "2 unpublished, 0 publishable" is a different problem from "0 unpublished":
  // the drafts exist but are missing location/type/time, and someone has to go
  // fill those in — the card must say so instead of offering nothing.
  const {pollCardHtml} = load();
  const html = pollCardHtml(poll({unpublished: 2, publishable: 0}));
  assert.doesNotMatch(html, /pl-poll-publish/);
  assert.match(html, /2 drafts need details/);
  assert.doesNotMatch(html, /All published/);
});

test('a fully-published poll offers nothing', () => {
  const {pollCardHtml} = load();
  const html = pollCardHtml(poll({unpublished: 0, publishable: 0}));
  assert.doesNotMatch(html, /pl-poll-publish/);
  assert.doesNotMatch(html, /need details/);
  assert.match(html, /All published/);
});

test('a partially-ready poll offers the button AND names the holdouts', () => {
  const {pollCardHtml} = load();
  const html = pollCardHtml(poll({unpublished: 3, publishable: 2}));
  assert.match(html, /Publish 2 practices/);
  assert.match(html, /1 draft needs details/);
});

/* ---------- block-level publish: honest result reporting ---------- */

test('the publish result names skipped practices and what they still need', () => {
  const {publishResultMessage, _setPractices} = load();
  _setPractices([
    {id: 2, date: '2099-05-05T18:15:00', location_name: 'TEST Elm'},
  ]);
  const msg = publishResultMessage({
    published: [1, 3],
    skipped: [{practice_id: 2, missing: ['location', 'type']}],
    already_published: [],
  });
  assert.match(msg, /Published 2/);
  assert.match(msg, /TEST Elm/);
  assert.match(msg, /needs location, type/);
});

test('an all-already-published block is reported as such, not as a publish', () => {
  const {publishResultMessage} = load();
  const msg = publishResultMessage(
    {published: [], skipped: [], already_published: [4, 5]});
  assert.match(msg, /already published/);
  assert.doesNotMatch(msg, /Published \d/);
});

test('a skipped practice missing from the loaded list still gets named by id', () => {
  const {publishResultMessage, _setPractices} = load();
  _setPractices([]);
  const msg = publishResultMessage({
    published: [], skipped: [{practice_id: 9, missing: ['time']}],
    already_published: [],
  });
  assert.match(msg, /#9/);
  assert.match(msg, /needs time/);
});

/* ---------- availability_warning handoff from the create form ---------- */

test('a stashed availability warning is toasted once on the list page, then cleared', () => {
  const {flashPendingAvailabilityWarning, dom, toasts} = load();
  dom.window.sessionStorage.setItem(
    'tcsc-availability-warning', 'TEST practice has no poll letter');
  flashPendingAvailabilityWarning();
  assert.deepEqual(toasts,
    [{msg: 'TEST practice has no poll letter', type: 'warning'}]);
  assert.equal(
    dom.window.sessionStorage.getItem('tcsc-availability-warning'), null);
  flashPendingAvailabilityWarning();
  assert.equal(toasts.length, 1, 'the warning must not re-toast on reload');
});

test('no stashed warning means no toast', () => {
  const {flashPendingAvailabilityWarning, toasts} = load();
  flashPendingAvailabilityWarning();
  assert.deepEqual(toasts, []);
});
