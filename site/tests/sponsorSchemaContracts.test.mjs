import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const EXPECTED_TIERS = ['trailblazer', 'community_partner', 'supporter'];

const astroSource = readFileSync(new URL('../src/content.config.ts', import.meta.url), 'utf8');
const keystaticSource = readFileSync(new URL('../keystatic.config.ts', import.meta.url), 'utf8');

function blockBetween(source, startMarker, endMarker) {
  const start = source.indexOf(startMarker);
  assert.notEqual(start, -1, `missing source marker: ${startMarker}`);

  const end = source.indexOf(endMarker, start + startMarker.length);
  assert.notEqual(end, -1, `missing source marker: ${endMarker}`);

  return source.slice(start, end);
}

function quotedValues(source) {
  return [...source.matchAll(/'([^']+)'/g)].map(([, value]) => value);
}

function readAstroSponsorContract() {
  const sponsorBlock = blockBetween(
    astroSource,
    'const sponsors = defineCollection({',
    '// --- Singleton pages',
  );
  const tierMatch = sponsorBlock.match(
    /tier:\s*z\s*\.enum\(\[([^\]]+)\]\)\s*\.default\('([^']+)'\)/s,
  );

  assert.ok(tierMatch, 'missing Astro sponsor tier enum and default');

  return {
    tiers: quotedValues(tierMatch[1]),
    defaultValue: tierMatch[2],
    strict: /\}\)\s*\.strict\(\),\s*\n\}\);/.test(sponsorBlock),
  };
}

function readKeystaticSponsorContract() {
  const sponsorBlock = blockBetween(
    keystaticSource,
    '    sponsors: collection({',
    '    wax_entries: collection({',
  );
  const tierBlock = blockBetween(
    sponsorBlock,
    'tier: fields.select({',
    '        url: fields.url(',
  );
  const defaultMatch = tierBlock.match(/defaultValue:\s*'([^']+)'/);

  assert.ok(defaultMatch, 'missing Keystatic sponsor tier default');

  return {
    tiers: [...tierBlock.matchAll(/value:\s*'([^']+)'/g)].map(([, value]) => value),
    defaultValue: defaultMatch[1],
  };
}

test('keeps the Astro sponsor tier schema exact and strict', () => {
  assert.deepEqual(readAstroSponsorContract(), {
    tiers: EXPECTED_TIERS,
    defaultValue: 'supporter',
    strict: true,
  });
});

test('keeps the Keystatic sponsor tier options exact', () => {
  assert.deepEqual(readKeystaticSponsorContract(), {
    tiers: EXPECTED_TIERS,
    defaultValue: 'supporter',
  });
});

test('keeps Astro and Keystatic sponsor tiers synchronized', () => {
  const astro = readAstroSponsorContract();
  const keystatic = readKeystaticSponsorContract();

  assert.deepEqual(keystatic.tiers, astro.tiers);
  assert.equal(keystatic.defaultValue, astro.defaultValue);
});

test('excludes the legacy friend tier from both sponsor schema blocks', () => {
  assert.equal(readAstroSponsorContract().tiers.includes('friend'), false);
  assert.equal(readKeystaticSponsorContract().tiers.includes('friend'), false);
});
