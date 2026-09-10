// usage: node build-state.mjs <open|soon|closed|populated>
// Builds the marketing site once for one registration state into builds/<name>/.
// `populated` = open + the fixture trip and wax entry copied into site/src/content for the
// duration of the build only. The fixture api must be reachable on 4499 during the build
// (started here if needed) and again when the pages are opened, because the conditions
// url is baked into the html for the browser to fetch.
import { spawn } from "node:child_process";
import { cpSync, existsSync, mkdirSync, readFileSync, rmSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { ensureFixtureApi, FIXTURE_PORT } from "./fixture-api.mjs";

const name = process.argv[2];
const STATES = { open: "open", soon: "soon", closed: "closed", populated: "open" };
if (!STATES[name]) {
  console.error("usage: node build-state.mjs <open|soon|closed|populated>");
  process.exit(2);
}

const here = fileURLToPath(new URL(".", import.meta.url));
const site = fileURLToPath(new URL("../../site/", import.meta.url));
const outDir = `${here}builds/${name}`;
const fixtures = [
  ["fixtures/content/trips/sisu-ski-fest.mdoc", "src/content/trips/sisu-ski-fest.mdoc"],
  ["fixtures/content/wax_entries/first-snow-wax.mdoc", "src/content/wax_entries/first-snow-wax.mdoc"],
];

const api = await ensureFixtureApi();
const placed = [];
if (name === "populated") {
  for (const [from, to] of fixtures) {
    cpSync(here + from, site + to);
    placed.push(site + to);
  }
}

const cleanup = () => {
  for (const f of placed) rmSync(f, { force: true });
  if (!api.external) api.close();
};
process.on("SIGINT", () => { cleanup(); process.exit(130); });

rmSync(outDir, { recursive: true, force: true });
mkdirSync(outDir, { recursive: true });

const build = spawn("npx", ["astro", "build", "--force", "--outDir", outDir], {
  cwd: site,
  stdio: "inherit",
  env: {
    ...process.env,
    TCSC_EDGE_CONFIG: "true", // production config: flat files, no trailing slash
    PUBLIC_SEASON_API_URL: `http://127.0.0.1:${FIXTURE_PORT}/season/${STATES[name]}`,
    PUBLIC_CONDITIONS_API_URL: `http://127.0.0.1:${FIXTURE_PORT}/conditions/live`,
  },
});

build.on("exit", (code) => {
  cleanup();
  if (code !== 0) process.exit(code ?? 1);
  const html = readFileSync(`${outDir}/index.html`, "utf8");
  const m = html.match(/data-season-source="(\w+)"/);
  if (!m || m[1] !== "api") {
    console.error(`build ${name}: data-season-source is ${m?.[1] ?? "missing"}, expected api`);
    process.exit(1);
  }
  const expectPages = name === "populated" ? ["trips.html", "wax-room/first-snow-wax.html"] : ["trips.html"];
  for (const p of expectPages) if (!existsSync(`${outDir}/${p}`)) { console.error(`missing ${p}`); process.exit(1); }
  console.log(`build ${name}: ok -> ${outDir}`);
});
build.on("error", (e) => { cleanup(); console.error(e); process.exit(1); });
