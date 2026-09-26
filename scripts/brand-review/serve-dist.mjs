// usage: node serve-dist.mjs <build-name> [--port 4400] [--preview]
// Serves builds/<name>/ like Render serves a static site built with format 'file' and
// trailingSlash 'never': /about -> about.html, /wax-room/x -> wax-room/x.html, unknown -> 404.html (404).
// --preview: also satisfy ~/preview/proxy.cjs's liveness probe so preview.eaer.app can front it.
// The proxy pins to a project dir and reads <dir>/.superpowers/brainstorm/.last-port and .last-token,
// then probes GET /?key=<token> expecting 200 + Set-Cookie brainstorm-key-<port>=... . We play along.
import { createServer } from "node:http";
import { existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { randomBytes } from "node:crypto";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

const args = process.argv.slice(2);
const name = args[0];
const portArg = args.indexOf("--port");
const port = (portArg >= 0 && Number(args[portArg + 1])) || Number(process.env.PORT) || 4400;
const preview = args.includes("--preview");
const here = fileURLToPath(new URL(".", import.meta.url));
const root = join(here, "builds", name ?? "");
if (!name || !existsSync(join(root, "index.html"))) {
  console.error(`no build at ${root}; run: node build-state.mjs ${name ?? "<name>"}`);
  process.exit(2);
}

const MIME = {
  ".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "text/javascript", ".mjs": "text/javascript",
  ".json": "application/json", ".xml": "application/xml", ".txt": "text/plain", ".svg": "image/svg+xml",
  ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".avif": "image/avif",
  ".ico": "image/x-icon", ".woff2": "font/woff2", ".woff": "font/woff", ".mp3": "audio/mpeg",
};

const token = randomBytes(32).toString("hex");

function resolve(pathname) {
  let p = normalize(decodeURIComponent(pathname)).replace(/^(\.\.[/\\])+/, "");
  if (p.endsWith("/")) p = p.slice(0, -1);
  const candidates = p === "" || p === "/" ? ["index.html"] : [p, `${p}.html`, `${p}/index.html`];
  for (const c of candidates) {
    const f = join(root, c);
    if (existsSync(f) && statSync(f).isFile()) return { file: f, status: 200 };
  }
  return { file: join(root, "404.html"), status: 404 };
}

createServer((req, res) => {
  const { file, status } = resolve(new URL(req.url, "http://x").pathname);
  const headers = { "Content-Type": MIME[extname(file)] ?? "application/octet-stream", "Cache-Control": "no-store" };
  if (preview) headers["Set-Cookie"] = `brainstorm-key-${port}=${token}; Path=/; SameSite=Lax`;
  res.writeHead(status, headers);
  res.end(readFileSync(file));
}).listen(port, "127.0.0.1", () => {
  console.log(`serving builds/${name} on http://127.0.0.1:${port}`);
  if (preview) {
    const repo = fileURLToPath(new URL("../../", import.meta.url));
    const bs = join(repo, ".superpowers", "brainstorm");
    mkdirSync(bs, { recursive: true });
    writeFileSync(join(bs, ".last-port"), String(port));
    writeFileSync(join(bs, ".last-token"), token);
    console.log(`preview mode: pin the proxy with  echo ${repo.replace(/\/$/, "")} > ~/preview/target  then open https://preview.eaer.app/`);
  }
});
