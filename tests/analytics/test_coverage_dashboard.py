"""Coverage dashboard checks with synthetic sessions and archive messages."""
import json
from datetime import date, datetime, timedelta
from unittest.mock import patch

import jsonschema
import pytest
import vl_convert as vlc

from app.analytics import CHANNELS, SYNC_CHANNELS
from app.analytics.dashboards import DASHBOARDS, coverage as cv
from app.analytics.dashboards.base import Chart, Filters, Note, Table, Tiles
from app.analytics.models import PracticeSession, SlackArchiveMessage
from app.models import AppConfig
from tests.analytics.conftest import FIXTURES

SCHEMA = json.loads((FIXTURES / "vega-lite-v6.schema.json").read_text())


def test_freshness():
    now = datetime(2099, 1, 3, 12)
    rows = cv.freshness([("C042G463AQ1", now - timedelta(hours=10)),
                         ("C02J1FDSBHT", now - timedelta(days=3))], now)
    assert [(r["channel"], r["fresh"]) for r in rows] == [
        ("announcements-practices", True), ("chat", False)]


def test_freshness_boundary_never_and_unknown_channel():
    now = datetime(2099, 1, 3, 12)
    rows = cv.freshness([("CFAKE0001", now - timedelta(hours=48)),
                         ("CFAKE0002", now - timedelta(hours=48, seconds=1)),
                         ("CFAKE0003", None)], now)
    assert rows == [
        {"channel": "CFAKE0001", "last_synced": "2099-01-01 06:00", "fresh": True, "fresh_display": "Yes"},
        {"channel": "CFAKE0002", "last_synced": "2099-01-01 05:59", "fresh": False, "fresh_display": "No"},
        {"channel": "CFAKE0003", "last_synced": "never", "fresh": False, "fresh_display": "No"}]


def test_weekly_counts_group_by_monday_and_kind():
    rows = cv.weekly_counts([(date(2099, 1, 6), "practice"), (date(2099, 1, 8), "practice"),
                             (date(2099, 1, 8), "event")])
    assert rows == [{"week": "2099-01-05", "kind": "event", "sessions": 1},
                    {"week": "2099-01-05", "kind": "practice", "sessions": 2}]


def test_weekly_counts_empty_and_week_boundaries():
    assert cv.weekly_counts([]) == []
    assert cv.weekly_counts([(date(2099, 1, 12), "trip"),
                             (date(2099, 1, 11), "trip"),
                             (date(2099, 1, 5), "trip")]) == [
        {"week": "2099-01-05", "kind": "trip", "sessions": 2},
        {"week": "2099-01-12", "kind": "trip", "sessions": 1}]


def test_build_with_empty_snapshot():
    with patch.object(cv, "_snapshot", return_value=None), \
         patch.object(cv, "_session_dates", return_value=[]), \
         patch.object(cv, "_sync_rows", return_value=[]), \
         patch.object(cv, "_soft_items", return_value=[]):
        blocks = cv.DASHBOARD.build(Filters())
    assert isinstance(blocks[0], Tiles)
    assert [t.value for t in blocks[0].tiles] == ["Not computed yet", "Not computed yet", "0 of 0", 0]
    chart = next(b for b in blocks if isinstance(b, Chart))
    jsonschema.validate(chart.spec, SCHEMA)
    assert chart.rows == []
    assert chart.spec["mark"]["size"] == {"expr": "min(24, width * 0.85 * 7 / 7)"}


