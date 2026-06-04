# Practice Announcement Redesign - Design

**Date:** 2026-06-04
**Status:** Approved design, ready for implementation plan
**Topic:** Redesign the automated practice announcement posted to `#announcements-practices`, normalize activity/type data, add a logistics notes field, drop warmup/cooldown from the post, and surface sunset / wind / AQI from existing Skipper integrations.

---

## 1. Background & Problem

The Flask app posts an automated Block Kit message announcing each ski practice. Members read it to decide whether to attend and to RSVP. The current layout (`app/slack/blocks/announcements.py::build_practice_announcement_blocks`) feels cramped and clunky:

- The most important facts (time, location, what we are doing) are de-emphasized, rendered in small gray `context` lines at the same visual weight as parking and gear.
- The time sits in a `section` line prefixed with a clipboard emoji and the club name, behind noise before the signal.
- Context lines use `A | B | C | D` pipe-delimited "soup" that reads as dense and is poor for screen readers.
- Everything is squeezed into ~8-9 blocks (to avoid Slack's "View full message" collapse), which is part of what makes it feel airless.

**Goal:** restore a clear typographic hierarchy and breathing room, surface when / where / what as focal points, and move secondary detail into a threaded reply, while keeping the top message tight enough never to collapse. Mobile-first (most members read on the Slack phone app, where two-column `fields` blocks stack).

## 2. How this design was produced

This design was brainstormed visually (Slack mockups rendered in a browser companion) and pressure-tested with two multi-agent passes:

1. A 6-perspective design debate (hierarchy purist, mobile minimalist, conversion optimizer, editorial typographer, accessibility advocate, Slack platform pragmatist) followed by a 4-judge board and a synthesizer. The board converged on a time-first header, divider-separated zones, text labels instead of pipe-soup, and emoji-reaction RSVP.
2. A 5-perspective "what info is missing" brainstorm (first-timer, racer, safety, logistics, community) plus a synthesizer, which surfaced that the app already fetches sunset / wind / AQI for Skipper but never shows them.

The user selected the final layout and the specific additions through iterative mockup review.

## 3. Goals / Non-Goals

**Goals**
- Strong visual hierarchy: time + activity in the header (the only large-text tool Slack offers), location/address next, then workout, then RSVP.
- A tight hero message (never collapses) plus a threaded "Practice Details" reply for secondary detail.
- Normalize `practice_activities` and `practice_types` names in the database so they are display-ready, removing the need for any activity-label translation logic in code.
- Add a freeform `logistics_notes` field for commentary on the workout/logistics, separate from the workout description.
- Remove warmup/cooldown from the announcement and editors (keep the DB columns).
- Surface sunset, wind, and AQI (value-only, when AQI > 49) in the thread, wired from existing integrations.

**Non-Goals**
- No redesign of the coach review / collab posts, cancellation posts, weekly summary, or App Home (only the member-facing announcement and its new thread reply).
- No new external API integrations (everything new is already fetched by the app).
- Not dropping the `warmup_description` / `cooldown_description` columns (data is retained; only the UI stops using them).
- The new info items the user did NOT select are out of scope (estimated end time, groomed-for-technique, race-conflict warning, RSVP-count-in-hero, trail pass/facilities fields, newcomer welcome hints, frostbite time, precip type).

## 4. Final Announcement Design

All literal renders below use the running sample: **Sunday, Dec 29, 12:00 PM at Theodore Wirth (Trailhead), Classic technique, Intervals workout, 25°F, social at Utepils.** Separators are middot (`·`), comma, or hyphen. **No em dashes anywhere.**

### 4.1 Hero (top message)

Block order:

1. **`header`** (plain_text, the only large text): `{day} · {activity label} at {time}`
   - Sample: `Sunday · Classic Ski at 12:00 PM`
   - The weekday is retained (evening announcements run the night before for morning practices, and the channel is a scroll-back archive, so the day disambiguates "today vs tomorrow").
2. **`section`** (mrkdwn) - Where + address:
   ```
   *Where:* Theodore Wirth - Trailhead
   <map_url|📍 1301 Theodore Wirth Pkwy>
   ```
   The address line uses the existing `_address_link()` fallback chain (google_maps_url → lat/lon → address query).
3. **`divider`**
4. **`section`** - Workout + type:
   ```
   *Workout · Intervals*
   5 × 4min @ threshold, 2min easy between. Smooth weight transfer, complete kick.
   ```
   The workout type name (normalized, e.g. "Intervals") is appended to the "Workout" label.
5. **`section`** - Notes (only when `logistics_notes` is set):
   ```
   *📌 Notes*
   Meet at the trailhead flagpole. It's cold out, get a solid 15+ min warmup in before we start.
   ```
6. **`section`** - Social (only when the practice has a social):
   ```
   🍹 *Social after at Utepils Brewing*
   ```
7. **`divider`**
8. **`section`** - RSVP call to action:
   ```
   Bop ✅ so we'll know you'll be there. 🌲 if you'll be there but doing endurance instead. Running late? Reply in the thread. <!channel>
   ```
   The `🌲 ... endurance` clause is included only when the practice has intervals.
9. **`context`** - Coach + Leads:
   ```
   👨‍🏫 Coach @Anders · 🧑‍🤝‍🧑 Leads @Maria, @Sam
   ```

RSVP remains **emoji reactions** (✅ going, 🌲 endurance, 🤔 maybe), not buttons. Slack renders reaction count pills under the message, which double as social proof. The existing emoji-reaction RSVP system and `reaction_added` handlers are unchanged.

Block count: 7 to 9 depending on Notes/Social presence, comfortably under the collapse threshold.

### 4.2 Thread reply - "Practice Details"

Posted as a threaded reply to the hero message (not broadcast to channel). Block order:

1. **`header`**: `Practice Details`
2. **`section`** - Parking + Gear:
   ```
   *Parking*
   Chalet lot; arrive 15 min early, it fills fast.

   *Gear*
   Classic skis + kick wax for ~25°F.
   ```
3. **`divider`**
4. **`section`** - Conditions:
   ```
   *Conditions*
   🌡️ 25°F (feels 18°), cloudy, light snow. No alerts.
   💨 Wind NW 12 mph
   ☀️ Sunset 4:38 PM
   🎿 Trails: Good, Groomed · <trail_report_url|Trail report>
   ```

**Conditional rules inside Conditions:**
- **Wind** (`💨 Wind {direction} {speed} mph`): always shown when wind data is present (already in `WeatherConditions.wind_speed_mph` / `.wind_direction`).
- **Sunset** (`☀️ Sunset {time}`): always shown. When the practice runs past sunset (after-dark / `is_dark_practice` or computed from end time vs `DaylightInfo.sunset`), the line upgrades to a headlamp advisory: `🔦 Sunset 5:42 PM, bring a headlamp` (comma, no em dash).
- **AQI** (`🌫️ AQI {value}`): shown **only when AQI > 49**, value only, no category/advisory text. Hidden on clean-air days.
- **Trails**: existing behavior (shown when trail conditions are available).

### 4.3 Combined lift (strength) announcement

`build_combined_lift_blocks` is brought into visual consistency with the same principles: `header` uses `{day(s)} · Strength`, no warmup/cooldown, the same thread "Practice Details" reply pattern, and the same RSVP/notes treatment where applicable. (Strength practices typically have no trail/AQI relevance; conditional rules naturally hide those lines.)

## 5. Activity / Type Normalization (replaces translation logic)

Rather than mapping activity names to display labels in code (e.g. `Classic → "Classic Ski"`), normalize the source data so the header and workout label print names verbatim.

- **Approach:** a one-off script set mirroring the existing locations pipeline (`scripts/locations_{export,geocode,apply}.py`):
  - `export`: dump current `practice_activities` and `practice_types` names.
  - curate: produce a display-ready name for each (e.g. `Classic → "Classic Ski"`, `Skate → "Skate Ski"`, lift/strength → `"Strength"`, types like `"Intervals"`, `"Distance"`, `"Technique"`). Final names confirmed with the user during implementation.
  - `apply`: write normalized names to the DB (idempotent, prod via gitignored `PROD_DATABASE_URL` per existing convention).
- **Header activity label rule** (after normalization): join the practice's activity names verbatim; for 2+ activities join with ` + `; when no activity is set, fall back to `"Practice"`.
- **Important regression guard:** `has_intervals` is computed via `'intervals' in type.name.lower()` (`announcements.py:239`). Normalized type names must preserve the `intervals` substring (e.g. keep "Intervals" in the name), or this check is updated to a flag/explicit match. Audit every place that string-matches activity/type names before renaming (coach review, weekly summary, `_is_strength_practice`).

## 6. New `logistics_notes` Field

Freeform commentary on the workout/logistics, separate from `workout_description`. Examples: "meet at the flagpole", "it's cold, warm up extra", "newer skiers grab Maria for a wax hand".

- **DB:** add `logistics_notes = db.Column(db.Text)` to `Practice` (`app/practices/models.py`). Nullable. Migration via `flask db migrate`.
- **Interfaces:** add `logistics_notes: Optional[str] = None` to `PracticeInfo` (`app/practices/interfaces.py`) and map it in `service.py` where `PracticeInfo` is built from `Practice`.
- **Admin editor:** add a Notes textarea to the unified practice editor (`templates/admin/practices/detail.html` + `_detail_script.js`), and persist it in the edit route (`app/routes/admin_practices.py::edit_practice`).
- **Slack workout-entry modal** (`app/slack/modals.py`): per user decision, **remove the warmup/cooldown inputs and add a `logistics_notes` input** alongside the workout field. Update the modal submission handler in `app/slack/bolt_app.py` (`workout_entry`) accordingly.
- **Render:** the hero "📌 Notes" section (block 5 above), shown only when set.

## 7. Warmup / Cooldown Removal

- Keep `warmup_description` and `cooldown_description` columns in the DB (no data loss).
- Stop rendering them in the announcement (`build_practice_announcement_blocks`, `build_combined_lift_blocks`).
- Remove their inputs from the admin editor and from the Slack workout-entry modal (replaced by Notes).
- Audit other surfaces that display them (`app/slack/blocks/coach_review.py`, `templates/admin/practices/detail.html`, `_detail_script.js`, `admin_practices.js`, `config.html`) and remove or hide as appropriate. Coach review may retain them if coaches still reference them internally; default is to remove from member-facing surfaces and keep coach-facing only if explicitly wanted. **Open question (see §11).**

## 8. New Data Wiring (sunset / wind / AQI)

The announcement builder currently receives `weather`, `trail_conditions`, and `rsvp_counts`. It does not receive daylight or AQI.

- **Wind:** already present on `WeatherConditions` (fetched via `get_weather_for_location`). No new fetch; just render in the Conditions block.
- **Sunset:** fetch `DaylightInfo` via `app.integrations.daylight.get_daylight_info(lat, lon, date)` in the announcement path (scheduler `post_practice_announcement` callers at `app/scheduler.py:~535-580`, and the refresh/update path). Pass through `post_practice_announcement` / `update_practice_announcement` into the builder. Fields: `DaylightInfo.sunset`, `.civil_twilight_end` (interfaces:410+).
- **AQI:** fetch via `app.integrations.air_quality.get_air_quality(...)` in the announcement path; pass an AQI value through to the builder; render only when `> 49`.
- **Builder signature:** `build_practice_announcement_blocks(practice, weather, trail_conditions, rsvp_counts, daylight=None, air_quality=None)`. `post_practice_announcement` and `update_practice_announcement` gain matching optional params.
- All fetches are best-effort with try/except and graceful omission (consistent with the existing weather fetch), so a failed fetch hides that line rather than breaking the post.

## 9. Threaded "Practice Details" Reply Mechanics

The thread reply is new behavior (the announcement is currently a single message).

- **Post:** after posting the hero message, post the "Practice Details" blocks as a threaded reply (`thread_ts = hero ts`, `reply_broadcast = false`).
- **Track:** add `slack_details_ts = db.Column(db.String(50))` to `Practice` to store the reply's timestamp (mirrors the other `slack_*_ts` columns).
- **Update:** on edits, `update_practice_announcement` and the central `refresh_practice_posts` dispatcher (`app/slack/practices/refresh.py`) update both the hero message and the thread reply (post the reply if `slack_details_ts` is missing, e.g. for practices created before this change).
- **Build:** add `build_practice_details_blocks(practice, weather, trail_conditions, daylight, air_quality)` to `app/slack/blocks/announcements.py`.

## 10. Affected Files (inventory)

- `app/practices/models.py` - add `logistics_notes`, `slack_details_ts`; migration.
- `app/practices/interfaces.py` - `PracticeInfo.logistics_notes`.
- `app/practices/service.py` - map new field; stop mapping warmup/cooldown where appropriate.
- `app/slack/blocks/announcements.py` - rewrite `build_practice_announcement_blocks`, add `build_practice_details_blocks`, update `build_combined_lift_blocks`; header activity label + fallback; conditional sunset/wind/AQI; remove warmup/cooldown.
- `app/slack/practices/announcements.py` - post/update hero + thread reply; thread `daylight`/`air_quality` params through.
- `app/scheduler.py` - fetch daylight + AQI alongside weather in the announce path.
- `app/agent/decision_engine.py` - reuse `get_daylight_info` / `get_air_quality` (no change, just import/use from the announce path).
- `app/slack/modals.py` + `app/slack/bolt_app.py` - workout-entry modal: drop warmup/cooldown, add Notes.
- `app/routes/admin_practices.py` - edit route persists `logistics_notes`, drops warmup/cooldown.
- `templates/admin/practices/detail.html`, `_detail_script.js`, `app/static/admin_practices.js`, `templates/admin/practices/config.html` - editor UI: add Notes, remove warmup/cooldown.
- `app/slack/blocks/coach_review.py` - audit warmup/cooldown usage (see §11).
- `scripts/` - new `activities_types_{export,apply}.py` (or similar) for normalization.
- Migration in `migrations/versions/`.

## 11. Risks & Open Questions

1. **Coach review surfaces still showing warmup/cooldown.** Default: remove from member-facing, keep coach-facing only if the coaches actually use them. Confirm during implementation whether `coach_review.py` should drop them too.
2. **Normalization regressions.** Any code that string-matches activity/type names (`has_intervals`, `_is_strength_practice`, summaries) must be audited before renaming. Mitigation: grep all name comparisons; prefer adding/relying on flags (`has_intervals` already exists on the type) over substring checks.
3. **AQI > 49 threshold is aggressive.** Most clean days sit 20-45, so the line will appear on moderate days. This is the user's explicit choice (value only, no advisory). Easy to tune the threshold later via config.
4. **Backfill for existing practices.** Practices announced before this change have no `slack_details_ts`; the update path must post the reply on first edit rather than assuming it exists.
5. **Thread reply notifications.** Threaded replies should not broadcast to the channel (`reply_broadcast = false`) to avoid double-pinging members.
6. **`@channel` (`<!channel>`) retained** in the hero CTA (drives the notification). Unchanged from current behavior.
7. **Live-tenant testing.** Local dev hits the real Slack workspace; use the designated test user/channel only when exercising posting paths.

## 12. Testing

- Unit tests for `build_practice_announcement_blocks` and `build_practice_details_blocks`: header label rendering (single activity, multi-activity, none → "Practice", strength), Notes shown/hidden, Social shown/hidden, intervals CTA clause, and conditional Conditions lines (wind present/absent, sunset vs headlamp, AQI hidden at ≤49 and shown at >49). Assert no em-dash characters in any rendered string.
- `has_intervals` and `_is_strength_practice` still behave after normalization (regression tests around renamed names).
- Refresh dispatcher test: editing a practice updates both hero and thread reply; missing `slack_details_ts` triggers a reply post.
- Follow existing block-builder test patterns in `tests/slack/`.
