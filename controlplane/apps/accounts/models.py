import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class Organization(models.Model):
    """Tenant boundary: every monitor, channel and alert belongs to an org."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    # Disabled by a platform admin: monitors stop being scheduled, data stays.
    is_active = models.BooleanField(default=True)
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


class UserProfile(models.Model):
    """Per-user platform state that doesn't belong on the auth user."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    # Null until the user finishes the first-login onboarding wizard.
    onboarded_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"profile of {self.user}"


def _invitation_token() -> str:
    return secrets.token_urlsafe(24)


def _invitation_expiry():
    return timezone.now() + timedelta(days=7)


class OrganizationInvitation(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=Membership.Role.choices, default=Membership.Role.MEMBER)
    token = models.CharField(max_length=64, unique=True, default=_invitation_token)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="sent_invitations"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=_invitation_expiry)
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"invite {self.email} -> {self.organization} ({self.role})"

    def is_pending(self) -> bool:
        return self.accepted_at is None and self.expires_at > timezone.now()
