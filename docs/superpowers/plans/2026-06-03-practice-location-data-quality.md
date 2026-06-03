# Practice Location Data Quality + Clickable Address Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the practice-announcement address a clickable maps link, and run a verified, staged data-quality pass over the 24 `practice_locations` rows in production.

**Architecture:** A self-contained code change in the Slack block builder adds an `_address_link()` helper with a fallback chain (stored URL → coords-pinned URL → address-search URL → skip). A separate, three-script data pipeline (export → geocode/verify → apply) stages every correction to a reviewed CSV before any `--commit` write touches production. Coordinates are kept when hand-placed and spot-precise, geocoded only when missing or malformed.

**Tech Stack:** Python 3.12, Flask/SQLAlchemy, Slack Block Kit (mrkdwn), `psycopg2` (prod DB), `requests` + Google Geocoding API, `python-dotenv`, pytest.

---

## File Structure

**Code (Component 1):**
- Modify: `app/slack/blocks/announcements.py` — add `_address_link()`; use it in `build_practice_announcement_blocks` (~line 167) and `build_combined_lift_blocks` (~line 400).
- Test: `tests/slack/test_address_link.py` (new) — unit tests for the fallback chain.

**Data tooling (Components 2 & 3):**
- Create: `scripts/locations_export.py` — read-only prod pull → `scripts/output/locations_current.csv`.
- Create: `scripts/locations_geocode.py` — geocode/verify → `scripts/output/locations_proposed.csv`.
- Create: `scripts/locations_apply.py` — apply reviewed CSV to prod (dry-run default, `--commit`).
- Create: `scripts/locations_README.md` — run order + review instructions.

**Shared facts (used by every script):**
- Prod DSN (same as `test_practice_post.py`): `postgresql://heidi:c1y7XzSne5jVDEOVRBy4ODUoHWDJv8jK@dpg-d4nrbauuk2gs73frosqg-a.oregon-postgres.render.com/tcsc_trips_db_6k97`
- Geocoding key: `GOOGLE_PLACES_API_KEY` in `.env` (works for the Geocoding API when that API is enabled on the key).
- Coords-pinned URL format: `https://www.google.com/maps/search/?api=1&query={lat},{lon}`

---

## Task 1: `_address_link()` helper + clickable address in both builders

**Files:**
- Modify: `app/slack/blocks/announcements.py`
- Test: `tests/slack/test_address_link.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/slack/test_address_link.py`:

```python
"""Tests for the clickable-address helper in practice announcements."""

from urllib.parse import quote_plus

from app.practices.interfaces import PracticeLocationInfo
from app.slack.blocks.announcements import _address_link


def _loc(**kw) -> PracticeLocationInfo:
    base = dict(id=1, name="Theodore Wirth")
    base.update(kw)
    return PracticeLocationInfo(**base)


def test_uses_stored_google_maps_url_when_present():
    loc = _loc(
        address="1221 Theodore Wirth Pkwy, Minneapolis, MN 55422",
        google_maps_url="https://maps.app.goo.gl/abc123",
        latitude=44.99, longitude=-93.32,
    )
    result = _address_link(loc)
    assert result == "<https://maps.app.goo.gl/abc123|1221 Theodore Wirth Pkwy, Minneapolis, MN 55422>"


def test_falls_back_to_coords_pin_when_no_url():
    loc = _loc(
        address="1221 Theodore Wirth Pkwy, Minneapolis, MN 55422",
        google_maps_url=None,
        latitude=44.991258, longitude=-93.32639,
    )
    result = _address_link(loc)
    assert result == (
        "<https://www.google.com/maps/search/?api=1&query=44.991258,-93.32639"
        "|1221 Theodore Wirth Pkwy, Minneapolis, MN 55422>"
    )


def test_falls_back_to_address_search_when_no_url_or_coords():
    loc = _loc(address="8100 Grimm Rd", google_maps_url=None, latitude=None, longitude=None)
    result = _address_link(loc)
    assert result == (
        f"<https://www.google.com/maps/search/?api=1&query={quote_plus('8100 Grimm Rd')}"
        "|8100 Grimm Rd>"
    )


def test_returns_none_when_no_address():
    loc = _loc(address=None, google_maps_url=None, latitude=None, longitude=None)
    assert _address_link(loc) is None


def test_url_never_expands_label_is_address():
    loc = _loc(address="RJGJ+J9 Bloomington, Minnesota",
               google_maps_url=None, latitude=44.826683, longitude=-93.369113)
    result = _address_link(loc)
    # Label (visible text) is always the address; URL is hidden behind the pipe.
    assert result.endswith("|RJGJ+J9 Bloomington, Minnesota>")
    assert result.startswith("<https://www.google.com/maps/search/?api=1&query=44.826683,-93.369113")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/slack/test_address_link.py -v`
