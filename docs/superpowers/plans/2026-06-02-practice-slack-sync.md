# Practice ↔ Slack Surface Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the "only 2 of 3 coaches show" bug and make every practice mutation consistently update its Slack surfaces through one extensible dispatcher.

**Architecture:** Two independent root-cause fixes for the coach-drop bug (data-layer degrade-visible + modal-resave preservation), then refactor `refresh_practice_posts` into a declarative surface registry and close the one confirmed admin gap (lead-confirmation toggle).

**Tech Stack:** Python 3.12, Flask, SQLAlchemy, slack-sdk/slack-bolt, pytest with `unittest.mock`. The practice refresh tests are pure-unit (mock-based) — no DB fixtures.

**Reference spec:** `docs/superpowers/specs/2026-06-02-practice-slack-sync-design.md`

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `app/practices/service.py` | Model→dataclass conversion | Modify `convert_lead_to_info` to degrade-visible instead of dropping (§1) |
| `app/slack/modals.py` | Slack modal builders | Modify `_build_person_multi_select` to always preserve assigned users (§1) |
| `app/slack/practices/_config.py` | Channel IDs / config | Add coach-summary fallback channel constant (§2) |
| `app/slack/practices/refresh.py` | Central Slack dispatcher | Refactor to `PracticeSurface` registry + `_week_bounds` helper (§2) |
| `app/routes/admin_practices.py` | Admin practice routes | Add refresh call to `toggle_lead_confirmation` (§3) |
| `tests/practices/test_service_leads.py` | NEW — convert_lead_to_info tests | Create |
| `tests/slack/test_modals_person_select.py` | NEW — modal preservation tests | Create |
| `tests/slack/test_refresh.py` | Existing dispatcher tests | Add registry tests; keep all existing green |

---

## Task 1: Bug 1a — `convert_lead_to_info` degrades visibly instead of dropping

A `PracticeLead` whose `.user` is unresolved is silently dropped, so an assigned coach disappears. Make it render a visible placeholder entry instead.

**Files:**
- Test: `tests/practices/test_service_leads.py` (create)
- Modify: `app/practices/service.py:85-109`

- [ ] **Step 1: Create the test directory marker**

Run:
```bash
mkdir -p tests/practices && touch tests/practices/__init__.py
```

- [ ] **Step 2: Write the failing test**

Create `tests/practices/test_service_leads.py`:

```python
"""Tests for PracticeLead → PracticeLeadInfo conversion edge cases."""

from types import SimpleNamespace

from app.practices.interfaces import LeadRole
from app.practices.service import convert_lead_to_info


def _fake_lead(**kw):
    return SimpleNamespace(
        id=kw.get("id", 5),
        practice_id=kw.get("practice_id", 2),
        user_id=kw.get("user_id", 99),
        role=kw.get("role", "coach"),
        confirmed=kw.get("confirmed", False),
        confirmed_at=kw.get("confirmed_at", None),
        user=kw.get("user", None),
    )


def test_missing_user_returns_visible_degraded_entry():
    lead = _fake_lead(user=None, role="coach", user_id=99)
    info = convert_lead_to_info(lead)
    assert info is not None, "lead with unresolved user must not be dropped"
    assert info.role == LeadRole.COACH
    assert info.user_id == 99
    assert "Unknown" in info.display_name
    assert info.slack_user_id is None


def test_none_lead_still_returns_none():
    assert convert_lead_to_info(None) is None


def test_resolved_user_unchanged():
    user = SimpleNamespace(
        id=99, first_name="Casey", last_name="Coach",
        email="casey@x.org", slack_user=SimpleNamespace(slack_uid="U999"),
    )
    info = convert_lead_to_info(_fake_lead(user=user, role="coach"))
    assert info.display_name == "Casey Coach"
    assert info.slack_user_id == "U999"
    assert info.role == LeadRole.COACH
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/practices/test_service_leads.py -v`
Expected: `test_missing_user_returns_visible_degraded_entry` FAILS (`info is None`).

- [ ] **Step 4: Implement degrade-visible conversion**

In `app/practices/service.py`, replace the body of `convert_lead_to_info` (lines 85-109):

