"""What makes a practice draw: turnout by factor, normalized per season and weekday."""
from collections import defaultdict
from datetime import date
from statistics import median

from app.analytics import charts
from app.analytics.dashboards.base import (
    Chart, Dashboard, Filters, Note, Table, Tile, Tiles, load_attendance, load_sessions,
)
from app.analytics.dashboards.splits import split_blocks

FACTORS = [("activity", "Activity"), ("workout_type", "Workout"), ("location", "Location"),
           ("start_hour", "Start time"), ("temp_f", "Temperature"), ("precip_in", "Precipitation"),
           ("snow_depth_in", "Snow depth"), ("minutes_after_sunset", "Daylight"),
           ("week_band", "Week of season"), ("lead", "Lead")]

# The theme's category range only has 3 colors, so 6+ activities repeat colors on the
# turnout scatter. Group into a small palette instead; every other activity is "Other".
COLOR_GROUPS = ["Strength", "Ski", "Run"]
COLOR_GROUP_DOMAIN = COLOR_GROUPS + ["Other"]
COLOR_GROUP_RANGE = [charts.PALETTE["early"], charts.PALETTE["late"], "#1baf7a", "#9a9994"]


def color_group(activity):
    return activity if activity in COLOR_GROUPS else "Other"


def band(field, value):
    if value is None:
        return "Unknown"
    if field == "temp_f":
        for limit, label in ((15, "Below 15°F"), (32, "15 to 31°F"), (50, "32 to 49°F"), (70, "50 to 69°F")):
            if value < limit:
                return label
        return "70°F and up"
    if field == "precip_in":
        return "Dry" if value == 0 else "Light" if value < 0.1 else "Wet"
    if field == "snow_depth_in":
        return "No snow" if value == 0 else "Under 4 in" if value < 4 else "4 in or more"
    if field == "minutes_after_sunset":
        return "Before sunset" if value < 0 else "First hour after sunset" if value < 60 else "Dark"
    if field == "start_hour":
        return f"{value % 12 or 12} {'AM' if value < 12 else 'PM'}"
    return str(value)


def nights(sessions, attendance, *, status="held"):
    people = defaultdict(set)
    leads = set()
    attended = set()
    for row in attendance:
        if row.role == "rsvp":
            attended.add(row.session_id)
            people[row.session_id].add(row.person_key)
        elif row.role == "lead":
            leads.add(row.session_id)
    groups = defaultdict(list)
    for session in sessions:
        if session.status == status:
            groups[(session.group_key, session.date)].append(session)
    rows = []
    for (_, day), group in sorted(groups.items(), key=lambda item: item[0][1]):
        first = min(group, key=lambda s: (s.start_time is None, s.start_time))
        rows.append({
            "date": day.isoformat(), "season_label": first.season_label, "day_of_week": first.day_of_week,
            "activity": first.activity, "color_group": color_group(first.activity), "workout_type": first.workout_type,
            "location": first.location_name or "Unknown",
            "start_hour": first.start_time.hour if first.start_time else None,
            "temp_f": first.temp_f, "precip_in": first.precip_in, "snow_depth_in": first.snow_depth_in,
            "minutes_after_sunset": first.minutes_after_sunset,
            "has_lead": any(s.id in leads for s in group),
            "rsvps": len(set().union(*(people[s.id] for s in group))) +
                     sum(s.reported_count for s in group if s.reported_count is not None and s.id not in attended),
            "formats": sorted({s.format for s in group}),
            "status": status,
        })
    return rows


def baseline_medians(rows):
    """Return each season/weekday group's median and night count."""
    groups = defaultdict(list)
    for row in rows:
        groups[(row["season_label"], row["day_of_week"])].append(row["rsvps"])
    return {key: (median(values), len(values)) for key, values in groups.items()}


def with_index(rows, medians):
    out = []
    for row in rows:
        base, count = medians.get((row["season_label"], row["day_of_week"]), (None, 0))
        out.append({**row, "index": round(row["rsvps"] / base, 2) if base and count >= 3 else None})
    return out


def _week_bands(rows, starts):
    for row in rows:
        week = (date.fromisoformat(row["date"]) - date.fromisoformat(starts[row["season_label"]])).days // 7 + 1
        row["week_band"] = "Weeks 1 to 4" if week <= 4 else "Weeks 5 to 8" if week <= 8 else \
            "Weeks 9 to 12" if week <= 12 else "Week 13 on"
        row["lead"] = "Named lead" if row["has_lead"] else "No lead"
    return rows


def factor_rows(rows, key):
    groups = defaultdict(list)
    for row in rows:
        if row.get("index") is not None:
            value = row[key] if key in ("activity", "workout_type", "location", "week_band", "lead") \
                else band(key, row[key])
            groups[value].append(row)
    out = [{"value": value, "median_index": round(median(r["index"] for r in group), 2),
            "median_rsvps": median(r["rsvps"] for r in group), "nights": len(group),
            "thin": len(group) < 5} for value, group in groups.items()]
    return sorted(out, key=lambda r: -r["median_index"])


