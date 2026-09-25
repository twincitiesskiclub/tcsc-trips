"""Temporary wrapper; deleted when the practice dashboard ships (Task 12)."""
from app.analytics.dashboards.base import Dashboard, load_attendance, load_sessions
from app.analytics.dashboards.splits import split_blocks, tiles


def build(filters):
    sessions = load_sessions(filters)
    attendance = load_attendance([s.id for s in sessions])
    return [tiles(sessions, attendance), *split_blocks(sessions, attendance, filters)]


DASHBOARD = Dashboard(
    slug="thursday-strength", title="Thursday strength",
    question="Should Thursday strength run as one session or two?",
    filters=["season", "date_range", "day_of_week", "format"], build=build,
    fixed={"activities": ["Strength"], "kinds": ["practice"]}, defaults={"days": ["Thursday"]},
)
