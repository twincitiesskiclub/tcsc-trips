#!/usr/bin/env python3
"""Migration-completeness verifier: Wix scrape vs ported Astro content.

Checks (exit 0 only when every check passes):

1. Pages — every slug in migration/pages/*.txt is either content-mapped
   (CONTENT_MAP), an intentional redirect verified against render.yaml
   routes (REDIRECT_SLUGS), or explicitly waived with a reason (WAIVED).
2. Text coverage — for each content-mapped page, ported word count
   (mapped content bodies + frontmatter prose) must be >= 70% of the
   migration .txt word count after stripping Wix page chrome
   (nav/footer lines repeated on every page).
3. Manifest/media — every row in migration/port-manifest.csv: asset
   exists, actual dims == committed dims, committed <= original (no
   upscale), width >= min_required_w. Reverse: every image under
   site/src/assets/images/** and site/public/og/ has a manifest row.
4. Unported-images inventory — every migration/images.csv row absent
   from the manifest must carry a coded classification (informational
   table; 'unclassified' is a failure).

Run from anywhere: python scripts/wix_scrape/verify.py
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]

# --------------------------------------------------------------------------
# Check 1: slug accounting
# --------------------------------------------------------------------------

# Wix slug -> content file globs (repo-relative) that carry the ported copy.
# practice_seasons is included for home + about because the Wix copy for the
# two training seasons appears on both pages and was normalized into the
# practice_seasons collection (rendered by SeasonsGrid.astro on / and /about).
CONTENT_MAP: dict[str, list[str]] = {
    'home': [
        'site/src/content/pages/home.yaml',
        'site/src/content/practice_seasons/*.yaml',
    ],
    'about': [
        'site/src/content/pages/about.mdoc',
        'site/src/content/practice_seasons/*.yaml',
    ],
    'community': ['site/src/content/pages/community.mdoc'],
    'racing': ['site/src/content/pages/racing.mdoc'],
    'coaches': ['site/src/content/coaches/*.mdoc'],
    'sponsors': [
        'site/src/content/pages/sponsors_page.yaml',
        'site/src/content/sponsors/*.yaml',
    ],
    'contact': ['site/src/content/pages/contact.yaml'],
    'sisu-information': ['site/src/content/trips/sisu-ski-fest.mdoc'],
}

# Slugs intentionally handled as redirects; each must appear as a
# `source: /<slug>` route in render.yaml.
REDIRECT_SLUGS = {
    'register',            # -> https://tcsc.ski/register (Flask app)
    'copy-of-register',    # 403/permission-gated on Wix; redirected like register
    'sisu-signup',         # -> https://tcsc.ski/trips/sisu-ski-fest
    'trip-sign-up',        # -> https://tcsc.ski/trips
    'trip-confirmation',   # Wix form thank-you page; obsolete -> /
    'confirmation',        # Wix form thank-you page; obsolete -> /
    'trip-information',    # stale Hayward trip page -> /trips
}

# Slugs waived entirely (neither content nor redirect), with reasons.
WAIVED: dict[str, str] = {}

# --------------------------------------------------------------------------
# Check 2: text coverage
# --------------------------------------------------------------------------

DEFAULT_COVERAGE_THRESHOLD = 0.70

# Per-slug threshold overrides, each with a coded reason. None needed today;
# kept as the documented hook so future overrides carry a reason string.
COVERAGE_OVERRIDES: dict[str, tuple[float, str]] = {}

# Wix page chrome: lines repeated on every scraped page (header nav, footer,
# Wix scaffolding). Stripped before word-counting so the comparison measures
# actual page copy. The first line of each .txt (the <title>) is also dropped.
CHROME_LINES = {
    'top of page',
    'bottom of page',
    'Skip to Main Content',
    'HOME',
    'ABOUT US',
    'COMMUNITY',
    'RACING',
    'COACHES',
    'SPONSORS',
    'CONTACT',
    'REGISTER',
    '© 2024 by Twin Cities Ski Club.',
}

# --------------------------------------------------------------------------
# Check 4: unported-image classification
# --------------------------------------------------------------------------

# Category -> human-readable reason.
CATEGORY_REASONS = {
    'social-icon': 'Wix footer social icon; new site uses inline SVG icons',
    'wix-logo': 'TCSC wordmark raster from Wix; new site ships its own brand assets',
    'gallery-not-selected': 'photo not selected for the curated mosaic/gallery port',
    'low-res': 'below the 800px floor for content slots (see migration/inventory.md)',
}

# local_filename (from images.csv) -> category, for every row that has no
# port-manifest entry. Anything missing here reports as 'unclassified' = fail.
UNPORTED_CLASSIFICATION = {
    'register-00-9ca0a4d6.png': 'social-icon',        # Facebook glyph
    'register-03-6246abd0.png': 'social-icon',        # Instagram glyph
    'register-01-93519dd7.png': 'wix-logo',           # navy TCSC wordmark
    'register-02-6aed0432.png': 'wix-logo',           # black TCSC wordmark
    'about-02-8b4ef1c5.jpg': 'gallery-not-selected',  # ski-hill group banner
    'coaches-01-c1bee67b.jpeg': 'gallery-not-selected',  # summer hillside banner
    'community-04-a5b57800.jpeg': 'gallery-not-selected',
    'community-06-c682b4a6.jpg': 'gallery-not-selected',
    'community-12-3c5a27ae.jpg': 'gallery-not-selected',
    'community-14-889754e8.jpg': 'gallery-not-selected',
    'community-15-81a0d706.png': 'gallery-not-selected',  # night group banner
    'home-01-564702c7.jpg': 'gallery-not-selected',   # home banner strip
    'racing-01-e7002d2a.jpg': 'gallery-not-selected',
    'racing-03-6e7db6a2.jpg': 'gallery-not-selected',
    'racing-05-6da48d8c.jpg': 'gallery-not-selected',
    'racing-10-c77e48f9.jpg': 'gallery-not-selected',
    'racing-11-a2b3aa75.jpg': 'gallery-not-selected',
    'racing-13-3949197c.jpg': 'gallery-not-selected',
    'racing-15-55e382cf.jpg': 'gallery-not-selected',
    'racing-16-078437a5.jpg': 'gallery-not-selected',
    'racing-17-ec9f512b.jpg': 'low-res',              # 480x640
    'racing-19-10d2592f.jpg': 'gallery-not-selected',
}

# Image directories that must be fully covered by the manifest (reverse check).
AUDITED_IMAGE_DIRS = ['site/src/assets/images', 'site/public/og']
IMAGE_SUFFIXES = {'.jpg', '.jpeg', '.png', '.webp', '.avif', '.gif'}


# --------------------------------------------------------------------------
# Pure helpers (unit-tested in tests/wix_scrape/test_verify.py)
# --------------------------------------------------------------------------

def account_slugs(slugs: list[str],
                  content_map: dict[str, list[str]],
                  redirect_slugs: set[str],
                  waived: dict[str, str]) -> dict[str, str]:
    """Map each slug to its disposition; 'UNACCOUNTED' marks a failure."""
    out = {}
    for slug in slugs:
        if slug in content_map:
            out[slug] = 'content'
        elif slug in redirect_slugs:
            out[slug] = 'redirect'
        elif slug in waived:
            out[slug] = f'waived: {waived[slug]}'
        else:
            out[slug] = 'UNACCOUNTED'
    return out


def strip_chrome(text: str, chrome_lines: set[str] = CHROME_LINES) -> str:
    """Drop the title line, Wix chrome lines, and zero-width filler lines."""
    lines = text.splitlines()
    kept = []
    for i, line in enumerate(lines):
        clean = line.replace('​', '').strip()
        if i == 0:  # <title> line, e.g. 'ABOUT US | Twin Cities Ski Club'
            continue
        if not clean or clean in chrome_lines:
            continue
        kept.append(clean)
    return '\n'.join(kept)


def count_words(text: str) -> int:
    return len(re.findall(r'\S+', text))


def _is_prose(value: str) -> bool:
    """Frontmatter strings that are URLs/asset paths are not page copy."""
    return not re.match(r'^(https?://|\.\./|/|mailto:)', value.strip())


def collect_yaml_strings(node) -> list[str]:
    """Recursively collect prose string values from parsed YAML."""
    out = []
    if isinstance(node, str):
        if _is_prose(node):
            out.append(node)
    elif isinstance(node, dict):
        for v in node.values():
            out.extend(collect_yaml_strings(v))
    elif isinstance(node, list):
        for v in node:
            out.extend(collect_yaml_strings(v))
    return out


def split_frontmatter(text: str) -> tuple[dict, str]:
    """Split an .mdoc/.md file into (frontmatter dict, body)."""
    m = re.match(r'\A---\n(.*?)\n---\n?(.*)\Z', text, re.DOTALL)
    if not m:
        return {}, text
    return (yaml.safe_load(m.group(1)) or {}), m.group(2)


def markdown_to_text(body: str) -> str:
    """Light markdown strip: links -> text, drop heading/emphasis markers."""
    body = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', body)
    body = re.sub(r'^#{1,6}\s+', '', body, flags=re.MULTILINE)
    return body.replace('**', '').replace('`', '')


def ported_words_for_file(path: Path) -> int:
    text = path.read_text(encoding='utf-8')
    if path.suffix in ('.yaml', '.yml'):
        data = yaml.safe_load(text)
        return count_words(' '.join(collect_yaml_strings(data)))
    fm, body = split_frontmatter(text)
    fm_words = count_words(' '.join(collect_yaml_strings(fm)))
    return fm_words + count_words(markdown_to_text(body))


def coverage_ratio(ported_words: int, source_words: int) -> float:
    if source_words == 0:
        return 1.0
    return ported_words / source_words


def validate_manifest_row(row: dict, actual_size: tuple[int, int] | None) -> list[str]:
    """Return a list of problems for one port-manifest row (pure)."""
    problems = []
    if actual_size is None:
        problems.append('asset file missing')
        return problems
    cw, ch = int(row['committed_w']), int(row['committed_h'])
    ow, oh = int(row['original_w']), int(row['original_h'])
    minw = int(row['min_required_w'])
    if actual_size != (cw, ch):
        problems.append(f'actual dims {actual_size[0]}x{actual_size[1]} != committed {cw}x{ch}')
    if cw > ow or ch > oh:
        problems.append(f'upscaled: committed {cw}x{ch} > original {ow}x{oh}')
    if cw < minw:
        problems.append(f'committed width {cw} < min_required_w {minw} for slot {row["slot"]}')
    return problems


# --------------------------------------------------------------------------
# Check runners
# --------------------------------------------------------------------------

def load_redirect_sources() -> set[str]:
    data = yaml.safe_load((REPO / 'render.yaml').read_text(encoding='utf-8'))
    sources = set()
    for svc in data.get('services', []):
        for route in svc.get('routes', []) or []:
            if route.get('type') == 'redirect':
                sources.add(route['source'].lstrip('/'))
    return sources


def check_pages() -> list[str]:
    failures = []
    slugs = sorted(p.stem for p in (REPO / 'migration/pages').glob('*.txt'))
    dispositions = account_slugs(slugs, CONTENT_MAP, REDIRECT_SLUGS, WAIVED)
    redirect_sources = load_redirect_sources()
    print('\n== Check 1: page slug accounting ==')
    for slug, disp in dispositions.items():
        note = ''
        if disp == 'UNACCOUNTED':
            failures.append(f'pages: slug {slug!r} has no content mapping, redirect, or waiver')
        if disp == 'redirect' and slug not in redirect_sources:
            failures.append(f'pages: redirect slug {slug!r} missing from render.yaml routes')
            note = ' (NOT IN render.yaml!)'
        if disp == 'content':
            files = []
            for pattern in CONTENT_MAP[slug]:
                files.extend(REPO.glob(pattern))
            if not files:
                failures.append(f'pages: content globs for {slug!r} matched no files')
                note = ' (NO FILES!)'
        print(f'  {slug:<20} {disp}{note}')
    for slug in CONTENT_MAP:
        if slug not in dispositions:
            failures.append(f'pages: CONTENT_MAP slug {slug!r} has no migration/pages/{slug}.txt')
    return failures


def check_text_coverage() -> list[str]:
    failures = []
    print('\n== Check 2: text coverage (ported words / source words) ==')
    print(f'  {"slug":<18} {"source":>7} {"ported":>7} {"ratio":>7}  threshold')
    for slug, patterns in sorted(CONTENT_MAP.items()):
        source_txt = (REPO / 'migration/pages' / f'{slug}.txt').read_text(encoding='utf-8')
        source_words = count_words(strip_chrome(source_txt))
        ported = 0
        for pattern in patterns:
            for path in sorted(REPO.glob(pattern)):
                ported += ported_words_for_file(path)
        threshold, reason = COVERAGE_OVERRIDES.get(
            slug, (DEFAULT_COVERAGE_THRESHOLD, ''))
        ratio = coverage_ratio(ported, source_words)
        flag = 'ok' if ratio >= threshold else 'FAIL'
        note = f' ({reason})' if reason else ''
        print(f'  {slug:<18} {source_words:>7} {ported:>7} {ratio:>6.0%}  {threshold:.0%} {flag}{note}')
        if ratio < threshold:
            failures.append(
                f'coverage: {slug} ported/source = {ratio:.0%} < {threshold:.0%}')
    return failures


def check_manifest() -> list[str]:
    from PIL import Image
    failures = []
    print('\n== Check 3: port-manifest media audit ==')
    manifest_assets = set()
    rows = list(csv.DictReader(open(REPO / 'migration/port-manifest.csv', encoding='utf-8')))
    for row in rows:
        asset = REPO / row['asset_path']
        manifest_assets.add(row['asset_path'])
        actual = None
        if asset.is_file():
            with Image.open(asset) as im:
                actual = im.size
        for problem in validate_manifest_row(row, actual):
            failures.append(f'manifest: {row["asset_path"]}: {problem}')
    print(f'  {len(rows)} manifest rows checked, {len(failures)} problem(s)')

    # Reverse: no unaudited committed images.
    unaudited = []
    for d in AUDITED_IMAGE_DIRS:
        for path in sorted((REPO / d).rglob('*')):
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
                rel = str(path.relative_to(REPO))
                if rel not in manifest_assets:
                    unaudited.append(rel)
    for rel in unaudited:
        failures.append(f'manifest: committed image with no manifest row: {rel}')
    print(f'  reverse check: {len(unaudited)} unaudited committed image(s)')
    return failures


def check_unported_inventory() -> list[str]:
    failures = []
    ported_sources = {
        row['source_migration_file'].split('/')[-1]
        for row in csv.DictReader(open(REPO / 'migration/port-manifest.csv', encoding='utf-8'))
    }
    rows = list(csv.DictReader(open(REPO / 'migration/images.csv', encoding='utf-8')))
    unported = [r for r in rows if r['local_filename'] not in ported_sources]
    print('\n== Check 4: unported-images inventory (informational) ==')
    print(f'  {len(rows)} scraped images, {len(rows) - len(unported)} ported sources, '
          f'{len(unported)} unported:')
    print(f'  {"file":<28} {"dims":>10}  classification')
    for r in sorted(unported, key=lambda r: r['local_filename']):
        cat = UNPORTED_CLASSIFICATION.get(r['local_filename'], 'unclassified')
        print(f'  {r["local_filename"]:<28} {r["width"]+"x"+r["height"]:>10}  {cat}')
        if cat == 'unclassified':
            failures.append(f'unported: {r["local_filename"]} is unclassified')
    print('\n  classification key:')
    for cat, reason in CATEGORY_REASONS.items():
        print(f'    {cat}: {reason}')
    stale = set(UNPORTED_CLASSIFICATION) - {r['local_filename'] for r in unported}
    for name in sorted(stale):
        failures.append(f'unported: classification for {name!r} is stale '
                        '(file is ported or no longer scraped)')
    return failures


def main() -> int:
    failures = []
    failures += check_pages()
    failures += check_text_coverage()
    failures += check_manifest()
    failures += check_unported_inventory()
    print('\n== Result ==')
    if failures:
        for f in failures:
            print(f'  FAIL: {f}')
        print(f'\n{len(failures)} failure(s).')
        return 1
    print('  All checks passed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
