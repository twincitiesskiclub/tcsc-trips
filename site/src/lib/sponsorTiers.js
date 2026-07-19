// @ts-check

/** @typedef {'trailblazer' | 'community_partner' | 'supporter'} SponsorTier */

/** @type {ReadonlyArray<Readonly<{ tier: SponsorTier; label: string }>>} */
export const SPONSOR_TIERS = Object.freeze([
  Object.freeze({ tier: 'trailblazer', label: 'Trailblazer Partners' }),
  Object.freeze({ tier: 'community_partner', label: 'Community Partners' }),
  Object.freeze({ tier: 'supporter', label: 'Supporters' }),
]);

/**
 * @template {{ id: string; data: { tier: string; order: number } }} T
 * @param {readonly T[]} sponsors
 * @returns {Array<{ tier: SponsorTier; label: string; items: T[] }>}
 */
export function groupSponsorsByTier(sponsors) {
  return SPONSOR_TIERS.map(({ tier, label }) => ({
    tier,
    label,
    items: sponsors
      .filter((sponsor) => sponsor.data.tier === tier)
      .sort((a, b) => a.data.order - b.data.order || a.id.localeCompare(b.id)),
  })).filter(({ items }) => items.length > 0);
}
