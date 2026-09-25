# Attendance analytics: design

Date: 2026-09-25. Branch: `attendance-analytics`. Status: approved in conversation with Rob, section by section.

Builds on `docs/superpowers/specs/2026-09-25-practice-analytics-design.md` (PRs #266-#269). Read that spec first; this one only describes what changes.

## Goal

Turn the Thursday-strength analytics into an attendance tool for everything the club organizes.

1. **Complete data.** Every emoji-RSVP'd TCSC happening is in the lineage: practices, kickoffs, socials, board meetings, races, volunteer days, banquets, and trip sign-ups.
2. **Provable completeness.** A coverage check shows every gap. "Complete" is a number that reads zero, not a belief.
3. **Why people come.** Dashboards that explain what makes a practice draw and who comes and who drifts.

Constraint from Rob: keep it simple and low in complexity while meeting all three goals. Every addition below exists because a goal needs it.

## Decisions

| Question | Decision |
|---|---|
| Sources added | `#announcements-general`, `#announcements-adventures`, `#tech-trip-signups`, `#chat`, `#races-information`. App events (`event_registrations`) are out for now. |
| Old general posts | Keep as count-only sessions. Reactor names were lost in the May 2026 channel migration; only per-emoji totals survive. |
| Trip attendance | Sign-ups only. Not payments, not channel rosters. |
| Table shape | Widen `practice_sessions` and `practice_attendance`. No second table, no view. |
| Event extraction | The parser finds candidate posts; agents write the catalog as corrections. No heuristic date parsing. |
| Dashboards | Three: what makes a practice draw, who comes and who drifts, data coverage. No event-driver dashboard. |
| Thursday strength | Folds into the practice dashboard. Its URL redirects there with Strength and Thursday preselected. |
| Names | Shown wherever useful. No extra permission beyond `/admin`. |
| Implementation workers | Codex (`codex exec`, model `gpt-6-astra`, effort `high`). Claude plans, dispatches, and reviews. |

## What recon found

Surveyed 2026-09-25. Raw dumps are in the gitignored `.superpowers/analytics-slack-dump/` (`general*.json`, `adventures*.json`, `other/<channel>.json`).

| Channel | ID | State | Token | Content |
|---|---|---|---|---|
| `#announcements-general` | C0B2VN1LU11 | live, private | bot | Created 2026-05-11. 184 posts copied from the old general channel by `scripts/migrate_announcements_general.py`, each with a text footer of per-emoji totals and its original date. 46 live posts since, with real reactions. |
| `#announcements-adventures` | C02HXN45214 | archived 2026-05-11 | bot | 303 real posts, Oct 2021 to Mar 2026. Human-written, no template. About 62 name an RSVP emoji. |
| `#tech-trip-signups` | C068ECRE0PQ | live | user token (bot not a member) | 444 Slack Workflow posts, Dec 2023 to Aug 2026, one per sign-up. Names the person by mention or typed name. |
| `#chat` | C02J1FDSBHT | live | bot | About 29 RSVP-style posts since 2021. |
| `#races-information` | C046XRWC4NR | live | bot | About 20 RSVP-style posts. |

Facts the design depends on:

- Kickoffs are undercounted today. The Sep 8, 2026 kickoff (practice 101) shows 7 RSVPs; the general post has 75 check marks and 33 `:x:`. The May 2026 kickoff potluck exists only in general. The fall 2025 kickoff (RSVPs in `#announcements-practices`, posted 2025-09-03) and the Oct 20, 2022 practice (cross-posted to old general) have no session.
- Kickoffs and 2026 board meetings use one fixed line: react `:white_check_mark:` to attend, `:x:` if you'll miss.
- Adventures posts name their emoji in free text ("bop the :pickle:", "smash that :party-wfh:"). Applause emoji (heart, +1, tada) outnumber RSVP emoji. `fire` was the RSVP emoji for relays.
- Posts can offer several options (race vs spectate). Reminder posts name the emoji but carry no reactions. Interest polls (trip-destination polls, cabin interest) look like RSVPs and are not attendance.
- Skin-tone suffixes appear in post text (`call_me_hand::skin-tone-4`) but not on reactions.
- The event date is days to weeks after the post date and is written in free text.
- Copied general posts all have a 2026-05-11 `ts`. Their real date and totals are in the footer (`*Mar 5, 2024 9:43 AM* · :rsvp: 16`).
- Every reactor in these channels is in `slack_users`. No bot reactors.
- `app/analytics` today: 404 sessions, 13 with `kind='event'`, several with blank titles or zero RSVPs.
- The practice-specific coupling to undo: `kind` check constraint, `slack_uid NOT NULL` in the attendance unique key, the role check constraint, the correction key regex, `capacity_lines` as global config, and the `kinds=["practice"]` default in `dashboards/base.py`.

## Data layer

### Channels

`app/analytics/__init__.py` holds three channel lists. `CHANNELS` (archive, and the reaction event log) gains all five. `SESSION_CHANNELS` (candidate and session sources) gains all five. `SYNC_CHANNELS` (nightly, 21-day window, unchanged) gains the four live ones. Adventures is imported once. `#tech-trip-signups` is imported once with `--token user`; Rob runs `/invite @TCSC` in it before PR 1 deploys so the nightly sync can use the bot token.

### Schema (one migration)

`practice_sessions`:

- `kind` allows `practice`, `event`, `trip`.
- New `category` text, not null. Practices: `practice`. Events: `kickoff`, `social`, `board`, `race`, `volunteer`, `banquet`, `other`. Trips: `trip`. Check-constrained.
- New `reported_count` int null. Set only on count-only sessions. When set, `rsvp_count = reported_count` and the session carries the `identities_lost` flag.

`practice_attendance`:

- New `person_key` text, not null: `slack:<uid>` or `name:<normalized full name>`.
- Unique key becomes `(session_id, person_key, role, emoji)`. `slack_uid` becomes nullable.
- `role` allows `rsvp`, `plan`, `lead`, `coach`, `signup`, `decline`.
- At rebuild, a `name:` person resolves to a member by exact case-insensitive full-name match on `users`. On a match the row gets `user_id` and the member's `slack_uid`, and `person_key` becomes `slack:<uid>`. No match keeps `name:` and adds the `unmatched_person` flag to the session.

The existing `rsvp_count` stays the headline number: distinct people with role `rsvp` (or `signup` for trips), or `reported_count`.

### Corrections

`CORRECTION_FIELDS` adds:

| Field | Type | Meaning |
|---|---|---|
| `title` | string | display title for created sessions |
| `category` | one of the categories above | |
| `emoji_roles` | `{emoji: role}` with role in `rsvp`, `decline`, `plan` | Only mapped emoji count. Replaces guessing from the post. |
| `reported_count` | int | count-only session |
| `gap_ok` | string | reason a week has no practice |

`kind` accepts `trip`. Key formats add `trip:<series-slug>:<YYYY>` for trip editions (YYYY is the Fall/Winter start year) and `gap:<YYYY-MM-DD>` (a Monday) for gap acknowledgements. The existing `create`, `skip`, `rsvp_from`, and `date` fields cover the rest. The Sep 8, 2026 kickoff is `practice:101` with `rsvp_from` pointing at the general post and `emoji_roles` `{white_check_mark: rsvp, x: decline}`; the general post itself gets `skip` so it does not become a second session.

### Trips

`parse_trips.py` reads `#tech-trip-signups` posts. Each Workflow post yields a trip name and a person (mention, else typed name). The Workflow's `username` ("Sisu Trip Sign-Up") maps to a series through a `trip_series` list in `config/practice_history.yaml` (match strings to a slug; slugs equal the app's `trip_series.slug`), and the post date picks the edition year: the post's year from June on, else the year before. Posts carry the person three ways: a `*What's your name?*` answer followed by the submitter mention, a bare mention, or typed first and last names. The typed name wins, because 158 of 304 name-form posts mention two different members (one member often signs up another). A mention is used only when the post has no typed name, or when the typed name matches no member and the post mentions exactly one person. A member with no Slack account gets `person_key` `user:<id>`. Each edition is one session: `kind=trip`, `category=trip`, date from its `trip:` correction (the trip's start date). One attendance row per person per edition, role `signup`, deduped. Non-cancelled `trip_registrations` rows are unioned in with the same dedupe. An edition with no date correction is flagged `missing_date` and left out of dashboards.

### Unchanged

Weather applies to any session with a resolved location (events at known venues get it; trips do not). `rebuild()` stays one transaction. The nightly job order stays sync, rebuild, weather.

`capacity_lines` moves under a `practice_views:` key in the YAML, since only the practice dashboard's split section uses it.

## Completeness

### Candidates

At rebuild, a top-level post in any archived channel (except `#extra-training-fun`, which is never counted) is a **candidate** when it did not become a session and either:

- names an emoji in RSVP phrasing (`hit`, `bop`, `smash`, `react with`, `give a`, `RSVP`, followed by `:emoji:`), or
- has 5 or more reactions on a single emoji.

Skin-tone suffixes are stripped before matching. Candidate detection is one function with no per-channel rules. This replaces the existing "possible miss" check in `flask analytics flags`.

A candidate is **resolved** when a correction exists for its post key (`create`, `skip`, or `rsvp_from` pointing at it).

### First pass by agents

Run once, after PR 1 deploys and the prod import finishes. Same process that cleared the 106 practice flags:

- Fixer agents read each candidate's raw post and thread and write one correction: `create` with `date`, `title`, `kind`, `category`, `emoji_roles` (and `reported_count` for copied general posts, read from the footer), or `skip` with a reason (interest poll, reminder, "bring a dish" emoji, member-run, Form-only, applause).
- Multi-option posts map every attending option to `rsvp` (racing and spectating both mean the person came).
- Fixers also write the `trip:` date corrections for every edition and `gap_ok` for real breaks.
- Reviewer agents check each correction against the raw post. Disagreements go to Rob. Accepted corrections go to prod via `flask analytics corrections import`.

After launch, new posts appear as unresolved candidates. Resolving them is a periodic Claude task. There is no review UI.

