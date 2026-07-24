# Generic Events System + Dry Tri 2026 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Google-Forms-plus-bitly event signups with a generic Events system (models, public register+pay page, admin tab), fold Social Events into it, and ship Dry Tri 2026 as a draft event — deployed to prod tonight.

**Architecture:** New `app/events/` package (Event / EventPriceOption / EventRegistration / EventParticipant) with zero FKs to member tables. Payments reuse the existing `Payment` table + Stripe webhook with a new `payment_type='event'`. Event-type templates live in `config/event_templates.yaml` and are copied into events at creation. SocialEvent is migrated in and retired.

**Tech Stack:** Flask + SQLAlchemy + Alembic (Flask-Migrate), Stripe PaymentIntents (automatic capture), Tabulator.js admin grids, pytest with PostgreSQL fixtures.

**Spec:** `docs/superpowers/specs/2026-07-24-generic-events-system-design.md` — read it first; it is the authority on behavior.

## Global Constraints

- Prices in **cents** (5500 = $55.00). Timestamps stored naive-UTC, displayed US Central (`app/utils.py` helpers).
- Event registrants must **never** create/lookup `User` rows. No FKs from event tables to `users`/`user_seasons`.
- `PaymentType` and status constants are **plain string classes** (like `app/constants.py` — no Enum `.value`).
- Statuses: Event `draft|active|closed`; EventRegistration `pending_payment|confirmed|cancelled|refunded`; audience `internal|external|both`.
- Dry Tri prices: Individual **5500**, Team of 3 **10500**, Run-only 6K **3000** (individual-only). Long/short course same price.
- Public POST endpoints follow existing CSRF pattern (`csrf_meta_tag()` + `csrf.js`); admin routes use the existing `@admin_required`-style decorator found in `app/routes/admin.py` (copy its actual name/usage).
- Server computes price; never trust client-side amounts. Discount code matches case-insensitively, trimmed.
- Follow existing code style: blueprints in `app/routes/`, models mirroring `app/practices/models.py` package pattern, admin grids mirroring `admin_social_events.js` / `admin/social_events.html`.
- Every task: run its tests, then run the FULL suite (`pytest`) before commit. All 124 existing tests must stay green until Task 6 (which removes SocialEvent and updates its tests), then the full suite must be green again.
- Commit after every green task. Do not push until Task 8.

---

### Task 1: Events models + PaymentType.EVENT + schema migration

**Files:**
- Create: `app/events/__init__.py`, `app/events/models.py`
- Modify: `app/constants.py` (PaymentType), `app/models.py` (Payment: add `event_registration_id`)
- Create: migration via `flask db migrate` (then hand-verify)
- Test: `tests/events/__init__.py`, `tests/events/test_models.py`

**Interfaces:**
- Consumes: `db` from `app.models`.
- Produces: `Event`, `EventPriceOption`, `EventRegistration`, `EventParticipant` (fields per spec tables, exactly); `PaymentType.EVENT = 'event'` (added to `PaymentType.ALL`); `Payment.event_registration_id` (nullable FK → `event_registrations.id`) with backref `payments` on EventRegistration.

Model specifics (copy spec field tables verbatim; notes):
- `Event.custom_questions` and `EventPriceOption.participant_roles` use `db.JSON`. `Event.slug` unique+indexed. Defaults: `status='draft'`, `audience='both'`, `custom_questions=[]`.
- `EventPriceOption.participant_count` is a property: `len(self.participant_roles or ["Participant"])`.
- Relationships: `Event.price_options` (ordered by `sort_order`, cascade delete-orphan), `Event.registrations`, `EventRegistration.participants` (ordered by `position`, cascade delete-orphan).
- Helper: `Event.confirmed_count` property → count of registrations with status `confirmed`.
- Class constants on models (strings, not Enums): `EventStatus`, `RegistrationStatus`, `Audience` in `app/events/models.py`.

