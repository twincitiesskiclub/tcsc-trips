# Practice Seed Commit Reporting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure the reaction-default seed never reports an abort after its approved database transaction has already committed.

**Architecture:** Preserve the current digest, lock, write transaction, and success result. Raise one separate non-`SeedPlanError` exception only from independent post-commit read-back, and give it an explicit CLI branch that reports committed-but-unverified with a nonzero exit.

**Tech Stack:** Python 3.13, standalone SQLAlchemy, argparse, pytest, PostgreSQL/SQLite test fixtures.

## Global Constraints

- Do not change seed targets, manifest validation, digest contents, locking, transaction boundaries, or successful output.
- `SeedPlanError` remains exclusively pre-commit/no-successful-commit reporting.
- A post-commit mismatch or read-back exception exits `1`, prints `COMMIT SUCCEEDED; VERIFICATION FAILED OR UNKNOWN`, and never prints `Seed aborted`.
- Keep `SeedCommitResult(verified=True, plan=...)` success-only; do not return an easy-to-ignore unverified result.
- Do not access the production database during implementation.
- The later production operation remains dry run → exact diff/digest → fresh approval → commit → independent dry run/read-back.
- Use TDD and preserve the untracked `env` symlink.

---

## File Map

- Modify `scripts/seed_practice_plan_reaction_defaults.py`: add the post-commit exception, wrap only independent read-back, and add exact CLI reporting.
- Modify `tests/scripts/test_seed_practice_plan_reaction_defaults.py`: prove durable writes for failed/unknown verification and preserve pre-commit abort semantics.

### Task 1: Distinguish Committed-but-Unverified from Aborted

**Files:**

- Modify: `scripts/seed_practice_plan_reaction_defaults.py`
- Modify: `tests/scripts/test_seed_practice_plan_reaction_defaults.py`

**Interfaces:**

- Produces `SeedPostCommitVerificationError(RuntimeError)`; it must not inherit from `SeedPlanError`.
- Keeps `commit_seed_plan(...) -> SeedCommitResult` unchanged for verified success.
- Raises `SeedPostCommitVerificationError` only after the write transaction context has exited successfully.

- [ ] **Step 1: Add failing durable-write verification tests**

Add `replace` to the existing dataclass imports and add:

```python
@pytest.mark.parametrize(
    ("readback_outcome", "expected_message"),
    [
        ("mismatch", "did not match the approved defaults"),
        ("error", "could not complete"),
    ],
)
def test_post_commit_verification_failure_is_distinct_after_writes_are_durable(
    seed_engine,
    complete_targets,
    monkeypatch,
    readback_outcome,
    expected_message,
):
    manifest = seed.load_manifest(MANIFEST_PATH)
    with Session(seed_engine) as session:
        plan = seed.build_seed_plan(session, manifest, lock=False)
    digest = seed.render_seed_plan(plan, environment="test").digest

    real_build_seed_plan = seed.build_seed_plan
    call_count = 0

    def controlled_build(session, loaded_manifest, *, lock=False):
        nonlocal call_count
        call_count += 1
        if call_count == 2 and readback_outcome == "error":
            raise RuntimeError("simulated read-back outage")
        built = real_build_seed_plan(
            session,
            loaded_manifest,
            lock=lock,
        )
        if call_count == 2:
            return replace(
                built,
                changes=(
                    replace(built.changes[0], status="fill"),
                    *built.changes[1:],
                ),
            )
        return built

    monkeypatch.setattr(seed, "build_seed_plan", controlled_build)

    with pytest.raises(
        seed.SeedPostCommitVerificationError,
        match=expected_message,
    ) as raised:
        seed.commit_seed_plan(
            seed_engine,
            manifest,
            approved_digest=digest,
            environment="test",
        )

    assert call_count == 2
    if readback_outcome == "error":
        assert isinstance(raised.value.__cause__, RuntimeError)

    with Session(seed_engine) as session:
        durable = real_build_seed_plan(session, manifest, lock=False)
    assert all(change.status == "exact" for change in durable.changes)
```

- [ ] **Step 2: Add failing exact CLI-reporting tests**

