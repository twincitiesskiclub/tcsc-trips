import hashlib

from scripts.wix_scrape.images import original_wix_url, url_to_filename


def test_original_wix_url_strips_full_transform():
    url = ('https://static.wixstatic.com/media/abc123~mv2.jpg/v1/fill/'
           'w_305,h_229,al_c,q_80,usm_0.66_1.00_0.01,enc_auto/abc123~mv2.jpg')
    assert original_wix_url(url) == 'https://static.wixstatic.com/media/abc123~mv2.jpg'


def test_original_wix_url_strips_fit_transform_and_query():
    url = ('https://static.wixstatic.com/media/def456~mv2.png/v1/fit/'
           'w_2500,h_1330,al_c/def456~mv2.png?width=2500')
    assert original_wix_url(url) == 'https://static.wixstatic.com/media/def456~mv2.png'


def test_original_wix_url_without_transform_passes_through():
    url = 'https://static.wixstatic.com/media/abc123~mv2.jpg'
    assert original_wix_url(url) == url


def test_original_wix_url_non_wix_unchanged():
    url = 'https://example.com/photos/team.jpg?size=large'
    assert original_wix_url(url) == url


def test_url_to_filename_combines_slug_index_digest():
    url = 'https://static.wixstatic.com/media/abc123~mv2.jpg'
    digest = hashlib.sha1(url.encode()).hexdigest()[:8]
    assert url_to_filename(url, 'coaches', 3) == f'coaches-03-{digest}.jpg'


def test_url_to_filename_falls_back_to_jpg_for_unknown_extension():
    url = 'https://static.wixstatic.com/media/weird.tiff'
    assert url_to_filename(url, 'home', 0).endswith('.jpg')


def test_url_to_filename_keeps_known_extensions():
    for ext in ('.png', '.webp', '.gif', '.svg', '.jpeg'):
        url = f'https://static.wixstatic.com/media/pic{ext}'
        assert url_to_filename(url, 'home', 1).endswith(ext)
