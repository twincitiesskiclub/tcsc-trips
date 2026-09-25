"""Synthetic people only."""
import json
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import jsonschema
import pytest
import vl_convert as vlc

from app.analytics.dashboards import people as pp
from app.analytics.dashboards.base import Chart, Filters, Note, Table, Tiles
from app.analytics.models import PracticeAttendance, PracticeSession
from app.models import Season, SlackUser, User, UserSeason
from tests.analytics.conftest import FIXTURES

SCHEMA = json.loads((FIXTURES / "vega-lite-v6.schema.json").read_text())


def _s(id, day, season, kind="practice", reported=None, status="held"):
    return SimpleNamespace(id=id, date=day, season_label=season, kind=kind,
                           reported_count=reported, status=status)


def _a(session, person, role="rsvp"):
    return SimpleNamespace(session_id=session.id, person_key=person, role=role)


F24, F25 = "2098 Fall/Winter", "2099 Fall/Winter"


def test_season_key_orders_labels():
    assert sorted(["2099 Fall/Winter", "2099 Spring/Summer", "2098 Fall/Winter"], key=pp.season_key) == [
        "2098 Fall/Winter", "2099 Spring/Summer", "2099 Fall/Winter"]


def test_pairs_drop_count_only_cancelled_and_declines():
    s1, s2, s3 = _s(1, date(2099, 1, 1), F24), _s(2, date(2099, 1, 2), F24, reported=40), \
        _s(3, date(2099, 1, 3), F24, status="cancelled")
    pairs = pp.attendance_pairs([s1, s2, s3], [_a(s1, "a"), _a(s1, "b", "decline"), _a(s3, "c")])
    assert [(p, s.id) for p, s in pairs] == [("a", 1)]


def test_retention_splits_first_season_and_returning():
    old = _s(1, date(2098, 1, 1), "2097 Fall/Winter")
    a, b = _s(2, date(2099, 1, 1), F24), _s(3, date(2100, 1, 1), F25)
    pairs = [("vet", old), ("vet", a), ("new", a), ("new2", a), ("vet", b), ("new", b)]
    rows = {(r["season_label"], r["group"]): r for r in pp.retention(pairs)}
    assert rows[(F24, "Returning")]["rate"] == 1.0
    assert (rows[(F24, "First season")]["people"], rows[(F24, "First season")]["returned"]) == (2, 1)


def test_newcomer_curve_buckets():
    sessions = [_s(i, date(2099, 1, i), F24) for i in range(1, 8)]
    pairs = [("one", sessions[0])] + [("seven", s) for s in sessions]
    rows = {r["bucket"]: r["people"] for r in pp.newcomer_curve(pairs) if r["season_label"] == F24}
    assert rows["1"] == 1 and rows["6 or more"] == 1 and rows["2"] == 0


def test_overlap_combos():
    p, e, t = _s(1, date(2099, 1, 1), F24), _s(2, date(2099, 1, 2), F24, "event"), _s(3, date(2099, 1, 3), F24, "trip")
    rows = {r["combo"]: r["people"] for r in pp.overlap([("x", p), ("x", e), ("y", t), ("z", p)])}
    assert rows == {"Event + Practice": 1, "Trip": 1, "Practice": 1}


def test_lapsed_regular():
    last = [_s(i, date(2098, 11, i), F24) for i in range(1, 7)]
    now = [_s(10, date(2099, 11, 1), F25), _s(11, date(2099, 11, 25), F25)]
    pairs = [("reg", s) for s in last] + [("reg", now[0]), ("other", now[1])]
    rows = pp.lapsed_regulars(pairs, today=date(2099, 11, 30))
    assert [(r["person_key"], r["last_season_count"], r["this_season_count"]) for r in rows] == [("reg", 6, 1)]
    assert pp.lapsed_regulars(pairs, today=date(2099, 11, 20)) == []    # no practice in the last 14 days


def test_unknown_season_and_empty_history():
    assert pp.season_key("Unknown") == (0, 0)
    assert pp.attendance_pairs([], []) == []
    assert pp.retention([]) == pp.newcomer_curve([]) == pp.overlap([]) == []
    assert pp.lapsed_regulars([], date(2099, 11, 30)) == []
    assert pp.everyone([], None) == []


