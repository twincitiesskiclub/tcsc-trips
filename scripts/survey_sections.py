"""Viewport-sized section screenshots: scroll through pages capturing each fold."""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "https://tcsc-marketing.onrender.com"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "migration/survey/sections")
OUT.mkdir(parents=True, exist_ok=True)

PAGES = {
    "home": ("/", 6),
    "about": ("/about", 3),
    "coaches": ("/coaches", 4),
    "community": ("/community", 3),
    "racing": ("/racing", 2),
    "wax-room": ("/wax-room", 1),
}

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
    for name, (route, folds) in PAGES.items():
        page.goto(BASE + route, wait_until="networkidle", timeout=45000)
        # pre-scroll to bottom to fire all lazy loads, then back to top
        page.evaluate("async () => { for (let y = 0; y <= document.body.scrollHeight; y += 600) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 60)); } window.scrollTo(0, 0); }")
        page.wait_for_timeout(1200)
        height = page.evaluate("document.body.scrollHeight")
        for i in range(folds):
            y = i * 880
            if y > height:
                break
            page.evaluate(f"window.scrollTo(0, {y})")
            page.wait_for_timeout(350)
            page.screenshot(path=str(OUT / f"{name}-f{i}.png"))
            print(f"{name}-f{i}.png")
    browser.close()
print("done")
