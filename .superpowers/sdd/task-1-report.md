# Task 1 Report: Events models, payment type, and schema migration

## What I implemented

- Added the `app.events` package and the four load-bearing SQLAlchemy models:
  `Event`, `EventPriceOption`, `EventRegistration`, and `EventParticipant`.
- Added every field from the design's Data Model tables, including JSON fields,
  timestamps, nullable fields, event/registration foreign keys, and the indexed
  unique event slug.
- Added the plain-string `EventStatus`, `RegistrationStatus`, and `Audience`
  constant classes.
- Added the required relationships:
  - `Event.price_options`, ordered by `sort_order`, with delete-orphan cascade.
  - `Event.registrations`.
  - `EventRegistration.participants`, ordered by `position`, with delete-orphan
    cascade.
  - `EventRegistration.payments`, with `Payment.event_registration` as the
    back-reference.
- Added `EventPriceOption.participant_count` and `Event.confirmed_count`.
- Added `PaymentType.EVENT = "event"` to `PaymentType.ALL`.
- Added nullable `Payment.event_registration_id`, targeting
  `event_registrations.id`.
- Imported the event models from `app/__init__.py` so Flask-Migrate/Alembic
  always registers their metadata.
- Generated and applied Alembic revision `b433791f5783`.
- Updated the existing release-lifecycle migration test to recognize the new
  Alembic head. The migration tolerates that test's intentionally partial
  historical schema, which has no `payments` table, while normal schemas still
  receive the required payments column and foreign key.

## Files changed

- `app/events/__init__.py` (new)
- `app/events/models.py` (new)
- `app/__init__.py`
- `app/constants.py`
- `app/models.py`
- `migrations/versions/b433791f5783_add_events_tables.py` (new)
- `tests/events/__init__.py` (new)
- `tests/events/conftest.py` (new)
- `tests/events/test_models.py` (new)
- `tests/practices/test_practice_migration_release.py`
- `.superpowers/sdd/task-1-report.md` (new)

## TDD evidence

### RED

Command:

```text
./run-tests.sh tests/events/ -v
```

Failing output:

```text
collected 0 items / 1 error

ERROR collecting tests/events/test_models.py
tests/events/test_models.py:4: in <module>
    from app.events.models import (
E   ModuleNotFoundError: No module named 'app.events'

1 error in 0.14s
```

This was run after creating the event tests and before creating any
`app/events/` production code.

### GREEN

Command:

```text
./run-tests.sh tests/events/ -v
```

Passing output:

```text
collected 4 items

tests/events/test_models.py::test_event_with_options_and_registration PASSED
tests/events/test_models.py::test_payment_links_to_event_registration PASSED
tests/events/test_models.py::test_event_defaults_and_string_constants PASSED
tests/events/test_models.py::test_event_tables_have_no_user_fk PASSED

4 passed in 0.35s
```

Final focused regression command:

```text
./run-tests.sh tests/events/ tests/practices/test_practice_migration_release.py -q
```

Result:

```text
6 passed in 2.32s
```

## Full-suite result

Command:

```text
./run-tests.sh -q
```

Final tail:

```text
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
1200 passed, 177 warnings in 47.95s
```

The warnings are the suite's existing SQLAlchemy legacy-API warnings.

## Migration review

- Revision: `b433791f5783`
- Parent: `d8b2c6f4a901`
- Applied successfully with `flask db upgrade`.
- `flask db current` reports `b433791f5783 (head)`.
- `flask db check` reports `No new upgrade operations detected.`
- Upgrade operation count is exactly:
  - **4 `create_table` calls**
  - **1 `add_column` call**
- The four tables are `events`, `event_price_options`,
  `event_registrations`, and `event_participants`.
- The one added column is nullable `payments.event_registration_id`; its named
  FK targets `event_registrations.id`.
- The event slug gets the required unique index.
- There are no table/column drops in `upgrade()`.
- Autogenerate reported no unrelated schema drift, so no unrelated operations
  needed to be deleted manually.

## Self-review

- Confirmed the model column sets match the four design tables with no extra
  membership fields.
- Confirmed the event tables have no foreign keys to `users` or any membership
  table. Their only targets are `events.id`, `event_price_options.id`, and
  `event_registrations.id`.
- Confirmed callable list/dict defaults are used for JSON values, avoiding
  shared mutable defaults.
- Confirmed relationship ordering, delete-orphan cascades, payment round-trip,
  status/audience defaults, and string constant values with database tests.
- Confirmed `git diff --check` passes.
- The design document named in the brief contains the Data Model section but no
  literal `Global Constraints` heading. I followed the brief's binding
  constraint that these model constants are plain strings, not enums.
- No unresolved functional concerns.

STATUS: DONE

## Fix round 1

### What changed

- Added a minimal `payments` table with an integer primary key to the synthetic
  e36 release-test baseline, matching the historical presence of that table.
- Removed the events migration's table/column existence checks and made the
  `payments.event_registration_id` column and foreign-key creation
  unconditional during upgrade.
- Made the matching foreign-key and column removal unconditional during
  downgrade.

### Verification

Command:

```text
./run-tests.sh tests/practices/test_practice_migration_release.py -v
```

Tail output:

```text
tests/practices/test_practice_migration_release.py::test_release_lifecycle_upgrades_e36_orphan_to_head_without_consumers PASSED [ 50%]
tests/practices/test_practice_migration_release.py::test_release_lifecycle_conflict_rolls_back_c4_and_restores_orphan PASSED [100%]

============================== 2 passed in 2.78s ===============================
```

Command:

```text
./run-tests.sh tests/events/ -v
```

Tail output:

```text
tests/events/test_models.py::test_event_with_options_and_registration PASSED [ 25%]
tests/events/test_models.py::test_payment_links_to_event_registration PASSED [ 50%]
tests/events/test_models.py::test_event_defaults_and_string_constants PASSED [ 75%]
tests/events/test_models.py::test_event_tables_have_no_user_fk PASSED    [100%]

============================== 4 passed in 0.35s ===============================
```

Command:

```text
./run-tests.sh -q
```

Tail output:

```text
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
1200 passed, 177 warnings in 48.18s
```