```python
def convert_lead_to_info(lead: Optional[PracticeLead]) -> Optional[PracticeLeadInfo]:
    """Convert PracticeLead model to PracticeLeadInfo dataclass.

    If the linked user is unresolved, return a visible degraded entry rather
    than dropping the assignment silently (which previously hid coaches/leads).
    """
    if not lead:
        return None

    # Safe enum conversion with fallback
    try:
        role = LeadRole(lead.role) if lead.role else LeadRole.LEAD
    except (ValueError, KeyError):
        role = LeadRole.LEAD

    user = lead.user
    if user is None:
        logger.warning(
            f"PracticeLead id={lead.id} for practice id={lead.practice_id} "
            f"has unresolved user (user_id={lead.user_id}); rendering degraded entry"
        )
        return PracticeLeadInfo(
            id=lead.id,
            practice_id=lead.practice_id,
            user_id=lead.user_id,
            display_name=f"Unknown (uid {lead.user_id})",
            slack_user_id=None,
            email=None,
            role=role,
            confirmed=lead.confirmed,
            confirmed_at=lead.confirmed_at,
        )

    slack_uid = user.slack_user.slack_uid if user.slack_user else None

    return PracticeLeadInfo(
        id=lead.id,
        practice_id=lead.practice_id,
        user_id=user.id,
        display_name=f"{user.first_name} {user.last_name}",
        slack_user_id=slack_uid,
        email=user.email,
        role=role,
        confirmed=lead.confirmed,
        confirmed_at=lead.confirmed_at,
    )
```

- [ ] **Step 5: Simplify `convert_practice_to_info` drop-logging (now redundant)**

