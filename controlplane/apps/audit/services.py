"""
Audit logging pipeline.

`record()` is the single entry point used across the platform. Each call:

1. persists an immutable AuditEvent row (queryable via API/admin),
2. emits a structured JSON line on the `pulsegrid.audit` logger — collect
   this from stdout with a Wazuh agent / your k8s log pipeline,
3. when the event severity is at or above PULSEGRID_MSSP["MIN_SEVERITY"]
   and an MSSP endpoint is configured, enqueues the event for forwarding.

Forwarding runs in the dispatcher process (`manage.py rundispatcher`) via
`forward_event()`, which posts the event to the MSSP alert-ingest API
(POST /api/v2/alerts/, see vels.online docs/alert-ingest-contract.md) so a
slow or unreachable SIEM can never back-pressure request handling.
"""

import json
import logging

import requests
from django.conf import settings

from pulsegrid import queues

from .models import SEVERITY_ORDER, AuditEvent, Severity

audit_logger = logging.getLogger("pulsegrid.audit")
logger = logging.getLogger(__name__)


def _client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def record(
    event_type: str,
    message: str,
    *,
    severity: str = Severity.INFO,
    request=None,
    actor: str = "",
    actor_type: str = "",
    organization=None,
    **metadata,
) -> AuditEvent:
    """Write one audit event. Actor/IP are derived from `request` unless
    given explicitly. Extra kwargs land in the metadata JSON."""
    source_ip = None
    if request is not None:
        # Unwrap DRF requests: touching request.user on the DRF wrapper
        # re-runs authentication, which recurses when we're called from
        # inside an authenticator (e.g. worker token failures).
        request = getattr(request, "_request", request)
        source_ip = _client_ip(request)
        user = getattr(request, "user", None)
        if not actor and user is not None and user.is_authenticated:
            actor = user.get_username()
            actor_type = actor_type or AuditEvent.ActorType.USER
    if not actor_type:
        actor_type = AuditEvent.ActorType.USER if actor else AuditEvent.ActorType.ANONYMOUS

    # keep metadata JSON-safe (UUIDs, datetimes, model instances...)
    metadata = json.loads(json.dumps(metadata, default=str))

    event = AuditEvent.objects.create(
        organization=organization,
        event_type=event_type,
        severity=severity,
        message=message[:500],
        actor=actor[:200],
        actor_type=actor_type,
        source_ip=source_ip,
        metadata=metadata,
    )

    audit_logger.info(
        json.dumps(
            {
                "pulsegrid.audit": True,
                "event.id": event.id,
                "event.type": event_type,
                "event.severity": severity,
                "message": event.message,
                "user.name": actor or None,
                "actor.type": actor_type,
                "source.ip": source_ip,
                "organization": str(organization.id) if organization else None,
                "@timestamp": event.created_at.isoformat(),
                "metadata": metadata,
            }
        )
    )

    mssp = settings.PULSEGRID_MSSP
    if mssp["URL"] and SEVERITY_ORDER[severity] >= SEVERITY_ORDER[mssp["MIN_SEVERITY"]]:
        if not mssp["TOKEN"]:
            _warn_token_missing_once()
        else:
            try:
                queues.push_audit_job(event.id)
            except Exception:
                # Auditing must never break the calling request path.
                logger.exception("failed to enqueue audit event %s for MSSP forwarding", event.id)

    return event


_token_warning_emitted = False


def _warn_token_missing_once() -> None:
    global _token_warning_emitted
    if not _token_warning_emitted:
        _token_warning_emitted = True
        logger.warning(
            "MSSP_URL is configured but MSSP_API_TOKEN is empty — "
            "audit events will NOT be forwarded to the MSSP platform"
        )


def forward_event(event_id: int) -> bool:
    """Deliver one audit event to the MSSP alert-ingest API (v2 contract).
    Returns True when the alert was accepted."""
    mssp = settings.PULSEGRID_MSSP
    if not mssp["URL"]:
        return False
    try:
        event = AuditEvent.objects.select_related("organization").get(pk=event_id)
    except AuditEvent.DoesNotExist:
        logger.warning("dropping MSSP forward for unknown audit event %s", event_id)
        return False

    # v2 requires at least one recognised ECS entity; host.name is always set.
    entities = {"host.name": mssp["HOST_NAME"].lower()}
    if event.actor and event.actor_type == AuditEvent.ActorType.USER:
        entities["user.name"] = event.actor.lower()
    if event.source_ip:
        entities["source.ip"] = event.source_ip.lower()

    payload = {
        "org": mssp["ORG"],
        "source_kind": "external",
        "source_ref": {
            "system": "pulsegrid",
            "audit_event_id": event.id,
            "event_type": event.event_type,
        },
        "title": f"[PulseGrid] {event.message}",
        "description": json.dumps(
            {
                "event_type": event.event_type,
                "actor": event.actor,
                "actor_type": event.actor_type,
                "organization": event.organization.slug if event.organization else None,
                "occurred_at": event.created_at.isoformat(),
                "metadata": event.metadata,
            },
            indent=2,
        ),
        "severity": event.severity,
        "entities": entities,
    }

    response = requests.post(
        f"{mssp['URL'].rstrip('/')}/api/v2/alerts/",
        json=payload,
        headers={"Authorization": f"{mssp['AUTH_SCHEME']} {mssp['TOKEN'].strip()}"},
        timeout=10,
        verify=mssp["VERIFY_SSL"],
    )
    if response.status_code >= 400:
        # Surface the API's own explanation (e.g. DRF's "Invalid token.")
        # before raising — raise_for_status() discards the body.
        logger.error(
            "MSSP alert-ingest rejected audit event %s: HTTP %s — %s",
            event_id,
            response.status_code,
            response.text[:500],
        )
    response.raise_for_status()
    return True