@pytest.mark.parametrize("empty_weeks", [[], ["2099-01-12"]])
def test_build_snapshot_tables_and_valid_chart(empty_weeks):
    snapshot = {"computed_at": "2099-01-20T12:00:00", "empty_weeks": empty_weeks,
                "candidates": [{"post_key": "C02J1FDSBHT:4070908800.000001",
                                "channel": "C02J1FDSBHT", "date": "2099-01-01",
                                "text": "Synthetic club outing", "reactions": {"ski": 3, "thumbsup": 2}}]}
    soft = [{"date": "2099-01-06", "title": "Synthetic count-only practice", "flag": "identities_lost"}]
    with patch.object(cv, "_snapshot", return_value=snapshot), \
         patch.object(cv, "_session_dates", return_value=[(date(2099, 1, 6), "practice"),
                                                         (date(2099, 1, 8), "event"),
                                                         (date(2099, 1, 19), "trip")]), \
         patch.object(cv, "_sync_rows", return_value=[(SYNC_CHANNELS[0], datetime(2099, 1, 20)),
                                                     (SYNC_CHANNELS[1], None)]), \
         patch.object(cv, "_soft_items", return_value=soft), \
         patch.object(cv, "datetime") as clock:
        clock.utcnow.return_value = datetime(2099, 1, 20, 12)
        blocks = cv.DASHBOARD.build(Filters())
    assert [t.value for t in blocks[0].tiles] == [1, len(empty_weeks), "1 of 2", 1]
    tables = {b.title: b.rows for b in blocks if isinstance(b, Table)}
    assert tables["Unresolved candidates"] == [{**snapshot["candidates"][0],
                                              "channel": "chat", "reactions": "ski 3, thumbsup 2"}]
    assert snapshot["candidates"][0]["reactions"] == {"ski": 3, "thumbsup": 2}
    assert tables["Empty weeks"] == [{"week": week} for week in empty_weeks]
    assert tables["Soft items"] == soft
    assert [r["fresh"] for r in tables["Sync freshness"]] == [True, False]
    assert [r["fresh_display"] for r in tables["Sync freshness"]] == ["Yes", "No"]
    sync = next(b for b in blocks if isinstance(b, Table) and b.title == "Sync freshness")
    assert sync.columns == [("channel", "Channel"), ("last_synced", "Last synced (Central)"),
                            ("fresh_display", "Fresh")]
    chart = next(b for b in blocks if isinstance(b, Chart))
    jsonschema.validate(chart.spec, SCHEMA)
    assert vlc.vegalite_to_svg(chart.spec)
    assert chart.rows == [{"week": "2099-01-05", "kind": "event", "sessions": 1},
                          {"week": "2099-01-05", "kind": "practice", "sessions": 1},
                          {"week": "2099-01-19", "kind": "trip", "sessions": 1}]
    if empty_weeks:
        bars, gaps = chart.spec["layer"]
        assert gaps["data"]["values"] == [{"week": "2099-01-12"}]
        assert gaps["mark"] == {"type": "rule", "color": "#dc2626", "strokeWidth": 1}
        assert gaps["encoding"]["x"]["type"] == "temporal"
    else:
        bars = chart.spec
        assert "layer" not in chart.spec
    assert bars["mark"]["size"] == {"expr": "min(24, width * 0.85 * 7 / 21)"}
    assert bars["encoding"]["x"]["type"] == "temporal"
    assert bars["encoding"]["color"]["scale"]["domain"] == ["practice", "event", "trip"]
    assert isinstance(blocks[-1], Note)
    assert blocks[-1].text == ("Complete means zero unresolved candidates and zero empty weeks. "
                               "Claude resolves new candidates with catalog corrections.")


def test_computed_snapshot_with_no_gaps_shows_zero():
    with patch.object(cv, "_snapshot", return_value={"computed_at": "2099-01-20T12:00:00",
                                                   "candidates": [], "empty_weeks": []}), \
         patch.object(cv, "_session_dates", return_value=[]), \
         patch.object(cv, "_sync_rows", return_value=[]), \
         patch.object(cv, "_soft_items", return_value=[]):
        blocks = cv.build(Filters())
    assert [t.value for t in blocks[0].tiles[:2]] == [0, 0]


def test_snapshot_reads_stored_value(db_session):
    db_session.query(AppConfig).filter_by(key="analytics_coverage").delete()
    assert cv._snapshot() is None
    value = {"computed_at": "2099-01-20T12:00:00", "candidates": [], "empty_weeks": []}
    db_session.add(AppConfig(key="analytics_coverage", value=value))
    db_session.flush()
    assert cv._snapshot() == value


