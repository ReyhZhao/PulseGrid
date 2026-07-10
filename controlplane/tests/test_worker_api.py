import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.monitors.scheduler import schedule_due_monitors

pytestmark = pytest.mark.django_db


def test_claim_requires_valid_token(db, regions):
    anonymous = APIClient()
    assert anonymous.post("/api/v1/worker/claim", {}, format="json").status_code in (401, 403)

    bad = APIClient()
    bad.credentials(HTTP_AUTHORIZATION="Bearer pgw_not-a-real-token")
    assert bad.post("/api/v1/worker/claim", {}, format="json").status_code == 401


def test_inactive_worker_is_rejected(worker_and_token):
    worker, token = worker_and_token
    worker.is_active = False
    worker.save()
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    assert client.post("/api/v1/worker/claim", {}, format="json").status_code == 401


def test_claim_returns_only_own_region_tasks(worker_api, monitor, regions):
    schedule_due_monitors()  # fans out to eu-west and us-east

    response = worker_api.post("/api/v1/worker/claim", {"max_tasks": 10}, format="json")
    assert response.status_code == 200
    assert response.data["region"] == "eu-west"
    tasks = response.data["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["region"] == "eu-west"

    # queue drained: next claim is empty
    response = worker_api.post("/api/v1/worker/claim", {"max_tasks": 10}, format="json")
    assert response.data["tasks"] == []


def test_submit_results_ingests_and_updates_state(worker_api, monitor):
    response = worker_api.post(
        "/api/v1/worker/results",
        {
            "results": [
                {
                    "monitor_id": str(monitor.id),
                    "checked_at": timezone.now().isoformat(),
                    "ok": True,
                    "latency_ms": 88.0,
                    "status_code": 200,
                    # region spoofing must be ignored; worker is bound to eu-west
                    "region": "us-east",
                }
            ]
        },
        format="json",
    )
    assert response.status_code == 200
    assert response.data["accepted"] == 1

    monitor.refresh_from_db()
    assert monitor.status == "up"
    assert monitor.region_states.get().region_code == "eu-west"


def test_submit_results_validates_shape(worker_api):
    response = worker_api.post("/api/v1/worker/results", {"results": "nope"}, format="json")
    assert response.status_code == 400


def test_heartbeat_updates_last_seen_and_reports_queue_depth(worker_api, worker_and_token):
    worker, _token = worker_and_token
    response = worker_api.post("/api/v1/worker/heartbeat", {"version": "1.2.3"}, format="json")
    assert response.status_code == 200
    assert response.data["region"] == "eu-west"
    assert response.data["queue_depth"] == 0

    worker.refresh_from_db()
    assert worker.last_seen_at is not None
    assert worker.version == "1.2.3"
