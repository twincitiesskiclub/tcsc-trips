import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

// Astro emits dist/<slug>/index.html with build.format 'directory' and
// dist/<slug>.html with 'file'. Production sets TCSC_EDGE_CONFIG=true, which
// selects 'file', and the test build now matches it -- so resolve either.
function page(slug) {
  const base = new URL('../dist/', import.meta.url);
  for (const candidate of [`${slug}/index.html`, `${slug}.html`]) {
    try {
      return readFileSync(new URL(candidate, base), 'utf8');
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
    }
  }
  throw new Error(`no built page for ${slug} (tried both build formats)`);
}


const sponsorsHtml = page('sponsors');
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
    'Team wax sessions',
    'Two wax drills and a shared wax supply, open to every member.',
  ],
  [
    'Vans to races',
    'Rental vans carried food, gear, and supplies to the Prebirkie and the Great Bear Chase, so volunteer trip leaders had less to haul.',
  ],
  [
    'A base at the Birkie',
    'A team tent and start-area parking: a place to wax, warm up, test skis, and cheer.',
  ],
];
const futureRows = [
  [
    'PFAS-free wax',
    "Replace the club's shared wax with PFAS-free products.",
  ],
  [
    'More coaches, more gym space',
    'Add coaches and book larger training spaces as the club grows.',
  ],
  [
    'Shared gear',
    'Equipment that lowers the cost of a first season.',
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
    'Trailblazer partners',
    'Our sponsors pay for the wax, vans, and race-day gear that every member shares, racer or not, and keep dues within reach.',
    'What sponsor money paid for',
    'Everything here is shared by racers and non-racers alike.',
    ...completedRows.flat(),
    'Sponsor logos at the races',
    'Six club jackets carry sponsor logos at races and in podium photos.',
    'A sponsor-logo team jacket at the Great Bear Chase.',
    'What comes next',
    'Where the next sponsor dollars go.',
    ...futureRows.flat(),
    'Sponsor TCSC',
    'Email club leadership about sponsorship and what the club needs this season.',
    'Email club leadership',
    "Sponsor recognition is thanks, not an endorsement of a sponsor's products or services.",
  ]) {
    assert.ok(sponsorText.includes(approvedCopy), `missing exact page copy: ${approvedCopy}`);
  }
});

test('keeps completed impact, recognition, future priorities, and contact in order', () => {
  const impactHeading = textPosition('What sponsor money paid for');
  const recognitionHeading = textPosition('Sponsor logos at the races');
  const jacketSentence = textPosition(
    'Six club jackets carry sponsor logos at races and in podium photos.',
  );
  const futureHeading = textPosition('What comes next');
  const disclosure = textPosition(
    "Sponsor recognition is thanks, not an endorsement of a sponsor's products or services.",
  );
  const contactHeading = textPosition('Sponsor TCSC');

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
  const impactHeading = 'What sponsor money paid for';
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
    'Sponsor recognition is thanks',
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
  assert.equal(homeText.includes('Trailblazer partners'), false);
  assert.ok(homeHtml.includes('alt="Twin Cities Orthopedics website"'));
  assert.ok(homeHtml.includes('alt="Kwik Trip website"'));
});
