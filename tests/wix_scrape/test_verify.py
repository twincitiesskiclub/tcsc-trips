"""Unit tests for the pure helpers in scripts/wix_scrape/verify.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.wix_scrape.verify import (  # noqa: E402
    account_slugs,
    collect_yaml_strings,
    count_words,
    coverage_ratio,
    markdown_to_text,
    split_frontmatter,
    strip_chrome,
    validate_manifest_row,
)


# -- slug accounting ---------------------------------------------------------

def test_account_slugs_dispositions():
    out = account_slugs(
        ['about', 'register', 'ghost', 'old-page'],
        content_map={'about': ['x.mdoc']},
        redirect_slugs={'register'},
        waived={'old-page': '403 on Wix'},
    )
    assert out['about'] == 'content'
    assert out['register'] == 'redirect'
    assert out['old-page'] == 'waived: 403 on Wix'
    assert out['ghost'] == 'UNACCOUNTED'


def test_account_slugs_content_takes_precedence_over_redirect():
    # sisu-information is both content-mapped and redirected on the static host
    out = account_slugs(['sisu-information'],
                        content_map={'sisu-information': ['t.mdoc']},
                        redirect_slugs={'sisu-information'},
                        waived={})
    assert out['sisu-information'] == 'content'


# -- chrome stripping + word counts ------------------------------------------

WIX_TXT = """ABOUT US | Twin Cities Ski Club
top of page
Skip to Main Content
HOME
ABOUT US
REGISTER
Real heading
Real body copy here.
​
© 2024 by Twin Cities Ski Club.
bottom of page"""


def test_strip_chrome_removes_title_nav_footer_and_zwsp():
    assert strip_chrome(WIX_TXT) == 'Real heading\nReal body copy here.'


def test_count_words():
    assert count_words('Real heading\nReal body copy here.') == 6
    assert count_words('') == 0


def test_coverage_ratio():
    assert coverage_ratio(70, 100) == 0.70
    assert coverage_ratio(0, 0) == 1.0  # empty source page never fails


# -- ported-content extraction -----------------------------------------------

def test_collect_yaml_strings_skips_urls_and_asset_paths():
    data = {
        'headline': 'Meet our sponsors',
        'logo': '../../assets/images/sponsors/kwik-trip.jpg',
        'url': 'https://www.kwiktrip.com/',
        'items': [{'note': 'great org'}],
    }
    assert collect_yaml_strings(data) == ['Meet our sponsors', 'great org']


def test_split_frontmatter_and_markdown_to_text():
    fm, body = split_frontmatter('---\nheadline: Hi\n---\n## Head\n\nSee [docs](https://x.y) **now**.')
    assert fm == {'headline': 'Hi'}
    text = markdown_to_text(body)
    assert 'https://x.y' not in text
    assert 'See docs now.' in text
    assert '##' not in text


def test_split_frontmatter_without_frontmatter():
    fm, body = split_frontmatter('plain body')
    assert fm == {}
    assert body == 'plain body'


# -- manifest row validation ---------------------------------------------------

ROW = {
    'asset_path': 'site/src/assets/images/photos/x.jpg',
    'original_w': '4032', 'original_h': '3024',
    'committed_w': '2560', 'committed_h': '1920',
    'slot': 'mosaic_photo', 'min_required_w': '800',
}


def test_validate_manifest_row_ok():
    assert validate_manifest_row(ROW, (2560, 1920)) == []


def test_validate_manifest_row_missing_file():
    assert validate_manifest_row(ROW, None) == ['asset file missing']


def test_validate_manifest_row_dim_mismatch():
    problems = validate_manifest_row(ROW, (1280, 960))
    assert any('!= committed' in p for p in problems)


def test_validate_manifest_row_upscale():
    row = dict(ROW, committed_w='5000', committed_h='3750')
    problems = validate_manifest_row(row, (5000, 3750))
    assert any('upscaled' in p for p in problems)


def test_validate_manifest_row_below_slot_minimum():
    row = dict(ROW, committed_w='640', committed_h='480')
    problems = validate_manifest_row(row, (640, 480))
    assert any('min_required_w' in p for p in problems)
