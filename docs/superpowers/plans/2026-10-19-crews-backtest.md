# Crews backtest dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A read-only "Crews" dashboard on `/admin/analytics` that backtests a crew draft against this season's practice RSVPs and shows what pairing crews would do.

**Architecture:** Pure pairing math in its own module. Two small, generic additions to the dashboard framework (extra GET params, a picker block, a heatmap chart). One dashboard module that loads a `CrewDraft`, this season's sessions and attendance, and builds blocks.

**Tech Stack:** Flask, SQLAlchemy, Postgres, Jinja, vendored Vega-Lite 6, pytest.

**Spec:** `docs/superpowers/specs/2026-10-19-crews-backtest-design.md`

## Global Constraints

- Read-only. No migrations, no new tables, no writes to `crew_drafts`, `crew_configs` or anything else.
- The bar is 4: a crew "works" at a practice when 4 or more members are there. One constant, `MIN_GROUP = 4`.
- Non-checker flag: more than 5 non-checkers. One constant, `NON_CHECKER_LIMIT = 5`.
- Counted roles: `rsvp`, `lead`, `coach`, once per (session_id, user_id). Not `plan`, not `decline`.
- Sessions: `kind='practice'`, `status='held'`, `reported_count IS NULL`, `date <= utils.today_central()`, `season_label == draft.season.name`, no `missing_date` flag. Two sessions on one day count separately.
- Pairing only: `k` from `ceil(n/2)` to `n`. Never three crews in one group.
- Crew numbers match the crew tool (1-based `member["crew"]`).
- Reuse `app/crews/engine.py` and `app/crews/service.py` helpers. Do not change them.
- Fixtures are synthetic. The repo is public.
- Copy: plain words, sentence case, no em dashes.
- Tests: `DATABASE_URL=postgresql://tcsc:tcsc@localhost:5432/tcsc_trips_test FLASK_SECRET_KEY=test-secret-key /workspace/tcsc-trips/.venv-linux/bin/python -m pytest <paths>`. The relay on localhost:5432 must be up (`ss -tln | grep 5432`).

## Review Focus

1. No current season, or a current season with no drafts: the page renders with a note, never a 500. (Task 3 test)
2. A season with zero practices so far: every share is 0, no ZeroDivisionError. (Task 3 test)
3. `crews` or `draft` params that are non-numeric, out of range, or name a draft from another season: fall back to defaults. (Task 3 test)
4. An odd crew count (11 crews): range is 6..11 and one crew stays unpaired at k=6. (Task 1 test)
5. A member with `user_id` that never appears in attendance is a non-checker, and a draft member missing `user_id` entirely is skipped without crashing. (Task 3 test)

---

### Task 1: Pairing math

**Files:**
- Create: `app/analytics/crew_pairing.py`
- Test: `tests/analytics/test_crew_pairing.py`

**Interfaces:**
- Produces:
  - `MIN_GROUP = 4`
  - `pairings(crews: list[int], k: int) -> Iterator[tuple[tuple[int, ...], ...]]`: every way to join `len(crews) - k` disjoint pairs, singles kept. Each group is a sorted tuple, groups ordered by their first crew. Deterministic order.
  - `@dataclass Pick: groups: tuple[tuple[int, ...], ...]; share: float; broken: int`
  - `best_pairing(turnout: dict[int, list[int]], k: int, apart: set[frozenset[int]], balance: Callable[[tuple[tuple[int, ...], ...]], float] | None = None, tie_cap: int = 2000) -> Pick`
  - `share_by_count(turnout: dict[int, list[int]], apart: set[frozenset[int]]) -> list[dict]`: rows `{"crews": k, "share": float}` for k from `ceil(n/2)` to `n`, best by (broken, share), no balance.

`turnout` maps crew number to its headcount at each session, all lists the same length. `apart` holds crew pairs that an `apart` rule forbids joining (rules already broken inside one crew are excluded by the caller).

- [ ] **Step 1: Write the failing tests**

