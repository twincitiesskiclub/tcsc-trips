"""Fetch a Wix page with Playwright, expand widgets, return rendered HTML."""
from __future__ import annotations

import re

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# Common Wix expander selectors — clicked before HTML capture.
_EXPAND_SELECTORS = [
    '[data-testid="accordion-header"]',
    'button[aria-expanded="false"]',
    '.accordion-item:not(.is-open) .accordion-header',
]

_BG_IMAGE_RE = re.compile(r'background-image\s*:\s*url\(\s*[\'"]?(https?://[^\'")]+)[\'"]?\s*\)', re.I)


def _settle(page, timeout_ms: int = 5000) -> None:
    """Wait for network idle, tolerating Wix's persistent connections."""
    try:
        page.wait_for_load_state('networkidle', timeout=timeout_ms)
    except Exception:  # noqa: BLE001 - Wix keeps sockets open; idle may never fire
        pass


def fetch_rendered_html(url: str, timeout_ms: int = 30000) -> str:
    """Open the URL in headless Chromium, expand accordions, scroll to force lazy loads, return final DOM."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        # Wix pages hold long-lived connections, so a strict 'networkidle'
        # goto can time out; 'load' + a tolerant idle wait is reliable.
        page.goto(url, wait_until='load', timeout=timeout_ms)
        _settle(page)
        # Scroll through the full page so Wix lazy-loads every image into the DOM.
        page.evaluate('''async () => {
            for (let y = 0; y < document.body.scrollHeight; y += 600) {
                window.scrollTo(0, y);
                await new Promise(r => setTimeout(r, 150));
            }
            window.scrollTo(0, 0);
        }''')
        for selector in _EXPAND_SELECTORS:
            for handle in page.locator(selector).all():
                try:
                    handle.click(timeout=1000)
                except Exception:  # noqa: BLE001
                    continue
        _settle(page)
        html = page.content()
        browser.close()
        return html


def extract_visible_text(html: str) -> str:
    """Return whitespace-collapsed visible text, one line per text fragment."""
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script', 'style', 'noscript']):
        tag.decompose()
    lines = []
    for raw in soup.get_text(separator='\n').splitlines():
        line = ' '.join(raw.split())
        if line:
            lines.append(line)
    return '\n'.join(lines)


def _largest_srcset_candidate(srcset: str) -> str | None:
    """Pick the URL with the largest width (Nw) or density (Nx) descriptor.

    Candidates are split on ',' followed by whitespace — NOT on bare ',' —
    because Wix transform paths contain commas (e.g. ``w_305,h_229,al_c``).
    """
    best_url, best_score = None, -1.0
    for candidate in re.split(r',\s+', srcset.strip()):
        parts = candidate.strip().split()
        if not parts:
            continue
        url = parts[0]
        score = 1.0
        if len(parts) > 1:
            desc = parts[1].lower()
            try:
                if desc.endswith('w'):
                    score = float(desc[:-1]) * 1000  # widths dominate densities
                elif desc.endswith('x'):
                    score = float(desc[:-1])
            except ValueError:
                pass
        if score > best_score:
            best_url, best_score = url, score
    return best_url


def _is_http(url: str) -> bool:
    return url.startswith('http://') or url.startswith('https://')


def extract_image_urls(html: str) -> list[str]:
    """Harvest every image URL Wix puts in the DOM: img src/data-src, srcset, CSS backgrounds, og:image."""
    soup = BeautifulSoup(html, 'html.parser')
    urls: set[str] = set()

    for img in soup.find_all('img'):
        for attr in ('src', 'data-src'):
            value = img.get(attr)
            if value and _is_http(value):
                urls.add(value)
    for tag in soup.find_all(['img', 'source']):
        srcset = tag.get('srcset')
        if srcset:
            best = _largest_srcset_candidate(srcset)
            if best and _is_http(best):
                urls.add(best)

    for match in _BG_IMAGE_RE.finditer(html):
        urls.add(match.group(1))

    for meta in soup.find_all('meta', attrs={'property': 'og:image'}):
        content = meta.get('content')
        if content and _is_http(content):
            urls.add(content)

    return sorted(urls)


def extract_image_alts(html: str) -> dict[str, str]:
    """Map each <img> URL to its alt text (empty string when missing)."""
    soup = BeautifulSoup(html, 'html.parser')
    alts: dict[str, str] = {}
    for img in soup.find_all('img'):
        alt = (img.get('alt') or '').strip()
        for attr in ('src', 'data-src'):
            value = img.get(attr)
            if value and _is_http(value) and (value not in alts or alt):
                alts[value] = alt
        srcset = img.get('srcset')
        if srcset:
            best = _largest_srcset_candidate(srcset)
            if best and _is_http(best) and (best not in alts or alt):
                alts[best] = alt
    return alts
