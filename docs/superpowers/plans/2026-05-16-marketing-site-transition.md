# TCSC Marketing Site — Wix → Astro Transition — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a new Astro static marketing site at `/site` in this repo, port all content from the current Wix site (`twincitiesskiclub.org`), deploy to Render Static, and cut over the production domain. Keep the Flask app at `tcsc.ski` untouched except for one small additive endpoint (`GET /api/conditions`) the marketing site consumes.

**Architecture:** Astro 5 static site under `/site` with its own `package.json` (separate Node project from the root). Tailwind v3 + Tailwind UI for component scaffolding. Keystatic for typed content (local mode for the developer; a separate Slack agent edits via the same schema via GitHub later). Drenched-navy home page with a real photographic hero; paper-default inner pages. Signature device is a `<LiveConditions>` strip sourced from a new Flask endpoint that re-uses the existing Skipper NWS + SkinnySkI integrations. New editorial section `/wax-room` for dated entries by coaches and members.

**Tech Stack:** Astro 5, Tailwind CSS 3 + Tailwind UI / Plus, Keystatic, TypeScript (in Astro), pnpm or npm, Python 3.12 + Playwright (for the Wix scrape), pytest (for Flask endpoint + scrape tests), Render Static (deploy). Specs: `docs/superpowers/specs/2026-05-16-marketing-site-transition-design.md`. Context docs: `PRODUCT.md`, `DESIGN.md`.

**Branch / PR strategy:** Work on `feat/marketing-site` branched from `main`. Two PRs total: PR-1 ships everything up through Render staging deploy (no DNS cutover); PR-2 is the DNS cutover (separate so it can be reverted instantly). Frequent commits within the branch. Squash merges are fine.

**Estimated scale:** ~70 tasks across 13 phases. Plan to ship over 2–3 weeks. Phase A (foundation) blocks everything; phases B–E can largely parallelize once A lands.

---

## Phase A — Foundation

### Task 1: Create feature branch

**Files:** none (git only)

- [ ] **Step 1: Verify clean tree on main**

Run: `git status && git branch --show-current`
Expected: on `main`. Untracked files are fine.

- [ ] **Step 2: Create + switch to feature branch**

```bash
git checkout -b feat/marketing-site
```

Expected: `Switched to a new branch 'feat/marketing-site'`

---

### Task 2: Scaffold the `/site` Astro project

**Files:**
- Create: `site/package.json`
- Create: `site/astro.config.mjs`
- Create: `site/tsconfig.json`
- Create: `site/.gitignore`
- Create: `site/src/pages/index.astro` (placeholder)

- [ ] **Step 1: Make the directory + initialize**

```bash
mkdir -p site && cd site
```

- [ ] **Step 2: Write `package.json`**

```json
{
  "name": "tcsc-site",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "astro dev --port 4321",
    "build": "astro build",
    "preview": "astro preview --port 4321",
    "check": "astro check"
  },
  "dependencies": {
    "astro": "^5.0.0"
  },
  "devDependencies": {
    "@astrojs/check": "^0.9.0",
    "typescript": "^5.4.0"
  }
}
```

- [ ] **Step 3: Write `astro.config.mjs`**

```js
import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://twincitiesskiclub.org',
  output: 'static',
  image: {
    service: { entrypoint: 'astro/assets/services/sharp' },
  },
});
```

- [ ] **Step 4: Write `tsconfig.json`**

```json
{
  "extends": "astro/tsconfigs/strict",
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  }
}
```

- [ ] **Step 5: Write `site/.gitignore`**

```
node_modules/
dist/
.astro/
.env
.env.production
```

- [ ] **Step 6: Write placeholder homepage**

`site/src/pages/index.astro`:
```astro
---
---
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>TCSC — Twin Cities Ski Club</title>
  </head>
  <body>
    <h1>TCSC scaffold</h1>
  </body>
</html>
```

- [ ] **Step 7: Install + run + verify**

```bash
cd site && npm install && npm run dev &
sleep 3
curl -sf http://localhost:4321/ | grep -q 'TCSC scaffold' && echo OK
kill %1
```

Expected: `OK` printed.

- [ ] **Step 8: Commit**

```bash
git add site/
git commit -m "feat(site): scaffold Astro project under /site"
```

---

### Task 3: Add Tailwind CSS to the Astro project

**Files:**
- Modify: `site/package.json` (deps)
- Modify: `site/astro.config.mjs`
- Create: `site/tailwind.config.ts`
- Create: `site/src/styles/global.css`
- Modify: `site/src/pages/index.astro`

- [ ] **Step 1: Install Tailwind + Astro integration**

```bash
cd site && npm install --save-dev tailwindcss@^3.4 @tailwindcss/forms @tailwindcss/typography @astrojs/tailwind
```

- [ ] **Step 2: Add the integration to `astro.config.mjs`**

```js
import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';

export default defineConfig({
  site: 'https://twincitiesskiclub.org',
  output: 'static',
  integrations: [tailwind({ applyBaseStyles: false })],
  image: {
    service: { entrypoint: 'astro/assets/services/sharp' },
  },
});
```

- [ ] **Step 3: Write `tailwind.config.ts` (with the design tokens from `DESIGN.md`)**

```ts
import type { Config } from 'tailwindcss';
import forms from '@tailwindcss/forms';
import typography from '@tailwindcss/typography';

export default {
  content: ['./src/**/*.{astro,html,ts,tsx,md,mdx}'],
  theme: {
    extend: {
      colors: {
        navy: 'oklch(0.25 0.06 260)',
        'navy-deep': 'oklch(0.18 0.05 260)',
        mint: 'oklch(0.91 0.12 155)',
        'mint-deep': 'oklch(0.55 0.13 155)',
        coral: 'oklch(0.74 0.16 15)',
        paper: 'oklch(0.985 0.003 90)',
        'paper-card': 'oklch(0.97 0.004 90)',
        ink: 'oklch(0.18 0.04 260)',
        slate: 'oklch(0.50 0.02 260)',
      },
      fontFamily: {
        sans: ['PolySans', 'system-ui', 'sans-serif'],
        display: ['PolySans Wide', 'PolySans', 'system-ui', 'sans-serif'],
      },
      maxWidth: {
        prose: '62ch',
        'prose-narrow': '56ch',
      },
    },
  },
  plugins: [forms, typography],
} satisfies Config;
```

- [ ] **Step 4: Write `site/src/styles/global.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  color-scheme: light;
}

html {
  font-family: 'PolySans', system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  background: oklch(0.985 0.003 90);
  color: oklch(0.18 0.04 260);
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

- [ ] **Step 5: Update `site/src/pages/index.astro` to import global.css**

```astro
---
import '@/styles/global.css';
---
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>TCSC — Twin Cities Ski Club</title>
  </head>
  <body class="bg-paper text-ink">
    <h1 class="font-display text-6xl text-navy">TCSC scaffold</h1>
  </body>
</html>
```

- [ ] **Step 6: Run + verify**

```bash
cd site && npm run dev &
sleep 3
curl -sf http://localhost:4321/ | grep -q 'text-navy' && echo OK
kill %1
```

Expected: `OK`. Visit `http://localhost:4321/` in browser; heading should be navy on paper background. (Type will render in a system fallback until Task 4 installs fonts.)

- [ ] **Step 7: Commit**

```bash
git add site/
git commit -m "feat(site): add Tailwind CSS with brand color tokens"
```

---

### Task 4: Self-host the type system

**Files:**
- Create: `site/public/fonts/polysans/*` (font files; downloaded from Pangram Pangram free tier)
- Modify: `site/src/styles/global.css` (add @font-face declarations)
- Create: `site/src/components/FontPreload.astro`

PolySans (Pangram Pangram, free for personal + non-profit use) is the choice here. If TCSC licenses Söhne later, this task is the swap point.

- [ ] **Step 1: Download PolySans Median + Wide weights**

Manually: visit `https://www.pangrampangram.com/products/poly-sans` and download the free PolySans Trial pack. Extract `PolySans-Median.woff2`, `PolySans-MedianItalic.woff2`, `PolySans-Bulky.woff2`, `PolySans-Slim.woff2`, and `PolySans-WideBold.woff2` (if available; otherwise use Bulky for display) into `site/public/fonts/polysans/`.

If the free trial pack doesn't include the weights above, fall back to **Inter Variable** (Google Fonts, self-hosted; acknowledge it's reflex-adjacent but acceptable as a temporary measure) and document the swap-to-PolySans as a follow-up. The plan continues either way.

- [ ] **Step 2: Add @font-face declarations to `global.css`**

Append above the `html { ... }` block:

```css
@font-face {
  font-family: 'PolySans';
  src: url('/fonts/polysans/PolySans-Median.woff2') format('woff2');
  font-weight: 400;
  font-style: normal;
  font-display: swap;
}

@font-face {
  font-family: 'PolySans';
  src: url('/fonts/polysans/PolySans-Bulky.woff2') format('woff2');
  font-weight: 700;
  font-style: normal;
  font-display: swap;
}

@font-face {
  font-family: 'PolySans Wide';
  src: url('/fonts/polysans/PolySans-WideBold.woff2') format('woff2');
  font-weight: 800;
  font-style: normal;
  font-display: swap;
}
```

- [ ] **Step 3: Create `FontPreload.astro` for use in shared layouts**

```astro
---
---
<link rel="preload" href="/fonts/polysans/PolySans-Median.woff2" as="font" type="font/woff2" crossorigin />
<link rel="preload" href="/fonts/polysans/PolySans-WideBold.woff2" as="font" type="font/woff2" crossorigin />
```

- [ ] **Step 4: Run + verify**

```bash
cd site && npm run dev &
sleep 3
curl -sf http://localhost:4321/fonts/polysans/PolySans-Median.woff2 -o /dev/null -w '%{http_code}\n' | grep -q '200' && echo OK
kill %1
```

Expected: `OK`. Visiting `http://localhost:4321/` in the browser, the heading now renders in PolySans Wide Bold.

- [ ] **Step 5: Commit**

```bash
git add site/
git commit -m "feat(site): self-host PolySans family"
```

---

### Task 5: Base layout + page shell

**Files:**
- Create: `site/src/layouts/BaseLayout.astro`
- Modify: `site/src/pages/index.astro`

- [ ] **Step 1: Write `BaseLayout.astro`**

```astro
---
import '@/styles/global.css';
import FontPreload from '@/components/FontPreload.astro';

interface Props {
  title: string;
  description?: string;
  ogImage?: string;
  variant?: 'home' | 'inner';
}

const {
  title,
  description = 'Twin Cities Ski Club — a nonprofit cross-country ski community for young adults in Minneapolis / St. Paul.',
  ogImage = '/og-default.jpg',
  variant = 'inner',
} = Astro.props;

const isHome = variant === 'home';
---
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    <meta name="description" content={description} />
    <meta property="og:title" content={title} />
    <meta property="og:description" content={description} />
    <meta property="og:image" content={ogImage} />
    <meta property="og:type" content="website" />
    <meta property="og:site_name" content="Twin Cities Ski Club" />
    <meta name="twitter:card" content="summary_large_image" />
    <link rel="canonical" href={Astro.url.href} />
    <FontPreload />
  </head>
  <body class={isHome ? 'bg-navy text-mint' : 'bg-paper text-ink'}>
    <slot />
  </body>
</html>
```

- [ ] **Step 2: Update `index.astro` to use the layout**

```astro
---
import BaseLayout from '@/layouts/BaseLayout.astro';
---
<BaseLayout title="TCSC — Twin Cities Ski Club" variant="home">
  <h1 class="font-display text-6xl p-8">Twin Cities Ski Club</h1>
</BaseLayout>
```

- [ ] **Step 3: Verify dev server renders without error**

```bash
cd site && npm run check && npm run build
```

Expected: build succeeds, no TypeScript errors.

- [ ] **Step 4: Commit**

```bash
git add site/
git commit -m "feat(site): base layout with SEO meta + variant theme"
```

---

### Task 6: Install + configure Keystatic

**Files:**
- Modify: `site/package.json` (deps)
- Modify: `site/astro.config.mjs`
- Create: `site/keystatic.config.ts`
- Create: `site/src/pages/keystatic/[...params].ts`

- [ ] **Step 1: Install Keystatic**

```bash
cd site && npm install --save @keystatic/core @keystatic/astro
```

- [ ] **Step 2: Update `astro.config.mjs`**

```js
import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';
import react from '@astrojs/react';
import keystatic from '@keystatic/astro';

export default defineConfig({
  site: 'https://twincitiesskiclub.org',
  output: 'hybrid',
  adapter: undefined, // Keystatic local-only; production stays static
  integrations: [tailwind({ applyBaseStyles: false }), react(), keystatic()],
  image: {
    service: { entrypoint: 'astro/assets/services/sharp' },
  },
});
```

(`@astrojs/react` is required by Keystatic. Install: `npm install --save-dev @astrojs/react react react-dom @types/react @types/react-dom`)

- [ ] **Step 3: Write a stub `keystatic.config.ts` (full schema fills in Task 9)**

```ts
import { config, fields, singleton } from '@keystatic/core';

export default config({
  storage: { kind: 'local' },
  collections: {},
  singletons: {
    site_meta: singleton({
      label: 'Site metadata',
      path: 'src/content/site_meta',
      schema: {
        title: fields.text({ label: 'Site title' }),
        description: fields.text({ label: 'Default description' }),
      },
    }),
  },
});
```

- [ ] **Step 4: Verify Keystatic admin loads**

```bash
cd site && npm run dev &
sleep 4
curl -sf http://localhost:4321/keystatic/ -o /dev/null -w '%{http_code}\n' | grep -q '200' && echo OK
kill %1
```

Expected: `OK`. Visit `http://localhost:4321/keystatic/` in browser; Keystatic UI loads.

- [ ] **Step 5: Commit**

```bash
git add site/
git commit -m "feat(site): install Keystatic, local mode, stub schema"
```

---

## Phase B — Wix scrape (Phase 0 in the spec)

### Task 7: Scrape script — Python project setup

**Files:**
- Create: `scripts/wix_scrape/__init__.py`
- Create: `scripts/wix_scrape/__main__.py`
- Create: `scripts/wix_scrape/requirements.txt`
- Create: `tests/wix_scrape/__init__.py`
- Create: `tests/wix_scrape/test_smoke.py`

- [ ] **Step 1: Create directory + init files**

```bash
mkdir -p scripts/wix_scrape tests/wix_scrape
touch scripts/wix_scrape/__init__.py tests/wix_scrape/__init__.py
```

- [ ] **Step 2: Write `requirements.txt`**

`scripts/wix_scrape/requirements.txt`:
```
playwright==1.49.0
beautifulsoup4==4.12.3
requests==2.32.3
pytest==8.3.3
```

- [ ] **Step 3: Write minimal smoke test**

`tests/wix_scrape/test_smoke.py`:
```python
def test_module_imports():
    from scripts.wix_scrape import sitemap, page, images, inventory  # noqa: F401
```

- [ ] **Step 4: Run + verify failure**

```bash
pip install -r scripts/wix_scrape/requirements.txt
pytest tests/wix_scrape/test_smoke.py -v
```

Expected: FAIL — modules don't exist yet.

- [ ] **Step 5: Create the module files (empty stubs)**

```bash
touch scripts/wix_scrape/sitemap.py scripts/wix_scrape/page.py scripts/wix_scrape/images.py scripts/wix_scrape/inventory.py
```

- [ ] **Step 6: Run + verify pass**

```bash
pytest tests/wix_scrape/test_smoke.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add scripts/wix_scrape/ tests/wix_scrape/
git commit -m "feat(scrape): scaffold wix_scrape package + smoke test"
```

---

### Task 8: Scrape — sitemap fetcher

**Files:**
- Modify: `scripts/wix_scrape/sitemap.py`
- Create: `tests/wix_scrape/test_sitemap.py`

- [ ] **Step 1: Write failing test**

`tests/wix_scrape/test_sitemap.py`:
```python
from unittest.mock import patch
from scripts.wix_scrape.sitemap import fetch_sitemap_urls

SAMPLE_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://www.twincitiesskiclub.org/about</loc></url>
  <url><loc>https://www.twincitiesskiclub.org/coaches</loc></url>
</urlset>
"""

def test_fetch_sitemap_urls_extracts_all_urls():
    with patch('scripts.wix_scrape.sitemap.requests.get') as mock_get:
        mock_get.return_value.content = SAMPLE_XML
        mock_get.return_value.raise_for_status = lambda: None
        urls = fetch_sitemap_urls('https://example.com/sitemap.xml')
    assert urls == [
        'https://www.twincitiesskiclub.org/about',
        'https://www.twincitiesskiclub.org/coaches',
    ]
```

- [ ] **Step 2: Run + verify failure**

```bash
pytest tests/wix_scrape/test_sitemap.py -v
```

Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `fetch_sitemap_urls`**

`scripts/wix_scrape/sitemap.py`:
```python
"""Fetch and parse Wix sitemap XML to enumerate page URLs."""
from __future__ import annotations
import xml.etree.ElementTree as ET
import requests

SITEMAP_URL = 'https://www.twincitiesskiclub.org/pages-sitemap.xml'
_NS = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}


def fetch_sitemap_urls(url: str = SITEMAP_URL) -> list[str]:
    """Return the list of <loc> URLs from a sitemap.xml document."""
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    return [loc.text for loc in root.findall('sm:url/sm:loc', _NS) if loc.text]
```

- [ ] **Step 4: Run + verify pass**

