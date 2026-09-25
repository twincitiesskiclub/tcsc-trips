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
