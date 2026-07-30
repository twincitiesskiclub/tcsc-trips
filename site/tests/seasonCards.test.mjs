import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { JSDOM } from 'jsdom';

import { seasonTypeToSlug } from '../src/lib/seasonSlug.ts';

test('maps a database season_type to its content file slug', () => {
  assert.equal(seasonTypeToSlug('fall/winter'), 'fall-winter');
  assert.equal(seasonTypeToSlug('spring/summer'), 'spring-summer');
  assert.equal(seasonTypeToSlug('legacy'), 'legacy');
  assert.equal(seasonTypeToSlug(''), '');
  assert.equal(seasonTypeToSlug(undefined), '');
});

test('the season cards render a registration line', () => {
  const html = readFileSync(new URL('../dist/index.html', import.meta.url), 'utf8');
  const { document } = new JSDOM(html).window;
  const notes = document.querySelectorAll('[data-season-card-note]');
  assert.ok(notes.length > 0, 'expected at least one season card note');
  for (const note of notes) {
    assert.ok(note.textContent.trim().length > 0, 'card note should not be empty');
  }
});

test('the card fields are documented as fallback-only', () => {
  const config = readFileSync(
    new URL('../src/content.config.ts', import.meta.url),
    'utf8',
  );
  assert.match(config, /fallback/i, 'card schema should say these are fallbacks');
});
