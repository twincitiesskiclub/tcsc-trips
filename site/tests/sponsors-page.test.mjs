import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const sponsorsHtml = readFileSync(new URL('../dist/sponsors/index.html', import.meta.url), 'utf8');
const homeHtml = readFileSync(new URL('../dist/index.html', import.meta.url), 'utf8');

const toText = (html) =>
  html
    .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replaceAll('&#39;', "'")
    .replaceAll('&#x27;', "'")
    .replaceAll('&apos;', "'")
    .replaceAll('&quot;', '"')
    .replaceAll('&amp;', '&')
    .replace(/\s+/g, ' ')
    .trim();

const sponsorText = toText(sponsorsHtml);
const homeText = toText(homeHtml);
const anchorTags = sponsorsHtml.match(/<a\b[^>]*>/gi) ?? [];
const anchorFor = (href) => anchorTags.find((tag) => tag.includes(`href="${href}"`));

test('renders the approved recognition and impact copy', () => {
  for (const phrase of [
    'Our sponsors',
    'Trailblazer Partners',
    'Sponsor support helped TCSC...',
    'Host team waxing sessions',
    'Pre-Birkie and Great Bear Chase',
    'Build a useful team base',
    'Visible support at team events',
    'six team jackets featuring sponsor logos',
    'What continued support makes possible',
    'products containing PFAS',
    'Coaching and training capacity',
    'Shared team equipment',
    'Interested in supporting TCSC?',
    'Sponsor recognition acknowledges support and does not constitute endorsement',
  ]) {
    assert.ok(sponsorText.includes(phrase), `missing page copy: ${phrase}`);
  }
});

test('keeps current sponsor links accessible and qualified', () => {
  for (const [href, name] of [
    ['https://tcomn.com/', 'Twin Cities Orthopedics'],
    ['https://www.kwiktrip.com/', 'Kwik Trip'],
  ]) {
    const anchor = anchorFor(href);
    assert.ok(anchor, `missing sponsor link: ${href}`);
    assert.match(anchor, /\brel="sponsored"/);
    assert.ok(sponsorsHtml.includes(`alt="${name} website"`));
  }

  assert.ok(sponsorsHtml.includes('href="mailto:contact@twincitiesskiclub.org"'));
  assert.ok(
    sponsorsHtml.includes(
      'alt="A large group of TCSC members posing with roller skis and poles after a summer training session"',
    ),
  );
  assert.ok(
    sponsorsHtml.includes(
      'alt="A TCSC member wearing a black team jacket with Kwik Trip and Twin Cities Orthopedics logos beside another member and the Great Bear Chase mascot"',
    ),
  );
});

test('keeps prices and highest-level claims off the public page', () => {
  assert.doesNotMatch(sponsorText, /highest level/i);
  assert.doesNotMatch(sponsorText, /\$(?:2|4|6)(?:,?000|k)\b/i);
});

test('keeps the home sponsor strip compact and unheaded', () => {
  assert.equal(homeText.includes('Trailblazer Partners'), false);
  assert.ok(homeHtml.includes('alt="Twin Cities Orthopedics website"'));
  assert.ok(homeHtml.includes('alt="Kwik Trip website"'));
});