```python
def test_cli_reports_post_commit_verification_without_claiming_abort(
    seed_engine,
    complete_targets,
    monkeypatch,
    capsys,
):
    monkeypatch.setenv("DATABASE_URL", str(seed_engine.url))

    def committed_but_unverified(*_args, **_kwargs):
        raise seed.SeedPostCommitVerificationError(
            "simulated read-back outage"
        )

    monkeypatch.setattr(
        seed,
        "commit_seed_plan",
        committed_but_unverified,
    )
    exit_code = seed.main([
        "--environment", "local",
        "--commit", "--approve", "approved-digest",
    ])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert captured.err.splitlines() == [
        "COMMIT SUCCEEDED; VERIFICATION FAILED OR UNKNOWN",
        "Verification error: simulated read-back outage",
        (
            "Run a new dry run/read-back with "
            "--environment local --dry-run before taking further action."
        ),
    ]
    assert "Seed aborted" not in captured.err


def test_cli_pre_commit_digest_failure_still_aborts_without_writes(
    seed_engine,
    complete_targets,
    monkeypatch,
    capsys,
):
    before = _reference_values(seed_engine)
    monkeypatch.setenv("DATABASE_URL", str(seed_engine.url))

    exit_code = seed.main([
        "--environment", "local",
        "--commit", "--approve", "wrong-digest",
    ])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert captured.err.startswith("Seed aborted: ")
    assert "approval digest" in captured.err
    assert "COMMIT SUCCEEDED" not in captured.err
    assert _reference_values(seed_engine) == before
```

- [ ] **Step 3: Run the new tests and verify RED**

```bash
env/bin/pytest tests/scripts/test_seed_practice_plan_reaction_defaults.py -k "post_commit_verification or cli_reports_post_commit or cli_pre_commit" -q
```

Expected: post-commit cases fail because the distinct exception and CLI branch
do not exist; the pre-commit characterization passes.

- [ ] **Step 4: Add the separate post-commit exception**

Immediately after `SeedPlanError`, add:

```python
class SeedPostCommitVerificationError(RuntimeError):
    """Raised after seed writes commit when read-back is not verified."""
```

Do not subclass `SeedPlanError`; otherwise the generic abort handler can
misreport a durable commit.

- [ ] **Step 5: Wrap only the independent read-back**

Replace the code after the write transaction block with:

```python
    try:
        with Session(engine) as verification:
            verified_plan = build_seed_plan(
                verification,
                manifest,
                lock=False,
            )
    except Exception as exc:
        raise SeedPostCommitVerificationError(
            f"Independent read-back could not complete: {exc}"
        ) from exc

    if any(item.status != "exact" for item in verified_plan.changes):
        raise SeedPostCommitVerificationError(
            "Committed values did not match the approved defaults "
            "during independent read-back"
        )
    return SeedCommitResult(verified=True, plan=verified_plan)
```

The `try` begins only after `with Session(engine) as session, session.begin()`
has exited. Never wrap the write transaction in this exception.

- [ ] **Step 6: Add the exact CLI branch before `SeedPlanError`**

```python
    except SeedPostCommitVerificationError as exc:
        print(
            "COMMIT SUCCEEDED; VERIFICATION FAILED OR UNKNOWN",
            file=sys.stderr,
        )
        print(f"Verification error: {exc}", file=sys.stderr)
        print(
            "Run a new dry run/read-back with "
            f"--environment {args.environment} --dry-run "
            "before taking further action.",
            file=sys.stderr,
        )
        return 1
    except SeedPlanError as exc:
        print(f"Seed aborted: {exc}", file=sys.stderr)
        return 1
```

- [ ] **Step 7: Run the focused suite and commit**

```bash
env/bin/pytest tests/scripts/test_seed_practice_plan_reaction_defaults.py -q
git add scripts/seed_practice_plan_reaction_defaults.py tests/scripts/test_seed_practice_plan_reaction_defaults.py
git commit -m "fix(practices): report post-commit seed verification"
```

Expected: all seed tests pass (33 tests if no unrelated tests are added).

### Task 2: Verify the Seed Boundary and Preserve the Production Gate

**Files:**

- No planned file changes; this task verifies the committed Task 1.

**Interfaces:**

- No new interface; this is the review and integration gate.

- [ ] **Step 1: Inspect the transaction boundary in the final diff**

```bash
git show --stat --oneline HEAD
git show --format=fuller HEAD -- scripts/seed_practice_plan_reaction_defaults.py tests/scripts/test_seed_practice_plan_reaction_defaults.py
```

Expected: `SeedPostCommitVerificationError` appears only after the write
transaction exits and its CLI handler precedes `SeedPlanError`.

- [ ] **Step 2: Run adjacent feature tests**

```bash
npm run test:practice-reactions
SLACK_BOT_TOKEN= SLACK_APP_TOKEN= SLACK_SIGNING_SECRET= env/bin/pytest tests/scripts/test_seed_practice_plan_reaction_defaults.py tests/practices/test_plan_reactions.py tests/practices/test_plan_reaction_queries.py -q
git diff --check
```

Expected: Node reaction tests and all listed Python tests pass; diff is clean.

- [ ] **Step 3: Request focused review**

Ask the reviewer to confirm that no pre-commit exception can reach the new
handler, durable writes are proven in both failed/unknown verification tests,
successful output is unchanged, and the production commit still requires a
fresh approved digest.

- [ ] **Step 4: Keep production untouched**

Do not run the production dry run or commit in this task. That operation occurs
only after application deployment, schema verification, exact diff/digest
review, and fresh user approval.
