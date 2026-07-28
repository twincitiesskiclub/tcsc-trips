# Task 5 Report: Seed script — practices, events, newsletter

(Note: this file previously held a report for an unrelated, differently-scoped
task — "lead picker stuck Loading + create/edit split documentation".
Overwritten with the current Task 5 report, per the per-task report
convention.)

## What I implemented

`scripts/ui_audit/seed_fixtures.py`:
- `seed_domain(core: dict) -> None` — populates every practices/events/newsletter/availability table on top of `seed_core()`'s output.
- `seed_all(volumes: dict | None = None) -> None` — calls `seed_core(volumes or default_volumes())` then `seed_domain(core)`.
- 18 new helper functions (`_make_practice_locations`, `_make_social_locations`, `_make_practice_activities`, `_make_practice_types`, `_practice_dates`, `_make_practices`, `_make_practice_leads`, `_make_practice_rsvps`, `_make_cancellation_requests`, `_make_availability_polls`, `_make_events`, `_make_event_price_options`, `_make_event_registrations`, `_make_newsletter_prompts`, `_make_newsletters`, `_make_newsletter_submissions`, `_make_status_changes`), following Task 4's `_make_x` naming and one-table(-family)-per-function pattern.

Tables populated, with real seeded counts from a full `seed_all()` run against `tcsc_trips`:

| Table | Count | Brief minimum | Notes |
|---|---:|---:|---|
| practice_locations | 4 | 3+ | Theodore Wirth, Hyland Hills, Elm Creek, Battle Creek |
| social_locations | 2 | — (added; config.html has a Social Locations tab) | |
| practice_types | 5 | 3+ | |
| practice_activities | 5 | 5+ | |
| practices | 36 | 12+ | Tue/Thu/Sat cadence, 6 weeks before → 6 weeks after `today_central()` |
| practice_leads | 44 | — | mix of confirmed/unconfirmed, lead/coach roles |
| practice_rsvps | 132 | — | past practices only |
| cancellation_requests | 7 | — (added; feeds `/admin/skipper`) | approved/rejected/pending/expired, none contradicting `Practice.status` |
| lead_availability_polls | 3 | — (deliberate divergence, prod=0) | one each of draft/open/closed |
| lead_availability_responses | 17 | — (deliberate divergence, prod=0) | |
| events | 3 | 2+ | one each of draft/active/closed |
| event_price_options | 6 | 3+ | 2 per event |
| event_registrations | 9 | 5+ | all 4 `RegistrationStatus` values represented |
| event_participants | 18 | — (deliberate divergence, prod=0) | |
| newsletter_prompts | 3 | 1+ | one per `PROMPT_DEFINITIONS` name (main/quiet/final) — deliberate divergence, prod=0 |
| newsletters | 3 | — | 2 published, 1 building |
| newsletter_submissions | 4 | — | mixed statuses, one with `newsletter_id=None` |
| status_changes | 28 | — (deliberate divergence, prod=0) | one per DROPPED user |

## What I tested and results

- `.venv-linux/bin/python -m pytest tests/test_ui_audit_seed.py -v` → **18 passed** (11 pre-existing Task 4 tests unchanged + 7 new).
- `./run-tests.sh -q` → **1589 passed** (baseline 1582 + the 7 new tests I added; zero regressions, zero reduction from baseline).
- Manually seeded the real dev DB (`tcsc_trips`) via `seed_all()` and eyeballed row counts and status distributions (see tables above and enum-check section below).
- Dispatched a smoke-test subagent that started the Flask app against the freshly-seeded `tcsc_trips` DB and curled 10 admin routes with a real signed session cookie (`admin_required` gate). All 10 returned 200 with legitimate rendered content, no tracebacks: `/admin/practices/`, `/admin/practices/1`, `/admin/practices/config`, `/admin/events`, `/admin/events/1/edit`, `/admin/events/1/registrations`, `/admin/newsletter/prompts`, `/admin/skipper/`, `/admin/availability/` (JSON, 3 polls), `/admin/users/4` (a DROPPED user).

## TDD Evidence

**RED** — `git stash push -- scripts/ui_audit/seed_fixtures.py` (test file changes kept), then:
```
.venv-linux/bin/python -m pytest tests/test_ui_audit_seed.py -v -k domain
```
```
tests/test_ui_audit_seed.py::test_domain_tables_are_populated FAILED     [100%]
...
E       ImportError: cannot import name 'seed_domain' from 'scripts.ui_audit.seed_fixtures'
=========================== short test summary info ============================
FAILED tests/test_ui_audit_seed.py::test_domain_tables_are_populated - Import...
======================= 1 failed, 17 deselected in 1.31s =======================
```
Expected and correct: `seed_domain` didn't exist yet.

`git stash pop` restored the implementation.

