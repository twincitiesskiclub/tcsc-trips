import assert from 'node:assert/strict';
import test from 'node:test';

import { deriveRegistrationState } from '../src/lib/registrationState.ts';

const WINDOWS = {
  returning_start: '2026-08-28T17:00:00Z',
  returning_end: '2026-09-02T05:00:00Z',
  new_start: '2026-09-03T17:00:00Z',
  new_end: '2026-09-20T05:00:00Z',
};
const at = (iso) => Date.parse(iso);

test('is coming_soon before anything opens', () => {
  assert.equal(deriveRegistrationState(WINDOWS, at('2026-07-30T12:00:00Z')), 'coming_soon');
});

test('is open inside the returning window', () => {
  assert.equal(deriveRegistrationState(WINDOWS, at('2026-08-29T12:00:00Z')), 'open');
});

test('is open inside the new-member window', () => {
  assert.equal(deriveRegistrationState(WINDOWS, at('2026-09-10T12:00:00Z')), 'open');
});

test('is open exactly at a window boundary, both ends', () => {
  assert.equal(deriveRegistrationState(WINDOWS, at('2026-08-28T17:00:00Z')), 'open');
  assert.equal(deriveRegistrationState(WINDOWS, at('2026-09-02T05:00:00Z')), 'open');
});

test('is coming_soon one second before opening and open one second after', () => {
  assert.equal(deriveRegistrationState(WINDOWS, at('2026-08-28T16:59:59Z')), 'coming_soon');
  assert.equal(deriveRegistrationState(WINDOWS, at('2026-08-28T17:00:01Z')), 'open');
});

test('is coming_soon in the gap between the two windows', () => {
  // Nobody can actually register here, but a window is still ahead, so
  // saying "open" would be a lie.
  assert.equal(deriveRegistrationState(WINDOWS, at('2026-09-02T18:00:00Z')), 'coming_soon');
});

test('is closed once every window has passed', () => {
  assert.equal(deriveRegistrationState(WINDOWS, at('2026-10-01T12:00:00Z')), 'closed');
});

test('is closed with no windows at all', () => {
  assert.equal(deriveRegistrationState({}, at('2026-07-30T12:00:00Z')), 'closed');
});

test('ignores a half-specified window', () => {
  // Matches Season.is_open_for, which requires both ends to be set.
  const half = { returning_start: '2026-08-28T17:00:00Z', returning_end: null };
  assert.equal(deriveRegistrationState(half, at('2026-08-29T12:00:00Z')), 'closed');
});

test('ignores unparseable timestamps rather than throwing', () => {
  const junk = { returning_start: 'not a date', returning_end: 'nope' };
  assert.equal(deriveRegistrationState(junk, at('2026-08-29T12:00:00Z')), 'closed');
});

test('uses only the new-member window when returning is absent', () => {
  const newOnly = { new_start: '2026-09-03T17:00:00Z', new_end: '2026-09-20T05:00:00Z' };
  assert.equal(deriveRegistrationState(newOnly, at('2026-09-10T12:00:00Z')), 'open');
  assert.equal(deriveRegistrationState(newOnly, at('2026-08-01T12:00:00Z')), 'coming_soon');
});
