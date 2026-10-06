"""Admin fallback for two-week lead blocks."""

from unittest.mock import patch


def test_create_route_is_gone(admin_client):
    assert admin_client.post("/admin/availability/polls/create", json={}).status_code == 404


def test_open_route_uses_open_block_poll(admin_client, monkeypatch):
    calls = []
    monkeypatch.setattr("app.routes.admin_availability.open_block_poll",
                        lambda pid, who: calls.append((pid, who)) or {"success": True})
    response = admin_client.post("/admin/availability/polls/42/open")
    assert response.status_code == 200
    assert calls == [(42, None)]


def test_open_surfaces_errors_to_the_director(admin_client):
    with patch("app.routes.admin_availability.open_block_poll") as opener:
        opener.return_value = {"success": False, "error": "missing workspace emoji letter_c"}
        response = admin_client.post("/admin/availability/polls/1/open")

    assert response.status_code == 400
    assert "letter_c" in response.get_json()["error"]


def test_run_block_job_route(admin_client, monkeypatch):
    monkeypatch.setattr("app.routes.admin_availability.run_block_job", lambda: [{"start": "x"}])
    response = admin_client.post("/admin/availability/block-job/run")
    assert response.status_code == 200
    assert response.get_json()["results"] == [{"start": "x"}]


def test_dashboard_lists_polls(admin_client):
    response = admin_client.get("/admin/availability/")
    assert response.status_code == 200
    polls = response.get_json()["polls"]
    assert isinstance(polls, list)
    for p in polls:
        assert set(p) == {"id", "starts_on", "ends_on", "status", "sessions", "posted"}
