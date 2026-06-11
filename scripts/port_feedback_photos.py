"""One-off: port the June 2026 design-feedback photos from the Slack archive.

Pipeline matches the site's photo convention: EXIF transpose, downscale to a
2560px long edge (never upscale), save progressive JPEG quality 90. Prints the
port-manifest.csv rows for the committed files.

Run from the repo root: python scripts/port_feedback_photos.py
"""
from pathlib import Path

from PIL import Image, ImageOps

SRC = Path('migration/slack_photos')
DEST = Path('site/src/assets/images/photos')
SOURCE_URL = 'slack://twincitiesskiclub/#photos-videos (see migration/slack_photos/manifest.csv)'
CONSENT = 'member-posted-club-slack; see migration/CONSENT.md'

# (dest_name, source_name, slot, min_required_w)
PHOTOS = [
    ('team-banner.jpg', '2024-03-30_1711812078-797759_0.jpg', 'page_header', 1920),
    ('canoe-social.jpg', '2024-07-09_1720579793-084489_1.jpg', 'page_header', 1920),
    ('race-crew-frosty.jpg', '2023-01-21_1674324661-077579_0.jpg', 'page_header', 1920),
    ('rollerski-golden-hour.jpg', '2024-08-13_1723597154-617769_0.jpg', 'page_body', 800),
    ('backyard-social.jpg', '2024-05-16_1715917971-931869_0.jpg', 'page_body', 800),
    ('run-club-selfie.jpg', '2026-04-23_1776954511-019769_2.jpg', 'page_body', 800),
    ('winter-five.jpg', '2023-01-08_1673242364-942339_1.jpg', 'page_body', 800),
    ('lakeside-picnic.jpg', '2024-03-03_1709501583-457379_0.jpg', 'page_body', 800),
    ('second-harvest.jpg', '2024-01-17_1705546321-840949_0.jpg', 'page_body', 800),
    ('barn-banquet.jpg', '2026-04-12_1776027078-470899_0.jpg', 'page_body', 800),
    ('ski-de-she-trio.jpg', '2023-01-28_1674942658-549799_0.jpg', 'page_body', 800),
    ('korte-medals.jpg', '2022-02-25_1645852380-232989_0.jpg', 'page_body', 800),
    ('birkie-start.jpg', '2024-02-23_1708738564-829599_1.jpg', 'page_body', 800),
    ('finlandia-podium.jpg', '2026-02-14_1771096714-097109_0.jpg', 'page_body', 800),
    ('skijor-race.jpg', '2024-02-07_1707360103-835559_0.jpg', 'page_body', 800),
]


def main() -> None:
    rows = []
    for dest_name, source_name, slot, minw in PHOTOS:
        src_path = SRC / source_name
        dest_path = DEST / dest_name
        with Image.open(src_path) as img:
            img = ImageOps.exif_transpose(img)
            ow, oh = img.size
            img.thumbnail((2560, 2560), Image.Resampling.LANCZOS)  # downscale only
            cw, ch = img.size
            img.convert('RGB').save(dest_path, 'JPEG', quality=90, progressive=True, optimize=True)
        if cw < minw:
            print(f'!! {dest_name}: committed width {cw} < min_required_w {minw}')
        rows.append(
            f'site/src/assets/images/photos/{dest_name},migration/slack_photos/{source_name},'
            f'{SOURCE_URL},{ow},{oh},{cw},{ch},{slot},{minw},{CONSENT}'
        )
        print(f'ok {dest_name}: {ow}x{oh} -> {cw}x{ch}')
    print('\n--- append to migration/port-manifest.csv ---')
    for r in rows:
        print(r)


if __name__ == '__main__':
    main()
