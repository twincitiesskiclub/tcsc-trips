import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const sponsorsHtml = readFileSync(new URL('../dist/sponsors/index.html', import.meta.url), 'utf8');
const homeHtml = readFileSync(new URL('../dist/index.html', import.meta.url), 'utf8');

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

const sponsorText = toText(sponsorsHtml);
const homeText = toText(homeHtml);
const sponsorCommercialSurface = [
  sponsorText,
  ...[...sponsorsHtml.matchAll(/\b(?:alt|title|aria-label|content)="([^"]*)"/gi)].map(
    ([, value]) => decodeHtml(value),
  ),
].join('. ');
const completedRows = [
  [
    'Host team waxing sessions',
    'Two team drills support organized waxing sessions, and shared waxing supplies remain available to members whether or not they race.',
  ],
  [
    'Make team travel easier',
    'Rental vans carried food, equipment, and team supplies to the Pre-Birkie and Great Bear Chase, reducing the logistics handled by volunteer trip leaders.',
  ],
  [
    'Build a useful team base',
    'A team tent and Birkie start parking created space for waxing, warming up, testing skis, cheering, and moving people and gear.',
  ],
];
const futureRows = [
  [
    'Shared wax resources',
    "Move the team's shared wax collection away from products containing PFAS, often called forever chemicals.",
  ],
  [
    'Coaching and training capacity',
    'Add coaches and secure larger training spaces as the team grows.',
  ],
  [
    'Shared team equipment',
    'Invest in equipment that lowers the upfront cost of participating and helps new members get up to speed.',
  ],
];

function anchorBlockFor(href) {
  const marker = `href="${href}"`;
  const markerIndex = sponsorsHtml.indexOf(marker);
  assert.notEqual(markerIndex, -1, `missing sponsor link: ${href}`);

  const start = sponsorsHtml.lastIndexOf('<a', markerIndex);
  assert.notEqual(start, -1, `missing anchor start for: ${href}`);

  const end = sponsorsHtml.indexOf('</a>', markerIndex);
  assert.notEqual(end, -1, `missing anchor end for: ${href}`);

  return sponsorsHtml.slice(start, end + '</a>'.length);
}

function textPosition(marker) {
  const position = sponsorText.indexOf(marker);
  assert.notEqual(position, -1, `missing ordered page copy: ${marker}`);
  return position;
}

function openingTagBefore(html, marker, tagName) {
  const markerIndex = html.indexOf(marker);
  assert.notEqual(markerIndex, -1, `missing markup marker: ${marker}`);

  const start = html.lastIndexOf(`<${tagName}`, markerIndex);
  assert.notEqual(start, -1, `missing <${tagName}> before: ${marker}`);

  const end = html.indexOf('>', start);
  assert.notEqual(end, -1, `missing end of <${tagName}> before: ${marker}`);

  return html.slice(start, end + 1);
}

test('renders the approved recognition and impact copy', () => {
  for (const approvedCopy of [
    'Our sponsors',
    'Trailblazer Partners',
    'Support from our sponsors strengthens the shared resources behind training, team waxing, travel, and race support while helping TCSC keep participation costs in reach.',
    'Sponsor support helped TCSC...',
    'Recent investments strengthened everyday team activities as well as travel, with shared resources available to racers and non-racers.',
    ...completedRows.flat(),
    'Visible support at team events',
    'TCSC purchased six team jackets featuring sponsor logos for use at races and podium photos.',
    'A sponsor-logo team jacket at the Great Bear Chase.',
    'What continued support makes possible',
    'As the team grows, sponsor support gives TCSC flexibility to invest where it can have the most impact.',
    ...futureRows.flat(),
    'Interested in supporting TCSC?',
    'Contact club leadership to discuss sponsorship opportunities and current team needs.',
    'Email club leadership',
    "Sponsor recognition acknowledges support and does not constitute endorsement of a sponsor's products or services.",
  ]) {
    assert.ok(sponsorText.includes(approvedCopy), `missing exact page copy: ${approvedCopy}`);
  }
});

