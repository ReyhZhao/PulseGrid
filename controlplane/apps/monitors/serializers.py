import re

from rest_framework import serializers

from apps.accounts.models import Membership

from .models import CheckResult, Monitor, Region

EXPECTED_STATUS_RE = re.compile(r"^\d{3}(-\d{3})?(,\d{3}(-\d{3})?)*$")


class RegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Region
        fields = ["code", "name", "is_active"]


class MonitorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Monitor
        fields = [
            "id",
            "organization",
            "name",
            "monitor_type",
            "url",
            "method",
            "expected_status",
            "keyword",
            "verify_ssl",
            "ssl_expiry_threshold_days",
            "host",
            "port",
            "hop_threshold_min",
            "hop_threshold_max",
            "required_asn",
            "interval_seconds",
            "timeout_seconds",
            "failure_threshold",
            "confirmations",
            "regions",
            "is_paused",
            "status",
            "status_changed_at",
            "created_at",
        ]
        read_only_fields = ["status", "status_changed_at", "created_at"]

    def validate_organization(self, org):
        user = self.context["request"].user
        if not Membership.objects.filter(user=user, organization=org).exists():
            raise serializers.ValidationError("You are not a member of this organization.")
        return org

    def validate_expected_status(self, value):
        value = value.replace(" ", "")
        if not EXPECTED_STATUS_RE.match(value):
            raise serializers.ValidationError(
                "Use comma-separated status codes or ranges, e.g. '200-299,301'."
            )
        return value

    def validate_regions(self, value):
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise serializers.ValidationError("Must be a list of region codes.")
        known = set(Region.objects.filter(is_active=True).values_list("code", flat=True))
        unknown = [code for code in value if code not in known]
        if unknown:
            raise serializers.ValidationError(f"Unknown or inactive region(s): {', '.join(unknown)}")
        return value

    def validate_required_asn(self, value):
        if value is not None and not 1 <= value <= 4294967295:
            raise serializers.ValidationError("AS numbers range from 1 to 4294967295.")
        return value

    def validate(self, attrs):
        def field(name, default=None):
            return attrs.get(name, getattr(self.instance, name, default))

        monitor_type = field("monitor_type", Monitor.Type.HTTP)
        if monitor_type == Monitor.Type.HTTP:
            if not field("url", ""):
                raise serializers.ValidationError({"url": "Required for HTTP monitors."})
        elif monitor_type == Monitor.Type.TRACEROUTE:
            if not field("host", ""):
                raise serializers.ValidationError({"host": "Host is required for traceroute monitors."})
            hop_min, hop_max = field("hop_threshold_min"), field("hop_threshold_max")
            if hop_min is not None and hop_max is not None and hop_min > hop_max:
                raise serializers.ValidationError(
                    {"hop_threshold_min": "Minimum hop threshold cannot exceed the maximum."}
                )
        else:
            if not field("host", "") or not field("port"):
                raise serializers.ValidationError({"host": "Host and port are required for TCP monitors."})
        return attrs


class CheckResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = CheckResult
        fields = [
            "id",
            "region_code",
            "checked_at",
            "ok",
            "latency_ms",
            "status_code",
            "error",
            "ssl_days_left",
            "dns_ms",
            "connect_ms",
            "tls_ms",
            "ttfb_ms",
            "hop_count",
            "hops",
        ]


class PauseStateSerializer(serializers.Serializer):
    """Response of the pause/resume actions."""

    is_paused = serializers.BooleanField()


class _UptimeWindowSerializer(serializers.Serializer):
    total_checks = serializers.IntegerField()
    uptime_pct = serializers.FloatField(allow_null=True)
    avg_latency_ms = serializers.FloatField(allow_null=True)


class _RegionStatSerializer(serializers.Serializer):
    region = serializers.CharField()
    status = serializers.CharField()
    last_check_at = serializers.DateTimeField(allow_null=True)
    last_latency_ms = serializers.IntegerField(allow_null=True)
    last_status_code = serializers.IntegerField(allow_null=True)
    last_error = serializers.CharField(allow_blank=True)
    consecutive_failures = serializers.IntegerField()
    ssl_days_left = serializers.IntegerField(allow_null=True)
    ssl_expires_at = serializers.DateTimeField(allow_null=True)
    last_hop_count = serializers.IntegerField(allow_null=True)


class MonitorStatsSerializer(serializers.Serializer):
    """Aggregate uptime/latency stats for a monitor (see `monitor_stats`)."""

    status = serializers.CharField()
    status_changed_at = serializers.DateTimeField(allow_null=True)
    uptime = serializers.DictField(child=_UptimeWindowSerializer())
    regions = _RegionStatSerializer(many=True)
