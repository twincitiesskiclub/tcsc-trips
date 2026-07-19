import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import test from 'node:test';

const source = {
  home: readFileSync(new URL('../src/content/pages/home.yaml', import.meta.url), 'utf8'),
  ctaStrip: readFileSync(new URL('../src/components/CTAStrip.astro', import.meta.url), 'utf8'),
  homePage: readFileSync(new URL('../src/pages/index.astro', import.meta.url), 'utf8'),
  dryTri: readFileSync(new URL('../src/content/pages/dry_tri.mdoc', import.meta.url), 'utf8'),
  extraTraining: readFileSync(
    new URL('../src/content/pages/extra_training.mdoc', import.meta.url),
    'utf8',
  ),
  community: readFileSync(
    new URL('../src/content/pages/community.mdoc', import.meta.url),
    'utf8',
  ),
  racing: readFileSync(new URL('../src/content/pages/racing.mdoc', import.meta.url), 'utf8'),
  sponsorsPage: readFileSync(new URL('../src/pages/sponsors.astro', import.meta.url), 'utf8'),
};

const html = {
  home: readFileSync(new URL('../dist/index.html', import.meta.url), 'utf8'),
  dryTri: readFileSync(new URL('../dist/dry-tri/index.html', import.meta.url), 'utf8'),
  extraTraining: readFileSync(
    new URL('../dist/extra-training-fun/index.html', import.meta.url),
    'utf8',
  ),
  community: readFileSync(new URL('../dist/community/index.html', import.meta.url), 'utf8'),
  racing: readFileSync(new URL('../dist/racing/index.html', import.meta.url), 'utf8'),
  sponsors: readFileSync(new URL('../dist/sponsors/index.html', import.meta.url), 'utf8'),
};

const MISSION =
  'Twin Cities Ski Club is a 501(c)(3) nonprofit dedicated to fostering a supportive community for young adults (ages 21-35) by promoting a healthy lifestyle through cross-country ski training sessions and educational programming.';
const MARKETING_ORIGIN = 'https://twincitiesskiclub.org';
const REGISTRATION_SUBHEAD = 'Returning members Aug 28; new members Sep 3.';
const DRY_TRI_2026 =
  'Planning for 2026 is underway. The date and registration details will be posted here when confirmed.';
const DRY_TRI_RESULTS = 'https://my.raceresult.com/361087/results';

function yamlScalar(document, key) {
  const lines = document.split('\n');
  const index = lines.findIndex((line) => line.startsWith(`${key}:`));
  assert.notEqual(index, -1, `missing source field: ${key}`);

  const value = lines[index].slice(key.length + 1).trim();
  if (!['>-', '>', '|-', '|'].includes(value)) return value;

  const continuation = [];
  for (const line of lines.slice(index + 1)) {
    if (!/^\s+\S/.test(line)) break;
    continuation.push(line.trim());
  }
  return continuation.join(' ');
}

function decodeHtml(text) {
  return text
    .replaceAll('&#39;', "'")
    .replaceAll('&#x27;', "'")
    .replaceAll('&apos;', "'")
    .replaceAll('&quot;', '"')
    .replaceAll('&amp;', '&');
}

function toText(document) {
  return decodeHtml(
    document
      .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, ' ')
      .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, ' ')
      .replace(/<[^>]+>/g, ' '),
  )
    .replace(/\s+/g, ' ')
    .trim();
}

