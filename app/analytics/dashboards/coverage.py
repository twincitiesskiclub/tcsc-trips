"""Is the data set complete? Candidates, empty weeks, sync freshness, soft items."""
from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import func

from app import utils
from app.analytics import CHANNELS, SYNC_CHANNELS, charts
from app.analytics.dashboards.base import Chart, Dashboard, Note, Table, Tile, Tiles
from app.analytics.models import PracticeSession, SlackArchiveMessage
from app.models import AppConfig, db

SOFT_FLAGS = ["identities_lost", "unmatched_person", "missing_date"]


def freshness(rows, now):
    out = []
    for channel, synced in rows:
        fresh = bool(synced) and now - synced <= timedelta(hours=48)
        out.append({"channel": CHANNELS.get(channel, channel),
                    "last_synced": utils.format_datetime_central(synced, "%Y-%m-%d %H:%M") if synced else "never",
                    "fresh": fresh, "fresh_display": "Yes" if fresh else "No"})
    return out


def weekly_counts(rows):
    counts = defaultdict(int)
    for day, kind in rows:
        counts[((day - timedelta(days=day.weekday())).isoformat(), kind)] += 1
    return [{"week": week, "kind": kind, "sessions": n} for (week, kind), n in sorted(counts.items())]


def _snapshot():
    return AppConfig.get("analytics_coverage")


def _session_dates():
    return db.session.query(PracticeSession.date, PracticeSession.kind).all()


def _sync_rows():
    found = dict(db.session.query(SlackArchiveMessage.channel_id, func.max(SlackArchiveMessage.synced_at))
                 .filter(SlackArchiveMessage.channel_id.in_(SYNC_CHANNELS))
                 .group_by(SlackArchiveMessage.channel_id).all())
    return [(channel, found.get(channel)) for channel in SYNC_CHANNELS]


def _soft_items():
    rows = PracticeSession.query.filter(PracticeSession.flags.overlap(SOFT_FLAGS)).order_by(
        PracticeSession.date).all()
    return [{"date": s.date.isoformat(), "title": s.title,
             "flag": ", ".join(f for f in s.flags if f in SOFT_FLAGS)} for s in rows]


def build(filters):
    snapshot = _snapshot()
    sync = freshness(_sync_rows(), datetime.utcnow())
    soft = _soft_items()
    candidates = snapshot["candidates"] if snapshot else []
    empty = snapshot["empty_weeks"] if snapshot else []
    tiles = Tiles([
        Tile("Unresolved candidates", len(candidates) if snapshot else "Not computed yet"),
        Tile("Empty weeks", len(empty) if snapshot else "Not computed yet"),
        Tile("Channels synced", f"{sum(r['fresh'] for r in sync)} of {len(sync)}", "in the last 48 hours"),
        Tile("Soft items", len(soft), "count-only, unmatched, undated"),
    ])
    candidate_rows = [{**row, "channel": CHANNELS.get(row["channel"], row["channel"]),
                       "reactions": ", ".join(f"{name} {n}" for name, n in row["reactions"].items())}
                      for row in candidates]
    weeks = weekly_counts(_session_dates())
    description = "Sessions per week by kind across all history. Red lines are weeks inside a practice season with no practice."
    body = charts.stacked_columns(weeks, x="week", y="sessions", color="kind",
                                  color_domain=["practice", "event", "trip"],
                                  color_range=[charts.PALETTE["violet"], charts.PALETTE["early"], charts.PALETTE["late"]],
                                  x_title="Week", y_title="Sessions", tooltip=["week", "kind", "sessions"],
                                  x_type="temporal")
    span_days = (date.fromisoformat(weeks[-1]["week"]) -
                 date.fromisoformat(weeks[0]["week"])).days + 7 if weeks else 7
    body["mark"]["size"] = {"expr": f"min(24, width * 0.85 * 7 / {span_days})"}
    gaps = {"data": {"values": [{"week": week} for week in empty]},
            "mark": {"type": "rule", "color": "#dc2626", "strokeWidth": 1},
            "encoding": {"x": {"field": "week", "type": "temporal"}}}
    chart_spec = charts.spec(description, charts.layered(body, gaps) if empty else body)
    return [
        tiles,
        Table("Unresolved candidates", candidate_rows, [("date", "Posted"), ("channel", "Channel"),
                                                        ("text", "Text"), ("reactions", "Top reactions"),
                                                        ("post_key", "Post key")]),
        Chart("Sessions per week", description, chart_spec, weeks,
              [("week", "Week of"), ("kind", "Kind"), ("sessions", "Sessions")]),
        Table("Empty weeks", [{"week": week} for week in empty], [("week", "Week of")]),
        Table("Sync freshness", sync, [("channel", "Channel"), ("last_synced", "Last synced (Central)"),
                                       ("fresh_display", "Fresh")]),
        Table("Soft items", soft, [("date", "Date"), ("title", "Session"), ("flag", "Flag")]),
        Note("Complete means zero unresolved candidates and zero empty weeks. "
             "Claude resolves new candidates with catalog corrections."),
    ]


DASHBOARD = Dashboard(slug="coverage", title="Data coverage",
                      question="Is every club happening in the data, and what is missing?",
                      filters=[], build=build)