```bash
pytest tests/wix_scrape/test_sitemap.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/wix_scrape/sitemap.py tests/wix_scrape/test_sitemap.py
git commit -m "feat(scrape): sitemap URL extractor"
```

---

### Task 9: Scrape — page rendering with Playwright

**Files:**
- Modify: `scripts/wix_scrape/page.py`
- Create: `tests/wix_scrape/test_page.py`

- [ ] **Step 1: Install Playwright browser**

```bash
playwright install chromium
```

- [ ] **Step 2: Write the page-fetcher function (no TDD on actual browser — too flaky for unit tests; integration-test the pure parts)**

`scripts/wix_scrape/page.py`:
```python
"""Fetch a Wix page with Playwright, expand widgets, return rendered HTML."""
from __future__ import annotations
from playwright.sync_api import sync_playwright

# Common Wix expander selectors — clicked before HTML capture.
_EXPAND_SELECTORS = [
    '[data-testid="accordion-header"]',
    'button[aria-expanded="false"]',
    '.accordion-item:not(.is-open) .accordion-header',
]


def fetch_rendered_html(url: str, timeout_ms: int = 30000) -> str:
    """Open the URL in headless Chromium, expand accordions, return final DOM."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until='networkidle', timeout=timeout_ms)
        for selector in _EXPAND_SELECTORS:
            for handle in page.locator(selector).all():
                try:
                    handle.click(timeout=1000)
                except Exception:  # noqa: BLE001
                    continue
        page.wait_for_load_state('networkidle')
        html = page.content()
        browser.close()
        return html


def extract_visible_text(html: str) -> str:
    """Strip scripts/styles; return whitespace-collapsed visible text."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script', 'style', 'noscript']):
        tag.decompose()
    lines = [ln.strip() for ln in soup.get_text('\n').splitlines() if ln.strip()]
    return '\n'.join(lines)


def extract_image_urls(html: str) -> list[str]:
    """All <img src> and CSS background-image URLs."""
    import re
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    urls: set[str] = set()
    for img in soup.find_all('img'):
        src = img.get('src') or img.get('data-src')
        if src and src.startswith('http'):
            urls.add(src)
    bg_re = re.compile(r"background-image\s*:\s*url\(['\"]?(https?://[^'\")]+)['\"]?\)")
    for m in bg_re.finditer(html):
        urls.add(m.group(1))
    return sorted(urls)
```

- [ ] **Step 3: Write unit tests for the pure parts**

`tests/wix_scrape/test_page.py`:
```python
from scripts.wix_scrape.page import extract_visible_text, extract_image_urls

SAMPLE_HTML = """
<html><body>
  <script>var x=1;</script>
  <style>p{color:red}</style>
  <h1>Hello</h1>
  <p>Welcome to TCSC.</p>
  <img src="https://static.wixstatic.com/media/abc.png" />
  <div style="background-image: url(https://static.wixstatic.com/media/def.jpg)"></div>
</body></html>
"""

def test_extract_visible_text_strips_script_style():
    text = extract_visible_text(SAMPLE_HTML)
    assert 'var x=1' not in text
    assert 'color:red' not in text
    assert 'Hello' in text
    assert 'Welcome to TCSC.' in text


def test_extract_image_urls_finds_img_and_background():
    urls = extract_image_urls(SAMPLE_HTML)
    assert 'https://static.wixstatic.com/media/abc.png' in urls
    assert 'https://static.wixstatic.com/media/def.jpg' in urls
```

- [ ] **Step 4: Run + verify pass**

```bash
pytest tests/wix_scrape/test_page.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/wix_scrape/page.py tests/wix_scrape/test_page.py
git commit -m "feat(scrape): page fetcher with Playwright + text/image extractors"
```

---

### Task 10: Scrape — image downloader

**Files:**
- Modify: `scripts/wix_scrape/images.py`
- Create: `tests/wix_scrape/test_images.py`

- [ ] **Step 1: Implement image downloader**

`scripts/wix_scrape/images.py`:
```python
"""Download images from Wix CDN to local filesystem."""
from __future__ import annotations
import hashlib
import re
from pathlib import Path
from urllib.parse import urlparse
import requests


def url_to_filename(url: str, page_slug: str, index: int) -> str:
    """Derive a stable, meaningful local filename for a Wix CDN image URL."""
    parsed = urlparse(url)
    ext = Path(parsed.path).suffix.lower() or '.jpg'
    if ext not in {'.jpg', '.jpeg', '.png', '.webp', '.svg', '.gif', '.avif'}:
        ext = '.jpg'
    digest = hashlib.sha1(url.encode()).hexdigest()[:8]
    return f'{page_slug}-{index:02d}-{digest}{ext}'


def download_image(url: str, dest_path: Path) -> bool:
    """Download `url` to `dest_path`. Return True on success."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    if dest_path.exists() and dest_path.stat().st_size > 0:
        return True
    try:
        resp = requests.get(url, timeout=30, stream=True)
        resp.raise_for_status()
        with dest_path.open('wb') as fh:
            for chunk in resp.iter_content(8192):
                fh.write(chunk)
        return True
    except requests.RequestException:
        return False


def largest_wix_variant(url: str) -> str:
    """Wix CDN URLs sometimes have ?w_=NN; rewrite to a maximum width."""
    return re.sub(r'/v1/fill/w_\d+', '/v1/fit/w_2500', url)
```

- [ ] **Step 2: Write tests**

`tests/wix_scrape/test_images.py`:
```python
from scripts.wix_scrape.images import url_to_filename, largest_wix_variant

def test_url_to_filename_includes_slug_index_extension():
    name = url_to_filename(
        'https://static.wixstatic.com/media/abc.png?x=1',
        page_slug='home',
        index=3,
    )
    assert name.startswith('home-03-')
    assert name.endswith('.png')


def test_largest_wix_variant_upgrades_fill_url():
    url = 'https://static.wixstatic.com/media/abc.png/v1/fill/w_235,h_74/abc.png'
    upgraded = largest_wix_variant(url)
    assert '/v1/fit/w_2500' in upgraded


def test_url_to_filename_falls_back_for_no_extension():
    name = url_to_filename('https://example.com/path/noext?a=b', 'p', 1)
    assert name.endswith('.jpg')
```

- [ ] **Step 3: Run + verify pass**

```bash
pytest tests/wix_scrape/test_images.py -v
```

Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add scripts/wix_scrape/images.py tests/wix_scrape/test_images.py
git commit -m "feat(scrape): image downloader + filename derivation"
```

---

### Task 11: Scrape — top-level orchestrator + inventory writer

**Files:**
- Modify: `scripts/wix_scrape/__main__.py`
- Modify: `scripts/wix_scrape/inventory.py`

- [ ] **Step 1: Write inventory writer**

`scripts/wix_scrape/inventory.py`:
```python
"""Write the human-readable inventory.md and CSV indexes."""
from __future__ import annotations
import csv
from pathlib import Path
from urllib.parse import urlparse


def write_images_csv(path: Path, rows: list[dict]) -> None:
    """rows: list of {'url', 'local_filename', 'page', 'alt_text'}."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=['url', 'local_filename', 'page', 'alt_text'])
        writer.writeheader()
        writer.writerows(rows)


def write_inventory_md(path: Path, pages: list[dict]) -> None:
    """pages: list of {'url', 'slug', 'title', 'headings', 'image_count', 'text_chars'}."""
    lines = ['# Wix Scrape Inventory', '']
    for p in pages:
        lines.append(f"## {p['slug']} — {p['title']}")
        lines.append(f"- Source: {p['url']}")
        lines.append(f"- Visible text: {p['text_chars']} chars")
        lines.append(f"- Images: {p['image_count']}")
        if p['headings']:
            lines.append('- Headings:')
            for h in p['headings']:
                lines.append(f"  - {h}")
        lines.append('')
    path.write_text('\n'.join(lines))


def url_to_slug(url: str) -> str:
    path = urlparse(url).path.strip('/')
    return path or 'home'
```

- [ ] **Step 2: Write the orchestrator `__main__.py`**

`scripts/wix_scrape/__main__.py`:
```python
"""Run a full Wix scrape into ./migration/. Usage: python -m scripts.wix_scrape"""
from __future__ import annotations
import json
import sys
from pathlib import Path

from scripts.wix_scrape.sitemap import fetch_sitemap_urls, SITEMAP_URL
from scripts.wix_scrape.page import fetch_rendered_html, extract_visible_text, extract_image_urls
from scripts.wix_scrape.images import url_to_filename, largest_wix_variant, download_image
from scripts.wix_scrape.inventory import url_to_slug, write_images_csv, write_inventory_md


def main() -> int:
    root = Path('migration')
    pages_dir = root / 'pages'
    images_dir = root / 'images'
    pages_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)

    urls = fetch_sitemap_urls(SITEMAP_URL)
    print(f'Found {len(urls)} URLs')

    image_rows: list[dict] = []
    page_summaries: list[dict] = []

    for url in urls:
        slug = url_to_slug(url)
        print(f'  → {slug}: {url}')

        try:
            html = fetch_rendered_html(url)
        except Exception as exc:  # noqa: BLE001
            print(f'    SKIP (fetch failed): {exc}')
            continue

        (pages_dir / f'{slug}.html').write_text(html)
        text = extract_visible_text(html)
        (pages_dir / f'{slug}.txt').write_text(text)

        # Extract image URLs (upgrade to largest variant on Wix CDN)
        image_urls = [largest_wix_variant(u) for u in extract_image_urls(html)]
        for i, img_url in enumerate(image_urls):
            local_name = url_to_filename(img_url, slug, i)
            local_path = images_dir / local_name
            if download_image(img_url, local_path):
                image_rows.append({
                    'url': img_url, 'local_filename': local_name,
                    'page': slug, 'alt_text': '',
                })

        # Capture headings for the inventory
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        headings = [h.get_text(strip=True) for h in soup.find_all(['h1', 'h2', 'h3'])
                    if h.get_text(strip=True)]
        title = soup.title.get_text(strip=True) if soup.title else slug

        # Write structured JSON for the page
        (pages_dir / f'{slug}.json').write_text(json.dumps({
            'url': url, 'slug': slug, 'title': title,
            'headings': headings, 'image_count': len(image_urls),
        }, indent=2))

        page_summaries.append({
            'url': url, 'slug': slug, 'title': title,
            'headings': headings, 'image_count': len(image_urls),
            'text_chars': len(text),
        })

    write_images_csv(root / 'images.csv', image_rows)
    write_inventory_md(root / 'inventory.md', page_summaries)
    print(f'Wrote {len(page_summaries)} pages, {len(image_rows)} images.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
```

- [ ] **Step 3: Run the scrape once**

```bash
python -m scripts.wix_scrape
```

Expected: ~15 page lines printed, `migration/` populated with `pages/`, `images/`, `images.csv`, `inventory.md`. Takes 2–4 minutes.

- [ ] **Step 4: Spot-check the output**

```bash
ls migration/pages/ migration/images/ | head -20
head -40 migration/inventory.md
```

Expected: home.html / about.html / coaches.html etc. present; image files exist; inventory.md is readable.

- [ ] **Step 5: Commit (scrape + migration output)**

```bash
git add scripts/wix_scrape/ migration/
git commit -m "feat(scrape): orchestrator + initial Wix content dump"
```

(The `migration/` directory is checked in as a tracked artifact. If it ends up >50MB, consider adding the `images/` subdir to `.gitignore` and storing it in S3 or similar; for now, in-repo is fine.)

---

## Phase C — Flask `/api/conditions` endpoint

### Task 12: Wax band recommendation function (pure logic)

**Files:**
- Create: `app/conditions/__init__.py`
- Create: `app/conditions/wax.py`
- Create: `tests/conditions/__init__.py`
- Create: `tests/conditions/test_wax.py`

- [ ] **Step 1: Write failing test**

`tests/conditions/test_wax.py`:
```python
from app.conditions.wax import recommend_wax, WaxBand

def test_cold_below_14():
    band = recommend_wax(temp_f=5)
    assert band == WaxBand.GREEN
    assert recommend_wax(temp_f=13).label.startswith('Green')


def test_blue_14_to_28():
    assert recommend_wax(temp_f=14) == WaxBand.BLUE
    assert recommend_wax(temp_f=20) == WaxBand.BLUE
    assert recommend_wax(temp_f=27) == WaxBand.BLUE


def test_purple_28_to_32():
    assert recommend_wax(temp_f=28) == WaxBand.PURPLE
    assert recommend_wax(temp_f=31) == WaxBand.PURPLE


def test_red_above_32():
    assert recommend_wax(temp_f=32) == WaxBand.RED
    assert recommend_wax(temp_f=45) == WaxBand.RED


def test_label_is_descriptive():
    assert recommend_wax(20).label == 'Blue wax · firm snow'
```

- [ ] **Step 2: Run + verify failure**

```bash
pytest tests/conditions/test_wax.py -v
```

Expected: FAIL — `ImportError`.

- [ ] **Step 3: Implement**

`app/conditions/__init__.py`: empty.

`app/conditions/wax.py`:
```python
"""Map temperature in Fahrenheit to a glide-wax recommendation band."""
from __future__ import annotations
from enum import Enum


class WaxBand(Enum):
    GREEN = ('green', 'Green wax · cold snow')
    BLUE = ('blue', 'Blue wax · firm snow')
    PURPLE = ('purple', 'Purple · transition snow')
    RED = ('red', 'Red wax · klister conditions')

    @property
    def label(self) -> str:
        return self.value[1]

    @property
    def slug(self) -> str:
        return self.value[0]


def recommend_wax(temp_f: float) -> WaxBand:
    if temp_f < 14:
        return WaxBand.GREEN
    if temp_f < 28:
        return WaxBand.BLUE
    if temp_f < 32:
        return WaxBand.PURPLE
    return WaxBand.RED
```

`tests/conditions/__init__.py`: empty.

- [ ] **Step 4: Run + verify pass**

```bash
pytest tests/conditions/test_wax.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add app/conditions/ tests/conditions/
git commit -m "feat(conditions): wax recommendation function"
```

---

### Task 13: Conditions assembler — pulls weather + trail data per location

**Files:**
- Create: `app/conditions/locations.py`
- Create: `app/conditions/service.py`
- Create: `tests/conditions/test_service.py`

- [ ] **Step 1: Write locations module**

`app/conditions/locations.py`:
```python
"""Four Twin Cities Nordic locations exposed by the conditions API."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    id: str
    name: str
    lat: float
    lon: float
    skinnyski_slug: str  # for trail_conditions lookup


LOCATIONS: list[Location] = [
    Location('wirth', 'Theodore Wirth', 44.9956, -93.3252, 'theodore-wirth'),
    Location('hyland', 'Hyland Park', 44.8451, -93.3950, 'hyland-park'),
    Location('french', 'French Park', 44.9787, -93.4854, 'french-park'),
    Location('battlecreek', 'Battle Creek', 44.9351, -93.0290, 'battle-creek'),
]
```

- [ ] **Step 2: Write failing test (mocks the weather/trail integrations)**

`tests/conditions/test_service.py`:
```python
from unittest.mock import patch
from app.conditions.service import build_conditions_response


def test_build_conditions_returns_one_entry_per_location():
    with patch('app.conditions.service.get_current_temp_f', return_value=20), \
         patch('app.conditions.service.get_wind_chill_f', return_value=12), \
         patch('app.conditions.service.get_trail_conditions', return_value='firm'):
        resp = build_conditions_response()
    assert 'updated_at' in resp
    assert len(resp['locations']) == 4
    first = resp['locations'][0]
    assert first['id'] == 'wirth'
    assert first['temp_f'] == 20
    assert first['wax_band'] == 'blue'
    assert first['wax_label'] == 'Blue wax · firm snow'


def test_build_conditions_handles_missing_data_gracefully():
    with patch('app.conditions.service.get_current_temp_f', return_value=None), \
         patch('app.conditions.service.get_wind_chill_f', return_value=None), \
         patch('app.conditions.service.get_trail_conditions', return_value=None):
        resp = build_conditions_response()
    assert resp['locations'][0]['temp_f'] is None
    assert resp['locations'][0]['wax_band'] is None
    assert resp.get('error') == 'upstream unavailable' or all(
        loc['temp_f'] is None for loc in resp['locations']
    )
```

- [ ] **Step 3: Run + verify failure**

```bash
pytest tests/conditions/test_service.py -v
```

Expected: FAIL.

- [ ] **Step 4: Implement**

`app/conditions/service.py`:
```python
"""Build the conditions response by combining weather + trail + wax recommendation."""
from __future__ import annotations
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

from app.conditions.locations import LOCATIONS, Location
from app.conditions.wax import recommend_wax

# Thin adapter functions — implemented as wrappers around app.integrations modules.
# Patched directly in tests.


def get_current_temp_f(lat: float, lon: float) -> Optional[float]:
    try:
        from app.integrations.weather import get_current_conditions
        result = get_current_conditions(lat, lon)
        return result.get('temperature_f') if result else None
    except Exception:  # noqa: BLE001
        return None


def get_wind_chill_f(lat: float, lon: float) -> Optional[float]:
    try:
        from app.integrations.weather import get_current_conditions
        result = get_current_conditions(lat, lon)
        return result.get('wind_chill_f') if result else None
    except Exception:  # noqa: BLE001
        return None


def get_trail_conditions(slug: str) -> Optional[str]:
    try:
        from app.integrations.trail_conditions import get_conditions_for_location
        return get_conditions_for_location(slug)
    except Exception:  # noqa: BLE001
        return None


