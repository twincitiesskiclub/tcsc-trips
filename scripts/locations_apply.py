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
    try:
        for row in rows:
            op = (row.get("op") or "update").strip()
            handler = HANDLERS.get(op)
            if handler is None:
                log.append(f"[{op} {row['id']}] SKIP — unknown op")
                continue
            handler(cur, row, commit, log)
        if commit:
            conn.commit()
    except Exception as exc:
        conn.rollback()
        print("\n".join(log))
        print(f"\nABORTED — no changes written ({exc})")
        sys.exit(1)
    finally:
        conn.close()

    print("\n".join(log))
    print(f"\n{'COMMITTED' if commit else 'DRY RUN (no changes)'} — {len(rows)} rows processed")


if __name__ == "__main__":
    main()
