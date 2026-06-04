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
        elif cur_lat is None:
            # Coords were backfilled from a street-level geocode — plausible but
            # unverified; surface for a human glance rather than silently "ok".
            op, review = "update", "verify_backfill"
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
