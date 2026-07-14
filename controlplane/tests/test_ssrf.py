"""SSRF guard tests (#1 webhook channels, #2 monitor targets).

The guard is off in settings_test (so example.com fixtures stay hermetic); each
test here turns it on with override_settings and, where a hostname needs to
resolve, patches ``pulsegrid.netguard.resolve_ips`` to a controlled IP so no
real DNS is issued.
"""

import pytest
from django.test import override_settings

from pulsegrid import netguard

pytestmark = pytest.mark.django_db

GUARD_ON = override_settings(PULSEGRID_BLOCK_PRIVATE_TARGETS=True)

METADATA_IP = "169.254.169.254"


def test_ip_is_public_classification():
    assert netguard.ip_is_public("8.8.8.8") is True
    assert netguard.ip_is_public("1.1.1.1") is True
    assert netguard.ip_is_public(METADATA_IP) is False
    assert netguard.ip_is_public("10.0.0.5") is False
    assert netguard.ip_is_public("127.0.0.1") is False
    assert netguard.ip_is_public("192.168.1.1") is False
    assert netguard.ip_is_public("::1") is False
    assert netguard.ip_is_public("fd00:ec2::254") is False
    assert netguard.ip_is_public("::ffff:169.254.169.254") is False  # v4-mapped metadata


def test_blocked_reason_disabled_is_noop():
    with override_settings(PULSEGRID_BLOCK_PRIVATE_TARGETS=False):
        assert netguard.blocked_reason(METADATA_IP) is None


def _channel_payload(org, url, **config):
    return {
        "organization": str(org.id),
        "name": "hook",
        "channel_type": "webhook",
        "config": {"url": url, **config},
    }


@GUARD_ON
def test_webhook_channel_rejects_metadata_ip(api, org):
    payload = _channel_payload(org, f"http://{METADATA_IP}/latest/")
    resp = api.post("/api/v1/channels/", payload, format="json")
    assert resp.status_code == 400
    assert "config" in resp.data


@GUARD_ON
def test_webhook_channel_rejects_private_hostname(api, org, monkeypatch):
    monkeypatch.setattr(netguard, "resolve_ips", lambda host, port=None: ["10.1.2.3"])
    resp = api.post("/api/v1/channels/", _channel_payload(org, "https://internal.example/"), format="json")
    assert resp.status_code == 400


@GUARD_ON
def test_webhook_channel_rejects_non_string_headers(api, org):
    payload = _channel_payload(org, "https://hooks.example.com/pg", headers={"X-Auth": 12345})
    resp = api.post("/api/v1/channels/", payload, format="json")
    assert resp.status_code == 400


@GUARD_ON
def test_webhook_channel_allows_public_host(api, org, monkeypatch):
    monkeypatch.setattr(netguard, "resolve_ips", lambda host, port=None: ["93.184.216.34"])
    resp = api.post("/api/v1/channels/", _channel_payload(org, "https://hooks.example.com/pg"), format="json")
    assert resp.status_code == 201, resp.data


@GUARD_ON
def test_webhook_delivery_blocks_private_host_at_send_time(monkeypatch):
    # A channel that slipped past creation (or DNS-rebound) is still blocked
    # when the dispatcher actually tries to POST to it.
    monkeypatch.setattr(netguard, "resolve_ips", lambda host, port=None: ["10.0.0.9"])
    with pytest.raises(netguard.BlockedTargetError):
        netguard.assert_public_host("internal.example")


@GUARD_ON
def test_monitor_rejects_metadata_ip(api, org, regions):
    payload = {
        "organization": str(org.id),
        "name": "ssrf",
        "url": f"http://{METADATA_IP}/latest/meta-data/",
        "interval_seconds": 60,
    }
    resp = api.post("/api/v1/monitors/", payload, format="json")
    assert resp.status_code == 400
    assert "url" in resp.data


@GUARD_ON
def test_monitor_tcp_rejects_private_host(api, org, regions, monkeypatch):
    monkeypatch.setattr(netguard, "resolve_ips", lambda host, port=None: ["192.168.0.10"])
    payload = {
        "organization": str(org.id),
        "name": "portscan",
        "monitor_type": "tcp",
        "host": "db.internal",
        "port": 5432,
        "interval_seconds": 60,
    }
    resp = api.post("/api/v1/monitors/", payload, format="json")
    assert resp.status_code == 400
    assert "host" in resp.data


@GUARD_ON
def test_monitor_allows_unresolvable_host_at_creation(api, org, regions, monkeypatch):
    # Creation stays lenient for not-yet-live DNS; the worker re-checks at run
    # time. Simulate NXDOMAIN.
    def boom(host, port=None):
        raise OSError("nxdomain")

    monkeypatch.setattr(netguard, "resolve_ips", boom)
    payload = {
        "organization": str(org.id),
        "name": "future",
        "url": "https://not-live-yet.example/",
        "interval_seconds": 60,
    }
    resp = api.post("/api/v1/monitors/", payload, format="json")
    assert resp.status_code == 201, resp.data
