from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Organization, UserProfile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_default_organization(sender, instance, created, **kwargs):
    """Every user gets a personal organization (renamed during onboarding)
    and a profile tracking their onboarding progress."""
    if created:
        UserProfile.objects.get_or_create(user=instance)
        if not instance.memberships.exists():
            Organization.create_for_user(instance)
