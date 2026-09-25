"""Synthetic RSVP seasons only; no member or archived Slack data."""
import json
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import jsonschema
import pytest
import vl_convert as vlc

from app.analytics import dashboards
from app.analytics.dashboards import thursday_strength as ts
from app.analytics.dashboards.base import Chart, Filters, Note, Table, Tiles
from tests.analytics.conftest import FIXTURES

WEEKS = [(20, 10), (25, 15), (18, 17), (30, 20)]
FIRST = date(2099, 9, 17)
SCHEMA = json.loads((FIXTURES / "vega-lite-v6.schema.json").read_text())


def _session(id, day=FIRST, format="split", season="2099 Fall/Winter", slot=None):
    return SimpleNamespace(id=id, date=day, format=format, status="held",
                           season_label=season, day_of_week=day.strftime("%A"),
                           start_time=None, slot=slot)


def _rsvp(session_id, person, slot=None, role="rsvp"):
    return SimpleNamespace(session_id=session_id, slack_uid=f"UFAKE{person:04d}",
                           slot=slot, role=role)


def _data():
    sessions, attendance = [], []
    for i, (early, late) in enumerate(WEEKS):
        sessions.append(_session(i, FIRST + timedelta(weeks=i)))
        for offset, (slot, n) in enumerate((("early", early), ("late", late))):
            attendance.extend(_rsvp(i, i * 100 + offset * 50 + k, slot) for k in range(n))
    return sessions, attendance


def _build(sessions, attendance, filters=None):
    with patch.object(ts, "load_sessions", return_value=sessions) as load, \
         patch.object(ts, "load_attendance", return_value=attendance) as load_rsvps:
        selected = filters or Filters(days=["Thursday"], activities=["Strength"])
        blocks = ts.DASHBOARD.build(selected)
        load.assert_called_once_with(selected)
        load_rsvps.assert_called_once_with([s.id for s in sessions])
        return blocks


@pytest.fixture
def blocks():
    return _build(*_data())


def _tiles(blocks):
    return {t.label: t for t in blocks[0].tiles}


def _charts(blocks):
    return [b for b in blocks if isinstance(b, Chart)]


def _render(chart):
    jsonschema.validate(chart.spec, SCHEMA)
    png = vlc.vegalite_to_png(json.dumps({**chart.spec, "width": 800}))
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    return png


def test_dashboard_contract_and_registration(blocks):
    d = ts.DASHBOARD
    assert dashboards.get_dashboard("thursday-strength") is d
    assert d.title == "Thursday strength"
    assert d.question == "Should Thursday strength run as one session or two?"
    assert d.filters == ["season", "date_range", "day_of_week", "format"]
    assert d.fixed == {"activities": ["Strength"], "kinds": ["practice"]}
    assert d.defaults == {"days": ["Thursday"]}
    assert [type(b) for b in blocks] == [Tiles, Chart, Chart, Table, Chart, Chart, Note, Note, Note]
    assert [c.title for c in _charts(blocks)] == [
        "Every strength session", "Season by season", "This season against last", "Who picks which slot"]
    assert blocks[-3].text == "RSVPs are not headcount. Some people RSVP and skip, some come without reacting, and leads often don't react."
    assert blocks[-2].text == "Merges happened on nights with low RSVPs, so merged weeks averaging fewer people does not mean merging lowers turnout."


def test_tiles(blocks):
    tiles = _tiles(blocks)
    assert tiles["Average per week"].value == "38.8"
    assert tiles["Average per week"].sub == "RSVPs a week, peak 50"
    assert tiles["Weeks over 27"].value == "4 of 4"
    assert tiles["Weeks over 35"].value == "2 of 4"
    assert tiles["Late session share"].value == "40%"
    assert tiles["Late session share"].sub == "of two-session RSVPs"
    assert str(tiles["Latest week"].value) == "50"
    assert "Weeks over 30" not in tiles


@pytest.mark.parametrize("index", range(4))
def test_every_chart_has_rows_and_valid_spec_and_renders(blocks, index, tmp_path):
    chart = _charts(blocks)[index]
    assert chart.rows and chart.description.endswith(".")
    assert chart.spec["description"] == chart.description
    assert "\u2014" not in json.dumps(chart.spec, ensure_ascii=False)
    (tmp_path / f"chart-{index}.png").write_bytes(_render(chart))