### Gap checks

Computed at rebuild, shown on the coverage dashboard, and listed by `flask analytics flags`:

1. **Unresolved candidates**, by channel.
2. **Empty weeks.** A Monday week inside a practice season with no practice session, and no `gap:` correction for that Monday. Season bounds come from the first and last practice session of each season label.
3. **Sync freshness**, per live channel: last successful sync.
4. **Soft items** (listed, never counted as gaps): count-only sessions, sessions with `unmatched_person`, and trip editions with `missing_date`.

The data set is complete when checks 1 and 2 are both zero.

## Dashboards

Three dashboards, all on the existing framework (`Dashboard`, blocks, `charts.py`, filter catalog). The filter catalog adds `category`. `kind` no longer defaults to `practice` globally; each dashboard fixes or defaults its own. `thursday_strength.py` is deleted, and `/admin/analytics/thursday-strength` redirects to `/admin/analytics/practices?activity=Strength&day_of_week=Thursday`.

### What makes a practice draw

`/admin/analytics/practices`. `kind` fixed to `practice`. Filters: season, date range, day of week, activity, workout type, location, format.

**Turnout index.** Each practice's RSVPs divided by the median RSVPs of practices in the same season label on the same weekday (cancelled sessions excluded). 1.2 means 20% above a typical practice of that slot. This keeps club growth and the winter-Tuesday-ski pattern from masquerading as factor effects. Factor charts plot the median index; tooltips and tables also show raw RSVPs.

Blocks:

1. Tiles: practices held, average RSVPs, distinct people, the activity with the highest and lowest median index.
2. Turnout over time: every practice, colored by activity bucket, cancelled ones faded.
3. Factor charts, one each, median index with session count on the bar: activity, workout type, location, start time (hour), temperature band, precipitation (none, light, heavy), snow depth band, darkness (`minutes_after_sunset` before vs after), week of season, and lead (any lead vs none). Bars with fewer than 5 sessions are greyed.
4. Split and merged, shown only when the filtered sessions include `split` or `merged`: the strength session chart moved as-is (early/late stacks, merged rings, capacity lines from `practice_views.capacity_lines`) and the slot-preference chart.
5. Table of every session, sortable.
6. Notes: RSVPs are not headcount; how the index works.

Acceptance: with Strength and Thursday selected, the split section reproduces the 44 hand-verified rows in `lift_verified.json`, as the old dashboard did.

### Who comes and who drifts

`/admin/analytics/people`. Filters: season, kind. Names come from `users` (or the `name:` text for unmatched people).

A person "attended" a session if they have a `rsvp` or `signup` row on a held session. Count-only sessions have no people and are excluded here.

