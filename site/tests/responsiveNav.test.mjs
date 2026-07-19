import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const navSource = readFileSync(
  new URL('../src/components/Nav.astro', import.meta.url),
  'utf8',
);

test('keeps hamburger navigation visible through tablet widths', () => {
  assert.match(
    navSource,
    /<nav aria-label="Primary" class="hidden lg:flex\b/,
    'primary navigation should start at the lg breakpoint',
  );
  assert.match(
    navSource,
    /<div class="hidden lg:flex items-center gap-5">/,
    'registration CTA should start at the lg breakpoint',
  );
  assert.match(
    navSource,
    /<button\s+class="lg:hidden\b/,
    'menu button should remain visible below the lg breakpoint',
  );
  assert.doesNotMatch(navSource, /\bhidden md:flex\b|\bmd:hidden\b/);
});
