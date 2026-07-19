import assert from 'node:assert/strict';
import test from 'node:test';

import { SPONSOR_TIERS, groupSponsorsByTier } from '../src/lib/sponsorTiers.js';

const sponsor = (id, tier, order) => ({ id, data: { tier, order } });

test('defines the three public tiers in recognition order', () => {
  assert.deepEqual(SPONSOR_TIERS, [
    { tier: 'trailblazer', label: 'Trailblazer Partners' },
    { tier: 'community_partner', label: 'Community Partners' },
    { tier: 'supporter', label: 'Supporters' },
  ]);
  assert.equal(SPONSOR_TIERS.some(({ tier }) => tier === 'friend'), false);
});

test('freezes the public tier array and every tier record', () => {
  assert.equal(Object.isFrozen(SPONSOR_TIERS), true);
  assert.equal(SPONSOR_TIERS.every((tier) => Object.isFrozen(tier)), true);
});

test('omits empty tiers and sorts sponsors by order then id', () => {
  const groups = groupSponsorsByTier([
    sponsor('zeta', 'supporter', 4),
    sponsor('bravo', 'trailblazer', 2),
    sponsor('alpha', 'trailblazer', 2),
    sponsor('first', 'trailblazer', 1),
  ]);

  assert.deepEqual(
    groups.map(({ tier, label, items }) => ({
      tier,
      label,
      ids: items.map(({ id }) => id),
    })),
    [
      {
        tier: 'trailblazer',
        label: 'Trailblazer Partners',
        ids: ['first', 'alpha', 'bravo'],
      },
      { tier: 'supporter', label: 'Supporters', ids: ['zeta'] },
    ],
  );
});
