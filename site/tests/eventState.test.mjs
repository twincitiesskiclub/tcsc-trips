import assert from 'node:assert/strict';
import test from 'node:test';

import { deriveEventState, endOfCentralDay } from '../src/lib/eventState.ts';

const TIMES = {
  signup_start: '2026-07-25T05:00:00Z',
  signup_end: '2026-10-23T04:59:00Z',
  event_date: '2026-10-24T14:00:00Z',
};
const at = (iso) => Date.parse(iso);

test('upcoming before signups open', () => {
  assert.equal(deriveEventState(TIMES, at('2026-07-25T04:59:59Z')), 'upcoming');
});

test('open at both boundaries, inclusive like the server', () => {
  assert.equal(deriveEventState(TIMES, at('2026-07-25T05:00:00Z')), 'open');
  assert.equal(deriveEventState(TIMES, at('2026-10-23T04:59:00Z')), 'open');
});

test('closed after signups end and through race day in Central', () => {
  assert.equal(deriveEventState(TIMES, at('2026-10-23T04:59:01Z')), 'closed');
  // 11:30 PM Central on race day is already Oct 25 in UTC.
  assert.equal(deriveEventState(TIMES, at('2026-10-25T04:30:00Z')), 'closed');
});

test('past from Central midnight after race day', () => {
  assert.equal(deriveEventState(TIMES, at('2026-10-25T05:00:00Z')), 'past');
});

test('end of a CST day is 06:00Z, of a CDT day 05:00Z', () => {
  assert.equal(endOfCentralDay(at('2026-01-19T18:00:00Z')), at('2026-01-20T06:00:00Z'));
  assert.equal(endOfCentralDay(at('2026-10-24T14:00:00Z')), at('2026-10-25T05:00:00Z'));
});

test('spring-forward: the day before ends at CST midnight, the day itself at CDT midnight', () => {
  // DST starts Sunday Mar 14 2027 at 2 AM. Midnight starting Mar 14 is still CST.
  assert.equal(endOfCentralDay(at('2027-03-13T18:00:00Z')), at('2027-03-14T06:00:00Z'));
  assert.equal(endOfCentralDay(at('2027-03-14T18:00:00Z')), at('2027-03-15T05:00:00Z'));
});

test('unparseable timestamps read as closed, never open', () => {
  assert.equal(deriveEventState({ ...TIMES, signup_end: 'nope' }, at('2026-08-01T00:00:00Z')), 'closed');
});
