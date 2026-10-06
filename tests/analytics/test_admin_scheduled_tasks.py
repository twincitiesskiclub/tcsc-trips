"""Manual analytics job discovery and dispatch, without external work."""
from unittest.mock import patch

import pytest


def test_analytics_is_listed_for_admin_run_now(admin_client):
    with patch("app.scheduler.get_scheduler_status", return_value={"running": False, "jobs": []}):
        response = admin_client.get("/admin/scheduled-tasks/status")
    assert response.status_code == 200
    jobs = [job for job in response.json["jobs"] if job["id"] == "analytics_nightly"]
    assert len(jobs) == 1
    assert jobs[0]["name"] == "Practice Analytics Nightly"
    assert jobs[0]["schedule"] == "Daily 3:30am"
    assert jobs[0]["category"] == "practices"
    assert jobs[0]["supports_channel_override"] is False
    assert jobs[0]["default_channel"] is None


@pytest.mark.parametrize("running", [False, True])
def test_manual_dispatch_uses_analytics_nightly_job(app, running):
    import app.scheduler as sched
    with patch.object(sched, "scheduler") as scheduler, \
         patch("app.analytics.jobs.run_nightly", return_value={"ok": True}) as nightly:
        scheduler.running = running
        result = sched.trigger_skipper_job_now(app, "analytics_nightly")
        assert result["status"] == ("scheduled" if running else "completed")
        if running:
            job = scheduler.add_job.call_args.kwargs
            assert job["func"] is sched.run_analytics_nightly_job
            assert job["args"] == [app]
            assert job["id"] == "manual_analytics_nightly"
            nightly.assert_not_called()
        else:
            nightly.assert_called_once_with()
