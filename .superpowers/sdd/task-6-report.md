# Task 6 Report: Fold Social Events into Events

## Implemented

- Added one hand-written Alembic revision,
  `c8f4a2d6e901_fold_social_events_into_events.py`, with
  `down_revision = "b433791f5783"`.
- The revision uses `op.get_bind()` and SQLAlchemy Core reflection,
  selects, inserts, updates, inspection, and DDL only. It imports no ORM
  models.
- Migrated every legacy social event into an event, including capacity,
  original timestamps, `custom_questions=[]`, `template_key="social"`,
  `audience="internal"`, the required status mapping, and one active
  Registration price option.
- Migrated every linked payment into an event registration and participant,
  including the `1900-01-01` DOB sentinel, required empty fields, status
  mapping, payment linkage, and `payment_type="event"`.
- Dropped the inspected `payments.social_event_id` foreign key, dropped the
  column, then dropped `social_events`.
- Added a compatibility guard for release-lifecycle scratch schemas where the
  retired table is already absent. The real data migration path remains
  unchanged.
- Made downgrade intentionally unavailable with
  `NotImplementedError("lossy migration")`.
- Removed the SocialEvent model, payment column, payment type constant,
  payment-intent endpoint, webhook metadata branches, admin CRUD, admin
  payment join, navigation, templates, and JavaScript.
- Kept the socials blueprint registered and changed `/social/<slug>` to a 302
  redirect to `/events/<slug>`.
- Changed the homepage to query active, open Events with audience `external`
  or `both`, ordered by `event_date`, and adapted the existing card markup to
  unified event URLs, dates, and price options.
- Added `/dryland-triathlon` as a 302 alias to `/events/dry-tri-2026`, while
  retaining the existing `/tri` redirect.
- Kept unknown webhook `payment_type` values tolerant: they are logged and a
  Payment is recorded. Development webhook dictionaries and Stripe objects
  are both supported.
- Removed the unreferenced `dryland-triathlon.html`.
- Renamed the remaining generic-event badge and homepage pill CSS from
  social-specific names to event-specific names.

## Files

### Created

- `migrations/versions/c8f4a2d6e901_fold_social_events_into_events.py`
- `tests/events/test_socials_migration.py`
- `.superpowers/sdd/task-6-report.md`

### Modified

- `app/__init__.py`
- `app/constants.py`
- `app/models.py`
- `app/routes/admin.py`
- `app/routes/main.py`
- `app/routes/payments.py`
- `app/routes/socials.py`
- `app/security.py`
- `app/static/admin_payments.js`
- `app/static/css/styles/base/_tokens.css`
- `app/static/css/styles/components/_badges.css`
- `app/static/css/styles/components/_forms.css`
- `app/templates/admin/index.html`
- `app/templates/admin/partials/sidebar.html`
- `app/templates/admin/user_detail.html`
- `app/templates/events/registration.html`
- `app/templates/index.html`
- `tests/events/conftest.py`
- `tests/events/test_routes.py`
- `tests/events/test_webhook.py`
- `tests/practices/test_practice_migration_release.py`
- `tests/routes/test_payments.py`

The admin navigation is rendered through
`app/templates/admin/partials/sidebar.html`, which is included by
`admin_base.html`; the Social Events entry was removed from that partial while
the Events entry remains.

### Deleted

- `app/templates/socials/registration.html` and the now-empty
  `app/templates/socials/` directory
- `app/templates/admin/social_events.html`
- `app/templates/admin/social_event_form.html`
- `app/static/social_event.js`
- `app/static/admin_social_events.js`
- `app/templates/dryland-triathlon.html`

## Manual Migration Verification

Database:
`postgresql://tcsc:tcsc@localhost:5432/tcsc_trips`

Client:

```text
psql (PostgreSQL) 15.18 (Debian 15.18-0+deb12u1)
```

Before writing the migration, I seeded two SocialEvent rows with current ORM
code and two linked payments:

```text
social_event id=20 slug=task6-active-social status=active signup_end=2030-02-08 23:59:00 price=2500
social_event id=21 slug=task6-closed-social status=active signup_end=2020-01-10 23:59:00 price=4000
payment id=54 intent=pi_task6_refunded status=refunded social_event_id=21 amount=4000
payment id=53 intent=pi_task6_succeeded status=succeeded social_event_id=20 amount=2500
```

Pre-upgrade `psql` output:

```text
 id |        slug         | status |     signup_end      | price
----+---------------------+--------+---------------------+-------
 20 | task6-active-social | active | 2030-02-08 23:59:00 |  2500
 21 | task6-closed-social | active | 2020-01-10 23:59:00 |  4000
(2 rows)

 id | payment_intent_id  |  status   | payment_type | social_event_id | event_registration_id | amount
----+--------------------+-----------+--------------+-----------------+-----------------------+--------
 53 | pi_task6_succeeded | succeeded | social_event |              20 |                       |   2500
 54 | pi_task6_refunded  | refunded  | social_event |              21 |                       |   4000
(2 rows)
```

Upgrade command and output:

```text
$ DATABASE_URL="postgresql://tcsc:tcsc@localhost:5432/tcsc_trips" TCSC_MIGRATION_ONLY=1 .venv-linux/bin/flask db upgrade
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade b433791f5783 -> c8f4a2d6e901, fold social events into events
```

Post-upgrade event and price-option verification:

