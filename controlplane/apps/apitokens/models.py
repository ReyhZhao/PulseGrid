import hashlib
import secrets

from django.db import models

from apps.accounts.models import Organization


class ApiToken(models.Model):
    """A read-only, organization-scoped credential for server-to-server API
    consumers (status pages, dashboards, SIEM integrations).

    Deliberately shaped like `workerapi.Worker`: a machine principal is not a
    Django user, so it holds no `Membership` and never shows up in org member
    lists, invitations or push-notification recipients. Tokens are stored
    hashed; the plaintext is only shown once, when the token is issued.
    """

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="api_tokens")
    name = models.CharField(max_length=200)
    token_hash = models.CharField(max_length=64, unique=True)
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} [{self.organization.slug}]"

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    @classmethod
    def issue(cls, name: str, organization: Organization) -> tuple["ApiToken", str]:
        # "pgr_" for read, distinct from the worker "pgw_" prefix, so a leaked
        # string is identifiable on sight and can't be mistaken for a worker
        # credential during incident response.
        token = f"pgr_{secrets.token_urlsafe(32)}"
        api_token = cls.objects.create(
            organization=organization, name=name, token_hash=cls.hash_token(token)
        )
        return api_token, token
