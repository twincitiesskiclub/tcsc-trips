import hashlib
from unittest.mock import patch

from scripts.wix_scrape.images import (
    download_best,
    download_image,
    original_wix_url,
    url_to_filename,
)


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


def test_original_wix_url_percent_encoding_normalizes_for_dedupe():
    encoded = ('https://static.wixstatic.com/media/abc123%7Emv2.jpg/v1/fill/'
               'w_305,h_229,al_c/abc123%7Emv2.jpg')
    plain = ('https://static.wixstatic.com/media/abc123~mv2.jpg/v1/fill/'
             'w_470,h_350,al_c/abc123~mv2.jpg')
    assert original_wix_url(encoded) == original_wix_url(plain)
    assert original_wix_url(encoded) == 'https://static.wixstatic.com/media/abc123~mv2.jpg'


_DOM_URL = ('https://static.wixstatic.com/media/abc123~mv2.jpg/v1/fill/'
            'w_305,h_229,al_c,q_80/abc123~mv2.jpg')
_ORIGINAL = 'https://static.wixstatic.com/media/abc123~mv2.jpg'
_FIT = f'{_ORIGINAL}/v1/fit/w_2500,h_2500,q_90/abc123~mv2.jpg'


def test_download_best_tries_original_first(tmp_path):
    dest = str(tmp_path / 'x.jpg')
    with patch('scripts.wix_scrape.images.download_image') as mock_dl:
        mock_dl.return_value = True
        ok, used = download_best(_DOM_URL, dest)
    assert ok is True
    assert used == _ORIGINAL
    mock_dl.assert_called_once_with(_ORIGINAL, dest)


def test_download_best_falls_back_original_then_fit_then_raw(tmp_path):
    dest = str(tmp_path / 'x.jpg')
    with patch('scripts.wix_scrape.images.download_image') as mock_dl:
        mock_dl.side_effect = [False, False, True]
        ok, used = download_best(_DOM_URL, dest)
    assert ok is True
    assert used == _DOM_URL
    assert [c.args[0] for c in mock_dl.call_args_list] == [_ORIGINAL, _FIT, _DOM_URL]


def test_download_best_reports_fit_variant_when_it_wins(tmp_path):
    dest = str(tmp_path / 'x.jpg')
    with patch('scripts.wix_scrape.images.download_image') as mock_dl:
        mock_dl.side_effect = [False, True]
        ok, used = download_best(_DOM_URL, dest)
    assert ok is True
    assert used == _FIT


def test_download_best_all_fail_reports_original(tmp_path):
    dest = str(tmp_path / 'x.jpg')
    with patch('scripts.wix_scrape.images.download_image') as mock_dl:
        mock_dl.return_value = False
        ok, used = download_best(_DOM_URL, dest)
    assert ok is False
    assert used == _ORIGINAL
    assert mock_dl.call_count == 3


class _FakeResponse:
    def __init__(self, content_type):
        self.headers = {'Content-Type': content_type}

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        yield b'<html>error page</html>'

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_download_image_rejects_non_image_content_type(tmp_path):
    dest = str(tmp_path / 'imgs' / 'x.jpg')
    with patch('scripts.wix_scrape.images.requests.get',
               return_value=_FakeResponse('text/html; charset=utf-8')):
        assert download_image('https://x.com/err', dest) is False
    import os
    assert not os.path.exists(dest)


def test_download_image_accepts_image_content_type(tmp_path):
    dest = str(tmp_path / 'imgs' / 'x.jpg')
    with patch('scripts.wix_scrape.images.requests.get',
               return_value=_FakeResponse('image/jpeg')):
        assert download_image('https://x.com/ok.jpg', dest) is True
    import os
    assert os.path.getsize(dest) > 0
