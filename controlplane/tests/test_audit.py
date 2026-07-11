"""Audit trail: event capture, tenancy scoping and MSSP forwarding."""

import json

import pytest
import responses as responses_lib
from django.test import Client

from apps.audit.models import AuditEvent, Severity
from apps.audit.services import forward_event, record
from pulsegrid import queues

pytestmark = pytest.mark.django_db

MSSP_SETTINGS = {
    "URL": "https://vels.online",
    "TOKEN": "mssp-token",
    "AUTH_SCHEME": "Token",
    "ORG": "pulsegrid",
    "MIN_SEVERITY": "medium",
    "VERIFY_SSL": True,
    "HOST_NAME": "pulsegrid.vels.online",
}


@pytest.fixture
def mssp(settings):
    settings.PULSEGRID_MSSP = MSSP_SETTINGS
    return settings


# --- capture ---------------------------------------------------------------


def test_login_and_failed_login_are_audited(user):
    client = Client()
    client.login(username="alice", password="pw")
    assert AuditEvent.objects.filter(event_type="auth.login", actor="alice").exists()

    client.login(username="alice", password="wrong")
    failed = AuditEvent.objects.get(event_type="auth.login_failed")
    assert failed.severity == Severity.MEDIUM


def test_monitor_lifecycle_is_audited(api, org, regions, monitor):
    api.post(f"/api/v1/monitors/{monitor.id}/pause/")
    api.delete(f"/api/v1/monitors/{monitor.id}/")

    events = list(AuditEvent.objects.order_by("created_at").values_list("event_type", flat=True))
    assert "monitor.paused" in events
    assert "monitor.deleted" in events
    deleted = AuditEvent.objects.get(event_type="monitor.deleted")
    assert deleted.organization == org
    assert deleted.actor == "alice"
    assert deleted.severity == Severity.MEDIUM


def test_channel_changes_are_audited(api, org):
    response = api.post(
        "/api/v1/channels/",
        {
            "organization": str(org.id),
            "name": "Ops",
            "channel_type": "email",
            "config": {"to": ["ops@example.com"]},
        },
        format="json",
    )
    assert response.status_code == 201
    event = AuditEvent.objects.get(event_type="channel.created")
    assert event.severity == Severity.MEDIUM


def test_worker_auth_failure_is_audited(db, regions):
    from rest_framework.test import APIClient

    bad = APIClient()
    bad.credentials(HTTP_AUTHORIZATION="Bearer pgw_bogus")
    bad.post("/api/v1/worker/claim", {}, format="json")

    event = AuditEvent.objects.get(event_type="worker.auth_failed")
    assert event.severity == Severity.HIGH
    assert event.organization is None


def test_monitor_down_alert_is_audited(monitor):
    from apps.monitors.services import ingest_result
    from tests.test_ingestion import result_payload

    ingest_result(result_payload(monitor, ok=False), region_code="eu-west")
    event = AuditEvent.objects.get(event_type="monitor.alert_opened")
    assert event.severity == Severity.MEDIUM
    assert event.organization == monitor.organization


# --- MSSP forwarding queue ---------------------------------------------------


def test_low_severity_events_are_not_queued(mssp, fake_redis):
    record("test.info", "informational", severity=Severity.INFO)
    assert queues.pop_dispatch_job(timeout_seconds=0) is None


def test_high_severity_events_are_queued(mssp, fake_redis):
    event = record("test.high", "something bad", severity=Severity.HIGH)
    job = queues.pop_dispatch_job(timeout_seconds=0)
    assert job == ("audit", {"audit_event_id": event.id})


def test_nothing_is_queued_without_mssp_configured(fake_redis):
    record("test.high", "something bad", severity=Severity.HIGH)
    assert queues.pop_dispatch_job(timeout_seconds=0) is None


# --- MSSP delivery -----------------------------------------------------------


@responses_lib.activate
def test_forward_event_posts_v2_alert(mssp, org):
    responses_lib.add(responses_lib.POST, "https://vels.online/api/v2/alerts/", status=201)
    event = record(
        "monitor.deleted",
        "Monitor 'Example' deleted",
        severity=Severity.MEDIUM,
        actor="alice",
        actor_type="user",
        organization=org,
    )

    assert forward_event(event.id) is True

    request = responses_lib.calls[0].request
    assert request.headers["Authorization"] == "Token mssp-token"
    body = json.loads(request.body)
    assert body["org"] == "pulsegrid"
    assert body["source_kind"] == "external"
    assert body["severity"] == "medium"
    assert body["title"].startswith("[PulseGrid]")
    assert body["source_ref"]["system"] == "pulsegrid"
    assert body["entities"]["host.name"] == "pulsegrid.vels.online"
    assert body["entities"]["user.name"] == "alice"


@responses_lib.activate
def test_forward_event_raises_on_mssp_error_for_retry_logging(mssp):
    import requests

    responses_lib.add(responses_lib.POST, "https://vels.online/api/v2/alerts/", status=503)
    event = record("test.high", "boom", severity=Severity.HIGH)
    with pytest.raises(requests.HTTPError):
        forward_event(event.id)


def test_forward_unknown_event_is_noop(mssp):
    assert forward_event(999999) is False


# --- API tenancy -------------------------------------------------------------


def test_audit_api_is_org_scoped(api, other_api, org, other_org):
    record("test.event", "mine", organization=org)
    record("test.event", "theirs", organization=other_org)
    record("platform.event", "platform-wide", organization=None)

    mine = api.get("/api/v1/audit/")
    assert mine.status_code == 200
    assert [e["message"] for e in mine.data["results"]] == ["mine"]

    theirs = other_api.get("/api/v1/audit/")
    assert [e["message"] for e in theirs.data["results"]] == ["theirs"]


def test_audit_api_filters(api, org):
    record("a.b", "one", organization=org, severity=Severity.HIGH)
    record("c.d", "two", organization=org)
    response = api.get("/api/v1/audit/?severity=high")
    assert [e["message"] for e in response.data["results"]] == ["one"]
