// usage: node screenshot.mjs <phase> [stateId...]
//   -> docs/superpowers/specs/2026-08-31-site-brand-review/screens/<phase>/<surface>-<state>-<viewport>.png
// Groups states by build, serves each build on PORT (default 4400) for the duration, answers the
// conditions fetch per state, asserts data-season-source="api", and writes one png per viewport.
import { spawn } from "node:child_process";
import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { STATES } from "./states.mjs";
import { getBrowser } from "./browser.mjs";
import { conditionsPayload, ensureFixtureApi } from "./fixture-api.mjs";

const VIEWPORTS = {
  mobile: { width: 390, height: 844 },
  tablet: { width: 768, height: 1024 },
  desktop: { width: 1440, height: 900 },
};
const [phase = "before", ...only] = process.argv.slice(2);
const port = Number(process.env.PORT) || 4400;
const base = `http://127.0.0.1:${port}`;
const here = fileURLToPath(new URL(".", import.meta.url));
const outDir = fileURLToPath(new URL(`../../docs/superpowers/specs/2026-08-31-site-brand-review/screens/${phase}/`, import.meta.url));
mkdirSync(outDir, { recursive: true });

const wanted = STATES.filter((s) => !only.length || only.includes(s.id));
if (!wanted.length) { console.error("no matching state ids"); process.exit(2); }
const byBuild = Map.groupBy(wanted, (s) => s.build);
const api = await ensureFixtureApi();
const browser = await getBrowser();
const failures = [];

function serve(build) {
  const child = spawn("node", [`${here}serve-dist.mjs`, build, "--port", String(port)], { stdio: ["ignore", "pipe", "inherit"] });
  return new Promise((resolve, reject) => {
    child.stdout.on("data", (d) => { if (String(d).includes("serving")) resolve(child); });
    child.on("exit", (code) => reject(new Error(`serve-dist exited ${code} for ${build}; run build-state.mjs ${build}`)));
  });
}

for (const [build, states] of byBuild) {
  const server = await serve(build);
  try {
    for (const s of states) {
      for (const vp of s.viewports ?? ["mobile", "desktop"]) {
        const ctx = await browser.newContext({ viewport: VIEWPORTS[vp], deviceScaleFactor: 2, reducedMotion: "no-preference" });
        if (s.clock) { await ctx.clock.install({ time: new Date(s.clock) }); }
        await ctx.route("**/conditions/**", (route) =>
          s.conditions === "unavailable"
            ? route.abort()
            : route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(conditionsPayload(s.conditions ?? "live")) }),
        );
        const page = await ctx.newPage();
        const file = `${outDir}${s.surface}-${s.state}-${vp}.png`;
        try {
          await page.goto(base + s.url, { waitUntil: "networkidle", timeout: 30000 });
          const source = await page.getAttribute("body", "data-season-source");
          if (source !== "api") throw new Error(`data-season-source=${source}`);
          // Astro images below the fold are loading="lazy"; a full-page capture would show blank
          // mosaic tiles. Sweep the page so every image requests, wait for them, and return to top.
          await page.evaluate(async () => {
            const step = window.innerHeight;
            for (let y = 0; y < document.body.scrollHeight; y += step) { window.scrollTo(0, y); await new Promise((r) => setTimeout(r, 80)); }
            window.scrollTo(0, 0);
            await Promise.all([...document.images].map((img) => img.complete || new Promise((r) => { img.onload = img.onerror = r; })));
          });
          await page.waitForTimeout(300);
          for (const a of s.actions ?? []) {
            if (a.click) await page.click(a.click);
            else if (a.hover) await page.hover(a.hover);
            else if (a.press) await page.keyboard.press(a.press);
            else if (a.waitFor) await page.waitForSelector(a.waitFor, { timeout: 15000 });
            else if (a.scroll !== undefined) await page.evaluate((y) => window.scrollTo(0, y), a.scroll);
            else if (a.wait) await page.waitForTimeout(a.wait);
          }
          await page.waitForTimeout(400); // let the 150ms hover and 200ms lightbox transitions settle
          await page.screenshot({ path: file, fullPage: !s.viewportOnly && !s.actions?.some((a) => a.scroll !== undefined) });
          console.log("ok", file.split("/").pop());
        } catch (e) {
          failures.push(`${s.id}/${vp}: ${e.message.split("\n")[0]}`);
          console.log("FAIL", s.id, vp, e.message.split("\n")[0]);
        } finally {
          await ctx.close();
        }
      }
    }
  } finally {
    server.kill();
  }
}

await browser.close();
if (!api.external) api.close();
if (failures.length) { console.error(`\n${failures.length} failures:\n${failures.join("\n")}`); process.exit(1); }
console.log(`\nall captures written to ${outDir}`);
