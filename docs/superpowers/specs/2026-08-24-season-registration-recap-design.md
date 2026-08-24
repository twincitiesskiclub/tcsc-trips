# Daily season registration recap — design

Date: 2026-08-24
Status: approved in brainstorming (season-only scope, window-open + tail cadence)

## Goal

Post a daily recap to the `leadership-registration` Slack channel each morning
while season registration is running, so leadership can see how registration is
going without opening the admin dashboard: yesterday's registrations, the
running totals, pace against the window and against prior seasons, volunteer
interest, and any notable one-off details.

## Decisions made during brainstorming

- **Scope: season registrations only.** Trips and events are out; they can be
  added later as separate sections if wanted.
- **Content:** yesterday's new/returning counts, season running totals,
  pace/trajectory (day N of window, days remaining, day-over-day movement),
  comparison to the same point in the prior season of the same type, volunteer
  interest from the Get Involved question, plus conditional "fun" lines.
  A `needs_review` count is included only when nonzero (those block the
  lottery; leadership should see them, but a daily zero is noise).
- **Cadence: window-open plus tail.** Post every morning (~8:05am Central,
  covering the prior Central day) while either the returning or new window is
  open, and for 7 days after the last window closes so the final tally
  settles. Silent the rest of the year. A zero-registration day during the
  window still posts — the zero is the signal.

## Data model facts this design relies on

- `UserSeason.registration_type` stores `'new'` or `'returning'` (lowercase).
- `UserSeason.registration_date` is a **Date** in Central time
  (written via `today_central()`).
- `UserSeason.volunteer_interests` / `volunteer_committees` are JSON lists of
  keys from `constants.VOLUNTEER_INTERESTS` / `VOLUNTEER_COMMITTEES`;
  null means the member was never asked.
- `Season.returning_start/end` and `new_start/end` are naive **UTC**
  DateTimes; convert to Central dates for day-offset math.
- `Season.season_type` + `year` identify comparable seasons across years.
- `Season.registration_limit` is the optional capacity.

## Components

### 1. Stats builder — `app/seasons/recap.py` (new)

Pure data layer: queries only, no Slack, no scheduler imports.

`build_recap(season, for_date)` — `for_date` is the Central date the recap
covers (normally yesterday). Returns a dict:

- `yesterday`: `{new, returning, total}` — count of UserSeasons with
  `registration_date == for_date`, split by `registration_type`.
- `season_totals`: `{new, returning, total}` for the whole season, and
  `registration_limit` + `pct_of_limit` when the season has a limit.
  All non-dropped rows count (PENDING_LOTTERY and ACTIVE); voluntarily or
  lottery-dropped rows do not.
- `windows`: for each of returning/new: start/end as Central dates, whether it
  is open on `for_date`, day number within the window, days remaining.
- `trend`: the day before's total, so the message can say "up from 3" /
  "down from 9".
- `prior_season`: the most recent Season with the same `season_type` and an
  earlier registration-window start that has any registrations. Comparison
  point: cumulative registrations through the same day-offset from that
  season's window anchor (anchor = earliest of returning_start/new_start,
  as a Central date). Returns `{name, count_at_same_point, final_count}`,
  or None when no comparable season exists.
- `volunteer`: among `for_date`'s registrations: how many answered the
  Get Involved question with at least one interest, and per-interest counts
  labeled via `VOLUNTEER_INTERESTS` (committee breakdown via
  `VOLUNTEER_COMMITTEES` when `committee` was picked).
- `needs_review`: count of rows with `needs_review=True` across the season
  (not just yesterday — the number that matters is the backlog).
- `highlights`: list of strings, each included only when true:
  - record day: `for_date`'s total is the highest single-day total of this
    season so far (and > 1, so day one of a slow season isn't a "record").
  - milestone: the season total crossed a multiple of 50 during `for_date`.
  - household: two or more of `for_date`'s registrants share a `phone_e164`.

`should_post(season, today)` — the cadence gate: True when either window is
open at `today`, or the latest window end is within the past 7 days. Lives
here so the scheduler job stays a thin wrapper and the gate is unit-testable.

### 2. Slack layer — `app/slack/season_recap.py` (new)

Follows the `app/slack/trips.py` contract: never raises, returns a result
dict (`{"success": bool, "error": ...}`), logs failures.

- `CHANNEL_NAME = "leadership-registration"` module constant.
- `post_season_recap(stats, channel_override=None)` — builds Block Kit from
  the stats dict and posts via `get_slack_client()` +
  `get_channel_id_by_name()`. Sections render only when their data exists
  (no prior season → no comparison line; empty highlights → no highlights
  block; needs_review 0 → omitted).
- Message shape: header line with the date and yesterday's count, a totals
  section, a pace/comparison section, a volunteer section, highlight lines,
  and a plain-text fallback string.

### 3. Scheduler job — `app/scheduler.py` (edit)

`run_season_recap_job(app, channel_override=None)`:

1. `Season.get_current()`; no current season → log, return.
2. `should_post(season, today_central())` → False → log "quiet", return.
3. `build_recap(season, today_central() - 1 day)`.
4. `post_season_recap(stats, channel_override=...)`; log the result.

Registered at 8:05 AM America/Chicago daily (`id='season_registration_recap'`,
`misfire_grace_time=3600`). Also added to `trigger_skipper_job_now`'s
`job_map` and `jobs_with_channel_override` so admins can fire it manually at
an override channel for testing.

## Error handling

- The job wraps its body in try/except and logs; a recap failure must never
  affect other scheduled jobs.
- The Slack layer never raises (trips.py convention).
- The stats builder may raise on programmer error — the job's try/except is
  the boundary.

## Testing

- `tests/seasons/test_recap.py` — stats builder against the Postgres test DB
  using the house fixture style (create Season/User/UserSeason rows, clean up
  in fixture teardown): yesterday split, season totals excluding dropped,
  window day math, trend, prior-season comparison at same day-offset,
  volunteer counts, each highlight's trigger and non-trigger, and
  `should_post` inside/after/outside the window (including the 7-day tail
  boundary).
- `tests/slack/test_season_recap.py` — block builder renders every section
  shape and omits empty ones; `post_season_recap` returns
  `{"success": False}` rather than raising when the client blows up
  (client mocked).
- Scheduler job: one test in the `test_scheduler_*` style asserting the gate
  short-circuits without posting and that a due day calls the poster
  (poster mocked).

## Out of scope

- Trip and event registrations.
- Any admin UI beyond the existing manual-trigger endpoint.
- Backfilling recaps for days the job missed (misfire grace covers restarts;
  an older gap just shows up in the running totals).