**GREEN**:
```
.venv-linux/bin/python -m pytest tests/test_ui_audit_seed.py -v
```
```
============================== 18 passed in 3.60s ==============================
```

## Model fields discovered/corrected versus the brief

The brief's Step 1 `sed -n` ranges were a starting point; I read the full model files plus `app/practices/availability_models.py`, `app/practices/interfaces.py`, `app/newsletter/interfaces.py`, and `app/models.py`'s `StatusChange`, none of which the brief mentioned at all despite `LeadAvailabilityPoll`/`StatusChange` being required by the brief's own "deliberate divergences" list.

- **`Event.status` has no `"published"` value.** The brief's Step 4 explicitly says "Seed at least one `published` event too." `EventStatus.ALL = ["draft", "active", "closed"]` (`app/events/models.py`), and both `event_form.html`'s `<select>` and `events.html`'s filter pills offer exactly those three. I used `"active"` for the live/accepting-registrations event instead of inventing `"published"` — this is exactly the Task-4-taught failure mode (seed a value the template can't render) the brief itself warned me to watch for, and the brief's own instruction was wrong about it.
- **`LeadAvailabilityPoll`/`Participant`/`Response` live in `app/practices/availability_models.py`, not `app/practices/models.py`** — a separate file the brief's Step 1 `sed` ranges never touch. Required reading it in full to get `PollStatus`/`ParticipantStatus` (plain string classes, not Enums) and the FK/unique-constraint shape (`uq_poll_emoji`, `uq_poll_practice`, `uq_poll_participant`, `uq_poll_practice_user`).
- **`StatusChange` lives in `app/models.py`**, not a practices/events/newsletter file at all — the brief's "deliberate divergence" list names `status_changes` but never says where the model is.
- **`PracticeLead.role` is a free-text `String(20)`, not constrained to `LeadRole`'s three values at the DB level** — `admin_practices.py` has a comment that `role='assist'` is "retired" but still read; I used only `lead`/`coach` (the two the `_detail_context.js` role-label map actually formats), leaving `assist` out rather than seeding a value described in-repo as deprecated.
- **`EventRegistration`/`EventParticipant` have six and five `nullable=False` columns respectively** with no defaults (`contact_email`, `contact_phone`, `emergency_contact_name`, `emergency_contact_phone`, `amount_cents`, `status` for the former; `position`, `role_label`, `name`, `date_of_birth`, `email`, `phone` for the latter) — all supplied.
- **`NewsletterPrompt.name` is only meaningfully rendered for three exact values** (`'main'`, `'quiet'`, `'final'`) — not enforced at the DB level, but `admin_newsletter.py`'s `/prompts/data` route iterates `PROMPT_DEFINITIONS.items()` (a hardcoded 3-key dict) and only surfaces a DB prompt whose `name` matches one of those keys. A prompt seeded with any other name would silently never appear in the admin UI despite existing in the table. Used exactly those three.
- **`Newsletter` requires `week_start`/`week_end` even for monthly newsletters** — nullable=False columns that predate the monthly-dispatch fields; the model's own `get_or_create_current_month` classmethod sets `week_start=period_start, week_end=period_end` as a compatibility shim, which I copied rather than leaving them null.

## Template-vocabulary check

Grepped the actual rendering template for every seeded status/enum, not the model or `app/constants.py`:

