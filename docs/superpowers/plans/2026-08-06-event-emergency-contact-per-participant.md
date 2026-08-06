# Event Emergency Contact Per Participant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the event registration emergency contact from one-per-checkout to one-per-participant, for every price option.

**Architecture:** The two `emergency_contact_*` columns move from `event_registrations` to `event_participants` in a single backfilling migration. Server validation moves into `_validate_participants`. The form's standalone Emergency contact section is replaced by two fields inside every participant card, so payload collection and value preservation ride the existing `data-participant-field` machinery. The admin roster folds the contact into each `participant_N` cell.

**Tech Stack:** Flask + SQLAlchemy + Alembic (hand-written migration), vanilla JS (`app/static/event_registration.js`), node:test + jsdom for the JS suite, pytest against the local PostgreSQL dev DB.

**Spec:** `docs/superpowers/specs/2026-08-06-event-emergency-contact-per-participant-design.md`

## Global Constraints

- Timestamps UTC in DB; prices in cents (no changes here, but do not "fix" them).
- No em dashes in any user-facing copy.
- Tests run via repo-root `./run-tests.sh` (wraps pytest with `DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips`). The localhost forwarder to the postgres container must be running (`scratchpad/pgforward.py`, target 172.27.0.1:5432).
- The JS suite runs via `npm run test:events` (invoked by `tests/test_events_js.py`); `npm install` is already done in this worktree.
- The dev DB's `alembic_version` is at `a7c1e5f2b9d3` (a trip-registration-redesign revision that main does not have). Do NOT run `flask db upgrade` against the dev DB from this worktree; apply schema changes to the dev DB with plain SQL (Task 1 Step 5) and leave `alembic_version` alone.
- Prod deploys run migrations via the Procfile release phase, so the migration must be correct standalone; its `down_revision` is main's head `539ad532aeb3`.

---

### Task 1: Migration (schema move + backfill), verified on a scratch DB

**Files:**
- Create: `migrations/versions/b9c8d7e6f5a4_move_emergency_contact_to_participants.py`
- Scratch (not committed): `/tmp/claude-1000/-workspace-tcsc-trips/f63664f1-c514-48d1-9966-f0a4711ec126/scratchpad/migration_check.py`

**Interfaces:**
- Produces: `event_participants.emergency_contact_name` (varchar 255, NOT NULL), `event_participants.emergency_contact_phone` (varchar 50, NOT NULL); `event_registrations` loses both columns. Every later task assumes this schema.

- [ ] **Step 1: Write the migration**

```python
"""move emergency contact from event registrations to participants

Revision ID: b9c8d7e6f5a4
Revises: 539ad532aeb3
Create Date: 2026-08-06

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b9c8d7e6f5a4'
down_revision = '539ad532aeb3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('event_participants', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'emergency_contact_name', sa.String(length=255), nullable=True
            )
        )
        batch_op.add_column(
            sa.Column(
                'emergency_contact_phone', sa.String(length=50), nullable=True
            )
        )

    op.execute(
        """
        UPDATE event_participants AS p
        SET emergency_contact_name = r.emergency_contact_name,
            emergency_contact_phone = r.emergency_contact_phone
        FROM event_registrations AS r
        WHERE p.registration_id = r.id
        """
    )

    with op.batch_alter_table('event_participants', schema=None) as batch_op:
        batch_op.alter_column(
            'emergency_contact_name',
            existing_type=sa.String(length=255),
            nullable=False,
        )
        batch_op.alter_column(
            'emergency_contact_phone',
            existing_type=sa.String(length=50),
            nullable=False,
        )

    with op.batch_alter_table('event_registrations', schema=None) as batch_op:
        batch_op.drop_column('emergency_contact_name')
        batch_op.drop_column('emergency_contact_phone')


def downgrade():
    with op.batch_alter_table('event_registrations', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'emergency_contact_name', sa.String(length=255), nullable=True
            )
        )
        batch_op.add_column(
            sa.Column(
                'emergency_contact_phone', sa.String(length=50), nullable=True
            )
        )

    # First participant's contact becomes the registration's; registrations
    # with no participants fall back to empty strings (matches the migrated
    # social registrations, which never collected one).
    op.execute(
        """
        UPDATE event_registrations AS r
        SET emergency_contact_name = p.emergency_contact_name,
            emergency_contact_phone = p.emergency_contact_phone
        FROM event_participants AS p
        WHERE p.registration_id = r.id AND p.position = 1
        """
    )
    op.execute(
        """
        UPDATE event_registrations
        SET emergency_contact_name = COALESCE(emergency_contact_name, ''),
            emergency_contact_phone = COALESCE(emergency_contact_phone, '')
        """
    )

    with op.batch_alter_table('event_registrations', schema=None) as batch_op:
        batch_op.alter_column(
            'emergency_contact_name',
            existing_type=sa.String(length=255),
            nullable=False,
        )
        batch_op.alter_column(
            'emergency_contact_phone',
            existing_type=sa.String(length=50),
            nullable=False,
        )

    with op.batch_alter_table('event_participants', schema=None) as batch_op:
        batch_op.drop_column('emergency_contact_phone')
        batch_op.drop_column('emergency_contact_name')
```

