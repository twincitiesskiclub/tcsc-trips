import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const EXPECTED_TIERS = ['trailblazer', 'community_partner', 'supporter'];
const SPONSOR_PAGE_FIELDS = [
  'headline',
  'intro',
  'impact_heading',
  'impact_intro',
  'impact_items',
  'recognition_heading',
  'recognition_body',
  'recognition_caption',
  'priorities_heading',
  'priorities_intro',
  'priority_items',
  'contact_heading',
  'contact_body',
  'contact_email',
  'contact_cta_label',
  'disclosure',
];
const SPONSOR_PAGE_ITEM_FIELDS = ['title', 'detail'];

const astroSource = readFileSync(new URL('../src/content.config.ts', import.meta.url), 'utf8');
const keystaticSource = readFileSync(new URL('../keystatic.config.ts', import.meta.url), 'utf8');
const sponsorPageSource = readFileSync(
  new URL('../src/content/pages/sponsors_page.yaml', import.meta.url),
  'utf8',
);
const sponsorPageContractUrl = new URL('../src/lib/sponsorPageContract.js', import.meta.url);
const MALFORMED_EMAILS = [
  'a@b.c',
  'x@y..com',
  'a@-b.com',
  'a@b.com.',
  'a..b@example.com',
];

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

function propertyNamesAtIndent(source, spaces) {
  return [...source.matchAll(new RegExp(`^ {${spaces}}([a-z_]+):`, 'gm'))].map(
    ([, name]) => name,
  );
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

function readAstroSponsorPageContract() {
  const itemBlock = blockBetween(
    astroSource,
    'const sponsorPageItem = z',
    'const sponsors_page = defineCollection({',
  );
  const pageBlock = blockBetween(
    astroSource,
    'const sponsors_page = defineCollection({',
    '// /extra-training-fun',
  );

  return {
    fields: propertyNamesAtIndent(pageBlock, 6),
    itemFields: propertyNamesAtIndent(itemBlock, 4),
    outerStrict: /\}\)\s*\.strict\(\),\s*\n\}\);\s*$/.test(pageBlock),
    itemStrict: /\}\)\s*\.strict\(\);\s*$/.test(itemBlock),
    nonEmptyArrays: {
      impact_items: /impact_items:\s*z\.array\(sponsorPageItem\)\.min\(1\)/.test(pageBlock),
      priority_items: /priority_items:\s*z\.array\(sponsorPageItem\)\.min\(1\)/.test(pageBlock),
    },
    emailValidation: {
      sharedPatternImport: astroSource.includes(
        "import { SPONSOR_CONTACT_EMAIL_PATTERN } from './lib/sponsorPageContract.js';",
      ),
      sharedPatternUse:
        /contact_email:\s*z\s*\.string\(\)\s*\.regex\(\s*SPONSOR_CONTACT_EMAIL_PATTERN,\s*'Enter a valid email address\.'\s*\)/s.test(
          pageBlock,
        ),
    },
  };
}

function readKeystaticSponsorPageContract() {
  const pageBlock = blockBetween(
    keystaticSource,
    '    sponsors_page: singleton({',
    '    // Photos on the two pages below',
  );
  const impactItemsBlock = blockBetween(
    pageBlock,
    '        impact_items: fields.array(',
    '        recognition_heading:',
  );
  const priorityItemsBlock = blockBetween(
    pageBlock,
    '        priority_items: fields.array(',
    '        contact_heading:',
  );
  const impactItemObject = blockBetween(
    impactItemsBlock,
    '          fields.object({',
    '          }),',
  );
  const priorityItemObject = blockBetween(
    priorityItemsBlock,
    '          fields.object({',
    '          }),',
  );
  const emailBlock = blockBetween(
    pageBlock,
    '        contact_email: fields.text({',
    '        contact_cta_label:',
  );
  const messageMatch = emailBlock.match(/message:\s*'([^']+)'/);

  return {
    fields: propertyNamesAtIndent(pageBlock, 8),
    impactItemFields: propertyNamesAtIndent(impactItemObject, 12),
    priorityItemFields: propertyNamesAtIndent(priorityItemObject, 12),
    nonEmptyArrays: {
      impact_items: /validation:\s*\{\s*length:\s*\{\s*min:\s*1\s*\}\s*\}/.test(
        impactItemsBlock,
      ),
      priority_items: /validation:\s*\{\s*length:\s*\{\s*min:\s*1\s*\}\s*\}/.test(
        priorityItemsBlock,
      ),
    },
    emailValidation: {
      isRequired: /isRequired:\s*true/.test(emailBlock),
      sharedPatternImport: keystaticSource.includes(
        "import { SPONSOR_CONTACT_EMAIL_PATTERN } from './src/lib/sponsorPageContract.js';",
      ),
      sharedPatternUse: /regex:\s*SPONSOR_CONTACT_EMAIL_PATTERN/.test(emailBlock),
      message: messageMatch?.[1],
    },
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

test('keeps the sponsors-page field model exact and synchronized', () => {
  const astro = readAstroSponsorPageContract();
  const keystatic = readKeystaticSponsorPageContract();

  assert.deepEqual(astro.fields, SPONSOR_PAGE_FIELDS);
  assert.deepEqual(keystatic.fields, SPONSOR_PAGE_FIELDS);
  assert.deepEqual(keystatic.fields, astro.fields);
});

test('keeps sponsors-page outer and nested item shapes strict and exact', () => {
  const astro = readAstroSponsorPageContract();
  const keystatic = readKeystaticSponsorPageContract();

  assert.equal(astro.outerStrict, true);
  assert.equal(astro.itemStrict, true);
  assert.deepEqual(astro.itemFields, SPONSOR_PAGE_ITEM_FIELDS);
  assert.deepEqual(keystatic.impactItemFields, SPONSOR_PAGE_ITEM_FIELDS);
  assert.deepEqual(keystatic.priorityItemFields, SPONSOR_PAGE_ITEM_FIELDS);
});

test('requires non-empty impact and priority arrays in both schemas', () => {
  assert.deepEqual(readAstroSponsorPageContract().nonEmptyArrays, {
    impact_items: true,
    priority_items: true,
  });
  assert.deepEqual(readKeystaticSponsorPageContract().nonEmptyArrays, {
    impact_items: true,
    priority_items: true,
  });
});

test('uses the shared sponsor contact email contract in both schemas', () => {
  assert.deepEqual(readAstroSponsorPageContract().emailValidation, {
    sharedPatternImport: true,
    sharedPatternUse: true,
  });
  assert.deepEqual(readKeystaticSponsorPageContract().emailValidation, {
    isRequired: true,
    sharedPatternImport: true,
    sharedPatternUse: true,
    message: 'Enter a valid email address.',
  });
});

test('rejects malformed sponsor emails and accepts the configured address', async () => {
  const { SPONSOR_CONTACT_EMAIL_PATTERN } = await import(sponsorPageContractUrl.href);
  const configuredEmail = sponsorPageSource.match(/^contact_email:\s*(\S+)\s*$/m)?.[1];

  assert.ok(configuredEmail, 'missing configured sponsor contact email');
  assert.equal(SPONSOR_CONTACT_EMAIL_PATTERN.test(configuredEmail), true);

  for (const malformedEmail of MALFORMED_EMAILS) {
    assert.equal(
      SPONSOR_CONTACT_EMAIL_PATTERN.test(malformedEmail),
      false,
      `accepted malformed sponsor email: ${malformedEmail}`,
    );
  }
});