```text
        slug         | status | audience | template_key | capacity | custom_questions |  price_name  | price_cents |      roles      | sort_order | active
---------------------+--------+----------+--------------+----------+------------------+--------------+-------------+-----------------+------------+--------
 task6-active-social | active | internal | social       |       24 | []               | Registration |        2500 | ["Participant"] |          0 | t
 task6-closed-social | closed | internal | social       |       18 | []               | Registration |        4000 | ["Participant"] |          0 | t
(2 rows)
```

Post-upgrade registration and participant verification:

```text
        slug         |  status   |        contact_email        | contact_phone | team_name | emergency_contact_name | emergency_contact_phone | answers | amount_cents | discount_applied | payment_intent_id  |     created_at      |     updated_at      | position | role_label  | participant_name | date_of_birth |      participant_email      | participant_phone
---------------------+-----------+-----------------------------+---------------+-----------+------------------------+-------------------------+---------+--------------+------------------+--------------------+---------------------+---------------------+----------+-------------+------------------+---------------+-----------------------------+-------------------
 task6-active-social | confirmed | task6-succeeded@example.com |               |           |                        |                         | {}      |         2500 | f                | pi_task6_succeeded | 2026-07-22 14:30:00 | 2026-07-22 14:30:00 |        1 | Participant | Succeeded Skier  | 1900-01-01    | task6-succeeded@example.com |
 task6-closed-social | refunded  | task6-refunded@example.com  |               |           |                        |                         | {}      |         4000 | f                | pi_task6_refunded  | 2020-01-03 15:45:00 | 2020-01-03 15:45:00 |        1 | Participant | Refunded Skier   | 1900-01-01    | task6-refunded@example.com  |
(2 rows)
```

Post-upgrade payment linkage:

```text
 id | payment_intent_id  |  status   | payment_type | event_registration_id | amount
----+--------------------+-----------+--------------+-----------------------+--------
 53 | pi_task6_succeeded | succeeded | event        |                   357 |   2500
 54 | pi_task6_refunded  | refunded  | event        |                   358 |   4000
(2 rows)
```

Legacy structure removal and Alembic head:

```text
 social_events_table | payments_social_event_id_exists
---------------------+---------------------------------
                     | f
(1 row)

 version_num
--------------
 c8f4a2d6e901
(1 row)
```

Final Flask-Migrate state:

```text
$ flask db heads
c8f4a2d6e901 (head)

$ flask db current
c8f4a2d6e901 (head)
```

## TDD Evidence

Red phase, before production changes:

```text
$ ./run-tests.sh tests/events/test_socials_migration.py -v
collected 3 items
test_legacy_social_url_redirects_to_event FAILED
test_homepage_only_lists_open_public_events FAILED
test_migrated_registration_shape_renders_in_admin_data PASSED
2 failed, 1 passed in 0.33s
```

The failures were the expected pre-change behavior: `/social/<slug>` returned
404 for an unknown legacy slug, and the homepage still queried and rendered
SocialEvent rows.

Green phase on the final source:

```text
$ ./run-tests.sh tests/events/test_socials_migration.py -v
collected 3 items
test_legacy_social_url_redirects_to_event PASSED
test_homepage_only_lists_open_public_events PASSED
test_migrated_registration_shape_renders_in_admin_data PASSED
3 passed in 0.30s
```

Additional focused coverage:

```text
$ ./run-tests.sh tests/events/ tests/routes/test_payments.py -q
81 passed, 5 warnings in 5.57s

$ ./run-tests.sh tests/practices/test_practice_migration_release.py -q
2 passed in 2.82s
```

The release-lifecycle test initially found that its deliberately minimal
scratch schema did not include `social_events`. The revision was hardened to
treat an already-absent legacy table as an already-clean state, and the release
test then passed while the seeded production-shaped migration path remained
unchanged.

## Full Suite

Command:

```text
$ ./run-tests.sh -q
```

Final tail:

```text
........................................................................ [ 90%]
........................................................................ [ 96%]
...........................................                              [100%]
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
1267 passed, 176 warnings in 53.00s
```

The warnings are the suite's existing SQLAlchemy `Query.get()` deprecation
warnings; there were no failures.

## Self-Review

- `grep -rn "SocialEvent\|social_event" app/ tests/ --include="*.py"`:
  no matches.
- Template/static search for `SocialEvent`, `social_event`,
  `create-social-event`, `Social Events`, `admin_social_events`, and
  `social_event.js`: no matches.
- Confirmed generic event template key `"social"` remains intentionally
  supported by the event template system.
- Confirmed operation ordering in the migration: events/options first,
  registrations/participants/payment updates second, foreign key/column/table
  removal last.
- Confirmed migrated JSON values from PostgreSQL: `custom_questions=[]`,
  participant roles `["Participant"]`, and registration answers `{}`.
- Confirmed the succeeded and refunded payment mappings manually.
- Confirmed the unknown payment-type webhook path logs and persists without
  crashing.
- Confirmed both legacy redirects return 302.
- `git diff --check`: clean.
- The homepage UI reuses the established card system and keeps the existing
  visual hierarchy. The only design-system change is semantic renaming of the
  unified event badge/pill tokens and classes.
- Unrelated pre-existing untracked workspace files were not modified or
  staged.

## Concerns

- Downgrade is intentionally unsupported because the migration drops source
  structures and synthesizes registrations with sentinel values.
- The two Task 6 verification events, registrations, participants, and linked
  payments remain in the local development database as migration evidence.
  No unrelated database rows were changed.

STATUS: COMPLETE
