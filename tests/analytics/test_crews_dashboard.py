"""Crews backtest dashboard. Synthetic people only; every test rolls back."""
import json
import time as time_
from datetime import date, datetime, time

from app.analytics.dashboards import crews as cd
from app.analytics.dashboards.base import Chart, Filters, Note, Picker, Table, Tiles
from app.analytics.models import PracticeAttendance, PracticeSession
from app.crews.models import CrewDraft
from app.models import Season, User, db

LABEL = "2099 Fall/Winter"


class World:
    def __init__(self, session):
        self.db = session
        Season.query.update({"is_current": False})
        self.season = Season(name=LABEL, season_type="fall", year=2099, start_date=date(2099, 9, 1),
                             end_date=date(2100, 3, 31), is_current=True)
        self.db.add(self.season)
        self.db.flush()
        self.users = []
        self.sessions = []

    def user(self):
        n = len(self.users) + 1
        user = User(first_name="Test", last_name=f"Skier{n}", email=f"crews-test-{n}@example.invalid")
        self.db.add(user)
        self.db.flush()
        self.users.append(user)
        return user

    def draft(self, sizes, label="Draft 1", status="draft", updated=datetime(2099, 10, 1),
              rules=(), crew_names=None, season=None):
        members = []
        for crew, size in enumerate(sizes, start=1):
            for _ in range(size):
                user = self.user()
                members.append({"user_id": user.id, "crew": crew, "name": f"{user.first_name} {user.last_name}",
                                "gender": "F" if user.id % 2 else "M", "age": 30, "tenure": 1, "ski": "3-7",
                                "thot": False, "board": False})
        draft = CrewDraft(season_id=(season or self.season).id, label=label, seed=1, status=status,
                          settings={"crews": len(sizes), "size": 12, "levels": {}, "board_rule": True},
                          rules=list(rules), members=members, crew_names=crew_names or {},
                          updated_at=updated)
        self.db.add(draft)
        self.db.flush()
        return draft

    def practice(self, day, start=time(18), label=LABEL, **values):
        values = {"kind": "practice", "status": "held", **values}
        key = f"crews-test:{len(self.sessions)}"
        s = PracticeSession(session_key=key, group_key=key, era="app", date=day, start_time=start,
                            day_of_week=day.strftime("%A"), season_label=label,
                            rebuilt_at=datetime(2099, 1, 1), **values)
        self.db.add(s)
        self.db.flush()
        self.sessions.append(s)
        return s

    def came(self, session, members, role="rsvp"):
        for m in members:
            self.db.add(PracticeAttendance(session_id=session.id, person_key=f"user:{m['user_id']}",
                                           user_id=m["user_id"], role=role, source="reaction"))
        self.db.flush()


def crew(draft, n):
    return [m for m in draft.members if m["crew"] == n]


def blocks(**params):
    return cd.build(Filters(params={k: str(v) for k, v in params.items()}))


def first(items, kind):
    return next(b for b in items if isinstance(b, kind))


def tiles(items):
    return {t.label: t.value for t in first(items, Tiles).tiles}


def named(items, title):
    return next(b for b in items if isinstance(b, Table) and b.title == title)


def table(items):
    return {r["label"]: r for r in named(items, "Turnout by crew").rows}


def test_default_draft_is_final_else_latest(db_session):
    w = World(db_session)
    old = w.draft([1], label="Old", updated=datetime(2099, 10, 1))
    new = w.draft([1], label="New", updated=datetime(2099, 10, 2))
    assert first(blocks(), Picker).selects[0].selected == str(new.id)
    old.status = "final"
    db_session.flush()
    assert first(blocks(), Picker).selects[0].selected == str(old.id)


def test_turnout_counts_rsvp_lead_coach_once_and_skips_plan_decline(db_session):
    w = World(db_session)
    draft = w.draft([6])
    s = w.practice(date(2020, 1, 7))
    w.came(s, crew(draft, 1)[:2])
    w.came(s, crew(draft, 1)[:1], role="lead")       # same person twice: counted once
    w.came(s, crew(draft, 1)[2:3], role="coach")
    w.came(s, crew(draft, 1)[3:4], role="plan")
    w.came(s, crew(draft, 1)[4:5], role="decline")
    grid = first([b for b in blocks() if isinstance(b, Chart) and b.title == "Crew by practice"], Chart)
    assert [r["people"] for r in grid.rows] == [3]


