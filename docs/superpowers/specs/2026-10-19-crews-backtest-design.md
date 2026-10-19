# Crews backtest dashboard

Date: 2026-10-19. Branch `crews-backtest`.

## Why

Mitchell built the 2026 Fall/Winter crews in the crew tool (`/admin/crews/season/14`)
and posts them to the team on 2026-10-20. Crews have two jobs:

1. **Practice splitting.** A coach says "split into your crews" and each crew trains
   as a group. A crew works for this when **4 or more** of its members are at that
   practice (Rob's number).
2. **A smaller community inside TCSC.** Size at practice does not matter for this job.

The decision this dashboard feeds, in Rob's words to Mitchell: "if the data is
neutral-ish or better, we just go with 12. If the data says there is a strong
imbalance, we should consider going to like 10 crews." Mitchell likes 12 because
bigger crews grow cliques, and he can pair crews for any practice that needs
bigger groups. His bar: "as long as no crew is >5 non-checkers I'm not too
worried." He also notes fall turnout does not always predict winter.

A quick read-only check of Draft 13 (12 crews of about 12) against the 11
practices since 9/15 found 2.7 people per crew per practice, and 27% of
crew-practices reached 4.

## Goals

- A new "Crews" dashboard on `/admin/analytics`, built the same way as the others
  (one module in `app/analytics/dashboards/`, one line in the registry).
- For a chosen draft: each crew's turnout at each practice this season, how often
  it reached 4, and how many of its members never checked in this season
  ("non-checkers"), with any crew over 5 non-checkers flagged.
- Imbalance at a glance: whether some crews are reliably full while others are
  reliably empty.
- Fewer crews by **pairing** Mitchell's crews. A pair is two whole crews joined, so
  no person moves and every hand swap survives. This is also how Mitchell would
  make "crew pairs" at a practice.

KISS. One page, two inputs, no recommendation text. People read the numbers and
decide.

## Non-goals

- Saving a merge. Pairings are a what-if on the dashboard only.
- Merging three or more crews into one.
- A "typical merge" line or any luck/overfitting analysis. The page shows the best
  pairing at each count and says in the note that it was picked on these
  practices.
- Any change to the crew tool, its pages, its engine or its Slack launch.
- Judging the community job, or forecasting winter turnout.

## Anti-goals

- **Writing to `crew_drafts` or `crew_configs`.** Mitchell is still editing his
  drafts. The dashboard only reads them. A test proves a dashboard render leaves
  every draft row unchanged.
- Crew numbers that differ from the crew tool's. Crew 3 here is crew 3 there.
- Real member names, emails or Slack IDs in committed fixtures. The repo is public.

## Data

**Crews.** `CrewDraft.members` is a snapshot list. Each entry has `user_id`,
`crew` (1-based), `name` and the balance traits. `CrewDraft.crew_names` maps `"1"`
to a display name when one was set. `CrewDraft.rules` holds
`together`/`apart`/`pin` rules. `CrewDraft.settings.crews` is the crew count.

**Practices.** `practice_sessions` rows with `kind = 'practice'`,
`status = 'held'`, `reported_count IS NULL`, date on or before today, and
`season_label` equal to the draft's `Season.name`. Today that is 11 sessions,
9/15 to 10/15. A day with two sessions counts each session on its own.

**Who was there.** `practice_attendance` rows with role `rsvp`, `lead` or `coach`,
counted once per (session, user_id). `plan` and `decline` do not count. Members
match by `user_id`. All 144 members of Draft 13 match today.

**Non-checker.** A crew member with zero counted attendance across those sessions.

These are RSVPs, not confirmed headcounts. The note says so.

## Inputs (GET params)

- `draft`: a `CrewDraft.id`. Default: the season's `final` draft if one exists,
  else the most recently updated draft of the current season (Draft 13 today).
- `crews`: crew count after pairing, from `ceil(n / 2)` to `n` where `n` is the
  draft's crew count. Default `n` (no pairing).

Invalid values fall back to the default. The shared season/date filters do not
apply: the draft fixes the season. How these plug into the route is the
builder's call (`base.parse_filters` only handles the fixed `FIELDS` today).

## Pairing

To go from `n` crews to `k`, join `n - k` pairs and leave the rest alone. A paired
crew's turnout at a practice is the sum of its two crews' turnout. Pick the
pairing that:

1. Breaks the fewest `apart` rules. An `apart` pair already in the same original
   crew is broken in the draft itself, so it does not count here and the note
   lists it.
2. Has the highest share of (crew, practice) pairs with 4 or more people.
3. Breaks ties by the crew engine's balance score (`engine.score` with
   `Settings(crews=k, levels=..., board_rule=...)` from the draft). Lower wins.

Deterministic. For 12 crews the largest case is about 62,000 pairings (k=7), so
exhaustive search over precomputed per-crew turnout is fine. The builder may
search smarter if the result is the same.

Paired crews are labelled by their originals, e.g. "3 + 7", using `crew_names`
where set.

## What the page shows

Top to bottom, using the existing `Tiles` / `Chart` / `Table` / `Note` blocks.

1. **Tiles** at the selected count: crews, people per crew, practices counted,
   average people per crew per practice, share of crew-practices with 4+, and
   crews with more than 5 non-checkers.
2. **Crew count chart.** One line: the 4+ share for every count from
   `ceil(n/2)` to `n`, best pairing at each. Nothing else on it.
3. **Crew by practice grid.** One row per crew, one column per practice, cell =
   headcount. Cells under 4 stand out. Crews sorted by crew number, so a reliably
   empty row is easy to spot.
4. **Crew table.** Crew label, size, non-checkers (flag over 5), average turnout,
   share of practices at 4+, practices with nobody there, and the crew tool's
   balance columns (`engine.crew_rows`).
5. **Note.** RSVPs not headcounts. Which draft and season. The pairing was picked
   to fit these practices. Fall may not predict winter. Any `apart` pair already
   broken in the draft.

A small form picks the draft and the crew count.

## Constraints

- Read-only. No migrations, no new tables, no writes.
- Anyone who can see `/admin/analytics` sees it, names included, like the People
  dashboard.
- Reuse `app/crews/engine.py` (`score`, `crew_rows`, `Person`, `Settings`). Do not
  change it.
- Tests run against the scratch DB `tcsc_trips_test`. Fixtures are synthetic.
- Ships through a PR. Render deploys on merge. Target: live before Mitchell posts
  on 2026-10-20.

## Left to the builder

- How the two GET params plug into the route.
- The pairing search method, within the rules above.
- Chart forms and copy, in plain words with no em dashes.