def test_sync_rows_uses_latest_sync_and_includes_never_synced(db_session):
    db_session.query(SlackArchiveMessage).delete()
    now = datetime(2099, 1, 3, 12)
    for i, (channel, synced) in enumerate([(SYNC_CHANNELS[0], now - timedelta(days=3)),
                                          (SYNC_CHANNELS[0], now), ("CFAKE0001", now)]):
        db_session.add(SlackArchiveMessage(channel_id=channel, ts=f"4070908800.{i:06d}",
                                           posted_at=now, synced_at=synced, text="Synthetic post", raw={}))
    db_session.flush()
    assert cv._sync_rows() == [(channel, now if channel == SYNC_CHANNELS[0] else None)
                              for channel in SYNC_CHANNELS]


def test_session_dates_and_soft_items_include_all_kinds(db_session):
    db_session.query(PracticeSession).delete()
    cases = [("trip", ["missing_date"]), ("practice", ["identities_lost", "unmatched_person", "other"]),
             ("event", ["unmatched_person"]), ("practice", ["other"])]
    for i, (kind, flags) in enumerate(cases, 1):
        db_session.add(PracticeSession(session_key=f"coverage:{i}", group_key=f"coverage:{i}",
                                       era="template", kind=kind, category="trip" if kind == "trip" else "practice",
                                       date=date(2099, 1, i), day_of_week=date(2099, 1, i).strftime("%A"),
                                       season_label="2098 Fall/Winter", title=f"Synthetic session {i}", flags=flags))
    db_session.flush()
    assert sorted(cv._session_dates()) == [(date(2099, 1, i), kind)
                                           for i, (kind, _) in enumerate(cases, 1)]
    assert cv._soft_items() == [
        {"date": "2099-01-01", "title": "Synthetic session 1", "flag": "missing_date"},
        {"date": "2099-01-02", "title": "Synthetic session 2", "flag": "identities_lost, unmatched_person"},
        {"date": "2099-01-03", "title": "Synthetic session 3", "flag": "unmatched_person"}]


def test_coverage_registry_and_no_filters():
    assert [dashboard.slug for dashboard in DASHBOARDS] == ["practices", "people", "coverage"]
    assert DASHBOARDS[-1] is cv.DASHBOARD
    assert cv.DASHBOARD.filters == []


def test_coverage_route_renders_dashboard(admin_client):
    response = admin_client.get("/admin/analytics/coverage")
    assert response.status_code == 200
    assert b"Data coverage" in response.data
    assert b"Is every club happening in the data, and what is missing?" in response.data
    assert b"Sync freshness" in response.data
    assert all(CHANNELS[channel].encode() in response.data for channel in SYNC_CHANNELS)


def test_coverage_route_requires_admin(client):
    assert client.get("/admin/analytics/coverage").status_code == 302


@pytest.mark.parametrize("synced, expected", [
    (datetime(2026, 1, 3, 2), "2026-01-02 20:00"),
    (datetime(2026, 7, 3, 2), "2026-07-02 21:00"),
])
def test_freshness_displays_central_but_compares_utc(synced, expected):
    row = cv.freshness([("CFAKE0001", synced)], synced + timedelta(hours=48))[0]
    assert row["last_synced"] == expected
    assert row["fresh"] is True


def test_weekly_bars_scale_to_long_history():
    dates = [(date(2023, 5, 1) + timedelta(weeks=i), "practice") for i in range(173)]
    with patch.object(cv, "_snapshot", return_value=None), \
         patch.object(cv, "_session_dates", return_value=dates), \
         patch.object(cv, "_sync_rows", return_value=[]), \
         patch.object(cv, "_soft_items", return_value=[]):
        blocks = cv.build(Filters())
    chart = next(b for b in blocks if isinstance(b, Chart))
    assert chart.spec["mark"]["size"] == {"expr": "min(24, width * 0.85 * 7 / 1211)"}
    jsonschema.validate(chart.spec, SCHEMA)
    assert vlc.vegalite_to_svg(chart.spec)
