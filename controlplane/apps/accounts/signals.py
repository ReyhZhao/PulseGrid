from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Organization


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_default_organization(sender, instance, created, **kwargs):
    """Every user gets a personal organization so they can create monitors
    immediately after their first (SSO) login."""
    if created and not instance.memberships.exists():
        Organization.create_for_user(instance)
