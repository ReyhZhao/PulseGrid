from rest_framework import permissions

from .models import Membership


def user_organization_ids(user):
    """Organization ids a Django user holds a Membership in."""
    return Membership.objects.filter(user=user).values_list("organization_id", flat=True)


def api_token_principal(request):
    """The `ApiToken` behind this request, or None when the caller is a user
    (or another kind of machine principal, e.g. a worker)."""
    # Imported lazily: apps.apitokens.models imports apps.accounts.models, so a
    # module-level import here would run during app loading.
    from apps.apitokens.models import ApiToken

    auth = getattr(request, "auth", None)
    return auth if isinstance(auth, ApiToken) else None


def organization_ids(request):
    """Organization ids visible to whichever principal made this request.

    One implementation for every tenant-scoped queryset: a logged-in user sees
    the orgs they are a member of, a `pgr_` API token sees exactly the single
    org it was issued for.
    """
    token = api_token_principal(request)
    if token is not None:
        return [token.organization_id]
    return user_organization_ids(request.user)


class IsOrganizationMember(permissions.IsAuthenticated):
    """Requires login, plus an object-level guard for any model with an
    `organization` FK (or a `monitor.organization` path).

    An `ApiToken` is not a Django user, so it fails `IsAuthenticated`. It is
    admitted here instead — and only for safe methods. That makes this the one
    place read-only is enforced for token principals, rather than something
    each viewset has to remember to opt out of.
    """

    def has_permission(self, request, view):
        if api_token_principal(request) is not None:
            return request.method in permissions.SAFE_METHODS
        return super().has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        org_id = getattr(obj, "organization_id", None)
        if org_id is None and hasattr(obj, "monitor"):
            org_id = obj.monitor.organization_id
        token = api_token_principal(request)
        if token is not None:
            return request.method in permissions.SAFE_METHODS and org_id == token.organization_id
        return Membership.objects.filter(user=request.user, organization_id=org_id).exists()
