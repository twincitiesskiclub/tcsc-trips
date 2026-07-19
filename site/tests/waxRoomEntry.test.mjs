import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import test from 'node:test';
import { JSDOM } from 'jsdom';

const title = 'Stone Grind or Hotbox? When Skis Need a Second Wind';
const route = '/wax-room/stone-grind-or-hotbox/';
const linkTarget = route.slice(0, -1);
const headings = [
  'What a stone grind changes',
  'What a hotbox changes',
  'Five useful things to tell the shop',
  'The short version',
];
const sourceUrl = new URL(
  '../src/content/wax_entries/stone-grind-or-hotbox.mdoc',
  import.meta.url,
);
const detailUrl = new URL('../dist/wax-room/stone-grind-or-hotbox/index.html', import.meta.url);

const toText = (node) => node.textContent.replace(/\s+/g, ' ').trim();

test('publishes the contingency Wax Room field guide', () => {
  assert.equal(existsSync(sourceUrl), true, 'Wax Room entry source must exist');
  assert.equal(existsSync(detailUrl), true, `Astro must generate ${route}`);

  const source = readFileSync(sourceUrl, 'utf8');
  const homeHtml = readFileSync(new URL('../dist/index.html', import.meta.url), 'utf8');
  const indexHtml = readFileSync(new URL('../dist/wax-room/index.html', import.meta.url), 'utf8');
  const detailHtml = readFileSync(detailUrl, 'utf8');
  const homeDocument = new JSDOM(homeHtml).window.document;
  const indexDocument = new JSDOM(indexHtml).window.document;
  const detailDocument = new JSDOM(detailHtml).window.document;

  for (const [surface, document] of [
    ['home page', homeDocument],
    ['Wax Room index', indexDocument],
  ]) {
    const titleLinks = [...document.querySelectorAll('a')].filter((anchor) =>
      toText(anchor).includes(title),
    );
    assert.equal(titleLinks.length, 1, `${surface} must include one title-bearing anchor`);
    assert.equal(
      titleLinks[0].getAttribute('href'),
      linkTarget,
      `${surface} title must link to ${route}`,
    );
  }

  const article = detailDocument.querySelector('main > article');
  assert.ok(article, 'Wax Room detail must render the entry as an article');
  const h1s = [...article.querySelectorAll('h1')];
  assert.equal(h1s.length, 1, 'rendered entry article must include exactly one h1');
  assert.equal(toText(h1s[0]), title, 'Wax Room detail h1 must be the article title');
  assert.deepEqual([...article.querySelectorAll('h2')].map(toText), headings);
  assert.equal(
    article.querySelectorAll('ol > li').length,
    5,
    'rendered checklist must have five items',
  );

  const articleText = toText(article);
  for (const fact of [
    'Eleven pairs joined a coordinated Finn Sisu service order.',
    "Finn Sisu's universal grind for a Midwest/manmade mix.",
    'A stone grind permanently cuts structure into the ski base.',
    'A hotbox uses controlled warmth to condition the base with wax over time.',
    'None of these labels is a slow-to-fast ranking.',
    'Choose both only when both jobs make sense for that ski.',
  ]) {
    assert.ok(articleText.includes(fact), `rendered article must include: ${fact}`);
  }
  assert.equal(
    [...article.querySelectorAll('*')].some((element) =>
      /^By\s+.+\s+·\s+(?:coach|member|board)$/i.test(toText(element)),
    ),
    false,
    'entry article must not render a byline',
  );
  assert.equal(article.querySelector('aside'), null, 'entry article must not render conditions');
  assert.equal(article.querySelector('img'), null, 'entry article must not render a photo');

  assert.match(source, /^date: 2026-07-19$/m);
  assert.doesNotMatch(source, /^(?:author_name|photo|conditions_snapshot):/m);

  for (const heading of headings) {
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
