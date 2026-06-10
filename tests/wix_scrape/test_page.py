from scripts.wix_scrape.page import (
    extract_image_alts,
    extract_image_urls,
    extract_visible_text,
)

HTML = """
<html>
  <head>
    <title>Coaches</title>
    <style>.hidden { display: none; }</style>
    <script>console.log('tracking');</script>
    <meta property="og:image" content="https://static.wixstatic.com/media/og123.jpg/v1/fill/w_1200,h_630/og123.jpg">
  </head>
  <body>
    <noscript>Enable JS</noscript>
    <h1>Our   Coaches</h1>
    <p>Meet the team.</p>
    <img src="https://static.wixstatic.com/media/coach1.jpg/v1/fill/w_200,h_200/coach1.jpg" alt="Coach One">
    <img data-src="https://static.wixstatic.com/media/lazy9.jpg" alt="">
    <div style="background-image: url(https://static.wixstatic.com/media/bg42.png/v1/fill/w_980/bg42.png);">hero</div>
  </body>
</html>
"""


def test_extract_visible_text_strips_script_and_style():
    text = extract_visible_text(HTML)
    assert 'Our Coaches' in text
    assert 'Meet the team.' in text
    assert 'console.log' not in text
    assert '.hidden' not in text
    assert 'Enable JS' not in text


def test_extract_image_urls_finds_src_and_background():
    urls = extract_image_urls(HTML)
    assert 'https://static.wixstatic.com/media/coach1.jpg/v1/fill/w_200,h_200/coach1.jpg' in urls
    assert 'https://static.wixstatic.com/media/bg42.png/v1/fill/w_980/bg42.png' in urls
    assert 'https://static.wixstatic.com/media/lazy9.jpg' in urls
    assert 'https://static.wixstatic.com/media/og123.jpg/v1/fill/w_1200,h_630/og123.jpg' in urls
    # Sorted + deduplicated
    assert urls == sorted(set(urls))


def test_extract_image_urls_picks_largest_srcset_density_candidate():
    html = '<img srcset="https://x.com/a.jpg 1x, https://x.com/b.jpg 2x" src="https://x.com/a.jpg">'
    urls = extract_image_urls(html)
    assert 'https://x.com/b.jpg' in urls


def test_extract_image_urls_picks_largest_srcset_width_candidate():
    html = (
        '<picture><source srcset="https://x.com/s.jpg 480w, https://x.com/l.jpg 1920w, '
        'https://x.com/m.jpg 960w"><img src="https://x.com/s.jpg"></picture>'
    )
    urls = extract_image_urls(html)
    assert 'https://x.com/l.jpg' in urls


def test_extract_image_urls_ignores_data_uris():
    html = '<img src="data:image/gif;base64,R0lGOD"><img src="https://x.com/real.jpg">'
    assert extract_image_urls(html) == ['https://x.com/real.jpg']


def test_extract_image_alts_maps_url_to_alt():
    alts = extract_image_alts(HTML)
    assert alts['https://static.wixstatic.com/media/coach1.jpg/v1/fill/w_200,h_200/coach1.jpg'] == 'Coach One'
    assert alts['https://static.wixstatic.com/media/lazy9.jpg'] == ''