- [ ] **Step 2: Write the scratch verification script**

Save as `<scratchpad>/migration_check.py`. It builds a throwaway DB, migrates to main's head, seeds a registration with two participants, applies the new revision, asserts the backfill, downgrades one step, asserts the reverse, then drops the DB.

```python
"""Verify b9c8d7e6f5a4 upgrade + downgrade on a throwaway database."""
import os
import subprocess
import sys

import psycopg2

ADMIN_URL = "postgresql://tcsc:tcsc@localhost:5432/tcsc_trips"
SCRATCH = "tcsc_migration_check"
SCRATCH_URL = f"postgresql://tcsc:tcsc@localhost:5432/{SCRATCH}"
WORKTREE = "/workspace/tcsc-trips/.claude/worktrees/event-emergency-contact"
PY = "/workspace/tcsc-trips/.venv-linux/bin/python"


def run_flask_db(*args):
    env = dict(
        os.environ,
        DATABASE_URL=SCRATCH_URL,
        FLASK_SECRET_KEY="migration-check",
    )
    subprocess.run(
        [PY, "-m", "flask", "db", *args],
        cwd=WORKTREE, env=env, check=True, capture_output=True, text=True,
    )


def admin_conn():
    conn = psycopg2.connect(ADMIN_URL)
    conn.autocommit = True
    return conn


with admin_conn() as conn, conn.cursor() as cur:
    cur.execute(f'DROP DATABASE IF EXISTS {SCRATCH}')
    cur.execute(f'CREATE DATABASE {SCRATCH}')

run_flask_db("upgrade", "539ad532aeb3")

with psycopg2.connect(SCRATCH_URL) as conn, conn.cursor() as cur:
    cur.execute(
        """
        INSERT INTO events (slug, name, location, event_date, signup_start,
            signup_end, status, audience, custom_questions, created_at,
            updated_at)
        VALUES ('mig-check', 'Mig Check', 'Test', now(), now(), now(),
            'active', 'both', '[]', now(), now())
        RETURNING id
        """
    )
    event_id = cur.fetchone()[0]
    cur.execute(
        """
        INSERT INTO event_price_options (event_id, name, price_cents,
            participant_roles, sort_order, active)
        VALUES (%s, 'Team', 1000, '["A", "B"]', 0, true) RETURNING id
        """,
        (event_id,),
    )
    option_id = cur.fetchone()[0]
    cur.execute(
        """
        INSERT INTO event_registrations (event_id, price_option_id,
            contact_email, contact_phone, emergency_contact_name,
            emergency_contact_phone, answers, amount_cents,
            discount_applied, status, created_at, updated_at)
        VALUES (%s, %s, 'a@x.com', '555-1', 'Pat Contact', '555-9',
            '{}', 1000, false, 'confirmed', now(), now())
        RETURNING id
        """,
        (event_id, option_id),
    )
    registration_id = cur.fetchone()[0]
    for position in (1, 2):
        cur.execute(
            """
            INSERT INTO event_participants (registration_id, position,
                role_label, name, date_of_birth, email, phone)
            VALUES (%s, %s, 'Role', 'Person', '1990-01-01', 'p@x.com',
                '555-2')
            """,
            (registration_id, position),
        )

run_flask_db("upgrade")

with psycopg2.connect(SCRATCH_URL) as conn, conn.cursor() as cur:
    cur.execute(
        "SELECT emergency_contact_name, emergency_contact_phone"
        " FROM event_participants ORDER BY position"
    )
    rows = cur.fetchall()
    assert rows == [("Pat Contact", "555-9")] * 2, rows
    cur.execute(
        "SELECT column_name FROM information_schema.columns"
        " WHERE table_name='event_registrations'"
        " AND column_name LIKE 'emergency%'"
    )
    assert cur.fetchall() == [], "registration columns not dropped"

run_flask_db("downgrade", "-1")

with psycopg2.connect(SCRATCH_URL) as conn, conn.cursor() as cur:
    cur.execute(
        "SELECT emergency_contact_name, emergency_contact_phone"
        " FROM event_registrations"
    )
    assert cur.fetchall() == [("Pat Contact", "555-9")]
    cur.execute(
        "SELECT column_name FROM information_schema.columns"
        " WHERE table_name='event_participants'"
        " AND column_name LIKE 'emergency%'"
    )
    assert cur.fetchall() == [], "participant columns not dropped"

with admin_conn() as conn, conn.cursor() as cur:
    cur.execute(f'DROP DATABASE {SCRATCH}')

print("migration check OK")
```

