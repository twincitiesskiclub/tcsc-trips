# Practice Delete Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep Slack-first practice deletion safe when Slack cleanup is partial or the final database delete fails by restoring the surviving practice's root and weekly summaries once.

**Architecture:** Capture the original root/channel/week, keep the current survivor-preserving cleanup, and add one focused recovery orchestrator. It reloads the database outcome, rebuilds or exactly-channel-reposts the root, then calls the canonical week-summary helper without delete exclusion; it never loops or creates an outbox.

**Tech Stack:** Python 3.13, Flask, Flask-SQLAlchemy, Slack Web API, pytest.

## Global Constraints

- Execute this plan after `2026-07-16-practice-summary-identity.md`; it consumes `refresh_registered_practice_summaries(value, *, exclude_practice_id=None)`.
- Preserve Slack-first deletion and the existing combined-session survivor behavior.
- Treat every failed posted-root cleanup as potentially partial; do not assume `success: false` means Slack was untouched.
- Recovery gets one root update or repost and one week-summary refresh. No retry loop, soft delete, outbox, or new model.
- Repost a deleted standalone root to the exact captured channel ID; never resolve a channel name during compensation.
- Never split a shared root. If its identity is missing or changed unexpectedly, report incomplete recovery.
- Never return success while a surviving practice row has incomplete Slack recovery.
- Do not expose raw database exceptions to the Admin client; log structured diagnostic details server-side.
- Keep the local companion stopped and make no external Slack calls in tests.
- Run persistent PostgreSQL tests serially, use TDD, and preserve the untracked `env` symlink.

---

## File Map

- Modify `app/slack/practices/announcements.py`: support exact channel-ID posting for internal compensation.
- Create `app/slack/practices/delete_recovery.py`: reload and restore one failed deletion.
- Modify `app/slack/practices/__init__.py`: export `recover_failed_practice_delete`.
- Modify `app/routes/admin_practices.py`: capture deletion identity, invoke recovery, and return truthful HTTP results.
- Modify `tests/slack/test_details_reply_wiring.py`: pin exact-channel post wiring.
- Create `tests/slack/test_delete_recovery.py`: pin standalone/shared/absent/incomplete one-shot behavior.
- Modify `tests/routes/test_admin_practice_delete.py`: pin partial-cleanup and final-commit route semantics.

### Task 1: Add Exact-Channel Reposting and the One-Shot Recovery Primitive

**Files:**

- Modify: `app/slack/practices/announcements.py`
- Create: `app/slack/practices/delete_recovery.py`
- Modify: `app/slack/practices/__init__.py`
- Modify: `tests/slack/test_details_reply_wiring.py`
- Create: `tests/slack/test_delete_recovery.py`

**Interfaces:**

- Extends `post_practice_announcement(..., *, channel_id_override=None) -> dict`.
- Produces `_restore_practice_announcement(practice, *, original_channel_id, original_message_ts) -> dict`.
- Produces `recover_failed_practice_delete(practice_id, *, original_channel_id, original_message_ts, original_week_start) -> dict`.

- [ ] **Step 1: Write the failing exact-channel post test**

Add to `TestPostPracticeAnnouncementWiring`:

```python
def test_exact_channel_id_override_bypasses_name_lookup(self):
    practice = self._practice()
    client = MagicMock()
    client.chat_postMessage.return_value = {"ts": "200.1"}

    with patch(
        "app.slack.practices.announcements.get_slack_client",
        return_value=client,
    ), patch(
        "app.slack.practices.announcements.get_channel_id_by_name",
    ) as resolve_name, patch(
        "app.slack.practices.announcements._get_announcement_channel",
    ) as resolve_default, patch(
        "app.slack.practices.announcements._conditions_for_render",
        return_value=None,
    ), patch(
        "app.slack.practices.announcements._upsert_details_reply",
        return_value={"success": True},
    ), patch(
        "app.slack.practices.announcements._seed_plan_reactions",
    ):
        result = post_practice_announcement(
            practice,
            channel_id_override="C-ORIGINAL",
        )

    assert result["success"] is True
    assert client.chat_postMessage.call_args.kwargs["channel"] == "C-ORIGINAL"
    resolve_name.assert_not_called()
    resolve_default.assert_not_called()
```

Also assert supplying both `channel_override` and `channel_id_override` returns
`{"success": False, "error": "Choose one channel override"}` before a Slack
client is used.

- [ ] **Step 2: Write failing recovery tests**

Create fixtures for a standalone practice and two practices sharing one exact
channel/root. Add these tests:

