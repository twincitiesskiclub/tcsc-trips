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
