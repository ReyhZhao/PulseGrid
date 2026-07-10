from django.db import models

from apps.accounts.models import Organization
from apps.monitors.models import Monitor


class NotificationChannel(models.Model):
    class Type(models.TextChoices):
        EMAIL = "email"
        WEBHOOK = "webhook"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="channels")
    name = models.CharField(max_length=200)
    channel_type = models.CharField(max_length=20, choices=Type.choices)
    # email: {"to": ["ops@example.com"]}
    # webhook: {"url": "https://...", "headers": {"X-Token": "..."}}
    config = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.channel_type})"


class AlertEvent(models.Model):
    class Type(models.TextChoices):
        DOWN = "down", "Monitor down"
        SSL_EXPIRY = "ssl_expiry", "Certificate expiring"

    class Status(models.TextChoices):
        OPEN = "open"
        RESOLVED = "resolved"

    monitor = models.ForeignKey(Monitor, on_delete=models.CASCADE, related_name="alert_events")
    event_type = models.CharField(max_length=20, choices=Type.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    summary = models.CharField(max_length=500)
    details = models.JSONField(default=dict, blank=True)
    opened_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-opened_at"]
        indexes = [models.Index(fields=["monitor", "event_type", "status"])]

    def __str__(self):
        return f"{self.summary} [{self.status}]"


class NotificationLog(models.Model):
    class Status(models.TextChoices):
        SENT = "sent"
        FAILED = "failed"

    event = models.ForeignKey(AlertEvent, on_delete=models.CASCADE, related_name="notifications")
    channel = models.ForeignKey(NotificationChannel, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=20, default="opened")  # opened | resolved
    status = models.CharField(max_length=20, choices=Status.choices)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
