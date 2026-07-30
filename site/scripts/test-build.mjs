// Deterministic build for the test suite.
//
// The site's registration state is derived from a live API at build time, so
// an unqualified `astro build` produces different HTML depending on whether
// tcsc.ski is reachable and what today's date is. Build-output assertions then
// skip silently instead of failing loudly. This serves a fixture whose windows
// are computed RELATIVE TO NOW, so the built page is always in the
// `coming_soon` state no matter when the suite runs.
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';

const DAY = 24 * 60 * 60 * 1000;
const iso = (offsetDays) =>
  new Date(Date.now() + offsetDays * DAY).toISOString().replace(/\.\d{3}Z$/, 'Z');

// Both windows open in the future, so the derived state is always coming_soon.
const season = {
  name: 'Fixture Fall/Winter',
  season_type: 'fall/winter',
  year: new Date().getFullYear(),
  price_cents: 20500,
  returning_start: iso(30),
  returning_end: iso(40),
  new_start: iso(45),
  new_end: iso(60),
};
const body = JSON.stringify({
  generated_at: iso(0),
  primary: season,
  by_type: { 'fall/winter': season },
});

const server = createServer((request, response) => {
  response.writeHead(200, { 'Content-Type': 'application/json' });
  response.end(body);
});

await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
const { port } = server.address();

const build = spawn('npx', ['astro', 'build', '--force'], {
  stdio: 'inherit',
  env: { ...process.env, PUBLIC_SEASON_API_URL: `http://127.0.0.1:${port}/api/season` },
});

build.on('exit', (code) => {
  server.close();
  process.exit(code ?? 1);
});

build.on('error', (error) => {
  server.close();
  console.error(error);
  process.exit(1);
});