def _build_location_entry(loc: Location) -> dict:
    temp = get_current_temp_f(loc.lat, loc.lon)
    wind = get_wind_chill_f(loc.lat, loc.lon)
    trail = get_trail_conditions(loc.skinnyski_slug)
    if temp is None:
        return {
            'id': loc.id, 'name': loc.name,
            'temp_f': None, 'wind_chill_f': None,
            'snow_conditions': trail, 'wax_band': None, 'wax_label': None,
        }
    band = recommend_wax(temp)
    return {
        'id': loc.id, 'name': loc.name,
        'temp_f': round(temp), 'wind_chill_f': round(wind) if wind is not None else None,
        'snow_conditions': trail, 'wax_band': band.slug, 'wax_label': band.label,
    }


def build_conditions_response() -> dict:
    entries = [_build_location_entry(loc) for loc in LOCATIONS]
    all_failed = all(e['temp_f'] is None for e in entries)
    resp = {
        'updated_at': datetime.now(ZoneInfo('America/Chicago')).isoformat(),
        'locations': entries,
    }
    if all_failed:
        resp['error'] = 'upstream unavailable'
    return resp
```

- [ ] **Step 5: Run + verify pass**

```bash
pytest tests/conditions/test_service.py -v
```

Expected: 2 passed. Real `app.integrations.weather.get_current_conditions` is a stub if it doesn't exist yet — confirm before relying on it. If the function signature differs from what's assumed, adjust the wrapper in `service.py`.

- [ ] **Step 6: Verify against the real weather module**

```bash
python -c "from app.integrations.weather import get_current_conditions; print(get_current_conditions(44.9956, -93.3252))"
```

If the import fails or the signature differs, adjust `service.py` accordingly. Document any deviation in the commit message.

- [ ] **Step 7: Commit**

```bash
git add app/conditions/ tests/conditions/
git commit -m "feat(conditions): assemble per-location response with wax recommendation"
```

---

### Task 14: Flask route + caching + CORS

**Files:**
- Create: `app/routes/conditions.py`
- Modify: `app/__init__.py` (register blueprint)
- Create: `tests/conditions/test_route.py`

- [ ] **Step 1: Write failing test**

`tests/conditions/test_route.py`:
```python
import json
from app import create_app


def test_get_conditions_returns_json():
    app = create_app()
    client = app.test_client()
    resp = client.get('/api/conditions')
    assert resp.status_code == 200
    assert resp.headers['Content-Type'].startswith('application/json')
    body = json.loads(resp.data)
    assert 'updated_at' in body
    assert isinstance(body['locations'], list)
    assert len(body['locations']) == 4


def test_get_conditions_sets_cors_for_marketing_site():
    app = create_app()
    client = app.test_client()
    resp = client.get('/api/conditions', headers={'Origin': 'https://twincitiesskiclub.org'})
    assert resp.headers.get('Access-Control-Allow-Origin') == 'https://twincitiesskiclub.org'


def test_get_conditions_rejects_other_origins():
    app = create_app()
    client = app.test_client()
    resp = client.get('/api/conditions', headers={'Origin': 'https://evil.com'})
    # CORS header should be absent or not the foreign origin
    assert resp.headers.get('Access-Control-Allow-Origin') != 'https://evil.com'
```

- [ ] **Step 2: Run + verify failure**

```bash
pytest tests/conditions/test_route.py -v
```

Expected: FAIL — route doesn't exist.

- [ ] **Step 3: Implement the blueprint**

`app/routes/conditions.py`:
```python
"""Public conditions API consumed by the marketing site."""
from __future__ import annotations
import time
from threading import Lock
from flask import Blueprint, jsonify, request, current_app

from app.conditions.service import build_conditions_response

bp = Blueprint('conditions', __name__, url_prefix='/api')

_CACHE_TTL_SECONDS = 300
_ALLOWED_ORIGIN = 'https://twincitiesskiclub.org'

_cache: dict[str, object] = {'expires_at': 0, 'body': None}
_lock = Lock()


def _get_cached_response() -> dict:
    now = time.time()
    if _cache['body'] is None or now >= _cache['expires_at']:
        with _lock:
            if _cache['body'] is None or now >= _cache['expires_at']:
                _cache['body'] = build_conditions_response()
                _cache['expires_at'] = now + _CACHE_TTL_SECONDS
    return _cache['body']  # type: ignore[return-value]


@bp.route('/conditions', methods=['GET'])
def get_conditions():
    body = _get_cached_response()
    resp = jsonify(body)
    origin = request.headers.get('Origin', '')
    if origin == _ALLOWED_ORIGIN or current_app.config.get('CONDITIONS_CORS_ALLOW_ANY'):
        resp.headers['Access-Control-Allow-Origin'] = origin or _ALLOWED_ORIGIN
        resp.headers['Vary'] = 'Origin'
    resp.headers['Cache-Control'] = f'public, max-age={_CACHE_TTL_SECONDS}'
    return resp
```

- [ ] **Step 4: Register the blueprint in `app/__init__.py`**

Find the existing blueprint registration block (search for `from app.routes import`). Add:

```python
from app.routes.conditions import bp as conditions_bp
app.register_blueprint(conditions_bp)
```

- [ ] **Step 5: Run + verify pass**

```bash
pytest tests/conditions/test_route.py -v
```

Expected: 3 passed. If `build_conditions_response` slows the test (real integrations called), wrap it: in `conftest.py` for the conditions tests, monkeypatch `app.routes.conditions.build_conditions_response` to return a stub.

- [ ] **Step 6: Manual smoke**

```bash
./scripts/dev.sh &
sleep 6
curl -sf http://localhost:5001/api/conditions | python -m json.tool | head -30
```

Expected: JSON output with `updated_at` and four locations.

- [ ] **Step 7: Commit**

```bash
git add app/routes/conditions.py app/__init__.py tests/conditions/test_route.py
git commit -m "feat(api): /api/conditions endpoint with 5min cache + CORS"
```

---

## Phase D — Keystatic content model

### Task 15: Full Keystatic schema

**Files:**
- Modify: `site/keystatic.config.ts`

- [ ] **Step 1: Replace the stub schema with the full one from the spec**

`site/keystatic.config.ts`:
```ts
import { config, fields, collection, singleton } from '@keystatic/core';

const requiredImage = (label: string) =>
  fields.image({
    label,
    directory: 'public/images/uploads',
    publicPath: '/images/uploads/',
    validation: { isRequired: true },
  });

export default config({
  storage: { kind: 'local' },

  singletons: {
    home: singleton({
      label: 'Home page',
      path: 'src/content/pages/home',
      schema: {
        hero_headline: fields.text({ label: 'Hero headline', validation: { isRequired: true } }),
        hero_image: requiredImage('Hero photograph'),
        hero_image_alt: fields.text({ label: 'Hero image alt text', validation: { isRequired: true } }),
        registration_state: fields.select({
          label: 'Registration state',
          options: [
            { label: 'Open', value: 'open' },
            { label: 'Coming soon', value: 'coming_soon' },
            { label: 'Closed (in-season)', value: 'closed' },
          ],
          defaultValue: 'closed',
        }),
        cta_open_label: fields.text({ label: 'CTA label when open', defaultValue: 'Register for the season →' }),
        cta_open_url: fields.url({ label: 'CTA URL when open' }),
        cta_coming_soon_label: fields.text({ label: 'CTA label when coming soon', defaultValue: 'Get on the list' }),
        cta_coming_soon_url: fields.url({ label: 'CTA URL when coming soon' }),
        cta_closed_label: fields.text({ label: 'CTA label when closed', defaultValue: 'Member area' }),
        cta_closed_url: fields.url({ label: 'CTA URL when closed' }),
        mission_paragraph: fields.text({ label: 'Mission paragraph', multiline: true }),
      },
    }),

    about: singleton({
      label: 'About page',
      path: 'src/content/pages/about',
      schema: {
        headline: fields.text({ label: 'Headline' }),
        intro: fields.text({ label: 'Intro paragraph', multiline: true }),
        body: fields.markdoc({ label: 'Body' }),
      },
    }),

    community: singleton({
      label: 'Community page',
      path: 'src/content/pages/community',
      schema: {
        headline: fields.text({ label: 'Headline' }),
        intro: fields.text({ label: 'Intro', multiline: true }),
        team_bonding_activities: fields.array(fields.text({ label: 'Activity' }), {
          label: 'Team bonding activities',
        }),
      },
    }),

    racing: singleton({
      label: 'Racing page',
      path: 'src/content/pages/racing',
      schema: {
        headline: fields.text({ label: 'Headline' }),
        intro: fields.text({ label: 'Intro', multiline: true }),
        races: fields.array(
          fields.object({
            name: fields.text({ label: 'Name' }),
            location: fields.text({ label: 'Location' }),
            date: fields.text({ label: 'Date or window' }),
            notes: fields.text({ label: 'Notes', multiline: true }),
          }),
          { label: 'Races' },
        ),
        body: fields.markdoc({ label: 'Body' }),
      },
    }),

    sponsors_page: singleton({
      label: 'Sponsors page',
      path: 'src/content/pages/sponsors_page',
      schema: {
        headline: fields.text({ label: 'Headline' }),
        intro: fields.text({ label: 'Intro', multiline: true }),
      },
    }),

    contact: singleton({
      label: 'Contact page',
      path: 'src/content/pages/contact',
      schema: {
        email: fields.text({ label: 'Email' }),
        mailing_address: fields.text({ label: 'Mailing address', multiline: true }),
        instagram_url: fields.url({ label: 'Instagram URL' }),
        slack_invite_url: fields.url({ label: 'Slack invite URL' }),
      },
    }),

    nav: singleton({
      label: 'Navigation',
      path: 'src/content/nav',
      schema: {
        top_links: fields.array(
          fields.object({
            label: fields.text({ label: 'Label' }),
            href: fields.text({ label: 'href' }),
          }),
          { label: 'Top nav links' },
        ),
      },
    }),

    site_meta: singleton({
      label: 'Site metadata',
      path: 'src/content/site_meta',
      schema: {
        title: fields.text({ label: 'Site title', defaultValue: 'Twin Cities Ski Club' }),
        description: fields.text({ label: 'Default meta description', multiline: true }),
        og_image: fields.image({ label: 'Default OG image', directory: 'public/og', publicPath: '/og/' }),
      },
    }),
  },

  collections: {
    coaches: collection({
      label: 'Coaches',
      path: 'src/content/coaches/*',
      slugField: 'slug',
      schema: {
        slug: fields.slug({ name: { label: 'Name (display)' } }),
        role: fields.text({ label: 'Role line' }),
        photo: requiredImage('Coach photo'),
        photo_alt: fields.text({ label: 'Photo alt text', validation: { isRequired: true } }),
        bio: fields.markdoc({ label: 'Bio' }),
        credentials: fields.array(fields.text({ label: 'Credential' }), { label: 'Credentials' }),
        order: fields.integer({ label: 'Sort order', defaultValue: 0 }),
      },
    }),

    practice_seasons: collection({
      label: 'Practice seasons',
      path: 'src/content/practice_seasons/*',
      slugField: 'slug',
      schema: {
        slug: fields.slug({ name: { label: 'Season name' } }),
        date_range: fields.text({ label: 'Date range (display)' }),
        fee_cents: fields.integer({ label: 'Fee (cents)' }),
        summary: fields.text({ label: 'Summary', multiline: true }),
        what_included: fields.array(fields.text({ label: 'Item' }), { label: 'What is included' }),
      },
    }),

    trips: collection({
      label: 'Trips (marketing pages)',
      path: 'src/content/trips/*',
      slugField: 'slug',
      schema: {
        slug: fields.slug({ name: { label: 'Trip name' } }),
        location: fields.text({ label: 'Location' }),
        dates: fields.text({ label: 'Dates' }),
        cost_summary: fields.text({ label: 'Cost summary', multiline: true }),
        signup_deadline: fields.text({ label: 'Sign-up deadline' }),
        capacity: fields.text({ label: 'Capacity' }),
        what_to_expect: fields.markdoc({ label: 'What to expect' }),
        refund_policy: fields.text({ label: 'Refund policy', multiline: true }),
        signup_url: fields.url({ label: 'Sign-up URL (external; Flask app)' }),
        hero_photo: fields.image({ label: 'Hero photo', directory: 'public/photos', publicPath: '/photos/' }),
      },
    }),

    photos: collection({
      label: 'Photos (mosaic)',
      path: 'src/content/photos/*',
      slugField: 'slug',
      schema: {
        slug: fields.slug({ name: { label: 'Photo identifier' } }),
        image: requiredImage('Image'),
        alt_text: fields.text({ label: 'Alt text', validation: { isRequired: true } }),
        caption: fields.text({ label: 'Caption', multiline: true }),
        event_tag: fields.select({
          label: 'Event tag',
          options: [
            { label: 'Practice', value: 'practice' },
            { label: 'Birkie', value: 'birkie' },
            { label: 'Sisu', value: 'sisu' },
            { label: 'Travel', value: 'travel' },
            { label: 'Social', value: 'social' },
            { label: 'Race', value: 'race' },
          ],
          defaultValue: 'practice',
        }),
        member_names: fields.array(fields.text({ label: 'Name' }), { label: 'Members in photo' }),
        order: fields.integer({ label: 'Sort order', defaultValue: 0 }),
        show_on_home: fields.checkbox({ label: 'Show on home mosaic', defaultValue: false }),
        photo_consent_recorded: fields.checkbox({
          label: 'Photo consent recorded (required to render)',
          defaultValue: false,
        }),
      },
    }),

    sponsors: collection({
      label: 'Sponsors',
      path: 'src/content/sponsors/*',
      slugField: 'slug',
      schema: {
        slug: fields.slug({ name: { label: 'Sponsor name' } }),
        logo: requiredImage('Logo'),
        tier: fields.select({
          label: 'Tier',
          options: [
            { label: 'Trailblazer', value: 'trailblazer' },
            { label: 'Supporter', value: 'supporter' },
            { label: 'Friend', value: 'friend' },
          ],
          defaultValue: 'supporter',
        }),
        url: fields.url({ label: 'URL' }),
      },
    }),

    wax_entries: collection({
      label: 'Wax Room entries',
      path: 'src/content/wax_entries/*',
      slugField: 'slug',
      schema: {
        slug: fields.slug({ name: { label: 'Title' } }),
        date: fields.date({ label: 'Date', validation: { isRequired: true } }),
        author_name: fields.text({ label: 'Author name' }),
        author_role: fields.select({
          label: 'Author role',
          options: [
            { label: 'Coach', value: 'coach' },
            { label: 'Member', value: 'member' },
            { label: 'Board', value: 'board' },
          ],
          defaultValue: 'coach',
        }),
        lede: fields.text({ label: 'Lede paragraph', multiline: true }),
        body: fields.markdoc({ label: 'Body' }),
        photo: fields.image({ label: 'Photo (optional)', directory: 'public/photos', publicPath: '/photos/' }),
        conditions_snapshot: fields.object({
          location: fields.text({ label: 'Location' }),
          temp_f: fields.integer({ label: 'Temp (°F)' }),
          wax_used: fields.text({ label: 'Wax used' }),
        }, { label: 'Conditions snapshot (optional)' }),
      },
    }),
  },
});
```

- [ ] **Step 2: Run dev server, open Keystatic UI**

```bash
cd site && npm run dev &
sleep 4
open http://localhost:4321/keystatic
```

Click through each collection and singleton. Confirm fields render. Kill server.

- [ ] **Step 3: Commit**

```bash
git add site/keystatic.config.ts
git commit -m "feat(site): full Keystatic schema (singletons + collections)"
```

---

### Task 16: Astro Content Collections mirror

**Files:**
- Create: `site/src/content/config.ts`

- [ ] **Step 1: Write the Astro side of the schema so Astro pages can `getCollection()` and `getEntry()` with types**

```ts
import { defineCollection, z } from 'astro:content';

const photos = defineCollection({
  type: 'data',
  schema: z.object({
    image: z.string(),
    alt_text: z.string().min(1),
    caption: z.string().optional(),
    event_tag: z.enum(['practice', 'birkie', 'sisu', 'travel', 'social', 'race']),
    member_names: z.array(z.string()).optional(),
    order: z.number().int().default(0),
    show_on_home: z.boolean().default(false),
    photo_consent_recorded: z.boolean().default(false),
  }),
});

const coaches = defineCollection({
  type: 'content',
  schema: z.object({
    role: z.string(),
    photo: z.string(),
    photo_alt: z.string().min(1),
    credentials: z.array(z.string()).optional(),
    order: z.number().int().default(0),
  }),
});

const practice_seasons = defineCollection({
  type: 'data',
  schema: z.object({
    date_range: z.string(),
    fee_cents: z.number().int(),
    summary: z.string(),
    what_included: z.array(z.string()),
  }),
});

const trips = defineCollection({
  type: 'content',
  schema: z.object({
    location: z.string(),
    dates: z.string(),
    cost_summary: z.string(),
    signup_deadline: z.string().optional(),
    capacity: z.string().optional(),
    refund_policy: z.string().optional(),
    signup_url: z.string().url().optional(),
    hero_photo: z.string().optional(),
  }),
});

const wax_entries = defineCollection({
  type: 'content',
  schema: z.object({
    date: z.coerce.date(),
    author_name: z.string(),
    author_role: z.enum(['coach', 'member', 'board']),
    lede: z.string(),
    photo: z.string().optional(),
    conditions_snapshot: z
      .object({
        location: z.string(),
        temp_f: z.number().int(),
        wax_used: z.string(),
      })
      .optional(),
  }),
});