def load_baseline_sessions(filters):
    """All practices in the selected seasons, unfiltered by factor, so the index keeps its meaning."""
    baseline = Filters(seasons=filters.seasons, kinds=["practice"])
    sessions = load_sessions(baseline)
    return sessions, load_attendance([s.id for s in sessions], role=("rsvp", "lead"))


def _tiles(rows, people):
    if not rows:
        return Tiles([Tile(label, "No data") for label in
                      ("Practices", "Average RSVPs", "Distinct people", "Strongest draw", "Weakest draw")])
    by_activity = [r for r in factor_rows(rows, "activity") if not r["thin"]]
    return Tiles([
        Tile("Practices", len(rows)),
        Tile("Average RSVPs", f"{sum(r['rsvps'] for r in rows) / len(rows):.1f}"),
        Tile("Distinct people", people),
        Tile("Strongest draw", by_activity[0]["value"] if by_activity else "N/A",
             f"median index {by_activity[0]['median_index']}" if by_activity else ""),
        Tile("Weakest draw", by_activity[-1]["value"] if by_activity else "N/A",
             f"median index {by_activity[-1]['median_index']}" if by_activity else ""),
    ])


def build(filters):
    sessions = load_sessions(filters)
    attendance = load_attendance([s.id for s in sessions], role=("rsvp", "lead"))
    base_sessions, base_attendance = load_baseline_sessions(filters)
    baseline = nights(base_sessions, base_attendance)
    medians = baseline_medians(baseline)
    starts = {}
    for row in baseline:
        starts[row["season_label"]] = min(starts.get(row["season_label"], row["date"]), row["date"])
    rows = _week_bands(with_index(nights(sessions, attendance), medians), starts)
    held_ids = {s.id for s in sessions if s.status == "held"}
    people = len({row.person_key for row in attendance if row.role == "rsvp" and row.session_id in held_ids})
    blocks = [_tiles(rows, people)]
    time_rows = sorted(rows + [{**row, "index": None} for row in nights(sessions, attendance, status="cancelled")],
                       key=lambda row: row["date"])
    over_time = "Every practice night, colored by activity. Cancelled nights are faded."
    points = charts.points(time_rows, x="date", y="rsvps", color="color_group",
                           tooltip=["date", "activity", "location", "rsvps", "index", "status"],
                           color_scale={"domain": COLOR_GROUP_DOMAIN, "range": COLOR_GROUP_RANGE})
    points["encoding"]["color"]["legend"] = {"title": "Activity"}
    points["encoding"]["opacity"] = {
        "condition": {"test": "datum.status === 'cancelled'", "value": 0.35}, "value": 0.8}
    blocks.append(Chart("Turnout over time", over_time,
                        charts.spec(over_time, points),
                        time_rows, [("date", "Date"), ("activity", "Activity"), ("location", "Location"),
                                    ("rsvps", "RSVPs"), ("index", "Index"), ("status", "Status")]))
    for key, label in FACTORS:
        factor = factor_rows(rows, key)
        description = (f"Median turnout index by {label.lower()}. Bars run right of 1.0 when practices draw "
                       "more than a typical practice for that season and weekday, left when they draw fewer.")
        blocks.append(Chart(label, description, charts.spec(description, charts.factor_bars(factor, title=label)),
                            factor, [("value", label), ("median_index", "Median index"),
                                     ("median_rsvps", "Median RSVPs"), ("nights", "Practices")]))
    if any(set(row["formats"]) & {"split", "merged"} for row in rows):
        split_attendance = [row for row in attendance if row.role == "rsvp"]
        blocks.extend(split_blocks(sessions, split_attendance, filters))
    blocks.append(Table("Every practice", rows, [
        ("date", "Date"), ("day_of_week", "Day"), ("activity", "Activity"), ("workout_type", "Workout"),
        ("location", "Location"), ("rsvps", "RSVPs"), ("index", "Index"), ("temp_f", "Temp °F")]))
    blocks += [Note("Turnout index: a practice's RSVPs divided by the median for practices on the same "
                    "weekday in the same season. 1.2 means 20% above a typical practice for that slot. "
                    "When a filter keeps only one session of a split night, that night is compared against whole nights."),
               Note("Faded bars have fewer than 5 practices behind them. Read them as anecdotes."),
               Note("RSVPs are not headcount. Some people RSVP and skip, some come without reacting.")]
    return blocks


DASHBOARD = Dashboard(
    slug="practices", title="What makes a practice draw",
    question="Which days, times, activities, places and conditions bring people out?",
    filters=["season", "date_range", "day_of_week", "activity", "workout_type", "location", "format"],
    build=build, fixed={"kinds": ["practice"]},
)