def test_weekly_totals_and_season_summary(blocks):
    weeks = ts.weekly_totals(*_data())
    assert [w["total"] for w in weeks] == [30, 40, 35, 50]
    assert [w["week"] for w in weeks] == [FIRST - timedelta(days=3) + timedelta(weeks=i) for i in range(4)]
    assert all(w["season_label"] == "2099 Fall/Winter" and w["formats"] == ["split"] for w in weeks)
    summary = next(b for b in blocks if isinstance(b, Table))
    row = summary.rows[0]
    assert (row["season_label"], row["weeks"], row["avg"], row["peak"]) == ("2099 Fall/Winter", 4, 38.8, 50)
    assert (row["over_27"], row["over_35"], row["late_pct"]) == (4, 2, "40%")


def test_split_rows_merged_slots_single_duplicates_and_roles():
    sessions = [_session(1, slot="early"), _session(2, slot="late"),
                _session(3, FIRST + timedelta(days=1), "merged"),
                _session(4, FIRST + timedelta(days=3), "single"),
                _session(5, FIRST + timedelta(days=4), "single")]
    att = [_rsvp(1, 1, "early"), _rsvp(1, 1, "early"), _rsvp(2, 1, "late"),
           _rsvp(3, 1, "early"), _rsvp(3, 1, "late"), _rsvp(3, 2, "late"),
           _rsvp(3, 9, "late", "coach"), _rsvp(3, 10, None),
           _rsvp(4, 1), _rsvp(4, 1, "early"), _rsvp(4, 2), _rsvp(5, 3),
           _rsvp(999, 1, "early")]
    weeks = ts.weekly_totals(sessions, att)
    assert [w["total"] for w in weeks] == [8, 1]
    assert weeks[0]["formats"] == ["merged", "single", "split"]
    blocks = _build(sessions, att)
    assert _tiles(blocks)["Late session share"].value == "50%"
    rows = _charts(blocks)[0].rows
    assert [(r["early"], r["late"], r["single"], r["total"]) for r in rows] == [
        (1, 0, 0, 1), (0, 1, 0, 1), (1, 2, 0, 4), (0, 0, 2, 2), (0, 0, 1, 1)]
    first_chart = _charts(blocks)[0]
    markers = [layer for layer in first_chart.spec["layer"] if layer["mark"]["type"] == "point"]
    assert len(markers) == 1 and markers[0]["mark"]["filled"] is False
    assert [row["date"] for row in markers[0]["data"]["values"]] == [(FIRST + timedelta(days=1)).isoformat()]
    for chart in _charts(blocks):
        _render(chart)


def test_slot_preference_counts_people_per_season_not_rsvps():
    sessions = [_session(1), _session(2, format="merged"), _session(3, format="single"),
                _session(4, season="2098 Fall/Winter")]
    att = [_rsvp(1, 1, "early"), _rsvp(1, 1, "early"), _rsvp(2, 1, "late"),
           _rsvp(1, 2, "late"), _rsvp(3, 3, "early"), _rsvp(1, 4, "early", "coach"),
           _rsvp(999, 3, "early"), _rsvp(4, 1, "early")]
    rows = ts.slot_preference(sessions, att)
    assert {r["preference"]: r["people"] for r in rows if r["season_label"] == "2099 Fall/Winter"} == {
        "Both": 1, "Late only": 1, "Early only": 0}
    assert {r["preference"]: r["people"] for r in rows if r["season_label"] == "2098 Fall/Winter"} == {
        "Both": 0, "Late only": 0, "Early only": 1}
    assert "UFAKE" not in json.dumps(_charts(_build(sessions, att))[-1].spec)


@pytest.mark.parametrize("day, bounded", [(date(2025, 11, 30), False), (date(2025, 12, 1), True),
    (date(2026, 3, 31), True), (date(2026, 4, 1), False), (date(2099, 9, 17), False)])
def test_capacity_overlap_and_tiles_use_same_lines(day, bounded):
    blocks = _build([_session(1, day)], [])
    tiles = _tiles(blocks)
    values = [27, 30, 35] if bounded else [27, 35]
    assert [int(key.split()[-1]) for key in tiles if key.startswith("Weeks over")] == values
    rules = [layer for layer in _charts(blocks)[0].spec["layer"] if layer["mark"]["type"] == "rule"]
    assert sorted(row["value"] for rule in rules for row in rule["data"]["values"]) == values
    table = next(b for b in blocks if isinstance(b, Table))
    assert [label for key, label in table.columns if key.startswith("over_")] == [f"Weeks over {v}" for v in values]


