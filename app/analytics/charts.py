"""Small, composable Vega-Lite builders for read-only admin dashboards."""
from copy import deepcopy

SCHEMA = "https://vega.github.io/schema/vega-lite/v6.json"
PALETTE = {"navy": "#1c2c44", "early": "#2a78d6", "late": "#eb6834",
           "single": "#4a3aa7", "violet": "#4a3aa7", "surface": "#ffffff", "ref": "#6b7076", "grid": "#e3e5e6",
           "ink": "#1c2c44", "muted": "#6b7280"}


def theme() -> dict:
    return {
        "font": "-apple-system, BlinkMacSystemFont, sans-serif",
        "background": PALETTE["surface"],
        "view": {"stroke": None},
        "axis": {"labelColor": PALETTE["muted"], "titleColor": PALETTE["ink"],
                 "labelAngle": 0, "labelOverlap": "greedy", "gridColor": PALETTE["grid"], "domain": False, "tickColor": PALETTE["grid"]},
        "legend": {"orient": "bottom", "labelColor": PALETTE["ink"], "title": None},
        "range": {"category": [PALETTE[key] for key in ("early", "late", "violet")]},
    }


def _tooltip(fields, y):
    return [deepcopy(field) if isinstance(field, dict) else
            {"field": field, "type": "quantitative" if field == y else "nominal"}
            for field in fields]


def stacked_columns(rows, *, x, y, color, color_domain, color_range,
                    x_title, y_title, tooltip, height=280, x_type="ordinal", x_sort=None) -> dict:
    x_encoding = {"field": x, "type": x_type, "title": x_title}
    if x_sort is not None:
        x_encoding["sort"] = x_sort
    return {
        "data": {"values": deepcopy(rows)}, "width": "container", "height": height,
        "description": f"{y_title} by {x_title}",
        "mark": {"type": "bar", "opacity": 1, "size": 24},
        "encoding": {
            "x": x_encoding,
            "y": {"field": y, "type": "quantitative", "title": y_title, "stack": "zero"},
            "color": {"field": color, "type": "nominal",
                      "scale": {"domain": list(color_domain), "range": list(color_range)}},
            "tooltip": _tooltip(tooltip, y),
        },
    }


def grouped_bars(rows, *, x, y, color, color_domain, color_range,
                 x_title, y_title, tooltip, height=260, x_sort=None) -> dict:
    body = stacked_columns(rows, x=x, y=y, color=color, color_domain=color_domain,
                           color_range=color_range, x_title=x_title, y_title=y_title,
                           tooltip=tooltip, height=height, x_sort=x_sort)
    body["encoding"]["y"]["stack"] = None
    body["encoding"]["xOffset"] = {"field": color, "type": "nominal", "sort": list(color_domain)}
    return body


def line(rows, *, x, y, color, x_title, y_title, tooltip, height=260) -> dict:
    return {
        "data": {"values": deepcopy(rows)}, "width": "container", "height": height,
        "description": f"{y_title} by {x_title}",
        "mark": {"type": "line", "strokeWidth": 2, "point": {"filled": True, "size": 64}},
        "encoding": {
            "x": {"field": x, "type": "ordinal", "title": x_title},
            "y": {"field": y, "type": "quantitative", "title": y_title},
            "color": {"field": color, "type": "nominal"},
            "tooltip": _tooltip(tooltip, y),
        },
    }


def reference_lines(lines: list[dict], *, date_domain=None) -> list[dict]:
    """Draw open references full width and bounded references on the date axis."""
    open_lines, bounded = [], []
    for line in lines:
        row = {"value": line["value"], "label": line["label"]}
        if not line.get("to"):
            open_lines.append(row)
        elif date_domain:
            row.update(start=max(str(line["from"]), date_domain[0]),
                       end=min(str(line["to"]), date_domain[1]))
            if row["start"] <= row["end"]:
                bounded.append(row)
    layers = []
    for rows, is_bounded in ((open_lines, False), (bounded, True)):
        if not rows:
            continue
        y = {"field": "value", "type": "quantitative"}
        rule_encoding = {"y": y}
        label_x = {"value": "width"}
        label_mark = {"type": "text", "color": PALETTE["muted"], "align": "left", "dx": 8}
        if is_bounded:
            scale = {"type": "utc", "domain": list(date_domain)}
            rule_encoding.update(x={"field": "start", "type": "temporal", "scale": scale},
                                 x2={"field": "end"})
            label_x = {"field": "end", "type": "temporal", "scale": scale}
            # Keep bounded labels inside the segment end, away from margin labels.
            label_mark.update(align="right", dx=-4, dy=-8)
        layers.extend([
            {"data": {"values": deepcopy(rows)},
             "mark": {"type": "rule", "color": PALETTE["ref"], "strokeWidth": 1},
             "encoding": rule_encoding},
            {"data": {"values": deepcopy(rows)},
             "transform": [{"calculate": "width < 360 ? toString(datum.value) : datum.label",
                            "as": "display_label"}],
             "mark": label_mark,
             "encoding": {"x": label_x, "y": y,
                          "text": {"field": "display_label", "type": "nominal"}}},
        ])
    return layers


