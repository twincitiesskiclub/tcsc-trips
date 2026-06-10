from scripts.wix_scrape.inventory import url_to_slug


def test_url_to_slug_root_is_home():
    assert url_to_slug('https://www.twincitiesskiclub.org') == 'home'
    assert url_to_slug('https://www.twincitiesskiclub.org/') == 'home'


def test_url_to_slug_path_and_nested():
    assert url_to_slug('https://www.twincitiesskiclub.org/coaches') == 'coaches'
    assert url_to_slug('https://x.org/a/b') == 'a-b'
