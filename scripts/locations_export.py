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
