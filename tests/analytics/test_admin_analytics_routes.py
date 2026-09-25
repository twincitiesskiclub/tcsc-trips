from unittest.mock import patch

import pytest

from app.analytics.dashboards import base
from app.analytics import dashboards
from app.analytics.dashboards.base import Chart, Dashboard, Note, Tile, Tiles


def _build(filters):
    return [Tiles([Tile("Average", "41.6", "RSVPs a week")]),
            Chart("Weekly", "Weekly RSVPs", {"$schema": "https://vega.github.io/schema/vega-lite/v6.json",
                                              "mark": "bar", "data": {"values": []}},
                  rows=[{"week": "2099-01-05", "rsvps": 3}], columns=[("week", "Week"), ("rsvps", "RSVPs")]),
            Note("RSVPs are not headcount.")]


REAL_FILTER_OPTIONS = base.filter_options

STUB = Dashboard(slug="stub", title="Stub", question="Does it render?",
                 filters=["season", "date_range"], build=_build)


@pytest.fixture(autouse=True)
def registry():
    with patch.object(dashboards, "DASHBOARDS", [STUB]), \
         patch.object(base, "get_filter_domains", return_value={"seasons": set(), "activities": set(),
                                                               "workout_types": set(), "location_ids": set()}), \
         patch.object(base, "footer", return_value={"data_through": "Sep 24, 2099", "needs_review": 3}), \
         patch.object(base, "filter_options", return_value={"seasons": [], "days": [], "formats": []}):
        yield


def test_requires_admin(client):
    assert client.get("/admin/analytics/").status_code in (302, 401)


def test_index_lists_dashboards(admin_client):
    r = admin_client.get("/admin/analytics/")
    assert r.status_code == 200 and b"Does it render?" in r.data


def test_dashboard_renders_blocks_and_footer(admin_client):
    r = admin_client.get("/admin/analytics/stub")
    html = r.data.decode()
    assert r.status_code == 200
    assert "41.6" in html and 'class="analytics-chart"' in html and "Show data" in html
    assert "3 sessions need review" in html and "RSVPs are not headcount" in html
    assert "vega-embed@" in html


def test_invalid_filter_values_are_ignored(admin_client):
    r = admin_client.get("/admin/analytics/stub?season=%3Cscript%3E&date_from=notadate&date_to=2099-99-99")
    assert r.status_code == 200
    assert b'value="<script>"' not in r.data
    assert b'&lt;script&gt;' not in r.data
    baseline = admin_client.get("/admin/analytics/stub").data
    assert r.data.count(b"<script>") == baseline.count(b"<script>")


def test_unknown_slug_404(admin_client):
    assert admin_client.get("/admin/analytics/nope").status_code == 404


def test_detail_requires_admin(client):
    assert client.get('/admin/analytics/stub').status_code in (302, 401)


def test_partial_dicts_render_and_index_does_not_load_vega(admin_client):
    with patch.object(base, 'footer', return_value={}), patch.object(base, 'filter_options', return_value={}):
        response = admin_client.get('/admin/analytics/stub')
    assert response.status_code == 200 and b'0 sessions need review' in response.data
    assert b'vega-embed@' not in admin_client.get('/admin/analytics/').data


def test_module_dispatch_and_all_filter_controls(admin_client):
    dashboard = Dashboard('all', 'All', 'Question?', list(base.FILTER_NAMES), lambda f: [
        base.Table('Table', [{'value': '</script><script>alert(1)</script>'}], [('value', 'Value')])])
    with patch.object(dashboards, 'get_dashboard', return_value=dashboard) as lookup, \
         patch.object(base, 'parse_filters', return_value=base.Filters()) as parse:
        response = admin_client.get('/admin/analytics/all')
    lookup.assert_called_once_with('all')
    parse.assert_called_once()
    assert response.status_code == 200
    html = response.data.decode()
    for label in ['Seasons', 'From', 'Through', 'Days', 'Activities', 'Workout types', 'Locations', 'Formats', 'Kinds']:
        assert label in html
    assert '&lt;script&gt;alert' in html
    assert 'method="get"' in html and 'analytics-table' in html


def test_empty_chart_keeps_description_and_table_without_embed_target(admin_client):
    empty = Chart("Empty weekly chart", "Weekly RSVPs for the selection.",
                  {"mark": "bar", "data": {"values": []}}, [], [("rsvps", "RSVPs")])
    with patch.object(STUB, "build", return_value=[empty]):
        response = admin_client.get("/admin/analytics/stub")
    assert response.status_code == 200
    html = response.data.decode()
    assert "Empty weekly chart" in html and "Weekly RSVPs for the selection." in html
    assert html.count("No data for these filters.") == 2
    assert "Show data" in html and '<td colspan="1">No data for these filters.</td>' in html
    assert 'class="analytics-chart"' not in html
    assert 'type="application/json"' not in html


def test_format_pills_have_readable_labels_and_preserve_query_values(admin_client):
    with patch.object(STUB, "filters", ["format"]), \
         patch.object(base, "filter_options", return_value={"formats": ["single", "split", "merged"]}):
        response = admin_client.get("/admin/analytics/stub?format=split")
    assert response.status_code == 200
    html = response.data.decode()
    for value, label in (("single", "One session"), ("split", "Two sessions"), ("merged", "Merged")):
        assert f'name="format" value="{value}"' in html
        assert f'<span class="admin-ui-pill">{label}</span>' in html
    assert 'name="format" value="split" checked' in html


def test_never_synced_footer(admin_client):
    with patch.object(base, "footer", return_value={"data_through": None, "needs_review": 0}):
        response = admin_client.get("/admin/analytics/stub")
    assert b"Data not yet synced" in response.data
    assert b"Data through not yet synced" not in response.data


def test_filter_domains_are_loaded_once_per_dashboard_request(admin_client):
    # Restore the real options builder hidden by the route fixture.
    with patch.object(base, "filter_options", REAL_FILTER_OPTIONS), \
         patch.object(base, "get_filter_domains", wraps=base.get_filter_domains) as domains:
        response = admin_client.get("/admin/analytics/stub")
    assert response.status_code == 200
    assert domains.call_count == 1
