"""Orchestrate the full Wix scrape: pages, text, full-resolution images, inventory.

Run from the repo root:  python -m scripts.wix_scrape
Output lands in migration/: pages/{slug}.{html,txt,json}, images/, images.csv,
inventory.md.
"""
from __future__ import annotations

import json
import os
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from scripts.wix_scrape.images import (
    download_best,
    image_dimensions,
    original_wix_url,
    url_to_filename,
)
from scripts.wix_scrape.inventory import (
    LOW_RES_WIDTH,
    url_to_slug,
    write_images_csv,
    write_inventory_md,
)
from scripts.wix_scrape.page import (
    extract_image_alts,
    extract_image_urls,
    extract_visible_text,
    fetch_rendered_html,
)
from scripts.wix_scrape.sitemap import fetch_sitemap_urls

MIGRATION_DIR = 'migration'

# Site chrome / platform assets we never want.
_SKIP_HOSTS = {'static.parastorage.com'}


def _should_skip(url: str) -> bool:
    if url.startswith('data:'):
        return True
    parsed = urlparse(url)
    if parsed.netloc in _SKIP_HOSTS:
        return True
    name = os.path.basename(parsed.path).lower()
    return 'favicon' in name


def _page_meta(html: str) -> tuple[str, str, list[str]]:
    """Return (title, meta_description, headings h1-h3) from rendered HTML."""
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.title.get_text(strip=True) if soup.title else ''
    desc_tag = soup.find('meta', attrs={'name': 'description'})
    description = (desc_tag.get('content') or '').strip() if desc_tag else ''
    headings = []
    for tag in soup.find_all(['h1', 'h2', 'h3']):
        text = ' '.join(tag.get_text(separator=' ').split())
        if text:
            headings.append(f'{tag.name}: {text}')
    return title, description, headings


def main() -> None:
    pages_dir = os.path.join(MIGRATION_DIR, 'pages')
    images_dir = os.path.join(MIGRATION_DIR, 'images')
    os.makedirs(pages_dir, exist_ok=True)
    os.makedirs(images_dir, exist_ok=True)

    urls = fetch_sitemap_urls()
    print(f'Sitemap: {len(urls)} pages')

    pages: list[dict] = []
    image_rows: list[dict] = []
    seen_normalized: set[str] = set()
    failures: list[str] = []

    for url in urls:
        slug = url_to_slug(url)
        print(f'== {slug} ({url})')
        html = fetch_rendered_html(url)
        text = extract_visible_text(html)
        title, description, headings = _page_meta(html)

        with open(os.path.join(pages_dir, f'{slug}.html'), 'w', encoding='utf-8') as fh:
            fh.write(html)
        with open(os.path.join(pages_dir, f'{slug}.txt'), 'w', encoding='utf-8') as fh:
            fh.write(text)

        dom_urls = extract_image_urls(html)
        alts = extract_image_alts(html)

        page_image_count = 0
        index = 0
        for dom_url in dom_urls:
            if _should_skip(dom_url):
                continue
            page_image_count += 1
            normalized = original_wix_url(dom_url)
            if normalized in seen_normalized:
                continue  # already downloaded, attributed to first page seen
            seen_normalized.add(normalized)

            filename = url_to_filename(normalized, slug, index)
            index += 1
            dest = os.path.join(images_dir, filename)
            ok, used_url = download_best(dom_url, dest)
            width = height = ''
            if ok:
                dims = image_dimensions(dest)
                if dims:
                    width, height = dims
            else:
                failures.append(dom_url)
                print(f'   FAILED: {dom_url}')
            image_rows.append({
                'url': dom_url,
                'requested_url': used_url,
                'local_filename': filename if ok else '',
                'page': slug,
                'alt_text': alts.get(dom_url, ''),
                'width': width,
                'height': height,
            })

        with open(os.path.join(pages_dir, f'{slug}.json'), 'w', encoding='utf-8') as fh:
            json.dump({
                'url': url,
                'slug': slug,
                'title': title,
                'meta_description': description,
                'headings': headings,
                'image_count': page_image_count,
            }, fh, indent=2)

        pages.append({
            'url': url, 'slug': slug, 'title': title,
            'meta_description': description, 'text_chars': len(text),
            'image_count': page_image_count, 'headings': headings,
        })
        print(f'   text={len(text)} chars, images on page={page_image_count}, '
              f'new downloads={index}')

    write_images_csv(os.path.join(MIGRATION_DIR, 'images.csv'), image_rows)
    write_inventory_md(os.path.join(MIGRATION_DIR, 'inventory.md'), pages, image_rows)

    downloaded = [r for r in image_rows if r['local_filename']]
    low_res = [r for r in downloaded
               if isinstance(r['width'], int) and r['width'] < LOW_RES_WIDTH]
    print('\n=== Summary ===')
    print(f'Pages scraped:     {len(pages)}')
    print(f'Images downloaded: {len(downloaded)}')
    print(f'Failures:          {len(failures)}')
    print(f'Raster images < {LOW_RES_WIDTH}px wide: {len(low_res)}')
    for f in failures:
        print(f'  FAILED {f}')


if __name__ == '__main__':
    main()