def test_pairs_deduplicate_people_sessions_and_include_signups():
    old = _s(1, date(2099, 1, 1), F24)
    trip = _s(2, date(2099, 1, 2), F24, "trip")
    count_only = _s(3, date(2099, 1, 3), F24, reported=4)
    rows = [_a(trip, "a", "signup"), _a(old, "b"), _a(old, "b", "signup"),
            _a(old, "c", "lead"), _a(count_only, "d"), _a(old, "c", "plan")]
    assert [(p, s.id) for p, s in pp.attendance_pairs([trip, old, count_only], rows)] == [
        ("b", 1), ("a", 2)]


def test_retention_requires_next_year_of_same_type():
    fall = _s(1, date(2098, 11, 1), F24)
    spring = _s(2, date(2099, 5, 1), "2099 Spring/Summer")
    later = _s(3, date(2100, 11, 1), "2100 Fall/Winter")
    assert pp.retention([("a", fall), ("a", spring), ("a", later)]) == []


def test_retention_omits_empty_groups_but_keeps_zero_returns():
    old = _s(1, date(2098, 11, 1), F24)
    later = _s(2, date(2099, 11, 1), F25)
    assert pp.retention([("a", old), ("b", later)]) == [
        {"season_label": F24, "next_season": F25, "group": "First season",
         "people": 1, "returned": 0, "rate": 0.0}]


def test_newcomer_buckets_exclude_returning_people():
    old = _s(0, date(2098, 11, 1), F24)
    sessions = [_s(i, date(2099, 11, i), F25) for i in range(1, 7)]
    pairs = [("vet", old)] + [("vet", s) for s in sessions]
    pairs += [(f"new{n}", s) for n in range(1, 7) for s in sessions[:n]]
    pairs.sort(key=lambda pair: pair[1].date)
    rows = {r["bucket"]: r["people"] for r in pp.newcomer_curve(pairs) if r["season_label"] == F25}
    assert rows == {"1": 1, "2": 1, "3": 1, "4 to 5": 2, "6 or more": 1}


@pytest.mark.parametrize("days_ago, expected", [(28, []), (29, ["reg"])])
def test_lapsed_regular_cutoff_and_future_sessions(days_ago, expected):
    today = date(2099, 11, 30)
    previous = [_s(i, date(2098, 11, i), F24) for i in range(1, 7)]
    recent = _s(10, today - timedelta(days=days_ago), F25)
    running = _s(11, today - timedelta(days=14), F25)
    future = _s(12, date(2100, 11, 1), "2100 Fall/Winter")
    pairs = [("reg", s) for s in previous] + [("reg", recent), ("other", running), ("reg", future)]
    assert [r["person_key"] for r in pp.lapsed_regulars(pairs, today)] == expected


def test_everyone_counts_kinds_and_previous_same_type_season():
    sessions = [_s(1, date(2098, 11, 1), F24),
                _s(2, date(2099, 5, 1), "2099 Spring/Summer"),
                _s(3, date(2099, 11, 1), F25),
                _s(4, date(2099, 11, 2), F25, "event"),
                _s(5, date(2099, 11, 3), F25, "trip")]
    pairs = [("a", s) for s in sessions] + [("b", sessions[-1])]
    rows = {r["person_key"]: r for r in pp.everyone(pairs, F25)}
    assert rows["a"] == {"person_key": "a", "first_seen": "2098-11-01", "last_seen": "2099-11-03",
                         "practice_this": 1, "event_this": 1, "trip_this": 1,
                         "practice_last": 1, "all_time": 5}
    assert rows["b"]["all_time"] == 1


def _member(db_session, season, index, status="ACTIVE"):
    user = User(first_name="Pat" if index == 1 else f"Person{index}", last_name="Example",
                email=f"task13-{index}@example.invalid",
                slack_user=SlackUser(slack_uid=f"UFAKE{index:04d}", full_name="Slack Example"))
    db_session.add(user)
    db_session.flush()
    db_session.add(UserSeason(user_id=user.id, season_id=season.id, status=status,
                              registration_type="new", registration_date=season.start_date))
    return user


def _season(db_session):
    Season.query.filter_by(is_current=True).update({"is_current": False})
    season = Season(name=F25, season_type="winter", year=2099, is_current=True,
                    start_date=date(2099, 11, 1), end_date=date(2100, 3, 31))
    db_session.add(season)
    db_session.flush()
    return season