Expected: FAIL with `ImportError: cannot import name '_address_link'`

- [ ] **Step 3: Add the helper**

In `app/slack/blocks/announcements.py`, add `quote_plus` to imports at the top:

```python
from urllib.parse import quote_plus
```

Then add this function near `_get_day_suffix` (after the imports, before `build_practice_announcement_blocks`):

```python
def _address_link(location) -> Optional[str]:
    """Return mrkdwn for the Address field: the address string as a clickable link.

    Fallback chain so the address is tappable even when google_maps_url is unset.
    The visible label is always the address text; the URL never expands inline.
    Returns None when there is no address to show.
    """
    address = getattr(location, "address", None)
    if not address:
        return None

    url = getattr(location, "google_maps_url", None)
    if not url:
        lat = getattr(location, "latitude", None)
        lon = getattr(location, "longitude", None)
        if lat is not None and lon is not None:
            url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
        else:
            url = f"https://www.google.com/maps/search/?api=1&query={quote_plus(address)}"

    return f"<{url}|{address}>"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/slack/test_address_link.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Use the helper in `build_practice_announcement_blocks`**

In `app/slack/blocks/announcements.py`, replace the Address field block (currently ~lines 167-171):

```python
    if practice.location and practice.location.address:
        location_fields.append({
            "type": "mrkdwn",
            "text": f"*:world_map: Address*\n{practice.location.address}"
        })
```

with:

```python
    address_md = _address_link(practice.location) if practice.location else None
    if address_md:
        location_fields.append({
            "type": "mrkdwn",
            "text": f"*:world_map: Address*\n{address_md}"
        })
```

- [ ] **Step 6: Use the helper in `build_combined_lift_blocks`**

In the same file, replace the Address field block in the combined-lift builder (currently ~lines 400-404):

```python
    if location and location.address:
        location_fields.append({
            "type": "mrkdwn",
            "text": f"*:world_map: Address*\n{location.address}"
        })
```

with:

```python
    address_md = _address_link(location) if location else None
    if address_md:
        location_fields.append({
            "type": "mrkdwn",
            "text": f"*:world_map: Address*\n{address_md}"
        })
```

- [ ] **Step 7: Run the full slack test suite to confirm no regressions**

Run: `pytest tests/slack/ -v`
Expected: PASS (all existing tests + 5 new)

- [ ] **Step 8: Commit**

```bash
git add app/slack/blocks/announcements.py tests/slack/test_address_link.py
git commit -m "feat(slack): make practice announcement address a clickable maps link

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: `locations_export.py` — read-only prod pull

**Files:**
- Create: `scripts/locations_export.py`
- Output: `scripts/output/locations_current.csv`

- [ ] **Step 1: Write the export script**

Create `scripts/locations_export.py`:

