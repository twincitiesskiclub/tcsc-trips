// usage: node smoke.mjs [url]  -> smoke.png. Proves the browser container is reachable.
import { getBrowser } from "./browser.mjs";

const url = process.argv[2] ?? "https://twincitiesskiclub.org/";
const browser = await getBrowser();
const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
await page.goto(url, { waitUntil: "networkidle", timeout: 30000 });
console.log("season source:", await page.getAttribute("body", "data-season-source"));
await page.screenshot({ path: "smoke.png", fullPage: true });
await browser.close();
console.log("ok");
