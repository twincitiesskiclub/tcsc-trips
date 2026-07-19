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

const bodyHtml = (html) => {
  const body = html.match(/<body\b[^>]*>([\s\S]*?)<\/body>/i);
  assert.ok(body, 'built page must include a body element');
  return body[1];
};

test('publishes the contingency Wax Room field guide', () => {
  assert.equal(existsSync(sourceUrl), true, 'Wax Room entry source must exist');
  assert.equal(existsSync(detailUrl), true, `Astro must generate ${route}`);

  const source = readFileSync(sourceUrl, 'utf8');
  const homeHtml = readFileSync(new URL('../dist/index.html', import.meta.url), 'utf8');
  const indexHtml = readFileSync(new URL('../dist/wax-room/index.html', import.meta.url), 'utf8');
  const detailHtml = readFileSync(detailUrl, 'utf8');
  const homeBody = bodyHtml(homeHtml);
  const indexBody = bodyHtml(indexHtml);
  const detailBody = bodyHtml(detailHtml);

  for (const [surface, body] of [
    ['home page', homeBody],
    ['Wax Room index', indexBody],
    ['Wax Room detail', detailBody],
  ]) {
    assert.ok(toText(body).includes(title), `${surface} must visibly include the title`);
  }

  const detailH1 = detailBody.match(/<h1\b[^>]*>([\s\S]*?)<\/h1>/i);
  assert.ok(detailH1, 'Wax Room detail must include an h1');
  assert.equal(toText(detailH1[1]), title, 'Wax Room detail h1 must be the article title');

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

  assert.match(source, /Shop labels vary\./);
  assert.match(source, /Fine, medium, and coarse[^.]*structure grades/i);
  assert.match(source, /Universal[^.]*(?:broader-use|broader use)[^.]*(?:pattern|menu label)/i);
  assert.match(source, /None of these labels is a slow-to-fast ranking\./);

  const checklistItems = source.match(/^\d+\. .+$/gm) ?? [];
  assert.equal(checklistItems.length, 5, 'shop checklist must contain exactly five items');
  assert.match(checklistItems.join('\n'), /classic or skate/i);
  assert.match(checklistItems.join('\n'), /technique affects structure selection/i);

  assert.doesNotMatch(source, /\$\s*\d/, 'article must not include a dollar price');
  assert.doesNotMatch(
    source,
    /\b(?:discount(?:ed|s)?|percent off|save \d+%?|\d+% off)\b/i,
    'article must not include a discount claim',
  );
  assert.doesNotMatch(source, /—/, 'article must not include an em dash');
  assert.doesNotMatch(source, /!/, 'article must not include an exclamation point');
});