function sectionById(document, id) {
  const opening = new RegExp(`<section\\b[^>]*\\bid="${id}"[^>]*>`, 'i').exec(document);
  assert.ok(opening, `missing built section target: #${id}`);

  const start = opening.index;
  const end = document.indexOf('</section>', start + opening[0].length);
  assert.notEqual(end, -1, `missing closing section for #${id}`);
  return document.slice(start, end + '</section>'.length);
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function htmlFiles(directory) {
  return readdirSync(directory, { recursive: true, withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith('.html'))
    .map((entry) => readFileSync(`${entry.parentPath}/${entry.name}`, 'utf8'));
}

test('wires the confirmed fall registration copy to the home CTA target', () => {
  assert.equal(yamlScalar(source.home, 'cta_coming_soon_label'), 'Fall registration dates');
  assert.equal(
    yamlScalar(source.home, 'cta_coming_soon_url'),
    `${MARKETING_ORIGIN}/#registration`,
  );
  assert.equal(yamlScalar(source.home, 'mission_paragraph'), MISSION);

  assert.match(source.ctaStrip, /\bid\?: string;/);
  assert.match(source.ctaStrip, /const \{ heading, subhead, cta_label, cta_url, id \} = Astro\.props;/);
  assert.match(
    source.ctaStrip,
    /<section id=\{id\} class="bg-navy border-t-\[3px\] border-coral text-paper">/,
  );
  assert.match(source.homePage, /<CTAStrip\s+id="registration"/);
  assert.ok(source.homePage.includes(REGISTRATION_SUBHEAD));

  const registration = sectionById(html.home, 'registration');
  const registrationText = toText(registration);
  assert.ok(registrationText.includes(REGISTRATION_SUBHEAD));
  const cta = registration.match(
    /<a\b([^>]*)>Fall registration dates<\/a>/i,
  );
  assert.ok(cta, 'registration CTA must render as a title-bearing anchor');
  const href = cta[1].match(/\bhref=(['"])(.*?)\1/i);
  assert.ok(href, 'registration CTA must include an href');

  const target = new URL(decodeHtml(href[2]), MARKETING_ORIGIN);
  assert.equal(target.origin, MARKETING_ORIGIN);
  assert.equal(target.pathname, '/');
  assert.equal(target.hash, '#registration');
  const targetId = target.hash.slice(1);
  assert.equal(
    (html.home.match(new RegExp(`\\bid=['"]${escapeRegExp(targetId)}['"]`, 'gi')) ?? [])
      .length,
    1,
    'registration CTA hash must resolve to exactly one target in the built home page',
  );
  assert.ok(toText(html.home).includes(MISSION));
});

test('publishes only confirmed Dry Tri registration details while retaining 2025 history', () => {
  assert.doesNotMatch(source.dryTri, /^register_url:/m);
  assert.ok(source.dryTri.includes(DRY_TRI_2026));
  assert.match(source.dryTri, new RegExp(`^results_url: ${DRY_TRI_RESULTS}$`, 'm'));
  assert.ok(source.dryTri.includes('The first Dry Tri was held on October 25, 2025.'));

  const dryTriText = toText(html.dryTri);
  assert.ok(dryTriText.includes(DRY_TRI_2026));
  assert.ok(dryTriText.includes('The first Dry Tri was held on October 25, 2025.'));
  assert.ok(html.dryTri.includes(`href="${DRY_TRI_RESULTS}"`));
  assert.doesNotMatch(html.dryTri, /href="https:\/\/tcsc\.ski\/tri\/?"/i);
  assert.doesNotMatch(dryTriText, /Registration for the 2026 race opens/i);
});

test('identifies informal workouts as member activities in source and rendered copy', () => {
  assert.equal(
    yamlScalar(source.extraTraining, 'intro'),
    'Coached practices run Tuesday and Thursday. The rest of the week, members organize their own workouts: track mornings, long rollerskis, open-water swims. Every member is welcome, and there is no signup.',
  );
  assert.ok(
    source.community.includes(
      'detail: Track mornings, long rollerskis, open-water swims. No signup; all members welcome.',
    ),
  );

  assert.ok(toText(html.extraTraining).includes('Every member is welcome, and there is no signup.'));
  assert.ok(
    toText(html.community).includes(
      'Track mornings, long rollerskis, open-water swims. No signup; all members welcome.',
    ),
  );
});

test('dates the Tour de Finn participation claim in source and rendered copy', () => {
  assert.ok(source.racing.includes('notes: Two TCSC teams participated in 2026.'));
  assert.ok(toText(html.racing).includes('Two TCSC teams participated in 2026.'));
});

test('keeps the 2.1 nonprofit fact out of the sponsor masthead', () => {
  assert.doesNotMatch(
    source.sponsorsPage,
    /facts=\{\[\{ value: '501\(c\)\(3\) nonprofit', label: 'Status' \}\]\}/,
  );

  const mainStart = html.sponsors.indexOf('<main id="main"');
  assert.notEqual(mainStart, -1, 'missing sponsor main-content boundary');
  const masthead = html.sponsors.slice(0, mainStart);
  assert.equal(toText(masthead).includes('501(c)(3) nonprofit Status'), false);
});

test('keeps rejected generic and undated phrases out of public content', () => {
  const publicSource = [
    source.home,
    source.dryTri,
    source.extraTraining,
    source.community,
    source.racing,
  ].join('\n');
  const distDirectory = new URL('../dist/', import.meta.url);
  const publicBuiltText = htmlFiles(distDirectory).map(toText).join('\n');

  for (const rejected of [
    /\bthis year\b/i,
    /\beveryone welcome\b/i,
  ]) {
    assert.doesNotMatch(publicSource, rejected);
    assert.doesNotMatch(publicBuiltText, rejected);
  }
});
