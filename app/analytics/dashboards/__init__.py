"""Registry of dashboards, each defined in its own Python module."""
from app.analytics.dashboards.base import Dashboard
from app.analytics.dashboards.thursday_strength import DASHBOARD as THURSDAY_STRENGTH

DASHBOARDS: list[Dashboard] = [THURSDAY_STRENGTH]


def get_dashboard(slug) -> Dashboard | None:
    return next((dashboard for dashboard in DASHBOARDS if dashboard.slug == slug), None)