```python
"""Read-only export of practice_locations from production for the data-quality pass.

Pulls every row plus its referencing-practice count, writes a CSV sorted with the
most-used locations first so review effort goes where it matters. READ ONLY — never
writes to the database.

Usage:
    python scripts/locations_export.py
Writes: scripts/output/locations_current.csv
"""

import csv
import os

import psycopg2

PROD_DB_URL = (
    "postgresql://heidi:c1y7XzSne5jVDEOVRBy4ODUoHWDJv8jK"
    "@dpg-d4nrbauuk2gs73frosqg-a.oregon-postgres.render.com/tcsc_trips_db_6k97"
)

OUT_PATH = os.path.join(os.path.dirname(__file__), "output", "locations_current.csv")

FIELDS = [
    "id", "name", "spot", "address", "google_maps_url",
    "latitude", "longitude", "parking_notes",
    "practice_count", "active_practice_count",
]


def main() -> None:
    conn = psycopg2.connect(PROD_DB_URL)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT pl.id, pl.name, pl.spot, pl.address, pl.google_maps_url,
               pl.latitude, pl.longitude, pl.parking_notes,
               COUNT(p.id) AS practice_count,
               COUNT(p.id) FILTER (WHERE p.status <> 'cancelled') AS active_count
        FROM practice_locations pl
        LEFT JOIN practices p ON p.location_id = pl.id
        GROUP BY pl.id
        ORDER BY active_count DESC, practice_count DESC, pl.id
        """
    )
    rows = cur.fetchall()
    conn.close()

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(FIELDS)
        writer.writerows(rows)

    print(f"Exported {len(rows)} locations to {OUT_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the export**

Run: `source env/bin/activate && python scripts/locations_export.py`
Expected: `Exported 24 locations to .../scripts/output/locations_current.csv`

- [ ] **Step 3: Eyeball the output**

Run: `head -3 scripts/output/locations_current.csv`
Expected: header row + the two most-active locations (Balance Fitness Studio, Theodore Wirth/Trailhead Bridge) first.

- [ ] **Step 4: Commit (script only — output CSV is git-ignored data)**

```bash
git add scripts/locations_export.py
git commit -m "feat(scripts): read-only export of practice_locations for data-quality pass

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: `locations_geocode.py` — geocode, verify coords, build proposed CSV

**Files:**
- Create: `scripts/locations_geocode.py`
- Input: `scripts/output/locations_current.csv`
- Output: `scripts/output/locations_proposed.csv`

- [ ] **Step 1: Write the geocode/verify script**

Create `scripts/locations_geocode.py`:

