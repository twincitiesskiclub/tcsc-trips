// Shared browser access for the site brand-review harness.
// This container has no chromium system libs and no root, so the browser runs in a
// sibling container (intimate-brand-browser, mcr.microsoft.com/playwright:v1.61.1-noble,
// `playwright run-server --port 3333 --host 127.0.0.1`) that shares this container's
// network namespace (--network container:<this id>). Both sides therefore use 127.0.0.1:
// the browser reaches our dist server and fixture api, and we reach the browser.
import { chromium } from "playwright-core";

export const BASE_URL = process.env.BASE_URL ?? "http://127.0.0.1:4400";
export const BROWSER_WS = process.env.BROWSER_WS ?? "ws://127.0.0.1:3333/";

export async function getBrowser() {
  try {
    return await chromium.connect(BROWSER_WS, { timeout: 15000 });
  } catch (e) {
    throw new Error(
      `cannot connect to ${BROWSER_WS}: ${e.message.split("\n")[0]}\n` +
        `start it with: docker start intimate-brand-browser`,
    );
  }
}