def test_latest_week_comparison_and_matching_season_type():
    previous = FIRST - timedelta(days=364)
    sessions = [_session(1, previous, season="2098 Fall/Winter"),
                _session(2, FIRST), _session(3, FIRST + timedelta(weeks=2)),
                _session(4, date(2099, 6, 4), season="2099 Spring/Summer")]
    att = [_rsvp(1, 1, "early"), _rsvp(1, 2, "late"), _rsvp(2, 3, "early"), _rsvp(4, 4, "early")]
    first = _build(sessions[:2], att)
    assert _tiles(first)["Latest week"].sub == "Same week last year: 2"
    blocks = _build(sessions, att)
    assert "Same week last year" not in _tiles(blocks)["Latest week"].sub
    rows = _charts(blocks)[2].rows
    assert {r["season_label"] for r in rows} == {"2098 Fall/Winter", "2099 Fall/Winter"}
    assert [r["week_of_season"] for r in rows if r["season_label"] == "2099 Fall/Winter"] == [1, 3]
    assert ts.week_of_season(ts.weekly_totals(sessions, att)) == rows


def test_empty_selection_is_not_a_zero_percent_and_renders():
    blocks = _build([], [])
    tiles = _tiles(blocks)
    assert all(tile.value == "No data" and tile.sub == "" for tile in tiles.values())
    for chart in _charts(blocks):
        assert chart.rows == []
        _render(chart)


def test_build_trusts_loaders_even_when_filters_do_not_match():
    blocks = _build(*_data(), filters=Filters(seasons=["Other"], days=["Friday"],
                                           date_to=date(2000, 1, 1)))
    assert _tiles(blocks)["Average per week"].value == "38.8"


def test_registered_dashboard_route_uses_real_blocks(admin_client):
    from app.analytics.dashboards import base
    with patch.object(ts, "load_sessions", return_value=_data()[0]), \
         patch.object(ts, "load_attendance", return_value=_data()[1]), \
         patch.object(base, "get_filter_domains", return_value={"seasons": {"2099 Fall/Winter"},
            "activities": {"Strength"}, "workout_types": set(), "location_ids": set()}), \
         patch.object(base, "filter_options", return_value={}), \
         patch.object(base, "footer", return_value={}):
        response = admin_client.get("/admin/analytics/thursday-strength")
    assert response.status_code == 200
    assert response.data.count(b'class="analytics-chart"') == 4
    assert b"38.8" in response.data and b"Should Thursday strength run as one session or two?" in response.data


def test_sessions_with_known_and_unknown_times_sort_safely():
    from datetime import time
    sessions = [_session(1), _session(2)]
    sessions[0].start_time = time(19)
    sessions[1].start_time = None
    blocks = _build(sessions, [_rsvp(1, 1, "late"), _rsvp(2, 2, "early")])
    assert _tiles(blocks)["Average per week"].value == "2.0"


def _long_data():
    """150 invented Thursday session rows across four seasons, including split pairs."""
    sessions, attendance = [], []
    first = date(2097, 5, 2)  # Thursday
    for i in range(104):
        day = first + timedelta(weeks=i)
        year = day.year if day.month >= 5 else day.year - 1
        season_type = "Spring/Summer" if 5 <= day.month <= 8 else "Fall/Winter"
        label = f"{year} {season_type}"
        format = "merged" if i % 9 == 0 else "single" if i % 7 == 0 else "split"
        # 46 of the split nights use separate early and late session rows.
        separate = format == "split" and sum(s.slot == "early" for s in sessions) < 46
        for slot in (("early", "late") if separate else (None,)):
            session = _session(len(sessions), day, format, label, slot)
            if i in (22, 71):
                session.status = "cancelled"
            sessions.append(session)
            counts = [(None, 20 + i % 13)] if format == "single" else [
                ("early", 14 + i % 19), ("late", 6 + i % 12)]
            for chosen, count in counts:
                if slot is None or chosen == slot:
                    attendance.extend(_rsvp(session.id, k + (50 if chosen == "late" else 0), chosen)
                                      for k in range(count))
    return sessions, attendance


