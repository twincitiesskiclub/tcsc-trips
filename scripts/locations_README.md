# Practice Location Data-Quality Pass

A three-step pipeline to clean up `practice_locations` in production: pull the
current data, geocode + verify it into a reviewable proposals file, then apply
the reviewed corrections. Nothing is written to prod until a human reviews the
proposals and explicitly runs the apply step with `--commit`.

The corrected `google_maps_url` (a coords-pinned map link) is what makes the
practice-announcement address tappable in Slack — see `_address_link()` in
`app/slack/blocks/announcements.py`.

Run everything from the repo root with the venv active:

```bash
source env/bin/activate
```

## Step 1 — Export (read-only)

```bash
python scripts/locations_export.py
```

Pulls every `practice_locations` row from prod plus its practice counts →
`scripts/output/locations_current.csv`, sorted with the most-used locations
first. Strictly read-only.

## Step 2 — Geocode + verify

```bash
python scripts/locations_geocode.py
```

Reads `locations_current.csv`, calls the Google Geocoding API (`GOOGLE_PLACES_API_KEY`
in `.env` — the **Geocoding API** must be enabled on that key's Cloud project, not
just Places), and writes `scripts/output/locations_proposed.csv`. Does NOT touch the
database.

For each row it either keeps the existing hand-placed coordinates (when the geocode
lands within ~150 m — those are spot-precise), backfills coordinates when the row had
none, or leaves coords alone and flags the row for a human. It builds the
`new_google_maps_url` from the **final** coordinates.

The `review` column tells you what to check:

| `review` flag    | meaning | your action |
|------------------|---------|-------------|
| `ok`             | existing spot-precise coords kept; address cleaned | spot-check, usually nothing |
| `verify_backfill`| row had no coords; coords backfilled from a **street-level** geocode (approximate) | glance at the pin; nudge to the real lot/trailhead if off |
| `needs_pin`      | input was vague/malformed, or the geocode disagreed with existing coords by >150 m | **drop a real pin** (see below) |
| `delete`         | row slated for deletion (id 30 "Unknown") | resolve its referencing practice first (see below) |

The script prints a summary of every non-`ok` row, e.g.:

```
14 need review: 32(needs_pin), 34(needs_pin), 30(delete), 29(verify_backfill),
31(needs_pin), 33(needs_pin), 39(verify_backfill), 40(verify_backfill),
42(verify_backfill), 43(verify_backfill), 45(needs_pin), 48(verify_backfill),
50(verify_backfill), 53(verify_backfill)
```

## Step 3 — Human review of `locations_proposed.csv` (REQUIRED before any write)

Open `scripts/output/locations_proposed.csv` and resolve the flagged rows:

- **`needs_pin`** (e.g. 32 Hyland/Jan's Place, 33 Carver Lake, 34 Wirth/Xerxes Field,
  45 Fort Snelling, 31 Afton/Valley Creek Trail): open Google Maps, find the exact
  spot (trailhead / lot / field), drop a pin, copy its `lat,lon`, and put those values
  in `new_lat` / `new_lon`. **Then update `new_google_maps_url` to match** the final
  coords:
  `https://www.google.com/maps/search/?api=1&query=LAT,LON`.

- **`verify_backfill`** (ids 29, 39, 40, 42, 43, 48, 50, 53): the coords are a
  plausible street-level geocode but unverified. Click the `new_google_maps_url` and
  confirm the pin is at the practice spot, not just the street address. If it's off
  (e.g. id 42 Wabun Picnic Area backfilled to the Minnehaha Falls pin), correct
  `new_lat`/`new_lon` and the URL the same way as `needs_pin`.

- **`delete` — id 30 "Unknown":** this location has no real data and is slated for
  deletion, but a **future scheduled** practice still references it: **#47
  (2026-03-10, "Lakes Run")**. The apply step will REFUSE to delete a location with a
  non-cancelled reference. Before deleting, reassign #47 to a real location in the
  admin UI (`/admin/practices`), changing its location to the correct venue. The
  cancelled practice (#38) is auto-nulled by the script. Once #47 is moved, the delete
  will go through on the next apply run.

- **Possible duplicates** (e.g. ids 35 Hyland/Visitor Center and 37 Hyland/Stadium
  Area share an address + coords but are genuinely ~1 km apart): decide per pair.
  - To **merge** (collapse into one), set `op=merge` on the redundant row and add a
    `merge_into_id` column whose value is the canonical location's `id`. The apply
    step repoints that location's practices to the canonical id, then deletes the
    redundant row.
  - To **keep both as distinct spots**, leave `op=update` on each and give each its
    own corrected `new_lat`/`new_lon` (and matching URL) so they pin different places.

- **`spot` cleanup** (ids 42, 48 have `spot` duplicating `name`): optional. Note that
  the apply step updates only `address`, `latitude`, `longitude`, and
  `google_maps_url` — it does **not** write `spot`, `name`, or `parking_notes`. If you
  want to fix those, edit them in the admin UI.

## Step 4 — Apply (dry-run first, then commit)

```bash
python scripts/locations_apply.py            # dry run — prints a before/after diff, writes NOTHING
```

Review the diff carefully. Every row will show a change on the first run (the
geocoder appends ", USA" to addresses and fills in the previously-empty
`google_maps_url`). The `[delete 30]` line stays `REFUSED` until you've reassigned
practice #47.

When the diff looks right:

```bash
python scripts/locations_apply.py --commit   # writes to prod
```

On any mid-run error the script rolls back and prints `ABORTED — no changes written`,
so it's all-or-nothing.

## Step 5 — Verify

```bash
python scripts/locations_apply.py            # re-run dry-run
```

All `update` rows should now report `no change` (their proposed values already match
prod) — that's the idempotency check. Note the `delete` row is the exception: once id
30 is gone it no longer prints "no change", and if #47 was never reassigned it will
still show `REFUSED` — handle that row on its own.

Finally, confirm the live result: re-post a test practice announcement to the test
channel `C07G9RTMRT3` and check that the address renders as a tappable link opening a
map pin at the correct spot.
