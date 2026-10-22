# Trip Scholarships Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mitchell sends one-time $100 trip scholarship codes from an admin page; each member gets a Slack DM whose button reveals their code; the code takes the amount off any trip registration for that member only.

**Architecture:** One new table (`trip_scholarships`) plus a nullable `trip_registrations.scholarship_id`. A scholarship's state (available / held / used) is derived from the registrations that point at it, so lottery release frees a code with no webhook or capture changes. Logic lives in a new `app/trips/scholarships.py`; Slack blocks join the other trip blocks; the Bolt action is a thin wrapper.

**Tech Stack:** Flask, SQLAlchemy + Alembic, PostgreSQL, Stripe PaymentIntents (manual capture, unchanged), Slack Bolt (socket mode), vanilla JS admin page.

**Spec:** `docs/superpowers/specs/2026-10-22-trip-scholarships-design.md`

## Global Constraints

- Prices in cents. Default scholarship `amount_cents = 10000`.
- Discounted amount: `max(tier_price - scholarship.amount_cents, 50)`.
- Trips stay `capture_method='manual'`. Do not touch `/admin/payments/<id>/capture` or `/admin/payments/bulk-capture`.
- Code format `TCSC-` + 6 chars from `ABCDEFGHJKMNPQRSTUVWXYZ23456789` (no 0/O/1/I/L). Stored uppercase; input matched after `.strip().upper()`.
- One scholarship per (`user_id`, `season_id`); `season_id` = `Season.get_current()` at send time.
- "Held" = linked registration `pending`, or `pending_payment` with `created_at >= utcnow() - PENDING_HOLD_WINDOW` (from `app/trips/service.py`). "Used" = linked registration `confirmed`.
- Error copy, exact: `That code doesn't match this member.` and `This code is already in use on {trip.name}.`
- Mitchell's Slack ID constant: `MITCHELL_SLACK_UID = "U045LF8PCSW"`.
- No em dashes in any copy (Rob's rule).
- Scholarship amounts in copy are whole dollars when even (`$100`, not `$100.00`); `_money` stays as is for other surfaces.
- DB timestamps UTC; display Central via `format_datetime_central`.
- Slack helpers never raise into callers (same contract as `app/slack/trips.py`).
- Tests run against the scratch DB: `DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test ../../env/bin/pytest ...` (Task 1 makes `tests/trips` honor it). Never run against `tcsc_trips` (dev DB is on another branch's schema).

## Review Focus

1. A member whose card fails retries with the code: the reused row keeps one link; retrying with the box blank clears it (Task 2 test `test_retry_without_code_clears_link`).
2. Code typed lowercase with spaces (` tcsc-7kq2m9 `) is accepted (Task 2 `test_code_is_case_and_space_insensitive`).
3. An abandoned `pending_payment` older than the hold window on Trip A does not block the code on Trip B (Task 2 `test_stale_pending_payment_does_not_hold_code`).
4. Mitchell double-clicks Send: no second scholarship and no second DM for the same member (Task 4 `test_send_skips_existing_recipients`).
5. Button clicked twice, or by a Slack user who isn't the recipient: second click re-renders the same code without changing `claimed_at`; a stranger gets nothing (Task 3 `test_reveal_is_idempotent`, `test_reveal_rejects_other_user`).

---

### Task 1: Model, migration, code generation, derived state

**Files:**
- Modify: `app/trips/models.py` (add `TripScholarship`; add `TripRegistration.scholarship_id` + relationship)
- Create: `migrations/versions/a7c3e9d2b4f1_trip_scholarships.py` (down_revision `f4b8d2a6c1e9`)
- Modify: `tests/practices/test_practice_migration_release.py:28` (`HEAD_REVISION = "a7c3e9d2b4f1"`)
- Create: `app/trips/scholarships.py`
- Modify: `tests/trips/conftest.py` (honor `DATABASE_URL` like `tests/events/conftest.py:37-41`; delete `TripScholarship` rows for test users in `_delete_test_trips` before deleting users, and null `scholarship_id` via the registration delete order)
- Test: `tests/trips/test_scholarships.py`

**Interfaces:**
- Produces:
  - `TripScholarship` columns: `id`, `user_id` (FK users, not null), `season_id` (FK seasons, not null), `amount_cents` (int, not null, default 10000), `code` (String(16), unique, not null), `sent_at`, `claimed_at`, `slack_channel_id`, `slack_message_ts`, `created_at`. `UniqueConstraint("user_id", "season_id", name="uq_trip_scholarship_member_season")`. Relationships `user`, `season`, `registrations` (backref `scholarship` on `TripRegistration`).
  - `generate_code() -> str`
  - `active_registration(scholarship) -> TripRegistration | None` (the held or used one; prefers confirmed)
  - `scholarship_state(scholarship) -> str` returning `"available" | "held" | "used"`

- [ ] **Step 1: Bring the scratch DB to main's head.** Run from the worktree: `DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test TCSC_MIGRATION_ONLY=1 SLACK_APP_TOKEN= ../../env/bin/flask db upgrade`. Expected: `alembic_version` reads `f4b8d2a6c1e9`. Copy `../../.env` and `../../.env.uiaudit` into the worktree if absent.

- [ ] **Step 2: Write failing tests** in `tests/trips/test_scholarships.py` (fixtures: an ACTIVE user `trip-member@example.com`, current season via `Season.get_current()`, two trips from the conftest slugs):
  - `test_generate_code_format`: `re.fullmatch(r"TCSC-[ABCDEFGHJKMNPQRSTUVWXYZ23456789]{6}", generate_code())`.
  - `test_state_available_without_registrations`: `scholarship_state(s) == "available"`.
  - `test_state_held_by_pending`: registration `status="pending"`, `scholarship_id=s.id` → `"held"`, `active_registration(s)` is that row.
  - `test_state_used_by_confirmed` → `"used"`.
  - `test_state_freed_by_cancelled`: only a `cancelled` linked row → `"available"`.
  - `test_unique_per_member_season`: second row same user+season raises `IntegrityError`.

- [ ] **Step 3: Run** `... pytest tests/trips/test_scholarships.py -v`. Expected: FAIL (ImportError).

- [ ] **Step 4: Implement** model, migration (create table + add nullable FK column `scholarship_id` on `trip_registrations`, downgrade drops both), `HEAD_REVISION` bump, and the three functions. `generate_code` uses `secrets.choice`; callers retry on collision (Task 4).

- [ ] **Step 5: Apply migration to scratch DB** (same command as Step 1). Expected: head `a7c3e9d2b4f1`.

- [ ] **Step 6: Run** `tests/trips/test_scholarships.py tests/practices/test_practice_migration_release.py`. Expected: PASS.

- [ ] **Step 7: Commit** `feat(trips): trip scholarship model and derived state`.

### Task 2: Registration accepts a scholarship code

**Files:**
- Modify: `app/trips/scholarships.py` (add `resolve_code`)
- Modify: `app/trips/service.py` `create_registration` (~line 225)
- Modify: `app/routes/trips.py` `register_for_trip` (PaymentIntent metadata)
- Modify: `app/templates/trips/register.html` (field after `#price-tiers` fieldset), `app/static/trip_registration.js` (send `scholarship_code`; add `'scholarship_code': 'scholarship-code'` to the error-field map near line 289)
- Test: `tests/trips/test_service.py`, `tests/trips/test_routes.py`

**Interfaces:**
- Consumes: Task 1 model, `active_registration`, `PENDING_HOLD_WINDOW`.
- Produces: `resolve_code(user, trip, raw_code) -> tuple[TripScholarship | None, str | None]` returning `(scholarship, None)` on success, `(None, error_message)` on failure, `(None, None)` when `raw_code` is blank. A held registration on the *same* trip is not a conflict.

- [ ] **Step 1: Write failing service tests** (`tests/trips/test_service.py`), payload as existing tests build it plus `scholarship_code`:
  - `test_code_discounts_low_tier`: trip `price_low=11000`, code for the member → `registration.amount_cents == 1000`, `registration.scholarship_id == s.id`.
  - `test_code_discounts_high_tier`: `price_high=13000` → `3000`.
  - `test_discount_floors_at_50_cents`: `price_low=9000` → `50`.
  - `test_code_is_case_and_space_insensitive`: `" " + s.code.lower() + " "` accepted.
  - `test_unknown_code_rejected`: `TripRegistrationError` with `errors["scholarship_code"] == "That code doesn't match this member."`.
  - `test_other_members_code_rejected`: same message.
  - `test_code_held_on_other_trip_rejected`: pending linked row on trip A, register trip B → `"This code is already in use on {tripA.name}."`.
  - `test_code_freed_after_cancel`: linked row on trip A `cancelled` → trip B accepted.
  - `test_stale_pending_payment_does_not_hold_code`: trip A row `pending_payment`, `created_at` 2h ago → trip B accepted.
  - `test_retry_without_code_clears_link`: register with code (row stays `pending_payment`), register again with blank code → same row, `scholarship_id is None`, `amount_cents == trip.price_low`.
- [ ] **Step 2: Write failing route test** (`tests/trips/test_routes.py`, existing Stripe mock pattern): `test_register_with_code_sets_intent_amount_and_metadata`: `PaymentIntent.create` called with `amount=1000` and `metadata["scholarship_id"] == str(s.id)`; without a code, metadata has no `scholarship_id` key.
- [ ] **Step 3: Run** both files. Expected: new tests FAIL.
- [ ] **Step 4: Implement.** In `create_registration`, call `resolve_code` after the tier is chosen; on error put it in `errors["scholarship_code"]`; on success apply the floor formula. Always assign `registration.scholarship_id` (the scholarship's id or `None`) so a reused row never keeps a stale link. In the route, add `scholarship_id` to metadata only when set.
- [ ] **Step 5: Form.** One optional text input `id="scholarship-code"`, `name="scholarship_code"`, label `Scholarship code`, help text `Got a trip scholarship? Enter your code. We'll apply it when you submit.`, `autocomplete="off"`, with the same error element pattern as other fields. The JS sends it trimmed; the hold summary keeps using the server's `amountCents`. No client-side discount math.
- [ ] **Step 6: Run** `tests/trips/`. Expected: PASS (compare against a baseline run of `tests/trips` on the base commit if anything unrelated fails).
- [ ] **Step 7: Commit** `feat(trips): apply a scholarship code at registration`.

### Task 3: Slack DM, reveal, and the Bolt action

**Files:**
- Modify: `app/slack/blocks/trips.py` (offer + revealed blocks and fallbacks)
- Modify: `app/trips/scholarships.py` (`send_scholarship_dm`, `reveal`, `open_trips`)
- Modify: `app/slack/bolt_app.py` (action `trip_scholarship_reveal`, next to the other block actions)
- Test: `tests/trips/test_scholarships.py`, `tests/trips/test_slack.py`

**Interfaces:**
- Consumes: Task 1 model/state; `get_slack_client()`; `base_url()` from `app/slack/trips.py`.
- Produces:
  - `build_scholarship_offer_blocks(scholarship) -> list`, `scholarship_offer_fallback(scholarship) -> str`
  - `build_scholarship_revealed_blocks(scholarship, applied_registration, open_trips, base_url) -> list`, `scholarship_revealed_fallback(scholarship) -> str`
  - `open_trips(now=None) -> list[Trip]`: `status == "active"`, has a series, and `signup_start <= now <= signup_end`, ordered by `signup_end`. Links use `{base_url}/{trip.series.slug}/register`.
  - `send_scholarship_dm(scholarship) -> bool`: posts the offer to the member's `slack_user.slack_uid`, stores `slack_channel_id` (response `channel`), `slack_message_ts` (response `ts`), `sent_at`; returns False (never raises) when no Slack link or the call fails.
  - `reveal(scholarship_id, slack_uid, now=None) -> list | None`: None when the scholarship is missing or `slack_uid` isn't the member's; else sets `claimed_at` if empty, commits, returns revealed blocks.

- [ ] **Step 1: Failing block tests** (`tests/trips/test_slack.py`, member first name `Mira`, `amount_cents=10000`), exact copy from the spec:
  - Offer text contains `Hi Mira, you're getting a TCSC trip scholarship: $100 off one trip this season, thanks to our sponsors Twin Cities Orthopedics and Kwik Trip. Tap the button to get your code. Questions? Ask <@U045LF8PCSW>.` and one button `action_id == "trip_scholarship_reveal"`, `value == str(s.id)`, text `Get my code`.
  - Revealed, no applied registration: contains `Your code: *{s.code}*` and `Enter it in the Scholarship code box when you register for a trip at tcsc.ski. It takes $100 off either price and only works for you. If you aren't picked in a trip lottery, the code comes back for another trip.`; no `actions` block.
  - Revealed with one open trip: contains `Open now: <{base}/training-trip/register|Hayward Training Trip> (registration closes {format_datetime_central(trip.signup_end)})`. With no open trips the "Open now" line is absent.
  - Revealed with an applied registration: contains `Already applied to Hayward Training Trip: we'll take $100 off when your spot is confirmed.` and not the "Enter it" sentence.
  - Copy contains no `—` or `–`.
- [ ] **Step 2: Failing logic tests** (`tests/trips/test_scholarships.py`, mock `get_slack_client`):
  - `test_send_dm_stores_message_ref`: mock returns `{"channel": "D1", "ts": "1.2"}` → True; fields stored; `sent_at` set.
  - `test_send_dm_without_slack_link_returns_false`: no `slack_user` → False, `sent_at is None`, no client call.
  - `test_send_dm_swallows_slack_error`: client raises → False.
  - `test_reveal_sets_claimed_at`, `test_reveal_is_idempotent` (second call returns equal blocks, `claimed_at` unchanged), `test_reveal_rejects_other_user` (returns None, `claimed_at is None`).
  - `test_open_trips_window`: one trip open, one closed, one draft → only the open one.
- [ ] **Step 3: Run.** Expected: FAIL.
- [ ] **Step 4: Implement** blocks (use `guard_slack_blocks`/`guard_fallback_text` with `surface="trip_scholarship"`), the three functions, and the Bolt handler: `ack()`, call `reveal(int(action["value"]), body["user"]["id"])`, and on a non-None result `client.chat_update(channel=body["channel"]["id"], ts=body["message"]["ts"], blocks=blocks, text=scholarship_revealed_fallback(...))`. Log and return on any exception. Run inside the app context the way neighboring handlers do.
- [ ] **Step 5: Run** `tests/trips/`. Expected: PASS.
- [ ] **Step 6: Commit** `feat(trips): scholarship DM with a reveal button`.

### Task 4: Admin scholarships page

**Files:**
- Modify: `app/routes/admin.py` (three routes beside the other `/admin/trips` routes)
- Modify: `app/trips/scholarships.py` (`issue_scholarships`, `scholarship_rows`)
- Create: `app/templates/admin/trip_scholarships.html`, `app/static/admin_trip_scholarships.js`
- Modify: `app/templates/admin/trips.html` (a "Scholarships" link in `.tl-head` next to the new-trip link)
- Test: `tests/trips/test_admin.py`

**Interfaces:**
- Consumes: Tasks 1 and 3.
- Produces:
  - `issue_scholarships(user_ids: list[int], amount_cents: int) -> list[dict]`: one dict per requested id: `{"user_id", "name", "status"}` with status `"sent" | "no_slack" | "send_failed" | "already_has_one" | "not_active"`. Requires a current season (raises `ValueError("No current season.")` otherwise). Creates rows with `generate_code()` (retry on `IntegrityError` for code collisions), commits, then calls `send_scholarship_dm`.
  - `scholarship_rows(season) -> list[dict]`: `{"id", "name", "email", "code", "amount_cents", "sent_at", "claimed_at", "state", "trip_name"}`, times formatted Central, sorted by name.
  - Routes (all `@admin_required`): `GET /admin/trips/scholarships` renders the page with active members (`User.status == UserStatus.ACTIVE`, sorted by last, first) and `scholarship_rows`; `POST /admin/trips/scholarships/send` JSON `{"user_ids": [...], "amount_dollars": 100}` → `{"results": [...]}`; `POST /admin/trips/scholarships/<int:scholarship_id>/resend` → `{"success": bool}` (posts a new DM, overwrites the message ref).

- [ ] **Step 1: Failing tests** (`tests/trips/test_admin.py`, existing admin-login pattern, Slack mocked):
  - `test_page_lists_scholarships`: GET 200, body contains the member name and code.
  - `test_send_creates_and_dms`: POST one active Slack-linked user, `amount_dollars: 100` → result `"sent"`, row `amount_cents == 10000`, client called once.
  - `test_send_skips_existing_recipients`: POST the same user twice → second result `"already_has_one"`, one row, client called once total.
  - `test_send_reports_no_slack`: user without Slack link → `"no_slack"`, row exists with `sent_at is None`.
  - `test_send_rejects_inactive_member`: ALUMNI user → `"not_active"`, no row.
  - `test_resend_posts_new_dm`: resend → `{"success": True}`, new `slack_message_ts` stored.
  - `test_routes_require_admin`: anonymous GET/POST → redirect or 403, matching other admin trip routes.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement** functions and routes.
- [ ] **Step 4: Page.** Match `admin/trips.html`'s scoped style. Top: filter input over a checkbox list of active members (name + email), amount input (dollars, default 100), Send button disabled until one box is checked; after Send, show per-member results inline and reload the table. Below: table of `scholarship_rows` (Member, Code, Sent, Clicked, State with trip name, Resend button). JS follows `admin_trip_registrations.js` (`fetchJSON`/`postJSON`, same CSRF handling, if any).
- [ ] **Step 5: Run** `tests/trips/`. Expected: PASS. Then render the page locally via the dev server or `scripts.ui_audit.serve` and screenshot at 390px and desktop width (see memory: headless chromium screenshots).
- [ ] **Step 6: Commit** `feat(admin): trip scholarships page`.

### Task 5: One-off for members already registered

**Files:**
- Create: `scripts/link_scholarship_registrations.py`
- Test: `tests/trips/test_scholarships.py`

**Interfaces:**
- Consumes: Task 1.
- Produces: `link_registrations(registration_ids: list[int], dry_run: bool = True) -> list[str]` (one line per id) and a `__main__` taking ids as argv plus `--apply`.

- [ ] **Step 1: Failing tests:**
  - `test_link_sets_scholarship_and_keeps_amount`: pending registration, member has an available scholarship, `dry_run=False` → `scholarship_id` set, `amount_cents` unchanged, state `"held"`.
  - `test_link_dry_run_changes_nothing`.
  - `test_link_refuses_member_without_scholarship` and `test_link_refuses_code_held_elsewhere`: line contains `refused`, nothing written.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** Script header documents prod usage: `TCSC_MIGRATION_ONLY=1`, `SLACK_APP_TOKEN` unset, `DATABASE_URL=$PROD_DATABASE_URL`, dry run first.
- [ ] **Step 4: Run** `tests/trips/`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(scripts): link existing trip registrations to scholarships`.

### Task 6: Full verification and PR

- [ ] **Step 1:** Baseline: on the base commit `5f031be7`, run `tests/trips tests/practices/test_practice_migration_release.py tests/routes` against the scratch DB; save failures. Then run the same on the branch. Expected: no new failures.
- [ ] **Step 2:** `git grep -n $'—' -- app/slack/blocks/trips.py app/templates/trips/register.html app/templates/admin/trip_scholarships.html` returns nothing.
- [ ] **Step 3:** Run `/simplify` on the branch diff, then push and open the PR. The body lists the rollout steps from the spec and the two prod registrations (Mira Tomten, Katherine Koehler) for Task 5's script.
