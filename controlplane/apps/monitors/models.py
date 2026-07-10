import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.accounts.models import Organization


class Region(models.Model):
    """A monitoring location. Workers are bound to exactly one region."""

    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} ({self.name})"


class MonitorStatus(models.TextChoices):
    UP = "up"
    DOWN = "down"
    UNKNOWN = "unknown"


class Monitor(models.Model):
    class Type(models.TextChoices):
        HTTP = "http", "HTTP(S)"
        TCP = "tcp", "TCP port"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="monitors")
    name = models.CharField(max_length=200)
    monitor_type = models.CharField(max_length=10, choices=Type.choices, default=Type.HTTP)

    # HTTP checks
    url = models.URLField(max_length=2000, blank=True)
    method = models.CharField(max_length=10, default="GET")
    expected_status = models.CharField(
        max_length=100,
        default="200-299",
        help_text="Comma-separated status codes or ranges, e.g. '200-299,301'",
    )
    keyword = models.CharField(max_length=200, blank=True, help_text="Response body must contain this")
    verify_ssl = models.BooleanField(default=True)
    ssl_expiry_threshold_days = models.PositiveIntegerField(
        default=14, help_text="Alert when the certificate expires within this many days; 0 disables"
    )

    # TCP checks
    host = models.CharField(max_length=500, blank=True)
    port = models.PositiveIntegerField(null=True, blank=True)

    interval_seconds = models.PositiveIntegerField(
        default=60, validators=[MinValueValidator(60), MaxValueValidator(86400)]
    )
    timeout_seconds = models.PositiveIntegerField(
        default=30, validators=[MinValueValidator(1), MaxValueValidator(120)]
    )
    # Consecutive failures in a region before that region counts as down.
    failure_threshold = models.PositiveIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    # Regions that must be down before the monitor (and alerting) goes down.
    confirmations = models.PositiveIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    # Region codes to check from; empty list means "all active regions".
    regions = models.JSONField(default=list, blank=True)

    is_paused = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=MonitorStatus.choices, default=MonitorStatus.UNKNOWN)
    status_changed_at = models.DateTimeField(null=True, blank=True)
    next_check_at = models.DateTimeField(default=timezone.now, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["organization", "status"])]

    def __str__(self):
        return self.name

    @property
    def target(self) -> str:
        if self.monitor_type == self.Type.TCP:
            return f"{self.host}:{self.port}"
        return self.url

    def effective_regions(self) -> list[str]:
        active = list(Region.objects.filter(is_active=True).values_list("code", flat=True))
        if not self.regions:
            return active
        return [code for code in self.regions if code in active]

    def to_check_task(self, region_code: str, scheduled_at) -> dict:
        task = {
            "task_id": str(uuid.uuid4()),
            "monitor_id": str(self.id),
            "region": region_code,
            "type": self.monitor_type,
            "timeout": self.timeout_seconds,
            "interval": self.interval_seconds,
            "scheduled_at": scheduled_at.isoformat(),
        }
        if self.monitor_type == self.Type.HTTP:
            task.update(
                {
                    "url": self.url,
                    "method": self.method,
                    "expected_status": self.expected_status,
                    "keyword": self.keyword,
                    "verify_ssl": self.verify_ssl,
                }
            )
        else:
            task.update({"host": self.host, "port": self.port})
        return task


class MonitorRegionState(models.Model):
    """Rolling per-region view of a monitor, updated on every result."""

    monitor = models.ForeignKey(Monitor, on_delete=models.CASCADE, related_name="region_states")
    region_code = models.SlugField(max_length=50)

    status = models.CharField(max_length=10, choices=MonitorStatus.choices, default=MonitorStatus.UNKNOWN)
    consecutive_failures = models.PositiveIntegerField(default=0)
    last_check_at = models.DateTimeField(null=True, blank=True)
    last_latency_ms = models.FloatField(null=True, blank=True)
    last_status_code = models.PositiveIntegerField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    ssl_expires_at = models.DateTimeField(null=True, blank=True)
    ssl_days_left = models.IntegerField(null=True, blank=True)

    class Meta:
        unique_together = [("monitor", "region_code")]

    def __str__(self):
        return f"{self.monitor} [{self.region_code}] {self.status}"


class CheckResult(models.Model):
    """One executed check from one region. High-volume, append-only."""

    monitor = models.ForeignKey(Monitor, on_delete=models.CASCADE, related_name="results")
    region_code = models.SlugField(max_length=50)
    checked_at = models.DateTimeField()

    ok = models.BooleanField()
    latency_ms = models.FloatField(null=True, blank=True)
    status_code = models.PositiveIntegerField(null=True, blank=True)
    error = models.TextField(blank=True)

    ssl_expires_at = models.DateTimeField(null=True, blank=True)
    ssl_days_left = models.IntegerField(null=True, blank=True)

    dns_ms = models.FloatField(null=True, blank=True)
    connect_ms = models.FloatField(null=True, blank=True)
    tls_ms = models.FloatField(null=True, blank=True)
    ttfb_ms = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["-checked_at"]
        indexes = [
            models.Index(fields=["monitor", "-checked_at"]),
            models.Index(fields=["checked_at"]),
        ]

    def __str__(self):
        return f"{self.monitor} [{self.region_code}] {'up' if self.ok else 'down'} @ {self.checked_at}"
