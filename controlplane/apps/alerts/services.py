"""
Alert lifecycle + notification delivery.

`open_event` / `resolve_event` are called from result ingestion inside its
transaction; they only enqueue a notification job. The actual delivery
(email/webhook) happens out-of-band in the dispatcher process
(`manage.py rundispatcher`), so a slow SMTP server can never back-pressure
result ingestion.
"""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from pulsegrid import queues

from .models import AlertEvent, NotificationChannel, NotificationLog

logger = logging.getLogger(__name__)


def open_event(monitor, event_type: str, summary: str, details: dict | None = None) -> AlertEvent | None:
    """Open an alert event unless one of this type is already open."""
    if AlertEvent.objects.filter(
        monitor=monitor, event_type=event_type, status=AlertEvent.Status.OPEN
    ).exists():
        return None
    event = AlertEvent.objects.create(
        monitor=monitor, event_type=event_type, summary=summary, details=details or {}
    )
    queues.push_notification(event.id)

    from apps.audit.models import Severity
    from apps.audit.services import record as audit

    audit(
        "monitor.alert_opened",
        summary,
        severity=Severity.MEDIUM if event_type == AlertEvent.Type.DOWN else Severity.LOW,
        actor="scheduler",
        actor_type="system",
        organization=monitor.organization,
        monitor_id=monitor.id,
        alert_event_id=event.id,
        alert_type=event_type,
    )
    return event


def resolve_event(monitor, event_type: str, summary: str) -> AlertEvent | None:
    event = (
        AlertEvent.objects.filter(monitor=monitor, event_type=event_type, status=AlertEvent.Status.OPEN)
        .order_by("-opened_at")
        .first()
    )
    if event is None:
        return None
    event.status = AlertEvent.Status.RESOLVED
    event.resolved_at = timezone.now()
    event.details = {**event.details, "resolution": summary}
    event.save(update_fields=["status", "resolved_at", "details"])
    queues.push_notification(event.id)
    return event


def dispatch_event(event_id: int) -> int:
    """Deliver one queued alert event to all active channels of its org.

    Returns the number of successful deliveries. Called by the dispatcher.
    """
    try:
        event = AlertEvent.objects.select_related("monitor__organization").get(pk=event_id)
    except AlertEvent.DoesNotExist:
        logger.warning("dropping notification for unknown event %s", event_id)
        return 0

    kind = "resolved" if event.status == AlertEvent.Status.RESOLVED else "opened"
    channels = NotificationChannel.objects.filter(
        organization=event.monitor.organization, is_active=True
    )
    sent = 0
    for channel in channels:
        try:
            _deliver(event, channel, kind)
        except Exception as exc:
            logger.exception("delivery to channel %s failed", channel.id)
            NotificationLog.objects.create(
                event=event,
                channel=channel,
                kind=kind,
                status=NotificationLog.Status.FAILED,
                error=str(exc)[:2000],
            )
        else:
            sent += 1
            NotificationLog.objects.create(
                event=event, channel=channel, kind=kind, status=NotificationLog.Status.SENT
            )
    return sent


def _deliver(event: AlertEvent, channel: NotificationChannel, kind: str) -> None:
    monitor = event.monitor
    if kind == "resolved":
        subject = f"[PulseGrid] RESOLVED: {event.summary}"
        body_intro = event.details.get("resolution", event.summary)
    else:
        subject = f"[PulseGrid] ALERT: {event.summary}"
        body_intro = event.summary

    if channel.channel_type == NotificationChannel.Type.EMAIL:
        recipients = channel.config.get("to") or []
        if not recipients:
            raise ValueError("email channel has no recipients configured")
        body = (
            f"{body_intro}\n\n"
            f"Monitor: {monitor.name}\n"
            f"Target: {monitor.target}\n"
            f"Status: {monitor.status}\n"
            f"Event: {event.event_type} ({kind})\n"
            f"At: {timezone.now().isoformat()}\n"
        )
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, recipients)
    elif channel.channel_type == NotificationChannel.Type.WEBHOOK:
        import requests

        url = channel.config.get("url")
        if not url:
            raise ValueError("webhook channel has no url configured")
        payload = {
            "event_id": event.id,
            "event_type": event.event_type,
            "kind": kind,
            "summary": event.summary,
            "details": event.details,
            "monitor": {
                "id": str(monitor.id),
                "name": monitor.name,
                "target": monitor.target,
                "status": monitor.status,
            },
            "organization": str(monitor.organization_id),
        }
        response = requests.post(
            url, json=payload, headers=channel.config.get("headers") or {}, timeout=10
        )
        response.raise_for_status()
    else:  # pragma: no cover - guarded by model choices
        raise ValueError(f"unsupported channel type {channel.channel_type}")