const sponsors = defineCollection({
  type: 'data',
  schema: z.object({
    logo: z.string(),
    tier: z.enum(['trailblazer', 'supporter', 'friend']),
    url: z.string().url().optional(),
  }),
});

export const collections = { photos, coaches, practice_seasons, trips, wax_entries, sponsors };
```

- [ ] **Step 2: Build to verify types**

```bash
cd site && npm run check
```

Expected: 0 errors. (Content directories are empty — that's fine.)

- [ ] **Step 3: Commit**

```bash
git add site/src/content/config.ts
git commit -m "feat(site): Astro content collections mirror Keystatic schema"
```

---

## Phase E — Component primitives

### Task 17: `<Nav>` + `<MobileNavPanel>`

**Files:**
- Create: `site/src/components/Nav.astro`
- Create: `site/src/components/MobileNavPanel.astro`
- Create: `site/src/components/CtaForState.astro`

- [ ] **Step 1: Write `CtaForState.astro` — reads `home.registration_state`**

```astro
---
interface Props {
  state: 'open' | 'coming_soon' | 'closed';
  label_open: string; url_open?: string;
  label_coming_soon: string; url_coming_soon?: string;
  label_closed: string; url_closed?: string;
  variant?: 'on-navy' | 'on-paper';
}
const { state, label_open, url_open, label_coming_soon, url_coming_soon, label_closed, url_closed, variant = 'on-navy' } = Astro.props;
const label = state === 'open' ? label_open : state === 'coming_soon' ? label_coming_soon : label_closed;
const url = state === 'open' ? url_open : state === 'coming_soon' ? url_coming_soon : url_closed;
const disabled = state !== 'open' && !url;
const cls = variant === 'on-navy'
  ? 'inline-flex items-center px-5 py-3 rounded-md bg-mint text-navy font-medium text-sm'
  : 'inline-flex items-center px-5 py-3 rounded-md bg-navy text-mint font-medium text-sm';
---
{disabled ? (
  <span class={cls + ' opacity-70 cursor-default'}>{label}</span>
) : (
  <a href={url} class={cls}>{label}</a>
)}
```

- [ ] **Step 2: Write `Nav.astro`**

```astro
---
import { getEntry } from 'astro:content';
import CtaForState from '@/components/CtaForState.astro';

const home = await getEntry('site_meta' as any, 'home').catch(() => null);
// Fallbacks for when content isn't ported yet
const state = (home as any)?.data?.registration_state ?? 'closed';
const cta_open_label = (home as any)?.data?.cta_open_label ?? 'Register for the season →';
const cta_open_url = (home as any)?.data?.cta_open_url ?? 'https://tcsc.ski/register';
const cta_coming_soon_label = (home as any)?.data?.cta_coming_soon_label ?? 'Get on the list';
const cta_coming_soon_url = (home as any)?.data?.cta_coming_soon_url;
const cta_closed_label = (home as any)?.data?.cta_closed_label ?? 'Member area';
const cta_closed_url = (home as any)?.data?.cta_closed_url;

const navLinks = [
  { label: 'About', href: '/about' },
  { label: 'Community', href: '/community' },
  { label: 'Racing', href: '/racing' },
  { label: 'Coaches', href: '/coaches' },
  { label: 'Wax Room', href: '/wax-room' },
  { label: 'Sponsors', href: '/sponsors' },
];
---
<header class="bg-navy text-paper border-b border-mint/10">
  <div class="mx-auto max-w-7xl px-6 py-5 flex items-center justify-between gap-6">
    <a href="/" class="flex items-center gap-3" aria-label="TCSC home">
      <svg width="56" height="18" viewBox="0 0 100 30" aria-hidden="true">
        <g fill="oklch(0.91 0.12 155)">
          <rect x="0" y="6" width="22" height="4" rx="2" />
          <rect x="0" y="18" width="22" height="4" rx="2" />
          <rect x="28" y="6" width="14" height="4" rx="2" />
          <rect x="28" y="18" width="14" height="4" rx="2" />
          <rect x="48" y="6" width="14" height="4" rx="2" />
          <rect x="48" y="18" width="14" height="4" rx="2" />
          <rect x="68" y="6" width="14" height="4" rx="2" />
          <rect x="68" y="18" width="14" height="4" rx="2" />
        </g>
      </svg>
      <span class="text-xs tracking-widest font-bold">TCSC</span>
    </a>

    <nav class="hidden md:flex items-center gap-7 text-sm text-paper/85">
      {navLinks.map((l) => <a href={l.href} class="hover:text-mint">{l.label}</a>)}
    </nav>

    <div class="hidden md:block">
      <CtaForState
        state={state}
        label_open={cta_open_label} url_open={cta_open_url}
        label_coming_soon={cta_coming_soon_label} url_coming_soon={cta_coming_soon_url}
        label_closed={cta_closed_label} url_closed={cta_closed_url}
      />
    </div>

    <button
      class="md:hidden p-2 -m-2 text-paper"
      aria-label="Open menu"
      data-mobile-toggle
    >
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M4 6h16M4 12h16M4 18h16" />
      </svg>
    </button>
  </div>
</header>
```

- [ ] **Step 3: Write `MobileNavPanel.astro`**

```astro
---
const navLinks = [
  { label: 'About', href: '/about' },
  { label: 'Community', href: '/community' },
  { label: 'Racing', href: '/racing' },
  { label: 'Coaches', href: '/coaches' },
  { label: 'Wax Room', href: '/wax-room' },
  { label: 'Sponsors', href: '/sponsors' },
];
---
<div
  data-mobile-panel
  class="fixed inset-0 z-50 bg-navy text-paper p-8 hidden flex-col"
  aria-hidden="true"
>
  <button class="self-end p-2 -m-2" aria-label="Close menu" data-mobile-close>
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M6 6l12 12M6 18L18 6" />
    </svg>
  </button>

  <nav class="flex-1 flex flex-col justify-center gap-6 text-2xl">
    {navLinks.map((l) => <a href={l.href} class="hover:text-mint">{l.label}</a>)}
  </nav>

  <div class="mt-auto">
    <slot name="cta" />
  </div>
</div>

<script>
  const toggle = document.querySelector('[data-mobile-toggle]');
  const panel = document.querySelector('[data-mobile-panel]') as HTMLElement | null;
  const close = document.querySelector('[data-mobile-close]');
  if (toggle && panel && close) {
    toggle.addEventListener('click', () => {
      panel.classList.remove('hidden');
      panel.classList.add('flex');
      panel.setAttribute('aria-hidden', 'false');
    });
    close.addEventListener('click', () => {
      panel.classList.add('hidden');
      panel.classList.remove('flex');
      panel.setAttribute('aria-hidden', 'true');
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') close.dispatchEvent(new Event('click'));
    });
  }
</script>
```

- [ ] **Step 4: Render Nav on the homepage to confirm**

Update `site/src/pages/index.astro`:
```astro
---
import BaseLayout from '@/layouts/BaseLayout.astro';
import Nav from '@/components/Nav.astro';
import MobileNavPanel from '@/components/MobileNavPanel.astro';
---
<BaseLayout title="TCSC — Twin Cities Ski Club" variant="home">
  <Nav />
  <MobileNavPanel />
  <main class="min-h-screen p-12 bg-navy text-paper">
    <h1 class="font-display text-6xl text-mint">Twin Cities Ski Club</h1>
  </main>
</BaseLayout>
```

- [ ] **Step 5: Run + verify**

```bash
cd site && npm run dev &
sleep 3
curl -sf http://localhost:4321/ | grep -q 'data-mobile-toggle' && echo OK
kill %1
```

Expected: `OK`. Manually verify the mobile hamburger toggles the panel.

- [ ] **Step 6: Commit**

```bash
git add site/src/components/ site/src/pages/index.astro
git commit -m "feat(site): Nav + MobileNavPanel + CtaForState components"
```

---

### Task 18: `<SectionBand>`, `<MissionPanel>`, `<CTAStrip>`, `<Footer>` (batched)

These four are layout primitives that touch similar territory; bundle them.

**Files:**
- Create: `site/src/components/SectionBand.astro`
- Create: `site/src/components/MissionPanel.astro`
- Create: `site/src/components/CTAStrip.astro`
- Create: `site/src/components/Footer.astro`

- [ ] **Step 1: Write `SectionBand.astro`**

```astro
---
interface Props {
  variant?: 'navy' | 'paper' | 'paper-on-navy';
  number?: string;
  heading?: string;
  subhead?: string;
  contentMax?: 'wide' | 'narrow';
}
const { variant = 'paper', number, heading, subhead, contentMax = 'wide' } = Astro.props;

const surface = variant === 'navy'
  ? 'bg-navy text-paper'
  : variant === 'paper-on-navy'
  ? 'bg-paper text-ink'
  : 'bg-paper text-ink';

const innerMax = contentMax === 'narrow' ? 'max-w-3xl' : 'max-w-7xl';
const padding = variant === 'paper-on-navy'
  ? 'rounded-xl px-8 py-12 md:px-16 md:py-20'
  : 'px-6 md:px-10 py-20 md:py-28';
---
<section class={surface + ' ' + (variant === 'paper-on-navy' ? 'bg-navy py-20' : '')}>
  <div class={'mx-auto ' + innerMax + ' ' + (variant === 'paper-on-navy' ? 'bg-paper text-ink ' + padding : padding)}>
    {number && (
      <div class="text-sm font-semibold tracking-wider mb-3 text-mint-deep">{number}</div>
    )}
    {heading && (
      <h2 class="font-display text-4xl md:text-5xl leading-[1.05] mb-4">{heading}</h2>
    )}
    {subhead && (
      <p class="text-lg leading-relaxed max-w-prose mb-8 opacity-90">{subhead}</p>
    )}
    <slot />
  </div>
</section>
```

- [ ] **Step 2: Write `MissionPanel.astro`**

```astro
---
interface Props { body: string; }
const { body } = Astro.props;
---
<section class="bg-navy py-20">
  <div class="mx-auto max-w-4xl px-6">
    <div class="bg-paper text-ink rounded-xl px-8 py-12 md:px-16 md:py-16">
      <p class="font-display text-2xl md:text-3xl leading-[1.25] text-navy">{body}</p>
    </div>
  </div>
</section>
```

- [ ] **Step 3: Write `CTAStrip.astro`**

```astro
---
interface Props {
  heading: string;
  subhead?: string;
  cta_label: string;
  cta_url: string;
}
const { heading, subhead, cta_label, cta_url } = Astro.props;
---
<section class="bg-navy border-t-[3px] border-coral text-paper">
  <div class="mx-auto max-w-7xl px-6 py-16 md:py-20 flex flex-col md:flex-row md:items-center md:justify-between gap-6">
    <div>
      <h2 class="font-display text-3xl md:text-4xl text-mint leading-tight">{heading}</h2>
      {subhead && <p class="mt-2 text-paper/75 text-sm md:text-base max-w-xl">{subhead}</p>}
    </div>
    <a
      href={cta_url}
      class="inline-flex items-center px-6 py-3 bg-mint text-navy font-semibold rounded-md"
    >{cta_label}</a>
  </div>
</section>
```

- [ ] **Step 4: Write `Footer.astro`**

```astro
---
import { getEntry } from 'astro:content';
const contact = await getEntry('contact' as any, 'contact' as any).catch(() => null) as any;
const email = contact?.data?.email ?? 'contact@twincitiesskiclub.org';
const ig = contact?.data?.instagram_url;
---
<footer class="bg-navy text-paper border-t border-mint/10">
  <div class="mx-auto max-w-7xl px-6 py-14 grid gap-10 md:grid-cols-3">
    <div>
      <div class="text-sm font-semibold tracking-widest text-mint">TCSC</div>
      <p class="mt-3 text-sm text-paper/70 max-w-xs leading-relaxed">
        Twin Cities Ski Club — a 501(c)(3) nonprofit Nordic ski community in Minneapolis / St. Paul.
      </p>
    </div>
    <nav class="text-sm space-y-2">
      <a class="block hover:text-mint" href="/about">About</a>
      <a class="block hover:text-mint" href="/community">Community</a>
      <a class="block hover:text-mint" href="/racing">Racing</a>
      <a class="block hover:text-mint" href="/coaches">Coaches</a>
      <a class="block hover:text-mint" href="/wax-room">Wax Room</a>
      <a class="block hover:text-mint" href="/sponsors">Sponsors</a>
    </nav>
    <div class="text-sm space-y-2">
      <a class="block hover:text-mint" href={'mailto:' + email}>{email}</a>
      {ig && <a class="block hover:text-mint" href={ig}>Instagram</a>}
      <p class="text-paper/50 pt-3">© {new Date().getFullYear()} Twin Cities Ski Club</p>
    </div>
  </div>
</footer>
```

- [ ] **Step 5: Build + verify**

```bash
cd site && npm run check && npm run build
```

Expected: 0 errors, build succeeds.

- [ ] **Step 6: Commit**

```bash
git add site/src/components/
git commit -m "feat(site): SectionBand, MissionPanel, CTAStrip, Footer primitives"
```

---

### Task 19: `<Hero>` home variant + inner variant

**Files:**
- Create: `site/src/components/HeroHome.astro`
- Create: `site/src/components/HeroInner.astro`

- [ ] **Step 1: Write `HeroHome.astro` (full-bleed photo + headline)**

```astro
---
import { Image } from 'astro:assets';
import CtaForState from '@/components/CtaForState.astro';

interface Props {
  headline: string;
  image: string;          // path under /public
  imageAlt: string;
  state: 'open' | 'coming_soon' | 'closed';
  cta_open_label: string; cta_open_url?: string;
  cta_coming_soon_label: string; cta_coming_soon_url?: string;
  cta_closed_label: string; cta_closed_url?: string;
}
const props = Astro.props as Props;
---
<section class="relative bg-navy overflow-hidden">
  <div class="relative h-[68vh] min-h-[520px]">
    {props.image
      ? <img
          src={props.image}
          alt={props.imageAlt}
          class="absolute inset-0 w-full h-full object-cover"
          loading="eager"
          decoding="async"
        />
      : null}
    <div class="absolute inset-0 bg-gradient-to-t from-navy/95 via-navy/30 to-transparent"></div>
    <div class="relative h-full mx-auto max-w-7xl px-6 flex flex-col justify-end pb-16 md:pb-24 text-paper">
      <h1 class="font-display text-5xl md:text-7xl leading-[0.95] text-mint max-w-4xl">{props.headline}</h1>
      <div class="mt-8">
        <CtaForState
          state={props.state}
          label_open={props.cta_open_label} url_open={props.cta_open_url}
          label_coming_soon={props.cta_coming_soon_label} url_coming_soon={props.cta_coming_soon_url}
          label_closed={props.cta_closed_label} url_closed={props.cta_closed_url}
        />
      </div>
    </div>
  </div>
</section>
```

- [ ] **Step 2: Write `HeroInner.astro` (paper background, ink display)**

```astro
---
interface Props { headline: string; subhead?: string; }
const { headline, subhead } = Astro.props;
---
<section class="bg-paper text-ink border-b border-ink/10">
  <div class="mx-auto max-w-5xl px-6 py-16 md:py-24">
    <h1 class="font-display text-4xl md:text-6xl leading-[1.05] text-navy">{headline}</h1>
    {subhead && <p class="mt-5 text-lg md:text-xl text-slate max-w-prose">{subhead}</p>}
  </div>
</section>
```

- [ ] **Step 3: Build + verify**

```bash
cd site && npm run check
```

Expected: 0 errors.

- [ ] **Step 4: Commit**

```bash
git add site/src/components/HeroHome.astro site/src/components/HeroInner.astro
git commit -m "feat(site): Hero home + inner variants"
```

---

## Phase F — The signature device: `<LiveConditions>`

### Task 20: `<LiveConditions>` component

**Files:**
- Create: `site/src/components/LiveConditions.astro`
- Create: `site/src/components/LiveConditions.client.ts`

- [ ] **Step 1: Write the Astro shell (renders skeleton; client script hydrates with real data)**

```astro
---
interface Props { variant?: 'prominent' | 'compact'; }
const { variant = 'prominent' } = Astro.props;
const apiUrl = import.meta.env.PUBLIC_CONDITIONS_API_URL ?? 'https://tcsc.ski/api/conditions';
---
<section
  class={variant === 'prominent'
    ? 'bg-navy-deep text-paper border-y border-mint/10'
    : 'bg-navy/40 text-paper text-xs border-t border-mint/10'}
  data-live-conditions
  data-api-url={apiUrl}
  aria-live="polite"
  aria-label="Current ski conditions"
>
  <div class={variant === 'prominent'
    ? 'mx-auto max-w-7xl px-6 py-5 grid grid-cols-2 md:grid-cols-4 gap-px bg-mint/10'
    : 'mx-auto max-w-7xl px-6 py-2 flex gap-4 flex-wrap text-paper/70'}>
    {['wirth', 'hyland', 'french', 'battlecreek'].map((id) => (
      <div data-location={id} class={variant === 'prominent' ? 'bg-navy-deep p-4' : ''}>
        <div class="text-[10px] tracking-widest uppercase text-mint" data-name>—</div>
        <div class="font-display text-2xl md:text-3xl text-mint mt-1" data-temp>—</div>
        <div class="text-xs text-paper/70 mt-1" data-wax>—</div>
      </div>
    ))}
  </div>
  {variant === 'prominent' && (
    <div class="mx-auto max-w-7xl px-6 pb-3 text-[11px] text-coral">
      <span data-updated>Loading conditions…</span>
    </div>
  )}
