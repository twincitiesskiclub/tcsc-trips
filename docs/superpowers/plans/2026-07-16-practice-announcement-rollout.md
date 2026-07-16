# Practice Announcement Rollout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify, merge, deploy, preview, and safely seed the completed practice-announcement release without duplicate Slack consumers or ambiguous production writes.

**Architecture:** Execute the three code plans first, then use one final branch review and deterministic test gate before a GitHub PR merge triggers Render. Observe migration completion read-only through the production database, test Preview through Render as the sole Socket Mode consumer, and keep the historical seed behind its exact digest approval gate.

**Tech Stack:** Git/GitHub CLI, Render auto-deploy, Flask/Alembic, PostgreSQL/SQLAlchemy, Slack Socket Mode, pytest, Node test runner, Tailwind CLI.

## Global Constraints

- Execute `2026-07-16-practice-summary-identity.md`, then `2026-07-16-practice-delete-recovery.md`, then `2026-07-16-practice-seed-commit-reporting.md` before this plan.
- Never post to `#announcements-practices`; Preview testing is user-invoked only in `C07G9RTMRT3`.
- Keep the local companion stopped. Render must be the sole consumer of the production Slack app's Socket Mode connection.
- Keep practice creation and editing quiet from the start of Render migration until the new service and schema are verified.
- Do not mutate production during schema checks or the seed dry run.
- Production seeding requires a freshly generated exact production digest and a new explicit user approval immediately before commit.
- If seed commit verification is unknown, assume writes committed and run read-back; never repeat the commit blindly.
- Preserve the untracked `env` symlink and do not clean unrelated user files.

---

## File Map

- No planned source changes. This plan operates on the completed branch and production deployment.
- Read `docs/superpowers/specs/2026-07-16-practice-deployment-safety-design.md` for the approved gates.
- Read `docs/superpowers/notes/2026-07-16-slack-test-app-follow-up.md` for the future dedicated test-app follow-up.

### Task 1: Run the Final Local Verification and Review Gate

**Files:**

- No planned file changes; failures return to the owning code plan with a new regression test.

**Interfaces:**

- Consumes the completed code from all three implementation plans.
- Produces a reviewed branch with one Alembic head and no uncommitted generated output.

- [ ] **Step 1: Confirm local Slack consumers are stopped**

```bash
pgrep -af "gunicorn|flask run|socket_mode|practice-preview" || true
```

Expected: no local TCSC companion/web process using production Slack tokens. If
an unrelated process matches, inspect it; do not kill unrelated user work.

- [ ] **Step 2: Run the focused feature suites serially**

```bash
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest tests/practices/test_practice_summary_posts.py tests/practices/test_practice_summary_post_migration.py tests/slack/test_practice_summary_registry.py tests/agent/test_weekly_summary.py tests/slack/test_coach_summary_posting.py tests/slack/test_refresh.py tests/slack/test_refresh_delete_exclusion.py tests/slack/test_cross_week_summary_refresh.py tests/routes/test_admin_practices_routes.py tests/slack/test_practice_create_modal.py tests/slack/test_practice_edit_full.py tests/slack/test_practice_quick_edit.py tests/routes/test_admin_practice_delete.py tests/slack/test_delete_recovery.py tests/slack/test_combined_announcements.py tests/slack/test_details_reply_wiring.py tests/scripts/test_seed_practice_plan_reaction_defaults.py -q
```

Expected: all pass with no external Slack calls.

- [ ] **Step 3: Run the complete Python and Node suites**

```bash
npm run test:practice-reactions
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest -q
```

Expected: all Node and Python tests pass.

- [ ] **Step 4: Verify generated CSS and repository hygiene**

```bash
npm run tailwind:build
git diff --exit-code -- app/static/css/tailwind-output.css
git diff --check
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips env/bin/flask db heads
git status --short
```

Expected: Tailwind is deterministic, diff checks are clean, the sole migration
head is `d8b2c6f4a901`, and status contains only the pre-existing `?? env`.

- [ ] **Step 5: Request final whole-branch review**

Review from merge-base through HEAD for Critical/Important correctness,
spec/plan compliance, migration safety, Slack side effects, summary identity,
delete compensation, seed transaction reporting, and test quality. Any
confirmed blocker returns to TDD in its owning plan. Do not merge with an open
Critical or Important finding.

### Task 2: Push, Merge, and Observe the Render Deployment

**Files:**

- No source changes; this task changes GitHub/Render deployment state.

**Interfaces:**

- Consumes a clean reviewed branch.
- Produces merged `main` and production schema revision `d8b2c6f4a901`.

- [ ] **Step 1: Start the practice-writer quiet window**

Tell the user that practice Create/Edit in Admin and Slack must remain unused
until the deployed Preview verification in Task 3 Step 3 completes. Do not add a
maintenance-mode feature for this short cutover.

- [ ] **Step 2: Push the feature branch and open the PR**

```bash
git push -u origin feat/practice-announcement-finalization
gh pr create --base main --head feat/practice-announcement-finalization --title "Finalize practice announcements and structured reactions" --body-file docs/superpowers/specs/2026-07-16-practice-deployment-safety-design.md
```

Expected: the branch is on origin and the PR targets `main`.

- [ ] **Step 3: Wait for GitHub checks**

```bash
gh pr checks
```

Expected: every required check passes. If checks are pending, poll with the
product wait mechanism in intervals no longer than 60 seconds while keeping the
user updated. Fix failures test-first and repeat Tasks 1–2 rather than bypassing
checks.

