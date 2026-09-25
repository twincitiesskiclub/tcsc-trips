"""Synthetic sessions only."""
import json
from datetime import date, time, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import jsonschema
import vl_convert as vlc

from app.analytics.dashboards import practices as p
from app.analytics.dashboards.base import Chart, Filters, Tiles
from tests.analytics.conftest import FIXTURES

SCHEMA = json.loads((FIXTURES / "vega-lite-v6.schema.json").read_text())


def _s(id, day, rsvps, group=None, activity="Run", fmt="single", temp=50.0, season="2099 Fall/Winter",
       status="held", hour=18):
    return SimpleNamespace(id=id, date=day, group_key=group or f"g{id}", season_label=season,
                           day_of_week=day.strftime("%A"), activity=activity, workout_type="Endurance",
                           location_name="Park", start_time=time(hour, 0), temp_f=temp, precip_in=0.0,
                           snow_depth_in=0.0, minutes_after_sunset=-30, format=fmt, status=status,
                           kind="practice", slot=None, rsvp_count=rsvps)


def _rsvps(session, n, start=0, role="rsvp"):
    return [SimpleNamespace(session_id=session.id, person_key=f"slack:UFAKE{start + i:04d}",
                            slack_uid=f"UFAKE{start + i:04d}", user_id=None, slot=None, role=role)
            for i in range(n)]


def test_split_night_collapses_to_one_row():
    a = _s(1, date(2099, 11, 5), 0, group="g", fmt="split")
    b = _s(2, date(2099, 11, 5), 0, group="g", fmt="split", hour=19)
    rows = p.nights([a, b], _rsvps(a, 10) + _rsvps(b, 8, start=100) + _rsvps(b, 1, start=0))
    assert len(rows) == 1 and rows[0]["rsvps"] == 18 and rows[0]["start_hour"] == 18
    assert rows[0]["formats"] == ["split"]


def test_cancelled_sessions_are_not_nights():
    s = _s(1, date(2099, 11, 5), 0, status="cancelled")
    assert p.nights([s], _rsvps(s, 5)) == []


def test_index_is_relative_to_season_weekday_median():
    rows = [{"season_label": "S", "day_of_week": "Tuesday", "rsvps": n} for n in (10, 20, 30)]
    medians = p.baseline_medians(rows)
    assert medians[("S", "Tuesday")] == 20
    assert [r["index"] for r in p.with_index(rows, medians)] == [0.5, 1.0, 1.5]
    assert p.with_index([{"season_label": "X", "day_of_week": "Monday", "rsvps": 4}], medians)[0]["index"] is None


def test_bands():
    assert p.band("temp_f", None) == "Unknown"
    assert p.band("temp_f", 5) == "Below 15°F"
    assert p.band("temp_f", 72) == "70°F and up"
    assert p.band("precip_in", 0) == "Dry"
    assert p.band("minutes_after_sunset", -10) == "Before sunset"
    assert p.band("minutes_after_sunset", 90) == "Dark"
    assert p.band("start_hour", 6) == "6 AM" and p.band("start_hour", 18) == "6 PM"


def test_factor_rows_mark_thin_groups():
    rows = [{"activity": "Run", "index": 1.0, "rsvps": 20}] * 5 + [{"activity": "Ski", "index": 2.0, "rsvps": 40}]
    out = p.factor_rows(rows, "activity")
    assert [(r["value"], r["thin"], r["nights"]) for r in out] == [("Ski", True, 1), ("Run", False, 5)]


def test_dashboard_builds_valid_specs():
    sessions = [_s(i, date(2099, 11, 3) + timedelta(weeks=i), 0, activity="Run" if i % 2 else "Ski") for i in range(8)]
    attendance = [row for i, s in enumerate(sessions) for row in _rsvps(s, 10 + i)]
    with patch.object(p, "load_sessions", return_value=sessions), \
         patch.object(p, "load_attendance", return_value=attendance), \
         patch.object(p, "load_baseline_sessions", return_value=(sessions, attendance)):
        blocks = p.DASHBOARD.build(Filters(kinds=["practice"]))
    assert isinstance(blocks[0], Tiles)
    charts = [b for b in blocks if isinstance(b, Chart)]
    assert len(charts) >= 5
    for chart in charts:
        jsonschema.validate(chart.spec, SCHEMA)
        assert vlc.vegalite_to_svg(chart.spec)


def test_split_section_only_when_splits_present():
    sessions = [_s(1, date(2099, 11, 5), 0)]
    with patch.object(p, "load_sessions", return_value=sessions), \
         patch.object(p, "load_attendance", return_value=[]), \
         patch.object(p, "load_baseline_sessions", return_value=(sessions, [])), \
         patch.object(p, "split_blocks") as split:
        p.DASHBOARD.build(Filters(kinds=["practice"]))
    split.assert_not_called()


def test_nights_count_rsvps_and_record_leads_separately():
    s = _s(1, date(2099, 11, 5), 99)
    s.start_time = None
    s.location_name = None
    rows = p.nights([s], _rsvps(s, 2) + _rsvps(s, 1, start=100, role="lead")
                    + _rsvps(s, 3, start=200, role="decline"))
    assert rows[0]["rsvps"] == 2
    assert rows[0]["has_lead"] is True
    assert rows[0]["start_hour"] is None
    assert rows[0]["location"] == "Unknown"


def test_zero_baseline_has_no_index_or_factor_group():
    rows = [{"season_label": "S", "day_of_week": "Tuesday", "rsvps": 0, "activity": "Run"}]
    indexed = p.with_index(rows, p.baseline_medians(rows))
    assert indexed[0]["index"] is None
    assert "index" not in rows[0]
    assert p.factor_rows(indexed, "activity") == []


def test_baseline_keeps_selected_seasons_without_factor_filters():
    filters = Filters(seasons=["2099 Fall/Winter"], kinds=["practice"], activities=["Run"],
                      date_from=date(2099, 11, 5), days=["Thursday"], formats=["split"])
    s = _s(1, date(2099, 11, 5), 0)
    with patch.object(p, "load_sessions", return_value=[s]) as sessions, \
         patch.object(p, "load_attendance", return_value=[]) as attendance:
        assert p.load_baseline_sessions(filters) == ([s], [])
    sessions.assert_called_once_with(Filters(seasons=["2099 Fall/Winter"], kinds=["practice"]))
    attendance.assert_called_once_with([1], role=("rsvp", "lead"))


def test_split_section_receives_only_rsvp_rows():
    s = _s(1, date(2099, 11, 5), 0, fmt="split")
    rsvps = _rsvps(s, 2)
    attendance = rsvps + _rsvps(s, 1, start=100, role="lead")
    filters = Filters(kinds=["practice"])
    with patch.object(p, "load_sessions", return_value=[s]), \
         patch.object(p, "load_attendance", return_value=attendance), \
         patch.object(p, "load_baseline_sessions", return_value=([s], attendance)), \
         patch.object(p, "split_blocks", wraps=p.split_blocks) as split:
        blocks = p.DASHBOARD.build(filters)
    split.assert_called_once_with([s], rsvps, filters)
    assert len([b for b in blocks if isinstance(b, Chart)]) == 15
    tiles = {tile.label: tile.value for tile in blocks[0].tiles}
    assert tiles["Distinct people"] == 2
    assert tiles["Average RSVPs"] == "2.0"


def test_practices_route_renders_dashboard_title(admin_client):
    response = admin_client.get("/admin/analytics/practices")
    assert response.status_code == 200
    assert b"What makes a practice draw" in response.data
