"""Web push (VAPID) delivery.

Turns an alert event into a self-contained notification payload and fans it
out to every registered browser/device of the channel's recipients. Runs in
the dispatcher process, like the other channel deliveries.
"""

import json
import logging

from django.conf import settings
from pywebpush import WebPushException, webpush

from apps.accounts.models import Membership

from .models import AlertEvent, PushDelivery, PushSubscription

logger = logging.getLogger(__name__)


def event_payload(event: AlertEvent, kind: str) -> dict:
    """Everything the service worker needs to render a useful notification
    without calling back: headline, human-readable body and the structured
    alert/monitor fields."""
    monitor = event.monitor
    details = event.details or {}
    error = details.get("error", "")
    resolution = details.get("resolution", "")

    if kind == "resolved":
        title = f"✅ PulseGrid resolved: {event.summary}"
        body_lines = [resolution or event.summary]
    else:
        title = f"🔴 PulseGrid alert: {event.summary}"
        body_lines = [event.summary]
        if error:
            body_lines.append(f"Error: {error}")
        if details.get("regions_down"):
            body_lines.append(f"Regions affected: {details['regions_down']}")
        if details.get("ssl_days_left") is not None:
            body_lines.append(f"Certificate expires in {details['ssl_days_left']} days")
    body_lines.append(f"Monitor: {monitor.name} ({monitor.target})")

    return {
        "title": title,
        "body": "\n".join(body_lines),
        "url": "/alerts",
        "alert": {
            "id": event.id,
            "event_type": event.event_type,
            "status": event.status,
            "kind": kind,
            "summary": event.summary,
            "error": error,
            "resolution": resolution,
            "details": details,
            "opened_at": event.opened_at.isoformat() if event.opened_at else None,
            "resolved_at": event.resolved_at.isoformat() if event.resolved_at else None,
        },
        "monitor": {
            "id": str(monitor.id),
            "name": monitor.name,
            "target": monitor.target,
            "status": monitor.status,
        },
    }


def send_to_user(user_id: int, payload: dict) -> int:
    """Push `payload` to every subscription of one user; returns deliveries.

    Subscriptions rejected as gone (404/410) are pruned; other per-device
    errors are logged and skipped so one dead browser can't block the rest.
    """
    if not settings.VAPID_PRIVATE_KEY:
        raise ValueError("web push is not configured (VAPID_PRIVATE_KEY is empty)")

    data = json.dumps(payload)
    delivered = 0
    stale: list[int] = []
    for subscription in PushSubscription.objects.filter(user_id=user_id):
        try:
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
                },
                data=data,
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={"sub": settings.VAPID_SUBJECT},
            )
        except WebPushException as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code in (404, 410):
                stale.append(subscription.pk)
            else:
                logger.warning("web push to subscription %s failed: %s", subscription.pk, exc)
        else:
            delivered += 1
    if stale:
        PushSubscription.objects.filter(pk__in=stale).delete()
    return delivered


def send_event(event: AlertEvent, channel, kind: str) -> int:
    """Deliver one alert event to a push channel's recipients.

    Recipients who have left the organization since the channel was
    configured are skipped. Returns the number of users reached.
    """
    configured_ids = channel.config.get("user_ids") or []
    member_ids = set(
        Membership.objects.filter(
            organization=channel.organization, user_id__in=configured_ids
        ).values_list("user_id", flat=True)
    )
    payload = event_payload(event, kind)
    users_reached = 0
    for user_id in configured_ids:
        if user_id not in member_ids:
            continue
        if send_to_user(user_id, payload):
            users_reached += 1
            PushDelivery.objects.create(user_id=user_id, event=event, kind=kind)
    return users_reached
