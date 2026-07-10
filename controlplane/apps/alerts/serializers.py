from rest_framework import serializers

from apps.accounts.models import Membership

from .models import AlertEvent, NotificationChannel


class NotificationChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationChannel
        fields = ["id", "organization", "name", "channel_type", "config", "is_active", "created_at"]
        read_only_fields = ["created_at"]

    def validate_organization(self, org):
        user = self.context["request"].user
        if not Membership.objects.filter(user=user, organization=org).exists():
            raise serializers.ValidationError("You are not a member of this organization.")
        return org

    def validate(self, attrs):
        channel_type = attrs.get(
            "channel_type", getattr(self.instance, "channel_type", NotificationChannel.Type.EMAIL)
        )
        config = attrs.get("config", getattr(self.instance, "config", {}))
        if channel_type == NotificationChannel.Type.EMAIL:
            to = config.get("to")
            if not isinstance(to, list) or not to:
                raise serializers.ValidationError(
                    {"config": "Email channels need config.to = [address, ...]"}
                )
        elif channel_type == NotificationChannel.Type.WEBHOOK:
            url = config.get("url", "")
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                raise serializers.ValidationError({"config": "Webhook channels need config.url"})
        return attrs


class AlertEventSerializer(serializers.ModelSerializer):
    monitor_name = serializers.CharField(source="monitor.name", read_only=True)

    class Meta:
        model = AlertEvent
        fields = [
            "id",
            "monitor",
            "monitor_name",
            "event_type",
            "status",
            "summary",
            "details",
            "opened_at",
            "resolved_at",
        ]
