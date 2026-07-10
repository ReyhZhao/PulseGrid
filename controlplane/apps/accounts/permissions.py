from rest_framework import permissions

from .models import Membership


def user_organization_ids(user):
    return Membership.objects.filter(user=user).values_list("organization_id", flat=True)


class IsOrganizationMember(permissions.IsAuthenticated):
    """Requires login, plus an object-level guard for any model with an
    `organization` FK (or a `monitor.organization` path)."""

    def has_object_permission(self, request, view, obj):
        org_id = getattr(obj, "organization_id", None)
        if org_id is None and hasattr(obj, "monitor"):
            org_id = obj.monitor.organization_id
        return Membership.objects.filter(user=request.user, organization_id=org_id).exists()
