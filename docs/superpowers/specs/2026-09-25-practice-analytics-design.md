# Practice analytics: design

Date: 2026-09-25. Branch: `practice-analytics`. Status: approved in conversation with Rob, section by section.

Inputs: `docs/superpowers/handoffs/2026-09-24-tcsc-analytics-lift-data.md`, the one-off lift artifact (https://claude.ai/artifact/Uvm3kz1DYAifEHGq1xfFEd), a full dump of both practice channels, and a lineage survey of every post format since 2022.

## Goal

Build an Analytics section in the tcsc.ski admin portal. Its first job is practice attendance across the club's whole history, so the practices team can see what makes a practice draw people: day, time, activity, workout, location, weather, darkness, season, format, leads, and plan choices.

Iteration 1 delivers:

1. A permanent copy of the practice channels in Postgres, so nobody needs Slack (or the archived channel) to answer an attendance question again.
2. One normalized record of every practice session from October 2022 to today, in the same format whatever era it came from.
3. A dashboard framework that Claude extends. Humans read dashboards and change filters. They do not build them.
4. The first dashboard: should Thursday strength run as one session or two?

Constraint from Rob: keep it simple. Every table and module below exists because a goal needs it.

## Decisions

| Question | Decision |
|---|---|
| Source of attendance | Slack reactions (plus early-2026 button RSVPs). Not `practice_rsvps`, which drops members with no linked account. |
| History depth | Everything with RSVP data: Oct 2022 onward. |
| Channels archived | `#announcements-practices` (C042G463AQ1), `#announcements-summer` (C03FKTTHNHW, archived), `#extra-training-fun` (C047BRZH1LG). The third is archived raw only. Its meetups are not team-sponsored and never become sessions. |
| Where the lineage lives | New `practice_sessions` table beside `practices`. `practices` stays operational. No backfill into it. |
| Who sees analytics | Anyone who can open `/admin`. No new permissions, no share links. |
| Chart library | Vega-Lite 6 + vega-embed, vendored, loaded only on analytics pages. |
| Dashboard shape | One Python module per dashboard, rendered by one shared template and one script. |
| Corrections | Data, so they live in an `analytics_corrections` table, not the repo. Rules (venue names, title keywords, excluded accounts, capacity lines) stay in a checked-in YAML file. Fixer and reviewer agents clear flags; only what they cannot settle goes to Rob. No review UI. |
| Theme | Light only, matching the admin portal (it has no dark mode). |
| Un-checks | Captured from now on in an append-only event log. Historical un-checks are unrecoverable. |

## What the data looks like

Usable history starts October 2022. Winter 2021-22 and summer 2022 have no RSVP data (summer 2022 posts came from a Google Calendar bot that nobody reacted to).

| Era | Where | Dates | Sessions | How to read it |
|---|---|---|---|---|
| Calendar bot | `#announcements-summer` | May to Sep 2022 | 37 | No RSVPs. Not imported as sessions. |
| Template | both channels | Oct 2022 to Dec 2025 | ~316 | Airtable to Zapier template (260 of 284 posts from the Zapier-linked account, the rest pasted by hand). Date header, `*Activity - Type @ Venue*` title, `Time:`, `Coach:`, `Leads:`, and a closing "Bop that :emoji:" line that maps emoji to sessions. |
| App | `#announcements-practices` | Jan 2026 onward | 92 | Join `practices.slack_message_ts`. Details come from the `practices` row. |
| Weekly previews | all | all | none | `Week of`, `There are N events`, `Weekly Practice Summary`, `Practices this week`. Skipped. |

Facts the parser must handle (from the lineage survey):

- The app bot reacts to its own posts with every RSVP emoji. It and the Zapier-linked account are excluded from attendance. The lift artifact's 2026 numbers include the bot, so they are 1 high per emoji.
- Jan to Mar 2026 posts had RSVP buttons. 105 of 702 RSVPs in that stretch exist only in `practice_rsvps` (`status='going'`). Those are unioned in.
- `conversations.history` caps a reaction's user list at 50. When `count > len(users)`, call `reactions.get` with `full=true`.
- The RSVP emoji varies per post: `white_check_mark`, `zap`, `six`/`seven`, `meow-coffee`, `ballot_box_with_check`, and seasonal jokes like `pumpkin`. Trust the post's "Bop that" line and the reactions actually present over the `Time:` line.
- Custom face emoji (one per coach, named after them) are coaches marking themselves as coming. They become `coach` rows, not RSVPs. Leads come from `Leads:` lines and `practice_leads`.
- Before 2026, some posts carried plan-choice reactions (technique vs intervals, skate vs classic). Multisport posts used activity emoji (runner, skier, bike) as the RSVP.
- Header defects in the template era: 11 wrong years, 7 weekday/date mismatches, 1 impossible date, 5 missing headers. AM practices are posted the night before, so post date is not practice date.
- 41 template posts hold two sessions (splits). 8 are multi-day (Wed+Fri, Thu+Fri). 4 sessions took RSVPs on a separate message. One app post was deleted and reposted.
- Merges and cancellations appear only in thread replies. 15 of 53 split lift nights have merge wording. A joking next-day reply on one merged night does not undo that merge.
- 160 of 323 session posts were edited. The app rewrites its own posts.
- All 240 people who ever reacted are in prod `slack_users`, and 283 of 284 of those link to a `users` row.
- 37 raw venue strings resolve to about 16 venues. All but 5 match `practice_locations`. The 5 (Royals Athletic Center, Hyland stadium, Beards Plaisance, Greenway/Punch Pizza, Monument) cover about 8 sessions.
- 74 raw titles map by keyword onto the existing 19 activities and 13 workout types. About 10% are joke titles.
- Prod `practices` is not a record of what happened: some threads cancelled practices that still say `scheduled`, and past-dated drafts exist.

## Architecture

```
Slack (3 channels) ──import/sync──▶ slack_archive_messages ──┐
reaction events ──────────────────▶ slack_reaction_events    │
practices, practice_leads, practice_rsvps ───────────────────┼──rebuild──▶ practice_sessions
config/practice_history.yaml ────────────────────────────────┤             practice_attendance
Open-Meteo ──fetch──▶ weather_hours ─────────────────────────┘                    │
                                                                                  ▼
                                               dashboards/*.py ──▶ /admin/analytics/<slug>
```

Everything lives in a new package `app/analytics/`. Nothing in it writes to `practices`, posts to Slack, or changes RSVP handling. The one touch point is a guarded insert in the reaction handler for the event log.

## Layer 1: raw archive

### `slack_archive_messages`

One row per message or thread reply.

| Column | Type | Notes |
|---|---|---|
| `id` | serial | |
| `channel_id` | text | |
| `ts` | text | Slack message ts |
| `thread_ts` | text null | set on replies and on parents with threads |
| `user_id` | text null | Slack user who posted |
| `bot_id` | text null | |
| `subtype` | text null | |
| `text` | text | |
| `posted_at` | timestamp (naive UTC) | from `ts` |
| `edited_at` | timestamp null | from `edited.ts` |
| `deleted_at` | timestamp null | set when a sync no longer finds the message |
| `raw` | jsonb | the full Slack message, reactions with complete user lists, blocks, attachments |
| `synced_at` | timestamp (naive UTC, codebase convention) | |

Unique `(channel_id, ts)`, index on `(channel_id, thread_ts)`. Rows are upserted, so only the latest version of an edited message is kept. Files and images are not downloaded; their metadata stays in `raw`.

### `slack_reaction_events`

Append-only log of reaction adds and removals, from now on. This is the only way to see un-checks.

| Column | Type |
|---|---|
| `id` | serial |
| `channel_id` | text |
| `message_ts` | text |
| `emoji` | text |
| `slack_uid` | text |
| `action` | text (`added` or `removed`) |
| `event_ts` | text |
| `received_at` | timestamp (naive UTC, codebase convention) |

Written by `_delegate_reaction_event` in `app/slack/bolt_app.py` after the attendance handler returns, only for the three channels in the archive, inside the existing app context. The insert is wrapped in try/except with `db.session.rollback()` on failure and never raises, so RSVP handling behaves exactly as it does today. Dashboards do not read this table in iteration 1. It exists so un-check data starts accumulating now.

### Import and sync

- `flask analytics import-slack --channel <id> [--token user]`: walks full history and every thread and upserts. It is safe to re-run. `#announcements-summer` needs `--token user` (`SLACK_USER_TOKEN`), because the bot is not a member and Slack does not allow joining archived channels. The other two channels use the bot token (the bot is a member of both).
- Nightly sync (bot token): re-fetch the last 21 days of `#announcements-practices` and `#extra-training-fun`, threads included. Replace each message's `raw`. Mark a message `deleted_at` if it is gone. After 21 days a message is final.
- Honor Slack rate limits: `conversations.history` and `conversations.replies` are Tier 3. Back off on `429` using `Retry-After`.

## Layer 2: practice lineage

Both tables are rebuilt from scratch in one transaction by `rebuild()`. About 450 sessions and 8,500 attendance rows, a few seconds. A parser crash rolls back and leaves the last good tables.

### `practice_sessions`

One row per session, same columns in every era.

| Column | Type | Notes |
|---|---|---|
| `id` | serial | |
| `session_key` | text unique | `<channel>:<ts>:<slot>` or `practice:<id>`. Stable across rebuilds. Corrections key on it. |
| `era` | text | `template` or `app` |
| `kind` | text | `practice` or `event` (kickoff potlucks, board meetings) |
| `source_message_id` | int null FK | `slack_archive_messages.id` |
| `practice_id` | int null FK | `practices.id`, app era |
| `date` | date | practice date, Central |
| `start_time` | time | Central |
| `day_of_week` | text | `Monday` … `Sunday` |
| `season_label` | text | see Seasons |
| `location_id` | int null FK | `practice_locations.id` |
| `location_name` | text | canonical display name |
| `lat`, `lon` | float null | from `practice_locations` or YAML venue |
| `is_indoor` | bool | from YAML venue list |
| `activity` | text | one bucket for charts, e.g. `Strength`, `Run`, `Rollerski`, `Ski` |
| `activities` | text[] | canonical `practice_activities` names |
| `workout_type` | text | one bucket, e.g. `Circuit`, `Intervals`, `Endurance`, `Technique` |
| `workout_types` | text[] | canonical `practice_types` names |
| `title` | text | as posted, for tooltips |
| `format` | text | `single`, `split`, or `merged` |
| `slot` | text null | `early` or `late` for split sessions |
| `group_key` | text | sessions from one post share it |
| `rsvp_emoji` | text null | |
| `status` | text | `held` or `cancelled` |
| `rsvp_count` | int | distinct humans with role `rsvp` |
| `temp_f`, `feels_like_f`, `wind_mph` | float null | at start hour |
| `precip_in`, `snowfall_in` | float null | start to start + 90 min |
| `snowfall_prior_24h_in`, `snow_depth_in` | float null | |
| `weather_code` | int null | WMO code |
| `minutes_after_sunset` | int null | start time minus sunset, negative before sunset; via `app/integrations/daylight.py` |
| `flags` | text[] | why the parser was unsure, e.g. `date_mismatch`, `merge_detected`, `cancel_language`, `unknown_venue` |
| `needs_review` | bool | flags present and no correction for the session |

Venues resolve by `practice_locations.name` (plus `spot` when given), because row ids differ between prod and dev databases.

A merged night is one row with `format='merged'`. Its attendance rows keep each person's original emoji, so early vs late intent is still countable.

### `practice_attendance`

One row per person per session per role.

| Column | Type | Notes |
|---|---|---|
| `id` | serial | |
| `session_id` | int FK cascade | |
| `slack_uid` | text | |
| `user_id` | int null FK | resolved through `slack_users` at rebuild |
| `role` | text | `rsvp`, `plan`, `lead`, `coach` |
| `emoji` | text null | |
| `slot` | text null | `early` or `late` when the emoji maps to a split slot, kept on merged nights |
| `source` | text | `reaction`, `button`, `post_text`, `app`, `correction` |

Unique `(session_id, slack_uid, role, emoji)`. No separate people table: `slack_users` already covers every reactor.

### `weather_hours`

Cache of Open-Meteo hourly observations, so `rebuild()` never calls the network.

| Column | Type |
|---|---|
| `lat`, `lon` | numeric(6,2), part of PK |
| `hour_local` | timestamp (Central), part of PK |
| `temp_f`, `feels_like_f`, `precip_in`, `snowfall_in`, `snow_depth_in`, `wind_mph` | float |
| `weather_code` | int |
| `fetched_at` | timestamp (naive UTC, codebase convention) |

`fetch_missing_weather()` finds sessions whose hours are not cached and fetches one date range per location from the Open-Meteo historical API. It requests Fahrenheit, mph, and inches, and converts every value using the units the response reports in `hourly_units` (snow depth comes back in feet when inches are requested). It then reruns only the weather columns. Open-Meteo's archive lags about five days, so a session's weather fills in within a week. A failed fetch logs and retries the next night.

### `analytics_corrections`

| Column | Type | Notes |
|---|---|---|
| `id` | serial | |
| `key` | text unique | a `session_key`, or `<channel>:<ts>` for a whole post |
| `fields` | jsonb | validated correction fields (below) |
| `note` | text | why, required |
| `author` | text | `claude-fixer`, `rob`, ... |
| `created_at`, `updated_at` | timestamp | |

Managed with `flask analytics corrections list|import|export`. `rebuild()` reads it.

### `config/practice_history.yaml`

Checked in. Rules only, never per-post data. Loaded and validated at rebuild. An invalid file fails the rebuild loudly and leaves the old tables in place. The example below is illustrative: its IDs, coordinates, and ts values are placeholders, and the real entries come from the prod import.

```yaml
excluded_slack_uids:        # bots and integration accounts, never attendance
  - U06FYPUNQCU             # TCSC app bot
  - U04C46UJXAM             # Zapier-linked account

venues:                     # raw venue text (case-insensitive substring) → location
  - match: ["the trailhead", "trailhead bridge"]
    location: {name: "Theodore Wirth", spot: "Trailhead Bridge"}   # looked up by name+spot, never by id
  - match: ["balance fitness"]
    location: {name: "Balance Fitness Studio"}
    indoor: true
  - match: ["beards plaisance"]
    name: Beards Plaisance        # not in practice_locations: name and coordinates live here
    lat: 44.921
    lon: -93.310

titles:                     # title keywords → canonical activity/type names
  - match: ["strength"]
    activities: [Strength]
    types: [Circuit]

capacity_lines:             # used by the lift dashboard
  - {value: 27, label: "2025 split rule", from: 2025-05-01}
  - {value: 30, label: "Dec 2025 cap", from: 2025-12-01, to: 2026-03-31}
  - {value: 35, label: "One session (5x7)", from: 2026-08-01}

```

Correction fields (stored in `analytics_corrections.fields`): `skip`, `kind`, `date`, `start_time`, `status`, `merged`, `rsvp_emoji`, `plan_emoji`, `rsvp_from`, `add` / `remove` (list of `{slack_uid, role}`), `location`, `activities`, `types`, and `ok` (acknowledge a flag without changing anything). A flag counts as resolved when a correction exists for that session or its post.

### Parsing rules

For each top-level message in the two practice channels, in order:

1. **Weekly preview?** Skip.
2. **App era:** `ts` matches `practices.slack_message_ts` for non-draft practices. One session per `practices` row. Location, activities, types, and status come from the row. Leads come from `practice_leads`. The split emoji comes from `slack_session_emoji`. When that is empty (11 of 16 split groups), read the `RSVP:` mapping from the post blocks. Button RSVPs come from `practice_rsvps` with `status='going'`.
3. **Template era:** the message has a date header and either a title line or a `Workout:` line. Parse:
   - date from the header, sanity-checked against the post time (practice date within 1 day before to 8 days after posting; outside that window, use the next matching weekday and flag `date_mismatch`)
   - start time from `Time:` or the header
   - venue from `Location:` or the title's `@ Venue`, resolved through `venues`
   - activity and type from the title through `titles`; unmatched keeps the raw title and flags `unmatched_title`
   - leads and coaches from `Leads:` / `Coach:` mentions
   - the emoji-to-session mapping from the "Bop that" line; default `white_check_mark`
   - multi-day posts become one session per day
4. **Anything else** is not a session. A message with 5+ reactions of one RSVP-style emoji (white_check_mark, six, seven, zap, meow-coffee, ballot_box_with_check) that did not become a session and has no correction is reported by `flask analytics flags` as a possible miss.

Then for every session:

- RSVPs are distinct reactors on its emoji, minus `excluded_slack_uids`, minus coach emoji. Other emoji on the post from members who also RSVP'd become `plan` rows when the post names them as plan choices.
- **Merges:** a thread reply or broadcast on the practice date matching the merge phrases (`combin`, `merg`, `one session`, `single session` near `today`/`tonight`) turns a split group into one `merged` session and flags `merge_detected`. A `merged: false` correction reverses it.
- **Cancellations:** app `status='cancelled'`, or a correction. Thread cancel language only adds the `cancel_language` flag, because leads often announce that a cancel decision is pending without cancelling.
- Corrections apply last.

### Seasons

If the session date falls inside a `seasons` row's `start_date..end_date`, use its name. Otherwise use a computed label: May through August is `<year> Spring/Summer`; September through April is `<start year> Fall/Winter`, where the start year is the September's year. The labels match the existing `seasons` names ("2025 Spring/Summer", "2025 Fall/Winter").

## Layer 3: dashboards

### Files

- `app/routes/admin_analytics.py`: blueprint `admin_analytics`, `url_prefix='/admin/analytics'`, every route `@admin_required`. `GET /admin/analytics` shows dashboard cards. `GET /admin/analytics/<slug>` shows one dashboard.
- `app/analytics/dashboards/__init__.py`: the registry, a list of dashboard modules.
- `app/analytics/dashboards/base.py`: `Dashboard`, the four block types, and the filter catalog.
- `app/analytics/charts.py`: Vega-Lite spec builders and the theme.
- `app/templates/admin/analytics/index.html` and `dashboard.html`, extending `admin/admin_base.html`.
- `app/static/admin_analytics.js`.
- `app/static/vendor/vega-<ver>.min.js`, `vega-lite-<ver>.min.js`, `vega-embed-<ver>.min.js`: pinned, vendored, loaded only by `dashboard.html`.
- Sidebar: a new "Analytics" section in `app/templates/admin/partials/sidebar.html`.

### A dashboard is one module

```python
DASHBOARD = Dashboard(
    slug="thursday-strength",
    title="Thursday strength",
    question="Should Thursday strength run as one session or two?",
    filters=["season", "date_range", "day_of_week", "format"],
    fixed={"activity": "Strength"},
    build=build,                      # build(filters) -> list[Block]
)
```

Blocks:

- `Tiles([Tile(label, value, sub)])`
- `Chart(title, description, spec, rows, columns)`: `rows` is rendered as a collapsible table under the chart.
- `Table(title, rows, columns)`: sortable.
- `Note(text)`

Filters come from one catalog: `season`, `date_range`, `day_of_week`, `activity`, `workout_type`, `location`, `format`, `kind`. Each parses and validates its own `request.args` values and applies itself to a `practice_sessions` query. Unknown or invalid values are ignored. `kind` defaults to `practice`. Sessions dated after today (Central) never reach a dashboard: the app creates practices weeks ahead, so the lineage holds future sessions with partial RSVPs. The filter bar is a GET form, so the URL is the full view state.

### Rendering

The page is server-rendered. Each chart's spec is inlined with `|tojson`. `admin_analytics.js` calls `vegaEmbed` with `renderer: 'svg'`, `actions: false` and `ast: true` (the admin CSP forbids `unsafe-eval`, so Vega must use its expression interpreter), sets width from the container, and re-embeds on resize (debounced ResizeObserver). A render error shows a message in place of the chart. The page keeps no client-side state and needs no JSON API.

### `charts.py`

Tested builders that dashboards compose: `stacked_columns`, `grouped_bars`, `line`, `heatmap`, `scatter`, `reference_lines` (layered `rule` marks with labels), and `theme()`. The theme uses the TCSC palette from `tailwind.config.js`, the admin's system font stack, and colors checked for contrast. Every spec sets `description` for screen readers.

### Shared footer

Every dashboard ends with: "Data through <last successful sync, Central> · RSVPs are not headcount · <N> sessions need review". N is the number of flagged sessions without a correction.

## First dashboard: Thursday strength

`/admin/analytics/thursday-strength`. Activity fixed to Strength. The day-of-week filter defaults to Thursday and can include the Dec 2025 Wednesday and Friday lifts.

A "week" is a Monday-to-Sunday week in Central time, summing every strength session in it.

1. **Tiles:** average RSVPs per week; weeks over each capacity line in effect during the selected range; late share in two-session weeks; the latest week next to the same week a year earlier.
2. **Every strength session, grouped by season:** two-session weeks stacked early/late, single sessions gray, merged nights marked, with the YAML capacity lines drawn for the dates they applied.
3. **Season by season:** average and peak per week, weeks over each line, late share. Chart and table.
4. **This season against last, aligned by week of season.**
5. **Slot preference:** per season, how many people only ever chose early, only late, or both. Counts only, no names.
6. **Notes:** RSVPs are not headcount. Merges happened on low nights, so merged weeks averaging fewer people does not show that merging lowers turnout.

Acceptance: after a rebuild, the Strength sessions from May 2025 on match the 44 hand-verified rows date for date (early and late counted by emoji, including merged nights; single sessions by total) in `.superpowers/analytics-slack-dump/lift_verified.json` (from the artifact's `lift-data` block, never committed). 2026 values in that file are corrected by −1 per emoji for the bot's own reaction, and the file records that correction in a comment field.

## Operations

- **CLI** (`flask analytics …`): `import-slack`, `sync`, `rebuild`, `fetch-weather`, `flags` (lists flagged sessions without a correction, plus possible misses).
- **Nightly job** in `app/scheduler.py`, 3:30 AM Central: `sync` then `rebuild` then `fetch-weather`. Each step logs and stops the run on failure, and the previous tables stay in place. The job shows up on the existing Scheduled Tasks page like the others.
- **One-time prod import**, after PR 1 deploys: run from the dev box against `PROD_DATABASE_URL` with `TCSC_MIGRATION_ONLY=1` and `SLACK_APP_TOKEN` unset, so `create_app` does not start the scheduler or the Socket Mode client. Import all three channels, rebuild, fetch weather, Then fixer agents propose corrections for every flag, reviewer agents check each one against the raw post, and accepted corrections are imported into `analytics_corrections`. Parser patterns become a small code PR. Only items the agents cannot settle go to Rob.

## Testing

The GitHub repo is public. Committed fixtures are hand-written to mirror each post format and contain no real Slack text, member IDs, names, or per-person data. Real data stays in the database, and local copies stay in the gitignored `.superpowers/analytics-slack-dump/` (the channel dumps, an export of app-era practice rows, `lift_verified.json`, and a corrections export). Tests that need them skip when they are absent. Dashboard tests use made-up numbers.

- **Parser:** golden tests on hand-written messages covering every format and edge case listed above, each with its expected sessions and attendance.
- **Lift acceptance:** building the lineage from the real dump reproduces `lift_verified.json` (runs locally, skips in environments without the dump).
- **Rebuild:** running it twice on the same input gives identical rows. An invalid YAML file leaves the previous tables untouched.
- **Reaction event log:** a failing insert does not change the attendance handler's result.
- **Weather:** unit conversion and the start-hour and window math, against recorded Open-Meteo responses. No network calls in tests.
- **Dashboards:** every spec validates against the Vega-Lite v6 JSON schema (vendored), and every dashboard renders to PNG with `vl-convert-python`. Route tests cover auth, the index, and each filter.
- Analytics tests honor `DATABASE_URL` and run against the scratch database `tcsc_trips_test`, not the shared dev database. DB tests roll back instead of committing.
- Test-only dependencies (`jsonschema`, `vl-convert-python`) go in a new `requirements-dev.txt`, so the Render build does not grow.

## Build approach

- Two PRs. Render deploys every commit on `main`.
  1. **Data foundation:** migration for the six tables, the archive import and sync, the parser, `rebuild`, the weather fetch, the YAML, the CLI, the nightly job, and the reaction event log.
  2. **Dashboards:** the blueprint, templates, `admin_analytics.js`, vendored Vega, `charts.py`, the filter catalog, the sidebar entry, and the Thursday strength dashboard.
- Implementation runs through Codex workers (`codex exec`, model `gpt-6-astra`, effort `high`). Claude plans, dispatches, and reviews.
- Every worker reads the official docs for the dependency its task touches before writing code, and every plan task names the pages. Reviews check the code against those docs.

| Dependency | Docs |
|---|---|
| Vega-Lite 6 | https://vega.github.io/vega-lite/docs/ (mark, layer, stack, rule, config, size, description) |
| Vega-Lite schema | https://vega.github.io/schema/vega-lite/v6.json |
| vega-embed | https://github.com/vega/vega-embed#options |
| vl-convert-python | https://github.com/vega/vl-convert |
| Slack Web API | https://docs.slack.dev/reference/methods/conversations.history, https://docs.slack.dev/reference/methods/conversations.replies, https://docs.slack.dev/reference/methods/reactions.get, https://docs.slack.dev/apis/web-api/rate-limits |
| Slack events | https://docs.slack.dev/reference/events/reaction_added, https://docs.slack.dev/reference/events/reaction_removed |
| Open-Meteo | https://open-meteo.com/en/docs/historical-weather-api |
| APScheduler 3 | https://apscheduler.readthedocs.io/en/3.x/userguide.html |
| Flask CLI, Flask-Migrate | https://flask.palletsprojects.com/en/stable/cli/, https://flask-migrate.readthedocs.io/ |
| PostgreSQL JSONB and arrays | https://www.postgresql.org/docs/current/datatype-json.html, https://www.postgresql.org/docs/current/arrays.html |

## Out of scope for iteration 1

- A review or corrections UI. Revisit if people other than Claude need to fix data.
- Recording merges in the app itself instead of detecting them from Slack threads.
- Dashboards beyond Thursday strength. The framework is built so the next ones are one module each.
- Un-check analysis. The event log starts collecting now.
- Downloading images and files from Slack.
- Share links, member-facing pages, dark mode.
- Weekend meetups in `#extra-training-fun` as sessions.
- Correcting the one-off lift artifact. Offered to Rob separately.
