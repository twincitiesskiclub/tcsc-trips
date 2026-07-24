# Task 5 Report: Admin Events tab

## Implemented

- Added the `admin_events_bp` blueprint and registered it with the Flask app.
- Added all required admin-guarded event endpoints:
  - event list page and JSON data, including confirmed revenue
  - template-backed create and JSON-backed edit
  - duplicate with unique `-copy`, `-copy-2`, and later suffixes
  - draft-only delete
  - JSON status transitions
  - registrations page and flattened JSON data
  - matching CSV export
  - pending cancellation and paid refund
- Added dynamic price-option and custom-question row editors. The editors serialize to the required hidden `price_options_json` and `custom_questions_json` textareas, preserve price-option IDs on edit, and convert dollars to cents before submission.
- Added server-side replacement logic that matches price options by ID and refuses to remove an option that has registrations.
- Added public `validate_question()` and `validate_price_option()` wrappers in `app/events/templates.py`; admin JSON validation reuses the Task 2 validators through those wrappers.
- Extracted `refund_or_cancel_payment()` in `app/routes/payments.py`. The existing single-payment refund route, bulk refund route, and event-registration refund action now share the same Stripe calls.
- Added event and registration grids with client-side search, filtering, sorting, responsive overflow, status actions, duplication, draft deletion, roster cancellation/refund, per-option confirmed counts, and CSV export.
- Added the Events navigation item beside Social Events. The current admin base delegates its navigation markup to `admin/partials/sidebar.html`, so the link was added there rather than directly to `admin_base.html`.
- Rebuilt the generated Tailwind stylesheet so all new utility classes ship in production.

## Files

Created:

- `app/routes/admin_events.py`
- `app/static/admin_events.js`
- `app/templates/admin/events.html`
- `app/templates/admin/event_form.html`
- `app/templates/admin/event_registrations.html`
- `tests/events/test_admin.py`
- `.superpowers/sdd/task-5-report.md`

Modified:

- `app/__init__.py`
- `app/events/templates.py`
- `app/routes/payments.py`
- `app/static/css/tailwind-output.css`
- `app/templates/admin/partials/sidebar.html`
- `tests/events/conftest.py`

## TDD evidence

Initial RED, before the blueprint existed:

```text
collected 7 items
tests/events/test_admin.py ... 7 failed
All failures were the expected 404 responses from the seven binding endpoints.
7 failed in 0.57s
```

Focused GREEN after implementation and edge coverage:

```text
..............                                                           [100%]
14 passed in 1.14s
```

Events package:

```text
..................................................................       [100%]
66 passed, 9 warnings in 4.89s
```

Payment route regression coverage after extracting the refund helper:

```text
..........                                                               [100%]
10 passed, 6 warnings in 1.48s
```

Syntax and generated-asset checks:

```text
python -m py_compile app/routes/admin_events.py app/routes/payments.py app/events/templates.py
node --check app/static/admin_events.js
npm run tailwind:build
All passed.
```

## Full-suite tail

Command: `./run-tests.sh -q`

```text
........................................................................ [ 91%]
........................................................................ [ 96%]
......................................                                   [100%]
1262 passed, 177 warnings in 52.50s
```

The warnings are existing SQLAlchemy `Query.get()` deprecations outside this new blueprint. The new blueprint uses `db.get_or_404()` and adds no new legacy warnings.

## Self-review

- Verified every listed endpoint has `@admin_required`.
- Verified event data revenue counts only confirmed registrations.
- Verified CSV field order and values come from the same flattening helper as the registrations JSON endpoint.
- Verified participant values use the required `role: name (dob, email, phone)` shape and question columns use each configured question key.
- Verified duplicate copies all event configuration and price options, starts in draft, and never copies registrations.
- Verified invalid status values return 400 and active deletion returns 409.
- Verified registered price options cannot be omitted during replacement and produce a clear 400 response.
- Verified paid cancellation calls the shared payment refund helper and marks the registration refunded; unpaid pending cancellation marks it cancelled.
- Verified list, form, and registrations templates render through authenticated route tests.
- Ran `git diff --check`, Python compile checks, JavaScript syntax checks, focused tests, event tests, payment regression tests, and the full suite.
- Preserved all unrelated untracked workspace files and did not modify `.env`, `run-tests.sh`, or any other `.superpowers/` file.

## Concerns

- The brief references Tabulator, but this branch deliberately removed Tabulator and its CDN from every admin surface. The current Social Events pattern is a self-contained AdminUI table/list. Task 5 follows that current convention while preserving all requested grid capabilities and endpoint shapes.
- No live browser was available for a visual walkthrough. Route rendering, responsive/touch styles, keyboard focus states, template compilation, JavaScript syntax, and generated Tailwind coverage were verified automatically.

STATUS: COMPLETE
