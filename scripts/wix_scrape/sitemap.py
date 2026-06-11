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
