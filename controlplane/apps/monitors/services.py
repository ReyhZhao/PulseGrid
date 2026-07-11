"""
Result ingestion and monitor state transitions.

Workers post batches of results; `ingest_result` records each one, updates
the per-region rolling state, recomputes the monitor's overall status and
opens/resolves alert events (which enqueues notifications).
"""

import logging
from datetime import UTC, timedelta

from django.db import connection, transaction
from django.db.models import Avg, Count, Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.alerts.models import AlertEvent
from apps.alerts.services import open_event, resolve_event

from .models import CheckResult, Monitor, MonitorRegionState, MonitorStatus

logger = logging.getLogger(__name__)


def _locked(queryset):
    """Row-lock on PostgreSQL; no-op on SQLite which lacks FOR UPDATE."""
    if connection.features.has_select_for_update:
        return queryset.select_for_update()
    return queryset


@transaction.atomic
def ingest_result(payload: dict, region_code: str) -> CheckResult | None:
    """Persist one worker-reported result and apply state transitions.

    `region_code` comes from the authenticated worker, never the payload.
    Returns None when the referenced monitor no longer exists.
    """
    try:
        monitor = _locked(Monitor.objects.all()).get(pk=payload["monitor_id"])
    except (Monitor.DoesNotExist, KeyError, ValueError):
        logger.warning("dropping result for unknown monitor %r", payload.get("monitor_id"))
        return None

    checked_at = parse_datetime(payload.get("checked_at") or "") or timezone.now()
    if timezone.is_naive(checked_at):
        checked_at = checked_at.replace(tzinfo=UTC)

    result = CheckResult.objects.create(
        monitor=monitor,
        region_code=region_code,
        checked_at=checked_at,
        ok=bool(payload.get("ok")),
        latency_ms=payload.get("latency_ms"),
        status_code=payload.get("status_code"),
        error=(payload.get("error") or "")[:5000],
        ssl_expires_at=_parse_optional_dt(payload.get("ssl_expires_at")),
        ssl_days_left=payload.get("ssl_days_left"),
        dns_ms=payload.get("dns_ms"),
        connect_ms=payload.get("connect_ms"),
        tls_ms=payload.get("tls_ms"),
        ttfb_ms=payload.get("ttfb_ms"),
        hop_count=payload.get("hop_count"),
        hops=payload.get("hops") or [],
    )

    state, _ = _locked(MonitorRegionState.objects.all()).get_or_create(
        monitor=monitor, region_code=region_code
    )
    if result.ok:
        state.status = MonitorStatus.UP
        state.consecutive_failures = 0
    else:
        state.consecutive_failures += 1
        if state.consecutive_failures >= monitor.failure_threshold:
            state.status = MonitorStatus.DOWN
    state.last_check_at = checked_at
    state.last_latency_ms = result.latency_ms
    state.last_status_code = result.status_code
    state.last_error = result.error
    if result.ssl_expires_at is not None:
        state.ssl_expires_at = result.ssl_expires_at
        state.ssl_days_left = result.ssl_days_left
    if result.hop_count is not None:
        state.last_hop_count = result.hop_count
    state.save()

    _recompute_monitor_status(monitor, result)
    _apply_ssl_alerting(monitor, result)
    return result


def _parse_optional_dt(value):
    if not value:
        return None
    parsed = parse_datetime(value)
    if parsed and timezone.is_naive(parsed):
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _recompute_monitor_status(monitor: Monitor, result: CheckResult) -> None:
    states = list(monitor.region_states.all())
    regions_down = sum(1 for s in states if s.status == MonitorStatus.DOWN)
    regions_reporting = sum(1 for s in states if s.status != MonitorStatus.UNKNOWN)

    if regions_reporting == 0:
        return

    required = min(monitor.confirmations, max(len(monitor.effective_regions()), 1))
    new_status = MonitorStatus.DOWN if regions_down >= required else MonitorStatus.UP

    if new_status == monitor.status:
        return

    previous = monitor.status
    monitor.status = new_status
    monitor.status_changed_at = timezone.now()
    monitor.save(update_fields=["status", "status_changed_at"])

    if new_status == MonitorStatus.DOWN:
        open_event(
            monitor,
            AlertEvent.Type.DOWN,
            summary=f"{monitor.name} is DOWN",
            details={
                "regions_down": regions_down,
                "error": result.error,
                "status_code": result.status_code,
            },
        )
    elif previous == MonitorStatus.DOWN:
        resolve_event(monitor, AlertEvent.Type.DOWN, summary=f"{monitor.name} is UP again")


def _apply_ssl_alerting(monitor: Monitor, result: CheckResult) -> None:
    threshold = monitor.ssl_expiry_threshold_days
    if not threshold or result.ssl_days_left is None:
        return
    if result.ssl_days_left <= threshold:
        open_event(
            monitor,
            AlertEvent.Type.SSL_EXPIRY,
            summary=(
                f"TLS certificate for {monitor.name} expires in {result.ssl_days_left} day(s)"
            ),
            details={
                "ssl_days_left": result.ssl_days_left,
                "ssl_expires_at": result.ssl_expires_at.isoformat() if result.ssl_expires_at else None,
            },
        )
    else:
        resolve_event(
            monitor,
            AlertEvent.Type.SSL_EXPIRY,
            summary=f"TLS certificate for {monitor.name} renewed",
        )


UPTIME_WINDOWS = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}


def monitor_stats(monitor: Monitor) -> dict:
    now = timezone.now()
    uptime = {}
    for label, delta in UPTIME_WINDOWS.items():
        agg = monitor.results.filter(checked_at__gte=now - delta).aggregate(
            total=Count("id"),
            up=Count("id", filter=Q(ok=True)),
            avg_latency=Avg("latency_ms", filter=Q(ok=True)),
        )
        uptime[label] = {
            "total_checks": agg["total"],
            "uptime_pct": round(agg["up"] / agg["total"] * 100, 3) if agg["total"] else None,
            "avg_latency_ms": round(agg["avg_latency"], 1) if agg["avg_latency"] is not None else None,
        }

    regions = [
        {
            "region": s.region_code,
            "status": s.status,
            "last_check_at": s.last_check_at,
            "last_latency_ms": s.last_latency_ms,
            "last_status_code": s.last_status_code,
            "last_error": s.last_error,
            "consecutive_failures": s.consecutive_failures,
            "ssl_days_left": s.ssl_days_left,
            "ssl_expires_at": s.ssl_expires_at,
            "last_hop_count": s.last_hop_count,
        }
        for s in monitor.region_states.order_by("region_code")
    ]

    return {
        "status": monitor.status,
        "status_changed_at": monitor.status_changed_at,
        "uptime": uptime,
        "regions": regions,
    }
