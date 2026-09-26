// usage: node capture-preview.mjs <outdir> [path...]
// Full-page desktop (1440) captures of the Render PR preview, so a change is checked
// against what Render serves rather than a local build. Uses the same sibling browser
// as screenshot.mjs. Paths default to the five pages Rob's preview walk covered.
import { mkdirSync } from "node:fs";
import { getBrowser } from "./browser.mjs";

const PREVIEW = process.env.PREVIEW_URL ?? "https://tcsc-team-site-pr-249.onrender.com";
const [outdir = "preview-screens", ...paths] = process.argv.slice(2);
const pages = paths.length ? paths : ["/", "/about", "/community", "/racing", "/coaches"];

mkdirSync(outdir, { recursive: true });
const browser = await getBrowser();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
const page = await ctx.newPage();
for (const p of pages) {
  await page.goto(PREVIEW + p, { waitUntil: "networkidle", timeout: 60000 });
  // lazy images: walk the page so every <img> requests, then wait for them
  await page.evaluate(async () => {
    const step = window.innerHeight;
    for (let y = 0; y < document.body.scrollHeight; y += step) { window.scrollTo(0, y); await new Promise((r) => setTimeout(r, 60)); }
    window.scrollTo(0, 0);
    await Promise.all([...document.images].filter((i) => !i.complete).map((i) => new Promise((r) => { i.onload = i.onerror = r; })));
  });
  await page.waitForTimeout(300);
  const name = p === "/" ? "home" : p.slice(1).replace(/\//g, "-");
  await page.screenshot({ path: `${outdir}/${name}-desktop.png`, fullPage: true });
  console.log(name, await page.title());
}
await browser.close();