- [ ] **Step 1: Write failing tests** — `tests/events/test_models.py` (use the `app`/`db` fixture pattern from `tests/newsletter/conftest.py` — copy its conftest shape into `tests/events/conftest.py`):

```python
def test_event_with_options_and_registration(db_session):
    event = Event(slug='dry-tri-2026', name='Dry Tri', location='Carver Park',
                  event_date=datetime(2026, 10, 24, 9, 0),
                  signup_start=datetime(2026, 8, 1), signup_end=datetime(2026, 10, 22),
                  custom_questions=[{'key': 'course', 'label': 'Course?', 'type': 'choice',
                                     'options': ['Long', 'Short'], 'required': True}])
    opt = EventPriceOption(name='Team of 3', price_cents=10500,
                           participant_roles=['Rollerskier', 'Mountain Biker', 'Trail Runner'])
    event.price_options.append(opt)
    db_session.add(event); db_session.commit()
    assert opt.participant_count == 3
    reg = EventRegistration(event_id=event.id, price_option_id=opt.id,
                            contact_email='cap@x.com', contact_phone='555',
                            emergency_contact_name='EC', emergency_contact_phone='911',
                            amount_cents=10500, status='pending_payment',
                            answers={'course': 'Long'})
    reg.participants.append(EventParticipant(position=1, role_label='Rollerskier',
                                             name='A B', date_of_birth=date(1990, 1, 1),
                                             email='a@x.com', phone='1'))
    db_session.add(reg); db_session.commit()
    assert event.confirmed_count == 0
    reg.status = 'confirmed'; db_session.commit()
    assert event.confirmed_count == 1

def test_payment_links_to_event_registration(db_session):
    # Payment(payment_type='event', event_registration_id=reg.id) round-trips
    ...

def test_event_tables_have_no_user_fk():
    from app.events import models as m
    for table in (m.Event.__table__, m.EventRegistration.__table__,
                  m.EventParticipant.__table__, m.EventPriceOption.__table__):
        for fk in table.foreign_keys:
            assert 'users' not in fk.target_fullname
```

- [ ] **Step 2: Run** `pytest tests/events/ -v` → FAIL (import errors).
- [ ] **Step 3: Implement** models per spec; add `EVENT = 'event'` to `PaymentType` and to `ALL`; add `event_registration_id = db.Column(db.Integer, db.ForeignKey('event_registrations.id'), nullable=True)` to Payment. Import the events models in `app/__init__.py` (like newsletter models) so Alembic sees them.
- [ ] **Step 4: Generate migration** — `TCSC_MIGRATION_ONLY=1 flask db migrate -m "add events tables"` (dev DB via `scripts/dev.sh` postgres container must be running; start it if not). Inspect the generated file: 4 new tables + payments column, nothing else (no drops).
- [ ] **Step 5: Apply + test** — `flask db upgrade`; `pytest tests/events/ -v` → PASS; full `pytest` → green.
- [ ] **Step 6: Commit** — `feat(events): add Event models, payment type, and schema migration`

---

### Task 2: Event templates config + loader

**Files:**
- Create: `config/event_templates.yaml`, `app/events/templates.py`
- Test: `tests/events/test_templates.py`

**Interfaces:**
- Produces: `load_event_templates() -> dict[str, dict]` (cached read of YAML, validates shape, raises `ValueError` on malformed), `get_template(key) -> dict | None`, `apply_template(event: Event, template_key: str) -> None` (sets `event.custom_questions`, `event.template_key`, and appends `EventPriceOption` rows — pure copy, no commit).

YAML content (exact — this is the seed data from the 2025 Google Forms):

