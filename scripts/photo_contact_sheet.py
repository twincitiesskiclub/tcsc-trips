"""Contact sheets from the Slack photo pull, ranked by reaction count.

Usage: python scripts/photo_contact_sheet.py [--min-edge 1600] [--top 60] [--landscape]
Writes numbered sheets to migration/slack_photos/sheets/ plus an index.csv
mapping sheet cell -> source file.
"""
import argparse
import csv
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent / "migration" / "slack_photos"
COLS, ROWS = 5, 6
CELL_W, CELL_H = 360, 300


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-edge", type=int, default=0)
    ap.add_argument("--top", type=int, default=60)
    ap.add_argument("--landscape", action="store_true")
    ap.add_argument("--out", default="sheets")
    args = ap.parse_args()

    with open(ROOT / "manifest.csv") as fh:
        rows = list(csv.DictReader(fh))

    picked = []
    for r in rows:
        w, h = int(r["w"] or 0), int(r["h"] or 0)
        if max(w, h) < args.min_edge:
            continue
        if args.landscape and w <= h:
            continue
        if not (ROOT / r["file"]).exists():
            continue
        picked.append(r)
        if len(picked) >= args.top:
            break

    out_dir = ROOT / args.out
    out_dir.mkdir(exist_ok=True)
    index = []
    per_sheet = COLS * ROWS
    for s in range(0, len(picked), per_sheet):
        batch = picked[s : s + per_sheet]
        sheet = Image.new("RGB", (COLS * CELL_W, ((len(batch) + COLS - 1) // COLS) * CELL_H), "#181818")
        draw = ImageDraw.Draw(sheet)
        for i, r in enumerate(batch):
            n = s + i
            try:
                im = Image.open(ROOT / r["file"])
                im.thumbnail((CELL_W, CELL_H - 22))
            except Exception:
                continue
            x = (i % COLS) * CELL_W + (CELL_W - im.width) // 2
            y = (i // COLS) * CELL_H
            sheet.paste(im, (x, y))
            label = f"#{n} r{r['reactions']} {r['w']}x{r['h']} {r['date']}"
            draw.text(((i % COLS) * CELL_W + 4, y + CELL_H - 18), label, fill="#9af0c0")
            index.append({"n": n, **{k: r[k] for k in ("file", "date", "poster", "w", "h", "reactions", "text")}})
        name = f"sheet-{s // per_sheet:02d}.png"
        sheet.save(out_dir / name)
        print(name, len(batch))
    with open(out_dir / "index.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["n", "file", "date", "poster", "w", "h", "reactions", "text"])
        w.writeheader()
        w.writerows(index)
    print(f"{len(picked)} photos -> {out_dir}")


if __name__ == "__main__":
    main()
