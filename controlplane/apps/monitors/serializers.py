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

    def validate(self, attrs):
        monitor_type = attrs.get("monitor_type", getattr(self.instance, "monitor_type", Monitor.Type.HTTP))
        if monitor_type == Monitor.Type.HTTP:
            url = attrs.get("url", getattr(self.instance, "url", ""))
            if not url:
                raise serializers.ValidationError({"url": "Required for HTTP monitors."})
        else:
            host = attrs.get("host", getattr(self.instance, "host", ""))
            port = attrs.get("port", getattr(self.instance, "port", None))
            if not host or not port:
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
        ]