def test_display_names_and_never_rsvpd(db_session):
    season = _season(db_session)
    user = _member(db_session, season, 1)
    db_session.add(SlackUser(slack_uid="UFAKE0099", full_name="Sam Example"))
    db_session.flush()
    assert pp.never_rsvpd() == [{"name": "Pat Example"}]
    assert pp.display_names(["slack:UFAKE0001", "name:pat example", f"user:{user.id}",
                             "slack:UFAKE0099", "slack:UFAKEUNKNOWN"]) == {
        "slack:UFAKE0001": "Pat Example", "name:pat example": "Pat Example",
        f"user:{user.id}": "Pat Example", "slack:UFAKE0099": "Sam Example",
        "slack:UFAKEUNKNOWN": "slack:UFAKEUNKNOWN"}


def test_never_rsvpd_uses_active_members_dates_and_attendance_roles(db_session):
    season = _season(db_session)
    users = [_member(db_session, season, i) for i in range(1, 6)]
    _member(db_session, season, 6, status="PENDING_LOTTERY")
    for index, (user, day, role) in enumerate([
            (users[0], season.start_date, "rsvp"),
            (users[1], season.start_date, "signup"),
            (users[2], season.start_date - timedelta(days=1), "rsvp"),
            (users[3], season.start_date, "decline")]):
        session = PracticeSession(session_key=f"task13:{index}", group_key=f"task13:{index}",
                                  era="app", date=day, day_of_week=day.strftime("%A"), season_label=F25)
        db_session.add(session)
        db_session.flush()
        db_session.add(PracticeAttendance(session_id=session.id, user_id=user.id,
                                          person_key=f"user:{user.id}", role=role, source="app"))
    db_session.flush()
    assert pp.never_rsvpd() == [{"name": f"Person{i} Example"} for i in (3, 4, 5)]


def test_never_rsvpd_without_current_season(db_session):
    Season.query.filter_by(is_current=True).update({"is_current": False})
    assert pp.never_rsvpd() == []


@pytest.mark.parametrize("role", ["rsvp", "signup"])
def test_never_rsvpd_only_counts_held_sessions(db_session, role):
    season = _season(db_session)
    user = _member(db_session, season, 1)
    session = PracticeSession(session_key="task13:cancelled", group_key="task13:cancelled",
                              era="app", date=season.start_date, day_of_week="Sunday",
                              season_label=F25, status="cancelled")
    db_session.add(session)
    db_session.flush()
    db_session.add(PracticeAttendance(session_id=session.id, user_id=user.id,
                                      person_key=f"user:{user.id}", role=role, source="app"))
    db_session.flush()
    assert pp.never_rsvpd() == [{"name": "Pat Example"}]
    session.status = "held"
    db_session.flush()
    assert pp.never_rsvpd() == []


@pytest.fixture
def filtered_build(monkeypatch):
    sessions = [_s(1, date(2097, 11, 1), "2097 Fall/Winter", "event"),
                _s(2, date(2098, 11, 1), F24, "event"),
                _s(3, date(2099, 11, 1), F25, "event"),
                _s(4, date(2098, 11, 2), F24),
                _s(5, date(2099, 11, 2), F25)]
    attendance = [_a(s, "vet") for s in sessions[:3]]
    attendance += [_a(s, "new") for s in sessions[1:3]]
    attendance += [_a(s, "practice") for s in sessions[3:]]
    attendance.append(_a(sessions[2], "practice"))
    monkeypatch.setattr(pp, "load_sessions", lambda filters: [
        s for s in sessions if (not filters.kinds or s.kind in filters.kinds)
        and (not filters.seasons or s.season_label in filters.seasons)])
    monkeypatch.setattr(pp, "load_attendance", lambda ids, role: [
        a for a in attendance if a.session_id in ids and a.role in role])
    monkeypatch.setattr(pp.utils, "today_central", lambda: date(2100, 5, 1))
    monkeypatch.setattr(pp, "display_names", lambda keys: {p: p.title() for p in keys})
    monkeypatch.setattr(pp, "never_rsvpd", lambda: [])
    return pp.build


