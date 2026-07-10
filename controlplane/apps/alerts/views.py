from rest_framework import viewsets

from apps.accounts.permissions import IsOrganizationMember, user_organization_ids

from .models import AlertEvent, NotificationChannel
from .serializers import AlertEventSerializer, NotificationChannelSerializer


class NotificationChannelViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationChannelSerializer
    permission_classes = [IsOrganizationMember]

    def get_queryset(self):
        return NotificationChannel.objects.filter(
            organization_id__in=user_organization_ids(self.request.user)
        )


class AlertEventViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AlertEventSerializer
    permission_classes = [IsOrganizationMember]

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