```yaml
templates:
  dry_tri:
    name: Dry Tri (race)
    price_options:
      - name: Individual
        description: Complete all three legs yourself
        price_cents: 5500
        participant_roles: ["Participant"]
      - name: Team of 3
        description: 'One registration covers your whole team. If the same participant will complete multiple legs, enter their information again.'
        price_cents: 10500
        participant_roles: ["Rollerskier", "Mountain Biker", "Trail Runner"]
      - name: Run-only 6K
        description: Just the 6K trail run
        price_cents: 3000
        participant_roles: ["Participant"]
    custom_questions:
      - key: competition_gender
        label: "Competition gender"
        type: choice
        options: ["Men", "Women", "Mixed / non-binary"]
        required: true
      - key: club
        label: "Club(s) or team(s) you represent (e.g., TCSC, LNR)"
        type: text
        required: false
      - key: city_state
        label: "City, State (e.g., Minneapolis, MN)"
        type: text
        required: true
      - key: course
        label: "Which race will you participate in?"
        type: choice
        options:
          - "Long course (18K roll, 17K ride, 11K run)"
          - "Short course (9K roll, 9K ride, 6K run)"
        required: true
      - key: wave
        label: "What is your preferred wave? (We may not be able to accommodate requested wave)"
        type: choice
        options:
          - "Wave 1 (fighting for the podium)"
          - "Wave 2 (strong finish)"
          - "Wave 3 (focused on completion)"
        required: false
  social:
    name: Social event
    price_options:
      - name: Registration
        price_cents: 0
        participant_roles: ["Participant"]
    custom_questions: []
  blank:
    name: Blank
    price_options: []
    custom_questions: []
```

- [ ] **Step 1: Failing tests** — templates load; `dry_tri` has 3 options with prices 5500/10500/3000 and the team option has 3 roles; `apply_template` copies questions+options onto an Event and later YAML edits don't affect saved events (copy semantics); unknown key → `get_template` returns None; malformed question (missing `key`) → ValueError.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** (follow `config/practices.yaml` loading style — `yaml.safe_load`, module-level cache with a `_reset_cache()` test hook). **Step 4: Run** task + full suite → PASS. **Step 5: Commit** — `feat(events): event type templates (dry_tri, social, blank)`

---

### Task 3: Registration service (pricing, validation, capacity)

**Files:**
- Create: `app/events/service.py`
- Test: `tests/events/test_service.py`

**Interfaces:**
- Produces (all consumed by Task 4/5 — signatures exact):
  - `compute_price(option: EventPriceOption, event: Event, discount_code: str | None) -> tuple[int, bool]` — returns `(amount_cents, discount_applied)`. Discount applies iff event.discount_code set, code matches (casefold/strip), and `option.member_price_cents` is not None.
  - `capacity_available(event: Event) -> bool` — True if `event.capacity is None` or confirmed + pending_payment-younger-than-1h registrations `< capacity`.
  - `expire_stale_pending(event: Event) -> int` — marks `pending_payment` older than 24h as `cancelled`, commits, returns count.
  - `class RegistrationError(Exception)` with `.errors: dict[str, str]` (field → message).
  - `create_registration(event: Event, payload: dict) -> EventRegistration` — validates and creates (commits) a `pending_payment` registration + participants. Payload shape:

```python
{
  "price_option_id": int,
  "contact_email": str, "contact_phone": str,
  "team_name": str | None,           # required iff option.participant_count > 1
  "emergency_contact_name": str, "emergency_contact_phone": str,
  "participants": [{"name": str, "date_of_birth": "YYYY-MM-DD", "email": str, "phone": str}, ...],
  "answers": {question_key: str},
  "discount_code": str | None,
}
```

Validation rules (each violation → key in `RegistrationError.errors`): event must be `active` (see Task 4 for admin-draft preview exception — service takes `allow_draft: bool = False` kwarg), now within signup window, option belongs to event + active, `len(participants) == option.participant_count`, every participant field non-empty with parseable DOB (`app/utils.py` `parse_date`), required custom questions answered and choice answers ∈ options, unknown answer keys dropped, email fields normalized via `normalize_email`, capacity available. `amount_cents`/`discount_applied` set from `compute_price`. Participants get `position` (1-based) and `role_label` copied from `option.participant_roles`.