def test_cancelled_count_only_future_and_other_season_sessions_ignored(db_session):
    w = World(db_session)
    draft = w.draft([4])
    for s in (w.practice(date(2020, 1, 7)), w.practice(date(2020, 1, 8), status="cancelled"),
              w.practice(date(2020, 1, 9), reported_count=30), w.practice(date(2999, 1, 1)),
              w.practice(date(2020, 1, 10), label="2098 Fall/Winter"),
              w.practice(date(2020, 1, 11), kind="event")):
        w.came(s, crew(draft, 1))
    assert tiles(blocks())["Practices"] == 1


def test_two_sessions_same_day_count_separately(db_session):
    w = World(db_session)
    draft = w.draft([4])
    w.came(w.practice(date(2020, 1, 7), start=time(6)), crew(draft, 1))
    w.came(w.practice(date(2020, 1, 7), start=time(18)), crew(draft, 1)[:1])
    grid = next(b for b in blocks() if isinstance(b, Chart) and b.title == "Crew by practice")
    assert [(r["practice"], r["people"]) for r in grid.rows] == [("Jan 7", 4), ("Jan 7 (2)", 1)]


def test_non_checkers_and_over_limit_flag(db_session):
    w = World(db_session)
    draft = w.draft([8, 8])
    s = w.practice(date(2020, 1, 7))
    w.came(s, crew(draft, 1)[:2] + crew(draft, 2)[:4])
    rows = table(blocks())
    assert (rows["1"]["non_checkers"], rows["1"]["over_limit"]) == (6, "Yes")
    assert (rows["2"]["non_checkers"], rows["2"]["over_limit"]) == (4, "")
    t = tiles(blocks())
    assert t["Crews over 5 non-checkers"] == 1 and t["Crew-practices with 4+"] == "50%"


def test_pairing_param_merges_and_labels_with_names(db_session):
    w = World(db_session)
    draft = w.draft([3, 3, 1, 1], crew_names={"1": "Wolves", "4": "Otters"})
    s = w.practice(date(2020, 1, 7))
    w.came(s, crew(draft, 1) + crew(draft, 2) + crew(draft, 3) + crew(draft, 4))
    out = blocks(draft=draft.id, crews=2)
    rows = table(out)
    # 3+1 and 3+1 both reach 4; joining the two 3s would leave a group of 1.
    assert set(rows) == {"Wolves + 3", "2 + Otters"} or set(rows) == {"Wolves + Otters", "2 + 3"}
    assert tiles(out)["Crew-practices with 4+"] == "100%" and tiles(out)["Crews"] == 2
    count_chart = next(b for b in out if isinstance(b, Chart) and b.title == "Crew count")
    assert [r["crews"] for r in count_chart.rows] == [2, 3, 4]


def test_bad_params_fall_back(db_session):
    w = World(db_session)
    other = Season(name="2098 Fall/Winter", season_type="fall", year=2098, start_date=date(2098, 9, 1),
                   end_date=date(2099, 3, 31))
    db_session.add(other)
    db_session.flush()
    foreign = w.draft([1, 1], season=other)
    mine = w.draft([1, 1, 1, 1])
    for params in ({"draft": "abc"}, {"draft": foreign.id}, {"crews": "99"}, {"crews": "1"}, {"crews": "x"}):
        picker = first(blocks(**params), Picker)
        assert [s.selected for s in picker.selects] == [str(mine.id), "4"]
    assert [v for v, _ in first(blocks(), Picker).selects[1].options] == ["2", "3", "4"]


def test_no_current_season_or_no_drafts_returns_note(db_session):
    World(db_session)
    out = blocks()
    assert len(out) == 1 and isinstance(out[0], Note)
    Season.query.update({"is_current": False})
    out = blocks()
    assert len(out) == 1 and isinstance(out[0], Note)


def test_zero_practices_renders_zero_shares(db_session):
    w = World(db_session)
    w.draft([2, 2, 2])
    out = blocks(crews=2)
    t = tiles(out)
    assert (t["Practices"], t["Average per crew"], t["Crew-practices with 4+"]) == (0, "0.0", "0%")
    assert all(r["average"] == 0 for r in named(out, "Turnout by crew").rows)


