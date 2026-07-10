import hashlib
import secrets

from django.db import models

from apps.monitors.models import Region


class Worker(models.Model):
    """A monitoring agent deployment. Tokens are stored hashed; the plaintext
    is only shown once when the token is created."""

    name = models.CharField(max_length=200)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name="workers")
    token_hash = models.CharField(max_length=64, unique=True)
    is_active = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    version = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} [{self.region.code}]"

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    @classmethod
    def issue(cls, name: str, region: Region) -> tuple["Worker", str]:
        token = f"pgw_{secrets.token_urlsafe(32)}"
        worker = cls.objects.create(name=name, region=region, token_hash=cls.hash_token(token))
        return worker, token