- [ ] **Step 1: Failing tests** — cover: happy path individual; happy path team-of-3 (role labels copied); wrong participant count rejected; team_name required for teams only; missing required question rejected; invalid choice rejected; discount code right/wrong/absent (member_price vs price); capacity full rejected; pending <1h counts toward capacity, pending >1h doesn't; `expire_stale_pending` cancels only >24h rows; draft event rejected unless `allow_draft=True`; window-closed rejected.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement**. **Step 4: Run** task + full suite → PASS. **Step 5: Commit** — `feat(events): registration service with pricing, capacity, validation`

---

### Task 4: Public event page, register endpoint, Stripe + webhook

**Files:**
- Create: `app/routes/events.py`, `app/templates/events/registration.html`, `app/static/event_registration.js`
- Modify: `app/routes/payments.py` (webhook + intent creation), `app/routes/main.py` (`/tri` redirect), `app/__init__.py` (register blueprint)
- Test: `tests/events/test_routes.py`, `tests/events/test_webhook.py`

**Interfaces:**
- Consumes: Task 3 service functions, Task 1 models.
- Produces:
  - `GET /events/<slug>` — renders `events/registration.html`. 404 unless event `active` OR (event `draft` AND current session is admin — reuse the session-admin check used by `app/routes/admin.py`; show a "DRAFT — admin preview" banner). Calls `expire_stale_pending(event)` first.
  - `POST /events/<slug>/register` — JSON body per Task 3 payload. On `RegistrationError` → 400 `{"error": {field: msg}}`. On success: creates registration, then Stripe PaymentIntent: `amount=reg.amount_cents`, `capture_method='automatic'`, `receipt_email=contact_email`, `statement_descriptor=build_statement_descriptor('EVENT', event.name)`, `description=f"TCSC Event - {event.name}"`, metadata `{'payment_type': PaymentType.EVENT, 'event_id': str(event.id), 'registration_id': str(reg.id), 'email': contact_email, 'name': first participant name}`, plus `stripe_idempotency_options()`. Stores `reg.payment_intent_id = intent.id`, commits, returns `{'clientSecret': ..., 'registrationId': reg.id}`. Zero-price options (social template) skip Stripe: registration is immediately `confirmed`, response `{'free': True}`.
  - Webhook (`payments.py`): in `PAYMENT_SUCCEEDED`, when `payment_type == PaymentType.EVENT`: look up registration by `metadata['registration_id']`; create Payment row (idempotent by intent id) with `event_registration_id`, `payment_type=PaymentType.EVENT`, `user_id=None` — **do not call `User.get_by_email`**; set registration `confirmed`; send existing `send_payment_notification`. Missing registration → log warning, still record Payment. In `PAYMENT_CANCELED` for events: mark registration `cancelled` if still pending.

Template/JS: follow `app/templates/socials/registration.html` + `app/static/social_event.js` exactly (csrf meta, Stripe v3, card element, payment-view/completed-view swap, styles from `css/styles/main.css`). Dynamic parts rendered by Jinja + vanilla JS: price option radio cards (from `event.price_options` where active, showing `format_price`), N participant fieldsets re-rendered on option change (roles + help text from option description), custom question fields (choice→select, text→input, required flags), discount code input with client-side "Apply" that just re-posts on submit (server is authoritative; on discount, server returns final amount in clientSecret intent — display "member price applied" from a `POST /events/<slug>/quote` — **no**: keep YAGNI, single submit, server computes; button label shows base price, success view confirms amount charged).

- [ ] **Step 1: Failing route tests** (Flask test client, mock `stripe.PaymentIntent.create` with `unittest.mock.patch` returning a stub with `.id`/`.client_secret`; existing tests in `tests/routes/` show the client/fixture pattern):
  - GET active event 200 + shows option names; GET draft anon → 404; GET draft with admin session → 200.
  - POST valid individual → 200, clientSecret, registration `pending_payment` with `payment_intent_id`.
  - POST team missing 3rd participant → 400 with `participants` error key.
  - POST with valid discount code → intent amount == member_price_cents.
  - `/tri` → 302 to `/events/dry-tri-2026`.