```python
def test_reload_absent_reports_delete_committed_without_slack_writes(...):
    result = recover_failed_practice_delete(
        missing_id,
        original_channel_id="C-ONE",
        original_message_ts="100.1",
        original_week_start=date(2026, 7, 13),
    )
    assert result == {
        "success": True,
        "outcome": "deleted",
        "practice_deleted": True,
    }
    update_root.assert_not_called()
    post_root.assert_not_called()
    refresh_summaries.assert_not_called()


def test_linked_original_root_is_rebuilt_then_summaries_include_row(...):
    result = recover_failed_practice_delete(
        shared.id,
        original_channel_id="C-SHARED",
        original_message_ts="100.1",
        original_week_start=date(2026, 7, 13),
    )
    update_root.assert_called_once_with(shared)
    refresh_summaries.assert_called_once_with(
        date(2026, 7, 13), exclude_practice_id=None
    )
    assert result["outcome"] == "restored"


def test_cleared_standalone_root_is_reposted_once_to_exact_channel(...):
    practice.slack_channel_id = None
    practice.slack_message_ts = None
    db.session.commit()
    result = recover_failed_practice_delete(
        practice.id,
        original_channel_id="C-ORIGINAL",
        original_message_ts="100.1",
        original_week_start=date(2026, 7, 13),
    )
    post_root.assert_called_once_with(
        practice, channel_id_override="C-ORIGINAL"
    )
    assert result["outcome"] == "restored"
```

Add three edge regressions:

- `message_not_found` while updating a standalone stale identity clears its
  root/channel/Details fields in memory and performs one exact-channel repost;
- `message_not_found` for a shared identity reports incomplete and never posts
  a split root;
- a root failure or a registered summary `success: false` reports incomplete,
  while summary `skipped: "absent"` is legitimate.

Each test asserts update, post, and summary functions are called at most once.

- [ ] **Step 3: Run the new tests and verify RED**

```bash
SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest tests/slack/test_details_reply_wiring.py::TestPostPracticeAnnouncementWiring::test_exact_channel_id_override_bypasses_name_lookup tests/slack/test_delete_recovery.py -q
```

Expected: unexpected `channel_id_override` and missing recovery module failures.

- [ ] **Step 4: Add exact channel-ID resolution**

Extend the signature without breaking existing positional callers:

```python
def post_practice_announcement(
    practice: Practice,
    weather: Optional[WeatherConditions] = _UNSET,
    trail_conditions: Optional[TrailCondition] = _UNSET,
    channel_override: Optional[str] = None,
    *,
    channel_id_override: Optional[str] = None,
) -> dict:
```

Resolve the channel in this order:

```python
if channel_override and channel_id_override:
    return {"success": False, "error": "Choose one channel override"}
if channel_id_override:
    channel_id = channel_id_override
elif channel_override:
    channel_id = get_channel_id_by_name(channel_override.lstrip("#"))
else:
    channel_id = _get_announcement_channel()
```

- [ ] **Step 5: Implement the private root restorer**

In `delete_recovery.py`, load siblings only by the captured exact
`original_channel_id` and `original_message_ts`. Implement these branches:

```python
if not original_message_ts:
    return {"success": True, "action": "not_posted"}
if not original_channel_id:
    return {"success": False, "error": "Original Slack channel is missing"}

original_siblings = Practice.query.filter_by(
    slack_channel_id=original_channel_id,
    slack_message_ts=original_message_ts,
).filter(Practice.id != practice.id).all()
shared = bool(original_siblings) or bool(practice.slack_session_emoji)
current_is_original = (
    practice.slack_channel_id == original_channel_id
    and practice.slack_message_ts == original_message_ts
)
```

If `current_is_original`, call `update_practice_slack_post(practice)` once. On
success, return `action="rebuilt"`. If it reports `message_not_found` and the
root is standalone, clear `slack_channel_id`, `slack_message_ts`, and
`slack_details_ts` in memory and perform one exact-channel repost. Any other
failure returns incomplete.

If the row identity is cleared and `shared` is false, repost once. A changed
non-empty identity or a cleared identity with original siblings returns an
error instead of creating a duplicate/split root.

- [ ] **Step 6: Implement the public recovery orchestrator**

Use one rollback and one fresh read:

```python
def recover_failed_practice_delete(
    practice_id,
    *,
    original_channel_id,
    original_message_ts,
    original_week_start,
):
    try:
        db.session.rollback()
        practice = db.session.get(
            Practice, practice_id, populate_existing=True
        )
    except Exception as exc:
        return _incomplete(error=f"Could not reload practice: {exc}")
    if practice is None:
        return {
            "success": True,
            "outcome": "deleted",
            "practice_deleted": True,
        }
```

Call `_restore_practice_announcement(...)`, then independently call:

```python
refresh_registered_practice_summaries(
    original_week_start,
    exclude_practice_id=None,
)
```

