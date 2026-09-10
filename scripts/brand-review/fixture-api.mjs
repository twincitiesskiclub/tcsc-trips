// Fixture API for the site brand review. Serves the two endpoints the marketing site
// reads (season at build time, conditions in the browser) with deterministic payloads.
//   node fixture-api.mjs            keeps a server up on 4499 (ctrl-c to stop)
//   import { ... } from "./fixture-api.mjs"   for tests and build-state.mjs
// Windows are relative to NOW so registrationFlip.ts (which re-derives state in the
// browser) agrees with what the build baked. Shape mirrors app/seasons + site/scripts/test-build.mjs.
import { createServer } from "node:http";
import { connect } from "node:net";

export const FIXTURE_PORT = 4499;
const DAY = 24 * 60 * 60 * 1000;
const iso = (offsetDays) =>
  new Date(Date.now() + offsetDays * DAY).toISOString().replace(/\.\d{3}Z$/, "Z");

// returning window, then new-member window, as day offsets from now.
const WINDOWS = {
  open: [-1, 3, 5, 20],
  soon: [30, 40, 45, 60],
  closed: [-60, -50, -45, -30],
};

export function seasonPayload(state) {
  const w = WINDOWS[state];
  if (!w) throw new Error(`unknown season state ${state}`);
  const season = (season_type, name) => ({
    name,
    season_type,
    year: new Date().getFullYear(),
    price_cents: 20500,
    returning_start: iso(w[0]),
    returning_end: iso(w[1]),
    new_start: iso(w[2]),
    new_end: iso(w[3]),
  });
  const fw = season("fall/winter", "Fixture Fall/Winter");
  return {
    generated_at: iso(0),
    primary: fw,
    by_type: { "fall/winter": fw, "spring/summer": season("spring/summer", "Fixture Spring/Summer") },
  };
}

// ids and names match app/conditions/locations.py and the cells in LiveConditions.astro.
const VENUES = [
  ["wirth", "Theo"],
  ["elm", "Elm"],
  ["hyland", "Hyland"],
  ["telemark", "Telemark"],
];

export function conditionsPayload(mode) {
  const updated_at = new Date().toISOString();
  if (mode === "dryland") return { updated_at, error: "Conditions unavailable", locations: [] };
  if (mode !== "live") throw new Error(`unknown conditions mode ${mode}`);
  const temps = [12, 18, 27, 33];
  const bands = [
    ["green", "Green wax · cold snow"],
    ["blue", "Blue wax · firm snow"],
    ["purple", "Purple · transition snow"],
    ["red", "Red wax · klister conditions"],
  ];
  return {
    updated_at,
    locations: VENUES.map(([id, name], i) => ({
      id,
      name,
      temp_f: temps[i],
      wind_chill_f: temps[i] - (i === 1 ? 6 : 1),
      snow_conditions: "groomed",
      wax_band: bands[i][0],
      wax_label: bands[i][1],
      source_url: `https://www.skinnyski.com/trails/report.asp?id=${100 + i}`,
      report_date: new Date().toISOString().slice(0, 10),
      groomed_for: i % 2 ? "both" : "skate",
    })),
    birkie: { status: "rising", word: "101.2°", detail: "Fever climbing. Wave assignments posted." },
  };
}

function handler(req, res) {
  const [, kind, arg] = new URL(req.url, "http://x").pathname.split("/");
  try {
    const body = kind === "season" ? seasonPayload(arg) : kind === "conditions" ? conditionsPayload(arg) : null;
    if (!body) throw new Error("not found");
    res.writeHead(200, {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
      "Access-Control-Allow-Origin": "*",
    });
    res.end(JSON.stringify(body));
  } catch (e) {
    res.writeHead(404, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: String(e.message) }));
  }
}

export function startFixtureApi(port = FIXTURE_PORT) {
  const server = createServer(handler);
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, "127.0.0.1", () => resolve({ port, close: () => server.close() }));
  });
}

function portOpen(port) {
  return new Promise((resolve) => {
    const s = connect({ port, host: "127.0.0.1" });
    s.once("connect", () => { s.end(); resolve(true); });
    s.once("error", () => resolve(false));
  });
}

/** Start the fixture api unless something already answers on the port. */
export async function ensureFixtureApi(port = FIXTURE_PORT) {
  if (await portOpen(port)) return { port, close: () => {}, external: true };
  return startFixtureApi(port);
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].split("/").pop())) {
  const { port } = await startFixtureApi();
  console.log(`fixture api on http://127.0.0.1:${port}  (/season/open|soon|closed, /conditions/live|dryland)`);
}