def test_cancelled_week_is_visible_but_changes_no_aggregate():
    sessions, attendance = _data()
    before = _build(sessions, attendance)
    cancelled = _session(99, FIRST + timedelta(weeks=8), season="2100 Spring/Summer")
    cancelled.status = "cancelled"
    sessions.append(cancelled)
    attendance += [_rsvp(99, 999, "late")]
    after = _build(sessions, attendance)
    assert _tiles(after) == _tiles(before)
    assert next(b for b in after if isinstance(b, Table)) == next(b for b in before if isinstance(b, Table))
    assert _charts(after)[1:] == _charts(before)[1:]
    assert [w["total"] for w in ts.weekly_totals(sessions, attendance)] == [30, 40, 35, 50]
    assert all(row["season_label"] != "2100 Spring/Summer" for row in ts.slot_preference(sessions, attendance))
    chart = _charts(after)[0]
    assert chart.rows[-1]["status"] == "cancelled" and chart.rows[-1]["total"] == 1
    assert chart.spec["layer"][0]["encoding"]["opacity"] == {
        "condition": {"test": "datum.status === 'cancelled'", "value": 0.35}, "value": 1}
    assert after[-1].text == "Cancelled nights appear faded in the session chart and are left out of every average."
    _render(chart)


def test_session_chart_uses_temporal_horizontal_axis_and_entity_colors(blocks):
    s = _charts(blocks)[0].spec
    bar = s["layer"][0]
    assert bar["encoding"]["x"]["type"] == "temporal"
    assert bar["encoding"]["x"]["axis"]["labelAngle"] == 0
    assert bar["encoding"]["x"]["axis"]["format"] == "%b %-d"
    assert bar["encoding"]["x"]["axis"]["labelOverlap"]
    assert bar["encoding"]["color"]["scale"]["range"] == ["#2a78d6", "#eb6834", "#4a3aa7"]
    gap = next(layer for layer in s["layer"] if layer["mark"]["type"] == "tick")
    assert gap["mark"]["color"] == "#ffffff" and gap["mark"]["thickness"] == 2
    assert [r["boundary"] for r in gap["data"]["values"]] == [20, 25, 18, 30]
    assert s["padding"]["right"] >= 8
    labels = next(layer for layer in s["layer"] if layer["mark"]["type"] == "text"
                  and layer.get("encoding", {}).get("text", {}).get("field") == "display_label")
    assert labels["encoding"]["x"] == {"value": "width"}
    assert labels["mark"]["align"] == "left" and labels["mark"]["dx"] > 0


def test_season_chart_uses_average_bars_and_peak_ticks(blocks):
    chart = _charts(blocks)[1]
    bar, tick = chart.spec["layer"]
    assert bar["mark"]["type"] == "bar" and bar["mark"]["size"] <= 24
    assert bar["mark"]["color"] == "#4a3aa7"
    assert tick["mark"]["type"] == "tick" and tick["mark"]["thickness"] == 2
    assert bar["encoding"]["x"] == tick["encoding"]["x"]
    assert "Bars: average per week. Tick: peak week." in bar["encoding"]["x"]["title"]
    assert bar["data"]["values"][0]["rsvps"] == 38.8
    assert tick["data"]["values"][0]["rsvps"] == 50
    preference = _charts(blocks)[3].spec
    assert preference["encoding"]["color"]["scale"]["range"] == ["#2a78d6", "#eb6834", "#4a3aa7"]
    assert preference["encoding"]["x"]["axis"]["labelAngle"] == 0


def test_long_session_history_validates_and_renders():
    sessions, attendance = _long_data()
    assert len(sessions) == 150 and len({s.season_label for s in sessions}) == 4
    chart = _charts(_build(sessions, attendance))[0]
    assert len(chart.rows) == 150
    assert any(r["status"] == "cancelled" for r in chart.rows)
    assert chart.spec["layer"][0]["encoding"]["x"]["type"] == "temporal"
    _render(chart)


def test_cancelled_dates_do_not_introduce_capacity_tiles():
    sessions, attendance = _data()
    cancelled = _session(99, date(2025, 12, 4))
    cancelled.status = "cancelled"
    before = _tiles(_build(sessions, attendance))
    after = _tiles(_build([cancelled, *sessions], attendance))
    assert after == before


