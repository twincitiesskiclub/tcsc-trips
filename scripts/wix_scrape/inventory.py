"""Write the scrape audit trail: images.csv and inventory.md."""
from __future__ import annotations

import csv
from urllib.parse import urlparse

CSV_COLUMNS = ['url', 'requested_url', 'local_filename', 'page', 'alt_text', 'width', 'height']

# Raster images narrower than this are flagged: too small for large UI slots.
LOW_RES_WIDTH = 800


def url_to_slug(url: str) -> str:
    """Derive a filesystem slug from a page URL ('' path -> 'home')."""
    path = urlparse(url).path.strip('/')
    if not path:
        return 'home'
    return path.replace('/', '-')


def write_images_csv(path: str, rows: list[dict]) -> None:
    """Write image records (CSV_COLUMNS keys) to a CSV file."""
    with open(path, 'w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, '') for col in CSV_COLUMNS})


def write_inventory_md(path: str, pages: list[dict], image_rows: list[dict]) -> None:
    """Write a human-readable inventory: low-res warnings, then per-page detail.

    ``pages``: dicts with url, slug, title, meta_description, text_chars,
    image_count, headings (list[str]).
    ``image_rows``: the same dicts passed to write_images_csv.
    """
    lines = [
        '# Wix Site Content Inventory',
        '',
        'Images are deduplicated globally: each image is listed under the '
        'first page seen; shared assets appear once.',
        '',
    ]

    low_res = [
        r for r in image_rows
        if isinstance(r.get('width'), int) and r['width'] < LOW_RES_WIDTH
    ]
    lines.append('## Low-resolution warnings')
    lines.append('')
    if low_res:
        lines.append(
            f'{len(low_res)} downloaded raster image(s) are narrower than '
            f'{LOW_RES_WIDTH}px. Do NOT use these in large UI slots.'
        )
        lines.append('')
        for r in low_res:
            lines.append(
                f"- `{r['local_filename']}` ({r['width']}x{r['height']}) "
                f"from {r['page']} — {r['url']}"
            )
    else:
        lines.append('None. Every raster image is at least '
                     f'{LOW_RES_WIDTH}px wide.')
    lines.append('')

    for page in pages:
        lines.append(f"## {page['slug']}")
        lines.append('')
        lines.append(f"- Source URL: {page['url']}")
        lines.append(f"- Title: {page.get('title') or '(none)'}")
        lines.append(f"- Meta description: {page.get('meta_description') or '(none)'}")
        lines.append(f"- Visible text: {page.get('text_chars', 0)} chars")
        lines.append(f"- Images: {page.get('image_count', 0)}")
        headings = page.get('headings') or []
        if headings:
            lines.append('- Headings:')
            for h in headings:
                lines.append(f'  - {h}')
        else:
            lines.append('- Headings: (none)')
        lines.append('')

    with open(path, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines))
