from rest_framework import authentication, exceptions, permissions

from apps.audit.models import Severity
from apps.audit.services import record as audit

from .models import Worker


class WorkerTokenAuthentication(authentication.BaseAuthentication):
    """Authenticates `Authorization: Bearer pgw_...` and attaches the Worker
    (not a Django user) as `request.auth`."""

    keyword = "bearer"

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).decode()
        if not header:
            return None
        parts = header.split()
        if len(parts) != 2 or parts[0].lower() != self.keyword:
            return None
        worker = Worker.objects.select_related("region").filter(
            token_hash=Worker.hash_token(parts[1]), is_active=True
        ).first()
        if worker is None:
            audit(
                "worker.auth_failed",
                "Worker API request with an invalid or inactive token",
                severity=Severity.HIGH,
                request=request,
                actor_type="worker",
                path=request.path,
            )
            raise exceptions.AuthenticationFailed("Invalid or inactive worker token.")
        return (None, worker)

    def authenticate_header(self, request):
        return "Bearer"


class IsWorker(permissions.BasePermission):
    def has_permission(self, request, view):
        return isinstance(request.auth, Worker)
