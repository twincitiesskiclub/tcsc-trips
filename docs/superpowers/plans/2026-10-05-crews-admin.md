# Crews admin: implementation plan

Spec: `docs/superpowers/specs/2026-10-05-crews-admin.md`. Branch `crews-admin`.
Tests run against the scratch DB:
`DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test pytest tests/crews`.

1. **Engine** (`app/crews/engine.py`), pure Python, no DB.
   - Person, Settings and Rule dataclasses, plus `generate(people, settings, seed)`
     (deal plus balance), `score`, `crew_stats` (balance table rows) and `spread`
     (per-trait max distance from even).
   - Tests: determinism per seed, the board rule, band dealing, an uneven last band,
     each rule type, an off weight dropping a trait, and impossible rules reported
     as broken.
   - Check: on the 10/5 roster, the default settings give the scratchpad result.
     This is a manual check against the scratchpad CSV, because real data stays
     out of the public repo.
2. **Models and migration**: `CrewConfig` and `CrewDraft` in `app/crews/models.py`,
   registered in `app/__init__.py`. Migration `d4e8f2a6b1c9`. Bump `HEAD_REVISION`.
3. **Roster** (`app/crews/roster.py`): build Person rows for a season from the
   DB (tenure, age, ski, pronouns, BOARD_MEMBER tag, speedy ids, overrides).
   Tests use scratch-DB fixtures that roll back.
4. **Slack seam** (`app/crews/slack.py`): `channel_member_user_ids(channel)`, with
   the bot client mocked in tests.
5. **Routes** (`app/routes/admin_crews.py`). These cover:
   - The season page.
   - Saving settings, overrides and rules.
   - CSV upload of overrides.
   - Refreshing the speedy group.
   - Making drafts and importing a draft CSV.
   - The draft page with move and swap (returns an HTML fragment), renaming
     crews, marking final, deleting, and CSV export.
   Each route is tested for access, the happy path and bad input.
6. **Templates and JS**: `admin/crews/season.html`, `admin/crews/draft.html`, the
   `_draft_body.html` partial and `static/admin_crews.js`. Add a sidebar link.
7. **Verification**: run the suite, `/simplify`, then take screenshots at 375px
   and 1280px against the scratch DB with seeded fake members. Then open the PR.