```python
def test_pairings_counts():
    assert len(list(pairings([1, 2, 3, 4], 2))) == 3
    assert list(pairings([1, 2, 3], 3)) == [((1,), (2,), (3,))]
    assert len(list(pairings(list(range(1, 13)), 7))) == 62370
    assert len(list(pairings(list(range(1, 13)), 6))) == 10395

def test_odd_count_keeps_one_single():
    groups = next(pairings(list(range(1, 12)), 6))
    assert sorted(len(g) for g in groups) == [1, 2, 2, 2, 2, 2]

def test_best_pairing_joins_strong_with_weak():
    turnout = {1: [4, 4], 2: [3, 3], 3: [1, 1], 4: [0, 0]}
    pick = best_pairing(turnout, 2, set())
    # {1,4} and {2,3}: both groups reach 4 at both sessions.
    assert pick.groups == ((1, 4), (2, 3)) and pick.share == 1.0 and pick.broken == 0

def test_apart_beats_share():
    turnout = {1: [4, 4], 2: [3, 3], 3: [1, 1], 4: [0, 0]}
    pick = best_pairing(turnout, 2, {frozenset({2, 3})})
    assert frozenset({2, 3}) not in {frozenset(g) for g in pick.groups} and pick.broken == 0

def test_balance_breaks_ties_then_order():
    turnout = {c: [0] for c in (1, 2, 3, 4)}   # every pairing ties on share
    prefer = {((1, 3), (2, 4)): 0.0}
    pick = best_pairing(turnout, 2, set(), balance=lambda g: prefer.get(g, 1.0))
    assert pick.groups == ((1, 3), (2, 4))
    assert best_pairing(turnout, 2, set()).groups == ((1, 2), (3, 4))   # first in order

def test_share_by_count_range_and_no_sessions():
    turnout = {c: [] for c in range(1, 12)}
    rows = share_by_count(turnout, set())
    assert [r["crews"] for r in rows] == list(range(6, 12)) and all(r["share"] == 0 for r in rows)

def test_twelve_crews_is_fast():
    turnout = {c: [c % 5, (c * 3) % 6] * 6 for c in range(1, 13)}
    start = time.perf_counter(); share_by_count(turnout, set())
    assert time.perf_counter() - start < 3.0
```

- [ ] **Step 2: Run to verify they fail**

Run: `... -m pytest tests/analytics/test_crew_pairing.py -q`
Expected: FAIL, `ModuleNotFoundError: app.analytics.crew_pairing`.

- [ ] **Step 3: Implement**

Approach, because the signatures leave it open: precompute `hits[group]` = number of sessions where the group's summed turnout is at least `MIN_GROUP`, for every single crew and every crew pair. A pairing's share is `sum(hits[g]) / (k * sessions)`, or 0 when there are no sessions. `broken` = number of groups that are a pair in `apart`. Rank by `(broken, -share)`. Call `balance` only on the tied-best pairings, first `tie_cap` of them in `pairings` order. Lower balance wins, then enumeration order.

- [ ] **Step 4: Run to verify they pass**

Expected: 7 passed.

- [ ] **Step 5: Commit** `feat(analytics): crew pairing math for the crews backtest`

---

### Task 2: Dashboard framework hooks

**Files:**
- Modify: `app/analytics/dashboards/base.py` (`Dashboard`, `Filters`, `parse_filters`; new `Select`, `Picker`)
- Modify: `app/analytics/charts.py` (new `heatmap`)
- Modify: `app/templates/admin/analytics/dashboard.html` (render `picker` blocks)
- Test: `tests/analytics/test_dashboard_base.py`, `tests/analytics/test_charts.py`, `tests/analytics/test_admin_analytics_routes.py`

**Interfaces:**
- Produces:
  - `Dashboard.params: tuple[str, ...] = ()`. Names of extra GET params the dashboard reads itself.
  - `Filters.params: dict[str, str]`, default empty. `parse_filters` copies `args.get(name)` for each name in `dashboard.params` when present. Raw strings. The dashboard validates.
  - `@dataclass Select: name: str; label: str; options: list[tuple[str, str]]; selected: str`
  - `@dataclass Picker: kind = "picker"; selects: list[Select]`
  - `charts.heatmap(rows, *, x, y, value, threshold, x_title, y_title, tooltip, x_sort=None, y_sort=None) -> dict`: rect + text layers. Cell fill is one color when `value >= threshold` and a muted one below. Text shows the value.

- [ ] **Step 1: Write the failing tests**