In `app/practices/service.py:136-146`, the per-lead warning branch now only fires for a truly `None` lead (which can't be in `practice.leads`). Keep the loop but the `else` warning is dead for real leads. Leave the loop as-is — it is harmless and still guards `None`. No change required; this step is a no-op verification that the loop at lines 136-146 still appends every non-`None` result.

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/practices/test_service_leads.py -v`
Expected: 3 PASS.

- [ ] **Step 7: Commit**

```bash
git add app/practices/service.py tests/practices/__init__.py tests/practices/test_service_leads.py
git commit -m "fix(practices): render unresolved practice leads instead of silently dropping them"
```

---

## Task 2: Bug 1b — edit-full modal preserves assigned users not in the eligible list

`eligible_coaches` is filtered to users with `HEAD_COACH`/`ASSISTANT_COACH` tags **and** a linked Slack UID (`bolt_app.py:380-387`). An assigned coach lacking the tag or Slack link is absent from the modal's option list, so it can't be pre-selected — and the submit handler's delete-all-then-re-add (`bolt_app.py:953-956`) permanently drops them. Fix: always include currently-assigned users in the option list.

**Files:**
- Test: `tests/slack/test_modals_person_select.py` (create)
- Modify: `app/slack/modals.py:77-93`

- [ ] **Step 1: Write the failing test**

Create `tests/slack/test_modals_person_select.py`:

```python
"""Tests for the practice person (coach/lead) multi-select builder."""

from types import SimpleNamespace

from app.slack.modals import _build_person_multi_select


def _assigned(user_id, display_name="Someone"):
    return SimpleNamespace(user_id=user_id, display_name=display_name)


def test_eligible_users_become_options():
    eligible = [(1, "Alice A", "U1"), (2, "Bob B", "U2")]
    el = _build_person_multi_select("coach_ids", "Pick coaches", eligible, [])
    values = {o["value"] for o in el["options"]}
    assert values == {"1", "2"}
    assert "initial_options" not in el


def test_assigned_user_outside_eligible_is_preserved():
    eligible = [(1, "Alice A", "U1"), (2, "Bob B", "U2")]
    assigned = [_assigned(3, "Carol C")]  # not in eligible list
    el = _build_person_multi_select("coach_ids", "Pick coaches", eligible, assigned)
    option_values = {o["value"] for o in el["options"]}
    assert "3" in option_values, "assigned user must survive even if not eligible"
    init_values = {o["value"] for o in el["initial_options"]}
    assert init_values == {"3"}


def test_assigned_user_with_blank_name_gets_fallback_label():
    assigned = [_assigned(7, "")]
    el = _build_person_multi_select("coach_ids", "Pick coaches", [], assigned)
    added = next(o for o in el["options"] if o["value"] == "7")
    assert added["text"]["text"].strip() != ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/slack/test_modals_person_select.py -v`
Expected: `test_assigned_user_outside_eligible_is_preserved` FAILS (`"3"` not in options).

- [ ] **Step 3: Implement assigned-user preservation**

In `app/slack/modals.py`, replace the body of `_build_person_multi_select` from line 77 down to the `return` (lines 77-94):

```python
    options = [
        {"text": {"type": "plain_text", "text": name[:75]}, "value": str(uid)}
        for uid, name, _ in eligible_users
    ]

    # Always include currently-assigned users, even if they are no longer in
    # the eligible list (e.g. missing a coach tag or Slack link). Otherwise the
    # modal cannot pre-select them and a re-save silently drops the assignment.
    eligible_ids = {str(uid) for uid, _, _ in eligible_users}
    for assignment in current_assignments:
        aid = str(assignment.user_id)
        if aid not in eligible_ids:
            label = (getattr(assignment, "display_name", None)
                     or f"Unknown (uid {assignment.user_id})")[:75]
            options.append({
                "text": {"type": "plain_text", "text": label},
                "value": aid,
            })
            eligible_ids.add(aid)

    element = {
        "type": "multi_static_select",
        "action_id": action_id,
        "placeholder": {"type": "plain_text", "text": placeholder},
        "options": options,
    }

    # Set initial selections from current assignments
    current_ids = {str(a.user_id) for a in current_assignments}
    initial = [opt for opt in options if opt["value"] in current_ids]
    if initial:
        element["initial_options"] = initial

    return element
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/slack/test_modals_person_select.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/slack/modals.py tests/slack/test_modals_person_select.py
git commit -m "fix(slack): keep assigned coaches/leads in edit modal so re-save can't drop them"
```

---

## Task 3: Add shared config — coach-summary fallback channel

`refresh.py` hardcodes the fallback channel literal `'C053T1AR48Y'`. Move it to `_config.py` so the registry refactor (Task 4) references a named constant.

**Files:**
- Modify: `app/slack/practices/_config.py:64`

- [ ] **Step 1: Add the constant**

In `app/slack/practices/_config.py`, immediately after the `COLLAB_CHANNEL_ID` line (line 64), add:

```python
# Legacy fallback channel for the coach weekly summary, used when an update to
# COLLAB_CHANNEL_ID fails (older summaries were posted here).
COACH_SUMMARY_FALLBACK_CHANNEL_ID = "C053T1AR48Y"
```

- [ ] **Step 2: Export it from the barrel**

In `app/slack/practices/__init__.py`, find the import line `COORD_CHANNEL_ID,` (line 16) and add on the next line:

```python
    COACH_SUMMARY_FALLBACK_CHANNEL_ID,
```

Then find `"COORD_CHANNEL_ID",` in the `__all__` list (line 79) and add on the next line:

```python
    "COACH_SUMMARY_FALLBACK_CHANNEL_ID",
```

- [ ] **Step 3: Verify import works**

Run: `python -c "from app.slack.practices._config import COACH_SUMMARY_FALLBACK_CHANNEL_ID; print(COACH_SUMMARY_FALLBACK_CHANNEL_ID)"`
Expected: prints `C053T1AR48Y`

- [ ] **Step 4: Commit**

```bash
git add app/slack/practices/_config.py app/slack/practices/__init__.py
git commit -m "refactor(slack): move coach-summary fallback channel to _config"
```

---

## Task 4: Refactor `refresh_practice_posts` into a declarative surface registry

Turn the four bespoke `_refresh_X` calls into a registry loop with a uniform contract, ready for future surfaces (e.g. lead-scheduling DMs). Behavior and the public result-dict shape are preserved so existing `test_refresh.py` tests stay green.

**Files:**
- Modify: `app/slack/practices/refresh.py`
- Test: `tests/slack/test_refresh.py` (add a class)

- [ ] **Step 1: Write the failing registry tests**

Append to `tests/slack/test_refresh.py`:

```python
class TestSurfaceRegistry:
    """Test the declarative PracticeSurface registry."""

    def test_registry_covers_known_surfaces(self):
        from app.slack.practices.refresh import PRACTICE_SURFACES
        names = {s.name for s in PRACTICE_SURFACES}
        assert names == {
            "announcement", "collab", "coach_summary", "weekly_summary"
        }

    def test_surface_skips_when_ts_absent(self):
        from app.slack.practices.refresh import PracticeSurface
        calls = []
        s = PracticeSurface(
            "x", "slack_message_ts", ["edit"],
            lambda p, c: calls.append(c) or {"success": True},
        )
        practice = FakePractice()  # no slack_message_ts
        assert s.refresh(practice, "edit") == {"skipped": True}
        assert calls == []

    def test_surface_skips_when_change_type_not_applicable(self):
        from app.slack.practices.refresh import PracticeSurface
        calls = []
        s = PracticeSurface(
            "x", "slack_message_ts", ["edit"],
            lambda p, c: calls.append(c) or {"success": True},
        )
        practice = FakePractice(slack_message_ts="1")
        assert s.refresh(practice, "rsvp") == {"skipped": True}
        assert calls == []

    def test_surface_runs_when_applicable_and_present(self):
        from app.slack.practices.refresh import PracticeSurface
        s = PracticeSurface(
            "x", "slack_message_ts", ["edit"],
            lambda p, c: {"success": True, "ct": c},
        )
        practice = FakePractice(slack_message_ts="1")
        assert s.refresh(practice, "edit") == {"success": True, "ct": "edit"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/slack/test_refresh.py::TestSurfaceRegistry -v`
Expected: FAIL with `ImportError`/`cannot import name 'PRACTICE_SURFACES'`.

- [ ] **Step 3: Add the `PracticeSurface` class and registry**

In `app/slack/practices/refresh.py`, add after the `logger = logging.getLogger(__name__)` line (line 15):

```python
# Change types that any surface may react to.
ALL_CHANGE_TYPES = ("edit", "cancel", "delete", "rsvp", "workout", "create")


class PracticeSurface:
    """A Slack surface that displays practice info and can be refreshed.

    Adding a new surface (e.g. a future lead-scheduling DM) is one registry
    entry — no changes to refresh_practice_posts() or any call site.
    """

    def __init__(self, name, ts_field, applies_to, refresh_fn):
        self.name = name
        self.ts_field = ts_field
        self.applies_to = set(applies_to)
        self._refresh_fn = refresh_fn

    def is_present(self, practice):
        return bool(getattr(practice, self.ts_field, None))

    def refresh(self, practice, change_type):
        if not self.is_present(practice):
            return {"skipped": True}
        if change_type not in self.applies_to:
            return {"skipped": True}
        return self._refresh_fn(practice, change_type)
```

- [ ] **Step 4: Add a `_week_bounds` helper (DRY the duplicated week math)**

In `app/slack/practices/refresh.py`, add right after the `PracticeSurface` class:

```python
def _week_bounds(practice_date):
    """Return (week_start, week_end) Monday-anchored bounds for a practice date."""
    days_since_monday = practice_date.weekday()
    week_start = (practice_date - timedelta(days=days_since_monday)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return week_start, week_start + timedelta(days=7)
```

Then in `_refresh_coach_summary` replace lines 115-120:

```python
        week_start, week_end = _week_bounds(practice.date)
```

And in `_refresh_weekly_summary` replace lines 174-179:

```python
        week_start, week_end = _week_bounds(practice.date)
```

- [ ] **Step 5: Use the named fallback channel constant**

In `_refresh_coach_summary`, change the import block (lines 108-112) to also import the constant, and update the `channels_to_try` line (141):

Replace line 111 (`from app.slack.practices._config import COLLAB_CHANNEL_ID`) with:

```python
        from app.slack.practices._config import (
            COLLAB_CHANNEL_ID,
            COACH_SUMMARY_FALLBACK_CHANNEL_ID,
        )
```

Replace line 141 (`channels_to_try = [COLLAB_CHANNEL_ID, 'C053T1AR48Y']`) with:

```python
        channels_to_try = [COLLAB_CHANNEL_ID, COACH_SUMMARY_FALLBACK_CHANNEL_ID]
```

- [ ] **Step 6: Build the registry and rewrite `refresh_practice_posts` as a loop**

In `app/slack/practices/refresh.py`, add the registry definition AFTER all four `_refresh_*` functions are defined (i.e. near the bottom of the file, after `_refresh_weekly_summary` ends at line 233, before `_post_edit_logs`):

```python
PRACTICE_SURFACES = [
    PracticeSurface("announcement", "slack_message_ts", ALL_CHANGE_TYPES, _refresh_announcement),
    PracticeSurface("collab", "slack_collab_message_ts", ALL_CHANGE_TYPES, _refresh_collab),
    PracticeSurface("coach_summary", "slack_coach_summary_ts", ALL_CHANGE_TYPES, _refresh_coach_summary),
    PracticeSurface("weekly_summary", "slack_weekly_summary_ts", ALL_CHANGE_TYPES, _refresh_weekly_summary),
]
```

Then replace the body of `refresh_practice_posts` (lines 36-54) with:

```python
    results = {}

    for surface in PRACTICE_SURFACES:
        results[surface.name] = surface.refresh(practice, change_type)

    # Edit logging (thread replies) remains a post-pass keyed on notify + type
    if notify and actor_slack_id and change_type in ("edit", "workout"):
        results["edit_logs"] = _post_edit_logs(practice, actor_slack_id)

    return results
```

> Note: `_refresh_announcement` keeps its own internal guard requiring BOTH
> `slack_message_ts` and `slack_channel_id`, so behavior is unchanged when the
> channel id is missing.

- [ ] **Step 7: Run the FULL refresh test suite**

Run: `pytest tests/slack/test_refresh.py -v`
Expected: all existing tests PASS plus the 4 new `TestSurfaceRegistry` tests PASS.

- [ ] **Step 8: Commit**

```bash
git add app/slack/practices/refresh.py tests/slack/test_refresh.py
git commit -m "refactor(slack): drive practice post refresh from a declarative surface registry"
```

---

## Task 5: Close the gap — lead-confirmation toggle triggers a refresh

`toggle_lead_confirmation` (`admin_practices.py:964-987`) commits a confirmation change but never refreshes Slack, even though confirmation status renders on the announcement, collab, and coach-summary posts. Add the refresh call. (This repo does not unit-test admin routes — see CLAUDE.md "Not tested: admin routes" — so verification is manual, consistent with existing practice.)

**Files:**
- Modify: `app/routes/admin_practices.py:964-987`

- [ ] **Step 1: Add the refresh call after a successful toggle**

In `app/routes/admin_practices.py`, inside `toggle_lead_confirmation`, replace the success block (lines 973-983) with:

```python
    try:
        lead.confirmed = not lead.confirmed
        lead.confirmed_at = datetime.utcnow() if lead.confirmed else None
        db.session.commit()

        # Keep Slack surfaces (announcement / collab / coach summary) in sync.
        # Local import matches the existing edit/cancel/delete routes in this file.
        from app.slack.practices import refresh_practice_posts
        from flask import current_app
        practice = Practice.query.get(practice_id)
        if practice:
            try:
                refresh_practice_posts(practice, change_type='edit')
            except Exception as refresh_err:
                current_app.logger.warning(
                    f"Lead toggle saved but Slack refresh failed for practice "
                    f"#{practice_id}: {refresh_err}"
                )

        return jsonify({
            'success': True,
            'confirmed': lead.confirmed,
            'confirmed_at': lead.confirmed_at.isoformat() if lead.confirmed_at else None,
            'message': f"Lead {'confirmed' if lead.confirmed else 'unconfirmed'} successfully"
        })
```

> Note: this file imports `refresh_practice_posts` **locally inside each route**
> (see lines 298, 319, 351), and does NOT import `current_app` at module level.
> The local imports above match that established pattern — do not hoist them.

- [ ] **Step 2: Sanity-check the module imports cleanly**

Run: `python -c "import app.routes.admin_practices"`
Expected: no error.

- [ ] **Step 3: Manual verification (dev workspace)**

Per memory guardrails, use the test workspace only. In a dev session: create/announce a practice with an assigned lead, toggle the lead's confirmation in the admin UI, and confirm the announcement/collab/coach-summary posts update to reflect the new confirmation state. Document the result in the PR description.

- [ ] **Step 4: Commit**

```bash
git add app/routes/admin_practices.py
git commit -m "fix(admin): refresh Slack posts when a practice lead confirmation is toggled"
```

---

## Task 6: Full-suite regression check

- [ ] **Step 1: Run the whole test suite**

Run: `pytest -q`
Expected: all tests pass (existing 124 + the new ones from Tasks 1, 2, 4).

- [ ] **Step 2: Final commit if any incidental fixups were needed**

```bash
git add -A
git commit -m "test: full-suite green for practice↔Slack sync work" || echo "nothing to commit"
```

---

## Self-Review Notes (coverage vs spec)

- **§1 (bug 1, data-layer)** → Task 1. **§1 (bug 1, modal resave)** → Task 2.
- **§2 (unified registry + extracted helpers + named fallback channel)** → Tasks 3 & 4.
- **§3 (gap audit / toggle-lead-confirmation)** → Task 5. Other audited sites already refresh and need no change (verified in spec table).
- **§4 (future lead-DM extension recipe)** → enabled by Task 4's `PracticeSurface` registry; documented in the spec, no code until that feature lands (YAGNI).
- **§5 (testing)** → Tasks 1, 2, 4 add tests; Task 6 runs the full suite; Task 5 manual verification matches the repo's untested-admin-routes convention.
