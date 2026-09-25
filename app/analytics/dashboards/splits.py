"""Thursday strength decisions from RSVP counts, with no member-level output."""
from collections import defaultdict
from datetime import date, time, timedelta

from app.analytics import charts
from app.analytics.dashboards.base import Chart, Note, Table, Tile, Tiles
from app.analytics.history_config import load_history_config


def _session_rows(sessions, attendance):
    counts = defaultdict(lambda: defaultdict(set))
    for rsvp in attendance:
        if rsvp.role == "rsvp":
            counts[rsvp.session_id][rsvp.slot].add(rsvp.slack_uid)
    rows = []
    for session in sorted(sessions, key=lambda s: (s.date, s.start_time or time.min, s.id)):
        slots = counts[session.id]
        single = len(set().union(*slots.values())) if session.format == "single" else 0
        early = len(slots["early"]) if session.format != "single" else 0
        late = len(slots["late"]) if session.format != "single" else 0
        unassigned = len(slots[None] - slots["early"] - slots["late"]) if session.format != "single" else 0
        rows.append({"date": session.date.isoformat(), "season_label": session.season_label,
                     "format": session.format, "early": early, "late": late,
                     "single": single, "unassigned": unassigned,
                     "total": early + late + single + unassigned, "status": session.status})
    return rows


def weekly_totals(sessions, attendance) -> list[dict]:
    """Sum session RSVPs into Monday weeks, preserving split-only denominators."""
    weeks = {}
    for row in _session_rows(sessions, attendance):
        if row["status"] == "cancelled":
            continue
        day = date.fromisoformat(row["date"])
        monday = day - timedelta(days=day.weekday())
        key = (monday, row["season_label"])
        week = weeks.setdefault(key, {
            "week": monday, "season_label": row["season_label"], "formats": set(),
            "early": 0, "late": 0, "single": 0, "total": 0, "split_early": 0, "split_late": 0,
        })
        week["formats"].add(row["format"])
        for field in ("early", "late", "single", "total"):
            week[field] += row[field]
        if row["format"] == "split":
            week["split_early"] += row["early"]
            week["split_late"] += row["late"]
    return [{**week, "formats": sorted(week["formats"])} for _, week in sorted(weeks.items())]


def _late_share(weeks):
    early = sum(w["split_early"] for w in weeks)
    late = sum(w["split_late"] for w in weeks)
    return f"{late / (early + late):.0%}" if early + late else "N/A"


def _as_date(value):
    return value if isinstance(value, date) else date.fromisoformat(value)


def _weeks_over(weeks, line):
    """Use Monday dates for bounded lines; open-ended lines cover all history."""
    eligible = [w for w in weeks if not line.get("to") or
                _as_date(line["from"]) <= w["week"] <= _as_date(line["to"])]
    return sum(w["total"] > line["value"] for w in eligible), len(eligible)


def _capacity_count(weeks, line, *, empty=""):
    over, count = _weeks_over(weeks, line)
    if line.get("to"):
        return f"{over} of {count} in effect" if count else empty
    return over


def season_summary(weeks, lines) -> list[dict]:
    """Summarize observed weeks; a week exactly at capacity is not over it."""
    seasons = defaultdict(list)
    for week in weeks:
        seasons[week["season_label"]].append(week)
    return [{
        "season_label": season, "weeks": len(group),
        "avg": round(sum(w["total"] for w in group) / len(group), 1),
        "peak": max(w["total"] for w in group), "late_pct": _late_share(group),
        **{f"over_{line['value']}": _capacity_count(group, line) for line in lines},
    } for season, group in sorted(seasons.items(), key=lambda item: min(w["week"] for w in item[1]))]


def slot_preference(sessions, attendance) -> list[dict]:
    """Classify distinct people within each season using split and merged slots."""
    eligible = {s.id: s.season_label for s in sessions if s.format in ("split", "merged") and s.status != "cancelled"}
    starts = {}
    for session in sessions:
        if session.status != "cancelled":
            starts[session.season_label] = min(starts.get(session.season_label, session.date), session.date)
    seasons = {label: defaultdict(set) for label in eligible.values()}
    for rsvp in attendance:
        if rsvp.role == "rsvp" and rsvp.slot in ("early", "late") and rsvp.session_id in eligible:
            seasons[eligible[rsvp.session_id]][rsvp.slack_uid].add(rsvp.slot)
    categories = [("Early only", {"early"}), ("Late only", {"late"}), ("Both", {"early", "late"})]
    return [{"season_label": season, "preference": label,
             "people": sum(chosen == slots for chosen in people.values())}
            for season, people in sorted(seasons.items(), key=lambda item: starts[item[0]])
            for label, slots in categories]