- [ ] **Step 2: Failing webhook tests** — simulate `payment_intent.succeeded` payload (metadata `payment_type='event'`, registration_id) through the dev-mode webhook path (`FLASK_ENV=development`, no signature — see existing pattern at `payments.py:112`): Payment row created with `event_registration_id` set and `user_id is None`; registration flips `confirmed`; **User count unchanged**; replay is idempotent; canceled intent → registration `cancelled`.
- [ ] **Step 3: Run** → FAIL. **Step 4: Implement** routes + webhook branch + template + JS + `/tri` redirect (keep route, `redirect('/events/dry-tri-2026', code=302)`), register blueprint. **Step 5: Run** task + full suite → PASS. **Step 6: Commit** — `feat(events): public registration page with unified Stripe payment`

---

### Task 5: Admin Events tab (CRUD, registrations grid, CSV)

**Files:**
- Create: `app/routes/admin_events.py`, `app/templates/admin/events.html`, `app/templates/admin/event_form.html`, `app/templates/admin/event_registrations.html`, `app/static/admin_events.js`
- Modify: `app/templates/admin/admin_base.html` (nav: add Events), `app/__init__.py` (register blueprint)
- Test: `tests/events/test_admin.py`

**Interfaces (all admin-auth-guarded, mirroring admin.py conventions):**
- `GET /admin/events` (grid page) and `GET /admin/events/data` → JSON rows: id, name, slug, event_date, audience, status, confirmed_count, capacity, revenue_cents (sum of confirmed `amount_cents`), template_key.
- `GET|POST /admin/events/new` — GET shows form with template `<select>` (options from `load_event_templates()`); POST creates Event, calls `apply_template`, then applies form fields. Form parses like `parse_social_event_form` (dollars→cents via existing convention, `parse_date`-style datetime parsing).
- `GET|POST /admin/events/<id>/edit` — core fields plus two JSON-backed editors (hidden `<textarea name="price_options_json">` and `custom_questions_json` managed by dynamic row UI in `admin_events.js`; server validates shapes with the Task 2 validators). Price option rows: name, description, price ($), member price ($, blank=none), roles (comma-separated), active. Question rows: key, label, type, options (one per line), required, help_text.
- `POST /admin/events/<id>/duplicate` — copies event + options + questions, slug `<slug>-copy` (uniquified), status `draft`, no registrations.
- `POST /admin/events/<id>/delete` — draft-only (409 otherwise).
- `POST /admin/events/<id>/status` — body `{"status": "active"|"closed"|"draft"}`.
- `GET /admin/events/<id>/registrations` (page), `GET /admin/events/<id>/registrations/data` → rows: id, status, price option name, team_name, contact email/phone, emergency contact, amount, discount_applied, created_at, one column per participant slot (`"{role}: {name} ({dob}, {email}, {phone})"`), one column per custom question key.
- `GET /admin/events/<id>/registrations/export.csv` — same flattened data, `text/csv` attachment `registrations-<slug>.csv`.
- `POST /admin/events/registrations/<id>/cancel` — if a succeeded Payment exists, call the existing refund logic (reuse `refund_payment` internals or POST-to it); set status `refunded` (paid) or `cancelled` (unpaid).

