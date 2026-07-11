from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import viewsets

from apps.accounts.permissions import IsOrganizationMember, user_organization_ids
from apps.audit.models import Severity
from apps.audit.services import record as audit

from .models import AlertEvent, NotificationChannel
from .serializers import AlertEventSerializer, NotificationChannelSerializer


@extend_schema(tags=["alerts"])
class NotificationChannelViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationChannelSerializer
    permission_classes = [IsOrganizationMember]
    queryset = NotificationChannel.objects.none()

    def get_queryset(self):
        return NotificationChannel.objects.filter(
            organization_id__in=user_organization_ids(self.request.user)
        )

    # Notification channels are an exfiltration vector (alert contents get
    # sent to them), so every change is audited at medium severity.
    def perform_create(self, serializer):
        channel = serializer.save()
        audit(
            "channel.created",
            f"Notification channel '{channel.name}' ({channel.channel_type}) created",
            severity=Severity.MEDIUM,
            request=self.request,
            organization=channel.organization,
            channel_id=channel.id,
            channel_type=channel.channel_type,
        )

    def perform_update(self, serializer):
        channel = serializer.save()
        audit(
            "channel.updated",
            f"Notification channel '{channel.name}' updated",
            severity=Severity.MEDIUM,
            request=self.request,
            organization=channel.organization,
            channel_id=channel.id,
        )

    def perform_destroy(self, instance):
        audit(
            "channel.deleted",
            f"Notification channel '{instance.name}' deleted",
            severity=Severity.MEDIUM,
            request=self.request,
            organization=instance.organization,
            channel_id=instance.id,
        )
        instance.delete()


@extend_schema(tags=["alerts"])
@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter("monitor", OpenApiTypes.INT, description="Filter to a single monitor id."),
            OpenApiParameter("status", OpenApiTypes.STR, description="Filter by alert status."),
        ]
    ),
)
class AlertEventViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AlertEventSerializer
    permission_classes = [IsOrganizationMember]
    queryset = AlertEvent.objects.none()

    def get_queryset(self):
        qs = AlertEvent.objects.filter(
            monitor__organization_id__in=user_organization_ids(self.request.user)
        ).select_related("monitor")
        monitor = self.request.query_params.get("monitor")
        if monitor:
            qs = qs.filter(monitor_id=monitor)
        status = self.request.query_params.get("status")
        if status:
            qs = qs.filter(status=status)
        return qs
