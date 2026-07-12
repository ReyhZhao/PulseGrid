"""Result ingestion, status transitions, alert events and SSL alerting."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.alerts.models import AlertEvent
from apps.monitors.models import CheckResult, Monitor, MonitorStatus
from apps.monitors.services import ingest_result, monitor_stats
from pulsegrid import queues

pytestmark = pytest.mark.django_db


def result_payload(monitor, ok=True, **overrides):
    payload = {
        "monitor_id": str(monitor.id),
        "checked_at": timezone.now().isoformat(),
        "ok": ok,
        "latency_ms": 123.4 if ok else None,
        "status_code": 200 if ok else None,
        "error": "" if ok else "connection refused",
    }
    payload.update(overrides)
    return payload


def test_ok_result_marks_monitor_up(monitor):
    result = ingest_result(result_payload(monitor), region_code="eu-west")
    assert result is not None

    monitor.refresh_from_db()
    assert monitor.status == MonitorStatus.UP
    state = monitor.region_states.get(region_code="eu-west")
    assert state.status == MonitorStatus.UP
    assert state.last_latency_ms == 123.4


def test_failure_below_threshold_does_not_alert(monitor):
    monitor.failure_threshold = 2
    monitor.save()

    ingest_result(result_payload(monitor, ok=True), region_code="eu-west")
    ingest_result(result_payload(monitor, ok=False), region_code="eu-west")

    monitor.refresh_from_db()
    assert monitor.status == MonitorStatus.UP
    assert AlertEvent.objects.count() == 0


def test_reaching_threshold_opens_down_event_and_queues_notification(monitor, fake_redis):
    monitor.failure_threshold = 2
    monitor.save()

    ingest_result(result_payload(monitor, ok=False), region_code="eu-west")
    ingest_result(result_payload(monitor, ok=False), region_code="eu-west")

    monitor.refresh_from_db()
    assert monitor.status == MonitorStatus.DOWN
    event = AlertEvent.objects.get()
    assert event.event_type == AlertEvent.Type.DOWN
    assert event.status == AlertEvent.Status.OPEN
    assert event.details["error"] == "connection refused"
    assert event.details["region"] == "eu-west"
    assert event.details["region_errors"] == [
        {
            "region": "eu-west",
            "error": "connection refused",
            "status_code": None,
            "consecutive_failures": 2,
        }
    ]
    assert queues.pop_notification(timeout_seconds=0) == {"event_id": event.id}

    # continued failures must not open duplicate events
    ingest_result(result_payload(monitor, ok=False), region_code="eu-west")
    assert AlertEvent.objects.count() == 1


def test_recovery_resolves_event_and_notifies(monitor, fake_redis):
    ingest_result(result_payload(monitor, ok=False), region_code="eu-west")
    ingest_result(result_payload(monitor, ok=True), region_code="eu-west")

    monitor.refresh_from_db()
    assert monitor.status == MonitorStatus.UP
    event = AlertEvent.objects.get()
    assert event.status == AlertEvent.Status.RESOLVED
    assert event.resolved_at is not None
    # one notification for open, one for resolve
    assert queues.pop_notification(timeout_seconds=0) is not None
    assert queues.pop_notification(timeout_seconds=0) is not None


def test_confirmations_require_multiple_regions_down(org, regions):
    monitor = Monitor.objects.create(
        organization=org, name="Multi", url="https://example.com", confirmations=2
    )
    ingest_result(result_payload(monitor, ok=True), region_code="us-east")
    ingest_result(result_payload(monitor, ok=False), region_code="eu-west")
    monitor.refresh_from_db()
    assert monitor.status == MonitorStatus.UP  # only one region down

    ingest_result(result_payload(monitor, ok=False), region_code="us-east")
    monitor.refresh_from_db()
    assert monitor.status == MonitorStatus.DOWN


def test_ssl_expiry_opens_and_resolves_event(monitor):
    monitor.ssl_expiry_threshold_days = 14
    monitor.save()

    expiring = timezone.now() + timedelta(days=5)
    ingest_result(
        result_payload(monitor, ssl_days_left=5, ssl_expires_at=expiring.isoformat()),
        region_code="eu-west",
    )
    event = AlertEvent.objects.get(event_type=AlertEvent.Type.SSL_EXPIRY)
    assert event.status == AlertEvent.Status.OPEN

    renewed = timezone.now() + timedelta(days=90)
    ingest_result(
        result_payload(monitor, ssl_days_left=90, ssl_expires_at=renewed.isoformat()),
        region_code="eu-west",
    )
    event.refresh_from_db()
    assert event.status == AlertEvent.Status.RESOLVED


def test_result_for_deleted_monitor_is_dropped(monitor):
    payload = result_payload(monitor)
    monitor.delete()
    assert ingest_result(payload, region_code="eu-west") is None
    assert CheckResult.objects.count() == 0


def test_monitor_stats_uptime(monitor):
    for ok in [True, True, True, False]:
        ingest_result(result_payload(monitor, ok=ok), region_code="eu-west")

    stats = monitor_stats(monitor)
    assert stats["uptime"]["24h"]["total_checks"] == 4
    assert stats["uptime"]["24h"]["uptime_pct"] == 75.0
    assert stats["regions"][0]["region"] == "eu-west"