- [ ] **Step 1: Failing tests** — with admin session (see how existing admin tests fake the session; if none exist, set `sess['user_email'] = 'x@twincitiesskiclub.org'` per the auth decorator's actual check): events/data returns seeded event with revenue; create-from-template `dry_tri` yields 3 price options; duplicate produces draft with copied options and zero registrations; delete active → 409; registrations/data flattens participants + answers; CSV export contains header + row values; cancel on unpaid pending → `cancelled`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** (Tabulator pages copy `admin/social_events.html` + `admin_social_events.js` structure; keep `admin_events.js` self-contained). **Step 4: Run** task + full suite → PASS. **Step 5: Commit** — `feat(admin): Events tab with registrations grid and CSV export`

---

### Task 6: Fold Social Events into Events

**Files:**
- Create: data+schema migration (hand-written Alembic revision)
- Modify: `app/routes/socials.py` (redirect only), `app/routes/main.py` (homepage events listing), `app/templates/index.html`, `app/routes/admin.py` (remove social CRUD + payment display join), `app/routes/payments.py` (remove `create-social-event-payment-intent` + social webhook branches), `app/models.py` (remove SocialEvent, Payment.social_event_id), `app/__init__.py`, `app/templates/admin/admin_base.html` (drop Social Events nav)
- Delete: `app/templates/socials/`, `app/templates/admin/social_events.html`, `app/templates/admin/social_event_form.html`, `app/static/social_event.js`, `app/static/admin_social_events.js`
- Test: `tests/events/test_socials_migration.py` + update any existing tests referencing SocialEvent (grep first: `grep -rn "SocialEvent\|social_event" tests/ app/`)

**Migration (single revision, order matters):**
1. For each `social_events` row → insert `events` row (same slug/name/location/event_date/signup window/description; `template_key='social'`, `audience='internal'`, status map: `draft`→`draft`, `active` with future `signup_end`→`active`, else `closed`) + one `event_price_options` row (name 'Registration', price_cents = old price, roles `["Participant"]`).
2. For each payment with `social_event_id`: insert `event_registrations` (status `confirmed` if payment succeeded, `refunded` if refunded, else `cancelled`; contact_email=payment.email, contact_phone='', emergency fields '', amount_cents=payment.amount, answers `{}`, payment_intent_id=payment.payment_intent_id, created_at=payment.created_at) + one participant (position 1, role 'Participant', name=payment.name, DOB `1900-01-01` sentinel, email=payment.email, phone=''); set `payments.event_registration_id`, `payment_type='event'`.
3. Drop `payments.social_event_id`, drop `social_events`.
Use `op.get_bind()` + SQLAlchemy Core (no ORM models in migrations). Downgrade: `raise NotImplementedError` with a comment (lossy).

**Code changes:** homepage queries `Event.status=='active' AND audience IN ('external','both') AND signup_end > now` and renders event cards (reuse the social-event card markup in `index.html`, link to `/events/<slug>`); `/social/<slug>` → 302 `/events/<slug>`; all SocialEvent imports/branches removed (`PaymentType.SOCIAL_EVENT` removed from constants; keep webhook tolerant: unknown `payment_type` logs + records Payment as today).

- [ ] **Step 1: Grep + failing tests** — migration test seeds pre-migration schema rows via raw SQL in a scratch schema? **No — too heavy.** Instead: test the migration's transform functions by extracting them into module-level pure helpers inside the revision file is overkill; test at the integration level instead: run `flask db upgrade` against the dev DB seeded with a SocialEvent + linked payment created *before* writing the drop (write a small pytest-marked-skip note) — practical approach: write `tests/events/test_socials_migration.py` asserting post-state invariants against a fixture DB built by inserting rows with SQLAlchemy Core into `events`/`event_registrations` shaped like the migration output, verifying redirects (`/social/<slug>` 302) and homepage rendering of events. Migration correctness itself is verified manually in Step 4.
- [ ] **Step 2: Implement migration + code removal.** Update existing tests that referenced SocialEvent (grep results) to Events equivalents.
- [ ] **Step 3: Manual migration verification (REQUIRED, do not skip):** on the dev DB: `flask db downgrade -1` is unavailable (new revision) — instead: seed 2 social_events + 2 linked payments via `flask shell` *before* upgrading (check out the pre-task commit if needed), run `flask db upgrade`, then verify in `psql`: events count +2, registrations linked, `payments.event_registration_id` set, `social_events` gone. Record the psql output in the task notes.
- [ ] **Step 4: Run** full suite → green (updated). **Step 5: Commit** — `feat(events)!: fold Social Events into Events with data migration`

---

### Task 7: Dry Tri 2026 seed (idempotent data migration)

**Files:**
- Create: Alembic data migration `seed dry tri 2026 draft event`
- Test: `tests/events/test_dry_tri_seed.py` (tests the shared builder, not the migration)

**Interfaces:**
- Add `app/events/seeds.py` with `build_dry_tri_2026() -> dict` returning the full insert payload; the migration and tests both consume it.

Content: slug `dry-tri-2026`, name `TCSC Dry Triathlon 2026`, location `Carver Park Reserve — Parley Lake, Victoria`, event_date `2026-10-24 09:00` (**placeholder — Mitchell confirms**), signup window `2026-07-25 00:00` → `2026-10-22 23:59`, status `draft`, audience `both`, details_url = participant guide URL (from spec), description containing the Roll/Ride/Run blurb + 2025-times-as-placeholder schedule block (7:30 packet pickup, 9:00/9:05 long waves, 9:30 short course, run-only start TBD), template `dry_tri` applied (3 options, 5 questions), `member_price_cents` null, no discount code. Migration inserts only if slug absent (idempotent).

- [ ] **Step 1: Failing test** — builder returns 3 options (5500/10500/3000), run-only roles == `["Participant"]`, 5 questions with required flags per template, status draft. **Step 2: Implement + migrate dev DB, verify via `flask shell`** (event exists, draft, invisible on homepage, `/events/dry-tri-2026` 404 anon / 200 with admin session). **Step 3: Full suite green. Commit** — `feat(events): seed Dry Tri 2026 draft event`

---

### Task 8: Final verification, deploy, prod smoke test, notify Mitchell

**Files:** none new (fixes only).

- [ ] **Step 1: Full local verification** — `pytest` (entire suite) green; `python -c "from app import create_app; create_app('development')"` boots; local dev server: GET `/`, `/events/dry-tri-2026` (admin session), `/tri` redirect, `/admin/events` all 200/302 as expected.
- [ ] **Step 2: Review pass** — Fable (orchestrator) reads the full diff (`git diff main-at-start..HEAD`) against the spec; fix anything material.
- [ ] **Step 3: Deploy** — push `main` to origin. Render auto-deploys (`autoDeployTrigger: commit`; `preDeployCommand` runs migrations). Monitor: poll `https://tcsc.ski/` until new build responds (allow ~5-10 min); then smoke test prod: `/tri` → 302; `/events/dry-tri-2026` → 404 anonymous (draft; correct); homepage 200 with no Dry Tri card; `/admin` loads.
- [ ] **Step 4: Notify Mitchell** — using `SLACK_BOT_TOKEN` from `.env` (pattern: `scripts/post_welcome_message.py`), find Mitchell Campbell's Slack user ID (`users_list` / lookup by profile name), open a DM, send: what shipped, prod URLs (`https://tcsc.ski/events/dry-tri-2026` — admin login required while draft, `https://tcsc.ski/admin/events`), the placeholder date/times that need his confirmation, the run-only 6K at $30, how to set the member discount code, and how to flip the event to active. Do NOT activate the event.
- [ ] **Step 5: Write handoff note** — `docs/superpowers/notes/2026-07-25-events-system-handoff.md`: what deployed, migration results, Mitchell message sent, open follow-ups (final date/times, discount amount, run-only wave time).

---

## Self-Review (completed)

- **Spec coverage:** models/templates/service/public flow/admin/migration/seed/deploy all mapped to Tasks 1-8. Draft-preview-for-admins added (Mitchell must test in prod while draft). `/tri` (actual route) redirected rather than spec's `/dryland-triathlon` (route didn't exist).
- **Placeholder scan:** Dry Tri date/times are intentional, flagged placeholders (business data, admin-editable), not plan gaps.
- **Type consistency:** service signatures in Task 3 match consumption in Tasks 4-5; `PaymentType.EVENT` consistent; `registration_id` metadata key consistent between Task 4 intent creation and webhook.