```python
"""Geocode + verify practice locations into a reviewable proposals CSV.

Reads scripts/output/locations_current.csv. For each row, calls the Google
Geocoding API to produce a cleaned canonical address and candidate coordinates,
then decides what to propose:

  - Keep existing hand-placed coords when they're within KEEP_RADIUS_M of the
    geocoded candidate (spot-precise; better than a street-level geocode).
  - Backfill coords from the geocode when the row has none.
  - Flag malformed/vague inputs for manual pinning rather than trusting the geocode.

Builds the coords-pinned google_maps_url from the FINAL proposed coordinates.
Does NOT touch the database. Review the output, then run locations_apply.py.

Usage:
    python scripts/locations_geocode.py
Writes: scripts/output/locations_proposed.csv
"""

import csv
import math
import os

import requests
from dotenv import load_dotenv

load_dotenv()

IN_PATH = os.path.join(os.path.dirname(__file__), "output", "locations_current.csv")
OUT_PATH = os.path.join(os.path.dirname(__file__), "output", "locations_proposed.csv")

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
KEEP_RADIUS_M = 150.0  # existing coords within this of the geocode are kept as-is

# Rows whose address is too vague/malformed to trust the geocode — needs human pin.
NEEDS_PIN_IDS = {30, 32, 33, 34, 45}

# id 30 "Unknown" is slated for deletion (see plan Task 5 / spec edge cases).
DELETE_IDS = {30}

OUT_FIELDS = [
    "id", "name", "spot", "practice_count", "active_practice_count", "op", "review",
    "cur_address", "new_address",
    "cur_lat", "cur_lon", "new_lat", "new_lon",
    "coord_delta_m", "new_google_maps_url", "notes",
]


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def pin_url(lat, lon) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"


def geocode(query: str, api_key: str):
    """Return (formatted_address, lat, lon) or (None, None, None)."""
    if not query:
        return None, None, None
    resp = requests.get(
        GEOCODE_URL, params={"address": query, "key": api_key}, timeout=15
    )
    data = resp.json()
    if data.get("status") != "OK" or not data.get("results"):
        return None, None, None
    top = data["results"][0]
    loc = top["geometry"]["location"]
    return top.get("formatted_address"), loc["lat"], loc["lng"]


def _f(v):
    return float(v) if v not in (None, "", "None") else None


def main() -> None:
    api_key = os.environ["GOOGLE_PLACES_API_KEY"]

    with open(IN_PATH, newline="") as f:
        rows = list(csv.DictReader(f))

    out = []
    for r in rows:
        loc_id = int(r["id"])
        cur_lat, cur_lon = _f(r["latitude"]), _f(r["longitude"])
        # Query Google with name+spot+address for the best match on POIs/parks.
        query = ", ".join(p for p in (r["name"], r["spot"], r["address"]) if p)
        g_addr, g_lat, g_lon = geocode(query, api_key)

        delta = ""
        new_lat, new_lon = cur_lat, cur_lon
        notes = []

        if cur_lat is not None and g_lat is not None:
            d = haversine_m(cur_lat, cur_lon, g_lat, g_lon)
            delta = round(d, 1)
            if d <= KEEP_RADIUS_M:
                notes.append("kept existing spot coords (within radius)")
            else:
                notes.append(f"geocode differs by {round(d)}m — verify which is the real spot")
        elif cur_lat is None and g_lat is not None:
            new_lat, new_lon = round(g_lat, 6), round(g_lon, 6)
            notes.append("backfilled coords from geocode (street-level, verify spot)")
        elif g_lat is None:
            notes.append("geocode returned no result")

        # Decide op + review flag.
        if loc_id in DELETE_IDS:
            op, review = "delete", "delete"
        elif loc_id in NEEDS_PIN_IDS:
            op, review = "update", "needs_pin"
        elif new_lat is None:
            op, review = "update", "missing_coords"
        elif delta != "" and delta > KEEP_RADIUS_M:
            op, review = "update", "needs_pin"
        else:
            op, review = "update", "ok"

        new_url = pin_url(new_lat, new_lon) if new_lat is not None else ""

        out.append({
            "id": loc_id,
            "name": r["name"],
            "spot": r["spot"],
            "practice_count": r["practice_count"],
            "active_practice_count": r["active_practice_count"],
            "op": op,
            "review": review,
            "cur_address": r["address"],
            "new_address": g_addr or r["address"],
            "cur_lat": cur_lat if cur_lat is not None else "",
            "cur_lon": cur_lon if cur_lon is not None else "",
            "new_lat": new_lat if new_lat is not None else "",
            "new_lon": new_lon if new_lon is not None else "",
            "coord_delta_m": delta,
            "new_google_maps_url": new_url,
            "notes": "; ".join(notes),
        })

    with open(OUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUT_FIELDS)
        writer.writeheader()
        writer.writerows(out)

    flagged = [o for o in out if o["review"] not in ("ok",)]
    print(f"Wrote {len(out)} proposals to {OUT_PATH}")
    print(f"{len(flagged)} need review: " +
          ", ".join(f"{o['id']}({o['review']})" for o in flagged))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the geocode pass**

Run: `source env/bin/activate && python scripts/locations_geocode.py`
Expected: `Wrote 24 proposals to .../locations_proposed.csv` and a list of flagged rows including `30(delete)`, `32(needs_pin)`, `33(needs_pin)`, `34(needs_pin)`, `45(needs_pin)`.

- [ ] **Step 3: Sanity-check a known row**

Run: `grep "^36," scripts/output/locations_proposed.csv`
Expected: Theodore Wirth/Trailhead Bridge keeps its existing coords (`coord_delta_m` small, `review=ok`, `new_google_maps_url` built from 44.991258,-93.32639).

- [ ] **Step 4: Commit (script only)**

```bash
git add scripts/locations_geocode.py
git commit -m "feat(scripts): geocode + coord-verify practice locations into proposals CSV

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: `locations_apply.py` — idempotent, dry-run-default writer

**Files:**
- Create: `scripts/locations_apply.py`
- Input: `scripts/output/locations_proposed.csv` (after human review)

- [ ] **Step 1: Write the apply script**

Create `scripts/locations_apply.py`:

