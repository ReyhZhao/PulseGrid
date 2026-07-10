import uuid

from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Organization(models.Model):
    """Tenant boundary: every monitor, channel and alert belongs to an org."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @classmethod
    def create_for_user(cls, user):
        base = slugify(user.username or user.email or "org") or "org"
        slug = base
        suffix = 1
        while cls.objects.filter(slug=slug).exists():
            suffix += 1
            slug = f"{base}-{suffix}"
        org = cls.objects.create(name=f"{user.username or user.email}", slug=slug)
        Membership.objects.create(organization=org, user=user, role=Membership.Role.OWNER)
        return org


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner"
        MEMBER = "member"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("organization", "user")]

    def __str__(self):
        return f"{self.user} @ {self.organization} ({self.role})"
