from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import viewsets

from apps.accounts.permissions import user_organization_ids

from .models import AuditEvent
from .serializers import AuditEventSerializer


@extend_schema(tags=["audit"])
@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter("event_type", OpenApiTypes.STR, description="Filter by event type."),
            OpenApiParameter("severity", OpenApiTypes.STR, description="Filter by severity."),
        ]
    ),
)
class AuditEventViewSet(viewsets.ReadOnlyModelViewSet):
    """Org-scoped audit trail. Platform-level events (organization=null,
    e.g. worker auth failures) are visible only in the Django admin."""

    serializer_class = AuditEventSerializer
    queryset = AuditEvent.objects.none()

    def get_queryset(self):
        qs = AuditEvent.objects.filter(organization_id__in=user_organization_ids(self.request.user))
        event_type = self.request.query_params.get("event_type")
        if event_type:
            qs = qs.filter(event_type=event_type)
        severity = self.request.query_params.get("severity")
        if severity:
            qs = qs.filter(severity=severity)
        return qs
