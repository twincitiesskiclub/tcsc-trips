import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { JSDOM } from 'jsdom';
import { parse as parseYaml } from 'yaml';

import { seasonTypeToSlug } from '../src/lib/seasonSlug.ts';

test('maps a database season_type to its content file slug', () => {
  assert.equal(seasonTypeToSlug('fall/winter'), 'fall-winter');
  assert.equal(seasonTypeToSlug('spring/summer'), 'spring-summer');
  assert.equal(seasonTypeToSlug('legacy'), 'legacy');
  assert.equal(seasonTypeToSlug(''), '');
  assert.equal(seasonTypeToSlug(undefined), '');
});

// The test fixture (scripts/test-build.mjs) serves exactly one database
// season, season_type 'fall/winter', with windows computed relative to
// `Date.now()`. So on every suite run the Fall/Winter card must be
// database-derived (its note text follows cardNote's shape and can't match
// the committed copy, since the committed copy has fixed 2026 dates that
// drift out of sync with the fixture's rolling window), while the
// Spring/Summer card has no matching database season and must fall back to
// its committed `registration_note` verbatim.
test('the Fall/Winter card note is database-derived, not the committed fallback', () => {
  const html = readFileSync(new URL('../dist/index.html', import.meta.url), 'utf8');
  const { document } = new JSDOM(html).window;

  const card = document.querySelector('[data-season-card="fall-winter"]');
  assert.ok(card, 'expected a Fall/Winter card in the built page');
  const note = card.querySelector('[data-season-card-note]');
  assert.ok(note, 'expected the Fall/Winter card to carry a registration note');
  const noteText = note.textContent.trim();

  assert.match(
    noteText,
    /^\d{4} registration: returning members [A-Z][a-z]{2} \d{1,2} · new members [A-Z][a-z]{2} \d{1,2}$/,
    'expected the cardNote() shape produced from the database windows',
  );

  const fallWinterYaml = readFileSync(
    new URL('../src/content/practice_seasons/fall-winter.yaml', import.meta.url),
    'utf8',
  );
  const committedNote = parseYaml(fallWinterYaml).registration_note;
  assert.notEqual(
    noteText,
    committedNote,
    'Fall/Winter note matched the committed copy instead of the database-derived value',
  );
});

test('the Spring/Summer card note falls back to the committed copy verbatim', () => {
  const html = readFileSync(new URL('../dist/index.html', import.meta.url), 'utf8');
  const { document } = new JSDOM(html).window;

  const card = document.querySelector('[data-season-card="spring-summer"]');
  assert.ok(card, 'expected a Spring/Summer card in the built page');
  const note = card.querySelector('[data-season-card-note]');
  assert.ok(note, 'expected the Spring/Summer card to carry a registration note');

  const springSummerYaml = readFileSync(
    new URL('../src/content/practice_seasons/spring-summer.yaml', import.meta.url),
    'utf8',
  );
  const committedNote = parseYaml(springSummerYaml).registration_note;

  assert.equal(note.textContent.trim(), committedNote);
});

test('the card fields are documented as fallback-only', () => {
  const config = readFileSync(
    new URL('../src/content.config.ts', import.meta.url),
    'utf8',
  );
  assert.match(config, /fallback/i, 'card schema should say these are fallbacks');
});