```python
"""Apply reviewed practice-location corrections to production.

Reads scripts/output/locations_proposed.csv (AFTER human review). Dry-run by
default — prints a before/after diff and makes NO changes. Pass --commit to write.
Idempotent: re-running after a successful commit produces no further changes.

Supported ops (the 'op' column):
  update  -> UPDATE practice_locations SET address/latitude/longitude/google_maps_url
  delete  -> NULL location_id on cancelled practices, then DELETE the location.
             REFUSES if a non-cancelled practice still references it.
  merge   -> repoint practices.location_id from this row to 'merge_into_id',
             then DELETE this row. (merge_into_id added by reviewer.)

Usage:
    python scripts/locations_apply.py            # dry run
    python scripts/locations_apply.py --commit   # write to prod
"""

import csv
import os
import sys

import psycopg2

PROD_DB_URL = (
    "postgresql://heidi:c1y7XzSne5jVDEOVRBy4ODUoHWDJv8jK"
    "@dpg-d4nrbauuk2gs73frosqg-a.oregon-postgres.render.com/tcsc_trips_db_6k97"
)
IN_PATH = os.path.join(os.path.dirname(__file__), "output", "locations_proposed.csv")


def _f(v):
    return float(v) if v not in (None, "", "None") else None


def apply_update(cur, row, commit, log):
    loc_id = int(row["id"])
    cur.execute(
        "SELECT address, latitude, longitude, google_maps_url "
        "FROM practice_locations WHERE id = %s", (loc_id,))
    before = cur.fetchone()
    if before is None:
        log.append(f"[update {loc_id}] SKIP — row not found")
        return
    new = (row["new_address"] or None, _f(row["new_lat"]), _f(row["new_lon"]),
           row["new_google_maps_url"] or None)
    if tuple(before) == new:
        log.append(f"[update {loc_id}] no change")
        return
    log.append(f"[update {loc_id}] {before} -> {new}")
    if commit:
        cur.execute(
            "UPDATE practice_locations "
            "SET address=%s, latitude=%s, longitude=%s, google_maps_url=%s WHERE id=%s",
            (*new, loc_id))


def apply_delete(cur, row, commit, log):
    loc_id = int(row["id"])
    cur.execute(
        "SELECT id, status FROM practices WHERE location_id = %s", (loc_id,))
    refs = cur.fetchall()
    blocking = [pid for pid, status in refs if status != "cancelled"]
    if blocking:
        log.append(f"[delete {loc_id}] REFUSED — non-cancelled practices still "
                   f"reference it: {blocking}. Reassign them first.")
        return
    log.append(f"[delete {loc_id}] null {len(refs)} cancelled practice refs, then delete")
    if commit:
        cur.execute(
            "UPDATE practices SET location_id = NULL WHERE location_id = %s", (loc_id,))
        cur.execute("DELETE FROM practice_locations WHERE id = %s", (loc_id,))


def apply_merge(cur, row, commit, log):
    loc_id = int(row["id"])
    into = row.get("merge_into_id")
    if not into:
        log.append(f"[merge {loc_id}] SKIP — no merge_into_id set by reviewer")
        return
    into = int(into)
    cur.execute(
        "SELECT COUNT(*) FROM practices WHERE location_id = %s", (loc_id,))
    n = cur.fetchone()[0]
    log.append(f"[merge {loc_id}] repoint {n} practices to {into}, then delete {loc_id}")
    if commit:
        cur.execute(
            "UPDATE practices SET location_id = %s WHERE location_id = %s", (into, loc_id))
        cur.execute("DELETE FROM practice_locations WHERE id = %s", (loc_id,))


HANDLERS = {"update": apply_update, "delete": apply_delete, "merge": apply_merge}


def main() -> None:
    commit = "--commit" in sys.argv[1:]
    with open(IN_PATH, newline="") as f:
        rows = list(csv.DictReader(f))

    conn = psycopg2.connect(PROD_DB_URL)
    cur = conn.cursor()
    log = []
    for row in rows:
        op = (row.get("op") or "update").strip()
        handler = HANDLERS.get(op)
        if handler is None:
            log.append(f"[{op} {row['id']}] SKIP — unknown op")
            continue
        handler(cur, row, commit, log)

    if commit:
        conn.commit()
    conn.close()

    print("\n".join(log))
    print(f"\n{'COMMITTED' if commit else 'DRY RUN (no changes)'} — {len(rows)} rows processed")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Dry-run against prod (no writes)**

Run: `source env/bin/activate && python scripts/locations_apply.py`
Expected: a before/after diff per row, ending with `DRY RUN (no changes) — 24 rows processed`. The `delete 30` line should show `REFUSED` until practice #47 is reassigned (it's a non-cancelled reference).

- [ ] **Step 3: Commit (script only)**

```bash
git add scripts/locations_apply.py
git commit -m "feat(scripts): idempotent dry-run-default apply for location corrections

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: README + human-review handoff (no auto-apply)