def test_season_filter_preserves_next_season_for_retention(filtered_build):
    blocks = filtered_build(Filters(seasons=[F24]))
    chart = next(b for b in blocks if isinstance(b, Chart) and b.title == "Coming back next season")
    assert chart.rows == [
        {"season_label": F24, "next_season": F25, "group": "First season",
         "people": 2, "returned": 2, "rate": 1.0},
        {"season_label": F24, "next_season": F25, "group": "Returning",
         "people": 1, "returned": 1, "rate": 1.0}]


def test_season_filter_preserves_true_first_season_for_newcomers(filtered_build):
    blocks = filtered_build(Filters(seasons=[F24]))
    chart = next(b for b in blocks if isinstance(b, Chart) and b.title == "How far newcomers get")
    assert chart.rows == [{"season_label": F24, "bucket": bucket, "people": count}
                          for bucket, count in [("1", 2), ("2", 0), ("3", 0), ("4 to 5", 0), ("6 or more", 0)]]


def test_kind_filter_only_narrows_retention_and_newcomers(filtered_build):
    blocks = filtered_build(Filters(seasons=[F24], kinds=["event"]))
    charts = [b for b in blocks if isinstance(b, Chart)]
    assert charts[0].rows == [
        {"season_label": F24, "next_season": F25, "group": "First season",
         "people": 1, "returned": 1, "rate": 1.0},
        {"season_label": F24, "next_season": F25, "group": "Returning",
         "people": 1, "returned": 1, "rate": 1.0}]
    assert charts[1].rows == [{"season_label": F24, "bucket": bucket, "people": count}
                             for bucket, count in [("1", 1), ("2", 0), ("3", 0), ("4 to 5", 0), ("6 or more", 0)]]
    for chart in charts:
        jsonschema.validate(chart.spec, SCHEMA)
        assert vlc.vegalite_to_svg(chart.spec)
    tiles = {t.label: t.value for t in blocks[0].tiles}
    assert tiles["People this season"] == 3
    tables = {b.title: b.rows for b in blocks if isinstance(b, Table)}
    assert tables["Who comes to what"] == [{"combo": "Event", "people": 2}, {"combo": "Practice", "people": 1}]
    all_seasons = filtered_build(Filters(kinds=["event"]))
    overlap = next(b for b in all_seasons if isinstance(b, Table) and b.title == "Who comes to what")
    assert overlap.rows == [{"combo": "Event", "people": 2}, {"combo": "Event + Practice", "people": 1}]
    assert {r["person_key"]: r["all_time"] for r in tables["Everyone"]} == {"vet": 3, "new": 2, "practice": 3}


def test_dashboard_explains_earliest_season_limit(filtered_build):
    note = next(b for b in filtered_build(Filters()) if isinstance(b, Note))
    assert "The earliest season on record (Oct 2022) counts everyone as first season because there is no earlier data." in note.text
    assert "\u2014" not in note.text and "\u2013" not in note.text