- [ ] **Step 4: Merge without deleting the working branch**

```bash
gh pr merge --merge
```

Expected: the PR is merged; Render auto-deploy begins from the new `main`.

- [ ] **Step 5: Check the production Alembic revision read-only**

Use the repository virtual environment without printing the connection URL:

```bash
env/bin/python - <<'PY'
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv('.env')
engine = create_engine(os.environ['PROD_DATABASE_URL'])
expected = 'd8b2c6f4a901'
with engine.connect() as connection:
    current = connection.execute(
        text('SELECT version_num FROM alembic_version')
    ).scalar_one()
print(f'production_revision={current}')
if current != expected:
    raise SystemExit('production migration has not reached expected revision')
engine.dispose()
PY
```

Expected: revision is `d8b2c6f4a901`. If it is still the previous revision,
use the product wait mechanism and rerun this one-shot query at intervals no
longer than 60 seconds; do not run a ten-minute blocking shell loop.

- [ ] **Step 6: Verify schema objects while keeping writers quiet**

```bash
env/bin/python - <<'PY'
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text

load_dotenv('.env')
engine = create_engine(os.environ['PROD_DATABASE_URL'])
with engine.connect() as connection:
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    assert 'practice_summary_posts' in tables
    practice_columns = {
        item['name'] for item in inspector.get_columns('practices')
    }
    assert {'plan_reactions', 'slack_session_emoji'} <= practice_columns
    type_columns = {
        item['name'] for item in inspector.get_columns('practice_types')
    }
    activity_columns = {
        item['name'] for item in inspector.get_columns('practice_activities')
    }
    assert 'default_plan_reactions' in type_columns
    assert 'default_plan_reactions' in activity_columns
    conflicts = connection.execute(text('''
        SELECT week_start, surface, count(*)
        FROM practice_summary_posts
        GROUP BY week_start, surface
        HAVING count(*) > 1
    ''')).all()
    assert conflicts == []
print('production_schema_verified')
engine.dispose()
PY
```

Expected: `production_schema_verified`. Tell the user the schema is ready but
keep the practice-writer quiet window active until the deployed Preview smoke
test succeeds.

### Task 3: Test Preview Through Render as the Sole Socket Consumer

**Files:**

- No source changes; this is a user-driven Slack smoke test.

**Interfaces:**

- Consumes the deployed Render Socket Mode service.
- Produces visual confirmation that the deployed modal opens and discards without mutation.

- [ ] **Step 1: Confirm the local companion remains stopped**

```bash
pgrep -af "gunicorn|flask run|socket_mode|practice-preview" || true
```

Expected: no local TCSC Slack consumer.

- [ ] **Step 2: Ask the user to invoke Preview in the test channel**

Ask the user to run `/tcsc practice-preview` in `C07G9RTMRT3`. The agent does
not invoke the command and does not post any message.

- [ ] **Step 3: Confirm deployed behavior**

The user confirms the structured fixed-emoji editor opens, defaults render,
collapsed editing expands in place, Preview matches the approved copy, and
discard closes without creating or editing a practice/message. If it fails,
diagnose Render logs and deployed revision before starting any local Socket
Mode process. After success, tell the user practice Create/Edit may resume and
close the writer quiet window.

### Task 4: Generate the Production Seed Plan and Stop for Approval

**Files:**

- No source changes; dry run is read-only.

**Interfaces:**

- Produces the exact canonical production diff and approval digest.
- Does not authorize or perform a write.

- [ ] **Step 1: Run a fresh production dry run**

```bash
env/bin/python scripts/seed_practice_plan_reaction_defaults.py --environment production --dry-run
```

Expected: canonical JSON followed by one `Approval digest: ...` line, with no
conflicts. Capture the complete output exactly.

- [ ] **Step 2: Present the exact diff and digest**

Show the user every target/status/current/desired value and the exact digest.
State explicitly that no production values changed during the dry run.

- [ ] **Step 3: Stop for fresh explicit approval**

Do not run `--commit`. Ask the user to approve that exact digest. Any time gap,
conflict, or database drift requires a new dry run and new approval.

### Task 5: Commit Only the Approved Seed and Read Back

**Files:**

- No source changes; this task mutates only the approved production defaults.

**Interfaces:**

- Consumes the exact digest explicitly approved in Task 4.
- Produces verified default rows and an idempotent read-back plan.

- [ ] **Step 1: Run the digest-bound commit**

After the user explicitly approves the exact digest, run:

```bash
env/bin/python scripts/seed_practice_plan_reaction_defaults.py --environment production --commit --approve "$APPROVED_DIGEST"
```

Set `APPROVED_DIGEST` to the exact user-approved value in the shell environment
for this command. Expected: every target reports `exact` and the command ends
with `Verified N targets.`

- [ ] **Step 2: Handle an unverified commit safely**

If the command prints `COMMIT SUCCEEDED; VERIFICATION FAILED OR UNKNOWN`, do
not repeat it. Proceed directly to Step 3 and treat the approved writes as
potentially durable.

- [ ] **Step 3: Run independent production read-back**

```bash
env/bin/python scripts/seed_practice_plan_reaction_defaults.py --environment production --dry-run
```

Expected: every target is `exact`, with no `fill`, `conflict`, or target drift.
Any existing upcoming snapshot mismatches remain report-only and unchanged.

- [ ] **Step 4: Final handoff**

Report the merged PR, deployed migration revision, Preview result, seed commit
result, independent read-back, and the still-open dedicated TCSC Slack test-app
follow-up. Do not claim completion without fresh command evidence from every
gate above.
