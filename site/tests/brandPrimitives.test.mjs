import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import test from 'node:test';
import { JSDOM } from 'jsdom';
import { parse } from 'yaml';

const siteRoot = new URL('../', import.meta.url);
const distRoot = new URL('../dist/', import.meta.url);
const srcRoot = new URL('../src/', import.meta.url);

function filesUnder(root, predicate) {
  return readdirSync(root, { recursive: true, withFileTypes: true })
    .filter((entry) => entry.isFile() && predicate(entry.name))
    .map((entry) => new URL(entry.parentPath + '/' + entry.name, siteRoot));
}

const htmlFiles = filesUnder(distRoot, (name) => name.endsWith('.html'));

test('keeps arbitrary pixel type and tracking out of built HTML', () => {
  for (const file of htmlFiles) {
    const html = readFileSync(file, 'utf8');
    assert.doesNotMatch(html, /\btext-\[\d+(?:\.\d+)?px\]/, file.pathname);
    assert.doesNotMatch(html, /\btracking-\[/, file.pathname);
  }
});

test('renders at most one seam inside each section band', () => {
  for (const file of htmlFiles) {
    const { document } = new JSDOM(readFileSync(file, 'utf8')).window;
    for (const section of document.querySelectorAll('section')) {
      const ownSeams = [...section.querySelectorAll('.seam')]
        .filter((seam) => seam.closest('section') === section);
      assert.ok(ownSeams.length <= 1, `${file.pathname} contains a band with ${ownSeams.length} seams`);
    }
  }
});

test('keeps the CTA strip coral rule singular and attached to the strip', () => {
  for (const file of htmlFiles) {
    const { document } = new JSDOM(readFileSync(file, 'utf8')).window;
    const strips = [...document.querySelectorAll('[data-cta-strip]')];
    assert.ok(strips.length <= 1, `${file.pathname} contains more than one CTA strip`);
    for (const strip of strips) {
      assert.ok(strip.classList.contains('border-t-[3px]'), `${file.pathname} CTA strip lost its 3px rule`);
      assert.ok(strip.classList.contains('border-coral'), `${file.pathname} CTA strip lost its coral rule`);
    }
  }
});

test('renders footer links in primary navigation order before footer extras', () => {
  const nav = parse(readFileSync(new URL('../src/content/nav.yaml', import.meta.url), 'utf8'));
  const expected = [
    ...nav.top_links,
    { label: 'Trips', href: '/trips' },
    { label: 'Extra training fun', href: '/extra-training-fun' },
    { label: 'Dry Tri', href: '/dry-tri' },
  ];

  let footerCount = 0;
  for (const file of htmlFiles) {
    const { document } = new JSDOM(readFileSync(file, 'utf8')).window;
    const footer = document.querySelector('footer nav[aria-label="Footer"]');
    if (!footer) continue;
    footerCount += 1;
    const links = [...footer.querySelectorAll('a')].map((link) => ({
      label: link.textContent.trim(),
      href: link.getAttribute('href'),
    }));
    assert.deepEqual(links, expected, `${file.pathname} footer order drifted from nav.yaml`);
  }
  assert.ok(footerCount > 0, 'build contains no footer to guard');
});

test('keeps raw OKLCH values in the two token-owning stylesheets', () => {
  const sourceFiles = filesUnder(
    srcRoot,
    (name) => /\.(?:astro|css|ts|tsx|mjs)$/.test(name),
  );
  const allowed = new URL('../src/styles/global.css', import.meta.url).pathname;

  for (const file of sourceFiles) {
    if (file.pathname === allowed) continue;
    assert.doesNotMatch(readFileSync(file, 'utf8'), /oklch\(/, file.pathname);
  }
});
