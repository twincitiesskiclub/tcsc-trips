"""Registry of dashboards, each defined in its own Python module."""
from app.analytics.dashboards.base import Dashboard
from app.analytics.dashboards.practices import DASHBOARD as PRACTICES

DASHBOARDS: list[Dashboard] = [PRACTICES]


def get_dashboard(slug) -> Dashboard | None:
    return next((dashboard for dashboard in DASHBOARDS if dashboard.slug == slug), None)