```python
# test_dashboard_base.py
def test_params_are_copied_raw_only_when_declared():
    d = Dashboard(slug="x", title="X", question="?", filters=[], build=lambda f: [], params=("draft",))
    f = parse_filters(MultiDict({"draft": "13", "crews": "6"}), d, domains={...empty domains...})
    assert f.params == {"draft": "13"}

# test_charts.py
def test_heatmap_validates_and_renders():
    rows = [{"crew": "1", "date": "2099-01-0%d" % i, "people": i} for i in range(1, 6)]
    spec = charts.spec("Crew turnout", charts.heatmap(rows, x="date", y="crew", value="people",
                       threshold=4, x_title="Practice", y_title="Crew", tooltip=["crew", "date", "people"]))
    _validate_and_render(spec)   # existing helper in this file: schema + vl_convert png

# test_admin_analytics_routes.py
def test_picker_block_renders_get_form_with_selected(admin_client):
    picker = Picker([Select("draft", "Draft", [("12", "Draft 12"), ("13", "Draft 13")], "13"),
                     Select("crews", "Crews", [("6", "6"), ("12", "12")], "12")])
    with patch.object(STUB, "filters", []), patch.object(STUB, "build", lambda f: [picker]):
        html = admin_client.get("/admin/analytics/stub").get_data(as_text=True)
    assert '<select name="draft"' in html and '<option value="13" selected>' in html
    assert '<option value="12" selected>Draft 12' not in html and ">Apply<" in html
```

Use whatever helper names `test_charts.py` and `test_dashboard_base.py` already use for validation and empty domains.

- [ ] **Step 2: Run to verify they fail.** Expected: `TypeError` on `params`, `AttributeError` on `heatmap`, `ImportError` on `Picker`.

- [ ] **Step 3: Implement.** The picker form is a GET form to the same dashboard URL with one labelled `<select>` per `Select` and an Apply button, styled like the existing filter card. Selects need `min-height: 44px` like the other controls.

- [ ] **Step 4: Run the three test files plus the whole `tests/analytics` dir.** Expected: all pass, no existing test changes behavior.

- [ ] **Step 5: Commit** `feat(analytics): dashboard params, picker block and heatmap chart`

---

### Task 3: Crews dashboard

**Files:**
- Create: `app/analytics/dashboards/crews.py`
- Modify: `app/analytics/dashboards/__init__.py` (register after `PEOPLE`)
- Test: `tests/analytics/test_crews_dashboard.py`

**Interfaces:**
- Consumes: Task 1 (`pairings`, `best_pairing`, `share_by_count`, `MIN_GROUP`), Task 2 (`Dashboard.params`, `Filters.params`, `Picker`, `Select`, `charts.heatmap`), `base.load_attendance`, `service.to_settings`, `service.PERSON_FIELDS`, `engine.Person`, `engine.score`, `engine.crew_rows`.
- Produces: `DASHBOARD = Dashboard(slug="crews", title="Crews", question="How many of each crew would have been at practice this season?", filters=[], params=("draft", "crews"), build=build)` and `NON_CHECKER_LIMIT = 5`.

Behavior, in order:

1. **Draft.** Current season = `Season.query.filter_by(is_current=True).first()`. Candidates = that season's drafts. `params["draft"]` picks one if it parses as an int and is a candidate. Otherwise: the `final` draft, else the one with the latest `updated_at` (ties by highest id). No season or no drafts: return `[Note("No crew drafts for the current season yet.")]`.
2. **Members.** Draft members with a `user_id`. Skip any without one.
3. **Sessions and turnout.** Sessions per Global Constraints, ordered by date, start_time, id. `load_attendance(ids, role=("rsvp", "lead", "coach"))`, dedupe on (session_id, user_id). `turnout[crew]` = headcount list per session.
4. **Apart rules.** For each `apart` rule in `draft.rules`: same original crew means broken in the draft (listed in the note by member name). Different crews means add `frozenset({crew_a, crew_b})` to `apart`.
5. **k.** `n = int(draft.settings["crews"])`. `params["crews"]` if int in `ceil(n/2)..n`, else `n`.
6. **Pick.** `best_pairing(turnout, k, apart, balance)` where `balance(groups)` maps each member to their group index and returns `engine.score(people, assignment, Settings(crews=k, levels=..., board_rule=...))` from `service.to_settings(draft.settings, [])`. At `k == n` the pick is the draft unchanged.
7. **Labels.** A group's label joins its crews with " + ", using `draft.crew_names[str(c)]` when set, else the number.

Blocks, in order:

