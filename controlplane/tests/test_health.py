"""Health probes must work no matter what Host header the kubelet sends."""

import pytest

pytestmark = pytest.mark.django_db

POD_IP_HOST = "10.42.5.60:8000"


def test_healthz_bypasses_allowed_hosts(client):
    response = client.get("/healthz", HTTP_HOST=POD_IP_HOST)
    assert response.status_code == 200


def test_readyz_bypasses_allowed_hosts(client, fake_redis):
    response = client.get("/readyz", HTTP_HOST=POD_IP_HOST)
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_other_paths_still_validate_host(client):
    response = client.get("/api/v1/regions/", HTTP_HOST=POD_IP_HOST)
    assert response.status_code == 400  # DisallowedHost


def test_readyz_reports_unavailable_when_redis_down(client, monkeypatch):
    from pulsegrid import queues

    def broken():
        raise ConnectionError("redis unreachable")

    monkeypatch.setattr(queues, "get_redis", broken)
    response = client.get("/readyz", HTTP_HOST=POD_IP_HOST)
    assert response.status_code == 503
