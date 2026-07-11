from django.db import models

from apps.accounts.models import Organization


class Severity(models.TextChoices):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


SEVERITY_ORDER = {
    Severity.INFO: 0,
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}


class AuditEvent(models.Model):
    """Immutable security audit trail. Every record is also emitted as a
    structured JSON log line and, above the configured severity, forwarded
    to the MSSP platform (see apps.audit.services)."""

    class ActorType(models.TextChoices):
        USER = "user"
        WORKER = "worker"
        SYSTEM = "system"
        ANONYMOUS = "anonymous"

    # Platform-level events (e.g. failed worker auth) have no organization.
    organization = models.ForeignKey(
        Organization, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_events"
    )
    event_type = models.CharField(max_length=100, db_index=True)  # e.g. "auth.login_failed"
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.INFO)
    message = models.CharField(max_length=500)

    actor = models.CharField(max_length=200, blank=True)
    actor_type = models.CharField(max_length=20, choices=ActorType.choices, default=ActorType.SYSTEM)
    source_ip = models.GenericIPAddressField(null=True, blank=True)

    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["organization", "-created_at"])]

    def __str__(self):
        return f"[{self.severity}] {self.event_type}: {self.message}"
