import assert from 'node:assert/strict';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const title = 'Stone Grind or Hotbox? When Skis Need a Second Wind';
const route = '/wax-room/stone-grind-or-hotbox';
const sourceUrl = new URL(
  '../src/content/wax_entries/stone-grind-or-hotbox.mdoc',
  import.meta.url,
);
const detailUrl = new URL('../dist/wax-room/stone-grind-or-hotbox/index.html', import.meta.url);
const distDirectory = fileURLToPath(new URL('../dist/', import.meta.url));

test('keeps the withdrawn Wax Room article unpublished', () => {
  assert.equal(existsSync(sourceUrl), false, 'withdrawn article source must be absent');
  assert.equal(existsSync(detailUrl), false, 'withdrawn article route must not be generated');

  const publicOutput = readdirSync(distDirectory, { recursive: true })
    .filter((file) => /\.(?:html|xml)$/.test(file))
    .map((file) => readFileSync(join(distDirectory, file), 'utf8'))
    .join('\n');
  assert.equal(publicOutput.includes(title), false, 'public output must not name the article');
  assert.equal(publicOutput.includes(route), false, 'public output must not expose the article route');

  const homeHtml = readFileSync(new URL('../dist/index.html', import.meta.url), 'utf8');
  assert.ok(homeHtml.includes('From the Wax Room'), 'home page must retain the Wax Room section');
  assert.ok(homeHtml.includes('href="/wax-room"'), 'home page must retain the Wax Room link');

  const indexHtml = readFileSync(new URL('../dist/wax-room/index.html', import.meta.url), 'utf8');
  assert.ok(indexHtml.includes('No entries yet.'), 'Wax Room index must retain its empty state');
});
