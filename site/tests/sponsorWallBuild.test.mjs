import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const TIER_LABELS = ['Trailblazer Partners', 'Community Partners', 'Supporters'];

const sponsorsHtml = readFileSync(new URL('../dist/sponsors/index.html', import.meta.url), 'utf8');
const homeHtml = readFileSync(new URL('../dist/index.html', import.meta.url), 'utf8');

function elementContaining(html, openingTag, marker) {
  const markerIndex = html.indexOf(marker);
  assert.notEqual(markerIndex, -1, `missing built output marker: ${marker}`);

  const start = html.lastIndexOf(openingTag, markerIndex);
  assert.notEqual(start, -1, `missing ${openingTag} before ${marker}`);

  const tagName = openingTag.slice(1);
  const closingTag = `</${tagName}>`;
  const end = html.indexOf(closingTag, markerIndex);
  assert.notEqual(end, -1, `missing ${closingTag} after ${marker}`);

  return html.slice(start, end + closingTag.length);
}

function elementStartingAt(html, openingMarker, tagName) {
  const start = html.indexOf(openingMarker);
  assert.notEqual(start, -1, `missing built output marker: ${openingMarker}`);

  const closingTag = `</${tagName}>`;
  const end = html.indexOf(closingTag, start + openingMarker.length);
  assert.notEqual(end, -1, `missing ${closingTag} after ${openingMarker}`);

  return html.slice(start, end + closingTag.length);
}

function linkedLogos(html) {
  return [...html.matchAll(/<a\b([^>]*)>\s*<img\b([^>]*)>\s*<\/a>/g)].map(
    ([, anchorAttributes, imageAttributes]) => ({ anchorAttributes, imageAttributes }),
  );
}

function attribute(attributes, name) {
  return attributes.match(new RegExp(`\\b${name}="([^"]*)"`))?.[1];
}

const sponsorsMain = elementStartingAt(sponsorsHtml, '<main id="main"', 'main');
const homeSponsorSection = elementContaining(homeHtml, '<section', 'About our sponsors');
const allLinkedLogos = [...linkedLogos(sponsorsMain), ...linkedLogos(homeSponsorSection)];

test('renders the Trailblazer heading when it is the only populated wall tier', () => {
  assert.match(sponsorsMain, /<h2\b[^>]*>Trailblazer Partners<\/h2>/);
  assert.doesNotMatch(sponsorsMain, /Community Partners|Supporters/);
});

test('keeps the home sponsor strip free of tier headings', () => {
  for (const label of TIER_LABELS) {
    assert.equal(homeSponsorSection.includes(label), false);
  }
});

test('keeps linked sponsor logos in the same tab', () => {
  assert.ok(allLinkedLogos.length > 0, 'expected linked sponsor logos in built output');

  for (const { anchorAttributes } of allLinkedLogos) {
    assert.equal(attribute(anchorAttributes, 'target'), undefined);
  }
});

test('qualifies linked sponsor logo anchors as sponsored', () => {
  assert.ok(allLinkedLogos.length > 0, 'expected linked sponsor logos in built output');

  for (const { anchorAttributes } of allLinkedLogos) {
    const rel = attribute(anchorAttributes, 'rel') ?? '';
    assert.equal(rel.split(/\s+/).includes('sponsored'), true);
  }
});

test('names linked sponsor logo destinations in image alt text', () => {
  assert.ok(allLinkedLogos.length > 0, 'expected linked sponsor logos in built output');

  for (const { imageAttributes } of allLinkedLogos) {
    assert.match(attribute(imageAttributes, 'alt') ?? '', /\S website$/);
  }
});
