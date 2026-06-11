"""One-shot: pull image originals from #photos-videos for the marketing-site photo refresh.

Downloads every image attachment >= MIN_EDGE px on its long edge to
migration/slack_photos/ and writes manifest.csv (date, poster, dims,
reaction count as a popularity proxy, permalink, message text snippet).

Read-only against Slack. Run from the worktree root with .env sourced.
"""
import csv
import json
import os
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

TOKEN = os.environ["SLACK_BOT_TOKEN"]
CHANNEL = "C02J4H23GR2"  # #photos-videos
MIN_EDGE = 800
OUT_DIR = Path(__file__).resolve().parent.parent / "migration" / "slack_photos"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def api(method: str, **params):
    url = f"https://slack.com/api/{method}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {TOKEN}"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.load(resp)
            if data.get("ok"):
                return data
            if data.get("error") == "ratelimited":
                time.sleep(int(resp.headers.get("Retry-After", 30)))
                continue
            raise RuntimeError(f"{method}: {data.get('error')}")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(int(e.headers.get("Retry-After", 30)))
                continue
            raise
    raise RuntimeError(f"{method}: retries exhausted")


def download(url: str, dest: Path) -> bool:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {TOKEN}"})
    try:
        with urllib.request.urlopen(req) as resp, open(dest, "wb") as f:
            f.write(resp.read())
        return True
    except Exception as e:  # noqa: BLE001 - log and continue, single file loss is fine
        print(f"  download failed {dest.name}: {e}")
        return False


user_cache: dict[str, str] = {}


def user_name(uid: str) -> str:
    if uid not in user_cache:
        try:
            u = api("users.info", user=uid)["user"]
            user_cache[uid] = u.get("real_name") or u.get("name") or uid
        except Exception:
            user_cache[uid] = uid
    return user_cache[uid]


def main():
    messages = []
    cursor = None
    while True:
        params = {"channel": CHANNEL, "limit": 200}
        if cursor:
            params["cursor"] = cursor
        r = api("conversations.history", **params)
        messages.extend(r["messages"])
        cursor = (r.get("response_metadata") or {}).get("next_cursor")
        print(f"history: {len(messages)} messages so far")
        if not cursor:
            break
        time.sleep(1.3)  # tier-3 method

    rows = []
    n_dl = 0
    for msg in messages:
        files = msg.get("files") or []
        imgs = [
            f
            for f in files
            if (f.get("mimetype") or "").startswith("image/")
            and max(f.get("original_w") or 0, f.get("original_h") or 0) >= MIN_EDGE
            and f.get("url_private_download")
        ]
        if not imgs:
            continue
        reactions = sum(rx.get("count", 0) for rx in msg.get("reactions") or [])
        ts = float(msg["ts"])
        date = time.strftime("%Y-%m-%d", time.localtime(ts))
        poster = user_name(msg.get("user", "")) if msg.get("user") else "unknown"
        text = re.sub(r"\s+", " ", msg.get("text") or "").strip()[:140]
        for i, f in enumerate(imgs):
            ext = (f.get("filetype") or "jpg").lower()
            name = f"{date}_{msg['ts'].replace('.', '-')}_{i}.{ext}"
            dest = OUT_DIR / name
            if not dest.exists():
                if not download(f["url_private_download"], dest):
                    continue
                n_dl += 1
                time.sleep(0.3)
            rows.append(
                {
                    "file": name,
                    "date": date,
                    "poster": poster,
                    "w": f.get("original_w"),
                    "h": f.get("original_h"),
                    "reactions": reactions,
                    "text": text,
                }
            )

    rows.sort(key=lambda r: (-int(r["reactions"]), r["date"]))
    with open(OUT_DIR / "manifest.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["file", "date", "poster", "w", "h", "reactions", "text"])
        w.writeheader()
        w.writerows(rows)
    print(f"done: {len(rows)} images in manifest, {n_dl} newly downloaded -> {OUT_DIR}")


if __name__ == "__main__":
    main()
