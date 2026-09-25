"""Read-only admin analytics pages."""
from flask import Blueprint, abort, redirect, render_template, request, url_for

from app.analytics import dashboards
from app.analytics.dashboards import base
from app.auth import admin_required

admin_analytics_bp = Blueprint("admin_analytics", __name__, url_prefix="/admin/analytics")


@admin_analytics_bp.get("/")
@admin_required
def index():
    return render_template("admin/analytics/index.html", dashboards=dashboards.DASHBOARDS)


@admin_analytics_bp.get("/<slug>")
@admin_required
def dashboard(slug):
    if slug == "thursday-strength":
        return redirect(url_for(".dashboard", slug="practices", activity="Strength",
                                day_of_week="Thursday"))
    definition = dashboards.get_dashboard(slug)
    if definition is None:
        abort(404)
    domains = base.get_filter_domains()
    filters = base.parse_filters(request.args, definition, domains)
    return render_template(
        "admin/analytics/dashboard.html", dashboard=definition, blocks=definition.build(filters),
        filters=filters, options=base.filter_options(definition, domains), footer=base.footer(),
        request_args=request.args,
    )