Catch each stage so a root exception does not prevent the one summary repair.
A summary result is healthy only when `success is True` or
`skipped == "absent"`. Return the exact result shapes:

```python
{
    "success": True,
    "outcome": "restored",
    "practice_deleted": False,
    "practice_restored": True,
    "announcement": announcement,
    "summaries": summaries,
}
```

or:

```python
{
    "success": False,
    "outcome": "incomplete",
    "practice_deleted": False,
    "practice_restored": False,
    "recovery_incomplete": True,
    "announcement": announcement,
    "summaries": summaries,
    "error": error,
}
```

Export only `recover_failed_practice_delete` from the package.

- [ ] **Step 7: Run focused and adjacent root tests**

```bash
SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest tests/slack/test_details_reply_wiring.py tests/slack/test_delete_recovery.py tests/slack/test_combined_announcements.py -q
```

Expected: exact-channel, standalone, shared, absent-row, message-not-found, and
one-shot tests pass.

- [ ] **Step 8: Commit**

```bash
git add app/slack/practices/announcements.py app/slack/practices/delete_recovery.py app/slack/practices/__init__.py tests/slack/test_details_reply_wiring.py tests/slack/test_delete_recovery.py
git commit -m "feat(slack): add one-shot practice delete recovery"
```

### Task 2: Wire Recovery into the Admin Delete Transaction

**Files:**

- Modify: `app/routes/admin_practices.py`
- Modify: `tests/routes/test_admin_practice_delete.py`

**Interfaces:**

- `delete_practice()` captures original channel, root, and Monday before Slack cleanup.
- Both an unsafe posted-root cleanup result and any exception after cleanup begins call `recover_failed_practice_delete(...)` once.
- Produces stable restored, incomplete, and already-deleted HTTP bodies; the existing Admin JavaScript needs no change because it already renders `result.error`.

- [ ] **Step 1: Add failing route orchestration tests**

Add these tests around the real route with Slack/recovery collaborators patched
at their package import boundary:

```python
def test_failed_final_database_delete_reposts_standalone_in_original_channel(...):
    recovery = {
        "success": True,
        "outcome": "restored",
        "practice_deleted": False,
        "practice_restored": True,
    }
    refresh_posts.return_value = {"announcement": {"success": True}}
    final_commit.side_effect = RuntimeError("database commit failed")
    recover_delete.return_value = recovery

    response = admin_client.post(f"/admin/practices/{practice_id}/delete")

    assert response.status_code == 500
    assert response.get_json() == {
        "success": False,
        "practice_deleted": False,
        "practice_restored": True,
        "error": (
            "Practice was not deleted. Its Slack posts were restored; "
            "review and retry the delete."
        ),
    }
    recover_delete.assert_called_once_with(
        practice_id,
        original_channel_id="C-ONE",
        original_message_ts="root.1",
        original_week_start=date(2026, 7, 13),
    )
```

Use the same assertion for a shared-root practice, and additionally have the
recovery primitive test from Task 1 prove the combined rebuild receives no
delete exclusion.

- [ ] **Step 2: Add partial cleanup, absent-row, and incomplete tests**

Pin these exact outcomes:

```python
def test_partial_slack_cleanup_restores_post_and_keeps_database_row(...):
    refresh_posts.return_value = {
        "announcement": {"success": False, "error": "root failed"}
    }
    recover_delete.return_value = restored_result
    response = admin_client.post(f"/admin/practices/{practice_id}/delete")
    assert response.status_code == 502
    assert response.get_json()["practice_restored"] is True
    assert practice_exists(app, practice_id) is True


def test_commit_exception_with_missing_row_reports_delete_committed(...):
    recover_delete.return_value = {
        "success": True,
        "outcome": "deleted",
        "practice_deleted": True,
    }
    response = admin_client.post(f"/admin/practices/{practice_id}/delete")
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "practice_deleted": True,
        "message": "Practice deleted successfully",
    }


def test_incomplete_delete_recovery_requires_manual_reconciliation(...):
    recover_delete.return_value = incomplete_result
    response = admin_client.post(f"/admin/practices/{practice_id}/delete")
    assert response.status_code in {500, 502}
    assert response.get_json() == {
        "success": False,
        "practice_deleted": False,
        "practice_restored": False,
        "recovery_incomplete": True,
        "error": (
            "Practice was not deleted, and Slack recovery is incomplete. "
            "Manual reconciliation is required."
        ),
    }
```

Update existing unsafe-announcement tests to expect recovery rather than the
old unqualified `practice was not deleted` response. Keep unposted deletion
and normal successful deletion expectations unchanged.

- [ ] **Step 3: Run the new route tests and verify RED**

