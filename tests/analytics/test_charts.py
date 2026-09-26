import json

import jsonschema
import pytest

from app.analytics import charts
from tests.analytics.conftest import FIXTURES

SCHEMA = json.loads((FIXTURES / "vega-lite-v6.schema.json").read_text())
ROWS = [{"week": "2099-01-05", "slot": "Early", "rsvps": 20},
        {"week": "2099-01-05", "slot": "Late", "rsvps": 12}]


def _check(spec):
    jsonschema.validate(spec, SCHEMA)
    import vl_convert as vlc
    png = vlc.vegalite_to_png(json.dumps({**spec, "width": 600}))
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_stacked_columns_with_reference_lines_validates_and_renders():
    base = charts.stacked_columns(
        ROWS, x="week", y="rsvps", color="slot", color_domain=["Early", "Late"],
        color_range=[charts.PALETTE["early"], charts.PALETTE["late"]],
        x_title="Week", y_title="RSVPs", tooltip=["week", "slot", "rsvps"])
    s = charts.spec("RSVPs per week", charts.layered(
        base, *charts.reference_lines([{"value": 27, "label": "27 split rule"}])))
    assert s["description"] == "RSVPs per week"
    _check(s)


@pytest.mark.parametrize("builder", ["grouped_bars", "line"])
def test_other_builders_validate(builder):
    fn = getattr(charts, builder)
    s = charts.spec("x", fn(ROWS, x="week", y="rsvps", color="slot",
                            **({"color_domain": ["Early", "Late"],
                                "color_range": ["#000", "#111"]} if builder == "grouped_bars" else {}),
                            x_title="Week", y_title="RSVPs", tooltip=["rsvps"]))
    _check(s)


@pytest.mark.parametrize('name', ['early', 'late', 'single', 'violet', 'ref'])
def test_series_contrast_against_white(name):
    rgb = [int(charts.PALETTE[name][i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in rgb]
    luminance = sum(v * weight for v, weight in zip(linear, (0.2126, 0.7152, 0.0722)))
    assert 1.05 / (luminance + 0.05) >= 3


def test_layering_preserves_dimensions_and_does_not_mutate_base():
    body = charts.stacked_columns(ROWS, x='week', y='rsvps', color='slot',
        color_domain=['Early', 'Late'], color_range=['#000', '#111'],
        x_title='Week', y_title='RSVPs', tooltip=['rsvps'], height=310,
        x_type='temporal', x_sort='descending')
    before = json.dumps(body, sort_keys=True)
    result = charts.layered(body, *charts.reference_lines([{'value': 27, 'label': 'Capacity'}]))
    assert result['height'] == 310 and result['width'] == 'container'
    assert result['data'] == body['data']
    assert 'data' not in result['layer'][0]
    assert json.dumps(body, sort_keys=True) == before
    _check(charts.spec('Temporal series', result))


def test_series_palette_and_reference_line_presentation():
    assert charts.PALETTE["single"] == "#4a3aa7"
    assert charts.PALETTE["violet"] == "#4a3aa7"
    assert charts.PALETTE["navy"] not in charts.theme()["range"]["category"]
    rule, label = charts.reference_lines([{"value": 27, "label": "Split rule"}])
    assert rule["mark"].get("strokeDash", []) == []
    assert rule["mark"]["strokeWidth"] == 1
    assert label["mark"]["align"] == "left"
    assert label["mark"]["color"] in (charts.PALETTE["ink"], charts.PALETTE["muted"])


def test_line_weight_and_point_size():
    body = charts.line(ROWS, x="week", y="rsvps", color="slot", x_title="Week",
                       y_title="RSVPs", tooltip=["rsvps"])
    assert body["mark"]["strokeWidth"] == 2
    assert body["mark"]["point"]["size"] >= 64


def test_factor_bars_validate_and_render_with_thin_groups():
    rows = [{"value": "Run", "median_index": 1.2, "median_rsvps": 24, "nights": 5, "thin": False},
            {"value": "Ski", "median_index": 0.8, "median_rsvps": 16, "nights": 2, "thin": True}]
    body = charts.factor_bars(rows, title="Activity")
    bar, high_label, low_label, rule = body["layer"]
    assert bar["encoding"]["opacity"] == {"condition": {"test": "datum.thin", "value": 0.35}, "value": 1}
    assert bar["encoding"]["x"]["field"] == "median_index"
    assert bar["encoding"]["y"]["field"] == "value"
    assert high_label["encoding"]["text"]["field"] == "nights"
    assert low_label["encoding"]["text"]["field"] == "nights"
    assert rule["data"]["values"] == [{"one": 1}]
    assert rule["encoding"]["x"]["field"] == "one"
    _check(charts.spec("Median turnout by activity", body))


def test_factor_bars_diverge_from_one_with_computed_domain_and_color_condition():
    rows = [{"value": "Run", "median_index": 1.8, "median_rsvps": 24, "nights": 5, "thin": False},
            {"value": "Ski", "median_index": 0.3, "median_rsvps": 6, "nights": 2, "thin": True}]
    body = charts.factor_bars(rows, title="Activity")
    bar, high_label, low_label, rule = body["layer"]
    assert bar["encoding"]["x2"] == {"datum": 1}
    assert bar["encoding"]["color"] == {
        "condition": {"test": "datum.median_index >= 1", "value": charts.PALETTE["early"]},
        "value": "#e34948"}
    assert bar["encoding"]["x"]["scale"] == {"domain": [0.25, 1.85]}
    assert bar["mark"]["clip"] is False
    assert high_label["mark"] == {"type": "text", "align": "left", "dx": 4, "color": charts.PALETTE["muted"]}
    assert high_label["transform"] == [{"filter": "datum.median_index >= 1"}]
    assert low_label["mark"] == {"type": "text", "align": "right", "dx": -4, "color": charts.PALETTE["muted"]}
    assert low_label["transform"] == [{"filter": "datum.median_index < 1"}]
    assert rule["mark"]["strokeDash"] == [4, 3]
    _check(charts.spec("Median turnout by activity", body))


def test_factor_bars_domain_falls_back_when_no_rows():
    body = charts.factor_bars([], title="Activity")
    bar = body["layer"][0]
    assert bar["encoding"]["x"]["scale"]["domain"] == [0.5, 1.5]


def test_factor_bar_text_layers_have_independent_encodings():
    body = charts.factor_bars([], title="Activity")
    high_label, low_label = body["layer"][1:3]
    high_label["encoding"]["text"]["field"] = "median_rsvps"
    assert low_label["encoding"]["text"]["field"] == "nights"


def test_points_validate_and_render_temporal_turnout():
    body = charts.points(ROWS, x="week", y="rsvps", color="slot", tooltip=["week", "slot", "rsvps"])
    assert body["encoding"]["x"]["type"] == "temporal"
    assert body["encoding"]["y"]["type"] == "quantitative"
    assert body["encoding"]["color"]["type"] == "nominal"
    _check(charts.spec("Turnout over time", body))


def test_points_accepts_color_scale():
    body = charts.points(ROWS, x="week", y="rsvps", color="slot", tooltip=["week", "slot", "rsvps"],
                         color_scale={"domain": ["Early", "Late"], "range": ["#111111", "#222222"]})
    assert body["encoding"]["color"]["scale"] == {"domain": ["Early", "Late"], "range": ["#111111", "#222222"]}
    _check(charts.spec("Turnout over time", body))
