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


def test_readyz_reports_unavailable_when_redis_down(client, monkeypatch, caplog):
    from pulsegrid import queues

    def broken():
        raise ConnectionError("redis unreachable at 10.42.0.9:6379")

    monkeypatch.setattr(queues, "get_redis", broken)
    with caplog.at_level("WARNING", logger="pulsegrid.views"):
        response = client.get("/readyz", HTTP_HOST=POD_IP_HOST)

    assert response.status_code == 503
    # The failing component is still named for whoever curls the probe...
    assert response.json()["problems"] == ["redis"]
    # ...but the driver's own message — which carries infra detail — stays in
    # the pod log rather than in an unauthenticated HTTP response.
    assert "10.42.0.9:6379" not in response.content.decode()
    assert any("10.42.0.9:6379" in message for message in caplog.messages)