test('keeps completed impact, recognition, future priorities, and contact in order', () => {
  const impactHeading = textPosition('Sponsor support helped TCSC...');
  const recognitionHeading = textPosition('Visible support at team events');
  const jacketSentence = textPosition(
    'TCSC purchased six team jackets featuring sponsor logos for use at races and podium photos.',
  );
  const futureHeading = textPosition('What continued support makes possible');
  const disclosure = textPosition(
    "Sponsor recognition acknowledges support and does not constitute endorsement of a sponsor's products or services.",
  );
  const contactHeading = textPosition('Interested in supporting TCSC?');

  let previousPosition = impactHeading;
  for (const [title, detail] of completedRows) {
    const titlePosition = textPosition(title);
    const detailPosition = textPosition(detail);
    assert.ok(titlePosition > previousPosition, `${title} is outside the completed-impact rows`);
    assert.ok(detailPosition > titlePosition, `${title} detail is not attached to its row`);
    assert.ok(detailPosition < recognitionHeading, `${title} is not before recognition`);
    previousPosition = detailPosition;
  }

  assert.ok(recognitionHeading > previousPosition, 'recognition must follow completed impact');
  assert.ok(jacketSentence > recognitionHeading, 'jacket copy must remain in recognition');
  assert.ok(jacketSentence < futureHeading, 'jacket copy must precede future priorities');

  previousPosition = futureHeading;
  for (const [title, detail] of futureRows) {
    const titlePosition = textPosition(title);
    const detailPosition = textPosition(detail);
    assert.ok(titlePosition > previousPosition, `${title} is outside the future-priority rows`);
    assert.ok(detailPosition > titlePosition, `${title} detail is not attached to its row`);
    assert.ok(detailPosition < contactHeading, `${title} is not before the contact section`);
    previousPosition = detailPosition;
  }

  assert.ok(disclosure > previousPosition, 'disclosure must follow future priorities');
  assert.ok(disclosure < contactHeading, 'disclosure must precede the contact section');
});

test('renders the impact photo before its copy in the mobile DOM flow', () => {
  const photoAlt =
    'alt="A large group of TCSC members posing with roller skis and poles after a summer training session"';
  const impactHeading = 'Sponsor support helped TCSC...';
  const photoPosition = sponsorsHtml.indexOf(photoAlt);
  const headingPosition = sponsorsHtml.indexOf(impactHeading);

  assert.notEqual(photoPosition, -1, 'missing impact photo');
  assert.notEqual(headingPosition, -1, 'missing impact heading');
  assert.ok(photoPosition < headingPosition, 'impact photo must precede impact copy in DOM order');
  assert.match(openingTagBefore(sponsorsHtml, photoAlt, 'figure'), /\bmd:order-2\b/);
  assert.match(openingTagBefore(sponsorsHtml, impactHeading, 'div'), /\bmd:order-1\b/);
});

test('keeps the sponsor disclosure at the mobile body-text minimum', () => {
  const disclosureTag = openingTagBefore(
    sponsorsHtml,
    'Sponsor recognition acknowledges support',
    'p',
  );

  assert.match(disclosureTag, /\btext-base\b/);
  assert.doesNotMatch(disclosureTag, /\btext-xs\b/);
});

test('keeps current sponsor links accessible and qualified', () => {
  for (const [href, expectedAlt] of [
    ['https://tcomn.com/', 'Twin Cities Orthopedics website'],
    ['https://www.kwiktrip.com/', 'Kwik Trip website'],
  ]) {
    const anchor = anchorBlockFor(href);
    assert.match(anchor, /\brel="sponsored"/);
    assert.doesNotMatch(anchor, /\btarget=/);
    assert.deepEqual(anchor.match(/\balt="[^"]*"/gi) ?? [], [`alt="${expectedAlt}"`]);
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

test('keeps commercial terms and sponsor-specific purchase attribution off the public page', () => {
  assert.doesNotMatch(sponsorCommercialSurface, /highest level/i);
  assert.doesNotMatch(
    sponsorCommercialSurface,
    /\$\s*\d[\d,]*(?:\.\d{1,2})?(?:\s*[km])?\b/i,
  );
  assert.doesNotMatch(
    sponsorCommercialSurface,
    /\b(?:package|packages|rate|rates|benefit|benefits)\b/i,
  );
  assert.doesNotMatch(
    sponsorCommercialSurface,
    /\b(?:tax[- ]deductible|tax deduction|deductible contribution|charitable deduction)\b/i,
  );

  const sponsorName = String.raw`(?:TCO|Twin Cities Orthopedics|Kwik Trip)`;
  const purchaseVerb = String.raw`(?:funded|paid(?:\s+for)?|bought|purchased|provided|donated|supplied)`;
  assert.doesNotMatch(
    sponsorCommercialSurface,
    new RegExp(`\\b${sponsorName}\\b[^.!?]{0,100}\\b${purchaseVerb}\\b`, 'i'),
  );
  assert.doesNotMatch(
    sponsorCommercialSurface,
    new RegExp(`\\b${purchaseVerb}\\b[^.!?]{0,100}\\b(?:by|from)\\s+${sponsorName}\\b`, 'i'),
  );
});

test('keeps the home sponsor strip compact and unheaded', () => {
  assert.equal(homeText.includes('Trailblazer Partners'), false);
  assert.ok(homeHtml.includes('alt="Twin Cities Orthopedics website"'));
  assert.ok(homeHtml.includes('alt="Kwik Trip website"'));
});