1. Tiles: people this season, regulars (6+ practice RSVPs this season), first-timers (first session ever this season), lapsed regulars.
2. Retention by season: share of each season's attendees who attend in the next season of the same type, split into first-season and returning.
3. Newcomer curve: of people whose first session fell in a season, how many attended exactly 1, 2, 3, 4-5, and 6+ sessions that season.
4. Overlap: counts of people by the set of kinds they attended (practice only, event only, trip only, and each combination), for the selected seasons.
5. Lapsed regulars: 6+ practice RSVPs last season of the current season type, none in the last 28 days, while a season is running. Name, last RSVP date, last-season count, this-season count.
6. Registered, never RSVP'd: members with an `ACTIVE` `user_seasons` row for the current season and no attendance this season.
7. Everyone: name, first seen, last seen, counts by kind for this season, last season, and all time. Sortable.

### Data coverage

`/admin/analytics/coverage`. No filters.

1. Tiles: unresolved candidates, empty weeks, channels synced in the last 48 hours out of total, soft items.
2. Unresolved candidates table: channel, post date, first line of text, top emoji and counts, Slack permalink.
3. Sessions per week by kind across all history, empty weeks marked.
4. Sync freshness table.
5. Soft items table.

Every dashboard keeps the shared footer. The index page lists the three dashboards.

## Build approach

Render deploys every merge to `main`, so each step is a PR.

1. **PR 1, data.** Migration; channel list; import and sync for the new channels; `person_key`, `category`, `reported_count`, the new roles; correction fields and key formats; candidate detection; `parse_trips.py` and the `trip_series` YAML; empty-week check; `capacity_lines` under `practice_views`. The old dashboard keeps working (it reads through `practice_views`).
2. **Catalog pass, data only.** Rob invites the bot to `#tech-trip-signups`. Import the new channels into prod (run from the dev box with `TCSC_MIGRATION_ONLY=1` and `SLACK_APP_TOKEN` unset), rebuild, run fixers and reviewers, import corrections, rebuild. Done when gap checks 1 and 2 read zero.
3. **PR 2, dashboards.** Practice, people, coverage; the redirect; `thursday_strength.py` deleted.

Workers: `codex exec` with model `gpt-6-astra` and effort `high`. Never pass `-s workspace-write` (bwrap fails in this container); confirm each run actually executed before trusting it. Every worker reads the docs for the dependency its task touches (list in the practice-analytics spec) before writing code.

## Testing

Same rules as the practice-analytics spec. The repo is public: fixtures are hand-written, with no real Slack text, IDs, or names. Tests run against `tcsc_trips_test`. The new migration bumps `HEAD_REVISION` in `tests/practices/test_practice_migration_release.py`.

New tests:

- Candidate detection on made-up posts: each RSVP phrasing, skin tones, applause only, reminder post with no reactions, 5-reaction threshold.
- `emoji_roles` applied to a created session: mapped emoji count, unmapped emoji ignored, `decline` rows written.
- Count-only session: `rsvp_count` equals `reported_count`, flag set, no attendance rows.
- `person_key` uniqueness and name resolution (match, no match, two members with one name stays unmatched).
- Trip parser on both sign-up formats, edition selection around June 1, dedupe with `trip_registrations`.
- Each gap check, including a `gap:` correction clearing an empty week.
- Turnout index on made-up sessions, and each new chart spec against the Vega-Lite v6 schema.
- People dashboard classifications (regular, first-timer, lapsed, never RSVP'd) on made-up attendance.
- Redirect from the old strength URL.

Local acceptance, skipped without the dumps:

- Strength and Thursday on the practice dashboard reproduce `lift_verified.json`.
- The Sep 8, 2026 kickoff shows 75 RSVPs and 33 declines.
- Every post in the `#tech-trip-signups` dump lands on a trip edition.
- After the catalog pass, gap checks 1 and 2 read zero.

## Out of scope

- App events (`event_registrations`). Add when there is history to analyze.
- An event-driver dashboard.
- A corrections or review UI.
- Recovering names for the old general channel.
- Payments and trip channel rosters as attendance.
- Member-run channels (`#techno-corner-soccer-club`, `#apres-ski-book-club`) and `#extra-training-fun` as sessions.
- Statistical modeling beyond the turnout index.