</section>

<script>
  import('@/components/LiveConditions.client').then((m) => m.init());
</script>
```

- [ ] **Step 2: Write the client script**

`site/src/components/LiveConditions.client.ts`:
```typescript
type LocResp = {
  id: string;
  name: string;
  temp_f: number | null;
  wind_chill_f: number | null;
  snow_conditions: string | null;
  wax_band: string | null;
  wax_label: string | null;
};
type Resp = { updated_at: string; locations: LocResp[]; error?: string };

const REFRESH_MS = 5 * 60 * 1000;

async function fetchAndRender(root: HTMLElement) {
  const url = root.dataset.apiUrl!;
  try {
    const r = await fetch(url, { cache: 'no-store' });
    if (!r.ok) throw new Error('Bad status');
    const data: Resp = await r.json();
    renderInto(root, data);
  } catch {
    renderFailure(root);
  }
}

function renderInto(root: HTMLElement, data: Resp) {
  data.locations.forEach((loc) => {
    const el = root.querySelector(`[data-location="${loc.id}"]`) as HTMLElement | null;
    if (!el) return;
    setText(el, '[data-name]', loc.name);
    setText(el, '[data-temp]', loc.temp_f == null ? '—' : `${loc.temp_f}°F`);
    setText(el, '[data-wax]', loc.wax_label ?? 'Conditions unavailable');
  });
  const stamp = root.querySelector('[data-updated]') as HTMLElement | null;
  if (stamp) {
    const date = new Date(data.updated_at);
    const mins = Math.max(0, Math.floor((Date.now() - date.getTime()) / 60000));
    stamp.textContent = data.error
      ? '● Conditions unavailable'
      : `● Live · updated ${mins} min ago`;
  }
}

function renderFailure(root: HTMLElement) {
  const stamp = root.querySelector('[data-updated]') as HTMLElement | null;
  if (stamp) stamp.textContent = '● Conditions unavailable';
}

function setText(el: HTMLElement, sel: string, val: string) {
  const t = el.querySelector(sel) as HTMLElement | null;
  if (t) t.textContent = val;
}

export function init() {
  const roots = document.querySelectorAll<HTMLElement>('[data-live-conditions]');
  roots.forEach((root) => {
    fetchAndRender(root);
    setInterval(() => fetchAndRender(root), REFRESH_MS);
  });
}
```

- [ ] **Step 3: Add to homepage to confirm wiring**

Update `site/src/pages/index.astro`:
```astro
---
import BaseLayout from '@/layouts/BaseLayout.astro';
import Nav from '@/components/Nav.astro';
import MobileNavPanel from '@/components/MobileNavPanel.astro';
import LiveConditions from '@/components/LiveConditions.astro';
---
<BaseLayout title="TCSC — Twin Cities Ski Club" variant="home">
  <Nav />
  <MobileNavPanel />
  <LiveConditions variant="prominent" />
  <main class="min-h-screen p-12 bg-navy text-paper">
    <h1 class="font-display text-6xl text-mint">Twin Cities Ski Club</h1>
  </main>
</BaseLayout>
```

- [ ] **Step 4: Verify the local Flask app is reachable and CORS-permissive for the dev origin**

The dev origin is `http://localhost:4321` which is NOT `https://twincitiesskiclub.org`. Add a dev-only env flag in Flask so localhost works:

Edit `app/routes/conditions.py`, change the CORS check from `origin == _ALLOWED_ORIGIN` to:
```python
allowed = origin == _ALLOWED_ORIGIN or (
    origin.startswith('http://localhost:') and current_app.config.get('FLASK_ENV') == 'development'
)
```

Then run both servers:
```bash
./scripts/dev.sh &       # Flask on :5001
cd site && npm run dev   # Astro on :4321
```

Visit `http://localhost:4321/` — the conditions strip should show real data (or "Conditions unavailable" if upstream APIs are offline).

Set `PUBLIC_CONDITIONS_API_URL=http://localhost:5001/api/conditions` in `site/.env` for local development.

- [ ] **Step 5: Commit**

```bash
git add site/ app/routes/conditions.py
git commit -m "feat(site): LiveConditions component wired to /api/conditions"
```

---

## Phase G — Photo mosaic + lightbox

### Task 21: `<PhotoMosaic>` grid

**Files:**
- Create: `site/src/components/PhotoMosaic.astro`
- Create: `site/src/components/PhotoMosaic.client.ts`

- [ ] **Step 1: Write the mosaic component**

```astro
---
import { getCollection } from 'astro:content';

interface Props { limit?: number; homeOnly?: boolean; }
const { limit, homeOnly = false } = Astro.props;

const all = await getCollection('photos', (e) =>
  e.data.photo_consent_recorded === true && (!homeOnly || e.data.show_on_home),
);
all.sort((a, b) => a.data.order - b.data.order);
const photos = typeof limit === 'number' ? all.slice(0, limit) : all;
const sparse = photos.length < 12;

// Cycle through size classes for asymmetric tiling on desktop
const sizes = ['', 'md:col-span-2', '', 'md:row-span-2 md:col-span-2', '', '', 'md:col-span-2', ''];
---
<section class="bg-navy py-20">
  <div class="mx-auto max-w-7xl px-6">
    <div class={sparse
      ? 'grid grid-cols-2 md:grid-cols-3 gap-2 md:gap-3'
      : 'grid grid-cols-2 md:grid-cols-4 grid-flow-row-dense gap-2 md:gap-3'}
      data-photo-mosaic>
      {photos.map((p, i) => (
        <button
          type="button"
          class={'relative aspect-square overflow-hidden bg-paper-card focus:outline-mint focus:outline-2 ' + (sparse ? '' : sizes[i % sizes.length])}
          data-index={i}
          data-caption={p.data.caption ?? ''}
          data-alt={p.data.alt_text}
          data-tag={p.data.event_tag}
        >
          <img
            src={p.data.image}
            alt={p.data.alt_text}
            class="absolute inset-0 w-full h-full object-cover"
            loading="lazy"
            decoding="async"
          />
          {p.data.caption && (
            <div class="hidden md:flex absolute inset-0 bg-navy/70 text-paper opacity-0 hover:opacity-100 transition-opacity duration-150 p-4 items-end">
              <p class="text-sm leading-snug">{p.data.caption}</p>
            </div>
          )}
        </button>
      ))}
    </div>
  </div>
</section>

<script>
  import('@/components/PhotoMosaic.client').then((m) => m.init());
</script>
```

- [ ] **Step 2: Commit (lightbox comes in next task)**

```bash
git add site/src/components/PhotoMosaic.astro
git commit -m "feat(site): PhotoMosaic grid with asymmetric tiling + sparse fallback"
```

---

### Task 22: Lightbox

**Files:**
- Create: `site/src/components/Lightbox.astro`
- Create: `site/src/components/PhotoMosaic.client.ts`

- [ ] **Step 1: Write the lightbox shell**

`site/src/components/Lightbox.astro`:
```astro
---
---
<div
  data-lightbox
  class="fixed inset-0 z-50 hidden bg-ink/95 text-paper p-4 md:p-12 flex-col"
  role="dialog"
  aria-modal="true"
  aria-label="Photo viewer"
>
  <button class="self-end p-2 -m-2" aria-label="Close" data-lightbox-close>
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M6 6l12 12M6 18L18 6" />
    </svg>
  </button>
  <div class="flex-1 flex items-center justify-center min-h-0">
    <img data-lightbox-img class="max-h-full max-w-full object-contain" />
  </div>
  <div class="mt-4 max-w-3xl mx-auto text-center text-sm" data-lightbox-caption></div>
  <div class="flex justify-center gap-6 mt-6">
    <button class="px-5 py-2 border border-paper/30 rounded" data-lightbox-prev aria-label="Previous photo">←</button>
    <button class="px-5 py-2 border border-paper/30 rounded" data-lightbox-next aria-label="Next photo">→</button>
  </div>
</div>
```

- [ ] **Step 2: Write the client controller**

`site/src/components/PhotoMosaic.client.ts`:
```typescript
type Item = { index: number; src: string; alt: string; caption: string };

export function init() {
  const grid = document.querySelector('[data-photo-mosaic]');
  const box = document.querySelector('[data-lightbox]') as HTMLElement | null;
  if (!grid || !box) return;

  const buttons = grid.querySelectorAll<HTMLButtonElement>('button[data-index]');
  const items: Item[] = Array.from(buttons).map((b) => ({
    index: Number(b.dataset.index),
    src: (b.querySelector('img') as HTMLImageElement).src,
    alt: b.dataset.alt ?? '',
    caption: b.dataset.caption ?? '',
  }));

  let current = 0;
  const img = box.querySelector('[data-lightbox-img]') as HTMLImageElement;
  const cap = box.querySelector('[data-lightbox-caption]') as HTMLElement;
  const close = box.querySelector('[data-lightbox-close]') as HTMLElement;
  const prev = box.querySelector('[data-lightbox-prev]') as HTMLElement;
  const next = box.querySelector('[data-lightbox-next]') as HTMLElement;

  function render() {
    const it = items[current];
    img.src = it.src;
    img.alt = it.alt;
    cap.textContent = it.caption;
  }
  function open(i: number) {
    current = i;
    render();
    box!.classList.remove('hidden');
    box!.classList.add('flex');
  }
  function shut() {
    box!.classList.add('hidden');
    box!.classList.remove('flex');
  }
  function step(n: number) { current = (current + n + items.length) % items.length; render(); }

  buttons.forEach((b) => b.addEventListener('click', () => open(Number(b.dataset.index))));
  close.addEventListener('click', shut);
  prev.addEventListener('click', () => step(-1));
  next.addEventListener('click', () => step(1));
  document.addEventListener('keydown', (e) => {
    if (box!.classList.contains('hidden')) return;
    if (e.key === 'Escape') shut();
    if (e.key === 'ArrowLeft') step(-1);
    if (e.key === 'ArrowRight') step(1);
  });
}
```

- [ ] **Step 3: Mount the lightbox at the page level (BaseLayout)**

Update `BaseLayout.astro` to include `<Lightbox />` once at the bottom of `<body>`:
```astro
---
import Lightbox from '@/components/Lightbox.astro';
// existing imports
---
<!-- existing head -->
<body class={isHome ? 'bg-navy text-mint' : 'bg-paper text-ink'}>
  <slot />
  <Lightbox />
</body>
```

- [ ] **Step 4: Verify**

```bash
cd site && npm run dev &
sleep 3
# Hit home (which doesn't have the mosaic yet) and confirm build succeeds
curl -sf http://localhost:4321/ -o /dev/null && echo OK
kill %1
```

Expected: `OK`. (Actual photo verification happens when content is ported.)

- [ ] **Step 5: Commit**

```bash
git add site/
git commit -m "feat(site): PhotoMosaic lightbox with keyboard + arrow nav"
```

---

## Phase H — Other surface components

### Task 23: `<SeasonsGrid>`, `<CoachEntry>`, `<TripEntry>`, `<TripsTable>`, `<SponsorWall>` (batched — small components)

**Files:**
- Create: `site/src/components/SeasonsGrid.astro`
- Create: `site/src/components/CoachEntry.astro`
- Create: `site/src/components/TripEntry.astro`
- Create: `site/src/components/TripsTable.astro`
- Create: `site/src/components/SponsorWall.astro`

- [ ] **Step 1: Write `SeasonsGrid.astro`**

```astro
---
import { getCollection } from 'astro:content';
interface Props { variant?: 'navy' | 'paper'; }
const { variant = 'navy' } = Astro.props;
const seasons = await getCollection('practice_seasons');
seasons.sort((a, b) => a.id.localeCompare(b.id));
const dollar = (cents: number) => (cents / 100).toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 0 });
const surface = variant === 'navy' ? 'bg-navy text-paper border-mint/20' : 'bg-paper text-ink border-ink/15';
const accent = variant === 'navy' ? 'text-mint' : 'text-mint-deep';
---
<div class="grid md:grid-cols-2 gap-px {surface}">
  {seasons.map((s) => (
    <div class={'p-8 md:p-10 ' + surface}>
      <div class="flex items-baseline justify-between">
        <div>
          <div class={'text-xs tracking-widest uppercase ' + accent}>{s.data.date_range}</div>
          <h3 class="font-display text-2xl md:text-3xl mt-2">{s.id}</h3>
        </div>
        <div class={'text-xl font-bold ' + accent}>{dollar(s.data.fee_cents)}</div>
      </div>
      <p class="mt-4 text-sm md:text-base leading-relaxed opacity-90 max-w-prose">{s.data.summary}</p>
      <ul class="mt-4 text-sm space-y-1 opacity-80">
        {s.data.what_included.map((it) => <li>· {it}</li>)}
      </ul>
    </div>
  ))}
</div>
```

- [ ] **Step 2: Write `CoachEntry.astro`** (full-bleed editorial entry — not a card)

```astro
---
interface Props { name: string; role: string; photo: string; photoAlt: string; credentials?: string[]; }
const { name, role, photo, photoAlt, credentials = [] } = Astro.props;
---
<article class="border-b border-ink/10 last:border-b-0">
  <div class="relative aspect-[16/9] md:aspect-[21/9] overflow-hidden">
    <img src={photo} alt={photoAlt} class="absolute inset-0 w-full h-full object-cover" loading="lazy" />
  </div>
  <div class="mx-auto max-w-4xl px-6 py-10">
    <h2 class="font-display text-4xl md:text-6xl text-navy leading-[1.0]">{name}</h2>
    <p class="mt-3 text-mint-deep text-sm tracking-wider uppercase font-semibold">{role}</p>
    <div class="mt-6 prose prose-lg max-w-prose text-ink">
      <slot />
    </div>
    {credentials.length > 0 && (
      <ul class="mt-6 text-sm text-slate space-y-1">
        {credentials.map((c) => <li>· {c}</li>)}
      </ul>
    )}
  </div>
</article>
```

- [ ] **Step 3: Write `TripEntry.astro`**

```astro
---
interface Props {
  name: string; location: string; dates: string;
  cost_summary: string; signup_deadline?: string; capacity?: string;
  signup_url?: string; hero_photo?: string;
}
const { name, location, dates, cost_summary, signup_deadline, capacity, signup_url, hero_photo } = Astro.props;
---
<article class="bg-paper text-ink">
  {hero_photo && (
    <div class="relative aspect-[21/9] overflow-hidden">
      <img src={hero_photo} alt="" class="absolute inset-0 w-full h-full object-cover" loading="lazy" />
    </div>
  )}
  <div class="mx-auto max-w-3xl px-6 py-12">
    <h1 class="font-display text-4xl md:text-5xl text-navy">{name}</h1>
    <p class="mt-2 text-mint-deep">{location} · {dates}</p>
    <div class="mt-8 prose prose-lg max-w-prose">
      <slot />
    </div>
    <dl class="mt-8 grid sm:grid-cols-3 gap-4 text-sm">
      <div><dt class="text-slate uppercase tracking-wide">Cost</dt><dd>{cost_summary}</dd></div>
      {signup_deadline && <div><dt class="text-slate uppercase tracking-wide">Sign up by</dt><dd>{signup_deadline}</dd></div>}
      {capacity && <div><dt class="text-slate uppercase tracking-wide">Capacity</dt><dd>{capacity}</dd></div>}
    </dl>
    {signup_url && (
      <a href={signup_url} class="mt-8 inline-flex items-center px-6 py-3 bg-navy text-mint font-medium rounded-md">
        Sign up →
      </a>
    )}
  </div>
</article>
```

- [ ] **Step 4: Write `TripsTable.astro`**

```astro
---
import { getCollection } from 'astro:content';
const trips = await getCollection('trips');
trips.sort((a, b) => (a.data.dates ?? '').localeCompare(b.data.dates ?? ''));
---
{trips.length === 0 ? (
  <div class="mx-auto max-w-3xl px-6 py-16 text-center">
    <p class="text-slate">No trips currently scheduled. <a href="https://twincitiesskiclub.slack.com" class="text-mint-deep underline">Join the Slack</a> to hear about new trips first.</p>
  </div>
) : (
  <table class="w-full text-left text-sm">
    <thead class="text-slate uppercase tracking-wider text-xs">
      <tr><th class="py-3">Dates</th><th>Name</th><th>Location</th><th></th></tr>
    </thead>
    <tbody>
      {trips.map((t) => (
        <tr class="border-t border-ink/10">
          <td class="py-4">{t.data.dates}</td>
          <td><a href={'/trips/' + t.slug} class="text-navy font-medium">{t.slug}</a></td>
          <td>{t.data.location}</td>
          <td class="text-right"><a href={'/trips/' + t.slug} class="text-mint-deep">View →</a></td>
        </tr>
      ))}
    </tbody>
  </table>
)}
```

- [ ] **Step 5: Write `SponsorWall.astro`**

```astro
---
import { getCollection } from 'astro:content';
const sponsors = await getCollection('sponsors');
const tiers: { id: 'trailblazer' | 'supporter' | 'friend'; label: string }[] = [
  { id: 'trailblazer', label: 'Trailblazer' },
  { id: 'supporter', label: 'Supporter' },
  { id: 'friend', label: 'Friend' },
];
---
{tiers.map((tier) => {
  const list = sponsors.filter((s) => s.data.tier === tier.id);
  if (list.length === 0) return null;
  return (
    <section class="border-b border-ink/10 last:border-b-0 py-12">
      <h3 class="font-display text-2xl text-navy mb-6">{tier.label}</h3>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-8 items-center">
        {list.map((s) => (
          <a href={s.data.url ?? '#'} class="block">
            <img src={s.data.logo} alt={s.slug} class="max-h-16 w-auto" />
          </a>
        ))}
      </div>
    </section>
  );
})}
```

