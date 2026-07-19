import assert from 'node:assert/strict';
import test from 'node:test';

import { conditionsDisplayMode } from '../src/lib/conditionsDisplayMode.ts';

const healthyPayload = {
  locations: [{ id: 'wirth' }],
};

const errorPayload = {
  error: 'Conditions unavailable',
  locations: [],
};

test('uses off-season mode for a healthy, non-empty July payload', () => {
  const at = new Date('2026-07-19T12:00:00-05:00');

  assert.equal(conditionsDisplayMode(healthyPayload, at), 'off-season');
});

test('uses off-season mode for an error/empty July payload', () => {
  const at = new Date('2026-07-19T12:00:00-05:00');

  assert.equal(conditionsDisplayMode(errorPayload, at), 'off-season');
});

test('uses live mode for a healthy, non-empty January payload', () => {
  const at = new Date('2027-01-15T12:00:00-06:00');

  assert.equal(conditionsDisplayMode(healthyPayload, at), 'live');
});

test('uses unavailable mode for an error/empty January payload', () => {
  const at = new Date('2027-01-15T12:00:00-06:00');

  assert.equal(conditionsDisplayMode(errorPayload, at), 'unavailable');
});