def week_of_season(weeks) -> list[dict]:
    """Align the latest season and its prior-year type to their first observed week.

    Calendar gaps remain gaps, rather than moving a later week forward in time.
    """
    if not weeks:
        return []
    latest = max(weeks, key=lambda w: w["week"])["season_label"]
    year, _, season_type = latest.partition(" ")
    labels = {latest}
    if year.isdigit() and season_type:
        labels.add(f"{int(year) - 1} {season_type}")
    starts = {}
    for week in weeks:
        label = week["season_label"]
        starts[label] = min(starts.get(label, week["week"]), week["week"])
    rows, previous = [], {}
    segments = defaultdict(int)
    for week in sorted(weeks, key=lambda w: w["week"]):
        label = week["season_label"]
        if label not in labels:
            continue
        number = (week["week"] - starts[label]).days // 7 + 1
        if label in previous and number - previous[label] > 1:
            segments[label] += 1
        rows.append({"season_label": label, "week": week["week"].isoformat(),
                     "week_of_season": number, "total": week["total"], "segment": segments[label]})
        previous[label] = number
    return rows


def _short_season_label(label):
    year, _, season_type = label.partition(" ")
    names = {"Fall/Winter": "Fall", "Spring/Summer": "Sum"}
    if year.isdigit() and season_type in names:
        return f"{names[season_type]} {year[-2:]}"
    return label


def _capacity_lines(sessions):
    dates = [s.date for s in sessions]
    return [dict(line)
            for line in load_history_config().capacity_lines
            if not line.get("to") or (dates and _as_date(line["from"]) <= max(dates)
                                      and _as_date(line["to"]) >= min(dates))]


def _tiles(weeks, lines):
    if not weeks:
        labels = ["Average per week", *[f"Weeks over {line['value']}" for line in lines],
                  "Late session share", "Latest week"]
        return Tiles([Tile(label, "No data") for label in labels])
    totals = [w["total"] for w in weeks]
    tiles = [Tile("Average per week", f"{sum(totals) / len(totals):.1f}" if totals else "N/A",
                  f"RSVPs a week, peak {max(totals, default=0)}")]
    tiles.extend(Tile(f"Weeks over {line['value']}",
                      (_capacity_count(weeks, line, empty="No data") if line.get("to") else
                       f"{_capacity_count(weeks, line)} of {len(totals)}"), line["label"])
                 for line in lines)
    tiles.append(Tile("Late session share", _late_share(weeks), "of two-session RSVPs"))
    latest = max(weeks, key=lambda w: w["week"]) if weeks else None
    previous = None
    if latest:
        target = latest["week"] - timedelta(days=364)
        previous = next((w for w in weeks if abs((w["week"] - target).days) <= 3), None)
    tiles.append(Tile("Latest week", str(latest["total"]) if latest else "N/A",
                      f"Same week last year: {previous['total']}" if previous else ""))
    return Tiles(tiles)


def tiles(sessions, attendance):
    weeks = weekly_totals(sessions, attendance)
    return _tiles(weeks, _capacity_lines([s for s in sessions if s.status != "cancelled"]))