- [ ] **Step 6: Build to verify**

```bash
cd site && npm run check && npm run build
```

Expected: 0 errors. (Empty collections produce empty markup; that's fine.)

- [ ] **Step 7: Commit**

```bash
git add site/src/components/
git commit -m "feat(site): SeasonsGrid, CoachEntry, TripEntry, TripsTable, SponsorWall"
```

---

## Phase I — The Wax Room

### Task 24: `<WaxEntry>` and `<WaxRoomFeed>`

**Files:**
- Create: `site/src/components/WaxEntry.astro`
- Create: `site/src/components/WaxRoomFeed.astro`

- [ ] **Step 1: Write `WaxEntry.astro` (per-entry editorial layout)**

```astro
---
interface Props {
  date: Date;
  author_name: string;
  author_role: 'coach' | 'member' | 'board';
  title: string;
  lede: string;
  photo?: string;
  conditions_snapshot?: { location: string; temp_f: number; wax_used: string };
}
const { date, author_name, author_role, title, lede, photo, conditions_snapshot } = Astro.props;
const formatted = date.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });
---
<article class="mx-auto max-w-3xl px-6 py-12 md:py-16">
  <div class="text-sm text-mint-deep tracking-wider uppercase">{formatted}</div>
  <h1 class="font-display text-3xl md:text-5xl text-navy mt-3 leading-tight">{title}</h1>
  <div class="mt-3 text-slate text-sm">By {author_name} · <span class="capitalize">{author_role}</span></div>
  {conditions_snapshot && (
    <aside class="mt-6 border-l-0 bg-paper-card p-4 rounded-md text-sm flex gap-6">
      <div><div class="text-xs text-slate uppercase tracking-wide">Location</div><div>{conditions_snapshot.location}</div></div>
      <div><div class="text-xs text-slate uppercase tracking-wide">Temp</div><div>{conditions_snapshot.temp_f}°F</div></div>
      <div><div class="text-xs text-slate uppercase tracking-wide">Wax used</div><div>{conditions_snapshot.wax_used}</div></div>
    </aside>
  )}
  {photo && (
    <div class="my-8 aspect-video overflow-hidden">
      <img src={photo} alt="" class="w-full h-full object-cover" />
    </div>
  )}
  <p class="mt-6 text-lg leading-relaxed text-ink/90">{lede}</p>
  <div class="mt-6 prose prose-lg max-w-prose">
    <slot />
  </div>
</article>
```

- [ ] **Step 2: Write `WaxRoomFeed.astro` (home-page strip)**

```astro
---
import { getCollection } from 'astro:content';
const entries = (await getCollection('wax_entries'))
  .sort((a, b) => +b.data.date - +a.data.date)
  .slice(0, 3);
---
{entries.length > 0 && (
  <section class="bg-navy py-20">
    <div class="mx-auto max-w-7xl px-6">
      <div class="flex items-baseline justify-between mb-8">
        <h2 class="font-display text-3xl md:text-4xl text-mint">From the Wax Room</h2>
        <a href="/wax-room" class="text-mint-deep text-sm hover:text-mint">All entries →</a>
      </div>
      <div class="grid md:grid-cols-3 gap-px bg-mint/10">
        {entries.map((e) => (
          <a href={'/wax-room/' + e.slug} class="bg-navy p-6 hover:bg-navy-deep transition-colors">
            <div class="text-xs text-coral tracking-wider uppercase">
              {e.data.date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
            </div>
            <h3 class="font-display text-xl text-mint mt-2 leading-tight">{e.slug}</h3>
            <p class="mt-3 text-sm text-paper/80 line-clamp-3">{e.data.lede}</p>
          </a>
        ))}
      </div>
    </div>
  </section>
)}
```

- [ ] **Step 3: Commit**

```bash
git add site/src/components/WaxEntry.astro site/src/components/WaxRoomFeed.astro
git commit -m "feat(site): WaxEntry + WaxRoomFeed for the Wax Room publication"
```

---

### Task 25: Wax Room pages

**Files:**
- Create: `site/src/pages/wax-room/index.astro`
- Create: `site/src/pages/wax-room/[slug].astro`

- [ ] **Step 1: Write the index page**

```astro
---
import { getCollection } from 'astro:content';
import BaseLayout from '@/layouts/BaseLayout.astro';
import Nav from '@/components/Nav.astro';
import MobileNavPanel from '@/components/MobileNavPanel.astro';
import HeroInner from '@/components/HeroInner.astro';
import LiveConditions from '@/components/LiveConditions.astro';
import Footer from '@/components/Footer.astro';

const entries = (await getCollection('wax_entries')).sort((a, b) => +b.data.date - +a.data.date);
---
<BaseLayout title="The Wax Room — TCSC" variant="inner" description="Conditions reports, wax notes, race prep, and technique from TCSC coaches and members.">
  <Nav />
  <MobileNavPanel />
  <HeroInner headline="The Wax Room" subhead="Conditions, wax notes, race-day prep, technique. Field reports from TCSC coaches and members." />
  <main class="bg-paper">
    <div class="mx-auto max-w-3xl px-6 py-12">
      {entries.length === 0 ? (
        <p class="text-slate">No entries yet. Come back after the first snow.</p>
      ) : (
        <ol class="space-y-10">
          {entries.map((e) => (
            <li class="border-b border-ink/10 pb-10 last:border-b-0">
              <div class="text-sm text-mint-deep tracking-wider uppercase">
                {e.data.date.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
              </div>
              <h2 class="font-display text-2xl md:text-3xl text-navy mt-2"><a href={'/wax-room/' + e.slug}>{e.slug}</a></h2>
              <p class="mt-2 text-slate text-sm">{e.data.author_name} · <span class="capitalize">{e.data.author_role}</span></p>
              <p class="mt-4 text-ink/90">{e.data.lede}</p>
              <a href={'/wax-room/' + e.slug} class="mt-3 inline-block text-mint-deep text-sm">Read →</a>
            </li>
          ))}
        </ol>
      )}
    </div>
  </main>
  <LiveConditions variant="compact" />
  <Footer />
</BaseLayout>
```

- [ ] **Step 2: Write the per-entry page**

`site/src/pages/wax-room/[slug].astro`:
```astro
---
import { getCollection } from 'astro:content';
import BaseLayout from '@/layouts/BaseLayout.astro';
import Nav from '@/components/Nav.astro';
import MobileNavPanel from '@/components/MobileNavPanel.astro';
import WaxEntry from '@/components/WaxEntry.astro';
import LiveConditions from '@/components/LiveConditions.astro';
import Footer from '@/components/Footer.astro';

export async function getStaticPaths() {
  const entries = await getCollection('wax_entries');
  return entries.map((e) => ({ params: { slug: e.slug }, props: { entry: e } }));
}

const { entry } = Astro.props as { entry: any };
const { Content } = await entry.render();
---
<BaseLayout title={entry.slug + ' — The Wax Room — TCSC'} variant="inner" description={entry.data.lede}>
  <Nav />
  <MobileNavPanel />
  <main class="bg-paper">
    <WaxEntry
      date={entry.data.date}
      author_name={entry.data.author_name}
      author_role={entry.data.author_role}
      title={entry.slug}
      lede={entry.data.lede}
      photo={entry.data.photo}
      conditions_snapshot={entry.data.conditions_snapshot}
    >
      <Content />
    </WaxEntry>
  </main>
  <LiveConditions variant="compact" />
  <Footer />
</BaseLayout>
```

- [ ] **Step 3: Build to verify**

```bash
cd site && npm run check && npm run build
```

Expected: build succeeds even with no wax entries (the routes will render empty).

- [ ] **Step 4: Commit**

```bash
git add site/src/pages/wax-room/
git commit -m "feat(site): /wax-room index + per-entry routing"
```

---

## Phase J — Content port (Phase 1 of the spec)

### Task 26: Port the home singleton from migration

**Files:**
- Create: `site/src/content/pages/home/index.yaml`
- Create: `site/public/images/uploads/home-hero.jpg` (copied from `migration/images/`)

- [ ] **Step 1: Pick the best hero photo from `migration/images/`**

Visit `migration/inventory.md` — find the largest image associated with the home page. Pick one that fits the "Birkie wave start / post-practice gathering / breath-fog moment" brief. Copy:

```bash
cp migration/images/home-XX-XXXXXXXX.jpg site/public/images/uploads/home-hero.jpg
```

If no suitable hero photo exists in the Wix scrape, leave the hero photo blank for now; the typography fallback in `<HeroHome>` will render. Mark this as a follow-up.

- [ ] **Step 2: Write `home/index.yaml`**

```yaml
hero_headline: "Cross-country skiing, built around community."
hero_image: "/images/uploads/home-hero.jpg"
hero_image_alt: "TCSC members gathered at the start line of a winter race"
registration_state: "closed"
cta_open_label: "Register for the season →"
cta_open_url: "https://tcsc.ski/register"
cta_coming_soon_label: "Get on the list"
cta_coming_soon_url: "https://twincitiesskiclub.slack.com"
cta_closed_label: "Member area"
cta_closed_url: "https://twincitiesskiclub.slack.com"
mission_paragraph: >-
  Twin Cities Ski Club is a 501(c)(3) nonprofit dedicated to fostering a supportive
  community for young adults (ages 21 - 35) by promoting a healthy lifestyle through
  cross-country ski training sessions and educational programming.
```

(The paragraph is lifted verbatim from `migration/pages/home.txt` — verify and preserve.)

- [ ] **Step 3: Run dev server + verify hero renders**

```bash
cd site && npm run dev &
sleep 3
curl -sf http://localhost:4321/ | grep -q 'Cross-country skiing' && echo OK
kill %1
```

Expected: `OK`. The page renders, but without the full home composition (that arrives in Task 33).

- [ ] **Step 4: Commit**

```bash
git add site/src/content/pages/home/ site/public/images/uploads/home-hero.jpg
git commit -m "content(site): port home singleton from Wix scrape"
```

---

### Task 27: Port About, Community, Racing, Sponsors page, Contact

**Files:**
- Create: `site/src/content/pages/about/index.md`
- Create: `site/src/content/pages/community/index.md`
- Create: `site/src/content/pages/racing/index.md`
- Create: `site/src/content/pages/sponsors_page/index.md`
- Create: `site/src/content/pages/contact/index.yaml`

For each, the source content is in `migration/pages/<slug>.txt` and `migration/pages/<slug>.html`. Preserve the existing TCSC voice verbatim. Format as markdoc / yaml per the Keystatic schema.

- [ ] **Step 1: Write `about/index.md`** (markdoc with frontmatter)

```markdown
---
headline: "About Twin Cities Ski Club"
intro: "TCSC was founded in 2020 as a way to introduce young adult cross-country skiers in the Twin Cities to one another during a time when creating community was at its most difficult. Now in 2025, we have our biggest team yet, but we still hold true to the same values: we provide educational training opportunities and emphasize community in the cross country ski space at a cost meant to encourage all skiers to get involved. In short, we put skiers on snow, and even on podiums, surrounded by their friends and without breaking the bank."
---

## Who joins TCSC

### Young adults
TCSC is a group built for young adults in the Twin Cities area. For that reason, we currently limit new registration to skiers 21 - 35 years old.

### Ski experience
We only ask that our members have an intermediate grasp of cross-country skiing. We do not vet based on ability. We aren't able to provide beginner-level lessons at this time, but we can recommend the Three Rivers and Loppet Foundation lessons for those who are just starting their ski journey.

### Community driven
TCSC is committed to providing a crucial third space to young, active adults in the Twin Cities. For more about this, check out our [Community page](/community).

## Coaching

The Twin Cities Ski Club has three dedicated [coaches](/coaches) who work year-round to help our members improve their skiing skills. Our coaches plan, execute, and lead practices and training sessions to help skiers of all levels reach their full potential.
```

- [ ] **Step 2: Write `community/index.md`** (lift from `migration/pages/community.txt`)

```markdown
---
headline: "A welcoming community"
intro: "Twin Cities Ski Club is an inclusive community for any cross-country skier ages 21 - 35 years old who lives in the greater Minneapolis / St. Paul area — regardless of race, gender, sexual orientation, religion."
team_bonding_activities:
  - "Meet & greet with 3-time Olympic medalist Jessie Diggins"
  - "Pickleball"
  - "MNUFC soccer game"
  - "Canoe/Kayak/SUP on the Chain of Lakes"
  - "Halloween 10K run"
  - "Costume ski relays"
  - "St. Patrick's Day ski games"
  - "Minneapolis Pride Parade"
  - "Mini-golf and arcade games"
  - "Ice skating"
  - "Board game competitions"
  - "Backyard BBQs"
  - "Summer beach days"
  - "Local ice cream shop and brewery visits"
---

## What does it mean to be a part of TCSC?

TCSC believes in the importance of creating strong connections both within our team and with the larger ski community. To encourage this, we regularly host non-skiing and after-practice team events and make this a focal point of our weekly gatherings.

Our team is made up of skiers of all kinds. Many are Twin Cities transplants just looking to establish roots with skiers their own age. Others are retired high school or collegiate racers in search of a new team to motivate them to train and race at their highest levels. Even still, plenty are "Après ski" lovers who put up with intervals in exchange for post-practice brews.

We're proud to say our skiers want to be involved. TCSCers can be found in coaching positions from beginner to high school levels all over the metro, and are active volunteers in the Twin Cities and beyond.
```

- [ ] **Step 3: Write `racing/index.md`** (lift from `migration/pages/racing.txt`)

```markdown
---
headline: "Twin Cities Ski Club racers"
intro: "Twin Cities Ski Club supports members who choose to race by helping organize food, transportation, and lodging for a variety of regional weekend events (additional racing fees not included in seasonal fee). Members also have the option to purchase custom TCSC race suits to show off their team spirit."
races:
  - name: "Sisu Ski Fest"
    location: "Ironwood, MI"
    date: "Early January"
    notes: "Our largest team trip of the year. Race or cheer."
  - name: "Prebirkie & North End Classic"
    location: "Cable, WI"
    date: "Late January"
    notes: ""
  - name: "American Birkebeiner"
    location: "Hayward, WI"
    date: "Late February"
    notes: "80+ TCSC skiers in 2025, every wave from Elite to Wave 8."
  - name: "Great Bear Chase"
    location: "Calumet, MI"
    date: "March"
    notes: ""
  - name: "Tour de Finn"
    location: "Twin Cities metro"
    date: "Local series"
    notes: "Two TCSC teams participated this year."
---

## Races

We think ski races are one of the most fun parts of the winter. Racing with TCSC is totally voluntary — but highly encouraged. Members of all experience levels take to the snow at citizen ski races to show off their hard work during the season.

Like running a marathon, some skiers aim to complete the race while others aim to win. No matter which camp you're in, you can expect your TCSC teammates to line the trail and cheer you in to the finish.

## Racing not your thing?

Skiers who choose not to race are always encouraged to come along to the events to cheer for their teammates and help celebrate successes, both large and small. Our now famous **Techno Corner** cheering section is ever-present at most big Midwest races.
```

- [ ] **Step 4: Write `sponsors_page/index.md`**

```markdown
---
headline: "Meet our sponsors"
intro: "We're a 501(c)(3) nonprofit, and our sponsors make it possible for us to offer affordable training to young adult cross-country skiers in the Twin Cities. We're grateful to the organizations that support our community."
---
```

- [ ] **Step 5: Write `contact/index.yaml`**

```yaml
email: "contact@twincitiesskiclub.org"
mailing_address: "Minneapolis / St. Paul, Minnesota"
instagram_url: "https://www.instagram.com/twincitiesskiclub"
slack_invite_url: ""
```

- [ ] **Step 6: Build to verify**

```bash
cd site && npm run check && npm run build
```

Expected: 0 errors.

- [ ] **Step 7: Commit**

```bash
git add site/src/content/pages/
git commit -m "content(site): port About, Community, Racing, Sponsors page, Contact"
```

---

### Task 28: Port coaches, practice_seasons, trips, sponsors collections

**Files:**
- Create: `site/src/content/coaches/kj.md`, `greg.md`, `rebecca.md`
- Create: `site/src/content/practice_seasons/fall-winter.yaml`, `spring-summer.yaml`
- Create: `site/src/content/trips/sisu-ski-fest.md`
- Create: `site/src/content/sponsors/*.yaml` (one per sponsor — names TBD from scrape)
- Create: `site/public/photos/coaches-kj.jpg` etc. (copied from `migration/images/`)

- [ ] **Step 1: Copy coach photos to `site/public/photos/`**

```bash
mkdir -p site/public/photos
# Identify by visual inspection from migration/images/
cp migration/images/coaches-XX-XXXXXXXX.jpg site/public/photos/coach-kj.jpg
cp migration/images/coaches-YY-YYYYYYYY.jpg site/public/photos/coach-greg.jpg
cp migration/images/coaches-ZZ-ZZZZZZZZ.jpg site/public/photos/coach-rebecca.jpg
```

- [ ] **Step 2: Write `coaches/kj.md`**

```markdown
---
role: "Head coach"
photo: "/photos/coach-kj.jpg"
photo_alt: "Coach KJ at a TCSC practice"
credentials:
  - "Salomon · Atomic · Bjorn Dahlie · Finn Sisu · Borah Teamwear"
  - "Former Vakava Juniors coach"
  - "Central Cross Country (CXC) Board of Directors"
order: 1
---

Kevin "KJ" Johnson began coaching the Twin Cities Ski Club in 2021. He has an extensive background in the ski community, working for several companies including Salomon, Atomic, Bjorn Dahlie, Finn Sisu, and Borah Teamwear. He also spent many years coaching the Vakava Juniors ski team and has served on the Central Cross Country Skiing (CXC) Board of Directors.
```

- [ ] **Step 3: Write `coaches/greg.md`**

```markdown
---
role: "Sports scientist · coach"
photo: "/photos/coach-greg.jpg"
photo_alt: "Coach Greg"
credentials:
  - "PhD in Kinesiology and Exercise Science, University of Minnesota"
  - "Wilderness First Responder"
order: 2
---

Greg is a sports scientist with a PhD in Kinesiology and Exercise Science from the U of M. Greg bridges the gap between exercise science theories and real-world applications, all with a flair for sports performance optimization. He was recently supporting the specialized athletes at the MTB World Cup in Snowshoe. Greg is also a certified Wilderness First Responder.
```

- [ ] **Step 4: Write `coaches/rebecca.md`**

```markdown
---
role: "Coach"
photo: "/photos/coach-rebecca.jpg"
photo_alt: "Coach Rebecca"
credentials:
  - "Former high school ski coach"
  - "Finn Sisu's Vakava team coach"
  - "University of Minnesota ski team alumna"
order: 3
---

Rebecca brings a wealth of experience to the team, having previously coached high school students and Finn Sisu's Vakava team. Her own skiing journey began in middle school, flourished at the U of M, and led her to Finn Sisu where she's immersed herself in the sport.
```

- [ ] **Step 5: Write `practice_seasons/fall-winter.yaml`**

```yaml
date_range: "September – March"
fee_cents: 20500
summary: "Dryland training (pole bounding/hiking, running intervals, rollerskiing, biking) early in the season, transitioning to skate and classic ski workouts focused on technique and intervals once snow arrives."
what_included:
  - "Organized evening practices twice per week"
  - "Coaching from KJ, Greg, and Rebecca"
  - "Race-season trip coordination"
```

- [ ] **Step 6: Write `practice_seasons/spring-summer.yaml`**

```yaml
date_range: "May – August (with a 2-week 4th of July break)"
fee_cents: 10500
summary: "Dryland training: pole bounding/hiking, running intervals, rollerskiing, biking, and more. Plus weekly strength workouts at a local gym."
what_included:
  - "Organized evening practices twice per week"
  - "Weekly gym strength workouts"
  - "Coaching from KJ, Greg, and Rebecca"
```

- [ ] **Step 7: Write `trips/sisu-ski-fest.md`** (lifted from `migration/pages/sisu-information.txt`)

```markdown
---
location: "Ironwood, MI"
dates: "Jan 4 – 7"
cost_summary: "Cost of lodging and all meals beginning with dinner on the day of arrival through breakfast on the day of departure. Transportation costs, ski passes, and race registration are not included."
signup_deadline: "November 28"
capacity: "37 people"
refund_policy: "No refunds will be issued after sign-up. If you sign up and are unable to attend, we are happy to share the waitlist so you can find someone to fill your spot."
signup_url: "https://tcsc.ski/trips/sisu-ski-fest"
---

It's time to kick off race season with the SISU Ski Fest. This is our largest team trip of the year. We'll head up to Ironwood to make the most of the trails at ABR and Wolverine. Come along to race or cheer on your teammates.

## What to expect

After sign-up, you will be added to a Slack channel about the trip. The team will help coordinate carpools via this channel and provide other updates.
```

- [ ] **Step 8: Sponsor entries**

Read sponsor names + logos from `migration/pages/sponsors.html` (the Wix sponsor page). Copy logo images from `migration/images/` to `site/public/photos/` and write one YAML file per sponsor in `site/src/content/sponsors/`. Example structure (one file per sponsor):

```yaml
# site/src/content/sponsors/finn-sisu.yaml
logo: "/photos/sponsor-finn-sisu.png"
tier: "trailblazer"
url: "https://finnsisu.com"
```

If a sponsor has no logo extractable from the scrape, leave that sponsor for a follow-up; do not invent a logo.

- [ ] **Step 9: Build + verify**

```bash
cd site && npm run check && npm run build
```

Expected: 0 errors.

- [ ] **Step 10: Commit**

```bash
git add site/src/content/coaches/ site/src/content/practice_seasons/ site/src/content/trips/ site/src/content/sponsors/ site/public/photos/
git commit -m "content(site): port coaches, seasons, sisu trip, sponsors"
```

---

### Task 29: Port the photo wall

**Files:**
- Create: `site/src/content/photos/*.yaml` (one per photo curated for the mosaic)
- Create: `site/public/photos/community-*.jpg` (copied from `migration/images/`)

- [ ] **Step 1: Curate ~25–30 photos from `migration/images/` suitable for the community mosaic**

Browse the directory visually. Pick photos that show real club moments — Birkie wave starts, post-practice gatherings, costume relays, paddleboarding, group photos. Skip head-shots, logos, marketing graphics.

For each chosen photo, copy to `site/public/photos/` with a meaningful name:
```bash
cp migration/images/community-XX-XXXXXXXX.jpg site/public/photos/community-birkie-wave-2025.jpg
# ...
```

- [ ] **Step 2: For each photo, create a YAML entry**

```yaml
# site/src/content/photos/birkie-wave-2025.yaml
image: "/photos/community-birkie-wave-2025.jpg"
alt_text: "TCSC skiers at the start of the American Birkebeiner"
caption: "Wave 4 at the 2025 Birkie"
event_tag: "birkie"
member_names: []
order: 1
show_on_home: true
photo_consent_recorded: true
```

**Consent note:** `photo_consent_recorded: true` should only be set if you can confirm — talk with the board first, or set to `false` initially and update as confirmations come in. Photos with `false` will not render. This is a deliberate safety mechanism.

Aim for **15 photos with `show_on_home: true`** (the home mosaic shows these); the rest (10–15 more) sit on the community page only.

- [ ] **Step 3: Build + verify**

```bash
cd site && npm run check && npm run build
```

Expected: 0 errors. Photo count reported.

- [ ] **Step 4: Commit**

```bash
git add site/src/content/photos/ site/public/photos/
git commit -m "content(site): port ~25 photos for community mosaic"
```

---

## Phase K — Page composition

### Task 30: Home page (`/`) — final composition

**Files:**
- Modify: `site/src/pages/index.astro`

- [ ] **Step 1: Write the full home composition**

```astro
---
import { getEntry } from 'astro:content';
import BaseLayout from '@/layouts/BaseLayout.astro';
import Nav from '@/components/Nav.astro';
import MobileNavPanel from '@/components/MobileNavPanel.astro';
import LiveConditions from '@/components/LiveConditions.astro';
import HeroHome from '@/components/HeroHome.astro';
import MissionPanel from '@/components/MissionPanel.astro';
import SectionBand from '@/components/SectionBand.astro';
import SeasonsGrid from '@/components/SeasonsGrid.astro';
import PhotoMosaic from '@/components/PhotoMosaic.astro';
import WaxRoomFeed from '@/components/WaxRoomFeed.astro';
import CTAStrip from '@/components/CTAStrip.astro';
import Footer from '@/components/Footer.astro';

const home = await getEntry('home' as any, 'home' as any) as any;
const h = home.data;
---
<BaseLayout title="Twin Cities Ski Club" variant="home" description="A 501(c)(3) nonprofit cross-country ski community for adults 21–35 in Minneapolis / St. Paul.">
  <Nav />
  <MobileNavPanel />
  <LiveConditions variant="prominent" />
  <HeroHome
    headline={h.hero_headline}
    image={h.hero_image}
    imageAlt={h.hero_image_alt}
    state={h.registration_state}
    cta_open_label={h.cta_open_label} cta_open_url={h.cta_open_url}
    cta_coming_soon_label={h.cta_coming_soon_label} cta_coming_soon_url={h.cta_coming_soon_url}
    cta_closed_label={h.cta_closed_label} cta_closed_url={h.cta_closed_url}
  />
  <MissionPanel body={h.mission_paragraph} />
  <SectionBand variant="navy" number="01 — Practices" heading="Two seasons. Year-round group ski.">
    <SeasonsGrid variant="navy" />
  </SectionBand>
  <PhotoMosaic homeOnly={true} />
  <WaxRoomFeed />
  <CTAStrip
    heading="Ready to find your winter people?"
    subhead="Adults 21–35 · intermediate ability · all paces welcome."
    cta_label="Become a member →"
    cta_url={h.cta_open_url ?? '#'}
  />
  <Footer />
</BaseLayout>
```

- [ ] **Step 2: Build + open in browser**

```bash
cd site && npm run dev &
sleep 3
open http://localhost:4321/
```

Walk through the page top to bottom. Check:
- Hero photo renders or fallback typography shows
- Mission paragraph reads correctly
- Seasons grid shows two seasons with prices
- Photo mosaic shows the home-flagged photos
- Wax Room feed appears if entries exist (or hides cleanly if not)
- CTA strip + footer

- [ ] **Step 3: Commit**

```bash
git add site/src/pages/index.astro
git commit -m "feat(site): compose home page from primitives"
```

---

### Task 31: About, Community, Racing, Coaches, Sponsors, Contact, Trips pages

These are similar in shape: BaseLayout + Nav + HeroInner + page content + LiveConditions (compact) + Footer. Bundle into one task.

**Files:**
- Create: `site/src/pages/about.astro`
- Create: `site/src/pages/community.astro`
- Create: `site/src/pages/racing.astro`
- Create: `site/src/pages/coaches.astro`
- Create: `site/src/pages/sponsors.astro`
- Create: `site/src/pages/contact.astro`
- Create: `site/src/pages/trips/index.astro`
- Create: `site/src/pages/trips/[slug].astro`

- [ ] **Step 1: Write `about.astro`**

```astro
---
import { getEntry, render } from 'astro:content';
import BaseLayout from '@/layouts/BaseLayout.astro';
import Nav from '@/components/Nav.astro';
import MobileNavPanel from '@/components/MobileNavPanel.astro';
import HeroInner from '@/components/HeroInner.astro';
import SectionBand from '@/components/SectionBand.astro';
import SeasonsGrid from '@/components/SeasonsGrid.astro';
import LiveConditions from '@/components/LiveConditions.astro';
import Footer from '@/components/Footer.astro';

const about = await getEntry('about' as any, 'about' as any) as any;
const { Content } = await render(about);
---
<BaseLayout title="About — TCSC" variant="inner" description={about.data.intro}>
  <Nav />
  <MobileNavPanel />
  <HeroInner headline={about.data.headline} subhead={about.data.intro} />
  <main class="bg-paper">
    <div class="mx-auto max-w-3xl px-6 py-12 prose prose-lg">
      <Content />
    </div>
    <SectionBand variant="paper" heading="Two seasons.">
      <SeasonsGrid variant="paper" />
    </SectionBand>
  </main>
  <LiveConditions variant="compact" />
  <Footer />
</BaseLayout>
```

- [ ] **Step 2: Write `community.astro`**

```astro
---
import { getEntry, render } from 'astro:content';
import BaseLayout from '@/layouts/BaseLayout.astro';
import Nav from '@/components/Nav.astro';
import MobileNavPanel from '@/components/MobileNavPanel.astro';
import HeroInner from '@/components/HeroInner.astro';
import PhotoMosaic from '@/components/PhotoMosaic.astro';
import LiveConditions from '@/components/LiveConditions.astro';
import Footer from '@/components/Footer.astro';

const community = await getEntry('community' as any, 'community' as any) as any;
const { Content } = await render(community);
const acts: string[] = community.data.team_bonding_activities ?? [];
---
<BaseLayout title="Community — TCSC" variant="inner" description={community.data.intro}>
  <Nav />
  <MobileNavPanel />
  <HeroInner headline={community.data.headline} subhead={community.data.intro} />
  <main class="bg-paper">
    <div class="mx-auto max-w-3xl px-6 py-12 prose prose-lg">
      <Content />
    </div>
    <PhotoMosaic />
    <section class="bg-paper py-16">
      <div class="mx-auto max-w-3xl px-6">
        <h2 class="font-display text-3xl text-navy">Team-bonding activities</h2>
        <div class="mt-6 flex flex-wrap gap-2">
          {acts.map((a: string) => (
            <span class="inline-block bg-paper-card text-ink rounded-full px-4 py-2 text-sm">{a}</span>
          ))}
        </div>
      </div>
    </section>
  </main>
  <LiveConditions variant="compact" />
  <Footer />
</BaseLayout>
```

- [ ] **Step 3: Write `racing.astro`**

```astro
---
import { getEntry, render } from 'astro:content';
import BaseLayout from '@/layouts/BaseLayout.astro';
import Nav from '@/components/Nav.astro';
import MobileNavPanel from '@/components/MobileNavPanel.astro';
import HeroInner from '@/components/HeroInner.astro';
import LiveConditions from '@/components/LiveConditions.astro';
import Footer from '@/components/Footer.astro';

const racing = await getEntry('racing' as any, 'racing' as any) as any;
const { Content } = await render(racing);
const races: any[] = racing.data.races ?? [];
---
<BaseLayout title="Racing — TCSC" variant="inner" description={racing.data.intro}>
  <Nav />
  <MobileNavPanel />
  <HeroInner headline={racing.data.headline} subhead={racing.data.intro} />
  <main class="bg-paper">
    <div class="mx-auto max-w-3xl px-6 py-12 prose prose-lg">
      <Content />
    </div>
    <section class="bg-paper py-12 border-t border-ink/10">
      <div class="mx-auto max-w-3xl px-6">
        <h2 class="font-display text-3xl text-navy">Races</h2>
        <ul class="mt-6 divide-y divide-ink/10">
          {races.map((r) => (
            <li class="py-4 grid grid-cols-3 gap-4 items-baseline">
              <div class="text-mint-deep text-sm">{r.date}</div>
              <div class="font-semibold">{r.name}</div>
              <div class="text-slate text-sm">{r.location}</div>
              {r.notes && <div class="col-span-3 text-sm text-ink/70 -mt-2">{r.notes}</div>}
            </li>
          ))}
        </ul>
      </div>
    </section>
  </main>
  <LiveConditions variant="compact" />
  <Footer />
</BaseLayout>
```

- [ ] **Step 4: Write `coaches.astro`**

```astro
---
import { getCollection, render } from 'astro:content';
import BaseLayout from '@/layouts/BaseLayout.astro';
import Nav from '@/components/Nav.astro';
import MobileNavPanel from '@/components/MobileNavPanel.astro';
import HeroInner from '@/components/HeroInner.astro';
import CoachEntry from '@/components/CoachEntry.astro';
import LiveConditions from '@/components/LiveConditions.astro';
import Footer from '@/components/Footer.astro';

const coaches = (await getCollection('coaches')).sort((a, b) => a.data.order - b.data.order);
const rendered = await Promise.all(coaches.map((c) => render(c)));
---
<BaseLayout title="Coaches — TCSC" variant="inner">
  <Nav />
  <MobileNavPanel />
  <HeroInner headline="Our coaches" subhead="An exceptional team bringing joy, excitement, and knowledge to every practice." />
  <main class="bg-paper">
    {coaches.map((c, i) => {
      const { Content } = rendered[i];
      return (
        <CoachEntry
          name={c.id.charAt(0).toUpperCase() + c.id.slice(1)}
          role={c.data.role}
          photo={c.data.photo}
          photoAlt={c.data.photo_alt}
          credentials={c.data.credentials}
        >
          <Content />
        </CoachEntry>
      );
    })}
  </main>
  <LiveConditions variant="compact" />
  <Footer />
</BaseLayout>
```

- [ ] **Step 5: Write `sponsors.astro`**

```astro
---
import { getEntry, render } from 'astro:content';
import BaseLayout from '@/layouts/BaseLayout.astro';
import Nav from '@/components/Nav.astro';
import MobileNavPanel from '@/components/MobileNavPanel.astro';
import HeroInner from '@/components/HeroInner.astro';
import SponsorWall from '@/components/SponsorWall.astro';
import LiveConditions from '@/components/LiveConditions.astro';
import Footer from '@/components/Footer.astro';

const page = await getEntry('sponsors_page' as any, 'sponsors_page' as any) as any;
const { Content } = await render(page);
---
<BaseLayout title="Sponsors — TCSC" variant="inner" description={page.data.intro}>
  <Nav />
  <MobileNavPanel />
  <HeroInner headline={page.data.headline} subhead={page.data.intro} />
  <main class="bg-paper">
    <div class="mx-auto max-w-5xl px-6 py-12">
      <SponsorWall />
    </div>
  </main>
  <LiveConditions variant="compact" />
  <Footer />
</BaseLayout>
```

- [ ] **Step 6: Write `contact.astro`**

```astro
---
import { getEntry } from 'astro:content';
import BaseLayout from '@/layouts/BaseLayout.astro';
import Nav from '@/components/Nav.astro';
import MobileNavPanel from '@/components/MobileNavPanel.astro';
import HeroInner from '@/components/HeroInner.astro';
import LiveConditions from '@/components/LiveConditions.astro';
import Footer from '@/components/Footer.astro';
const c = (await getEntry('contact' as any, 'contact' as any) as any).data;
---
<BaseLayout title="Contact — TCSC" variant="inner">
  <Nav />
  <MobileNavPanel />
  <HeroInner headline="Contact" />
  <main class="bg-paper">
    <div class="mx-auto max-w-3xl px-6 py-16 prose prose-lg">
      <p><a href={'mailto:' + c.email}>{c.email}</a></p>
      <p>{c.mailing_address}</p>
      {c.instagram_url && <p><a href={c.instagram_url}>Instagram</a></p>}
    </div>
  </main>
  <LiveConditions variant="compact" />
  <Footer />
</BaseLayout>
```

- [ ] **Step 7: Write `trips/index.astro` and `trips/[slug].astro`**

`site/src/pages/trips/index.astro`:
```astro
---
import BaseLayout from '@/layouts/BaseLayout.astro';
import Nav from '@/components/Nav.astro';
import MobileNavPanel from '@/components/MobileNavPanel.astro';
import HeroInner from '@/components/HeroInner.astro';
import TripsTable from '@/components/TripsTable.astro';
import LiveConditions from '@/components/LiveConditions.astro';
import Footer from '@/components/Footer.astro';
---
<BaseLayout title="Trips — TCSC" variant="inner">
  <Nav />
  <MobileNavPanel />
  <HeroInner headline="Trips" subhead="Race weekends, ski festivals, and team adventures organized by TCSC." />
  <main class="bg-paper py-12">
    <div class="mx-auto max-w-3xl px-6">
      <TripsTable />
    </div>
  </main>
  <LiveConditions variant="compact" />
  <Footer />
</BaseLayout>
```

`site/src/pages/trips/[slug].astro`:
```astro
---
import { getCollection, render } from 'astro:content';
import BaseLayout from '@/layouts/BaseLayout.astro';
import Nav from '@/components/Nav.astro';
import MobileNavPanel from '@/components/MobileNavPanel.astro';
import TripEntry from '@/components/TripEntry.astro';
import LiveConditions from '@/components/LiveConditions.astro';
import Footer from '@/components/Footer.astro';

export async function getStaticPaths() {
  const trips = await getCollection('trips');
  return trips.map((t) => ({ params: { slug: t.slug }, props: { trip: t } }));
}
const { trip } = Astro.props as any;
const { Content } = await render(trip);
---
<BaseLayout title={trip.slug + ' — TCSC'} variant="inner" description={trip.data.cost_summary}>
  <Nav />
  <MobileNavPanel />
  <main class="bg-paper">
    <TripEntry
      name={trip.slug}
      location={trip.data.location}
      dates={trip.data.dates}
      cost_summary={trip.data.cost_summary}
      signup_deadline={trip.data.signup_deadline}
      capacity={trip.data.capacity}
      signup_url={trip.data.signup_url}
      hero_photo={trip.data.hero_photo}
    >
      <Content />
    </TripEntry>
  </main>
  <LiveConditions variant="compact" />
  <Footer />
</BaseLayout>
```

- [ ] **Step 8: Build + walk through every page in dev**

```bash
cd site && npm run check && npm run build && npm run dev &
sleep 4
for path in / /about /community /racing /coaches /sponsors /contact /trips /trips/sisu-ski-fest /wax-room; do
  echo "=== $path ==="
  curl -sf -o /dev/null -w '%{http_code}\n' http://localhost:4321$path
done
kill %1
```

Expected: all 200s.

- [ ] **Step 9: Commit**

```bash
git add site/src/pages/
git commit -m "feat(site): compose About, Community, Racing, Coaches, Sponsors, Contact, Trips pages"
```

---

## Phase L — SEO + structured data + redirects

### Task 32: JSON-LD SportsOrganization

**Files:**
- Modify: `site/src/layouts/BaseLayout.astro`

- [ ] **Step 1: Add a single JSON-LD block to the layout's head**

In `BaseLayout.astro`, inside `<head>` after `<FontPreload />`:

```astro
<script type="application/ld+json" set:html={JSON.stringify({
  '@context': 'https://schema.org',
  '@type': 'SportsOrganization',
  name: 'Twin Cities Ski Club',
  alternateName: 'TCSC',
  url: 'https://twincitiesskiclub.org',
  email: 'contact@twincitiesskiclub.org',
  sport: 'Cross-country skiing',
  address: {
    '@type': 'PostalAddress',
    addressLocality: 'Minneapolis',
    addressRegion: 'MN',
    addressCountry: 'US',
  },
  sameAs: [
    'https://www.instagram.com/twincitiesskiclub',
  ],
})} />
```

- [ ] **Step 2: Build + view source to confirm**

```bash
cd site && npm run build && npx serve dist &
sleep 2
curl -sf http://localhost:3000/ | grep -q 'SportsOrganization' && echo OK
kill %1
```

Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add site/src/layouts/BaseLayout.astro
git commit -m "feat(site): JSON-LD SportsOrganization for SEO"
```

---

### Task 33: Sitemap + robots.txt

**Files:**
- Modify: `site/astro.config.mjs`
- Modify: `site/package.json` (deps)
- Create: `site/public/robots.txt`

- [ ] **Step 1: Install the Astro sitemap integration**

```bash
cd site && npm install --save @astrojs/sitemap
```

- [ ] **Step 2: Add to `astro.config.mjs`**

```js
import sitemap from '@astrojs/sitemap';
// ...
integrations: [tailwind({ applyBaseStyles: false }), react(), keystatic(), sitemap()],
```

- [ ] **Step 3: Write `robots.txt`**

```
User-agent: *
Allow: /

Sitemap: https://twincitiesskiclub.org/sitemap-index.xml
```

- [ ] **Step 4: Build + verify**

```bash
cd site && npm run build
ls dist/sitemap-*.xml
```

Expected: a sitemap-index.xml + sitemap-0.xml exist.

- [ ] **Step 5: Commit**

```bash
git add site/
git commit -m "feat(site): sitemap.xml + robots.txt"
```

---

### Task 34: Redirects from old Wix form URLs

**Files:**
- Create: `site/public/_redirects` (Render/Netlify-style)

- [ ] **Step 1: Write `_redirects`**

```
/register             https://tcsc.ski/register         302
/copy-of-register     https://tcsc.ski/register         302
/sisu-signup          https://tcsc.ski/trips/sisu-ski-fest  302
/trip-sign-up         https://tcsc.ski/trips            302
/trip-information     /trips                            302
/trip-confirmation    /                                 302
/confirmation         /                                 302
```

- [ ] **Step 2: Commit**

```bash
git add site/public/_redirects
git commit -m "feat(site): redirects from old Wix form URLs to Flask app"
```

(Render Static reads `_redirects` natively. Verify in Render dashboard during deploy.)

---

## Phase M — Render Static deploy

### Task 35: Render service config

**Files:**
- Create: `render.yaml` (or add a manifest at the repo root if the project doesn't yet have one — verify before creating)

- [ ] **Step 1: Check if `render.yaml` exists at repo root**

```bash
ls render.yaml 2>/dev/null && echo EXISTS || echo MISSING
```

If MISSING, create it. If EXISTS, modify it to add the new static service alongside whatever's already defined.

- [ ] **Step 2: Add the static service**

Add to `render.yaml`:

```yaml
services:
  - type: web
    name: tcsc-marketing
    runtime: static
    branch: feat/marketing-site   # change to main after merge
    buildCommand: cd site && npm install && npm run build
    staticPublishPath: ./site/dist
    routes:
      - type: rewrite
        source: /*
        destination: /index.html
    envVars:
      - key: PUBLIC_CONDITIONS_API_URL
        value: https://tcsc.ski/api/conditions
```

- [ ] **Step 3: Push branch + create Render service manually if Render Blueprints aren't auto-syncing**

```bash
git push -u origin feat/marketing-site
```

In the Render dashboard: New → Static Site → Connect this repo → branch `feat/marketing-site` → build command and publish dir as above → set env var `PUBLIC_CONDITIONS_API_URL=https://tcsc.ski/api/conditions`.

Wait for first deploy. Get the staging URL (e.g., `tcsc-marketing.onrender.com`).

- [ ] **Step 4: Smoke-test the staging URL**

```bash
STAGING=https://tcsc-marketing.onrender.com   # replace
for p in / /about /community /racing /coaches /sponsors /contact /wax-room /trips/sisu-ski-fest; do
  curl -sfI $STAGING$p | head -1
done
```

Expected: all `200 OK`.

- [ ] **Step 5: Commit `render.yaml`**

```bash
git add render.yaml
git commit -m "deploy(site): Render Static config for tcsc-marketing service"
git push
```

---

## Phase N — Verification + cutover

### Task 36: Inventory verification script

**Files:**
- Create: `scripts/wix_scrape/verify.py`
- Create: `tests/wix_scrape/test_verify.py`

- [ ] **Step 1: Write the verification script**

`scripts/wix_scrape/verify.py`:
```python
"""Compare migration/inventory.md against site/ content to catch missing material."""
from __future__ import annotations
import sys
from pathlib import Path
import csv


def check_images_ported(images_csv: Path, site_root: Path) -> list[str]:
    issues: list[str] = []
    with images_csv.open() as fh:
        for row in csv.DictReader(fh):
            local = row['local_filename']
            # Look in site/public/{photos,images/uploads} for the file (possibly renamed)
            # Accept any match: photos/community-*.jpg etc.
            candidates = list((site_root / 'public').glob(f'**/*{Path(local).stem[-8:]}*'))
            if not candidates:
                issues.append(f'image not found in site/public/: {local}')
    return issues


def check_pages_ported(pages_dir: Path, site_content_pages: Path) -> list[str]:
    issues: list[str] = []
    for txt in pages_dir.glob('*.txt'):
        slug = txt.stem
        if slug in {'register', 'copy-of-register', 'sisu-signup', 'trip-sign-up',
                    'trip-confirmation', 'confirmation', 'trip-information'}:
            continue  # intentional redirects
        candidates = list(site_content_pages.glob(f'**/*{slug}*')) + \
                     list(site_content_pages.parent.glob(f'**/*{slug}*'))
        if not candidates:
            issues.append(f'no Keystatic content found for Wix page: {slug}')
    return issues


def main() -> int:
    root = Path('.')
    migration = root / 'migration'
    issues = []
    issues += check_images_ported(migration / 'images.csv', root / 'site')
    issues += check_pages_ported(migration / 'pages', root / 'site' / 'src' / 'content' / 'pages')
    if issues:
        print(f'❌ {len(issues)} issues:')
        for i in issues:
            print(f'  - {i}')
        return 1
    print('✅ all migration items accounted for')
    return 0


if __name__ == '__main__':
    sys.exit(main())
```

- [ ] **Step 2: Run it**

```bash
python -m scripts.wix_scrape.verify
```

Expected: ideally `✅ all migration items accounted for`. If issues, triage: some images are decorative chrome and can be intentionally skipped (note in a follow-up); pages should all be accounted for.

- [ ] **Step 3: Commit the verifier**

```bash
git add scripts/wix_scrape/verify.py
git commit -m "feat(scrape): verifier comparing migration to ported content"
```

---

### Task 37: Manual QA pass on the staging URL

This is a checklist task, not a code task.

- [ ] **Step 1: Walk through every page on `STAGING` URL**

For each of `/`, `/about`, `/community`, `/racing`, `/coaches`, `/sponsors`, `/contact`, `/wax-room`, `/trips`, `/trips/sisu-ski-fest`:
- Does the page render with content?
- Does the Live Conditions strip load real data?
- Do photos render (lazy-loaded; lightbox opens)?
- Mobile: hamburger opens panel; CTAs reachable?
- Reduced motion (set in OS): hero photo doesn't fade?

- [ ] **Step 2: Lighthouse audit**

In Chrome DevTools, run Lighthouse on `/`. Targets:
- Performance: ≥ 95
- Accessibility: ≥ 95
- Best Practices: ≥ 95
- SEO: ≥ 100

If any fall below target, file follow-up tasks. Don't block cutover on edge accessibility issues if the core is solid; do block on broken contrast or missing alt text.

- [ ] **Step 3: Share staging URL with the user for sign-off**

Wait for explicit user sign-off before moving to Task 38.

---

### Task 38: Open PR-1 for the build (no DNS cutover yet)

- [ ] **Step 1: Push final branch state**

```bash
git push
```

- [ ] **Step 2: Open the PR via `gh`**

```bash
gh pr create --title "feat: TCSC marketing site (Astro + Keystatic)" --body "$(cat <<'EOF'
## Summary
- New Astro static site under `/site` replacing the Wix marketing site (`twincitiesskiclub.org`).
- Drenched-navy home page with real photographic hero; paper-default inner pages.
- Signature device: `<LiveConditions>` strip showing current temp + wax recommendation at four Twin Cities ski areas, sourced from new Flask `/api/conditions` endpoint.
- New `/wax-room` editorial publication section.
- Keystatic for content; schema becomes the contract for the future Slack editing agent.
- Wix scrape script preserves all source content under `migration/`.
- Deployed to Render Static as `tcsc-marketing`. **DNS not yet cut over** — that ships in PR-2 after a clean staging period.

## Test plan
- [ ] Walk through every page on staging URL
- [ ] Verify Live Conditions shows real temp/wax data
- [ ] Verify photo mosaic + lightbox
- [ ] Mobile nav opens/closes
- [ ] Reduced-motion respects hero photo
- [ ] Lighthouse: perf/a11y/SEO all ≥ 95

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR URL returned.

---

### Task 39: DNS cutover (PR-2)

**Files:**
- Modify: `render.yaml` (custom domain entry)

This task happens ONLY after PR-1 has been merged, staging has been clean for ≥ 24h, and the user has approved.

- [ ] **Step 1: Confirm the staging URL is rock-solid**

```bash
STAGING=https://tcsc-marketing.onrender.com
for _ in $(seq 1 20); do curl -sf -o /dev/null -w '%{http_code} ' $STAGING/; done
echo
```

Expected: 20× `200`.

- [ ] **Step 2: Add the custom domain to the Render service**

In the Render dashboard → tcsc-marketing → Custom Domains → Add `twincitiesskiclub.org` and `www.twincitiesskiclub.org`. Render shows DNS records required.

- [ ] **Step 3: Update DNS at the registrar**

Wherever the apex DNS is hosted (Cloudflare, Google Domains, etc.):
- Replace Wix's `A` records on `twincitiesskiclub.org` with Render's instructions.
- Set `www.twincitiesskiclub.org` to redirect to the apex.

Use Cloudflare's "DNS only" mode (gray cloud) for initial cutover — don't proxy through Cloudflare until the Render-issued cert is confirmed.

- [ ] **Step 4: Wait + verify**

```bash
for _ in $(seq 1 30); do
  resolved=$(dig +short twincitiesskiclub.org @1.1.1.1 | head -1)
  echo "twincitiesskiclub.org → $resolved"
  if [ -n "$resolved" ] && [ "$resolved" != "0.0.0.0" ]; then break; fi
  sleep 60
done
```

Confirm in browser: `https://twincitiesskiclub.org/` loads the new site with a valid cert.

- [ ] **Step 5: Confirm redirects from old form URLs work**

```bash
for p in /register /copy-of-register /sisu-signup /trip-sign-up; do
  curl -sI https://twincitiesskiclub.org$p | head -3
done
```

Expected: 302 to `https://tcsc.ski/...`.

- [ ] **Step 6: Wait 7 days. Then cancel the Wix subscription.**

Do not cancel Wix until 7 days of clean Render traffic logs confirm everything is working. Document the cancel-after date in the PR-2 description.

- [ ] **Step 7: Commit + ship PR-2**

```bash
git checkout -b feat/marketing-site-cutover
# Update render.yaml customDomains and any envVars for production
git add render.yaml
git commit -m "deploy(site): cut over twincitiesskiclub.org to Render Static"
git push -u origin feat/marketing-site-cutover
gh pr create --title "deploy: cut twincitiesskiclub.org to Render" --body "Cutover only. Wix subscription stays active for 7 days for rollback."
```

---

## Self-Review

**1. Spec coverage:** Every section of the spec maps to tasks:
- Stack / repo architecture → Tasks 2–6
- Visual system (DESIGN.md) → Tasks 3, 4, 17–25, 30, 31 (components built per DESIGN.md)
- Live Conditions signature device → Tasks 12–14, 20
- Wax Room → Tasks 24, 25, 29 (port)
- Content model (Keystatic) → Tasks 15, 16
- Editing workflow → covered by Keystatic local mode (Tasks 6, 15); Slack agent is out of scope as the spec says
- Pages & sitemap → Tasks 30, 31
- Migration plan (scrape → port → verify → cutover) → Tasks 7–11, 26–29, 36–39
- UX edges (mobile nav, registration_state, empty states, SEO) → Tasks 17, 18, 32, 33; empty states baked into the relevant components
- Flask `/api/conditions` dependency → Tasks 12–14
- Redirects → Task 34

**2. Placeholder scan:** No "TBD", no "implement later", no "similar to Task N" without code. All code blocks contain runnable content. Two known soft spots flagged in-place:
- Task 4 Step 1: PolySans font files must be downloaded manually from Pangram Pangram. Acknowledged with a fallback (Inter Variable) and a follow-up swap.
- Task 28 Step 8: Sponsor logos require human curation from the scrape because Wix logo URLs aren't predictably named. Documented inline.

**3. Type consistency:** Component prop names and content schema field names match between tasks. The Flask endpoint response shape in Task 13 matches what `<LiveConditions>` consumes in Task 20.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-16-marketing-site-transition.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Good fit for this plan because tasks are small and the subagent gets a clean context per task.

**2. Inline Execution** — Execute tasks in this session using `executing-plans`, batch execution with checkpoints for review.

Which approach?
