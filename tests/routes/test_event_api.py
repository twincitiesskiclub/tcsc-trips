"""Wiring, shape, privacy and CORS for the public event API. Selection is
unit-tested in tests/events/test_selection.py, so most tests stub the query."""
from datetime import datetime, timedelta
from types import SimpleNamespace

import app.routes.event_api as event_api
from app import create_app


def _option(name, cents, order, active=True, description=""):
    return SimpleNamespace(
        name=name, description=description, price_cents=cents,
        member_price_cents=cents - 2000, sort_order=order, active=active,
    )


def _stub_event(**overrides):
    fields = dict(
        slug="dry-tri-2026",
        name="TCSC Roll, Ride, and Run Dry Tri 2026",
        location="Carver Park Reserve, Parley Lake, Victoria",
        description="Schedule of events\r\n\r\n- 7:30 AM: Packet pickup opens",
        event_date=datetime.utcnow() + timedelta(days=18),
        signup_start=datetime(2026, 7, 25, 5, 0),
        signup_end=datetime(2026, 10, 23, 4, 59),
        details_url="https://docs.google.com/document/d/x",
        discount_code="SECRET",
        capacity=200,
        status="active",
        audience="both",
        template_key="dry_tri",
        price_options=[
            _option("Run-only 6K", 3000, 2),
            _option("Individual Triathlon", 5500, 0, description="Complete all three legs yourself"),
            _option("Retired", 100, 1, active=False),
        ],
    )
    fields.update(overrides)
    return SimpleNamespace(**fields)


def _client(monkeypatch, events):
    monkeypatch.setattr(event_api, "_all_events", lambda: events)
    return create_app().test_client()


def test_returns_the_selected_event_with_the_public_shape(monkeypatch):
    body = _client(monkeypatch, [_stub_event()]).get("/api/events/dry-tri").get_json()

    event = body["event"]
    assert set(event) == {
        "slug", "name", "location", "description", "event_date", "signup_start",
        "signup_end", "registration_path", "details_url", "entries",
    }
    assert event["registration_path"] == "/events/dry-tri-2026"
    assert event["signup_end"] == "2026-10-23T04:59:00Z"
    assert event["description"].startswith("Schedule of events\r\n")
    assert body["generated_at"].endswith("Z")


def test_entries_are_active_options_in_sort_order_with_public_prices_only(monkeypatch):
    body = _client(monkeypatch, [_stub_event()]).get("/api/events/dry-tri").get_json()

    assert body["event"]["entries"] == [
        {"name": "Individual Triathlon", "description": "Complete all three legs yourself", "price_cents": 5500},
        {"name": "Run-only 6K", "description": "", "price_cents": 3000},
    ]


def test_never_leaks_member_pricing_or_the_discount_code(monkeypatch):
    raw = _client(monkeypatch, [_stub_event()]).get("/api/events/dry-tri").get_data(as_text=True)

    for secret in ("member_price", "SECRET", "discount", "capacity", "3500"):
        assert secret not in raw


def test_no_event_returns_null_not_404(monkeypatch):
    resp = _client(monkeypatch, []).get("/api/events/dry-tri")
    assert resp.status_code == 200
    assert resp.get_json()["event"] is None


def test_unknown_series_is_404(monkeypatch):
    assert _client(monkeypatch, []).get("/api/events/pickleball").status_code == 404


def test_cors_and_cache_headers(monkeypatch):
    resp = _client(monkeypatch, [_stub_event()]).get(
        "/api/events/dry-tri", headers={"Origin": "https://twincitiesskiclub.org"}
    )
    assert resp.headers["Access-Control-Allow-Origin"] == "https://twincitiesskiclub.org"
    assert resp.headers["Vary"] == "Origin"
    assert resp.headers["Cache-Control"] == "public, max-age=300"


def test_disallowed_origin_gets_no_cors_header(monkeypatch):
    resp = _client(monkeypatch, [_stub_event()]).get(
        "/api/events/dry-tri", headers={"Origin": "https://evil.example"}
    )
    assert "Access-Control-Allow-Origin" not in resp.headers
