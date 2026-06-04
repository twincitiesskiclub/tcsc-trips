# Practice Location Data Quality + Clickable Address — Design

**Date:** 2026-06-03
**Status:** Approved (brainstorming)

## Problem

Members can't tap the practice location in the Slack announcement to navigate there.
Two root causes, one underlying gap:

1. **Rendering:** The "Address" field at the bottom of the practice announcement renders
   as plain text (`announcements.py:167-171` and `:400-404`).
2. **Data:** `google_maps_url` is `NULL` for **all 24** `practice_locations` rows, and
   several addresses are malformed (plus-codes, intersections, missing city/zip) or missing
   coordinates entirely.

This is two coordinated changes: a small code change to make the address a clickable link,
and a verified data-quality pass over `practice_locations` in production.

## Goals

- The address in the practice announcement is a **clickable link** whose visible text stays
  the address string and whose target pins the **exact spot's coordinates**. The URL never
  expands inline, and this is the **only** place the link is rendered.
- Every `practice_locations` row has a working `google_maps_url`, a clean `address`,
  verified `latitude`/`longitude`, and sane `spot`/`parking_notes`/`name`.
- Nothing is written to production until the staged corrections are reviewed and explicitly
  applied with `--commit`.

## Non-goals

- No change to the social-location rendering or any other surface that shows an address.
- No re-resolution of locations to canonical Google Places (would collapse spot precision).
- No investigation/fix of why many locations have 0 referencing practices (assumed a
  separate linking bug; out of scope — see Edge Cases).

## Approach: B (populate `google_maps_url` + render fallback)

The data pass fills `google_maps_url` derived from the **corrected spot coordinates**, cleans
address strings, and backfills missing coordinates via the Google **Geocoding** API. The block
builder links to `google_maps_url` when present and otherwise derives a link at render time, so
rendering is robust even where data is still imperfect.

## Component 1 — Clickable address (code)

File: `app/slack/blocks/announcements.py`. `PracticeLocationInfo` already carries `address`,
`google_maps_url`, `latitude`, `longitude` (verified in `service.py:51-61`), so the change is
self-contained — no plumbing.

Add a helper:

```python
def _address_link(location) -> Optional[str]:
    """Return mrkdwn for the Address field: the address text linked to a maps URL.
    Fallback chain so the address is clickable even when google_maps_url is unset."""
```

Fallback chain (visible label is always the address string):

1. `google_maps_url` set → `<google_maps_url|address>`
2. else `latitude`/`longitude` set → `<https://www.google.com/maps/search/?api=1&query={lat},{lon}|address>`
3. else `address` set → `<https://www.google.com/maps/search/?api=1&query={urlencoded address}|address>`
4. else → no Address field (unchanged "skip" behavior)

Apply in both `build_practice_announcement_blocks` (~line 167) and
`build_combined_lift_blocks` (~line 400), replacing the plain-text Address field. The field
label (`*:world_map: Address*`) is unchanged.

## Component 2 — Data tooling (`scripts/`)

Three small, single-purpose scripts. Prod connection string is the one already in
`test_practice_post.py` (read for export, write only on `--commit`).

- **`scripts/locations_export.py`** — read-only pull of all `practice_locations` rows →
  `scripts/output/locations_current.csv`. Also emits, per location, the count of referencing
  practices and (for review ordering) sorts active locations first.

- **`scripts/locations_geocode.py`** — for each row, call Google Geocoding API (`GOOGLE_PLACES_API_KEY`
  in `.env`) to produce a cleaned canonical `address`, backfill missing lat/lon, and build the
  coords-pinned `google_maps_url`. Writes `scripts/output/locations_proposed.csv` with
  current-vs-proposed columns plus flags (see Component 3). Does **not** touch the DB.

- **`scripts/locations_apply.py`** — applies the reviewed `locations_proposed.csv` to prod.
  **Dry-run by default**; `--commit` to write. Idempotent (`UPDATE … WHERE id=`; re-running is a
  no-op). Handles three operation types from a `op` column: `update` (field corrections),
  `delete` (with FK reassignment, see Edge Cases), `merge` (repoint practices to canonical id,
  then delete redundant row). Logs a before/after diff per row.

## Component 3 — Coordinate verification

For each location, `locations_geocode.py` does a round-trip:

- **Forward-geocode** the cleaned address → candidate coords.
- Compute `coord_delta_m` = great-circle distance between existing lat/lon and the candidate.
- **Keep existing** coords when `coord_delta_m < ~150 m` — they're hand-placed at the real
  trailhead and more spot-precise than a geocoded street address.
- **Flag `needs_review`** when the delta is large, when coords were missing, or when the input
  address is malformed/vague (manual-pin cases below).
- The final `google_maps_url` is built from the **agreed** lat/lon, preserving spot precision.

Output columns include: `id`, `name`, `spot`, `practice_count`, `op`, current vs proposed
`address`/`lat`/`lon`/`google_maps_url`, `coord_delta_m`, and a `review` flag with a reason
(`ok` / `needs_pin` / `possible_duplicate` / `missing_coords` / `delete`).

## Edge cases & decisions

- **id 30 "Unknown" → delete.** Referenced by 2 practices: #38 (cancelled, 2026-02-24) — null
  its `location_id`; and **#47 (scheduled, 2026-03-10, "Lakes Run")** — a *future* practice that
  must be reassigned to a real location **before** deletion. The export surfaces both; #47's
  reassignment target is a human decision captured in the review file. `locations_apply.py`
  refuses to delete a location still referenced by a non-cancelled practice.

- **Vague / malformed addresses → manual pin.** id 45 Fort Snelling ("St. Paul, Minneapolis"),
  id 34 Theodore Wirth (intersection string), id 33 Carver Lake (no city/zip), and the
  plus-code id 32 Hyland/Jan's Place. Flagged `needs_pin`; geocode proposes a best guess but
  the user supplies/confirms exact spot coords in the review file rather than trusting the
  automated result.

- **Same address+coords pairs → distinguish, don't auto-merge.** id 35 (Hyland/Visitor Center)
  and id 37 (Hyland/Stadium Area) share address+coords but are genuinely different spots
  (~1 km apart). Flagged `possible_duplicate`; the user chooses per pair: **merge** (repoint +
  delete redundant) or **keep both with distinct corrected coords**. No blind merge.

- **`spot` == `name` duplication** (id 42 Minnehaha-Wabun, id 48 Richardson): flagged for a
  trivial `spot` cleanup the user confirms.

- **0-practice locations are kept.** Their unused-ness is assumed to be a separate linking bug,
  not a reason to delete. Only "Unknown" (delete) and any confirmed duplicate (merge) are
  removed; all other singletons stay and still get the quality pass.

- **Nothing auto-applied.** Prod writes happen only after the staged file is reviewed and only
  via `locations_apply.py --commit`.

## Testing

- Unit tests for `_address_link` covering all four fallback branches (url / coords / address /
  none), added to `tests/slack/`. Assert the URL never expands and the label equals the address.
- `locations_apply.py` dry-run reviewed before any commit; a second apply run is a verified
  no-op (idempotency).
- Manual spot-check: re-post a test announcement (test channel `C07G9RTMRT3`) and confirm the
  address renders as a tappable link to the correct pin.

## Rollout

1. Ship the code change (Component 1) + unit tests — safe on its own; falls back gracefully
   while `google_maps_url` is still null.
2. Export → geocode → **user reviews `locations_proposed.csv`** (resolve `needs_pin`,
   `possible_duplicate`, and #47's reassignment).
3. `locations_apply.py` dry-run → review diff → `--commit`.
4. Verify a live announcement renders the corrected, clickable address.