def test_long_chart_renders_at_phone_width():
    chart = _charts(_build(*_long_data()))[0]
    png = vlc.vegalite_to_png({**chart.spec, "width": 320})
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def _gapped_data():
    sessions, attendance = [], []
    for year, start in ((2098, FIRST - timedelta(days=364)), (2099, FIRST)):
        for week in (1, 2, 12, 26, 28, 29):
            session = _session(len(sessions), start + timedelta(weeks=week - 1),
                               season=f"{year} Fall/Winter")
            sessions.append(session)
            attendance.extend(_rsvp(session.id, k, "early") for k in range(week + year % 10))
    return sessions, attendance


def test_comparison_keeps_calendar_spacing_and_breaks_lines_at_missing_weeks():
    chart = _charts(_build(*_gapped_data()))[2]
    for season in ("2098 Fall/Winter", "2099 Fall/Winter"):
        rows = [r for r in chart.rows if r["season_label"] == season]
        assert [r["week_of_season"] for r in rows] == [1, 2, 12, 26, 28, 29]
        assert [r["segment"] for r in rows] == [0, 0, 1, 2, 3, 3]
    x = chart.spec["encoding"]["x"]
    assert x["type"] == "quantitative"
    assert x["scale"]["domainMin"] == 1 and x["scale"]["zero"] is False
    assert x["axis"]["tickMinStep"] == 1 and x["axis"]["format"] == "d"
    assert chart.spec["encoding"]["detail"] == {"field": "segment", "type": "nominal"}
    _render(chart)


@pytest.mark.parametrize("label, short", [("2025 Fall/Winter", "Fall 25"),
    ("2026 Spring/Summer", "Sum 26"), ("2099 Fall/Winter", "Fall 99"),
    ("Custom season", "Custom season")])
def test_short_season_label(label, short):
    assert ts._short_season_label(label) == short


def test_session_season_row_always_uses_short_labels_with_full_tooltip():
    chart = _charts(_build(*_long_data()))[0]
    row = next(layer for layer in chart.spec["layer"]
               if layer["mark"]["type"] == "text" and "season_label" in layer["data"]["values"][0])
    assert row["encoding"]["text"]["field"] == "short_label"
    assert [r["short_label"] for r in row["data"]["values"]] == ["Sum 97", "Fall 97", "Sum 98", "Fall 98"]
    assert {"field": "season_label", "type": "nominal", "title": "Season"} in row["encoding"]["tooltip"]


def test_bounded_capacity_counts_only_mondays_in_effect():
    sessions = [_session(i, day, season=season) for i, (day, season) in enumerate([
        (date(2098, 5, 8), "2098 Spring/Summer"),
        (date(2099, 9, 17), "2099 Fall/Winter"),
        (date(2099, 9, 24), "2099 Fall/Winter"),
        (date(2099, 10, 1), "2099 Fall/Winter"),
    ])]
    attendance = [_rsvp(s.id, k, "early") for s, n in zip(sessions, (40, 40, 30, 40)) for k in range(n)]
    lines = [{"value": 27, "label": "Open", "from": "2000-01-01"},
             {"value": 30, "label": "Temporary", "from": "2099-09-14", "to": "2099-09-21"}]
    with patch.object(ts, "load_history_config", return_value=SimpleNamespace(capacity_lines=lines)):
        blocks = _build(sessions, attendance)
    assert _tiles(blocks)["Weeks over 30"].value == "1 of 2 in effect"
    assert _tiles(blocks)["Weeks over 27"].value == "4 of 4"
    summary = next(b for b in blocks if isinstance(b, Table)).rows
    assert [r["over_30"] for r in summary] == ["", "1 of 2 in effect"]
    # The practice is inside this narrower window, but its Monday is outside.
    lines[1].update({"from": "2099-09-17", "to": "2099-09-20"})
    with patch.object(ts, "load_history_config", return_value=SimpleNamespace(capacity_lines=lines)):
        narrow = _build([sessions[1]], attendance)
    assert next(b for b in narrow if isinstance(b, Table)).rows[0]["over_30"] == ""
    assert _tiles(narrow)["Weeks over 30"].value == "No data"


