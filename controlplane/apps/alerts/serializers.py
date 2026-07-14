from urllib.parse import urlsplit

from rest_framework import serializers

from apps.accounts.models import Membership
from pulsegrid import netguard

from .models import AlertEvent, NotificationChannel, PushSubscription


class PushSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushSubscription
        fields = ["endpoint", "p256dh", "auth"]
        # endpoint is unique per browser; registration upserts instead of
        # failing, so skip the default unique validator.
        extra_kwargs = {"endpoint": {"validators": []}}


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
            # SSRF guard: the dispatcher will POST here from inside the control
            # plane, so reject internal/metadata destinations up front.
            reason = netguard.blocked_reason(urlsplit(url).hostname or "", block_unresolvable=False)
            if reason is not None:
                raise serializers.ValidationError({"config": f"Webhook url is not allowed: {reason}"})
            headers = config.get("headers")
            if headers is not None and (
                not isinstance(headers, dict)
                or not all(isinstance(k, str) and isinstance(v, str) for k, v in headers.items())
            ):
                raise serializers.ValidationError(
                    {"config": "Webhook headers must be a flat object of string names to string values."}
                )
        elif channel_type == NotificationChannel.Type.PUSH:
            organization = attrs.get("organization", getattr(self.instance, "organization", None))
            user_ids = config.get("user_ids")
            if not isinstance(user_ids, list) or not user_ids or not all(
                isinstance(user_id, int) for user_id in user_ids
            ):
                raise serializers.ValidationError(
                    {"config": "Push channels need config.user_ids = [user id, ...]"}
                )
            members = set(
                Membership.objects.filter(
                    organization=organization, user_id__in=user_ids
                ).values_list("user_id", flat=True)
            )
            outsiders = [user_id for user_id in user_ids if user_id not in members]
            if outsiders:
                raise serializers.ValidationError(
                    {"config": "All recipients must be members of the organization."}
                )
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