@pytest.mark.parametrize("empty", [False, True])
@pytest.mark.parametrize("seasons", [[F24], []])
@pytest.mark.parametrize("kinds", [["practice"], ["event"], []])
def test_dashboard_builds_valid_specs_and_preserves_full_history(empty, seasons, kinds):
    old = [_s(i, date(2098, 11, i), F24) for i in range(1, 7)]
    current = [_s(10, date(2099, 11, 1), F25)] + [
        _s(i, date(2099, 11, i + 9), F25) for i in range(11, 17)]
    sessions = [] if empty else old + current
    attendance = [] if empty else ([_a(s, "reg") for s in old + current[:1]]
                                   + [_a(s, "new") for s in current[1:]])
    filters = Filters(seasons=seasons, kinds=kinds)
    with patch.object(pp, "load_sessions", return_value=sessions) as load, \
         patch.object(pp, "load_attendance", return_value=attendance) as attendees, \
         patch.object(pp.utils, "today_central", return_value=date(2099, 11, 30)), \
         patch.object(pp, "display_names", return_value={"reg": "Pat Example", "new": "Sam Example"}), \
         patch.object(pp, "never_rsvpd", return_value=[{"name": "Alex Example"}]):
        blocks = pp.build(filters)
    load.assert_called_once_with(Filters())
    attendees.assert_called_once_with([s.id for s in sessions], role=("rsvp", "signup"))
    assert isinstance(blocks[0], Tiles)
    tiles = {t.label: t.value for t in blocks[0].tiles}
    assert tiles == {"People this season": 0 if empty else 2, "Regulars": 0 if empty else 1,
                     "First-timers": 0 if empty else 1, "Lapsed regulars": 0 if empty else 1}
    chart_blocks = [b for b in blocks if isinstance(b, Chart)]
    assert [b.title for b in chart_blocks] == ["Coming back next season", "How far newcomers get"]
    for chart in chart_blocks:
        jsonschema.validate(chart.spec, SCHEMA)
        assert vlc.vegalite_to_svg(chart.spec)
        assert all(r["season_label"] in (seasons or [F24, f"{F25} (so far)"]) for r in chart.rows)
    if empty or kinds == ["event"]:
        assert all(chart.rows == [] for chart in chart_blocks)
    assert chart_blocks[0].rows == []
    tables = {b.title: b.rows for b in blocks if isinstance(b, Table)}
    assert tables["Who comes to what"] == ([] if empty else [
        {"combo": "Practice", "people": 1 if seasons else 2}])
    assert tables["Registered, never RSVP'd"] == [{"name": "Alex Example"}]
    assert len(tables["Everyone"]) == (0 if empty else 2)
    if not empty:
        assert tables["Lapsed regulars"] == [{"person_key": "reg", "name": "Pat Example",
                                              "last_rsvp": "2099-11-01", "last_season_count": 6,
                                              "this_season_count": 1}]
        assert next(r for r in tables["Everyone"] if r["person_key"] == "reg")["all_time"] == 7
    assert isinstance(blocks[-1], Note)
    assert "Count-only sessions" in blocks[-1].text


def test_people_route_renders_dashboard_title(admin_client):
    response = admin_client.get("/admin/analytics/people")
    assert response.status_code == 200
    assert b"Who comes and who drifts" in response.data


def test_people_route_requires_admin(client):
    response = client.get("/admin/analytics/people")
    assert response.status_code == 302


@pytest.mark.parametrize("label, today, expected", [
    ("2099 Spring/Summer", date(2099, 4, 30), False),
    ("2099 Spring/Summer", date(2099, 5, 1), True),
    ("2099 Spring/Summer", date(2099, 8, 31), True),
    ("2099 Spring/Summer", date(2099, 9, 1), False),
    ("2099 Fall/Winter", date(2099, 8, 31), False),
    ("2099 Fall/Winter", date(2099, 9, 1), True),
    ("2099 Fall/Winter", date(2100, 4, 30), True),
    ("2099 Fall/Winter", date(2100, 5, 1), False),
    ("Unknown", date(2099, 6, 1), False),
    ("2099 Unknown", date(2099, 6, 1), False),
    ("0000 Spring/Summer", date(2099, 6, 1), False),
    (None, date(2099, 6, 1), False),
])
def test_season_in_progress_boundaries(label, today, expected):
    assert pp.season_in_progress(label, today) is expected


def test_in_progress_season_omits_retention_and_labels_newcomers(filtered_build, monkeypatch):
    monkeypatch.setattr(pp.utils, "today_central", lambda: date(2099, 11, 30))
    blocks = filtered_build(Filters())
    charts = [b for b in blocks if isinstance(b, Chart)]
    assert {r["next_season"] for r in charts[0].rows} == {F24}
    assert {r["season_label"] for r in charts[1].rows} == {
        "2097 Fall/Winter", F24, f"{F25} (so far)"}
    selected = filtered_build(Filters(seasons=[F25]))
    newcomers = next(b for b in selected if isinstance(b, Chart) and b.title == "How far newcomers get")
    assert {r["season_label"] for r in newcomers.rows} == {f"{F25} (so far)"}
    assert any("The current season is still in progress, so it is not yet counted as a next season "
               "in the retention chart, and its newcomer column is partial." in b.text
               for b in blocks if isinstance(b, Note))


def test_shift_keeps_season_type_across_years():
    assert pp._shift("2099 Spring/Summer", 1) == "2100 Spring/Summer"
    assert pp._shift("2099 Fall/Winter", -1) == "2098 Fall/Winter"
