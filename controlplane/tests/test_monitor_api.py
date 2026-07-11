import pytest

from apps.monitors.models import Monitor

pytestmark = pytest.mark.django_db


def create_payload(org, **overrides):
    payload = {
        "organization": str(org.id),
        "name": "API check",
        "url": "https://example.com/health",
        "interval_seconds": 60,
    }
    payload.update(overrides)
    return payload


def test_create_monitor(api, org, regions):
    response = api.post("/api/v1/monitors/", create_payload(org), format="json")
    assert response.status_code == 201, response.data
    monitor = Monitor.objects.get(pk=response.data["id"])
    assert monitor.organization == org
    assert monitor.status == "unknown"


def test_interval_below_one_minute_rejected(api, org, regions):
    response = api.post("/api/v1/monitors/", create_payload(org, interval_seconds=30), format="json")
    assert response.status_code == 400
    assert "interval_seconds" in response.data


def test_invalid_expected_status_rejected(api, org, regions):
    response = api.post(
        "/api/v1/monitors/", create_payload(org, expected_status="banana"), format="json"
    )
    assert response.status_code == 400
    assert "expected_status" in response.data


def test_unknown_region_rejected(api, org, regions):
    response = api.post(
        "/api/v1/monitors/", create_payload(org, regions=["mars-north"]), format="json"
    )
    assert response.status_code == 400
    assert "regions" in response.data


def test_http_monitor_requires_url(api, org, regions):
    response = api.post(
        "/api/v1/monitors/",
        {"organization": str(org.id), "name": "No URL", "monitor_type": "http"},
        format="json",
    )
    assert response.status_code == 400
    assert "url" in response.data


def test_tcp_monitor_requires_host_and_port(api, org, regions):
    response = api.post(
        "/api/v1/monitors/",
        {"organization": str(org.id), "name": "TCP", "monitor_type": "tcp"},
        format="json",
    )
    assert response.status_code == 400

    response = api.post(
        "/api/v1/monitors/",
        {
            "organization": str(org.id),
            "name": "TCP",
            "monitor_type": "tcp",
            "host": "db.example.com",
            "port": 5432,
        },
        format="json",
    )
    assert response.status_code == 201


def traceroute_payload(org, **overrides):
    payload = {
        "organization": str(org.id),
        "name": "Path check",
        "monitor_type": "traceroute",
        "host": "edge.example.com",
    }
    payload.update(overrides)
    return payload


def test_traceroute_monitor_requires_host(api, org, regions):
    payload = traceroute_payload(org)
    del payload["host"]
    response = api.post("/api/v1/monitors/", payload, format="json")
    assert response.status_code == 400
    assert "host" in response.data


def test_create_traceroute_monitor(api, org, regions):
    response = api.post(
        "/api/v1/monitors/",
        traceroute_payload(org, hop_threshold_min=3, hop_threshold_max=20, required_asn=13335),
        format="json",
    )
    assert response.status_code == 201, response.data
    monitor = Monitor.objects.get(pk=response.data["id"])
    assert monitor.monitor_type == "traceroute"
    assert monitor.hop_threshold_min == 3
    assert monitor.hop_threshold_max == 20
    assert monitor.required_asn == 13335


def test_traceroute_hop_min_above_max_rejected(api, org, regions):
    response = api.post(
        "/api/v1/monitors/",
        traceroute_payload(org, hop_threshold_min=20, hop_threshold_max=3),
        format="json",
    )
    assert response.status_code == 400
    assert "hop_threshold_min" in response.data


def test_traceroute_asn_out_of_range_rejected(api, org, regions):
    response = api.post(
        "/api/v1/monitors/", traceroute_payload(org, required_asn=4294967296), format="json"
    )
    assert response.status_code == 400
    assert "required_asn" in response.data


def test_traceroute_check_task_payload(api, org, regions):
    response = api.post(
        "/api/v1/monitors/",
        traceroute_payload(org, hop_threshold_max=15, required_asn=3320),
        format="json",
    )
    assert response.status_code == 201, response.data
    monitor = Monitor.objects.get(pk=response.data["id"])
    task = monitor.to_check_task("eu-west", monitor.next_check_at)
    assert task["type"] == "traceroute"
    assert task["host"] == "edge.example.com"
    assert task["hop_threshold_min"] is None
    assert task["hop_threshold_max"] == 15
    assert task["required_asn"] == 3320


def test_pause_and_resume(api, monitor):
    assert api.post(f"/api/v1/monitors/{monitor.id}/pause/").status_code == 200
    monitor.refresh_from_db()
    assert monitor.is_paused is True

    assert api.post(f"/api/v1/monitors/{monitor.id}/resume/").status_code == 200
    monitor.refresh_from_db()
    assert monitor.is_paused is False


def test_regions_endpoint_lists_active(api, regions):
    response = api.get("/api/v1/regions/")
    assert response.status_code == 200
    assert {r["code"] for r in response.data} == {"eu-west", "us-east"}