def layered(base: dict, *extra_layers) -> dict:
    child = deepcopy(base)
    body = {key: child.pop(key) for key in
            ("data", "height", "description", "config", "autosize") if key in child}
    child.pop("$schema", None)
    child.pop("width", None)
    return {**body, "$schema": SCHEMA, "width": "container",
            "description": body.get("description", "Chart with reference lines"),
            "layer": [child, *deepcopy(extra_layers)]}


def spec(description: str, body: dict) -> dict:
    return {**deepcopy(body), "$schema": SCHEMA, "config": theme(),
            "description": description, "autosize": {"type": "fit-x", "contains": "padding"}}


def factor_bars(rows, *, title) -> dict:
    height = max(80, 28 * len(rows))
    y = {"field": "value", "type": "nominal", "title": None, "sort": None}
    indices = [row["median_index"] for row in rows]
    domain = [min(0.5, min(indices) - 0.05), max(1.5, max(indices) + 0.05)] if indices else [0.5, 1.5]
    x = {"field": "median_index", "type": "quantitative", "title": "Median turnout index",
         "scale": {"domain": domain}}
    color = {"condition": {"test": "datum.median_index >= 1", "value": PALETTE["early"]}, "value": "#e34948"}
    text_encoding = {"y": y, "x": {"field": "median_index", "type": "quantitative"},
                      "text": {"field": "nights", "type": "quantitative"}}
    return {
        "data": {"values": deepcopy(rows)}, "width": "container", "height": height,
        "description": f"Median turnout index by {title}",
        "layer": [
            {"mark": {"type": "bar", "cornerRadiusEnd": 3, "clip": False},
             "encoding": {"y": y, "x": x, "x2": {"datum": 1}, "color": color,
                          "opacity": {"condition": {"test": "datum.thin", "value": 0.35}, "value": 1},
                          "tooltip": [{"field": "value", "title": title},
                                      {"field": "median_index", "title": "Median index"},
                                      {"field": "median_rsvps", "title": "Median RSVPs"},
                                      {"field": "nights", "title": "Practices"}]}},
            # Two static layers instead of a conditional mark property: align/dx on a
            # text mark can't be driven by an encoding condition in Vega-Lite.
            {"transform": [{"filter": "datum.median_index >= 1"}],
             "mark": {"type": "text", "align": "left", "dx": 4, "color": PALETTE["muted"]},
             "encoding": deepcopy(text_encoding)},
            {"transform": [{"filter": "datum.median_index < 1"}],
             "mark": {"type": "text", "align": "right", "dx": -4, "color": PALETTE["muted"]},
             "encoding": deepcopy(text_encoding)},
            {"data": {"values": [{"one": 1}]},
             "mark": {"type": "rule", "color": PALETTE["ref"], "strokeDash": [4, 3]},
             "encoding": {"x": {"field": "one", "type": "quantitative"}}},
        ],
    }


def points(rows, *, x, y, color, tooltip, color_scale=None, height=280) -> dict:
    color_encoding = {"field": color, "type": "nominal"}
    if color_scale is not None:
        color_encoding["scale"] = deepcopy(color_scale)
    return {
        "data": {"values": deepcopy(rows)}, "width": "container", "height": height,
        "description": f"{y} over time",
        "mark": {"type": "point", "filled": True, "size": 36, "opacity": 0.8},
        "encoding": {"x": {"field": x, "type": "temporal", "title": None},
                     "y": {"field": y, "type": "quantitative", "title": "RSVPs"},
                     "color": color_encoding,
                     "tooltip": _tooltip(tooltip, y)},
    }