**Files:**
- Create: `scripts/locations_README.md`

- [ ] **Step 1: Write the runbook**

Create `scripts/locations_README.md`:

```markdown
# Practice Location Data-Quality Pass

Run order (all from repo root, with `source env/bin/activate`):

1. `python scripts/locations_export.py`
   → `scripts/output/locations_current.csv` (read-only pull from prod)

2. `python scripts/locations_geocode.py`
   → `scripts/output/locations_proposed.csv` (geocode + coord verification)

3. **Human review of `locations_proposed.csv`** — required before any write:
   - `review=needs_pin` (ids 32, 33, 34, 45): replace `new_lat`/`new_lon` with the
     exact spot coordinates (drop a pin in Google Maps at the real trailhead/lot,
     copy the lat,lon). The `new_google_maps_url` must match the final coords:
     `https://www.google.com/maps/search/?api=1&query=LAT,LON`.
   - `review=delete` (id 30 "Unknown"): first reassign the future practice **#47
     (2026-03-10 "Lakes Run")** to a real location id by editing
     `practices.location_id` in the admin UI (or note the target), because
     `locations_apply.py` refuses to delete a location with a non-cancelled
     reference. The cancelled #38 is auto-nulled.
   - Possible duplicates (ids 35 Visitor Center / 37 Stadium Area share
     address+coords): decide per pair. To MERGE, set `op=merge` on the redundant
     row and add a `merge_into_id` column with the canonical id. To KEEP BOTH,
     leave `op=update` and give each distinct `new_lat`/`new_lon`.
   - `spot == name` rows (ids 42, 48): fix the `spot` value if desired (optional;
     not applied by the script unless you add it — current script updates only
     address/coords/url).

4. `python scripts/locations_apply.py`            # dry run — review the diff
5. `python scripts/locations_apply.py --commit`   # write to prod
6. Re-run `python scripts/locations_apply.py` → confirms `no change` everywhere
   (idempotency check).

7. Verify live: re-post a test announcement to test channel `C07G9RTMRT3` and
   confirm the address renders as a tappable link to the correct pin.
```

- [ ] **Step 2: Commit**

```bash
git add scripts/locations_README.md
git commit -m "docs(scripts): runbook for the practice-location data-quality pass

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 3: STOP for human review (do not auto-apply)**

The export → geocode → review → apply loop requires human judgment (manual pins,
the #47 reassignment, duplicate decisions). After Tasks 1-5 land, hand the
`locations_proposed.csv` to the user and pause. Production writes happen only after
the user reviews and explicitly runs `locations_apply.py --commit`.

---

## Self-Review Notes

- **Spec coverage:** Component 1 (clickable address) → Task 1. Component 2 (export/geocode/apply) → Tasks 2-4. Component 3 (coord verification) → Task 3 (`haversine_m`, `KEEP_RADIUS_M`, delta flags). Edge cases: Unknown delete → Task 4 `apply_delete` + README #47 note; needs_pin → Task 3 `NEEDS_PIN_IDS` + README; duplicates → Task 4 `apply_merge` + README; 0-practice kept → no delete path for them; nothing auto-applied → Task 5 Step 3 stop gate. Testing → Task 1 unit tests + README live-verify step.
- **Type consistency:** `_address_link(location)` signature and the `query={lat},{lon}` URL format are identical across Task 1 helper, tests, and Task 3 `pin_url`. CSV column names (`new_lat`, `new_lon`, `new_address`, `new_google_maps_url`, `op`, `merge_into_id`) match between `locations_geocode.py` output and `locations_apply.py` input.
- **No placeholders:** every code step is complete and runnable.
```
