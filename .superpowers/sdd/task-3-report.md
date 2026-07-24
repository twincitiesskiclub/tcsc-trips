# Task 3 Report: Registration service

## What I implemented

- Added `compute_price(option, event, discount_code)`, with stripped,
  case-insensitive discount matching, no match for unset/blank event codes,
  and member pricing only when a member price exists.
- Added `capacity_available(event)`, counting confirmed registrations and
  pending-payment registrations created less than one hour ago.
- Added `expire_stale_pending(event)`, which cancels only pending-payment
  registrations older than 24 hours, commits, and returns the affected count.
- Added `RegistrationError` with the required field-to-message `.errors`
  dictionary.
- Added `create_registration(event, payload, *, allow_draft=False)`, including:
  - active-event and inclusive signup-window validation;
  - the explicit admin draft-preview override;
  - active price-option ownership validation;
  - participant count, required participant fields, and DOB parsing;
  - team-name validation for multi-participant options;
  - required custom-question and choice-option validation;
  - silent removal of unknown answer keys;
  - contact and participant email normalization;
  - capacity validation;
  - server-side price computation; and
  - committed pending registrations with 1-based participant positions and
    copied role labels.
- Extended the shared event cleanup fixture with the two service-test slugs.

## Files changed

- `app/events/service.py` (new)
- `tests/events/test_service.py` (new)
- `tests/events/conftest.py`
- `.superpowers/sdd/task-3-report.md` (new)

## TDD evidence

### RED

Command run after adding the service tests and before adding production code:

```text
./run-tests.sh tests/events/test_service.py -q
```

Result:

```text
________________ ERROR collecting tests/events/test_service.py ________________
tests/events/test_service.py:12: in <module>
    from app.events.service import (
E   ModuleNotFoundError: No module named 'app.events.service'

1 error in 0.14s
```

During self-review, I added a whitespace-only configured-code case before
fixing it:

```text
./run-tests.sh tests/events/test_service.py::test_compute_price_never_matches_an_unset_event_code -q
```

The new case failed because a configured value of `"   "` incorrectly matched
an empty submitted code:

```text
E       assert (4500, True) == (5500, False)
1 failed, 2 passed in 0.34s
```

### GREEN

Focused service command:

```text
./run-tests.sh tests/events/test_service.py -q
```

Result:

```text
........................                                                 [100%]
24 passed in 1.82s
```

Event regression command before the final whitespace-code regression was
added:

```text
./run-tests.sh tests/events/ -q
```

Result:

```text
....................................                                     [100%]
36 passed in 2.43s
```

The later focused and full-suite runs include the additional regression.

## Full-suite result

Command:

```text
./run-tests.sh -q
```

Final tail:

```text
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
1233 passed, 177 warnings in 49.43s
```

The 177 warnings are the suite's existing SQLAlchemy legacy-API warnings.

## Self-review

- Confirmed every public function and the draft-preview keyword match the
  binding Task 3 interfaces.
- Confirmed all time comparisons use naive UTC `datetime.utcnow()`, with
  strict "younger than one hour" and "older than 24 hours" cutoffs.
- Confirmed capacity counts registrations rather than participants and is
  unlimited when `event.capacity is None`.
- Confirmed pricing never trusts a submitted amount and blank/whitespace-only
  configured discount codes cannot activate member pricing.
- Confirmed validation collects independent event, capacity, option, contact,
  participant, team, and custom-answer errors before raising.
- Confirmed validation performs no database writes, while successful creation
  and stale expiration commit as required.
- Confirmed only event-defined answer keys are persisted.
- Confirmed tests cover both happy paths, role/position copying, pricing
  variants, participant and team validation, question validation, option
  ownership/activity, capacity aging, stale expiration, draft preview, signup
  windows, required fields, email normalization, and malformed DOBs.
- Confirmed `git diff --check` passes.
- Existing unrelated untracked workspace files were left untouched and will
  not be staged.

## Concerns

No unresolved functional concerns within Task 3's scope.

STATUS: DONE
