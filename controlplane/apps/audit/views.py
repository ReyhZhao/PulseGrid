from rest_framework import viewsets

from apps.accounts.permissions import user_organization_ids

from .models import AuditEvent
from .serializers import AuditEventSerializer


class AuditEventViewSet(viewsets.ReadOnlyModelViewSet):
    """Org-scoped audit trail. Platform-level events (organization=null,
    e.g. worker auth failures) are visible only in the Django admin."""

    serializer_class = AuditEventSerializer

    def get_queryset(self):
        qs = AuditEvent.objects.filter(organization_id__in=user_organization_ids(self.request.user))
        event_type = self.request.query_params.get("event_type")
        if event_type:
            qs = qs.filter(event_type=event_type)
        severity = self.request.query_params.get("severity")
        if severity:
            qs = qs.filter(severity=severity)
        return qs