- [ ] **Step 3: Run the scratch verification**

Run: `/workspace/tcsc-trips/.venv-linux/bin/python <scratchpad>/migration_check.py`
Expected: `migration check OK`. (The flask CLI boots the app, which may log Slack Socket Mode lines; ignore them.)

- [ ] **Step 4: Commit the migration**

```bash
git add migrations/versions/b9c8d7e6f5a4_move_emergency_contact_to_participants.py
git commit -m "feat(events): migration moving emergency contact to participants"
```

- [ ] **Step 5: Apply the same DDL to the shared dev DB (plain SQL, no alembic)**

The dev DB serves the pytest suite. `alembic_version` stays untouched (it belongs to another branch's chain).

```bash
/workspace/tcsc-trips/.venv-linux/bin/python - <<'EOF'
import psycopg2
conn = psycopg2.connect("postgresql://tcsc:tcsc@localhost:5432/tcsc_trips")
conn.autocommit = False
cur = conn.cursor()
cur.execute(
    "ALTER TABLE event_participants"
    " ADD COLUMN emergency_contact_name VARCHAR(255),"
    " ADD COLUMN emergency_contact_phone VARCHAR(50)"
)
cur.execute(
    "UPDATE event_participants AS p"
    " SET emergency_contact_name = r.emergency_contact_name,"
    "     emergency_contact_phone = r.emergency_contact_phone"
    " FROM event_registrations AS r WHERE p.registration_id = r.id"
)
cur.execute(
    "ALTER TABLE event_participants"
    " ALTER COLUMN emergency_contact_name SET NOT NULL,"
    " ALTER COLUMN emergency_contact_phone SET NOT NULL"
)
cur.execute(
    "ALTER TABLE event_registrations"
    " DROP COLUMN emergency_contact_name,"
    " DROP COLUMN emergency_contact_phone"
)
conn.commit()
print("dev DB schema updated")
EOF
```

Expected: `dev DB schema updated`. From this point the old code fails against the dev DB; Tasks 2-4 restore green.

---

### Task 2: Model + service validation

**Files:**
- Modify: `app/events/models.py` (EventRegistration lines 158-159 out, EventParticipant gains two columns after `phone`)
- Modify: `app/events/service.py` (registration-level required-fields loop out; `_validate_participants` extended; constructors updated)
- Test: `tests/events/test_service.py`, `tests/events/test_models.py`, `tests/events/test_webhook.py`, `tests/events/test_socials_migration.py`

**Interfaces:**
- Consumes: Task 1 schema.
- Produces: `EventParticipant.emergency_contact_name` / `.emergency_contact_phone` model attributes (str, required); `create_registration()` accepts participant dicts carrying `emergency_contact_name` and `emergency_contact_phone` and no longer reads registration-level emergency keys; validation errors for missing fields arrive as `errors["participants"]` mentioning "emergency contact name" / "emergency contact phone".

- [ ] **Step 1: Write failing tests**

In `tests/events/test_service.py`, extend `_participant` (near line 74) so every generated participant carries the new fields, and change `_payload` to drop the registration-level keys:

```python
def _participant(position):
    return {
        "name": f"Participant {position}",
        "date_of_birth": f"199{position}-01-0{position}",
        "email": f"  PERSON{position}@Example.COM ",
        "phone": f"555-010{position}",
        "emergency_contact_name": f"Emergency {position}",
        "emergency_contact_phone": f"555-099{position}",
    }
```

In `_payload`, delete the `"emergency_contact_name"` and `"emergency_contact_phone"` entries. In `_existing_registration`, delete the two `emergency_contact_*` kwargs.

Add these tests next to the existing participant validation tests:

```python
def test_each_participant_requires_emergency_contact(db_session, event_setup):
    event, option = event_setup
    payload = _payload(option)
    del payload["participants"][0]["emergency_contact_name"]
    payload["participants"][0]["emergency_contact_phone"] = "  "

    with pytest.raises(RegistrationError) as excinfo:
        create_registration(event, payload)

    message = excinfo.value.errors["participants"]
    assert "Participant 1 requires" in message
    assert "emergency contact name" in message
    assert "emergency contact phone" in message


def test_participants_store_their_own_emergency_contact(
    db_session, event_setup
):
    event, option = event_setup
    registration = create_registration(event, _payload(option))

    for position, participant in enumerate(
        registration.participants, start=1
    ):
        assert participant.emergency_contact_name == f"Emergency {position}"
        assert participant.emergency_contact_phone == f"555-099{position}"


def test_registration_level_emergency_contact_is_ignored(
    db_session, event_setup
):
    event, option = event_setup
    payload = _payload(option)
    payload["emergency_contact_name"] = "Legacy Top Level"
    payload["emergency_contact_phone"] = "555-0000"

    registration = create_registration(event, payload)

    assert not hasattr(registration, "emergency_contact_name")
```

(Adapt fixture names to the file's actual fixtures; `_payload`/`_existing_registration` callers show which fixture provides `event, option`.)

Update fixtures in the other three test files to match the new model: every `EventRegistration(...)` loses its `emergency_contact_name` / `emergency_contact_phone` kwargs, and every `EventParticipant(...)` gains them, e.g. in `tests/events/test_admin.py`-style fixtures (that file is Task 4's) leave alone for now, but fix:
- `tests/events/test_models.py` lines ~66-67 (registration kwargs out) and the `EventParticipant(...)` constructions gain `emergency_contact_name="EC", emergency_contact_phone="911"`.
- `tests/events/test_webhook.py` lines ~53-54: kwargs move from the registration to any participants it creates (if it creates none, just delete the kwargs).
- `tests/events/test_socials_migration.py` lines ~112-113: delete the empty-string kwargs; the migrated-shape assertions keep whatever the roster shows after Task 4 (that file asserts `row["emergency_contact"] == ""`; update in Task 4 if the roster test lives there, otherwise adjust here to match reality after removal - the column is gone, so the assertion should be removed).

- [ ] **Step 2: Run tests to verify they fail**

Run: `./run-tests.sh tests/events/test_service.py -q` (from the worktree root; `run-tests.sh` exists only in the main checkout, so use `DATABASE_URL="postgresql://tcsc:tcsc@localhost:5432/tcsc_trips" FLASK_SECRET_KEY=test-secret-key /workspace/tcsc-trips/.venv-linux/bin/python -m pytest tests/events/test_service.py -q` if needed)
Expected: FAIL (model lacks the attributes; service still requires top-level fields).

- [ ] **Step 3: Implement model change**

In `app/events/models.py`, delete lines 158-159 from `EventRegistration`:

```python
    emergency_contact_name = db.Column(db.String(255), nullable=False)
    emergency_contact_phone = db.Column(db.String(50), nullable=False)
```

and add the same two lines to `EventParticipant` directly after `phone` (line 221).

- [ ] **Step 4: Implement service change**

In `app/events/service.py`:

1. Delete the `required_registration_fields` block (lines 158-164).
2. In `_validate_participants`, extend the missing-fields tuple:

```python
        missing_fields = [
            field
            for field in (
                "name",
                "date_of_birth",
                "email",
                "phone",
                "emergency_contact_name",
                "emergency_contact_phone",
            )
            if _is_blank(participant.get(field))
        ]
```

and extend the validated dict:

```python
        validated.append(
            {
                "name": participant["name"].strip(),
                "date_of_birth": date_of_birth,
                "email": email,
                "phone": participant["phone"].strip(),
                "emergency_contact_name": participant[
                    "emergency_contact_name"
                ].strip(),
                "emergency_contact_phone": participant[
                    "emergency_contact_phone"
                ].strip(),
            }
        )
```

3. In `create_registration`, delete the two `emergency_contact_*` kwargs from the `EventRegistration(...)` construction, and add to the `EventParticipant(...)` construction:

```python
                emergency_contact_name=participant["emergency_contact_name"],
                emergency_contact_phone=participant["emergency_contact_phone"],
```

- [ ] **Step 5: Run the touched files' tests**

Run: `.../pytest tests/events/test_service.py tests/events/test_models.py tests/events/test_webhook.py tests/events/test_socials_migration.py -q`
Expected: PASS (socials-migration roster assertions may still reference the dropped column; if so they move to Task 4 only if they exercise the roster, otherwise fix here).

- [ ] **Step 6: Commit**

```bash
git add app/events/models.py app/events/service.py tests/events/
git commit -m "feat(events): emergency contact per participant in model and service"
```

---

### Task 3: Registration form (template + JS + jsdom suite)

**Files:**
- Modify: `app/templates/events/registration.html` (remove lines 83-96, the standalone Emergency contact section; keep the `form-divider`)
- Modify: `app/static/event_registration.js` (`renderParticipants`, `collectPayload`, `showServerErrors`)
- Test: `tests/js/event_registration_scopes.test.js`, `tests/events/test_routes.py`

**Interfaces:**
- Consumes: `create_registration()` participant contract from Task 2.
- Produces: form payloads whose participant objects each include `emergency_contact_name` and `emergency_contact_phone`; no top-level emergency keys.

- [ ] **Step 1: Write failing JS test**

In `tests/js/event_registration_scopes.test.js`, remove the two standalone inputs from the DOM skeleton (`<input type="text" id="emergency-contact-name">` and `<input type="tel" id="emergency-contact-phone">`), then add:

```javascript
test('every participant card collects its own emergency contact', () => {
  const dom = load([]);
  select(dom, 2);  // Relay Triathlon renders three cards

  const groups = dom.window.document.querySelectorAll('[data-participant]');
  assert.equal(groups.length, 3);
  groups.forEach(group => {
    assert.ok(group.querySelector(
      '[data-participant-field="emergency_contact_name"]'));
    assert.ok(group.querySelector(
      '[data-participant-field="emergency_contact_phone"]'));
  });
});

test('emergency contact values survive switching options', () => {
  const dom = load([]);
  const document = dom.window.document;
  document.querySelector(
    '[data-participant="0"] [data-participant-field="emergency_contact_name"]'
  ).value = 'Pat Contact';

  select(dom, 2);
  select(dom, 1);

  assert.equal(
    document.querySelector(
      '[data-participant="0"] ' +
      '[data-participant-field="emergency_contact_name"]'
    ).value,
    'Pat Contact');
});
```

- [ ] **Step 2: Run JS suite to verify failure**

Run: `npm run test:events`
Expected: FAIL (no emergency inputs inside participant groups).

- [ ] **Step 3: Implement JS changes**

In `renderParticipants` (after the `contactRow` block, before `group.append`):

```javascript
        const emergencyRow = document.createElement('div');
        emergencyRow.className = 'form-row form-row--pair';
        emergencyRow.append(
          createInputField(
            'Emergency contact name',
            'text',
            `participant-${participantNumber}-emergency_contact_name`,
            saved.emergency_contact_name,
            'off'
          ),
          createInputField(
            'Emergency contact phone',
            'tel',
            `participant-${participantNumber}-emergency_contact_phone`,
            saved.emergency_contact_phone,
            'off'
          )
        );

        const emergencyHint = document.createElement('p');
        emergencyHint.className = 'form-field__hint';
        emergencyHint.textContent =
          'Emergency contact: someone who is not participating with you.';

        group.append(title, identityRow, contactRow, emergencyRow, emergencyHint);
```

(replacing the existing `group.append(title, identityRow, contactRow);`).

In `collectPayload`, delete the `emergency_contact_name` and `emergency_contact_phone` entries from the returned object (the participant loop already picks the new fields up via `data-participant-field`).

In `showServerErrors`, shrink the field-id map to:

```javascript
        const fieldId = {
          team_name: 'team-name'
        }[key];
```

- [ ] **Step 4: Run JS suite to verify pass**

Run: `npm run test:events`
Expected: PASS.

- [ ] **Step 5: Update the template and its route tests**

Delete the standalone section from `app/templates/events/registration.html` (the `<section class="form-section" aria-labelledby="emergency-title">...</section>` block, lines 83-96).

In `tests/events/test_routes.py`:
- `_payload` (line ~94): delete the two top-level emergency entries; extend its `_participant` helper with the two fields exactly as in Task 2 Step 1.
- Any `EventRegistration(...)` fixture (line ~185): delete the two kwargs; add them to `EventParticipant(...)` fixtures if present.
- The template assertions: `assert 'id="emergency-contact-name"' in page` (line ~381) flips to `not in page`; in `test_get_event_page_puts_team_name_with_participant_details` (line ~385) drop the `emergency_heading` lookup and assert only `participants_heading < team_name_field`; also assert `"Emergency contact" not in page` (the copy now lives in JS).

- [ ] **Step 6: Run route tests**

Run: `.../pytest tests/events/test_routes.py tests/test_events_js.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/templates/events/registration.html app/static/event_registration.js tests/js/event_registration_scopes.test.js tests/events/test_routes.py
git commit -m "feat(events): collect an emergency contact inside every participant card"
```

---

### Task 4: Admin roster and CSV

**Files:**
- Modify: `app/routes/admin_events.py` (`_REGISTRATION_BASE_COLUMNS` line 52, `_registration_rows` lines 424-456)
- Test: `tests/events/test_admin.py`, `tests/events/test_socials_migration.py`

**Interfaces:**
- Consumes: Task 2 model attributes.
- Produces: roster rows without an `emergency_contact` key; `participant_N` cells formatted `"{role}: {name} ({dob}, {email}, {phone}; emergency: {ec_name} {ec_phone})"`, with the `; emergency: ...` clause omitted when both fields are empty (migrated socials data).

- [ ] **Step 1: Write failing tests**

In `tests/events/test_admin.py`, `_registration` fixture: delete the two registration kwargs; give each of the three `EventParticipant(...)` constructions an emergency contact (`emergency_contact_name="Casey Contact", emergency_contact_phone="612-555-0199"` for position 1, `"Dana Contact"/"612-555-0299"` for 2, `"Eli Contact"/"612-555-0399"` for 3). Update the flattening assertions:

```python
    assert row["participant_1"] == (
        "Rollerskier: Ada Skier "
        "(1990-01-02, ada@example.com, 612-555-0101; "
        "emergency: Casey Contact 612-555-0199)"
    )
    assert row["participant_3"] == (
        "Trail Runner: Cam Runner "
        "(1992-03-04, cam@example.com, 612-555-0103; "
        "emergency: Eli Contact 612-555-0399)"
    )
```

Add, next to the flattening test:

```python
def test_registrations_data_drops_registration_level_emergency_column(
    admin_client,
    registration_event,
):
    event, _registration = registration_event

    response = admin_client.get(
        f"/admin/events/{event.id}/registrations/data"
    )

    row = response.get_json()["registrations"][0]
    assert "emergency_contact" not in row
```

In `tests/events/test_socials_migration.py`, the `assert row["emergency_contact"] == ""` (line ~147) becomes `assert "emergency_contact" not in row`, and its participant fixtures (if any) get empty-string emergency fields so the cell renders without the emergency clause.

- [ ] **Step 2: Run tests to verify failure**

Run: `.../pytest tests/events/test_admin.py tests/events/test_socials_migration.py -q`
Expected: FAIL on the new assertions.

- [ ] **Step 3: Implement**

In `app/routes/admin_events.py`:
- Delete `("emergency_contact", "Emergency contact"),` from `_REGISTRATION_BASE_COLUMNS`.
- In `_registration_rows`, delete the `emergency_contact` computation (lines 425-430) and the `"emergency_contact": emergency_contact,` row entry; change the participant cell to:

```python
        for position, participant in enumerate(
            registration.participants,
            start=1,
        ):
            details = (
                f"{participant.date_of_birth.isoformat()}, "
                f"{participant.email}, {participant.phone}"
            )
            emergency = (
                f"{participant.emergency_contact_name} "
                f"{participant.emergency_contact_phone}"
            ).strip()
            if emergency:
                details = f"{details}; emergency: {emergency}"
            row[f"participant_{position}"] = (
                f"{participant.role_label}: {participant.name} ({details})"
            )
```

- [ ] **Step 4: Run tests to verify pass**

Run: `.../pytest tests/events/test_admin.py tests/events/test_socials_migration.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/routes/admin_events.py tests/events/test_admin.py tests/events/test_socials_migration.py
git commit -m "feat(events): per-participant emergency contact in roster and CSV"
```

---

### Task 5: Full verification + PR

- [ ] **Step 1: Full test suite**

Run (from the worktree root): `DATABASE_URL="postgresql://tcsc:tcsc@localhost:5432/tcsc_trips" FLASK_SECRET_KEY=test-secret-key /workspace/tcsc-trips/.venv-linux/bin/python -m pytest --ignore=tests/wix_scrape -q`
Expected: everything passes (baseline before this work: 101 events tests green; full suite was green on main).

- [ ] **Step 2: Re-run the migration scratch check**

Run: `/workspace/tcsc-trips/.venv-linux/bin/python <scratchpad>/migration_check.py`
Expected: `migration check OK` (final state of the migration file, post any review edits).

- [ ] **Step 3: Re-seed the dev Dry Tri if the suite deleted it**

The events conftest deletes slug `dry-tri-2026` from the dev DB every run; nothing in this task depends on it, so only re-seed if manual browser testing is wanted.

- [ ] **Step 4: Push branch and open PR to main**

```bash
git push -u origin worktree-event-emergency-contact
gh pr create --base main --title "Per-participant emergency contact for event registrations" --body "..."
```

PR body summarizes: schema move + backfill, form change (fields inside each participant card), roster change, and calls out that merging deploys the migration via the release phase. Deploys go through PRs; do not push to main directly.
