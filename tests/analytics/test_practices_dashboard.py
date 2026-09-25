"""Synthetic sessions only."""
import json
from datetime import date, time, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import jsonschema
import vl_convert as vlc

from app.analytics.dashboards import practices as p
from app.analytics.dashboards.base import Chart, Filters, Note, Table, Tiles
from tests.analytics.conftest import FIXTURES

SCHEMA = json.loads((FIXTURES / "vega-lite-v6.schema.json").read_text())


def _s(id, day, rsvps, group=None, activity="Run", fmt="single", temp=50.0, season="2099 Fall/Winter",
       status="held", hour=18, reported_count=None):
    return SimpleNamespace(id=id, date=day, group_key=group or f"g{id}", season_label=season,
                           day_of_week=day.strftime("%A"), activity=activity, workout_type="Endurance",
                           location_name="Park", start_time=time(hour, 0), temp_f=temp, precip_in=0.0,
                           snow_depth_in=0.0, minutes_after_sunset=-30, format=fmt, status=status,
                           kind="practice", slot=None, rsvp_count=rsvps, reported_count=reported_count)


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
    assert medians[("S", "Tuesday")] == (20, 3)
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
    rows = [{"season_label": "S", "day_of_week": "Tuesday", "rsvps": 0, "activity": "Run"}] * 3
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
    assert b">Apply<" in response.data


def test_factor_bar_description_explains_which_way_bars_run():
    sessions = [_s(1, date(2099, 11, 5), 10)]
    attendance = _rsvps(sessions[0], 10)
    with patch.object(p, "load_sessions", return_value=sessions), \
         patch.object(p, "load_attendance", return_value=attendance), \
         patch.object(p, "load_baseline_sessions", return_value=(sessions, attendance)):
        blocks = p.build(Filters(kinds=["practice"]))
    chart = next(b for b in blocks if isinstance(b, Chart) and b.title == "Activity")
    assert chart.description == ("Median turnout index by activity. Bars run right of 1.0 when practices draw "
                                 "more than a typical practice for that season and weekday, left when they draw fewer.")
    assert "—" not in chart.description and "–" not in chart.description


def test_color_group_buckets_named_activities_and_puts_the_rest_in_other():
    assert p.color_group("Strength") == "Strength"
    assert p.color_group("Ski") == "Ski"
    assert p.color_group("Run") == "Run"
    assert p.color_group("Multisport") == "Other"


def test_turnout_over_time_colors_by_group_with_a_legend_and_keeps_real_activity_in_tooltip():
    sessions = [_s(1, date(2099, 11, 5), 10, activity="Strength"),
                _s(2, date(2099, 11, 12), 10, activity="Multisport")]
    attendance = [row for s in sessions for row in _rsvps(s, s.rsvp_count)]
    with patch.object(p, "load_sessions", return_value=sessions), \
         patch.object(p, "load_attendance", return_value=attendance), \
         patch.object(p, "load_baseline_sessions", return_value=(sessions, attendance)):
        blocks = p.build(Filters(kinds=["practice"]))
    chart = next(b for b in blocks if isinstance(b, Chart) and b.title == "Turnout over time")
    assert [r["color_group"] for r in chart.rows] == ["Strength", "Other"]
    assert chart.spec["encoding"]["color"]["field"] == "color_group"
    assert chart.spec["encoding"]["color"]["scale"] == {
        "domain": ["Strength", "Ski", "Run", "Other"],
        "range": ["#2a78d6", "#eb6834", "#1baf7a", "#9a9994"]}
    assert chart.spec["encoding"]["color"]["legend"] == {"title": "Activity"}
    tooltip_fields = [t["field"] for t in chart.spec["encoding"]["tooltip"]]
    assert "activity" in tooltip_fields
    jsonschema.validate(chart.spec, SCHEMA)
    assert vlc.vegalite_to_svg(chart.spec)


def test_date_filter_preserves_baseline_week_of_season():
    sessions = [_s(i, date(2099, 11, 3) + timedelta(weeks=i), 10) for i in range(8)]
    attendance = [row for s in sessions for row in _rsvps(s, 10)]
    with patch.object(p, "load_sessions", return_value=sessions[4:]), \
         patch.object(p, "load_attendance", return_value=[r for r in attendance if r.session_id >= 4]), \
         patch.object(p, "load_baseline_sessions", return_value=(sessions, attendance)):
        blocks = p.build(Filters(kinds=["practice"], date_from=sessions[4].date))
    table = next(b for b in blocks if isinstance(b, Table) and b.title == "Every practice")
    assert table.rows[0]["date"] == "2099-12-01"
    assert table.rows[0]["week_band"] == "Weeks 5 to 8"
    factor = next(b for b in blocks if isinstance(b, Chart) and b.title == "Week of season")
    assert factor.rows == [{"value": "Weeks 5 to 8", "median_index": 1.0,
                            "median_rsvps": 10, "nights": 4, "thin": True}]