def test_member_without_user_id_is_skipped(db_session):
    w = World(db_session)
    draft = w.draft([2])
    draft.members = draft.members + [{"crew": 1, "name": "No Account"}]
    db_session.flush()
    assert table(blocks())["1"]["size"] == 2


def test_apart_rule_inside_one_crew_is_listed_in_note(db_session):
    w = World(db_session)
    draft = w.draft([2, 1])
    a, b = crew(draft, 1)
    draft.rules = [{"kind": "apart", "a": a["user_id"], "b": b["user_id"]}]
    db_session.flush()
    notes = " ".join(n.text for n in blocks() if isinstance(n, Note))
    assert f"{a['name']} and {b['name']}" in notes


def _snapshot():
    return [(d.id, json.dumps(d.members, sort_keys=True), json.dumps(d.settings, sort_keys=True),
             json.dumps(d.rules, sort_keys=True), d.status, d.updated_at)
            for d in CrewDraft.query.order_by(CrewDraft.id)]


def test_render_does_not_write(db_session):
    w = World(db_session)
    draft = w.draft([3, 3, 3, 3])
    w.came(w.practice(date(2020, 1, 7)), crew(draft, 1))
    db_session.flush()
    before = _snapshot()
    blocks(draft=draft.id, crews=2)
    assert not db_session.dirty and not db_session.new and not db_session.deleted
    assert _snapshot() == before


def test_crews_route_renders(admin_client, db_session):
    w = World(db_session)
    draft = w.draft([4, 4])
    w.came(w.practice(date(2020, 1, 7)), crew(draft, 1))
    html = admin_client.get("/admin/analytics/crews?crews=1").get_data(as_text=True)
    assert "Crew by practice" in html and '<select name="crews"' in html


def test_large_draft_skips_pairing_and_stays_fast(db_session):
    w = World(db_session)
    draft = w.draft([1] * 16)
    w.came(w.practice(date(2020, 1, 7)), crew(draft, 1))
    start = time_.perf_counter()
    out = blocks(crews=8)
    assert time_.perf_counter() - start < 3.0
    assert [v for v, _ in first(out, Picker).selects[1].options] == ["16"]
    assert tiles(out)["Crews"] == 16
    assert any("pairing is off" in n.text for n in out if isinstance(n, Note))


def test_over_limit_column_label(db_session):
    w = World(db_session)
    w.draft([1])
    assert ("over_limit", "Over limit") in named(blocks(), "Turnout by crew").columns


def test_picker_shows_central_update_date(db_session):
    w = World(db_session)
    w.draft([1], updated=datetime(2099, 10, 2, 3, 0))   # UTC: 10 pm Oct 1 in Central
    assert first(blocks(), Picker).selects[0].options[0][1] == "Draft 1 (updated Oct 1)"


def test_table_has_ski_column(db_session):
    w = World(db_session)
    w.draft([2])
    out = named(blocks(), "Crew balance")
    assert ("ski", "Ski experience") in out.columns and out.rows[0]["ski"] == "3-7 2"


def test_turnout_table_comes_first_with_counts(db_session):
    w = World(db_session)
    draft = w.draft([4, 4])
    w.came(w.practice(date(2020, 1, 7)), crew(draft, 1))
    w.came(w.practice(date(2020, 1, 8)), crew(draft, 1)[:1])
    out = blocks()
    kinds = [type(b).__name__ for b in out]
    assert kinds.index("Tiles") + 1 == out.index(named(out, "Turnout by crew"))
    assert [key for key, _ in named(out, "Turnout by crew").columns] == [
        "label", "non_checkers", "over_limit", "average", "practices_4plus", "zero_practices"]
    rows = table(out)
    assert (rows["1"]["practices_4plus"], rows["1"]["zero_practices"], rows["1"]["average"]) == (1, 0, 2.5)
    assert (rows["2"]["practices_4plus"], rows["2"]["zero_practices"]) == (0, 2)
    balance = [key for key, _ in named(out, "Crew balance").columns]
    assert balance == ["label", "size", "board", "speedy", "gender", "ski", "age", "tenure"]
