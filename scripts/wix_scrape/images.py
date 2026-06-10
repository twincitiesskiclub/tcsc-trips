"""Download Wix images at their true original resolution.

Wix CDN URLs in the DOM carry a rendered-variant transform suffix:

    https://static.wixstatic.com/media/<mediaId>.jpg/v1/fill/w_305,h_229,.../<name>.jpg

The full-resolution original is served by stripping everything from ``/v1/``
onward, leaving the bare media URL. A previous scrape only rewrote ``w_``
inside the transform and downloaded 200-305px thumbnails — never do that.
"""
from __future__ import annotations

import hashlib
import os
import re
from urllib.parse import urlparse, urlsplit, urlunsplit

import requests
from PIL import Image

_KNOWN_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.avif'}
_USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
)


def url_to_filename(url: str, page_slug: str, index: int) -> str:
    """Derive a stable local filename: {slug}-{index:02d}-{sha1[:8]}{ext}."""
    digest = hashlib.sha1(url.encode()).hexdigest()[:8]
    path = urlparse(url).path
    ext = os.path.splitext(path)[1].lower()
    if ext not in _KNOWN_EXTENSIONS:
        ext = '.jpg'
    return f'{page_slug}-{index:02d}-{digest}{ext}'


def original_wix_url(url: str) -> str:
    """Return the bare full-resolution media URL for a Wix CDN URL.

    Strips the entire transform suffix (everything from the first ``/v1/``
    onward) plus any query string. Non-Wix URLs are returned unchanged.
    """
    if urlparse(url).netloc != 'static.wixstatic.com':
        return url
    scheme, netloc, path, _query, _frag = urlsplit(url)
    path = re.split(r'/v1/', path, maxsplit=1)[0]
    return urlunsplit((scheme, netloc, path, '', ''))


def _fit_variant(url: str) -> str | None:
    """Fallback: replace the transform with a large /v1/fit/ variant."""
    if urlparse(url).netloc != 'static.wixstatic.com':
        return None
    bare = original_wix_url(url)
    name = bare.rsplit('/', 1)[-1]
    return f'{bare}/v1/fit/w_2500,h_2500,q_90/{name}'


def download_image(url: str, dest_path: str) -> bool:
    """Stream the image to dest_path. Returns False on any request/HTTP error."""
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
        return True
    try:
        with requests.get(url, stream=True, timeout=60,
                          headers={'User-Agent': _USER_AGENT}) as resp:
            resp.raise_for_status()
            with open(dest_path, 'wb') as fh:
                for chunk in resp.iter_content(chunk_size=65536):
                    fh.write(chunk)
    except requests.RequestException:
        if os.path.exists(dest_path):
            os.remove(dest_path)
        return False
    return os.path.getsize(dest_path) > 0


def download_best(url: str, dest_path: str) -> tuple[bool, str]:
    """Try the true original first, then a large fit variant, then the raw URL.

    Returns (success, url_actually_used).
    """
    candidates = [original_wix_url(url)]
    fit = _fit_variant(url)
    if fit and fit not in candidates:
        candidates.append(fit)
    if url not in candidates:
        candidates.append(url)
    for candidate in candidates:
        if download_image(candidate, dest_path):
            return True, candidate
    return False, candidates[0]


def image_dimensions(path: str) -> tuple[int, int] | None:
    """Return (width, height) via Pillow, or None for SVG/unreadable files."""
    try:
        with Image.open(path) as img:
            return img.size
    except Exception:  # noqa: BLE001 - SVGs and corrupt files land here
        return None
