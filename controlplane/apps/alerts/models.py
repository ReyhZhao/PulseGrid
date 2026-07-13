from django.conf import settings
from django.db import models

from apps.accounts.models import Organization
from apps.monitors.models import Monitor


class PushSubscription(models.Model):
    """One browser/device registered for web push (VAPID) by a user.

    A user can hold several (phone PWA, desktop browser, …). Endpoints are
    globally unique per the Push API, so re-registering re-binds the row.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="push_subscriptions"
    )
    endpoint = models.TextField(unique=True)
    p256dh = models.TextField()
    auth = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"push subscription of {self.user} ({self.endpoint[:40]}…)"


class NotificationChannel(models.Model):
    class Type(models.TextChoices):
        EMAIL = "email"
        WEBHOOK = "webhook"
        PUSH = "push"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="channels")
    name = models.CharField(max_length=200)
    channel_type = models.CharField(max_length=20, choices=Type.choices)
    # email: {"to": ["ops@example.com"]}
    # webhook: {"url": "https://...", "headers": {"X-Token": "..."}}
    # push: {"user_ids": [1, 2]} — org members who receive web push
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


class PushDelivery(models.Model):
    """One alert event pushed to one user (any number of their devices).

    Backs the per-user "alerts received" statistics on the profile page.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="push_deliveries"
    )
    event = models.ForeignKey(AlertEvent, on_delete=models.CASCADE, related_name="push_deliveries")
    kind = models.CharField(max_length=20, default="opened")  # opened | resolved
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "created_at"])]

    def __str__(self):
        return f"push of event {self.event_id} to {self.user}"


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
