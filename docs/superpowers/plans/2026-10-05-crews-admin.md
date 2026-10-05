# Crews admin: implementation plan

Spec: `docs/superpowers/specs/2026-10-05-crews-admin.md`. Branch `crews-admin`.
Run the tests against a scratch DB at main's head:
`DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/<scratch db> pytest tests/crews`.

1. **Engine** (`app/crews/engine.py`): pure Python, no DB.
   - Dataclasses `Person`, `Settings` and `Rule`, plus `generate`, `score`,
     `crew_rows`, `spread` and `broken_rules`.
   - The board weight follows the board rule.
   - Tests cover: determinism per seed, the board rule, bands, an uneven last
     band, each rule type, off/low/high weights, and impossible rules being
     reported.
2. **Models and migration**: `CrewConfig` and `CrewDraft`. Migration
   `d4e8f2a6b1c9`, with down_revision `7a1c5e9d3b20` (interest list, #276).
   Bump `HEAD_REVISION` and add a `seasons` stub to the release-test baseline.
3. **Roster** (`app/crews/roster.py`): one row per ACTIVE member, with tenure,
   age, ski, pronoun gender, the BOARD_MEMBER tag, the speedy list and any
   overrides.
4. **Slack** (`app/crews/slack.py`): read the #thots members and match them to
   users through slack_users.
5. **Service and routes** (`app/crews/service.py`, `app/routes/admin_crews.py`).
   Routes:
   - The season page, settings, members, clearing overrides, the speedy
     refresh, and adding and removing rules.
   - Make 5 drafts.
   - The draft page and saving it.
   - Final, delete and the CSV export.
6. **Templates**:
   - `season.html`: summary and Make 5 drafts first, then three
     `<details>` sections.
   - `draft.html`: one form and Save.
   - `admin_crews.js`: season picker, rule fields and confirm prompts.
   - A sidebar link.
7. **Verification**:
   - The full crews, analytics and top-level suites, plus the migration
     release test.
   - The read-only prod equivalence check at seed 2026.
   - Screenshots at 375px and 1280px.
   - `/simplify`, then the PR.