- `Picker([Select("draft", "Draft", [(id, f"{label} (updated {Mon D})")...], ...), Select("crews", "Crews", [(k, k) for k in range(ceil(n/2), n+1)], ...)])`
- `Tiles`: "Crews" (k), "People per crew" (e.g. "12" or "12 to 13"), "Practices" (session count), "Average per crew" (one decimal), "Crew-practices with 4+" (percent), "Crews over 5 non-checkers" (count).
- `Chart` "Crew count": `share_by_count` rows as a line or bars of percent vs crews, one series. Description says each count uses its best pairing on these practices.
- `Chart` "Crew by practice": `charts.heatmap`, y = group label sorted by first crew number, x = session date label (add " (2)" for a second session the same day), value = headcount, threshold `MIN_GROUP`.
- `Table` "Crews": label, size, non-checkers, over_limit ("Yes" when > 5), average, share_4plus (percent), zero_practices, plus `engine.crew_rows` columns flattened: board, speedy, gender (e.g. "F 6 · M 6"), age range, tenure mix.
- `Note`: "RSVPs, not headcounts. {draft label}, {season name}, {N} practices from {first} to {last}. Pairings are the best fit for these practices. Fall turnout may not predict winter." Plus a line for each already-broken apart rule.

- [ ] **Step 1: Write the failing tests** (synthetic rows in the scratch DB, rolled back by `db_session`; build a helper that creates a `Season(is_current=True, name="2099 Fall/Winter", ...)`, N `User`s, a `CrewDraft` with `members` snapshots and `settings={"crews": n, "size": ..., "levels": {}, "board_rule": True}`, `PracticeSession`s and `PracticeAttendance` rows)

```python
def test_default_draft_is_final_else_latest(db_session): ...
def test_turnout_counts_rsvp_lead_coach_once_and_skips_plan_decline(db_session): ...
def test_cancelled_count_only_future_and_other_season_sessions_ignored(db_session): ...
def test_non_checkers_and_over_limit_flag(db_session):
    # crew 1: 6 members never attended -> non_checkers 6, over_limit "Yes"
def test_pairing_param_merges_and_labels_with_names(db_session):
    # crew_names {"1": "Wolves", "4": "Otters"}; crews=2 of 4 -> a row labelled "Wolves + Otters"
def test_bad_params_fall_back(db_session):
    # draft="abc", draft=<other season's id>, crews="99", crews="1" -> defaults
def test_no_current_season_or_no_drafts_returns_note(db_session): ...
def test_zero_practices_renders_zero_shares(db_session): ...
def test_member_without_user_id_is_skipped(db_session): ...
def test_apart_rule_inside_one_crew_is_listed_in_note(db_session): ...
def test_render_does_not_write(db_session):
    before = [(d.id, json.dumps(d.members, sort_keys=True), json.dumps(d.settings, sort_keys=True), d.updated_at)
              for d in CrewDraft.query.all()]
    build(Filters(params={"draft": str(draft.id), "crews": "2"}))
    assert not db_session.dirty and not db_session.new and not db_session.deleted
    assert before == [...same tuple recomputed...]
def test_crews_route_renders(admin_client, db_session): ...   # GET /admin/analytics/crews -> 200, "Crew by practice" in html
```

- [ ] **Step 2: Run to verify they fail.** Expected: `ModuleNotFoundError: app.analytics.dashboards.crews`.
- [ ] **Step 3: Implement** `build(filters: Filters) -> list` in `crews.py` and register it.
- [ ] **Step 4: Run** `tests/analytics tests/crews`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(analytics): crews backtest dashboard`

---

### Task 4: Check against production data, then PR

- [ ] **Step 1:** Serve the worktree locally against prod, read-only (`PGOPTIONS='-c default_transaction_read_only=on'`, `DATABASE_URL=$PROD_DATABASE_URL`, `TCSC_MIGRATION_ONLY=1`, `SLACK_APP_TOKEN` unset) in a herdr pane on a port in the project's block. Open `/admin/analytics/crews` with Draft 13.
- [ ] **Step 2:** Numbers must match the read-only SQL already run for Draft 13: 11 practices; crew 1 average 1.7 with 0 practices at 4+; crew 4 average 4.5 with 8; max non-checkers 5 (crews 3, 6, 9); overall 4+ share 27%. Check `crews=10` and `crews=6` render and render time stays under 3 s.
- [ ] **Step 3:** Screenshot at 390px and desktop width. Check there's no horizontal page scroll except inside table/heatmap wraps.
- [ ] **Step 4:** Full suite green (`run-tests.sh` equivalent against `tcsc_trips_test`), push branch, open PR with the Draft 13 findings in the description. Do not merge without Rob.
