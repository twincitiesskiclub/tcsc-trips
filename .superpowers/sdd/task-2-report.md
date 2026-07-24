# Task 2 Report: Event templates config and loader

## What I implemented

- Added the exact `dry_tri`, `social`, and `blank` seed templates from the Task
  2 brief.
- Added `load_event_templates() -> dict[str, dict]`, using `yaml.safe_load` and
  a module-level cache.
- Added validation for the top-level template mapping; each template's
  required `name`, `price_options`, and `custom_questions` fields; and all
  required question fields and types.
- Added offender-specific `ValueError` messages for malformed template data
  and wrapped malformed YAML parser errors as `ValueError`.
- Added `get_template(key: str) -> dict | None`, including the required `None`
  result for unknown keys.
- Added `apply_template(event: Event, template_key: str) -> None`, which sets
  the template key, deep-copies custom questions, and appends fully populated
  `EventPriceOption` objects without committing.
- Added `_reset_cache()` as a test hook.
- Added tests for cached loading, the exact Dry Tri prices and team roles,
  persisted copy semantics, unknown template lookup, and malformed questions.

## Files changed

- `config/event_templates.yaml` (new)
- `app/events/templates.py` (new)
- `tests/events/test_templates.py` (new)
- `.superpowers/sdd/task-2-report.md` (new)

## TDD evidence

### RED

Command:

```text
./run-tests.sh tests/events/test_templates.py -q
```

Failing output:

```text
_______________ ERROR collecting tests/events/test_templates.py ________________
ImportError while importing test module '/workspace/tcsc-trips/tests/events/test_templates.py'.
tests/events/test_templates.py:6: in <module>
    from app.events import templates as event_templates
E   ImportError: cannot import name 'templates' from 'app.events' (/workspace/tcsc-trips/app/events/__init__.py)

1 error in 0.13s
```

This was run after adding `tests/events/test_templates.py` and before adding
the YAML or loader implementation.

### GREEN

Command:

```text
./run-tests.sh tests/events/test_templates.py -q
```

Passing output:

```text
.....                                                                    [100%]
5 passed in 0.33s
```

Final event regression command after self-review:

```text
./run-tests.sh tests/events/ -q
```

Result:

```text
.........                                                                [100%]
9 passed in 0.56s
```

## Full-suite result

Command:

```text
./run-tests.sh -q
```

Final tail:

```text
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
1205 passed, 177 warnings in 48.13s
```

The warnings are the suite's existing SQLAlchemy legacy-API warnings.

## Self-review

- Compared `config/event_templates.yaml` directly with the YAML code block in
  the brief; `diff` reported no differences.
- Confirmed all public functions have the required names and return
  annotations.
- Confirmed the cache is populated only after parsing and validation succeed,
  and `_reset_cache()` restores an unloaded state.
- Confirmed validation names the template and question responsible for an
  error, checks `required` with an actual boolean type check, restricts question
  types to `choice` and `text`, and requires an options list for choices.
- Confirmed applying a template deep-copies nested question and participant
  role data, assigns stable zero-based sort order, defaults active options to
  `True`, and does not call `add`, `flush`, or `commit`.
- Confirmed an applied and committed event remains unchanged when the cached
  source template is later edited.
- Confirmed `git diff --check` passes for all Task 2 files.
- Existing unrelated untracked workspace files were left untouched and were
  not staged.

## Concerns

No unresolved functional concerns.

STATUS: DONE
