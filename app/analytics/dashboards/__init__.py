"""Registry of dashboards, each defined in its own Python module."""
from app.analytics.dashboards.base import Dashboard
from app.analytics.dashboards.practices import DASHBOARD as PRACTICES
from app.analytics.dashboards.people import DASHBOARD as PEOPLE
from app.analytics.dashboards.coverage import DASHBOARD as COVERAGE

DASHBOARDS: list[Dashboard] = [PRACTICES, PEOPLE, COVERAGE]


def get_dashboard(slug) -> Dashboard | None:
    return next((dashboard for dashboard in DASHBOARDS if dashboard.slug == slug), None)