def split_blocks(sessions, attendance, filters):
    weeks = weekly_totals(sessions, attendance)
    lines = _capacity_lines([s for s in sessions if s.status != "cancelled"])
    rows = _session_rows(sessions, attendance)
    slots = [("early", "Early"), ("late", "Late"), ("single", "Single")]
    if any(row["unassigned"] for row in rows):
        slots.append(("unassigned", "Unassigned"))
    columns = [{**row, "slot": label, "rsvps": row[key], "slot_order": order}
               for row in rows for order, (key, label) in enumerate(slots)]
    dates = sorted({s.date for s in sessions})
    span = (dates[-1] - dates[0]).days + 14 if dates else 14
    gap = min(((right - left).days for left, right in zip(dates, dates[1:])), default=7)
    x_axis = {"labelAngle": 0, "labelOverlap": "greedy", "format": "%b %-d",
              "labelPadding": 16, "tickCount": {"expr": "max(2, floor(width / 85))"}, "grid": False}
    x_scale = {"type": "utc"}
    if dates:
        x_scale["domain"] = [(dates[0] - timedelta(days=7)).isoformat(),
                             (dates[-1] + timedelta(days=7)).isoformat()]
    opacity = {"condition": {"test": "datum.status === 'cancelled'", "value": 0.35}, "value": 1}
    session_body = charts.stacked_columns(
        columns, x="date", y="rsvps", color="slot", color_domain=[label for _, label in slots],
        color_range=[charts.PALETTE["muted" if key == "unassigned" else key] for key, _ in slots], x_title="Date", y_title="RSVPs",
        tooltip=["date", "season_label", "format", "slot", "rsvps", "status"], x_type="temporal")
    session_body["encoding"]["order"] = {"field": "slot_order", "type": "quantitative"}
    session_body["encoding"]["x"].update(axis=x_axis, scale=x_scale)
    session_body["encoding"]["opacity"] = opacity
    bar_size = {"expr": f"min(24, width * {gap * 0.85} / {span})"}
    session_body["mark"]["size"] = bar_size
    # White ticks cut only the horizontal segment joins, keeping thin bars visible.
    daily = defaultdict(lambda: {key: 0 for key, _ in slots})
    for row in rows:
        for key, _ in slots:
            daily[row["date"]][key] += row[key]
    boundaries = []
    for day, counts in daily.items():
        nonzero = [counts[key] for key, _ in slots if counts[key]]
        total = 0
        for count in nonzero[:-1]:
            total += count
            boundaries.append({"date": day, "boundary": total})
    segment_gaps = {
        "data": {"values": boundaries},
        "mark": {"type": "tick", "color": charts.PALETTE["surface"], "opacity": 1,
                 "orient": "horizontal", "thickness": 2, "size": bar_size},
        "encoding": {"x": {"field": "date", "type": "temporal", "scale": x_scale, "axis": x_axis},
                     "y": {"field": "boundary", "type": "quantitative", "title": "RSVPs"}},
    }
    session_body["transform"] = [{"filter": "datum.rsvps > 0"}]
    merged = {
        "data": {"values": [row for row in rows if row["format"] == "merged"]},
        "mark": {"type": "point", "filled": False, "shape": "circle", "size": 64,
                 "color": charts.PALETTE["ref"], "strokeWidth": 1.5, "yOffset": 8},
        "encoding": {"x": {"field": "date", "type": "temporal", "scale": x_scale, "axis": x_axis},
                     "opacity": opacity,
                     "y": {"value": "height"},
                     "tooltip": [{"field": "date"}, {"field": "format"},
                                 {"field": "total", "type": "quantitative", "title": "RSVPs"}]},
    }
    seasons = defaultdict(list)
    for session in sessions:
        seasons[session.season_label].append(session.date)
    season_labels = [{"date": (min(days) + (max(days) - min(days)) / 2).isoformat(),
                      "season_label": label,
                      "short_label": _short_season_label(label),
                      "span": (max(days) - min(days)).days + 14}
                     for label, days in seasons.items()]
    season_row = {
        "data": {"values": season_labels},
        "mark": {"type": "text", "color": charts.PALETTE["muted"], "baseline": "bottom",
                 "limit": {"expr": f"max(0, width * datum.span / {span} - 8)"}},
        "encoding": {"x": {"field": "date", "type": "temporal", "scale": x_scale, "axis": x_axis},
                     "y": {"value": -12}, "text": {"field": "short_label"},
                     "tooltip": [{"field": "season_label", "type": "nominal", "title": "Season"}]},
    }
    session_spec = charts.layered(
        session_body, segment_gaps, merged, season_row,
        *charts.reference_lines(lines, date_domain=x_scale.get("domain")))
    session_spec["padding"] = {"left": 5, "top": 28, "right": 12, "bottom": 5}
    session_description = "Early, late and single RSVPs are stacked by date, with rings below merged nights and capacity reference lines."
    session_chart = Chart(
        "Every strength session", session_description,
        charts.spec(session_description, session_spec),
        rows, [("date", "Date"), ("format", "Format"), ("early", "Early RSVPs"),
               ("late", "Late RSVPs"), ("single", "Single RSVPs"),
               *([("unassigned", "Button, no slot")] if any(r["unassigned"] for r in rows) else []),
               ("total", "Total RSVPs"), ("status", "Status")])

    summary = season_summary(weeks, lines)
    season_order = [_short_season_label(row["season_label"]) for row in summary]
    season_rows = [{"season_label": row["season_label"], "short_label": _short_season_label(row["season_label"]),
                    "measure": label, "rsvps": row[key]}
                   for row in summary for key, label in (("avg", "Average"), ("peak", "Peak"))]
    season_description = "Average and peak weekly RSVPs are compared by season."
    season_x = {"field": "short_label", "type": "ordinal", "sort": season_order,
                "title": ["Season", "Bars: average per week. Tick: peak week."],
                "axis": {"labelAngle": 0, "labelOverlap": "greedy"}}
    season_body = {
        "width": "container", "height": 260,
        "layer": [
            {"data": {"values": [r for r in season_rows if r["measure"] == "Average"]},
             "mark": {"type": "bar", "color": charts.PALETTE["violet"], "size": 24,
                      "cornerRadiusTopLeft": 4, "cornerRadiusTopRight": 4},
             "encoding": {"x": season_x,
                          "y": {"field": "rsvps", "type": "quantitative",
                                "title": "RSVPs"},
                          "tooltip": [{"field": "season_label"}, {"field": "rsvps", "title": "Average RSVPs"}]}},
            {"data": {"values": [r for r in season_rows if r["measure"] == "Peak"]},
             "mark": {"type": "tick", "color": charts.PALETTE["ink"], "size": 24,
                      "thickness": 2, "opacity": 1},
             "encoding": {"x": season_x,
                          "y": {"field": "rsvps", "type": "quantitative", "title": "RSVPs"},
                          "tooltip": [{"field": "season_label"}, {"field": "rsvps", "title": "Peak RSVPs"}]}}
        ],
    }
    season_chart = Chart(
        "Season by season", season_description, charts.spec(season_description, season_body),
        season_rows, [("season_label", "Season"), ("measure", "Measure"), ("rsvps", "RSVPs a week")])
    season_table = Table("Season summary", summary, [
        ("season_label", "Season"), ("weeks", "Weeks"), ("avg", "Average RSVPs"), ("peak", "Peak RSVPs"),
        *[(f"over_{line['value']}", f"Weeks over {line['value']}") for line in lines],
        ("late_pct", "Late %")])

    comparison = week_of_season(weeks)
    comparison_description = "Weekly RSVPs are plotted by week of season for the latest season and the same season type one year earlier."
    comparison_body = charts.line(
        comparison, x="week_of_season", y="total", color="season_label",
        x_title="Week of season", y_title="RSVPs", tooltip=["season_label", "week", "week_of_season", "total"])
    comparison_body["encoding"]["x"].update(
        type="quantitative",
        scale={"domainMin": 1, "domainMax": max([2, *[w["week_of_season"] for w in comparison]]),
               "zero": False, "nice": False},
        axis={"format": "d", "tickMinStep": 1})
    comparison_seasons = list(dict.fromkeys(row["season_label"] for row in comparison))
    current = max(weeks, key=lambda w: w["week"])["season_label"] if weeks else None
    comparison_body["encoding"]["color"]["scale"] = {
        "domain": comparison_seasons,
        "range": [charts.PALETTE["violet" if label == current else "muted"] for label in comparison_seasons],
    }
    comparison_body["encoding"]["detail"] = {"field": "segment", "type": "nominal"}
    if not comparison:
        # Vega's empty line legend produces an unbounded SVG height.
        comparison_body["encoding"]["color"]["legend"] = None
    comparison_chart = Chart(
        "This season against last", comparison_description,
        charts.spec(comparison_description, comparison_body),
        comparison, [("season_label", "Season"), ("week", "Week starting"),
                     ("week_of_season", "Week of season"), ("total", "RSVPs")])

    preferences = [{**row, "short_label": _short_season_label(row["season_label"])}
                   for row in slot_preference(sessions, attendance)]
    preference_description = "People who chose only early, only late or both slots are counted by season across split and merged sessions."
    preference_body = charts.grouped_bars(
        preferences, x="short_label", y="people", color="preference",
        color_domain=["Early only", "Late only", "Both"],
        color_range=[charts.PALETTE[key] for key in ("early", "late", "violet")],
        x_title="Season", y_title="People", tooltip=["season_label", "preference", "people"])
    preference_body["encoding"]["x"].update(
        sort=season_order, axis={"labelAngle": 0, "labelOverlap": "greedy"})
    preference_body["mark"].update(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
    preference_chart = Chart(
        "Who picks which slot", preference_description,
        charts.spec(preference_description, preference_body),
        preferences, [("season_label", "Season"), ("preference", "Slot preference"), ("people", "People")])

    return [session_chart, season_chart, season_table, comparison_chart, preference_chart,
            Note("RSVPs are not headcount. Some people RSVP and skip, some come without reacting, and leads often don't react."),
            Note("Merges happened on nights with low RSVPs, so merged weeks averaging fewer people does not mean merging lowers turnout."),
            Note("Cancelled nights appear faded in the session chart and are left out of every average."),
            *([Note("Weekly totals add every selected day, so a week with two lifts counts both nights.")]
              if len(filters.days) > 1 else [])]
