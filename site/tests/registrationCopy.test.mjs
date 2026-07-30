import assert from 'node:assert/strict';
import test from 'node:test';

import {
  cardNote,
  datesSentence,
  formatDay,
  stripSubhead,
} from '../src/lib/registrationCopy.ts';

const WINDOWS = {
  returning_start: '2026-08-28T17:00:00Z',
  returning_end: '2026-09-02T05:00:00Z',
  new_start: '2026-09-03T17:00:00Z',
  new_end: '2026-09-20T05:00:00Z',
};

test('formats a day in US Central, not UTC', () => {
  // 2026-08-28T17:00Z is 12:00 CDT the same day.
  assert.equal(formatDay('2026-08-28T17:00:00Z'), 'Aug 28');
});

test('uses the Central day, not the UTC day, across the date boundary', () => {
  // A 9pm Central deadline is stored as the NEXT day in UTC. Formatting in
  // UTC would show members a date that is off by one, which is the exact bug
  // this pins. Daylight time here (UTC-5).
  assert.equal(formatDay('2026-09-03T02:00:00Z'), 'Sep 2');
});

test('uses the Central day across the boundary in standard time too', () => {
  // The same trap in CST (UTC-6), so no offset is hardcoded anywhere.
  assert.equal(formatDay('2026-12-16T03:00:00Z'), 'Dec 15');
});

test('returns null for missing or unparseable input', () => {
  assert.equal(formatDay(null), null);
  assert.equal(formatDay(undefined), null);
  assert.equal(formatDay('not a date'), null);
});

test('builds the dates sentence from both windows', () => {
  assert.equal(datesSentence(WINDOWS), 'Returning members Aug 28; new members Sep 3');
});

test('builds a partial dates sentence when only one window exists', () => {
  assert.equal(
    datesSentence({ new_start: '2026-09-03T17:00:00Z' }),
    'New members Sep 3',
  );
});

test('has no dates sentence when no window exists', () => {
  assert.equal(datesSentence({}), null);
});

test('the coming_soon subhead leads with the real dates', () => {
  assert.equal(
    stripSubhead('coming_soon', WINDOWS),
    'Returning members Aug 28; new members Sep 3. Intermediate ability and up, no racing required.',
  );
});

test('the coming_soon subhead omits dates rather than inventing them', () => {
  assert.equal(
    stripSubhead('coming_soon', {}),
    'Registration opens soon. Intermediate ability and up, no racing required.',
  );
});

test('the open and closed subheads do not carry dates', () => {
  assert.equal(
    stripSubhead('open', WINDOWS),
    'Intermediate ability and up, no racing required.',
  );
  assert.equal(
    stripSubhead('closed', WINDOWS),
    'Registration is closed. Intermediate ability and up, no racing required.',
  );
});

test('the card note matches the hand-written format it replaces', () => {
  assert.equal(
    cardNote(2026, WINDOWS),
    '2026 registration: returning members Aug 28 · new members Sep 3',
  );
});

test('there is no card note without dates', () => {
  assert.equal(cardNote(2026, {}), null);
});
