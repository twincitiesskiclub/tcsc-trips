"""Full-page screenshots of the staging site for the impeccable polish pass."""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "https://tcsc-marketing.onrender.com"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "migration/survey")
OUT.mkdir(parents=True, exist_ok=True)

ROUTES = ["/", "/about", "/community", "/racing", "/coaches", "/wax-room", "/sponsors", "/trips", "/contact"]
VIEWPORTS = {"desktop": (1440, 900), "mobile": (390, 844)}

with sync_playwright() as p:
    browser = p.chromium.launch()
    for vname, (w, h) in VIEWPORTS.items():
        page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=2)
        for route in ROUTES:
            slug = "home" if route == "/" else route.strip("/").replace("/", "-")
            page.goto(BASE + route, wait_until="networkidle", timeout=45000)
            page.wait_for_timeout(800)
            page.screenshot(path=str(OUT / f"{slug}-{vname}.png"), full_page=True)
            print(f"{slug}-{vname}.png")
    browser.close()
print(f"done -> {OUT}")
