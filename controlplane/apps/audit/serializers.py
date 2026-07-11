from rest_framework import serializers

from .models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "organization",
            "event_type",
            "severity",
            "message",
            "actor",
            "actor_type",
            "source_ip",
            "metadata",
            "created_at",
        ]