@pytest.mark.parametrize("start,end,want_start,want_end", [
    ("2099-09-16", "2099-09-25", "2099-09-16", "2099-09-25"),
    ("2090-01-01", "2100-01-01", "2099-09-10", "2099-10-01"),
])
def test_bounded_capacity_segment_clamps_to_chart_domain(start, end, want_start, want_end):
    lines = [{"value": 27, "label": "Open", "from": "2099-09-20"},
             {"value": 30, "label": "Temporary", "from": start, "to": end}]
    with patch.object(ts, "load_history_config", return_value=SimpleNamespace(capacity_lines=lines)):
        chart = _charts(_build([_session(1), _session(2, FIRST + timedelta(days=7))], []))[0]
    rules = [layer for layer in chart.spec["layer"] if layer["mark"]["type"] == "rule"]
    bounded = next(rule for rule in rules if "x2" in rule["encoding"])
    enc = bounded["encoding"]
    assert enc["x"]["type"] == "temporal"
    row = bounded["data"]["values"][0]
    assert row[enc["x"]["field"]] == want_start
    assert row[enc["x2"]["field"]] == want_end
    assert any("x" not in rule["encoding"] for rule in rules)
    label = next(layer for layer in chart.spec["layer"] if layer["mark"]["type"] == "text"
                 and layer["data"]["values"] and layer["data"]["values"][0].get("value") == 30)
    assert label["encoding"]["x"]["field"] == enc["x2"]["field"]
    assert label["mark"]["align"] == "right" and label["mark"]["dx"] < 0
    _render(chart)


def test_season_axes_and_preference_rows_follow_summary_chronology():
    sessions, attendance = _long_data()
    blocks = _build(list(reversed(sessions)), attendance)
    order = ["2097 Spring/Summer", "2097 Fall/Winter", "2098 Spring/Summer", "2098 Fall/Winter"]
    summary = next(b for b in blocks if isinstance(b, Table))
    assert [r["season_label"] for r in summary.rows] == order
    preferences = ts.slot_preference(list(reversed(sessions)), attendance)
    assert list(dict.fromkeys(r["season_label"] for r in preferences)) == order
    for chart in (_charts(blocks)[1], _charts(blocks)[3]):
        layers = chart.spec.get("layer", [chart.spec])
        for layer in layers:
            x = layer["encoding"]["x"]
            assert x["sort"] == ["Sum 97", "Fall 97", "Sum 98", "Fall 98"]
            assert x["field"] == "short_label"
            assert any(t["field"] == "season_label" for t in layer["encoding"]["tooltip"])
        _render(chart)


def test_comparison_colors_identify_current_and_prior_seasons():
    chart = _charts(_build(*_gapped_data()))[2]
    scale = chart.spec["encoding"]["color"]["scale"]
    assert dict(zip(scale["domain"], scale["range"])) == {
        "2098 Fall/Winter": ts.charts.PALETTE["muted"], "2099 Fall/Winter": "#4a3aa7"}


@pytest.mark.parametrize("format", ["split", "merged"])
def test_unassigned_rsvps_are_in_totals_and_visible_only_when_needed(format):
    sessions = [_session(1, format=format)]
    blocks = _build(sessions, [_rsvp(1, 1, "early"), _rsvp(1, 2), _rsvp(1, 2)])
    chart = _charts(blocks)[0]
    assert chart.rows[0]["total"] == 2
    assert chart.rows[0]["unassigned"] == 1
    assert ("unassigned", "Button, no slot") in chart.columns
    assert _tiles(blocks)["Average per week"].value == "2.0"
    assert "Unassigned" in chart.spec["layer"][0]["encoding"]["color"]["scale"]["domain"]
    assigned = _charts(_build(sessions, [_rsvp(1, 1, "early")]))[0]
    assert "Unassigned" not in assigned.spec["layer"][0]["encoding"]["color"]["scale"]["domain"]
    _render(chart)


@pytest.mark.parametrize("days,shown", [(["Thursday"], False), (["Wednesday", "Thursday"], True)])
def test_multiple_selected_days_explain_weekly_sum(days, shown):
    blocks = _build([], [], Filters(days=days))
    note = "Weekly totals add every selected day, so a week with two lifts counts both nights."
    assert (note in [b.text for b in blocks if isinstance(b, Note)]) is shown
