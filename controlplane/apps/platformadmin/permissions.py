from rest_framework import permissions


class IsPlatformAdmin(permissions.BasePermission):
    """Grants access to staff and superusers only. Every endpoint under
    /api/v1/admin/ sits behind this check."""

    message = "Platform administrator access required."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))
