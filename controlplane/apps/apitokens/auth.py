from django.utils import timezone
from rest_framework import authentication, exceptions

from apps.audit.models import AuditEvent, Severity
from apps.audit.services import record as audit

from .models import ApiToken


class ReadTokenAuthentication(authentication.BaseAuthentication):
    """Authenticates `Authorization: Bearer pgr_...` and attaches the ApiToken
    (not a Django user) as `request.auth`.

    Read-only is *not* enforced here — it is enforced once, in
    `apps.accounts.permissions.IsOrganizationMember`, so no viewset can forget
    to opt out of token writes.
    """

    keyword = "bearer"

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).decode()
        if not header:
            return None
        parts = header.split()
        if len(parts) != 2 or parts[0].lower() != self.keyword:
            return None
        token = ApiToken.objects.filter(
            token_hash=ApiToken.hash_token(parts[1]), is_active=True
        ).first()
        if token is None:
            # Credential probing must be visible, exactly as for worker tokens.
            audit(
                "api_token.auth_failed",
                "API request with an invalid or inactive read token",
                severity=Severity.HIGH,
                request=request,
                actor_type=AuditEvent.ActorType.API_TOKEN,
                path=request.path,
            )
            raise exceptions.AuthenticationFailed("Invalid or inactive API token.")
        # update() rather than save() so a read request never races another
        # process writing the same row.
        ApiToken.objects.filter(pk=token.pk).update(last_used_at=timezone.now())
        return (None, token)

    def authenticate_header(self, request):
        return "Bearer"