| Field | Template(s) checked | Values found | Values seeded |
|---|---|---|---|
| `Practice.status` | `app/templates/admin/practices/list.html` (filter `<select>`), `.../detail.html` (edit `<select>`) | scheduled, confirmed, in_progress, cancelled, completed | all 5 |
| `Event.status` | `app/templates/admin/event_form.html` (`<select>`), `.../events.html` (filter `<option>`s) | draft, active, closed | all 3 |
| `EventRegistration.status` | `app/templates/admin/event_registrations.html` (filter `<select>`) | pending_payment, confirmed, cancelled, refunded | all 4 |
| `PracticeLead.role` | `app/templates/admin/practices/_detail_context.js` (role→label map) | lead, coach (assist retired per code comment) | lead, coach |
| `LeadAvailabilityPoll.status` | `app/static/admin_practices.js`'s `POLL_STATUS_LABEL` (backs the `/admin/availability/`-driven poll widget on the practices list page) | draft, open, closed | all 3 |
| `LeadAvailabilityParticipant.status` | not template-rendered (JSON dashboard doesn't surface participant rows directly) | — | pending, responded, done (model-defined values, no divergence risk) |
| `RSVPStatus`, `CancellationStatus` | not rendered by any admin `<select>`; used only by internal Skipper/RSVP logic | — | model's own enum values |

Verified via direct `docker exec ... psql` queries after seeding `tcsc_trips` (see table in "What I implemented") that every value above actually appears in the seeded rows, and via the smoke-test subagent that the pages rendering them return 200 with no template errors.

## Dev-DB check

Before: `docker exec tcsc-postgres psql -U tcsc -d tcsc_trips` — `users=0, practices=0, events=0, newsletters=0, payments=1`.

Ran the full suite (`./run-tests.sh -q`, 1589 passed) between the before/after snapshots.

After: identical — `users=0, practices=0, events=0, newsletters=0, payments=1`. The dev database was untouched by the test run. (It was then *deliberately* seeded in a separate, later step per the brief's Step 6, using a plain script invocation with `DATABASE_URL` pointed at `tcsc_trips` — not part of the test suite. `tcsc_trips` now holds the seeded practices/events/newsletter data for the upcoming screenshot pass.)

The `tests/test_ui_audit_seed.py::app` fixture creates/drops its own `tcsc_trips_uiaudit_test` database each session, matching Task 4's established pattern; I extended it, not a second mechanism. Confirmed the throwaway DB doesn't linger after the run (`psql \l` shows no `uiaudit` database post-run).

## Files changed

- `/workspace/tcsc-trips/scripts/ui_audit/seed_fixtures.py` — added `seed_domain()`, `seed_all()`, and their helpers (+760 lines; file is now 1121 lines total).
- `/workspace/tcsc-trips/tests/test_ui_audit_seed.py` — added 7 tests (+105 lines; file is now 372 lines total): `test_domain_tables_are_populated`, `test_practices_span_past_and_future`, `test_every_practice_status_is_represented`, `test_every_event_status_is_represented_by_the_edit_forms_vocabulary`, `test_every_registration_status_is_represented`, `test_status_changes_populated_for_dropped_users`, `test_seed_all_runs_end_to_end`.

## Self-review

- **Completeness:** every table in the brief's Step 4 list is populated, at or above the stated minimums. All five deliberate-divergence tables (`event_registrations`, `event_participants`, `newsletter_prompts`, `lead_availability_polls`/`_responses`, `status_changes`) are populated. `events.status` covers all 3 real values, not just `draft` (brief's `published` request was invalid — used `active`, the real live-registration state).
- **Quality:** every seed value was checked against the model's `nullable=False` columns and the rendering template, not guessed. Comments explain *why* a value was chosen where it isn't obvious (e.g. why `CancellationRequest.status='rejected'` is never attached to a `Practice.status='cancelled'` row).
- **Discipline:** stayed inside `_make_x` function-per-table(-family) pattern from Task 4; no new seeding mechanism invented. Added `SocialLocation` and `CancellationRequest` seeding beyond the brief's literal minimum list because both back real admin panes (config.html's Social Locations tab; `/admin/skipper`) that would otherwise render empty — flagged here rather than silently over-scoping.
- **Testing:** all new tests hit the real dedicated `tcsc_trips_uiaudit_test` database through Task 4's existing fixtures, no mocks. Determinism: `seed_domain` seeds a fresh `Random(SEED)` per call, matching `seed_core`'s pattern, though I did not add an explicit `test_seed_domain_is_deterministic` test mirroring `test_seed_is_deterministic` (see concerns below).
- **Correctness:** every seeded enum value cross-checked against its actual rendering template (see table above), and empirically confirmed present in the seeded `tcsc_trips` rows.
- **Safety:** dev DB (`tcsc_trips`) row counts identical before/after the full test suite run; `tcsc_trips_uiaudit_test` is created and dropped per session, confirmed absent afterward.

## Issues or concerns — DONE_WITH_CONCERNS

1. **File size.** `scripts/ui_audit/seed_fixtures.py` is now 1121 lines (up from 370 after Task 4). Per the task instructions I'm flagging this rather than splitting it unilaterally. A natural split would be `seed_fixtures_core.py` (Task 4's content) + `seed_fixtures_domain.py` (this task's content), re-exported from a package `__init__.py` or a thin `seed_fixtures.py` — but that's a call for whoever reviews both tasks together, not mine to make solo mid-task.
2. **No `test_seed_domain_is_deterministic` test.** Task 4 has `test_seed_is_deterministic` for `seed_core`; I did not add an equivalent for `seed_domain`, even though I designed it to be deterministic (fresh `Random(SEED)` per call, no wall-clock-seeded randomness). The one genuinely non-deterministic input is `today_central()` itself, which the practice/poll/event date math is anchored to — a determinism test would need to freeze that (e.g. via `freezegun` or a monkeypatched `today_central`), which the existing test file doesn't have infrastructure for. I judged this an acceptable gap given time, but a reviewer may want it added.
3. **`CancellationRequest` and `SocialLocation` seeding exceed the brief's literal Step 4 list.** Both are cheap and back real admin surfaces (see above), but flagging in case a reviewer wants them trimmed for strict brief-scope adherence.