```bash
SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest tests/routes/test_admin_practice_delete.py -k "failed_final_database_delete or partial_slack_cleanup or commit_exception_with_missing_row or incomplete_delete_recovery" -q
```

Expected: current early 502/raw rollback-only 500 paths never invoke recovery
and do not return the required state flags.

- [ ] **Step 4: Capture the immutable deletion snapshot**

At the start of `delete_practice()` capture:

```python
original_channel_id = practice.slack_channel_id
original_message_ts = practice.slack_message_ts
original_week_start = (
    practice.date.date() - timedelta(days=practice.date.weekday())
)
cleanup_started = False
```

Set `cleanup_started = True` immediately before
`refresh_practice_posts(..., change_type="delete")`.

- [ ] **Step 5: Add one response mapper for recovery outcomes**

Keep this local to `admin_practices.py`:

```python
def _failed_delete_response(recovery, *, status_code):
    if recovery.get("outcome") == "deleted":
        return jsonify({
            "success": True,
            "practice_deleted": True,
            "message": "Practice deleted successfully",
        }), 200
    if recovery.get("success") is True:
        return jsonify({
            "success": False,
            "practice_deleted": False,
            "practice_restored": True,
            "error": (
                "Practice was not deleted. Its Slack posts were restored; "
                "review and retry the delete."
            ),
        }), status_code
    return jsonify({
        "success": False,
        "practice_deleted": False,
        "practice_restored": False,
        "recovery_incomplete": True,
        "error": (
            "Practice was not deleted, and Slack recovery is incomplete. "
            "Manual reconciliation is required."
        ),
    }), status_code
```

- [ ] **Step 6: Invoke recovery on both unsafe paths**

If a posted root's announcement result is not explicitly successful, call the
recovery function and map it with HTTP 502. In the exception handler, call it
with HTTP 500 only when `cleanup_started` is true. Import the recovery function
locally like the existing refresh import. Rollback occurs inside the recovery
orchestrator, so do not perform a competing second recovery attempt.

Log a warning for restored recovery, a warning when an exception is followed
by absent-row read-back, and a critical entry for incomplete recovery. Include
practice ID, original channel/root/week, initial cause, and recovery results in
server logs; never return the raw exception.

- [ ] **Step 7: Run route and adjacent regressions**

```bash
SLACK_BOT_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest tests/routes/test_admin_practice_delete.py tests/slack/test_delete_recovery.py tests/slack/test_refresh.py tests/slack/test_refresh_delete_exclusion.py tests/slack/test_combined_announcements.py tests/slack/test_details_reply_wiring.py -q
```

Expected: normal, unposted, shared, partial, failed-commit, restored, absent,
and incomplete cases pass.

- [ ] **Step 8: Commit**

```bash
git add app/routes/admin_practices.py tests/routes/test_admin_practice_delete.py
git commit -m "fix(admin): compensate failed practice deletes"
```

### Task 3: Verify the Full Delete Safety Boundary

**Files:**

- No planned file changes; this task verifies the committed Tasks 1–2.

**Interfaces:**

- No new interface; this is the integration and review gate.

- [ ] **Step 1: Run all practice deletion/announcement tests serially**

```bash
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest tests/routes/test_admin_practice_delete.py tests/slack/test_delete_recovery.py tests/slack/test_refresh.py tests/slack/test_refresh_delete_exclusion.py tests/slack/test_combined_announcements.py tests/slack/test_details_reply_wiring.py tests/slack/test_cross_week_summary_refresh.py -q
```

Expected: all pass with no external Slack access.

- [ ] **Step 2: Run source hygiene checks**

```bash
git diff --check
rg -n "recover_failed_practice_delete|refresh_registered_practice_summaries|channel_id_override" app tests
```

Expected: one route recovery call per failure path, summary recovery passes
`exclude_practice_id=None`, and exact-channel repost bypasses name lookup.

- [ ] **Step 3: Request focused code review**

Ask the reviewer to confirm there is no retry loop/outbox, no summary recovery
with delete exclusion, no channel-name lookup during compensation, no split
shared root, no success response for an incomplete surviving row, and no
regression in ordinary successful or unposted deletion.

- [ ] **Step 4: Commit confirmed review corrections**

If a confirmed review finding requires changes, write its failing regression,
fix it, rerun Task 3 Step 1, then stage the exact changed files and commit:

```bash
git add app/slack/practices/announcements.py app/slack/practices/delete_recovery.py app/slack/practices/__init__.py app/routes/admin_practices.py tests/slack/test_details_reply_wiring.py tests/slack/test_delete_recovery.py tests/routes/test_admin_practice_delete.py
git commit -m "fix(slack): harden practice delete recovery"
```

Do not create an empty commit when review is clean.