def test_cancelled_night_appears_only_in_turnout_over_time():
    held = [_s(i, date(2099, 11, 3) + timedelta(weeks=i), n) for i, n in enumerate((10, 10, 20, 30, 30))]
    cancelled = _s(10, date(2099, 12, 8), 50, status="cancelled", activity="Ski")
    sessions = held + [cancelled]
    attendance = [row for s in held for row in _rsvps(s, s.rsvp_count)] + _rsvps(cancelled, 50)
    with patch.object(p, "load_sessions", return_value=sessions), \
         patch.object(p, "load_attendance", return_value=attendance), \
         patch.object(p, "load_baseline_sessions", return_value=(sessions, attendance)):
        blocks = p.build(Filters(kinds=["practice"]))
    chart = next(b for b in blocks if isinstance(b, Chart) and b.title == "Turnout over time")
    assert len(chart.rows) == 6
    assert [(r["date"], r["rsvps"]) for r in chart.rows if r["status"] == "cancelled"] == [("2099-12-08", 50)]
    assert chart.spec["data"]["values"] == chart.rows
    assert chart.spec["encoding"]["opacity"] == {
        "condition": {"test": "datum.status === 'cancelled'", "value": 0.35}, "value": 0.8}
    assert [r["index"] for r in chart.rows if r["status"] == "held"] == [0.5, 0.5, 1.0, 1.5, 1.5]
    tiles = {t.label: t.value for t in blocks[0].tiles}
    assert tiles["Practices"] == 5
    assert tiles["Average RSVPs"] == "20.0"
    assert tiles["Strongest draw"] == tiles["Weakest draw"] == "Run"
    for block in blocks:
        if isinstance(block, Chart):
            jsonschema.validate(block.spec, SCHEMA)
            assert vlc.vegalite_to_svg(block.spec)
            if block is not chart:
                assert sum(r["nights"] for r in block.rows) == 5
                assert all(r["value"] != "Ski" for r in block.rows)
        elif isinstance(block, Table):
            assert len(block.rows) == 5
            assert all(r["date"] != "2099-12-08" for r in block.rows)
    activity = next(b for b in blocks if isinstance(b, Chart) and b.title == "Activity")
    assert activity.rows == [{"value": "Run", "median_index": 1.0,
                              "median_rsvps": 20, "nights": 5, "thin": False}]


def test_count_only_session_contributes_reported_count_to_night():
    s = _s(1, date(2099, 11, 5), 12, reported_count=12)
    assert p.nights([s], [])[0]["rsvps"] == 12


def test_cancelled_only_season_has_chart_point_without_held_metrics():
    s = _s(1, date(2099, 11, 5), 12, status="cancelled", reported_count=12)
    with patch.object(p, "load_sessions", return_value=[s]), \
         patch.object(p, "load_attendance", return_value=[]), \
         patch.object(p, "load_baseline_sessions", return_value=([s], [])):
        blocks = p.build(Filters(kinds=["practice"]))
    assert all(t.value == "No data" for t in blocks[0].tiles)
    chart = next(b for b in blocks if isinstance(b, Chart) and b.title == "Turnout over time")
    assert [(r["status"], r["rsvps"], r["index"]) for r in chart.rows] == [("cancelled", 12, None)]
    for block in blocks:
        if isinstance(block, (Chart, Table)) and block is not chart:
            assert block.rows == []
        if isinstance(block, Chart):
            jsonschema.validate(block.spec, SCHEMA)


def test_split_night_adds_count_only_sessions_to_distinct_rsvps():
    a = _s(1, date(2099, 11, 5), 12, group="g", fmt="split", reported_count=12)
    b = _s(2, a.date, 3, group="g", fmt="split", hour=19)
    c = _s(3, a.date, 3, group="g", fmt="split", hour=20)
    rows = p.nights([a, b, c], _rsvps(b, 3) + _rsvps(c, 3, start=2))
    assert rows[0]["rsvps"] == 17


def test_distinct_people_counts_only_held_session_rsvps():
    held = _s(1, date(2099, 11, 5), 2)
    cancelled = _s(2, date(2099, 11, 12), 3, status="cancelled")
    attendance = _rsvps(held, 2) + _rsvps(held, 1, start=100, role="lead") + _rsvps(cancelled, 3)
    with patch.object(p, "load_sessions", return_value=[held, cancelled]), \
         patch.object(p, "load_attendance", return_value=attendance), \
         patch.object(p, "load_baseline_sessions", return_value=([held, cancelled], attendance)):
        blocks = p.build(Filters(kinds=["practice"]))
    assert next(t.value for t in blocks[0].tiles if t.label == "Distinct people") == 2


def test_turnout_index_note_explains_filtered_split_night_comparison():
    with patch.object(p, "load_sessions", return_value=[]), \
         patch.object(p, "load_attendance", return_value=[]), \
         patch.object(p, "load_baseline_sessions", return_value=([], [])):
        blocks = p.build(Filters(kinds=["practice"]))
    note = next(b.text for b in blocks if isinstance(b, Note) and b.text.startswith("Turnout index:"))
    assert "When a filter keeps only one session of a split night, that night is compared against whole nights." in note
    assert "\u2014" not in note and "\u2013" not in note


def test_two_night_baseline_has_no_index_even_when_other_groups_are_large():
    thin = [{"season_label": "S", "day_of_week": "Tuesday", "rsvps": n} for n in (10, 20)]
    other = [{"season_label": "S", "day_of_week": "Thursday", "rsvps": 10}] * 3
    other += [{"season_label": "Previous", "day_of_week": "Tuesday", "rsvps": 10}] * 3
    medians = p.baseline_medians(thin + other)
    assert [r["index"] for r in p.with_index(thin, medians)] == [None, None]
    assert medians[("S", "Tuesday")] == (15, 2)
    assert p.with_index(other[:1], medians)[0]["index"] == 1.0
