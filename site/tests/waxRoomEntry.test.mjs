import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import test from 'node:test';

const title = 'Stone Grind or Hotbox? When Skis Need a Second Wind';
const route = '/wax-room/stone-grind-or-hotbox/';
const linkTarget = route.slice(0, -1);
const sourceUrl = new URL(
  '../src/content/wax_entries/stone-grind-or-hotbox.mdoc',
  import.meta.url,
);
const detailUrl = new URL('../dist/wax-room/stone-grind-or-hotbox/index.html', import.meta.url);

const decodeHtml = (text) =>
  text
    .replaceAll('&#39;', "'")
    .replaceAll('&#x27;', "'")
    .replaceAll('&apos;', "'")
    .replaceAll('&quot;', '"')
    .replaceAll('&amp;', '&');

const toText = (html) =>
  decodeHtml(
    html
      .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, ' ')
      .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, ' ')
      .replace(/<[^>]+>/g, ' '),
  )
    .replace(/\s+/g, ' ')
    .trim();

test('publishes the contingency Wax Room field guide', () => {
  assert.equal(existsSync(sourceUrl), true, 'Wax Room entry source must exist');
  assert.equal(existsSync(detailUrl), true, `Astro must generate ${route}`);

  const source = readFileSync(sourceUrl, 'utf8');
  const homeHtml = readFileSync(new URL('../dist/index.html', import.meta.url), 'utf8');
  const indexHtml = readFileSync(new URL('../dist/wax-room/index.html', import.meta.url), 'utf8');
  const detailHtml = readFileSync(detailUrl, 'utf8');

  for (const [surface, html] of [
    ['home page', homeHtml],
    ['Wax Room index', indexHtml],
    ['Wax Room detail', detailHtml],
  ]) {
    assert.ok(toText(html).includes(title), `${surface} must include the article title`);
  }

  for (const [surface, html] of [
    ['home page', homeHtml],
    ['Wax Room index', indexHtml],
  ]) {
    assert.match(
      html,
      new RegExp(`href=["']${linkTarget}["']`),
      `${surface} must link to ${route}`,
    );
  }

  assert.match(source, /^date: 2026-07-19$/m);
  assert.doesNotMatch(source, /^(?:author_name|photo|conditions_snapshot):/m);

  for (const heading of [
    'What a stone grind changes',
    'What a hotbox changes',
    'Five useful things to tell the shop',
    'The short version',
  ]) {
    assert.match(source, new RegExp(`^## ${heading}$`, 'm'), `missing heading: ${heading}`);
  }

  assert.doesNotMatch(source, /\$\s*\d/, 'article must not include a dollar price');
  assert.doesNotMatch(
    source,
    /\b(?:discount(?:ed|s)?|percent off|save \d+%?|\d+% off)\b/i,
    'article must not include a discount claim',
  );
  assert.doesNotMatch(source, /—/, 'article must not include an em dash');
  assert.doesNotMatch(source, /!/, 'article must not include an exclamation point');
});
